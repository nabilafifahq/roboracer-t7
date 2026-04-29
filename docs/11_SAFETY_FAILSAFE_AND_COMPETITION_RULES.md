# Safety Fail-Safe Tests and Competition Rules Impact

This document defines:

- safety test cases for emergency stop behavior
- what currently works vs what must be added
- competition-rule impacts on code and setup

Use this during pre-competition validation.

---

## 1) Safety behavior target

Target behavior for this car:

1. If Operator triggers kill-switch, car stops immediately.
2. If RC link is lost or controller powers off, car stops.
3. If launch process dies, car stops.
4. If onboard computer dies/reboots, car stops.
5. If LiDAR data is invalid for too long, car stops and stays stopped until relaunch.
6. Car must not resume motion by itself after a fault.

---

## 2) Current status (as of now)

### Already implemented

- Manual stop via RC deadman/kill input.
- LiDAR invalid timeout latch in `wall_follow_node` (`lidar_drop_timeout_s`).
- Manual latch behavior in `wall_follow_node` (requires relaunch to return to autonomy).
- `ackermann_mux` topic timeout behavior (manual input timeout configured).

### Not guaranteed yet (must verify/fix)

- RC powered OFF or out-of-range always causing full stop while autonomy is running.
- Launch process crash always forcing motor command to zero.
- Host reboot/power loss always resulting in motor-safe state immediately.

---

## 3) Test cases (step-by-step)

Run all tests in open safe area, wheels lifted first, then floor test.

For each case:

- **Pass**: car reaches full stop and stays stopped until intended restart.
- **Fail**: any continued motion or delayed stop beyond safe margin.

---

### TC-01: Operator kill-switch while driving

Goal: verify immediate remote stop.

Steps:

1. Open `docs/05_AUTONOMY_SETUP_AND_RUN.md`.
2. Launch autonomy stack:
  - `ros2 launch /race_ws/bringup.launch.py`
3. Confirm motion command exists:
  - `ros2 topic hz /drive`
4. While car is moving, trigger RC kill/deadman OFF.

Expected:

- Car speed drops to zero immediately.
- No continued motion.

If fail:

- Check `config/joy_rc_steer_fix.yaml` deadman mapping.
- Check `config/ackermann_mux_topics.yaml` priorities/timeouts.

---

### TC-02: RC controller powered OFF

Goal: verify stop when controller battery dies or power is switched off.

Steps:

1. Start unified stack and begin low-speed motion.
2. Power OFF RC controller completely.
3. Observe car response for 3 seconds.

Expected:

- Car stops and stays stopped.

Current risk:

- If autonomy `/drive` is still active, `ackermann_mux` may continue accepting nav commands.

Solution to implement if fail:

1. Add a dedicated watchdog node:
  - subscribe `/joy`
  - if no joy messages for timeout (example 0.3-0.5 s), publish zero command to highest-priority safety input
2. Add `safety_stop` input to `ackermann_mux` with highest priority.
3. Require heartbeat from RC link for autonomy-enable state.

---

### TC-03: RC out of range / packet loss

Goal: verify same behavior as powered-OFF controller.

Steps:

1. Begin slow motion.
2. Move controller out of range or shield antenna.
3. Observe stop behavior.

Expected:

- Car stops and does not continue under autonomy without operator-ready state.

Fix if fail:

- Same as TC-02 watchdog + highest-priority safety channel.

---

### TC-04: ROS launch terminated (`Ctrl+C`)

Goal: verify car stops when launch file exits.

Steps:

1. Start `ros2 launch /race_ws/bringup.launch.py`.
2. Confirm command topics active.
3. Press `Ctrl+C` in launch terminal.

Expected:

- Motor command stream ends.
- Car stops quickly.

Fix if fail:

- Add explicit zero-command-on-shutdown node/hook.
- Ensure VESC command timeout is enabled and short enough.

---

### TC-05: Process crash (`wall_follow_node` crash)

Goal: verify no runaway when planner crashes.

Steps:

1. Keep stack running.
2. Kill planner process:
  - `pkill -f wall_follow_node`
3. Observe vehicle.

Expected:

- No unsafe acceleration.
- Car should stop unless manual operator is actively commanding.

Fix if fail:

- Add safety supervisor that forces zero when autonomy publisher disappears.

---

### TC-06: Computer reboot or power loss

Goal: verify drivetrain fails safe when onboard compute goes down.

Steps:

1. Run low-speed motion.
2. Reboot host or disconnect compute power (test stand first).
3. Observe wheel behavior.

Expected:

- Motor output drops to zero.
- No sustained drive command.

Fix if fail:

