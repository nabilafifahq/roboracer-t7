# Slim image: only the reactive_control package (manual_map_logger).
# Build from repo root:
#   docker build -t roboracer-t7:manual-map-logger -f docker/manual_map_logger.dockerfile .
# Offline smoke test (no car): run smoke in one terminal, logger in another (same host):
#   ros2 run reactive_control manual_map_logger_smoke
#   ros2 run reactive_control manual_map_logger --ros-args -p world_frame:=odom -p output_csv:=/tmp/m.csv
# Run on the same machine as the robot stack (needs /tf and /scan), host networking:
#   docker run --rm --net=host roboracer-t7:manual-map-logger
# Override parameters:
#   docker run --rm --net=host roboracer-t7:manual-map-logger \
#     ros2 run reactive_control manual_map_logger --ros-args \
#       -p world_frame:=odom -p output_csv:=/race_ws/logs/manual_map.csv

FROM ros:humble-ros-base

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions \
    ros-humble-tf2-ros \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /race_ws
RUN mkdir -p src logs

COPY wall_follow_script/ ./src/wall_follow_script/

RUN source /opt/ros/humble/setup.sh && \
    colcon build --symlink-install --packages-select reactive_control

COPY docker/manual_map_logger_entrypoint.sh /manual_map_logger_entrypoint.sh
RUN chmod +x /manual_map_logger_entrypoint.sh

ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp

ENTRYPOINT ["/manual_map_logger_entrypoint.sh"]
CMD ["ros2", "run", "reactive_control", "manual_map_logger"]
