#!/usr/bin/env python

# MY CODEEEE
#%%
## Hyperalignment is run with PyMVPA2 (now compatible with Python 3.9+)
# All analyses use Python 3

import os
import sys

import tempfile
TMPDIR = tempfile.gettempdir()  # Uses system temp directory
os.environ['TMPDIR'] = TMPDIR
os.environ['TEMP'] = TMPDIR
os.environ['TMP'] = TMPDIR

# Set environment variable to suppress warnings
os.environ['PYTHONWARNINGS'] = 'ignore::DeprecationWarning'

import warnings
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*np.float.*")
warnings.filterwarnings("ignore", message=".*deprecated alias.*")
warnings.filterwarnings("ignore", message=".*pixdim.*")

# Suppress nibabel warnings
import logging
logging.getLogger('nibabel').setLevel(logging.ERROR)

import numpy as np

# Patch numpy to prevent the warnings at the source
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int

# Consolidated imports (moved to top so all functions can use them)
import glob
import time
import multiprocessing as mp
from scipy.stats import zscore
import contextlib
from io import StringIO
import nibabel as nib
import random

@contextlib.contextmanager
def suppress_stderr():
    with open(os.devnull, "w") as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

# Import mvpa2 with suppressed stderr
with suppress_stderr():
    from mvpa2.algorithms.hyperalignment import Hyperalignment
    from mvpa2.datasets import Dataset
    from mvpa2.base import debug

# Import centralized configuration (Python 2 compatible)
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_config import (
    POOL_NUM, N_JOBS, VERTICES_IN_BOUNDS, N_PARCELS,
    DTSERIES_ROOT, PTSERIES_ROOT, BASE_OUTDIR, TEMPORARY_OUTDIR,
    PARCELLATION_FILE, DTSERIES_FILENAME_TEMPLATE, DTSERIES_FILENAME_PATTERN,
    pool_num, n_jobs  # lowercase aliases for backward compatibility
)
import utils

# For backwards compatibility with existing code
BASE_CONNECTOME_DIR = BASE_OUTDIR
ATLAS_FILE = PARCELLATION_FILE
DTSERIES_PATTERN = os.path.join(DTSERIES_ROOT, DTSERIES_FILENAME_PATTERN)

# Suppress warnings during Dataset creation
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    empty_dataset = Dataset(np.empty((1, VERTICES_IN_BOUNDS)))

# Load Glasser atlas (use centralized ATLAS_FILE)
def load_glasser_atlas():
    g = nib.load(ATLAS_FILE)
    return g.get_fdata().T


# Loads in pre-computed connectomes for each subject, each parcel, and formats training hyperalignment.
def prep_cnx(args):
    subject, connectome_dir, current_parcel = args
    fn = connectome_dir + '/{a}_full_connectome_parcel_{i:03d}.npy'.format(a=subject, i=current_parcel)
    if not os.path.exists(fn):
        raise FileNotFoundError("Connectome file not found: {}".format(fn))
    
    d = np.nan_to_num(zscore(np.load(fn)))
    
    # Suppress warnings during Dataset creation
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ds_train = Dataset(d)
    
    # Use centralized parcel constant
    ds_train.sa['targets'] = np.arange(1, N_PARCELS)
    ds_train.fa['seeds'] = np.where(glasser_atlas == current_parcel)[0]
    return ds_train


# NEW: Loads in pre-computed split-half connectomes for each subject, each parcel, and formats for hyperalignment.
def prep_cnx_split(args):
    subject, split, connectome_dir, current_parcel = args
    fn = connectome_dir + '/{a}_split_{split}_connectome_parcel_{i:03d}.npy'.format(a=subject, split=split, i=current_parcel)
    if not os.path.exists(fn):
        raise FileNotFoundError("Split connectome file not found: {}".format(fn))

    d = np.nan_to_num(zscore(np.load(fn)))

    # Suppress warnings during Dataset creation
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ds_train = Dataset(d)

    ds_train.sa['targets'] = np.arange(1, N_PARCELS)
    ds_train.fa['seeds'] = np.where(glasser_atlas == current_parcel)[0]
    return ds_train

