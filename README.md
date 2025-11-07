# HBN ASD/ADHD Hyperalignment Pipeline

Hyperalignment pipeline for HBN (Healthy Brain Network) CIFTI dtseries data with support for both local execution (Mac/Ubuntu) and PBS cluster deployment.

## 🚀 Quick Start

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
# Local (Mac/Ubuntu)
./local_scripts/run_full_pipeline.sh

# PBS Cluster
./docker-to-singularity.sh
# Then follow PBS guide
```

## 📚 Documentation

Choose your path:

### 🔰 Getting Started
- **[BUILD_AND_TEST.md](BUILD_AND_TEST.md)** ← **START HERE**
  - How to build Docker image
  - How to test with small subset of subjects
  - Validation and troubleshooting

### 💻 Local Execution (Mac/Ubuntu)
- **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)**
  - Run pipeline on your Mac or Ubuntu server
  - Resource requirements and optimization
  - Step-by-step instructions

### ☁️ PBS Cluster Execution
- **[DOCKER_PBS_README.md](DOCKER_PBS_README.md)**
  - Convert Docker to Singularity
  - PBS job scripts
  - Cluster deployment guide

### ⚙️ Configuration
- **[hyperalignment_scripts/CONFIG_README.md](hyperalignment_scripts/CONFIG_README.md)**
  - Centralized configuration system
  - How to customize parameters

### ⚡ Quick Reference
- **[QUICKSTART.md](QUICKSTART.md)**
  - Quick command reference
  - Common configurations

## 🎯 What This Pipeline Does

```
Raw CIFTI dtseries files (*.dtseries.nii)
    ↓
[1] Parcellation (Glasser Atlas)
    → Creates parcellated timeseries (*.ptseries.nii)
    ↓
[2] Hyperalignment (Python 2 + PyMVPA2)
    → Learns alignment transformations
    → Creates aligned timeseries
    ↓
[3] Build Connectomes (Python 3)
    → Generates connectivity matrices
    ↓
Output: Connectivity matrices (.npy files)
```

## 🐳 Docker Container

The Docker container includes:
- **Python 2.7**: For PyMVPA2 hyperalignment
- **Python 3.8**: For connectome analysis
- **PyMVPA2**: Hyperalignment algorithm
- **Scientific Stack**: numpy, scipy, nibabel, pandas, scikit-learn
- **Connectome Workbench**: CIFTI processing tools

## 📂 Project Structure

```
HBN_ASD_ADHD/
├── Dockerfile                          # Container definition
├── docker-build.sh                     # Build Docker image
├── test_pipeline.sh                    # Test with sample subjects
│
├── local_scripts/                      # Local execution (Mac/Ubuntu)
│   ├── run_parcellation.sh
│   ├── run_hyperalignment_single.sh
│   ├── run_hyperalignment_parallel.sh
│   ├── run_build_connectomes.sh
│   └── run_full_pipeline.sh
│
├── pbs_scripts/                        # PBS cluster execution
│   ├── pbs_parcellation.sh
│   ├── pbs_hyperalignment_array.sh
│   ├── pbs_build_connectomes.sh
│   └── submit_pipeline.sh
│
├── hyperalignment_scripts/             # Pipeline code
│   ├── config.sh                       # Centralized configuration
│   ├── read_config.py                  # Config reader (Python 2/3)
│   ├── utils.py                        # Utility functions
│   ├── run_hyperalignment.py           # Hyperalignment (Python 2)
│   ├── build_aa_connectomes.py         # Build connectomes (Python 3)
│   ├── build_CHA_connectomes.py        # CHA connectomes (Python 3)
│   └── apply_parcellation.sh           # Parcellation script
│
└── Documentation/
    ├── BUILD_AND_TEST.md               # Build and test guide
    ├── LOCAL_EXECUTION_GUIDE.md        # Local execution guide
    ├── DOCKER_PBS_README.md            # PBS cluster guide
    ├── QUICKSTART.md                   # Quick reference
    └── CONFIG_README.md                # Configuration docs
```

## 🔧 Data Directory Structure

Your data should be organized as:

```
/path/to/your/data/
├── HBN_CIFTI/                          # Input dtseries files
│   ├── sub-NDARAA123_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   ├── sub-NDARAA456_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii
│   └── ...
│
├── diagnosis_summary/                  # Subject metadata (optional)
│   └── matched_subjects_diagnosis_mini.csv
│
├── hyperalignment_input/               # Created by pipeline
│   └── glasser_ptseries/
│
└── connectomes/                        # Created by pipeline
    ├── fine/                           # Connectivity matrices
    └── hyperalignment_output/          # Aligned timeseries + mappers
