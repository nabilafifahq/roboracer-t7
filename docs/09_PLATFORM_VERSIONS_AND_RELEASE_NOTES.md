# Platform Versions and Release Notes

Use this file as the single source of truth for runtime versions and update history.

---

## A) Official Runtime Platform (Current)

### Hardware

- Compute: **Raspberry Pi 5** (not Jetson)
- LiDAR: **Livox Mid-360**
- Camera: **OAK-D W Pro**
- Motor controller: **VESC**
- RC controller/receiver: manual control + deadman

### Software

- OS: Linux on Raspberry Pi host
- ROS 2: **Humble**
- Container image: `nabilafifahq/roboracer-t7:main-latest`
- Docker Engine on car host: *(fill from command below)*
- Docker Engine on dev machine: *(optional)*

---

## B) Version Capture Commands

Run these and paste outputs in section C:

```bash
# On car host
docker --version

# In runtime container
ros2 --version
python3 --version
```

Optional:

```bash
git rev-parse --short HEAD
docker image inspect nabilafifahq/roboracer-t7:main-latest --format '{{index .RepoDigests 0}}'
```

---

## C) Current Validated Values

Update this block after each validated release.

- Date validated: `2026-03-12`
- Branch: `main`
- Git commit: `c450be7` *(update as needed)*
- Docker image tag: `nabilafifahq/roboracer-t7:main-latest`
- Docker image digest: `sha256:a9069f88e7d6a5cf67909f0c162ad88ad961ff3b22307779cc3045beefe5ec94` *(update if changed)*
- Docker version (car host): `TODO` *(run `docker --version` on car host and replace)*
- Docker version (dev machine): `Docker version 29.1.3, build f52814d`
- ROS 2 distro: `Humble`
- Manual config source: `config/joy_rc_steer_fix.yaml`

---

## D) Release Notes (Human-readable)

### 2026-03-13

- Unified launch uses stable manual RC config automatically.
- Livox launch path fixed to `launch_ROS2`.
- `/scan` QoS compatibility fixed for autonomy subscriber.
- Added helper scripts for container workflow:
  - `scripts/car_run.sh`
  - `scripts/car_status.sh`
  - `scripts/car_exec.sh`
  - `scripts/car_launch.sh`
  - `scripts/car_stop.sh`

Add new entries below for every new validated update.
