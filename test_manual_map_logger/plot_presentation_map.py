#!/usr/bin/env python3
"""Presentation figures: manual_map_logger CSV as a top-down path in `map` (+ optional corridor sketch).

SLAM's OccupancyGrid (/map) is not in the CSV — this plots the logged pose trajectory, which is what
we feed the optimizer / pure pursuit in `map` frame.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np


def load_trimmed(path: Path, drop_first: int) -> dict[str, np.ndarray]:
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    if drop_first:
        rows = rows[drop_first:]
    if not rows:
        raise SystemExit("No rows after trim")
    return {
        "x": np.array([float(r["x"]) for r in rows]),
        "y": np.array([float(r["y"]) for r in rows]),
        "left": np.array([float(r["left_wall_m"]) for r in rows]),
        "right": np.array([float(r["right_wall_m"]) for r in rows]),
        "t": np.array([float(r["time_sec"]) for r in rows]),
    }


def box_smooth(a: np.ndarray, win: int) -> np.ndarray:
    """Odd-length moving average (same length)."""
    win = max(3, win | 1)
    k = np.ones(win, dtype=float) / float(win)
    return np.convolve(a.astype(float), k, mode="same")


def rolling_median(a: np.ndarray, win: int) -> np.ndarray:
    """Centered-ish rolling median; knocks down spiky scan returns (people, bags, other robots)."""
    win = max(3, int(win) | 1)
    half = win // 2
    a = np.asarray(a, dtype=float)
    n = len(a)
    out = np.empty(n, dtype=float)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        out[i] = float(np.median(a[lo:hi]))
    return out


def smooth_wall_ranges_for_viz(left: np.ndarray, right: np.ndarray, median_win: int, mean_win: int):
    """Viz-only: median then mean + clip; raw CSV unchanged."""
    ml, mr = rolling_median(left, median_win), rolling_median(right, median_win)
    ml = box_smooth(ml, mean_win)
    mr = box_smooth(mr, mean_win)
    return np.clip(ml, 0.12, 5.0), np.clip(mr, 0.12, 5.0)


def corridor_offsets(x: np.ndarray, y: np.ndarray, left: np.ndarray, right: np.ndarray):
    """Rough left/right boundary polylines using path tangent and scan window ranges."""
    n = len(x)
    tx = np.zeros(n)
    ty = np.zeros(n)
    for i in range(n):
        if i == 0:
            dx, dy = x[1] - x[0], y[1] - y[0]
        elif i == n - 1:
            dx, dy = x[-1] - x[-2], y[-1] - y[-2]
        else:
            dx, dy = x[i + 1] - x[i - 1], y[i + 1] - y[i - 1]
        norm = math.hypot(dx, dy) + 1e-9
        tx[i], ty[i] = dx / norm, dy / norm
    # perpendicular (left of forward motion in +y cross +x sense — visualization only)
    nx, ny = -ty, tx
    lx = x + left * nx
    ly = y + left * ny
    rx = x - right * nx
    ry = y - right * ny
    return lx, ly, rx, ry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="manual_map_logger CSV")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output PNG (default: _plots/<stem>_presentation_16x9.png)",
    )
    ap.add_argument("--drop-first", type=int, default=1, help="Drop first N data rows")
    ap.add_argument(
        "--corridor",
        choices=("off", "smooth", "raw"),
        default="smooth",
        help="Scan-based corridor: off | smooth (median then mean on ranges) | raw (noisy)",
    )
    ap.add_argument(
        "--corridor-window",
        type=int,
        default=21,
        help="Moving-average window after median for --corridor smooth (odd; default 21)",
    )
    ap.add_argument(
        "--corridor-median-window",
        type=int,
        default=25,
        help="Rolling median window for --corridor smooth (odd; default 25); 0 skips median",
    )
    ap.add_argument(
        "--closure-chord",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Draw dashed start–end gap (default: on; use --no-closure-chord to hide)",
    )
    ap.add_argument("--dpi", type=int, default=200, help="Raster DPI")
    args = ap.parse_args()

    d = load_trimmed(args.csv, args.drop_first)
    x, y, left, right, t = d["x"], d["y"], d["left"], d["right"], d["t"]
    steps = np.hypot(np.diff(x), np.diff(y))
    path_len = float(steps.sum())
    duration = float(t[-1] - t[0])

    out = args.output
    if out is None:
        out = args.csv.parent / "_plots" / f"{args.csv.stem}_presentation_16x9.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    # 16:9 slide
    fig_w, fig_h = 16.0, 9.0
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[2.15, 1.0], wspace=0.22)

    ax = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    ax_right.axis("off")

    # Colored path by arc-length fraction
    seg = np.array([np.column_stack([x[:-1], y[:-1]]), np.column_stack([x[1:], y[1:]])])
    seg = np.moveaxis(seg, 0, 1)
    frac = np.linspace(0.0, 1.0, len(x))
    lc = LineCollection(seg, cmap="viridis", linewidths=3.0, alpha=0.95)
    lc.set_array(0.5 * (frac[:-1] + frac[1:]))
    ax.add_collection(lc)
    ax.autoscale()

    if args.corridor != "off":
        le, ri = left, right
        if args.corridor == "smooth":
            w = args.corridor_window | 1
            mw_arg = int(args.corridor_median_window)
            if mw_arg <= 0:
                le, ri = box_smooth(left, w), box_smooth(right, w)
            else:
                mw = max(3, mw_arg | 1)
                le, ri = smooth_wall_ranges_for_viz(left, right, mw, w)
        lx, ly, rx, ry = corridor_offsets(x, y, le, ri)
        lab = "Corridor (scan, viz-smoothed)" if args.corridor == "smooth" else "Corridor (scan, raw)"
        ax.plot(lx, ly, color="#b8c5de", linewidth=1.2, alpha=0.55, zorder=0, label=lab)
        ax.plot(rx, ry, color="#b8c5de", linewidth=1.2, alpha=0.55, zorder=0)

    lc.set_zorder(2)
    ax.plot(x, y, color="0.2", linewidth=0.7, alpha=0.35, zorder=1, label="Centerline (under)")

    gap = float(np.hypot(x[-1] - x[0], y[-1] - y[0]))
    if args.closure_chord and gap > 0.01:
        ax.plot(
            [x[-1], x[0]],
            [y[-1], y[0]],
            color="0.45",
            ls="--",
            lw=1.5,
            alpha=0.85,
            zorder=1,
            label=f"Start–end gap ({gap:.2f} m)",
        )

    ax.scatter([x[0]], [y[0]], c="#2ca02c", s=220, zorder=5, edgecolors="white", linewidths=2, label="Start")
    ax.scatter([x[-1]], [y[-1]], c="#d62728", s=220, zorder=5, edgecolors="white", linewidths=2, label="End")

    ax.set_aspect("equal")
    ax.grid(True, alpha=0.35)
    ax.set_xlabel("x in map [m]", fontsize=13)
    ax.set_ylabel("y in map [m]", fontsize=13)
    ax.set_title(
        "Logged reference path (SLAM `map` frame)\n"
        "Same frame as `pursuit_world_frame:=map` + TUM raceline output",
        fontsize=15,
        fontweight="bold",
    )
    ax.legend(loc="upper left", fontsize=10, framealpha=0.92)

    cbar = fig.colorbar(lc, ax=ax, fraction=0.046, pad=0.02)
    cbar.set_label("Progress along lap", fontsize=11)

    # Right panel: why it works + stats
    stats = (
        f"Dataset\n"
        f"  • rows: {len(x)}\n"
        f"  • duration: {duration:.1f} s\n"
        f"  • path length: {path_len:.1f} m\n"
        f"  • start–end gap: {gap:.2f} m\n"
        f"  • frame_id: map\n\n"
        "Why this is valid for today’s story\n"
        "  1. SLAM publishes map→odom; EKF\n"
        "     keeps odom→base_link. Poses\n"
        "     here are where the robot was\n"
        "     in the global map frame.\n\n"
        "  2. TUM optimizer smooths this\n"
        "     polyline + wall hints into a\n"
        "     raceline CSV (faster / safer\n"
        "     line within your model).\n\n"
        "  3. Pure pursuit tracks that CSV\n"
        "     in map — same geometry the\n"
        "     car used while mapping.\n\n"
        "Note: SLAM occupancy grid (/map)\n"
        "is separate from this CSV; it was\n"
        "live in the car during capture.\n\n"
        "Corridor (if on): viz smoothing\n"
        "only — people / other cars still\n"
        "bias real scans in mapping & race."
    )
    ax_right.text(
        0.02,
        0.98,
        stats,
        transform=ax_right.transAxes,
        fontsize=11.5,
        verticalalignment="top",
        fontfamily="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f4f4f4", edgecolor="#999999", alpha=1.0),
    )

    fig.suptitle(
        "RoboRacer T7 — hall mapping → raceline pipeline (concept)",
        fontsize=17,
        fontweight="bold",
        y=0.98,
    )

    fig.savefig(out, dpi=args.dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
