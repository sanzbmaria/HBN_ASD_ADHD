FROM ubuntu:20.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    build-essential \
    software-properties-common \
    ca-certificates \
    libhdf5-dev \
    libxml2-dev \
    libxslt1-dev \
    libfreetype6-dev \
    libpng-dev \
    pkg-config \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

# Install Python 2 and Python 3
RUN apt-get update && apt-get install -y \
    python2 \
    python2-dev \
    python3 \
    python3-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Get pip for Python 2
RUN curl https://bootstrap.pypa.io/pip/2.7/get-pip.py --output get-pip.py && \
    python2 get-pip.py && \
    rm get-pip.py

# Install Python 3 packages
RUN pip3 install --no-cache-dir \
    numpy==1.21.6 \
    scipy==1.7.3 \
    nibabel==3.2.2 \
    pandas==1.3.5 \
    scikit-learn==1.0.2 \
    joblib==1.1.0 \
    tqdm==4.64.1

# Install Python 2 packages (compatible versions)
RUN pip2 install --no-cache-dir \
    numpy==1.16.6 \
    scipy==1.2.3 \
    nibabel==2.5.2 \
    pandas==0.24.2 \
    h5py==2.10.0

# Install PyMVPA2 for Python 2 (needed for hyperalignment)
RUN pip2 install --no-cache-dir pymvpa2

# Install Connectome Workbench
RUN wget -q https://www.humanconnectome.org/storage/app/media/workbench/workbench-linux64-v1.5.0.zip && \
    unzip -q workbench-linux64-v1.5.0.zip -d /opt/ && \
    rm workbench-linux64-v1.5.0.zip

# Add Workbench to PATH
ENV PATH="/opt/workbench/bin_linux64:${PATH}"

# Create working directory
WORKDIR /app

# Copy the hyperalignment scripts
COPY hyperalignment_scripts/ /app/hyperalignment_scripts/

# Set Python path to include hyperalignment_scripts
ENV PYTHONPATH="/app/hyperalignment_scripts:${PYTHONPATH}"

# Create directories for data mounting
RUN mkdir -p /data/HBN_CIFTI \
             /data/hyperalignment_input/glasser_ptseries \
             /data/connectomes \
             /data/diagnosis_summary

# Default command
CMD ["/bin/bash"]
