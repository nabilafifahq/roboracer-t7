#!/usr/bin/env python3
"""Extra presentation figures from manual_map_logger CSV (and optional raceline overlay).

Generates PNGs next to the CSV under _plots/<stem>_extra_<name>.png
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_map_csv(path: Path, drop_first: int) -> dict[str, np.ndarray]:
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    if drop_first:
        rows = rows[drop_first:]
    if not rows:
        raise SystemExit("No rows after drop")
    return {
        "x": np.array([float(r["x"]) for r in rows]),
        "y": np.array([float(r["y"]) for r in rows]),
        "yaw": np.array([float(r["yaw_rad"]) for r in rows]),
        "t": np.array([float(r["time_sec"]) for r in rows]),
        "left": np.array([float(r["left_wall_m"]) for r in rows]),
        "right": np.array([float(r["right_wall_m"]) for r in rows]),
        "scan": np.array([float(r["scan_stamp_sec"]) for r in rows]),
    }


def load_xy_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """First two columns as floats per row (skip # lines; skip non-numeric header)."""
    xs, ys = [], []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not str(row[0]).strip() or str(row[0]).strip().startswith("#"):
                continue
            try:
                xs.append(float(row[0]))
                ys.append(float(row[1]))
            except (ValueError, IndexError):
                continue
    return np.array(xs), np.array(ys)


def cumulative_s(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    d = np.hypot(np.diff(x), np.diff(y))
    return np.concatenate([[0.0], np.cumsum(d)])


def heading_unwrapped(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    n = len(x)
    psi = np.zeros(n)
    for i in range(1, n):
        psi[i] = math.atan2(y[i] - y[i - 1], x[i] - x[i - 1])
    psi[0] = psi[1]
    return np.unwrap(psi)


def curvature_from_xy(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Discrete curvature ~ d(psi)/ds along polyline (rad/m); robust to duplicate poses."""
    psi = heading_unwrapped(x, y)
    s = cumulative_s(x, y)
    n = len(x)
    kappa = np.zeros(n)
    for i in range(1, n - 1):
        ds = s[i + 1] - s[i - 1]
        if ds > 1e-4:
            kappa[i] = (psi[i + 1] - psi[i - 1]) / ds
    kappa[0] = kappa[1]
    kappa[-1] = kappa[-2]
    return kappa


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="manual_map_logger CSV")
    ap.add_argument("--drop-first", type=int, default=1)
    ap.add_argument(
        "--raceline",
        type=Path,
        default=None,
        help="Optional optimized raceline CSV (x,y or x_m,y_m) to overlay on plan view",
    )
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    stem = args.csv.stem
    out_dir = args.csv.parent / "_plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_map_csv(args.csv, 0)
    tr = load_map_csv(args.csv, args.drop_first)
    x, y, yaw, t, scan = tr["x"], tr["y"], tr["yaw"], tr["t"], tr["scan"]
    s = cumulative_s(x, y)
    steps = np.hypot(np.diff(x), np.diff(y))
    lag = t - scan
    kappa = curvature_from_xy(x, y)
    idx = np.arange(len(x))

    dpi = args.dpi

    # 1) Cumulative distance vs time
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(t - t[0], s, color="C0", lw=2)
    ax.set_xlabel("Time from start [s]")
    ax.set_ylabel("Cumulative path length [m]")
    ax.set_title("How far along the lap (arc length vs time)")
    ax.grid(True, alpha=0.35)
    fig.savefig(out_dir / f"{stem}_extra_cumdist_vs_time.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # 2) Yaw vs index
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(idx, np.rad2deg(yaw), color="C1", lw=1)
    ax.set_xlabel("Sample index")
    ax.set_ylabel("yaw [deg]")
    ax.set_title("Heading from TF (map frame)")
    ax.grid(True, alpha=0.35)
    fig.savefig(out_dir / f"{stem}_extra_yaw_vs_index.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # 3) Curvature magnitude vs index
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(idx, np.abs(kappa), color="C2", lw=0.8)
    ax.set_xlabel("Sample index")
    ax.set_ylabel("|κ| [1/m]")
    ax.set_title("Path curvature (discrete; high spikes = sharp corners / noise)")
    ax.grid(True, alpha=0.35)
    fig.savefig(out_dir / f"{stem}_extra_curvature_vs_index.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # 4) Step histogram
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(steps * 1000.0, bins=40, color="C3", edgecolor="white", alpha=0.9)
    ax.set_xlabel("Step size [mm]")
    ax.set_ylabel("Count")
    ax.set_title("Along-path step sizes (after trim) — tight = smooth logging")
    ax.grid(True, alpha=0.3)
    fig.savefig(out_dir / f"{stem}_extra_step_hist_mm.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # 5) Scan lag
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(idx, lag, color="C4", lw=0.8)
    ax.set_xlabel("Sample index")
    ax.set_ylabel("time_sec − scan_stamp_sec [s]")
    ax.set_title("Pose vs lidar stamp lag (sensor–TF timing)")
    ax.grid(True, alpha=0.35)
    fig.savefig(out_dir / f"{stem}_extra_scan_lag_vs_index.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # 6) Raw vs trimmed overlay
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot(raw["x"], raw["y"], color="0.6", lw=1.2, alpha=0.85, label="Raw (includes SLAM snap)")
    ax.plot(x, y, color="C0", lw=2.0, alpha=0.95, label=f"Trimmed (drop_first={args.drop_first})")
    if args.drop_first > 0:
        ax.scatter(
            [raw["x"][0]],
            [raw["y"][0]],
            c="gray",
            s=60,
            zorder=5,
            marker="x",
            label="First raw point (dropped)",
        )
    ax.scatter([x[0]], [y[0]], c="green", s=100, zorder=6, edgecolors="k", linewidths=0.5)
    ax.scatter([x[-1]], [y[-1]], c="red", s=100, zorder=6, edgecolors="k", linewidths=0.5)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.35)
    ax.legend(loc="best", fontsize=9)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("Why we drop the first row (startup jump)")
    fig.savefig(out_dir / f"{stem}_extra_raw_vs_trim_xy.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # 7) Plan view + optional raceline
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.plot(x, y, color="C0", lw=2.2, alpha=0.9, label="Logged centerline (trimmed)")
    if args.raceline and args.raceline.is_file():
        rx, ry = load_xy_csv(args.raceline)
        if len(rx) > 2:
            ax.plot(rx, ry, color="C3", lw=2.0, ls="--", alpha=0.95, label=f"Raceline: {args.raceline.name}")
        else:
            ax.text(0.02, 0.98, "(raceline file too short to plot)", transform=ax.transAxes, va="top")
    ax.scatter([x[0]], [y[0]], c="green", s=120, zorder=6, edgecolors="k", label="Start")
    ax.scatter([x[-1]], [y[-1]], c="red", s=120, zorder=6, edgecolors="k", label="End")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.35)
    ax.legend(loc="best", fontsize=9)
    ax.set_xlabel("x in map [m]")
    ax.set_ylabel("y in map [m]")
    ttl = "Centerline vs optimized raceline (if provided)"
    if not (args.raceline and args.raceline.is_file()):
        ttl = "Centerline (add --raceline path/to/tum_output.csv when you have it)"
    ax.set_title(ttl)
    fig.savefig(out_dir / f"{stem}_extra_xy_with_raceline.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    print("Wrote under", out_dir.resolve())
    for pat in (
        "extra_cumdist_vs_time",
        "extra_yaw_vs_index",
        "extra_curvature_vs_index",
        "extra_step_hist_mm",
        "extra_scan_lag_vs_index",
        "extra_raw_vs_trim_xy",
        "extra_xy_with_raceline",
    ):
        print(" ", out_dir / f"{stem}_{pat}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