- Configure VESC-side command timeout / neutral-on-lost-command behavior.
- Validate hardware E-stop path independent of ROS.

---

### TC-07: LiDAR data drop

Goal: verify existing LiDAR timeout latch.

Steps:

1. Start autonomy and confirm `/scan` active.
2. Disconnect LiDAR data path (or stop driver).
3. Wait longer than `lidar_drop_timeout_s`.

Expected:

- `wall_follow_node` latches fault and commands stop.
- Relaunch required to return to autonomy.

---

## 4) Required implementation items before competition

1. Add **RC heartbeat watchdog** (no `/joy` -> forced stop).
2. Add **highest-priority safety-stop input** in `ackermann_mux`.
3. Add **zero-on-shutdown** behavior for launch/process exits.
4. Confirm **VESC command timeout** for compute failure.
5. Re-test TC-01..TC-07 and record pass/fail with date and commit hash.

---

## 5) Competition rules impact on this project (2026 draft)

These are the main rules that directly affect code/setup.  
Quoted text below is copied verbatim from **RoboRacer Rules**, version **3.2026-draft** (27th International RoboRacer Autonomous Racing Competition general rules). Competition-specific addenda may override these; always use the version linked on the official competition site.

### A) Kill-switch is mandatory

**Original rule text (2026 draft):**

> **Kill-switch:** A method to remotely and immediately stop the car.

> **Remote controller:** It must have a kill-switch ability so the Operator is able to stop the car immediately and remotely.

> **Race violations:** Triggering the emergency stop must stop the car completely.

> **Race violations:** During the race, the teams MUST NOT control the car manually. Manual control is allowed only after a crash, as specified in Race penalties.

> **Race:** During the race, the Operator MUST maintain Operator stance to be clear that the car is not manually controlled. Lowering the remote and raising the other hand is a signal that the emergency stop was triggered.

Rule impact:

- Operator must remotely and immediately stop the car.
- During race, manual driving is prohibited except allowed crash-handling cases.

Code/setup action:

- Keep kill-switch path independent and always available.
- Document operator stance and emergency-stop procedure in pit checklist.

### B) Onboard compute only

**Original rule text (2026 draft):**

> **Compute:** No limits, but all computation during the race MUST be done onboard the vehicle.

Rule impact:

- All race-time computation must run onboard the vehicle.

Code/setup action:

- Do not depend on laptop-side runtime nodes.
- SSH laptop is for monitoring only.

### C) Safety and crash handling

**Original rule text (2026 draft):**

> Upon crashing into an obstacle/track border, the team has to: Stop its car. Move the car (by hand or using the remote control) to the side of the track next to the latest position before the crash. Repair the track and/or place the obstacles to their appropriate positions. Wait for the clearance from the organizers (using, e.g., a green flag). Start the car and continue the race.

> The race is stopped (paused) by, e.g.: Raising a red flag. Raising a black flag. Using a whistle.

> **Race violations:** Switching to an autonomous mode MUST be done only after a clearance from the organizers (using, e.g., a green flag).

Rule impact:

- After crashes, teams must stop, reposition, and resume only after organizer clearance.

Code/setup action:

- Add clear operator runbook for stop/restart sequence.
- Keep relaunch steps short and tested.

### D) Speed-restricted sections / flags

**Original rule text (2026 draft):**

> **Yellow flag:** A flag is raised to indicate that the teams have to drive slowly, because of, e.g., a hazard on the track. Yellow flags MAY also be placed on the track to define a slow-speed section.

> **Speed-restricted sections:** Track contains sections with defined speed limits. Driving over the speed limit is not allowed. Upon exceeding the speed limit, the team has to stop the car and move it before the speed-restricted section.

Rule impact:

- Yellow flag or speed-limited sections require reduced speed.

Code/setup action:

- Keep a quick runtime speed override command ready:
  - `ros2 param set /wall_follow_node target_speed_mps <value>`
- Predefine low-speed profile (example 0.15-0.20 m/s).

### E) Vehicle detectability box (12x12 cm, 10-30 cm height band)

**Original rule text (2026 draft):**

> At all times, the car MUST occupy a square-shaped space of size at least 12×12 cm at every horizontal plane between 10 and 30 cm above the ground. Usually, this is achieved by placing a 12x12x20cm box on top of the car at its back. The box MUST be made of LiDAR perceivable material (e.g., cardboard). As long as the object results in the desired LiDAR signature, the object can have any additional aerodynamic shapes added, like fins, wings, etc. The box MAY have any color as long as it is easily perceivable by the LiDARs of the other cars.

