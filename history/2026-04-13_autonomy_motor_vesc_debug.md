# Session summary: autonomy steers but does not roll (motor / VESC path)

**Date:** 2026-04-13  
**Vehicle:** UCSD-Blue (Docker `/race_ws`, `ros2 launch /race_ws/bringup.launch.py`)  
**Purpose:** Handoff for another developer/AI — what we did, what changed in-repo, what we measured, what to do next.

**Deployment note:** As of this write-up, the team had **not** run a fresh **`docker build` → `docker push` → `docker pull`** cycle to ship these repo changes into the race image. Until that happens, the car may still be running an older container unless configs are copied in manually.

---

## 1. Symptom

- With **`bringup.launch.py`** running: **front wheels steer** (left/right) when obstacles affect LiDAR or when covering one side of the sensor — **steering path works**.
- **Drive wheels do not roll** (car stays put on the ground / on a box); only steering reacts.
- **`/teleop`** often quiet with **deadman off** (expected for autonomy-only testing).

---

## 2. Root causes we identified (software + interpretation)

### 2a. Mux could starve navigation (fixed in repo)

- **`ackermann_mux`:** joystick **`/teleop`** has **higher priority** than navigation **`/drive`**.
- If `/teleop` keeps publishing with **speed ≈ 0** but **non-zero steering**, the mux can keep **motor at 0** while still moving the **servo** — looks like “steers but won’t roll.”
- **Config bug:** `wall_follow_node` publishes **`/drive`**, but **`config/ackermann_mux_topics.yaml`** previously pointed navigation at **`/ackermann_mux/input/nav_0`** instead of **`/drive`**, so autonomy might never reach the mux when that YAML is loaded.

**Change:** Navigation topic set to **`/drive`** to match `wall_follow_node` and docs.

### 2b. Autonomy speed tuned for slow indoor hallway (in repo)

- **`bringup.launch.py`** — `wall_follow_node` params (intent): **`target_speed_mps` ~0.1**, **`max_speed_mps` ~0.12** for safe corridor driving.
- **`clamped_speed` / `clamped_steering`** in `wall_follow_node.py`: standard clamps to `[min_speed_mps, max_speed_mps]` and ±`max_steering_angle_rad`; not the primary failure mode once `/drive` shows non-zero speed.

### 2c. Main drivetrain finding: **sign / ERPM vs VESC behavior** (not “wall_follow is off”)

Measured on the car (representative):

| Condition | `/commands/motor/speed` (ERPM-scale) | `/sensors/core` |
|-----------|----------------------------------------|-----------------|
| Autonomy / small forward command | **+461 … +554** (positive) | **`duty_cycle` ~ 0**, **`current_motor` ~ 0**, motor not really driven |
| Manual (stick producing motion) | **~-2307** (negative, larger magnitude) | **Non-zero duty**, **~3–5 A**, **non-zero shaft speed** |

**Interpretation:**

- **Steering** uses **`/commands/servo/position`** — works independently.
- **Drive** uses **`/commands/motor/speed`** → VESC. ROS **does** publish a motor setpoint, but for **small positive** ERPM the VESC often reported **~0 duty**; **negative, larger** ERPM **did** produce torque in the manual test.
- **RC throttle was inverted** (stick forward rolled backward): fixed by **negating** throttle scale in **`config/joy_rc_steer_fix.yaml`** (`drive-speed` **`scale: -0.50`** was applied; was `0.50`).
- **Autonomy does not read the joy YAML.** It always commands **positive** `AckermannDrive.speed` for “forward” in software. If the **physical** “forward” direction that the VESC actually drives corresponds to **negative** ERPM in this setup, autonomy will still not roll until **one global invert** is applied (e.g. **`ackermann_to_vesc`** / **VESC “invert motor direction”** / equivalent in `f1tenth_stack`), so **positive** software forward matches **correct** wheel motion — same as corrected RC.

