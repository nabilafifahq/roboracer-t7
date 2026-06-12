# RoboRacer T7 — Full Project Handoff (as of 2026-06-08)

**Course:** UCSD DSC190, Team 7 · **Repo:** https://github.com/nabilafifahq/roboracer-t7 · **Working branch:** `dl-debug`

This document is written for **a team that starts with zero knowledge of this project** — exactly where we
started. It covers the hardware, the software, every command, every error we hit (with the real error
text and the fix), and the full start-to-end workflow: **map the track → clean the data → optimize a
racing line with TUM → drive it autonomously with pure pursuit.**

> ⚠️ **Honesty notes (read first).** A few things below are marked **`CONFIRM`** — those are items we are
> *not 100% certain of* and the next team should verify before relying on them. We deliberately did **not**
> exaggerate. The two biggest honesty points:
> 1. **Autonomous driving is proven in the `odom` frame.** The `map`-frame racing line is *generated and
>    ready*, but we did not confirm a full autonomous lap in `map` frame.
> 2. **ORB-SLAM3 is installed on the car but NOT tested by us.**

---

## 0. TL;DR status (2026-06-08)

| | Item |
|---|---|
| ✅ **Works** | Mapping a closed loop (Cartographer 2D), point-cloud→scan tuning, VESC odometry (drift minimized), `/scan` drop fixed (CycloneDDS), offline de-drift of the map, measured racing line via TUM min-curvature, **autonomous driving in odom frame** (pure pursuit), visualizers, one-command pipeline, documentation |
| ⚠️ **Partial / not confirmed** | Autonomous driving in **map** frame (raceline ready, lap not confirmed); inner-box wall only partially measured by LiDAR at close range |
| ❌ **Not done** | ORB-SLAM3 test, camera-based mapping, smart live scan-param tuning |

---

## 1. What is this project & the goal

We have an **F1TENTH-style 1/10-scale autonomous race car**. The goal:

1. **Map any enclosed loop track** (our DIY track = a black corrugated **hose** as the outer wall + a white
   **box** as a central island).
2. **Find the racing line** ("best path") for that track — the fast, smooth line a race driver would take.
3. **Drive it autonomously** and **hand off clean documentation** to the next team.

The "Berlin-style" deliverable = a figure showing **inner wall + outer wall + optimal racing line**, with the
walls *measured* by the car's LiDAR.

---

## 2. Hardware

| Part | What it is | Notes |
|---|---|---|
| **Compute** | Raspberry Pi 5 (arm64 / aarch64), Ubuntu, ROS 2 Humble in Docker | hostname `ucsd-blue`, user `ucsd-blue` |
| **LiDAR** | **Livox MID-360** — a 3D solid-state LiDAR | scans **−7° to +52°** vertically (it looks UP, barely samples the floor). Non-repetitive scan pattern (coverage builds over time). IP `192.168.1.124`. Publishes `/livox/lidar` (PointCloud2) + `/livox/imu` |
| **Motor controller** | **VESC** (open-source ESC) | Talks serial over USB. **It is an STMicroelectronics ChibiOS device** — see the port gotcha in §10 |
| **RC receiver / joystick** | **Arduino Leonardo** based | enumerates as `/dev/input/js0` AND a `/dev/ttyACM*` serial port (this collides with the VESC — see §10) |
| **Camera** | `CONFIRM` — present (ORB-SLAM3 is installed) but we did not use it. Model/driver: **next team to fill in** | |
| **Chassis / battery / servo** | 1/10 RC car, steering servo | wheelbase **0.33 m** (important — see §10) |

**Measured heights (matter for the LiDAR slice):** LiDAR sits **0.11 m** above the ground (`base_link→laser`
z = 0.11). Track walls (hose / box) are **~0.20 m** tall. The box and outer wall are both low.

---

## 3. Software stack

- **ROS 2 Humble**, everything runs **inside Docker** on the Pi.
- **DDS middleware:** we force **CycloneDDS** (`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`) — this is the fix for
  `/scan` dropping (see §10). The default FastDDS stalls.
- **Docker images:**

