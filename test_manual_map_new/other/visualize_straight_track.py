#!/usr/bin/env python3
"""
Merge manual_map training runs into one straight-racetrack wall map.

Same wall math as your single-run visualizer:
  nx, ny = -sin(yaw), cos(yaw)
  left  = (x, y) + (nx, ny) * left_wall_m
  right = (x, y) - (nx, ny) * right_wall_m

Runs are trimmed from each start, projected into a straight track frame
(s along hallway, d lateral), ghost walls removed (2σ on d), then binned every
--s-bin-m along track (default 5 cm).

Usage:
  cd test_manual_map_new
  MPLBACKEND=Agg python3 visualize_straight_track.py
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from process_multi_run_map import (
    align_segments,
    apply_common_origin,
    detect_travel_wall_axes,
    filter_2sd,
    load_csv,
    load_starts,
    mode_float,
)


def wall_scatter_xy(
    x: np.ndarray,
    y: np.ndarray,
    yaw: np.ndarray,
    w_l: np.ndarray,
    w_r: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    nx = -np.sin(yaw)
    ny = np.cos(yaw)
    left_x = np.where(np.isfinite(w_l), x + nx * w_l, np.nan)
    left_y = np.where(np.isfinite(w_l), y + ny * w_l, np.nan)
    right_x = np.where(np.isfinite(w_r), x - nx * w_r, np.nan)
    right_y = np.where(np.isfinite(w_r), y - ny * w_r, np.nan)
    return left_x, left_y, right_x, right_y


def estimate_track_heading(yaw: np.ndarray) -> float:
    return float(np.arctan2(np.mean(np.sin(yaw)), np.mean(np.cos(yaw))))


def estimate_heading_from_path(seg: pd.DataFrame) -> float:
    """Robust heading = principal direction of the driven path (ignores noisy yaw)."""
    pts = np.column_stack([seg["x"].to_numpy(float), seg["y"].to_numpy(float)])
    pts = pts[np.isfinite(pts).all(axis=1)]
    if len(pts) < 3:
        return 0.0
    pts = pts - pts.mean(axis=0)
    w, v = np.linalg.eigh(np.cov(pts.T))
    pc = v[:, int(np.argmax(w))]
    ang = math.atan2(pc[1], pc[0])
    # Point heading toward net displacement (start -> end)
    disp = pts[-1] - pts[0]
    if disp @ np.array([math.cos(ang), math.sin(ang)]) < 0:
        ang += math.pi
    return ang


def to_track_sd(
    x: np.ndarray,
    y: np.ndarray,
    origin: tuple[float, float],
    heading: float,
) -> tuple[np.ndarray, np.ndarray]:
    ox, oy = origin
    c, sn = math.cos(heading), math.sin(heading)
    dx, dy = x - ox, y - oy
    along = dx * c + dy * sn
    lat = -dx * sn + dy * c
    return along, lat


def from_track_sd(
    s: float,
    d: float,
    origin: tuple[float, float],
    heading: float,
) -> tuple[float, float]:
    ox, oy = origin
    c, sn = math.cos(heading), math.sin(heading)
    x = ox + s * c - d * sn
    y = oy + s * sn + d * c
    return x, y


def add_wall_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    x = out["x"].to_numpy(dtype=float)
    y = out["y"].to_numpy(dtype=float)
    yaw = out["yaw_rad"].to_numpy(dtype=float)
    w_l = out["left_wall_m"].to_numpy(dtype=float)
    w_r = out["right_wall_m"].to_numpy(dtype=float)
    lx, ly, rx, ry = wall_scatter_xy(x, y, yaw, w_l, w_r)
    out["left_x"] = lx
    out["left_y"] = ly
    out["right_x"] = rx
    out["right_y"] = ry
    return out


def project_to_track(seg: pd.DataFrame, origin: tuple[float, float], heading: float) -> pd.DataFrame:
    seg = add_wall_columns(seg)
    for prefix, xc, yc in (
        ("", "x", "y"),
        ("left_", "left_x", "left_y"),
        ("right_", "right_x", "right_y"),
    ):
        s, d = to_track_sd(seg[xc].to_numpy(), seg[yc].to_numpy(), origin, heading)
        seg[f"{prefix}s_m"] = s
        seg[f"{prefix}d_m"] = d

    # Yaw-robust walls: assume the side beams are perpendicular to the TRACK,
    # so wall lateral position = pose lateral ± range. This ignores noisy
    # per-sample yaw (which scatters walls into a ring on spinny captures).
    seg["left_d_track"] = seg["d_m"] + seg["left_wall_m"]
    seg["right_d_track"] = seg["d_m"] - seg["right_wall_m"]
    return seg


def build_merged_track(
    segments: pd.DataFrame,
    *,
    origin: tuple[float, float],
    heading: float,
    s_bin_m: float,
    n_sd: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    seg = project_to_track(segments, origin, heading)
    seg = seg[np.isfinite(seg["s_m"]) & np.isfinite(seg["d_m"])].copy()
    seg = seg.loc[filter_2sd(seg["d_m"], n_sd)].copy()
    if seg.empty:
        return seg, pd.DataFrame()

    lo, hi = seg["s_m"].min(), seg["s_m"].max()
    edges = np.arange(lo, hi + s_bin_m, s_bin_m)
    rows: list[dict] = []

    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        g = seg[(seg["s_m"] >= a) & (seg["s_m"] < b)]
        if g.empty:
            continue
        g = g.loc[filter_2sd(g["d_m"], n_sd)]
        if g.empty:
            continue

        s_c = 0.5 * (a + b)
        d_mode = mode_float(g["d_m"])
        d_min = float(g["d_m"].min())
        d_max = float(g["d_m"].max())

        # Yaw-robust wall lateral positions (track frame), 2σ filtered per bin.
        ld = g["left_d_track"].dropna()
        rd = g["right_d_track"].dropna()
        ld = ld.loc[filter_2sd(ld, n_sd)] if len(ld) > 2 else ld
        rd = rd.loc[filter_2sd(rd, n_sd)] if len(rd) > 2 else rd
        left_d = float(ld.median()) if len(ld) else math.nan
        right_d = float(rd.median()) if len(rd) else math.nan

        x_c, y_c = from_track_sd(s_c, d_mode, origin, heading)
        lx, ly = from_track_sd(s_c, left_d, origin, heading) if math.isfinite(left_d) else (math.nan, math.nan)
        rx, ry = from_track_sd(s_c, right_d, origin, heading) if math.isfinite(right_d) else (math.nan, math.nan)

        rows.append(
            {
                "s_m": s_c,
                "d_mode_m": d_mode,
                "d_min_m": d_min,
                "d_max_m": d_max,
                "left_d_m": left_d,
                "right_d_m": right_d,
                "x_m": x_c,
                "y_m": y_c,
                "left_x_m": lx,
                "left_y_m": ly,
                "right_x_m": rx,
                "right_y_m": ry,
                "n_samples": len(g),
                "n_runs": int(g["run"].nunique()),
            }
        )

    return seg, pd.DataFrame(rows)


def smooth_series(vals: pd.Series, window: int) -> pd.Series:
    """Robust smoother: median then mean centered rolling windows."""
    if window < 3:
        return vals.copy()
    if window % 2 == 0:
        window += 1
    med = vals.rolling(window=window, center=True, min_periods=1).median()
    return med.rolling(window=window, center=True, min_periods=1).mean()


def build_optimizer_map(
    binned: pd.DataFrame,
    *,
    origin: tuple[float, float],
    heading: float,
    min_runs: int,
    smooth_window: int,
    min_width_m: float,
) -> pd.DataFrame:
    """
    Build an optimizer-ready map with smooth centerline + corridor bounds.

    Best-practice choices:
    - keep only stations observed by >= min_runs
    - interpolate short gaps before smoothing
    - smooth center + walls in track frame (s,d)
    - enforce non-zero corridor width
    - provide yaw + curvature for downstream optimizers
    """
    if binned.empty:
        return pd.DataFrame()

    d = binned.sort_values("s_m").copy()
    if "n_runs" in d.columns:
        d = d[d["n_runs"] >= int(min_runs)].copy()
    if d.empty:
        return pd.DataFrame()

    d["d_mode_m"] = pd.to_numeric(d["d_mode_m"], errors="coerce").interpolate(limit_direction="both")
    d["left_d_m"] = pd.to_numeric(d["left_d_m"], errors="coerce").interpolate(limit_direction="both")
    d["right_d_m"] = pd.to_numeric(d["right_d_m"], errors="coerce").interpolate(limit_direction="both")

    d["d_mode_sm"] = smooth_series(d["d_mode_m"], smooth_window)
    d["left_d_sm"] = smooth_series(d["left_d_m"], smooth_window)
    d["right_d_sm"] = smooth_series(d["right_d_m"], smooth_window)

    # Ensure "left" is the larger lateral bound in track frame.
    if np.nanmedian((d["left_d_sm"] - d["right_d_sm"]).to_numpy(float)) < 0:
        t = d["left_d_sm"].copy()
        d["left_d_sm"] = d["right_d_sm"]
        d["right_d_sm"] = t

    width = (d["left_d_sm"] - d["right_d_sm"]).to_numpy(float)
    width = np.maximum(width, float(min_width_m))
    center = d["d_mode_sm"].to_numpy(float)
    half = 0.5 * width
    left_d = center + half
    right_d = center - half

    s = d["s_m"].to_numpy(float)
    x_c, y_c = from_track_sd(s, center, origin, heading)
    lx, ly = from_track_sd(s, left_d, origin, heading)
    rx, ry = from_track_sd(s, right_d, origin, heading)

    dx_ds = np.gradient(x_c, s, edge_order=1)
    dy_ds = np.gradient(y_c, s, edge_order=1)
    yaw = np.unwrap(np.arctan2(dy_ds, dx_ds))
    kappa = np.gradient(yaw, s, edge_order=1)

    out = pd.DataFrame(
        {
            "s_m": s,
            "x_m": x_c,
            "y_m": y_c,
            "yaw_rad": yaw,
            "curvature_1pm": kappa,
            "left_d_m": left_d,
            "right_d_m": right_d,
            "track_width_m": width,
            "left_x_m": lx,
            "left_y_m": ly,
            "right_x_m": rx,
            "right_y_m": ry,
            "n_samples": d["n_samples"].to_numpy(int),
            "n_runs": d["n_runs"].to_numpy(int),
        }
    )
    return out


def plot_map_frame(
    out_path: Path,
    points: pd.DataFrame,
    binned: pd.DataFrame,
    n_sd: float,
    origin: tuple[float, float],
    heading: float,
    run_count: int,
) -> None:
    """Notebook-style X/Y wall scatter — all runs pooled (yaw-robust walls)."""
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.scatter(points["x"], points["y"], s=10, c="black", alpha=0.35, label="Centerline")
    # Yaw-robust wall points: reconstruct map x,y from track-frame lateral
    lx, ly = from_track_sd(points["s_m"].to_numpy(), points["left_d_track"].to_numpy(), origin, heading)
    rx, ry = from_track_sd(points["s_m"].to_numpy(), points["right_d_track"].to_numpy(), origin, heading)
    ax.scatter(lx, ly, s=8, c="blue", alpha=0.22, label="Left wall")
    ax.scatter(rx, ry, s=8, c="red", alpha=0.22, label="Right wall")
    if not binned.empty:
        ax.plot(binned["x_m"], binned["y_m"], "k-", lw=2.5, label="merged centerline", zorder=5)
        ax.plot(binned["left_x_m"], binned["left_y_m"], "b-", lw=2, label="merged left", zorder=4)
        ax.plot(binned["right_x_m"], binned["right_y_m"], "r-", lw=2, label="merged right", zorder=4)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(f"Straight track — {run_count} runs merged (±{n_sd}σ lateral)")
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_track_unwrapped(
    out_path: Path,
    points: pd.DataFrame,
    binned: pd.DataFrame,
    n_sd: float,
    run_count: int,
) -> None:
    """Side view: along-track s vs lateral d (straight racetrack layout)."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.scatter(points["s_m"], points["d_m"], s=8, c="black", alpha=0.25, label="Centerline")
    # Yaw-robust wall scatter (track frame)
    lmask = points["left_d_track"].notna()
    rmask = points["right_d_track"].notna()
    ax.scatter(points.loc[lmask, "s_m"], points.loc[lmask, "left_d_track"], s=6, c="blue", alpha=0.2, label="Left wall")
    ax.scatter(points.loc[rmask, "s_m"], points.loc[rmask, "right_d_track"], s=6, c="red", alpha=0.2, label="Right wall")
    if not binned.empty:
        ax.fill_between(binned["s_m"], binned["right_d_m"], binned["left_d_m"], color="#c8e6c9", alpha=0.4, label="corridor")
        ax.plot(binned["s_m"], binned["left_d_m"], "b-", lw=2, label="merged left")
        ax.plot(binned["s_m"], binned["right_d_m"], "r-", lw=2, label="merged right")
        ax.plot(binned["s_m"], binned["d_mode_m"], "k-", lw=2, label="merged center")
    ax.set_xlabel("s — along track [m] (0 = common start)")
    ax.set_ylabel("d — lateral [m]")
    ax.set_title(f"Straight racetrack (unwrapped, {run_count} runs) — ±{n_sd}σ")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--glob", default="manual_map_*.csv")
    ap.add_argument("--n-sd", type=float, default=2.0)
    ap.add_argument("--s-bin-m", type=float, default=0.05, help="Along-track distance bin [m]")
    ap.add_argument("--common-origin", default="median")
    ap.add_argument("--optimizer-min-runs", type=int, default=2, help="Keep bins seen by at least this many runs")
    ap.add_argument("--optimizer-smooth-window", type=int, default=9, help="Centered smoothing window (odd preferred)")
    ap.add_argument("--optimizer-min-width-m", type=float, default=0.35, help="Minimum corridor width for optimizer map")
    ap.add_argument("--plot-dir", type=Path, default=None)
    args = ap.parse_args()

    paths = sorted(args.data_dir.glob(args.glob))
    if not paths:
        raise SystemExit(f"No files: {args.glob}")

    runs = {p.name: load_csv(p) for p in paths}
    starts_path = args.data_dir / "run_starts.yaml"
    starts = load_starts(starts_path if starts_path.is_file() else None, runs, 0.005)
    origin = apply_common_origin(starts, mode=args.common_origin, runs=runs)

    combined = pd.concat(runs.values(), ignore_index=True)
    travel, wall, report = detect_travel_wall_axes(combined)
    print(f"Axes: travel={travel}  wall={wall}  (PCA {report.get('pca_travel_angle_deg', 0):.1f}°)")

    segments = align_segments(runs, starts, travel, wall, 0.005)
    heading = estimate_heading_from_path(segments)

    points, binned = build_merged_track(
        segments,
        origin=origin,
        heading=heading,
        s_bin_m=args.s_bin_m,
        n_sd=args.n_sd,
    )
    optimizer_map = build_optimizer_map(
        binned,
        origin=origin,
        heading=heading,
        min_runs=args.optimizer_min_runs,
        smooth_window=args.optimizer_smooth_window,
        min_width_m=args.optimizer_min_width_m,
    )

    plot_dir = args.plot_dir or (args.data_dir / "_plots")
    plot_dir.mkdir(parents=True, exist_ok=True)
    run_count = len(runs)
    plot_map_frame(plot_dir / "straight_track_walls_xy.png", points, binned, args.n_sd, origin, heading, run_count)
    plot_track_unwrapped(plot_dir / "straight_track_unwrapped_sd.png", points, binned, args.n_sd, run_count)

    points.to_csv(args.data_dir / "straight_track_points.csv", index=False)
    binned.to_csv(args.data_dir / "straight_track_map.csv", index=False)
    optimizer_map.to_csv(args.data_dir / "straight_track_map_optimizer.csv", index=False)

    print(f"Runs: {len(runs)}  points: {len(points)}  bins: {len(binned)}  (s_bin_m={args.s_bin_m})")
    print(f"Origin: ({origin[0]:.3f}, {origin[1]:.3f})  heading: {math.degrees(heading):.1f}°")
    print(f"→ {plot_dir}/straight_track_walls_xy.png")
    print(f"→ {args.data_dir}/straight_track_map.csv")
    print(
        f"→ {args.data_dir}/straight_track_map_optimizer.csv"
        f"  (min_runs={args.optimizer_min_runs}, smooth={args.optimizer_smooth_window},"
        f" min_width={args.optimizer_min_width_m:.2f}m)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
