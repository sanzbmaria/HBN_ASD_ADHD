#!/usr/bin/python3

import numpy as np
import pandas as pd
import utils
import glob, sys, os
from joblib import Parallel, delayed
from scipy.stats import pearsonr

# Try to import mantel if available, otherwise use fallback
try:
    import mantel
    HAS_MANTEL = True
except ImportError:
    HAS_MANTEL = False
    print("Warning: mantel module not found, using fallback implementation")

def mantel_test_fallback(vec1, vec2, method='pearson', permutations=1000):
    """
    Fallback mantel test implementation when mantel module is not available
    """
    # Calculate observed correlation
    if method == 'pearson':
        observed_r, _ = pearsonr(vec1, vec2)
    else:
        raise ValueError("Only pearson method supported")

    # Permutation test
    permuted_r = []
    np.random.seed(42)  # For reproducibility
    for _ in range(permutations):
        perm_vec2 = np.random.permutation(vec2)
        perm_r, _ = pearsonr(vec1, perm_vec2)
        permuted_r.append(perm_r)

    # Calculate p-value (two-tailed)
    permuted_r = np.array(permuted_r)
    p_value = np.sum(np.abs(permuted_r) >= np.abs(observed_r)) / permutations

    # Calculate z-score equivalent
    z_score = (observed_r - np.mean(permuted_r)) / np.std(permuted_r)

    return observed_r, p_value, z_score

def get_valid_ISC_subjects(mat1, mat2=None, include_these=None):
    valid1 = np.argwhere(np.sum(np.isnan(mat1.values), axis=0) < 10)
    if mat2 is not None:
        valid2 = np.argwhere(np.sum(np.isnan(mat2.values), axis=0) < 10)
    else:
        valid2=valid1
    valid_inds = list(np.intersect1d(valid1, valid2))
    valid_subjects = mat1.index[valid_inds]
    if include_these is not None:
        valid_subjects = [v for v in valid_subjects if v in include_these]
    return valid_subjects

def run_reliability(fn0, fn1):
    try:
        mat0 = pd.read_csv(fn0, index_col=0)
        mat1 = pd.read_csv(fn1, index_col=0)
        valid_subs = get_valid_ISC_subjects(mat0, mat1)

        if len(valid_subs) < 2:
            return np.nan, np.nan, np.nan

        triu = np.triu_indices(len(valid_subs),1)
        vec0 = mat0.loc[valid_subs][valid_subs].values[triu]
        vec1 = mat1.loc[valid_subs][valid_subs].values[triu]

        if HAS_MANTEL:
            r,p,z = mantel.test(vec0, vec1, method='pearson')
        else:
            r,p,z = mantel_test_fallback(vec0, vec1, method='pearson')
        return r, p, z
    except Exception as e:
        print(f"Error processing {fn0}, {fn1}: {e}")
        return np.nan, np.nan, np.nan

