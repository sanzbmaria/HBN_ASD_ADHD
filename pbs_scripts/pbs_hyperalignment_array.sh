#!/bin/bash
#PBS -N hyperalign_array
#PBS -J 1-360
#PBS -l select=1:ncpus=24:mem=128gb
#PBS -l walltime=24:00:00
#PBS -j oe
#PBS -o logs/hyperalignment_parcel_${PBS_ARRAY_INDEX}_${PBS_JOBID}.log

# ============================================================================
# PBS Array Job Script: Run Hyperalignment for All Parcels
# ============================================================================
# This script runs hyperalignment for all 360 parcels as an array job
# Each array task processes one parcel
#
# Usage:
#   qsub pbs_hyperalignment_array.sh
#
# To run a subset:
#   qsub -J 1-50 pbs_hyperalignment_array.sh      # Run first 50 parcels
#   qsub -J 100-200 pbs_hyperalignment_array.sh   # Run parcels 100-200
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

# Get parcel number from PBS array index
PARCEL=${PBS_ARRAY_INDEX}

# Mode: 'full', 'split', or 'both'
MODE=${MODE:-both}

# Number of parallel jobs (match ncpus in PBS header)
export N_JOBS=24
export POOL_NUM=24

# ============================================================================
# EXECUTION
# ============================================================================

cd ${PBS_O_WORKDIR}

echo "================================================"
echo "PBS Array Job: Hyperalignment"
echo "================================================"
echo "Job ID: ${PBS_JOBID}"
echo "Array Index: ${PBS_ARRAY_INDEX}"
echo "Parcel: ${PARCEL}"
echo "Node: $(hostname)"
echo "Start time: $(date)"
echo "Working directory: ${PBS_O_WORKDIR}"
echo "Singularity image: ${SINGULARITY_IMAGE}"
echo "Data root: ${DATA_ROOT}"
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
    python run_hyperalignment.py ${PARCEL} ${MODE}

EXIT_CODE=$?

echo ""
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "================================================"
    echo "SUCCESS: Hyperalignment complete for parcel ${PARCEL}!"
    echo "End time: $(date)"
    echo "================================================"
else
    echo "================================================"
    echo "ERROR: Hyperalignment failed for parcel ${PARCEL}"
    echo "Exit code: ${EXIT_CODE}"
    echo "End time: $(date)"
    echo "================================================"
    exit ${EXIT_CODE}
fi
