# Handoff Status

**Last updated:** June 2026  
**Branch with clean docs:** `docs/clean-handoff`  
**Docker image:** `nabilafifahq/roboracer-t7:cartographer-ekf`

Read this first, then [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md) (includes a **photo of the current track** — layout can change) and [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md).

---

## Summary

We can **record several short drives on the car**, **build a clean readable map and racing line on a laptop** (TUM optimizer), and produce a **final track figure** with measured walls and an optimal path. We have **not yet successfully run that raceline on the car in pursuit mode** — that is the next main task for the next team.

---

## What works today

| Capability | Status | Evidence |
|------------|--------|----------|
| RC manual driving + deadman | Working | Doc 04 validation |
| LiDAR → `/scan` + EKF odometry | Working | Health checks in mapping guide |
| Record rosbag on car (2–3 laps) | Working | `testrun/june7_set7/lap3x/` |
| Offline map de-drift (laptop) | Working | `scripts/cartographer_offline_dedrift.sh` |
| Raceline + track figure (laptop) | Working | `testrun/june7_set7/FINAL_berlin_dedrift.png` |
| Output pipeline | Working | `scripts/build_raceline_from_bag.py` → `FINAL_track_map.png` |
| Wall-follow baseline autonomy | Working (slow) | Doc 05 |

---

## What does NOT work yet (your starting point)

