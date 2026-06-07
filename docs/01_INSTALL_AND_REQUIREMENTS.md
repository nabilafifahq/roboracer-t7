# Install and Requirements

What must be ready before driving tests. For car/track details see [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md).

---

## 1) Required hardware

- RoboRacer car with Raspberry Pi installed
- VESC connected to Pi (`/dev/ttyACM*`)
- RC receiver/controller connected to Pi (`/dev/input/js0`)
- Livox Mid-360 connected
- Stable power source (battery or bench supply)

---

## 2) Required software

- Docker on host machine (Pi host and developer machine)
- Git
- SSH client

Optional but recommended:

- RViz2-capable machine for visualization

---

## 3) Accounts and access

- GitHub access to this repository
- Docker Hub account (only if you will push your own image)
- SSH access to car host

---

## 4) Quick prerequisite check

On car host (or via local terminal):

```bash
docker --version
ls -l /dev/input/js0
ls -l /dev/ttyACM*
```

If device paths are missing, fix hardware/wiring first.

---

## 5) Current default runtime image

```bash
nabilafifahq/roboracer-t7:cartographer-ekf
```

This is the mapping image (Cartographer + EKF). Older tag `full-stack` works for basic bringup.
Use this unless your team explicitly validates a newer tag.
If you build/push your own image, use your own namespace:

```bash
<your_dockerhub_username>/roboracer-t7:<tag>
```
