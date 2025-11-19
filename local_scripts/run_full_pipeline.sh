#!/bin/bash
# Local execution: Run the complete hyperalignment pipeline (biobank/DNAnexus friendly)

set -euo pipefail

# -------------------------------------------------------------------------
# Configuration (can be overridden via environment)
# -------------------------------------------------------------------------
IMAGE_NAME="${IMAGE_NAME:-hyperalignment:latest}"

# Required: host path containing dtseries files (read-only)
DATA_ROOT="${DATA_ROOT:-}"   # e.g. /mnt/project/CIFTI_1

# Writable output locations on host
PARCELLATION_OUTPUT_ROOT="${PARCELLATION_OUTPUT_ROOT:-/home/dnanexus/hyperalignment_output}"
CONNECTOMES_OUTPUT_ROOT="${CONNECTOMES_OUTPUT_ROOT:-/home/dnanexus/connectomes}"

# Control flags
RUN_PARCELLATION="${RUN_PARCELLATION:-yes}"
RUN_AA_CONNECTOMES="${RUN_AA_CONNECTOMES:-yes}"
RUN_HYPERALIGNMENT="${RUN_HYPERALIGNMENT:-yes}"
RUN_CHA_CONNECTOMES="${RUN_CHA_CONNECTOMES:-yes}"

# Resource configuration
N_JOBS_PARCELLATION="${N_JOBS_PARCELLATION:-8}"
N_JOBS_HYPERALIGN="${N_JOBS_HYPERALIGN:-4}"
N_JOBS_CONNECTOMES="${N_JOBS_CONNECTOMES:-8}"
MAX_PARALLEL="${MAX_PARALLEL:-4}"
START_PARCEL="${START_PARCEL:-1}"
END_PARCEL="${END_PARCEL:-360}"
MODE="${MODE:-both}"

# -------------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------------
if [ -z "${DATA_ROOT}" ]; then
    echo "ERROR: DATA_ROOT is not set. Example:"
    echo "  export DATA_ROOT=/mnt/project/CIFTI_1"
    exit 1
fi

if [ ! -d "${DATA_ROOT}" ]; then
    echo "ERROR: DATA_ROOT not found: ${DATA_ROOT}"
    exit 1
fi

# Ensure outputs exist
mkdir -p "${PARCELLATION_OUTPUT_ROOT}"
mkdir -p "${CONNECTOMES_OUTPUT_ROOT}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "Hyperalignment Full Pipeline - Local Execution"
echo "================================================"
echo "Start time: $(date)"
echo "DATA_ROOT (host): ${DATA_ROOT}"
echo "Parcellation output (host): ${PARCELLATION_OUTPUT_ROOT}"
echo "Connectomes output (host): ${CONNECTOMES_OUTPUT_ROOT}"
echo "Docker image: ${IMAGE_NAME}"
echo ""
echo "Pipeline steps:"
echo "  Parcellation: ${RUN_PARCELLATION}"
echo "  AA Connectomes: ${RUN_AA_CONNECTOMES}"
echo "  Hyperalignment: ${RUN_HYPERALIGNMENT} (parcels ${START_PARCEL}-${END_PARCEL}, mode: ${MODE})"
echo "  CHA Connectomes: ${RUN_CHA_CONNECTOMES}"
echo ""
echo "Resources:"
echo "  Parcellation jobs: ${N_JOBS_PARCELLATION}"
echo "  Hyperalignment jobs per container: ${N_JOBS_HYPERALIGN}"
echo "  Max parallel containers: ${MAX_PARALLEL}"
echo "  Connectome jobs: ${N_JOBS_CONNECTOMES}"
echo "================================================"
echo ""

# -------------------------------------------------------------------------
# STEP 1: Parcellation
# -------------------------------------------------------------------------
if [ "${RUN_PARCELLATION}" = "yes" ]; then
    echo "================================================"
    echo "STEP 1: Parcellation"
    echo "================================================"
    export N_JOBS="${N_JOBS_PARCELLATION}"

    # run_parcellation.sh should mount:
    #  - ${DATA_ROOT} -> /data/inputs (read-only)
    #  - ${PARCELLATION_OUTPUT_ROOT}/glasser_ptseries -> /data/outputs (writable)
    "${SCRIPT_DIR}/run_parcellation.sh"

    P_EXIT=$?
    if [ ${P_EXIT} -ne 0 ]; then
        echo "WARNING: Parcellation returned exit code ${P_EXIT}"
        # check outputs
        COUNT=$(find "${PARCELLATION_OUTPUT_ROOT}/glasser_ptseries" -name "*.ptseries.nii" 2>/dev/null | wc -l || echo 0)
        if [ "${COUNT}" -eq 0 ]; then
            echo "ERROR: No parcellation outputs found. Aborting."
            exit ${P_EXIT}
        else
            echo "Found ${COUNT} parcellation outputs; continuing."
        fi
    fi
