#!/bin/bash
# Test mode: Run the pipeline on a subset of subjects
# This is perfect for testing the Docker setup before full runs

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# Data directory (REQUIRED)
DATA_ROOT="${DATA_ROOT:-}"

# Test subjects (can be overridden)
# Format: space-separated list of subject IDs
TEST_SUBJECTS="${TEST_SUBJECTS:-}"

# Or specify number of subjects to auto-select
N_TEST_SUBJECTS="${N_TEST_SUBJECTS:-5}"

# Test parcels (run only a few parcels for faster testing)
TEST_PARCELS="${TEST_PARCELS:-1 2 3}"  # Space-separated list

# Pipeline steps to run
RUN_PARCELLATION="${RUN_PARCELLATION:-yes}"
RUN_BUILD_AA_CONNECTOMES="${RUN_BUILD_AA_CONNECTOMES:-yes}"
RUN_HYPERALIGNMENT="${RUN_HYPERALIGNMENT:-yes}"
RUN_CHA_CONNECTOMES="${RUN_CHA_CONNECTOMES:-yes}"

# Mode for hyperalignment
MODE="${MODE:-full}"

# Resource configuration
N_JOBS="${N_JOBS:-4}"
POOL_NUM="${POOL_NUM:-4}"

# ============================================================================
# VALIDATION
# ============================================================================

echo "================================================"
echo "HYPERALIGNMENT PIPELINE - TEST MODE"
echo "================================================"
echo ""

if [ -z "${DATA_ROOT}" ]; then
    echo "ERROR: DATA_ROOT environment variable not set"
    echo ""
    echo "Usage:"
    echo "  export DATA_ROOT=/path/to/your/data"
    echo "  ./test_pipeline.sh"
    echo ""
    echo "Or specify test subjects:"
    echo "  export DATA_ROOT=/path/to/your/data"
    echo "  export TEST_SUBJECTS=\"sub-NDARAA123 sub-NDARAA456 sub-NDARAA789\""
    echo "  ./test_pipeline.sh"
    echo ""
    echo "Or specify number of subjects to auto-select:"
    echo "  export DATA_ROOT=/path/to/your/data"
    echo "  export N_TEST_SUBJECTS=10"
    echo "  ./test_pipeline.sh"
    exit 1
fi

if [ ! -d "${DATA_ROOT}" ]; then
    echo "ERROR: Data directory not found: ${DATA_ROOT}"
    exit 1
fi

# Check if Docker image exists
if ! docker image inspect ${IMAGE_NAME} &> /dev/null; then
    echo "ERROR: Docker image '${IMAGE_NAME}' not found"
    echo ""
    echo "Please build it first:"
    echo "  ./docker-build.sh"
    exit 1
fi

# ============================================================================
# DISCOVER AND SELECT TEST SUBJECTS
# ============================================================================

DTSERIES_DIR="${DATA_ROOT}/HBN_CIFTI"

if [ ! -d "${DTSERIES_DIR}" ]; then
    echo "ERROR: dtseries directory not found: ${DTSERIES_DIR}"
    exit 1
fi

