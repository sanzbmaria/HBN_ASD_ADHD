# How to Build and Test the Docker Pipeline

This guide walks you through building the Docker image and testing it with a small subset of subjects before running the full pipeline.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Build the Docker Image](#step-1-build-the-docker-image)
3. [Step 2: Prepare Test Data](#step-2-prepare-test-data)
4. [Step 3: Run Test Mode](#step-3-run-test-mode)
5. [Step 4: Verify Test Results](#step-4-verify-test-results)
6. [Step 5: Run Full Pipeline](#step-5-run-full-pipeline)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Mac

1. Install Docker Desktop: https://www.docker.com/products/docker-desktop
2. Start Docker Desktop
3. Configure resources:
   - Open Docker Desktop → Preferences → Resources
   - **CPUs**: 4-8 cores
   - **Memory**: 16-32GB
   - **Disk**: 50GB free

### Ubuntu

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
```

---

## Step 1: Build the Docker Image

### Clone the Repository (if not already done)

```bash
git clone https://github.com/sanzbmaria/HBN_ASD_ADHD.git
cd HBN_ASD_ADHD
```

### Build the Image

```bash
./docker-build.sh
```

**What this does:**
- Downloads Ubuntu 20.04 base image
- Installs Python 2.7 and Python 3.8
- Installs scientific libraries (numpy, scipy, nibabel, pandas, etc.)
- Installs PyMVPA2 for hyperalignment
- Installs Connectome Workbench
- Copies your hyperalignment scripts

**Time**: 5-10 minutes (depends on internet speed)

**Output**: You should see:
```
Successfully tagged hyperalignment:latest
================================================
Build complete!
Image: hyperalignment:latest
...
================================================
```

### Verify the Build

```bash
# Check the image exists
docker images | grep hyperalignment

# You should see:
# hyperalignment   latest   <image_id>   <size>
```

---

## Step 2: Prepare Test Data

### Organize Your Data Directory

```bash
# Set your data path
export DATA_ROOT=/path/to/your/data

# For example:
# Mac:    export DATA_ROOT=/Users/maria/Documents/HBN_data
# Ubuntu: export DATA_ROOT=/home/maria/HBN_data
```

### Expected Directory Structure

```
$DATA_ROOT/
├── HBN_CIFTI/                          # Your dtseries files go here
│   ├── sub-NDARAA123_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   ├── sub-NDARAA456_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   ├── sub-NDARAA789_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   └── ...
│
├── diagnosis_summary/                  # Optional: subject metadata
│   └── matched_subjects_diagnosis_mini.csv
│
├── hyperalignment_input/               # Will be created automatically
└── connectomes/                        # Will be created automatically
```

### Verify Data Files

```bash
# Check how many subjects you have
ls $DATA_ROOT/HBN_CIFTI/*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii | wc -l

# List first few subjects
ls $DATA_ROOT/HBN_CIFTI/*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii | head -5
```

---

## Step 3: Run Test Mode

### Option A: Quick Test (Auto-select 5 subjects)

```bash
export DATA_ROOT=/path/to/your/data

# Run test with default settings (5 subjects, 3 parcels)
./test_pipeline.sh
```

**What this does:**
1. Automatically selects first 5 subjects
2. Runs parcellation on these subjects
3. Runs hyperalignment on parcels 1, 2, 3
4. Builds connectomes for test subjects
5. Validates all outputs

**Time**: ~15-30 minutes

### Option B: Specify Subjects by ID

```bash
export DATA_ROOT=/path/to/your/data

# Specify exact subjects to test
export TEST_SUBJECTS="sub-NDARAA123 sub-NDARAA456 sub-NDARAA789"

./test_pipeline.sh
```

### Option C: Custom Test Configuration

```bash
export DATA_ROOT=/path/to/your/data

# Select number of subjects
export N_TEST_SUBJECTS=10

# Select which parcels to test
export TEST_PARCELS="1 10 50 100 180"

# Select which steps to run
export RUN_PARCELLATION=yes
export RUN_HYPERALIGNMENT=yes
export RUN_CONNECTOMES=yes

# Hyperalignment mode
export MODE=full  # or 'split' or 'both'

# Resource allocation
export N_JOBS=4
export POOL_NUM=4

./test_pipeline.sh
```

### Test Output Example

```
================================================
HYPERALIGNMENT PIPELINE - TEST MODE
================================================

Discovering available subjects...
Found 150 subjects with dtseries files

Auto-selected first 5 subjects for testing:
  - sub-NDARAA123ABC
  - sub-NDARAA456DEF
  - sub-NDARAA789GHI
  - sub-NDARBB123JKL
  - sub-NDARBB456MNO

================================================
Test Configuration
================================================
Docker image: hyperalignment:latest
Data root: /Users/maria/Documents/HBN_data
Test subjects (5): sub-NDARAA123ABC sub-NDARAA456DEF ...
Test parcels: 1 2 3

Pipeline steps:
  Parcellation: yes
  Hyperalignment: yes (mode: full)
  Connectomes: yes

Resources:
  N_JOBS: 4
  POOL_NUM: 4
================================================

Continue with test? (y/n)
```

---

## Step 4: Verify Test Results

After the test completes, you should see:

```
================================================
TEST PIPELINE COMPLETE
================================================
End time: Mon Jan  1 12:34:56 PST 2024
Total elapsed time: 23m 45s

Validating outputs...

Checking parcellated data...
  ✓ sub-NDARAA123ABC: ptseries found
  ✓ sub-NDARAA456DEF: ptseries found
  ✓ sub-NDARAA789GHI: ptseries found
  ✓ sub-NDARBB123JKL: ptseries found
  ✓ sub-NDARBB456MNO: ptseries found

Checking hyperalignment outputs...
  ✓ Parcel 1: 4 mappers, 4 aligned files
  ✓ Parcel 2: 4 mappers, 4 aligned files
  ✓ Parcel 3: 4 mappers, 4 aligned files

Checking connectomes...
  ✓ Parcel 1: 5 connectome files
  ✓ Parcel 2: 5 connectome files
  ✓ Parcel 3: 5 connectome files

================================================
✓ ALL VALIDATION CHECKS PASSED
================================================

Your Docker setup is working correctly!

Output locations:
  Parcellated data: /Users/maria/Documents/HBN_data/hyperalignment_input/glasser_ptseries/
  Hyperalignment outputs: /Users/maria/Documents/HBN_data/connectomes/hyperalignment_output/
  Connectomes: /Users/maria/Documents/HBN_data/connectomes/fine/

Logs: /Users/maria/HBN_ASD_ADHD/logs/
```

### Manually Inspect Outputs

```bash
# Check parcellated files
ls $DATA_ROOT/hyperalignment_input/glasser_ptseries/sub-*/

# Check hyperalignment outputs
ls $DATA_ROOT/connectomes/hyperalignment_output/aligned_timeseries/parcel_001/
ls $DATA_ROOT/connectomes/hyperalignment_output/mappers/parcel_001/

# Check connectomes
ls $DATA_ROOT/connectomes/fine/parcel_001/

# View logs
ls logs/
tail logs/test_hyperalignment_parcel_1.log
```

---

## Step 5: Run Full Pipeline

Once testing passes, you can run the full pipeline:

### Option A: Local Execution (Mac/Ubuntu)

```bash
export DATA_ROOT=/path/to/your/data

# Run all subjects, all parcels
./local_scripts/run_full_pipeline.sh
```

See `LOCAL_EXECUTION_GUIDE.md` for detailed options.

### Option B: PBS Cluster

```bash
# Convert to Singularity
./docker-to-singularity.sh

# Transfer to cluster
scp hyperalignment.sif your-cluster:/project/hyperalignment/
scp -r pbs_scripts your-cluster:/project/hyperalignment/

# On cluster
cd /project/hyperalignment
export DATA_ROOT=/scratch/username/HBN_data
./pbs_scripts/submit_pipeline.sh
```

See `DOCKER_PBS_README.md` for detailed PBS instructions.

---

## Troubleshooting

### Build Issues

**Problem**: `docker: command not found`

```bash
# Mac: Install Docker Desktop
# Ubuntu: Run installation commands from Prerequisites section
```

**Problem**: Build fails on PyMVPA2

```bash
# This usually means network issues
# Try again:
./docker-build.sh

# Or build with no cache:
docker build --no-cache -t hyperalignment:latest .
```

**Problem**: "No space left on device"

```bash
# Clean up Docker
docker system prune -a

# Check disk space
df -h

# Free up space and try again
```

### Test Issues

**Problem**: "No subjects found"

```bash
# Check your data directory
ls $DATA_ROOT/HBN_CIFTI/

# Make sure files match the expected pattern
ls $DATA_ROOT/HBN_CIFTI/*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii

# If files have different names, you may need to update config.sh
```

**Problem**: Test fails on parcellation

```bash
# Check the log
cat logs/test_hyperalignment_parcel_1.log

# Common issue: wb_command not found
# Solution: Rebuild Docker image
./docker-build.sh
```

**Problem**: Test fails on hyperalignment with memory error

```bash
# Reduce N_JOBS
export N_JOBS=2
export POOL_NUM=2

# Run test again
./test_pipeline.sh
```

**Problem**: Python 2 import errors

```bash
# Rebuild the Docker image
./docker-build.sh

# Test Python 2 inside container
docker run --rm -it hyperalignment:latest python2 -c "from mvpa2.algorithms.hyperalignment import Hyperalignment; print('PyMVPA2 OK')"
```

### Validation Failures

**Problem**: "ptseries NOT found"

```
This means parcellation failed. Check:
1. Input dtseries files exist
2. wb_command is working in container
3. Parcellation log for errors
```

**Problem**: "mappers NOT found"

```
This means hyperalignment failed. Check:
1. Parcellation completed successfully
2. Python 2 and PyMVPA2 are working
3. Hyperalignment log for detailed errors
```

**Problem**: "connectomes NOT found"

```
This means connectome building failed. Check:
1. Hyperalignment completed successfully
2. Python 3 and dependencies are working
3. Connectome log for detailed errors
```

---

## Quick Command Reference

### Build and Test
```bash
# Build Docker image
./docker-build.sh

# Test with 5 subjects (auto-selected)
export DATA_ROOT=/path/to/your/data
./test_pipeline.sh

# Test with specific subjects
export DATA_ROOT=/path/to/your/data
export TEST_SUBJECTS="sub-NDARAA123 sub-NDARAA456"
./test_pipeline.sh

# Test with 10 subjects
export DATA_ROOT=/path/to/your/data
export N_TEST_SUBJECTS=10
./test_pipeline.sh
```

### Check Docker
```bash
# List images
docker images

# Check if container works
docker run --rm -it hyperalignment:latest /bin/bash

# Inside container, test:
python2 --version
python3 --version
wb_command -version
python2 -c "import mvpa2; print('PyMVPA2 OK')"
```

### Clean Up Test Data
```bash
# Remove test outputs (keep input data)
rm -rf $DATA_ROOT/hyperalignment_input/
rm -rf $DATA_ROOT/connectomes/
rm -rf $DATA_ROOT/test_HBN_CIFTI/
rm -f $DATA_ROOT/test_subjects.txt
rm -rf logs/
```

---

## Next Steps After Successful Test

1. **Small-scale local run**: Process 10-20 subjects locally
   ```bash
   export START_PARCEL=1
   export END_PARCEL=50
   ./local_scripts/run_full_pipeline.sh
   ```

2. **Full local run**: If you have a powerful machine
   ```bash
   ./local_scripts/run_full_pipeline.sh
   ```

3. **PBS cluster run**: For large-scale production
   - Convert to Singularity: `./docker-to-singularity.sh`
   - Follow instructions in `DOCKER_PBS_README.md`

---

## Summary

✅ **Build**: `./docker-build.sh` (5-10 min)
✅ **Test**: `./test_pipeline.sh` (15-30 min)
✅ **Verify**: Check validation output
✅ **Deploy**: Local or cluster full run

The test mode ensures:
- Docker image works correctly
- Python 2 (hyperalignment) works
- Python 3 (connectomes) works
- Connectome Workbench works
- All pipeline steps work end-to-end
- Your data is in the correct format

You're now ready for production runs!
