#!/bin/bash
# Full Pipeline V2: Uses custom hyperalignment module instead of PyMVPA2
# This version calls run_hyperalignment_v2.py which uses hyperalignment.py

set -e

# ============================================================================
# CONFIGURATION - Override via environment variables or Docker params
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# BioBank Configuration: Separate read-only inputs and writable outputs
# INPUTS_ROOT: Path to read-only CIFTI files (can be separate from outputs)
# OUTPUTS_ROOT: Path to writable directory for all pipeline outputs
INPUTS_ROOT="${INPUTS_ROOT:-}"
OUTPUTS_ROOT="${OUTPUTS_ROOT:-}"

# Legacy: DATA_ROOT can be used if inputs/outputs are under same parent
DATA_ROOT="${DATA_ROOT:-}"

# Configuration overrides (optional - will use config.sh defaults if not set)
# These are CONTAINER paths (inside Docker)
DTSERIES_ROOT="${DTSERIES_ROOT:-/data/inputs}"
PTSERIES_ROOT="${PTSERIES_ROOT:-/data/outputs/glasser_ptseries}"
BASE_OUTDIR="${BASE_OUTDIR:-/data/outputs/connectomes}"
N_JOBS="${N_JOBS:-32}"
POOL_NUM="${POOL_NUM:-32}"

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

# ============================================================================
# VALIDATION
# ============================================================================

echo "================================================"
echo "HYPERALIGNMENT PIPELINE V2 - CUSTOM HYPERALIGNMENT"
echo "================================================"
echo ""

# Determine mount strategy based on what's provided
if [ -n "${INPUTS_ROOT}" ] && [ -n "${OUTPUTS_ROOT}" ]; then
    # BioBank mode: Separate read-only inputs and writable outputs
    echo "BioBank Mode: Using separate input/output directories"
    DOCKER_MOUNTS="-v ${INPUTS_ROOT}:/data/inputs:ro -v ${OUTPUTS_ROOT}:/data/outputs"

    if [ ! -d "${INPUTS_ROOT}" ]; then
        echo "ERROR: INPUTS_ROOT directory not found: ${INPUTS_ROOT}"
        echo "This should point to your read-only CIFTI files location"
        exit 1
    fi

    # Create outputs directory if it doesn't exist
    mkdir -p "${OUTPUTS_ROOT}"

elif [ -n "${DATA_ROOT}" ]; then
    # Legacy mode: Single parent directory containing inputs/ and outputs/
    echo "Legacy Mode: Using single DATA_ROOT directory"
    DOCKER_MOUNTS="-v ${DATA_ROOT}:/data"

    if [ ! -d "${DATA_ROOT}" ]; then
        echo "ERROR: DATA_ROOT directory not found: ${DATA_ROOT}"
        exit 1
    fi

else
    echo "ERROR: Must set either (INPUTS_ROOT + OUTPUTS_ROOT) or DATA_ROOT"
    echo ""
    echo "BioBank Usage (recommended for read-only inputs):"
    echo "  export INPUTS_ROOT=/biobank/readonly/cifti/path"
    echo "  export OUTPUTS_ROOT=/scratch/user/outputs"
    echo "  ./full_pipeline_v2.sh"
    echo ""
    echo "Legacy Usage (if inputs and outputs under same parent):"
    echo "  export DATA_ROOT=/path/to/parent/directory"
    echo "  ./full_pipeline_v2.sh"
    echo ""
    echo "Configuration can be overridden via environment variables:"
    echo "  export N_JOBS=32               # Number of parallel jobs"
    echo "  export CONNECTOME_MODE=split   # Use 'full', 'split', or 'both'"
    exit 1
fi

# Check if Docker image exists
if ! docker image inspect ${IMAGE_NAME} &> /dev/null; then
    echo "ERROR: Docker image '${IMAGE_NAME}' not found"
    echo ""
    echo "Please build it first:"
    echo "  ./docker-build.sh"
    exit 1
