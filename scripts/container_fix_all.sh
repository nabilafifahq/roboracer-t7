#!/usr/bin/env bash
# ============================================================================
# roboracer-t7 — apply ALL runtime fixes inside a fresh container.
# Run ONCE after `docker exec -it roboracer_t7 bash`, BEFORE launching.
# Idempotent: safe to re-run. (Long-term: bake these into the dockerfile.)
#
#   source /race_ws/scripts/container_fix_all.sh     # `source` so RMW export sticks
#   ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=false
# ============================================================================
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash

echo "=== (1) Livox -> PointCloud2 (xfer_format=0, pcl_data_type=0, frame_id=laser) ==="
for LIV in $(find /race_ws/src /race_ws/install /opt -name 'msg_MID360_launch.py' 2>/dev/null); do
  sed -i -E 's/^([[:space:]]*xfer_format[[:space:]]*=[[:space:]]*)[01]/\10/' "$LIV"
  sed -i -E "s/(frame_id[[:space:]]*=[[:space:]]*)'livox_frame'/\1'laser'/" "$LIV"
done
for CFG in $(find /race_ws/src /race_ws/install /opt -name 'MID360_config.json' 2>/dev/null); do
  sed -i -E 's/("pcl_data_type"[[:space:]]*:[[:space:]]*)1/\10/' "$CFG"
done

echo "=== (2) VESC: single odom->base_link TF publisher + correct wheelbase ==="
for VESC in $(find /race_ws/src /race_ws/install -path '*f1tenth_stack/config/vesc.yaml' 2>/dev/null); do
  sed -i -E 's/(publish_tf[[:space:]]*:[[:space:]]*)true/\1false/' "$VESC"   # EKF is sole TF publisher
  sed -i -E 's/(wheelbase[[:space:]]*:[[:space:]]*)0?\.25/\10.33/'   "$VESC"  # real wheelbase
  echo "  $VESC:"; grep -nE 'publish_tf|wheelbase' "$VESC" | sed 's/^/    /'
done

echo "=== (3) EKF: gyro drives yaw; drop the Livox 6-axis fake absolute orientation ==="
python3 - <<'PY'
p="/race_ws/config/ekf_car.yaml"; s=open(p).read()
before=s
s=s.replace("""        imu0_config: [false, false, false,
                      true,  true,  true,""",
            """        imu0_config: [false, false, false,
                      false, false, false,""")
open(p,"w").write(s)
print("  imu0 orientation row -> false" if s!=before else "  imu0 already patched (false)")
PY

echo "=== (4) Steering scale 0.34 (no servo clipping) + slow speed ==="
cat > /race_ws/config/joy_rc_steer_fix.yaml <<'EOF'
joy:
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
        drive-steering_angle: {axis: 3, scale: 0.34, offset: 0.0}
EOF

echo "=== (5) pointcloud_to_laserscan: 360 FOV, hose slice, QoS match attempt ==="
cat > /race_ws/config/pointcloud_to_laserscan_indoor.yaml <<'EOF'
pointcloud_to_laserscan:
  ros__parameters:
    target_frame: laser
    transform_tolerance: 0.2
    min_height: -0.10
    max_height: 0.30
    angle_min: -3.14159
    angle_max: 3.14159
    angle_increment: 0.00872665
    scan_time: 0.1
    range_min: 0.20
    range_max: 4.0          # open-window venue; raise to ~8-12 for a closed track
    use_inf: true
    # Best-effort attempt to match the Livox RELIABLE publisher. The REAL stall fix
    # is CycloneDDS below (the p2l node may ignore this override).
    qos_overrides:
      /livox/lidar:
        subscription:
          reliability: reliable
          history: keep_last
          depth: 5
EOF

echo "=== (6) CycloneDDS — the actual /scan-stall fix (off FastDDS shared-memory) ==="
if ros2 pkg prefix rmw_cyclonedds_cpp >/dev/null 2>&1; then
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  grep -q 'RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' ~/.bashrc 2>/dev/null || \
    echo 'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' >> ~/.bashrc
  echo "  RMW_IMPLEMENTATION=rmw_cyclonedds_cpp  (set now + added to ~/.bashrc)"
else
  echo "  !! rmw_cyclonedds_cpp NOT installed. Install then re-source this script:"
  echo "     apt-get update && apt-get install -y ros-humble-rmw-cyclonedds-cpp"
fi

echo ""
echo "=== DONE. In EVERY terminal: export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ==="
echo "Launch:  ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=false"
echo "Verify:  ros2 topic hz /scan   (~10 Hz, STAYS up)"
echo "         ros2 run tf2_ros tf2_echo odom base_link   (rotate car 90 deg -> yaw tracks smoothly)"
