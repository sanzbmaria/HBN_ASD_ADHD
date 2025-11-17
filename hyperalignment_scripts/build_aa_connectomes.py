#!/usr/bin/python3
#%%
## BUILD AA CONNECTOMES

import warnings
# Suppress nibabel pixdim warnings
warnings.filterwarnings("ignore", message=".*pixdim.*")
warnings.filterwarnings("ignore", category=UserWarning, module="nibabel")

import os
import glob
import numpy as np
import nibabel as nib
from scipy.stats import zscore
from scipy.spatial.distance import cdist
import utils as utils
from joblib import Parallel, delayed
import multiprocessing as mp
from tqdm import tqdm
import csv
from datetime import datetime
import pandas as pd

# Use GSR-aware configuration from utils
base_outdir = utils.BASE_OUTDIR  # This now automatically switches based on USE_GSR flag
vertices_in_bounds = utils.VERTICES_IN_BOUNDS
n_parcels = utils.N_PARCELS
LOGDIR = utils.LOGDIR
LOG_FILE = os.path.join(LOGDIR, 'build_aa_connectomes_runlog.csv')

def check_completion_status(subjects_list):
    """
    Check which subjects and parcels are completed for both full and split connectomes.
    Returns dictionaries with completion info.
    """
    completion = {
        'full': {'completed_subjects': set(), 'incomplete_subjects': set()},
        'split': {'completed_subjects': set(), 'incomplete_subjects': set()}
    }
    
    for subj_id in subjects_list:
        # Check full connectomes
        full_complete = True
        for parcel in range(1, n_parcels + 1):
            fine_parcel_dir = f'{base_outdir}/fine/parcel_{parcel:03d}'
            fine_out = os.path.join(fine_parcel_dir, f'{subj_id}_full_connectome_parcel_{parcel:03d}.npy')
            if not os.path.exists(fine_out):
                full_complete = False
                break
        
        if full_complete:
            completion['full']['completed_subjects'].add(subj_id)
        else:
            completion['full']['incomplete_subjects'].add(subj_id)
        
        # Check split connectomes
        split_complete = True
        for parcel in range(1, n_parcels + 1):
            fine_parcel_dir = f'{base_outdir}/fine/parcel_{parcel:03d}'
            split0_out = os.path.join(fine_parcel_dir, f'{subj_id}_split_0_connectome_parcel_{parcel:03d}.npy')
            split1_out = os.path.join(fine_parcel_dir, f'{subj_id}_split_1_connectome_parcel_{parcel:03d}.npy')
            if not (os.path.exists(split0_out) and os.path.exists(split1_out)):
                split_complete = False
                break
        
        if split_complete:
            completion['split']['completed_subjects'].add(subj_id)
        else:
            completion['split']['incomplete_subjects'].add(subj_id)
    
    return completion

def append_log(subj_id, mode, parcels_completed, status, message=''):
    """Append a one-line CSV summary for a subject run.
    Fields: timestamp,subject,mode,parcels_completed,status,message
    """
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        write_header = not os.path.exists(LOG_FILE)
        with open(LOG_FILE, 'a', newline='') as fh:
            writer = csv.writer(fh)
            if write_header:
                writer.writerow(['timestamp', 'subject', 'mode', 'parcels_completed', 'status', 'message'])
            writer.writerow([datetime.utcnow().isoformat(), subj_id, mode, parcels_completed, status, message])
            fh.flush()
    except Exception as e:
        if 'verbose' in globals() and verbose:
            print(f"Failed to write log for {subj_id}: {e}")

