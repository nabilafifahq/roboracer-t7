# Install and Requirements

This page covers what must be ready before any driving tests.

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
- Docker Hub access to pull/push images
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
nabilafifahq/roboracer-t7:main-latest
```

Use this unless your team explicitly validates a newer tag.
