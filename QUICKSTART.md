# RoboRacer T7 Quickstart (Pi + Joystick)

Fast start guide for lab day.

---

## 1) On laptop: update repo

```bash
cd ~/Documents/roboracer-t7
git pull
```

---

## 2) SSH to Raspberry Pi

```bash
ssh ucsd-blue@ucsd-blue.local
```

---

## 3) Start container (Pi host shell)

```bash
docker pull nabilafifahq/joystick_test:latest

docker run --rm -it \
  --net=host \
  --ipc=host \
  --privileged \
  --device=/dev/input/js0 \
  nabilafifahq/joystick_test:latest
```

You should now see:
`root@UCSD-Blue:/race_ws#`

---

## 4) Inside container: ROS + device links

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash

mkdir -p /dev/sensors
ln -sf /dev/input/js0 /dev/input/joypad-f710
ln -sf /dev/ttyACM0 /dev/sensors/vesc
```

---

## 5) Launch driving stack

```bash
ros2 launch f1tenth_stack no_lidar_bringup_launch.py
```

If launch is healthy, VESC and joystick nodes should start without fatal errors.

---

## 6) Drive controls

- Hold **LB** (deadman)
- Move **left stick**:
  - up/down = speed
  - left/right = steering

If LB is released, command returns to zero.

---

## 7) Quick debug terminal (optional)

Open a new terminal, SSH to Pi, then:

```bash
docker ps
docker exec -it <container_id> bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
ros2 topic echo /teleop
```

You should see `ackermann_msgs/msg/AckermannDriveStamped` messages while holding LB and moving sticks.

---

## 8) Common fixes

- `ros2: command not found`:
  - You are on host shell, or forgot `source /opt/ros/humble/setup.bash`.
- `No such container`:
  - Run `docker ps` and use current container ID.
- VESC serial error `/dev/sensors/vesc`:
  - Recreate symlink to `/dev/ttyACM0`.
- Joystick not found `/dev/input/joypad-f710`:
  - Recreate symlink to `/dev/input/js0`.

---

## 9) Stop

- In launch terminal: `Ctrl+C`
- Exit container: `exit`
- Confirm stopped: `docker ps`

---

For full details and troubleshooting, see `RUNBOOK_PI_JOYSTICK.md`.
