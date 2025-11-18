#!/bin/bash
# Full Pipeline: Run the complete hyperalignment pipeline
# Order: Parcellation -> AA Connectomes -> Hyperalignment -> CHA Connectomes

set -e

# ============================================================================
# CONFIGURATION - Override via environment variables or Docker params
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# Data directory (REQUIRED - mount point inside container is /data)
DATA_ROOT="${DATA_ROOT:-}"

# Configuration overrides (optional - will use config.sh defaults if not set)
# Note: Trailing slashes are included to match config.sh
DTSERIES_ROOT="${DTSERIES_ROOT:-/data/HBN_CIFTI/}"
PTSERIES_ROOT="${PTSERIES_ROOT:-/data/hyperalignment_input/glasser_ptseries/}"
BASE_OUTDIR="${BASE_OUTDIR:-/data/connectomes}"
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

# ============================================================================
# VALIDATION
# ============================================================================

echo "================================================"
echo "HYPERALIGNMENT PIPELINE - FULL PRODUCTION MODE"
echo "================================================"
echo ""

if [ -z "${DATA_ROOT}" ]; then
    echo "ERROR: DATA_ROOT environment variable not set"
    echo ""
    echo "Usage:"
    echo "  export DATA_ROOT=/path/to/your/data"
    echo "  ./full_pipeline.sh"
    echo ""
    echo "Configuration can be overridden via environment variables:"
    echo "  export N_JOBS=32               # Number of parallel jobs"
    echo "  export CONNECTOME_MODE=split   # Use 'full', 'split', or 'both' (default)"
    echo "  export DTSERIES_ROOT=/data/CIFTI_DATA  # Path to your CIFTI files"
    echo "  ./full_pipeline.sh"
    exit 1
fi

if [ ! -d "${DATA_ROOT}" ]; then
    echo "ERROR: Data directory not found: ${DATA_ROOT}"
    exit 1
fi

# Validate that DTSERIES_ROOT and other paths are container paths (start with /data)
# or are subdirectories of DATA_ROOT (for host paths)
if [ -n "${DTSERIES_ROOT}" ]; then
    # If DTSERIES_ROOT is set and doesn't start with /data, it should be under DATA_ROOT
    if [[ ! "${DTSERIES_ROOT}" =~ ^/data ]]; then
        # This is a host path - check if it's under DATA_ROOT
        # Convert to absolute paths for comparison
        DTSERIES_ABS=$(cd "$(dirname "${DTSERIES_ROOT}")" 2>/dev/null && pwd)/$(basename "${DTSERIES_ROOT}") || DTSERIES_ABS="${DTSERIES_ROOT}"
        DATA_ROOT_ABS=$(cd "${DATA_ROOT}" && pwd)

        # Check if DTSERIES_ABS starts with DATA_ROOT_ABS
        if [[ ! "${DTSERIES_ABS}" == "${DATA_ROOT_ABS}"* ]]; then
            echo "ERROR: DTSERIES_ROOT must be under DATA_ROOT or use container paths (/data/...)"
            echo ""
            echo "Current configuration:"
            echo "  DATA_ROOT: ${DATA_ROOT}"
            echo "  DTSERIES_ROOT: ${DTSERIES_ROOT}"
            echo ""
            echo "Solutions:"
            echo "  1. Set DATA_ROOT to the parent directory containing all data:"
            echo "     export DATA_ROOT=/path/to/parent/directory"
            echo "     Then use container paths like:"
            echo "     export DTSERIES_ROOT=/data/HBN_CIFTI/"
            echo ""
            echo "  2. Or ensure DTSERIES_ROOT is under DATA_ROOT:"
            echo "     DATA_ROOT should contain (or be the parent of) HBN_CIFTI/"
            exit 1
        fi
    fi
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
echo "✓ Docker image validated"
echo ""

# Create log directory
mkdir -p logs

