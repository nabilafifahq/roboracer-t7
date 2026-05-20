# Manual map logger (`manual_map_logger`)

This document describes a small ROS 2 node that **records where the car is** and **how far the walls are on the left and right** while someone **drives manually** (for example with the RC controller). The output is a **CSV file** you can feed into a raceline optimizer or other offline tools later.

---

## Big picture (what problem does this solve?)

During a competition or practice, you may want a **dataset of poses plus corridor widths** along the track. A human drives one lap; the computer samples data at a fixed rate and saves it. That is cheaper and simpler than full SLAM for “I just need a path and approximate wall distances along it.”

**For a competition-grade raceline** (CSV → TUM optimizer → pure pursuit aligned with the real track), log in the **`map`** frame with **SLAM** enabled—see **`docs/COMPETITION_RACELINE_PIPELINE.md`**.

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

The optimizer in [TUMFTM/global_racetrajectory_optimization](https://github.com/TUMFTM/global_racetrajectory_optimization) loads `inputs/tracks/<name>.csv` with **four numeric columns per row** in this order:

`x_m, y_m, w_tr_right_m, w_tr_left_m`

A **one-line header** with those names is fine (TUM’s loader can accept it). The basename (without **`.csv`**) becomes **`file_paths["track_name"]`** in **`main_globaltraj.py`**—e.g. **`hallway.csv`** → **`"hallway"`**, **`raceline_opt_input.csv`** → **`"raceline_opt_input"`**.

**When you do *not* run the converter.** If the file body is **already** TUM layout—only the filename differs (e.g. someone saved it as **`hallway.csv`** or **`raceline_opt_input.csv`** but the columns are **`x_m, y_m, w_tr_right_m, w_tr_left_m`**)—copy it straight to **`inputs/tracks/<name>.csv`** and skip **`manual_map_csv_to_tum_track.py`**. Example in repo: **`raceline_data/inputs/tracks/raceline_opt_input.csv`**.

**When you *do* run the converter.** Use **`/race_ws/scripts/manual_map_csv_to_tum_track.py`** for **`manual_map_logger` CSVs that are *not* yet in TUM layout**—typically the current logger header row includes **`x`**, **`y`**, **`left_wall_m`**, **`right_wall_m`**. **Older runs may use different headers**; if the converter errors, fix or rename columns to match what the script expects, or open an issue with a sample header row. Convert on the **laptop** or **inside the car image**:

```bash
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  /path/to/manual_map_20260429_201233.csv \
  -o ~/raceline_data/inputs/tracks/from_manual_map.csv \
  --step 2 \
  --comment
```

Mapping (heuristic):

- `x`, `y` from the logger → reference line
- `right_wall_m` → `w_tr_right_m`
- `left_wall_m` → `w_tr_left_m`

Rows with empty or non‑finite wall distances are skipped.

**What the TUM maintainers recommend (upstream README).** Their workflow targets **Ubuntu 20.04 LTS** and **Python 3.7**. Install Python dependencies from their repo root:

```bash
pip3 install -r /path/to/global_racetrajectory_optimization/requirements.txt
```

For **Ubuntu** install issues they suggest:

```bash
sudo apt install python3-tk python3-dev
```

(`python3-tk` for matplotlib; `python3-dev` supplies `Python.h` and headers needed when native extensions such as **quadprog** are built.)

If **`quadprog` fails** with their pinned stack, they suggest trying **`quadprog` 0.1.6 instead of 0.1.7** (cause described as unclear in their README).

**Why this repo’s car image differs.** The race stack ships on **Ubuntu 22.04 + Python 3.10** inside **ROS 2 Humble**, not 20.04/py3.7. Blind `requirements.txt` plus `pkg_resources` pins is a poor fit, and **`linux-aarch64`** often breaks with the stock **`quadprog==0.1.7`** wheel. **`docker/dockerfile`** therefore installs the Ubuntu packages above via `apt`, applies **`docker/patch_tum_main_globaltraj_ros.py`**, and uses a curated **`pip`** set (including **`quadprog` 0.1.13** built from source with **`LDFLAGS` linking `gfortran`** plus **`trajectory-planning-helpers --no-deps`**) per the commented install block in that file.

**Native Ubuntu on the car (outside Docker): follow TUM first.** Clone [`TUMFTM/global_racetrajectory_optimization`](https://github.com/TUMFTM/global_racetrajectory_optimization), then:

```bash
sudo apt install python3-tk python3-dev build-essential gfortran
cd /path/to/global_racetrajectory_optimization
python3 -m venv .venv && source .venv/bin/activate   # upstream used py3.7; match your distro’s python
pip install --upgrade pip wheel
pip install -r requirements.txt
```

On **Ubuntu 22.04 / aarch64**, you may hit the same **`quadprog`** ImportError as upstream issues describe; treating **`quadprog` 0.1.6** as TUM suggests is one path on **amd64**. On **aarch64**, mirroring the **`docker/dockerfile`** `pip` sequence is usually more reliable than the stock **`0.1.7`** wheel. Optionally apply **`docker/patch_tum_main_globaltraj_ros.py`** against **`main_globaltraj.py`** if you rely on **`mincurv`** without wanting CasADi at import time.

**Main car image (`docker/dockerfile`).** TUM is cloned into **`/race_ws/tum_global_racetrajectory_optimization`** with those patches and `pip`/`apt` steps baked in—rebuild/pull the Docker image rather than reinstalling manually on each node if you standardize on containers. Use **`mincurv`** or **`shortest_path`** in **`main_globaltraj.py`** for a lighter test; **`mintime`** pulls in CasADi and is heavier.

**Car-side TUM overrides.** After the `git clone`, `docker/dockerfile` overlays files from **`docker/tum_overrides/`** onto the cloned tree (then runs the ROS-Py3.10 patch). Currently kept there:

- **`docker/tum_overrides/main_globaltraj.py`** — sets **`file_paths["track_name"] = "hallway"`** as the default track. Edit this file in the repo if you want a different default baked into the image (otherwise `nano main_globaltraj.py` in the container at runtime).
- **`docker/tum_overrides/opt_mintime_traj/src/opt_mintime.py`** — wraps the **`n_min`** / **`n_max`** track-bound expressions in **`float(...)`** so CasADi DM objects don't pollute the plain-Python bound lists in `mintime` mode.

**Separate raceline-only image.** For the minimal TUM/Python 3.7 stack, see **`docker/raceline.dockerfile`** and **`scripts/raceline_run.sh`** (mount **`raceline_data/`**).

### 8) Car workflow: TUM track file → raceline CSV → onboard pure pursuit

**A. Track file on the Pi.**

- **Logger CSV (non-TUM headers):** Run **`manual_map_csv_to_tum_track.py`** first (§7), then place the **output** `.csv` under **`inputs/tracks/`**.
- **Already TUM columns** (`x_m,y_m,w_tr_right_m,w_tr_left_m`; filename can be **`hallway.csv`**, **`raceline_opt_input.csv`**, etc.): copy into **`~/raceline_data/inputs/tracks/`** with **no** converter.

Example layout:

```
~/raceline_data/
  inputs/tracks/hallway.csv          # or raceline_opt_input.csv, from_manual_map.csv, …
  outputs/traj_race_cl.csv
```

A checked-in example: **`raceline_data/inputs/tracks/raceline_opt_input.csv`** in this repo (**`git pull`** on the car, or copy from your laptop).

**B. Run TUM inside your container.** (**`roboracer_raceline`** = your **`docker ps`** name; image must include **`/race_ws/tum_global_racetrajectory_optimization`**. Replace **`hallway.csv`** / **`"hallway"`** with your **`<name>.csv`** / **`"<name>"`**.)

```bash
mkdir -p ~/raceline_data/outputs

docker cp ~/raceline_data/inputs/tracks/hallway.csv \
  roboracer_raceline:/race_ws/tum_global_racetrajectory_optimization/inputs/tracks/

docker exec -it roboracer_raceline bash
```

Inside the container:

```bash
cd /race_ws/tum_global_racetrajectory_optimization
# file_paths["track_name"] must match basename without .csv (e.g. "hallway").
# opt_type = "mincurv" is a good default on the car image.
nano main_globaltraj.py

python3 main_globaltraj.py
```

Leave the optimizer shell (`exit`), then pull the trajectory and expose it where pursuit reads it:

```bash
docker cp roboracer_raceline:/race_ws/tum_global_racetrajectory_optimization/outputs/traj_race_cl.csv \
  ~/raceline_data/outputs/traj_race_cl.csv

docker cp ~/raceline_data/outputs/traj_race_cl.csv \
  roboracer_raceline:/race_ws/racelines/traj_race_cl.csv
```

The last **`docker cp`** places the trajectory at the default **`raceline_pure_pursuit`** path (**`/race_ws/racelines/traj_race_cl.csv`**).

**C. Drive with pure pursuit.** Launch bringup with pursuit instead of wall-follow (after **`source install/setup.bash`**):

```bash
ros2 launch /race_ws/bringup.launch.py autonomy:=raceline_pure_pursuit \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv
```

**`raceline_pure_pursuit_node`** publishes **`AckermannDriveStamped`** on **`/drive`** ( **`ackermann_mux`** **navigation**). Tune **`lookahead_m`**, **`target_speed_mps`**, **`wheelbase_m`** in **`bringup.launch.py`**.

**D. Frames.** The track is in the same planar frame used to build it (often **`map`**, matching **`manual_map_logger`** if it came from the logger path). **`map`→`base_link`** must be meaningful when you engage pursuit; adjust **`world_frame`** if everything is purely in **`odom`**.

**E. Overrides.** **`/teleop`** stays higher priority than **`/drive`** in **`config/ackermann_mux_topics.yaml`** for manual safety.

Then (alternative only): **`docker/raceline.dockerfile`** workflows copy any **`<name>.csv`** into **`inputs/tracks/`**, set **`file_paths["track_name"]`** to **`<name>`**, **`python main_globaltraj.py`**, default **`outputs/traj_race_cl.csv`** — see **`scripts/raceline_run.sh`** + **`DATA_DIR`**.

### 9) Field checklist (team notes, corrected)

This section mirrors a common **on-car + laptop** flow and fixes typos / ordering issues from ad-hoc notes.

**A. Drive stack container (logging).** Example: **`docker run --name roboracer_t7`** with **`--net=host`**, **`--privileged`**, **`/dev`/`/dev/bus/usb`**, **`~/roboracer_logs:/race_ws/logs`**, and your team image tag. Source ROS + workspace, then **`ros2 launch /race_ws/bringup.launch.py`**.

**B. Log a map.** Second shell in the same container, source again, then:

```bash
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=odom \
  -p robot_frame:=base_link \
  -p scan_topic:=/scan \
  -p record_hz:=10.0 \
  -p output_csv:=/race_ws/logs/manual_map.csv
```

Use **`Ctrl+C`** when done. Copy **`/race_ws/logs/manual_map.csv`** off the robot (**`docker cp`** then **`scp`**, or bind-mount **`roboracer_logs`** as above).

**C. Logger CSV → TUM track.** If the file is **not** already **`x_m,y_m,w_tr_right_m,w_tr_left_m`**, run **`manual_map_csv_to_tum_track.py`** (§7). If you only **rename** an already-TUM file to **`hallway.csv`**, skip conversion.

**D. Track on the Pi.** Example:

```bash
mkdir -p ~/raceline_data/inputs/tracks ~/raceline_data/outputs
# place hallway.csv (or any <name>.csv) under inputs/tracks/
```

**E. Custom `main_globaltraj.py` from laptop.** Only needed if you will **not** edit **`track_name`** in the container. If the track is **`hallway.csv`**, set **`file_paths["track_name"] = "hallway"`** inside **`/race_ws/tum_global_racetrajectory_optimization/main_globaltraj.py`** ( **`nano`** / **`sed`** ) instead of **`scp`**’ing a whole file.

**F. Optimizer shell (volume mount, recommended).** Run a **second** container (name e.g. **`roboracer_raceline`**) with **`-v ~/raceline_data:/data`** so inputs/outputs persist without repeated **`docker cp`**:

```bash
docker run --rm -it --name roboracer_raceline \
  -v "$HOME/raceline_data:/data" \
  nabilafifahq/roboracer-t7:main-manual-map-logger-20260428 \
  bash
```

Inside it, TUM lives at **`/race_ws/tum_global_racetrajectory_optimization`**. You **do not** need **`/dev/sensors`** or VESC **`ln -sf`** for running **`main_globaltraj.py`** only (those belong to the **drive** container).

**G. Install track + run.**

```bash
cd /race_ws/tum_global_racetrajectory_optimization
mkdir -p inputs/tracks
cp /data/inputs/tracks/hallway.csv inputs/tracks/
# file_paths["track_name"] must match basename without .csv → "hallway"
nano main_globaltraj.py   # set track_name; prefer opt_type = "mincurv" on this image unless mintime is validated
python3 main_globaltraj.py
```

**Important path typo to avoid:** the directory is **`inputs/tracks/`** (plural **`tracks`**), **not** **`inputs/track`**.

**H. Patches in `/usr/local/lib/.../trajectory_planning_helpers/`** (e.g. **`spline_approximation.py`** **`sed`**). Only apply if you hit a **specific** runtime error; patching **`site-packages`** inside a throwaway container is easy to lose on rebuild. Prefer fixing in a **venv** or a **rebuilt image** if the bug is reproducible.

**I. Custom `opt_mintime.py`.** Advanced only; keep in repo or document why it diverges from upstream.

**J. Use this repo’s image defaults.** The baked **`main_globaltraj.py`** is **patched** for ROS Python 3.10 (lazy **`opt_mintime_traj`**, no **`pkg_resources.require`** on **`requirements.txt`**). Do **not** replace it with a **stock** upstream copy unless you restore those patches and dependencies. For a quick raceline on the car, **`opt_type = "mincurv"`** is the usual choice; **`mintime`** is heavier and needs CasADi/IPOPT working.

**K. Copy result out.** With **`/data`** mount:

```bash
cp ./outputs/traj_race_cl.csv /data/outputs/
```

Then **`scp`** from the Pi home or from **`~/raceline_data/outputs/`** on the host.

**L. Jupyter / notebook.** Loading **`traj_race_cl.csv`** and plotting **`x_m`**, **`y_m`** is **visualization only**; you do **not** need to paste all of **`main_globaltraj.py`** into a notebook to generate the trajectory (that belongs in the TUM repo directory with **`python3 main_globaltraj.py`**).

**Frame reminder:** If the logger used **`world_frame:=odom`**, treat the track and any pursuit stack as **odom**-consistent unless you transform or re-log in **`map`**.
