#!/usr/bin/env python3
"""Make a presentation-quality 'track map + best path' figure (Berlin-style).

Input is a manual_map_logger CSV (RECORD IN ODOM FRAME for a clean loop:
world_frame:=odom -> no Cartographer teleport jumps). We:
  1. extract one clean lap from the driven path, smooth it -> CENTERLINE,
  2. project left/right_wall_m through the heading normal -> WALL BOUNDARIES,
     reject outliers (open gaps / one-sided readings) and smooth,
  3. optionally overlay a BEST-PATH raceline CSV (x_m,y_m from path_to_raceline.py).

  python3 presentation_map_plot.py LAP.csv -o out.png [--raceline raceline.csv]
     [--max-wall 2.0] [--smooth 7] [--title "UCSD June 6 track"]

Pure numpy + matplotlib. The logged x,y,yaw is the EKF *actual* pose (TF
world->base_link), NOT joystick — see manual_map_logger.py.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load_lap(path: Path):
    x, y, yaw, wl, wr = [], [], [], [], []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                xx, yy, yw = float(r["x"]), float(r["y"]), float(r["yaw_rad"])
            except (KeyError, ValueError):
                continue
            if not (math.isfinite(xx) and math.isfinite(yy) and math.isfinite(yw)):
                continue
            x.append(xx); y.append(yy); yaw.append(yw)

            def num(key):
                v = r.get(key, "")
                try:
                    f_ = float(v)
                    return f_ if math.isfinite(f_) else math.nan
                except (TypeError, ValueError):
                    return math.nan

            wl.append(num("left_wall_m")); wr.append(num("right_wall_m"))
    return (np.array(x), np.array(y), np.array(yaw), np.array(wl), np.array(wr))


def dedup(xy, step=0.02):
    keep = [0]
    for i in range(1, len(xy)):
        if math.hypot(xy[i, 0] - xy[keep[-1], 0], xy[i, 1] - xy[keep[-1], 1]) >= step:
            keep.append(i)
    return np.array(keep)


def extract_one_lap(x, y, leave_r=0.4, return_r=0.5, min_perim=2.0):
    """Trim the parked start, return index slice for ONE lap (leave start -> first return)."""
    ref = np.array([x[0], y[0]])
    d = np.hypot(x - ref[0], y - ref[1])
    left = int(np.argmax(d > leave_r))
    if left == 0:
        left = 1
    seg_x, seg_y = x[left:], y[left:]
    arc = np.r_[0, np.cumsum(np.hypot(np.diff(seg_x), np.diff(seg_y)))]
    dref = np.hypot(seg_x - ref[0], seg_y - ref[1])
    ret = len(seg_x) - 1
    for i in range(len(seg_x)):
        if arc[i] > min_perim and dref[i] < return_r:
            ret = i
            break
    return left, left + ret + 1


def smooth_periodic(arr, win):
    if win < 3 or len(arr) < win:
        return arr
    k = np.ones(win) / win
    pad = win // 2
    out = np.empty_like(arr)
    for c in range(arr.shape[1]):
        ext = np.r_[arr[-pad:, c], arr[:, c], arr[:pad, c]]
        out[:, c] = np.convolve(ext, k, mode="same")[pad:-pad]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lap_csv", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--raceline", type=Path, default=None, help="x_m,y_m best-path CSV to overlay")
    ap.add_argument("--max-wall", type=float, default=2.0, help="reject wall readings beyond this (m)")
    ap.add_argument("--min-wall", type=float, default=0.10)
    ap.add_argument("--smooth", type=int, default=7, help="boundary/centerline smoothing window")
    ap.add_argument("--title", default="Track map + best path")
    ap.add_argument("--no-lap-extract", action="store_true", help="plot the whole driven path as-is")
    args = ap.parse_args()

    x, y, yaw, wl, wr = load_lap(args.lap_csv)
    if len(x) < 5:
        raise SystemExit(f"only {len(x)} pose rows — need a real lap")

    if args.no_lap_extract:
        lo, hi = 0, len(x)
    else:
        lo, hi = extract_one_lap(x, y)
    x, y, yaw, wl, wr = x[lo:hi], y[lo:hi], yaw[lo:hi], wl[lo:hi], wr[lo:hi]

    xy = np.column_stack([x, y])
    keep = dedup(xy, 0.02)
    x, y, yaw, wl, wr = x[keep], y[keep], yaw[keep], wl[keep], wr[keep]

    # left-facing normal (ROS yaw: +pi/2 is left)
    nx, ny = -np.sin(yaw), np.cos(yaw)

    def boundary(w, sign):
        ok = np.isfinite(w) & (w > args.min_wall) & (w < args.max_wall)
        bx = x + sign * nx * w
        by = y + sign * ny * w
        return bx[ok], by[ok]

    lbx, lby = boundary(wl, +1.0)
    rbx, rby = boundary(wr, -1.0)

    center = smooth_periodic(np.column_stack([x, y]), args.smooth)

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(lbx, lby, s=6, c="#d62728", alpha=0.55, label="left boundary")
    ax.scatter(rbx, rby, s=6, c="#1f77b4", alpha=0.55, label="right boundary")
    ax.plot(center[:, 0], center[:, 1], "-", c="#2ca02c", lw=1.4, alpha=0.8, label="centerline (driven)")

    if args.raceline and args.raceline.exists():
        rl = []
        with open(args.raceline) as f:
            for row in csv.DictReader(f):
                try:
                    rl.append((float(row["x_m"]), float(row["y_m"])))
                except (KeyError, ValueError):
                    continue
        if rl:
            rl = np.array(rl)
            ax.plot(rl[:, 0], rl[:, 1], "-", c="black", lw=2.4, label="best path (raceline)")

    ax.plot(x[0], y[0], "*", c="green", ms=16, label="start", zorder=5)
    ax.set_aspect("equal", "box")
    ax.grid(alpha=0.3)
    ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]")
    span = math.hypot(x.max() - x.min(), y.max() - y.min())
    ax.set_title(f"{args.title}\n{len(x)} pts · diag {span:.1f} m · ODOM frame")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"wrote {args.out}  ({len(lbx)} left, {len(rbx)} right boundary pts)")


if __name__ == "__main__":
    main()
