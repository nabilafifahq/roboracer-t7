# Project Layout

Where everything lives in this repo. Read this once when taking over the project.

---

## Top-level folders

| Folder | Purpose | New team needs it? |
|--------|---------|-------------------|
| **`docs/`** | All documentation — start at `00_START_HERE.md` | **Yes** |
| **`scripts/`** | Shell helpers (car, offline map, raceline) | **Yes** |
| **`config/`** | EKF, joy, Cartographer, mux YAML/Lua | **Yes** (referenced by container) |
| **`docker/`** | Dockerfile, entrypoint, build overrides | When rebuilding image |
| **`wall_follow_script/`** | ROS 2 package: wall follow, map logger, pursuit nodes | **Yes** (built into image) |
| **`launch/`** | Cartographer launch file | **Yes** |
| **`bringup.launch.py`** | Main stack entrypoint (root of repo) | **Yes** |
| **`raceline_data/`** | TUM optimizer inputs/outputs (templates) | For raceline pipeline |
| **`racelines/`** | Example optimized trajectories | Reference |
| **`testrun/`** | Recorded bags, maps, figures from June 2026 sessions | Reference + examples |
| **`test_manual_map_logger/`** | Offline plotting / notebook tools | Optional |
| **`test_manual_map_new/`** | Older offline map merge experiments | Optional / historical |
| **`roboracer_nav2_vector_pursuit/`** | Nav2 + vector pursuit integration | Advanced autonomy |
| **`vesc-main/`** | Local VESC driver reference copy | Reference only (runtime uses image) |
| **`history/`** | Old debug session notes | Historical |
| **`2026-IV-Competition-Map/`** | Real competition track reference (not our DIY track) | Context only |

---

## Key scripts (`scripts/`)

| Script | Run on | What it does |
|--------|--------|--------------|
| `car_run.sh` | Pi host | Start Docker container |
| `car_exec.sh` | Pi host | Shell into running container |
| `car_stop.sh` | Pi host | Stop container |
| `car_status.sh` | Pi host | Check if container is up |
| `car_map_setup.sh` | Container | Apply all mapping fixes (once per session) |
| `cartographer_offline_dedrift.sh` | Laptop | Replay bag → clean map |
| `build_raceline_from_bag.py` | Laptop | Map + bag → raceline + figure |
| `manual_map_csv_to_tum_track.py` | Laptop or container | CSV logger → TUM input |
| `docker_build_full_stack.sh` | Dev machine | Build + push Docker image |

---

## Documentation map (`docs/`)

| File | Purpose |
|------|---------|
| `00_START_HERE.md` | Router — read first |
| **`HANDOFF_STATUS.md`** | **Status + pick-up task (pursuit)** |
| **`PHYSICAL_SETUP.md`** | **Car, track, Wi-Fi, layout** |
| `01`–`04` | Install, Docker, car connect, manual RC |
| **`MAPPING_AND_RACELINE_GUIDE.md`** | Map pipeline (A–B done, C = pursuit) |
| `05`–`07` | Autonomy, validation, troubleshooting |
| `08`–`11` | Reference, versions, credits, safety |
| `archive/` | Old session runbooks (history only) |

---

## Test data (`testrun/`)

Organized by session date. Useful references:

| Folder | Contents |
|--------|----------|
| `testrun/june7_set7/` | **Best result** — offline de-drift + final figure |
| `testrun/june7_set6/` | Good offline pipeline example |
| `testrun/my_run/` | **Your runs** — create this when following the guide |

Each session folder typically has: `lap_bag/` (recording), `maps/` (de-drifted `.pgm`), output CSVs and PNGs.

---

## Docker image

**Handoff tag (use this):**

```bash
nabilafifahq/roboracer-t7:cartographer-ekf
```

Contains: ROS 2 Humble, Livox driver, EKF, Cartographer, wall-follow, map logger, bringup.

Legacy tags (`full-stack`, `main-latest`) — see `docs/02_DOCKER_BUILD_PUSH.md` if you hit old docs.

---

## What you can ignore at first

- `test_manual_map_new/` — early offline merge experiments
- `docs/archive/` — superseded runbooks
- `vesc-main/` — not used at runtime directly
- `ORB_SLAM3` docs — visual SLAM spike, not main pipeline

---

## Recommended first-day checklist

1. Read `docs/00_START_HERE.md` + **`docs/HANDOFF_STATUS.md`**
2. Read **`docs/PHYSICAL_SETUP.md`** (track + car access)
3. Pull `cartographer-ekf` on car and laptop
4. Complete docs 01–04 (RC works)
5. Reproduce map: mapping guide Parts A–B
6. **Pick up:** Part C pursuit — milestone in HANDOFF_STATUS
