# Manual Drive Setup (RC)

Use this first before any autonomy test.

---

## 1) Launch manual stack

Inside container:

```bash
ros2 launch f1tenth_stack no_lidar_bringup_launch.py joy_config:=/race_ws/config/joy_rc_steer_fix.yaml
```

Expected:
- Nodes start without crash (`joy_node`, `joy_teleop`, `ackermann_mux`, `vesc_driver_node`)
- No parameter parse errors

Current validated RC config file:

- `config/joy_rc_steer_fix.yaml`
- deadman button index: `1`

---

## 2) Control behavior

- Deadman ON (`buttons[1] == 1`): manual commands enabled
- Deadman OFF (`buttons[1] == 0`): manual commands blocked/zeroed

---

## 3) Verify manual path

In another sourced shell:

```bash
ros2 topic hz /joy
ros2 topic hz /teleop
ros2 topic hz /commands/motor/speed
ros2 topic hz /commands/servo/position
```

Expected:

- moving RC sticks changes `/teleop`
- motor and servo command topics update
- rates are non-zero while control input is active

---

## 4) If wheels do not move

Check:

```bash
ros2 topic echo /sensors/core --once
```

If missing or faulted, debug VESC connection/power first.

Also check deadman state quickly:

```bash
ros2 topic echo /joy --once
```

Expected:
- button index `1` changes between `0` and `1` when the deadman switch is toggled
