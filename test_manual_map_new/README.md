# Multi-run manual map processing (5 drives)

Straight corridor runs in **`map`** frame (`manual_map_1.csv` … `manual_map_5.csv`).

## Axis convention (your data)

| Axis | Role | Why |
|------|------|-----|
| **x** | **Travel** (along corridor) | x span ~1.5–2 m, PCA ≈ ±180° |
| **y** | **Wall** (lateral / ghost filter) | y span ~0.1–0.6 m |

Driving is mostly **+x**; filter **y** outliers (>2σ) to drop ghost walls.

## Straight-track map (5 runs → one track, notebook-style)

```bash
MPLBACKEND=Agg python3 visualize_straight_track.py --s-bin-m 0.05
```

- Distance bins **5 cm** along track (`--s-bin-m 0.05`), not time
- `_plots/straight_track_walls_xy.png` — black center / blue left / red right + merged lines
- `straight_track_map.csv` — one row per 5 cm

## Process (time bins, professor spec)

```bash
cd test_manual_map_new
MPLBACKEND=Agg python3 process_multi_run_map.py --bin-sec 1.0 --n-sd 2.0 --map-bin-m 0.05
```

Outputs:

- **`_plots/corridor_map.png`** — **the map**: centerline + left/right walls + corridor fill (map frame)
- **`_plots/corridor_map_relative.png`** — same corridor in each-run-aligned frame (x along corridor)
- `corridor_map.csv` — spatial stations every `--map-bin-m` along travel: center, L/R walls, width
- `run_starts_detected.json` — start row/time/position per run
- `run_segments_aligned.csv` — pooled moving samples with `x_rel`, `y_rel`, `x_map_m`, `y_map_m`
- `cleaned_bins.csv` — per **time** bin: `x_rel_mode`, `y_rel_min`, wall mins (professor’s time grouping)
- `_plots/multi_run_xy.png`, `binned_axes_vs_time.png`, `binned_wall_distances.png`

Map frame uses **median start** across runs as origin shift (`x_map = x_rel + ref_x`).

## Override start (manual same start line)

Edit `run_starts.yaml` then re-run:

```yaml
runs:
  manual_map_1.csv:
    row: 7
    time_sec: 1779854243.498
    x: 1.227861
    y: -0.243511
```

## Flags

| Flag | Default | Meaning |
|------|---------|---------|
| `--travel-axis` | `auto` | `x` or `y` |
| `--bin-sec` | `1.0` | Group all runs every N seconds from each start |
| `--map-bin-m` | `0.05` | Spatial map resolution along corridor [m] |
| `--n-sd` | `2.0` | Drop wall-axis samples outside ±2σ |

## Foxglove / RViz

This script cleans **logged CSVs** offline. Live SLAM viz still uses `/map`, `/scan`, `/tf` on the car.
