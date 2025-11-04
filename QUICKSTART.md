# Quick Start Guide - PBS Cluster

This is a condensed guide to get the hyperalignment pipeline running on your PBS cluster quickly.

## Prerequisites

- Access to a PBS cluster with Singularity/Apptainer
- Your data organized in the expected directory structure
- The `hyperalignment.sif` Singularity image

## 5-Minute Setup

### 1. Build Container (on local machine or cluster)

```bash
# Build Docker image
./docker-build.sh

# Convert to Singularity
./docker-to-singularity.sh
# Or on cluster: singularity build hyperalignment.sif docker-daemon://hyperalignment:latest
```

### 2. Transfer to Cluster

```bash
# Transfer image and scripts
scp hyperalignment.sif your-cluster:/project/hyperalignment/
scp -r pbs_scripts your-cluster:/project/hyperalignment/
```

### 3. Configure PBS Scripts

On the cluster, edit `pbs_scripts/*.sh` and change:

```bash
DATA_ROOT="/path/to/your/data"  # Change to your data path
```

### 4. Prepare Data

Ensure data structure:
```
$DATA_ROOT/
├── HBN_CIFTI/              # Your dtseries files here
├── hyperalignment_input/   # Will be created
├── connectomes/            # Will be created
└── diagnosis_summary/      # Your CSV files here
```

### 5. Submit Jobs

```bash
cd /project/hyperalignment
export DATA_ROOT=/scratch/username/HBN_data

# Submit everything interactively
./pbs_scripts/submit_pipeline.sh

# Or submit manually:
qsub pbs_scripts/pbs_parcellation.sh
qsub pbs_scripts/pbs_hyperalignment_array.sh
qsub pbs_scripts/pbs_build_connectomes.sh
```

### 6. Monitor

```bash
# Check job status
qstat -u $USER

# Watch logs
tail -f logs/hyperalignment_parcel_1_*.log
```

## Expected Runtime

- Parcellation: 2-4 hours (depends on number of subjects)
- Hyperalignment: 30 min - 2 hours per parcel
  - All 360 parcels in parallel: ~2-4 hours total
- Connectomes: 12-24 hours

## Common Adjustments

### Run fewer parcels
```bash
# Just first 50 parcels
qsub -J 1-50 pbs_scripts/pbs_hyperalignment_array.sh
```

### Increase resources
Edit PBS script headers:
```bash
#PBS -l select=1:ncpus=32:mem=256gb  # More CPUs/memory
#PBS -l walltime=48:00:00             # More time
```

### Use less parallelism (if running out of memory)
```bash
export N_JOBS=12  # Reduce from 24
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Job fails immediately | Check `SINGULARITY_IMAGE` and `DATA_ROOT` paths |
| Python 2 not found | Rebuild container with `./docker-build.sh` |
| Out of memory | Increase `mem=` in PBS header or reduce `N_JOBS` |
| Walltime exceeded | Increase `walltime=` in PBS header |
| Files not found | Check data directory structure and paths |

## File Locations After Completion

```
$DATA_ROOT/
├── connectomes/
│   ├── fine/                        # Per-parcel connectomes
│   │   └── parcel_001/
│   │       ├── sub-XXX_full_connectome_parcel_001.npy
│   │       └── ...
│   └── hyperalignment_output/       # Hyperalignment results
│       ├── mappers/                 # Learned transformations
│       └── aligned_timeseries/      # Aligned data
└── hyperalignment_input/
    └── glasser_ptseries/            # Parcellated data
        └── sub-XXX/
            └── sub-XXX_run-1_glasser.ptseries.nii
```

## Next Steps

- See `DOCKER_PBS_README.md` for detailed documentation
- See `hyperalignment_scripts/CONFIG_README.md` for configuration options
- Check logs in `logs/` directory for any errors

## Get Help

1. Check log files: `logs/`
2. Test container locally: `./docker-run.sh`
3. Review full documentation: `DOCKER_PBS_README.md`
4. Contact cluster support for PBS-specific issues
