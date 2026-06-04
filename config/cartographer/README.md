# Cartographer configuration (RoboRacer T7)

## Design

- **`map_builder.lua`** / **`trajectory_builder.lua`**: `dofile()` official Humble configs; override `TRAJECTORY_BUILDER_2D.*` only. Never `TRAJECTORY_BUILDER = TRAJECTORY_BUILDER_2D` (causes `trajectory_builder_2d` key error on 2.0.x).
- **`roboracer_2d.lua`**: Robot frames and topics; **`provide_odom_frame = false`** so **EKF** keeps `odom` → `base_link`; Cartographer publishes **`map` → `odom`**.
- **Do not** copy old `FAST_CORRELATIVE_SCAN_MATCHER_3D` blocks into this directory (Humble 2.0.x schema differs → node exit -6).

## Launch

```bash
ros2 launch /race_ws/bringup.launch.py use_cartographer:=true
# or
/race_ws/scripts/launch_cartographer_mapping.sh
```

Cartographer node remaps: `/scan`, `/odometry/filtered`, `/livox/imu` (see `launch/cartographer_2d.launch.py`).

## Livox IMU frame

`/livox/imu` often uses `livox_frame`. `bringup.launch.py` publishes static **`base_link` → `livox_frame`** (same extrinsics as `base_link` → `laser`).

Adjust `0.27 0 0.11` in `bringup.launch.py` if your mount differs.
