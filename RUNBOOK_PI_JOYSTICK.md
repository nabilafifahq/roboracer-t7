# RoboRacer T7 Raspberry Pi Runbook (Joystick + VESC)

This guide is for running the car from a Raspberry Pi using Docker and ROS 2 Humble.

It covers:
- pulling latest code
- pulling/running Docker image
- terminal workflow
- joystick bringup
- VESC bringup
- common fixes

---

## 0) Prerequisites

- Raspberry Pi is on and reachable by SSH.
- Logitech F710 receiver is plugged in.
- VESC USB is plugged in.
- Docker is installed on Pi host.
- Docker image exists on Docker Hub: `nabilafifahq/joystick_test:latest`.

---

## 1) Update Repo (on your laptop)

```bash
cd ~/Documents/roboracer-t7
git pull
```

---

## 2) SSH into Raspberry Pi

```bash
ssh ucsd-blue@ucsd-blue.local
```

You should now be on Pi host shell, prompt similar to:
`(env) ucsd-blue@UCSD-Blue:~ $`

---

## 3) Pull and Run Docker Image (on Pi host)

```bash
docker pull nabilafifahq/joystick_test:latest

docker run --rm -it \
  --net=host \
  --ipc=host \
  --privileged \
  --device=/dev/input/js0 \
  nabilafifahq/joystick_test:latest
```

You should now be inside container:
`root@UCSD-Blue:/race_ws#`

---

## 4) Know Your Shell Context (important)

- Run `docker ...` commands on **Pi host shell** (`(env) ucsd-blue@UCSD-Blue:~ $`).
- Run `ros2 ...` commands inside **container shell** (`root@UCSD-Blue:/race_ws#`).

If you open a new `docker exec` shell, always source ROS again:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
```

---

## 5) Find Running Container ID

On Pi host shell:

```bash
docker ps
```

Example output:

```text
CONTAINER ID   IMAGE                               COMMAND                 STATUS        NAMES
440126236a97   nabilafifahq/joystick_test:latest   "/entrypoint.sh bash"   Up ...        zen_shamir
```

Attach from another terminal:

```bash
docker exec -it 440126236a97 bash
```

---

## 6) Device Path Fixes (required on this setup)

The launch expects:
- joystick at `/dev/input/joypad-f710`
- vesc serial at `/dev/sensors/vesc`

But Pi often exposes:
- `/dev/input/js0`
- `/dev/ttyACM0`

Create symlinks inside container:

```bash
mkdir -p /dev/sensors
ln -sf /dev/input/js0 /dev/input/joypad-f710
ln -sf /dev/ttyACM0 /dev/sensors/vesc

ls -l /dev/input/joypad-f710 /dev/sensors/vesc
```

---

## 7) Launch Full Driving Stack

Inside container:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
ros2 launch f1tenth_stack no_lidar_bringup_launch.py
```

Expected processes include:
- `joy_node`
- `joy_teleop`
- `ackermann_mux`
- `ackermann_to_vesc_node`
- `vesc_driver_node`

If you see VESC serial failure, check symlink step above.

---

## 8) Manual Driving Controls

- Deadman button: `LB` (button index 4 in this setup)
- Hold `LB` while commanding
- Left stick:
  - up/down = speed
  - left/right = steering

If deadman is not held, output will go back to zero.

---

## 9) Verification Commands (separate terminal)

Attach to running container, source ROS, then:

```bash
ros2 topic list | grep -Ei "teleop|drive|ackermann|vesc|cmd_vel"
ros2 topic echo /teleop
ros2 topic echo /commands/motor/speed
ros2 topic echo /commands/servo/position
```

When holding LB and moving sticks:
- `/teleop` should show non-zero `speed` / `steering_angle`
- motor/servo command topics should change

---

## 10) Common Errors and Fixes

### A) `docker: command not found`
You are inside container. Run `docker ...` on Pi host shell.

### B) `ros2: command not found`
You are either:
- on host shell, or
- inside container but forgot to source ROS.

### C) `No such container: <id>`
Container was restarted. Use `docker ps` and the new ID.

### D) `/teleop` not published
- Ensure `joy_node` and `joy_teleop` are running.
- Ensure deadman (LB) is held.

### E) Wheels do not move but `/teleop` changes
- Check VESC node is running and connected.
- Check motor power/e-stop hardware state.
- Check `/commands/motor/speed` and `/commands/servo/position` are changing.

### F) `sequence size exceeds remaining buffer`
Known noisy output in this setup. If topics and controls work, this can be ignored for now.

---

## 11) Suggested Terminal Layout

- **Terminal 1 (Pi host):** launch container
- **Terminal 2 (container):** run/monitor bringup
- **Terminal 3 (container):** topic echo and debugging

Open extra terminals only on host first, then attach with `docker exec`.

---

## 12) Safe Shutdown

- In launch terminal: `Ctrl+C`
- Exit container shell: `exit`
- Confirm stopped containers on host:

```bash
docker ps
```

With `--rm`, container is removed automatically on stop.
