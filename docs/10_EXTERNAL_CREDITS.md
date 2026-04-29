# External Credits and Licenses

This file tracks third-party software used by this project.

---

## A) Repository pulled at build time

These are the exact repos currently pulled by `docker/racer.repos`:

- `fish-mouse/f1tenth_system`
  - URL: <https://github.com/fish-mouse/f1tenth_system>
  - Purpose: base F1TENTH stack, teleop, mux, VESC dependencies

- `fish-mouse/livox_ros_driver2`
  - URL: <https://github.com/fish-mouse/livox_ros_driver2>
  - Purpose: Livox MID-360 ROS 2 driver used by this project

Additional clone in `docker/dockerfile` (not listed in `racer.repos`):

- `AgoraRobotics/ros2-system-monitor`
  - URL: <https://github.com/AgoraRobotics/ros2-system-monitor>
  - Purpose: `ros2_system_monitor` package; `bringup.launch.py` includes `system_monitor.launch.py` for `/diagnostics` alongside optional `ros2 bag record`.

---

## B) Original upstream projects to credit

The `fish-mouse/*` repos above are team-access mirrors/forks. Original upstream projects must still be credited:

- `f1tenth/f1tenth_system`
  - URL: <https://github.com/f1tenth/f1tenth_system>
  - Upstream source for F1TENTH system code

- `Livox-SDK/livox_ros_driver2`
  - URL: <https://github.com/Livox-SDK/livox_ros_driver2>
  - Upstream source for Livox ROS driver

- `Livox-SDK/Livox-SDK2`
  - URL: <https://github.com/Livox-SDK/Livox-SDK2>
  - Livox SDK dependency used by driver builds

- `ros-perception/pointcloud_to_laserscan`
  - URL: <https://github.com/ros-perception/pointcloud_to_laserscan>
  - Used through apt package for PointCloud2 -> LaserScan conversion

---

## C) Additional ROS packages from apt

Packages such as `joy`, `ackermann_msgs`, `pcl`, and `rviz2` are installed from official ROS 2 Humble apt repositories.
Their original licenses remain with upstream maintainers.

---

## D) Policy

- Keep third-party license files and notices unchanged.
- Do not remove upstream copyright headers.
- When adding a new external dependency:
  1. Add the build source repo (where we pull from).
  2. Add the original upstream repo (if different).
  3. Add one-line purpose.
