# Local Execution Guide - Mac and Ubuntu

This guide explains how to run the hyperalignment pipeline locally on your Mac or Ubuntu server using Docker.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Step-by-Step Execution](#step-by-step-execution)
4. [Resource Requirements](#resource-requirements)
5. [Troubleshooting](#troubleshooting)
6. [Advanced Usage](#advanced-usage)

---

## Prerequisites

### Mac (macOS)

1. **Docker Desktop**: [Download and install](https://www.docker.com/products/docker-desktop)
   - Minimum version: 4.0+
   - Allocate sufficient resources in Docker Desktop preferences:
     - **CPUs**: At least 4-8 cores (more is better)
     - **Memory**: At least 16GB (32GB+ recommended for hyperalignment)
     - **Disk**: 50GB+ free space

2. **Verify installation**:
   ```bash
   docker --version
   docker info
   ```

### Ubuntu Server

1. **Docker Engine**: Install following [official guide](https://docs.docker.com/engine/install/ubuntu/)

   ```bash
   # Quick install
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh

   # Add your user to docker group (to avoid using sudo)
   sudo usermod -aG docker $USER
   newgrp docker
   ```

2. **Verify installation**:
   ```bash
   docker --version
   docker info
   ```

### Common Requirements

- **Disk space**: At least 50GB free
  - Docker image: ~5GB
  - Input data: Varies
  - Output data: ~2-3x input data size
- **RAM**: 16GB minimum, 32GB+ recommended
- **CPU**: 4+ cores (8+ cores recommended)

---

## Quick Start

### 1. Build the Docker Image

```bash
# Clone the repository
git clone https://github.com/sanzbmaria/HBN_ASD_ADHD.git
cd HBN_ASD_ADHD

# Build Docker image (takes 5-10 minutes)
./docker-build.sh
```

### 2. Prepare Your Data

Organize your data directory:

```
/path/to/your/data/
├── HBN_CIFTI/                          # Your dtseries files here
│   ├── sub-NDARAA123_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   ├── sub-NDARAA456_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   └── ...
├── diagnosis_summary/                  # Subject metadata (optional)
│   └── matched_subjects_diagnosis_mini.csv
├── hyperalignment_input/               # Will be created automatically
└── connectomes/                        # Will be created automatically
```

### 3. Set Your Data Path

```bash
# Set the path to your data directory
export DATA_ROOT=/path/to/your/data

# For example on Mac:
export DATA_ROOT=/Users/maria/Documents/HBN_data

# For example on Ubuntu:
export DATA_ROOT=/home/maria/HBN_data
```

### 4. Run the Full Pipeline

```bash
# Run everything (parcellation → hyperalignment → connectomes)
./local_scripts/run_full_pipeline.sh
```

**That's it!** The pipeline will run all steps automatically.

---

## Step-by-Step Execution

If you prefer to run steps individually or want more control:

### Step 1: Parcellation

Apply Glasser parcellation to your dtseries files:

```bash
export DATA_ROOT=/path/to/your/data
export N_JOBS=8  # Adjust based on your CPU cores

./local_scripts/run_parcellation.sh
```

**Output**: Creates `.ptseries.nii` files in `$DATA_ROOT/hyperalignment_input/glasser_ptseries/`

**Time**: ~30 seconds per subject (depends on N_JOBS)

### Step 2: Hyperalignment

#### Option A: Single Parcel (for testing)

```bash
export DATA_ROOT=/path/to/your/data

# Run hyperalignment for parcel 1 (full mode)
./local_scripts/run_hyperalignment_single.sh 1 full

# Run hyperalignment for parcel 180 (both full and split)
./local_scripts/run_hyperalignment_single.sh 180 both
```

#### Option B: Multiple Parcels in Parallel

```bash
export DATA_ROOT=/path/to/your/data

# Run first 10 parcels
export START_PARCEL=1
export END_PARCEL=10
export MAX_PARALLEL=2      # Run 2 parcels at a time
export N_JOBS=4            # Use 4 cores per parcel
./local_scripts/run_hyperalignment_parallel.sh

# Or run all 360 parcels (WARNING: This takes a long time!)
export START_PARCEL=1
export END_PARCEL=360
export MAX_PARALLEL=4      # Run 4 parcels simultaneously
export N_JOBS=4            # Use 4 cores per parcel
./local_scripts/run_hyperalignment_parallel.sh
```

**Output**:
- Aligned timeseries in `$DATA_ROOT/connectomes/hyperalignment_output/aligned_timeseries/`
- Transformation mappers in `$DATA_ROOT/connectomes/hyperalignment_output/mappers/`

**Time**: 30 minutes to 2 hours per parcel (depends on data size and N_JOBS)

### Step 3: Build Connectomes

```bash
export DATA_ROOT=/path/to/your/data
export N_JOBS=8

# Build anatomical connectomes
./local_scripts/run_build_connectomes.sh build_aa_connectomes.py

# Or build CHA connectomes
./local_scripts/run_build_connectomes.sh build_CHA_connectomes.py
```

**Output**: Connectivity matrices in `$DATA_ROOT/connectomes/fine/`

**Time**: Several hours (depends on number of subjects and parcels)

---

## Resource Requirements

### Recommended Configurations

| Task | CPU Cores | RAM | Disk I/O | Notes |
|------|-----------|-----|----------|-------|
| Parcellation | 8 | 8GB | High | I/O bound, benefits from fast disk |
| Hyperalignment (single) | 8 | 16GB | Medium | CPU and RAM intensive |
| Hyperalignment (parallel) | 16+ | 32GB+ | Medium | RAM = 8-16GB per concurrent parcel |
| Connectomes | 8 | 16GB | High | CPU intensive, benefits from parallelization |

### Memory Considerations

**Hyperalignment is memory-intensive!** Each parcel can use 8-16GB of RAM.

**Safe configurations**:

| Your RAM | MAX_PARALLEL | N_JOBS per parcel | Total cores used |
|----------|--------------|-------------------|------------------|
| 16GB | 1 | 8 | 8 |
| 32GB | 2 | 8 | 16 |
| 64GB | 4 | 8 | 32 |
| 128GB | 8 | 8 | 64 |

**Example for 32GB Mac**:
```bash
export MAX_PARALLEL=2    # Run 2 parcels at a time
export N_JOBS=4          # Use 4 cores per parcel
export POOL_NUM=4
```

### Disk Space Requirements

Approximate sizes (varies by dataset):

- **Input data**: Your original dtseries files
- **Parcellated data**: ~10% of input size
- **Hyperalignment outputs**: ~2x input size
- **Connectomes**: ~1x input size
- **Total**: ~4x input data size

Example for 100 subjects with 1GB dtseries each:
- Input: 100GB
- Outputs: ~400GB total

---

## Full Pipeline Options

The `run_full_pipeline.sh` script supports extensive customization:

```bash
export DATA_ROOT=/path/to/your/data

# Run only specific steps
export RUN_PARCELLATION=yes       # yes or no
export RUN_HYPERALIGNMENT=yes     # yes or no
export RUN_CONNECTOMES=yes        # yes or no

# Hyperalignment configuration
export START_PARCEL=1             # First parcel to process
export END_PARCEL=360             # Last parcel to process
export MODE=both                  # full, split, or both
export MAX_PARALLEL=4             # Concurrent parcel jobs

# Resource allocation per step
export N_JOBS_PARCELLATION=8      # Cores for parcellation
export N_JOBS_HYPERALIGN=4        # Cores per hyperalignment job
export N_JOBS_CONNECTOMES=8       # Cores for connectome building

# Run the pipeline
./local_scripts/run_full_pipeline.sh
```

### Example: Test Run (First 5 Parcels)

```bash
export DATA_ROOT=/path/to/your/data
export START_PARCEL=1
export END_PARCEL=5
export MAX_PARALLEL=2
export N_JOBS_HYPERALIGN=4

./local_scripts/run_full_pipeline.sh
```

### Example: Production Run (All Parcels, Large Server)

```bash
export DATA_ROOT=/path/to/your/data
export START_PARCEL=1
export END_PARCEL=360
export MAX_PARALLEL=8
export N_JOBS_HYPERALIGN=4
export N_JOBS_PARCELLATION=16
export N_JOBS_CONNECTOMES=16

./local_scripts/run_full_pipeline.sh
```

---

## Troubleshooting

### Docker Issues

**Problem**: `docker: command not found`

```bash
# Mac: Install Docker Desktop
# Ubuntu: Install docker engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Problem**: `permission denied while trying to connect to the Docker daemon socket`

```bash
# Ubuntu only - add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Problem**: Docker Desktop on Mac shows "Docker Desktop is not running"

```
Solution: Start Docker Desktop from Applications folder
Wait for it to fully start (whale icon in menu bar should be stable)
```

### Resource Issues

**Problem**: Out of memory errors during hyperalignment

```bash
# Solution 1: Reduce MAX_PARALLEL
export MAX_PARALLEL=1  # Run only 1 parcel at a time

# Solution 2: Reduce N_JOBS
export N_JOBS=2
export POOL_NUM=2

# Solution 3: Increase Docker Desktop memory (Mac)
# Docker Desktop → Preferences → Resources → Memory
# Set to maximum available
```

**Problem**: Disk space errors

```bash
# Check disk space
df -h

# Clean up Docker (removes unused images/containers)
docker system prune -a

# Clean up old logs
rm -rf logs/
mkdir logs
```

**Problem**: "Too many open files" error

```bash
# Mac: Increase file descriptor limit
ulimit -n 4096

# Ubuntu: Edit /etc/security/limits.conf
# Add: * soft nofile 4096
#      * hard nofile 8192
```

### Performance Issues

**Problem**: Hyperalignment is very slow

```bash
# Solution 1: Increase N_JOBS (if you have spare CPU)
export N_JOBS=8

# Solution 2: Check if Docker Desktop has enough CPU allocated (Mac)
# Docker Desktop → Preferences → Resources → CPUs

# Solution 3: Use SSD for data storage (not network drive)
# Network drives are much slower

# Solution 4: Run fewer parcels in parallel but more cores per parcel
export MAX_PARALLEL=2
export N_JOBS=8
```

**Problem**: Parcellation is slow

```bash
# Solution 1: Increase parallelization
export N_JOBS=16

# Solution 2: Use local disk, not network storage
# Move data to local disk if currently on network drive

# Solution 3: Use SSD storage
# HDDs are significantly slower for CIFTI I/O
```

### Data Issues

**Problem**: "No matching dtseries files found"

```
Solution: Check your data directory structure
Ensure files match the pattern: *_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
Set BASEDIR explicitly if needed:
export BASEDIR=/path/to/HBN_CIFTI
```

**Problem**: "Directory not found" errors

```bash
# Verify DATA_ROOT is set correctly
echo $DATA_ROOT

# Check directory exists
ls -la $DATA_ROOT

# Check directory contains expected subdirectories
ls -la $DATA_ROOT/HBN_CIFTI/
```

**Problem**: Python 2 fails with import errors

```
Solution: Rebuild Docker image
./docker-build.sh

If still fails, check Dockerfile has correct PyMVPA2 installation
```

### Monitoring Progress

```bash
# View logs in real-time
tail -f logs/hyperalignment_parcel_1.log

# Check Docker containers
docker ps

# Check resource usage
docker stats

# On Mac: Use Activity Monitor to see Docker Desktop resource usage
# On Ubuntu: Use htop or top to monitor resources
```

---

## Advanced Usage

### Running on Specific Parcels

```bash
# Run just parcels 1, 50, 100, 150, 200
for parcel in 1 50 100 150 200; do
    ./local_scripts/run_hyperalignment_single.sh $parcel full
done
```

### Custom Python Scripts

Run your own Python scripts inside the container:

```bash
# Python 3
docker run --rm \
    -v "${DATA_ROOT}":/data \
    -v "$(pwd)":/workspace \
    -w /workspace \
    hyperalignment:latest \
    python3 my_analysis_script.py

# Python 2
docker run --rm \
    -v "${DATA_ROOT}":/data \
    -v "$(pwd)":/workspace \
    -w /workspace \
    hyperalignment:latest \
    python2 my_legacy_script.py
```

### Interactive Shell

Get an interactive shell in the container:

```bash
export DATA_ROOT=/path/to/your/data
./docker-run.sh

# Now you're inside the container
# You can run commands manually:
cd /app/hyperalignment_scripts
python2 run_hyperalignment.py 1 full
python3 build_aa_connectomes.py
exit
```

### Resuming After Interruption

The pipeline is resumable. If it stops:

**Parcellation**:
- Automatically skips files that already exist (unless `FORCE=1`)
- Can safely rerun

**Hyperalignment**:
- Check which parcels completed: `ls $DATA_ROOT/connectomes/hyperalignment_output/aligned_timeseries/parcel_*/`
- Resume from next parcel:
  ```bash
  export START_PARCEL=50  # If parcels 1-49 are done
  export END_PARCEL=360
  ./local_scripts/run_hyperalignment_parallel.sh
  ```

**Connectomes**:
- Scripts typically check for existing files
- Can safely rerun

### Batch Processing

Process data in batches to manage resources:

```bash
# Batch 1: Parcels 1-90
export START_PARCEL=1
export END_PARCEL=90
./local_scripts/run_hyperalignment_parallel.sh

# Batch 2: Parcels 91-180
export START_PARCEL=91
export END_PARCEL=180
./local_scripts/run_hyperalignment_parallel.sh

# Batch 3: Parcels 181-270
export START_PARCEL=181
export END_PARCEL=270
./local_scripts/run_hyperalignment_parallel.sh

# Batch 4: Parcels 271-360
export START_PARCEL=271
export END_PARCEL=360
./local_scripts/run_hyperalignment_parallel.sh
```

---

## Comparison: Local vs PBS Cluster

| Aspect | Local (Mac/Ubuntu) | PBS Cluster |
|--------|-------------------|-------------|
| **Setup** | Easy (just Docker) | More complex (Singularity conversion) |
| **Resources** | Limited by your machine | Virtually unlimited |
| **Parallelization** | Limited (4-8 parcels max) | Massive (360 parcels simultaneously) |
| **Speed** | Slower (days for all parcels) | Faster (hours for all parcels) |
| **Best for** | Testing, small datasets | Production, large datasets |
| **Cost** | Free (your hardware) | May have compute costs |
| **Monitoring** | Easy (your machine) | Need SSH access |

**Recommendation**:
- Use **local execution** for testing and small datasets (<10 subjects)
- Use **PBS cluster** for production and large datasets (>50 subjects)

---

## Performance Expectations

### On a 32GB MacBook Pro (8 cores)

```
Parcellation (100 subjects):
  - Configuration: N_JOBS=8
  - Time: ~1 hour

Hyperalignment (10 parcels):
  - Configuration: MAX_PARALLEL=2, N_JOBS=4
  - Time: ~4-8 hours

Hyperalignment (all 360 parcels):
  - Configuration: MAX_PARALLEL=2, N_JOBS=4
  - Time: ~5-7 days (running continuously)
```

### On Ubuntu Server (64GB, 32 cores)

```
Parcellation (100 subjects):
  - Configuration: N_JOBS=16
  - Time: ~30 minutes

Hyperalignment (all 360 parcels):
  - Configuration: MAX_PARALLEL=8, N_JOBS=4
  - Time: ~2-3 days
```

---

## Tips for Optimal Performance

1. **Use SSD storage** - CIFTI I/O is disk-intensive
2. **Allocate maximum RAM** to Docker (Mac: Docker Desktop preferences)
3. **Don't run other intensive tasks** while pipeline is running
4. **Monitor resource usage** to tune MAX_PARALLEL and N_JOBS
5. **Run test with 1-5 parcels** before full run
6. **Use `screen` or `tmux`** to keep pipeline running if SSH connection drops (Ubuntu)
7. **Back up your data** before running pipeline

---

## Getting Help

1. **Check logs**: `logs/` directory contains detailed output
2. **Test container**: `./docker-run.sh` for interactive debugging
3. **Verify data**: Ensure correct directory structure
4. **Check resources**: Monitor RAM/CPU usage with `docker stats`
5. **Review documentation**: See `DOCKER_PBS_README.md` for more details

---

## Summary of Scripts

| Script | Purpose | Use Case |
|--------|---------|----------|
| `run_parcellation.sh` | Apply Glasser parcellation | Step 1 of pipeline |
| `run_hyperalignment_single.sh` | Single parcel hyperalignment | Testing, specific parcels |
| `run_hyperalignment_parallel.sh` | Multiple parcels in parallel | Batch processing |
| `run_build_connectomes.sh` | Build connectivity matrices | Final step |
| `run_full_pipeline.sh` | Complete pipeline automation | Full production runs |

All scripts are in `local_scripts/` directory and work on both Mac and Ubuntu.
