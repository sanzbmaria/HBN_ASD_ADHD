# Configuration Guide

This guide explains how to configure the hyperalignment pipeline for different machines and use cases.

## Table of Contents

1. [Configuration Priority](#configuration-priority)
2. [Running Full vs Split Connectomes](#running-full-vs-split-connectomes)
3. [Machine-Specific Configuration](#machine-specific-configuration)
4. [Full Pipeline Usage](#full-pipeline-usage)
5. [Examples](#examples)

---

## Configuration Priority

The pipeline uses a **three-tier configuration system** with the following priority order:

```
Environment Variables > config.sh > Defaults
```

### 1. Environment Variables (Highest Priority)
Set via Docker's `-e` flag or `export` command:
```bash
docker run -e N_JOBS=32 -e BASE_OUTDIR=/data/my_output ...
```

### 2. config.sh (Middle Priority)
Default configuration file in `hyperalignment_scripts/config.sh`

### 3. Hard-coded Defaults (Lowest Priority)
Built into the code as fallback values

---

## Running Full vs Split Connectomes

### Why Separate Full and Split?

- **Full connectomes**: Use all timepoints, computationally expensive
- **Split connectomes**: Use half timepoints each, can run in parallel on separate machines
- Running separately allows distributing work across multiple machines

### AA Connectomes (Anatomical)

```bash
# Build only full connectomes (for one machine)
docker run ... python3 build_aa_connectomes.py --mode full

# Build only split connectomes (for another machine)
docker run ... python3 build_aa_connectomes.py --mode split

# Build both (default, single machine with lots of resources)
docker run ... python3 build_aa_connectomes.py --mode both
```

### CHA Connectomes (Hyperaligned)

```bash
# Build only full connectomes
docker run ... python3 build_CHA_connectomes.py --mode full

# Build only split connectomes
docker run ... python3 build_CHA_connectomes.py --mode split

# Build both (default)
docker run ... python3 build_CHA_connectomes.py --mode both
```

---

## Machine-Specific Configuration

### Option 1: Environment Variables (Recommended)

**Advantages:**
- No need to edit config.sh
- Easy to run on different machines
- No git conflicts

**Example: Running on a high-memory server**
```bash
export DATA_ROOT=/mnt/bigdata/fmri
export N_JOBS=48
export POOL_NUM=48
export BASE_OUTDIR=/data/connectomes_48cores

./full_pipeline.sh
```

**Example: Running on a machine with limited memory**
```bash
export DATA_ROOT=/data/fmri
export N_JOBS=16
export POOL_NUM=16

./full_pipeline.sh
```

### Option 2: Edit config.sh

**Only do this if:**
- You're the only user
- You won't be pulling updates frequently
- You want permanent machine-specific settings

**Steps:**
1. Copy config.sh to config.local.sh:
   ```bash
   cp hyperalignment_scripts/config.sh hyperalignment_scripts/config.local.sh
   ```

2. Edit config.local.sh with your paths

3. Add to .gitignore:
   ```bash
   echo "hyperalignment_scripts/config.local.sh" >> .gitignore
   ```

4. Symlink it:
   ```bash
   cd hyperalignment_scripts
   ln -sf config.local.sh config.sh
   ```

---

## Full Pipeline Usage

### Basic Usage

```bash
export DATA_ROOT=/path/to/your/data
./full_pipeline.sh
```

This runs all 4 steps:
1. Parcellation (dtseries → ptseries)
2. Build AA Connectomes (training data)
3. Hyperalignment (360 parcels)
4. Build CHA Connectomes (hyperaligned data)

### Selective Steps

Skip completed steps:
```bash
export DATA_ROOT=/path/to/your/data
export RUN_PARCELLATION=no
export RUN_BUILD_AA_CONNECTOMES=no
export RUN_HYPERALIGNMENT=yes
export RUN_CHA_CONNECTOMES=yes

./full_pipeline.sh
```

### Separate Full and Split Processing

**Machine 1: Process full connectomes**
```bash
export DATA_ROOT=/mnt/server1/fmri
export N_JOBS=32
export AA_CONNECTOME_MODE=full
export CHA_CONNECTOME_MODE=full

./full_pipeline.sh
```

**Machine 2: Process split connectomes**
```bash
export DATA_ROOT=/mnt/server2/fmri
export N_JOBS=32
export AA_CONNECTOME_MODE=split
export CHA_CONNECTOME_MODE=split

./full_pipeline.sh
```

---

## Examples

### Example 1: PBS Cluster with 24 cores, 128GB RAM

```bash
#!/bin/bash
#PBS -l nodes=1:ppn=24,mem=128gb,walltime=48:00:00

cd $PBS_O_WORKDIR

export DATA_ROOT=/scratch/user/fmri_data
export N_JOBS=24
export POOL_NUM=24
export AA_CONNECTOME_MODE=both
export CHA_CONNECTOME_MODE=both

./full_pipeline.sh
```

### Example 2: Two machines splitting work

**Server 1 (High memory, full connectomes)**
```bash
export DATA_ROOT=/data/shared_fmri
export N_JOBS=48
export AA_CONNECTOME_MODE=full
export CHA_CONNECTOME_MODE=full
export RUN_HYPERALIGNMENT=no  # Skip hyperalignment on this machine

./full_pipeline.sh
```

**Server 2 (Moderate memory, split connectomes + hyperalignment)**
```bash
export DATA_ROOT=/data/shared_fmri
export N_JOBS=24
export AA_CONNECTOME_MODE=split
export CHA_CONNECTOME_MODE=split
export RUN_PARCELLATION=no  # Already done on server 1

./full_pipeline.sh
```

### Example 3: Mac local testing

```bash
export DATA_ROOT=/Volumes/home/FMRI/data/test_HBN_CIFTI
export N_JOBS=8
export N_TEST_SUBJECTS=5
export RUN_BUILD_AA_CONNECTOMES=yes
export RUN_HYPERALIGNMENT=no  # Too slow for local testing
export RUN_CHA_CONNECTOMES=no

./test_pipeline.sh
```

### Example 4: Ubuntu server with custom paths

```bash
export DATA_ROOT=/mnt/storage/projects/hyperalignment
export DTSERIES_ROOT=/data/HBN_CIFTI
export PTSERIES_ROOT=/data/output/ptseries
export BASE_OUTDIR=/data/output/connectomes
export N_JOBS=32

./full_pipeline.sh
```

---

## Available Configuration Variables

### Resource Configuration
- `N_JOBS`: Number of parallel jobs (default: 24)
- `POOL_NUM`: Multiprocessing pool size (default: 24)

### Path Configuration
- `DATA_ROOT`: Host directory to mount (required)
- `DTSERIES_ROOT`: Input dtseries directory (default: /data/HBN_CIFTI)
- `PTSERIES_ROOT`: Output ptseries directory (default: /data/hyperalignment_input/glasser_ptseries)
- `BASE_OUTDIR`: Output directory for connectomes (default: /data/connectomes)

### Pipeline Control
- `RUN_PARCELLATION`: yes/no (default: yes)
- `RUN_BUILD_AA_CONNECTOMES`: yes/no (default: yes)
- `RUN_HYPERALIGNMENT`: yes/no (default: yes)
- `RUN_CHA_CONNECTOMES`: yes/no (default: yes)

### Connectome Mode
- `AA_CONNECTOME_MODE`: full/split/both (default: both)
- `CHA_CONNECTOME_MODE`: full/split/both (default: both)
- `HYPERALIGNMENT_MODE`: full/split (default: full)

### Data Configuration
- `VERTICES_IN_BOUNDS`: Number of vertices (default: 59412)
- `N_PARCELS`: Number of parcels (default: 360)

---

## Quick Reference

### I want to...

**Run the full pipeline with default settings:**
```bash
export DATA_ROOT=/path/to/data
./full_pipeline.sh
```

**Use 48 cores instead of 24:**
```bash
export N_JOBS=48 POOL_NUM=48
./full_pipeline.sh
```

**Build only full connectomes (skip split):**
```bash
export AA_CONNECTOME_MODE=full CHA_CONNECTOME_MODE=full
./full_pipeline.sh
```

**Resume from hyperalignment (parcellation already done):**
```bash
export RUN_PARCELLATION=no RUN_BUILD_AA_CONNECTOMES=no
./full_pipeline.sh
```

**Test with 10 subjects:**
```bash
export N_TEST_SUBJECTS=10
./test_pipeline.sh
```

**Split work across two machines:**
```bash
# Machine 1:
export AA_CONNECTOME_MODE=full CHA_CONNECTOME_MODE=full
./full_pipeline.sh

# Machine 2:
export AA_CONNECTOME_MODE=split CHA_CONNECTOME_MODE=split
./full_pipeline.sh
```

---

## Troubleshooting

### Config not being recognized

**Problem:** Changed config.sh but Docker still uses old values

**Solution:** Rebuild Docker image:
```bash
./docker-build.sh
```

### Different paths on different machines

**Problem:** Mac uses `/Volumes/...`, server uses `/mnt/...`

**Solution:** Use environment variables, don't edit config.sh:
```bash
# Mac
export DATA_ROOT=/Volumes/home/FMRI/data
./full_pipeline.sh

# Server
export DATA_ROOT=/mnt/storage/fmri/data
./full_pipeline.sh
```

### Git conflicts with config.sh

**Problem:** `git pull` shows conflicts in config.sh

**Solution:** Use environment variables instead of editing config.sh:
```bash
git checkout -- hyperalignment_scripts/config.sh
git pull
export N_JOBS=32  # Set your custom values
./full_pipeline.sh
```