else
    echo "Skipping parcellation (RUN_PARCELLATION=no)"
fi

# -------------------------------------------------------------------------
# STEP 2: Build AA Connectomes
# -------------------------------------------------------------------------
if [ "${RUN_AA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 2: Build AA Connectomes"
    echo "================================================"
    export N_JOBS="${N_JOBS_CONNECTOMES}"

    # IMPORTANT: here INPUT_DIR must point to the *glasser_ptseries* folder
    export INPUT_DIR="${PARCELLATION_OUTPUT_ROOT}/glasser_ptseries"
    export OUTPUT_DIR="${CONNECTOMES_OUTPUT_ROOT}"
    export DATA_ROOT="${DATA_ROOT}"

    # Basic sanity check
    if [ ! -d "${INPUT_DIR}" ]; then
        echo "ERROR: INPUT_DIR not found: ${INPUT_DIR}"
        exit 1
    fi
    subs_count=$(find "${INPUT_DIR}" -maxdepth 1 -mindepth 1 -type d | wc -l || echo 0)
    if [ "${subs_count}" -eq 0 ]; then
        echo "ERROR: No subject folders found in ${INPUT_DIR}"
        exit 1
    fi

    "${SCRIPT_DIR}/run_build_connectomes.sh" build_aa_connectomes.py

    AA_EXIT=$?
    if [ ${AA_EXIT} -ne 0 ]; then
        echo "ERROR: AA connectomes failed with exit code ${AA_EXIT}"
        exit ${AA_EXIT}
    fi
else
    echo "Skipping AA connectomes (RUN_AA_CONNECTOMES=no)"
fi

# -------------------------------------------------------------------------
# STEP 3: Hyperalignment
# -------------------------------------------------------------------------
if [ "${RUN_HYPERALIGNMENT}" = "yes" ]; then
    echo "================================================"
    echo "STEP 3: Hyperalignment"
    echo "================================================"
    export N_JOBS="${N_JOBS_HYPERALIGN}"
    export POOL_NUM="${N_JOBS_HYPERALIGN}"
    export START_PARCEL="${START_PARCEL}"
    export END_PARCEL="${END_PARCEL}"
    export MODE="${MODE}"
    export MAX_PARALLEL="${MAX_PARALLEL}"

    "${SCRIPT_DIR}/run_hyperalignment_parallel.sh"

    H_EXIT=$?
    if [ ${H_EXIT} -ne 0 ]; then
        echo "ERROR: Hyperalignment failed with exit code ${H_EXIT}"
        exit ${H_EXIT}
    fi
else
    echo "Skipping hyperalignment (RUN_HYPERALIGNMENT=no)"
fi

# -------------------------------------------------------------------------
# STEP 4: Build CHA Connectomes
# -------------------------------------------------------------------------
if [ "${RUN_CHA_CONNECTOMES}" = "yes" ]; then
    echo "================================================"
    echo "STEP 4: Build CHA Connectomes"
    echo "================================================"
    export N_JOBS="${N_JOBS_CONNECTOMES}"

    export INPUT_DIR="${PARCELLATION_OUTPUT_ROOT}/glasser_ptseries"
    export OUTPUT_DIR="${CONNECTOMES_OUTPUT_ROOT}"

    "${SCRIPT_DIR}/run_build_connectomes.sh" build_CHA_connectomes.py

    C_EXIT=$?
    if [ ${C_EXIT} -ne 0 ]; then
        echo "ERROR: CHA connectomes failed with exit code ${C_EXIT}"
        exit ${C_EXIT}
    fi
else
    echo "Skipping CHA connectomes (RUN_CHA_CONNECTOMES=no)"
fi

# -------------------------------------------------------------------------
# SUMMARY
# -------------------------------------------------------------------------
echo ""
echo "================================================"
echo "PIPELINE COMPLETE"
echo "================================================"
echo "Parcellated data: ${PARCELLATION_OUTPUT_ROOT}/glasser_ptseries/"
echo "AA Connectomes: ${CONNECTOMES_OUTPUT_ROOT}/fine/"
echo "CHA Connectomes: ${CONNECTOMES_OUTPUT_ROOT}/fine/"
echo "Logs: $(pwd)/logs/"
echo "================================================"
