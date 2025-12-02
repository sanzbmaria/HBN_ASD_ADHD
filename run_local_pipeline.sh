#!/bin/bash
# Full Pipeline: Run the complete hyperalignment pipeline WITHOUT DOCKER
# Order: Parcellation -> AA Connectomes -> Hyperalignment -> CHA Connectomes

set -e

# ============================================================================
# CONFIGURATION - Override via environment variables
# ============================================================================

IMAGE_NAME="hyperalignment:latest"  # Kept for consistency, not used in local mode

# Data directory (REQUIRED)
DATA_ROOT="${DATA_ROOT:-}"

# Directory paths - LOCAL filesystem paths (not container paths)
# Note: Trailing slashes are included to match Docker version
DTSERIES_ROOT="${DTSERIES_ROOT:-${DATA_ROOT}/CIFTI_1/}"
PTSERIES_ROOT="${PTSERIES_ROOT:-${DATA_ROOT}/hyperalignment_input/glasser_ptseries/}"
BASE_OUTDIR="${BASE_OUTDIR:-${DATA_ROOT}/connectomes}"

# Processing parameters
N_JOBS="${N_JOBS:-24}"
POOL_NUM="${POOL_NUM:-24}"

# Pipeline control - set to "no" to skip a step
RUN_PARCELLATION="${RUN_PARCELLATION:-yes}"
RUN_BUILD_AA_CONNECTOMES="${RUN_BUILD_AA_CONNECTOMES:-yes}"
RUN_HYPERALIGNMENT="${RUN_HYPERALIGNMENT:-yes}"
RUN_CHA_CONNECTOMES="${RUN_CHA_CONNECTOMES:-yes}"
RUN_SIMILARITY_MATRICES="${RUN_SIMILARITY_MATRICES:-yes}"
RUN_IDM_RELIABILITY="${RUN_IDM_RELIABILITY:-yes}"

# Centralized connectome mode: full, split, or both
CONNECTOME_MODE="${CONNECTOME_MODE:-both}"

# Metadata filtering (optional)
USE_METADATA_FILTER="${USE_METADATA_FILTER:-0}"
METADATA_EXCEL="${METADATA_EXCEL:-${DATA_ROOT}/HBN_ASD_ADHD.xlsx}"

# Train/test split configuration (optional)
GENERATE_SPLIT="${GENERATE_SPLIT:-no}"
SPLIT_MODE="${SPLIT_MODE:-random}"
TRAIN_PCT="${TRAIN_PCT:-1.0}"
SPLIT_OUTPUT="${SPLIT_OUTPUT:-${DATA_ROOT}/train_test_split.txt}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HYPERALIGNMENT_DIR="${SCRIPT_DIR}/hyperalignment_scripts"

# ============================================================================
# AA CONNECTOME MODE HANDLING
# ============================================================================

# IMPORTANT: AA connectomes always needs FULL connectomes for hyperalignment training.
ORIGINAL_MODE="${CONNECTOME_MODE}"
if [ "${CONNECTOME_MODE}" = "split" ]; then
    AA_CONNECTOME_MODE="both"
    echo ""
    echo "======================================================================"
    echo "NOTE: AA connectomes will build BOTH full and split connectomes"
    echo "(Hyperalignment training requires full connectomes)"
    echo "Other stages will use mode: ${ORIGINAL_MODE}"
    echo "======================================================================"
    echo ""
else
    AA_CONNECTOME_MODE="${CONNECTOME_MODE}"
fi

# ============================================================================
# VALIDATION
# ============================================================================

echo "================================================"
echo "HYPERALIGNMENT PIPELINE - FULL PRODUCTION MODE"
echo "================================================"
echo ""

if [ -z "${DATA_ROOT}" ]; then
    echo "ERROR: DATA_ROOT environment variable not set"
    echo ""
    echo "Usage:"
    echo "  export DATA_ROOT=/path/to/your/data"
    echo "  ./run_pipeline_local.sh"
    echo ""
    echo "Configuration can be overridden via environment variables:"
    echo "  export N_JOBS=32               # Number of parallel jobs"
    echo "  export CONNECTOME_MODE=split   # Use 'full', 'split', or 'both' (default)"
    echo "  export DTSERIES_ROOT=\${DATA_ROOT}/CIFTI_DATA  # Path to your CIFTI files"
    echo "  ./run_pipeline_local.sh"
    exit 1
fi

