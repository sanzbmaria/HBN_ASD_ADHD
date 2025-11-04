import os
import glob
import numpy as np
import nibabel as nib
from scipy.stats import zscore
from scipy.spatial.distance import cdist


# --- edit these two paths to match your machine (watch 'Code' vs 'code' casing) ---
# In utils_test.py, replace the hardcoded paths with:

# DTSERIES filename pattern configuration (edit here if you need to change naming)
# Template used to build exact filenames and discovery glob patterns.
# Example default: "{subj}_task-rest_run-1_gsr_Atlas_s5.dtseries.nii"
DTSERIES_FILENAME_TEMPLATE = "{subj}_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"
DTSERIES_FILENAME_PATTERN = "*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"

DTSERIES_ROOT = "../data/HBN_CIFTI/" 
PTSERIES_ROOT = "../data/hyperalignment_input/glasser_ptseries/"
BASE_OUTDIR = os.path.join("../data/", "connectomes")  # Separate output directory
LOGDIR = os.path.join(BASE_OUTDIR, "logs")


project_dir = "."
scratch_dir = os.path.join(project_dir, "work")
parcellation_dir = os.path.join(project_dir, "HCP_S1200_Atlas_Z4_pkXDZ")

PARCELLATION_FILE = (
    "atlas/"
    "Q1-Q6_RelatedValidation210.CorticalAreas_dil_Final_Final_Areas_Group_Colors.32k_fs_LR.dlabel.nii"
)

POOL_NUM = 24  # Up from 16
N_JOBS = 24    # Keep as is
VERTICES_IN_BOUNDS = 59412 # based on Glasser atlas
N_PARCELS = 360 # based on Glasser atlas

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
                "Parcellation file not found. Update PARCELLATION_FILE in utils_test.py"
            )
        f = cands[0]
    g = nib.load(f)
    return g.get_fdata().T


# Load once at import so subj_dtseries_to_npy can mask parcels
parcellation = get_glasser_atlas_file()


def _discover_subject_ids():
    """Find IDs with files like <ID>_task-rest_run-1__s5.dtseries.nii or <ID>_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"""
    # Use the configurable discovery glob pattern defined at the top of the file
    pattern = os.path.join(DTSERIES_ROOT, DTSERIES_FILENAME_PATTERN)
    
    ids = []
    for fp in glob.glob(pattern):
        name = os.path.basename(fp)
        sid = name.split("_task-rest")[0]
        ids.append(sid)
    return sorted(set(ids))

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
