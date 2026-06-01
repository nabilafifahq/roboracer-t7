# Cartographer + EKF: assumptions, workflow, and CSV pipeline

> **Full guide (simple terms + code changes + all 7 sections):** see **`docs/CARTOGRAPHER_EKF_SETUP_GUIDE.md`**.

This document answers how **EKF** (`robot_localization`) and **Cartographer** fit the RoboRacer T7 stack, from manual driving through **`manual_map_*.csv`** to TUM raceline output.

**Launch flags**

| Flag | Effect |
|------|--------|
| *(default)* | EKF always on; no global SLAM |
| `use_cartographer:=true` | Cartographer 2D (`map` → `odom`) |
| `use_slam:=true` | SLAM Toolbox (`map` → `odom`) — **ignored if** `use_cartographer:=true` |
| Do **not** set both SLAM backends at once | Only one should publish `map` → `odom` |

---

## 1) Assumptions the stack makes

### EKF (`config/ekf_car.yaml`)

| Assumption | Detail |
|------------|--------|
| **Planar car** | `two_d_mode: true` — ignores significant 3D motion |
| **Frames (REP-105)** | `odom` → `base_link` from EKF; `world_frame` is **`odom`** (EKF does not fuse global map pose) |
| **Wheel odom** | `vesc_to_odom` publishes **`/odom`**; **`publish_tf: false`** so only EKF broadcasts `odom` → `base_link` |
| **IMU** | Livox built-in IMU on **`/livox/imu`**; orientation + angular rates + linear accel fused with wheel data |
| **TF tree** | `f1tenth_stack` static **`base_link` → `laser`**; Livox cloud/scan in **`laser`** frame |
| **Rate** | Filter runs at **15 Hz** on Pi (tuned for CPU load) |

### Cartographer (`config/cartographer/roboracer_2d.lua`)

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

- Cartographer does **not** replace `manual_map_logger` or TUM optimizer — it only improves **`map`** pose quality.
- No automatic “save map and localize later” workflow is wired in bringup yet (manual Cartographer CLI / follow-up).

---

## 2) Track / mapping requirements

| Requirement | SLAM / Cartographer | `manual_map_logger` CSV |
|-------------|---------------------|---------------------------|
| **Closed loop** | **Strongly recommended** for long tracks — loop closure reduces drift. Not strictly required for a short hallway segment. | Optional; `--close-loop` only affects TUM **conversion**, not logging |
| **Minimum distance** | Cartographer **motion filter**: ~**5 cm** translation or **~0.12 rad** rotation between processed scans (see `trajectory_builder.lua`). Standing still = few map updates. | No hard minimum; need enough motion that TF and `/scan` update |
| **Minimum duration** | Allow **10–30 s** after launch for first stable **`map` → `odom`** before logging | Entire lap while `/scan` + TF are healthy |
| **Speed** | Slow, smooth RC lap (~walking pace); jerky driving hurts scan match | Same |
| **Environment** | Visible walls in `/scan` height slice; glass / open space = gaps | Left/right wall columns need valid ranges in chosen angular windows |
| **Overlap** | Revisiting the same corridor helps loop closure | — |

**Hallway / F1TENTH-scale track:** one full lap with loop closure is the usual target. A **partial** lap can still produce a CSV, but global shape may drift on long straights.

---

## 3) Behind the scenes (data flow)

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

**Frame chain when Cartographer is on**

`map` → `odom` (Cartographer) → `base_link` (EKF) → `laser` (static)

**Who publishes what**

| Transform / topic | Publisher |
|-------------------|-----------|
| `odom` → `base_link` | **EKF** only |
| `map` → `odom` | **Cartographer** (or SLAM Toolbox if `use_slam:=true`) |
| `base_link` → `laser` | static TF (`f1tenth_stack`) |
| `/odom` | VESC integrator (input to EKF) |
| `/odometry/filtered` | EKF (input to Cartographer) |
| `/scan` | `pointcloud_to_laserscan` |

---

## 4) Command sequence: drive → CSV → raceline

Run inside the container (or `./scripts/car_launch.sh` with `EXTRA_LAUNCH_ARGS`).

### A — Start stack (EKF + Cartographer)

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash

ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true
```

Or from host:

```bash
EXTRA_LAUNCH_ARGS='autonomy:=wall_follow use_cartographer:=true' ./scripts/car_launch.sh
```

### B — Preflight (second shell)

```bash
/race_ws/scripts/preflight_manual_map_logger.sh
ros2 run tf2_ros tf2_echo map base_link
```

Wait until `map` → `base_link` updates smoothly (often **10–30 s** after `/scan` is healthy).

### C — Log CSV in `map` frame

```bash
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map \
  -p robot_frame:=base_link \
  -p record_hz:=20.0 \
  -p output_csv:=/race_ws/logs/map_cart_$(date +%Y%m%d_%H%M%S).csv
```

Drive **one slow, complete lap** with deadman on. `Ctrl+C` the logger when done.

### D — Sanity-check CSV

```bash
wc -l /race_ws/logs/map_cart_*.csv
awk -F, 'NR>1 {print $9}' /race_ws/logs/map_cart_*.csv | sort -u | wc -l
```

Expect many rows and many unique `scan_stamp_sec` values (not ~4).

### E — Convert to TUM track input (same as SLAM Toolbox path)

```bash
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  /race_ws/logs/map_cart_YYYYMMDD_HHMMSS.csv \
  -o /race_ws/raceline_data/inputs/tracks/from_manual_map.csv \
  --drop-first 1
