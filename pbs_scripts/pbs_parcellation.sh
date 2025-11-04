#!/bin/bash
#PBS -N parcellation
#PBS -l select=1:ncpus=24:mem=64gb
#PBS -l walltime=12:00:00
#PBS -j oe
#PBS -o logs/parcellation_${PBS_JOBID}.log

# ============================================================================
# PBS Job Script: Apply Parcellation to CIFTI dtseries files
# ============================================================================
# This script runs wb_command to parcellate CIFTI dtseries files using
# the Glasser atlas
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
DTSERIES_DIR="${DATA_ROOT}/HBN_CIFTI"
OUTPUT_DIR="${DATA_ROOT}/hyperalignment_input/glasser_ptseries"

# Number of parallel jobs (match ncpus in PBS header)
export N_JOBS=24

# ============================================================================
# EXECUTION
# ============================================================================

cd ${PBS_O_WORKDIR}

echo "================================================"
echo "PBS Job: Parcellation"
echo "================================================"
echo "Job ID: ${PBS_JOBID}"
echo "Node: $(hostname)"
echo "Start time: $(date)"
echo "Working directory: ${PBS_O_WORKDIR}"
echo "Singularity image: ${SINGULARITY_IMAGE}"
echo "Input data: ${DTSERIES_DIR}"
echo "Output directory: ${OUTPUT_DIR}"
echo "Parallel jobs: ${N_JOBS}"
echo "================================================"
echo ""

# Check if Singularity image exists
if [ ! -f "${SINGULARITY_IMAGE}" ]; then
    echo "ERROR: Singularity image not found: ${SINGULARITY_IMAGE}"
    exit 1
fi

# Check if input directory exists
if [ ! -d "${DTSERIES_DIR}" ]; then
    echo "ERROR: Input directory not found: ${DTSERIES_DIR}"
    exit 1
fi

# Create output directory if needed
mkdir -p "${OUTPUT_DIR}"
mkdir -p logs

# Run parcellation using Singularity
echo "Starting parcellation..."
echo ""

singularity exec \
    --bind ${DATA_ROOT}:/data \
    --bind ${PBS_O_WORKDIR}:/workspace \
    --pwd /app/hyperalignment_scripts \
    ${SINGULARITY_IMAGE} \
    bash -c "
        export BASEDIR=/data/HBN_CIFTI
        export OUTDIR=/data/hyperalignment_input/glasser_ptseries
        export N_JOBS=${N_JOBS}
        ./apply_parcellation.sh
    "

echo ""
echo "================================================"
echo "Parcellation complete!"
echo "End time: $(date)"
echo "Output directory: ${OUTPUT_DIR}"
echo "================================================"
