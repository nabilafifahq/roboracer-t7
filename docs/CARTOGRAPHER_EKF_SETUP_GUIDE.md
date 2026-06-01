# Cartographer + EKF — complete setup guide (RoboRacer T7)

Single reference for **what EKF and Cartographer do**, **what was added to the repo**, **assumptions**, **track requirements**, **data flow**, **commands (drive → CSV → raceline)**, **CSV guarantees**, **topics/config**, and **known quirks**.

Related: `docs/CARTOGRAPHER_EKF_PIPELINE.md` (same content, maintained in parallel) · `docs/COMPETITION_RACELINE_PIPELINE.md` · `docs/MANUAL_MAP_LOGGER.md`

---

## What these features do (simple terms)

### EKF (`robot_localization` / `ekf_node`)

The car has several partial guesses about motion:

- **Wheel odometry** (`/odom` from VESC): how far the wheels turned and how much you steered — good short-term, **drifts** over time.
- **IMU** (`/livox/imu`): rotation and acceleration from the Livox — helps **heading** and smooth motion.

The **EKF** blends those into one estimate and publishes **`odom` → `base_link`**. It does **not** build a map; it only improves **local** pose for control, logging in `odom`, and as motion input to SLAM.

### Cartographer

**SLAM** uses LiDAR (`/scan`) to build a 2D map and estimate pose in a fixed **`map`** frame. It publishes **`map` → `odom`**, correcting long-term drift that wheel odometry cannot fix.

**Cartographer** is Google’s SLAM stack (different backend than **SLAM Toolbox**). This team added it because SLAM Toolbox maps were **too drift/noisy** for competition-grade racelines. The **CSV pipeline is unchanged** — only pose quality in `map` should improve.

### How they work together

| Layer | Job | Main TF / output |
|-------|-----|------------------|
| **EKF** | Smooth local motion | `odom` → `base_link`, `/odometry/filtered` |
| **Cartographer** | Global map + drift correction | `map` → `odom`, `/map` |
| **manual_map_logger** | Record path + wall distances | `manual_map_*.csv` via TF `map` → `base_link` |

---

## Software added in the repo

| File / change | Purpose |
|---------------|---------|
| `config/cartographer/map_builder.lua` | Cartographer map builder |
| `config/cartographer/trajectory_builder.lua` | 2D scan matcher + motion filter (hallway tuning) |
| `config/cartographer/roboracer_2d.lua` | Main options: frames, external EKF odom |
| `launch/cartographer_2d.launch.py` | `cartographer_node` + occupancy grid node |
| `bringup.launch.py` | `use_cartographer:=true`; EKF always on; SLAM Toolbox off when Cartographer on |
| `docker/dockerfile` | `ros-humble-cartographer`, `ros-humble-cartographer-ros` |
| `scripts/preflight_manual_map_logger.sh` | Checks `/map` and `map` → `base_link` |
| `docs/CARTOGRAPHER_EKF_PIPELINE.md` | Technical pipeline doc |

**EKF** was already integrated (`config/ekf_car.yaml`, `ekf_node` in bringup). **Cartographer** remaps odom to **`/odometry/filtered`** (EKF output), not raw VESC `/odom`.

**Rebuild the Docker image** after pulling these changes:

```bash
# Mac → Raspberry Pi (linux/arm64, buildx emulated ARM):
export DOCKER_USER=<your_dockerhub_username>
docker login
./scripts/docker_buildx_arm64.sh

# Same machine as car arch / native build:
./scripts/docker_build_full_stack.sh
```

Inside the container after pull:

```bash
ros2 pkg prefix cartographer_ros
```

---

## Launch flags (quick reference)

| Flag | Effect |
|------|--------|
| *(default)* | EKF on; no global SLAM |
| `use_cartographer:=true` | Cartographer 2D (`map` → `odom`) |
| `use_slam:=true` | SLAM Toolbox (`map` → `odom`) — **ignored if** `use_cartographer:=true` |
| **Do not run both SLAM backends** | Only one node should publish `map` → `odom` |

