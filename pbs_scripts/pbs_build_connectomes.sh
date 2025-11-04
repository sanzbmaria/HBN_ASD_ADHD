#!/bin/bash
#PBS -N build_connectomes
#PBS -l select=1:ncpus=24:mem=128gb
#PBS -l walltime=48:00:00
#PBS -j oe
#PBS -o logs/build_connectomes_${PBS_JOBID}.log

# ============================================================================
# PBS Job Script: Build Connectomes
# ============================================================================
# This script builds connectomes from aligned or non-aligned timeseries
#
# Usage:
#   qsub -v SCRIPT=build_aa_connectomes.py pbs_build_connectomes.sh
#   qsub -v SCRIPT=build_CHA_connectomes.py pbs_build_connectomes.sh
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

# Script to run (passed via -v SCRIPT=filename or default)
SCRIPT=${SCRIPT:-build_aa_connectomes.py}

# Number of parallel jobs (match ncpus in PBS header)
export N_JOBS=24

# ============================================================================
# EXECUTION
# ============================================================================

cd ${PBS_O_WORKDIR}

echo "================================================"
echo "PBS Job: Build Connectomes"
echo "================================================"
echo "Job ID: ${PBS_JOBID}"
echo "Node: $(hostname)"
echo "Start time: $(date)"
echo "Working directory: ${PBS_O_WORKDIR}"
echo "Singularity image: ${SINGULARITY_IMAGE}"
echo "Data root: ${DATA_ROOT}"
echo "Script: ${SCRIPT}"
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

# Run connectome building using Singularity with Python 3
echo "Starting connectome building with ${SCRIPT}..."
echo ""

singularity exec \
    --bind ${DATA_ROOT}:/data \
    --bind ${PBS_O_WORKDIR}:/workspace \
    --pwd /app/hyperalignment_scripts \
    ${SINGULARITY_IMAGE} \
    python3 ${SCRIPT}

EXIT_CODE=$?

echo ""
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "================================================"
    echo "SUCCESS: Connectome building complete!"
    echo "End time: $(date)"
    echo "================================================"
else
    echo "================================================"
    echo "ERROR: Connectome building failed"
    echo "Exit code: ${EXIT_CODE}"
    echo "End time: $(date)"
    echo "================================================"
    exit ${EXIT_CODE}
fi
