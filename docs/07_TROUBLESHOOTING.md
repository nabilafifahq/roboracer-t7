# Troubleshooting

This page lists real issues seen on this project and the exact recovery steps.

---

## 1) SSH fails (`.local` unknown host)

Symptoms:
- `ping ucsd-blue.local` -> unknown host
- `ssh ucsd-blue@ucsd-blue.local` fails immediately

Fix:
1. Confirm laptop is on Wi-Fi `ucsd_robocar`.
2. Confirm target vehicle is the **1tenth blue car**.
3. Try direct IP:

```bash
ssh ucsd-blue@<car_ip>
```

4. If IP is unknown, scan port 22:

```bash
python3 - <<'PY'
import socket
for i in range(1, 255):
    ip = f"192.168.11.{i}"
    s = socket.socket()
    s.settimeout(0.2)
    try:
        if s.connect_ex((ip, 22)) == 0:
            print(ip)
    finally:
        s.close()
PY
```

---

## 2) SSH times out or connection refused

Symptoms:
- `Operation timed out`
- `Connection refused`

Likely causes:
- Pi did not boot correctly (power path issue)
- SSH service not reachable yet

Fix:
1. Verify car power path first (this was a real blocker before).
2. Power cycle car, wait 20-60 seconds.
3. Retry SSH by IP.

---

## 3) `joy_node` / `joy_teleop` crash with params parse error

Symptom:
- `RCLInvalidROSArgsError` with `joy_teleop.yaml`

Cause:
- Wrong/invalid joy config file passed by default launch.

Fix:
- Always launch with:

```bash
ros2 launch f1tenth_stack no_lidar_bringup_launch.py joy_config:=/race_ws/config/joy_rc_steer_fix.yaml
```

Verify:

```bash
ros2 topic hz /joy
ros2 topic hz /teleop
```

---

## 4) `/teleop` appears frozen or wheels do not move

Symptoms:
- `/joy` updates but `/teleop` stays zero
- Car does not move

Checks:
1. Deadman switch mapping is correct (`deadman_buttons: [1]`).
2. SD/LB switch is in ON state when testing.
3. VESC is connected and powered.

Verify:

```bash
ros2 topic echo /joy --once
ros2 topic hz /teleop
ros2 topic hz /commands/motor/speed
ros2 topic hz /commands/servo/position
```

---

## 4b) Front wheels steer (react to obstacles) but car does not roll — motor speed ~0

**Typical cause: `ackermann_mux` priority.** `joy_teleop` on **`/teleop`** has **higher priority** than autonomy on **`/drive`**. If `/teleop` is still publishing messages with **`speed ≈ 0`** but **non-zero `steering_angle`** (e.g. RC sticks moved, noisy axes, or autorepeat), the mux **keeps using `/teleop`** and **never applies `/drive`’s forward speed** — you see **steering only**, no drive.

**Checks:**

```bash
ros2 topic echo /teleop --once
ros2 topic echo /drive --once
ros2 topic echo /ackermann_cmd --once
```

- If **`/ackermann_cmd.drive.speed`** tracks **`/teleop`** (near zero) while **`/drive.speed`** is non-zero, mux is choosing teleop.

**Mitigations:**

1. For **autonomy-only** tests: do not touch the speed/steer sticks; ensure **deadman** behavior matches `joy_teleop` so `/teleop` is not continuously “winning” with zero speed.
2. Confirm **`config/ackermann_mux_topics.yaml`** lists navigation on **`/drive`** (same topic `wall_follow_node` publishes to).

**Also verify** `wall_follow` is not latched (`manual_latched` / LiDAR fault) and VESC is not in a mode that blocks motor with non-zero servo.

---

## 5) Bringup fails: Livox launch file not found

Symptom:
- `No such file or directory ... livox_ros_driver2 ... msg_MID360_launch.py`

Fix:
- Ensure `bringup.launch.py` uses Livox `launch_ROS2` path.

---

## 6) `/scan` not received due QoS mismatch

Symptom:
- warning about incompatible QoS (`RELIABILITY`)
- `/scan` has no usable stream in autonomy node

Fix:
- Keep `/scan` subscriber on `BEST_EFFORT` + `VOLATILE` in `wall_follow_node`.

Verify bridge path clearly:

```bash
ros2 node list
ros2 node info /pointcloud_to_laserscan
ros2 topic hz /livox/lidar
ros2 topic hz /scan
```

Expected:
- node `/pointcloud_to_laserscan` exists
- `/livox/lidar` and `/scan` both publish

---

## 7) `/drive` not publishing after startup

Symptoms:
- No autonomy command stream
- Node logs show autonomy latched off

