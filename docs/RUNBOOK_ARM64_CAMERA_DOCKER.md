# Quick runbook: ARM64 host, Docker, and OAK-D camera

This doc summarizes how to run the race stack and OAK-D camera on an **ARM64 (aarch64)** machine (e.g. Raspberry Pi 5, Apple Silicon, or an aarch64 server like UCSD-Blue) using Docker.

---

## 1. Why this runbook?

- **Pre-built amd64 image** (e.g. `cabbagelover/equip_test:latest`) fails on ARM64 with:
  - `exec /entrypoint.sh: exec format error` — image is x86_64, host is ARM.
  - Even with `--platform linux/amd64`, running **DepthAI/camera** or heavy tools in the container can hit **QEMU** crashes: `cpu_exec: assertion failed (cpu == current_cpu)`.
- **Fix:** Build and run a **native ARM64** image on the ARM host so there is no emulation. Use that image for camera and USB.

---

## 2. After you SSH in (get back to the container)

Once you’re logged into the host (e.g. `ucsd-blue@UCSD-Blue:~ $`), do one of the following.

**If the container already exists** (you created it before):

```bash
docker start equip-test-arm
docker exec -it equip-test-arm bash
```

You should get a prompt like `root@...:/race_ws#`. You’re inside the container; plug in the OAK-D if needed and run `python3 /race_ws/src/scripts/check_camera.py` to verify.

**If the container doesn’t exist** (first time or you removed it):

```bash
docker run -it --privileged \
  -v /dev/bus/usb:/dev/bus/usb \
  --name equip-test-arm \
  equip_test:arm64 bash
```

Again you’ll get `root@...:/race_ws#`. If Docker says the image `equip_test:arm64` is missing, do the **one-time setup** (Section 3) first to build the image to build it.

**To leave the container:** type `exit` (you’re back on the host).

---

## 3. One-time setup: clone repo and build ARM64 image on the host

All commands below are on the **host** (your ARM machine), not inside a container. Prompt should look like `(env) ucsd-blue@UCSD-Blue:~ $`.

```bash
# Clone the repo
cd ~
git clone https://github.com/nabilafifahq/roboracer-t7.git
cd roboracer-t7

# Optional: use a specific branch
git checkout feat/doc-for-wheels   # or your branch

# Submodules (e.g. f1tenth_system)
git submodule update --init --recursive

# Build native ARM64 image (no --platform; uses host arch)
docker build -t equip_test:arm64 -f docker/dockerfile .
```

- First build can take **10–15+ minutes**.
- The Dockerfile skips `livox_ros_driver2` so the build completes without Livox (see repo Dockerfile/comments). Camera and VESC stack are included.

---

## 4. Run the ARM64 container with USB/camera access

On the **host**:

```bash
docker run -it --privileged \
  -v /dev/bus/usb:/dev/bus/usb \
  --name equip-test-arm \
  equip_test:arm64 bash
```

- `--privileged` and `-v /dev/bus/usb:/dev/bus/usb` give the container access to USB devices (OAK-D).
- You will get a shell inside the container (e.g. `root@...:/race_ws#`).

To **leave** the container: type `exit`.

To **start again later** (container already exists):

```bash
docker start equip-test-arm
docker exec -it equip-test-arm bash
```

To **recreate** (e.g. after reboot or if you removed the container):

```bash
docker rm -f equip-test-arm
docker run -it --privileged -v /dev/bus/usb:/dev/bus/usb --name equip-test-arm equip_test:arm64 bash
```

---

## 5. Verify OAK-D camera inside the container

Inside the container:

```bash
python3 /race_ws/src/scripts/check_camera.py
```

You should see something like:

```
=== CAMERA CONNECTED ===
Product Name: OAK-D-PRO-W-97
Board Name:   DM9098
=== SENSORS FOUND ===
 - Socket CameraBoardSocket.CAM_A: OV9782 (1280x800)
 ...
```

If you see **No OAK-D Camera found**: ensure the camera is plugged in and you started the container with `--privileged` and `-v /dev/bus/usb:/dev/bus/usb` (step 3).

---

## 6. Run the ROS 2 camera node

Inside the container, after camera check works:

```bash
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ros2 launch depthai_ros_driver driver.launch.py
```

Leave this running (it publishes image topics). If the launch file name differs on your install, list them:

```bash
ls $(ros2 pkg prefix depthai_ros_driver)/share/depthai_ros_driver/launch/
```

---

## 7. Record to rosbag and visualize in RViz

**Workflow:** Record camera (and other) topics to a rosbag → later play the bag and visualize in RViz. Live visualization method is TBD.

### 7.1 Saving bags to the host (recommended)

**Where:** On the **host** (your SSH prompt, e.g. `ucsd-blue@UCSD-Blue:~ $`), when you **create** the container with `docker run` — not inside the container. If `equip-test-arm` already exists without this volume, remove it (`docker rm -f equip-test-arm`) then run the command below.

So bags persist after the container is removed, start the container with a bind mount. On the **host**:

```bash
mkdir -p ~/rosbags
docker run -it --privileged \
  -v /dev/bus/usb:/dev/bus/usb \
  -v ~/rosbags:/rosbags \
  --name equip-test-arm \
  equip_test:arm64 bash
```

Bags saved to `/rosbags` in the container will appear in `~/rosbags` on the host.

(If the container already exists without this mount, remove it and re-run with `-v ~/rosbags:/rosbags`.)

### 7.2 Record a rosbag

**You need two terminals.** Open two SSH sessions to the host. In the first, get into the container (or you’re already in). In the second, attach to the same container. Then run the commands below in order.

**Terminal 1 — run these in order (leave the driver running):**

