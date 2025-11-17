#!/usr/bin/env bash
# Centralized configuration for hyperalignment pipeline
# This file can be sourced by bash scripts and parsed by Python 2/3

# Processing parameters
POOL_NUM=24
N_JOBS=24
VERTICES_IN_BOUNDS=59412
N_PARCELS=360

# Pipeline mode: full, split, or both
# This controls what connectomes are built throughout the pipeline
CONNECTOME_MODE="both"

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

# Excel column names - customize these for your dataset
SUBJECT_ID_COL="EID"           # Column containing subject IDs
SPLIT_COL="split"              # Column with "train" or "test" assignments

# That's it! Just provide an Excel with:
# - A subject ID column (e.g., "EID", "subject", "participant_id")
# - A split column with "train" or "test" for each subject
#
# Do your own stratification/random splitting however you want outside the pipeline,
# then provide the final assignments in your Excel file.