```bash
# On car / in container
ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true

# From host
EXTRA_LAUNCH_ARGS='autonomy:=wall_follow use_cartographer:=true' ./scripts/car_launch.sh
```

---

## 1) Assumptions the stack makes

### EKF (`/race_ws/config/ekf_car.yaml`)

| Assumption | Detail |
|------------|--------|
| **Planar car** | `two_d_mode: true` — ignores significant 3D motion |
| **Frames (REP-105)** | `odom` → `base_link` from EKF; `world_frame` is **`odom`** (EKF does not fuse global map pose) |
| **Wheel odom** | `vesc_to_odom` publishes **`/odom`**; **`publish_tf: false`** so only EKF broadcasts `odom` → `base_link` |
| **IMU** | Livox built-in IMU on **`/livox/imu`**; orientation + angular rates + linear accel fused with wheel data |
| **TF tree** | `f1tenth_stack` static **`base_link` → `laser`**; Livox cloud/scan in **`laser`** frame |
| **Rate** | Filter runs at **15 Hz** on Pi (tuned for CPU load) |

### Cartographer (`/race_ws/config/cartographer/roboracer_2d.lua`)

| Assumption | Detail |
|------------|--------|
| **2D SLAM** | Uses **`sensor_msgs/LaserScan`** on **`/scan`** (not raw 3D cloud) |
| **Scan source** | `pointcloud_to_laserscan` slices Livox cloud (height band, 180° FOV) — same as wall-follow |
| **External odometry** | `provide_odom_frame = false` — **EKF** owns `odom` → `base_link`; Cartographer owns **`map` → `odom`** |
| **Odom topic** | Subscribes to **`/odometry/filtered`** (EKF output), not raw VESC `/odom` |
| **IMU in Cartographer** | **Off** by default (`use_imu_data = false`) — EKF already fuses IMU; avoids frame quirks |
| **Indoor range** | `min_range` 0.2 m, `max_range` 12 m — matches `pointcloud_to_laserscan_indoor.yaml` |
| **Docker / Pi** | Cartographer is CPU-heavy; expect higher load than SLAM Toolbox alone |

### What is *not* assumed

- Cartographer does **not** replace `manual_map_logger` or the TUM optimizer — it only improves **`map`** pose quality.
- No automatic “save map and localize later” workflow is wired in bringup yet (`.pbstream` / pure localization is follow-up work).

---

## 2) Race track / mapping requirements

| Requirement | SLAM / Cartographer | `manual_map_logger` CSV |
|-------------|---------------------|---------------------------|
| **Closed loop** | **Strongly recommended** on long tracks (loop closure). Not strictly required for a short hallway. | Optional; `--close-loop` only affects TUM **conversion**, not logging |
| **Minimum distance** | Cartographer motion filter: ~**5 cm** translation or **~0.12 rad** rotation between processed scans (`trajectory_builder.lua`). Standing still → few map updates. | No hard minimum; need motion so TF and `/scan` update |
| **Minimum duration** | **10–30 s** after launch before first stable **`map` → `odom`** | Log for a full lap while `/scan` + TF are healthy |
| **Speed** | Slow, smooth RC lap (~walking pace) | Same |
| **Environment** | Walls visible in `/scan` height slice; glass/open areas hurt matching | Left/right wall columns need valid laser ranges in configured angular windows |
| **Overlap** | Revisiting the same corridor helps loop closure | — |

**F1TENTH / hallway scale:** target **one full slow lap** with loop closure. A partial lap can still produce a CSV, but global shape may drift on long straights.

---

## 3) Behind the scenes (workflow / data flow)

```text
RC /joy → /teleop ──┐
                    ├→ ackermann_mux → VESC → vesc_to_odom → /odom ──┐
                    │                                                 ├→ EKF → TF: odom→base_link
Livox → /livox/imu ─┘                                                 │         /odometry/filtered
                                                                      │
Livox → /livox/lidar → pointcloud_to_laserscan → /scan ───────────────┼→ Cartographer
                                                                      │         TF: map→odom
                                                                      │         /map (grid)
manual_map_logger: TF lookup map→base_link + /scan → manual_map_*.csv
```