So: **flipped RC did not “break” autonomy by config coupling**, but it **explained** why manual “worked” when pulling the stick the wrong way (negative speed) while autonomy kept asking **positive** forward.

---

## 3. Files changed in this repo (check git for exact diff)

| File | Change |
|------|--------|
| `config/ackermann_mux_topics.yaml` | Navigation input **`/drive`** (was wrong topic). |
| `bringup.launch.py` | Slow indoor `wall_follow_node` speeds; optional bag topics include VESC debug (`/commands/motor/speed`, `/sensors/core`, etc.). |
| `config/joy_rc_steer_fix.yaml` | **`drive-speed` `scale: -0.50`** — invert RC forward/back vs drivetrain. |
| `docs/07_TROUBLESHOOTING.md` | §4b-style notes on “steers but does not roll” / mux / teleop (if present in branch). |

**Packages not in this repo but on the car:** `f1tenth_stack` (e.g. **`ackermann_to_vesc`**, **`vesc_driver`** params). Motor invert / wheel diameter / gear ratio are often there or in VESC firmware.

---

## 4. Commands & procedures we used

**Shell / ROS2 CLI:**

- Stuck **`ros2 topic list`** / daemon: `export ROS_DISABLE_ROS2_DAEMON=1` or `ros2 daemon stop && ros2 daemon start`.
- **`/commands/motor/brake`**, **`/commands/motor/duty_cycle`**: `ros2 topic echo` **hangs** if **no publisher** — use `ros2 topic info -v <topic>` first.

**Sanity chain (autonomy, deadman off):**

```bash
ros2 topic hz /scan
ros2 topic echo /drive --once
ros2 topic echo /ackermann_cmd --once
ros2 topic echo /commands/motor/speed --once
ros2 topic echo /commands/servo/position --once
ros2 topic echo /sensors/core --once
```

**Tune speed live:**

```bash
ros2 param set /wall_follow_node target_speed_mps 0.5
ros2 param set /wall_follow_node max_speed_mps 0.65
```

After changing params, wait for **`/scan`** callbacks if `/drive` does not update immediately.

**Record a bag (no image rebuild required):**

```bash
ros2 bag record -o /race_ws/bags/vesc_debug_<name> \
  /drive /ackermann_cmd /commands/motor/speed /commands/servo/position /sensors/core /scan
```

---

## 5. What is **not** solved only in this repo

- **VESC Tool** (USB to ESC): motor detection, current limits, min ERPM / duty, APP mode vs UART speed command — required if duty stays ~0 despite large commands.
- **Bench supply vs battery:** weak adapter may current-limit; real pack retest helps.
- **Single motor-direction invert** so **positive** `AckermannDrive.speed` = physical forward for **both** teleop and autonomy (after RC sign fix).

---

## 6. Next steps (recommended order)

1. **Redeploy:** Run **`docker build`** → **`docker push`** → **`docker pull`** on the robot so the image includes **`ackermann_mux`**, **`bringup.launch.py`**, and **`joy_rc_steer_fix.yaml`** changes.
2. **Restart bringup**; verify RC forward matches track direction after **`scale: -0.50`**.
3. **Autonomy test (deadman off):** echo `/drive`, `/ackermann_cmd`, `/commands/motor/speed`, `/sensors/core`. If **positive** ERPM still gives **duty ~0** but **negative** manual ERPM works → apply **one** motor invert at **`ackermann_to_vesc` or VESC**, then retest.
4. **VESC Tool** if duty remains zero at large commanded ERPM.
5. **Optional:** `ros2 bag record` during a short autonomy + manual segment for offline plots.

---

## 7. One-line takeaway

**Steering worked because the servo path was fine; drive failed because the VESC did not apply power for the small positive ERPM autonomy produced, while manual often commanded negative ERPM that did move the motor — fix RC invert for human driving, then align software “forward” sign globally (invert) so autonomy matches the drivetrain.**
