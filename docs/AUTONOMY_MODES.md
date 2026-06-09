# Autonomy modes (`bringup.launch.py`)

Manual RC (`/teleop`) always has highest mux priority (100). Autonomy commands on `/drive` use priority 10.

**Handoff default:** use **`map` frame** + **`use_cartographer:=true`** — your raceline was built in `map` after offline de-drift. See [HANDOFF_STATUS.md](HANDOFF_STATUS.md).

---

## Recommended for Team 7 pipeline (map frame + Cartographer)

### Step 1 — Launch stack (mapping / localization)

Does **not** drive the car by itself. Provides `/scan`, EKF, Cartographer (`map` → `odom`), and TF.

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=none \
  use_cartographer:=true
```

Drive manually with RC while Cartographer builds/refines `map` → `odom`, or use during pursuit so `map` → `base_link` stays defined.

### Step 2 — Pure pursuit ( **start here for your milestone** )

Publishes steering/throttle on `/drive`. **This is what makes the car follow the line.**

```bash
ros2 run reactive_control raceline_pure_pursuit_node --ros-args \
  -p trajectory_csv:=/race_ws/racelines/traj_race_cl.csv \
  -p world_frame:=map \
  -p target_speed_mps:=0.08 \
  -p lookahead_m:=0.45 \
  -p wheelbase_m:=0.33
```

**Deadman:** Turn on = stop (RC override). Turn off deadman to let autonomy drive.

Full terminal layout: [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md) Part C.

---

## Path publisher only (does NOT drive the car)

Publishes the raceline on `/global_path` for RViz or Nav2 — **no motor commands**.

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=map \
  use_cartographer:=true
```

Verify:

```bash
ros2 topic echo /global_path --once
```

Use this to **visualize** the path while driving manually. For autonomous follow, you still need pure pursuit (above) or Nav2 (below).

Aliases: `autonomy:=csv_path`

---

## Nav2 vector pursuit (advanced — not validated yet)

Full Derek stack: CSV → `/global_path` → Nav2 → `/nav2_cmd_ackermann` → mux.

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=map \
  use_cartographer:=true
```

Aliases: `autonomy:=nav2_vector_pursuit`, `autonomy:=pure_pursuit`.

Try this **after** pure pursuit works. See `roboracer_nav2_vector_pursuit/`.

---

## Legacy: `odom` frame (older sessions)

Early tests logged/teached paths in **`odom`**, which drifts. **Do not use for competition-style racelines** unless you accept the path shifting over time.

```bash
# Legacy — odom-frame teach log (not recommended for handoff pipeline)
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=odom
```

Team 7's validated offline pipeline outputs **`map`-frame** geometry. Always use `pursuit_world_frame:=map` and `world_frame:=map` for pursuit.

---

## Other modes

| `autonomy` | Purpose | Drives car? |
|------------|---------|-------------|
| `wall_follow` (default) | LiDAR corridor follow | Yes → `/drive` (need /pointcloud_to_laserscan param configuration adjustment) |
| `none` | Manual RC only + sensors | No (RC only) |
| `raceline_path` | Publish `/global_path` | **No** |
| `raceline` | Nav2 follow | Yes → `/nav2_cmd_ackermann` |
| `raceline_pure_pursuit` / `raceline_geometric` | Launch-integrated geometric pursuit (experimental) | Yes — prefer standalone node above |

---

## Pipeline overview

```text
Bag on car → offline de-drift (laptop) → build_raceline_from_bag.py → traj_race_cl.csv
       |
       v
On car: bringup (Cartographer, map frame) + raceline_pure_pursuit_node → /drive → VESC
```

Optional parallel path:

```text
traj_race_cl.csv → traj_csv_path_publisher → /global_path → [Nav2] → /nav2_cmd_ackermann
```

---

## VESC on UCSD-Blue

```bash
sudo ln -sf /dev/ttyACM0 /dev/sensors/vesc
```

(`car_map_setup.sh` does this automatically.)

---

## Image

```bash
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
docker pull "$IMAGE"
```

See [02_DOCKER_BUILD_PUSH.md](02_DOCKER_BUILD_PUSH.md) to rebuild.
