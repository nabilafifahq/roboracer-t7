# RoboRacer T7

UCSD Winter 2026 Team 7 RoboRacer (F1TENTH indoor platform).

RoboRacer (1/10 Robot Indoors) project for:

- Halicioglu Data Science Institute (HDSI), UC San Diego
- DSC 190, Winter 2026, Team 7
- Professor/Mentor: Jack Silberman
- Team Members: Derek Huang, Nabila Afifah Qotrunnada, Ricky Zhang

---

## Start Here (required)

Read this first:

- `docs/00_START_HERE.md`

Then follow docs in this exact order:

1. `docs/01_INSTALL_AND_REQUIREMENTS.md`
2. `docs/02_DOCKER_BUILD_PUSH.md`
3. `docs/03_CAR_CONNECT_AND_CONTAINER.md`
4. `docs/04_MANUAL_DRIVE_SETUP.md`
5. `docs/05_AUTONOMY_SETUP_AND_RUN.md`
6. `docs/06_VALIDATION_CHECKLIST.md`
7. `docs/07_TROUBLESHOOTING.md`
8. `docs/08_FULL_STACK_REFERENCE_MANUAL.md` (full hardware/software/glossary/reference guide)
9. `docs/09_PLATFORM_VERSIONS_AND_RELEASE_NOTES.md` (official runtime versions + release notes)

---

## Repository Structure

- `docs/`
  - all official runbooks, setup guides, troubleshooting, and architecture docs
- `docker/`
  - Docker build files and runtime config payloads
- `config/`
  - first-party runtime configs (RC teleop, mux topics)
- `scripts/`
  - helper shell scripts for container workflow
- `wall_follow_script/`
  - first-party autonomy package (`reactive_control`)
- `bringup.launch.py`
  - unified launch entrypoint used in runtime image

External/vendor code (not first-party docs target):

- `third_party_research/`
- `vesc-main/`

---

## Helper Scripts (fast workflow)

From repo root on the car host:

- Start container: `./scripts/car_run.sh`
- Check container status: `./scripts/car_status.sh`
- Open sourced shell in running container: `./scripts/car_exec.sh`
- Launch unified stack: `./scripts/car_launch.sh`
- Stop named container: `./scripts/car_stop.sh`

---

## Additional Reference Docs

- Node/topic communication map: `docs/MANUAL_AUTONOMY_NODE_TOPIC_FLOW.md`
- PointCloud2 -> LaserScan focused runbook: `docs/POINTCLOUD2_TO_LASERSCAN_CAR_RUNBOOK.md`
- ARM64 camera notes: `docs/RUNBOOK_ARM64_CAMERA_DOCKER.md`
- Docs index (all docs + media): `docs/README.md`
