#!/usr/bin/env bash
# Centralized configuration for hyperalignment pipeline
# Default paths inside the Docker container.
# External environment variables will ALWAYS override these.

# Processing parameters

CONNECTOME_MODE="${CONNECTOME_MODE:-both}"


POOL_NUM="${POOL_NUM:-32}"
N_JOBS="${N_JOBS:-32}"
VERTICES_IN_BOUNDS=59412
N_PARCELS=360

# Directory paths - INSIDE the Docker container
DTSERIES_ROOT="${DTSERIES_ROOT:-/data/inputs}"
PTSERIES_ROOT="${PTSERIES_ROOT:-/data/outputs/glasser_ptseries}"
BASE_OUTDIR="${BASE_OUTDIR:-/data/outputs/connectomes}"

TEMPORARY_OUTDIR="${TEMPORARY_OUTDIR:-work}"

# Atlas configuration
PARCELLATION_FILE="${PARCELLATION_FILE:-/app/hyperalignment_scripts/atlas/Q1-Q6_RelatedValidation210.CorticalAreas_dil_Final_Final_Areas_Group_Colors.32k_fs_LR.dlabel.nii}"

# File naming patterns
DTSERIES_FILENAME_TEMPLATE="{subj}_bb.rfMRI.MNI.MSMAll.dtseries.nii"
DTSERIES_FILENAME_PATTERN="*_bb.rfMRI.MNI.MSMAll.dtseries.nii"

# Subject selection configuration
METADATA_EXCEL="${METADATA_EXCEL:-/data/inputs/HBN_ASD_ADHD.xlsx}"
SUBJECT_ID_COL="EID"
SPLIT_COL="split"
