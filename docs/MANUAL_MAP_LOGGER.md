# Manual map logger (`manual_map_logger`)

This document describes a small ROS 2 node that **records where the car is** and **how far the walls are on the left and right** while someone **drives manually** (for example with the RC controller). The output is a **CSV file** you can feed into a raceline optimizer or other offline tools later.

---

## Big picture (what problem does this solve?)

During a competition or practice, you may want a **dataset of poses plus corridor widths** along the track. A human drives one lap; the computer samples data at a fixed rate and saves it. That is cheaper and simpler than full SLAM for “I just need a path and approximate wall distances along it.”

This node does **not** build an occupancy grid or a pretty map image. It **logs samples**: time, position, heading, and two laser-derived distances (left and right “wall” distances in chosen angular sectors).

---

## What we added (files)

| File | What changed |
|------|----------------|
| `wall_follow_script/reactive_control/manual_map_logger.py` | **New** Python node: subscribes to laser, uses TF2, writes CSV. |
| `wall_follow_script/setup.py` | Registers the executable name `manual_map_logger` so `ros2 run reactive_control manual_map_logger` works. |
| `wall_follow_script/package.xml` | Declares dependencies so the build system installs what the node needs (`rclpy`, `geometry_msgs`, `tf2_ros`, etc.). |

---

## Why `/tf` is not read “directly” as x and y

In ROS 2, **`/tf`** (and `/tf_static`) are **streams of transforms** between named coordinate frames (for example `odom` and `base_link`). There is **no single** “the x,y of the robot” until you decide:

1. **Which frame is the world?** (often `map` or `odom`)
2. **Which frame is the robot?** (often `base_link`)

The node uses **`tf2_ros`** (`Buffer` + `TransformListener`) to ask: “Give me the transform from **`world_frame`** to **`robot_frame`**.” From that transform it reads **translation** \((x, y, z)\) and **rotation** (converted to **yaw** around the vertical axis).

So: **same information as TF**, but with an explicit, correct pair of frames instead of guessing from raw messages.

---

## What each CSV column means

| Column | Meaning |
|--------|--------|
| `time_sec` | ROS time when the row was written (seconds, floating point). |
| `frame_id` | The **parent** frame name used for position (same as `world_frame`, e.g. `odom`). |
| `x`, `y`, `z` | Position of the robot frame origin **expressed in the world frame** (meters). For a ground car, `z` is often small or noisy. |
| `yaw_rad` | Heading of the robot in the world frame, yaw only (radians). |
| `left_wall_m` | **Shortest valid** laser range in the **left** angular window (see below). Empty if no valid hit in that window. |
| `right_wall_m` | Same for the **right** window. |
| `scan_stamp_sec` | Timestamp from the laser message header (when that scan was taken). |

Together, each row is one **snapshot**: “At about this time, the car was here and the walls on my chosen left/right cones were about this far.”

---

## How left / right wall distances are computed

The laser publishes `sensor_msgs/LaserScan`: a list of ranges at angles `angle_min`, `angle_min + angle_increment`, … in the laser’s **frame** (check `scan.header.frame_id`; often aligned with the robot).

The node picks two **angular intervals** (in radians):

- **Left window** (default about `1.10` to `1.75` rad): beams pointing to the car’s **left** in that convention.
- **Right window** (default about `-1.75` to `-1.10` rad): beams to the **right**.

For each window it takes the **minimum** range among readings that are **finite** and strictly between `range_min` and `range_max` from the message. That approximates “closest obstacle on that side” inside that cone.

If your lidar is mounted differently or your track layout needs different cones, change `left_window_rad` and `right_window_rad` (see parameters below).

---

## QoS note (`/scan`)

Many laser drivers use **best-effort** reliability. The node subscribes with **BEST_EFFORT** and **VOLATILE** durability so it can receive those scans. If your stack uses reliable-only laser topics, you would need to match that QoS (a small code change).

---

## Parameters

