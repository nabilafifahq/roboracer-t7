# Cursor agent handoff: local workspace vs `origin/main` (nabilafifahq/roboracer-t7)

**Baseline remote:** [https://github.com/nabilafifahq/roboracer-t7](https://github.com/nabilafifahq/roboracer-t7) — branch **`main`**, commit **`000678f`** (“Bake odom-sign fix into Docker image and complete TUM build chain”) at time of comparison.

**Local state:** `main` is **not ahead** of `origin/main` in commits; **all deltas below are uncommitted** (`git diff origin/main`) plus **untracked** files/folders. Total tracked diff: **15 files, +466 / −29 lines**.

Use this doc to replay or review work without guessing from chat history.

---

## 1. Summary: what problem the delta solves

1. **Competition-style raceline in global frame** — optional **SLAM Toolbox** (`map`→`odom`) + **`manual_map_logger` with `world_frame:=map`** + TUM CSV export + on-car **`raceline_pure_pursuit`** (vs drifting `odom`-only teach logs).
2. **Single TF authority for `odom`→`base_link`** — **`robot_localization` EKF** + **`vesc_to_odom` `publish_tf: false`** so wheel integration does not fight the EKF.
3. **Stable ROS 2 middleware in Docker** — default **`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`** (image `ENV`, `entrypoint.sh`, `~/.bashrc` append, manual-logger image) to avoid Fast DDS SHM pain in containers.
4. **Robust `manual_map_logger` with SLAM** — TF lookup uses explicit **`Time(seconds=0, nanoseconds=0)`**, longer TF cache, shallow **LaserScan copy** (no loaned message past callback), safer shutdown.
5. **`/scan` QoS alignment** — `wall_follow_node` subscribes to **`/scan`** with **best-effort** sensor QoS; `/drive` publisher uses explicit QoS (still see mux vs other publisher **reliability mismatch** warnings if another node uses RELIABLE on `/drive`).
6. **TUM export hygiene** — `manual_map_csv_to_tum_track.py` gains **`--drop-first N`** for SLAM startup pose snap.
7. **Docs + tooling** — extended `MANUAL_MAP_LOGGER.md`, new competition pipeline doc, README helper bullets, optional **`car_launch.sh` `EXTRA_LAUNCH_ARGS`**, **`preflight_manual_map_logger.sh`** (note: `ros2 topic hz /scan` may hang on some CLI builds when `/scan` is best-effort; use `ros2 topic info /scan -v` or Python subscriber with `qos_profile_sensor_data`).

---

## 2. Tracked file changes (line-by-line intent)

### `bringup.launch.py` (+80 / large)

- New launch args: **`autonomy`** (default `wall_follow` | `raceline_pure_pursuit`), **`raceline_csv`**, **`pursuit_world_frame`** (default `odom`, use `map` when following map-frame raceline), **`use_slam`** (default `false`).
- **Bag topic list** extended: `/odometry/filtered`, `/livox/imu`.
- **`robot_localization` `ekf_node`** with `/race_ws/config/ekf_car.yaml`.
- **Conditional `slam_toolbox`** via `online_async_launch.py` when **`use_slam:=true`**, params `/race_ws/config/slam_toolbox_mapper_online_async.yaml`.
- **`wall_follow_node`**: `condition=UnlessCondition(autonomy == raceline_pure_pursuit)`.
- **New node `raceline_pure_pursuit_node`** (`reactive_control` package): runs when **`autonomy:=raceline_pure_pursuit`**; params include `trajectory_csv`, `lookahead_m`, `wheelbase_m`, `target_speed_mps`, `max_steering_rad`, **`world_frame` ← `pursuit_world_frame`**, `robot_frame:=base_link`.

### `wall_follow_script/reactive_control/manual_map_logger.py`

- Imports **`Duration`**, **`Time`**.
- TF buffer cache **10 s → 30 s**.
- **`_lookup_world_to_robot_tf()`**: `lookup_transform(world, robot, Time(0,0), timeout=0.25)` — docstring explains avoiding **`now()`**-based extrapolation with SLAM.
- **`_scan_cb`**: copies primitives into a fresh **`LaserScan`** (avoids rclpy loaned-message / large scan crashes).
- **`main`**: catch **`RuntimeError`** on shutdown in addition to `KeyboardInterrupt`.

### `wall_follow_script/reactive_control/wall_follow_node.py`

- **`/scan`** subscription uses **explicit `QoSProfile`**: `BEST_EFFORT`, `VOLATILE`, depth 10.
- **`/drive`** publisher QoS renamed to `drive_qos`; still best-effort.
- **`is_valid_lidar_scan`** now passed **`scan.range_min` / `scan.range_max`** (stricter validity vs message metadata).

### `wall_follow_script/setup.py`

- New console script: **`raceline_pure_pursuit_node = reactive_control.raceline_pure_pursuit_node:main`** (implementation file is **untracked** in this workspace snapshot — see §4).

### `scripts/manual_map_csv_to_tum_track.py`

- Docstring: when to skip conversion if CSV is already TUM-shaped.
- **`--drop-first N`**: after building `rows_out`, drop first **N** valid rows; error if none left.
- Output path example updated to `raceline_data/inputs/tracks/...`.

### `scripts/car_launch.sh`

- **`EXTRA_LAUNCH_ARGS`** env var appended to `ros2 launch ...` (e.g. `autonomy:=raceline_pure_pursuit use_slam:=true`).

### `docker/dockerfile` (main race image)

- Apt: **`ros-humble-rmw-cyclonedds-cpp`**, **`ros-humble-robot-localization`**, **`ros-humble-tf2-ros`**, **`ros-humble-slam-toolbox`**.
- **`ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`**.
- **`COPY config/ekf_car.yaml`**, **`COPY config/slam_toolbox_mapper_online_async.yaml`** into `/race_ws/config/`.
- **`chmod +x`** `preflight_manual_map_logger.sh`.
- **`mkdir -p /race_ws/logs`**; **`COPY racelines/traj_race_cl.csv`** into `/race_ws/racelines/`.
- **Build-time assert**: installed `vesc.yaml` must contain **`vesc_to_odom_node:`** block with **`publish_tf: false`**.
- Append **`export RMW_IMPLEMENTATION=...`** to **`/root/.bashrc`** for `docker exec` shells.

### `docker/entrypoint.sh`

- Export **`RMW_IMPLEMENTATION`** default Cyclone + short comment (SHM / Docker).

### `docker/manual_map_logger.dockerfile` + `docker/manual_map_logger_entrypoint.sh`

- **`ros-humble-rmw-cyclonedds-cpp`** in manual-logger image.
- **`ENV RMW_IMPLEMENTATION`**: **FastRTPS → Cyclone**.

### `docker/patch_vesc_yaml.py`

- Injects / migrates **`publish_tf: false`** under **`vesc_to_odom_node:`** (with legacy replace path if gain patch exists but `publish_tf` missing).
- Docstring notes EKF owns **`odom`→`base_link`**.

### `README.md`

- Bullets for **`raceline_data/inputs/tracks/raceline_opt_input.csv`**, TUM conversion when headers are logger-shaped, and **`autonomy:=raceline_pure_pursuit`** + `docs/MANUAL_MAP_LOGGER.md` §8.

### `docs/MANUAL_MAP_LOGGER.md`, `docs/02_DOCKER_BUILD_PUSH.md`, `docs/03_CAR_CONNECT_AND_CONTAINER.md`

- Large expansion (+189 on `MANUAL_MAP_LOGGER.md` per `git diff --stat`): pipeline, SLAM, map-frame logging, TUM, pursuit — agent should read the actual diff or open the file on disk.

---

## 3. New / notable **untracked** paths (not on GitHub `main`)

| Path | Role |
|------|------|
| `docs/COMPETITION_RACELINE_PIPELINE.md` | End-to-end competition raceline doc (`use_slam`, `map`, `--drop-first`, preflight commands). |
| `config/ekf_car.yaml` | EKF fusion config (referenced by bringup; copied in Dockerfile). |
| `config/slam_toolbox_mapper_online_async.yaml` | SLAM Toolbox online async params. |
| `scripts/preflight_manual_map_logger.sh` | Shell checks: RMW, `publish_tf` grep, `timeout … ros2 topic hz` on odom/filtered/livox/scan, `/tf` info. |
| `test_manual_map_logger/` | CSV samples, **`Visualization Optimizer.ipynb`**, **`plot_presentation_map.py`**, **`plot_presentation_extras.py`**, `_plots/*.png`, `berlin_2018.csv`, etc. |
| `wall_follow_script/reactive_control/raceline_pure_pursuit_node.py` | **Pure pursuit node** — **must be committed** if bringup references it; currently **untracked** in this snapshot. |
| `raceline_data/`, `racelines/`, `history/`, `third_party_research/` | Data / notes — usually **gitignore** or selective add. |
| `__pycache__/`, `.DS_Store` | Junk — do not commit. |

**Agent action:** run `git status -u` and decide what to **`git add`**; ensure **`raceline_pure_pursuit_node.py`** and **`test_manual_map_logger/*.py`** are not lost.

---

## 4. Operational notes for the friend (car + Docker)

1. **`ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_slam:=true`** — default autonomy remains wall-follow; SLAM optional.
2. **Logger:** `ros2 run reactive_control manual_map_logger` with **`-p world_frame:=map`** when SLAM is on; **`--drop-first 1`** on TUM conversion for first-row snap.
3. **`ros2 topic hz /scan`:** On Humble, **`hz` has no `--qos-reliability`**; default subscriber may be **incompatible** with **best-effort `/scan`** → appears stuck. Use **`ros2 topic info /scan -v`**, **`ros2 topic echo /scan --once --qos-reliability best_effort`**, or a **Python** subscriber with **`qos_profile_sensor_data`**.
4. **`/drive` QoS warnings** (mux vs wall_follow): may still appear until all `/drive` endpoints agree on reliability.

---

## 5. How to reproduce this diff locally

```bash
git fetch origin
git diff origin/main --stat
git diff origin/main -- bringup.launch.py
# etc.
```

To **reset** tracked files to remote (destructive):

```bash
git checkout origin/main -- <paths>
```

Untracked files are **not** removed by that; delete or add selectively.

---

## 6. Canonical upstream URL

Repository: [https://github.com/nabilafifahq/roboracer-t7.git](https://github.com/nabilafifahq/roboracer-t7.git)

---

*Generated from workspace analysis: `main` aligned with `origin/main` at `000678f`, diff = working tree only.*
