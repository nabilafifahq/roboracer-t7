# ORB-SLAM3 (Mechazo) Docker Spike

This guide adds a separate Docker image for ORB-SLAM3 testing without disturbing the existing `full-stack` flow.

## 1) Create a safe branch

```bash
git switch -c spike/orbslam3-mechazo
```

## 2) Build and push ORB-SLAM3 image

From repo root:

```bash
chmod +x scripts/docker_build_orbslam3_mechazo.sh
DOCKER_USER=nabilafifahq IMAGE_NAME=roboracer-t7 TAG=orbslam3-mechazo \
  PLATFORM=linux/arm64 \
  ./scripts/docker_build_orbslam3_mechazo.sh
```

## 3) Run on car

On car host:

```bash
export IMAGE=nabilafifahq/roboracer-t7:orbslam3-mechazo
./scripts/car_run.sh
```

Inside container:

```bash
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
source /opt/orbslam3_ws/install/setup.bash
```

## 4) Start baseline stack and OAK

Terminal A:

```bash
ros2 launch /race_ws/bringup.launch.py use_slam:=true
```

Terminal B:

```bash
ros2 launch depthai_ros_driver camera.launch.py camera_model:=OAK-D-W
```

## 5) Bridge OAK topics to common ORB topic names

Terminal C:

```bash
ros2 run topic_tools relay /oak/rgb/image_raw /camera/image_raw
```

Terminal D:

```bash
ros2 run topic_tools relay /oak/imu/data /imu
```

## 6) Verify topic availability/rates

Any terminal:

```bash
orbslam3_mechazo_topics
```

## 7) Verify ORB executables

```bash
orbslam3_mechazo_execs
```

Then run the executable pair required by the Mechazo package (names shown by `orbslam3_mechazo_execs`).

## Notes

- If `/oak/rgb/image_raw` stays around 3-4 Hz, ORB tracking will be poor. Prefer USB3 (`USB SPEED: SUPER`) and disable extra OAK workloads if needed.
- This spike image keeps ORB in `/opt/orbslam3_ws`, separate from `/race_ws`.
- Rollback is simple: switch image back to `nabilafifahq/roboracer-t7:full-stack`.
