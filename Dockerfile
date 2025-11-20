FROM continuumio/miniconda3:latest

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies (including libGL for Workbench)
RUN apt-get update && apt-get install -y \
    build-essential \
    swig \
    wget \
    curl \
    git \
    unzip \
    ca-certificates \
    libgl1 \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

# Create conda environment with needed packages
RUN conda create -n mvpa_stable \
    python=3.9.23 \
    nibabel=5.3.2 \
    scikit-learn=1.6.1 \
    pandas=2.3.3 \
    numpy=1.23.5 \
    scipy=1.10.1 \
    matplotlib=3.9.4 \
    setuptools=59.8.0 \
    joblib \
    tqdm \
    -c conda-forge \
    && conda clean -afy

# Activate environment and install PyMVPA2
RUN /bin/bash -c "source activate mvpa_stable && \
    pip cache purge && \
    pip install pymvpa2==2.6.5 && \
    conda install numpy=1.23.5 -c conda-forge --yes"

# Make environment default
ENV PATH=/opt/conda/envs/mvpa_stable/bin:$PATH
ENV CONDA_DEFAULT_ENV=mvpa_stable

# Install Connectome Workbench
RUN wget -q https://www.humanconnectome.org/storage/app/media/workbench/workbench-linux64-v1.5.0.zip && \
    unzip -q workbench-linux64-v1.5.0.zip -d /opt/ && \
    rm workbench-linux64-v1.5.0.zip

# Add Workbench to PATH
ENV PATH="/opt/workbench/bin_linux64:${PATH}"

# Create working directory
WORKDIR /app

# Copy hyperalignment code
COPY hyperalignment_scripts/ /app/hyperalignment_scripts/

# Ensure Python can import hyperalignment scripts
ENV PYTHONPATH=/app/hyperalignment_scripts

# Create directories for mounting
RUN mkdir -p /data/inputs \
             /data/outputs \
             /data/HBN_CIFTI \
             /data/hyperalignment_input/glasser_ptseries \
             /data/connectomes \
             /data/diagnosis_summary

# Default command
CMD ["/bin/bash"]
