# Visualization Optimizer — map CSV → TUM → raceline → pure pursuit

This note matches **`Visualization Optimizer.ipynb`** in this folder: how to take a **`manual_map_logger`** capture in **`map`** (SLAM), clean it, convert it for **TUM `global_racetrajectory_optimization`**, and run it on the car with **pure pursuit** in the same frame.

---

## 1. What you have after a good logging run

Logger CSV columns (header row):

`time_sec`, `frame_id`, `x`, `y`, `z`, `yaw_rad`, `left_wall_m`, `right_wall_m`, `scan_stamp_sec`

- **`frame_id`** should be **`map`** for the competition-style pipeline.
- **`x`, `y`, `yaw_rad`** are the driven path in **`map`** (global-ish while SLAM is healthy).
- **Walls** are heuristic ranges from **`/scan`** windows (TUM uses them as track half-width hints).

**Sanity on the car (or laptop):**

```bash
wc -l map_hall_....csv
head -5 map_hall_....csv
```

Expect **hundreds+** lines and **non-constant** `x`, `y` over the lap.

**Optional geometry check:**

```bash
python3 << 'PY'
import csv, math
rows = list(csv.DictReader(open("map_hall_....csv")))
xs = [float(r["x"]) for r in rows]; ys = [float(r["y"]) for r in rows]
length = sum(math.hypot(xs[i]-xs[i-1], ys[i]-ys[i-1]) for i in range(1, len(xs)))
steps = [math.hypot(xs[i]-xs[i-1], ys[i]-ys[i-1]) for i in range(1, len(xs))]
print("rows", len(rows), "path_len_m", round(length, 2), "max_step_m", round(max(steps), 3), "at_i", steps.index(max(steps)) + 1)
PY
```

If **`max_step_m` ≫ 0.3–0.5** at **`at_i == 1`**, that is usually a **SLAM first-fix jump** (not real motion).

---

## 2. Startup spike (first row) — trim before optimizer

After SLAM publishes **`map` → `odom`**, the first logged pose can sit near the origin while the **second** sample snaps to the true map pose → a **multi-meter fake edge** in the polyline.

**Quick check after dropping the first row:**

```bash
python3 << 'PY'
import csv, math
rows = list(csv.DictReader(open("map_hall_....csv")))[1:]
xs = [float(r["x"]) for r in rows]; ys = [float(r["y"]) for r in rows]
length = sum(math.hypot(xs[i]-xs[i-1], ys[i]-ys[i-1]) for i in range(1, len(xs)))
steps = [math.hypot(xs[i]-xs[i-1], ys[i]-ys[i-1]) for i in range(1, len(xs))]
print("rows", len(rows), "path_len_m", round(length, 2), "max_step_m", round(max(steps), 3))
PY
```

You want **`max_step_m`** in line with speed and logger rate (often **under ~0.2 m** for slow RC mapping at 20 Hz).

**Automated trim in conversion:** use **`--drop-first 1`** on the repo script (see §3).

---

## 3. Copy CSV off the car

On the **Pi host**:

```bash
docker cp roboracer_t7:/race_ws/logs/map_hall_YYYYMMDD_HHMMSS.csv ~/
```

Then **`scp`** to your laptop and place under **`test_manual_map_logger/`** (or `raceline_data/inputs/...`) as you prefer.

---

## 4. Convert to TUM track CSV

From **repo root** (or in the container where **`/race_ws/scripts/`** exists):

```bash
python3 scripts/manual_map_csv_to_tum_track.py \
  test_manual_map_logger/map_hall_20260514_211326.csv \
  -o raceline_data/inputs/tracks/from_manual_map.csv \
  --drop-first 1 \
  --comment
```

Output columns: **`x_m`, `y_m`, `w_tr_right_m`, `w_tr_left_m`** (TUM `import_track.py` style).

- **`--drop-first 1`**: drop the first valid row after parsing (fixes typical SLAM startup snap).
- **`--step N`**: optional downsampling if the optimizer is slow.
- **`--comment`**: leading `#` line (safe for `numpy.loadtxt`).

---

## 5. Run TUM global racetrajectory optimization (laptop)

Use your team’s checkout of **`global_racetrajectory_optimization`** (also vendored under **`/race_ws/tum_global_racetrajectory_optimization`** in the Docker image). Point **`import_track.py`** (or your wrapper) at **`from_manual_map.csv`** (or the path you chose), set track name / bounds per TUM docs, and export the optimized trajectory (e.g. **`traj_race_cl.csv`** or your naming).

Use the **Visualization Optimizer** notebook to plot:

- **`x` / `y` vs index** (raw logger CSV)
- **Scatter `y` vs `x`** (centerline shape)
- Optional: **walls vs index** (sanity vs corridor)

Do the same plots on the **optimized** CSV to confirm smoothing and no self-intersections.

---

## 6. On-car pure pursuit in `map`

Copy the **optimized** CSV into the image, e.g. **`/race_ws/racelines/my_race.csv`**.

**Bringup** (SLAM still on so **`map` → `base_link`** exists):

```bash
ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_pure_pursuit \
  use_slam:=true \
  pursuit_world_frame:=map \
  raceline_csv:=/race_ws/racelines/my_race.csv
```

**`pursuit_world_frame:=map`** must match the frame in which the raceline and the mapping log were produced.

For a **real race**, you will usually move from **online async mapping** to **saved map + localization**; see **`docs/COMPETITION_RACELINE_PIPELINE.md`** for the full stack picture.

---

## 8. Presentation slide (16×9 PNG)

From repo root (or path to script):

```bash
MPLCONFIGDIR=/tmp/mpl python3 test_manual_map_logger/plot_presentation_map.py \
  test_manual_map_logger/map_hall_20260514_211326.csv --dpi 150
```

Optional: **`--corridor off`** for centerline-only; **`--corridor raw`** reproduces the old noisy sketch. Default is **`smooth`**. **`--no-closure-chord`** hides the start–end dashed gap line.

Writes **`test_manual_map_logger/_plots/<stem>_presentation_16x9.png`**: top-down path in **`map`**, progress colormap, optional smoothed scan corridor, start–end gap chord, and a short “why this works” text block for slides.

---

## 8b. Extra slides (metrics + raceline overlay)

```bash
MPLCONFIGDIR=/tmp/mpl python3 test_manual_map_logger/plot_presentation_extras.py \
  test_manual_map_logger/map_hall_20260514_211326.csv \
  --raceline racelines/your_tum_output.csv
```

Omit **`--raceline`** until you have a real TUM export. Outputs **`_plots/<stem>_extra_*.png`**: arc length vs time, yaw, curvature, step histogram, scan lag, raw-vs-trim XY, and XY with optional raceline dashed overlay.

---

## 9. Reference

- **`docs/COMPETITION_RACELINE_PIPELINE.md`** — end-to-end competition pipeline.
- **`docs/MANUAL_MAP_LOGGER.md`** — logger parameters and topics.
- **`scripts/manual_map_csv_to_tum_track.py`** — conversion + **`--drop-first`**.
