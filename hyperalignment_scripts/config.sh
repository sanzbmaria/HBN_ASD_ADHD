#!/usr/bin/env bash
# Centralized configuration for hyperalignment pipeline
# This file can be sourced by bash scripts and parsed by Python 2/3

# Processing parameters
POOL_NUM=24
N_JOBS=24
VERTICES_IN_BOUNDS=59412
N_PARCELS=360

# Directory paths (relative to hyperalignment_scripts/)
DTSERIES_ROOT="../data/HBN_CIFTI/"
PTSERIES_ROOT="../data/hyperalignment_input/glasser_ptseries/"
BASE_OUTDIR="../data/connectomes"
TEMPORARY_OUTDIR="work"

# Atlas configuration
PARCELLATION_FILE="atlas/Q1-Q6_RelatedValidation210.CorticalAreas_dil_Final_Final_Areas_Group_Colors.32k_fs_LR.dlabel.nii"

# File naming patterns
DTSERIES_FILENAME_TEMPLATE="{subj}_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"
DTSERIES_FILENAME_PATTERN="*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"
