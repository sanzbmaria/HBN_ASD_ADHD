#!/usr/bin/python3
import numpy as np
import pandas as pd
import utils
import os, sys, glob
from joblib import Parallel, delayed
from scipy.spatial.distance import cdist, pdist, squareform

def load_full_connectomes(parcel, connectome_dir, subjects):
    connectome_list = []
    for s in subjects:
        fn = f'{connectome_dir}/{s}_full_connectome_parcel_{parcel:03d}.npy'
        connectome_list.append(np.load(fn).ravel())
    print(f"parcel {parcel} stacked shape {np.shape(connectome_list)}")
    return np.stack(connectome_list)

def load_split_connectomes(parcel, connectome_dir, subjects, split):
    connectome_list = []
    for s in subjects:
        fn = f'{connectome_dir}/{s}_split_{split}_connectome_parcel_{parcel:03d}.npy'
        connectome_list.append(np.load(fn).ravel())
    print(f"parcel {parcel} split {split} stacked shape {np.shape(connectome_list)}")
    return np.stack(connectome_list)


# subject by subject correlation matrix.
def ISC(scale, alignment, parcel, connectome_dir, outdir, subjects, split=None):
    # Ensure subjects are strings for consistent CSV output
    subjects = [str(s) for s in subjects]

    # load in connectomes
    if split is None:
        cnx = load_full_connectomes(parcel, connectome_dir, subjects)
        outfn = f'{outdir}/{alignment}_{scale}_full_parcel_{parcel:03d}_ISC.csv'
    else:
        cnx = load_split_connectomes(parcel, connectome_dir, subjects, split)
        outfn = f'{outdir}/{alignment}_{scale}_split{split}_parcel_{parcel:03d}_ISC.csv'
    isc_mat = 1-pdist(cnx, 'correlation')
    isc_mat = pd.DataFrame(data=squareform(isc_mat), columns=subjects, index=subjects)
    isc_mat.to_csv(outfn)
    print(f'finished {outfn}')

# subject by subject covariance matrix.
def IS_covariance(scale, alignment, parcel, connectome_dir, outdir, subjects, split=None):
    # Ensure subjects are strings for consistent CSV output
    subjects = [str(s) for s in subjects]

    # load in connectomes
    if split is None:
        cnx = load_full_connectomes(parcel, connectome_dir, subjects)
        outfn = f'{outdir}/{alignment}_{scale}_full_parcel_{parcel:03d}_COV.csv'
    else:
        cnx = load_split_connectomes(parcel, connectome_dir, subjects, split)
        outfn = f'{outdir}/{alignment}_{scale}_split{split}_parcel_{parcel:03d}_COV.csv'
    cov_mat = np.cov(cnx)
    cov_mat = pd.DataFrame(data=cov_mat, columns=subjects, index=subjects)
    cov_mat.to_csv(outfn)
    print(f'finished {outfn}')


def get_available_subjects(connectome_dir, parcel, connectome_mode):
    """
    Find subjects that actually have connectome files available.

    Parameters:
    -----------
    connectome_dir : str
        Directory containing connectome files (e.g., coarse/parcel_001/)
    parcel : int
        Parcel number
    connectome_mode : str
        'full', 'split', or 'both'

    Returns:
    --------
    full_subjects : list
        Subjects with full connectomes (empty if mode is 'split')
    split_subjects : list
        Subjects with split connectomes (empty if mode is 'full')
    """
    full_subjects = []
    split_subjects = []

    # Check for full connectomes
    if connectome_mode in ['full', 'both']:
        full_pattern = os.path.join(connectome_dir, f'*_full_connectome_parcel_{parcel:03d}.npy')
        full_files = glob.glob(full_pattern)
        full_subjects = [os.path.basename(f).split('_full_connectome')[0] for f in full_files]

    # Check for split connectomes
    if connectome_mode in ['split', 'both']:
        split_pattern = os.path.join(connectome_dir, f'*_split_0_connectome_parcel_{parcel:03d}.npy')
        split_files = glob.glob(split_pattern)
        split_subjects = [os.path.basename(f).split('_split_0_connectome')[0] for f in split_files]

    return full_subjects, split_subjects


