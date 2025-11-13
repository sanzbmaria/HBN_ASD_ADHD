# Hyperalignment Pipeline for fMRI Connectomes

A flexible Docker-based pipeline for hyperalignment and connectome analysis of CIFTI dtseries data. Originally developed for HBN ASD/ADHD data but easily adaptable to other datasets.

## Quick Start

### 1. Build Docker Image
```bash
./docker-build.sh
```

### 2. Test with Sample Subjects
```bash
export DATA_ROOT=/path/to/your/data
./test_pipeline.sh
```

### 3. Run Full Pipeline
```bash
# Run on all subjects (uses local_scripts/run_full_pipeline.sh internally)
export DATA_ROOT=/path/to/your/data
./local_scripts/run_full_pipeline.sh

# Or run specific steps:
./local_scripts/run_parcellation.sh
./local_scripts/run_hyperalignment_parallel.sh
./local_scripts/run_build_connectomes.sh
```

## What This Pipeline Does

```
Raw CIFTI dtseries files (*.dtseries.nii)
    ↓
[1] Parcellation
    → Applies Glasser atlas using Connectome Workbench
    → Creates parcellated timeseries (*.ptseries.nii)
    ↓
[2] Anatomically-Aligned (AA) Connectomes
    → Builds connectivity matrices before hyperalignment
    ↓
[3] Hyperalignment
    → Uses PyMVPA2 to learn subject-to-template transformations
    → Processes each parcel independently (360 parcels)
    → Creates aligned timeseries
    ↓
[4] Connectome-Hyperaligned (CHA) Connectomes
    → Builds connectivity matrices after hyperalignment
    ↓
Output: Connectivity matrices (.npy files)
```

## Directory Structure

### Project Structure
```
HBN_ASD_ADHD/
├── docker-build.sh                  # Build Docker image
├── docker-run.sh                    # Interactive Docker shell
├── test_pipeline.sh                 # Test with sample subjects
│
├── local_scripts/                   # Execution scripts
│   ├── run_full_pipeline.sh         # Run entire pipeline
│   ├── run_parcellation.sh          # Step 1: Parcellation
│   ├── run_hyperalignment_parallel.sh  # Step 2: Hyperalignment
│   └── run_build_connectomes.sh     # Step 3: Build connectomes
│
└── hyperalignment_scripts/          # Pipeline code
    ├── config.sh                    # ⚙️ MAIN CONFIG FILE ⚙️
    ├── read_config.py               # Config reader (Python 2/3)
    ├── organize_subjects.py         # Subject selection from Excel
    ├── apply_parcellation.sh        # Parcellation
    ├── run_hyperalignment.py        # Hyperalignment (Python 2)
    ├── build_aa_connectomes.py      # AA connectomes (Python 3)
    └── build_CHA_connectomes.py     # CHA connectomes (Python 3)
```

### Data Directory Structure
Your data directory (mounted at `/data` in the container) should be organized as:

```
/path/to/your/data/
├── HBN_CIFTI/                       # Input dtseries files
│   ├── sub-XXXXX_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   └── ...
│
├── HBN_ASD_ADHD.xlsx                # Subject metadata (optional)
│
├── hyperalignment_input/            # Created by pipeline
│   └── glasser_ptseries/
│
└── connectomes/                     # Created by pipeline
    ├── fine/                        # Connectivity matrices
    └── hyperalignment_output/       # Aligned timeseries
```

## Configuration

All configuration is centralized in **`hyperalignment_scripts/config.sh`**.

### Key Configuration Sections

#### Processing Parameters
```bash
POOL_NUM=24                          # Number of parallel jobs
N_JOBS=24                            # Number of CPU cores
N_PARCELS=360                        # Number of parcels (Glasser atlas)
```

#### Directory Paths (inside Docker container)
```bash
DTSERIES_ROOT="/data/HBN_CIFTI/"     # Input dtseries files
PTSERIES_ROOT="/data/hyperalignment_input/glasser_ptseries/"
BASE_OUTDIR="/data/connectomes"
```

