#!/bin/bash
# Local execution: Run the complete hyperalignment pipeline
# Modified for UK Biobank RAP with correct pipeline order

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# Data directory (REQUIRED)
DATA_ROOT="${DATA_ROOT:-}"

# Pipeline steps to run
RUN_PARCELLATION="${RUN_PARCELLATION:-yes}"
RUN_AA_CONNECTOMES="${RUN_AA_CONNECTOMES:-yes}"
RUN_HYPERALIGNMENT="${RUN_HYPERALIGNMENT:-yes}"
RUN_CHA_CONNECTOMES="${RUN_CHA_CONNECTOMES:-yes}"

# Hyperalignment configuration
START_PARCEL="${START_PARCEL:-1}"
END_PARCEL="${END_PARCEL:-360}"
MODE="${MODE:-both}"
MAX_PARALLEL="${MAX_PARALLEL:-4}"

# Resource configuration
N_JOBS_PARCELLATION="${N_JOBS_PARCELLATION:-8}"
N_JOBS_HYPERALIGN="${N_JOBS_HYPERALIGN:-4}"
N_JOBS_CONNECTOMES="${N_JOBS_CONNECTOMES:-8}"

# ============================================================================
# VALIDATION
# ============================================================================

if [ -z "${DATA_ROOT}" ]; then
    echo "ERROR: DATA_ROOT environment variable not set"
    echo ""
    echo "Please set it to your data directory:"
    echo "  export DATA_ROOT=/path/to/your/data"
    echo ""
    echo "Expected directory structure:"
    echo "  \$DATA_ROOT/"
    echo "  ├── Input CIFTI files"
    echo "  Outputs will go to /home/dnanexus/hyperalignment_output and /home/dnanexus/connectomes"
    exit 1
fi

if [ ! -d "${DATA_ROOT}" ]; then
    echo "ERROR: Data directory not found: ${DATA_ROOT}"
    exit 1
fi

# Check if Docker image exists
if ! docker image inspect ${IMAGE_NAME} &> /dev/null; then
    echo "ERROR: Docker image '${IMAGE_NAME}' not found"
    echo "Please build it first: ./docker-build.sh"
    exit 1
fi

# ============================================================================
# SETUP
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START_TIME=$(date +%s)

mkdir -p logs

echo "================================================"
echo "Hyperalignment Full Pipeline - Local Execution"
echo "================================================"
echo "Start time: $(date)"
echo "Data root: ${DATA_ROOT}"
echo "Docker image: ${IMAGE_NAME}"
echo ""
echo "Pipeline steps:"
echo "  1. Parcellation: ${RUN_PARCELLATION}"
echo "  2. AA Connectomes: ${RUN_AA_CONNECTOMES}"
echo "  3. Hyperalignment: ${RUN_HYPERALIGNMENT} (parcels ${START_PARCEL}-${END_PARCEL}, mode: ${MODE})"
echo "  4. CHA Connectomes: ${RUN_CHA_CONNECTOMES}"
echo ""
echo "Resource allocation:"
echo "  Parcellation jobs: ${N_JOBS_PARCELLATION}"
echo "  Hyperalignment parallel containers: ${MAX_PARALLEL}"
echo "  Hyperalignment jobs per container: ${N_JOBS_HYPERALIGN}"
echo "  Connectome jobs: ${N_JOBS_CONNECTOMES}"
echo "================================================"
echo ""

# ============================================================================
# STEP 1: PARCELLATION
# ============================================================================

if [ "${RUN_PARCELLATION}" = "yes" ]; then
    echo "================================================"
    echo "STEP 1: PARCELLATION"
    echo "================================================"
    echo "Started: $(date)"
    echo ""

    export N_JOBS=${N_JOBS_PARCELLATION}
    ${SCRIPT_DIR}/run_parcellation.sh

    PARCELLATION_EXIT=$?
    if [ ${PARCELLATION_EXIT} -ne 0 ]; then
        echo ""
        echo "WARNING: Parcellation returned exit code ${PARCELLATION_EXIT}"
        echo "Checking if output files were created..."
        
        # Count output files to verify success
        OUTPUT_COUNT=$(find /home/dnanexus/hyperalignment_output/glasser_ptseries -name "*.ptseries.nii" 2>/dev/null | wc -l)
        if [ ${OUTPUT_COUNT} -eq 0 ]; then
            echo "ERROR: No output files found. Parcellation actually failed."
            exit ${PARCELLATION_EXIT}
        else
            echo "Found ${OUTPUT_COUNT} output files. Continuing despite exit code..."
        fi
    fi

    echo ""
    echo "Parcellation completed: $(date)"
    echo ""
