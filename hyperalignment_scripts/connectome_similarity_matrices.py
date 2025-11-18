#!/usr/bin/python3
import numpy as np
import pandas as pd
import utils as utils
import os, sys, glob
from joblib import Parallel, delayed
from scipy.spatial.distance import cdist, pdist, squareform
from tqdm import tqdm

def discover_subjects(connectome_dir, parcel, alignment_type='full'):
    """
    Discover available subjects for a given parcel and alignment type
    alignment_type can be 'full', 0 (split0), or 1 (split1)
    """
    if alignment_type == 'full':
        pattern = f'{connectome_dir}/*_full_connectome_parcel_{parcel:03d}.npy'
        files = glob.glob(pattern)
        subjects = [os.path.basename(f).split('_full_connectome')[0] for f in files]
    else:
        # Support both split0 and split_0 patterns for backward compatibility
        pattern1 = f'{connectome_dir}/*_split{alignment_type}_connectome_parcel_{parcel:03d}.npy'
        pattern2 = f'{connectome_dir}/*_split_{alignment_type}_connectome_parcel_{parcel:03d}.npy'
        files1 = glob.glob(pattern1)
        files2 = glob.glob(pattern2)
        subjects1 = [os.path.basename(f).split(f'_split{alignment_type}_connectome')[0] for f in files1]
        subjects2 = [os.path.basename(f).split(f'_split_{alignment_type}_connectome')[0] for f in files2]
        subjects = subjects1 + subjects2
    return sorted(set(subjects))

def load_full_connectomes(parcel, connectome_dir, subjects):
    connectome_list = []
    missing_subjects = []

    for s in subjects:
        fn = f'{connectome_dir}/{s}_full_connectome_parcel_{parcel:03d}.npy'
        try:
            if os.path.exists(fn):
                connectome_list.append(np.load(fn).ravel())
            else:
                missing_subjects.append(s)
        except Exception as e:
            print(f"Error loading {fn}: {e}")
            missing_subjects.append(s)

    if missing_subjects:
        print(f"Warning: Missing {len(missing_subjects)} subjects for parcel {parcel}")

    if len(connectome_list) == 0:
        raise ValueError(f"No valid connectomes found for parcel {parcel}")

    print(f"parcel {parcel} stacked shape {np.shape(connectome_list)}")
    return np.stack(connectome_list), [s for s in subjects if s not in missing_subjects]

def load_split_connectomes(parcel, connectome_dir, subjects, split):
    """
    Load split connectomes, supporting both naming patterns:
    - New pattern: *_split_{split}_connectome_* (with underscore before number)
    - Old pattern: *_split{split}_connectome_* (without underscore before number)
    """
    connectome_list = []
    missing_subjects = []

    for s in subjects:
        # Try new pattern first: _split_0_ or _split_1_
        fn_new = f'{connectome_dir}/{s}_split_{split}_connectome_parcel_{parcel:03d}.npy'
        # Fallback to old pattern: _split0_ or _split1_
        fn_old = f'{connectome_dir}/{s}_split{split}_connectome_parcel_{parcel:03d}.npy'

        fn = None
        if os.path.exists(fn_new):
            fn = fn_new
        elif os.path.exists(fn_old):
            fn = fn_old

        if fn:
            try:
                arr = np.load(fn)
                if arr is None or arr.size == 0:
                    print(f"Warning: File is empty or corrupted: {fn}")
                    missing_subjects.append(s)
                else:
                    connectome_list.append(arr.ravel())
            except Exception as e:
                print(f"Error loading {fn}: {e}")
                missing_subjects.append(s)
        else:
            missing_subjects.append(s)

    if missing_subjects:
        print(f"Warning: Missing {len(missing_subjects)} subjects for parcel {parcel}, split {split}")

    if len(connectome_list) == 0:
        raise ValueError(f"No valid split connectomes found for parcel {parcel}, split {split}")

    print(f"parcel {parcel} split {split} stacked shape {np.shape(connectome_list)}")
    return np.stack(connectome_list), [s for s in subjects if s not in missing_subjects]