# Simplified dtseries loader: always load GSR dtseries (uses top-level nib)
def load_dtseries_data(subj_id, parcel=None):
    """Load dtseries data from the GSR dataset (Python 2 version)."""
    dtseries_root = DTSERIES_ROOT
    filename = DTSERIES_FILENAME_TEMPLATE.format(subj=subj_id)
    ds = nib.load(os.path.join(dtseries_root, filename)).get_fdata()[:, :VERTICES_IN_BOUNDS]
    if parcel:
        mask = (glasser_atlas == parcel).squeeze()
        return zscore(ds[:, mask], axis=0)
    return zscore(ds, axis=0)

# Helper to centralize output directory construction
def setup_output_dirs(base_connectome_dir, parcel):
    train_connectome_dir = os.path.join(base_connectome_dir, 'fine', 'parcel_{:03d}'.format(parcel))
    mapper_base = os.path.join(base_connectome_dir, 'hyperalignment_output')
    mapper_dir = os.path.join(mapper_base, 'mappers', 'parcel_{:03d}'.format(parcel))
    aligned_dir = os.path.join(mapper_base, 'aligned_timeseries', 'parcel_{:03d}'.format(parcel))
    return train_connectome_dir, mapper_dir, aligned_dir

# Loads and shapes the vertex-wise timeseries for this parcel for testing subjects
def prep_dtseries(args):
    subject, current_parcel, split = args
    d = load_dtseries_data(subject, parcel=current_parcel)

    if split is not None:  # Choose if this is either the first or the second half of the dataset
        half = d.shape[0] // 2
        start = split * half
        tpts_in_bounds = np.arange(start, start + half)
        d = d[tpts_in_bounds]

    return zscore(d, axis=0)

# Ensure apply_mappers canonical definition exists
def apply_mappers(args):
    data_out_fn, mapper_out_fn, subject, mapper, current_parcel, split = args
    try:
        dtseries = prep_dtseries((subject, current_parcel, split))
        aligned = zscore((np.asmatrix(dtseries) * mapper._proj).A, axis=0)
        np.save(data_out_fn, aligned)
        np.save(mapper_out_fn, mapper._proj)
        print("Successfully processed subject {} (split: {})".format(subject, split))
    except Exception as e:
        print("Error processing subject {} (split: {}): {}".format(subject, split, e))

# NEW: Apply hyperalignment mappers from split-half analysis
def apply_mappers_split(args):
    data_out_fn, mapper_fn, subject, mapper0, mapper1, current_parcel = args
    try:
        dtseries0 = prep_dtseries((subject, current_parcel, 0))
        dtseries1 = prep_dtseries((subject, current_parcel, 1))

        aligned0 = zscore((np.asmatrix(dtseries0) * mapper0._proj).A, axis=0)
        aligned1 = zscore((np.asmatrix(dtseries1) * mapper1._proj).A, axis=0)

        # Save aligned splits and mapper projections
        np.save(data_out_fn + '_0.npy', aligned0)
        np.save(data_out_fn + '_1.npy', aligned1)
        np.save(mapper_fn + '_0.npy', mapper0._proj)
        np.save(mapper_fn + '_1.npy', mapper1._proj)

        print("Successfully processed split data for subject {}".format(subject))
    except Exception as e:
        print("Error processing split data for subject {}: {}".format(subject, e))
        return
    

