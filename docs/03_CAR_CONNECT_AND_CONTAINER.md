# Car Connect and Container Startup

This page is for connecting to the car host and entering the runtime container.

---

## 0) Network prerequisite (before SSH)

1. Connect your laptop to Wi-Fi: `ucsd_robocar`
2. Confirm you are targeting the correct vehicle: **1tenth blue car**
3. The expected host/user for this car is:

```bash
ssh ucsd-blue@ucsd-blue.local
```

If your laptop is not on `ucsd_robocar`, SSH discovery usually fails.

---

## 1) Power-on sequence (do this first)

Use this order every time for consistent behavior:

1. Turn ON the RC controller first.
2. Turn ON car power.
3. Wait 20-60 seconds for Pi boot and Wi-Fi.
4. Confirm network is up from your laptop:

```bash
ping -c 2 ucsd-blue.local
```

If `.local` does not resolve, use known car IP in later steps.

---

## 2) SSH into car host

Preferred:

```bash
ssh ucsd-blue@ucsd-blue.local
```

If `.local` fails, use the known IP:

```bash
ssh ucsd-blue@<car_ip>
```

Expected:
- Host shell prompt appears, similar to: `ucsd-blue@UCSD-Blue:~ $`

---

## 3) Pull image

Class default:

```bash
docker pull nabilafifahq/roboracer-t7:main-latest
```

Expected:
- Pull completes without error
- Image visible in `docker images`

If your team publishes its own image, set:

```bash
export IMAGE=<your_dockerhub_username>/roboracer-t7:main-latest
docker pull ${IMAGE}
```

---

## 4) Start container

Recommended helper:

```bash
./scripts/car_run.sh
```

Expected:
- Container starts
- Prompt changes to container prompt, similar to: `root@UCSD-Blue:/race_ws#`

To override image for your own namespace:

```bash
IMAGE=<your_dockerhub_username>/roboracer-t7:main-latest ./scripts/car_run.sh
```

Optional: override Livox MID360 config (host IP/LiDAR IP/ports) without forking:

```bash
cp /path/to/your/MID360_config.json ~/MID360_config.local.json
LIVOX_MID360_CONFIG_PATH=~/MID360_config.local.json ./scripts/car_run.sh
```

This bind-mounts your local config into the container at:
`/race_ws/src/drivers/livox_ros_driver2/config/MID360_config.json`

Useful helpers:

```bash
./scripts/car_status.sh
./scripts/car_exec.sh
./scripts/car_launch.sh
./scripts/car_stop.sh
```

Equivalent explicit command:

```bash
docker run --rm -it \
  --name roboracer_t7 \
  --net=host \
  --ipc=host \
  --privileged \
  --device=/dev/input/js0 \
  --device=/dev/ttyACM0 \
  --device=/dev/ttyACM1 \
  -v /dev/sensors:/dev/sensors \
  -v /dev/bus/usb:/dev/bus/usb \
  ${IMAGE:-nabilafifahq/roboracer-t7:main-latest}
```

---

## 5) Source ROS environment

Inside container:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
```

Expected:

```bash
printenv | grep -E '^ROS_DISTRO='
```

Output should include `ROS_DISTRO=humble`.

Important:

- `./scripts/car_exec.sh` is designed to open a shell with ROS already sourced.
- If you open any additional shell manually (for example with `docker exec -it ... bash`), run the same source commands again in that shell.
- Quick check:

```bash
printenv | grep -E '^ROS_DISTRO='
```

---

## 6) Setup VESC symlink

Inside container:

```bash
mkdir -p /dev/sensors
if [ -e /dev/ttyACM1 ]; then
  ln -sf /dev/ttyACM1 /dev/sensors/vesc
else
  ln -sf /dev/ttyACM0 /dev/sensors/vesc
fi
ls -l /dev/sensors/vesc
```

Expected:
- `/dev/sensors/vesc` points to `/dev/ttyACM1` or `/dev/ttyACM0`

---

## 7) Open additional sourced shell (optional)

From host:

```bash
./scripts/car_exec.sh
```

---

## 8) Power-off sequence (recommended)

1. Stop ROS launch (`Ctrl+C`).
2. Stop container (`./scripts/car_stop.sh` or exit running shell).
3. Turn OFF car power.
4. Turn OFF RC controller last.
