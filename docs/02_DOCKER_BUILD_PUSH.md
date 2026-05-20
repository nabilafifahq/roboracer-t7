# Docker Build and Push Guide

Use this when updating the stack image.

Important: do **not** log in to another student's Docker Hub account.

---

## 1) Choose your workflow

### A) Run the class-validated image only (most users)

You only need pull access:

```bash
docker pull nabilafifahq/roboracer-t7:main-latest
```

No Docker Hub login is required for public pull.

### B) Build and publish your own image (maintainers)

Use your own Docker Hub username:

```bash
export DOCKER_USER=<your_dockerhub_username>
export IMAGE=${DOCKER_USER}/roboracer-t7:main-latest
```

Then follow build/tag/push below.

---

## 2) Build locally

From repo root:

```bash
docker build -t roboracer-t7:main-latest -f docker/dockerfile .
```

The Dockerfile copies `config/joy_rc_steer_fix.yaml` (RC deadman `buttons[1]`, axes 1/3) and `bringup.launch.py` into `/race_ws/config/` so the image matches repo defaults without relying on `/tmp` hacks.

---

## 2b) Build from a pinned git commit (example: [bae4787](https://github.com/nabilafifahq/roboracer-t7/tree/bae47872ddfa0c90f8f9607d55ecae597e89c3ae))

Use this when you need a reproducible build from a specific tree (e.g. class submission snapshot).

```bash
git clone https://github.com/nabilafifahq/roboracer-t7.git
cd roboracer-t7
git checkout bae47872ddfa0c90f8f9607d55ecae597e89c3ae
docker build -t roboracer-t7:bae4787 -f docker/dockerfile .
```

If that commit is missing later fixes (for example RC deadman index `1` everywhere), merge or cherry-pick from `main` **before** `docker build`, or build from `main` at/after the commit that includes those files.

**Raspberry Pi (ARM64)** images are often tagged `humble-arm64` on the car. Build on the Pi, or use buildx from a desktop:

```bash
docker buildx build --platform linux/arm64 \
  -t ${DOCKER_USER:-nabilafifahq}/roboracer-t7:humble-arm64 \
  -f docker/dockerfile --load .
```

(`--load` requires a single platform; for multi-arch push, omit `--load` and use `--push`.)

---

## 2c) Hallway / manual_map_logger test image (`hallway-test`)

Build and push the stack image used for hallway logging and TF/EKF checks:

```bash
# From repo root (same Dockerfile as main-latest)
docker build -t nabilafifahq/roboracer-t7:hallway-test -f docker/dockerfile .
docker push nabilafifahq/roboracer-t7:hallway-test
```

On the car, pull and run with that tag (override the default `main-latest`):

```bash
export IMAGE=nabilafifahq/roboracer-t7:hallway-test
docker pull "$IMAGE"
./scripts/car_launch.sh   # or car_run.sh / car_exec.sh — they honor $IMAGE
```

For **ARM64** (Raspberry Pi) from a desktop, use `buildx` and the same tag:

```bash
docker buildx build --platform linux/arm64 \
  -t nabilafifahq/roboracer-t7:hallway-test \
  -f docker/dockerfile --push .
```

---

## 2d) Full stack + manual map / SLAM (`manual-logger`)

Same **`docker/dockerfile`** as everything else (Cyclone **`ENV`**, **`ros-humble-rmw-cyclonedds-cpp`**, **`ros-humble-slam-toolbox`**, EKF, **`bringup.launch.py`** with **`use_slam`**, **`config/slam_toolbox_mapper_online_async.yaml`**, **`reactive_control`** / **`manual_map_logger`**, vesc patch, Livox, preflight script).

**Build and push (x86 builder → Hub; Pi pulls):**

```bash
cd /path/to/roboracer-t7
docker build --no-cache -t nabilafifahq/roboracer-t7:manual-logger -f docker/dockerfile .
docker push nabilafifahq/roboracer-t7:manual-logger
```

**Build for Raspberry Pi ARM64 from a Mac/CI (push only, no `--load`):**

```bash
docker buildx build --platform linux/arm64 \
  -t nabilafifahq/roboracer-t7:manual-logger \
  -f docker/dockerfile --push .
```

**On the car:**

```bash
docker rm -f roboracer_t7 2>/dev/null || true
docker pull nabilafifahq/roboracer-t7:manual-logger
export IMAGE=nabilafifahq/roboracer-t7:manual-logger
docker run --rm -it --name roboracer_t7 --net=host --ipc=host --privileged \
  --device=/dev/input/js0 --device=/dev/ttyACM0 --device=/dev/ttyACM1 \
  -v /dev/sensors:/dev/sensors -v /dev/bus/usb:/dev/bus/usb \
  "$IMAGE"
```

Inside the container you should **not** need `apt-get install ros-humble-rmw-cyclonedds-cpp` anymore; Cyclone is in the image. Optional check:

```bash
printenv RMW_IMPLEMENTATION
ldconfig -p | grep -i cyclonedds | head
dpkg -l | grep -E 'slam-toolbox|rmw-cyclonedds'
grep -n slam_toolbox /race_ws/bringup.launch.py | head
```

---

## 3) Tag for Docker Hub

```bash
docker tag roboracer-t7:main-latest ${IMAGE}
```

---

## 4) Login and push (your account)

```bash
docker login
docker push ${IMAGE}
```

---

## 5) Verify digest (important)

After push, save the digest shown in terminal for release notes.

Example:

```text
main-latest: digest: sha256:...
```

---

## 6) Pull on car

If using class image:

```bash
docker pull nabilafifahq/roboracer-t7:main-latest
```

If using your own image:

```bash
docker pull ${IMAGE}
```