| Image | Arch | Where | Purpose |
|---|---|---|---|
| **`nabilafifahq/roboracer-t7:cartographer-ekf`** | arm64 | the **Pi** (and Mac, Apple Silicon) | **The main image — has the whole driving stack:** Livox driver, VESC, EKF, Cartographer, pointcloud_to_laserscan, reactive_control. **This is the one to use.** |
| **`roboracer-t7-raceline:latest`** | amd64 | **laptop only** | the TUM racing-line optimizer (heavy scientific stack; will not run on the Pi) |
| `nabilafifahq/roboracer-t7:full-stack` | ? | referenced in `docs/RACELINE_PIPELINE.md` | `CONFIRM` — may be a newer combined image; we used `cartographer-ekf` this session |

- The running container is named **`roboracer_t7`**.

---

## 4. GitHub & external references (what each is for)

- **Our repo:** `github.com/nabilafifahq/roboracer-t7` (branch `dl-debug`). Holds our configs, launch files,
  the `reactive_control` package, runbooks, the racing-line pipeline, and all `testrun/` analysis.
- **`third_party_research/`** in the repo holds reference checkouts we studied (not all used):
  `F1TENTH-lab_ws`, `f1_tenth_ros2`, `f1tenth_planning`, `livox_ros_driver2_upstream`,
  `pointcloud_to_laserscan`, `pure_pursuit`, `autodrive_roboracer_ws`.
- **TUM racing-line optimizer:** https://github.com/TUMFTM/global_racetrajectory_optimization — the
  min-curvature optimizer we run inside `roboracer-t7-raceline`.
- **Livox driver:** `livox_ros_driver2`. **Cartographer:** `cartographer_ros` (ships in the image).
  **robot_localization** (the `ekf_node`). **f1tenth_system / f1tenth_stack** (VESC, joy, mux).

---

## 5. Frames: what `odom` and `map` mean (READ THIS)

ROS keeps track of where the car is with a **transform tree**. Ours, top to bottom:

```
map ──(Cartographer)──► odom ──(VESC wheel odometry)──► base_link ──(static)──► laser
                                                                   └─(static)──► livox_frame
```

- **`base_link`** = the car. **`laser`** = the LiDAR (0.27 m forward, 0.11 m up).
- **`odom → base_link`** (VESC): smooth, continuous, never jumps, but **drifts slowly** over time.
- **`map → odom`** (Cartographer): the global correction that cancels the drift, computed by matching the
  live scan against the map it's building.

**Rule: exactly ONE node may publish each edge.** (This bit us — see the EKF/VESC conflict in §10.)

**`odom` frame vs `map` frame for racing:**
- **odom frame:** the racing line is anchored to wherever the car *started*. So **the car MUST start exactly
  on the line, facing down-track.** Simple and robust (no Cartographer needed). **This is what we drove
  autonomously.**
- **map frame:** Cartographer gives global localization, so you can **place the car anywhere** on the track
  and it still knows where it is. More powerful, but depends on Cartographer being stable. **This is what we
  built the clean map + raceline in; full autonomous lap not yet confirmed.**

---

## 6. The ROS nodes (what each one does)

When you launch `bringup.launch.py` you get (from the launch log):

| Node | Job |
|---|---|
| `livox_ros_driver2_node` | drives the MID-360 → publishes `/livox/lidar` (PointCloud2) and `/livox/imu` |
| `pointcloud_to_laserscan_node` | **flattens** the 3D cloud to a 2D `/scan` using a **height slice** |
| `static_transform_publisher` ×2 | `base_link→laser` and `base_link→livox_frame` (fixed offsets) |
| `vesc_driver_node` | talks to the VESC over serial (`/dev/sensors/vesc`) |
| `ackermann_to_vesc_node` | converts steering/speed commands → VESC motor + servo |
| `vesc_to_odom_node` | integrates VESC speed + steering → `/odom` and the `odom→base_link` TF |
| `joy_node` | reads the RC joystick (`/dev/input/js0`) |
| `joy_teleop` | maps joystick axes → `/teleop` drive command (with a **deadman button**) |
| `ackermann_mux` | picks between teleop (priority) and autonomous `/drive` |
| `ekf_node` | robot_localization; fuses odom + IMU → `/odometry/filtered` (TF publishing **off**) |
| `cartographer_node` | 2D SLAM → publishes `map→odom` |
| `cartographer_occupancy_grid_node` | publishes the `/map` occupancy grid |
| `cpu/hdd/mem/net/ntp _monitor_node` | system monitors — **they eat Pi CPU; `pkill -f monitor_node` if `/scan` drops** |