| Parameter | Default | Role |
|-----------|---------|------|
| `world_frame` | `map` | “World” parent frame for the pose lookup. |
| `robot_frame` | `base_link` | Robot child frame. |
| `scan_topic` | `/scan` | Laser topic to subscribe to. |
| `output_csv` | `/race_ws/logs/manual_map.csv` | Output CSV path (parent directories are created if needed). |
| `record_hz` | `10.0` | How often to append a row (if a scan was received). |
| `left_window_rad` | `[1.10, 1.75]` | Left sector bounds in radians (same convention as `LaserScan`). |
| `right_window_rad` | `[-1.75, -1.10]` | Right sector bounds in radians. |

---

## `map` vs `odom` (important for x,y meaning)

- **`odom` → `base_link`**: Position drifts over time but is usually **always available** from wheel odometry / EKF. Good for “one continuous lap” logging if nobody publishes `map`.
- **`map` → `base_link`**: Only works if something (e.g. SLAM) publishes **`map` → `odom`** (or directly **`map` → `base_link`**). Then x,y are in the **map** frame, which is what many optimizers expect.

**Practical default for manual laps without SLAM:** use **`world_frame:=odom`**.

---

## Build and run

After building your workspace and sourcing the overlay:

```bash
# Example: log pose in odom frame while driving manually
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=odom \
  -p robot_frame:=base_link \
  -p output_csv:=/tmp/manual_map.csv
```

Stop the node with **Ctrl+C**; the CSV is flushed as it runs.

Rebuild whenever you change the package:

```bash
colcon build --packages-select reactive_control
source install/setup.bash
```

---

## Limitations (honest expectations)

- **Odometry drift:** If you use `odom`, the path is not globally accurate forever; it is still useful for many raceline pipelines that work in a local frame.
- **Left/right are heuristic:** They are min ranges in fixed angular slices, not a full 360° map or guaranteed “wall” semantics (open door, people, cones all count as obstacles).
- **Synchronization:** Each row uses the **latest** scan at tick time and the **current** TF lookup; they are not perfectly time-aligned unless you add interpolation later.

---

## Optional next step

You can add a launch-file flag (for example `record_mapping:=true`) in `bringup.launch.py` to start this node alongside manual drive. That was not added automatically; say if you want it wired in.

---

## End-to-end runbook (clear terminal layout)

This section is the operational checklist to run manual mapping from start to finish.

### Important rule before launch

Before running `bringup.launch.py`, **turn ON the RC deadman/manual switch** so the system stays in manual priority and does not rely on autonomy commands.

- Manual topic: `/teleop`
- Autonomy topic: `/drive`
- `ackermann_mux` priority gives manual (`/teleop`) higher priority.

### Terminal map

Use 3 terminals:

- **Terminal 1 (Car host shell):** Start container
- **Terminal 2 (Inside container):** Run unified stack (`bringup.launch.py`)
- **Terminal 3 (Inside container):** Run `manual_map_logger` and stop it with `Ctrl+C`

Optional:

- **Terminal 4 (Laptop shell):** Copy CSV from car to laptop with `scp`

### 0) Preconditions

- RC transmitter ON
- Car powered
- Receiver bound to RC
- Livox connected
- VESC connected (`/dev/sensors/vesc` ready on host)
- Docker image available on car:
  - `nabilafifahq/roboracer-t7:main-manual-map-logger-20260428`

### 1) Terminal 1 (car host): start Docker container

```bash
ssh ucsd-blue@ucsd-blue.local
docker pull nabilafifahq/roboracer-t7:main-manual-map-logger-20260428
mkdir -p ~/roboracer_logs
sudo mkdir -p /dev/sensors
# set the correct ttyACM for your car (example: ttyACM1)
sudo ln -sf /dev/ttyACM1 /dev/sensors/vesc

docker rm -f roboracer_t7 2>/dev/null || true
docker run --rm -it \
  --name roboracer_t7 \
  --net=host \
  --ipc=host \
  --privileged \
  --device=/dev/input/js0 \
  --device=/dev/ttyACM0 \
  --device=/dev/ttyACM1 \
  -v /dev/sensors:/dev/sensors \
  -v /dev/bus/usb:/dev/bus/usb \
  -v ~/roboracer_logs:/race_ws/logs \
  nabilafifahq/roboracer-t7:main-manual-map-logger-20260428
```

Keep Terminal 1 open.