# Discover available subjects
echo "Discovering available subjects..."
ALL_SUBJECTS=$(ls "${DTSERIES_DIR}"/*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii 2>/dev/null | \
    xargs -n 1 basename | \
    sed 's/_task-rest.*//' | \
    sort -u)

N_AVAILABLE=$(echo "${ALL_SUBJECTS}" | wc -l | tr -d ' ')

if [ ${N_AVAILABLE} -eq 0 ]; then
    echo "ERROR: No subjects found in ${DTSERIES_DIR}"
    echo "Expected files matching pattern: *_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"
    exit 1
fi

echo "Found ${N_AVAILABLE} subjects with dtseries files"
echo ""

# Select test subjects
if [ -n "${TEST_SUBJECTS}" ]; then
    # Use explicitly specified subjects
    SUBJECTS_TO_TEST="${TEST_SUBJECTS}"
    N_TEST=$(echo "${SUBJECTS_TO_TEST}" | wc -w)
    echo "Using ${N_TEST} explicitly specified test subjects:"
    for subj in ${SUBJECTS_TO_TEST}; do
        echo "  - ${subj}"
    done
else
    # Auto-select N subjects
    SUBJECTS_TO_TEST=$(echo "${ALL_SUBJECTS}" | head -n ${N_TEST_SUBJECTS} | tr '\n' ' ')
    N_TEST=$(echo "${SUBJECTS_TO_TEST}" | wc -w)
    echo "Auto-selected first ${N_TEST} subjects for testing:"
    for subj in ${SUBJECTS_TO_TEST}; do
        echo "  - ${subj}"
    done
fi

echo ""

# Validate test subjects exist
for subj in ${SUBJECTS_TO_TEST}; do
    DTSERIES_FILE="${DTSERIES_DIR}/${subj}_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"
    if [ ! -f "${DTSERIES_FILE}" ]; then
        echo "ERROR: dtseries file not found for subject: ${subj}"
        echo "Expected: ${DTSERIES_FILE}"
        exit 1
    fi
done

# ============================================================================
# TEST CONFIGURATION SUMMARY
# ============================================================================

echo "================================================"
echo "Test Configuration"
echo "================================================"
echo "Docker image: ${IMAGE_NAME}"
echo "Data root: ${DATA_ROOT}"
echo "Test subjects (${N_TEST}): ${SUBJECTS_TO_TEST}"
echo "Test parcels: ${TEST_PARCELS}"
echo ""
echo "Pipeline steps:"
echo "  1. Parcellation: ${RUN_PARCELLATION}"
echo "  2. Build AA Connectomes: ${RUN_BUILD_AA_CONNECTOMES}"
echo "  3. Hyperalignment: ${RUN_HYPERALIGNMENT} (mode: ${MODE})"
echo "  4. Build CHA Connectomes: ${RUN_CHA_CONNECTOMES}"
echo ""
echo "Resources:"
echo "  N_JOBS: ${N_JOBS}"
echo "  POOL_NUM: ${POOL_NUM}"
echo "================================================"
echo ""

read -p "Continue with test? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Test cancelled."
    exit 0
fi

# ============================================================================
# SETUP
# ============================================================================

START_TIME=$(date +%s)
mkdir -p logs

# Create a test subject list file
TEST_SUBJECT_FILE="${DATA_ROOT}/test_subjects.txt"
echo "${SUBJECTS_TO_TEST}" | tr ' ' '\n' > "${TEST_SUBJECT_FILE}"
echo ""
echo "Created test subject list: ${TEST_SUBJECT_FILE}"
echo ""

# ============================================================================
# STEP 1: PARCELLATION
# ============================================================================

if [ "${RUN_PARCELLATION}" = "yes" ]; then
    echo "================================================"
    echo "STEP 1: PARCELLATION (Test Subjects Only)"
    echo "================================================"
    echo "Started: $(date)"
    echo ""

    echo "Running parcellation on ${N_TEST} test subjects..."
    echo "Note: Parcellation will process all files but we'll only use outputs for test subjects"
    echo ""

    docker run --rm \
        -v "${DATA_ROOT}":/data \
        -e BASEDIR=/data/HBN_CIFTI \
        -e OUTDIR=/data/hyperalignment_input/glasser_ptseries \
        -e N_JOBS=${N_JOBS} \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        bash apply_parcellation.sh

    PARCELLATION_EXIT=$?
    if [ ${PARCELLATION_EXIT} -ne 0 ]; then
        echo ""
        echo "ERROR: Parcellation failed with exit code ${PARCELLATION_EXIT}"
        exit ${PARCELLATION_EXIT}
    fi

    echo ""
    echo "✓ Parcellation completed: $(date)"
    echo ""
else
    echo "Skipping parcellation step"
    echo ""
fi

# ============================================================================
# STEP 2: BUILD AA CONNECTOMES (Anatomical Connectomes)
# ============================================================================

if [ "${RUN_BUILD_AA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 2: BUILD AA CONNECTOMES"
    echo "================================================"
    echo "Started: $(date)"
    echo ""
    echo "Building anatomical connectomes from parcellated data..."
    echo "This creates the connectomes needed for hyperalignment training."
    echo "Processing ${N_TEST} test subjects only..."
    echo ""

    docker run --rm \
        -v "${DATA_ROOT}":/data \
        -e N_JOBS=${N_JOBS} \
        -e TEST_SUBJECTS_LIST="${SUBJECTS_TO_TEST}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_aa_connectomes.py \
        2>&1 | tee logs/test_build_aa_connectomes.log

    AA_EXIT=${PIPESTATUS[0]}

    if [ ${AA_EXIT} -ne 0 ]; then
        echo ""
        echo "ERROR: AA connectome building failed with exit code ${AA_EXIT}"
        echo "Check logs/test_build_aa_connectomes.log for details"
        exit ${AA_EXIT}
    fi

    echo ""
    echo "✓ AA connectome building completed: $(date)"
    echo ""
else
    echo "Skipping AA connectome building step"
    echo ""
fi

# ============================================================================
# STEP 3: HYPERALIGNMENT (Test Parcels Only)
# ============================================================================

if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo "================================================"
    echo "STEP 3: HYPERALIGNMENT (Test Parcels Only)"
    echo "================================================"
    echo "Started: $(date)"
    echo "Processing parcels: ${TEST_PARCELS}"
    echo ""

    FAILED_PARCELS=0
    COMPLETED_PARCELS=0

    for parcel in ${TEST_PARCELS}; do
        echo "----------------------------------------"
        echo "Processing parcel ${parcel}..."
        echo "----------------------------------------"

        docker run --rm \
            -v "${DATA_ROOT}":/data \
            -e N_JOBS=${N_JOBS} \
            -e POOL_NUM=${POOL_NUM} \
            -w /app/hyperalignment_scripts \
            ${IMAGE_NAME} \
            python run_hyperalignment.py ${parcel} ${MODE} \
            2>&1 | tee logs/test_hyperalignment_parcel_${parcel}.log

        EXIT_CODE=${PIPESTATUS[0]}

        if [ ${EXIT_CODE} -eq 0 ]; then
            echo "✓ Parcel ${parcel} completed successfully"
            COMPLETED_PARCELS=$((COMPLETED_PARCELS + 1))
        else
            echo "✗ Parcel ${parcel} failed with exit code ${EXIT_CODE}"
            FAILED_PARCELS=$((FAILED_PARCELS + 1))
        fi
        echo ""
    done

    echo "Hyperalignment Summary:"
    echo "  Completed: ${COMPLETED_PARCELS}"
    echo "  Failed: ${FAILED_PARCELS}"
    echo ""

    if [ ${FAILED_PARCELS} -gt 0 ]; then
        echo "ERROR: Some parcels failed. Check logs in logs/ directory"
        exit 1
    fi

    echo "✓ Hyperalignment completed: $(date)"
    echo ""
else
    echo "Skipping hyperalignment step"
    echo ""
fi

# ============================================================================
# STEP 4: BUILD CHA CONNECTOMES (Hyperaligned Connectomes)
# ============================================================================

if [ "${RUN_CHA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 4: BUILD CHA CONNECTOMES (Test Subjects Only)"
    echo "================================================"
    echo "Started: $(date)"
    echo ""
    echo "Building CHA (Commonspace Hyperaligned Anatomical) connectomes..."
    echo "This uses the hyperaligned timeseries to build final connectomes."
    echo ""

    docker run --rm \
        -v "${DATA_ROOT}":/data \
        -e N_JOBS=${N_JOBS} \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_CHA_connectomes.py \
        2>&1 | tee logs/test_build_cha_connectomes.log

    CHA_EXIT=${PIPESTATUS[0]}

    if [ ${CHA_EXIT} -ne 0 ]; then
        echo ""
        echo "ERROR: CHA connectome building failed with exit code ${CHA_EXIT}"
        echo "Check logs/test_build_cha_connectomes.log for details"
        exit ${CHA_EXIT}
    fi

    echo ""
    echo "✓ CHA connectome building completed: $(date)"
    echo ""
else
    echo "Skipping CHA connectome building step"
    echo ""
fi

# ============================================================================
# VALIDATION AND SUMMARY
# ============================================================================

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo "================================================"
echo "TEST PIPELINE COMPLETE"
echo "================================================"
echo "End time: $(date)"
echo "Total elapsed time: ${MINUTES}m ${SECONDS}s"
echo ""

# Validate outputs
echo "Validating outputs..."
echo ""

VALIDATION_PASSED=true

# Check parcellated data
if [ "${RUN_PARCELLATION}" = "yes" ]; then
    echo "Checking parcellated data..."
    PTSERIES_DIR="${DATA_ROOT}/hyperalignment_input/glasser_ptseries"
    for subj in ${SUBJECTS_TO_TEST}; do
        PTSERIES_FILE=$(find "${PTSERIES_DIR}/${subj}" -name "${subj}_run-*_glasser.ptseries.nii" 2>/dev/null | head -1)
        if [ -f "${PTSERIES_FILE}" ]; then
            echo "  ✓ ${subj}: ptseries found"
        else
            echo "  ✗ ${subj}: ptseries NOT found"
            VALIDATION_PASSED=false
        fi
    done
    echo ""
fi

# Check hyperalignment outputs
if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo "Checking hyperalignment outputs..."
    for parcel in ${TEST_PARCELS}; do
        MAPPER_DIR="${DATA_ROOT}/connectomes/hyperalignment_output/mappers/parcel_$(printf %03d ${parcel})"
        ALIGNED_DIR="${DATA_ROOT}/connectomes/hyperalignment_output/aligned_timeseries/parcel_$(printf %03d ${parcel})"

        if [ -d "${MAPPER_DIR}" ] && [ -d "${ALIGNED_DIR}" ]; then
            N_MAPPERS=$(ls "${MAPPER_DIR}"/*.npy 2>/dev/null | wc -l)
            N_ALIGNED=$(ls "${ALIGNED_DIR}"/*.npy 2>/dev/null | wc -l)
            echo "  ✓ Parcel ${parcel}: ${N_MAPPERS} mappers, ${N_ALIGNED} aligned files"
        else
            echo "  ✗ Parcel ${parcel}: outputs NOT found"
            VALIDATION_PASSED=false
        fi
    done
    echo ""
fi

# Check connectomes
if [ "${RUN_CONNECTOMES}" = "yes" ]; then
    echo "Checking connectomes..."
    for parcel in ${TEST_PARCELS}; do
        CONNECTOME_DIR="${DATA_ROOT}/connectomes/fine/parcel_$(printf %03d ${parcel})"
        if [ -d "${CONNECTOME_DIR}" ]; then
            N_CONNECTOMES=$(ls "${CONNECTOME_DIR}"/*.npy 2>/dev/null | wc -l)
            echo "  ✓ Parcel ${parcel}: ${N_CONNECTOMES} connectome files"
        else
            echo "  ✗ Parcel ${parcel}: connectomes NOT found"
            VALIDATION_PASSED=false
        fi
    done
    echo ""
fi

# Final summary
echo "================================================"
if [ "${VALIDATION_PASSED}" = "true" ]; then
    echo "✓ ALL VALIDATION CHECKS PASSED"
    echo "================================================"
    echo ""
    echo "Your Docker setup is working correctly!"
    echo ""
    echo "Output locations:"
    echo "  Parcellated data: ${DATA_ROOT}/hyperalignment_input/glasser_ptseries/"
    echo "  Hyperalignment outputs: ${DATA_ROOT}/connectomes/hyperalignment_output/"
    echo "  Connectomes: ${DATA_ROOT}/connectomes/fine/"
    echo ""
    echo "Logs: $(pwd)/logs/"
    echo ""
    echo "Next steps:"
    echo "  - For local full run: ./local_scripts/run_full_pipeline.sh"
    echo "  - For PBS cluster: See DOCKER_PBS_README.md"
    echo "================================================"
    exit 0
else
    echo "✗ SOME VALIDATION CHECKS FAILED"
    echo "================================================"
    echo ""
    echo "Please check the output above and logs in logs/ directory"
    echo "================================================"
    exit 1
fi
