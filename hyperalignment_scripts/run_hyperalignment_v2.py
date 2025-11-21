#!/usr/bin/env python3

# Hyperalignment v2: Uses custom hyperalignment module instead of PyMVPA2
# Adapted from Erica Bush's implementation to work with BioBank pipeline

import os
import sys

# Set TMPDIR to a writable location (critical for BioBank with read-only inputs)
TMPDIR = os.environ.get('TMPDIR', '/data/outputs/.tmp')
os.makedirs(TMPDIR, exist_ok=True)
os.environ['TMPDIR'] = TMPDIR
os.environ['TEMP'] = TMPDIR
os.environ['TMP'] = TMPDIR

# Set environment variable to suppress warnings
os.environ['PYTHONWARNINGS'] = 'ignore::DeprecationWarning'

import warnings
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*pixdim.*")

# Suppress nibabel warnings
import logging
logging.getLogger('nibabel').setLevel(logging.ERROR)

import numpy as np
import glob
import time
import multiprocessing as mp
from scipy.stats import zscore
import random

# Import custom hyperalignment module
try:
    import hyperalignment as hyp
except ImportError:
    print("ERROR: hyperalignment module not found!")
    print("Please ensure hyperalignment.py is in the same directory or in PYTHONPATH")
    sys.exit(1)

# Import centralized configuration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_config import (
    POOL_NUM, N_JOBS, VERTICES_IN_BOUNDS, N_PARCELS,
    DTSERIES_ROOT, PTSERIES_ROOT, BASE_OUTDIR, TEMPORARY_OUTDIR,
    PARCELLATION_FILE, DTSERIES_FILENAME_TEMPLATE, DTSERIES_FILENAME_PATTERN,
    pool_num, n_jobs
)
import utils

# For backwards compatibility
BASE_CONNECTOME_DIR = BASE_OUTDIR

# Load Glasser atlas
def load_glasser_atlas():
    import nibabel as nib
    g = nib.load(PARCELLATION_FILE)
    return g.get_fdata().T

glasser_atlas = load_glasser_atlas()


# ============================================================================
# DATA PREPARATION FUNCTIONS
# ============================================================================

def prep_cnx(subject, connectome_dir, current_parcel):
    """Load full connectome for training/testing"""
    fn = os.path.join(connectome_dir, f'{subject}_full_connectome_parcel_{current_parcel:03d}.npy')
    if not os.path.exists(fn):
        raise FileNotFoundError(f"Connectome file not found: {fn}")

    d = np.nan_to_num(zscore(np.load(fn)))

    # Return as dictionary (compatible with custom hyperalignment module)
    ds_train = {
        'data': d,
        'targets': np.arange(1, N_PARCELS),
        'seeds': np.where(glasser_atlas == current_parcel)[0]
    }
    return ds_train


def prep_cnx_split(subject, split, connectome_dir, current_parcel):
    """Load split-half connectome for reliability analysis"""
    fn = os.path.join(connectome_dir, f'{subject}_split_{split}_connectome_parcel_{current_parcel:03d}.npy')
    if not os.path.exists(fn):
        raise FileNotFoundError(f"Split connectome file not found: {fn}")

    d = np.nan_to_num(zscore(np.load(fn)))

    ds_train = {
        'data': d,
        'targets': np.arange(1, N_PARCELS),
        'seeds': np.where(glasser_atlas == current_parcel)[0]
    }
    return ds_train


def load_dtseries_data(subj_id, parcel=None):
    """Load dtseries data for a subject"""
    filename = DTSERIES_FILENAME_TEMPLATE.format(subj=subj_id)
    import nibabel as nib
    ds = nib.load(os.path.join(DTSERIES_ROOT, filename)).get_fdata()[:, :VERTICES_IN_BOUNDS]
    if parcel:
        mask = (glasser_atlas == parcel).squeeze()
        return zscore(ds[:, mask], axis=0)
    return zscore(ds, axis=0)


def prep_dtseries(subject, current_parcel, split=None):
    """Load and prepare vertex-wise timeseries for a subject"""
    d = load_dtseries_data(subject, parcel=current_parcel)

    if split is not None:
        half = d.shape[0] // 2
        start = split * half
        tpts_in_bounds = np.arange(start, start + half)
        d = d[tpts_in_bounds]

    return zscore(d, axis=0)