Causes:
- manual override latch triggered
- LiDAR fault latch triggered (invalid for timeout)

Fix:
1. Stop launch (`Ctrl+C`).
2. Relaunch:

```bash
ros2 launch /race_ws/bringup.launch.py
```

3. Do not toggle deadman if you want autonomy to continue.

---

## 8) VESC not connected

Symptoms:
- `Failed to connect to the VESC`
- no motor response

Fix:

```bash
mkdir -p /dev/sensors
if [ -e /dev/ttyACM1 ]; then
  ln -sf /dev/ttyACM1 /dev/sensors/vesc
else
  ln -sf /dev/ttyACM0 /dev/sensors/vesc
fi
ls -l /dev/sensors/vesc
```

Verify:

```bash
ros2 topic echo /sensors/core --once
```

---

## 9) Livox network settings need change (no driver fork wanted)

Goal:
- Update MID360 host/LiDAR IP/ports without editing `racer.repos` or forking driver.

Fix:
1. Prepare local JSON file with your network values.
2. Start container with runtime override:

```bash
LIVOX_MID360_CONFIG_PATH=~/MID360_config.local.json ./scripts/car_run.sh
```

This mounts your file to:
- `/race_ws/src/drivers/livox_ros_driver2/config/MID360_config.json`

Keep `pcl_data_type` set to `0` in that JSON if you want `sensor_msgs/msg/PointCloud2` on `/livox/lidar` (same as the baked image default).

---

## 10) Livox MID360: PointCloud2, TF, and rosbag (`/livox/lidar`)

**What the stack expects**

1. **`xfer_format = 0`** in `msg_MID360_launch.py` so `/livox/lidar` is **`sensor_msgs/msg/PointCloud2`**, not Livox custom. Upstream often ships `xfer_format = 1` (custom), which breaks `ros2 bag record` (multiple types) and is harder for `pointcloud_to_laserscan`.

2. **`pcl_data_type = 0`** per lidar in `MID360_config.json` (`lidar_configs[]`). If this stays `1`, the driver can still behave like custom cloud even when ROS params say PointCloud2.

3. **`frame_id` = `laser`** in `msg_MID360_launch.py` (not `livox_frame`). `no_lidar_bringup` already publishes **`base_link` → `laser`**. The bridge uses `target_frame: base_link` in `pointcloud_to_laserscan_indoor.yaml`, so the cloud must be in a frame that connects to `base_link`. Using **`laser`** avoids an extra static TF.

**Permanent behavior (current Docker build)**

`docker/dockerfile` patches the vendored `livox_ros_driver2` **before** `colcon build`: JSON `pcl_data_type`, launch `xfer_format` and `frame_id`. Rebuild/push the image to get this on a fresh container.

**Unified launch**

```bash
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
ros2 launch /race_ws/bringup.launch.py
```

**Temporary patch inside an old container** (paths resolve via `get_package_share_directory`)

```bash
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash

PREFIX="$(python3 -c "from ament_index_python.packages import get_package_share_directory; import os; print(get_package_share_directory('livox_ros_driver2'))")"
MID360_JSON="${PREFIX}/config/MID360_config.json"
LIVOX_LAUNCH="${PREFIX}/launch_ROS2/msg_MID360_launch.py"

cp -a "${MID360_JSON}" "${MID360_JSON}.bak.manual"
python3 << PY
import json
from pathlib import Path
p = Path("${MID360_JSON}")
data = json.loads(p.read_text())
for cfg in data.get("lidar_configs", []):
    cfg["pcl_data_type"] = 0
p.write_text(json.dumps(data, indent=2) + "\n")
PY

cp -a "${LIVOX_LAUNCH}" "${LIVOX_LAUNCH}.bak.manual"
sed -i -E 's/^([[:space:]]*xfer_format[[:space:]]*=[[:space:]]*)[01]/\10/' "${LIVOX_LAUNCH}"
sed -i -E "s/(frame_id[[:space:]]*=[[:space:]]*)'livox_frame'/\1'laser'/" "${LIVOX_LAUNCH}"
grep -E 'xfer_format|frame_id' "${LIVOX_LAUNCH}" | head
```

Verify:

```bash
ros2 topic info /livox/lidar -v
ros2 topic echo /livox/lidar --once | head -15
```

---

## 11) Container shell confusion (`docker` vs `ros2`)

Host shell prompt example:
- `ucsd-blue@UCSD-Blue:~ $`

Container shell prompt example:
- `root@UCSD-Blue:/race_ws#`

Rules:
- Run `docker ...` on host shell.
- Run `ros2 ...` in container shell.
- If opening a manual new shell, source ROS again:

```bash
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
```