**Our package `reactive_control`:**
- `manual_map_logger` — drive a lap; it logs pose + left/right wall distance (from `/scan`) → CSV.
- `raceline_pure_pursuit_node` — follows a racing-line CSV (pure pursuit).

---

## 7. Getting started — SSH, terminals, Docker

You need **2–3 SSH terminals into the Pi** + **your laptop**.

```bash
# ---- LAPTOP: SSH into the car ----
ssh ucsd-blue@ucsd-blue.local         # password required

# ---- on the Pi: start the container (drops you inside it) ----
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
cd ~/roboracer-t7 && ./scripts/car_run.sh
```

**In EVERY terminal that goes into the container**, run these three lines first (always):
```bash
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp          # the /scan-drop fix — do this EVERY shell
ln -sf /dev/ttyACM0 /dev/sensors/vesc                 # VESC serial symlink (see §10 if VESC errors)
```

To open **more terminals into the same running container** (new SSH session each):
```bash
docker exec -it roboracer_t7 bash
# then the three source/export/ln lines again
```

**Suggested terminal layout:**
- **Terminal A** — the launch (stays running the whole time).
- **Terminal B** — record bag / save map / run pursuit.
- **Terminal C** — monitoring (`ros2 topic hz /scan`, `tf2_echo`).
- **Laptop** — `scp` data off, run TUM, run the pipeline.

> ⚠️ The container is started with `--rm` (**ephemeral**): when it exits, anything written inside is **lost**.
> Always `docker cp` your maps/bags out to the Pi host **before** exiting. And re-apply configs each session
> (we use cat/sed, **never `git pull` on the Pi** — see §8).

---

## 8. Applying the config (cat/sed inside the container)

We keep all tuning as in-container `cat`/`sed` (to be baked into the image later). The one-shot script is
**`scripts/car_map_setup.sh`**. Key values it sets (and why):

| Setting | Value | File | Why |
|---|---|---|---|
| RMW | `rmw_cyclonedds_cpp` | env | `/scan` drop fix |
| Livox format | PointCloud2, `frame_id=laser` | `msg_MID360_launch.py`, `MID360_config.json` | feed pointcloud_to_laserscan |
| LiDAR slice | `min_height -0.08`, `max_height -0.02` | `pointcloud_to_laserscan_indoor.yaml` | keep the **wall band**, not floor. **Set in the CONFIG — runtime `param set` is IGNORED by this node** |
| range | `0.30` / `2.5` | same | indoor track |
| VESC TF | `publish_tf: true` | `vesc.yaml` | VESC owns `odom→base_link` |
| EKF TF | `publish_tf: false` | `ekf_car.yaml` | **so it doesn't fight the VESC** (§10) |
| wheelbase | `0.33` | `vesc.yaml` | correct geometry (was 0.25 → over-rotated heading) |
| Cartographer | no correlative matcher, `optimize_every_n_nodes=0` (live), high ceres weights, `use_imu_data=false` | `cartographer/roboracer_2d.lua` | anti-teleport + no IMU NaN crash |

> **Box-measuring tip:** the `-0.08/-0.02` slice catches the **far outer wall** well but the **close inner
> box** poorly (geometry: a horizontal beam at laser height is *excluded* by `max_height -0.02`, so only the
> lowest downward beams hit the close box). To measure the box better next time: **drive slow and within
> ~0.6 m of it** (the lowest beams then land on its face), or carefully raise `max_height` toward `+0.05`
> (catches the box but risks seeing past gaps in the outer wall — test it).

---