### 2) Terminal 2 (inside container): launch stack

Open a second shell and enter container:

```bash
ssh ucsd-blue@ucsd-blue.local
docker exec -it roboracer_t7 bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
```

**Before the next command: confirm deadman/manual switch is ON.**

Then run:

```bash
ros2 launch /race_ws/bringup.launch.py
```

Leave Terminal 2 running.

### 3) Terminal 3 (inside container): run manual map logger

Open third shell:

```bash
ssh ucsd-blue@ucsd-blue.local
docker exec -it roboracer_t7 bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash

CSV=/race_ws/logs/manual_map_$(date +%Y%m%d_%H%M%S).csv
echo "CSV=$CSV"

ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=odom \
  -p robot_frame:=base_link \
  -p scan_topic:=/scan \
  -p output_csv:=$CSV \
  -p record_hz:=10.0
```

Drive manually with RC for 1-3 laps, then press `Ctrl+C`.

Note: a shutdown traceback (`rcl_shutdown already called`) may appear after `Ctrl+C`; logging is still valid if CSV rows were written.

### 4) Terminal 3: verify CSV was captured

```bash
ls -lh /race_ws/logs
LATEST=$(ls -t /race_ws/logs/manual_map_*.csv | head -n1)
echo "$LATEST"
wc -l "$LATEST"
sed -n '1,5p' "$LATEST"
tail -n 5 "$LATEST"
```

Success criteria:

- `wc -l` is greater than `1`
- Header is present
- `x,y,yaw_rad,left_wall_m,right_wall_m` are populated in many rows

### 5) Terminal 4 (laptop): copy latest CSV to laptop

Run this from your laptop shell (not inside car/container shell):

```bash
scp ucsd-blue@ucsd-blue.local:~/roboracer_logs/manual_map_YYYYMMDD_HHMMSS.csv ~/Downloads/
```

Example:

```bash
scp ucsd-blue@ucsd-blue.local:~/roboracer_logs/manual_map_20260429_201233.csv ~/Downloads/
```

Verify:

```bash
ls -lh ~/Downloads/manual_map_*.csv
```

### 6) Repeat runs cleanly

For each new run:

1. Keep Terminal 2 stack running
2. Re-run Terminal 3 logger command (new timestamped filename)
3. Drive lap(s)
4. Stop logger and validate
5. Copy file to laptop

### 7) Export to TUM raceline optimizer track format

The optimizer in [TUMFTM/global_racetrajectory_optimization](https://github.com/TUMFTM/global_racetrajectory_optimization) does **not** read the manual logger header directly. It loads `inputs/tracks/<name>.csv` with **four numeric columns per row** (no header row):

`x_m, y_m, w_tr_right_m, w_tr_left_m`

Convert on the **laptop** or **inside the car image** using the repo script:

```bash
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  /path/to/manual_map_20260429_201233.csv \
  -o ~/raceline_data/inputs/tracks/hallway.csv \
  --step 2 \
  --comment
```

Mapping (heuristic):

- `x`, `y` from the logger → reference line
- `right_wall_m` → `w_tr_right_m`
- `left_wall_m` → `w_tr_left_m`

Rows with empty or non‑finite wall distances are skipped.

**Run the optimizer (two options):**

1. **Inside the main car image** (same `nabilafifahq/roboracer-t7` build that includes the ROS stack):  
   TUM code is installed at `/race_ws/tum_global_racetrajectory_optimization` with a Python 3.7 **`.venv`** (kept separate from ROS). After conversion, place the track file at  
   `/race_ws/tum_global_racetrajectory_optimization/inputs/tracks/<name>.csv`, set `file_paths["track_name"] = "<name>"` in `main_globaltraj.py`, then:

   ```bash
   /race_ws/scripts/run_tum_raceline_optimizer.sh
   ```

   Default output: `/race_ws/tum_global_racetrajectory_optimization/outputs/traj_race_cl.csv` (see upstream [Running the code](https://github.com/TUMFTM/global_racetrajectory_optimization)).

2. **Separate lightweight image** (optional, for laptop-only workflow): `docker/raceline.dockerfile` and `./scripts/raceline_run.sh` still work as before.