# runs the hyperalignment pipeline for the full timeseries data    
def drive_hyperalignment_full(train_subjects, test_subjects, connectome_dir, mapper_dir, aligned_dir, current_parcel):
    t0 = time.time()
    print("Starting hyperalignment for parcel {}".format(current_parcel))
    print("Training subjects: {}".format(len(train_subjects)))
    print("Test subjects: {}".format(len(test_subjects)))
    
    pool = mp.Pool(pool_num)
    
    print("Loading training connectomes...")
    try:
        # Prepare arguments with parcel info
        # Use full connectomes for training (matching Erica Bush's implementation)
        train_args = [(subject, connectome_dir, current_parcel) for subject in train_subjects]
        train_cnx = pool.map(prep_cnx, train_args)
        print("Successfully loaded {} training connectomes".format(len(train_cnx)))
    except Exception as e:
        print("Error loading training connectomes: {}".format(e))
        pool.close()
        return
    
    print("Training hyperalignment...")
    ha = Hyperalignment(nproc=n_jobs, joblib_backend='multiprocessing')
    debug.active += ['HPAL']
    
    try:
        ha(train_cnx)  # train the hyperalignment model
        t1 = time.time() - t0
        print('Finished training @ {:.2f} seconds'.format(t1))
    except Exception as e:
        print("Error during hyperalignment training: {}".format(e))
        pool.close()
        return
    
    print("Loading test connectomes and applying mappers...")
    try:
        test_args = [(subject, connectome_dir, current_parcel) for subject in test_subjects]
        # Use full connectomes for test subjects (matching Erica Bush's implementation)
        test_cnx = pool.map(prep_cnx, test_args)
        mappers = ha(test_cnx)  # get mappers for test subjects
        
        # Prepare file paths
        data_fns = [os.path.join(aligned_dir, '{}_aligned_dtseries.npy'.format(s)) for s in test_subjects]
        mapper_fns = [os.path.join(mapper_dir, '{}_trained_mapper.npy'.format(s)) for s in test_subjects]
        
        # Apply mappers (None for split parameter in full timeseries)
        apply_args = [(data_fns[i], mapper_fns[i], test_subjects[i], mappers[i], current_parcel, None) 
                     for i in range(len(test_subjects))]
        pool.map(apply_mappers, apply_args)
        
        t2 = time.time() - t1
        print('Finished aligning full timeseries @ {:.2f} seconds'.format(t2))
        
    except Exception as e:
        print("Error during mapper application: {}".format(e))
    finally:
        pool.close()
        pool.join()

# NEW: runs the hyperalignment pipeline for the reliability subjects where mappers are learned in split halves
def drive_hyperalignment_split(train_subjects, test_subjects, connectome_dir, mapper_dir, aligned_dir, current_parcel):
    print("Starting split-half hyperalignment for parcel {}".format(current_parcel))
    print("Training subjects: {}".format(len(train_subjects)))
    print("Test subjects: {}".format(len(test_subjects)))
    
    t0 = time.time()
    pool = mp.Pool(pool_num)
    
    print("Loading training connectomes...")
    try:
        # Use full connectomes for training (matching Erica Bush's implementation)
        train_args = [(subject, connectome_dir, current_parcel) for subject in train_subjects]
        train_cnx = pool.map(prep_cnx, train_args)
        print("Successfully loaded {} training connectomes".format(len(train_cnx)))
    except Exception as e:
        print("Error loading training connectomes: {}".format(e))
        pool.close()
        return
    
    print("Training hyperalignment...")
    ha = Hyperalignment(nproc=n_jobs, joblib_backend='multiprocessing')
    debug.active += ['HPAL']
    
    try:
        ha(train_cnx)  # train the hyperalignment model
        t1 = time.time() - t0
        print('Finished training @ {:.2f} seconds'.format(t1))
    except Exception as e:
        print("Error during hyperalignment training: {}".format(e))
        pool.close()
        return
    
    print("Processing split-half data...")
    try:
        # Prepare split connectomes for test subjects
        test_args0 = [(subject, 0, connectome_dir, current_parcel) for subject in test_subjects]  # split 0
        test_args1 = [(subject, 1, connectome_dir, current_parcel) for subject in test_subjects]  # split 1

        # Check if split connectome files exist, if not use regular connectomes
        # Debug: print the exact file paths being checked
        for subject in test_subjects[:3]:
            check_path = os.path.join(connectome_dir, '{a}_split_0_connectome_parcel_{i:03d}.npy'.format(a=subject, i=current_parcel))
            print("Checking for split connectome file:", check_path, "Exists:", os.path.exists(check_path))
        split_files_exist = all(os.path.exists(os.path.join(connectome_dir, '{a}_split_0_connectome_parcel_{i:03d}.npy'.format(a=subject, i=current_parcel)))
                              for subject in test_subjects[:3])  # Check first few subjects
        if split_files_exist:
            print("Using pre-computed split connectomes...")
            test_cnx0 = pool.map(prep_cnx_split, test_args0)
            test_cnx1 = pool.map(prep_cnx_split, test_args1)
        else:
            print("Split connectomes not found, using full connectomes for split analysis...")
            test_args_full = [(subject, connectome_dir, current_parcel) for subject in test_subjects]
            test_cnx0 = pool.map(prep_cnx, test_args_full)
            test_cnx1 = pool.map(prep_cnx, test_args_full)

        # Get mappers for both splits
        mappers0 = ha(test_cnx0)
        mappers1 = ha(test_cnx1)

        # Prepare file paths for split data
        data_fns = [os.path.join(aligned_dir, '{}_aligned_dtseries_split'.format(s)) for s in test_subjects]
        mapper_fns = [os.path.join(mapper_dir, '{}_trained_mapper_split'.format(s)) for s in test_subjects]

        # Apply split mappers
        apply_args = [(data_fns[i], mapper_fns[i], test_subjects[i], mappers0[i], mappers1[i], current_parcel) 
                     for i in range(len(test_subjects))]
        pool.map(apply_mappers_split, apply_args)

        t2 = time.time() - t1
        print('Finished aligning split timeseries @ {:.2f} seconds'.format(t2))

    except Exception as e:
        print("Error during split mapper application: {}".format(e))
    finally:
        pool.close()
        pool.join()


