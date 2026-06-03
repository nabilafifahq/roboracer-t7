# Cartographer + EKF vs SLAM Toolbox — A/B test & mapping-quality runbook

Goal: decide objectively whether to drop SLAM Toolbox in favor of **EKF (odom→base_link) + Cartographer (map→odom)** for competition mapping, and fix the mapping-quality issues this car actually hits.

Related: `docs/CARTOGRAPHER_EKF_SETUP_GUIDE.md` · `docs/CARTOGRAPHER_EKF_PIPELINE.md` · `docs/MANUAL_MAP_LOGGER.md`

---

## Why we are switching

| | SLAM Toolbox | EKF + Cartographer |
|---|---|---|
| Integration | simple, fast to start | more config (frames, sampling, scan matcher) — **now done** |
| Odom/scan noise tolerance | brittle; frequent retune | stronger pose-graph loop closure, correlative scan matching |
| Repeated-lap consistency | drifts → retune cycles | better global consistency |
| This car's pain | "too much tuning and noise" | the architecture we're committing to |

EKF is **not** a SLAM replacement — it is the smooth `odom→base_link` foundation that *feeds* Cartographer. Cartographer adds the global `map→odom` correction.

---

## Three known mapping-quality issues on THIS car (and the fixes)

### 1. LiDAR was slicing over the walls ("looking too high") — FIXED in config
The track walls are only **~0.20 m** tall, but `pointcloud_to_laserscan` was accepting returns up to `max_height: 0.35` **in the laser frame**. The laser sits **0.11 m above base_link**, so that was ~0.46 m above the ground — far over the walls, catching people/background → noise.

Fixed slice (`docker/config/pointcloud_to_laserscan_indoor.yaml`):
```yaml
min_height: -0.08   # ~0.03 m above ground (above the floor)
max_height:  0.06   # ~0.17 m above ground (below the ~0.20 m wall top)
```
**Verify on the car and nudge:** bag `/livox/lidar`, look at the z of wall hits; if walls are taller/shorter or base_link height differs, adjust these two numbers. Symptom of too-tight: `/scan` has gaps / dropouts on straights. Symptom of too-loose: distant clutter reappears.

### 2. Car won't drive straight without holding steer (pulls right) — mechanical
This is a **servo neutral/trim** bias, not software. The constant counter-steer injects zig-zag into wheel odom and degrades every mapper. **Fix the servo trim so the car tracks straight hands-off before judging either SLAM backend.** Until then, Cartographer's correlative scan matching (`use_online_correlative_scan_matching = true`) and the EKF (feeding `/odometry/filtered`, not raw VESC `/odom`) absorb more of it than SLAM Toolbox did.

### 3. Stop-and-go exaggerates noise — drive smooth, and the config helps
Mapping while repeatedly stopping corrupts odom and piles up redundant scans. Two mitigations are already set:
- Cartographer **motion filter** skips inserting nodes when nearly stationary (`max_distance_meters 0.05`, `max_angle_radians 0.12`, `max_time_seconds 5.0`) → standing still no longer pollutes the graph.
- Cartographer uses the **EKF-fused** odom prior + scan matching, so a single bad stop doesn't permanently warp the map (the pose graph re-optimizes).

**Operationally:** do ONE slow, continuous lap (walking pace), minimal stops, close the loop. If you must stop, stop *briefly* and resume smoothly.

---

## Frame ownership (must be exactly this)

```
map  --(Cartographer)-->  odom  --(EKF)-->  base_link  --(static)-->  laser
```
- EKF publishes `odom→base_link` only.
- Cartographer publishes `map→odom` only (`published_frame = "odom"`, `provide_odom_frame = false`).
- Never run SLAM Toolbox and Cartographer at once — only one node may publish `map→odom`. (`bringup` suppresses SLAM Toolbox when `use_cartographer:=true`.)

---

## Runbook — Cartographer mapping (terminal by terminal)

All inside the container; source first:
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
```

**T1 — stack with EKF + Cartographer**
```bash
ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true
```

**T2 — preflight / health**
```bash
/race_ws/scripts/preflight_manual_map_logger.sh
ros2 topic hz /scan                       # steady ~10 Hz, no big gaps
ros2 topic hz /odometry/filtered          # EKF alive
ros2 run tf2_ros tf2_echo map base_link   # must update smoothly (wait 10-30 s)
```
Do not map until `map→base_link` is smooth.

**T3 — drive ONE slow continuous lap** with the RC (deadman held), close the loop, then stop.

**T4 — save the map (both formats)**
```bash
/race_ws/scripts/cartographer_save_map.sh track1 /race_ws/maps
# -> /race_ws/maps/track1.pbstream  (Cartographer pure localization)
# -> /race_ws/maps/track1.pgm/.yaml (Nav2 / AMCL / RViz)
```
`cartographer_save_map.sh` calls `finish_trajectory` + `write_state`, then `nav2 map_saver_cli`. After it runs, that Cartographer session can't map again — relaunch to remap.

**Race day — pure localization on the saved map (no remapping):**
```bash
ros2 launch /race_ws/launch/cartographer_2d.launch.py \
  configuration_basename:=roboracer_2d_localization.lua \
  load_state_filename:=/race_ws/maps/track1.pbstream
```
(or run the full stack with `use_cartographer:=true` and add the two args via your launch include.)

---

## A/B procedure (same track, same laps, same speed)

Run each backend on the **same** physical lap path, walking pace, one continuous lap.

- **A — SLAM Toolbox:** `ros2 launch /race_ws/bringup.launch.py use_slam:=true`
- **B — Cartographer:** `ros2 launch /race_ws/bringup.launch.py use_cartographer:=true`

For each, record a bag of `/scan /tf /tf_static /odometry/filtered /map` and save the map.

### Objective comparison checklist

| Metric | How to measure | Better = |
|---|---|---|
| **Loop-closure offset** | Drive start→full lap→back to start mark. Compare `map→base_link` x,y at start vs end (`tf2_echo`). | smaller gap |
| **Map wall thickness** | Open saved `.pgm` (or RViz `/map`); measure apparent wall thickness in px × resolution (0.05 m/px). | thinner, crisper |
| **Pose jitter on a straight** | On a straight segment, log `map→base_link` yaw/position; compute stddev. | lower stddev |
| **Relocalization after spin** | Do a quick in-place U-turn/spin; time until pose snaps back consistent. | faster, no jump |
| **CPU load on Pi** | `top` / `/diagnostics` during mapping. | sustainable |
| **Repeatability** | Map the loop twice; overlay the two `.pgm`. | maps agree |

Decision: if Cartographer wins loop-closure offset + wall thickness + jitter with acceptable Pi CPU, drop SLAM Toolbox for competition (keep it in the image as a fallback flag).

---

## Gotchas

- **Config load fails** → make sure `config/cartographer/` contains only `roboracer_2d*.lua` (no local `map_builder.lua`/`trajectory_builder.lua`; those shadow Cartographer's required defaults).
- **Two parents for base_link / TF error** → `published_frame` must be `odom`, not `base_link`.
- **`/scan` gaps after the height fix** → slice too tight for car tilt; widen `max_height` a couple cm.
- **No `map→odom`** → car hasn't moved enough yet, or `/odometry/filtered` missing.
- **Pursuit diverges on race day** → raceline is in `map` but Cartographer/localization not running; keep `use_cartographer:=true` (or localization launch) up.
