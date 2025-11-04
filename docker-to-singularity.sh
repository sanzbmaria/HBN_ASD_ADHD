#!/bin/bash
# Convert Docker image to Singularity image for HPC cluster use
# This script requires Singularity/Apptainer to be installed

set -e

IMAGE_NAME="hyperalignment"
IMAGE_TAG="latest"
OUTPUT_FILE="hyperalignment.sif"

echo "Converting Docker image to Singularity"
echo "================================================"
echo "Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Output file: ${OUTPUT_FILE}"
echo "================================================"
echo ""

# Check if singularity or apptainer is available
if command -v singularity &> /dev/null; then
    SING_CMD="singularity"
elif command -v apptainer &> /dev/null; then
    SING_CMD="apptainer"
else
    echo "ERROR: Neither singularity nor apptainer found in PATH"
    echo ""
    echo "Please install Singularity/Apptainer or run this on your cluster:"
    echo "  singularity build ${OUTPUT_FILE} docker-daemon://${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
    echo "Or pull from Docker Hub (if pushed):"
    echo "  singularity build ${OUTPUT_FILE} docker://yourusername/${IMAGE_NAME}:${IMAGE_TAG}"
    exit 1
fi

echo "Using: ${SING_CMD}"
echo ""
echo "Building Singularity image..."
${SING_CMD} build ${OUTPUT_FILE} docker-daemon://${IMAGE_NAME}:${IMAGE_TAG}

echo ""
echo "================================================"
echo "Conversion complete!"
echo "Singularity image: ${OUTPUT_FILE}"
echo ""
echo "Transfer this file to your PBS cluster and use with PBS scripts:"
echo "  scp ${OUTPUT_FILE} your-cluster:/path/to/images/"
echo "================================================"
