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
DTSERIES_ROOT="${DTSERIES_ROOT:-/data/HBN_CIFTI}"
PTSERIES_ROOT="${PTSERIES_ROOT:-/data/hyperalignment_input/glasser_ptseries}"
BASE_OUTDIR="${BASE_OUTDIR:-/data/connectomes}"
N_JOBS="${N_JOBS:-24}"
POOL_NUM="${POOL_NUM:-24}"

# Pipeline control
RUN_PARCELLATION="${RUN_PARCELLATION:-yes}"
RUN_BUILD_AA_CONNECTOMES="${RUN_BUILD_AA_CONNECTOMES:-yes}"
RUN_HYPERALIGNMENT="${RUN_HYPERALIGNMENT:-yes}"
RUN_CHA_CONNECTOMES="${RUN_CHA_CONNECTOMES:-yes}"

# Connectome mode: full, split, or both
AA_CONNECTOME_MODE="${AA_CONNECTOME_MODE:-both}"
CHA_CONNECTOME_MODE="${CHA_CONNECTOME_MODE:-both}"

# Hyperalignment mode
HYPERALIGNMENT_MODE="${HYPERALIGNMENT_MODE:-full}"

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
    echo "  export N_JOBS=32              # Number of parallel jobs"
    echo "  export AA_CONNECTOME_MODE=full  # Build only full AA connectomes"
    echo "  export CHA_CONNECTOME_MODE=split # Build only split CHA connectomes"
    echo "  ./full_pipeline.sh"
    exit 1
fi

if [ ! -d "${DATA_ROOT}" ]; then
    echo "ERROR: Data directory not found: ${DATA_ROOT}"
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

# Create log directory
mkdir -p logs

echo "Configuration:"
echo "  Data Root: ${DATA_ROOT}"
echo "  N_JOBS: ${N_JOBS}"
echo "  POOL_NUM: ${POOL_NUM}"
echo "  AA Connectome Mode: ${AA_CONNECTOME_MODE}"
echo "  CHA Connectome Mode: ${CHA_CONNECTOME_MODE}"
echo ""
echo "Pipeline steps:"
echo "  1. Parcellation: ${RUN_PARCELLATION}"
echo "  2. Build AA Connectomes: ${RUN_BUILD_AA_CONNECTOMES}"
echo "  3. Hyperalignment: ${RUN_HYPERALIGNMENT}"
echo "  4. Build CHA Connectomes: ${RUN_CHA_CONNECTOMES}"
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
    echo "Mode: ${AA_CONNECTOME_MODE}"
    echo ""

    docker run --rm \
        -v "${DATA_ROOT}":/data \
        -e N_JOBS=${N_JOBS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e DTSERIES_ROOT="${DTSERIES_ROOT}" \
        -e PTSERIES_ROOT="${PTSERIES_ROOT}" \
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
# STEP 3: HYPERALIGNMENT
# ============================================================================

if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo "================================================"
    echo "STEP 3: HYPERALIGNMENT"
    echo "================================================"
    echo ""
    echo "Running hyperalignment for all 360 parcels..."
    echo "This is the most time-consuming step."
    echo ""

    for parcel in {1..360}; do
        echo "Processing parcel ${parcel}/360..."

        docker run --rm \
            -v "${DATA_ROOT}":/data \
            -e N_JOBS=${N_JOBS} \
            -e POOL_NUM=${POOL_NUM} \
            -e BASE_OUTDIR="${BASE_OUTDIR}" \
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
    echo "Mode: ${CHA_CONNECTOME_MODE}"
    echo ""

    docker run --rm \
        -v "${DATA_ROOT}":/data \
        -e N_JOBS=${N_JOBS} \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_CHA_connectomes.py --mode ${CHA_CONNECTOME_MODE} \
        2>&1 | tee logs/build_cha_connectomes.log

    echo ""
    echo "✓ CHA connectomes built"
    echo ""
else
    echo "Skipping CHA connectome building (RUN_CHA_CONNECTOMES=no)"
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
echo "  ${DATA_ROOT}/hyperalignment_input/glasser_ptseries/  (parcellated data)"
echo "  ${DATA_ROOT}/connectomes/                             (AA connectomes)"
echo "  ${DATA_ROOT}/connectomes/hyperalignment_output/      (hyperaligned data & CHA connectomes)"
echo ""
echo "Logs saved to: ./logs/"
echo ""
