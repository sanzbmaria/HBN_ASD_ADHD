#!/usr/bin/env python
"""
Configuration reader for both Python 2 and Python 3.
Reads the centralized config.sh file and makes parameters available as module variables.
"""

import os
import re

def read_config(config_path=None):
    """
    Read configuration from config.sh file.

    Parameters
    ----------
    config_path : str, optional
        Path to config.sh file. If None, uses the file in the same directory.

    Returns
    -------
    dict
        Dictionary of configuration parameters
    """
    if config_path is None:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.sh')

    if not os.path.exists(config_path):
        raise IOError("Config file not found: {}".format(config_path))

    config = {}

    # Read and parse the config file
    with open(config_path, 'r') as f:
        for line in f:
            # Strip whitespace and comments
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('#!/'):
                continue

            # Match pattern: KEY=value or KEY="value"
            match = re.match(r'^([A-Z_]+)=(.+)$', line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()

                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]

                # Try to convert to int if it looks like a number
                if value.isdigit():
                    value = int(value)

                config[key] = value

    return config

# Load configuration at module import time
_config = read_config()

# Export as module-level variables for easy access
POOL_NUM = _config.get('POOL_NUM', 24)
N_JOBS = _config.get('N_JOBS', 24)
VERTICES_IN_BOUNDS = _config.get('VERTICES_IN_BOUNDS', 59412)
N_PARCELS = _config.get('N_PARCELS', 360)

DTSERIES_ROOT = _config.get('DTSERIES_ROOT', '../data/HBN_CIFTI/')
PTSERIES_ROOT = _config.get('PTSERIES_ROOT', '../data/hyperalignment_input/glasser_ptseries/')
BASE_OUTDIR = _config.get('BASE_OUTDIR', '../data/connectomes')
TEMPORARY_OUTDIR = _config.get('TEMPORARY_OUTDIR', 'work')

PARCELLATION_FILE = _config.get('PARCELLATION_FILE',
    'atlas/Q1-Q6_RelatedValidation210.CorticalAreas_dil_Final_Final_Areas_Group_Colors.32k_fs_LR.dlabel.nii')

DTSERIES_FILENAME_TEMPLATE = _config.get('DTSERIES_FILENAME_TEMPLATE',
    '{subj}_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii')
DTSERIES_FILENAME_PATTERN = _config.get('DTSERIES_FILENAME_PATTERN',
    '*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii')

# Derived values
LOGDIR = os.path.join(BASE_OUTDIR, 'logs')

# For backwards compatibility, provide lowercase aliases
pool_num = POOL_NUM
n_jobs = N_JOBS
