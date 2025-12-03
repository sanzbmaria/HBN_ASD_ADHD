#!/usr/bin/python3

# This script is run on the aligned timeseries data produced from run_hyperalignment_simplified.py
import numpy as np
import utils as utils
import os, sys, glob
from scipy.stats import zscore
from scipy.spatial.distance import pdist, cdist, squareform
from joblib import Parallel, delayed
import csv
from datetime import datetime

import warnings
# Suppress nibabel pixdim warnings
warnings.filterwarnings("ignore", message=".*pixdim.*")
warnings.filterwarnings("ignore", category=UserWarning, module="nibabel")

# Logging setup
LOGDIR = utils.LOGDIR if hasattr(utils, 'LOGDIR') else os.path.join(utils.BASE_OUTDIR, 'logs')
LOG_FILE = os.path.join(LOGDIR, 'build_CHA_connectomes_runlog.csv')
verbose = True  # Set to False to suppress stdout

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
            # FIXED: Use datetime.utcnow() instead of datetime.now(datetime.timezone.utc)
            writer.writerow([
                datetime.utcnow().isoformat(),
                subj_id, mode, parcels_completed, status, message
            ])
            fh.flush()
    except Exception as e:
        if verbose:
            print(f"Failed to write log for {subj_id}: {e}")


def build_cha_full_connectomes(subj_id, aligned_ts_dir, aligned_connectome_dir, n_parcels):
    """
    Build full connectomes from aligned timeseries data
    """
    
    # load in a whole-brain timeseries
    # get the number of timepoints for this subject
    all_parcel_timeseries = []
    missing_parcels = []
    
    for parcel in range(1, n_parcels + 1):
        ts_file = os.path.join(aligned_ts_dir, f'parcel_{parcel:03d}', f'{subj_id}_aligned_dtseries.npy')
        
        if os.path.exists(ts_file):
            try:
                ts = zscore(np.nan_to_num(np.load(ts_file)), axis=0)
                all_parcel_timeseries.append(ts)
            except Exception as e:
                msg = f'Error loading timeseries for subject {subj_id}, parcel {parcel}: {e}'
                if verbose:
                    print(msg)
                append_log(subj_id, 'full', parcel, 'error', msg)
                missing_parcels.append(parcel)
                all_parcel_timeseries.append(None)
        else:
            msg = f'Missing timeseries file for subject {subj_id}, parcel {parcel}: {ts_file}'
            if verbose:
                print(msg)
            append_log(subj_id, 'full', parcel, 'missing', msg)
            missing_parcels.append(parcel)
            all_parcel_timeseries.append(None)
    
    if missing_parcels:
        msg = f'Warning: Subject {subj_id} missing data for parcels: {missing_parcels}'
        if verbose:
            print(msg)
        append_log(subj_id, 'full', len(missing_parcels), 'warning', msg)
        # Skip this subject if too much data is missing
        if len(missing_parcels) > n_parcels * 0.1:  # More than 10% missing
            msg = f'Skipping subject {subj_id} due to too much missing data'
            if verbose:
                print(msg)
            append_log(subj_id, 'full', len(missing_parcels), 'skipped', msg)
            return
    
    # Filter out None values and keep track of valid parcels
    valid_parcels = []
    valid_timeseries = []
    for i, ts in enumerate(all_parcel_timeseries):
        if ts is not None:
            valid_parcels.append(i + 1)  # parcel numbers are 1-indexed
            valid_timeseries.append(ts)
    
    if len(valid_timeseries) == 0:
        msg = f'No valid timeseries found for subject {subj_id}'
        if verbose:
            print(msg)
        append_log(subj_id, 'full', 0, 'skipped', msg)
        return
    
    # compute the coarse connectivity profiles
    parcel_average_ts = np.stack([np.mean(ts, axis=1) for ts in valid_timeseries])
    coarse_connectivity_mtx = 1 - squareform(pdist(parcel_average_ts, 'correlation'))
    
    # Save coarse connectomes
    for i, parcel in enumerate(valid_parcels):
        others = np.setdiff1d(np.arange(len(valid_parcels)), i)
        cp = coarse_connectivity_mtx[i][others]
        
        coarse_dir = os.path.join(aligned_connectome_dir, 'coarse', f'parcel_{parcel:03d}')
        os.makedirs(coarse_dir, exist_ok=True)
        np.save(os.path.join(coarse_dir, f'{subj_id}_full_connectome_parcel_{parcel:03d}.npy'), cp)

    # now correlate the coarse TS with the parcel TS to get a fine connectome
    for ts, parcel in zip(valid_timeseries, valid_parcels):
        # Find index of this parcel in valid_parcels
        parcel_idx = valid_parcels.index(parcel)
        others_idx = np.setdiff1d(np.arange(len(valid_parcels)), parcel_idx)
        coarse = parcel_average_ts[others_idx]
        
        try:
            cnx = 1 - cdist(coarse, ts.T, 'correlation')
            fine_dir = os.path.join(aligned_connectome_dir, 'fine', f'parcel_{parcel:03d}')
            os.makedirs(fine_dir, exist_ok=True)
            np.save(os.path.join(fine_dir, f'{subj_id}_full_connectome_parcel_{parcel:03d}.npy'), cnx)
        except Exception as e:
            msg = f'Error computing fine connectome for subject {subj_id}, parcel {parcel}: {e}'
            if verbose:
                print(msg)
            append_log(subj_id, 'full', parcel, 'error', msg)


