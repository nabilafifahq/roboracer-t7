#!/usr/bin/env python3
"""Turn a manual_map driven-path CSV into a clean closed racing line (x_m,y_m).

Use when the occupancy map is too noisy to extract walls but the *driven loop*
is clean: we take the human-driven trajectory, trim the parked start/end,
extract ONE lap, resample evenly, smooth periodically, and close the loop.
Output is the simple x_m,y_m CSV the pursuit nodes consume.

  python3 path_to_raceline.py IN.csv -o OUT.csv [--plot OUT.png]
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np


def load_xy(path: Path, xcol: str, ycol: str) -> np.ndarray:
    pts = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                x, y = float(r[xcol]), float(r[ycol])
            except (KeyError, ValueError):
                continue
            if math.isfinite(x) and math.isfinite(y):
                pts.append((x, y))
    return np.asarray(pts, float)


def dedup(xy: np.ndarray, step: float) -> np.ndarray:
    out = [xy[0]]
    for p in xy[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= step:
            out.append(p)
    return np.asarray(out, float)


def extract_one_lap(xy: np.ndarray, leave_r: float, return_r: float, min_perim: float) -> np.ndarray:
    """From the parked start, find where the car leaves and first returns -> one lap."""
    ref = xy[0]
    d = np.hypot(xy[:, 0] - ref[0], xy[:, 1] - ref[1])
    # index where it has clearly left the start
    left = np.argmax(d > leave_r)
    if left == 0 and d[0] <= leave_r:
        left = 1
    # arc length from 'left'
    seg = xy[left:]
    arc = np.r_[0, np.cumsum(np.hypot(np.diff(seg[:, 0]), np.diff(seg[:, 1])))]
    dref = np.hypot(seg[:, 0] - ref[0], seg[:, 1] - ref[1])
    ret = None
    for i in range(len(seg)):
        if arc[i] > min_perim and dref[i] < return_r:
            ret = i
            break
    if ret is None:  # never returned cleanly -> use whole thing up to last near-ref point
        ret = len(seg) - 1
    return seg[: ret + 1]


def resample(xy: np.ndarray, n: int, closed: bool) -> np.ndarray:
    pts = np.vstack([xy, xy[0]]) if closed else xy
    seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    s = np.r_[0, np.cumsum(seg)]
    if s[-1] == 0:
        raise SystemExit("degenerate path (zero length)")
    su = np.linspace(0, s[-1], n, endpoint=not closed)
    return np.column_stack([np.interp(su, s, pts[:, 0]), np.interp(su, s, pts[:, 1])])


def smooth_periodic(xy: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return xy
    win = win if win % 2 == 1 else win + 1
    k = np.ones(win) / win
    out = xy.copy()
    for c in (0, 1):
        out[:, c] = np.convolve(np.r_[xy[-win:, c], xy[:, c], xy[:win, c]], k, mode="same")[win:-win]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--xcol", default="x")
    ap.add_argument("--ycol", default="y")
    ap.add_argument("--dedup", type=float, default=0.04, help="min spacing when cleaning [m]")
    ap.add_argument("--leave-r", type=float, default=0.6, help="dist from start that counts as 'left' [m]")
    ap.add_argument("--return-r", type=float, default=0.35, help="dist back to start that closes the lap [m]")
    ap.add_argument("--min-perim", type=float, default=4.0, help="min lap length before a return counts [m]")
    ap.add_argument("--n", type=int, default=200, help="output point count")
    ap.add_argument("--smooth", type=int, default=9, help="periodic smoothing window (odd)")
    ap.add_argument("--no-loop", action="store_true", help="keep open path (don't close)")
    ap.add_argument("--plot", type=Path, default=None)
    args = ap.parse_args()

    raw = load_xy(args.input, args.xcol, args.ycol)
    if len(raw) < 10:
        raise SystemExit(f"only {len(raw)} usable points")
    clean = dedup(raw, args.dedup)
    closed = not args.no_loop
    lap = extract_one_lap(clean, args.leave_r, args.return_r, args.min_perim) if closed else clean
    line = resample(lap, args.n, closed)
    line = smooth_periodic(line, args.smooth) if closed else line

    perim = float(np.hypot(np.diff(np.r_[line[:, 0], line[0, 0]]), np.diff(np.r_[line[:, 1], line[0, 1]])).sum())
    gap = float(math.hypot(line[0, 0] - line[-1, 0], line[0, 1] - line[-1, 1]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        f.write("x_m,y_m\n")
        for x, y in line:
            f.write(f"{x:.4f},{y:.4f}\n")
    print(f"wrote {len(line)} pts -> {args.out}")
    print(f"  loop perimeter ~{perim:.2f} m, start-end gap {gap:.2f} m, "
          f"x[{line[:,0].min():.2f},{line[:,0].max():.2f}] y[{line[:,1].min():.2f},{line[:,1].max():.2f}]")

    if args.plot is not None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.plot(raw[:, 0], raw[:, 1], color="0.8", lw=1, label="raw driven (all laps)")
        ax.plot(line[:, 0], line[:, 1], "b-", lw=2.5, label="racing line (1 lap, smoothed)")
        ax.scatter([line[0, 0]], [line[0, 1]], c="limegreen", s=90, marker="*", zorder=5, label="start")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_title(f"Racing line from driven loop ({len(line)} pts, ~{perim:.1f} m)")
        ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]")
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.plot, dpi=150, bbox_inches="tight")
        print(f"  plot -> {args.plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
