#!/bin/bash
# Build the Docker image for hyperalignment pipeline

set -e

IMAGE_NAME="hyperalignment"
IMAGE_TAG="latest"

echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "================================================"

docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo ""
echo "================================================"
echo "Build complete!"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "Next steps:"
echo "  1. Test locally: ./docker-run.sh"
echo "  2. Convert to Singularity for PBS cluster: ./docker-to-singularity.sh"
echo "================================================"