def build_cha_split_connectomes(subj_id, aligned_ts_dir, aligned_connectome_dir, n_parcels):
    """
    Build split connectomes from aligned split timeseries data
    """
    
    # load in a whole-brain timeseries for both splits
    for split in [0, 1]:
        all_parcel_timeseries = []
        missing_parcels = []
        
        for parcel in range(1, n_parcels + 1):
            ts_file = os.path.join(aligned_ts_dir, f'parcel_{parcel:03d}', f'{subj_id}_aligned_dtseries_split_{split}.npy')
            
            if os.path.exists(ts_file):
                try:
                    ts = zscore(np.nan_to_num(np.load(ts_file)), axis=0)
                    all_parcel_timeseries.append(ts)
                except Exception as e:
                    msg = f'Error loading split timeseries for subject {subj_id}, parcel {parcel}, split {split}: {e}'
                    if verbose:
                        print(msg)
                    append_log(subj_id, f'split{split}', parcel, 'error', msg)
                    missing_parcels.append(parcel)
                    all_parcel_timeseries.append(None)
            else:
                msg = f'Missing split timeseries file for subject {subj_id}, parcel {parcel}, split {split}: {ts_file}'
                if verbose:
                    print(msg)
                append_log(subj_id, f'split{split}', parcel, 'missing', msg)
                missing_parcels.append(parcel)
                all_parcel_timeseries.append(None)
        
        if missing_parcels:
            msg = f'Warning: Subject {subj_id} split {split} missing data for parcels: {missing_parcels}'
            if verbose:
                print(msg)
            append_log(subj_id, f'split{split}', len(missing_parcels), 'warning', msg)
            # Skip this split if too much data is missing
            if len(missing_parcels) > n_parcels * 0.1:  # More than 10% missing
                msg = f'Skipping subject {subj_id} split {split} due to too much missing data'
                if verbose:
                    print(msg)
                append_log(subj_id, f'split{split}', len(missing_parcels), 'skipped', msg)
                continue
        
        # Filter out None values and keep track of valid parcels
        valid_parcels = []
        valid_timeseries = []
        for i, ts in enumerate(all_parcel_timeseries):
            if ts is not None:
                valid_parcels.append(i + 1)  # parcel numbers are 1-indexed
                valid_timeseries.append(ts)
        
        if len(valid_timeseries) == 0:
            msg = f'No valid timeseries found for subject {subj_id} split {split}'
            if verbose:
                print(msg)
            append_log(subj_id, f'split{split}', 0, 'skipped', msg)
            continue
            
        # compute the coarse connectivity profiles
        parcel_average_ts = np.stack([np.mean(ts, axis=1) for ts in valid_timeseries])
        coarse_connectivity_mtx = 1 - squareform(pdist(parcel_average_ts, 'correlation'))
        
        # Save coarse connectomes
        for i, parcel in enumerate(valid_parcels):
            others = np.setdiff1d(np.arange(len(valid_parcels)), i)
            cp = coarse_connectivity_mtx[i][others]
            
            coarse_dir = os.path.join(aligned_connectome_dir, 'coarse', f'parcel_{parcel:03d}')
            os.makedirs(coarse_dir, exist_ok=True)
            np.save(os.path.join(coarse_dir, f'{subj_id}_split_{split}_connectome_parcel_{parcel:03d}.npy'), cp)
            
        # now correlate the coarse TS with the parcel TS to get a fine connectome
        for ts, parcel in zip(valid_timeseries, valid_parcels):
            # Find index of this parcel in valid_parcels
            parcel_idx = valid_parcels.index(parcel)
            others_idx = np.setdiff1d(np.arange(len(valid_parcels)), parcel_idx)
            coarse = parcel_average_ts[others_idx]
            
            try:
                cnx = 1 - cdist(coarse, ts.T, 'correlation')
                fine_dir = os.path.join(aligned_connectome_dir, 'fine', f'parcel_{parcel:03d}')
                os.makedirs(fine_dir, exist_ok=True)
                np.save(os.path.join(fine_dir, f'{subj_id}_split_{split}_connectome_parcel_{parcel:03d}.npy'), cnx)
            except Exception as e:
                msg = f'Error computing fine connectome for subject {subj_id}, parcel {parcel}, split {split}: {e}'
                if verbose:
                    print(msg)
                append_log(subj_id, f'split{split}', parcel, 'error', msg)


