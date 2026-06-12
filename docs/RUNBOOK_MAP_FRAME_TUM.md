# Runbook — Map frame + TUM autonomous (next session, fresh from SSH)

Goal: build a Cartographer map → drive the TUM raceline in **map frame** so the car can be
placed **anywhere** on the track (no more starting-on-the-line). Also confirms the new LiDAR
slice fixed the inner-wall tangle.

Prereq: battery charged, RC ON **before** car power.

---
## 0. SSH + container
```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7 && git pull          # get my latest (configs, TUM raceline, this runbook)
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh
# --- inside container ---
ln -sf /dev/ttyACM0 /dev/sensors/vesc
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
```

## 1. Apply ALL configs (paste the whole block)
```bash
# (a) Livox -> PointCloud2 + frame_id laser
for LIV in $(find /race_ws/src /race_ws/install /opt -name 'msg_MID360_launch.py' 2>/dev/null); do
  sed -i -E 's/^([[:space:]]*xfer_format[[:space:]]*=[[:space:]]*)[01]/\10/' "$LIV"
  sed -i -E "s/(frame_id[[:space:]]*=[[:space:]]*)'livox_frame'/\1'laser'/" "$LIV"
done
for CFG in $(find /race_ws/src /race_ws/install /opt -name 'MID360_config.json' 2>/dev/null); do
  sed -i -E 's/("pcl_data_type"[[:space:]]*:[[:space:]]*)1/\10/' "$CFG"
done

# (b) VESC — vesc_to_odom publishes the clean TF (publish_tf TRUE), F1TENTH params
cat > /race_ws/src/f1tenth_system/f1tenth_stack/config/vesc.yaml <<'EOF'
/**:
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
    publish_tf: true
    base_frame: base_link
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
EOF

# (c) EKF: do NOT publish TF (vesc is sole odom->base_link -> no gyro-drift spin)
sed -i -E 's/(publish_tf[[:space:]]*:[[:space:]]*)true/\1false/' /race_ws/config/ekf_car.yaml

# (d) Steering 0.40 (full lock, no clipping)
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
        drive-steering_angle: {axis: 3, scale: 0.40, offset: 0.0}
EOF

# (e) ===== LiDAR slice — below the 20cm box step (fixes inner-wall tangle) =====
cat > /race_ws/config/pointcloud_to_laserscan_indoor.yaml <<'EOF'
pointcloud_to_laserscan:
  ros__parameters:
    target_frame: laser
    transform_tolerance: 0.2
    min_height: 0.0          # ~7 cm above floor
    max_height: 0.1           # ~15 cm floor — BELOW the 20 cm box step
    angle_min: -3.14159
    angle_max: 3.14159
    angle_increment: 0.00872665
    scan_time: 0.1
    range_min: 0.30
    range_max: 2.5
    use_inf: true
EOF
```
> **If the inner wall still tangles** (or the box reads inconsistently): lower `max_height` to `-0.02`.
> **If a wall goes sparse/empty:** widen `min_height` to `-0.10`.

## 2. Build + source + CycloneDDS
```bash
cd /race_ws && colcon build --packages-select f1tenth_stack 2>&1 | tail -2
source /race_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

## 3. Launch WITH Cartographer (map frame)
```bash
ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=true
```

## 4. Verify — new tab (`docker exec -it roboracer_t7 bash`, source + RMW export)
```bash
ros2 topic hz /scan                                          # ~10 Hz, stays up
ros2 topic echo /scan --once --field ranges | tr ',' '\n' | grep -vci inf   # few hundred
ros2 run tf2_ros tf2_echo odom base_link                     # parked -> yaw STEADY (vesc TF)
ros2 run tf2_ros tf2_echo map base_link                      # drive 1 m -> MOVES, NO teleport
```
- `map->base_link` stable → continue with map frame.
- Teleports → Cartographer still unstable → fall back to the odom flow that already works.

## 5. Build the map + record a MAP-frame lap
```bash
# drive 2-3 SLOW clean laps to build the map, then ONE clean lap logged in MAP frame:
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map -p robot_frame:=base_link -p scan_topic:=/scan -p record_hz:=20.0 \
  -p output_csv:=/race_ws/logs/maplap.csv          # one smooth lap, Ctrl+C