```

## 💡 Common Use Cases

### Test with 5 subjects (auto-selected)
```bash
export DATA_ROOT=/path/to/your/data
./test_pipeline.sh
```

### Test with specific subjects
```bash
export DATA_ROOT=/path/to/your/data
export TEST_SUBJECTS="sub-NDARAA123 sub-NDARAA456 sub-NDARAA789"
./test_pipeline.sh
```

### Run locally on first 10 parcels
```bash
export DATA_ROOT=/path/to/your/data
export START_PARCEL=1
export END_PARCEL=10
./local_scripts/run_hyperalignment_parallel.sh
```

### Run single parcel for testing
```bash
export DATA_ROOT=/path/to/your/data
./local_scripts/run_hyperalignment_single.sh 1 full
```

### Run full pipeline locally (all subjects, all parcels)
```bash
export DATA_ROOT=/path/to/your/data
./local_scripts/run_full_pipeline.sh
```

### Deploy to PBS cluster
```bash
# 1. Build and test locally first
./docker-build.sh
./test_pipeline.sh

# 2. Convert to Singularity
./docker-to-singularity.sh

# 3. Transfer to cluster
scp hyperalignment.sif your-cluster:/project/hyperalignment/
scp -r pbs_scripts your-cluster:/project/hyperalignment/

# 4. Submit on cluster
cd /project/hyperalignment
export DATA_ROOT=/scratch/username/HBN_data
./pbs_scripts/submit_pipeline.sh
```

## 🎓 Learning Path

1. **First Time Users**: Start with [BUILD_AND_TEST.md](BUILD_AND_TEST.md)
2. **Local Execution**: Read [LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)
3. **Cluster Execution**: Read [DOCKER_PBS_README.md](DOCKER_PBS_README.md)
4. **Customize Settings**: Read [CONFIG_README.md](hyperalignment_scripts/CONFIG_README.md)

## ⚙️ Features

- ✅ **Centralized Configuration**: Single `config.sh` for all parameters
- ✅ **Dual Python Support**: Python 2 (hyperalignment) + Python 3 (analysis)
- ✅ **Flexible Deployment**: Local (Docker) or Cluster (Singularity/PBS)
- ✅ **Test Mode**: Test with subset of subjects before full run
- ✅ **Resume Capability**: Pipeline can resume from interruptions
- ✅ **Parallel Processing**: Optimized for multi-core systems
- ✅ **Comprehensive Logging**: Detailed logs for debugging
- ✅ **Validation**: Automatic output validation

## 🔍 Resource Requirements

### Local Execution (Mac/Ubuntu)
- **CPU**: 4-8 cores minimum (more is better)
- **RAM**: 16GB minimum, 32GB+ recommended
- **Disk**: 50GB+ free space
- **Time**: Days for all 360 parcels

### PBS Cluster Execution
- **Per-job resources**: 24 CPUs, 128GB RAM, 24h walltime
- **Time**: Hours for all 360 parcels (with array jobs)

## 🐛 Troubleshooting

See the documentation for detailed troubleshooting:
- [BUILD_AND_TEST.md](BUILD_AND_TEST.md#troubleshooting)
- [LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md#troubleshooting)
- [DOCKER_PBS_README.md](DOCKER_PBS_README.md#troubleshooting)

## 📊 Pipeline Components

### Parcellation (`apply_parcellation.sh`)
- Uses Connectome Workbench `wb_command`
- Applies Glasser atlas to dtseries files
- Creates ptseries files

### Hyperalignment (`run_hyperalignment.py`)
- Python 2 + PyMVPA2
- Learns subject-to-template transformations
- Supports full and split-half modes
- Processes each parcel independently

### Connectomes (`build_aa_connectomes.py`, `build_CHA_connectomes.py`)
- Python 3 + scipy
- Builds connectivity matrices
- Multiple connectome types supported

## 🤝 Contributing

For issues or questions:
1. Check documentation in this repository
2. Review logs in `logs/` directory
3. Test with `./test_pipeline.sh`
4. Create an issue with details

## 📝 Citation

If you use this pipeline, please cite:
- PyMVPA2 for hyperalignment
- HCP Workbench for CIFTI processing
- Healthy Brain Network (HBN) for the dataset

## 📄 License

[Your License Here]

---

## Quick Command Reference

```bash
# Build
./docker-build.sh

# Test (5 subjects, 3 parcels)
export DATA_ROOT=/path/to/data
./test_pipeline.sh

# Test (specific subjects)
export TEST_SUBJECTS="sub-XXX sub-YYY sub-ZZZ"
./test_pipeline.sh

# Run locally (full pipeline)
./local_scripts/run_full_pipeline.sh

# Run locally (single parcel)
./local_scripts/run_hyperalignment_single.sh 1 full

# Convert for cluster
./docker-to-singularity.sh

# Interactive shell
./docker-run.sh
```

---

**Need help?** Start with [BUILD_AND_TEST.md](BUILD_AND_TEST.md) for step-by-step instructions!
