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
