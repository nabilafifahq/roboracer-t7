# End-to-end raceline pipeline (manual map → Derek pursuit)

Single coherent flow combining **your** logging/SLAM/EKF stack and **Derek’s** CSV→`/global_path` (+ optional Nav2) pursuit.

## Stack always on (every `bringup.launch.py`)

| Component | Source |
|-----------|--------|
| Cyclone DDS (`RMW_IMPLEMENTATION`) | Docker + `entrypoint.sh` |
| RC teleop + deadman `buttons[1]` | `config/joy_rc_steer_fix.yaml` (`drive-speed scale: -0.50` sign fix) |
| VESC odom sign + `publish_tf: false` | `docker/patch_vesc_yaml.py` |
| EKF `odom`→`base_link` | `config/ekf_car.yaml` |
| Optional SLAM `map`→`odom` | `use_slam:=true` |
| Livox → `/scan` | bringup |
| Mux priorities | `config/ackermann_mux_topics.yaml` (baked in image) |

**UCSD-Blue VESC:** `sudo ln -sf /dev/ttyACM0 /dev/sensors/vesc` (STM, not Arduino `ttyACM1`).

---

## Pipeline steps

### 1) Map the hallway (your work)

```bash
ros2 launch /race_ws/bringup.launch.py use_slam:=true
# separate shell:
ros2 run reactive_control manual_map_logger --ros-args -p world_frame:=map -p output_dir:=/race_ws/logs
```

### 2) Convert logger CSV → TUM track input

```bash
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  /race_ws/logs/manual_map_*.csv \
  -o /race_ws/raceline_data/inputs/tracks/from_manual_map.csv \
  --drop-first 1
```

### 3) Optimize (TUM, in container or manual-logger image)

Produces **`outputs/traj_race_cl.csv`** (semicolon `s_m;x_m;y_m;psi_rad;...`).

### 4) Copy optimized traj to car

```bash
docker cp traj_race_cl.csv roboracer_t7:/race_ws/racelines/traj_race_cl.csv
```

### 5) Publish path (Derek — team-tested)

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=map \
  use_slam:=true
```

Verify:

```bash
ros2 topic echo /global_path --once
```

`traj_csv_path_publisher` accepts TUM semicolon export, comma numeric rows, or `x_m,y_m` with computed heading.

### 6) Follow path (Derek Nav2 — when ready)

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=map \
  use_slam:=true
```

Aliases: `nav2_vector_pursuit`, `pure_pursuit`.

---

## Autonomy modes (summary)

See **`docs/AUTONOMY_MODES.md`**.

| Mode | Use |
|------|-----|
| `wall_follow` | Default indoor LiDAR |
| `raceline_path` | **Derek CSV → `/global_path` only** |
| `raceline` | Derek CSV + Nav2 vector pursuit |
| `raceline_pure_pursuit` | Experimental geometric node (not team default) |

---

## Rebuild image after git pull

```bash
docker build -f docker/dockerfile -t nabilafifahq/roboracer-t7:main-latest .
docker push nabilafifahq/roboracer-t7:main-latest
```
