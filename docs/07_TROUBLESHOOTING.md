# Troubleshooting

Quick fixes for common failures.

---

## SSH fails (`.local` unknown host)

- Use direct IP instead of `.local`
- Confirm car is on same subnet
- Scan for SSH-open hosts:

```bash
python3 - <<'PY'
import socket
for i in range(1,255):
    ip=f"192.168.11.{i}"
    s=socket.socket(); s.settimeout(0.2)
    try:
        if s.connect_ex((ip,22))==0:
            print(ip)
    finally:
        s.close()
PY
```

---

## VESC not connected

- Verify `/dev/sensors/vesc` symlink
- Verify cable/power
- Check:

```bash
ros2 topic echo /sensors/core --once
```

---

## `/teleop` not publishing

- Confirm `deadman_buttons` matches your controller (`[1]` in current config)
- Check `/joy` updates:

```bash
ros2 topic echo /joy
```

---

## `/scan` not publishing

- Verify `/livox/lidar` exists
- Verify bridge node is running
- Check:

```bash
ros2 topic hz /livox/lidar
ros2 topic hz /scan
```

---

## `/drive` not publishing

- Verify `wall_follow_node` running
- Ensure manual latch is not currently active
- Relaunch unified stack:

```bash
Ctrl+C
ros2 launch /race_ws/bringup.launch.py
```

---

## Container workflow confusion

Use helper scripts:

- `./scripts/car_run.sh`
- `./scripts/car_exec.sh`
- `./scripts/car_launch.sh`
