#!/bin/bash
# Local execution: Apply parcellation to CIFTI dtseries files
# Works on Mac and Linux with Docker

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# Data directories (edit these to match your local setup)
# BioBank paths: inputs are READ-ONLY, outputs are WRITABLE
DATA_ROOT="${DATA_ROOT:-$(pwd)/data}"
BASEDIR="${BASEDIR:-${DATA_ROOT}/inputs}"
OUTDIR="${OUTDIR:-${DATA_ROOT}/outputs/glasser_ptseries}"

# Number of parallel jobs (adjust based on your CPU cores)
N_JOBS="${N_JOBS:-8}"  # Default to 8 cores, adjust as needed

# ============================================================================
# VALIDATION
# ============================================================================

echo "================================================"
echo "Local Execution: Parcellation"
echo "================================================"
echo "Docker image: ${IMAGE_NAME}"
echo "Input directory: ${BASEDIR}"
echo "Output directory: ${OUTDIR}"
echo "Parallel jobs: ${N_JOBS}"
echo "================================================"
echo ""

# Check if Docker image exists
if ! docker image inspect ${IMAGE_NAME} &> /dev/null; then
    echo "ERROR: Docker image '${IMAGE_NAME}' not found"
    echo "Please build it first: ./docker-build.sh"
    exit 1
fi

# Check if input directory exists
if [ ! -d "${BASEDIR}" ]; then
    echo "ERROR: Input directory not found: ${BASEDIR}"
    echo ""
    echo "Please set DATA_ROOT or BASEDIR:"
    echo "  export DATA_ROOT=/path/to/your/data"
    echo "  export BASEDIR=/path/to/HBN_CIFTI"
    exit 1
fi

# Create output directory if needed
mkdir -p "${OUTDIR}"

# ============================================================================
# EXECUTION
# ============================================================================

echo "Starting parcellation..."
echo ""

docker run --rm \
    -v "${DATA_ROOT}":/data \
    -e BASEDIR=/data/inputs \
    -e OUTDIR=/data/outputs/glasser_ptseries \
    -e TMPDIR="${TMPDIR:-/data/outputs/.tmp}" \
    -e N_JOBS=${N_JOBS} \
    -w /app/hyperalignment_scripts \
    ${IMAGE_NAME} \
    bash apply_parcellation.sh

echo ""
echo "================================================"
echo "Parcellation complete!"
echo "Output directory: ${OUTDIR}"
echo "================================================"
