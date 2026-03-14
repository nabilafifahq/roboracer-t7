# Full Stack Reference Manual

This is the complete reference page for new team members and future classes.

Use this after reading:

- `00_START_HERE.md`

---

## 1) System Overview

RoboRacer T7 uses ROS 2 Humble in Docker to run:

- manual RC driving (safe deadman switch)
- LiDAR point cloud ingestion and conversion
- slow indoor hallway autonomy (wall-follow baseline)
- VESC motor/steering actuation

Current baseline image:

- `nabilafifahq/roboracer-t7:main-latest`

For custom pushes, each team/user should publish to their own namespace:

- `<your_dockerhub_username>/roboracer-t7:<tag>`

---

## 2) Hardware Setup (Current Team Platform)

- Compute: Raspberry Pi (car host)
- LiDAR: Livox Mid-360 (3D LiDAR + built-in IMU)
- Camera: OAK-D W Pro
- Motor control: VESC (EDU VESC 6 stack)
- RC controller/receiver (manual override and deadman switch)
- Power system: LiPo / bench supply (must provide stable 5V path to compute)

Important:

- For manual safety, deadman switch is mapped in `config/joy_rc_steer_fix.yaml`.
- For LiDAR, host IP + LiDAR IP + ports must match `MID360_config.json` expectations.
- Use runtime override with `LIVOX_MID360_CONFIG_PATH=<local_json> ./scripts/car_run.sh` to adjust network settings without forking `livox_ros_driver2`.

---

## 3) Software Components

- ROS 2 Humble (runtime)
- Docker image + containerized workspace
- `f1tenth_stack` (manual + VESC path)
- `livox_ros_driver2` (Livox input)
- `pointcloud_to_laserscan` (bridge: `/livox/lidar` -> `/scan`)
- `reactive_control/wall_follow_node` (autonomy planning/control baseline)

---

## 4) Node and Topic Function Summary

Detailed map:

- `MANUAL_AUTONOMY_NODE_TOPIC_FLOW.md`

Core command flow:

- RC/manual: `/joy` -> `/teleop` -> `ackermann_mux` -> `ackermann_cmd` -> VESC commands
- Autonomy: `/livox/lidar` -> `/scan` -> `/drive` -> `ackermann_mux` -> `ackermann_cmd` -> VESC

---

## 5) Required Configuration Files

- `config/joy_rc_steer_fix.yaml`
  - RC axis mapping, deadman button index, teleop scaling
- `config/ackermann_mux_topics.yaml`
  - manual/autonomy input topic priorities
- `docker/config/pointcloud_to_laserscan_indoor.yaml`
  - LiDAR-to-scan bridge parameters
- Livox MID-360 config (`MID360_config.json` in Livox driver area)
  - host IP, LiDAR IP, and ports must match network setup
  - can be overridden at runtime via `LIVOX_MID360_CONFIG_PATH`

---

## 6) Commands Glossary (Most Used)

### Docker

- Build: `docker build -t <tag> -f docker/dockerfile .`
- Push: `docker push <repo>:<tag>`
- Pull: `docker pull <repo>:<tag>`
- Run: `docker run ... <repo>:<tag>`
- List containers: `docker ps`
- Enter container: `docker exec -it <container_id> bash`

### ROS 2

- Launch: `ros2 launch <package> <launch_file>`
- Run node: `ros2 run <package> <executable>`
- List nodes: `ros2 node list`
- List topics: `ros2 topic list`
- Topic rate: `ros2 topic hz <topic>`
- Topic echo: `ros2 topic echo <topic>`
- Params: `ros2 param list|get|set`

### Helper scripts in this repo

- `./scripts/car_run.sh`
- `./scripts/car_exec.sh`
- `./scripts/car_launch.sh`

---

## 7) Recommended Setup Flow (Mac/Linux User)

1. Read `00_START_HERE.md`
2. Install requirements from `01_INSTALL_AND_REQUIREMENTS.md`
3. Build/push image if needed (`02_DOCKER_BUILD_PUSH.md`)
4. SSH + container bringup (`03_CAR_CONNECT_AND_CONTAINER.md`)
5. Validate manual first (`04_MANUAL_DRIVE_SETUP.md`)
6. Start autonomy (`05_AUTONOMY_SETUP_AND_RUN.md`)
7. Run checklist (`06_VALIDATION_CHECKLIST.md`)
8. Use fixes in `07_TROUBLESHOOTING.md`

---

## 8) Safety Notes

- Always test on stand first.
- Keep deadman/manual override ready in every run.
- Stop immediately on unstable steering or unexpected acceleration.
- Never leave LiPo unattended while charging.
- Store LiPo at storage voltage when not in active use.

Demo/safety media in this repo:

- `How to set Battery to Storage Mode.mov`

---

## 9) External Reference Websites

RoboRacer:

- [RoboRacer Build](https://roboracer.ai/build)
- [RoboRacer Learn](https://roboracer.ai/learn)

F1TENTH docs:

- [Wireless software combine](https://f1tenth.readthedocs.io/en/foxy_test/getting_started/software_setup/software_combine.html)
- [VESC firmware setup](https://f1tenth.readthedocs.io/en/foxy_test/getting_started/firmware/firmware_vesc.html)
- [Hokuyo ethernet setup](https://f1tenth.readthedocs.io/en/foxy_test/getting_started/firmware/firmware_hokuyo10.html)
- [Driver workspace](https://f1tenth.readthedocs.io/en/foxy_test/getting_started/firmware/drive_workspace.html)
- [Driver workspace (Docker)](https://f1tenth.readthedocs.io/en/foxy_test/getting_started/firmware/drive_workspace_docker.html)
- [Driving index](https://f1tenth.readthedocs.io/en/foxy_test/getting_started/driving/index.html)
- [Manual driving + odometry](https://f1tenth.readthedocs.io/en/foxy_test/getting_started/driving/drive_manual.html)
- [Autonomous driving basics](https://f1tenth.readthedocs.io/en/foxy_test/getting_started/driving/drive_autonomous.html)

Livox:

- [Livox Viewer 2 User Manual](https://terra-1-g.djicdn.com/65c028cd298f4669a7f0e40e50ba1131/Mid360/Livox_Viewer_2_User_Manual_EN_v1.2.pdf)
- [Livox Wiki](https://livox-wiki-en.readthedocs.io/en/latest/)
- [Livox-SDK2](https://github.com/Livox-SDK/Livox-SDK2)
- [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2)

ROS2 parameters tutorials:

- [rclpy params tutorial](https://roboticsbackend.com/rclpy-params-tutorial-get-set-ros2-params-with-python/)
- [rclcpp params tutorial](https://roboticsbackend.com/rclcpp-params-tutorial-get-set-ros2-params-with-cpp/)

---

## 10) Repo and Documentation Policy

- All official docs go under `docs/`.
- Root should stay clean and minimal (single onboarding entry in `README.md`).
- Keep commands copy-pasteable and versioned with code changes.
- Prefer updating existing runbooks over creating duplicate files.
- Keep third-party attributions updated in `10_EXTERNAL_CREDITS.md`.
