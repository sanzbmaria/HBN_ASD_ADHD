#!/bin/bash
set -e

###############################################
# HYPERALIGNMENT PIPELINE - BIOBANK MODE
###############################################

IMAGE_NAME="hyperalignment:latest"

# Host paths
INPUT_ROOT="${INPUT_ROOT:-/mnt/project/CIFTI_1}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/home/dnanexus/HBN_ASD_ADHD}"

# Paths INSIDE the container
DTSERIES_ROOT="/data/inputs"
PTSERIES_ROOT="/data/outputs/glasser_ptseries"
BASE_OUTDIR="/data/outputs/connectomes"

# Jobs
N_JOBS="${N_JOBS:-24}"
POOL_NUM="${POOL_NUM:-24}"

# Pipeline control
RUN_PARCELLATION="${RUN_PARCELLATION:-yes}"
RUN_BUILD_AA_CONNECTOMES="${RUN_BUILD_AA_CONNECTOMES:-yes}"
RUN_HYPERALIGNMENT="${RUN_HYPERALIGNMENT:-yes}"
RUN_CHA_CONNECTOMES="${RUN_CHA_CONNECTOMES:-yes}"
RUN_SIMILARITY_MATRICES="${RUN_SIMILARITY_MATRICES:-yes}"
RUN_IDM_RELIABILITY="${RUN_IDM_RELIABILITY:-yes}"

# Centralized connectome mode: full, split, or both
# This applies to ALL stages (AA connectomes, hyperalignment, CHA connectomes, similarity matrices)
CONNECTOME_MODE="${CONNECTOME_MODE:-both}"

# IMPORTANT: AA connectomes always needs FULL connectomes for hyperalignment training.
# We'll use AA_CONNECTOME_MODE="both" for AA step, but keep original mode for other stages.
ORIGINAL_MODE="${CONNECTOME_MODE}"
if [ "${CONNECTOME_MODE}" = "split" ]; then
    AA_CONNECTOME_MODE="both"
    echo ""
    echo "======================================================================"
    echo "NOTE: AA connectomes will build BOTH full and split connectomes"
    echo "(Hyperalignment training requires full connectomes)"
    echo "Other stages will use mode: ${ORIGINAL_MODE}"
    echo "======================================================================"
    echo ""
else
    AA_CONNECTOME_MODE="${CONNECTOME_MODE}"
fi

###############################################
# STAGE 1: PARCELLATION
###############################################
if [ "${RUN_PARCELLATION}" = "yes" ]; then
    echo ""
    echo "======================================================================"
    echo "STAGE 1: PARCELLATION"
    echo "======================================================================"
    docker run --rm \
        -v "${INPUT_ROOT}:${DTSERIES_ROOT}:ro" \
        -v "${OUTPUT_ROOT}:$(dirname ${PTSERIES_ROOT})" \
        "${IMAGE_NAME}" \
        python /workspace/src/01_parcellation.py \
            --dtseries_root "${DTSERIES_ROOT}" \
            --output_dir "${PTSERIES_ROOT}" \
            --n_jobs "${N_JOBS}"
    echo "Parcellation complete."
fi

###############################################
# STAGE 2: BUILD AA CONNECTOMES
###############################################
if [ "${RUN_BUILD_AA_CONNECTOMES}" = "yes" ]; then
    echo ""
    echo "======================================================================"
    echo "STAGE 2: BUILD AA CONNECTOMES (MODE: ${AA_CONNECTOME_MODE})"
    echo "======================================================================"
    docker run --rm \
        -v "${OUTPUT_ROOT}:$(dirname ${PTSERIES_ROOT})" \
        "${IMAGE_NAME}" \
        python /workspace/src/02_build_aa_connectomes.py \
            --ptseries_root "${PTSERIES_ROOT}" \
            --output_dir "${BASE_OUTDIR}/AA" \
            --n_jobs "${N_JOBS}" \
            --mode "${AA_CONNECTOME_MODE}"
    echo "AA connectome building complete."
fi

###############################################
# STAGE 3: HYPERALIGNMENT
###############################################
if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo ""
    echo "======================================================================"
    echo "STAGE 3: HYPERALIGNMENT TRAINING"
    echo "======================================================================"
    docker run --rm \
        -v "${OUTPUT_ROOT}:$(dirname ${PTSERIES_ROOT})" \
        "${IMAGE_NAME}" \
        python /workspace/src/03_train_hyperalignment.py \
            --ptseries_root "${PTSERIES_ROOT}" \
            --aa_connectome_dir "${BASE_OUTDIR}/AA" \
            --output_dir "${BASE_OUTDIR}/hyperalignment" \
            --pool_num "${POOL_NUM}"
    echo "Hyperalignment training complete."
fi

###############################################
# STAGE 4: BUILD CHA CONNECTOMES
###############################################
if [ "${RUN_CHA_CONNECTOMES}" = "yes" ]; then
    echo ""
    echo "======================================================================"
    echo "STAGE 4: BUILD CHA CONNECTOMES (MODE: ${ORIGINAL_MODE})"
    echo "======================================================================"
    docker run --rm \
        -v "${OUTPUT_ROOT}:$(dirname ${PTSERIES_ROOT})" \
        "${IMAGE_NAME}" \
        python /workspace/src/04_build_cha_connectomes.py \
            --ptseries_root "${PTSERIES_ROOT}" \
            --mappers_dir "${BASE_OUTDIR}/hyperalignment" \
            --output_dir "${BASE_OUTDIR}/CHA" \
            --n_jobs "${N_JOBS}" \
            --mode "${ORIGINAL_MODE}"
    echo "CHA connectome building complete."
fi

###############################################
# STAGE 5: SIMILARITY MATRICES
###############################################
if [ "${RUN_SIMILARITY_MATRICES}" = "yes" ]; then
    echo ""
    echo "======================================================================"
    echo "STAGE 5: COMPUTE SIMILARITY MATRICES (MODE: ${ORIGINAL_MODE})"
    echo "======================================================================"
    docker run --rm \
        -v "${OUTPUT_ROOT}:$(dirname ${PTSERIES_ROOT})" \
        "${IMAGE_NAME}" \
        python /workspace/src/05_compute_similarity_matrices.py \
            --connectome_dir "${BASE_OUTDIR}" \
            --output_dir "${BASE_OUTDIR}/similarity_matrices" \
            --n_jobs "${N_JOBS}" \
            --mode "${ORIGINAL_MODE}"
    echo "Similarity matrix computation complete."
fi

###############################################
# STAGE 6: IDM RELIABILITY
###############################################
if [ "${RUN_IDM_RELIABILITY}" = "yes" ]; then
    echo ""
    echo "======================================================================"
    echo "STAGE 6: IDM RELIABILITY ANALYSIS (MODE: ${ORIGINAL_MODE})"
    echo "======================================================================"
    docker run --rm \
        -v "${OUTPUT_ROOT}:$(dirname ${PTSERIES_ROOT})" \
        "${IMAGE_NAME}" \
        python /workspace/src/06_idm_reliability.py \
            --similarity_dir "${BASE_OUTDIR}/similarity_matrices" \
            --output_dir "${BASE_OUTDIR}/idm_reliability" \
            --mode "${ORIGINAL_MODE}"
    echo "IDM reliability analysis complete."
fi

echo ""
echo "======================================================================"
echo "HYPERALIGNMENT PIPELINE COMPLETE"
echo "======================================================================"
echo "Results saved to: ${OUTPUT_ROOT}"
echo ""