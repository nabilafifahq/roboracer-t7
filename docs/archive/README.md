# Archived documentation

These files are **historical** — kept for context on June 2026 debugging sessions.

**Use the current guide instead:**

→ [../HANDOFF_STATUS.md](../HANDOFF_STATUS.md) · [../MAPPING_AND_RACELINE_GUIDE.md](../MAPPING_AND_RACELINE_GUIDE.md)

---

## What's here

| File | Why archived |
|------|--------------|
| `RUNBOOK_2026-06-04.md` | Session-specific steps |
| `RUNBOOK_2026-06-06.md` | June 6 odom-frame session |
| `RUNBOOK_FINAL_MAP_FRAME.md` | Merged into mapping guide Part A |
| `RUNBOOK_MAP_FRAME_TUM.md` | Long paste blocks, superseded |
| `MANUAL_LOGGING_CARTOGRAPHER_RUNBOOK.md` | Duplicate mapping steps |
| `MAPPING_RUNBOOK_CARTOGRAPHER_EKF.md` | Branch-specific runbook |
| `HANDOVER_2026-06-03.md` | Point-in-time handoff |
| `CURSOR_AGENT_HANDOFF_local_vs_origin_main.md` | Agent session notes |
| `CARTOGRAPHER_EKF_PIPELINE.md` | Merged into mapping guide |
| `CARTOGRAPHER_EKF_SETUP_GUIDE.md` | Too long; fixes in `car_map_setup.sh` |
| `CARTOGRAPHER_VS_SLAMTOOLBOX_AB.md` | A/B experiment notes |
| `COMPETITION_RACELINE_PIPELINE.md` | Merged into mapping guide Part C |
| `RACELINE_PIPELINE.md` | Merged into mapping guide |
| `PROJECT_COMPLETE_SUMMARY.md` | 500-line dump; replaced by START_HERE + mapping guide |

## Lessons preserved

- Long live mapping on Pi drifts — use **2–3 laps** + **offline de-drift on laptop**.
- LiDAR slice **-0.08 / -0.02 m** reads walls, not floor.
- Set `range_max` in config file, not via `ros2 param set`.
