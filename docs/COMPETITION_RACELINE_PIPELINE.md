# Competition raceline: CSV → optimizer → pure pursuit (map frame)

`manual_map_logger` with **`world_frame:=odom`** records a **drifting local** path. That is fine for stack debug, but **not** a venue-accurate centerline for TUM `global_racetrajectory_optimization` + on-car pure pursuit at a **fixed** track.

This pipeline uses **SLAM Toolbox** (optional in `bringup.launch.py`) so poses are logged in **`map`**, then the same CSV → TUM → raceline CSV flow matches **global** geometry.

---

## What we added in software

| Piece | Role |
|--------|------|
| `use_slam:=true` on `bringup.launch.py` | Starts `slam_toolbox` **online async** mapping (`map` → `odom`; EKF still publishes `odom` → `base_link`). |
| `/race_ws/config/slam_toolbox_mapper_online_async.yaml` | `base_link`, `/scan`, tighter motion thresholds for slow RC mapping. |
| `pursuit_world_frame:=map` | `raceline_pure_pursuit` looks up **`map` → `base_link`** so the car follows the raceline in the **same** frame as the optimizer output. |
| `manual_map_logger` **`world_frame:=map`** | CSV **`x,y,yaw`** are in **`map`** (globally consistent while SLAM is healthy). |

Rebuild / pull the Docker image that includes **`ros-humble-slam-toolbox`** and the YAML copy (see `docker/dockerfile`).

When recording a **SLAM mapping** session with `ros2 bag record`, add **`/map`** (and optionally **`/map_metadata`**) to your topic list so the grid is saved (those topics exist only when SLAM is running).

---

## On-vehicle procedure (quick)

### 1) Bringup with SLAM

```bash
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_slam:=true
```

Wait until **`map` → `odom`** exists (SLAM lifecycle comes up; first scans may take **10–30 s**).

### 2) Preflight (second shell, `docker exec` if needed)

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash

ros2 topic hz /scan --window 15
ros2 run tf2_ros tf2_echo map base_link
```

You want **`tf2_echo`** translations to update **smoothly** (no multi-meter jumps). If **`map`** or **`map` → `base_link`** is missing, do **not** log yet.

### 3) Log in **`map`** frame

```bash
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map \
  -p robot_frame:=base_link \
  -p record_hz:=20.0 \
  -p output_csv:=/race_ws/logs/map_hall_$(date +%Y%m%d_%H%M%S).csv
```

Drive **one deliberate mapping lap** (steady speed, full track). Keep **`ros2 topic hz /scan`** or the logger subscribed the whole time.

### 4) Sanity on CSV

```bash
awk -F, 'NR>1 {print $9}' /race_ws/logs/map_hall_....csv | sort -u | wc -l
```

Many unique **`scan_stamp_sec`** values (not ~4).

### 5) Convert to TUM track format

On laptop or in container (from repo):

```bash
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  /path/to/map_hall_....csv \
  -o raceline_data/inputs/tracks/from_manual_map.csv \
  --drop-first 1
```

`--drop-first 1` removes the first valid pose row, which often fixes a **~1–2 m SLAM startup jump** between the first and second logged samples when `world_frame:=map`.

Feed **`from_manual_map.csv`** (or your chosen path) into **TUM global_racetrajectory_optimization** per your team workflow; export optimized trajectory CSV.

### 6) On-car pure pursuit in **`map`**

Copy the optimized CSV into the image (e.g. `/race_ws/racelines/my_race.csv`) and launch:

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_pure_pursuit \
  use_slam:=true \
  pursuit_world_frame:=map \
  raceline_csv:=/race_ws/racelines/my_race.csv
```

**SLAM must still be running** (or replaced by **localization** with a saved map) so **`map` → `base_link`** stays defined. If you only run mapping once, save a **`.posegraph` / serialized map`** per slam_toolbox docs and switch to **localization** mode for the race—that is a follow-up tuning step.

---

## What to send back if something fails

Paste (redact secrets):

1. `ros2 topic list | egrep 'map|scan|tf'`
2. `ros2 topic info /tf -v` (first ~40 lines)
3. `ros2 run tf2_ros tf2_echo map base_link` (10 lines) **after** `use_slam:=true`
4. First 5 data lines of the CSV (header + rows)

---

## Limits (honest)

- **SLAM drift / loop closure** still affects global shape; competition quality depends on **good mapping lap**, **loop closures** on long tracks, and CPU headroom on the Pi.
- **Saved map + localization** is usually what you want for the **race run** itself; this doc describes **mapping + pursuit in `map`** on one bringup for a **fast path** to valid geometry.
