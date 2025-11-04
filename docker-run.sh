#!/bin/bash
# Run the hyperalignment Docker container interactively
# This script is for local testing - use PBS scripts for cluster execution

set -e

IMAGE_NAME="hyperalignment:latest"

# Default data paths (edit these to match your local setup)
DATA_ROOT="${DATA_ROOT:-$(pwd)/data}"

echo "Running Docker container: ${IMAGE_NAME}"
echo "================================================"
echo "Mounting data from: ${DATA_ROOT}"
echo ""
echo "Directory structure expected:"
echo "  ${DATA_ROOT}/HBN_CIFTI/                    <- input dtseries files"
echo "  ${DATA_ROOT}/hyperalignment_input/         <- parcellated data"
echo "  ${DATA_ROOT}/connectomes/                  <- output connectomes"
echo "  ${DATA_ROOT}/diagnosis_summary/            <- subject metadata CSV"
echo "================================================"
echo ""

docker run -it --rm \
    -v "${DATA_ROOT}":/data \
    -e N_JOBS=24 \
    -w /app/hyperalignment_scripts \
    ${IMAGE_NAME} \
    /bin/bash

echo ""
echo "Container exited."
