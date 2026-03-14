# Car Connect and Container Startup

This page is for connecting to the car host and entering the runtime container.

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

---

## 3) Pull image

```bash
docker pull nabilafifahq/roboracer-t7:main-latest
```

---

## 4) Start container

Recommended helper:

```bash
./scripts/car_run.sh
```

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
  nabilafifahq/roboracer-t7:main-latest
```

---

## 5) Source ROS environment

Inside container:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
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
