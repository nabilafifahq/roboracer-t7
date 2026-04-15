FROM python:3.8-slim

# Keep image non-interactive and reproducible-ish
ENV DEBIAN_FRONTEND=noninteractive

# System deps commonly needed for scientific Python wheels/builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    gfortran \
    pkg-config \
    libopenblas-dev \
    liblapack-dev \
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
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

# Default to interactive shell; users can run python scripts directly.
CMD ["bash"]