**Frame chain when Cartographer is on:**

`map` → `odom` (Cartographer) → `base_link` (EKF) → `laser` (static)

**Who publishes what**

| Transform / topic | Publisher |
|-------------------|-----------|
| `odom` → `base_link` | **EKF** only |
| `map` → `odom` | **Cartographer** (or SLAM Toolbox if `use_slam:=true` and Cartographer off) |
| `base_link` → `laser` | static TF (`f1tenth_stack`) |
| `/odom` | VESC integrator (input to EKF) |
| `/odometry/filtered` | EKF (input to Cartographer) |
| `/scan` | `pointcloud_to_laserscan` |

---

## 4) Command sequence: driving → CSV → raceline

Run inside the container unless noted. Source ROS and Cyclone DDS first:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
```

### Step A — Start stack (EKF + Cartographer)

```bash
ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true
```

### Step B — Preflight (second shell)

```bash
/race_ws/scripts/preflight_manual_map_logger.sh
ros2 run tf2_ros tf2_echo map base_link
```

Wait until `map` → `base_link` updates **smoothly** (often **10–30 s** after `/scan` is healthy). Do not start logging until then.

### Step C — Log CSV in `map` frame

```bash
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map \
  -p robot_frame:=base_link \
  -p record_hz:=20.0 \
  -p output_csv:=/race_ws/logs/map_cart_$(date +%Y%m%d_%H%M%S).csv
```

Drive **one slow, complete lap** with RC deadman on. `Ctrl+C` the logger when finished.

### Step D — Sanity-check CSV

```bash
wc -l /race_ws/logs/map_cart_*.csv
awk -F, 'NR>1 {print $9}' /race_ws/logs/map_cart_*.csv | sort -u | wc -l
```

Expect **many rows** and **many unique** `scan_stamp_sec` values (not ~4).

### Step E — Convert to TUM track input

```bash
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  /race_ws/logs/map_cart_YYYYMMDD_HHMMSS.csv \
  -o /race_ws/raceline_data/inputs/tracks/from_manual_map.csv \
  --drop-first 1
```

`--drop-first 1` removes the first valid row after filtering (often fixes a **~1–2 m SLAM startup snap**).

### Step F — TUM optimizer (offline)

Run **global_racetrajectory_optimization** on `from_manual_map.csv` → export **`traj_race_cl.csv`** (see `docs/COMPETITION_RACELINE_PIPELINE.md`).

### Step G — On-car pursuit

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  use_cartographer:=true \
  pursuit_world_frame:=map \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv
```

**`map` → `base_link` must stay valid** for the whole run (keep Cartographer running, or add saved-map localization later).

---

## 5) Does this guarantee a CSV? Conversion complexity?

| Step | Guaranteed? | Notes |
|------|-------------|--------|
| **`manual_map_logger` → CSV** | **No** | Needs TF **`map` → `base_link`** and **`/scan`**; skips rows if missing |
| **CSV → TUM track CSV** | **Yes**, if logger wrote valid rows | `scripts/manual_map_csv_to_tum_track.py` — **no Cartographer-specific converter** |
| **TUM → `traj_race_cl.csv`** | Depends on optimizer | Same team workflow as before |

**Nothing new is required for conversion.** Cartographer only changes pose quality in **`map`**, not the CSV schema.

**Logger columns (unchanged):** `time_sec`, `frame_id`, `x`, `y`, `z`, `yaw_rad`, `left_wall_m`, `right_wall_m`, `scan_stamp_sec`.

**Optional conversion flags:** `--drop-first`, `--moving-min-step`, `--close-loop`, `--step` (see script `--help`).

---

## 6) Topics and configuration checklist

### Must be healthy before logging