def build_full_connectomes(subj_id, save_coarse=False):
    try:
        subj_dss_all = utils.subj_dtseries_to_npy(subj_id)
        subj_prc = utils.subj_ptseries_to_npy(subj_id)

        connectome = 1 - cdist(subj_dss_all.T, subj_prc.T, 'correlation')

        # Add progress bar for parcels
        parcel_iter = tqdm(range(1, n_parcels+1), desc=f"Processing {subj_id} full connectomes", leave=False)

        parcels_done = 0
        for i, parcel in enumerate(parcel_iter):
                # Create parcel-specific directories BEFORE trying to save files
                fine_parcel_dir = f'{base_outdir}/fine/parcel_{parcel:03d}'
                os.makedirs(fine_parcel_dir, exist_ok=True)
                
                if save_coarse:
                    coarse_parcel_dir = f'{base_outdir}/coarse/parcel_{parcel:03d}'
                    os.makedirs(coarse_parcel_dir, exist_ok=True)

                # paths to check for resumability
                fine_out = os.path.join(fine_parcel_dir, f'{subj_id}_full_connectome_parcel_{parcel:03d}.npy')
                coarse_out = os.path.join(coarse_parcel_dir, f'{subj_id}_full_connectome_parcel_{parcel:03d}.npy') if save_coarse else None

                # Skip if output files already exist
                files_exist = os.path.exists(fine_out)
                if save_coarse and coarse_out:
                    files_exist = files_exist and os.path.exists(coarse_out)
                if files_exist:
                    continue

                mask = (glasser == parcel).squeeze()
                target_indices = np.setdiff1d(np.arange(n_parcels), i)
                d = connectome[mask][:, target_indices]

                # Save fine connectome
                np.save(fine_out, d.T)

                # Save coarse if requested
                if save_coarse and coarse_out:
                    np.save(coarse_out, np.mean(d, axis=0).T)

                parcels_done += 1

    except Exception as e:
        # Print but don't crash the whole job runner; record in log
        msg = str(e)
        print(f"Error processing full connectomes for {subj_id}: {msg}")
        try:
            append_log(subj_id, 'full', parcels_done if 'parcels_done' in locals() else 0, 'error', msg)
        except Exception:
            pass
        return
    append_log(subj_id, 'full', parcels_done, 'ok', '')
    if verbose: print(f'finished full connectomes for {subj_id} saved at {base_outdir}')