## 9. END-TO-END WORKFLOW (map → racing line → autonomous)

### Step A — Map the track + record everything
```bash
# Terminal A (inside container, sourced):
ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=true

# Terminal C — sanity checks (sourced + RMW export):
ros2 topic hz /scan                      # want steady ~10 Hz
ros2 run tf2_ros tf2_echo odom base_link # parked -> yaw STEADY
ros2 run tf2_ros tf2_echo map base_link  # drive 1 m -> moves smoothly, no big jumps

# Terminal B — record a bag (BEFORE you drive) and drive 3-5 slow laps:
ros2 bag record -o /race_ws/logs/lap /scan /tf /tf_static /odom /livox/lidar
#   ... drive the laps now (RC, deadman held) ...

# After laps, save the map (mkdir FIRST or it errors):
mkdir -p /race_ws/maps
ros2 run nav2_map_server map_saver_cli -f /race_ws/maps/track --occ 0.45 --ros-args -p save_map_timeout:=20.0
ros2 service call /write_state cartographer_ros_msgs/srv/WriteState "{filename: '/race_ws/maps/track.pbstream', include_unfinished_submaps: true}"
```
**Keep mapping sessions SHORT (~90 s).** Long sessions drift (see §10). Record the **bag** regardless — it
lets us de-drift offline.

**Copy out + to laptop:**
```bash
# Pi host (outside container):
docker cp roboracer_t7:/race_ws/maps        ~/maps_run
docker cp roboracer_t7:/race_ws/logs/lap    ~/lap_run
# Laptop:
DEST=~/Documents/roboracer-t7/testrun/<newrun>; mkdir -p $DEST/maps_4x
scp ucsd-blue@ucsd-blue.local:'~/maps_run/*' $DEST/maps_4x/
scp -r ucsd-blue@ucsd-blue.local:~/lap_run   $DEST/lap3x
```

### Step B — (laptop) De-drift the map offline (if the live map is smeared)
Long/live maps drift. Re-run Cartographer on the bag with loop closure (no real-time pressure):
```bash
docker run --rm --platform linux/arm64 -v "$PWD/testrun/<newrun>:/data" \
  nabilafifahq/roboracer-t7:cartographer-ekf bash -lc '
  source /opt/ros/humble/setup.bash
  python3 <<PY      # QUOTED heredoc to avoid bash mangling backslashes
import re; p="/race_ws/config/cartographer/roboracer_2d.lua"; s=open(p).read()
s=re.sub(r"use_imu_data\s*=\s*\w+","use_imu_data = false",s)        # bag has no /livox/imu
s=re.sub(r"optimize_every_n_nodes\s*=\s*\d+","optimize_every_n_nodes = 30",s)  # loop closure ON
open(p,"w").write(s)
PY
  ros2 run cartographer_ros cartographer_offline_node \
    -configuration_directory /race_ws/config/cartographer -configuration_basenames roboracer_2d.lua \
    -bag_filenames /data/lap3x -save_state_filename /data/dedrift.pbstream -use_bag_transforms true \
    --ros-args -r scan:=/scan -r odom:=/odom -p use_sim_time:=true
  ros2 run cartographer_ros cartographer_pbstream_to_ros_map \
    -pbstream_filename /data/dedrift.pbstream -map_filestem /data/track_dedrift -resolution 0.05'
# then fix track_dedrift.yaml image path to relative. Output map is GRAYSCALE prob (occupied = value <60).
```

### Step C — (laptop) Build the racing line + run TUM — ONE command
```bash
python3 scripts/build_raceline_from_bag.py \
  --bag testrun/<newrun>/lap3x \
  --pgm testrun/<newrun>/maps_4x/track.pgm \
  --yaml testrun/<newrun>/maps_4x/track.yaml \
  --outdir testrun/<newrun> --run-tum
```
This does: read the driven path (TF compose) → clean centerline (percentile envelope + Fourier low-pass) →
**measure left/right widths from the map** → write the TUM track → **run TUM min-curvature** → output
`traj_race_cl.csv` + the Berlin figure. (Internals & the TUM gotchas are in §10.)

