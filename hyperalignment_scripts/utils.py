import os
import glob
import numpy as np
import nibabel as nib
from scipy.stats import zscore
from scipy.spatial.distance import cdist

# Import centralized configuration
from read_config import (
    POOL_NUM, N_JOBS, VERTICES_IN_BOUNDS, N_PARCELS,
    DTSERIES_ROOT, PTSERIES_ROOT, BASE_OUTDIR, TEMPORARY_OUTDIR,
    PARCELLATION_FILE, DTSERIES_FILENAME_TEMPLATE, DTSERIES_FILENAME_PATTERN,
    LOGDIR, METADATA_EXCEL, SUBJECT_ID_COL
)

# Legacy variables for backwards compatibility
project_dir = "."
scratch_dir = os.path.join(project_dir, TEMPORARY_OUTDIR)
parcellation_dir = os.path.join(project_dir, "HCP_S1200_Atlas_Z4_pkXDZ")

def subj_dtseries_to_npy(subj_id, z=False, parcel=None):
    """
    load the dense timeseries return either the timeseries for specific parcels or the whole brain, in numpy format
    can normalize or not
    """

    # Build filename using the configurable template and GSR tag
    filename = DTSERIES_FILENAME_TEMPLATE.format(subj=subj_id)
    
    ds = nib.load(os.path.join(DTSERIES_ROOT, filename)).get_fdata()[:,:VERTICES_IN_BOUNDS]

    if parcel:
        if type(parcel) == list:
            to_return=[]
            for p in parcel: 
                mask=(parcellation==p).squeeze()
            if z: return zscore(ds[:,mask],axis=0)
            return ds[:,mask]        
        
    return zscore(ds[:,:VERTICES_IN_BOUNDS],axis=0)

def subj_ptseries_to_npy(subj_id, fdata=True):
    # Look for ptseries files based on GSR setting

    filename_pattern = "{}_*_glasser.ptseries.nii".format(subj_id)
        
    ptseries_files = glob.glob(os.path.join(PTSERIES_ROOT, subj_id, filename_pattern))
    
    if not ptseries_files:
        raise IOError("No ptseries files found for {} with pattern {}".format(subj_id, filename_pattern))
    
    ds = nib.load(ptseries_files[0])
    if fdata:
        ds = zscore(ds.get_fdata(),axis=0)
        ds = ds[:,:360]
    return ds

def get_glasser_atlas_file():
    """Load the Glasser atlas labels as a numpy array (CIFTI dlabel)."""
    f = PARCELLATION_FILE
    if not os.path.isfile(f):
        # try to discover a *.dlabel.nii in the same folder
        atlas_dir = os.path.dirname(PARCELLATION_FILE) or project_dir
        cands = glob.glob(os.path.join(atlas_dir, "*.dlabel.nii"))
        if not cands:
            raise FileNotFoundError(
                "Parcellation file not found at: {}\n"
                "Update PARCELLATION_FILE in config.sh or set PARCELLATION_FILE environment variable.\n"
                "The file should be a *.dlabel.nii atlas file.".format(PARCELLATION_FILE)
            )
        f = cands[0]
    g = nib.load(f)
    return g.get_fdata().T


# Load once at import so subj_dtseries_to_npy can mask parcels
parcellation = get_glasser_atlas_file()


def load_metadata_subjects():
    """
    Load subject IDs from METADATA_EXCEL file (supports both CSV and Excel).
    Returns all subjects in the file (regardless of train/test split).
    Set USE_METADATA_FILTER=1 environment variable to enable filtering.
    """
    use_filter = os.environ.get('USE_METADATA_FILTER', '0') == '1'

    if not use_filter:
        return None  # No filtering

    if not os.path.exists(METADATA_EXCEL):
        print(f"Warning: METADATA_EXCEL not found at {METADATA_EXCEL}, skipping metadata filtering")
        return None

    try:
        import pandas as pd

        # Auto-detect file format based on extension
        if METADATA_EXCEL.endswith('.csv'):
            df = pd.read_csv(METADATA_EXCEL)
        else:
            df = pd.read_excel(METADATA_EXCEL)

        # Normalize subject IDs to sub-XXXXX format
        # Get subject IDs as strings
        subjects = df[SUBJECT_ID_COL].astype(str).str.strip()

        print(f"Loaded {len(subjects)} subjects from metadata file")
        return sorted(set(subjects.tolist()))
    except Exception as e:
        print(f"Warning: Error reading METADATA_EXCEL: {e}, skipping metadata filtering")
        return None

##### change the name of CIFTI files #####
def _discover_subject_ids():
    """Find IDs with files like <ID>_bb.rfMRI.MNI.MSMAll.dtseries"""
    pattern = os.path.join(DTSERIES_ROOT, DTSERIES_FILENAME_PATTERN)

    ids = []
    for fp in glob.glob(pattern):
        name = os.path.basename(fp)
        # Extract ID before _bb.rfMRI
        sid = name.split("_bb.rfMRI")[0]
        # Don't add "sub-" prefix if not already there
        ids.append(sid)

    discovered_ids = sorted(set(ids))

    # Apply metadata filtering if enabled
    metadata_subjects = load_metadata_subjects()
    if metadata_subjects is not None:
        filtered_ids = [sid for sid in discovered_ids if sid in metadata_subjects]
        print(f"Filtered: {len(discovered_ids)} discovered -> {len(filtered_ids)} in metadata")
        return filtered_ids

    return discovered_ids

def get_HA_train_subjects():
    ids = _discover_subject_ids()
    if len(ids) > 50:
        return ids[:50]
    return ids[: max(1, len(ids) // 2)]

def load_twin_subjects():
    """No twin metadata locally; return an empty list (safe fallback)."""
    return []

def get_reliability_subjects():
    ids = _discover_subject_ids()
    twins = set(load_twin_subjects())
    rest = [s for s in ids if s not in twins]
    return rest[:50] if len(rest) > 50 else rest