# ============================================================================
# MAPPER APPLICATION FUNCTIONS
# ============================================================================

def apply_mappers(data_out_fn, mapper_out_fn, subject, mapper, current_parcel, split=None):
    """Apply learned mapper to align subject's timeseries"""
    try:
        dtseries = prep_dtseries(subject, current_parcel, split=split)
        # Use @ operator for matrix multiplication (Python 3)
        aligned = zscore((np.asmatrix(dtseries) @ mapper.T).A, axis=0)
        np.save(data_out_fn, aligned)
        np.save(mapper_out_fn, mapper)
        print(f"Successfully processed subject {subject} (split: {split})")
    except Exception as e:
        print(f"Error processing subject {subject} (split: {split}): {e}")


def apply_mappers_split(data_out_fn, mapper_fn, subject, mapper0, mapper1, current_parcel):
    """Apply split-half mappers"""
    try:
        dtseries0 = prep_dtseries(subject, current_parcel, split=0)
        dtseries1 = prep_dtseries(subject, current_parcel, split=1)

        aligned0 = zscore(np.array(dtseries0) @ mapper0.T, axis=0)
        aligned1 = zscore(np.array(dtseries1) @ mapper1.T, axis=0)

        np.save(data_out_fn + '_0.npy', aligned0)
        np.save(data_out_fn + '_1.npy', aligned1)
        np.save(mapper_fn + '_0.npy', mapper0)
        np.save(mapper_fn + '_1.npy', mapper1)

        print(f"Successfully processed split data for subject {subject}")
    except Exception as e:
        print(f"Error processing split data for subject {subject}: {e}")


# ============================================================================
# HYPERALIGNMENT DRIVER FUNCTIONS
# ============================================================================

def drive_hyperalignment_full(train_subjects, test_subjects, connectome_dir, mapper_dir, aligned_dir, current_parcel):
    """Run hyperalignment pipeline for full timeseries data"""
    t0 = time.time()
    print(f"Starting hyperalignment for parcel {current_parcel}")
    print(f"Training subjects: {len(train_subjects)}")
    print(f"Test subjects: {len(test_subjects)}")

    pool = mp.Pool(pool_num)

    print("Loading training connectomes...")
    try:
        # Load training data - extract 'data' field from dictionaries
        train_cnx = [prep_cnx(subject, connectome_dir, current_parcel)['data'] for subject in train_subjects]
        print(f"Successfully loaded {len(train_cnx)} training connectomes")
    except Exception as e:
        print(f"Error loading training connectomes: {e}")
        pool.close()
        return

    print("Training hyperalignment...")
    try:
        ha = hyp.Hyperalignment(verbose=True)
        mappers_train = ha.fit(train_cnx)
        t1 = time.time() - t0
        print(f'Finished training @ {t1:.2f} seconds')
    except Exception as e:
        print(f"Error during hyperalignment training: {e}")
        pool.close()
        return

    print("Loading test connectomes and applying mappers...")
    try:
        # Load test data
        test_cnx = [prep_cnx(subject, connectome_dir, current_parcel)['data'] for subject in test_subjects]

        # Get mappers for test subjects
        mappers = ha.fit(test_cnx).get_transformations()

        # Prepare file paths
        data_fns = [os.path.join(aligned_dir, f'{s}_aligned_dtseries.npy') for s in test_subjects]
        mapper_fns = [os.path.join(mapper_dir, f'{s}_trained_mapper.npy') for s in test_subjects]

        # Apply mappers
        iterable = list(zip(data_fns, mapper_fns, test_subjects, mappers, [None]*len(mappers), [current_parcel]*len(mappers)))
        pool.starmap(apply_mappers, iterable)

        t2 = time.time() - t1
        print(f'Finished aligning full timeseries @ {t2:.2f} seconds')
    except Exception as e:
        print(f"Error during mapper application: {e}")
    finally:
        pool.close()
        pool.join()


