# Docker Build Notes

## Python Version Change

**IMPORTANT**: This Docker image now uses **Python 3.9** for ALL components, including hyperalignment.

### Why the Change?

- **PyMVPA2 2.6.5** works with Python 3.9+
- Python 2 reached end-of-life in 2020
- Old scipy versions for Python 2 no longer compile reliably
- Simpler, more maintainable environment with single Python version

### Versions Used

Based on tested working environment:

```
Python: 3.9.23
PyMVPA2: 2.6.5
NumPy: 1.23.5
SciPy: 1.10.1
Nibabel: 5.3.2
Pandas: 2.3.3
Scikit-learn: 1.6.1
Matplotlib: 3.9.4
```

### Build Requirements

The Dockerfile now uses **miniconda** as the base image and requires:
- `build-essential` - C/C++ compilers
- `swig` - For PyMVPA2 compilation

### Compatibility

All scripts have been updated to use `python` instead of `python2`:
- `run_hyperalignment.py` - Hyperalignment (uses PyMVPA2)
- `build_aa_connectomes.py` - Connectome building
- `build_CHA_connectomes.py` - CHA connectomes

Everything runs in a single Python 3.9 conda environment called `mvpa_stable`.

### Building

```bash
./docker-build.sh
```

Build time: ~5-10 minutes (depends on internet speed)

### Testing

```bash
# Verify Python version
docker run --rm hyperalignment:latest python --version
# Should output: Python 3.9.23

# Verify PyMVPA2
docker run --rm hyperalignment:latest python -c "import mvpa2; print(mvpa2.__version__)"
# Should output: 2.6.5

# Run full test
export DATA_ROOT=/path/to/your/data
./test_pipeline.sh
```

### Troubleshooting

If build fails:
1. Clean Docker: `docker system prune -a`
2. Check internet connection
3. Try build again: `./docker-build.sh`

If PyMVPA2 import fails:
- Ensure SWIG was installed correctly
- Check conda environment activated: `echo $CONDA_DEFAULT_ENV` should show `mvpa_stable`

### Migration Notes

**No changes needed to your code!** All scripts work the same way, they just now use Python 3.9 internally instead of Python 2.7.

The container automatically activates the correct conda environment, so `python` runs Python 3.9 with all required packages.
