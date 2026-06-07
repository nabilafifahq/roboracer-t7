#!/usr/bin/env python3
"""
Aggregate multiple manual_map_logger runs (same corridor, separate starts).

Pipeline (per professor spec):
  1. Specify start pose + time per run (auto-detect or run_starts.yaml).
  2. Align time to t=0 at start; bin every --bin-sec across all runs.
  3. Auto-detect travel vs wall axis (PCA); override with --travel-axis.
  4. Per bin: drop wall-axis samples > 2 SD from mean (ghost walls / lateral outliers).
  5. Per bin: min on wall axis (lateral extent), mode on travel axis (along-track).
  6. Also aggregate min(left_wall_m), min(right_wall_m) for corridor width.

Outputs: cleaned_bins.csv, corridor_map.csv, run_segments_aligned.csv,
         plots including corridor_map.png (the map).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for c in ("x", "y", "yaw_rad", "left_wall_m", "right_wall_m", "time_sec"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def detect_travel_wall_axes(df: pd.DataFrame, moving_min_step: float = 0.005) -> tuple[str, str, dict]:
    """
    Return (travel_axis, wall_axis, report).

    PCA on moving points: largest variance ≈ along-track (travel);
    smallest ≈ lateral (wall / ghost-wall filter axis).
    """
    d = df.copy()
    step = np.hypot(d["x"].diff(), d["y"].diff())
    mov = step > moving_min_step
    d = d.loc[mov.fillna(False)]
    if len(d) < 5:
        return "x", "y", {"reason": "too_few_points", "travel_axis": "x", "wall_axis": "y"}

    pts = np.column_stack([d["x"].to_numpy(), d["y"].to_numpy()])
    pts -= pts.mean(axis=0)
    cov = np.cov(pts.T)
    w, v = np.linalg.eigh(cov)
    i_max, i_min = int(np.argmax(w)), int(np.argmin(w))
    ang = math.degrees(math.atan2(v[1, i_max], v[0, i_max]))
    travel = "x" if abs(ang) < 45 or abs(ang) > 135 else "y"
    wall = "y" if travel == "x" else "x"
    var_x, var_y = float(cov[0, 0]), float(cov[1, 1])
    report = {
        "travel_axis": travel,
        "wall_axis": wall,
        "pca_travel_angle_deg": ang,
        "variance_x": var_x,
        "variance_y": var_y,
        "variance_along_travel": float(w[i_max]),
        "variance_along_wall": float(w[i_min]),
        "rule": "travel = axis with larger PCA eigenvalue (along-track); wall = orthogonal",
    }
    return travel, wall, report


def auto_start_row(df: pd.DataFrame, min_step_m: float = 0.005) -> int:
    """First index where pose moves after initial freeze."""
    x, y = df["x"].to_numpy(), df["y"].to_numpy()
    for i in range(1, len(df)):
        if math.hypot(x[i] - x[i - 1], y[i] - y[i - 1]) >= min_step_m:
            return i
    return 0


def load_starts(path: Path | None, runs: dict[str, pd.DataFrame], min_step_m: float) -> dict[str, dict]:
    out: dict[str, dict] = {}
    file_cfg: dict = {}
    if path and path.is_file():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        file_cfg = raw.get("runs", raw)

    for name, df in runs.items():
        if name in file_cfg:
            row = file_cfg[name]
            idx = int(row.get("row", auto_start_row(df, min_step_m)))
            out[name] = {
                "row": idx,
                "time_sec": float(row.get("time_sec", df.loc[idx, "time_sec"])),
                "x": float(row.get("x", df.loc[idx, "x"])),
                "y": float(row.get("y", df.loc[idx, "y"])),
            }
        else:
            idx = auto_start_row(df, min_step_m)
            out[name] = {
                "row": idx,
                "time_sec": float(df.loc[idx, "time_sec"]),
                "x": float(df.loc[idx, "x"]),
                "y": float(df.loc[idx, "y"]),
            }
    return out


def apply_common_origin(
    starts: dict[str, dict],
    *,
    mode: str,
    runs: dict[str, pd.DataFrame],
) -> tuple[float, float]:
    """One map origin for all runs' _rel coords (same physical start line)."""
    if mode == "median":
        ox = float(np.median([st["x"] for st in starts.values()]))
        oy = float(np.median([st["y"] for st in starts.values()]))
    else:
        ref = starts.get(mode)
        if ref is None:
            raise ValueError(f"--common-origin run not found: {mode}")
        ox, oy = ref["x"], ref["y"]
    for st in starts.values():
        st["origin_x"] = ox
        st["origin_y"] = oy
    return ox, oy


