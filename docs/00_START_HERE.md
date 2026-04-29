# RoboRacer T7 - Start Here

This repo is the handoff guide for new students. Follow the docs in this exact order.

---

## Read in this order

1. `docs/01_INSTALL_AND_REQUIREMENTS.md`
2. `docs/02_DOCKER_BUILD_PUSH.md`
3. `docs/03_CAR_CONNECT_AND_CONTAINER.md`
4. `docs/04_MANUAL_DRIVE_SETUP.md`
5. `docs/05_AUTONOMY_SETUP_AND_RUN.md`
6. `docs/06_VALIDATION_CHECKLIST.md`
7. `docs/07_TROUBLESHOOTING.md`
8. `docs/08_FULL_STACK_REFERENCE_MANUAL.md`
9. `docs/09_PLATFORM_VERSIONS_AND_RELEASE_NOTES.md`
10. `docs/10_EXTERNAL_CREDITS.md`
11. `docs/11_SAFETY_FAILSAFE_AND_COMPETITION_RULES.md`

---

## How to use these docs

For each step:
1. Open the file listed in order.
2. Run commands exactly as shown.
3. Check the "Expected" result before moving to the next file.
4. If a step fails, go to `docs/07_TROUBLESHOOTING.md`, fix it, then continue.

Do not skip the manual-drive validation step before autonomy.

---

## What this stack does

- Manual RC driving with deadman safety switch.
- LiDAR point cloud to LaserScan bridge for autonomy.
- Slow indoor hallway autonomy (wall-follow baseline).
- Docker-first workflow for reproducibility.

---

## One-command helper scripts

From repo root on the car host:

- Start container: `./scripts/car_run.sh`
- Check container status: `./scripts/car_status.sh`
- Enter running container with ROS sourced: `./scripts/car_exec.sh`
- Launch unified stack: `./scripts/car_launch.sh`
- Stop named container: `./scripts/car_stop.sh`

These helpers save time, but new users should still read the runbooks first.
