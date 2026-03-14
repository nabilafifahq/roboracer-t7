# Autonomy Setup and Run

This is the baseline indoor autonomy flow.

---

## 1) Start unified stack

Inside container:

```bash
ros2 launch bringup.launch.py
```

This launch includes:

- base manual stack (`f1tenth_stack`)
- Livox driver
- pointcloud-to-laserscan bridge
- wall-follow autonomy node

---

## 2) Verify autonomy topics

In another sourced shell:

```bash
ros2 topic hz /livox/lidar
ros2 topic hz /scan
ros2 topic hz /drive
ros2 topic echo /drive --once
```

Expected:

- `/livox/lidar` active
- `/scan` active
- `/drive` active (autonomy command stream)

---

## 3) Current autonomy behavior

- target speed: `0.25 m/s`
- clamp: min `0.0`, max `0.35`
- manual override latch uses RC button index `1`
- LiDAR invalid data timeout latch: `2.0s`

---

## 4) Safe floor test sequence

1. Test on stand first
2. Confirm `/drive` updates
3. Place on floor, clear hallway
4. Keep manual switch ready at all times
5. Stop immediately if unstable

---

## 5) Relaunch rule

If manual latch or LiDAR latch triggers stop, relaunch:

```bash
Ctrl+C
ros2 launch /race_ws/bringup.launch.py
```
