# Timing Reports and RAP Upload Guide

## 1. Pipeline Timing Reports

The pipeline now automatically tracks and reports the duration of each step!

### What's New

When you run `./full_pipeline_v2.sh`, you'll see:

**During execution:**
```
STEP 1: PARCELLATION
Started at: Mon Jan 15 14:23:10 UTC 2024
...
✓ Parcellation complete - Duration: 01:23:45
```

**At the end:**
```
================================================
PIPELINE V2 COMPLETE
================================================

Finished at: Mon Jan 15 18:45:32 UTC 2024

TIMING SUMMARY:
----------------------------------------
  Parcellation:          01:23:45
  Build AA Connectomes:  00:45:12
  Hyperalignment:        12:34:56
  Build CHA Connectomes: 00:38:22
  Similarity Matrices:   02:15:30
  IDM Reliability:       00:12:08
----------------------------------------
  TOTAL PIPELINE TIME:   17:49:53
========================================
```

### How It Works

- Times are in `HH:MM:SS` format
- Only shows steps that actually ran
- Total pipeline time includes setup and validation
- Each step shows start time and completion duration

---

## 2. Uploading to UK Biobank RAP

Two methods available: **Bash script** (simpler) or **Python script** (more control).

### Method 1: Bash Script (Recommended)

**Basic usage:**
```bash
export OUTPUTS_ROOT=/home/dnanexus/HBN_ASD_ADHD/data
export RAP_PROJECT_PATH=/my_analysis/results
./upload_to_biobank_rap.sh
```

**Customize what to upload:**
```bash
# Skip large parcellation data
export UPLOAD_PARCELLATION=no

# Upload only connectomes and similarity matrices
export UPLOAD_CONNECTOMES=yes
export UPLOAD_SIMILARITY_MATRICES=yes
export UPLOAD_RELIABILITY_RESULTS=no
export UPLOAD_LOGS=no

./upload_to_biobank_rap.sh
```

**What gets uploaded:**
- ✅ AA connectomes (coarse & fine)
- ✅ CHA connectomes (hyperalignment outputs)
- ✅ Similarity matrices (ISC & covariance)
- ✅ Reliability results
- ✅ Pipeline logs
- ❌ Parcellation data (off by default - very large!)

### Method 2: Python Script (Using dxpy)

**Basic usage:**
```bash
python upload_to_rap_python.py \
    --outputs /home/dnanexus/HBN_ASD_ADHD/data \
    --destination /my_analysis/results
```

**Upload only specific outputs:**
```bash
# Only connectomes and similarity matrices
python upload_to_rap_python.py \
    --outputs /home/dnanexus/HBN_ASD_ADHD/data \
    --destination /results \
    --no-reliability --no-logs
```

**Include large parcellation data:**
```bash
python upload_to_rap_python.py \
    --outputs /home/dnanexus/HBN_ASD_ADHD/data \
    --destination /complete_results \
    --include-parcellation
```

**Available options:**
- `--no-connectomes` - Skip connectomes
- `--no-similarity` - Skip similarity matrices
- `--no-reliability` - Skip reliability results
- `--no-logs` - Skip logs
- `--include-parcellation` - Upload parcellation data (large!)

---

## 3. Typical Workflow

**Run pipeline with timing:**
```bash
export INPUTS_ROOT=/mnt/project/CIFTI_1
export OUTPUTS_ROOT=/home/dnanexus/HBN_ASD_ADHD/data
export CONNECTOME_MODE=split
./full_pipeline_v2.sh
```

**Upload results to RAP:**
```bash
# After pipeline completes
export OUTPUTS_ROOT=/home/dnanexus/HBN_ASD_ADHD/data
export RAP_PROJECT_PATH=/my_analysis/run_$(date +%Y%m%d)
./upload_to_biobank_rap.sh
```

**Close server without losing data:**
Once the upload completes, all your results are safely stored on RAP! You can now close the ttyd server and the data will persist.

---

## 4. Upload Output Structure

Your data will be uploaded to RAP in this structure:

```
/pipeline_outputs/upload_20240115_184532/
├── connectomes/
│   ├── coarse/           # AA coarse connectomes
│   ├── fine/             # AA fine connectomes
│   ├── hyperalignment_output/
│   │   ├── aligned_timeseries/
│   │   ├── mappers/
│   │   └── connectomes/  # CHA connectomes
│   ├── similarity_matrices/
│   ├── reliability_results/
│   └── logs/
├── logs/                 # Pipeline execution logs
└── upload_summary.txt    # Upload metadata
```

The timestamp (`20240115_184532`) ensures each upload session is unique and won't overwrite previous uploads.

---

## 5. Checking Upload on RAP

**List uploaded files:**
```bash
dx ls /pipeline_outputs/upload_20240115_184532
```

**Download specific results:**
```bash
# Download similarity matrices
dx download -r /pipeline_outputs/upload_20240115_184532/connectomes/similarity_matrices

# Download reliability results
dx download -r /pipeline_outputs/upload_20240115_184532/connectomes/reliability_results
```

**Download everything:**
```bash
dx download -r /pipeline_outputs/upload_20240115_184532
```

---

## 6. Troubleshooting

**"dx command not found"**
- You must run the bash upload script on a UK Biobank RAP node where `dx` CLI is installed

**"dxpy module not found"**
- For Python script: `pip install dxpy`
- Or use the bash script instead

**Upload is slow**
- UK Biobank RAP uploads can be slow depending on data size
- Consider skipping parcellation data (`UPLOAD_PARCELLATION=no`)
- The scripts show progress and timing for each section

**Data already uploaded, want to upload again**
- Each upload creates a timestamped directory, so you can upload multiple times safely
- Previous uploads won't be overwritten

---

## 7. Estimated Upload Sizes & Times

Typical sizes for 50 subjects:

| Data Type | Size | Upload Time* |
|-----------|------|--------------|
| AA Connectomes | ~2-5 GB | 5-10 min |
| CHA Connectomes | ~3-6 GB | 8-15 min |
| Similarity Matrices | ~500 MB | 2-5 min |
| Reliability Results | ~50 MB | <1 min |
| Logs | ~100 MB | 1-2 min |
| Parcellation | ~20-50 GB | 45-90 min |

*Times vary based on network speed and RAP load

**Recommendation:** Upload everything except parcellation data by default. Only upload parcellation if you specifically need the intermediate ptseries files for other analyses.