#### File Naming Patterns
```bash
DTSERIES_FILENAME_TEMPLATE="{subj}_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"
DTSERIES_FILENAME_PATTERN="*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii"
```

#### Subject Selection (for organize_subjects.py)
```bash
METADATA_EXCEL="/data/HBN_ASD_ADHD.xlsx"
SUBJECT_ID_COL="EID"                 # Column with subject IDs
SITE_COL="SITE"                      # Site/scanner column
SEX_COL="Sex"                        # Sex/gender column
AGE_COL="Age"                        # Age column
MOTION_COL="MeanFD"                  # Motion metric column

# Columns used for grouping (e.g., diagnosis)
SELECTION_COL_1="ASD"
SELECTION_COL_2="ADHD"
SELECTION_COL_3="ASD+ADHD"

TRAIN_FRACTION=0.25                  # Fraction for hyperalignment training
CV_FOLDS=5                           # Cross-validation folds

# Stratification for train/test split
STRATIFY_BY_SITE=true
STRATIFY_BY_SEX=true
STRATIFY_BY_AGE=true
STRATIFY_BY_MOTION=true
```

### Environment Variable Overrides
You can override any config.sh setting with environment variables:
```bash
export N_JOBS=8                      # Override parallelization
export DATA_ROOT=/my/data            # Override data location
export START_PARCEL=1                # Run subset of parcels
export END_PARCEL=10
./local_scripts/run_hyperalignment_parallel.sh
```

## Adapting to Your Dataset

This pipeline can be adapted to other datasets in three ways:

### Option 1: Update config.sh (Recommended)
For basic adaptations (different column names, file patterns, paths):
1. Edit `hyperalignment_scripts/config.sh`
2. Update paths, column names, and file patterns
3. Run the pipeline

### Option 2: Customize organize_subjects.py
For different subject selection criteria:
1. Edit `hyperalignment_scripts/config.sh` - update column names
2. Edit `hyperalignment_scripts/organize_subjects.py` - modify the `derive_dx_row()` function (~line 178-202) to match your grouping logic
3. Run `python organize_subjects.py` to generate subject lists

Example for a Control/Patient study:
```python
def derive_dx_row(row):
    if row["_sel01_1"] == 1:
        return "Patient"
    else:
        return "Control"
```

### Option 3: Provide Subject Lists Directly
Skip organize_subjects.py entirely:
1. Create your own subject lists: `cha_train.csv`, `test_pool.csv`
2. Or use `TEST_SUBJECTS_LIST` environment variable:
```bash
export TEST_SUBJECTS_LIST="sub-001 sub-002 sub-003"
```

## Common Use Cases

### Test with auto-selected subjects
```bash
export DATA_ROOT=/path/to/your/data
./test_pipeline.sh
```
Automatically selects 5 subjects and runs 3 test parcels.

### Test with specific subjects
```bash
export DATA_ROOT=/path/to/your/data
export TEST_SUBJECTS="sub-NDARAA123 sub-NDARAA456"
./test_pipeline.sh
```

### Run full pipeline on all subjects
```bash
export DATA_ROOT=/path/to/your/data
./local_scripts/run_full_pipeline.sh
```

### Run specific parcel range
```bash
export DATA_ROOT=/path/to/your/data
export START_PARCEL=1
export END_PARCEL=50
./local_scripts/run_hyperalignment_parallel.sh
```

### Run single parcel for debugging
```bash
export DATA_ROOT=/path/to/your/data
./local_scripts/run_hyperalignment_single.sh 1 full
# Arguments: <parcel_number> <mode: full|split|both>
```

### Interactive Docker session
```bash
export DATA_ROOT=/path/to/your/data
./docker-run.sh
# Opens bash shell inside container for manual testing
```

## Resource Requirements

- **CPU**: 4+ cores (more is better for parallel processing)
- **RAM**: 16GB minimum, 32GB+ recommended
- **Disk**: 50GB+ free space
- **Time**: Depends on number of subjects and parcels
  - Test mode (5 subjects, 3 parcels): ~30 minutes
  - Full run (all subjects, all 360 parcels): Several days

