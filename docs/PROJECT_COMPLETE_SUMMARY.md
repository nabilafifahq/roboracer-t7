# RoboRacer T7 — Complete Project Summary

**Team:** UCSD DSC 190 Winter 2026, Team 7 (HDSI)  
**Platform:** F1TENTH-scale indoor RoboRacer (1/10), Livox MID-360 LiDAR, VESC drivetrain, OAK-D Wide camera  
**Primary repo:** [https://github.com/nabilafifahq/roboracer-t7](https://github.com/nabilafifahq/roboracer-t7)  
**Last updated:** 2026-05-29 (conversation + workspace state)

---

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [System architecture](#2-system-architecture)
3. [Connected repositories and their roles](#3-connected-repositories-and-their-roles)
4. [Docker images and tags](#4-docker-images-and-tags)
5. [Problems tackled (chronological / by area)](#5-problems-tackled-chronological--by-area)
6. [Tools, scripts, and key files](#6-tools-scripts-and-key-files)
7. [Operational workflows (step-by-step)](#7-operational-workflows-step-by-step)
8. [ORB-SLAM3 spike (Mechazo)](#8-orb-slam3-spike-mechazo)
9. [Offline manual map processing (`test_manual_map_new`)](#9-offline-manual-map-processing-test_manual_map_new)
10. [SLAM / localization strategy (EKF vs SLAM Toolbox vs Cartographer vs ORB)](#10-slam--localization-strategy)
11. [Open issues — not fully tackled](#11-open-issues--not-fully-tackled)
12. [Command cheat sheet](#12-command-cheat-sheet)

---

## 1. What this project is

RoboRacer T7 is a **Docker-first ROS 2 Humble** stack for an indoor F1TENTH-style race car. Goals:

| Goal | How |
|------|-----|
| Manual RC driving with safety deadman | `joy` + `joy_teleop` → `/teleop` → `ackermann_mux` → VESC |
| LiDAR perception for autonomy | Livox MID-360 → `pointcloud_to_laserscan` → `/scan` |
| Stable odometry | VESC wheel odom + Livox IMU → **EKF** (`robot_localization`) |
| Optional global mapping | **SLAM Toolbox** (`use_slam:=true`) → `map` → `odom` |
| Corridor autonomy | `wall_follow_node` (slow indoor) |
| Competition raceline | `manual_map_logger` → TUM optimizer → Derek CSV → `/global_path` (+ optional Nav2) |
| Research spikes | ORB-SLAM3 (OAK camera), offline map fusion scripts |

**Not in scope of “main map” today:** ORB-SLAM3 does **not** replace LiDAR SLAM for Nav2 occupancy maps; it is a separate visual-SLAM experiment.

---

## 2. System architecture

### 2.1 High-level data flow

```text
RC /joy ──► /teleop (prio 100) ──┐
                                  ├──► ackermann_mux ──► VESC ──► vesc_to_odom ──► /odom ──┐
autonomy /drive (prio 10) ────────┘                                                        ├──► EKF ──► odom→base_link
                                                                                           │         /odometry/filtered
Livox /livox/imu ──────────────────────────────────────────────────────────────────────────┘

Livox /livox/lidar ──► pointcloud_to_laserscan ──► /scan ──► [SLAM Toolbox optional] ──► map→odom
                                                          └──► wall_follow / manual_map_logger

manual_map_logger: TF(map or odom) + /scan ──► manual_map_*.csv
CSV ──► manual_map_csv_to_tum_track.py ──► TUM ──► traj_race_cl.csv ──► traj_csv_path_publisher ──► /global_path
```

### 2.2 TF frame chain (REP-105)

| When | Chain |
|------|--------|
| EKF only (default) | `odom` → `base_link` (EKF), static `base_link` → `laser` |
| `use_slam:=true` | `map` → `odom` (SLAM Toolbox), EKF still owns `odom` → `base_link` |

### 2.3 First-party code in this repo

| Path | Role |
|------|------|
| `bringup.launch.py` | Unified launch: teleop, Livox, `/scan`, EKF, optional SLAM, autonomy modes |
| `wall_follow_script/reactive_control/` | `wall_follow_node`, `manual_map_logger`, raceline publishers, pursuit nodes |
| `config/` | EKF, SLAM, joy, mux, Cartographer Lua (config only) |
| `docker/` | Main image build, patches, ORB image, raceline image |
| `scripts/` | Car host helpers, map conversion, ORB build |
| `roboracer_nav2_vector_pursuit/` | Nav2 + vector pursuit launch for Derek stack |
| `test_manual_map_new/` | Offline multi-run map fusion (straight + closed loop) |

Imported at **Docker build** via `docker/racer.repos` (not vendored in `src/` on laptop).

---

## 3. Connected repositories and their roles

### 3.1 Pulled at Docker build (`docker/racer.repos`)

| Repo | URL | Function |
|------|-----|----------|
| `fish-mouse/f1tenth_system` | https://github.com/fish-mouse/f1tenth_system | F1TENTH stack: VESC, mux, teleop, bringup |
| `fish-mouse/livox_ros_driver2` | https://github.com/fish-mouse/livox_ros_driver2 | Livox MID-360 ROS 2 driver |
| `blackcoffeerobotics/vector_pursuit_controller` | https://github.com/blackcoffeerobotics/vector_pursuit_controller.git | Nav2 vector pursuit plugin |

### 3.2 Cloned in `docker/dockerfile` (not in racer.repos)

| Repo | URL | Function |
|------|-----|----------|
| `AgoraRobotics/ros2-system-monitor` | https://github.com/AgoraRobotics/ros2-system-monitor | `/diagnostics` for bags / monitoring |
| `Livox-SDK/Livox-SDK2` | https://github.com/Livox-SDK/Livox-SDK2 | Native SDK for driver build |
| `TUMFTM/global_racetrajectory_optimization` | https://github.com/TUMFTM/global_racetrajectory_optimization.git | Raceline optimizer (offline) |

### 3.3 Upstream credits (mirrors/forks)

| Upstream | Purpose |
|----------|---------|
| [f1tenth/f1tenth_system](https://github.com/f1tenth/f1tenth_system) | Original F1TENTH system |
| [Livox-SDK/livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2) | Original Livox driver |
| [ros-perception/pointcloud_to_laserscan](https://github.com/ros-perception/pointcloud_to_laserscan) | Apt: cloud → `/scan` |

### 3.4 ORB-SLAM3 spike (`docker/orbslam3_mechazo.dockerfile`)

| Repo | URL | Function |
|------|-----|----------|
| `Mechazo11/ros2_orb_slam3` | https://github.com/Mechazo11/ros2_orb_slam3 | ROS 2 Humble wrapper around ORB-SLAM3 |
| `stevenlovegrove/Pangolin` | https://github.com/stevenlovegrove/Pangolin | ORB-SLAM3 visualization dep (built from source on arm64) |
| ORB-SLAM3 (vendored inside Mechazo) | UZ-SLAMLab ORB-SLAM3 | Visual SLAM core (DBoW2, g2o rebuilt for arm64 in image) |

### 3.5 Other references in workspace

| Path / name | Notes |
|-------------|--------|
| `vesc-main/` | Local copy of F1TENTH VESC package (reference; runtime uses image-built `f1tenth_system`) |
| `external_audit/` | Audit notes (if present) |
| `history/` | Session handoffs (e.g. motor/VESC debug) |

---

## 4. Docker images and tags

| Image tag | Dockerfile | Purpose |
|-----------|------------|---------|
| `nabilafifahq/roboracer-t7:full-stack` | `docker/dockerfile` | **Main car image** — bringup, EKF, SLAM Toolbox, wall-follow, TUM, Nav2 deps |
| `nabilafifahq/roboracer-t7:main-latest` | (alias / older naming in docs) | Same family as full-stack in many runbooks |
| `nabilafifahq/roboracer-t7:orbslam3-mechazo` | `docker/orbslam3_mechazo.dockerfile` | ORB-SLAM3 + OAK (`depthai-ros`) overlay — **pushed** |
| `roboracer-t7-raceline:latest` | `docker/raceline.dockerfile` | TUM-focused manual map / optimizer workflow |
| `main-manual-map-logger-*` | `docker/manual_map_logger.dockerfile` | Logger + conversion tooling |

**Build / run (car host):**

```bash
# Main stack
./scripts/docker_build_full_stack.sh
docker push nabilafifahq/roboracer-t7:full-stack

export IMAGE=nabilafifahq/roboracer-t7:full-stack
./scripts/car_run.sh
```

```bash
# ORB spike (laptop, arm64)
./scripts/docker_build_orbslam3_mechazo.sh
# or:
docker buildx build --platform linux/arm64 -f docker/orbslam3_mechazo.dockerfile \
  -t nabilafifahq/roboracer-t7:orbslam3-mechazo --push .
```

---

## 5. Problems tackled (chronological / by area)

### 5.1 Docker / ROS middleware

| Problem | Fix |
|---------|-----|
| Fast DDS SHM issues in Docker | Default `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` in image + entrypoint + `.bashrc` |
| Livox wrong message type / frame | Patch `MID360_config.json` + `msg_MID360_launch.py` → PointCloud2, `frame_id:=laser` |
| Livox SDK not found | Build Livox-SDK2 in Dockerfile, link driver |
| Mux wrong nav topic | `config/ackermann_mux_topics.yaml` → navigation on `/drive` |
| TUM optimizer on arm64 | quadprog pin workaround, `docker/tum_overrides/`, CasADi import checks |

### 5.2 Odometry, EKF, and TF

| Problem | Fix |
|---------|-----|
| Duplicate `odom`→`base_link` (VESC + EKF fighting) | `docker/patch_vesc_yaml.py` → `vesc_to_odom_node.publish_tf: false`; EKF owns TF |
| Noisy yaw / drift on manual logs | `config/ekf_car.yaml`: fuse `/odom` + `/livox/imu`, 15 Hz on Pi |
| Odom sign wrong (forward decreased x) | `patch_vesc_yaml.py` inverts `speed_to_erpm_gain` for **odom integrator only** |
| Manual map “oval” from bad odom | Same odom sign fix + EKF architecture |

### 5.3 RC / steering / drivetrain

| Problem | Fix |
|---------|-----|
| Joystick forward = car backward | `config/joy_rc_steer_fix.yaml`: `drive-speed.scale: -0.50` |
| `joy_node` crash (bad YAML) | Restore valid `joy_rc_steer_fix.yaml` after corrupted `sed` |
| U-turn / steering range | Tune `drive-steering_angle.scale` (e.g. 1.0 rad) and VESC servo limits |
| **Car pulls right on straight** (mechanical bias) | User must hold slight left on RC — **hurts SLAM** (zig-zag odom); needs servo trim / neutral calibration |
| Autonomy “steers but won’t roll” | Mux priority + `/drive` topic fix; motor ERPM sign vs small positive commands (see `history/2026-04-13_autonomy_motor_vesc_debug.md`) |

### 5.4 LiDAR / `/scan`

| Problem | Fix |
|---------|-----|
| No `/scan` for SLAM / wall-follow | `pointcloud_to_laserscan` + `docker/config/pointcloud_to_laserscan_indoor.yaml` |
| `ros2 topic hz /scan` hangs | `/scan` is often **best_effort** — use `ros2 topic echo /scan --once` with sensor QoS or Python subscriber |
| `wall_follow` not seeing scans | Explicit BEST_EFFORT QoS on `/scan` subscription |

### 5.5 SLAM and mapping

| Problem | Fix / status |
|---------|----------------|
| Need `map` frame for competition raceline | `use_slam:=true` + `manual_map_logger` with `world_frame:=map` |
| SLAM Toolbox tuning heavy / drift | Documented; **Cartographer config added** in repo but **not yet in main Dockerfile/bringup** |
| First row snap in TUM export | `manual_map_csv_to_tum_track.py --drop-first 1` |

### 5.6 ORB-SLAM3 Docker build (arm64)

| Problem | Fix |
|---------|-----|
| `libpangolin-dev` missing on arm64 | Build Pangolin from source |
| `rosdep` `libcrypto` / `python3-natsort` | `libssl-dev`, pip `natsort`, `--skip-keys` |
| Prebuilt x86 DBoW2/g2o `.so` | Delete prebuilts; rebuild DBoW2/g2o with OpenCV + Eigen flags |
| DBoW2 `opencv2/core.hpp` not found | `-DOpenCV_INCLUDE_DIRS=/usr/include/opencv4` |
| g2o `Eigen/Core` not found | `-DCMAKE_CXX_FLAGS="-I/usr/include/eigen3"` |
| Image build + push | `nabilafifahq/roboracer-t7:orbslam3-mechazo` built and pushed |

### 5.7 ORB-SLAM3 runtime (limitations found)

| Finding | Implication |
|---------|-------------|
| Mechazo wrapper is **dataset-driven** (`mono_driver_node.py` + EuRoC sample), not live OAK | Relays to `/camera/image_raw` are infrastructure only |
| `mono_driver_node.py` needs `numpy<2` | `pip install "numpy<2"` in container |
| Hardcoded path `/root/ros2_test/src/...` | Symlink: `ln -sfn /opt/orbslam3_ws/src/ros2_orb_slam3 /root/ros2_test/src/ros2_orb_slam3` |
| OAK image ~3–4 Hz in tests | Too low for strong visual SLAM without USB3 / lighter pipeline |

### 5.8 Offline map processing (`may_28`)

| Deliverable | Script / output |
|-------------|-----------------|
| Per-run wall scatter plots | `plot_single_run.py` → `_plots/manual_map0*_map.png` |
| 4-run straight merge | `visualize_straight_track.py` |
| 4-run closed loop (phase-aligned) | `visualize_closed_loop_track.py` |
| Best-shape anchor | `manual_map03.csv` as reference (`--reference-run`, `--reference-weight 0.9`) |
| Trimmed + smooth optimizer map | `closed_loop_ref3_trimmed_smooth_map_optimizer.csv` |

---

## 6. Tools, scripts, and key files

### 6.1 Car host scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `car_run.sh` | Start container (`IMAGE` env) |
| `car_exec.sh` | Shell into running container |
| `car_status.sh` | Container status |
| `car_launch.sh` | Launch bringup (`EXTRA_LAUNCH_ARGS`) |
| `car_stop.sh` | Stop container |
| `docker_build_full_stack.sh` | Build/push main image |
| `docker_build_orbslam3_mechazo.sh` | Build/push ORB image |
| `docker_buildx_arm64.sh` | Generic arm64 buildx helper |
| `preflight_manual_map_logger.sh` | Pre-flight checks (RMW, topics, TF) |
| `manual_map_csv_to_tum_track.py` | Logger CSV → TUM 4-column track |
| `orbslam3_mechazo_topics.sh` | Check OAK/ORB-related topics |
| `orbslam3_mechazo_execs.sh` | List `ros2_orb_slam3` executables |

### 6.2 Offline map Python (`test_manual_map_new/`)

| Script | Purpose |
|--------|---------|
| `process_multi_run_map.py` | Professor-style time bins + 2σ wall filter |
| `visualize_straight_track.py` | Along-track bins → straight corridor map + optimizer CSV |
| `visualize_closed_loop_track.py` | Phase-aligned circular fusion (closed loop) |
| `plot_single_run.py` | Single CSV wall visualization |

### 6.3 Key configs

| File | Purpose |
|------|---------|
| `config/ekf_car.yaml` | EKF: `/odom` + `/livox/imu` → `odom`→`base_link` |
| `config/slam_toolbox_mapper_online_async.yaml` | SLAM Toolbox online async |
| `config/joy_rc_steer_fix.yaml` | RC axes, deadman, throttle sign |
| `config/ackermann_mux_topics.yaml` | Topic priorities |
| `config/cartographer/*.lua` | Cartographer 2D tuning (**repo only**) |
| `docker/config/pointcloud_to_laserscan_indoor.yaml` | Height slice, range for indoor |

### 6.4 Documentation index

Official runbooks: `docs/00_START_HERE.md` through `docs/11_SAFETY_...`.  
Also: `docs/RACELINE_PIPELINE.md`, `docs/MANUAL_MAP_LOGGER.md`, `docs/ORB_SLAM3_MECHAZO_DOCKER.md`, `docs/CARTOGRAPHER_EKF_PIPELINE.md`, `docs/CURSOR_AGENT_HANDOFF_local_vs_origin_main.md`.

---

## 7. Operational workflows (step-by-step)

### 7.1 Daily car bringup

```bash
# On car host
export IMAGE=nabilafifahq/roboracer-t7:full-stack
cd ~/roboracer-t7
./scripts/car_run.sh

# Inside container
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ros2 launch /race_ws/bringup.launch.py
```

### 7.2 Manual drive + SLAM map logging

```bash
# T1 — stack with SLAM
ros2 launch /race_ws/bringup.launch.py use_slam:=true

# T2 — logger (map frame)
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map \
  -p output_dir:=/race_ws/logs
```

Drive **slow, smooth, closed loop** if possible. Avoid constant left-right correction if the car pulls right.

### 7.3 Raceline pipeline (competition)

```bash
# Convert CSV → TUM input
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  /race_ws/logs/manual_map_*.csv \
  -o /race_ws/raceline_data/inputs/tracks/from_manual_map.csv \
  --drop-first 1

# After TUM optimization → copy traj_race_cl.csv to /race_ws/racelines/

# Publish path (team-tested)
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=map \
  use_slam:=true
```

### 7.4 ORB-SLAM3 spike (separate image)

```bash
export IMAGE=nabilafifahq/roboracer-t7:orbslam3-mechazo
./scripts/car_run.sh

# Inside container — one-time
python3 -m pip install --no-cache-dir "numpy<2"
mkdir -p /root/ros2_test/src
ln -sfn /opt/orbslam3_ws/src/ros2_orb_slam3 /root/ros2_test/src/ros2_orb_slam3
source /opt/orbslam3_ws/install/setup.bash

# T1 bringup (optional SLAM off for ORB test)
ros2 launch /race_ws/bringup.launch.py

# T2 OAK
ros2 launch depthai_ros_driver camera.launch.py camera_model:=OAK-D-W

# T3–T4 relays (for future live wrapper; Mechazo default uses dataset)
ros2 run topic_tools relay /oak/rgb/image_raw /camera/image_raw
ros2 run topic_tools relay /oak/imu/data /imu

# T5–T6 Mechazo nodes (dataset smoke test)
ros2 run ros2_orb_slam3 mono_node_cpp --ros-args -p node_name_arg:=mono_slam_cpp
ros2 run ros2_orb_slam3 mono_driver_node.py --ros-args \
  -p settings_name:=EuRoC -p image_seq:=sample_euroc_MH05
```

See `docs/ORB_SLAM3_MECHAZO_DOCKER.md`.

### 7.5 Offline closed-loop map (`may_28`)

```bash
cd test_manual_map_new
MPLBACKEND=Agg MPLCONFIGDIR=".mplconfig" \
python3 visualize_closed_loop_track.py \
  --data-dir may_28 \
  --glob "manual_map0*.csv" \
  --reference-run manual_map03.csv \
  --reference-weight 0.90 \
  --trim-start-frac 0.05 \
  --trim-end-frac 0.05 \
  --cross-run-mad-z 2.5 \
  --n-points 480 \
  --smooth-window 21 \
  --min-width-m 0.40 \
  --out-prefix closed_loop_ref3_trimmed_smooth
```

Outputs: `may_28/closed_loop_ref3_trimmed_smooth_map_optimizer.csv`, `_plots/closed_loop_ref3_trimmed_smooth_xy.png`.

---

## 8. ORB-SLAM3 spike (Mechazo)

**Purpose:** Evaluate visual SLAM on OAK-D Wide vs LiDAR SLAM.  
**Status:** Image builds and runs on arm64; **not** integrated as primary mapper.

**Executables:**

```text
ros2_orb_slam3 mono_node_cpp
ros2_orb_slam3 mono_driver_node.py
```

**Why not main map yet:**

- Wrapper publishes on internal topics (`/mono_py_driver/...`), expects EuRoC-style image folders.
- No live subscription to `/camera/image_raw` in default Mechazo design.
- Low OAK FPS (~3–4 Hz) observed in bringup tests.
- Output is sparse VSLAM trajectory/landmarks, not Nav2 `map.pgm`.

**Rollback:**

```bash
export IMAGE=nabilafifahq/roboracer-t7:full-stack
./scripts/car_run.sh
```

---

## 9. Offline manual map processing (`test_manual_map_new`)

### 9.1 `may_28` dataset (4 runs)

| File | Notes |
|------|--------|
| `manual_map01.csv` … `manual_map04.csv` | Primary runs for fusion |
| `manual_map.csv`, `manual_map-2.csv` | Extra captures (exclude with `--glob "manual_map0*.csv"`) |

### 9.2 Map products

| Output | Description |
|--------|-------------|
| `_plots/manual_map0*_map.png` | Per-run wall scatter |
| `straight_track_map.csv` | Straight-unwrapped 5 cm bins |
| `straight_track_map_optimizer.csv` | Smoothed corridor for optimizer |
| `corridor_map.csv` / `_plots/corridor_map.png` | Professor time-bin pipeline |
| `closed_loop_ref3_trimmed_smooth_map_optimizer.csv` | **Closed loop**, trimmed, smoothed, anchored to run 3 |

**Trusted reference run:** `manual_map03.csv` (best match to physical track).

---

## 10. SLAM / localization strategy

| Component | Role | Status on car |
|-----------|------|----------------|
| **EKF** (`robot_localization`) | Fuse wheel odom + IMU → smooth `odom`→`base_link` | **In main image + bringup** |
| **SLAM Toolbox** | `map`→`odom`, 2D occupancy | **In main image**; `use_slam:=true` |
| **Cartographer** | Alternative 2D SLAM, strong loop closure | **Config + launch in repo**; **not in `docker/dockerfile` or `bringup.launch.py` yet** |
| **ORB-SLAM3** | Visual pose / sparse map | **Separate image**; dataset mode only |
| **manual_map_logger + offline scripts** | Raceline / wall corridor for optimizer | **Active** |
| **slam_toolbox “feels bad”** | Often odom noise + manual steering correction + tuning | Mitigate with EKF, straight driving, Cartographer A/B, mechanical trim |

**Recommended direction (from team discussion):**

1. Fix steering neutral / pull-right bias.  
2. Keep EKF.  
3. Bake **Cartographer** into image and wire `use_cartographer:=true` in bringup.  
4. A/B vs SLAM Toolbox on same lap.  
5. Keep ORB-SLAM3 as optional fusion/compare, not primary 2D map.

---

## 11. Open issues — not fully tackled

### 11.1 On-vehicle / stack

| Issue | Notes |
|-------|--------|
| **Steering pull-right / trim** | User must counter-steer; degrades SLAM quality |
| **Cartographer in production image** | Lua + `launch/cartographer_2d.launch.py` exist; not apt-installed or launched from `bringup.launch.py` |
| **Cartographer vs SLAM Toolbox A/B** | Not run systematically on car with metrics |
| **ORB-SLAM3 live OAK mapping** | No custom live wrapper; Mechazo dataset path only |
| **OAK camera FPS** | ~3–4 Hz; need USB3 / lighter graph for real-time VSLAM |
| **Long hallway EKF drive test** | Pending full validation after image rebuild on vehicle |
| **Safety / kill-switch competition checklist** | `docs/11_SAFETY_FAILSAFE_AND_COMPETITION_RULES.md` — verify on hardware |
| **Some handoff files untracked** | e.g. `raceline_pure_pursuit_node.py` — ensure committed on `main` |

### 11.2 ORB-SLAM3

| Issue | Notes |
|-------|--------|
| Live topic integration | Relay topics exist; nodes don't consume them by default |
| `numpy<2` in image | Manual pip fix per container; should be baked in Dockerfile |
| Pose fusion with EKF | Not implemented |
| Comparison with `slam_toolbox` / Cartographer | Not done |

### 11.3 Mapping / optimizer

| Issue | Notes |
|-------|--------|
| **Closed-loop CSV → TUM → on-car raceline** | Offline loop map exists; not wired into TUM pipeline automatically |
| **Loop closure in live SLAM** | Depends on lap quality + SLAM backend choice |
| **Map save / reload workflow** | `nav2_map_server map_saver_cli` documented for Cartographer tutorial style; not fully automated in bringup |

### 11.4 Documentation / process

| Issue | Notes |
|-------|--------|
| Doc says `use_cartographer` in bringup | **Code gap:** only `use_slam` in current `bringup.launch.py` |
| ORB doc still shows `use_slam:=true` in T1 | Optional; clarify ORB test doesn't need SLAM |

---

## 12. Command cheat sheet

### Container

```bash
export IMAGE=nabilafifahq/roboracer-t7:full-stack
./scripts/car_run.sh
./scripts/car_exec.sh
./scripts/car_status.sh
./scripts/car_stop.sh
```

### Launch variants

```bash
# Default wall-follow + EKF
ros2 launch /race_ws/bringup.launch.py

# SLAM mapping
ros2 launch /race_ws/bringup.launch.py use_slam:=true

# Raceline publish
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=map \
  use_slam:=true

# Extra args via helper
EXTRA_LAUNCH_ARGS='use_slam:=true record_bag:=true' ./scripts/car_launch.sh
```

### Topic / TF checks

```bash
ros2 topic list | grep -E 'scan|odom|imu|map|tf'
ros2 topic hz /scan    # may hang — use echo with best_effort
ros2 topic echo /odometry/filtered --once
ros2 run tf2_ros tf2_echo map odom
ros2 run tf2_ros tf2_echo odom base_link
```

### Map save (when SLAM publishes /map)

```bash
ros2 run nav2_map_server map_saver_cli -f /race_ws/logs/my_map
```

### VESC device (UCSD-Blue example)

```bash
sudo ln -sf /dev/ttyACM0 /dev/sensors/vesc
```

### Build main image (developer laptop)

```bash
./scripts/docker_build_full_stack.sh
docker push nabilafifahq/roboracer-t7:full-stack
```

---

## Related reading (in order)

1. `docs/00_START_HERE.md`  
2. `docs/RACELINE_PIPELINE.md`  
3. `docs/MANUAL_MAP_LOGGER.md`  
4. `docs/CARTOGRAPHER_EKF_SETUP_GUIDE.md` (planned Cartographer integration)  
5. `docs/ORB_SLAM3_MECHAZO_DOCKER.md`  
6. `history/2026-04-13_autonomy_motor_vesc_debug.md`  
7. `docs/CURSOR_AGENT_HANDOFF_local_vs_origin_main.md`

---

*This document consolidates team debugging, Docker/ORB build work, offline `may_28` map processing, and architecture decisions through 2026-05-29. Update when Cartographer is baked into `bringup.launch.py` or when ORB live mapping is implemented.*