# subject by subject correlation matrix.
def ISC(scale, alignment, parcel, connectome_dir, outdir, subjects, split=None):
    try:
        # load in connectomes
        if split is None:
            cnx, valid_subjects = load_full_connectomes(parcel, connectome_dir, subjects)
            outfn = f'{outdir}/{alignment}_{scale}_full_parcel_{parcel:03d}_ISC.csv'
        else:
            cnx, valid_subjects = load_split_connectomes(parcel, connectome_dir, subjects, split)
            outfn = f'{outdir}/{alignment}_{scale}_split{split}_parcel_{parcel:03d}_ISC.csv'

        isc_mat = 1-pdist(cnx, 'correlation')
        isc_mat = pd.DataFrame(data=squareform(isc_mat), columns=valid_subjects, index=valid_subjects)
        isc_mat.to_csv(outfn)
        print(f'finished {outfn}')
    except Exception as e:
        print(f"Error in ISC for {alignment} {scale} parcel {parcel} split {split}: {e}")

# subject by subject covariance matrix.
def IS_covariance(scale, alignment, parcel, connectome_dir, outdir, subjects, split=None):
    try:
        # load in connectomes
        if split is None:
            cnx, valid_subjects = load_full_connectomes(parcel, connectome_dir, subjects)
            outfn = f'{outdir}/{alignment}_{scale}_full_parcel_{parcel:03d}_COV.csv'
        else:
            cnx, valid_subjects = load_split_connectomes(parcel, connectome_dir, subjects, split)
            outfn = f'{outdir}/{alignment}_{scale}_split{split}_parcel_{parcel:03d}_COV.csv'

        cov_mat = np.cov(cnx)
        cov_mat = pd.DataFrame(data=cov_mat, columns=valid_subjects, index=valid_subjects)
        cov_mat.to_csv(outfn)
        print(f'finished {outfn}')
    except Exception as e:
        print(f"Error in covariance for {alignment} {scale} parcel {parcel} split {split}: {e}")


def is_parcel_complete(parcel, all_subjects, split_subjects, outdir):
    """
    Check if all expected output files exist for a parcel
    Returns True if parcel is complete, False otherwise
    """
    expected_files = []

    # Check for all combinations of alignment, scale, metric, and split
    for alignment in ['aa', 'cha']:
        for scale in ['coarse', 'fine']:
            for metric in ['ISC', 'COV']:
                # Full connectome files (if applicable)
                if len(all_subjects) > 0:
                    fn = f'{outdir}/{alignment}_{scale}_full_parcel_{parcel:03d}_{metric}.csv'
                    expected_files.append(fn)

                # Split connectome files (if applicable)
                if len(split_subjects) > 0:
                    for split in [0, 1]:
                        fn = f'{outdir}/{alignment}_{scale}_split{split}_parcel_{parcel:03d}_{metric}.csv'
                        expected_files.append(fn)

    # Check if all expected files exist
    all_exist = all(os.path.exists(fn) for fn in expected_files)
    return all_exist


def process_single_parcel(parcel, all_subjects, split_subjects, outdir, aa_dir, cha_dir, n_jobs=1):
    """Process a single parcel"""
    joblist = []

    for alignment, conndir in zip(['aa','cha'], [aa_dir, cha_dir]):
        for scale in ['coarse','fine']:
            dn = os.path.join(conndir, scale, f'parcel_{parcel:03d}')
            # Check if directory exists
            if not os.path.exists(dn):
                print(f"Directory does not exist: {dn}, skipping {alignment} {scale} parcel {parcel}")
                continue
            # Only run full connectome analysis if full connectomes are available
            if len(all_subjects) > 0:
                joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, all_subjects, split=None))
                joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, all_subjects, split=None))
            # Only run split connectome analysis if split connectomes are available
            if len(split_subjects) > 0:
                joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, split_subjects, split=0))
                joblist.append(delayed(ISC)(scale, alignment, parcel, dn, outdir, split_subjects, split=1))
                joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, split_subjects, split=0))
                joblist.append(delayed(IS_covariance)(scale, alignment, parcel, dn, outdir, split_subjects, split=1))

    # Run jobs for this parcel
    if joblist:
        with Parallel(n_jobs=n_jobs) as parallel:
            parallel(joblist)

    return parcel


