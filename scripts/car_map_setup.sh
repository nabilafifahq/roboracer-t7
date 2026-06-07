#!/usr/bin/env bash
# ============================================================================
# roboracer-t7 — ONE-SHOT map-frame setup inside a fresh container.
# Copy in once per container, then `source` it (so the RMW export sticks):
#
#   # Pi host (container already running via car_run.sh):
#   docker cp ~/roboracer-t7/scripts/car_map_setup.sh roboracer_t7:/race_ws/scripts/
#   # inside the container:
#   source /race_ws/scripts/car_map_setup.sh
#   ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=true
#
# Avoids the multi-line heredoc paste corruption that keeps breaking vesc.yaml.
# Idempotent: safe to re-run.
# ============================================================================
set -e
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ln -sf /dev/ttyACM0 /dev/sensors/vesc 2>/dev/null || true

echo "=== (1) CycloneDDS — the /scan-stall fix (do this FIRST, every shell) ==="
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
grep -q 'rmw_cyclonedds_cpp' ~/.bashrc 2>/dev/null || echo 'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' >> ~/.bashrc

echo "=== (2) Livox -> PointCloud2, frame_id=laser ==="
for LIV in $(find /race_ws/src /race_ws/install /opt -name 'msg_MID360_launch.py' 2>/dev/null); do
  sed -i -E 's/^([[:space:]]*xfer_format[[:space:]]*=[[:space:]]*)[01]/\10/' "$LIV"
  sed -i -E "s/(frame_id[[:space:]]*=[[:space:]]*)'livox_frame'/\1'laser'/" "$LIV"
done
for CFG in $(find /race_ws/src /race_ws/install /opt -name 'MID360_config.json' 2>/dev/null); do
  sed -i -E 's/("pcl_data_type"[[:space:]]*:[[:space:]]*)1/\10/' "$CFG"
done

echo "=== (3) vesc.yaml — vesc_to_odom publishes clean TF, full servo range ==="
VESC=/race_ws/src/f1tenth_system/f1tenth_stack/config/vesc.yaml
python3 - "$VESC" <<'PY'
import sys
open(sys.argv[1],"w").write('''/**:
  ros__parameters:
    speed_to_erpm_gain: 4614.0
    speed_to_erpm_offset: 0.0
    steering_angle_to_servo_gain: -1.0
    steering_angle_to_servo_offset: 0.5
    port: /dev/sensors/vesc
    duty_cycle_min: 0.0
    duty_cycle_max: 0.0
    current_min: 0.0
    current_max: 100.0
    brake_min: -20000.0
    brake_max: 200000.0
    speed_min: -23250.0
    speed_max: 23250.0
    position_min: 0.0
    position_max: 0.0
    servo_min: 0.05
    servo_max: 0.95
vesc_to_odom_node:
  ros__parameters:
    speed_to_erpm_gain: -4614.0
    odom_frame: odom
    base_frame: base_link
    publish_tf: true
    use_servo_cmd_to_calc_angular_velocity: true
    wheelbase: 0.33
throttle_interpolator:
  ros__parameters:
    rpm_input_topic: commands/motor/unsmoothed_speed
    rpm_output_topic: commands/motor/speed
    servo_input_topic: commands/servo/unsmoothed_position
    servo_output_topic: commands/servo/position
    max_acceleration: 2.5
    throttle_smoother_rate: 75.0
    max_servo_speed: 3.2
    servo_smoother_rate: 75.0
''')
print("  vesc.yaml written OK")
PY

echo "=== (4) EKF: no TF (vesc is sole odom->base_link) ==="
sed -i -E 's/(publish_tf[[:space:]]*:[[:space:]]*)true/\1false/' /race_ws/config/ekf_car.yaml

echo "=== (5) Steering 0.40 ==="
python3 - <<'PY'
open("/race_ws/config/joy_rc_steer_fix.yaml","w").write('''joy:
  ros__parameters:
    dev: /dev/input/js0
    deadzone: 0.04
    autorepeat_rate: 40.0
joy_teleop:
  ros__parameters:
    human_control:
      type: topic
      interface_type: ackermann_msgs/msg/AckermannDriveStamped
      topic_name: /teleop
      deadman_buttons: [1]
      axis_mappings:
        drive-speed: {axis: 1, scale: -0.30, offset: 0.0}
        drive-steering_angle: {axis: 3, scale: 0.40, offset: 0.0}
''')
print("  joy steering 0.40")
PY

echo "=== (6) LiDAR slice + RANGE (in CONFIG, not param-set: this node reads at startup) ==="
# Validated: -0.08/-0.02 catches the wall band (box+hose at laser height), not floor.
# range_max set HERE in the config (runtime `param set range_max` is IGNORED by this node).
python3 - <<'PY'
open("/race_ws/config/pointcloud_to_laserscan_indoor.yaml","w").write('''pointcloud_to_laserscan:
  ros__parameters:
    target_frame: laser
    transform_tolerance: 0.2
    min_height: -0.08
    max_height: -0.02
    angle_min: -3.14159
    angle_max: 3.14159
    angle_increment: 0.00872665
    scan_time: 0.1
    range_min: 0.30
    range_max: 2.5
    use_inf: true
''')
print("  slice -0.08/-0.02, range 0.30-2.5 (in config -> applies at launch)")
PY

echo "=== (7) Cartographer anti-teleport overrides + odom prior = clean vesc /odom ==="
python3 - <<'PY'
p="/race_ws/config/cartographer/roboracer_2d.lua"; s=open(p).read()
if "use_online_correlative_scan_matching = false" not in s:
    ov='''-- anti-teleport overrides (clean odom; applied last)
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = false
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.occupied_space_weight = 1.0
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.translation_weight = 30.0
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.rotation_weight = 60.0
POSE_GRAPH.optimize_every_n_nodes = 0
POSE_GRAPH.constraint_builder.min_score = 0.65

return options'''
    s=s.replace("return options", ov); open(p,"w").write(s); print("  lua patched")
else: print("  lua already patched")
PY
sed -i 's|("odom", "/odometry/filtered")|("odom", "/odom")|g' /race_ws/launch/cartographer_2d.launch.py

echo "=== (8) build f1tenth_stack ==="
( cd /race_ws && colcon build --packages-select f1tenth_stack 2>&1 | tail -2 )
source /race_ws/install/setup.bash
set +e
echo ""
echo "=== DONE. RMW=$RMW_IMPLEMENTATION ==="
echo "Launch:  ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=true"
echo "If /scan still drops while driving, free CPU:  pkill -f monitor_node"