```

`--drop-first 1` still helps if the first `map` pose snaps after SLAM startup.

### F — TUM optimizer (offline)

Run **global_racetrajectory_optimization** on `from_manual_map.csv` → export **`traj_race_cl.csv`** (team workflow; see `docs/COMPETITION_RACELINE_PIPELINE.md`).

### G — On-car pursuit (Cartographer or localization still required)

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  use_cartographer:=true \
  pursuit_world_frame:=map \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv
```

**`map` → `base_link` must stay valid** during the run (keep Cartographer mapping/localization running, or add saved-map localization later).

---

## 5) Does this guarantee a CSV? Conversion complexity?

| Step | Guaranteed? | Notes |
|------|-------------|--------|
| **`manual_map_logger` → CSV** | **No** — needs TF `map`→`base_link` + `/scan` | Logger skips rows if TF or scan missing |
| **CSV → TUM track CSV** | **Yes**, if logger produced valid rows | Existing script; **no Cartographer-specific converter** |
| **TUM → `traj_race_cl.csv`** | Depends on optimizer inputs | Same as before |

**Nothing new is required for conversion** — Cartographer only changes pose quality in **`map`**, not the CSV schema.

Logger columns (unchanged): `time_sec`, `frame_id`, `x`, `y`, `z`, `yaw_rad`, `left_wall_m`, `right_wall_m`, `scan_stamp_sec`.

Optional conversion flags (same script): `--drop-first`, `--moving-min-step`, `--close-loop`, `--step`.

---

## 6) Topics and configuration checklist

### Must be running / healthy before logging

| Topic / TF | Role | Check |
|------------|------|--------|
| `/joy`, `/teleop` | Manual drive | `ros2 topic hz /teleop` |
| `/odom` | EKF input | `ros2 topic hz /odom` |
| `/livox/imu` | EKF input | `ros2 topic hz /livox/imu` |
| `/odometry/filtered` | Cartographer odom input | `ros2 topic hz /odometry/filtered` |
| `/livox/lidar` | Cloud source | `ros2 topic hz /livox/lidar` |
| `/scan` | Cartographer + logger | `ros2 topic hz /scan` |
| TF `odom`→`base_link` | EKF | `tf2_echo odom base_link` |
| TF `map`→`base_link` | Logger `world_frame:=map` | `tf2_echo map base_link` |
| `/map` | Visualization / bags | optional for CSV |

### Config files (image paths)

| File | Purpose |
|------|---------|
| `/race_ws/config/ekf_car.yaml` | EKF fusion |
| `/race_ws/config/cartographer/*.lua` | Cartographer |
| `/race_ws/config/pointcloud_to_laserscan_indoor.yaml` | `/scan` |
| `/race_ws/config/joy_rc_steer_fix.yaml` | RC teleop |

### Launch arguments

```bash
use_cartographer:=true          # Cartographer on
pursuit_world_frame:=map        # raceline modes in map frame
world_frame:=map                # manual_map_logger param
```

### Do not run together

- `use_cartographer:=true` **and** `use_slam:=true` → only Cartographer starts (SLAM Toolbox suppressed).

---

## 7) Expected quirks / failure modes

| Symptom | Likely cause |
|---------|----------------|
| No `/scan` | Livox QoS / network; see `docs/07_TROUBLESHOOTING.md` §10 |
| `map` frame missing | Cartographer not started or no motion yet |
| Multi-meter jumps in `tf2_echo map base_link` | Mapping too fast, bad loop closure, or startup — try `--drop-first 1` |
| Cartographer dies / high CPU on Pi | Lower load: close RViz, reduce bag topics, mapping lap only |
| Duplicate TF errors | `vesc_to_odom` `publish_tf: true` — rebuild image with VESC patch |
| Empty `left_wall_m` / `right_wall_m` | Open area or wrong angular windows — CSV still has `x,y,yaw` |
| Logger writes few rows | TF timeouts — increase drive time; check `map`→`base_link` |
| Pursuit diverges | Raceline in `map` but `use_cartographer:=false` on race day |
| Cartographer vs SLAM Toolbox maps differ | Same `/scan`; Cartographer may look cleaner but still depends on lap quality |

**Cartographer-specific**

- First **~10–30 s**: `map`→`odom` may be unstable — do not log yet.
- **2D slice** limits: ceiling/floor clutter in height band can add noise (tune `min_height`/`max_height` in pointcloud YAML).
- Saving `.pbstream` / pure localization is **not** in bringup yet — race runs still expect live Cartographer (or future localization node).

---

## Rebuild image after pulling these changes

```bash
# Mac → Pi (arm64): ./scripts/docker_buildx_arm64.sh
./scripts/docker_build_full_stack.sh   # native host arch
```

See `docs/02_DOCKER_BUILD_PUSH.md` §2d for buildx details.

Verify Cartographer is in the image:

```bash
ros2 pkg prefix cartographer_ros
```

---

## Related docs

- `docs/COMPETITION_RACELINE_PIPELINE.md` — same CSV→TUM flow with `use_slam:=true` (swap to `use_cartographer:=true`)
- `docs/MANUAL_MAP_LOGGER.md` — logger parameters and `map` vs `odom`
- `docs/RACELINE_PIPELINE.md` — end-to-end raceline overview