*Manual alternative (the original pipeline):* drive a lap with `manual_map_logger world_frame:=odom`, convert
with `scripts/manual_map_csv_to_tum_track.py`, run TUM via `scripts/raceline_run.sh`.

### Step D — Drive it autonomously (pure pursuit, odom frame)
```bash
# copy the raceline to the car, triple it so it loops:
docker cp testrun/<newrun>/traj_race_cl.csv roboracer_t7:/race_ws/racelines/raceline.csv
docker exec roboracer_t7 bash -c 'cd /race_ws/racelines; head -1 raceline.csv > raceline_loop.csv; for i in 1 2 3; do tail -n +2 raceline.csv >> raceline_loop.csv; done'

# launch the stack, then the pursuit node (place the car ON the line, facing down-track):
ros2 run reactive_control raceline_pure_pursuit_node --ros-args \
  -p trajectory_csv:=/race_ws/racelines/raceline_loop.csv \
  -p world_frame:=odom -p robot_frame:=base_link \
  -p use_traj_velocity:=false -p target_speed_mps:=0.5 \
  -p lookahead_m:=0.5 -p max_steering_rad:=0.45 -p stop_within_m:=0.20
```
**Deadman:** HOLD the deadman button → start the node → **RELEASE = autonomous**, **SQUEEZE = stop/override**.

---

## 10. Errors we hit — real messages, cause, fix, how to check

> Each entry: the **actual terminal text**, what it means, and the fix.

**(1) `/scan` drops / stalls.** *Symptom:* `ros2 topic hz /scan` starts ~10 Hz then collapses / latency
spikes to 0.3–0.8 s.
- **Cause:** default **FastDDS** shared-memory transport stalls with the big LiDAR messages on the Pi.
- **Fix:** `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` in **every** shell.
- **Do NOT** add `qos_overrides: reliable` to the scan node — that creates a QoS mismatch and makes `/scan`
  stick completely. **Secondary cause:** CPU backlog on long runs → `pkill -f monitor_node`.

**(2) Cartographer aborts on IMU:**
```
F imu_tracker.cc:67] Check failed: (orientation_ * gravity_vector_).z() > 0. (nan vs. 0)
```
- **Cause:** IMU is enabled in the lua but the Livox IMU produces a NaN gravity vector at startup.
- **Fix:** force `TRAJECTORY_BUILDER_2D.use_imu_data = false` and `tracking_frame = "base_link"` in
  `roboracer_2d.lua`. (Our anti-teleport lua patch must include this line.)

**(3) VESC driver dies / spews serial errors:**
```
[ERROR] vesc_driver_node: process has died ... exit code -11
Out-of-sync with VESC, discarding N bytes.
Invalid end-of-frame character
```
- **Cause:** `/dev/sensors/vesc` is pointing at the **wrong serial device** — the Arduino RC receiver and the
  VESC **both** show up as `/dev/ttyACM*`, so `ttyACM0` is often the *joystick*, not the VESC.
- **Fix:** the VESC is the **STMicroelectronics ChibiOS** device:
  ```bash
  ls -l /dev/serial/by-id/        # find the *ChibiOS* entry
  ln -sf /dev/serial/by-id/usb-STMicroelectronics_ChibiOS_RT_*  /dev/sensors/vesc
  ```

**(4) Heading spins / odom drifts fast / tf warns about a transform having multiple publishers.**
- **Cause:** **two nodes publish `odom→base_link`** — the `ekf_node` AND `vesc_to_odom_node`. Only one edge
  owner is allowed.
- **Fix:** `vesc_to_odom publish_tf: true`, `ekf publish_tf: false`. Also set wheelbase `0.33` (not 0.25).

**(5) map_saver fails:**
```
[ERROR] map_io: Failed to write map ... Magick: Unable to open file (/race_ws/maps/track.pgm) (OpenBlob)
```
- **Cause:** the `/race_ws/maps` directory doesn't exist (fresh container).
- **Fix:** `mkdir -p /race_ws/maps` **first**, then run map_saver. (Map data is still live in Cartographer; no
  re-driving — just make the dir and re-save.)