def build_split_connectomes(subj_id, save_coarse=False):
    try:
        subj_dss_all = utils.subj_dtseries_to_npy(subj_id)
        subj_prc = utils.subj_ptseries_to_npy(subj_id)
        split = subj_prc.shape[0]//2
        split0_tpts = np.arange(0, split)
        split1_tpts = np.arange(split, subj_prc.shape[0])
        
        subj_dss0, subj_dss1 = subj_dss_all[split0_tpts], subj_dss_all[split1_tpts] 
        subj_prc0, subj_prc1 = subj_prc[split0_tpts], subj_prc[split1_tpts]
        
        connectome0 = 1 - cdist(subj_dss0.T, subj_prc0.T, 'correlation')
        connectome1 = 1 - cdist(subj_dss1.T, subj_prc1.T, 'correlation')

        
        parcel_iter = tqdm(range(1, n_parcels+1), 
                desc=f"Processing {subj_id} split connectomes", 
                leave=False)

        parcels_done = 0
        for i, parcel in enumerate(parcel_iter):
                fine_parcel_dir = f'{base_outdir}/fine/parcel_{parcel:03d}'
                os.makedirs(fine_parcel_dir, exist_ok=True)
                
                if save_coarse:
                    coarse_parcel_dir = f'{base_outdir}/coarse/parcel_{parcel:03d}'
                    os.makedirs(coarse_parcel_dir, exist_ok=True)
                
                mask = (glasser == parcel).squeeze()
                target_indices = np.setdiff1d(np.arange(n_parcels), i)

                # paths for resumability
                out_split0 = os.path.join(fine_parcel_dir, f'{subj_id}_split_0_connectome_parcel_{parcel:03d}.npy')
                out_split1 = os.path.join(fine_parcel_dir, f'{subj_id}_split_1_connectome_parcel_{parcel:03d}.npy')

                # Check if all required files already exist
                files_exist = os.path.exists(out_split0) and os.path.exists(out_split1)
                if save_coarse:
                    coarse_out0 = os.path.join(coarse_parcel_dir, f'{subj_id}_split_0_connectome_parcel_{parcel:03d}.npy')
                    coarse_out1 = os.path.join(coarse_parcel_dir, f'{subj_id}_split_1_connectome_parcel_{parcel:03d}.npy')
                    files_exist = files_exist and os.path.exists(coarse_out0) and os.path.exists(coarse_out1)
                
                if files_exist:
                    continue

                # Split 0
                d0 = connectome0[mask][:, target_indices]
                np.save(out_split0, d0.T)

                # Split 1
                d1 = connectome1[mask][:, target_indices]
                np.save(out_split1, d1.T)
                
                # Save coarse versions if requested
                if save_coarse:
                    np.save(coarse_out0, np.mean(d0, axis=0).T)
                    np.save(coarse_out1, np.mean(d1, axis=0).T)

                parcels_done += 1

    except Exception as e:
        msg = str(e)
        print(f"Error processing split connectomes for {subj_id}: {msg}")
        try:
            append_log(subj_id, 'split', parcels_done if 'parcels_done' in locals() else 0, 'error', msg)
        except Exception:
            pass
        return
    append_log(subj_id, 'split', parcels_done, 'ok', '')
    if verbose: print(f'finished split-half connectomes for {subj_id} saved at {base_outdir}')

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Build AA connectomes from parcellated data')
    parser.add_argument('--mode', type=str, choices=['full', 'split', 'both'], default='both',
                        help='Build full connectomes, split connectomes, or both (default: both)')
    args = parser.parse_args()

    verbose = True

    if verbose:
        print(f"Building AA connectomes (mode: {args.mode})")
        print(f"Output directory: {base_outdir}")
    
    # Use utils to find subjects (GSR-aware)
    all_subjects = utils._discover_subject_ids()
    
    # Also check ptseries directory for subjects
    subjects_from_ptseries = []
    if os.path.exists(utils.PTSERIES_ROOT):
        subjects_from_ptseries = [d for d in os.listdir(utils.PTSERIES_ROOT) 
                                 if d.startswith("sub-") and os.path.isdir(os.path.join(utils.PTSERIES_ROOT, d))]
    
    # Use intersection of subjects available in both dtseries and ptseries
    subjects2run = list(set(all_subjects).intersection(set(subjects_from_ptseries)))

    # Filter for test mode if TEST_SUBJECTS_LIST is set
    test_subjects_env = os.environ.get('TEST_SUBJECTS_LIST', '')
    if test_subjects_env:
        test_subjects = test_subjects_env.split()
        subjects2run = [s for s in subjects2run if s in test_subjects]
        if verbose:
            print(f"TEST MODE: Filtering to {len(test_subjects)} test subjects")
            print(f"Test subjects: {test_subjects}")
            print(f"Found {len(subjects2run)} test subjects with complete data")

    if not subjects2run:
        if verbose:
            print(f"No subjects found with both dtseries and ptseries data!")
            print(f"Dtseries subjects: {len(all_subjects)}")
            print(f"Ptseries subjects: {len(subjects_from_ptseries)}")
        exit(1)
    
    if verbose:
        print(f'Found {len(subjects2run)} subjects with complete data')
        print(f'Sample subjects: {subjects2run[:3]}')

    glasser = utils.get_glasser_atlas_file()
    verbose = True
    n_jobs = mp.cpu_count() - 1

    joblist = []
    
    if verbose:
        print("Creating job list...")
    
    # Only process subjects that are incomplete for split connectomes
    subjects_to_process = list(set(subjects2run))
    if not subjects_to_process:
        if verbose:
            print("All split connectomes are already completed!")
        exit(0)
    
    if verbose:
        print(f"Processing {len(subjects_to_process)} incomplete subjects...")

    for s in tqdm(subjects_to_process, desc="Setting up jobs"):
        if args.mode in ['full', 'both']:
            joblist.append(delayed(build_full_connectomes)(s, save_coarse=True))
        if args.mode in ['split', 'both']:
            joblist.append(delayed(build_split_connectomes)(s, save_coarse=True))
    
    if verbose:
        print(f"Running {len(joblist)} jobs with {n_jobs} parallel workers...")
    
    with Parallel(n_jobs=n_jobs, verbose=1) as parallel:
        parallel(joblist)
                   
    if verbose:
        print("All connectome processing completed!")
        print(f"Results saved to: {base_outdir}")

# %%