# save the occupancy map (also the proof the slice fixed the box):
ros2 run nav2_map_server map_saver_cli -f /race_ws/maps/track --occ 0.45 \
  --ros-args -p save_map_timeout:=20.0
ros2 run nav2_map_server map_saver_cli -f /race_ws/maps/track_scale --mode scale \
  --ros-args -p save_map_timeout:=20.0
```
> **Optional backup (recommended): also record a rosbag** of the mapping drive — lets me
> rebuild a dense map / re-derive walls offline if the CSV is noisy:
> ```bash
> ros2 bag record -o /race_ws/bags/mapsession /scan /livox/lidar /tf /tf_static /odom
> ```

## 6. Send me the data (how)
Copy out of the container, then scp to the laptop into `testrun/june6/`:
```bash
# Pi host (outside container):
docker cp roboracer_t7:/race_ws/logs/maplap.csv ~/
docker cp roboracer_t7:/race_ws/maps ~/maps
# from laptop:
scp ucsd-blue@ucsd-blue.local:~/maplap.csv  ~/Documents/roboracer-t7/testrun/june6/
scp -r ucsd-blue@ucsd-blue.local:~/maps     ~/Documents/roboracer-t7/testrun/june6/maps
# (if you recorded the bag too:)
docker cp roboracer_t7:/race_ws/bags/mapsession ~/mapsession   # on Pi
scp -r ucsd-blue@ucsd-blue.local:~/mapsession ~/Documents/roboracer-t7/testrun/june6/mapsession
```
**Send me:** `maplap.csv` + `maps/track_scale.png`. (Bag only if asked.)
**I then:** run the proven TUM pipeline on `maplap.csv` (map frame) → `traj_race_cl.csv` → I push it.

## 7. (After I push the raceline) — pursuit in MAP frame
```bash
cd ~/roboracer-t7 && git pull                                  # get the new raceline
docker cp <path>/traj_race_cl.csv roboracer_t7:/race_ws/racelines/raceline.csv
# triple it to loop:
docker exec roboracer_t7 bash -c 'cd /race_ws/racelines; head -1 raceline.csv > raceline_loop.csv; for i in 1 2 3; do tail -n +2 raceline.csv >> raceline_loop.csv; done'
# pursuit (MAP frame — place car ANYWHERE on the track):
ros2 run reactive_control raceline_pure_pursuit_node --ros-args \
  -p trajectory_csv:=/race_ws/racelines/raceline_loop.csv \
  -p world_frame:=map -p robot_frame:=base_link \
  -p use_traj_velocity:=false -p target_speed_mps:=0.5 \
  -p lookahead_m:=0.5 -p max_steering_rad:=0.45 -p stop_within_m:=0.20
```
Deadman: HOLD → start node → RELEASE = autonomous → SQUEEZE = stop.
**Keep the launch (Cartographer) running the whole time — it IS your map localization.**

---
## NOTES — re-pull, data handoff, rosbag-vs-CSV
- **Re-pull:** I push to branch **`dl-debug`**. After I produce the raceline (or edit configs),
  run `git pull` on the Pi (`~/roboracer-t7`) AND on your laptop before continuing.
- **How to give me data:** `docker cp` out of the container → `scp` to the laptop into
  `testrun/june6/` → tell me the filename. Small files you can paste; CSVs/maps/bags must be scp'd.
- **rosbag vs CSV:** for **TUM** I only need `maplap.csv` (centerline + wall widths) — the CSV is
  enough. Record the **rosbag** only as a backup / if I need to rebuild a dense map or re-slice
  the LiDAR height offline. Default: send the **CSV + map.png**; send the **bag** if I ask.
- **Frame:** map frame removes the start-on-the-line limit; if Cartographer teleports, fall back
  to odom (origin-anchored raceline, car launched facing down-track) — that already works.
- **TUM image is laptop-only:** rebuild with
  `docker build --platform linux/amd64 -f docker/raceline.dockerfile -t roboracer-t7-raceline:latest .`
  on a new machine.