def get_available_subjects(aligned_ts_dir, n_parcels):
    """
    Find subjects that have aligned timeseries data available.
    Only returns subjects that have data for at least one parcel.
    """
    subjects = set()
    
    # Look through all parcel directories to find subjects
    for parcel in range(1, n_parcels + 1):
        parcel_dir = os.path.join(aligned_ts_dir, f'parcel_{parcel:03d}')
        if os.path.exists(parcel_dir):
            # Find all aligned timeseries files
            full_files = glob.glob(os.path.join(parcel_dir, '*_aligned_dtseries.npy'))
            split_files = glob.glob(os.path.join(parcel_dir, '*_aligned_dtseries_split_0.npy'))
            
            # Extract subject IDs
            for f in full_files:
                subj_id = os.path.basename(f).replace('_aligned_dtseries.npy', '')
                subjects.add(subj_id)
            
            for f in split_files:
                subj_id = os.path.basename(f).replace('_aligned_dtseries_split_0.npy', '')
                subjects.add(subj_id)
    
    return sorted(list(subjects))

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Build CHA connectomes from hyperaligned data')
    parser.add_argument('--mode', type=str, choices=['full', 'split', 'both'], default='both',
                        help='Build full connectomes, split connectomes, or both (default: both)')
    args = parser.parse_args()

    if verbose:
        print(f"Building CHA connectomes (mode: {args.mode})")

    # Set up directories using utils configuration
    aligned_ts_dir = os.path.join(utils.BASE_OUTDIR, 'hyperalignment_output', 'aligned_timeseries')
    aligned_connectome_dir = os.path.join(utils.BASE_OUTDIR, 'hyperalignment_output', 'connectomes')
    n_parcels = utils.N_PARCELS  # typically 360 for Glasser parcellation
    
    # Check if aligned timeseries directory exists
    if not os.path.exists(aligned_ts_dir):
        msg = f"Error: Aligned timeseries directory not found: {aligned_ts_dir}"
        if verbose:
            print(msg)
            print("Make sure you've run run_hyperalignment_simplified.py first")
        append_log('N/A', 'init', 0, 'error', msg)
        sys.exit(1)
    
    # Automatically find all subjects with aligned timeseries data
    subjects2run = get_available_subjects(aligned_ts_dir, n_parcels)
    if verbose:
        print(f'Found {len(subjects2run)} subjects with aligned timeseries data.')
        if len(subjects2run) > 0:
            print(f'Sample subjects: {subjects2run[:5]}')

    if len(subjects2run) == 0:
        msg = "No subjects with aligned timeseries found"
        if verbose:
            print(msg)
            print(f"\nChecked directory: {aligned_ts_dir}")
            print("This usually means hyperalignment hasn't been run yet, or no test subjects were processed.")
            print("\nTo fix:")
            print("1. Make sure you've run hyperalignment first")
            print("2. Check that hyperalignment produced aligned timeseries in:")
            print(f"   {aligned_ts_dir}/parcel_XXX/*_aligned_dtseries.npy")
        append_log('N/A', 'init', 0, 'error', msg)
        sys.exit(1)

    # Create output directories
    for conn_type in ['coarse', 'fine']:
        for parcel in range(1, n_parcels + 1):
            parcel_dir = os.path.join(aligned_connectome_dir, conn_type, f'parcel_{parcel:03d}')
            os.makedirs(parcel_dir, exist_ok=True)

    # Build job list based on mode argument
    joblist = []
    for s in subjects2run:
        if args.mode in ['full', 'both']:
            joblist.append(delayed(build_cha_full_connectomes)(s, aligned_ts_dir, aligned_connectome_dir, n_parcels))
        if args.mode in ['split', 'both']:
            joblist.append(delayed(build_cha_split_connectomes)(s, aligned_ts_dir, aligned_connectome_dir, n_parcels))

    if verbose:
        print(f"Running {len(joblist)} jobs with {utils.N_JOBS} parallel workers...")
        print(f"Building CHA connectomes: 0/{len(joblist)} completed")

    # Run jobs in parallel with joblib's built-in progress
    Parallel(n_jobs=utils.N_JOBS, verbose=10)(joblist)

    if verbose:
        print(f"\nBuilding CHA connectomes: {len(joblist)}/{len(joblist)} completed")
        print('Finished building connectomes!')