if __name__ == "__main__":
    parcel = int(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'single'

    # Get connectome mode from environment
    connectome_mode = os.environ.get('CONNECTOME_MODE', 'both')

    twin_subjects = utils.load_twin_subjects()
    reliability_subjects = utils.get_reliability_subjects()
    all_subjects = list(set(twin_subjects + reliability_subjects))

    outdir = os.path.join(utils.BASE_OUTDIR, 'similarity_matrices')
    aa_dir = utils.BASE_OUTDIR  # AA connectomes directory
    cha_dir = os.path.join(utils.BASE_OUTDIR, 'hyperalignment_output', 'connectomes')  # CHA connectomes

    # Create output directory
    os.makedirs(outdir, exist_ok=True)

    if mode == 'single':
        # Run for single parcel (original behavior)
        joblist = []
        for alignment, conndir in zip(['aa','cha'],[aa_dir, cha_dir]):
            for scale in ['coarse','fine']:
                dn = os.path.join(conndir, scale, f'parcel_{parcel:03d}')
                if not os.path.exists(dn):
                    print(f"Warning: Directory not found: {dn}")
                    continue

                # Discover which subjects have files for this alignment/scale
                available_full, available_split = get_available_subjects(dn, parcel, connectome_mode)

                # Only compute full connectome matrices if mode includes full
                if connectome_mode in ['full', 'both'] and available_full:
                    # Filter to subjects that have files
                    filtered_full = [s for s in all_subjects if s in available_full]
                    if filtered_full:
                        print(f"  {alignment}/{scale}: {len(filtered_full)} subjects with full connectomes")
                        joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, filtered_full, split=None))
                        joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, filtered_full, split=None))

                # Only compute split matrices if mode includes split
                if connectome_mode in ['split', 'both'] and available_split:
                    # Filter to subjects that have files
                    filtered_split = [s for s in reliability_subjects if s in available_split]
                    if filtered_split:
                        print(f"  {alignment}/{scale}: {len(filtered_split)} subjects with split connectomes")
                        joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, filtered_split, split=0))
                        joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, filtered_split, split=1))
                        joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, filtered_split, split=0))
                        joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, filtered_split, split=1))

        print(f"Processing parcel {parcel}...")
        print(f"Running {len(joblist)} similarity jobs...")
        Parallel(n_jobs=utils.N_JOBS, verbose=10)(joblist)
        print(f"Finished parcel {parcel}")

    elif mode == 'batch':
        # Run all 360 parcels
        print(f"Running batch mode for all 360 parcels...")
        print(f"Connectome mode: {connectome_mode}")
        print(f"Total subjects: {len(all_subjects)}")
        print(f"Reliability subjects: {len(reliability_subjects)}")

        for p in range(1, 361):
            print(f"\nProcessing parcel {p}/360...")
            joblist = []
            for alignment, conndir in zip(['aa','cha'],[aa_dir, cha_dir]):
                for scale in ['coarse','fine']:
                    dn = os.path.join(conndir, scale, f'parcel_{p:03d}')
                    if not os.path.exists(dn):
                        print(f"  Warning: Directory not found: {dn}")
                        continue

                    # Discover which subjects have files for this alignment/scale
                    available_full, available_split = get_available_subjects(dn, p, connectome_mode)

                    # Only compute full connectome matrices if mode includes full
                    if connectome_mode in ['full', 'both'] and available_full:
                        # Filter to subjects that have files
                        filtered_full = [s for s in all_subjects if s in available_full]
                        if filtered_full:
                            joblist.append(delayed(ISC)(scale, alignment, p, dn, outdir, filtered_full, split=None))
                            joblist.append(delayed(IS_covariance)(scale, alignment, p, dn, outdir, filtered_full, split=None))

                    # Only compute split matrices if mode includes split
                    if connectome_mode in ['split', 'both'] and available_split:
                        # Filter to subjects that have files
                        filtered_split = [s for s in reliability_subjects if s in available_split]
                        if filtered_split:
                            joblist.append(delayed(ISC)(scale, alignment, p, dn, outdir, filtered_split, split=0))
                            joblist.append(delayed(ISC)(scale, alignment, p, dn, outdir, filtered_split, split=1))
                            joblist.append(delayed(IS_covariance)(scale, alignment, p, dn, outdir, filtered_split, split=0))
                            joblist.append(delayed(IS_covariance)(scale, alignment, p, dn, outdir, filtered_split, split=1))

            if joblist:
                print(f"  Running {len(joblist)} similarity jobs for parcel {p}...")
                Parallel(n_jobs=utils.N_JOBS, verbose=10)(joblist)
        print("\nFinished all parcels")
    else:
        print(f"Unknown mode: {mode}. Use 'single' or 'batch'")
        sys.exit(1)