```bash
# If you're on the host (e.g. ucsd-blue@UCSD-Blue:~ $), get into the container first:
docker exec -it equip-test-arm bash

# Then inside the container, run:
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ros2 launch depthai_ros_driver driver.launch.py
```
Leave this running. When you’re done recording, press **Ctrl+C** here to stop the driver.

**Terminal 2 — run these in order:**

```bash
# On the host, attach to the same container:
docker exec -it equip-test-arm bash

# Inside the container:
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ros2 topic list
ros2 bag record -a -o /rosbags/cam_$(date +%Y%m%d_%H%M%S)
```
Let it record, then press **Ctrl+C** to stop. The bag is in `/rosbags/` (and in `~/rosbags` on the host if you used the mount in 7.1).

**Optional:** To record only specific image topics, in Terminal 2 replace the `ros2 bag record` line with (adjust topic names from `ros2 topic list`):
`ros2 bag record -o /rosbags/cam_$(date +%Y%m%d_%H%M%S) /oak_d_pro/color/image_raw /oak_d_pro/left/image_raw /oak_d_pro/right/image_raw`

---

### 7.3 Play the bag and visualize in RViz

**You need two terminals**, both inside the container (two SSH sessions, then `docker exec -it equip-test-arm bash` in each). First, note your bag folder name: inside the container run `ls /rosbags` and use that folder name in Terminal 1 below.

**Terminal 1 — run these in order (play the bag):**

```bash
# On the host, get into the container:
docker exec -it equip-test-arm bash

# Inside the container (replace cam_20250101_120000 with your actual folder from ls /rosbags):
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ros2 bag play /rosbags/cam_20250101_120000
```
Leave this running while you view in RViz.

**Terminal 2 — run these in order (open RViz):**

```bash
# On the host, get into the container:
docker exec -it equip-test-arm bash

# Inside the container:
apt-get update && apt-get install -y ros-humble-rviz2
source /opt/ros/humble/setup.bash
ros2 run rviz2 rviz2
```

**In the RViz window:** Click **Add** → **By topic** → choose an image topic (e.g. `/oak_d_pro/color/image_raw`). If the image doesn’t show, set **Fixed Frame** (e.g. `oak_d_pro_link`). The view updates as the bag plays in Terminal 1.

---

### 7.3b Download the bag and view in RViz on another computer

Use this when the machine where you recorded (e.g. UCSD-Blue) doesn’t have RViz. Copy the bag to another computer that has ROS 2 and RViz, then play and visualize there.

**Step 1 – Copy the bag from the recording machine to your other computer**

The bag lives on the **host** in `~/rosbags/` (because of the `-v ~/rosbags:/rosbags` mount). Each recording is a **folder** (e.g. `cam_20260303_220000`).

On your **other computer** (e.g. your laptop), open a terminal and run:

```bash
mkdir -p ~/rosbags
scp -r ucsd-blue@UCSD-Blue:~/rosbags/cam_* ~/rosbags/
```

Use your real hostname or IP if not `UCSD-Blue`. To copy one specific folder: `scp -r ucsd-blue@UCSD-Blue:~/rosbags/cam_20260303_220000 ~/rosbags/`. The copy may take a while if the bag is large.

**Step 2 – On the other computer: install ROS 2 Humble and RViz (one-time)**

Example on Ubuntu 22.04: install [ROS 2 Humble](https://docs.ros.org/en/humble/Installation.html), then:

```bash
sudo apt update
sudo apt install -y ros-humble-rviz2 ros-humble-sensor-msgs
```

**Step 3 – Play the bag and open RViz on the other computer**

**Terminal A** (play the bag; use your actual bag folder name from `ls ~/rosbags`):

```bash
source /opt/ros/humble/setup.bash
ros2 bag play ~/rosbags/cam_20260303_220000
```

**Terminal B** (start RViz):

```bash
source /opt/ros/humble/setup.bash
ros2 run rviz2 rviz2
```

In RViz: **Add** → **By topic** → choose an image topic (e.g. `/oak_d_pro/color/image_raw`). Set **Fixed Frame** (e.g. `oak_d_pro_link`) if the image doesn’t show.

---

### 7.4 Live visualization

Exact method for **live** viewing (camera running in real time over SSH or on another machine) is TBD. Options when you decide: RViz or rqt_image_view with X11 forwarding (`ssh -X` and container started with `-e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix`), or a separate machine with ROS 2 subscribing to the same `ROS_DOMAIN_ID`.

---

## 8. Quick reference: host vs container

| Action                    | Where to run        | Example prompt              |
|---------------------------|---------------------|-----------------------------|
| Clone, build image, `docker run` | **Host**            | `ucsd-blue@UCSD-Blue:~ $`  |
| Camera check, ROS, development | **Inside container** | `root@...:/race_ws#`        |
| Docker commands (`docker build`, `docker run`) | **Host only**; not available inside the container | — |

To get from container back to host: run `exit`.

---

## 9. Summary

1. **After you SSH in:** Run `docker start equip-test-arm && docker exec -it equip-test-arm bash` (or `docker run -it ...` if the container doesn’t exist yet). You’re then inside the container at `root@...:/race_ws#`.
2. **One-time on a new host:** Clone roboracer-t7 → build image with `docker build -t equip_test:arm64 -f docker/dockerfile .`
3. **Run container with USB (first time or after remove):** `docker run -it --privileged -v /dev/bus/usb:/dev/bus/usb --name equip-test-arm equip_test:arm64 bash`
4. **Inside container:** Run `python3 /race_ws/src/scripts/check_camera.py` to verify OAK-D; then optionally start the ROS 2 camera node.
5. Use the **ARM64 image** for camera and USB; avoid relying on amd64 + QEMU for DepthAI on this host.