def process_parcel_with_error_handling(p, all_subjects, split_subjects, outdir, aa_dir, cha_dir, n_jobs):
    """Wrapper to handle errors gracefully during batch processing"""
    try:
        return process_single_parcel(p, all_subjects, split_subjects, outdir, aa_dir, cha_dir, n_jobs)
    except Exception as e:
        print(f"\nError processing parcel {p}: {e}")
        return None


if __name__ == "__main__":
    # Handle both command line and Jupyter notebook execution
    if len(sys.argv) < 2 or any('kernel' in arg or '--f=' in arg for arg in sys.argv):
        # Running in Jupyter or no arguments provided
        print("Running in interactive mode...")
        print("Set parcel and mode manually:")
        parcel = 1  # Default parcel
        mode = 'single'  # Default mode
        print(f"Using parcel {parcel} in {mode} mode")
        print("To change these, modify the parcel and mode variables in the script")
    else:
        # Running from command line
        try:
            # Filter out Jupyter-specific arguments
            clean_args = [arg for arg in sys.argv if not ('kernel' in arg or '--f=' in arg or arg.startswith('-'))]
            if len(clean_args) < 2:
                print("Usage: python connectome_similarity_matrices.py <parcel_number> [mode]")
                print("  parcel_number: parcel to analyze")
                print("  mode: 'single' for one parcel, 'batch' for multiple parcels (default: single)")
                sys.exit(1)

            parcel = int(clean_args[1])
            mode = clean_args[2] if len(clean_args) > 2 else 'single'
        except ValueError as e:
            print(f"Error parsing arguments: {e}")
            print("Usage: python connectome_similarity_matrices.py <parcel_number> [mode]")
            sys.exit(1)

    # Set up directories based on your structure
    outdir = os.path.join(utils.BASE_OUTDIR, 'similarity_matrices')
    aa_dir = utils.BASE_OUTDIR  # AA connectomes directory (will look in fine/coarse subdirs)
    cha_dir = os.path.join(utils.BASE_OUTDIR, 'hyperalignment_output', 'connectomes')  # CHA connectomes

    # Check if directories exist
    aa_fine_dir = os.path.join(aa_dir, 'fine')
    if not os.path.exists(aa_fine_dir):
        print(f"Error: AA connectome directory not found: {aa_fine_dir}")
        print("Make sure you've run build_aa_connectomes.py first")
        sys.exit(1)

    cha_fine_dir = os.path.join(cha_dir, 'fine')
    if not os.path.exists(cha_fine_dir):
        print(f"Error: CHA connectome directory not found: {cha_fine_dir}")
        print("Make sure you've run build_CHA_connectomes.py first")
        sys.exit(1)

    # Get subjects from available data
    print("Discovering available subjects...")

    # Find subjects from AA and CHA data (try full first, fallback to split)
    aa_sample_dir = os.path.join(aa_fine_dir, 'parcel_001')
    cha_sample_dir = os.path.join(cha_fine_dir, 'parcel_001')

    # Try to find full connectomes
    aa_full_subjects = discover_subjects(aa_sample_dir, 1, 'full') if os.path.exists(aa_sample_dir) else []
    cha_full_subjects = discover_subjects(cha_sample_dir, 1, 'full') if os.path.exists(cha_sample_dir) else []

    print(f"Found {len(aa_full_subjects)} AA full subjects")
    print(f"Found {len(cha_full_subjects)} CHA full subjects")

    all_subjects = sorted(list(set(aa_full_subjects).intersection(set(cha_full_subjects))))

    # If no full connectomes, use split connectomes
    if len(all_subjects) == 0:
        print("No common full connectome subjects found, trying split connectomes...")
        aa_split0 = discover_subjects(aa_sample_dir, 1, 0) if os.path.exists(aa_sample_dir) else []
        aa_split1 = discover_subjects(aa_sample_dir, 1, 1) if os.path.exists(aa_sample_dir) else []
        cha_split0 = discover_subjects(cha_sample_dir, 1, 0) if os.path.exists(cha_sample_dir) else []
        cha_split1 = discover_subjects(cha_sample_dir, 1, 1) if os.path.exists(cha_sample_dir) else []

        print(f"AA split0: {len(aa_split0)} subjects, sample: {aa_split0[:5]}")
        print(f"AA split1: {len(aa_split1)} subjects, sample: {aa_split1[:5]}")
        print(f"CHA split0: {len(cha_split0)} subjects, sample: {cha_split0[:5]}")
        print(f"CHA split1: {len(cha_split1)} subjects, sample: {cha_split1[:5]}")

        split_subjects = sorted(list(
            set(aa_split0).intersection(set(aa_split1))
            .intersection(set(cha_split0))
            .intersection(set(cha_split1))
        ))
        print(f"Found {len(split_subjects)} subjects with split connectomes (intersection)")
        if len(split_subjects) > 0:
            print(f"Sample split subjects: {split_subjects[:5]}")
            # Keep all_subjects empty since we only have split connectomes
        else:
            print("ERROR: No common subjects found between AA and CHA split datasets")
            sys.exit(1)
    else:
        split_subjects = []
        print(f"Found {len(all_subjects)} subjects with full connectomes")
        print(f"Sample full subjects: {all_subjects[:5]}")

    # Create output directory
    os.makedirs(outdir, exist_ok=True)

    if mode == 'single':
        # Run analysis for single parcel
        print(f"\nProcessing single parcel: {parcel}")

        process_single_parcel(parcel, all_subjects, split_subjects, outdir, aa_dir, cha_dir, n_jobs=utils.N_JOBS)

        print(f"Finished parcel {parcel}")

    elif mode == 'batch':
        # Run analysis for all 360 parcels with parallelization
        print(f"\nProcessing all 360 parcels")
        print(f"Total subjects (full): {len(all_subjects)}")
        print(f"Total subjects (splits): {len(split_subjects)}")

        # Smart parallelization: balance parcel-level and task-level parallelism
        # Use sqrt approach to avoid CPU oversubscription
        import math
        total_jobs = utils.N_JOBS
        n_parcel_jobs = max(1, int(math.sqrt(total_jobs)))  # Parcels in parallel
        n_task_jobs = max(1, total_jobs // n_parcel_jobs)    # Tasks per parcel

        print(f"Parallelization: {n_parcel_jobs} parcels × {n_task_jobs} tasks/parcel = {n_parcel_jobs * n_task_jobs} total jobs")

        # Check which parcels are already complete (resumability)
        print("Checking for already completed parcels...")
        all_parcels = list(range(1, 361))
        completed_parcels = [p for p in all_parcels if is_parcel_complete(p, all_subjects, split_subjects, outdir)]
        incomplete_parcels = [p for p in all_parcels if p not in completed_parcels]

        print(f"Already completed: {len(completed_parcels)} parcels")
        print(f"Remaining: {len(incomplete_parcels)} parcels")

        if len(incomplete_parcels) == 0:
            print("All parcels already completed!")
            sys.exit(0)

        # Create job list only for incomplete parcels
        parcel_jobs = [
            delayed(process_parcel_with_error_handling)(p, all_subjects, split_subjects, outdir, aa_dir, cha_dir, n_task_jobs)
            for p in incomplete_parcels
        ]

        # Process parcels in parallel with progress tracking
        print(f"Starting parallel processing of {len(incomplete_parcels)} parcels...")
        with Parallel(n_jobs=n_parcel_jobs, verbose=10) as parallel:
            results = parallel(parcel_jobs)

        # Report any failed parcels
        failed_parcels = [incomplete_parcels[i] for i, r in enumerate(results) if r is None]
        if failed_parcels:
            print(f"\nWarning: {len(failed_parcels)} parcels failed: {failed_parcels[:10]}{'...' if len(failed_parcels) > 10 else ''}")

        print("\nFinished all parcels!")
        print(f"Results saved in: {outdir}")

        # Show sample output files
        sample_files = glob.glob(os.path.join(outdir, '*_ISC.csv'))[:5]
        if sample_files:
            print("\nSample output files:")
            for f in sample_files:
                print(f"  {os.path.basename(f)}")

    else:
        print(f"Unknown mode: {mode}")
        print("Use 'single' or 'batch'")
        sys.exit(1)
