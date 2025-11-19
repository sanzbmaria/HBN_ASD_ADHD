#!/usr/bin/python3
import numpy as np
import pandas as pd
import utils
import os, sys, glob
from joblib import Parallel, delayed
from scipy.spatial.distance import cdist, pdist, squareform

def filter_subjects_with_files(parcel, connectome_dir, subjects, split=None):
    """Filter subjects to only those with existing connectome files."""
    valid_subjects = []
    for s in subjects:
        if split is None:
            fn = f'{connectome_dir}/{s}_full_connectome_parcel_{parcel:03d}.npy'
        else:
            fn = f'{connectome_dir}/{s}_split_{split}_connectome_parcel_{parcel:03d}.npy'
        if os.path.exists(fn):
            valid_subjects.append(s)
    return valid_subjects

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
    # Filter to only subjects with existing files
    valid_subjects = filter_subjects_with_files(parcel, connectome_dir, subjects, split)
    if len(valid_subjects) < 2:
        print(f'Skipping {alignment}_{scale}_parcel_{parcel:03d} (split={split}): only {len(valid_subjects)} subjects with files')
        return
    if len(valid_subjects) < len(subjects):
        print(f'Warning: {len(subjects) - len(valid_subjects)} subjects missing files for {alignment}_{scale}_parcel_{parcel:03d} (split={split})')

    # load in connectomes
    if split is None:
        cnx = load_full_connectomes(parcel, connectome_dir, valid_subjects)
        outfn = f'{outdir}/{alignment}_{scale}_full_parcel_{parcel:03d}_ISC.csv'
    else:
        cnx = load_split_connectomes(parcel, connectome_dir, valid_subjects, split)
        outfn = f'{outdir}/{alignment}_{scale}_split{split}_parcel_{parcel:03d}_ISC.csv'
    isc_mat = 1-pdist(cnx, 'correlation')
    isc_mat = pd.DataFrame(data=squareform(isc_mat), columns=valid_subjects, index=valid_subjects)
    isc_mat.to_csv(outfn)
    print(f'finished {outfn}')

# subject by subject covariance matrix.
def IS_covariance(scale, alignment, parcel, connectome_dir, outdir, subjects, split=None):
    # Filter to only subjects with existing files
    valid_subjects = filter_subjects_with_files(parcel, connectome_dir, subjects, split)
    if len(valid_subjects) < 2:
        print(f'Skipping {alignment}_{scale}_parcel_{parcel:03d} (split={split}): only {len(valid_subjects)} subjects with files')
        return
    if len(valid_subjects) < len(subjects):
        print(f'Warning: {len(subjects) - len(valid_subjects)} subjects missing files for {alignment}_{scale}_parcel_{parcel:03d} (split={split})')

    # load in connectomes
    if split is None:
        cnx = load_full_connectomes(parcel, connectome_dir, valid_subjects)
        outfn = f'{outdir}/{alignment}_{scale}_full_parcel_{parcel:03d}_COV.csv'
    else:
        cnx = load_split_connectomes(parcel, connectome_dir, valid_subjects, split)
        outfn = f'{outdir}/{alignment}_{scale}_split{split}_parcel_{parcel:03d}_COV.csv'
    cov_mat = np.cov(cnx)
    cov_mat = pd.DataFrame(data=cov_mat, columns=valid_subjects, index=valid_subjects)
    cov_mat.to_csv(outfn)
    print(f'finished {outfn}')



