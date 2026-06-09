# Manual Drive Setup (RC)

Use this to confirm the RC controller works **before** mapping or autonomy.

**Run on:** Container (`root@UCSD-Blue:/race_ws#`).
---

## Terminals for this test

| Tab | Where | Job |
|-----|-------|-----|
| **Tab 1** | Container | Launch manual stack |
| **Tab 2** | Container (`car_exec.sh`) | Verify topics while you move sticks |

---

## 1) Tab 1 — Launch manual stack

Inside container:

```bash
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
ros2 launch f1tenth_stack no_lidar_bringup_launch.py joy_config:=/race_ws/config/joy_rc_steer_fix.yaml
```

**Expected:**
- Nodes start without crash (`joy_node`, `joy_teleop`, `ackermann_mux`, `vesc_driver_node`)
- No YAML parse errors

RC config: `config/joy_rc_steer_fix.yaml` — deadman button index `1`.

---

## 2) Deadman behavior

| Deadman (button 1) | Effect |
|--------------------|--------|
| **Pressed / ON** | Manual drive commands go to motors |
| **Released / OFF** | Manual commands blocked — car should not move |

---

## 3) Tab 2 — Verify manual path

Open **Tab 2** (Pi host → `./scripts/car_exec.sh` → container):

```bash
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
ros2 topic hz /joy
ros2 topic hz /teleop
```

Move RC sticks (with deadman held). **Expected:** rates become non-zero while you move controls.

---

## 4) If wheels do not move

```bash
ros2 topic echo /sensors/core --once
ros2 topic echo /joy --once
```

Check VESC power/connection and deadman state (button index `1` toggles 0/1).

---

## 5) Next step

Manual RC works → proceed to [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md).

That guide uses the **full stack** launch (`bringup.launch.py` with Cartographer + LiDAR), not the minimal launch above.
