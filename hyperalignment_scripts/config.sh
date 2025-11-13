#!/usr/bin/env bash
# Centralized configuration for hyperalignment pipeline
# This file can be sourced by bash scripts and parsed by Python 2/3

# Processing parameters
POOL_NUM=24
N_JOBS=24
VERTICES_IN_BOUNDS=59412
N_PARCELS=360

# Directory paths - these are INSIDE the Docker container
# The host directory is mounted at /data in the container
DTSERIES_ROOT="/data/HBN_CIFTI/"
PTSERIES_ROOT="/data/hyperalignment_input/glasser_ptseries/"
BASE_OUTDIR="/data/connectomes"
TEMPORARY_OUTDIR="work"

# Atlas configuration - inside container
PARCELLATION_FILE="atlas/Q1-Q6_RelatedValidation210.CorticalAreas_dil_Final_Final_Areas_Group_Colors.32k_fs_LR.dlabel.nii"

# File naming patterns
DTSERIES_FILENAME_TEMPLATE="{subj}_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"
DTSERIES_FILENAME_PATTERN="*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"

# Subject selection configuration (for organize_subjects.py)
# Path to metadata Excel file (relative to /data in container or absolute)
METADATA_EXCEL="/data/HBN_ASD_ADHD.xlsx"

# Excel column names mapping - customize these for your dataset
SUBJECT_ID_COL="EID"           # Column containing subject IDs
SITE_COL="SITE"                # Column for site/scanner (optional, set to "" to disable)
SEX_COL="Sex"                  # Column for sex/gender (optional, set to "" to disable)
AGE_COL="Age"                  # Column for age (optional, set to "" to disable)
MOTION_COL="MeanFD"            # Column for motion metric (optional, set to "" to disable)

# Subject selection criteria - customize for your research question
# For diagnosis-based selection (like HBN ASD/ADHD), set these columns:
SELECTION_COL_1="ASD"          # First selection criterion column (e.g., "ASD")
SELECTION_COL_2="ADHD"         # Second selection criterion column (e.g., "ADHD")
SELECTION_COL_3="ASD+ADHD"     # Third selection criterion column (optional)

# For other datasets, you can:
# 1. Set SELECTION_COL_* to your filtering columns (e.g., "GROUP", "CONDITION")
# 2. Or leave empty ("") and modify organize_subjects.py's derive_dx_row function
# 3. Or skip organize_subjects.py and directly provide subject lists via TEST_SUBJECTS_LIST

# Training/test split configuration
TRAIN_FRACTION=0.25            # Fraction of subjects for hyperalignment training (0-1)
CV_FOLDS=5                     # Number of cross-validation folds for test pool

# Stratification columns - which covariates to balance across train/test split
# Set to "true" to include in stratification, "false" to exclude
STRATIFY_BY_SITE=true
STRATIFY_BY_SEX=true
STRATIFY_BY_AGE=true
STRATIFY_BY_MOTION=true
