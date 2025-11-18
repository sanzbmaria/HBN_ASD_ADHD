#!/bin/bash
# Build the Docker image for hyperalignment pipeline

set -e

IMAGE_NAME="hyperalignment"
IMAGE_TAG="latest"

echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "================================================"

# Validate required files exist before building
echo "Validating required files..."
REQUIRED_FILES=(
    "hyperalignment_scripts/config.sh"
    "hyperalignment_scripts/read_config.py"
    "hyperalignment_scripts/utils.py"
    "Dockerfile"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "ERROR: Required file not found: $file"
        echo "Please ensure all pipeline files are present before building."
        exit 1
    fi
done

echo "✓ All required files found"
echo ""

docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo ""
echo "================================================"
echo "Build complete!"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "Next steps:"
echo "  1. Test locally: ./docker-run.sh"
echo "  2. Run test pipeline: ./test_pipeline.sh"
echo "  3. Run full pipeline: ./local_scripts/run_full_pipeline.sh"
echo "================================================"
