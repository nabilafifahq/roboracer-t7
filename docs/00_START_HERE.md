# RoboRacer T7 — Start Here

**Handoff doc for a new team.** Read this page once, then follow the path below.

---

## What is this project?

A small indoor race car (F1TENTH scale) that:

1. You drive with an RC controller (with a safety deadman switch).
2. A LiDAR sensor maps the track while you drive.
3. Software builds a **track map + optimal racing line** from that recording.
4. The car should follow that line autonomously — **that last step is your main task**.

**Team:** UCSD DSC 190 Winter 2026, Team 7.

---

## Read these three first

| # | Doc | Why |
|---|-----|-----|
| 1 | **[HANDOFF_STATUS.md](HANDOFF_STATUS.md)** | What works, what doesn't, **where you pick up** |
| 2 | **[PHYSICAL_SETUP.md](PHYSICAL_SETUP.md)** | Car, track, Wi-Fi, power-on, layout |
| 3 | **[PROJECT_LAYOUT.md](PROJECT_LAYOUT.md)** | What each folder is |

---

## Full setup path (first time)

Do these **in order**:

| Step | Doc | What you do |
|------|-----|-------------|
| 1 | [01_INSTALL_AND_REQUIREMENTS.md](01_INSTALL_AND_REQUIREMENTS.md) | Check hardware + software |
| 2 | [02_DOCKER_BUILD_PUSH.md](02_DOCKER_BUILD_PUSH.md) | Pull Docker images (car + laptop) |
| 3 | [03_CAR_CONNECT_AND_CONTAINER.md](03_CAR_CONNECT_AND_CONTAINER.md) | SSH to car, start container |
| 4 | [04_MANUAL_DRIVE_SETUP.md](04_MANUAL_DRIVE_SETUP.md) | Confirm RC driving works |
| 5 | [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md) | Record bag → build map (Parts A–B) |
| 6 | [HANDOFF_STATUS.md](HANDOFF_STATUS.md) § milestone | **Implement pursuit on car (Part C)** |
| 7 | [06_VALIDATION_CHECKLIST.md](06_VALIDATION_CHECKLIST.md) | Sign-off |

**Optional:** [05_AUTONOMY_SETUP_AND_RUN.md](05_AUTONOMY_SETUP_AND_RUN.md) (wall-follow) · [07_TROUBLESHOOTING.md](07_TROUBLESHOOTING.md) (fixes)

---

## One Docker image (use everywhere)

```bash
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
docker pull "$IMAGE"
```

Pull on **car (Pi)** and **laptop** (laptop needs it for offline map processing).

---

## Helper scripts (Pi host)

Prompt must be **`ucsd-blue@UCSD-Blue:~$`** (Pi host):

```bash
cd ~/roboracer-t7
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh       # start container
./scripts/car_exec.sh      # another shell inside container
./scripts/car_status.sh
./scripts/car_stop.sh
```

Inside container: **`root@UCSD-Blue:/race_ws#`**

---

## Reference docs

| Doc | When |
|-----|------|
| [08_FULL_STACK_REFERENCE_MANUAL.md](08_FULL_STACK_REFERENCE_MANUAL.md) | Hardware, TF frames |
| [09_PLATFORM_VERSIONS_AND_RELEASE_NOTES.md](09_PLATFORM_VERSIONS_AND_RELEASE_NOTES.md) | Versions |
| [11_SAFETY_FAILSAFE_AND_COMPETITION_RULES.md](11_SAFETY_FAILSAFE_AND_COMPETITION_RULES.md) | Safety tests |
| [AUTONOMY_MODES.md](AUTONOMY_MODES.md) | Pursuit mode options |

Archived June session notes: [archive/](archive/) — history only.

---

## How to read any doc

1. Check **which machine** (laptop / Pi host / container) — see prompt in each step.
2. Run commands exactly as shown.
3. Read **Expected** before continuing.
4. Stuck → [07_TROUBLESHOOTING.md](07_TROUBLESHOOTING.md).
