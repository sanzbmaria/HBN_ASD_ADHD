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

# Helper function to get value with priority: ENV > config.sh > default
def _get_config_value(key, default, value_type=None):
    """
    Get configuration value with priority order:
    1. Environment variable (highest priority)
    2. config.sh value
    3. Default value (lowest priority)

    Parameters
    ----------
    key : str
        Configuration key name
    default : any
        Default value if not found
    value_type : type, optional
        Type to convert environment variable to (int, str, etc.)

    Returns
    -------
    any
        Configuration value
    """
    # Check environment variable first
    env_value = os.environ.get(key)
    if env_value is not None:
        if value_type == int:
            try:
                return int(env_value)
            except ValueError:
                pass  # Fall through to config.sh
        return env_value

    # Fall back to config.sh, then default
    return _config.get(key, default)

# Export as module-level variables with environment variable override support
# Environment variables take precedence over config.sh values
POOL_NUM = _get_config_value('POOL_NUM', 24, int)
N_JOBS = _get_config_value('N_JOBS', 24, int)
VERTICES_IN_BOUNDS = _get_config_value('VERTICES_IN_BOUNDS', 59412, int)
N_PARCELS = _get_config_value('N_PARCELS', 360, int)

DTSERIES_ROOT = _get_config_value('DTSERIES_ROOT', '../data/HBN_CIFTI/')
PTSERIES_ROOT = _get_config_value('PTSERIES_ROOT', '../data/hyperalignment_input/glasser_ptseries/')
BASE_OUTDIR = _get_config_value('BASE_OUTDIR', '../data/connectomes')
TEMPORARY_OUTDIR = _get_config_value('TEMPORARY_OUTDIR', 'work')

PARCELLATION_FILE = _get_config_value('PARCELLATION_FILE',
    'atlas/Q1-Q6_RelatedValidation210.CorticalAreas_dil_Final_Final_Areas_Group_Colors.32k_fs_LR.dlabel.nii')

DTSERIES_FILENAME_TEMPLATE = _get_config_value('DTSERIES_FILENAME_TEMPLATE',
    '{subj}_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii')
DTSERIES_FILENAME_PATTERN = _get_config_value('DTSERIES_FILENAME_PATTERN',
    '*_task-rest_run-1_nogsr_Atlas_s5.dtseries.nii')

# Derived values
LOGDIR = os.path.join(BASE_OUTDIR, 'logs')

# For backwards compatibility, provide lowercase aliases
pool_num = POOL_NUM
n_jobs = N_JOBS
