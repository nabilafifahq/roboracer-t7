# PointCloud2 to LaserScan Runbook (Fishmouse Branch)

This runbook assumes the stack is delivered by Docker image only.

**Current unified stack:** `bringup.launch.py` already includes Livox + `pointcloud_to_laserscan`. Prefer:

```bash
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ros2 launch /race_ws/bringup.launch.py
```

The image build patches Livox so `/livox/lidar` is **`sensor_msgs/msg/PointCloud2`** with **`frame_id` = `laser`** (matches `base_link` → `laser` TF). See `docs/07_TROUBLESHOOTING.md` §10 if you need manual patches on an old image.

Goal:

- convert Livox `PointCloud2` topic to `/scan` (`LaserScan`)
- verify it works on the car after SSH
- optionally visualize in RViz

---

## 1) Build and publish image (developer machine)

From repo root:

```bash
docker build -t <your-dockerhub-user>/roboracer-t7:sync-fishmouse-p2l -f docker/dockerfile .
docker push <your-dockerhub-user>/roboracer-t7:sync-fishmouse-p2l
```

---

## 2) SSH to car and pull image

```bash
ssh ucsd-blue@ucsd-blue.local
docker pull <your-dockerhub-user>/roboracer-t7:sync-fishmouse-p2l
```

---

## 3) Run container on car

```bash
docker run --rm -it \
  --net=host \
  --ipc=host \
  --privileged \
  --device=/dev/input/js0 \
  --device=/dev/ttyACM0 \
  --device=/dev/ttyACM1 \
  -v /dev/sensors:/dev/sensors \
  -v /dev/bus/usb:/dev/bus/usb \
  <your-dockerhub-user>/roboracer-t7:sync-fishmouse-p2l
```

Inside container:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
```

---

## 4) Start base nodes (manual + Livox)

Terminal A:

```bash
ros2 launch f1tenth_stack no_lidar_bringup_launch.py
```

Terminal B:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Check Livox topic name:

```bash
ros2 topic list | grep -Ei "livox|point|imu"
```

If your cloud topic is not `/livox/lidar`, replace it in Step 5 remap.

---

## 5) Run PointCloud2 -> LaserScan node

Terminal C:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash

ros2 run pointcloud_to_laserscan pointcloud_to_laserscan_node --ros-args \
  -r cloud_in:=/livox/lidar \
  -r scan:=/scan \
  --params-file /race_ws/config/pointcloud_to_laserscan_indoor.yaml
```

---

## 6) Verify it works (no RViz required)

Terminal D:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash

ros2 topic hz /scan
ros2 topic echo /scan --once
```

Pass condition:

- `/scan` publishes continuously (non-zero Hz)
- message has valid `ranges` array and expected frame

Extra checks:

```bash
ros2 topic info /scan
ros2 topic list | grep -E "^/livox/lidar$|^/scan$"
```

---

## 7) Do we need RViz?

Short answer: no.

- RViz is optional for visualization/debugging.
- For autonomy bringup, `ros2 topic hz`, `echo`, and controller behavior are enough.

Use RViz when:

- `/scan` exists but wall geometry looks wrong
- you need quick visual confirmation of hallway wall detection

---

## 8) Optional RViz workflow

If RViz runs on the same machine as ROS graph (inside container with display forwarding configured):

```bash
rviz2
```

In RViz:

- Fixed Frame: `base_link` (or your active TF root)
- Add display: `LaserScan`
- Topic: `/scan`

If using remote laptop RViz:

- ensure network route to ROS graph
- set matching `ROS_DOMAIN_ID`
- run `rviz2` on laptop and subscribe to `/scan`

---

## 9) Common failure patterns

- No `/scan` output:
  - wrong cloud remap; check actual Livox topic and remap `cloud_in`
- `/scan` rate is low or unstable:
  - check Livox health first (`ros2 topic hz /livox/lidar`)
- Walls look noisy:
  - tune `min_height` and `max_height` in `/race_ws/config/pointcloud_to_laserscan_indoor.yaml`
- TF-related warnings:
  - verify `target_frame` exists in TF tree and matches your car setup

---

## 10) One-command quick health check

```bash
ros2 topic hz /livox/lidar
ros2 topic hz /scan
ros2 topic echo /scan --once
```

If all three are healthy, bridge is working and ready for planner/localization that requires LaserScan.