## Pipeline Components

### 1. Parcellation
- **Script**: `apply_parcellation.sh`
- **Tool**: Connectome Workbench `wb_command`
- **Input**: dtseries files
- **Output**: ptseries files (parcellated timeseries)
- **Atlas**: Glasser 360-parcel atlas

### 2. Hyperalignment
- **Script**: `run_hyperalignment.py`
- **Dependencies**: Python 2.7 + PyMVPA2
- **Method**: Learns subject-to-template transformations per parcel
- **Modes**:
  - `full`: Use all data for alignment
  - `split`: Split data into two halves
  - `both`: Run both full and split modes
- **Output**: Aligned timeseries + transformation mappers

### 3. Connectome Building
- **Scripts**:
  - `build_aa_connectomes.py` - Before hyperalignment
  - `build_CHA_connectomes.py` - After hyperalignment
- **Dependencies**: Python 3.8 + scipy
- **Method**: Correlation-based connectivity matrices
- **Output**: Numpy arrays (.npy) with connectivity matrices

## Docker Container

The container includes:
- **Python 2.7**: For PyMVPA2 hyperalignment
- **Python 3.8**: For connectome analysis
- **PyMVPA2**: Hyperalignment algorithm
- **Connectome Workbench**: CIFTI processing (`wb_command`)
- **Scientific Stack**: numpy, scipy, nibabel, pandas, scikit-learn, openpyxl

## Troubleshooting

### Docker build fails
```bash
# Clear Docker cache and rebuild
docker system prune -a
./docker-build.sh
```

### "No subjects found" error
- Check `DATA_ROOT` points to correct directory
- Verify dtseries files match pattern in config.sh
- Check file naming: `sub-*_task-rest_*.dtseries.nii`

### "Config not found" error
```bash
# Ensure you're running from project root
cd /path/to/HBN_ASD_ADHD
./test_pipeline.sh
```

### Memory errors during hyperalignment
- Reduce `N_JOBS` in config.sh
- Run fewer parcels at once (use START_PARCEL/END_PARCEL)
- Increase Docker memory limit (Docker Desktop settings)

### Permission errors
```bash
# Fix permissions on data directory
sudo chmod -R 755 /path/to/your/data
```

## Validation

The pipeline includes automatic validation:
- ✓ Checks for required input files
- ✓ Verifies parcellation outputs
- ✓ Validates hyperalignment mappers
- ✓ Confirms connectome matrices are created
- ✓ Reports detailed statistics

Validation results are shown at the end of `test_pipeline.sh`.

## Features

- ✅ **Centralized Configuration**: Single `config.sh` for all parameters
- ✅ **Flexible Dataset Support**: Easy to adapt to different datasets
- ✅ **Dual Python Support**: Python 2 (hyperalignment) + Python 3 (analysis)
- ✅ **Test Mode**: Test with subset of subjects before full run
- ✅ **Resume Capability**: Pipeline can resume from interruptions
- ✅ **Parallel Processing**: Optimized for multi-core systems
- ✅ **Comprehensive Logging**: Detailed logs for debugging
- ✅ **Automatic Validation**: Checks outputs at each stage

## Citation

If you use this pipeline, please cite:
- **PyMVPA2** for hyperalignment methodology
- **Glasser et al. (2016)** for the 360-parcel atlas
- **HCP Workbench** for CIFTI processing tools
- **Healthy Brain Network (HBN)** if using HBN data

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs in `logs/` directory
3. Test with `./test_pipeline.sh` to isolate problems
4. Open an issue on the repository with:
   - Error messages from logs
   - Output of `./test_pipeline.sh`
   - Your config.sh settings (redact sensitive paths)

---

**Quick Reference**
```bash
# Build                    → ./docker-build.sh
# Test                     → ./test_pipeline.sh
# Full run                 → ./local_scripts/run_full_pipeline.sh
# Interactive shell        → ./docker-run.sh
# Configuration            → hyperalignment_scripts/config.sh
```