fi

# Validate that the Docker image has config.sh (detect stale images)
echo "Validating Docker image contents..."
if ! docker run --rm ${IMAGE_NAME} test -f /app/hyperalignment_scripts/config.sh; then
    echo ""
    echo "ERROR: Docker image is missing config.sh"
    echo ""
    echo "Your Docker image appears to be outdated and is missing required configuration files."
    echo "This usually happens when the image was built before config.sh was added to the repository."
    echo ""
    echo "Solution: Rebuild the Docker image:"
    echo "  ./docker-build.sh"
    echo ""
    echo "Then re-run this script."
    exit 1
fi

# Check if hyperalignment.py module exists
if ! docker run --rm ${IMAGE_NAME} test -f /app/hyperalignment_scripts/hyperalignment.py; then
    echo ""
    echo "ERROR: Custom hyperalignment module not found"
    echo ""
    echo "This pipeline requires hyperalignment.py to be in the hyperalignment_scripts directory."
    echo "Please ensure hyperalignment.py is present and rebuild the Docker image:"
    echo "  ./docker-build.sh"
    echo ""
    exit 1
fi

echo "✓ Docker image validated"
echo ""

# Create log directory
mkdir -p logs

echo "Configuration:"
if [ -n "${INPUTS_ROOT}" ]; then
    echo "  CIFTI Inputs (read-only): ${INPUTS_ROOT}"
    echo "  Pipeline Outputs (writable): ${OUTPUTS_ROOT}"
else
    echo "  Data Root: ${DATA_ROOT}"
fi
echo "  Container CIFTI Path: ${DTSERIES_ROOT}"
echo "  Container Output Path: ${BASE_OUTDIR}"
echo "  N_JOBS: ${N_JOBS}"
echo "  POOL_NUM: ${POOL_NUM}"
echo "  Connectome Mode: ${CONNECTOME_MODE}"
if [ "${USE_METADATA_FILTER:-0}" = "1" ]; then
    echo "  Metadata Filtering: ENABLED"
    echo "  Metadata File: ${METADATA_EXCEL:-/data/inputs/HBN_ASD_ADHD.xlsx}"
else
    echo "  Metadata Filtering: DISABLED"
fi
echo ""
echo "Pipeline steps:"
echo "  1. Parcellation: ${RUN_PARCELLATION}"
echo "  2. Build AA Connectomes: ${RUN_BUILD_AA_CONNECTOMES}"
echo "  3. Hyperalignment (V2 - Custom Module): ${RUN_HYPERALIGNMENT}"
echo "  4. Build CHA Connectomes: ${RUN_CHA_CONNECTOMES}"
echo "  5. Compute Similarity Matrices: ${RUN_SIMILARITY_MATRICES}"
echo "  6. Compute IDM Reliability: ${RUN_IDM_RELIABILITY}"
echo ""

# ============================================================================
# STEP 1: PARCELLATION
# ============================================================================

if [ "${RUN_PARCELLATION}" = "yes" ]; then
    echo "================================================"
    echo "STEP 1: PARCELLATION"
    echo "================================================"
    echo ""
    echo "Converting dtseries to parcellated ptseries..."
    echo "This may take several hours depending on the number of subjects."
    echo ""

    docker run --rm \
        ${DOCKER_MOUNTS} \
        -e N_JOBS=${N_JOBS} \
        -e DTSERIES_ROOT="${DTSERIES_ROOT}" \
        -e PTSERIES_ROOT="${PTSERIES_ROOT}" \
        -e TMPDIR="${TMPDIR:-/data/outputs/.tmp}" \
        -e USE_METADATA_FILTER="${USE_METADATA_FILTER:-0}" \
        -e METADATA_EXCEL="${METADATA_EXCEL:-/data/inputs/HBN_ASD_ADHD.xlsx}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        bash apply_parcellation.sh \
        2>&1 | tee logs/parcellation.log

    echo ""
    echo "✓ Parcellation complete"
    echo ""
