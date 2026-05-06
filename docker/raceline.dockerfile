#
# Optional standalone optimizer image for laptop workflows.
# The main race stack Dockerfile (docker/dockerfile) also bundles the same repo +
# Python 3.7 venv at /race_ws/tum_global_racetrajectory_optimization plus
# /race_ws/scripts/run_tum_raceline_optimizer.sh .
#
# TUMFTM/global_racetrajectory_optimization is developed against
# Ubuntu 20.04 + Python 3.7 era scientific-python stacks.
# Using Python 3.7 here avoids many build failures for pinned old deps
# (e.g., numpy==1.18.1) on newer Python versions.
#
#
# Use a supported Debian base so apt-get works.
# (buster repos are EOL and may 404.)
#
FROM python:3.7-slim-bullseye

# Keep image non-interactive and reproducible-ish
ENV DEBIAN_FRONTEND=noninteractive

# System deps commonly needed for scientific Python wheels/builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    g++ \
    gfortran \
    pkg-config \
    libopenblas-dev \
    liblapack-dev \
    libgfortran5 \
    python3-distutils \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# Pin to a repo + ref so builds are stable.
# You can override at build time:
#   docker build --build-arg TUM_REPO_URL=... --build-arg TUM_REPO_REF=... -f docker/raceline.dockerfile .
ARG TUM_REPO_URL="https://github.com/TUMFTM/global_racetrajectory_optimization.git"
ARG TUM_REPO_REF="master"

# Clone the raceline repo into the image
RUN git clone --depth 1 --branch "${TUM_REPO_REF}" "${TUM_REPO_URL}" /work/global_racetrajectory_optimization

WORKDIR /work/global_racetrajectory_optimization

# Install python deps
#
# Pin installer tooling to versions compatible with older packages.
# Newer pip/setuptools can break source builds of old numpy/scipy.
#
RUN python -m pip install --no-cache-dir --upgrade "pip<24" "setuptools<60" wheel && \
    python -m pip install --no-cache-dir "cython>=0.29.14,<3" && \
    python -m pip install --no-cache-dir --no-build-isolation -r requirements.txt && \
    # quadprog wheels can be ABI-problematic; rebuild from source at a known-good version.
    python -m pip uninstall -y quadprog || true && \
    python -m pip install --no-cache-dir --no-binary=:all: "quadprog==0.1.6"

# Default to interactive shell; users can run python scripts directly.
CMD ["bash"]

