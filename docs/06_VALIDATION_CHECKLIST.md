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

## Optional RViz validation

```bash
rviz2
```

Recommended displays:

- `PointCloud2` -> `/livox/lidar`
- `LaserScan` -> `/scan`
- `TF`
- `Odometry` -> `/odom`