def drive_hyperalignment_split(train_subjects, test_subjects, connectome_dir, mapper_dir, aligned_dir, current_parcel):
    """Run hyperalignment pipeline for split-half reliability analysis"""
    print(f"Starting split-half hyperalignment for parcel {current_parcel}")
    print(f"Training subjects: {len(train_subjects)}")
    print(f"Test subjects: {len(test_subjects)}")

    t0 = time.time()
    pool = mp.Pool(pool_num)

    print("Loading training connectomes...")
    try:
        # Use full connectomes for training
        train_cnx = [prep_cnx(subject, connectome_dir, current_parcel)['data'] for subject in train_subjects]
        print(f"Successfully loaded {len(train_cnx)} training connectomes")
    except Exception as e:
        print(f"Error loading training connectomes: {e}")
        pool.close()
        return

    print("Training hyperalignment...")
    try:
        ha = hyp.Hyperalignment(verbose=True)
        mappers_train = ha.fit(train_cnx)
        t1 = time.time() - t0
        print(f'Finished training @ {t1:.2f} seconds')
    except Exception as e:
        print(f"Error during hyperalignment training: {e}")
        pool.close()
        return

    print("Processing split-half data...")
    try:
        # Load split connectomes
        test_cnx0 = [prep_cnx_split(subject, 0, connectome_dir, current_parcel)['data'] for subject in test_subjects]
        test_cnx1 = [prep_cnx_split(subject, 1, connectome_dir, current_parcel)['data'] for subject in test_subjects]

        # Get mappers for both splits
        mappers0 = ha.fit(test_cnx0).get_transformations()
        mappers1 = ha.fit(test_cnx1).get_transformations()

        # Prepare file paths
        data_fns = [os.path.join(aligned_dir, f'{s}_aligned_dtseries_split') for s in test_subjects]
        mapper_fns = [os.path.join(mapper_dir, f'{s}_trained_mapper_split') for s in test_subjects]

        # Apply split mappers
        iterable = list(zip(data_fns, mapper_fns, test_subjects, mappers0, mappers1, [current_parcel]*len(test_subjects)))
        pool.starmap(apply_mappers_split, iterable)

        t2 = time.time() - t1
        print(f'Finished aligning split timeseries @ {t2:.2f} seconds')
    except Exception as e:
        print(f"Error during split mapper application: {e}")
    finally:
        pool.close()
        pool.join()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def setup_output_dirs(base_connectome_dir, parcel):
    """Setup output directory structure"""
    train_connectome_dir = os.path.join(base_connectome_dir, 'fine', f'parcel_{parcel:03d}')
    mapper_base = os.path.join(base_connectome_dir, 'hyperalignment_output')
    mapper_dir = os.path.join(mapper_base, 'mappers', f'parcel_{parcel:03d}')
    aligned_dir = os.path.join(mapper_base, 'aligned_timeseries', f'parcel_{parcel:03d}')
    return train_connectome_dir, mapper_dir, aligned_dir


