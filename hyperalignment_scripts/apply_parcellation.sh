#!/usr/bin/env bash
set -euo pipefail

# --- SOURCE CENTRALIZED CONFIGURATION ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# --- INPUTS ---
# Override BASEDIR and OUTDIR from environment if needed
# These are machine-specific absolute paths, so we use environment variables
# Default to centralized config values if not set
BASEDIR="${BASEDIR:-$DTSERIES_ROOT}"
OUTDIR="${OUTDIR:-$PTSERIES_ROOT}"
PARCELLATION="${PARCELLATION:-$PARCELLATION_FILE}"

# Convert relative paths to absolute if needed
if [[ ! "$BASEDIR" = /* ]]; then
    BASEDIR="$SCRIPT_DIR/$BASEDIR"
fi
if [[ ! "$OUTDIR" = /* ]]; then
    OUTDIR="$SCRIPT_DIR/$OUTDIR"
fi
if [[ ! "$PARCELLATION" = /* ]]; then
    PARCELLATION="$SCRIPT_DIR/$PARCELLATION"
fi

# --- PREP ---
mkdir -p "$OUTDIR"

# Set TMPDIR to ensure wb_command writes temporary files to writable location
# This is critical when BASEDIR is read-only
export TMPDIR="${TMPDIR:-${OUTDIR}/.tmp}"
mkdir -p "$TMPDIR"

# Make the glob return empty if no matches (bash)
shopt -s nullglob

# Parallelism and resume options
# N_JOBS is now set from config.sh (can still be overridden by environment)
N_JOBS=${N_JOBS:-24}
# Set FORCE=1 to overwrite existing outputs
FORCE=${FORCE:-0}

# Simple job tracking array
pids=()
failed=0

# Ensure background jobs are cleaned up on exit
trap 'for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done' EXIT

# --- LOOP OVER FILES ---
# Your files look like:
#   sub-NDARAXXXXXXX_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
# Collect matching files into an array so we can show progress n/m
# Use pattern from centralized config
files=( "$BASEDIR"/$DTSERIES_FILENAME_PATTERN )
total=${#files[@]}

if [ "$total" -eq 0 ]; then
  echo "No matching dtseries files found in: $BASEDIR"
  exit 0
fi

# Loop with index to show progress; run jobs in background and cap concurrency
for ((idx=0; idx<total; idx++)); do
  INFILE="${files[idx]}"
  fname=$(basename "$INFILE")
  INDEX=$((idx+1))

  # Extract sub-ID (e.g., "sub-NDARAA948VFH")
  SUBID="${fname%%_*}"  # everything up to first underscore

  # Extract run number if present (e.g., "1" from run-1)
  if [[ "$fname" =~ run-([0-9]+) ]]; then
    RUN="${BASH_REMATCH[1]}"
  else
    RUN="1"
  fi

  # Per-subject subfolder keeps things tidy
  OUTDN="$OUTDIR/$SUBID"
  mkdir -p "$OUTDN"

  # Output name
  # Example: sub-XXXX_run-1_glasser.ptseries.nii
  OUTFN="$OUTDN/${SUBID}_run-${RUN}_glasser.ptseries.nii"

  # Skip if already done (non-empty file) unless FORCE=1
  if [ "$FORCE" != "1" ] && [ -s "$OUTFN" ]; then
    echo "Skipping ($INDEX/$total): already exists -> $OUTFN"
    continue
  fi

  echo "Parcellating ($INDEX/$total): $INFILE"

  (
    set -e
    wb_command -cifti-parcellate "$INFILE" "$PARCELLATION" COLUMN "$OUTFN"
    echo " -> $OUTFN"
  ) &

  pids+=("$!")

  # If we've reached the job limit, wait for at least one job to finish
  while [ "${#pids[@]}" -ge "$N_JOBS" ]; do
    for i in "${!pids[@]}"; do
      pid=${pids[i]}
      if ! kill -0 "$pid" 2>/dev/null; then
        wait "$pid" || failed=$((failed+1))
        unset 'pids[i]'
      fi
    done
    # reindex array
    pids=("${pids[@]:-}")
    sleep 0.5
  done

done

# Wait for remaining background jobs
for pid in "${pids[@]:-}"; do
  if [ -n "$pid" ]; then
    wait "$pid" || failed=$((failed+1))
  fi
done

if [ "$failed" -ne 0 ]; then
  echo "Finished with $failed failed jobs"
  # Clean up temporary directory
  rm -rf "$TMPDIR"
  exit 1
fi

# Clean up temporary directory
rm -rf "$TMPDIR"

echo "All done. Outputs in: $OUTDIR"
