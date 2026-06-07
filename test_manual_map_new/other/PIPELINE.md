# Multi-run map processing (professor logic)

Five separate drives in `manual_map_*.csv` → one cleaned corridor map.

## Steps (matches lecture spec)

| Step | What we do |
|------|------------|
| 1 | **Start per run** — row + `time_sec` + `(x,y)` when you began moving (`run_starts.yaml` or auto-detect). |
| 2 | **Time align** — `t_rel = time_sec - start_time` for each run. |
| 3 | **Pool bins** — every `--bin-sec` seconds (default 1 s), merge samples from **all 5 runs** into the same bin. |
| 4 | **Axis choice** — PCA on moving points: **travel** = larger variance axis, **wall** = orthogonal. Your hallway: **travel = x**, **wall = y**. |
| 5 | **Ghost-wall filter** — inside each bin, drop samples with **wall axis** outside **±2σ** (only **y** when driving along **x**). |
| 6 | **Aggregate** — **mode** on **travel** axis, **minimum** on **wall** axis. |
| 7 | **Plot** — `corridor_map.png` in map frame; `corridor_map_relative.png` in aligned corridor frame. |

## Run

```bash
cd test_manual_map_new
MPLBACKEND=Agg python3 process_multi_run_map.py --bin-sec 1.0 --n-sd 2.0 --common-origin median
```

- `--common-origin median` — same physical start line for all runs’ `x_rel`/`y_rel` (recommended when you restarted at the same place).
- `--travel-axis x` — force if auto is wrong (your data: always **x**).

## Outputs

- `axis_detection.json` — PCA angles, variances, chosen travel/wall axes.
- `cleaned_bins.csv` — one row per time bin with `travel_mode_map`, `wall_min_map`, etc.
- `corridor_map.csv` — map polyline from time bins (the professor map).
- `_plots/corridor_map.png` — visualization.

## Your data (confirmed)

- Driving is mostly **+x** (PCA ≈ −169° → travel **x**).
- Lateral spread is **y** (~0.1–0.6 m) → filter **y** for ghost walls.
- Odom start positions differ per run; use `--common-origin median` or set one pose in `run_starts.yaml`.
