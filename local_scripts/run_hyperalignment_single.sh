#!/bin/bash
# Local execution: Run hyperalignment for a single parcel
# Works on Mac and Linux with Docker

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# Data directory
DATA_ROOT="${DATA_ROOT:-$(pwd)/data}"

# Parcel to process (required)
PARCEL="${1:-}"

# Mode: 'full', 'split', or 'both'
MODE="${2:-both}"

# Number of parallel jobs
N_JOBS="${N_JOBS:-8}"
POOL_NUM="${POOL_NUM:-8}"

# ============================================================================
# VALIDATION
# ============================================================================

if [ -z "${PARCEL}" ]; then
    echo "Usage: $0 <parcel_number> [mode]"
    echo ""
    echo "Arguments:"
    echo "  parcel_number: Parcel to process (1-360)"
    echo "  mode: 'full', 'split', or 'both' (default: both)"
    echo ""
    echo "Example:"
    echo "  $0 1 full"
    echo "  $0 180 both"
    echo ""
    echo "Environment variables:"
    echo "  DATA_ROOT: Path to data directory (default: ./data)"
    echo "  N_JOBS: Number of parallel jobs (default: 8)"
    exit 1
fi

if [ ${PARCEL} -lt 1 ] || [ ${PARCEL} -gt 360 ]; then
    echo "ERROR: PARCEL must be between 1 and 360 (got: ${PARCEL})"
    exit 1
fi

if [[ ! "${MODE}" =~ ^(full|split|both)$ ]]; then
    echo "ERROR: MODE must be 'full', 'split', or 'both' (got: ${MODE})"
    exit 1
fi

echo "================================================"
echo "Local Execution: Hyperalignment"
echo "================================================"
echo "Docker image: ${IMAGE_NAME}"
echo "Data root: ${DATA_ROOT}"
echo "Parcel: ${PARCEL}"
echo "Mode: ${MODE}"
echo "N_JOBS: ${N_JOBS}"
echo "================================================"
echo ""

# Check if Docker image exists
if ! docker image inspect ${IMAGE_NAME} &> /dev/null; then
    echo "ERROR: Docker image '${IMAGE_NAME}' not found"
    echo "Please build it first: ./docker-build.sh"
    exit 1
fi

# Check if data directory exists
if [ ! -d "${DATA_ROOT}" ]; then
    echo "ERROR: Data directory not found: ${DATA_ROOT}"
    echo "Please set DATA_ROOT: export DATA_ROOT=/path/to/your/data"
    exit 1
fi

# ============================================================================
# EXECUTION
# ============================================================================

echo "Starting hyperalignment for parcel ${PARCEL}..."
echo ""

docker run --rm \
    -v "${DATA_ROOT}":/data \
    -e N_JOBS=${N_JOBS} \
    -e POOL_NUM=${POOL_NUM} \
    -w /app/hyperalignment_scripts \
    ${IMAGE_NAME} \
    python2 run_hyperalignment.py ${PARCEL} ${MODE}

EXIT_CODE=$?

echo ""
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "================================================"
    echo "SUCCESS: Hyperalignment complete for parcel ${PARCEL}!"
    echo "================================================"
else
    echo "================================================"
    echo "ERROR: Hyperalignment failed for parcel ${PARCEL}"
    echo "Exit code: ${EXIT_CODE}"
    echo "================================================"
    exit ${EXIT_CODE}
fi