# Load atlas once
glasser_atlas = load_glasser_atlas()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def discover_subject_ids():
    """
    Discover available subject IDs from dtseries files.

    Returns
    -------
    list of str
        Sorted list of unique subject IDs
    """
    pattern = DTSERIES_PATTERN
    ids = []
    for fp in glob.glob(pattern):
        name = os.path.basename(fp)
        sid = name.split("_task-rest")[0]
        ids.append(sid)
    return sorted(set(ids))


def format_subject_id(subject_id_raw):
    subject_id = str(subject_id_raw).split(',')[0].strip()
    return subject_id  # No prefix added


def get_train_test_subjects(csv_path=None):
    """
    Get training and test subjects from freesurfer CSV file.

    Training subjects: Those with "No Diagnosis Given" in Diagnosis Category column
    Test subjects: All other subjects with available data

    The CSV has subject IDs in format "NDARXXXXX,assessment" which we convert to "sub-NDARXXXXX"

    Parameters
    ----------
    csv_path : str
        Path to CSV file with subject metadata

    Returns
    -------
    tuple
        (train_subjects, test_subjects) - lists of subject IDs
    """
    import pandas as pd

    # TEST MODE: If TEST_SUBJECTS_LIST is set, use simple random split
    test_subjects_env = os.environ.get('TEST_SUBJECTS_LIST', '')
    if test_subjects_env:
        print("TEST MODE: Using simple random train/test split")
        test_subjects_list = test_subjects_env.split()
        print("Test subjects from environment: {}".format(len(test_subjects_list)))

        random.seed(42)
        test_subjects_copy = list(test_subjects_list)
        random.shuffle(test_subjects_copy)

        # train/test with specified percentage
        train_pct = float(os.environ.get('TRAIN_PCT', '0.4'))
        n_train = max(1, int(len(test_subjects_copy) * train_pct))
        train_subjects = test_subjects_copy[:n_train]
        test_subjects = test_subjects_copy[n_train:]

        print("Random split for test mode:")
        print("  Training: {} subjects".format(len(train_subjects)))
        print("  Test: {} subjects".format(len(test_subjects)))
        print("  Train subjects: {}".format(train_subjects))
        print("  Test subjects: {}".format(test_subjects))

        return train_subjects, test_subjects

    # Check if CSV path provided and exists
    if csv_path is None or not os.path.exists(csv_path):
        if csv_path:
            print("WARNING: CSV file not found: {}".format(csv_path))

        # Try to use METADATA_EXCEL with split column if available
        use_metadata = os.environ.get('USE_METADATA_FILTER', '0') == '1'
        metadata_path = os.environ.get('METADATA_EXCEL', '')

        if use_metadata and metadata_path and os.path.exists(metadata_path):
            print("Using train/test split from metadata file: {}".format(metadata_path))
            try:
                import pandas as pd
                from read_config import SUBJECT_ID_COL, SPLIT_COL

                # Load metadata file
                if metadata_path.endswith('.csv'):
                    df = pd.read_csv(metadata_path)
                else:
                    df = pd.read_excel(metadata_path)

                print("Loaded {} subjects from metadata".format(len(df)))

                # Check if split column exists
                if SPLIT_COL in df.columns:
                    print("Using '{}' column for train/test split".format(SPLIT_COL))

                    # Get train and test subjects
                    train_df = df[df[SPLIT_COL].str.lower() == 'train']
                    test_df = df[df[SPLIT_COL].str.lower() == 'test']

                    # Format subject IDs
                    def format_id(sid):
                        return str(sid).strip()  # No prefix added

                    train_subjects = [format_id(s) for s in train_df[SUBJECT_ID_COL].values]
                    test_subjects = [format_id(s) for s in test_df[SUBJECT_ID_COL].values]

                    print("From metadata split column:")
                    print("  Training: {} subjects".format(len(train_subjects)))
                    print("  Test: {} subjects".format(len(test_subjects)))

                    return train_subjects, test_subjects
                else:
                    print("Warning: '{}' column not found in metadata, falling back to random split".format(SPLIT_COL))
            except Exception as e:
                print("Error reading metadata file: {}, falling back to random split".format(e))

        # Fall back to random split
        print("Using random split of discovered subjects (respects metadata filtering)")
        # Use utils._discover_subject_ids() which respects metadata filtering
        all_subjects = utils._discover_subject_ids()
        print("Found {} total subjects".format(len(all_subjects)))
        
        random.seed(42)
        all_subjects_copy = list(all_subjects)
        random.shuffle(all_subjects_copy)
        
        # Read train percentage from environment
        train_pct = float(os.environ.get('TRAIN_PCT', '0.4'))
        n_train = int(len(all_subjects_copy) * train_pct)
        train_subjects = all_subjects_copy[:n_train]
        test_subjects = all_subjects_copy[n_train:]
        
        print("Train percentage: {:.1%}".format(train_pct))

        print("Random split: {} training, {} test".format(
            len(train_subjects), len(test_subjects)))

        return train_subjects, test_subjects

    # Load CSV
    df = pd.read_csv(csv_path)
    print("Loaded {} subjects from {}".format(len(df), csv_path))

    # Check required columns exist
    if 'diagnosis_category' not in df.columns:
        print("ERROR: Column 'diagnosis_category' not found in CSV")
        print("Available columns: {}".format(df.columns.tolist()))
        raise KeyError("Required column 'diagnosis_category' not found")

    if 'subject_id' not in df.columns:
        print("ERROR: Column 'subject_id' not found in CSV")
        print("Available columns: {}".format(df.columns.tolist()))
        raise KeyError("Required column 'subject_id' not found")

    # Print diagnosis categories
    print("\nDiagnosis Categories:")
    print(df['diagnosis_category'].value_counts().to_string())

    # Split train/test based on diagnosis category
    train_df = df[df['diagnosis_category'] == 'No Diagnosis Given']
    test_df = df[df['diagnosis_category'] != 'No Diagnosis Given']

    print("\nFrom CSV:")
    print("  Total subjects: {}".format(len(df)))
    print("  Training ('No Diagnosis Given'): {}".format(len(train_df)))
    print("  Test (other diagnoses): {}".format(len(test_df)))

    # Format subject IDs (remove ',assessment' and add 'sub-' prefix)
    train_subjects = [format_subject_id(raw_id) for raw_id in train_df['subject_id'].values]
    test_subjects = [format_subject_id(raw_id) for raw_id in test_df['subject_id'].values]

    # Show sample formatting
    if len(train_subjects) > 0:
        print("\nSample training subject formatting:")
        for i in range(min(3, len(train_subjects))):
            raw = train_df['subject_id'].values[i]
            formatted = train_subjects[i]
            print("  {} -> {}".format(raw, formatted))

    # Get available subjects from filesystem (respects metadata filtering)
    available_subjects = utils._discover_subject_ids()
    print("\nAvailable in filesystem: {}".format(len(available_subjects)))

    # Filter to subjects with available data
    train_subjects_available = [s for s in train_subjects if s in available_subjects]
    test_subjects_available = [s for s in test_subjects if s in available_subjects]

    print("\nFiltered to available data:")
    print("  Training: {}".format(len(train_subjects_available)))
    print("  Test: {}".format(len(test_subjects_available)))

    if len(train_subjects_available) == 0:
        print("\nWARNING: No training subjects found with available data!")
        print("Check that subject IDs in CSV match filesystem naming")
        print("CSV format: 'NDARXXXXX,assessment' -> expecting filesystem: 'sub-NDARXXXXX'")

    if len(test_subjects_available) == 0:
        print("\nWARNING: No test subjects found with available data!")

    return train_subjects_available, test_subjects_available

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == '__main__':
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python run_hyperalignment_v3.py <parcel_number> [mode]")
        print("  parcel_number: parcel to process (1-360)")
        print("  mode: 'full', 'split', or 'both' (default: 'both')")
        sys.exit(1)

    parcel = int(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'both'

    if parcel < 1 or parcel > 360:
        print("ERROR: Parcel must be between 1 and 360")
        sys.exit(1)

    if mode not in ['full', 'split', 'both']:
        print("ERROR: Mode must be 'full', 'split', or 'both'")
        sys.exit(1)

    print("\n" + "="*80)
    print("HYPERALIGNMENT PIPELINE v3.0 (Python 3 + Erica's Implementation)")
    print("="*80)
    print("Parcel: {}".format(parcel))
    print("Mode: {}".format(mode))
    print("="*80)

    t_overall = time.time()

    # Set up directories
    train_connectome_dir, mapper_dir, aligned_dir = setup_output_dirs(
        BASE_CONNECTOME_DIR, parcel)

    print("\nDirectories:")
    print("  Training connectomes: {}".format(train_connectome_dir))
    print("  Mappers output:       {}".format(mapper_dir))
    print("  Aligned timeseries:   {}".format(aligned_dir))

    # Check if training connectomes exist
    if not os.path.exists(train_connectome_dir):
        print("\nERROR: Training connectome directory not found:")
        print("  {}".format(train_connectome_dir))
        sys.exit(1)

    # Get train/test subjects
    train_subjects, test_subjects = get_train_test_subjects()

    # Filter to subjects with available data based on mode
    # Check for the appropriate connectome files depending on mode
    if mode == 'full':
        pattern = os.path.join(train_connectome_dir, '*_full_connectome_parcel_{:03d}.npy'.format(parcel))
        split_str = '_full_connectome'
    elif mode == 'split':
        # For split mode, check for split_0 files
        pattern = os.path.join(train_connectome_dir, '*_split_0_connectome_parcel_{:03d}.npy'.format(parcel))
        split_str = '_split_0_connectome'
    else:  # mode == 'both'
        # Check for either full or split files
        pattern = os.path.join(train_connectome_dir, '*_split_0_connectome_parcel_{:03d}.npy'.format(parcel))
        split_str = '_split_0_connectome'

    available_files = glob.glob(pattern)
    available_subjects = [os.path.basename(f).split(split_str)[0]
                         for f in available_files]

    train_subjects = [s for s in train_subjects if s in available_subjects]
    test_subjects = [s for s in test_subjects if s in available_subjects]

    print("\nFiltered to subjects with available data:")
    print("  Training: {}".format(len(train_subjects)))
    print("  Test:     {}".format(len(test_subjects)))

    if len(train_subjects) == 0 or len(test_subjects) == 0:
        print("\nERROR: No subjects with available connectome data found")
        print("Pattern searched: {}".format(pattern))
        print("Available files: {}".format(len(available_files)))
        if len(available_files) > 0:
            print("Sample file: {}".format(available_files[0]))
        sys.exit(1)

    print("  Training subjects: {}".format(train_subjects))
    # Create output directories
    for dn in [aligned_dir, mapper_dir]:
        if not os.path.isdir(dn):
            os.makedirs(dn)
            print("Created directory: {}".format(dn))
    
    # Run hyperalignment based on mode
    if mode == 'full' or mode == 'both':
        drive_hyperalignment_full(train_subjects, test_subjects,
                                 train_connectome_dir, mapper_dir,
                                 aligned_dir, parcel)

    if mode == 'split' or mode == 'both':
        drive_hyperalignment_split(train_subjects, test_subjects,
                                  train_connectome_dir, mapper_dir,
                                  aligned_dir, parcel)

    total_time = time.time() - t_overall
    print("\n" + "="*80)
    print("ALL PROCESSING COMPLETE")
    print("="*80)
    print("Total time: {:.2f} seconds ({:.2f} minutes)".format(
        total_time, total_time/60))
    print("Outputs saved to: {}".format(BASE_CONNECTOME_DIR))