> You MUST NOT hinder the opponents from detecting your car, e.g., using materials/colors to adjust the car reflectivity.

Rule impact:

- Car must remain LiDAR-detectable by opponents.

Code/setup action:

- Hardware checklist must include compliant rear box and mounting.

### F) LiDAR and environment limitations

**Original rule text (2026 draft):**

> When the room is surrounded by windows or semi-transparent surfaces, it might result in incorrect sensor measurements.

> When the track is delimited by a set of pipes (on top of each other), there might be gaps between them.

> Due to the car tilting, the sensors might see over the track borders or see the floor.

> **Open walls:** Track borders are not closed, i.e., there are horizontal gaps in them. Gaps might be in the inner walls as well as in the outside walls.

Rule impact:

- Track gaps, reflective surfaces, and border visibility issues are expected.

Code/setup action:

- Keep `pointcloud_to_laserscan` filtering tuned for venue.
- Validate LiDAR network config (`MID360_config.json`) before each session.

---

## 6) Session-day operator checklist

Before each run:

1. Connect to `ucsd_robocar`.
2. Confirm correct car (1tenth blue car).
3. RC ON first, then car power ON.
4. Verify kill-switch works on stand.
5. Verify `/joy`, `/scan`, `/drive`.
6. Run at low speed first lap.

If anything abnormal happens:

1. Trigger kill-switch.
2. Confirm full stop.
3. Move car only when safe/allowed.
4. Relaunch only after issue is understood.

---

## 7) What we need to do today (race-readiness plan)

This is the practical checklist for today.

### Step 1 - Prepare car and environment

1. Connect laptop to `ucsd_robocar`.
2. Confirm target car is **1tenth blue car**.
3. RC ON first, car power ON second.
4. SSH to car:
  - `ssh ucsd-blue@ucsd-blue.local`
5. Start container:
  - `./scripts/car_run.sh`
6. In another shell:
  - `./scripts/car_exec.sh`
7. Confirm ROS env:
  - `printenv | grep -E '^ROS_DISTRO='`

Pass criteria:

- You are in `root@...:/race_ws#`
- `ROS_DISTRO=humble` is shown.

---

### Step 2 - Bring up stack and baseline checks

1. Launch stack:
  - `ros2 launch /race_ws/bringup.launch.py`
2. In another sourced shell, run:
  - `ros2 node list`
  - `ros2 topic hz /joy`
  - `ros2 topic hz /livox/lidar`
  - `ros2 topic hz /scan`
  - `ros2 topic hz /drive`

Pass criteria:

- `/pointcloud_to_laserscan` node exists.
- `/joy`, `/livox/lidar`, `/scan`, `/drive` all have non-zero rates.

---

### Step 3 - Run safety test cases in order

Run these in order: `TC-01` -> `TC-07`.

For each test:

1. Trigger event.
2. Observe stop response.
3. Mark result: PASS or FAIL.
4. Record notes with timestamp.

Minimum required pass today:

- TC-01 (kill-switch press): PASS
- TC-04 (launch stopped): PASS
- TC-07 (LiDAR drop latch): PASS

Strongly recommended:

- TC-02 and TC-03 must pass before race day.

---

### Step 4 - Implement missing safety items (if any FAIL)

If TC-02 or TC-03 fails, implement immediately:

1. Add RC heartbeat watchdog node:
  - subscribe `/joy`
  - if timeout, publish stop signal
2. Add highest-priority `safety_stop` input in `ackermann_mux`.
3. Re-test TC-02 and TC-03.

If TC-04/TC-05/TC-06 fails:

1. Add zero-command-on-shutdown behavior.
2. Verify VESC command timeout configuration.
3. Re-test failed case.

Pass criteria:

- No fail-safe test remains in FAIL state.

---

### Step 5 - Competition-rules compliance checks

Before ending today:

1. Verify Operator kill-switch procedure is clear to all team members.
2. Verify no manual drive is required during autonomous race flow.
3. Verify onboard-only operation (no required offboard compute).
4. Verify LiDAR-detectable rear box requirement is satisfied physically.
5. Verify low-speed override method is ready:
  - `ros2 param set /wall_follow_node target_speed_mps <value>`

Pass criteria:

- Team can explain and execute stop/restart and rule-compliant behavior without guessing.

---

### Step 6 - Sign-off record for today

Create a short log entry in your team notes:

- Date/time
- Git commit hash tested
- Docker image tag tested
- TC-01..TC-07 results
- Open issues (if any) and owner
- Next test session date

Definition of done for today:

- Safety tests required above are passing.
- Rule-impact checks completed.
- Open issues are assigned with owner and deadline.

