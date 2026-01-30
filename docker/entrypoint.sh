#!/bin/bash
set -e

# Source ROS 2 Humble
source /opt/ros/humble/setup.bash

# Source Our Workspace (if built)
if [ -f /race_ws/install/setup.bash ]; then
  source /race_ws/install/setup.bash
fi

# Execute the command
exec "$@"