if [ ! -d "${DATA_ROOT}" ]; then
    echo "ERROR: Data directory not found: ${DATA_ROOT}"
    exit 1
fi

# Validate that DTSERIES_ROOT is under DATA_ROOT if it's a custom path
if [ -n "${DTSERIES_ROOT}" ] && [[ "${DTSERIES_ROOT}" != "${DATA_ROOT}"* ]]; then
    # DTSERIES_ROOT is set but not under DATA_ROOT - try to resolve it
    # Convert to absolute paths for comparison
    if [ -d "${DTSERIES_ROOT}" ]; then
        DTSERIES_ABS=$(cd "${DTSERIES_ROOT}" && pwd)
        DATA_ROOT_ABS=$(cd "${DATA_ROOT}" && pwd)

        # Check if DTSERIES_ABS starts with DATA_ROOT_ABS
        if [[ ! "${DTSERIES_ABS}" == "${DATA_ROOT_ABS}"* ]]; then
            echo "WARNING: DTSERIES_ROOT is not under DATA_ROOT"
            echo ""
            echo "Current configuration:"
            echo "  DATA_ROOT: ${DATA_ROOT}"
            echo "  DTSERIES_ROOT: ${DTSERIES_ROOT}"
            echo ""
            echo "This may be intentional, but ensure paths are correct."
            echo ""
        fi
    fi
fi

# Check for required tools
echo "Checking dependencies..."

# Check for wb_command (Connectome Workbench)
if ! command -v wb_command &> /dev/null; then
    echo "ERROR: wb_command (Connectome Workbench) not found in PATH"
    echo ""
    echo "Please install Connectome Workbench:"
    echo "  https://www.humanconnectome.org/software/get-connectome-workbench"
    echo ""
    echo "Or add it to your PATH:"
    echo "  export PATH=/path/to/workbench/bin_linux64:\$PATH"
    exit 1
fi
echo "  - wb_command: OK"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found in PATH"
    exit 1
fi
echo "  - python3: OK"

# Check for required Python packages
python3 -c "import numpy" 2>/dev/null || { echo "ERROR: numpy not installed"; exit 1; }
python3 -c "import scipy" 2>/dev/null || { echo "ERROR: scipy not installed"; exit 1; }
python3 -c "import nibabel" 2>/dev/null || { echo "ERROR: nibabel not installed"; exit 1; }
python3 -c "import sklearn" 2>/dev/null || { echo "ERROR: scikit-learn not installed"; exit 1; }
python3 -c "import mvpa2" 2>/dev/null || { echo "ERROR: pymvpa2 not installed"; exit 1; }
python3 -c "import pandas" 2>/dev/null || { echo "ERROR: pandas not installed"; exit 1; }
python3 -c "import joblib" 2>/dev/null || { echo "ERROR: joblib not installed"; exit 1; }
python3 -c "import tqdm" 2>/dev/null || { echo "ERROR: tqdm not installed"; exit 1; }
echo "  - Python packages: OK"

# Validate that config.sh exists (detect missing configuration)
echo "Validating local configuration..."
if [ ! -f "${HYPERALIGNMENT_DIR}/config.sh" ]; then
    echo ""
    echo "ERROR: Configuration file missing"
    echo ""
    echo "The required config.sh file is missing from ${HYPERALIGNMENT_DIR}/"
    echo "This file is needed for the pipeline to run correctly."
    echo ""
    echo "Solution: Ensure all pipeline scripts are present in the hyperalignment_scripts/ directory."
    exit 1
fi
echo "✓ Configuration validated"
echo ""

# Create log directory
mkdir -p "${SCRIPT_DIR}/logs"

# Create output directories
mkdir -p "${PTSERIES_ROOT}"
mkdir -p "${BASE_OUTDIR}"
mkdir -p "${BASE_OUTDIR}/hyperalignment_output"
mkdir -p "${BASE_OUTDIR}/similarity_matrices"
mkdir -p "${BASE_OUTDIR}/reliability_results"

echo "Configuration:"
echo "  Data Root: ${DATA_ROOT}"
echo "  CIFTI Data: ${DTSERIES_ROOT}"
echo "  Parcellated Output: ${PTSERIES_ROOT}"
echo "  Output Directory: ${BASE_OUTDIR}"
echo "  N_JOBS: ${N_JOBS}"
echo "  POOL_NUM: ${POOL_NUM}"
echo "  Connectome Mode: ${CONNECTOME_MODE}"
if [ "${USE_METADATA_FILTER:-0}" = "1" ]; then
    echo "  Metadata Filtering: ENABLED"
    echo "  Metadata File: ${METADATA_EXCEL}"
