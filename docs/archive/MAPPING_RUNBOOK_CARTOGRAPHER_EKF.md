# Mapping runbook — EKF + Cartographer (branch `feat/cartographer-ekf-mapping`)

End-to-end: **SSH → container → launch → drive → correct map → save → raceline**, terminal by terminal.
This branch fixes every mapping bug we found. Read [§0](#0-what-this-branch-fixes) once, then follow [§2](#2-build--load-the-image) onward.

> Safety: do the first run with the **car on a box / wheels up**. Keep the RC on with the deadman ready — RC always overrides autonomy (ackermann_mux priority 100).

---

## 0. What this branch fixes

| Bug | Fix | File |
|-----|-----|------|
| LiDAR sliced **over** the 20 cm walls (`max_height 0.35` ≈ 0.46 m above ground) → noise | Slice tightened to the wall band (`min_height -0.08`, `max_height 0.06`) | `docker/config/pointcloud_to_laserscan_indoor.yaml` |
| Cartographer `published_frame = base_link` → fights EKF for base_link → broken TF | `published_frame = "odom"` (Cartographer owns `map→odom`) | `config/cartographer/roboracer_2d.lua` |
| Local `map_builder.lua`/`trajectory_builder.lua` shadowed Cartographer defaults → node crash | Removed; single self-contained config that includes Cartographer's bases | `config/cartographer/` |
| `/livox/imu` is in `livox_frame` with **no transform** → EKF mishandles IMU + Cartographer warns | Static TF `base_link → livox_frame` added | `bringup.launch.py` |
| `wall_follow_node` ignored params, **hardcoded 2.2 m/s**, no LiDAR-drop stop | Honors `target_speed_mps`/caps; latches STOP on LiDAR loss | `wall_follow_script/.../wall_follow_node.py` |
| No saved-map workflow | `.pbstream` + `.pgm` save script and pure-localization config | `scripts/cartographer_save_map.sh`, `config/cartographer/roboracer_2d_localization.lua` |

Still open (not mapping blockers): RC-loss heartbeat watchdog; servo **pull-right trim is mechanical** — fix it on the bench or odom stays noisy.

---

## 1. Network + SSH

```bash
# Laptop: join the car's network
#   Wi-Fi: ucsd_robocar
ssh ucsd-blue@ucsd-blue.local      # adjust user/host to your car
```
Confirm the VESC device exists on the car host (once):
```bash
ls -l /dev/sensors/vesc || sudo ln -sf /dev/ttyACM0 /dev/sensors/vesc
```

---

## 2. Build / load the image

The car is a Raspberry Pi (**arm64**). Pick one:

### Option A — build on the car (simplest, native arm64)
```bash
# on the car host, in the repo
git fetch origin && git checkout feat/cartographer-ekf-mapping
TAG=cartographer-ekf ./scripts/docker_build_full_stack.sh    # builds + pushes if logged in
```

### Option B — cross-build from the Mac and push, pull on car
```bash
# Mac (Docker Desktop running, logged in to Docker Hub)
git checkout feat/cartographer-ekf-mapping
export DOCKER_USER=nabilafifahq
docker login
TAG=cartographer-ekf PLATFORM=linux/arm64 ./scripts/docker_build_full_stack.sh
# then on the car:
docker pull nabilafifahq/roboracer-t7:cartographer-ekf
```

Set the image for the run scripts (car host):
```bash
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
```

---

## 3. Terminal layout

| Term | Job |
|------|-----|
| **T1** | Start container + **launch the stack** (EKF + Cartographer) |
| **T2** | Health checks (topics + TF) — **also the "check on the box" block** |
| **T3** | `tf2_echo map base_link` while you drive |
| **T4** | `manual_map_logger` (records the raceline CSV in `map` frame) |
| **T5** | Save the map (`.pbstream` + `.pgm`) when the lap is done |

Each new shell into the container:
```bash
./scripts/car_exec.sh
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
```

---

## 4. T1 — launch the stack

```bash
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh           # start container (first shell is inside it)
# inside the container:
ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true
```
- `use_cartographer:=true` runs EKF (`odom→base_link`) + Cartographer (`map→odom`), SLAM Toolbox stays off.
- You drive **manually** with the RC; `wall_follow` is harmless (now capped at 0.12 m/s and stops on LiDAR loss).

---

## 5. T2 — health checks (run these NOW with the car on the box)

```bash
./scripts/car_exec.sh   # source as in §3
/race_ws/scripts/preflight_manual_map_logger.sh

# Sensors / pipeline
ros2 topic hz /livox/lidar          # ~10 Hz
ros2 topic hz /scan                 # ~10 Hz, no long gaps  (height-slice sanity)
ros2 topic hz /livox/imu            # IMU alive
ros2 topic hz /odom                 # VESC wheel odom (input to EKF)
ros2 topic hz /odometry/filtered    # EKF output (input to Cartographer)

# Frames — ALL must resolve, no "frame does not exist"
ros2 run tf2_ros tf2_echo base_link laser          # static 0.27 0 0.11
ros2 run tf2_ros tf2_echo base_link livox_frame    # NEW static TF (IMU) — must exist now
ros2 run tf2_ros tf2_echo odom base_link           # EKF
ros2 run tf2_ros tf2_echo map base_link            # Cartographer (after ~10-30 s of motion)

# IMU frame id should be livox_frame, and the warning should be gone:
ros2 topic echo /livox/imu --once | grep frame_id
```

**Paste me this output** and I'll confirm before you put it on the floor. What I'm checking:
- `/scan` steady with the new tight slice (no starvation).
- `base_link → livox_frame` resolves (IMU bug fixed).
- `/odometry/filtered` smooth.

> On the box you can spin the wheels with the RC to make odom move and watch `odom→base_link` update.

---

## 6. T3/T4 — drive and log the map

**T3:** watch the global pose while driving:
```bash
ros2 run tf2_ros tf2_echo map base_link
```
Wait until `map→base_link` updates **smoothly** (10–30 s after `/scan` is healthy and the car has moved a little). Do not log before that.

**T4:** start the raceline CSV logger (records pose + wall distances in `map` frame):
```bash
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map \
  -p robot_frame:=base_link \
  -p record_hz:=20.0 \
  -p output_csv:=/race_ws/logs/map_cart_$(date +%Y%m%d_%H%M%S).csv
```

**Now drive ONE slow, continuous lap** (walking pace), close the loop, minimal stops. Stop-and-go and the steering pull both hurt — drive smooth, and if the car pulls, fix the servo trim first. `Ctrl+C` the logger at the end.

Sanity-check the CSV:
```bash
wc -l /race_ws/logs/map_cart_*.csv
awk -F, 'NR>1 {print $9}' /race_ws/logs/map_cart_*.csv | sort -u | wc -l   # many unique scan stamps
```

---

## 7. T5 — save the map

```bash
/race_ws/scripts/cartographer_save_map.sh track1 /race_ws/maps
# -> /race_ws/maps/track1.pbstream   (Cartographer pure localization)
# -> /race_ws/maps/track1.pgm/.yaml  (Nav2 / AMCL / RViz, view the occupancy grid)
```
Open `track1.pgm` to eyeball the map: walls should be **thin and closed** at the loop. Thick/smeared walls ⇒ noisy run (re-drive) or slice still too high.

> The save script calls `finish_trajectory` — that Cartographer session can't map again. Relaunch T1 to remap.

---

## 8. Raceline from the map (TUM)

The logged CSV → TUM track → optimized raceline. TUM optimizer:
**https://github.com/TUMFTM/global_racetrajectory_optimization** (their `inputs/tracks/*.csv` show the expected centerline + width format; our converter writes that format).

```bash
# CSV -> TUM track input (x_m, y_m, w_tr_right_m, w_tr_left_m)
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  /race_ws/logs/map_cart_YYYYMMDD_HHMMSS.csv \
  -o /race_ws/raceline_data/inputs/tracks/from_manual_map.csv \
  --drop-first 1 --close-loop
```
Run the TUM optimizer (offline / raceline image) on `from_manual_map.csv` → export `traj_race_cl.csv` → copy to `/race_ws/racelines/`. See `docs/COMPETITION_RACELINE_PIPELINE.md`.

Drive the raceline (still localizing in `map`):
```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path use_cartographer:=true \
  pursuit_world_frame:=map \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv
```

---

## 9. Race day — localize on the saved map (don't remap)

```bash
ros2 launch /race_ws/launch/cartographer_2d.launch.py \
  configuration_basename:=roboracer_2d_localization.lua \
  load_state_filename:=/race_ws/maps/track1.pbstream
```
(Run alongside the rest of the stack; only one node may publish `map→odom`.)

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `/scan` has gaps / starves | Height slice too tight for car tilt → widen `max_height` ~2 cm in `pointcloud_to_laserscan_indoor.yaml`, rebuild |
| Map maps people/background | Slice still too high → lower `max_height` |
| `base_link → livox_frame` missing | This branch adds it; confirm you launched **this** image |
| Cartographer won't start / Lua error | Ensure `config/cartographer/` has only `roboracer_2d*.lua` (no `map_builder.lua`/`trajectory_builder.lua`) |
| TF error: base_link has two parents | `published_frame` must be `odom`, not `base_link` |
| `map→base_link` jumps meters | Fast/stop-and-go driving or poor loop closure → slow continuous lap; `--drop-first 1` on convert |
| Walls thick/smeared in `.pgm` | Noisy odom (servo pull-right, stop-and-go) → fix trim, drive smoother |
| Car bolts when RC released | You're on an old image; this branch caps wall_follow at `max_speed_mps` |

---

## 11. Quick reference

```bash
# launch (map)
ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true
# save map
/race_ws/scripts/cartographer_save_map.sh track1 /race_ws/maps
# localize (race day)
ros2 launch /race_ws/launch/cartographer_2d.launch.py \
  configuration_basename:=roboracer_2d_localization.lua \
  load_state_filename:=/race_ws/maps/track1.pbstream
```
A/B vs SLAM Toolbox + objective metrics: `docs/CARTOGRAPHER_VS_SLAMTOOLBOX_AB.md`.
```
