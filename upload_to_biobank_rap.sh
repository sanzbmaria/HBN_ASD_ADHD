#!/bin/bash
# Upload pipeline outputs to UK Biobank RAP platform
# Uses dx (DNAnexus) CLI to upload results

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default output paths (override with environment variables)
OUTPUTS_ROOT="${OUTPUTS_ROOT:-/home/dnanexus/HBN_ASD_ADHD/data}"
RAP_PROJECT_PATH="${RAP_PROJECT_PATH:-/pipeline_outputs}"

# What to upload (set to "no" to skip)
UPLOAD_CONNECTOMES="${UPLOAD_CONNECTOMES:-yes}"
UPLOAD_SIMILARITY_MATRICES="${UPLOAD_SIMILARITY_MATRICES:-yes}"
UPLOAD_RELIABILITY_RESULTS="${UPLOAD_RELIABILITY_RESULTS:-yes}"
UPLOAD_LOGS="${UPLOAD_LOGS:-yes}"
UPLOAD_PARCELLATION="${UPLOAD_PARCELLATION:-no}"  # Usually large, skip by default

echo "================================================"
echo "UK BIOBANK RAP UPLOAD SCRIPT"
echo "================================================"
echo ""
echo "This script uploads pipeline outputs to UK Biobank RAP platform"
echo ""

# Check if dx command is available
if ! command -v dx &> /dev/null; then
    echo "ERROR: dx command not found!"
    echo ""
    echo "The DNAnexus SDK (dx-toolkit) is required to upload to UK Biobank RAP."
    echo "Please install it or run this script on a UK Biobank RAP node."
    echo ""
    exit 1
fi

# Check if outputs directory exists
if [ ! -d "${OUTPUTS_ROOT}" ]; then
    echo "ERROR: Outputs directory not found: ${OUTPUTS_ROOT}"
    echo ""
    echo "Set OUTPUTS_ROOT environment variable to point to your pipeline outputs:"
    echo "  export OUTPUTS_ROOT=/path/to/outputs"
    echo "  ./upload_to_biobank_rap.sh"
    echo ""
    exit 1
fi

echo "Configuration:"
echo "  Local outputs: ${OUTPUTS_ROOT}"
echo "  RAP destination: ${RAP_PROJECT_PATH}"
echo ""
echo "Upload settings:"
echo "  Connectomes: ${UPLOAD_CONNECTOMES}"
echo "  Similarity matrices: ${UPLOAD_SIMILARITY_MATRICES}"
echo "  Reliability results: ${UPLOAD_RELIABILITY_RESULTS}"
echo "  Logs: ${UPLOAD_LOGS}"
echo "  Parcellation data: ${UPLOAD_PARCELLATION}"
echo ""

# Create timestamp for this upload session
UPLOAD_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RAP_UPLOAD_PATH="${RAP_PROJECT_PATH}/upload_${UPLOAD_TIMESTAMP}"

echo "Creating upload directory on RAP: ${RAP_UPLOAD_PATH}"
dx mkdir -p "${RAP_UPLOAD_PATH}"
echo ""

UPLOAD_START=$(date +%s)

# ============================================================================
# UPLOAD CONNECTOMES
# ============================================================================

if [ "${UPLOAD_CONNECTOMES}" = "yes" ] && [ -d "${OUTPUTS_ROOT}/connectomes" ]; then
    echo "================================================"
    echo "Uploading connectomes..."
    echo "================================================"
    STEP_START=$(date +%s)

    # Upload AA connectomes (coarse and fine)
    if [ -d "${OUTPUTS_ROOT}/connectomes/coarse" ]; then
        echo "  Uploading AA coarse connectomes..."
        dx upload -r "${OUTPUTS_ROOT}/connectomes/coarse" --path "${RAP_UPLOAD_PATH}/connectomes/"
    fi

    if [ -d "${OUTPUTS_ROOT}/connectomes/fine" ]; then
        echo "  Uploading AA fine connectomes..."
        dx upload -r "${OUTPUTS_ROOT}/connectomes/fine" --path "${RAP_UPLOAD_PATH}/connectomes/"
    fi

    # Upload CHA connectomes (hyperalignment outputs)
    if [ -d "${OUTPUTS_ROOT}/connectomes/hyperalignment_output" ]; then
        echo "  Uploading CHA connectomes and hyperalignment outputs..."
        dx upload -r "${OUTPUTS_ROOT}/connectomes/hyperalignment_output" --path "${RAP_UPLOAD_PATH}/connectomes/"
    fi

    STEP_END=$(date +%s)
    echo "  ✓ Connectomes uploaded ($(((STEP_END - STEP_START) / 60)) minutes)"
    echo ""
fi

# ============================================================================
# UPLOAD SIMILARITY MATRICES
# ============================================================================

if [ "${UPLOAD_SIMILARITY_MATRICES}" = "yes" ] && [ -d "${OUTPUTS_ROOT}/connectomes/similarity_matrices" ]; then
    echo "================================================"
    echo "Uploading similarity matrices..."
    echo "================================================"
    STEP_START=$(date +%s)

    dx upload -r "${OUTPUTS_ROOT}/connectomes/similarity_matrices" --path "${RAP_UPLOAD_PATH}/connectomes/"

    STEP_END=$(date +%s)
    echo "  ✓ Similarity matrices uploaded ($(((STEP_END - STEP_START) / 60)) minutes)"
    echo ""