else
    echo "  Metadata Filtering: DISABLED"
fi
if [ "${GENERATE_SPLIT}" = "yes" ]; then
    echo "  Train/Test Split: ENABLED"
    echo "  Split Mode: ${SPLIT_MODE}"
    echo "  Train Percentage: ${TRAIN_PCT}"
    echo "  Split Output: ${SPLIT_OUTPUT}"
else
    echo "  Train/Test Split: DISABLED"
fi
echo ""
echo "Pipeline steps:"
echo "  0. Generate Train/Test Split: ${GENERATE_SPLIT}"
echo "  1. Parcellation: ${RUN_PARCELLATION}"
echo "  2. Build AA Connectomes: ${RUN_BUILD_AA_CONNECTOMES}"
echo "  3. Hyperalignment: ${RUN_HYPERALIGNMENT}"
echo "  4. Build CHA Connectomes: ${RUN_CHA_CONNECTOMES}"
echo "  5. Compute Similarity Matrices: ${RUN_SIMILARITY_MATRICES}"
echo "  6. Compute IDM Reliability: ${RUN_IDM_RELIABILITY}"
echo ""

# Export environment variables for Python scripts
export N_JOBS
export POOL_NUM
export BASE_OUTDIR
export DTSERIES_ROOT
export PTSERIES_ROOT
export CONNECTOME_MODE
export USE_METADATA_FILTER
export METADATA_EXCEL
export PYTHONPATH="${HYPERALIGNMENT_DIR}:${PYTHONPATH:-}"

# ============================================================================
# STEP 0: GENERATE TRAIN/TEST SPLIT (OPTIONAL)
# ============================================================================

if [ "${GENERATE_SPLIT}" = "yes" ]; then
    echo "================================================"
    echo "STEP 0: GENERATE TRAIN/TEST SPLIT"
    echo "================================================"
    echo ""
    echo "Generating train/test subject split..."
    echo "Mode: ${SPLIT_MODE}"
    echo "Train percentage: ${TRAIN_PCT}"
    echo "Output: ${SPLIT_OUTPUT}"
    echo ""

    cd "${HYPERALIGNMENT_DIR}"
    python3 split_subjects.py \
        --mode ${SPLIT_MODE} \
        --train-pct ${TRAIN_PCT} \
        --output ${SPLIT_OUTPUT} \
        2>&1 | tee "${SCRIPT_DIR}/logs/train_test_split.log"

    echo ""
    echo "✓ Train/test split generated"
    echo ""
else
    echo "Skipping train/test split generation (GENERATE_SPLIT=no)"
    echo ""
fi

# ============================================================================
# STEP 1: PARCELLATION
# ============================================================================

if [ "${RUN_PARCELLATION}" = "yes" ]; then
    echo "================================================"
    echo "STEP 1: PARCELLATION"
    echo "================================================"
    echo ""
    echo "Converting dtseries to parcellated ptseries..."
    echo "This may take several hours depending on the number of subjects."
    echo ""

    # Run parcellation script
    cd "${HYPERALIGNMENT_DIR}"
    bash apply_parcellation.sh 2>&1 | tee "${SCRIPT_DIR}/logs/parcellation.log"

    echo ""
    echo "✓ Parcellation complete"
    echo ""
else
    echo "Skipping parcellation (RUN_PARCELLATION=no)"
    echo ""
fi

# ============================================================================
# STEP 2: BUILD AA CONNECTOMES
# ============================================================================