def get_train_test_subjects(csv_path=None):
    """Get training and test subjects"""
    # TEST MODE: If TEST_SUBJECTS_LIST is set, use simple random split
    test_subjects_env = os.environ.get('TEST_SUBJECTS_LIST', '')
    if test_subjects_env:
        print("TEST MODE: Using simple random train/test split")
        test_subjects_list = test_subjects_env.split()
        print(f"Test subjects from environment: {len(test_subjects_list)}")

        random.seed(42)
        test_subjects_copy = list(test_subjects_list)
        random.shuffle(test_subjects_copy)

        # Split: 20% train, 80% test
        n_train = max(1, int(len(test_subjects_copy) * 0.2))
        train_subjects = test_subjects_copy[:n_train]
        test_subjects = test_subjects_copy[n_train:]

        print("Random split for test mode:")
        print(f"  Training: {len(train_subjects)} subjects")
        print(f"  Test: {len(test_subjects)} subjects")

        return train_subjects, test_subjects

    # Try to use metadata file with split column
    use_metadata = os.environ.get('USE_METADATA_FILTER', '0') == '1'
    metadata_path = os.environ.get('METADATA_EXCEL', '')

    if use_metadata and metadata_path and os.path.exists(metadata_path):
        print(f"Using train/test split from metadata file: {metadata_path}")
        try:
            import pandas as pd
            from read_config import SUBJECT_ID_COL, SPLIT_COL

            # Load metadata file
            if metadata_path.endswith('.csv'):
                df = pd.read_csv(metadata_path)
            else:
                df = pd.read_excel(metadata_path)

            print(f"Loaded {len(df)} subjects from metadata")

            # Check if split column exists
            if SPLIT_COL in df.columns:
                print(f"Using '{SPLIT_COL}' column for train/test split")

                train_df = df[df[SPLIT_COL].str.lower() == 'train']
                test_df = df[df[SPLIT_COL].str.lower() == 'test']

                # Format subject IDs (no "sub-" prefix for BioBank)
                def format_id(sid):
                    return str(sid).strip()

                train_subjects = [format_id(s) for s in train_df[SUBJECT_ID_COL].values]
                test_subjects = [format_id(s) for s in test_df[SUBJECT_ID_COL].values]

                print("From metadata split column:")
                print(f"  Training: {len(train_subjects)} subjects")
                print(f"  Test: {len(test_subjects)} subjects")

                return train_subjects, test_subjects
        except Exception as e:
            print(f"Error reading metadata file: {e}, falling back to random split")

    # Fall back to random split
    print("Using random split of discovered subjects")
    all_subjects = utils._discover_subject_ids()
    print(f"Found {len(all_subjects)} total subjects")

    random.seed(42)
    all_subjects_copy = list(all_subjects)
    random.shuffle(all_subjects_copy)

    n_train = int(len(all_subjects_copy) * 0.2)
    train_subjects = all_subjects_copy[:n_train]
    test_subjects = all_subjects_copy[n_train:]

    print(f"Random split: {len(train_subjects)} training, {len(test_subjects)} test")

    return train_subjects, test_subjects


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python run_hyperalignment_v2.py <parcel_number> [mode]")
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
    print("HYPERALIGNMENT PIPELINE v2.0 (Custom Hyperalignment Module)")
    print("="*80)
    print(f"Parcel: {parcel}")
    print(f"Mode: {mode}")
    print("="*80)

    t_overall = time.time()

    # Set up directories
    train_connectome_dir, mapper_dir, aligned_dir = setup_output_dirs(BASE_CONNECTOME_DIR, parcel)

    print("\nDirectories:")
    print(f"  Training connectomes: {train_connectome_dir}")
    print(f"  Mappers output:       {mapper_dir}")
    print(f"  Aligned timeseries:   {aligned_dir}")

    # Check if training connectomes exist
    if not os.path.exists(train_connectome_dir):
        print(f"\nERROR: Training connectome directory not found:")
        print(f"  {train_connectome_dir}")
        sys.exit(1)

    # Get train/test subjects
    train_subjects, test_subjects = get_train_test_subjects()

    # Filter to subjects with available data based on mode
    if mode == 'full':
        pattern = os.path.join(train_connectome_dir, f'*_full_connectome_parcel_{parcel:03d}.npy')
        split_str = '_full_connectome'
    elif mode == 'split':
        pattern = os.path.join(train_connectome_dir, f'*_split_0_connectome_parcel_{parcel:03d}.npy')
        split_str = '_split_0_connectome'
    else:  # mode == 'both'
        pattern = os.path.join(train_connectome_dir, f'*_split_0_connectome_parcel_{parcel:03d}.npy')
        split_str = '_split_0_connectome'

    available_files = glob.glob(pattern)
    available_subjects = [os.path.basename(f).split(split_str)[0] for f in available_files]

    train_subjects = [s for s in train_subjects if s in available_subjects]
    test_subjects = [s for s in test_subjects if s in available_subjects]

    print("\nFiltered to subjects with available data:")
    print(f"  Training: {len(train_subjects)}")
    print(f"  Test:     {len(test_subjects)}")

    if len(train_subjects) == 0 or len(test_subjects) == 0:
        print("\nERROR: No subjects with available connectome data found")
        print(f"Pattern searched: {pattern}")
        print(f"Available files: {len(available_files)}")
        if len(available_files) > 0:
            print(f"Sample file: {available_files[0]}")
        sys.exit(1)

    # Create output directories
    for dn in [aligned_dir, mapper_dir]:
        if not os.path.isdir(dn):
            os.makedirs(dn)
            print(f"Created directory: {dn}")

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
    print(f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"Outputs saved to: {BASE_CONNECTOME_DIR}")
