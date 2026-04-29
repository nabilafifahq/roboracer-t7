#!/bin/bash
# Do not use nounset (-u): ROS setup.bash reads vars like AMENT_TRACE_SETUP_FILES before they exist.
set -eo pipefail
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
exec "$@"
