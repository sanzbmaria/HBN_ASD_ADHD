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

AA_CONNECTOME_MODE="${AA_CONNECTOME_MODE:-both}"
CHA_CONNECTOME_MODE="${CHA_CONNECTOME_MODE:-both}"
HYPERALIGNMENT_MODE="${HYPERALIGNMENT_MODE:-full}"

###############################################
# VALIDATION
###############################################

echo ""
echo "================================================"
echo "HYPERALIGNMENT PIPELINE - BIOBANK MODE"
echo "================================================"
echo ""

if [ ! -d "${INPUT_ROOT}" ]; then
    echo "ERROR: Input directory not found: ${INPUT_ROOT}"
    exit 1
fi

mkdir -p "${OUTPUT_ROOT}"
mkdir -p "${OUTPUT_ROOT}/logs"

###############################################
# STEP 1 — PARCELLATION
###############################################

if [ "${RUN_PARCELLATION}" = "yes" ]; then
    echo ""
    echo "========== STEP 1: PARCELLATION =========="

    docker run --rm \
        -v "${INPUT_ROOT}":/data/inputs:ro \
        -v "${OUTPUT_ROOT}":/data/outputs \
        -e DTSERIES_ROOT="${DTSERIES_ROOT}" \
        -e OUTDIR="${PTSERIES_ROOT}" \
        -e N_JOBS="${N_JOBS}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        bash apply_parcellation.sh \
        2>&1 | tee "${OUTPUT_ROOT}/logs/parcellation.log"

    echo "✓ Parcellation complete"
fi

###############################################
# STEP 2 — BUILD AA CONNECTOMES
###############################################

if [ "${RUN_BUILD_AA_CONNECTOMES}" = "yes" ]; then
    echo ""
    echo "====== STEP 2: BUILD AA CONNECTOMES ======"

    docker run --rm \
        -v "${INPUT_ROOT}":/data/inputs:ro \
        -v "${OUTPUT_ROOT}":/data/outputs \
        -e DTSERIES_ROOT="${DTSERIES_ROOT}" \
        -e PTSERIES_ROOT="${PTSERIES_ROOT}" \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e N_JOBS="${N_JOBS}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_aa_connectomes.py --mode ${AA_CONNECTOME_MODE} \
        2>&1 | tee "${OUTPUT_ROOT}/logs/build_aa_connectomes.log"

    echo "✓ AA connectomes built"
fi
###############################################
# STEP 3 — HYPERALIGNMENT
###############################################

if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo ""
    echo "============ STEP 3: HYPERALIGNMENT ============"

    for parcel in {1..360}; do
        echo "Processing parcel ${parcel}/360..."

        docker run --rm \
            -v "${INPUT_ROOT}":/data/inputs:ro \
            -v "${OUTPUT_ROOT}":/data/outputs \
            -e BASE_OUTDIR="${BASE_OUTDIR}" \
            -e N_JOBS="${N_JOBS}" \
            -e POOL_NUM="${POOL_NUM}" \
            -w /app/hyperalignment_scripts \
            ${IMAGE_NAME} \
            python run_hyperalignment.py ${parcel} ${HYPERALIGNMENT_MODE} \
            2>&1 | tee "${OUTPUT_ROOT}/logs/hyperalignment_parcel_${parcel}.log"
    done

    echo "✓ Hyperalignment complete"
fi

###############################################
# STEP 4 — BUILD CHA CONNECTOMES
###############################################

if [ "${RUN_CHA_CONNECTOMES}" = "yes" ]; then
    echo ""
    echo "======= STEP 4: BUILD CHA CONNECTOMES ======="

    docker run --rm \
        -v "${INPUT_ROOT}":/data/inputs:ro \
        -v "${OUTPUT_ROOT}":/data/outputs \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e N_JOBS="${N_JOBS}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_CHA_connectomes.py --mode ${CHA_CONNECTOME_MODE} \
        2>&1 | tee "${OUTPUT_ROOT}/logs/build_cha_connectomes.log"

    echo "✓ CHA connectomes built"
fi

###############################################
# SUMMARY
###############################################

                                                                                                                                                                            141,1         87%
                                                                                                                                                                            
echo ""
echo "================================================"
echo "PIPELINE COMPLETE"
echo "================================================"
echo ""
echo "Results in:"
echo "  ${OUTPUT_ROOT}/glasser_ptseries/"
echo "  ${OUTPUT_ROOT}/connectomes/"
echo "  ${OUTPUT_ROOT}/connectomes/hyperalignment_output/"
echo ""
echo "Logs: ${OUTPUT_ROOT}/logs/"
echo ""

                                                                                                                                                                            159,0-1       Bot