else
    echo "Skipping parcellation (RUN_PARCELLATION=no)"
    echo ""
fi

# ============================================================================
# STEP 2: BUILD AA CONNECTOMES
# ============================================================================

if [ "${RUN_BUILD_AA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 2: BUILD AA CONNECTOMES"
    echo "================================================"
    echo ""
    echo "Building anatomical connectomes from parcellated data..."
    echo "Mode: ${AA_CONNECTOME_MODE}"
    echo ""

    docker run --rm \
        ${DOCKER_MOUNTS} \
        -e N_JOBS=${N_JOBS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e DTSERIES_ROOT="${DTSERIES_ROOT}" \
        -e PTSERIES_ROOT="${PTSERIES_ROOT}" \
        -e CONNECTOME_MODE="${AA_CONNECTOME_MODE}" \
        -e USE_METADATA_FILTER="${USE_METADATA_FILTER:-0}" \
        -e METADATA_EXCEL="${METADATA_EXCEL:-/data/inputs/HBN_ASD_ADHD.xlsx}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_aa_connectomes.py --mode ${AA_CONNECTOME_MODE} \
        2>&1 | tee logs/build_aa_connectomes.log

    echo ""
    echo "✓ AA connectomes built"
    echo ""
else
    echo "Skipping AA connectome building (RUN_BUILD_AA_CONNECTOMES=no)"
    echo ""
fi

# ============================================================================
# STEP 3: HYPERALIGNMENT V2 (Custom Module)
# ============================================================================

if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo "================================================"
    echo "STEP 3: HYPERALIGNMENT V2 (Custom Module)"
    echo "================================================"
    echo ""
    echo "Running hyperalignment for all 360 parcels..."
    echo "Using custom hyperalignment module (not PyMVPA2)"
    echo "Mode: ${CONNECTOME_MODE}"
    echo "This is the most time-consuming step."
    echo ""

    # Pass through CONNECTOME_MODE to hyperalignment
    HYPERALIGNMENT_MODE="${CONNECTOME_MODE}"

    for parcel in {1..360}; do
        echo "Processing parcel ${parcel}/360..."

        docker run --rm \
            ${DOCKER_MOUNTS} \
            -e N_JOBS=${N_JOBS} \
            -e POOL_NUM=${POOL_NUM} \
            -e BASE_OUTDIR="${BASE_OUTDIR}" \
            -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
            -e TMPDIR="${TMPDIR:-/data/outputs/.tmp}" \
            -e USE_METADATA_FILTER="${USE_METADATA_FILTER:-0}" \
            -e METADATA_EXCEL="${METADATA_EXCEL:-/data/inputs/HBN_ASD_ADHD.xlsx}" \
            -w /app/hyperalignment_scripts \
            ${IMAGE_NAME} \
            python3 run_hyperalignment_v2.py ${parcel} ${HYPERALIGNMENT_MODE} \
            2>&1 | tee logs/hyperalignment_v2_parcel_${parcel}.log
    done

    echo ""
    echo "✓ Hyperalignment V2 complete for all parcels"
    echo ""
else
    echo "Skipping hyperalignment (RUN_HYPERALIGNMENT=no)"
    echo ""
fi

# ============================================================================
# STEP 4: BUILD CHA CONNECTOMES
# ============================================================================

if [ "${RUN_CHA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 4: BUILD CHA CONNECTOMES"
    echo "================================================"
    echo ""
    echo "Building connectomes from hyperaligned data..."
    echo "Mode: ${CONNECTOME_MODE}"
    echo ""

    docker run --rm \
        ${DOCKER_MOUNTS} \
        -e N_JOBS=${N_JOBS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
        -e USE_METADATA_FILTER="${USE_METADATA_FILTER:-0}" \
        -e METADATA_EXCEL="${METADATA_EXCEL:-/data/inputs/HBN_ASD_ADHD.xlsx}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_CHA_connectomes.py --mode ${CONNECTOME_MODE} \
        2>&1 | tee logs/build_cha_connectomes.log

    echo ""
    echo "✓ CHA connectomes built"
    echo ""
else
    echo "Skipping CHA connectome building (RUN_CHA_CONNECTOMES=no)"
    echo ""
fi

# ============================================================================
# STEP 5: COMPUTE SIMILARITY MATRICES
# ============================================================================

if [ "${RUN_SIMILARITY_MATRICES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 5: COMPUTE SIMILARITY MATRICES"
    echo "================================================"
    echo ""
    echo "Computing inter-subject similarity matrices..."
    echo "This computes ISC and covariance matrices for all 360 parcels."
    echo ""

    docker run --rm \
        ${DOCKER_MOUNTS} \
        -e N_JOBS=${N_JOBS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
        -e USE_METADATA_FILTER="${USE_METADATA_FILTER:-0}" \
        -e METADATA_EXCEL="${METADATA_EXCEL:-/data/inputs/HBN_ASD_ADHD.xlsx}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 connectome_similarity_matrices.py 1 batch \
        2>&1 | tee logs/similarity_matrices.log

    echo ""
    echo "✓ Similarity matrices computed"
    echo ""
else
    echo "Skipping similarity matrix computation (RUN_SIMILARITY_MATRICES=no)"
    echo ""
fi

# ============================================================================
# STEP 6: COMPUTE IDM RELIABILITY
# ============================================================================

if [ "${RUN_IDM_RELIABILITY}" = "yes" ]; then
    echo "================================================"
    echo "STEP 6: COMPUTE IDM RELIABILITY"
    echo "================================================"
    echo ""
    echo "Computing split-half reliability of IDMs..."
    echo ""

    docker run --rm \
        ${DOCKER_MOUNTS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e N_JOBS=${N_JOBS} \
        -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
        -e USE_METADATA_FILTER="${USE_METADATA_FILTER:-0}" \
        -e METADATA_EXCEL="${METADATA_EXCEL:-/data/inputs/HBN_ASD_ADHD.xlsx}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 idm_reliability.py \
        2>&1 | tee logs/idm_reliability.log

    echo ""
    echo "✓ IDM reliability computed"
    echo ""
else
    echo "Skipping IDM reliability computation (RUN_IDM_RELIABILITY=no)"
    echo ""
fi

# ============================================================================
# SUMMARY
# ============================================================================

echo "================================================"
echo "PIPELINE V2 COMPLETE"
echo "================================================"
echo ""
echo "All requested steps completed successfully!"
echo ""
echo "Results can be found in:"
if [ -n "${OUTPUTS_ROOT}" ]; then
    echo "  ${OUTPUTS_ROOT}/glasser_ptseries/                           (parcellated data)"
    echo "  ${OUTPUTS_ROOT}/connectomes/                                (AA connectomes)"
    echo "  ${OUTPUTS_ROOT}/connectomes/hyperalignment_output/          (hyperaligned data & CHA connectomes)"
    echo "  ${OUTPUTS_ROOT}/connectomes/similarity_matrices/            (ISC & covariance matrices)"
    echo "  ${OUTPUTS_ROOT}/connectomes/reliability_results/            (IDM reliability results)"
else
    echo "  ${DATA_ROOT}/glasser_ptseries/                           (parcellated data)"
    echo "  ${DATA_ROOT}/connectomes/                                (AA connectomes)"
    echo "  ${DATA_ROOT}/connectomes/hyperalignment_output/          (hyperaligned data & CHA connectomes)"
    echo "  ${DATA_ROOT}/connectomes/similarity_matrices/            (ISC & covariance matrices)"
    echo "  ${DATA_ROOT}/connectomes/reliability_results/            (IDM reliability results)"
fi
echo ""
echo "Logs saved to: ./logs/"
echo ""
