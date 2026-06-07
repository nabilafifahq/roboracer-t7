# Validation Checklist

Use before declaring a session or handoff milestone complete.

**Current team goal:** map pipeline works; **pursuit on car is the open milestone** — see [HANDOFF_STATUS.md](HANDOFF_STATUS.md).

---

## A) Physical + connectivity

- [ ] RC on before car power (see [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md))
- [ ] Laptop on Wi-Fi `ucsd_robocar`
- [ ] `ssh ucsd-blue@ucsd-blue.local` works
- [ ] Track built: inner stacked boxes + outer pipe/walls, closed loop (see [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md) §4 photo)
- [ ] `./scripts/car_run.sh` → prompt `root@...:/race_ws#`

---

## B) Manual RC (doc 04)

- [ ] `ros2 topic hz /joy` active
- [ ] Deadman ON → `/teleop` and motor commands update
- [ ] Deadman OFF → commands stop
- [ ] Wheels move in intended direction

---

## C) Sensors (mapping session)

- [ ] `ros2 topic hz /livox/lidar` ~10 Hz
- [ ] `ros2 topic hz /scan` ~10 Hz (not `nan`)
- [ ] `ros2 topic echo /scan --once --field range_max` → `2.5`
- [ ] `ros2 topic echo /sensors/core --once` → healthy VESC

---

## D) Map pipeline (Parts A–B) — **working today**

- [ ] Bag recorded: 2–3 laps, `testrun/my_run/lap_bag/` on laptop
- [ ] `./scripts/cartographer_offline_dedrift.sh` → `track_dedrift.pgm` + `.yaml`
- [ ] `build_raceline_from_bag.py` → `FINAL_track_map.png`
- [ ] Figure quality: sharp outer ring, clear inner box (compare `testrun/june7_set7/`)
- [ ] `traj_race_cl.csv` exists

---

## E) Pursuit on car — **NOT DONE — next team**

Use [HANDOFF_STATUS.md](HANDOFF_STATUS.md) § Pursuit quick start (pure pursuit + `world_frame:=map`).

- [ ] `traj_race_cl.csv` on car (reference: `testrun/june7_set7/`)
- [ ] `car_map_setup.sh` copied into container (Step C2b)
- [ ] Stack: `autonomy:=none use_cartographer:=true`
- [ ] `raceline_pure_pursuit_node` running (`world_frame:=map`)
- [ ] **Not** relying on `raceline_path` alone (that does not drive)
- [ ] Car completes **one full lap** at ~0.08 m/s
- [ ] Squeeze deadman = stop; release = autonomy allowed
- [ ] No collisions

---

## F) Optional — wall-follow baseline (doc 05)

- [ ] `ros2 launch /race_ws/bringup.launch.py` — wall_follow runs
- [ ] `/drive` active, car moves slowly in hallway
- [ ] Manual override works

---

## G) Optional — rosbag from bringup

```bash
ros2 launch /race_ws/bringup.launch.py record_bag:=true bag_name:=my_run
```

Default off. Bags under `/race_ws/bags/`.

---

## Sign-off

| Milestone | Owner | Date | Pass? |
|-----------|-------|------|-------|
| Map pipeline (D) | | | |
| Pursuit one lap (E) | | | |
| Full validation (A–E) | | | |
