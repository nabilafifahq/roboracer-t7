# Autonomy modes (`bringup.launch.py`)

Manual RC (`/teleop`) always has highest mux priority. Your stack (EKF, SLAM, manual map, VESC) runs in **all** modes.

## Team raceline path (Derek + Ricky — use this)

Derek’s branch implements **optimized TUM CSV → ROS 2 topic**. That is what was tested on the car:

| Step | Component | Topic |
|------|-----------|--------|
| 1 | `traj_csv_path_publisher` | publishes `nav_msgs/Path` on **`/global_path`** |
| 2 (optional) | Nav2 + vector pursuit + bridge | follows path → **`/nav2_cmd_ackermann`** |

### Mode A — CSV → topic only (**tested**)

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=odom
```

Verify:

```bash
ros2 topic echo /global_path --once
```

Drive manually with RC while visualizing the path in RViz, or record a bag.

Aliases: `autonomy:=csv_path` (same as `raceline_path`).

### Mode B — CSV + Nav2 vector pursuit (full Derek stack)

Adds Nav2, `global_path_follow_bridge`, and `twist_to_ackermann`. Use when Mode A looks correct and you are ready to close the loop on the car.

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=odom
```

Aliases: `autonomy:=nav2_vector_pursuit`, `autonomy:=pure_pursuit`.

Mux: **`/nav2_cmd_ackermann`** (priority 50) &lt; **`/teleop`** (100).

### Map-frame raceline (SLAM + competition pipeline)

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  use_slam:=true \
  pursuit_world_frame:=map \
  raceline_csv:=/race_ws/racelines/my_race.csv
```

Log with `manual_map_logger` using `world_frame:=map`; convert with `manual_map_csv_to_tum_track.py` (see `docs/MANUAL_MAP_LOGGER.md`).

---

## Other modes

| `autonomy` | Purpose | Output |
|------------|---------|--------|
| `wall_follow` (default) | LiDAR corridor follow | `/drive` (mux 10) |
| `raceline_pure_pursuit` / `raceline_geometric` | Lightweight geometric pursuit (**experimental**, not team-tested) | `/drive` (mux 10) |

---

## Pipeline overview (combined repo)

```text
manual_map_logger (your work) -> TUM optimizer -> traj_race_cl.csv
       |
       v
traj_csv_path_publisher (Derek) -> /global_path
       |
       +--[raceline_path] stop here (team tested)
       |
       +--[raceline] Nav2 vector pursuit -> /nav2_cmd_ackermann -> mux -> VESC
```

Supporting scripts:

- `scripts/manual_map_csv_to_tum_track.py` — logger CSV → TUM `inputs/tracks/*.csv`
- `scripts/traj_race_cl_to_waypoints.py` — Derek; waypoint export helper

---

## VESC on UCSD-Blue

```bash
sudo ln -sf /dev/ttyACM0 /dev/sensors/vesc
```

STM = `ttyACM0`, Arduino RC = `ttyACM1`.

---

## Rebuild image after pull

```bash
docker build -f docker/dockerfile -t nabilafifahq/roboracer-t7:main-latest .
docker push nabilafifahq/roboracer-t7:main-latest
```

On car: `docker pull`, then your usual `docker run` + launch.