if [ "${RUN_BUILD_AA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 2: BUILD AA CONNECTOMES"
    echo "================================================"
    echo ""
    echo "Building anatomical connectomes from parcellated data..."
    echo "Mode: ${AA_CONNECTOME_MODE}"
    echo ""

    cd "${HYPERALIGNMENT_DIR}"
    python3 build_aa_connectomes.py --mode ${AA_CONNECTOME_MODE} \
        2>&1 | tee "${SCRIPT_DIR}/logs/build_aa_connectomes.log"

    echo ""
    echo "✓ AA connectomes built"
    echo ""
else
    echo "Skipping AA connectome building (RUN_BUILD_AA_CONNECTOMES=no)"
    echo ""
fi

# ============================================================================
# STEP 3: HYPERALIGNMENT
# ============================================================================

if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo "================================================"
    echo "STEP 3: HYPERALIGNMENT"
    echo "================================================"
    echo ""
    echo "Running hyperalignment for all 360 parcels..."
    echo "Mode: ${CONNECTOME_MODE}"
    echo "This is the most time-consuming step."
    echo ""

    # Determine hyperalignment mode from CONNECTOME_MODE
    if [ "${CONNECTOME_MODE}" = "split" ] || [ "${CONNECTOME_MODE}" = "both" ]; then
        HYPERALIGNMENT_MODE="split"
    else
        HYPERALIGNMENT_MODE="full"
    fi

    cd "${HYPERALIGNMENT_DIR}"
    for parcel in {1..360}; do
        echo "Processing parcel ${parcel}/360..."

        python3 run_hyperalignment.py ${parcel} ${HYPERALIGNMENT_MODE} \
            2>&1 | tee "${SCRIPT_DIR}/logs/hyperalignment_parcel_${parcel}.log"
    done

    echo ""
    echo "✓ Hyperalignment complete for all parcels"
    echo ""
else
    echo "Skipping hyperalignment (RUN_HYPERALIGNMENT=no)"
    echo ""
fi

# ============================================================================
# STEP 4: BUILD CHA CONNECTOMES
# ============================================================================

if [ "${RUN_CHA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 4: BUILD CHA CONNECTOMES"
    echo "================================================"
    echo ""
    echo "Building connectomes from hyperaligned data..."
    echo "Mode: ${CONNECTOME_MODE}"
    echo ""

    cd "${HYPERALIGNMENT_DIR}"
    python3 build_CHA_connectomes.py --mode ${CONNECTOME_MODE} \
        2>&1 | tee "${SCRIPT_DIR}/logs/build_cha_connectomes.log"

    echo ""
    echo "✓ CHA connectomes built"
    echo ""
else
    echo "Skipping CHA connectome building (RUN_CHA_CONNECTOMES=no)"
    echo ""
fi

# ============================================================================
# STEP 5: COMPUTE SIMILARITY MATRICES
# ============================================================================

if [ "${RUN_SIMILARITY_MATRICES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 5: COMPUTE SIMILARITY MATRICES"
    echo "================================================"
    echo ""
    echo "Computing inter-subject similarity matrices..."
    echo "This computes ISC and covariance matrices for all 360 parcels."
    echo ""

    cd "${HYPERALIGNMENT_DIR}"
    python3 connectome_similarity_matrices.py 1 batch \
        2>&1 | tee "${SCRIPT_DIR}/logs/similarity_matrices.log"

    echo ""
    echo "✓ Similarity matrices computed"
    echo ""
else
    echo "Skipping similarity matrix computation (RUN_SIMILARITY_MATRICES=no)"
    echo ""
fi

# ============================================================================
# STEP 6: COMPUTE IDM RELIABILITY
# ============================================================================

if [ "${RUN_IDM_RELIABILITY}" = "yes" ]; then
    echo "================================================"
    echo "STEP 6: COMPUTE IDM RELIABILITY"
    echo "================================================"
    echo ""
    echo "Computing split-half reliability of IDMs..."
    echo ""

    cd "${HYPERALIGNMENT_DIR}"
    python3 idm_reliability.py \
        2>&1 | tee "${SCRIPT_DIR}/logs/idm_reliability.log"

    echo ""
    echo "✓ IDM reliability computed"
    echo ""
else
    echo "Skipping IDM reliability computation (RUN_IDM_RELIABILITY=no)"
    echo ""
fi

# ============================================================================
# SUMMARY
# ============================================================================

echo "================================================"
echo "PIPELINE COMPLETE"
echo "================================================"
echo ""
echo "All requested steps completed successfully!"
echo ""
echo "Results can be found in:"
echo "  ${PTSERIES_ROOT}              (parcellated data)"
echo "  ${BASE_OUTDIR}/                                        (AA connectomes)"
echo "  ${BASE_OUTDIR}/hyperalignment_output/                  (hyperaligned data & CHA connectomes)"
echo "  ${BASE_OUTDIR}/similarity_matrices/                    (ISC & covariance matrices)"
echo "  ${BASE_OUTDIR}/reliability_results/                    (IDM reliability results)"
echo ""
echo "Logs saved to: ${SCRIPT_DIR}/logs/"
echo ""
