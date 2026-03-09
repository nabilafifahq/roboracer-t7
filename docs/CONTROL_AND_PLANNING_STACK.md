# Control & Planning Stack (RoboRacer T7)

This doc maps the **current** control/planning stack, lists **desired behaviors**, and describes how to **add one repo, integrate, then repeat**.

---

## 1. Current stack map (control vs planning)

### 1.1 High-level flow

```
  [ Human input ]     [ Optional: autonomy / planning ]
         │                          │
         ▼                          ▼
  joy_node → joy_teleop ──► /teleop  (AckermannDriveStamped)
         │                          │
         │                    (future: /autonomy or /path_cmd)
         │                          │
         └──────────┬────────────────┘
                    ▼
            ackermann_mux  (picks one source)
                    │
                    ▼
            ackermann_to_vesc_node  (Ackermann → motor/servo)
                    │
                    ▼
            vesc_driver_node  (serial → VESC hardware)
                    │
                    ▼
            [ Wheels / steering ]
```

### 1.2 Control vs planning (today)

| Layer        | Role                         | In this repo? | Where it lives / how it runs |
|-------------|------------------------------|---------------|------------------------------|
| **Perception** | Camera, LiDAR, etc.          | Partial       | OAK-D: `depthai_ros_driver` (apt). LiDAR: `livox_ros_driver2` (racer.repos, build skipped in Docker). |
| **Planning**   | Path, waypoints, obstacles   | **No**        | None. No node produces an “autonomy” Ackermann stream. |
| **Control**    | Turn desired motion into commands | **Yes**   | **f1tenth_system**: `ackermann_mux`, `ackermann_to_vesc_node`, `vesc_driver_node`. |
| **Teleop**     | Human → Ackermann             | **Yes**       | **f1tenth_system**: `joy_node`, `joy_teleop` → `/teleop`. |

So today the stack is **control + teleop only**; there is **no planning layer**. Adding “planning” means adding at least one node that publishes `AckermannDriveStamped` (or equivalent) into a topic that the mux can use (e.g. `/autonomy`).

### 1.3 Where things come from

| Component              | Source | How you get it |
|------------------------|--------|----------------|
| f1tenth_stack, ackermann_mux, vesc, teleop_tools | `docker/racer.repos` → **fish-mouse/f1tenth_system** (submodules) | `vcs import` + `colcon build` |
| Launch (full bringup)  | f1tenth_system | `ros2 launch f1tenth_stack no_lidar_bringup_launch.py` |
| Car-only (no joy)      | Your fork (see FORK_CAR_ONLY_LAUNCH.md) | `ros2 launch f1tenth_stack no_lidar_car_only_bringup_launch.py` |
| OAK-D camera           | apt: `ros-humble-depthai-ros` | In Dockerfile |
| RViz2                  | apt: `ros-humble-rviz2` | In Dockerfile |

### 1.4 Important topics (control path)

| Topic | Type | Publisher | Subscriber |
|-------|------|-----------|------------|
| `/teleop` | `ackermann_msgs/msg/AckermannDriveStamped` | joy_teleop (or laptop in wireless mode) | ackermann_mux |
| (future) `/autonomy` or `/path_cmd` | Same | Planning node (e.g. pure_pursuit) | ackermann_mux |
| Mux output (internal) | Same | ackermann_mux | ackermann_to_vesc_node |
| `/commands/motor/speed` | VESC type | ackermann_to_vesc_node | vesc_driver_node |
| `/commands/servo/position` | VESC type | ackermann_to_vesc_node | vesc_driver_node |

To add planning, the new node must publish **AckermannDriveStamped** on a topic that ackermann_mux is configured to accept (and optionally give lower priority than `/teleop` for safety).

---

## 2. Desired behaviors (checklist)

Use this to decide what to add next. Tick when you have a repo + integration.

| # | Behavior | Description | Typical input | Output | Status |
|---|----------|-------------|--------------|--------|--------|
| 1 | **Waypoint / path following** | Follow a list of waypoints or a path (e.g. pure pursuit) | Path/waypoints, odometry (or pose) | AckermannDriveStamped | First candidate below |
| 2 | **Lane keeping** | Stay in lane from camera (or pre-mapped path) | Image or lane model | AckermannDriveStamped | Future |
| 3 | **Obstacle stop / slow** | Slow or stop when obstacle in front | Depth or detections | AckermannDriveStamped (or modify mux) | Future |
| 4 | **Full autonomy (e.g. Nav2)** | Plan and follow paths with obstacle avoidance | Map, goal, costmap, sensors | Nav2 → controller → Ackermann | Future (heavier) |

---

## 3. Add one repo, integrate, then repeat

### 3.1 Process (each new repo)

