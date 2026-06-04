# Paste inside container: docker exec -it roboracer_t7 bash
# Fixes from Cartographer handoff + Cursor Fix Instructions (corrected for EKF stack).
#
# DO NOT use provide_odom_frame=true (EKF already publishes odom->base_link).
# DO NOT use RETURN = options (Lua must be: return options)

set -e
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
set +u
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
set -u

echo "========== FIX 1: Cartographer Lua (Humble schema) =========="
mkdir -p /race_ws/config/cartographer

cat > /race_ws/config/cartographer/map_builder.lua <<'EOF'
dofile('/opt/ros/humble/share/cartographer/configuration_files/map_builder.lua')
MAP_BUILDER.use_trajectory_builder_2d = true
MAP_BUILDER.use_trajectory_builder_3d = false
MAP_BUILDER.num_background_threads = 2
EOF

cat > /race_ws/config/cartographer/trajectory_builder.lua <<'EOF'
dofile('/opt/ros/humble/share/cartographer/configuration_files/trajectory_builder.lua')
TRAJECTORY_BUILDER_2D.min_range = 0.20
TRAJECTORY_BUILDER_2D.max_range = 12.0
TRAJECTORY_BUILDER_2D.min_z = -0.15
TRAJECTORY_BUILDER_2D.max_z = 0.35
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 5.0
TRAJECTORY_BUILDER_2D.num_accumulated_range_data = 1
TRAJECTORY_BUILDER_2D.use_imu_data = false
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true
TRAJECTORY_BUILDER_2D.motion_filter.max_time_seconds = 5.0
TRAJECTORY_BUILDER_2D.motion_filter.max_distance_meters = 0.05
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = 0.12
TRAJECTORY_BUILDER = TRAJECTORY_BUILDER_2D
EOF

cat > /race_ws/config/cartographer/roboracer_2d.lua <<'EOF'
include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "base_link",
  published_frame = "base_link",
  odom_frame = "odom",
  provide_odom_frame = false,
  publish_frame_projected_to_2d = true,
  use_odometry = true,
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  lookup_transform_timeout_sec = 0.3,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
  trajectory_publish_period_sec = 30e-3,
  rangefinder_sampling_ratio = 1.0,
  odometry_sampling_ratio = 1.0,
  fixed_frame_pose_sampling_ratio = 1.0,
  imu_sampling_ratio = 1.0,
  landmarks_sampling_ratio = 1.0,
}

MAP_BUILDER.use_trajectory_builder_2d = true

return options
EOF

echo "========== FIX 2: Livox IMU frame (livox_frame) =========="
cat > /race_ws/scripts/run_livox_frame_tf.sh <<'EOF'
#!/bin/bash
# Run in background if bringup has no static_base_link_to_livox_frame yet.
exec ros2 run tf2_ros static_transform_publisher \
  0.27 0 0.11 0 0 0 base_link livox_frame
EOF
chmod +x /race_ws/scripts/run_livox_frame_tf.sh

echo "========== FIX 3: wall_follow /drive QoS RELIABLE =========="
python3 <<'PY'
from pathlib import Path
p = Path("/race_ws/src/wall_follow_script/reactive_control/wall_follow_node.py")
if not p.exists():
    print("skip: no src wall_follow_node.py")
    raise SystemExit(0)
text = p.read_text()
old = """        drive_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )"""
new = old.replace("BEST_EFFORT", "RELIABLE")
if old in text:
    p.write_text(text.replace(old, new))
    print("patched drive_qos")
else:
    print("drive_qos already patched or manual edit needed")
PY
cd /race_ws && colcon build --packages-select reactive_control --symlink-install
source /race_ws/install/setup.bash

echo "========== FIX 4: manual_map_logger SyntaxError (elif after except) =========="
python3 <<'PY'
from pathlib import Path
OLD = """        except Exception as e:
            self.get_logger().error(
                f"No rows yet: TF {self._world}->{self._robot} unavailable ({e}). "
                f"With SLAM, wait until `ros2 run tf2_ros tf2_echo map base_link` works, "
                f"or use -p world_frame:=odom if not using map."
            )
        elif self._last_scan is None:"""
NEW = """        except Exception as e:
            self.get_logger().error(
                f"No rows yet: TF {self._world}->{self._robot} unavailable ({e}). "
                f"Launch bringup with use_cartographer:=true and wait for map TF."
            )
            return
        if self._last_scan is None:"""
for rel in [
    "src/wall_follow_script/reactive_control/manual_map_logger.py",
    "build/reactive_control/reactive_control/manual_map_logger.py",
]:
    p = Path("/race_ws") / rel
    if p.exists() and OLD in p.read_text():
        p.write_text(p.read_text().replace(OLD, NEW))
        print("patched", p)
PY
colcon build --packages-select reactive_control --symlink-install
source /race_ws/install/setup.bash

echo "========== DONE =========="
echo "Terminal 1: ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true"
echo "Optional if IMU TF warnings persist: /race_ws/scripts/run_livox_frame_tf.sh &"
echo "Terminal 2: ros2 run tf2_ros tf2_echo map base_link"