echo "Configuration:"
echo "  Data Root: ${DATA_ROOT}"
echo "  CIFTI Data: ${DTSERIES_ROOT}"
echo "  Output Directory: ${BASE_OUTDIR}"
echo "  N_JOBS: ${N_JOBS}"
echo "  POOL_NUM: ${POOL_NUM}"
echo "  Connectome Mode: ${CONNECTOME_MODE}"
echo ""
echo "Pipeline steps:"
echo "  1. Parcellation: ${RUN_PARCELLATION}"
echo "  2. Build AA Connectomes: ${RUN_BUILD_AA_CONNECTOMES}"
echo "  3. Hyperalignment: ${RUN_HYPERALIGNMENT}"
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
        -v "${DATA_ROOT}":/data \
        -e N_JOBS=${N_JOBS} \
        -e DTSERIES_ROOT="${DTSERIES_ROOT}" \
        -e PTSERIES_ROOT="${PTSERIES_ROOT}" \
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
    echo "Mode: ${CONNECTOME_MODE}"
    echo ""

    docker run --rm \
        -v "${DATA_ROOT}":/data \
        -e N_JOBS=${N_JOBS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e DTSERIES_ROOT="${DTSERIES_ROOT}" \
        -e PTSERIES_ROOT="${PTSERIES_ROOT}" \
        -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_aa_connectomes.py --mode ${CONNECTOME_MODE} \
        2>&1 | tee logs/build_aa_connectomes.log

    echo ""
    echo "✓ AA connectomes built"
    echo ""
else
    echo "Skipping AA connectome building (RUN_BUILD_AA_CONNECTOMES=no)"
    echo ""
fi

# ============================================================================
# STEP 3: HYPERALIGNMENT
# ============================================================================

if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo "================================================"
    echo "STEP 3: HYPERALIGNMENT"
    echo "================================================"
    echo ""
    echo "Running hyperalignment for all 360 parcels..."
    echo "Mode: ${CONNECTOME_MODE}"
    echo "This is the most time-consuming step."
    echo ""

    # Determine hyperalignment mode from CONNECTOME_MODE
    # If CONNECTOME_MODE is 'split' or 'both', run split hyperalignment
    # Otherwise run full hyperalignment
    if [ "${CONNECTOME_MODE}" = "split" ] || [ "${CONNECTOME_MODE}" = "both" ]; then
        HYPERALIGNMENT_MODE="split"
    else
        HYPERALIGNMENT_MODE="full"
    fi

    for parcel in {1..360}; do
        echo "Processing parcel ${parcel}/360..."

        docker run --rm \
            -v "${DATA_ROOT}":/data \
            -e N_JOBS=${N_JOBS} \
            -e POOL_NUM=${POOL_NUM} \
            -e BASE_OUTDIR="${BASE_OUTDIR}" \
            -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
            -w /app/hyperalignment_scripts \
            ${IMAGE_NAME} \
            python run_hyperalignment.py ${parcel} ${HYPERALIGNMENT_MODE} \
            2>&1 | tee logs/hyperalignment_parcel_${parcel}.log
    done

    echo ""
    echo "✓ Hyperalignment complete for all parcels"
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
        -v "${DATA_ROOT}":/data \
        -e N_JOBS=${N_JOBS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
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
        -v "${DATA_ROOT}":/data \
        -e N_JOBS=${N_JOBS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
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
        -v "${DATA_ROOT}":/data \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e N_JOBS=${N_JOBS} \
        -e CONNECTOME_MODE="${CONNECTOME_MODE}" \
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
echo "PIPELINE COMPLETE"
echo "================================================"
echo ""
echo "All requested steps completed successfully!"
echo ""
echo "Results can be found in:"
echo "  ${DATA_ROOT}/hyperalignment_input/glasser_ptseries/              (parcellated data)"
echo "  ${DATA_ROOT}/connectomes/                                        (AA connectomes)"
echo "  ${DATA_ROOT}/connectomes/hyperalignment_output/                  (hyperaligned data & CHA connectomes)"
echo "  ${DATA_ROOT}/connectomes/similarity_matrices/                    (ISC & covariance matrices)"
echo "  ${DATA_ROOT}/connectomes/reliability_results/                    (IDM reliability results)"
echo ""
echo "Logs saved to: ./logs/"
echo ""
