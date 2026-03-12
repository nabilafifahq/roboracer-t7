# (current repo)

## What exists in this repo vs what’s “external”

- **What was added:**
  - `wall_follow_script/` (ROS 2 Python package: `reactive_control`)
  - `ackermann_mux-foxy-devel/` (vendored `ackermann_mux`)
  - `vesc-main/` (vendored VESC packages)
  - `config/ackermann_mux_topics.yaml` (your project mux inputs)


### Useful topics to know in the future

- **Autonomy input**: `/scan` (`sensor_msgs/LaserScan`)
- **Autonomy output to mux**: `/ackermann_mux/input/nav_0` (`ackermann_msgs/AckermannDriveStamped`)
- **Teleop output**: `/teleop` (`ackermann_msgs/AckermannDriveStamped`)
- **Mux output**: **`ackermann_cmd`** (`ackermann_msgs/AckermannDriveStamped`)
  - This is the *default output topic* in the vendored `ackermann_mux`.

---

## What was changed

### `wall_follow_script/reactive_control/wall_follow_node.py`

- **Subscribe** changed from `autodrive/roboracer_1/lidar` → **`/scan`**
- **Publish** changed from `drive` → **`/ackermann_mux/input/nav_0`**

### `config/ackermann_mux_topics.yaml` (new)

Your project-level mux input config (do not edit the vendored package config for robot-specific wiring):

- `navigation` input: `/ackermann_mux/input/nav_0` (priority 10)
- `joystick` input: `/teleop` (priority 100)

Key reminder (ties into the future work)
Even though the mux inputs are now correct, the mux’s default output topic is ackermann_cmd (not /drive).
Later in bringup you’ll remap ackermann_cmd ↔ /drive depending on what ackermann_to_vesc_node expects.