1. **Pick one behavior** from the table above (or your own).
2. **Search for a repo**: GitHub keywords e.g. `ROS2 humble ackermann path follower`, `f1tenth pure pursuit`, `waypoint follower ackermann_msgs`.
3. **Check compatibility**: ROS 2 distro (Humble), dependencies (`ackermann_msgs`, `nav_msgs`, etc.), and that it **publishes** `AckermannDriveStamped` (or that you can add a small relay).
4. **Add to the workspace**: Put the repo in `docker/racer.repos` (see format below). Rebuild the image (or `vcs pull` + `colcon build`).
5. **Integrate with the mux**:
   - Configure the planning node to publish to a topic (e.g. `/autonomy`).
   - In your **f1tenth_system fork**, adjust ackermann_mux config so it has a second input (e.g. `/autonomy`) with **lower** priority than `/teleop` (so joystick overrides autonomy).
6. **Launch**: Add the planning node to a launch file (same launch as bringup, or a separate “autonomy” launch that you run when you want path following).
7. **Test**: With teleop disabled or idle, run the planner and confirm the car follows; then confirm teleop overrides.
8. **Repeat** for the next behavior (next repo).

### 3.2 First repo: Pure Pursuit (path / waypoint following)

A natural first addition is a **pure pursuit** (or waypoint follower) node that subscribes to a path/waypoints and publishes `AckermannDriveStamped`, then feed that into ackermann_mux.

**Repo added in this repo:** `pure_pursuit` from **f1tenth-dev** (see `docker/racer.repos`).

- **Upstream:** https://github.com/f1tenth-dev/pure_pursuit (branch: `main` in racer.repos).
- **If build fails (e.g. ROS 1 only):** Edit `docker/racer.repos`: set `url` to a ROS 2 fork (e.g. search GitHub for `pure_pursuit ros2 humble`) or change to another waypoint-follower package. See Section 3.1 for the integration pattern.

**Build and first run**

- Rebuild the image so the new repo is pulled and built:  
  `docker build -t equip_test:arm64 -f docker/dockerfile .`  
  (Or, if you already have a container with the workspace mounted, run `vcs import . < docker/racer.repos` from repo root and `colcon build` in the workspace.)
- If the build fails (e.g. pure_pursuit is ROS 1), change `docker/racer.repos` to a ROS 2 fork or another package as in Section 3.1.

**Integration steps (once the package builds):**

1. **Topics**
   - Find what the node subscribes to (e.g. path, waypoints, odom/pose).
   - Find what topic it publishes (e.g. `drive` or `cmd`). Remap that to `/autonomy` so the mux can subscribe.
2. **Mux**
   - In your f1tenth_system fork, edit ackermann_mux config (e.g. `ackermann_mux_config.yaml`) to add an input topic `/autonomy` with priority **below** `/teleop`.
3. **Launch**
   - Either add the pure_pursuit node to `no_lidar_bringup_launch.py` (or your car-only launch), or create `autonomy_bringup_launch.py` that includes bringup + pure_pursuit.
4. **Path source**
   - Provide a path (e.g. from a file, or from a separate “path publisher” node). Document the path topic name and format in this runbook.

**Verification**

- `ros2 topic echo /autonomy` shows Ackermann messages when the path is active.
- With teleop idle, the car follows the path; with teleop active, teleop overrides.

### 3.3 After the first repo (repeat)

- **Next behaviors** (examples): lane keeping (vision node → Ackermann), obstacle reaction (depth/detections → speed/stop).
- For each: search → add to `racer.repos` → build → wire topic to mux (or to a small relay that publishes Ackermann) → launch → test → document here or in a runbook.

---

## 4. Quick reference: where to look in the repo

| Task | Where |
|------|--------|
| Add a new dependency repo | `docker/racer.repos` |
| Rebuild after adding repo | `docker build -t equip_test:arm64 -f docker/dockerfile .` (or `vcs pull` + `colcon build` in container) |
| Mux config (input topics, priorities) | Your **f1tenth_system** fork, e.g. `f1tenth_stack/config/ackermann_mux_config.yaml` |
| Launch (what runs on the car) | f1tenth_system: `f1tenth_stack/launch/` |
| Control path (teleop → VESC) | RUNBOOK_PI_JOYSTICK.md, QUICKSTART.md, docs/FORK_CAR_ONLY_LAUNCH.md |

---

## 5. Summary

- **Current:** Control (VESC + ackermann_mux + ackermann_to_vesc) + teleop (`/teleop`). **No planning.**
- **To add planning:** Add nodes that publish `AckermannDriveStamped` to a topic (e.g. `/autonomy`) and configure ackermann_mux to use it with lower priority than `/teleop`.
- **Process:** Pick one behavior → find repo → add to `racer.repos` → integrate with mux and launch → test → repeat for the next behavior.
