#!/bin/bash
# Setup script for HBN ASD/ADHD Hyperalignment Pipeline (NO DOCKER)
# This script helps install all dependencies

set -e

echo "=============================================="
echo "HBN Hyperalignment Pipeline - Environment Setup"
echo "=============================================="
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# STEP 1: Check for conda
# ============================================================================

echo "STEP 1: Checking for conda/mamba..."
echo ""

if command -v mamba &> /dev/null; then
    CONDA_CMD="mamba"
    echo "  Found mamba (faster)"
elif command -v conda &> /dev/null; then
    CONDA_CMD="conda"
    echo "  Found conda"
else
    echo "ERROR: Neither conda nor mamba found!"
    echo ""
    echo "Please install Miniconda or Anaconda first:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    echo ""
    exit 1
fi

# ============================================================================
# STEP 2: Create conda environment
# ============================================================================

echo ""
echo "STEP 2: Creating conda environment 'hyperalignment'..."
echo ""

ENV_NAME="hyperalignment"

# Check if environment already exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "Environment '${ENV_NAME}' already exists."
    read -p "Do you want to remove and recreate it? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        conda env remove -n ${ENV_NAME} -y
    else
        echo "Skipping environment creation."
        echo "Activate with: conda activate ${ENV_NAME}"
        echo ""
        SKIP_CREATE=1
    fi
fi

if [ -z "${SKIP_CREATE:-}" ]; then
    echo "Creating conda environment with Python 3.9..."

    ${CONDA_CMD} create -n ${ENV_NAME} \
        python=3.9.23 \
        numpy=1.23.5 \
        scipy=1.10.1 \
        nibabel=5.3.2 \
        scikit-learn=1.6.1 \
        pandas=2.3.3 \
        matplotlib=3.9.4 \
        setuptools=59.8.0 \
        joblib \
        tqdm \
        openpyxl \
        swig \
        gsl \
        -c conda-forge \
        -y

    echo ""
    echo "Installing PyMVPA2..."

    # Activate environment and install pymvpa2
    eval "$(conda shell.bash hook)"
    conda activate ${ENV_NAME}

    pip install pymvpa2==2.6.5

    # Ensure numpy version is correct (pymvpa2 might change it)
    ${CONDA_CMD} install numpy=1.23.5 -c conda-forge -y

    echo ""
    echo "Conda environment '${ENV_NAME}' created successfully!"
fi

# ============================================================================
# STEP 3: Install Connectome Workbench
# ============================================================================

echo ""
echo "STEP 3: Connectome Workbench"
echo ""

if command -v wb_command &> /dev/null; then
    WB_PATH=$(which wb_command)
    echo "  Connectome Workbench already installed: ${WB_PATH}"
    wb_command -version 2>&1 | head -1
else
    echo "  Connectome Workbench NOT found in PATH."
    echo ""
    echo "  Please download and install from:"
    echo "  https://www.humanconnectome.org/software/get-connectome-workbench"
    echo ""
    echo "  After installing, add to your PATH:"
    echo "  export PATH=/path/to/workbench/bin_linux64:\$PATH"
    echo ""

    read -p "Would you like to download and install Workbench now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        INSTALL_DIR="${HOME}/workbench"
        echo "Installing Connectome Workbench to ${INSTALL_DIR}..."

        mkdir -p "${INSTALL_DIR}"
        cd "${INSTALL_DIR}"

        # Download workbench
        wget -q --show-progress https://www.humanconnectome.org/storage/app/media/workbench/workbench-linux64-v1.5.0.zip

        # Extract
        unzip -q workbench-linux64-v1.5.0.zip
        rm workbench-linux64-v1.5.0.zip

        # Add to .bashrc
        echo "" >> ~/.bashrc
        echo "# Connectome Workbench" >> ~/.bashrc
        echo "export PATH=\"${INSTALL_DIR}/workbench/bin_linux64:\$PATH\"" >> ~/.bashrc

        echo ""
        echo "Workbench installed to: ${INSTALL_DIR}/workbench"
        echo "Added to ~/.bashrc"
        echo ""
        echo "IMPORTANT: Run 'source ~/.bashrc' or restart your terminal"

        cd "${SCRIPT_DIR}"
    fi
fi

# ============================================================================
# STEP 4: Verify installation
# ============================================================================

echo ""
echo "STEP 4: Verifying installation..."
echo ""

# Activate environment for testing
eval "$(conda shell.bash hook)"
conda activate ${ENV_NAME}

echo "Python packages:"
python3 -c "import numpy; print(f'  numpy: {numpy.__version__}')"
python3 -c "import scipy; print(f'  scipy: {scipy.__version__}')"
python3 -c "import nibabel; print(f'  nibabel: {nibabel.__version__}')"
python3 -c "import sklearn; print(f'  scikit-learn: {sklearn.__version__}')"
python3 -c "import pandas; print(f'  pandas: {pandas.__version__}')"
python3 -c "import mvpa2; print(f'  pymvpa2: {mvpa2.__version__}')"
python3 -c "import joblib; print('  joblib: OK')"
python3 -c "import tqdm; print('  tqdm: OK')"

echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo "=============================================="
echo "SETUP COMPLETE"
echo "=============================================="
echo ""
echo "To use the pipeline:"
echo ""
echo "1. Activate the environment:"
echo "   conda activate ${ENV_NAME}"
echo ""
echo "2. Set your data directory:"
echo "   export DATA_ROOT=/path/to/your/data"
echo ""
echo "3. Run the pipeline:"
echo "   ./run_pipeline_local.sh"
echo ""
echo "Your data directory should contain:"
echo "  - HBN_CIFTI/                    (input dtseries files)"
echo "  - HBN_ASD_ADHD.xlsx             (metadata with train/test splits)"
echo ""
echo "Optional configuration:"
echo "  export N_JOBS=24                # Number of parallel jobs"
echo "  export CONNECTOME_MODE=both     # full, split, or both"
echo ""