| Capability | Status | What to do |
|------------|--------|------------|
| **On-car raceline pursuit** | **Not implemented / not validated** | **Primary task** — see [§ Your first milestone](#your-first-milestone) |
| Saved-map localization (drive without re-mapping) | Config exists, untested on car | `config/cartographer/roboracer_2d_localization.lua` + `.pbstream` |
| Nav2 full-stack follow | Partially wired, not team-validated | `AUTONOMY_MODES.md`, `roboracer_nav2_vector_pursuit/` |
| RC-loss watchdog | Not implemented | Doc 11 TC-02/03 |
| Steering pull-right trim | Mechanical — hurts map quality | Bench calibration |

---

## Pipeline that produces the map (reproduce this first)

```
Car: 2–3 laps + rosbag          →  Laptop: offline de-drift 
                                 →  Laptop: build_raceline_from_bag.py (visualization only)
                                 →  Output: FINAL_track_map.png + traj_race_cl.csv
```

**Do not** rely on long live mapping sessions on the Pi (5+ laps) — maps smear and drift. Always use the **offline de-drift** step on the laptop.

Full steps: [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md) Parts A and B.

**Compare your result to:** `testrun/june7_set6/set6_FINAL_berlin.png`

---

## Pursuit quick start (skip re-mapping)

Use the reference raceline from June 7. **Start with pure pursuit only** — `raceline_path` publishes a visualization topic but **does not move the car**.

### Terminals

| Tab | Prompt | Job |
|-----|--------|-----|
| **Tab 1** | `root@...:/race_ws#` | Launch stack (`autonomy:=none`) — keep open |
| **Tab 2** | `ucsd-blue@...:~$` | `docker cp` CSV + setup scripts (once) |
| **Tab 3** | `root@...:/race_ws#` | Run pure pursuit node |

### Commands (in order)

**Laptop** — copy reference CSV to car:

```bash
scp testrun/june7_set7/traj_race_cl.csv ucsd-blue@ucsd-blue.local:~/traj_race_cl.csv
```

**Tab 1 (Pi host → container)** — start container first:

```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh
mkdir -p /race_ws/racelines
```

**Expected:** Prompt `root@UCSD-Blue:/race_ws#`. Leave this tab open.

**Tab 2 (Pi host)** — copy into running container (container must be up from Tab 1):

```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7
docker cp scripts/car_map_setup.sh roboracer_t7:/race_ws/scripts/
docker cp config/cartographer/roboracer_2d.lua roboracer_t7:/race_ws/config/cartographer/
docker cp ~/traj_race_cl.csv roboracer_t7:/race_ws/racelines/traj_race_cl.csv
```

**Tab 1 (container)** — setup + launch (same tab as above):

```bash
source /race_ws/scripts/car_map_setup.sh
ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=true
```

**Tab 3 (container)** — via `./scripts/car_exec.sh` from Pi host:

```bash
ros2 run reactive_control raceline_pure_pursuit_node --ros-args \
  -p trajectory_csv:=/race_ws/racelines/traj_race_cl.csv \
  -p world_frame:=map \
  -p target_speed_mps:=0.08 \
  -p lookahead_m:=0.45 \
  -p wheelbase_m:=0.33
```

### Deadman rule (pursuit)

| Action | Effect |
|--------|--------|
| **Squeeze / hold deadman** | RC override — **car stops** (safest) |
| **Release deadman** | Autonomy allowed — car **may move** on `/drive` |

Start with the car lifted or blocked. Release deadman only when ready for a slow test (~0.08 m/s).

Full Part C with your own CSV: [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md).

---

## Your first milestone

**Goal:** Car autonomously follows `traj_race_cl.csv` for at least one full lap without collision.

### Step 1 — Reproduce the map (1–2 sessions)

Follow mapping guide Parts A + B. Confirm your `FINAL_track_map.png` looks like the reference (sharp outer ring, clear inner box, closed raceline).

### Step 2 — Implement pursuit on the car (pick up here)

Use the **[Pursuit quick start](#pursuit-quick-start-skip-re-mapping)** above first.

**Option A — Pure pursuit (recommended):** launch stack + `raceline_pure_pursuit_node` — see quick start.

**Option B — Nav2 (later):** only after Option A works — see [AUTONOMY_MODES.md](AUTONOMY_MODES.md) § Nav2.

**Do not expect the car to move** with only:

```bash
autonomy:=raceline_path   # publishes /global_path only — no /drive
```

### Step 3 — Validate

- [ ] Car completes one lap at low speed (~0.08 m/s)
- [ ] Deadman stops car immediately when squeezed
- [ ] No wall collisions
- [ ] Document what you changed in a PR or session note

---

## Key files for pursuit work

| File | Role |
|------|------|
| `traj_race_cl.csv` | Optimized raceline (from Part B or `testrun/june7_set7/`) |
| `wall_follow_script/reactive_control/raceline_pure_pursuit_node.py` | Geometric pursuit node |
| `bringup.launch.py` | Launch args: `autonomy:=raceline_path`, `pursuit_world_frame:=map` |
| `config/ackermann_mux_topics.yaml` | RC priority 100 > autonomy `/drive` 10 |

---

## Reference data (June 7, best run)

| Path | Contents |
|------|----------|
| `testrun/june7_set7/lap3x/` | Source rosbag |
| `testrun/june7_set7/maps/` / `track_dedrift.pgm` | De-drifted map |
| `testrun/june7_set7/traj_race_cl.csv` | Raceline to load on car |
| `testrun/june7_set7/FINAL_berlin_dedrift.png` | Reference figure |

You can copy `traj_race_cl.csv` from this folder for first pursuit tests without re-mapping.

---

## Known lessons (don't repeat our mistakes)

1. **Short bag on car, heavy SLAM on laptop** — not the reverse.
2. **Track must have walls on both sides** — see [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md).
3. **Don't relaunch** mid-session if you need consistent `odom` / `map` frame.
4. **2–3 laps max** when recording — more laps on Pi caused drift and bad maps.
5. **`car_map_setup.sh` every container session** — container is ephemeral.

---

## Doc reading order for new team

1. [00_START_HERE.md](00_START_HERE.md)
2. [HANDOFF_STATUS.md](HANDOFF_STATUS.md) ← this file
3. [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md)
4. Docs 01 → 04 (setup + RC test)
5. [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md) Parts A–B (reproduce map)
6. **Part C + milestone above** (pursuit — your work)
7. [06_VALIDATION_CHECKLIST.md](06_VALIDATION_CHECKLIST.md)

---

## Contact / context

- **Course:** UCSD DSC 190, Winter 2026, Team 7 (HDSI)
- **Professor:** Jack Silberman
- **Repo:** https://github.com/nabilafifahq/roboracer-t7

Ask professor for car access, track storage location, and battery charging procedure.
