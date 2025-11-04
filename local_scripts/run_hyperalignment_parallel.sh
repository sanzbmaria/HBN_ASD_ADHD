#!/bin/bash
# Local execution: Run hyperalignment for multiple parcels in parallel
# Works on Mac and Linux with Docker

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

IMAGE_NAME="hyperalignment:latest"

# Data directory
DATA_ROOT="${DATA_ROOT:-$(pwd)/data}"

# Parcel range (default: all 360 parcels)
START_PARCEL="${START_PARCEL:-1}"
END_PARCEL="${END_PARCEL:-360}"

# Mode: 'full', 'split', or 'both'
MODE="${MODE:-both}"

# Number of concurrent Docker containers to run
# Be careful not to exceed your system's memory!
# Each hyperalignment job can use 8-16GB RAM
MAX_PARALLEL="${MAX_PARALLEL:-4}"  # Run 4 parcels at a time by default

# Number of parallel jobs within each container
N_JOBS="${N_JOBS:-4}"  # Use fewer cores per container when running multiple containers
POOL_NUM="${POOL_NUM:-4}"

# ============================================================================
# VALIDATION
# ============================================================================

echo "================================================"
echo "Local Parallel Execution: Hyperalignment"
echo "================================================"
echo "Docker image: ${IMAGE_NAME}"
echo "Data root: ${DATA_ROOT}"
echo "Parcel range: ${START_PARCEL} to ${END_PARCEL}"
echo "Mode: ${MODE}"
echo "Max parallel containers: ${MAX_PARALLEL}"
echo "N_JOBS per container: ${N_JOBS}"
echo "================================================"
echo ""

if [ ${START_PARCEL} -lt 1 ] || [ ${START_PARCEL} -gt 360 ]; then
    echo "ERROR: START_PARCEL must be between 1 and 360"
    exit 1
fi

if [ ${END_PARCEL} -lt 1 ] || [ ${END_PARCEL} -gt 360 ]; then
    echo "ERROR: END_PARCEL must be between 1 and 360"
    exit 1
fi

if [ ${END_PARCEL} -lt ${START_PARCEL} ]; then
    echo "ERROR: END_PARCEL must be >= START_PARCEL"
    exit 1
fi

# Check if Docker image exists
if ! docker image inspect ${IMAGE_NAME} &> /dev/null; then
    echo "ERROR: Docker image '${IMAGE_NAME}' not found"
    echo "Please build it first: ./docker-build.sh"
    exit 1
fi

# Check if data directory exists
if [ ! -d "${DATA_ROOT}" ]; then
    echo "ERROR: Data directory not found: ${DATA_ROOT}"
    exit 1
fi

# ============================================================================
# SETUP
# ============================================================================

# Create logs directory
mkdir -p logs

# Track background jobs
pids=()
failed=0
completed=0
total=$((END_PARCEL - START_PARCEL + 1))

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up background jobs..."
    for pid in "${pids[@]:-}"; do
        kill $pid 2>/dev/null || true
    done
}

trap cleanup EXIT

# ============================================================================
# EXECUTION
# ============================================================================

echo "Starting hyperalignment for parcels ${START_PARCEL} to ${END_PARCEL}..."
echo "Running ${MAX_PARALLEL} parcels at a time"
echo ""

for parcel in $(seq ${START_PARCEL} ${END_PARCEL}); do
    # Wait if we've reached max parallel jobs
    while [ ${#pids[@]} -ge ${MAX_PARALLEL} ]; do
        for i in "${!pids[@]}"; do
            pid=${pids[i]}
            if ! kill -0 $pid 2>/dev/null; then
                wait $pid
                exit_code=$?
                if [ $exit_code -eq 0 ]; then
                    completed=$((completed + 1))
                else
                    failed=$((failed + 1))
                fi
                unset 'pids[i]'
            fi
        done
        pids=("${pids[@]:-}")
        sleep 1
    done

    # Start job for this parcel
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting parcel ${parcel} (${completed}/${total} complete, ${failed} failed)"

    (
        docker run --rm \
            -v "${DATA_ROOT}":/data \
            -e N_JOBS=${N_JOBS} \
            -e POOL_NUM=${POOL_NUM} \
            -w /app/hyperalignment_scripts \
            ${IMAGE_NAME} \
            python run_hyperalignment.py ${parcel} ${MODE} \
            > logs/hyperalignment_parcel_${parcel}.log 2>&1
    ) &

    pids+=($!)

    # Small delay to avoid overwhelming the system
    sleep 2
done

# Wait for remaining jobs
echo ""
echo "Waiting for remaining jobs to complete..."
for pid in "${pids[@]:-}"; do
    wait $pid
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        completed=$((completed + 1))
    else
        failed=$((failed + 1))
    fi
done

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
echo "================================================"
echo "Hyperalignment Parallel Execution Complete"
echo "================================================"
echo "Total parcels: ${total}"
echo "Completed: ${completed}"
echo "Failed: ${failed}"
echo "================================================"

if [ ${failed} -gt 0 ]; then
    echo ""
    echo "Check logs/ directory for error details"
    exit 1
fi
