#!/bin/bash
# Local execution: Build connectomes
# Modified for UK Biobank RAP with separate read-only inputs and writable outputs

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# Data directories
DATA_ROOT="${DATA_ROOT:-$(pwd)/data}"
INPUT_DIR="${INPUT_DIR:-/home/dnanexus/hyperalignment_output}"
OUTPUT_DIR="${OUTPUT_DIR:-/home/dnanexus/connectomes}"

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
echo "Input directory: ${INPUT_DIR}"
echo "Output directory: ${OUTPUT_DIR}"
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

# Check if input directory exists
if [ ! -d "${INPUT_DIR}" ]; then
    echo "ERROR: Input directory not found: ${INPUT_DIR}"
    exit 1
fi

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# ============================================================================
# EXECUTION
# ============================================================================

echo "Starting connectome building with ${SCRIPT}..."
echo ""

docker run --rm \
    -v "${INPUT_DIR}":/data/inputs:ro \
    -v "${OUTPUT_DIR}":/data/outputs \
    -e N_JOBS=${N_JOBS} \
    -e PTSERIES_ROOT=/data/inputs/glasser_ptseries \
    -e BASE_OUTDIR=/data/outputs \
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