| Topic / TF | Role | Check |
|------------|------|--------|
| `/joy`, `/teleop` | Manual drive | `ros2 topic hz /teleop` |
| `/odom` | EKF input | `ros2 topic hz /odom` |
| `/livox/imu` | EKF input | `ros2 topic hz /livox/imu` |
| `/odometry/filtered` | Cartographer odom input | `ros2 topic hz /odometry/filtered` |
| `/livox/lidar` | Cloud source | `ros2 topic hz /livox/lidar` |
| `/scan` | Cartographer + logger | `ros2 topic hz /scan` |
| TF `odom` → `base_link` | EKF | `ros2 run tf2_ros tf2_echo odom base_link` |
| TF `map` → `base_link` | Logger with `world_frame:=map` | `ros2 run tf2_ros tf2_echo map base_link` |
| `/map` | Visualization / bags | Optional for CSV itself |

### Config files (in Docker image)

| Path | Purpose |
|------|---------|
| `/race_ws/config/ekf_car.yaml` | EKF fusion |
| `/race_ws/config/cartographer/*.lua` | Cartographer |
| `/race_ws/config/pointcloud_to_laserscan_indoor.yaml` | `/scan` from Livox |
| `/race_ws/config/joy_rc_steer_fix.yaml` | RC teleop + deadman |

### Launch / node parameters

```bash
use_cartographer:=true       # enable Cartographer in bringup
pursuit_world_frame:=map     # raceline / path publisher frame
world_frame:=map             # manual_map_logger parameter
```

### Do not run together

- `use_cartographer:=true` **and** `use_slam:=true` → bringup starts **only Cartographer** (SLAM Toolbox suppressed).

---

## 7) Expected quirks and failure modes

| Symptom | Likely cause |
|---------|----------------|
| No `/scan` | Livox QoS / network — `docs/07_TROUBLESHOOTING.md` §10 |
| `map` frame missing | Cartographer not started or car not moving yet |
| Multi-meter jumps in `tf2_echo map base_link` | Fast driving, poor loop closure, or startup — try `--drop-first 1` |
| Cartographer dies / high CPU on Pi | Close RViz; mapping lap only; reduce bag topics |
| Duplicate TF on `odom` → `base_link` | `vesc_to_odom` `publish_tf: true` — rebuild image with VESC patch |
| Empty `left_wall_m` / `right_wall_m` | Open area or wrong laser windows — CSV still has `x`, `y`, `yaw` |
| Logger writes few rows | TF timeouts — drive longer; fix `map` → `base_link` |
| Pursuit diverges | Raceline in `map` but `use_cartographer:=false` on race day |
| Cartographer map still noisy | Bad `/scan` slice or EKF odom — tune pointcloud height band or mapping lap |

**Cartographer-specific**

- First **~10–30 s**: `map` → `odom` may be unstable — **do not log yet**.
- **2D height slice** can add clutter noise — tune `min_height` / `max_height` in `pointcloud_to_laserscan_indoor.yaml`.
- **`.pbstream` save + pure localization`** is not in bringup yet — race runs currently expect **live** Cartographer (or future localization node).

---

## EKF-only mode (no Cartographer)

For wall-follow or logging in **`odom`** (drifting but always available):

```bash
ros2 launch /race_ws/bringup.launch.py
ros2 run reactive_control manual_map_logger --ros-args -p world_frame:=odom
```

Use **`pursuit_world_frame:=odom`** for raceline modes when not using SLAM.

---

## Related documentation

| Doc | Contents |
|-----|----------|
| `docs/COMPETITION_RACELINE_PIPELINE.md` | Competition CSV → TUM → pursuit (`use_cartographer` or `use_slam`) |
| `docs/MANUAL_MAP_LOGGER.md` | Logger parameters, `map` vs `odom`, CSV columns |
| `docs/RACELINE_PIPELINE.md` | End-to-end raceline overview |
| `docs/MANUAL_AUTONOMY_NODE_TOPIC_FLOW.md` | Full node/topic map |
| `docs/07_TROUBLESHOOTING.md` | Livox, `/scan`, mux, VESC |
