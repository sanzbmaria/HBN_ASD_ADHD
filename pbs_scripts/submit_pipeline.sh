#!/bin/bash
# Master script to submit the entire hyperalignment pipeline to PBS

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

# Check required environment variable
if [ -z "${DATA_ROOT}" ]; then
    echo "ERROR: DATA_ROOT environment variable not set"
    echo "Please set it to your data directory:"
    echo "  export DATA_ROOT=/path/to/your/data"
    exit 1
fi

echo "================================================"
echo "Hyperalignment Pipeline Submission"
echo "================================================"
echo "Data root: ${DATA_ROOT}"
echo "Working directory: $(pwd)"
echo "================================================"
echo ""

# Create logs directory
mkdir -p logs

# ============================================================================
# STEP 1: PARCELLATION (Optional - run if not already done)
# ============================================================================

read -p "Do you need to run parcellation? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Submitting parcellation job..."
    PARCELLATION_JOB=$(qsub pbs_parcellation.sh)
    echo "Parcellation job submitted: ${PARCELLATION_JOB}"
    DEPENDENCY="-W depend=afterok:${PARCELLATION_JOB}"
else
    echo "Skipping parcellation step"
    DEPENDENCY=""
fi

echo ""

# ============================================================================
# STEP 2: HYPERALIGNMENT ARRAY JOB
# ============================================================================

read -p "Submit hyperalignment array job for all 360 parcels? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Run which mode? (full/split/both) [both]: " MODE
    MODE=${MODE:-both}

    read -p "Run all parcels (1-360) or specify range? (all/range) [all]: " RANGE_CHOICE
    if [[ $RANGE_CHOICE == "range" ]]; then
        read -p "Enter start parcel (1-360): " START_PARCEL
        read -p "Enter end parcel (1-360): " END_PARCEL
        ARRAY_RANGE="-J ${START_PARCEL}-${END_PARCEL}"
    else
        ARRAY_RANGE=""
    fi

    echo "Submitting hyperalignment array job..."
    if [ -n "${DEPENDENCY}" ]; then
        HYPERALIGN_JOB=$(qsub ${DEPENDENCY} ${ARRAY_RANGE} -v MODE=${MODE} pbs_hyperalignment_array.sh)
    else
        HYPERALIGN_JOB=$(qsub ${ARRAY_RANGE} -v MODE=${MODE} pbs_hyperalignment_array.sh)
    fi
    echo "Hyperalignment array job submitted: ${HYPERALIGN_JOB}"
    DEPENDENCY="-W depend=afterokarray:${HYPERALIGN_JOB}"
else
    echo "Skipping hyperalignment step"
fi

echo ""

# ============================================================================
# STEP 3: BUILD CONNECTOMES (Optional)
# ============================================================================

read -p "Submit connectome building job? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Which script? (aa/cha) [aa]: " CONNECTOME_TYPE
    CONNECTOME_TYPE=${CONNECTOME_TYPE:-aa}

    if [[ $CONNECTOME_TYPE == "cha" ]]; then
        SCRIPT="build_CHA_connectomes.py"
    else
        SCRIPT="build_aa_connectomes.py"
    fi

    echo "Submitting connectome building job..."
    if [ -n "${DEPENDENCY}" ]; then
        CONNECTOME_JOB=$(qsub ${DEPENDENCY} -v SCRIPT=${SCRIPT} pbs_build_connectomes.sh)
    else
        CONNECTOME_JOB=$(qsub -v SCRIPT=${SCRIPT} pbs_build_connectomes.sh)
    fi
    echo "Connectome job submitted: ${CONNECTOME_JOB}"
else
    echo "Skipping connectome building step"
fi

echo ""
echo "================================================"
echo "Pipeline submission complete!"
echo "================================================"
echo ""
echo "Monitor jobs with:"
echo "  qstat -u \$USER"
echo ""
echo "View logs in:"
echo "  logs/"
echo "================================================"
