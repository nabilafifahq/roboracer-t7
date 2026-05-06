#!/usr/bin/env bash
set -euo pipefail
# TUM global raceline optimizer (bundled Python 3.7 venv; see Dockerfile multi-stage tum_raceline).
# Usage (inside container, after copying track to inputs/tracks/ and editing main_globaltraj.py):
#   /race_ws/scripts/run_tum_raceline_optimizer.sh

cd /race_ws/tum_global_racetrajectory_optimization
mkdir -p outputs
export MPLBACKEND="${MPLBACKEND:-Agg}"
exec .venv/bin/python main_globaltraj.py "$@"
