#!/bin/bash
# Source ROS 2 + workspace with Cyclone DDS (use in every container shell).
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"
set +u
source /opt/ros/humble/setup.bash
if [ -f /race_ws/install/setup.bash ]; then
  source /race_ws/install/setup.bash
fi
set -u