**(6) Cartographer "extrapolation into the past" / growing latency.**
- **Cause:** Pi falls behind over a long session (backlog) → map smears, `map→odom` drifts (we measured
  **0.36 m, 43 snaps** on a 212 s run).
- **Fix:** keep sessions short, `pkill -f monitor_node`, and/or **de-drift offline** (Step B).

**(7) TUM optimizer — series of failures (all real):**
```
pkg_resources.ContextualVersionConflict: (quadprog 0.1.6 ..., Requirement.parse('quadprog==0.1.7'))
```
→ skip the strict version check (`pkg_resources.require(...)` → `pass`).
```
ValueError: could not convert string to float: 'x_m'
```
→ the track CSV header must be **`#`-commented**: `# x_m,y_m,w_tr_right_m,w_tr_left_m`.
```
RuntimeError: Horizon of 10 points is too large for a track with 1 points
```
→ the `racecar.ini` stepsizes are km-scale; use the **F1TENTH ini** (`docker/tum_overrides/racecar.ini`:
stepsize 0.1/0.2, width 0.20–0.30, curvlim 2.8).
```
OSError: At least two spline normals are crossed, check input or increase smoothing factor!
```
→ centerline corners tighter than the track half-width. **Fourier-smooth the centerline (N=3)** and cap
half-width below the local turn radius.
```
EXIT: Maximum Number of Iterations Exceeded.   (IPOPT)
```
→ the image bakes `opt_type = mintime` (needs friction maps, won't converge at our scale). **Force
`opt_type = 'mincurv'`.** Also the image bakes `track_name = "berlin_2018"` → **force `track_name = "hallway"`**
or it optimizes the wrong track.

**(8) Cartographer lua parse crash (when patching via a heredoc):**
```
lua_parameter_dictionary.cc:83] ... unexpected symbol near '\'
```
- **Cause:** an **unquoted** bash heredoc ate the backslashes in a Python regex → literal `\` in the lua.
- **Fix:** use a **quoted** heredoc (`<<'PY'`).

**(9) `git push` rejected:**
```
remote: error: File testrun/.../lap_last_0.db3 is 1079.04 MB; this exceeds GitHub's file size limit of 100.00 MB
! [remote rejected] dl-debug -> dl-debug (pre-receive hook declined)
```
- **Cause:** rosbag `.db3` files (up to 1 GB) committed; GitHub caps files at 100 MB.
- **Fix:** they're gitignored now (`*.db3`, `*.mcap`). Keep bags **local only**; push maps/pbstreams/CSVs/figures.

---

## 11. How to debug (general method)

1. **Is the scan alive?** `ros2 topic hz /scan` (want ~10 Hz, steady). If dead/dropping → §10(1).
2. **Is the TF tree whole?** `ros2 run tf2_tools view_frames` (makes a PDF) or
   `ros2 run tf2_ros tf2_echo map base_link`. Missing `map`? Cartographer crashed (check its log → §10(2)).
   Jittery `odom→base_link`? Two publishers → §10(4).
3. **What is the scan actually seeing?** Dump it and plot it:
   `ros2 topic echo /scan > scan.yaml` → run `scripts/visualizers/scan_yaml_visualizer.py` (§12). Lets you
   see walls vs floor, gaps, range cut-off.
4. **Is odom drifting?** Drive a closed loop with `manual_map_logger`, then run
   `scripts/visualizers/maplogger_stats_visualizer.py` — "Position error" (start vs end) should be ~0 on a
   closed loop. Big value = drift.
5. **Is the map any good?** `map_saver_cli` → open the `.pgm`; or re-render the bag offline.
6. **Check a node's params actually applied:** `ros2 param get <node> <param>` — BUT remember
   `pointcloud_to_laserscan` **ignores runtime params**; it reads the config at launch only.
7. **Free CPU** if things lag: `pkill -f monitor_node`.

---

## 12. The debugging-visualizer combo (READ — this is how you tune the car)

You cannot tune what you cannot see. These **three scripts are a workflow**, not three random tools — use
them in order, and each one tells you **which knob to turn next**. Code is in `scripts/visualizers/` (full
listings in the Appendix).

```
   scan_yaml_visualizer.py     ->  is the LiDAR slice seeing the WALLS?        (fix: height slice / range)
   maplogger_chronologic_*.py  ->  do the walls build CORRECTLY over the lap?  (fix: drift spot / scan gap / sign)
   maplogger_stats_*.py        ->  how bad is the ODOM DRIFT, as a number?     (fix: wheelbase / TF owner / IMU)
```

**Our analysis figures (what "good" looks like):**
- `testrun/june7_set7/set7_dedrift_compare.png` — smeared live map vs clean de-drifted map.
- `testrun/june7_set7/FINAL_berlin_dedrift.png` — inner box + outer wall + racing line (the deliverable).
- `testrun/june7_set6/set6_envelope.png` — driven laps → clean centerline (blue inner / yellow outer / red center).

---

### 12.1 `scan_yaml_visualizer.py` — "Is the slice seeing the walls?"
- **What it is:** plots a single `/scan` as a **polar** view (rays around the car) and a **Cartesian** X-Y view.
- **How to use:**
  ```bash
  # on the car (sourced): capture one scan as YAML, name encodes locN / height / range
  ros2 topic echo /scan > scan_loc1_-8to-2cm_30to250cm.yaml
  # laptop: put scan_loc*.yaml next to the script, then:
  python3 scripts/visualizers/scan_yaml_visualizer.py
  ```
- **Why it matters:** map quality starts here. If the slice sees the floor or nothing, everything downstream
  is garbage. **Check this first.**
- **What you find → what to tune:**

  | Plot shows | Means | Tune |
  |---|---|---|
  | clean **outline** tracing the walls | slice on the walls ✓ | nothing |
  | **filled disk** / points everywhere close | seeing the **floor** (slice too low) | raise `min_height` |
  | **sparse / missing** walls | slice too thin/high, or wall too far | widen band / lower `max_height`; check `range_max` |
  | returns stop at a hard circle | `range_max` cutting the track | raise `range_max` |
  | close **inner box invisible**, far wall fine | box below the beams at close range | drive within ~0.6 m of box, or raise `max_height` toward +0.05 (§8) |

  Knobs live in `pointcloud_to_laserscan_indoor.yaml` and **apply at launch only** (runtime `param set` ignored).

---

### 12.2 `maplogger_chronologic_visualizer.py` — "Do the walls build correctly?"
- **What it is:** a Jupyter widget that **steps through a logged lap CSV chunk-by-chunk** (slider + play),
  drawing the centerline (black) and reconstructed **left wall (blue)** / **right wall (red)** over time.
- **How to use:** record a lap with `manual_map_logger` (CSV: `x, y, yaw_rad, left_wall_m, right_wall_m,
  time_sec`), point the script at it, run in Jupyter, drag the slider / press play.
- **Why it matters:** a static map hides *when* it broke. This **replays** the lap so you catch the exact
  moment the walls jump, smear, or vanish — which reveals the cause.
- **What you find → what to tune:**

  | While stepping you see | Means | Tune / do |
  |---|---|---|
  | walls jump/shift at one spot | odom drift snap or scan dropout there | check `/scan hz` there; de-drift; §10(1),(6) |
  | left & right walls **swapped** | yaw / normal **sign** wrong | check logger normal (`left=+90°`), IMU/odom yaw sign |
  | walls **disappear** for a stretch | scan returned nothing (slice/range or `/scan` drop) | fix slice/range (§12.1); fix `/scan` (§10(1)) |
  | centerline doesn't **close** to the green start | odom drift over the lap | quantify with §12.3; de-drift |
  | walls **fuzzy / double** | car wobbled, or slice catches two heights | smoother driving; tighten slice |

---

### 12.3 `maplogger_stats_visualizer.py` — "How bad is the drift, as a number?"
- **What it is:** prints an **odometry drift report** + 4 plots: distance-from-start vs time, X/Y drift vs
  time, cumulative yaw, and trajectory colored by time (plot 4 = the "What we have Done" slide chart).
- **How to use:** same lap CSV; `python3 scripts/visualizers/maplogger_stats_visualizer.py`.
- **Why it matters:** turns "the map looks off" into **hard numbers** you can compare run-to-run. The key one:
  on a **closed loop the Position error (start → end) should be ≈ 0.**
- **What you find → what to tune:**

  | Number / plot | Good | If bad → tune |
  |---|---|---|
  | **Position error** (start↔end) | ≈ 0 on a closed loop | large → odom drift: check **EKF/VESC TF conflict** (§10(4)), then de-drift (§9 Step B) |
  | **Total rotation** (turns) | matches laps driven | wrong → **wheelbase** (must be 0.33) or heading source (§10(4)) |
  | **Drift per meter** (%) | small & steady | grows over time → Cartographer backlog on long runs (§10(6)) |
  | **X / Y drift vs time** | flat-ish | a ramp → systematic steering/odom bias |
  | **Trajectory (color=time)** | clean single loop, ends meet | spiral / open loop → drift ("before" on our slide) |

---

### 12.4 The pipeline (laptop)
**`build_raceline_from_bag.py`** — one-command bag → map → racing line. **Pros:** deterministic, measured
widths, de-drift-friendly. **Cons:** widths only as good as the map (under-observed box → partly interpolated).

> **In short:** scan viz = *is my sensor input good?* → chronologic viz = *did the lap build cleanly?* →
> stats viz = *how much do I trust the geometry?* Fix in that order before you ever run TUM.

---

## 13. ORB-SLAM3 (installed, NOT tested by us)

ORB-SLAM3 is a **camera (visual) SLAM** system and is **already installed on the car**, but **we did not test
it** — it's a candidate for camera-based localization that doesn't depend on LiDAR wall geometry.
`CONFIRM` for the next team: the exact install location, the camera model/driver, calibration, and the launch
command. Why it's interesting here: our track walls are sparse/soft and Cartographer can lose tracking
(§10(6)); a visual SLAM could be more robust, OR fused with the LiDAR/odom.

---

## 14. testrun/ folders (where the data is)

`testrun/june4`, `june6`, `june7`, `june7_set1` … `june7_set7`. Each holds a recording + our analysis PNGs.
**Latest & best:** **`june7_set7`** (de-drifted clean map + final raceline). `june7_set6` = first full
measured-width raceline. **Note:** the `.db3` bags are **local only** (gitignored, too big for GitHub) — the
maps/pbstreams/CSVs/figures are in git.
`CONFIRM`: which folder holds the *autonomous odom run* — check the raceline CSVs (likely `june6`).

---

## 15. If we had another week / next steps

1. **Confirm a full autonomous lap in `map` frame** (raceline is ready; just run pursuit with
   `world_frame:=map use_slam:=true`).
2. **Re-map with the box well-observed** (drive slow & close to it) so the inner-wall widths are fully
   *measured*, not interpolated.
3. **Test ORB-SLAM3** (§13) and/or 3D LiDAR SLAM (FAST-LIO / Point-LIO) for robust localization on sparse
   tracks.
4. **Smart live `pointcloud_to_laserscan` parameter tuning** (auto-pick the slice from the scene).
5. **Bake all configs into the Docker image** (so a fresh `car_run.sh` doesn't reset them — today we re-apply
   via cat/sed each session).
6. **Tune pursuit speed up** (we ran slow/constant; the TUM velocity profile is available).

---

## Appendix — the three visualizer scripts

> Saved as runnable files in `scripts/visualizers/`. Reproduced here so this handoff is self-contained.
> (They expect a `manual_map_logger` CSV named `lap10_june7.csv`, or `scan_loc*.yaml` dumps for the scan one.)

See:
- `scripts/visualizers/scan_yaml_visualizer.py`
- `scripts/visualizers/maplogger_chronologic_visualizer.py`
- `scripts/visualizers/maplogger_stats_visualizer.py`

---
*Maintainers: DSC190 Team 7. Questions for the next team → start at §7 (get it running), then §9 (the
workflow), and keep §10 (errors) open in another tab.*
