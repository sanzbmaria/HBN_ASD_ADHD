#!/usr/bin/python3
#%%
import numpy as np
import pandas as pd
import os, sys, glob
from joblib import Parallel, delayed
from scipy.stats import pearsonr
import utils as utils

# Adapter to use utils_test configuration instead of hardcoded paths
class ConfigAdapter:
    """Adapter to use utils_test configuration"""
    def __init__(self):
        self.similarity_dir = os.path.join(utils.BASE_OUTDIR, "similarity_matrices")
        self.results_dir = os.path.join(utils.BASE_OUTDIR, "reliability_results")
        self.n_jobs = utils.N_JOBS

        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)

# Global config object
config = ConfigAdapter()

def mantel_test(vec1, vec2, method='pearson', permutations=1000):
    """
    Simplified mantel test implementation
    Based on the original mantel import but self-contained
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
    """
    Get subjects with valid data - adapted from original
    """
    valid1 = np.argwhere(np.sum(np.isnan(mat1.values), axis=0) < 10)
    if mat2 is not None:
        valid2 = np.argwhere(np.sum(np.isnan(mat2.values), axis=0) < 10)
    else:
        valid2 = valid1
    valid_inds = list(np.intersect1d(valid1, valid2))
    valid_subjects = mat1.index[valid_inds]
    if include_these is not None:
        valid_subjects = [v for v in valid_subjects if v in include_these]
    return valid_subjects

def run_reliability(fn0, fn1):
    """
    Run reliability analysis on split-half similarity matrices
    """
    try:
        mat0 = pd.read_csv(fn0, index_col=0)
        mat1 = pd.read_csv(fn1, index_col=0)
        valid_subs = get_valid_ISC_subjects(mat0, mat1)
        
        if len(valid_subs) < 2:
            print(f"Not enough valid subjects for {fn0} and {fn1}")
            return np.nan, np.nan, np.nan
            
        triu = np.triu_indices(len(valid_subs), 1)
        vec0 = mat0.loc[valid_subs][valid_subs].values[triu]
        vec1 = mat1.loc[valid_subs][valid_subs].values[triu]
        
        # Check for valid data
        if len(vec0) == 0 or len(vec1) == 0:
            return np.nan, np.nan, np.nan
            
        r, p, z = mantel_test(vec0, vec1, method='pearson')
        return r, p, z
        
    except Exception as e:
        print(f"Error processing {fn0} and {fn1}: {e}")
        return np.nan, np.nan, np.nan

def build_file_paths():
    """
    Find all split matrix pairs dynamically
    """
    file_specs = []
    
    # Find all files with split0 in similarity directory
    pattern = os.path.join(config.similarity_dir, "*split0*.csv")
    split0_files = glob.glob(pattern)
    
    for split0_file in split0_files:
        # Generate corresponding split1 filename
        split1_file = split0_file.replace('split0', 'split1')
        
        if os.path.exists(split1_file):
            # Parse the filename to extract components
            basename = os.path.basename(split0_file)
            parts = basename.replace('.csv', '').split('_')
            
            if len(parts) >= 4:
                align = parts[0]  # aa or cha
                scale = parts[1]  # fine or coarse  
                metric = parts[-1]  # ISC or COV
                
                file_specs.append({
                    'align': align,
                    'scale': scale,
                    'metric': metric,
                    'fn0': split0_file,
                    'fn1': split1_file
                })
    
    return file_specs

if __name__ == '__main__':
    print("=== IDM RELIABILITY ANALYSIS ===")
    print(f"Similarity matrices directory: {config.similarity_dir}")
    
    # Create results dataframe
    df = pd.DataFrame(columns=['align', 'scale', 'metric', 'r', 'p', 'z'])
    
    # Build file specifications dynamically
    file_specs = build_file_paths()
    
    if not file_specs:
        print("No split matrix pairs found!")
        print(f"Looking in: {config.similarity_dir}")
        print("Expected files with 'split0' and 'split1' in filename")
        print("Make sure you've run connectome_similarity_matrices.py first")
        sys.exit(1)
    
    print(f"Found {len(file_specs)} split matrix pairs")
    
    # Prepare job list
    align_vals, scale_vals, metric_vals = [], [], []
    joblist = []
    
    for spec in file_specs:
        joblist.append(delayed(run_reliability)(spec['fn0'], spec['fn1']))
        align_vals.append(spec['align'])
        scale_vals.append(spec['scale'])
        metric_vals.append(spec['metric'])
        print(f"Queued: {spec['align']}_{spec['scale']}_{spec['metric']}")
    
    # Run parallel jobs
    print(f"Running {len(joblist)} reliability analyses with {config.n_jobs} jobs...")
    
    with Parallel(n_jobs=config.n_jobs, verbose=10) as parallel:
        results = np.array(parallel(joblist))
    
    # Build results dataframe
    df = pd.DataFrame({
        'align': align_vals,
        'scale': scale_vals, 
        'metric': metric_vals,
        'r': results[:, 0],
        'p': results[:, 1],
        'z': results[:, 2]
    })
    
    # Filter out NaN results
    df_clean = df.dropna(subset=['r'])
    if len(df_clean) < len(df):
        print(f"Warning: {len(df) - len(df_clean)} analyses failed")
    
    if len(df_clean) == 0:
        print("Error: No successful reliability analyses")
        sys.exit(1)
    
    # Save results
    output_file = os.path.join(config.results_dir, 'reliability_results.csv')
    df_clean.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")
    
    # Print summary
    print("\n=== RELIABILITY RESULTS SUMMARY ===")
    print(df_clean.to_string(index=False, float_format='%.4f'))
    
    print(f"\nMean reliability: {df_clean['r'].mean():.4f}")
    print(f"Range: [{df_clean['r'].min():.4f}, {df_clean['r'].max():.4f}]")
    print(f"Significant results (p<0.05): {(df_clean['p'] < 0.05).sum()}/{len(df_clean)}")
    
    # Specific comparisons as in the original paper
    print("\n=== COMPARISONS ===")
    
    # Compare alignment methods
    if 'aa' in df_clean['align'].values and 'cha' in df_clean['align'].values:
        aa_mean = df_clean[df_clean['align'] == 'aa']['r'].mean()
        cha_mean = df_clean[df_clean['align'] == 'cha']['r'].mean()
        print(f"AA mean reliability: {aa_mean:.4f}")
        print(f"CHA mean reliability: {cha_mean:.4f}")
        print(f"CHA improvement: {cha_mean - aa_mean:+.4f}")
    
    # Compare scales
    if 'fine' in df_clean['scale'].values and 'coarse' in df_clean['scale'].values:
        fine_mean = df_clean[df_clean['scale'] == 'fine']['r'].mean()
        coarse_mean = df_clean[df_clean['scale'] == 'coarse']['r'].mean()
        print(f"Fine scale mean: {fine_mean:.4f}")
        print(f"Coarse scale mean: {coarse_mean:.4f}")
        print(f"Fine advantage: {fine_mean - coarse_mean:+.4f}")
    
    # Compare metrics
    if 'ISC' in df_clean['metric'].values and 'COV' in df_clean['metric'].values:
        isc_mean = df_clean[df_clean['metric'] == 'ISC']['r'].mean()
        cov_mean = df_clean[df_clean['metric'] == 'COV']['r'].mean()
        print(f"ISC mean reliability: {isc_mean:.4f}")
        print(f"COV mean reliability: {cov_mean:.4f}")
        print(f"ISC vs COV difference: {isc_mean - cov_mean:+.4f}")
    
    # Warning for suspiciously high reliability
    if df_clean['r'].min() > 0.8:
        print(f"\nWarning: All reliability values > 0.8!")
        print("This may indicate over-alignment in hyperalignment process")
        print("Expected range for developmental data: ~0.3-0.7")
    
    # Warning for suspiciously low reliability
    if df_clean['r'].max() < 0.1:
        print(f"\nWarning: All reliability values < 0.1!")
        print("This may indicate poor data quality or processing issues")
        print("Expected range for developmental data: ~0.3-0.7")
    
# %%