if __name__ == "__main__":
    parcel = int(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'single'

    # Get connectome mode from environment
    connectome_mode = os.environ.get('CONNECTOME_MODE', 'both')

    # Get subject lists
    # AA connectomes exist for ALL subjects (train + test)
    # CHA connectomes only exist for TEST subjects
    reliability_subjects = utils.get_reliability_subjects()  # These are test subjects when using Excel
    test_subjects = utils.get_test_subjects()  # Only test subjects for CHA

    # For AA, use all subjects from metadata (both train and test)
    all_metadata_subjects = utils.load_metadata_subjects()
    if all_metadata_subjects is not None:
        # Filter to subjects with files
        discovered = utils._discover_subject_ids()
        aa_subjects = [s for s in all_metadata_subjects if s in discovered]
    else:
        # Fallback: use reliability subjects
        aa_subjects = reliability_subjects

    print(f"AA subjects: {len(aa_subjects)}")
    print(f"CHA/Test subjects: {len(test_subjects)}")
    print(f"Reliability subjects: {len(reliability_subjects)}")

    outdir = os.path.join(utils.BASE_OUTDIR, 'similarity_matrices')
    aa_dir = utils.BASE_OUTDIR  # AA connectomes directory
    cha_dir = os.path.join(utils.BASE_OUTDIR, 'hyperalignment_output', 'connectomes')  # CHA connectomes

    # Create output directory
    os.makedirs(outdir, exist_ok=True)

    if mode == 'single':
        # Run for single parcel (original behavior)
        joblist = []
        for alignment, conndir in zip(['aa','cha'],[aa_dir, cha_dir]):
            # Use appropriate subjects: AA uses all, CHA uses test only
            subjects_for_full = aa_subjects if alignment == 'aa' else test_subjects
            subjects_for_split = reliability_subjects  # Test subjects for split

            for scale in ['coarse','fine']:
                dn = os.path.join(conndir, scale, f'parcel_{parcel:03d}')
                # Only compute full connectome matrices if mode includes full
                # AA always has full (because we auto-build both), CHA only has full if mode is 'full' or 'both'
                if connectome_mode in ['full', 'both'] or alignment == 'aa':
                    joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, subjects_for_full, split=None))
                    joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, subjects_for_full, split=None))
                # Only compute split matrices if mode includes split
                if connectome_mode in ['split', 'both']:
                    joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, subjects_for_split, split=0))
                    joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, subjects_for_split, split=1))
                    joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, subjects_for_split, split=0))
                    joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, subjects_for_split, split=1))

        print(f"Processing parcel {parcel}...")
        print(f"Running {len(joblist)} similarity jobs...")
        Parallel(n_jobs=utils.N_JOBS, verbose=10)(joblist)
        print(f"Finished parcel {parcel}")

    elif mode == 'batch':
        # Run all 360 parcels
        print(f"Running batch mode for all 360 parcels...")
        print(f"Connectome mode: {connectome_mode}")

        for p in range(1, 361):
            print(f"\nProcessing parcel {p}/360...")
            joblist = []
            for alignment, conndir in zip(['aa','cha'],[aa_dir, cha_dir]):
                # Use appropriate subjects: AA uses all, CHA uses test only
                subjects_for_full = aa_subjects if alignment == 'aa' else test_subjects
                subjects_for_split = reliability_subjects  # Test subjects for split

                for scale in ['coarse','fine']:
                    dn = os.path.join(conndir, scale, f'parcel_{p:03d}')
                    if not os.path.exists(dn):
                        print(f"Warning: Directory not found: {dn}")
                        continue
                    # Only compute full connectome matrices if mode includes full
                    # AA always has full (because we auto-build both), CHA only has full if mode is 'full' or 'both'
                    if connectome_mode in ['full', 'both'] or alignment == 'aa':
                        joblist.append(delayed(ISC)(scale, alignment, p, dn, outdir, subjects_for_full, split=None))
                        joblist.append(delayed(IS_covariance)(scale, alignment, p, dn, outdir, subjects_for_full, split=None))
                    # Only compute split matrices if mode includes split
                    if connectome_mode in ['split', 'both']:
                        joblist.append(delayed(ISC)(scale, alignment, p, dn, outdir, subjects_for_split, split=0))
                        joblist.append(delayed(ISC)(scale, alignment, p, dn, outdir, subjects_for_split, split=1))
                        joblist.append(delayed(IS_covariance)(scale, alignment, p, dn, outdir, subjects_for_split, split=0))
                        joblist.append(delayed(IS_covariance)(scale, alignment, p, dn, outdir, subjects_for_split, split=1))

            if joblist:
                print(f"  Running {len(joblist)} similarity jobs for parcel {p}...")
                Parallel(n_jobs=utils.N_JOBS, verbose=10)(joblist)
        print("\nFinished all parcels")
    else:
        print(f"Unknown mode: {mode}. Use 'single' or 'batch'")
        sys.exit(1)
