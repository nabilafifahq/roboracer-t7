# Handoff Status

**Last updated:** June 2026  
**Branch with clean docs:** `docs/clean-handoff`  
**Docker image:** `nabilafifahq/roboracer-t7:cartographer-ekf`

Read this first, then [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md) (includes a **photo of the current track** — layout can change) and [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md).

---

## Summary

We can **record several short drives on the car**, **build a clean readable map and racing line on a laptop** (TUM optimizer), and produce a **final track figure** with measured walls and an optimal path. We have **not yet successfully run that raceline on the car in pursuit mode** — that is the next main task for the next team.

---

## What works right now

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

## What does NOT work yet

| Capability | Status | What to do |
|------------|--------|------------|
| **On-car raceline pursuit** | **Not implemented / not validated** | **Primary task** — see [§ Your first milestone](#your-first-milestone) |
| Saved-map localization (drive without re-mapping) | Config exists, untested on car | `config/cartographer/roboracer_2d_localization.lua` + `.pbstream` |
| Nav2 full-stack follow | Partially wired, not team-validated | `AUTONOMY_MODES.md`, `roboracer_nav2_vector_pursuit/` |
| RC-loss watchdog | Not implemented | Doc 11 TC-02/03 |
| Steering pull-right trim | Mechanical — hurts map quality | Bench calibration |

---

## Pipeline that produces the map

```
Car: 2–3 laps + rosbag          →  Laptop: offline de-drift 
                                 →  Laptop: build_raceline_from_bag.py
                                 →  Output: FINAL_track_map.png + traj_race_cl.csv
```

**Do not** rely on long live mapping sessions on the Pi (5+ laps) — maps smear and drift. Always use the **offline de-drift** step on the laptop.

Full steps: [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md) Parts A and B.

**Compare your result to:** `testrun/june7_set6/set6_FINAL_berlin.png`

---

## Pursuit quick start

After completing step A and B, follow Part C: [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md). This however is not fully tested.

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