else
    echo "Skipping parcellation step"
    echo ""
fi

# ============================================================================
# STEP 2: BUILD AA CONNECTOMES
# ============================================================================

if [ "${RUN_AA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 2: BUILD AA CONNECTOMES"
    echo "================================================"
    echo "Started: $(date)"
    echo ""

    export N_JOBS=${N_JOBS_CONNECTOMES}
    ${SCRIPT_DIR}/run_build_connectomes.sh build_aa_connectomes.py

    AA_EXIT=$?
    if [ ${AA_EXIT} -ne 0 ]; then
        echo ""
        echo "ERROR: AA connectome building failed with exit code ${AA_EXIT}"
        exit ${AA_EXIT}
    fi

    echo ""
    echo "AA connectome building completed: $(date)"
    echo ""
else
    echo "Skipping AA connectome building step"
    echo ""
fi

# ============================================================================
# STEP 3: HYPERALIGNMENT
# ============================================================================

if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo "================================================"
    echo "STEP 3: HYPERALIGNMENT"
    echo "================================================"
    echo "Started: $(date)"
    echo "Processing parcels ${START_PARCEL} to ${END_PARCEL}"
    echo ""

    export N_JOBS=${N_JOBS_HYPERALIGN}
    export POOL_NUM=${N_JOBS_HYPERALIGN}
    export START_PARCEL=${START_PARCEL}
    export END_PARCEL=${END_PARCEL}
    export MODE=${MODE}
    export MAX_PARALLEL=${MAX_PARALLEL}

    ${SCRIPT_DIR}/run_hyperalignment_parallel.sh

    HYPERALIGN_EXIT=$?
    if [ ${HYPERALIGN_EXIT} -ne 0 ]; then
        echo ""
        echo "ERROR: Hyperalignment failed with exit code ${HYPERALIGN_EXIT}"
        exit ${HYPERALIGN_EXIT}
    fi

    echo ""
    echo "Hyperalignment completed: $(date)"
    echo ""
else
    echo "Skipping hyperalignment step"
    echo ""
fi

# ============================================================================
# STEP 4: BUILD CHA CONNECTOMES
# ============================================================================

if [ "${RUN_CHA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 4: BUILD CHA CONNECTOMES"
    echo "================================================"
    echo "Started: $(date)"
    echo ""

    export N_JOBS=${N_JOBS_CONNECTOMES}
    ${SCRIPT_DIR}/run_build_connectomes.sh build_CHA_connectomes.py

    CHA_EXIT=$?
    if [ ${CHA_EXIT} -ne 0 ]; then
        echo ""
        echo "ERROR: CHA connectome building failed with exit code ${CHA_EXIT}"
        exit ${CHA_EXIT}
    fi

    echo ""
    echo "CHA connectome building completed: $(date)"
    echo ""
else
    echo "Skipping CHA connectome building step"
    echo ""
fi

# ============================================================================
# SUMMARY
# ============================================================================

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))
SECONDS=$((ELAPSED % 60))

echo "================================================"
echo "PIPELINE COMPLETE"
echo "================================================"
echo "End time: $(date)"
echo "Total elapsed time: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo ""
echo "Output locations:"
echo "  Parcellated data: /home/dnanexus/hyperalignment_output/glasser_ptseries/"
echo "  AA Connectomes: /home/dnanexus/connectomes/fine/"
echo "  Aligned timeseries: /home/dnanexus/connectomes/hyperalignment_output/aligned_timeseries/"
echo "  Mappers: /home/dnanexus/connectomes/hyperalignment_output/mappers/"
echo "  CHA Connectomes: /home/dnanexus/connectomes/fine/"
echo ""
echo "Logs: $(pwd)/logs/"
echo "================================================"