fi

# ============================================================================
# UPLOAD RELIABILITY RESULTS
# ============================================================================

if [ "${UPLOAD_RELIABILITY_RESULTS}" = "yes" ] && [ -d "${OUTPUTS_ROOT}/connectomes/reliability_results" ]; then
    echo "================================================"
    echo "Uploading reliability results..."
    echo "================================================"
    STEP_START=$(date +%s)

    dx upload -r "${OUTPUTS_ROOT}/connectomes/reliability_results" --path "${RAP_UPLOAD_PATH}/connectomes/"

    STEP_END=$(date +%s)
    echo "  ✓ Reliability results uploaded ($(((STEP_END - STEP_START) / 60)) minutes)"
    echo ""
fi

# ============================================================================
# UPLOAD PARCELLATION DATA
# ============================================================================

if [ "${UPLOAD_PARCELLATION}" = "yes" ] && [ -d "${OUTPUTS_ROOT}/glasser_ptseries" ]; then
    echo "================================================"
    echo "Uploading parcellation data..."
    echo "================================================"
    echo "  Warning: This may be very large and take a long time!"
    STEP_START=$(date +%s)

    dx upload -r "${OUTPUTS_ROOT}/glasser_ptseries" --path "${RAP_UPLOAD_PATH}/"

    STEP_END=$(date +%s)
    echo "  ✓ Parcellation data uploaded ($(((STEP_END - STEP_START) / 60)) minutes)"
    echo ""
fi

# ============================================================================
# UPLOAD LOGS
# ============================================================================

# Upload logs from hyperalignment_scripts directory
if [ "${UPLOAD_LOGS}" = "yes" ]; then
    echo "================================================"
    echo "Uploading logs..."
    echo "================================================"
    STEP_START=$(date +%s)

    # Check multiple possible log locations
    LOG_UPLOADED=false

    # Logs in connectomes directory
    if [ -d "${OUTPUTS_ROOT}/connectomes/logs" ]; then
        echo "  Uploading logs from connectomes/logs..."
        dx upload -r "${OUTPUTS_ROOT}/connectomes/logs" --path "${RAP_UPLOAD_PATH}/connectomes/"
        LOG_UPLOADED=true
    fi

    # Logs in main project directory
    if [ -d "$(dirname $(dirname ${OUTPUTS_ROOT}))/logs" ]; then
        echo "  Uploading logs from project directory..."
        dx upload -r "$(dirname $(dirname ${OUTPUTS_ROOT}))/logs" --path "${RAP_UPLOAD_PATH}/"
        LOG_UPLOADED=true
    fi

    if [ "$LOG_UPLOADED" = true ]; then
        STEP_END=$(date +%s)
        echo "  ✓ Logs uploaded ($(((STEP_END - STEP_START) / 60)) minutes)"
    else
        echo "  ⚠ No logs found to upload"
    fi
    echo ""
fi

# ============================================================================
# UPLOAD SUMMARY FILE
# ============================================================================

echo "Creating upload summary..."
SUMMARY_FILE="/tmp/upload_summary_${UPLOAD_TIMESTAMP}.txt"
cat > "${SUMMARY_FILE}" <<EOF
UK Biobank RAP Pipeline Upload Summary
======================================

Upload Date: $(date)
Local Source: ${OUTPUTS_ROOT}
RAP Destination: ${RAP_UPLOAD_PATH}

Files Uploaded:
- Connectomes: ${UPLOAD_CONNECTOMES}
- Similarity Matrices: ${UPLOAD_SIMILARITY_MATRICES}
- Reliability Results: ${UPLOAD_RELIABILITY_RESULTS}
- Parcellation Data: ${UPLOAD_PARCELLATION}
- Logs: ${UPLOAD_LOGS}

Pipeline Configuration:
$(cat ${OUTPUTS_ROOT}/../logs/pipeline_config.txt 2>/dev/null || echo "No config file found")

Upload completed at: $(date)
Total upload time: $((($(date +%s) - UPLOAD_START) / 60)) minutes
EOF

dx upload "${SUMMARY_FILE}" --path "${RAP_UPLOAD_PATH}/upload_summary.txt"
rm "${SUMMARY_FILE}"

UPLOAD_END=$(date +%s)
TOTAL_DURATION=$((UPLOAD_END - UPLOAD_START))

echo ""
echo "================================================"
echo "UPLOAD COMPLETE"
echo "================================================"
echo ""
echo "All selected outputs have been uploaded to:"
echo "  ${RAP_UPLOAD_PATH}"
echo ""
echo "Total upload time: $((TOTAL_DURATION / 60)) minutes"
echo ""
echo "To view your files on RAP:"
echo "  dx ls ${RAP_UPLOAD_PATH}"
echo ""
echo "To download files from RAP to another location:"
echo "  dx download -r ${RAP_UPLOAD_PATH}"
echo ""