def filter_2sd(series: pd.Series, n_sd: float = 2.0) -> pd.Series:
    m = series.mean()
    s = series.std(ddof=0)
    if s < 1e-9 or not np.isfinite(s):
        return pd.Series(True, index=series.index)
    return (series - m).abs() <= n_sd * s


def mode_float(vals: pd.Series) -> float:
    v = vals.dropna()
    if v.empty:
        return float("nan")
    # Histogram mode for floats (5 mm bins)
    bin_w = 0.005
    lo, hi = v.min(), v.max()
    if hi - lo < bin_w:
        return float(v.median())
    edges = np.arange(lo, hi + bin_w, bin_w)
    hist, edges = np.histogram(v, bins=edges)
    i = int(hist.argmax())
    return float(0.5 * (edges[i] + edges[i + 1]))


def process_runs(
    runs: dict[str, pd.DataFrame],
    starts: dict[str, dict],
    *,
    travel_axis: str,
    wall_axis: str,
    bin_sec: float,
    n_sd: float,
    moving_min_step: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_df = align_segments(runs, starts, travel_axis, wall_axis, moving_min_step)
    all_df["bin"] = (all_df["t_rel"] // bin_sec).astype(int)
    travel_col, wall_col = travel_axis, wall_axis
    rows: list[dict] = []

    travel_rel = f"{travel_col}_rel"
    wall_rel = f"{wall_col}_rel"

    for bin_id, grp in all_df.groupby("bin"):
        wall_vals = grp[wall_rel]
        keep = filter_2sd(wall_vals, n_sd)
        g = grp.loc[keep]
        if len(g) < 1:
            continue
        t_mode = mode_float(g[travel_rel])
        w_min = float(g[wall_rel].min())
        row = {
            "bin": int(bin_id),
            "t_center_sec": float(bin_id * bin_sec + 0.5 * bin_sec),
            "n_raw": int(len(grp)),
            "n_kept": int(len(g)),
            # Professor outputs (relative to common / per-run origin):
            "travel_mode_rel": t_mode,
            "wall_min_rel": w_min,
            f"{travel_axis}_rel_mode": t_mode,
            f"{wall_axis}_rel_min": w_min,
            f"{wall_axis}_rel_max": float(g[wall_rel].max()),
            f"{wall_axis}_rel_median": float(g[wall_rel].median()),
            # Same aggregates in map frame (x,y columns):
            "travel_mode_map": mode_float(g[travel_col]),
            "wall_min_map": float(g[wall_col].min()),
            f"{travel_axis}_mode": mode_float(g[travel_col]),
            f"{wall_axis}_min": float(g[wall_col].min()),
            f"{wall_axis}_max": float(g[wall_col].max()),
            f"{wall_axis}_median": float(g[wall_col].median()),
            "left_wall_min_m": float(g["left_wall_m"].min()) if g["left_wall_m"].notna().any() else math.nan,
            "right_wall_min_m": float(g["right_wall_m"].min()) if g["right_wall_m"].notna().any() else math.nan,
            "travel_axis": travel_axis,
            "wall_axis": wall_axis,
        }
        rows.append(row)

    bins_df = pd.DataFrame(rows).sort_values("bin").reset_index(drop=True)
    segments_df = all_df.copy()
    return bins_df, segments_df


def align_segments(
    runs: dict[str, pd.DataFrame],
    starts: dict[str, dict],
    travel_axis: str,
    wall_axis: str,
    moving_min_step: float,
) -> pd.DataFrame:
    """All runs trimmed, moving-only, with _rel coords from each start."""
    travel_col, wall_col = travel_axis, wall_axis
    pieces: list[pd.DataFrame] = []
    for run_name, df in runs.items():
        st = starts[run_name]
        seg = df.iloc[st["row"] :].copy()
        seg = seg.loc[filter_moving(seg, moving_min_step)].copy()
        if seg.empty:
            continue
        seg["run"] = run_name
        seg["t_rel"] = seg["time_sec"] - st["time_sec"]
        seg["start_x"] = st["x"]
        seg["start_y"] = st["y"]
        ox = st.get("origin_x", st["x"])
        oy = st.get("origin_y", st["y"])
        seg["origin_x"] = ox
        seg["origin_y"] = oy
        seg[f"{travel_col}_rel"] = seg[travel_col] - ox
        seg[f"{wall_col}_rel"] = seg[wall_col] - oy
        pieces.append(seg)
    if not pieces:
        raise ValueError("No moving samples after start trim")
    return pd.concat(pieces, ignore_index=True)


def build_corridor_map(
    segments_df: pd.DataFrame,
    *,
    travel_axis: str,
    wall_axis: str,
    map_bin_m: float,
    n_sd: float,
    ref_origin: tuple[float, float],
) -> pd.DataFrame:
    """
    Spatial map along corridor: bin by travel (_rel), 2σ filter on wall axis,
    mode travel / min wall / min left-right ranges per station.
    """
    tc, wc = travel_axis, wall_axis
    tr, wr = f"{tc}_rel", f"{wc}_rel"
    d = segments_df.copy()
    d = d[np.isfinite(d[tr]) & np.isfinite(d[wr])]
    if d.empty:
        return pd.DataFrame()

    lo, hi = d[tr].min(), d[tr].max()
    edges = np.arange(lo, hi + map_bin_m, map_bin_m)
    if len(edges) < 2:
        edges = np.array([lo, lo + map_bin_m])

    ref_x, ref_y = ref_origin
    rows: list[dict] = []

    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        grp = d[(d[tr] >= a) & (d[tr] < b)]
        if grp.empty:
            continue
        keep = filter_2sd(grp[wr], n_sd)
        g = grp.loc[keep]
        if len(g) < 1:
            continue

        s_center = 0.5 * (a + b)
        y_med = float(g[wr].median())
        x_map = s_center + ref_x
        y_map = y_med + ref_y
        psi = float(g["yaw_rad"].median()) if g["yaw_rad"].notna().any() else 0.0
        nx, ny = -math.sin(psi), math.cos(psi)
        cx = float(g["x"].median())
        cy = float(g["y"].median())

        lw = float(g["left_wall_m"].min()) if g["left_wall_m"].notna().any() else math.nan
        rw = float(g["right_wall_m"].min()) if g["right_wall_m"].notna().any() else math.nan

        # Wall hits from pose + left normal (left +n, right -n)
        lx = cx + nx * lw if math.isfinite(lw) else math.nan
        ly = cy + ny * lw if math.isfinite(lw) else math.nan
        rx = cx - nx * rw if math.isfinite(rw) else math.nan
        ry = cy - ny * rw if math.isfinite(rw) else math.nan

        rows.append(
            {
                "s_along_rel_m": s_center,
                "x_rel_m": s_center,
                "y_rel_center_m": y_med,
                "y_rel_min_m": float(g[wr].min()),
                "y_rel_max_m": float(g[wr].max()),
                "x_map_m": x_map,
                "y_map_m": y_map,
                "yaw_rad": psi,
                "left_wall_m": lw,
                "right_wall_m": rw,
                "corridor_width_m": (lw + rw) if math.isfinite(lw) and math.isfinite(rw) else math.nan,
                "left_x_map": lx,
                "left_y_map": ly,
                "right_x_map": rx,
                "right_y_map": ry,
                "n_samples": int(len(g)),
                "n_runs": int(g["run"].nunique()),
            }
        )

    return pd.DataFrame(rows)


def bins_to_corridor_map(
    bins_df: pd.DataFrame,
    travel_axis: str,
    wall_axis: str,
) -> pd.DataFrame:
    """Map polyline from time bins: mode(travel), min(wall) per professor spec."""
    if bins_df.empty:
        return pd.DataFrame()
    tc, wc = travel_axis, wall_axis
    t_col = "travel_mode_map" if "travel_mode_map" in bins_df.columns else f"{tc}_mode"
    w_min = "wall_min_map" if "wall_min_map" in bins_df.columns else f"{wc}_min"
    w_max = f"{wc}_max"
    return pd.DataFrame(
        {
            "t_center_sec": bins_df["t_center_sec"],
            f"{tc}_m": bins_df[t_col],
            f"{wc}_min_m": bins_df[w_min],
            f"{wc}_max_m": bins_df[w_max],
            "left_wall_min_m": bins_df["left_wall_min_m"],
            "right_wall_min_m": bins_df["right_wall_min_m"],
            "n_kept": bins_df["n_kept"],
        }
    ).sort_values("t_center_sec")


def filter_moving(df: pd.DataFrame, min_step_m: float) -> pd.Series:
    x, y = df["x"].to_numpy(), df["y"].to_numpy()
    step = np.concatenate([[min_step_m + 1], np.hypot(np.diff(x), np.diff(y))])
    return pd.Series(step > min_step_m, index=df.index)


def plot_corridor_map(
    out_dir: Path,
    segments_df: pd.DataFrame,
    time_map_df: pd.DataFrame,
    travel_axis: str,
    wall_axis: str,
    n_sd: float,
    bin_sec: float,
) -> None:
    """Main map: time bins → 2σ wall filter → mode(travel), min(wall)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tc, wc = travel_axis, wall_axis
    tr, wr = f"{tc}_rel", f"{wc}_rel"

    d = segments_df.copy()
    keep_all = filter_2sd(d[wr], n_sd)
    d_f = d.loc[keep_all]

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.scatter(d_f["x"], d_f["y"], s=6, c="0.75", alpha=0.35, label="training (2σ wall filter)", zorder=1)

    if not time_map_df.empty and f"{tc}_m" in time_map_df.columns:
        xm = time_map_df[f"{tc}_m"]
        ymin = time_map_df[f"{wc}_min_m"]
        ymax = time_map_df[f"{wc}_max_m"]
        ax.fill_between(xm, ymin, ymax, color="#c8e6c9", alpha=0.45, label=f"corridor ({wc} min…max)", zorder=2)
        ax.plot(xm, ymin, color="#c00000", lw=2, label=f"{wc} min (professor)", zorder=4)
        ax.plot(xm, ymax, color="#1f4e79", lw=1.5, label=f"{wc} max (kept)", zorder=3)
        ax.plot(xm, ymin, "ko-", ms=5, lw=1.5, label=f"{tc} mode + {wc} min", zorder=6)

    ax.set_aspect("equal")
    ax.grid(True, alpha=0.35)
    ax.legend(loc="best", fontsize=8)
    ax.set_xlabel(f"{tc} map [m]  (travel axis)")
    ax.set_ylabel(f"{wc} map [m]  (wall axis)")
    ax.set_title(
        f"Cleaned map — 5 runs, bin={bin_sec}s\n"
        f"travel={tc}: mode | wall={wc}: ±{n_sd}σ then min"
    )
    fig.savefig(out_dir / "corridor_map.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(d_f[tr], d_f[wr], s=6, c="0.75", alpha=0.4, label="samples (2σ)")
    fig.savefig(out_dir / "corridor_map_relative.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_corridor_map_relative(
    out_dir: Path,
    bins_df: pd.DataFrame,
    travel_axis: str,
    wall_axis: str,
    n_sd: float,
    bin_sec: float,
) -> None:
    tc, wc = travel_axis, wall_axis
    if bins_df.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(
        bins_df["travel_mode_rel"],
        bins_df["wall_min_rel"],
        bins_df[f"{wc}_rel_max"],
        color="#bbdefb",
        alpha=0.5,
    )
    ax.plot(
        bins_df["travel_mode_rel"],
        bins_df["wall_min_rel"],
        "ko-",
        ms=6,
        label=f"mode({tc}), min({wc})",
    )
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_xlabel(f"{tc} rel [m] (from common origin)")
    ax.set_ylabel(f"{wc} rel [m]")
    ax.set_title(f"Time bins {bin_sec}s — ±{n_sd}σ on {wc}, then min/mode")
    fig.savefig(out_dir / "corridor_map_relative.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_outputs(
    out_dir: Path,
    runs: dict[str, pd.DataFrame],
    starts: dict[str, dict],
    bins_df: pd.DataFrame,
    segments_df: pd.DataFrame,
    map_df: pd.DataFrame,
    travel_axis: str,
    wall_axis: str,
    n_sd: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tc, wc = travel_axis, wall_axis

    fig, ax = plt.subplots(figsize=(9, 6))
    for name, df in runs.items():
        st = starts[name]
        ax.scatter(df["x"], df["y"], s=8, alpha=0.5, label=name)
        ax.scatter(st["x"], st["y"], s=120, marker="*", zorder=5)
    if not bins_df.empty and "travel_mode_map" in bins_df.columns:
        ax.plot(
            bins_df["travel_mode_map"],
            bins_df["wall_min_map"],
            "ko-",
            ms=5,
            lw=1.8,
            label="cleaned (mode x, min y)",
        )
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(f"5 runs raw + cleaned centerline (travel={tc}, wall={wc})")
    fig.savefig(out_dir / "multi_run_xy.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    wc0 = f"{wc}_rel_min" if f"{wc}_rel_min" in bins_df.columns else f"{wc}_min"
    wc1 = f"{wc}_rel_max" if f"{wc}_rel_max" in bins_df.columns else f"{wc}_max"
    axes[0].plot(bins_df["t_center_sec"], bins_df[wc0], "b.-", label=f"{wc} rel min")
    axes[0].plot(bins_df["t_center_sec"], bins_df[wc1], "r.-", label=f"{wc} rel max")
    axes[0].set_ylabel(f"{wc} [m]")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f"Wall axis ({wc}) after {n_sd}σ filter")

    tc_col = f"{tc}_rel_mode" if f"{tc}_rel_mode" in bins_df.columns else f"{tc}_mode"
    axes[1].plot(bins_df["t_center_sec"], bins_df[tc_col], "k.-", label=f"{tc} rel mode")
    axes[1].set_ylabel(f"{tc} [m]")
    axes[1].set_xlabel("time since start [s] (binned)")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    fig.savefig(out_dir / "binned_axes_vs_time.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(bins_df["t_center_sec"], bins_df["left_wall_min_m"], label="min left_wall")
    ax.plot(bins_df["t_center_sec"], bins_df["right_wall_min_m"], label="min right_wall")
    ax.set_xlabel("time since start [s]")
    ax.set_ylabel("[m]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title("Min wall distances per time bin (all runs)")
    fig.savefig(out_dir / "binned_wall_distances.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--glob", default="manual_map_*.csv")
    ap.add_argument("--starts", type=Path, default=None, help="run_starts.yaml")
    ap.add_argument("--bin-sec", type=float, default=1.0, help="Time bin width [s]")
    ap.add_argument("--n-sd", type=float, default=2.0, help="Wall-axis outlier cutoff (SD)")
    ap.add_argument("--travel-axis", choices=("x", "y", "auto"), default="auto")
    ap.add_argument("--moving-min-step", type=float, default=0.005)
    ap.add_argument("--plot-dir", type=Path, default=None)
    ap.add_argument("--map-bin-m", type=float, default=0.05, help="Optional spatial bins [m] (extra CSV)")
    ap.add_argument(
        "--common-origin",
        default=None,
        help="Align all runs to one origin: 'median' or run csv name e.g. manual_map_5.csv",
    )
    args = ap.parse_args()

    paths = sorted(args.data_dir.glob(args.glob))
    if not paths:
        raise SystemExit(f"No files matching {args.glob} in {args.data_dir}")

    runs = {p.name: load_csv(p) for p in paths}
    starts_path = args.starts or (args.data_dir / "run_starts.yaml")
    starts = load_starts(starts_path if starts_path.is_file() else None, runs, args.moving_min_step)
    common_origin = None
    if args.common_origin:
        common_origin = apply_common_origin(starts, mode=args.common_origin, runs=runs)

    combined = pd.concat(runs.values(), ignore_index=True)
    auto_travel, auto_wall, axis_report = detect_travel_wall_axes(combined, args.moving_min_step)
    travel = auto_travel if args.travel_axis == "auto" else args.travel_axis
    wall = "y" if travel == "x" else "x"
    axis_report["chosen_travel_axis"] = travel
    axis_report["chosen_wall_axis"] = wall
    axis_report["filter"] = f"±{args.n_sd} SD on {wall} only (ghost walls)"
    axis_report["per_bin"] = f"mode({travel}), min({wall})"

    segments_df = align_segments(runs, starts, travel, wall, args.moving_min_step)

    bins_df, _ = process_runs(
        runs,
        starts,
        travel_axis=travel,
        wall_axis=wall,
        bin_sec=args.bin_sec,
        n_sd=args.n_sd,
        moving_min_step=args.moving_min_step,
    )

    time_map_df = bins_to_corridor_map(bins_df, travel, wall)

    ref_x = float(np.median([st.get("origin_x", st["x"]) for st in starts.values()]))
    ref_y = float(np.median([st.get("origin_y", st["y"]) for st in starts.values()]))
    spatial_df = build_corridor_map(
        segments_df,
        travel_axis=travel,
        wall_axis=wall,
        map_bin_m=args.map_bin_m,
        n_sd=args.n_sd,
        ref_origin=(ref_x, ref_y),
    )

    out_dir = args.data_dir
    bins_path = out_dir / "cleaned_bins.csv"
    seg_path = out_dir / "run_segments_aligned.csv"
    map_path = out_dir / "corridor_map.csv"
    spatial_path = out_dir / "corridor_map_spatial.csv"
    axis_path = out_dir / "axis_detection.json"
    starts_out = out_dir / "run_starts_detected.json"
    bins_df.to_csv(bins_path, index=False)
    segments_df.to_csv(seg_path, index=False)
    time_map_df.to_csv(map_path, index=False)
    spatial_df.to_csv(spatial_path, index=False)
    axis_path.write_text(json.dumps(axis_report, indent=2), encoding="utf-8")
    starts_out.write_text(json.dumps(starts, indent=2), encoding="utf-8")

    plot_dir = args.plot_dir or (out_dir / "_plots")
    plot_corridor_map(plot_dir, segments_df, time_map_df, travel, wall, args.n_sd, args.bin_sec)
    plot_corridor_map_relative(plot_dir, bins_df, travel, wall, args.n_sd, args.bin_sec)
    plot_outputs(plot_dir, runs, starts, bins_df, segments_df, spatial_df, travel, wall, args.n_sd)

    print(f"Runs: {len(runs)}  travel_axis={travel}  wall_axis={wall}  (auto was {auto_travel}/{auto_wall})")
    print(f"Axis report: {axis_path}")
    print(f"Bin width: {args.bin_sec}s  wall filter: {args.n_sd} SD on '{wall}' only")
    print(f"Per bin: mode({travel}), min({wall})  — see {map_path}")
    print(f"Wrote {bins_path} ({len(bins_df)} bins)")
    print(f"Wrote {seg_path}")
    print(f"Wrote {starts_out}")
    if common_origin:
        print(f"Common origin: ({common_origin[0]:.3f}, {common_origin[1]:.3f})")
    print(f"Plots in {plot_dir}/  -> corridor_map.png")
    for name, st in starts.items():
        print(f"  {name}: row={st['row']} t={st['time_sec']:.3f} pos=({st['x']:.3f},{st['y']:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
