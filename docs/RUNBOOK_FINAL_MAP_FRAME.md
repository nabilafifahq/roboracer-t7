# RUNBOOK — Final map-frame recording (everything fixed)

All fixes consolidated: scan (CycloneDDS + slice), range (in config, not param-set),
vesc-TF localization, EKF no-TF, Cartographer anti-teleport, map frame.
Goal: record a **drift-free map-frame lap** → clean inner/outer walls + best-path figure.

> What we learned (don't repeat these): the LiDAR reads **walls, not floor**; the slice is
> fine; `param set range_max` is **ignored** by pointcloud_to_laserscan (set it in the config);
> the real blur was **odom drift** → Cartographer map frame fixes it.

---
## 0. Power on + SSH + container
```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7 && git pull                      # get latest script + this runbook
git reset --hard origin/dl-debug                   # if pull says "already up to date" but files missing
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh                               # drops you into the container
```

## 1. Apply ALL fixes — one command (no multi-line paste)
The container is ephemeral (`--rm`), so copy the script in each session from a **second Pi-host terminal**:
```bash
# --- SECOND terminal on the Pi host (container already running) ---
docker cp ~/roboracer-t7/scripts/car_map_setup.sh roboracer_t7:/race_ws/scripts/
docker cp ~/roboracer-t7/config/cartographer/roboracer_2d.lua roboracer_t7:/race_ws/config/cartographer/roboracer_2d.lua
docker cp ~/roboracer-t7/launch/cartographer_2d.launch.py     roboracer_t7:/race_ws/launch/cartographer_2d.launch.py
```
```bash
# --- back INSIDE the container ---
source /race_ws/scripts/car_map_setup.sh           # writes vesc/ekf/joy/slice+range configs, patches cartographer, builds
```
The script applies, in order:
1. **CycloneDDS** (`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`) — the `/scan`-stall fix
2. **Livox → PointCloud2**, frame_id=laser
3. **vesc.yaml**: `publish_tf:true`, wheelbase 0.33, full servo range (clean live pose)
4. **EKF**: `publish_tf:false` (vesc is sole odom→base_link → no gyro spin)
5. **Steering** scale 0.40
6. **Slice -0.08/-0.02 + range_max 2.5 IN THE CONFIG** (applies at launch; param-set is ignored)
7. **Cartographer anti-teleport**: no correlative matcher, no loop closure, high ceres weights, odom prior=/odom
8. **colcon build**

## 2. Launch WITH Cartographer (map frame)
```bash
ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=true
```

## 3. Verify (second container tab: `docker exec -it roboracer_t7 bash`, then source + RMW export)
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash

ros2 topic echo /scan --once --field range_max          # MUST print 2.5  (proves range applied)
ros2 topic hz /scan                                      # ~10 Hz, stays up
ros2 run tf2_ros tf2_echo odom base_link                 # parked -> yaw STEADY (vesc TF)
ros2 run tf2_ros tf2_echo map base_link                  # drive ~2 m -> tracks SMOOTH, no 0.4-0.7 m jumps
```
- All good → record. If `map→base_link` jumps → tell me (scan rate / cartographer).
- If `/scan` drops while driving → free CPU: `pkill -f monitor_node`

## 4. Record the map-frame lap (bag + CSV, 10 Hz)
```bash
# CSV (for quick TUM) — drive ONE clean lap, Ctrl+C:
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map -p robot_frame:=base_link -p scan_topic:=/scan -p record_hz:=10.0 \
  -p output_csv:=/race_ws/logs/lap_map.csv

# BAG (for me to rebuild/verify) — record while driving the SAME lap:
ros2 bag record -o /race_ws/logs/lap_map_bag /scan /tf /tf_static /odom /livox/lidar
```
> The bag's `/tf` carries **map→base_link** (drift-corrected) — that's what makes the walls close.

## 5. Get files to the Mac
```bash
# --- Pi host ---
docker cp roboracer_t7:/race_ws/logs/lap_map.csv  ~/
docker cp roboracer_t7:/race_ws/logs/lap_map_bag  ~/lap_map_bag
# --- Mac ---
DEST=~/Documents/roboracer-t7/testrun/june7_set3 ; mkdir -p $DEST
scp    ucsd-blue@ucsd-blue.local:~/lap_map.csv  $DEST/
scp -r ucsd-blue@ucsd-blue.local:~/lap_map_bag  $DEST/
```
Then tell me the folder. I build the clean **inner wall + outer wall + centerline + TUM best-path** figure from the **map-frame** data (no drift, measured walls).

---
## Quick reference — the fixed values
| Thing | Value | Where it's set |
|---|---|---|
| RMW | `rmw_cyclonedds_cpp` | env + ~/.bashrc |
| LiDAR slice | min `-0.08`, max `-0.02` | p2l **config** (not param-set) |
| range_min / max | `0.30` / `2.5` | p2l **config** (not param-set) |
| vesc publish_tf | `true` | vesc.yaml |
| ekf publish_tf | `false` | ekf_car.yaml |
| wheelbase | `0.33` | vesc.yaml |
| steering scale | `0.40` | joy_rc_steer_fix.yaml |
| cartographer | no correlative, `optimize_every_n_nodes=0`, ceres t30/r60, odom prior `/odom` | roboracer_2d.lua + launch |
| frame | `map` | launch `use_cartographer:=true`, logger `world_frame:=map` |

## Notes
- **`param set` is unreliable** for pointcloud_to_laserscan — always set slice/range in the config + relaunch.
- **`git reset --hard origin/dl-debug`** on the Pi if a pull says up-to-date but files are missing.
- **Autonomous later:** same setup, then pursuit `world_frame:=map use_traj_velocity:=false target_speed_mps:=0.5` on the TUM raceline (triple it to loop).
