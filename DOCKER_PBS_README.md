# Docker and PBS Cluster Setup Guide

This guide explains how to build a Docker container for the hyperalignment pipeline and run it on a PBS cluster.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start - Local Testing](#quick-start---local-testing)
4. [PBS Cluster Deployment](#pbs-cluster-deployment)
5. [Detailed Usage](#detailed-usage)
6. [Troubleshooting](#troubleshooting)

---

## Overview

The hyperalignment pipeline is containerized using Docker and can be converted to Singularity for HPC cluster use. The container includes:

- **Python 2.7**: For PyMVPA2 and hyperalignment
- **Python 3.8**: For connectome building and analysis
- **Connectome Workbench**: For CIFTI file processing
- **Scientific libraries**: NumPy, SciPy, nibabel, pandas, scikit-learn

### Pipeline Architecture

```
Raw CIFTI dtseries
    ↓
[1] Parcellation (wb_command) → ptseries files
    ↓
[2] Hyperalignment (Python 2) → aligned timeseries
    ↓
[3] Build Connectomes (Python 3) → connectivity matrices
```

---

## Prerequisites

### Local Machine (for building)
- Docker installed
- Sufficient disk space (~5GB for image)

### PBS Cluster (for running)
- Singularity or Apptainer installed
- PBS job scheduler
- Access to data storage with sufficient space

---

## Quick Start - Local Testing

### 1. Build the Docker Image

```bash
./docker-build.sh
```

This creates a Docker image tagged as `hyperalignment:latest`.

### 2. Test the Container Locally

```bash
# Set your data directory
export DATA_ROOT=/path/to/your/data

# Run interactive shell
./docker-run.sh
```

Inside the container, you can test individual scripts:

```bash
# Check Python versions
python2 --version  # Should be 2.7.x
python3 --version  # Should be 3.8.x

# Check Workbench
wb_command -version

# Test parcellation (if you have data)
export BASEDIR=/data/HBN_CIFTI
export OUTDIR=/data/hyperalignment_input/glasser_ptseries
./apply_parcellation.sh

# Test hyperalignment for one parcel
python2 run_hyperalignment.py 1 full
```

---

## PBS Cluster Deployment

### Step 1: Convert Docker to Singularity

**Option A: On your local machine (if Singularity installed)**

```bash
./docker-to-singularity.sh
```

This creates `hyperalignment.sif`.

**Option B: On the cluster**

Transfer the Docker image as a tar archive:

```bash
# On local machine
docker save hyperalignment:latest | gzip > hyperalignment.tar.gz
scp hyperalignment.tar.gz cluster:/path/to/images/

# On cluster
gunzip hyperalignment.tar.gz
singularity build hyperalignment.sif docker-archive://hyperalignment.tar
```

**Option C: Via Docker Hub**

```bash
# Push to Docker Hub (requires account)
docker tag hyperalignment:latest yourusername/hyperalignment:latest
docker push yourusername/hyperalignment:latest

# Pull on cluster
singularity pull hyperalignment.sif docker://yourusername/hyperalignment:latest
```

### Step 2: Transfer Files to Cluster

```bash
# Create project directory on cluster
ssh cluster "mkdir -p /project/hyperalignment"

# Transfer Singularity image
scp hyperalignment.sif cluster:/project/hyperalignment/

# Transfer PBS scripts
scp -r pbs_scripts cluster:/project/hyperalignment/
```

### Step 3: Configure PBS Scripts

Edit the PBS scripts in `pbs_scripts/` to match your cluster configuration:

1. **Module loading**: Update `module load` commands
2. **Data paths**: Set `DATA_ROOT` to your data location
3. **Resource requests**: Adjust `ncpus`, `mem`, `walltime` as needed
4. **Singularity path**: Update `SINGULARITY_IMAGE` path

Example edits in each PBS script:

```bash
# BEFORE
DATA_ROOT="/path/to/your/data"  # EDIT THIS

# AFTER
DATA_ROOT="/scratch/username/HBN_data"
```

### Step 4: Prepare Data Directory Structure

On the cluster, organize your data as:

```
/your/data/root/
├── HBN_CIFTI/                          # Input dtseries files
│   ├── sub-NDARAA123_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   └── ...
├── hyperalignment_input/               # Parcellated data
│   └── glasser_ptseries/
├── connectomes/                        # Output connectomes
│   ├── fine/                           # Per-parcel connectomes
│   └── hyperalignment_output/          # Aligned outputs
└── diagnosis_summary/                  # Subject metadata
    └── matched_subjects_diagnosis_mini.csv
```

### Step 5: Submit Jobs

**Option A: Interactive submission**

```bash
cd /project/hyperalignment
export DATA_ROOT=/scratch/username/HBN_data
./pbs_scripts/submit_pipeline.sh
```

Follow the prompts to submit parcellation, hyperalignment, and connectome building.

**Option B: Manual submission**

```bash
# Step 1: Parcellation
qsub pbs_scripts/pbs_parcellation.sh

# Step 2: Hyperalignment (all parcels)
qsub pbs_scripts/pbs_hyperalignment_array.sh

# Step 2b: Or specific parcels
qsub -J 1-50 pbs_scripts/pbs_hyperalignment_array.sh

# Step 3: Build connectomes (after hyperalignment completes)
qsub -v SCRIPT=build_aa_connectomes.py pbs_scripts/pbs_build_connectomes.sh
```

### Step 6: Monitor Jobs

```bash
# View job status
qstat -u $USER

# View detailed job info
qstat -f JOBID

# View logs (while running or after completion)
tail -f logs/hyperalignment_parcel_1_*.log
```

---

## Detailed Usage

### PBS Scripts Overview

| Script | Purpose | Resources | Array Job |
|--------|---------|-----------|-----------|
| `pbs_parcellation.sh` | Apply Glasser parcellation | 24 CPUs, 64GB, 12h | No |
| `pbs_hyperalignment_single.sh` | Run hyperalignment for one parcel | 24 CPUs, 128GB, 24h | No |
| `pbs_hyperalignment_array.sh` | Run hyperalignment for all/subset parcels | 24 CPUs, 128GB, 24h | Yes (1-360) |
| `pbs_build_connectomes.sh` | Build connectivity matrices | 24 CPUs, 128GB, 48h | No |
| `submit_pipeline.sh` | Interactive pipeline submission | N/A | No |

### Running Specific Parcels

```bash
# Single parcel
qsub -v PARCEL=100 pbs_scripts/pbs_hyperalignment_single.sh

# Range of parcels (array job)
qsub -J 100-150 pbs_scripts/pbs_hyperalignment_array.sh

# Specific parcels (multiple individual jobs)
for p in 1 50 100 150 200 250 300 350; do
    qsub -v PARCEL=$p pbs_scripts/pbs_hyperalignment_single.sh
done
```

### Hyperalignment Modes

The hyperalignment script supports three modes:

- **`full`**: Full timeseries hyperalignment only
- **`split`**: Split-half reliability analysis only
- **`both`**: Both full and split (default)

```bash
# Specify mode
qsub -v PARCEL=1,MODE=full pbs_scripts/pbs_hyperalignment_single.sh
qsub -v MODE=split pbs_scripts/pbs_hyperalignment_array.sh
```

### Environment Variables

You can override configuration parameters via environment variables:

```bash
# In PBS scripts or before submission
export N_JOBS=16           # Number of parallel processes
export POOL_NUM=16         # Multiprocessing pool size

# In parcellation job
export BASEDIR=/custom/path/to/cifti
export OUTDIR=/custom/output/path
```

### Data Binding with Singularity

The PBS scripts automatically bind necessary paths:

```bash
singularity exec \
    --bind ${DATA_ROOT}:/data \                # Your data directory
    --bind ${PBS_O_WORKDIR}:/workspace \       # Job working directory
    --pwd /app/hyperalignment_scripts \        # Work in scripts dir
    ${SINGULARITY_IMAGE} \
    command
```

Paths inside container:
- `/data/` → Your `DATA_ROOT`
- `/data/HBN_CIFTI/` → Input dtseries files
- `/data/connectomes/` → Output connectomes
- `/app/hyperalignment_scripts/` → Pipeline scripts

---

## Troubleshooting

### Docker Build Issues

**Problem**: Docker build fails on PyMVPA2

```
Solution: PyMVPA2 requires specific versions of dependencies
Check that Python 2 packages use compatible versions:
- numpy==1.16.6
- scipy==1.2.3
```

**Problem**: Workbench download fails

```
Solution: The Workbench URL may change. Check latest version at:
https://www.humanconnectome.org/software/get-connectome-workbench
Update Dockerfile URL if needed.
```

### Singularity Conversion Issues

**Problem**: `singularity` command not found

```
Solution: Load the Singularity module or use apptainer:
module load singularity
# or
module load apptainer
```

**Problem**: Permission denied when building .sif

```
Solution: Build in a directory where you have write permission
cd /tmp
singularity build hyperalignment.sif docker-daemon://hyperalignment:latest
```

### PBS Job Issues

**Problem**: Job fails immediately with "Image not found"

```
Solution: Check SINGULARITY_IMAGE path in PBS script
Make sure hyperalignment.sif exists at that location
Use absolute paths, not relative paths
```

**Problem**: Job fails with "Directory not found"

```
Solution: Check DATA_ROOT path exists on the cluster
Verify data directory structure matches expected layout
Check that paths are accessible from compute nodes
```

**Problem**: Python 2 not found in container

```
Solution: The container should have both Python 2 and 3
Test with: singularity exec hyperalignment.sif python2 --version
Rebuild container if necessary
```

**Problem**: Out of memory errors

```
Solution: Increase memory in PBS header
#PBS -l select=1:ncpus=24:mem=256gb  # Increase from 128gb

Or reduce N_JOBS:
export N_JOBS=12  # Reduce parallelism
```

**Problem**: Walltime exceeded

```
Solution: Increase walltime or reduce parcels per job
#PBS -l walltime=48:00:00  # Increase from 24:00:00

Or run fewer parcels per array job:
qsub -J 1-100 pbs_scripts/pbs_hyperalignment_array.sh  # First batch
qsub -J 101-200 pbs_scripts/pbs_hyperalignment_array.sh  # Second batch
```

### Data Access Issues

**Problem**: "Permission denied" accessing data

```
Solution: Ensure Singularity can access bound directories
Check file permissions on cluster
Some clusters require additional bind options:
--bind ${DATA_ROOT}:/data:rw  # Explicitly allow read-write
```

**Problem**: Files not found even though path seems correct

```
Solution: Paths inside container differ from cluster paths
Cluster: /scratch/user/data/HBN_CIFTI/file.nii
Container: /data/HBN_CIFTI/file.nii

Update config.sh to use /data/ prefix for containerized runs
Or adjust bind mounts in PBS scripts
```

### Output Issues

**Problem**: Logs are empty or not created

```
Solution:
1. Ensure logs directory exists: mkdir -p logs
2. Check PBS_O_WORKDIR is correct in PBS script
3. Use absolute path for log directory:
   #PBS -o /full/path/to/logs/job_${PBS_JOBID}.log
```

**Problem**: Output files created but empty

```
Solution: Check actual error messages in log files
Common causes:
- Input data not found (check paths)
- Insufficient memory (check memory usage)
- Missing dependencies (rebuild container)
```

---

## Performance Tips

### Optimizing Resource Usage

1. **CPU cores**: Match `N_JOBS` to `ncpus` in PBS header
   ```bash
   #PBS -l select=1:ncpus=24
   export N_JOBS=24
   ```

2. **Memory**: Hyperalignment is memory-intensive
   - Start with 128GB for typical datasets
   - Monitor with `qstat -f JOBID | grep mem`
   - Increase if jobs fail with OOM errors

3. **Walltime**: Typical times per parcel
   - Parcellation: ~15-30 seconds per subject
   - Hyperalignment: 30 minutes to 2 hours per parcel
   - Connectomes: Several hours for all subjects

4. **Parallelization strategy**:
   - Parcellation: Single job, parallel within (N_JOBS)
   - Hyperalignment: Array job across parcels (360 jobs)
   - Connectomes: Single job, parallel within (N_JOBS)

### Disk I/O Optimization

1. Use fast scratch storage for intermediate files
2. Avoid network file systems for heavy I/O operations
3. Consider local node storage if available:
   ```bash
   #PBS -l select=1:ncpus=24:mem=128gb:scratch_local=100gb
   ```

---

## Advanced Usage

### Custom Python Scripts

To run custom Python scripts in the container:

```bash
# Python 3
singularity exec hyperalignment.sif python3 /workspace/my_script.py

# Python 2
singularity exec hyperalignment.sif python2 /workspace/my_analysis.py
```

### Installing Additional Packages

If you need additional Python packages:

1. Edit `Dockerfile` to add them:
   ```dockerfile
   RUN pip3 install additional-package==1.0.0
   ```

2. Rebuild image:
   ```bash
   ./docker-build.sh
   ```

3. Reconvert to Singularity:
   ```bash
   ./docker-to-singularity.sh
   ```

### Using with Other Job Schedulers

The scripts can be adapted for SLURM or other schedulers:

**SLURM equivalent headers**:
```bash
#!/bin/bash
#SBATCH --job-name=hyperalign
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=24
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=logs/hyperalignment_%A_%a.log
#SBATCH --array=1-360

# Use $SLURM_ARRAY_TASK_ID instead of $PBS_ARRAY_INDEX
PARCEL=$SLURM_ARRAY_TASK_ID
```

---

## Contact and Support

For issues specific to:
- Docker/Singularity: Check official documentation
- PBS cluster: Contact your cluster administrator
- Pipeline code: Create an issue in the repository

---

## Appendix: File Inventory

### Docker-related files
- `Dockerfile` - Container definition
- `.dockerignore` - Files excluded from build context
- `docker-build.sh` - Build script
- `docker-run.sh` - Local run script
- `docker-to-singularity.sh` - Conversion script

### PBS scripts
- `pbs_scripts/pbs_parcellation.sh` - Parcellation job
- `pbs_scripts/pbs_hyperalignment_single.sh` - Single parcel hyperalignment
- `pbs_scripts/pbs_hyperalignment_array.sh` - Array job for all parcels
- `pbs_scripts/pbs_build_connectomes.sh` - Connectome building
- `pbs_scripts/submit_pipeline.sh` - Interactive submission helper

### Configuration
- `hyperalignment_scripts/config.sh` - Centralized parameters
- `hyperalignment_scripts/read_config.py` - Config reader (Python 2/3)

### Documentation
- `README.md` - Main project documentation
- `hyperalignment_scripts/CONFIG_README.md` - Configuration system docs
- `DOCKER_PBS_README.md` - This file
