# Centralized Configuration

## Overview

All main parameters for the hyperalignment pipeline are now centralized in `config.sh`. This eliminates duplicate parameter definitions across Python 2, Python 3, and bash scripts.

## Files

- **config.sh**: Master configuration file with all parameters
- **read_config.py**: Python module that reads config.sh (works with Python 2 and Python 3)

## Configuration Parameters

### Processing Parameters
- `POOL_NUM`: Number of processes for multiprocessing pool (default: 24)
- `N_JOBS`: Number of parallel jobs (default: 24)
- `VERTICES_IN_BOUNDS`: Number of vertices in Glasser atlas (default: 59412)
- `N_PARCELS`: Number of parcels in atlas (default: 360)

### Directory Paths
- `DTSERIES_ROOT`: Location of input CIFTI dtseries files
- `PTSERIES_ROOT`: Location of output parcellated ptseries files
- `BASE_OUTDIR`: Base directory for connectome outputs
- `TEMPORARY_OUTDIR`: Temporary working directory

### File Configuration
- `PARCELLATION_FILE`: Path to atlas parcellation file
- `DTSERIES_FILENAME_TEMPLATE`: Template for dtseries filenames (with {subj} placeholder)
- `DTSERIES_FILENAME_PATTERN`: Glob pattern for discovering dtseries files

## How to Use

### In Python Scripts (Python 3)

```python
from read_config import (
    POOL_NUM, N_JOBS, VERTICES_IN_BOUNDS, N_PARCELS,
    DTSERIES_ROOT, PTSERIES_ROOT, BASE_OUTDIR,
    PARCELLATION_FILE, DTSERIES_FILENAME_TEMPLATE
)
```

### In Python 2 Scripts (run_hyperalignment.py)

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_config import POOL_NUM, N_JOBS, pool_num, n_jobs
```

Note: Both uppercase (`POOL_NUM`, `N_JOBS`) and lowercase (`pool_num`, `n_jobs`) versions are available for backward compatibility.

### In Bash Scripts

```bash
# Source the config file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Use the variables
echo "Processing with $N_JOBS jobs"
echo "Reading from $DTSERIES_ROOT"
```

### Overriding Configuration

#### Environment Variables (Bash)
You can override any parameter by setting environment variables:

```bash
export N_JOBS=16
export BASEDIR="/custom/path/to/data"
./apply_parcellation.sh
```

#### For Machine-Specific Paths
If you need machine-specific absolute paths (e.g., for `apply_parcellation.sh`), set them as environment variables rather than modifying `config.sh`:

```bash
export BASEDIR="/Volumes/MyPassport-Selin/HBN_CIFTI/"
export OUTDIR="/Volumes/FMRI2/data/hyperalignment_input/glasser_ptseries"
./apply_parcellation.sh
```

## Migration from Old Code

All scripts have been updated to use the centralized configuration:

1. **utils.py**: Now imports from `read_config` instead of defining parameters
2. **run_hyperalignment.py**: Now imports from `read_config` (Python 2 compatible)
3. **apply_parcellation.sh**: Now sources `config.sh`

## Benefits

1. **Single Source of Truth**: All parameters defined in one place
2. **No Duplication**: No need to update parameters in multiple files
3. **Cross-Platform**: Works with Python 2, Python 3, and bash
4. **Backward Compatible**: Existing code continues to work
5. **Easy to Override**: Environment variables can override defaults
