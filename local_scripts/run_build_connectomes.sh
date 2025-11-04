#!/bin/bash
# Local execution: Build connectomes
# Works on Mac and Linux with Docker

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# Data directory
DATA_ROOT="${DATA_ROOT:-$(pwd)/data}"

# Script to run
SCRIPT="${1:-build_aa_connectomes.py}"

# Number of parallel jobs
N_JOBS="${N_JOBS:-8}"

# ============================================================================
# VALIDATION
# ============================================================================

echo "================================================"
echo "Local Execution: Build Connectomes"
echo "================================================"
echo "Docker image: ${IMAGE_NAME}"
echo "Data root: ${DATA_ROOT}"
echo "Script: ${SCRIPT}"
echo "N_JOBS: ${N_JOBS}"
echo "================================================"
echo ""

# Validate script name
if [[ ! "${SCRIPT}" =~ ^(build_aa_connectomes\.py|build_CHA_connectomes\.py)$ ]]; then
    echo "ERROR: Invalid script name: ${SCRIPT}"
    echo ""
    echo "Usage: $0 [script_name]"
    echo ""
    echo "Valid scripts:"
    echo "  build_aa_connectomes.py   - Build anatomical connectomes (default)"
    echo "  build_CHA_connectomes.py  - Build CHA connectomes"
    echo ""
    echo "Example:"
    echo "  $0 build_aa_connectomes.py"
    echo "  $0 build_CHA_connectomes.py"
    exit 1
fi

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

echo "Starting connectome building with ${SCRIPT}..."
echo ""

docker run --rm \
    -v "${DATA_ROOT}":/data \
    -e N_JOBS=${N_JOBS} \
    -w /app/hyperalignment_scripts \
    ${IMAGE_NAME} \
    python3 ${SCRIPT}

EXIT_CODE=$?

echo ""
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "================================================"
    echo "SUCCESS: Connectome building complete!"
    echo "================================================"
else
    echo "================================================"
    echo "ERROR: Connectome building failed"
    echo "Exit code: ${EXIT_CODE}"
    echo "================================================"
    exit ${EXIT_CODE}
fi
