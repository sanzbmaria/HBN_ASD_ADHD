#!/usr/bin/env bash
# Centralized configuration for hyperalignment pipeline
# This file can be sourced by bash scripts and parsed by Python 2/3

# Processing parameters
# Can be overridden by environment variables
POOL_NUM="${POOL_NUM:-24}"
N_JOBS="${N_JOBS:-24}"
VERTICES_IN_BOUNDS="${VERTICES_IN_BOUNDS:-59412}"
N_PARCELS="${N_PARCELS:-360}"

# Pipeline mode: full, split, or both
# This controls what connectomes are built throughout the pipeline
# Can be overridden by environment variable
CONNECTOME_MODE="${CONNECTOME_MODE:-both}"

# Directory paths - these are INSIDE the Docker container
# The host directory is mounted at /data in the container
# Can be overridden by environment variables for custom data locations
##### change the CIFTI folder name here #####
DTSERIES_ROOT="${DTSERIES_ROOT:-/data/CIFTI_1/}"
PTSERIES_ROOT="${PTSERIES_ROOT:-/data/hyperalignment_input/glasser_ptseries/}"
BASE_OUTDIR="${BASE_OUTDIR:-/data/connectomes}"
TEMPORARY_OUTDIR="${TEMPORARY_OUTDIR:-work}"

# Atlas configuration - inside container
PARCELLATION_FILE="atlas/Q1-Q6_RelatedValidation210.CorticalAreas_dil_Final_Final_Areas_Group_Colors.32k_fs_LR.dlabel.nii"

# File naming patterns
##### change the CIFTI file name here #####
DTSERIES_FILENAME_TEMPLATE="{subj}_bb.rfMRI.MNI.MSMAll.dtseries"
##### change the CIFTI file name here #####
DTSERIES_FILENAME_PATTERN="*_bb.rfMRI.MNI.MSMAll.dtseries"

# Subject selection configuration (for organize_subjects.py)
# Path to metadata Excel file (relative to /data in container or absolute)
# Can be overridden by environment variable
METADATA_EXCEL="${METADATA_EXCEL:-/data/HBN_ASD_ADHD.xlsx}"

# Excel column names - customize these for your dataset
SUBJECT_ID_COL="EID"           # Column containing subject IDs
SPLIT_COL="split"              # Column with "train" or "test" assignments

# That's it! Just provide an Excel with:
# - A subject ID column (e.g., "EID", "subject", "participant_id")
# - A split column with "train" or "test" for each subject
#
# Do your own stratification/random splitting however you want outside the pipeline,
# then provide the final assignments in your Excel file.

##### add function (TRAIN_TEST_MODE) to directly tell the percentage of train/test if not having excel #####
# Train/test split configuration
# If TRAIN_TEST_MODE is set, it overrides Excel-based splitting
# Options: "random", "percentage", "explicit"
TRAIN_TEST_MODE="${TRAIN_TEST_MODE:-}"

# For random mode: specify train percentage (e.g., 0.1 = 10% train, 90% test)
TRAIN_PERCENTAGE="${TRAIN_PERCENTAGE:-0.4}"

# For explicit mode: comma-separated subject IDs
EXPLICIT_TRAIN_SUBJECTS="${EXPLICIT_TRAIN_SUBJECTS:-}"
EXPLICIT_TEST_SUBJECTS="${EXPLICIT_TEST_SUBJECTS:-}"

# Random seed for reproducibility
RANDOM_SEED="${RANDOM_SEED:-42}"
