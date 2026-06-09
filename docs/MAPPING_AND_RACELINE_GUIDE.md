# Mapping and Raceline Guide

**Goal:** Record the track on the car, build a clean map + optimal racing line on your laptop.

**Reference result:** `testrun/june7_set6/set6_FINAL_berlin.png` (same layout as your `FINAL_track_map.png` output).

---

## Who should read this?

| You are… | Read first |
|----------|------------|
| **Brand new to this repo** | [00_START_HERE.md](00_START_HERE.md) → setup docs **01 through 04** → then come back here |
| **Car already works, RC tested** | Start at [Part A](#part-a--record-on-the-car) below |
| **Something broke** | [07_TROUBLESHOOTING.md](07_TROUBLESHOOTING.md) |

---

## Glossary

| Term | Plain meaning |
|------|----------------|
| **Laptop** | Your Laptop/PC where you edit code |
| **Car host (Pi)** | Raspberry Pi on the car. Prompt looks like: `ucsd-blue@UCSD-Blue:~$` |
| **Container** | Software environment inside Docker on the Pi. Prompt looks like: `root@UCSD-Blue:/race_ws#` |
| **SSH** | Remote login: `ssh ucsd-blue@ucsd-blue.local` opens a shell on the car |
| **Docker image** | Pre-built software package. We use: `nabilafifahq/roboracer-t7:cartographer-ekf` |
| **Bag** | A recording file (like a video of sensor data) saved while you drive |
| **SLAM / Cartographer** | Software that builds a map from LiDAR while the car moves |
| **De-drift (offline)** | Re-process the bag on a laptop with loop closure — fixes map smear from Pi CPU load |
| **`/scan`** | LiDAR data as a 2D laser ring (~10 messages per second) |
| **Deadman (RC button 1)** | Safety switch on the remote — see [Safety](#safety-deadman-switch) below |
| **TUM optimizer** | Offline tool that computes a fast racing line from track width data |

---

## The workflow (big picture)

```
  CAR (2–3 laps, record bag)  →  LAPTOP (de-drift + raceline)  →  CAR (optional: drive line)
```

**Important lesson from our testing:**

| Approach | Result |
|----------|--------|
| Long live mapping on Pi (5+ laps) | Map **smears** and drifts — do **not** rely on this |
| Short drive (2–3 laps) + **offline de-drift on laptop** | **Clean walls** — this is the recommended pipeline |

---

## What you are building

```
  ┌─────────────────────────────────────┐
  │  outer hose wall (measured)         │
  │    ┌───────────────┐                │
  │    │  inner box    │  ← ~1.25×0.40 m│
  │    │  (measured)   │                │
  │    └───────────────┘                │
  │         ╭── racing line ──╮         │
  └─────────────────────────────────────┘
```

Final deliverable: **`FINAL_track_map.png`** — measured walls + optimized raceline on one figure.

---

## Safety: deadman switch

The RC controller has a **deadman button** (index `1` on `/joy`).

| Phase | What to do |
|-------|------------|
| **Manual driving / mapping** | Turn deadman **ON** to drive. |
| **Autonomous driving (Part C)** | Turn deadman **OFF** to allow `/drive`. **Press deadman = stop** (RC overrides autonomy). |

---

## Part A — Record on the car

You need **3 terminal tabs on your laptop**. Each tab SSHs into the car. Prompt tells you where you are.

### Terminal map (keep this open while reading)

| Tab | Where you are | Prompt looks like | Job | Keep open? |
|-----|---------------|-------------------|-----|------------|
| **Tab 1** | Container | `root@UCSD-Blue:/race_ws#` | Main software launch | **Yes — whole session** |
| **Tab 2** | Pi host | `ucsd-blue@UCSD-Blue:~$` | One-time file copy into container | Can close after Step A2 |
| **Tab 3** | Container | `root@UCSD-Blue:/race_ws#` | Health checks + bag recording | Yes until bag copied off |

```
  Laptop
    ├── Tab 1 ──SSH──► Pi ──car_run.sh──► Container ── ros2 launch (DON'T STOP)
    ├── Tab 2 ──SSH──► Pi host ────────── docker cp (once)
    └── Tab 3 ──SSH──► Pi ──car_exec.sh──► Container ── record bag
```

---

### Step A1 — Tab 1: SSH, pull repo, start container

Sequence: RC transmitter **ON** → car power **ON** → wait ~30 s → SSH.

On **Tab 1** (laptop):

```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7
git fetch origin && git checkout docs/clean-handoff && git pull
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
docker pull "$IMAGE"
./scripts/car_run.sh
```

**Expected:** Prompt changes to `root@UCSD-Blue:/race_ws#` — you are now **inside the container**.

---

### Step A2 — Tab 2: Copy setup script into container (once)

Open **Tab 2** on your laptop (new SSH session — do **not** use Tab 1):

```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7
docker cp scripts/car_map_setup.sh roboracer_t7:/race_ws/scripts/
docker cp config/cartographer/roboracer_2d.lua roboracer_t7:/race_ws/config/cartographer/
```

**Expected:** No errors. Prompt stays `ucsd-blue@UCSD-Blue:~$` (Pi host — **not** `/race_ws#`).

You can close Tab 2 after this.

---

### Step A3 — Tab 1: Apply fixes and launch stack

Back on **Tab 1** (container, `/race_ws#`):

```bash
source /race_ws/scripts/car_map_setup.sh
ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=true
```

**Expected:** Nodes start, no crash loop. Text scrolls but terminal stays running.

**Do not Ctrl+C this until the entire session is done.** Restarting resets the `odom` origin.

---

### Step A4 — Tab 3: Health check

Open **Tab 3** on your laptop:

```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7
./scripts/car_exec.sh
```

**Expected:** Prompt is `root@UCSD-Blue:/race_ws#` (container via exec, not car_run).

Run checks:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash

ros2 topic hz /scan
```

**Expected (good):** Lines like `average rate: 9.xxx` or `10.xxx` — let it run 5–10 seconds.

**Bad:** `average rate: nan` or no output for 10+ s → go to Tab 1, Ctrl+C launch, redo Step A3.

More checks:

```bash
ros2 topic echo /scan --once --field range_max    # Expected: 2.5
ros2 run tf2_ros tf2_echo odom base_link          # Parked: yaw number stable (not spinning)
```

---

### Step A5 — Tab 3: Record bag while driving

Still on **Tab 3** (container). **Hold RC deadman.** Drive **2–3 slow, smooth laps** around the track (inner box + outer hose). Not more than 3 laps (~60–90 seconds of driving).

Start recording **before** you drive:

```bash
ros2 bag record -o /race_ws/logs/lap_bag \
  /scan /tf /tf_static /odom /odometry/filtered /livox/lidar
```

When finished:

1. **Ctrl+C** the bag recorder (Tab 3)
2. Stop the car
3. Leave Tab 1 launch **running** until files are copied off

**Expected:** Message showing bag saved under `/race_ws/logs/lap_bag/`.

---

### Step A6 — Copy bag to laptop

On **Tab 2** (`exit` to return to Pi Host):

```bash
ssh ucsd-blue@ucsd-blue.local
docker cp roboracer_t7:/race_ws/logs/lap_bag ~/lap_bag
```

On **your laptop** (`exit` to return to local terminal, not SSH):

```bash
mkdir -p ~/Documents/roboracer-t7/testrun/my_run
scp -r ucsd-blue@ucsd-blue.local:~/lap_bag ~/Documents/roboracer-t7/testrun/my_run/
```

**Expected:** Folder `testrun/my_run/lap_bag/` exists on laptop with `.db3` files inside.

Now you may Ctrl+C Tab 1 launch and run `./scripts/car_stop.sh` on Pi host if done for the day.

---

## Part B — Build map and raceline on laptop

All steps run on **your laptop** in **one terminal**. Not on the car.

### Before you start (checklist)

- [ ] Repo cloned: `git clone https://github.com/nabilafifahq/roboracer-t7.git`
- [ ] On branch: `git checkout docs/clean-handoff`
- [ ] Bag copied to: `testrun/my_run/lap_bag/`
- [ ] **Docker Desktop** running (for de-drift script)
- [ ] Docker image pulled: `docker pull nabilafifahq/roboracer-t7:cartographer-ekf`
- [ ] Python packages: `pip install numpy scipy matplotlib pillow rosbags`
- [ ] (Optional, for TUM) Raceline image built — [02_DOCKER_BUILD_PUSH.md](02_DOCKER_BUILD_PUSH.md) § “raceline optimizer”, or skip `--run-tum`

```bash
cd ~/Documents/roboracer-t7   # your repo path
git checkout docs/clean-handoff && git pull
```

---

### Step B1 — De-drift the map

```bash
./scripts/cartographer_offline_dedrift.sh \
  testrun/my_run/lap_bag \
  testrun/my_run/maps
```

**Expected** in `testrun/my_run/maps/`:

| File | Meaning |
|------|---------|
| `dedrift.pbstream` | Cartographer state (loop closure applied) |
| `track_dedrift.pgm` + `.yaml` | Occupancy map — sharp walls |
| `offline_log.txt` | Log (should end without errors) |

Takes ~20–60 s on a laptop.

---

### Step B2 — Build raceline + final figure

**With TUM optimizer** (needs `roboracer-t7-raceline:latest` Docker image):

```bash
python3 scripts/build_raceline_from_bag.py \
  --bag   testrun/my_run/lap_bag \
  --pgm   testrun/my_run/maps/track_dedrift.pgm \
  --yaml  testrun/my_run/maps/track_dedrift.yaml \
  --outdir testrun/my_run \
  --run-tum
```

**Without TUM** (track input CSV only — if raceline Docker image not available):

```bash
python3 scripts/build_raceline_from_bag.py \
  --bag   testrun/my_run/lap_bag \
  --pgm   testrun/my_run/maps/track_dedrift.pgm \
  --yaml  testrun/my_run/maps/track_dedrift.yaml \
  --outdir testrun/my_run
```

**Expected** in `testrun/my_run/`:

| File | Meaning |
|------|---------|
| `tum_track_input.csv` | Centerline + measured wall widths |
| `traj_race_cl.csv` | Optimized raceline (if `--run-tum`) |
| `FINAL_track_map.png` | **Final figure** — walls + raceline |

Open `FINAL_track_map.png`. Good result:

- Closed outer ring (hose) — not blurry/smeared
- Rectangular inner box — sharp corners
- Raceline looping around the box

Compare to reference: `testrun/june7_set6/set6_FINAL_berlin.png` (June 7 best run).

---

## Part C — Drive the raceline on the car (**YOUR MAIN TASK**)

**Team 7 status:** Map + raceline CSV/figure works offline. **Pursuit on the car is not yet validated** — this is where the next team picks up.

Read [HANDOFF_STATUS.md](HANDOFF_STATUS.md) § “Pursuit quick start” before starting.

Need **3 tabs** (same pattern as Part A): Tab 1 = launch, Tab 2 = Pi host copies, Tab 3 = pursuit node.

> **`autonomy:=raceline_path` does not drive the car** — it only publishes `/global_path`. Use pure pursuit (Step C4) to move.

### Step C1 — Copy raceline from laptop to car

**Laptop** (local terminal). Use your own CSV or the reference:

```bash
# Your run:
scp ~/Documents/roboracer-t7/testrun/my_run/traj_race_cl.csv \
    ucsd-blue@ucsd-blue.local:~/traj_race_cl.csv

# Or reference (skip re-mapping):
scp ~/Documents/roboracer-t7/testrun/june7_set7/traj_race_cl.csv \
    ucsd-blue@ucsd-blue.local:~/traj_race_cl.csv
```

### Step C2 — Tab 1 (Pi host): start container

```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7
git fetch origin && git checkout docs/clean-handoff && git pull
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh
mkdir -p /race_ws/racelines
```

**Expected:** Prompt `root@UCSD-Blue:/race_ws#`

### Step C2b — Tab 2 (Pi host): copy setup scripts + CSV into container

Open **Tab 2** (Pi host — prompt `ucsd-blue@...`, **not** container):

```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7
docker cp scripts/car_map_setup.sh roboracer_t7:/race_ws/scripts/
docker cp config/cartographer/roboracer_2d.lua roboracer_t7:/race_ws/config/cartographer/
docker cp ~/traj_race_cl.csv roboracer_t7:/race_ws/racelines/traj_race_cl.csv
```

**Expected:** No errors. Required every fresh container — scripts are not persisted after `car_stop.sh`.

### Step C3 — Tab 1 (container): setup + launch stack

Back on **Tab 1**:

```bash
source /race_ws/scripts/car_map_setup.sh
ros2 launch /race_ws/bringup.launch.py autonomy:=none use_cartographer:=true
```

**Expected:** Nodes start, no crash loop. Leave running.

This provides Cartographer + `map` frame. It does **not** follow the raceline yet.

### Step C4 — Tab 3 (container): pure pursuit

Open **Tab 3** (Pi host → `./scripts/car_exec.sh`):

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash

ros2 run reactive_control raceline_pure_pursuit_node --ros-args \
  -p trajectory_csv:=/race_ws/racelines/traj_race_cl.csv \
  -p world_frame:=map \
  -p target_speed_mps:=0.08 \
  -p lookahead_m:=0.45 \
  -p wheelbase_m:=0.33
```

**Expected:** Node starts without errors. Car moves when deadman is released (see below).

### Step C5 — Deadman (pursuit)

| Action | Effect |
|--------|--------|
| **Squeeze / hold deadman** | RC override — **car stops** |
| **Release deadman** | Autonomy on `/drive` — **car may move** |

Test with wheels up or car blocked first. Target speed ~0.08 m/s.

### Optional — visualize path in RViz (does not drive)

In a fourth shell, you can publish `/global_path` without affecting motors:

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  raceline_csv:=/race_ws/racelines/traj_race_cl.csv \
  pursuit_world_frame:=map \
  use_cartographer:=true
```

Do **not** run this instead of Step C4 if you want the car to move. See [AUTONOMY_MODES.md](AUTONOMY_MODES.md).

---

## Troubleshooting (quick)

| Problem | Fix |
|---------|-----|
| Wrong prompt for command | Pi host = `ucsd-blue@...`. Container = `root@...:/race_ws#`. Use [Terminal map](#terminal-map-keep-this-open-while-reading). |
| `/scan` is 0 Hz | Restart launch (Tab 1). May need to re-record bag. |
| Walls smeared in figure | Skipped offline de-drift, or drove too many laps. Re-run Part B. |
| Fake extra walls in map | Too many laps on Pi live. Shorter bag + offline pipeline. |
| TUM fails | Drop `--run-tum`; use `tum_track_input.csv` manually, or `scripts/path_to_raceline.py`. |
| `docker cp` fails | Container must be running (`./scripts/car_status.sh`). |

Full list: [07_TROUBLESHOOTING.md](07_TROUBLESHOOTING.md)

---

## Scripts reference

| Script | Run on | Purpose |
|--------|--------|---------|
| `scripts/car_run.sh` | Pi host | Start container |
| `scripts/car_exec.sh` | Pi host | Open second shell inside container |
| `scripts/car_map_setup.sh` | Container | Apply all mapping fixes (once per session) |
| `scripts/cartographer_offline_dedrift.sh` | Laptop | Bag → de-drifted map |
| `scripts/build_raceline_from_bag.py` | Laptop | Map + bag → raceline + figure |

---

## Historical runbooks

June 2026 session notes are in [archive/](archive/) — for history only. **Use this guide instead.**
