#!/usr/bin/env bash
set -euo pipefail

# --- INPUTS (edit these if needed) ---
# Your flat directory of dtseries files:
BASEDIR="/Volumes/MyPassport-Selin/HBN_CIFTI/"

# Choose where you want outputs to go.
# Option A (recommended): a tidy project-local folder
OUTDIR="/Volumes/FMRI2/data/hyperalignment_input/glasser_ptseries"

# Option B (alt): next to your data mirror (uncomment to use)
# OUTDIR="/Users/maria/Documents/code/ASD/Data_mirror/Parcellated/glasser_ptseries"

# Parcellation: Glasser MMP (the one you listed)
PARCELLATION="/Volumes/FMRI2/hyperalignment_scripts/atlas/Q1-Q6_RelatedValidation210.CorticalAreas_dil_Final_Final_Areas_Group_Colors.32k_fs_LR.dlabel.nii"

# (Optional) If you want Gordon instead, just swap the line above for:
# PARCELLATION="HCP_S1200_Atlas_Z4_pkXDZ/Gordon333.32k_fs_LR.dlabel.nii"

# --- PREP ---
mkdir -p "$OUTDIR"

# Make the glob return empty if no matches (bash)
shopt -s nullglob

# Parallelism and resume options
# Set N_JOBS in the environment to override (e.g., export N_JOBS=12)
N_JOBS=${N_JOBS:-22}
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
files=( "$BASEDIR"/sub-*_task-rest_run-*_nogsr_Atlas_s5.dtseries.nii )
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
  wait "$pid" || failed=$((failed+1))
done

if [ "$failed" -ne 0 ]; then
  echo "Finished with $failed failed jobs"
  exit 1
fi

echo "All done. Outputs in: $OUTDIR"
