#!/bin/bash
#PBS -N hyperalign
#PBS -l select=1:ncpus=24:mem=128gb
#PBS -l walltime=24:00:00
#PBS -j oe
#PBS -o logs/hyperalignment_parcel_${PARCEL}_${PBS_JOBID}.log

# ============================================================================
# PBS Job Script: Run Hyperalignment for a Single Parcel
# ============================================================================
# This script runs hyperalignment for a single parcel using Python 2
#
# Usage:
#   qsub -v PARCEL=1 pbs_hyperalignment_single.sh
#   qsub -v PARCEL=180 pbs_hyperalignment_single.sh
# ============================================================================

set -e

# Load Singularity module (adjust for your cluster)
module load singularity || module load apptainer || true

# ============================================================================
# CONFIGURATION - EDIT THESE PATHS FOR YOUR CLUSTER
# ============================================================================

# Path to Singularity image
SINGULARITY_IMAGE="${PBS_O_WORKDIR}/hyperalignment.sif"

# Data directories on your cluster
DATA_ROOT="/path/to/your/data"  # EDIT THIS

# Parcel to process (passed via -v PARCEL=N or default to 1)
PARCEL=${PARCEL:-1}

# Mode: 'full', 'split', or 'both'
MODE=${MODE:-both}

# Number of parallel jobs (match ncpus in PBS header)
export N_JOBS=24
export POOL_NUM=24

# ============================================================================
# VALIDATION
# ============================================================================

if [ ${PARCEL} -lt 1 ] || [ ${PARCEL} -gt 360 ]; then
    echo "ERROR: PARCEL must be between 1 and 360 (got: ${PARCEL})"
    exit 1
fi

# ============================================================================
# EXECUTION
# ============================================================================

cd ${PBS_O_WORKDIR}

echo "================================================"
echo "PBS Job: Hyperalignment"
echo "================================================"
echo "Job ID: ${PBS_JOBID}"
echo "Node: $(hostname)"
echo "Start time: $(date)"
echo "Working directory: ${PBS_O_WORKDIR}"
echo "Singularity image: ${SINGULARITY_IMAGE}"
echo "Data root: ${DATA_ROOT}"
echo "Parcel: ${PARCEL}"
echo "Mode: ${MODE}"
echo "N_JOBS: ${N_JOBS}"
echo "================================================"
echo ""

# Check if Singularity image exists
if [ ! -f "${SINGULARITY_IMAGE}" ]; then
    echo "ERROR: Singularity image not found: ${SINGULARITY_IMAGE}"
    exit 1
fi

# Create log directory
mkdir -p logs

# Run hyperalignment using Singularity with Python 2
echo "Starting hyperalignment for parcel ${PARCEL}..."
echo ""

singularity exec \
    --bind ${DATA_ROOT}:/data \
    --bind ${PBS_O_WORKDIR}:/workspace \
    --pwd /app/hyperalignment_scripts \
    ${SINGULARITY_IMAGE} \
    python2 run_hyperalignment.py ${PARCEL} ${MODE}

echo ""
echo "================================================"
echo "Hyperalignment complete for parcel ${PARCEL}!"
echo "End time: $(date)"
echo "================================================"
