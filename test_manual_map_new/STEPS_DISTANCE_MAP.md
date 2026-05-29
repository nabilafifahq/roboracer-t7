# Straight-track map — step-by-step (honest)

This is exactly what `visualize_straight_track.py` does to merge **5 training CSVs** into **one smooth straight hallway map**.

**Why distance bins, not time:** You can drive slow or fast. Time bins mis-align runs; **distance along the hallway (s)** does not.

---

## Step 0 — Inputs

- Files: `manual_map_1.csv` … `manual_map_5.csv`
- Columns used: `time_sec`, `x`, `y`, `yaw_rad`, `left_wall_m`, `right_wall_m` (map frame)
- ~10 Hz logger rows when moving

---

## Step 1 — Load & numeric cleanup

- Read each CSV; coerce pose and wall columns to float.
- Drop rows missing `x`, `y`, `yaw_rad`.

---

## Step 2 — Start pose + time per run

Each drive is **separate** (not one continuous log).

- **Auto:** first row where position moves ≥ **5 mm** (`moving_min_step=0.005`).
- **Manual:** `run_starts.yaml` (row, `time_sec`, x, y).
- Saved to `run_starts_detected.json`.

We keep `time_sec` at start only for trimming; **binning does not use time**.

---

## Step 3 — Trim & moving-only

- Cut each run from its start row onward.
- Remove rows where step length ≤ 5 mm (idle/joystick noise at standstill).

---

## Step 4 — Common origin (same start line)

Your 5 runs have **different odom (x,y) at “start”** (map frame drift). You physically restarted at the same hallway line.

- Default: **`--common-origin median`** → one `(origin_x, origin_y)` for all runs.
- All “along / lateral” math is relative to this point.

**Honest limit:** This does not fix large odom jumps between sessions; it overlays drives in a best-effort shared frame. Tighter result → set the same `(x,y)` in `run_starts.yaml` for every run.

---

## Step 5 — Which axis is travel vs wall?

PCA on all moving points from all runs:

| Result (your hallway) | Meaning |
|----------------------|---------|
| **travel = x** | Variance along hallway ≈ **2.05 m²** |
| **wall = y** | Lateral spread ≈ **0.008 m²** |
| PCA angle ≈ **−169°** | Motion along **±x** |

Ghost-wall filtering is applied only on **y** (lateral), not on x.

Written to `axis_detection.json` / `pipeline_report.json`.

---

## Step 6 — Straight track frame (s, d)

- Estimate mean heading ψ from yaw (circular mean).
- For every point (center, left wall hit, right wall hit):

  ```
  s = along-track distance from common origin
  d = lateral offset from common origin
  ```

---

## Step 7 — Wall points (your notebook math)

Same as your visualizer:

```
nx = -sin(yaw),  ny = cos(yaw)
left  = (x, y) + (nx, ny) * left_wall_m
right = (x, y) - (nx, ny) * right_wall_m
```

Blue/red scatters in the plot are these hits, pooled from all 5 runs.

---

## Step 8 — Ghost-wall filter (2σ on lateral)

- On all pooled samples: remove points where **d** is outside **±2σ** of the mean (`--n-sd`, default **2.0**).
- Applied again **inside each distance bin** (local outliers).

This targets “ghost walls” that stick out sideways, not along-track noise.

---

## Step 9 — Distance bins (core aggregation)

- Bin width: **`--s-bin-m`** (default **0.05 m = 5 cm**).
- Bins are `[0, 0.05), [0.05, 0.10), …` along **s** (not seconds).
- Pool **all runs** in the same bin.
- Skip bin if fewer than **`--min-samples`** points (default 2).
- Optional: `--s-min-m 0` drops negative-s bins (pre-start clutter).

**Per bin (professor logic, distance-based):**

| Quantity | Rule |
|----------|------|
| Along-track station | `s` = bin center |
| Center lateral | **mode** of `d` (histogram mode, 5 mm bins) |
| Corridor extent | min / max of `d` |
| Left / right wall lateral | median of `left_d_m`, `right_d_m` |
| LiDAR ranges | min `left_wall_m`, min `right_wall_m` |

Output: `straight_track_map_raw.csv` — one row per **5 cm** of hallway.

---

## Step 10 — Smoothing

Raw bins are jagged (sparse bins, odom noise).

- Window: **`--smooth-window-m`** (default **0.25 m** → 5 bins at 5 cm).
- **Savitzky–Golay** (quadratic) on `d_mode`, `d_min`, `d_max`, `left_d`, `right_d` along s.
- Fallback: moving average if SciPy missing.
- Rebuild `(x, y)` and left/right wall polylines from smoothed track coordinates.

Output: `straight_track_map.csv` (smooth), plots use **bold** smooth lines.

---

## Step 11 — Plots & exports

| File | Content |
|------|---------|
| `_plots/straight_track_walls_xy.png` | Gray scatter + gray raw bin line + **black/blue/red smooth** walls |
| `_plots/straight_track_unwrapped_sd.png` | s vs d (straight racetrack side view) |
| `straight_track_points.csv` | All filtered sample points |
| `straight_track_map_raw.csv` | Distance-binned, not smoothed |
| `straight_track_map.csv` | Distance-binned + smoothed |
| `pipeline_report.json` | Parameters + axis detection + starts |

---

## Run command

```bash
cd test_manual_map_new
MPLBACKEND=Agg python3 visualize_straight_track.py \
  --s-bin-m 0.05 \
  --smooth-window-m 0.25 \
  --n-sd 2.0 \
  --common-origin median
```

**Tuning:**

- Finer map: `--s-bin-m 0.03`
- Smoother walls: `--smooth-window-m 0.40`
- Stricter ghost filter: `--n-sd 1.5`

---

## What we do *not* claim

- Not SLAM — offline merge of manual_map_logger CSVs.
- Not perfect global alignment if odom origin jumps between runs.
- Smoothing can round sharp corners (hallway is straight, so that is OK).
- Bins with 1 sample are dropped — gaps remain if no run covered that distance.
