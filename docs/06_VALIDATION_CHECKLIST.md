# Validation Checklist

Use this checklist before declaring a test successful.

---

## Manual validation

- [ ] `ros2 topic hz /joy` is active
- [ ] `ros2 topic hz /teleop` is active when RC input is active
- [ ] `ros2 topic hz /commands/motor/speed` is active
- [ ] `ros2 topic hz /commands/servo/position` is active
- [ ] Deadman switch disables commands when OFF

---

## Sensor validation

- [ ] `ros2 topic hz /livox/lidar` is active
- [ ] `ros2 topic hz /scan` is active
- [ ] `ros2 topic echo /scan --once` returns valid ranges
- [ ] `ros2 topic echo /sensors/core --once` returns healthy VESC state

---

## Autonomy validation

- [ ] `ros2 topic hz /drive` is active
- [ ] car moves at low speed in hallway
- [ ] manual override works immediately
- [ ] no collisions

---

## Optional rosbag recording (bringup)

`bringup.launch.py` can start **`ros2 bag record`** when enabled, and includes **`ros2_system_monitor`** so **`/diagnostics`** is available for post-run analysis (see commit `a088558` pattern).

Enable when launching:

```bash
ros2 launch /race_ws/bringup.launch.py record_bag:=true bag_name:=my_run
```

Defaults: `record_bag:=false`, `bag_dir:=/race_ws/bags`, `bag_name:=race_bag`. Bags are written under `bag_dir` (ensure the directory exists or use a mounted volume).

Recorded topics include `/drive`, `/scan`, `/livox/lidar`, `/teleop`, `/tf`, `/tf_static`, `/odom`, `/joy`, `/diagnostics` (edit `bag_topics` in `bringup.launch.py` to change).

---

## Optional RViz validation

```bash
rviz2
```

Recommended displays:

- `PointCloud2` -> `/livox/lidar`
- `LaserScan` -> `/scan`
- `TF`
- `Odometry` -> `/odom`