if __name__ == '__main__':
    # Get output directory from config
    similarity_dir = os.path.join(utils.BASE_OUTDIR, 'similarity_matrices')
    results_dir = os.path.join(utils.BASE_OUTDIR, 'reliability_results')
    os.makedirs(results_dir, exist_ok=True)

    n_jobs = utils.N_JOBS
    df = pd.DataFrame(columns=['align','scale','parcel','r', 'p', 'z'])
    align_vals, scale_vals, parcel_vals = [], [], []
    joblist = []

    print(f"Looking for similarity matrices in: {similarity_dir}")

    # Build job list for ALL parcels (matching Erica's original)
    # This ensures parcel numbers are always present, even if files are missing (will be NaN)
    for a in ['aa','cha']:
        for s in ['coarse','fine']:
            for p in range(1,361):
                fn0 = f'{similarity_dir}/{a}_{s}_split0_parcel_{p:03d}_ISC.csv'
                fn1 = f'{similarity_dir}/{a}_{s}_split1_parcel_{p:03d}_ISC.csv'

                # Always add to job list (like Erica's original)
                # Missing files will result in NaN which we keep in final output
                joblist.append(delayed(run_reliability)(fn0, fn1))
                align_vals.append(a)
                scale_vals.append(s)
                parcel_vals.append(p)

    # Sanity check: should have 1440 jobs (2 alignments × 2 scales × 360 parcels)
    if len(joblist) == 0:
        print("ERROR: No jobs created - this should not happen!")
        sys.exit(1)

    print(f"Total jobs to run: {len(joblist)} (expecting 1440)")

    print(f"Running {len(joblist)} reliability analyses with {n_jobs} jobs...")

    with Parallel(n_jobs=n_jobs, verbose=10) as parallel:
        results = np.array(parallel(joblist))

    df = pd.DataFrame({'align':align_vals,
                      'scale':scale_vals,
                      'parcel':parcel_vals,
                      'r':results[:,0],
                      'p':results[:,1],
                      'z':results[:,2]})

    # Save ALL results including NaN (matching Erica's original)
    output_file = os.path.join(results_dir, 'reliability_results.csv')
    df.to_csv(output_file, index=False)

    print(f"\nResults saved to: {output_file}")

    # For statistics, filter out NaN
    df_valid = df.dropna(subset=['r'])
    n_failed = len(df) - len(df_valid)
    if n_failed > 0:
        print(f"Warning: {n_failed}/{len(df)} analyses failed (NaN in output)")

    print(f"\nOverall statistics (valid results only):")
    print(f"  Mean reliability: {df_valid['r'].mean():.4f}")
    print(f"  Range: [{df_valid['r'].min():.4f}, {df_valid['r'].max():.4f}]")
    print(f"  Significant results (p<0.05): {(df_valid['p'] < 0.05).sum()}/{len(df_valid)}")

    # Print detailed breakdown by alignment and scale
    print("\n" + "="*60)
    print("IDM RELIABILITY SUMMARY")
    print("="*60)

    # Calculate means for each combination
    for alignment in ['aa', 'cha']:
        for scale in ['coarse', 'fine']:
            subset = df_valid[(df_valid['align'] == alignment) & (df_valid['scale'] == scale)]
            if len(subset) > 0:
                mean_r = subset['r'].mean()
                std_r = subset['r'].std()
                min_r = subset['r'].min()
                max_r = subset['r'].max()
                n_parcels = len(subset)
                n_sig = (subset['p'] < 0.05).sum()

                print(f"\n{alignment.upper()} - {scale.capitalize()}:")
                print(f"  Mean reliability (r): {mean_r:.4f} ± {std_r:.4f}")
                print(f"  Range: [{min_r:.4f}, {max_r:.4f}]")
                print(f"  N parcels: {n_parcels}")
                print(f"  Significant (p<0.05): {n_sig}/{n_parcels} ({100*n_sig/n_parcels:.1f}%)")

    # Overall comparison
    print("\n" + "-"*60)
    print("OVERALL COMPARISON")
    print("-"*60)

    # AA vs CHA
    aa_mean = df_valid[df_valid['align'] == 'aa']['r'].mean()
    cha_mean = df_valid[df_valid['align'] == 'cha']['r'].mean()
    print(f"\nAlignment method:")
    print(f"  AA (anatomical):          {aa_mean:.4f}")
    print(f"  CHA (hyperalignment):     {cha_mean:.4f}")
    print(f"  CHA improvement:          {cha_mean - aa_mean:+.4f} ({100*(cha_mean-aa_mean)/aa_mean:+.1f}%)")

    # Coarse vs Fine
    coarse_mean = df_valid[df_valid['scale'] == 'coarse']['r'].mean()
    fine_mean = df_valid[df_valid['scale'] == 'fine']['r'].mean()
    print(f"\nScale:")
    print(f"  Coarse:                   {coarse_mean:.4f}")
    print(f"  Fine:                     {fine_mean:.4f}")
    print(f"  Fine advantage:           {fine_mean - coarse_mean:+.4f} ({100*(fine_mean-coarse_mean)/coarse_mean:+.1f}%)")

    print("\n" + "="*60)
