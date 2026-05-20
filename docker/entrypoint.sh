#!/bin/bash
set -e

# Cyclone DDS: avoids Fast DDS shared-memory "RTPS_TRANSPORT_SHM ... open_and_lock_file failed"
# when many nodes run in Docker (default /dev/shm is small; SHM port collisions across exec shells).
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"

# Source ROS 2 Humble
source /opt/ros/humble/setup.bash

# Source Our Workspace (if built)
if [ -f /race_ws/install/setup.bash ]; then
  source /race_ws/install/setup.bash
fi

# Execute the command
exec "$@"