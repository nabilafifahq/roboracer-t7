# Autonomy modes (`bringup.launch.py`)

Unified launch supports **three** `autonomy:=` values. Manual RC (`/teleop`) always has highest mux priority.

| `autonomy` | Stack | Command output |
|------------|--------|----------------|
| `wall_follow` (default) | LiDAR reactive wall-follow | `/drive` → mux (priority 10) |
| `raceline_pure_pursuit` | TUM CSV + geometric pure pursuit (Nabila) | `/drive` → mux (priority 10) |
| `nav2_vector_pursuit` | CSV → `/global_path` → Nav2 vector pursuit (Derek) | `/nav2_cmd_ackermann` → mux (priority 50) |

## Common launch args

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_pure_pursuit \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=odom \
  use_slam:=false
```

Nav2 mode:

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=nav2_vector_pursuit \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=odom
```

With SLAM + map-frame raceline:

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_pure_pursuit \
  use_slam:=true \
  pursuit_world_frame:=map \
  raceline_csv:=/race_ws/racelines/my_race.csv
```

## VESC on UCSD-Blue

```bash
sudo ln -sf /dev/ttyACM0 /dev/sensors/vesc
```

STM = `ttyACM0`, Arduino RC = `ttyACM1`.

## Rebuild image after merge

```bash
docker build -f docker/dockerfile -t nabilafifahq/roboracer-t7:main-latest .
docker push nabilafifahq/roboracer-t7:main-latest
```

On car: `docker pull` then `car_run.sh` / your usual `docker run`.
