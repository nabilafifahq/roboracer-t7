#!/usr/bin/env python3
"""Build a TUM track CSV (x_m, y_m, w_tr_right_m, w_tr_left_m) from a Cartographer
occupancy-grid map (`map_saver_cli` .pgm/.yaml) plus a manual_map driven-path CSV.

Why this exists: `manual_map_logger`'s left_wall_m/right_wall_m come from a single
LiDAR beam at a fixed side angle, which gives garbage on open/curved tracks (it hits
the far room wall, the box, or nothing). Here the walls instead come from RAY-CASTING
the actual occupancy map perpendicular to the driving line at every point, so they use
the whole map and reflect the real walls.

Inputs:
  --map   path to the map .yaml from `ros2 run nav2_map_server map_saver_cli`
  --path  the manual_map CSV (columns x,y in the map frame) = centerline source
Output:
  --out   TUM track CSV: x_m, y_m, w_tr_right_m, w_tr_left_m

Dependencies: numpy only (matplotlib optional, just for --plot).
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np


# ----------------------------- map loading --------------------------------
def read_pgm(path: Path) -> np.ndarray:
    """Read an 8-bit binary (P5) or ASCII (P2) PGM into a HxW uint8 array."""
    raw = Path(path).read_bytes()

    def next_token(i: int):
        while i < len(raw):
            c = raw[i : i + 1]
            if c.isspace():
                i += 1
            elif c == b"#":  # comment to end of line
                while i < len(raw) and raw[i : i + 1] not in (b"\n", b"\r"):
                    i += 1
            else:
                break
        j = i
        while j < len(raw) and not raw[j : j + 1].isspace():
            j += 1
        return raw[i:j], j

    magic, i = next_token(0)
    w_t, i = next_token(i)
    h_t, i = next_token(i)
    mx_t, i = next_token(i)
    w, h, maxv = int(w_t), int(h_t), int(mx_t)
    if maxv > 255:
        raise ValueError("16-bit PGM not supported (map_saver writes 8-bit)")
    i += 1  # exactly one whitespace byte separates header from data
    if magic == b"P5":
        img = np.frombuffer(raw[i : i + w * h], dtype=np.uint8).reshape(h, w)
    elif magic == b"P2":
        vals = raw[i:].split()[: w * h]
        img = np.array([int(v) for v in vals], dtype=np.uint8).reshape(h, w)
    else:
        raise ValueError(f"Unsupported PGM magic {magic!r}")
    return img


def read_map_yaml(path: Path) -> dict:
    d: dict[str, str] = {}
    for ln in Path(path).read_text().splitlines():
        ln = ln.split("#", 1)[0].strip()
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        d[k.strip()] = v.strip()
    res = float(d["resolution"])
    origin = [float(x) for x in d["origin"].strip("[] ").split(",")]
    image = d["image"].strip().strip("'\"")
    negate = int(d.get("negate", "0"))
    occ = float(d.get("occupied_thresh", "0.65"))
    return {"resolution": res, "origin": origin, "image": image, "negate": negate, "occupied_thresh": occ}


# ----------------------------- path loading -------------------------------
def load_path(path: Path, xcol: str, ycol: str, min_step: float) -> np.ndarray:
    import csv

    pts: list[tuple[float, float]] = []
    with open(path) as fh:
        rdr = csv.DictReader(fh)
        for row in rdr:
            try:
                x, y = float(row[xcol]), float(row[ycol])
            except (KeyError, ValueError):
                continue
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
            if pts and math.hypot(x - pts[-1][0], y - pts[-1][1]) < min_step:
                continue  # drop near-duplicate samples (slow driving)
            pts.append((x, y))
    if len(pts) < 5:
        raise SystemExit(f"path {path} has too few usable points ({len(pts)})")
    return np.asarray(pts, dtype=float)


def smooth_xy(xy: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return xy
    win = win if win % 2 == 1 else win + 1
    k = np.ones(win) / win
    pad = win // 2
    out = xy.copy()
    for c in (0, 1):
        padded = np.r_[np.full(pad, xy[0, c]), xy[:, c], np.full(pad, xy[-1, c])]
        out[:, c] = np.convolve(padded, k, mode="valid")
    return out


def moving_avg(a: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return a
    win = win if win % 2 == 1 else win + 1
    pad = win // 2
    k = np.ones(win) / win
    return np.convolve(np.r_[np.full(pad, a[0]), a, np.full(pad, a[-1])], k, mode="valid")


# ----------------------------- ray casting --------------------------------
class Grid:
    def __init__(self, occ: np.ndarray, res: float, origin: list[float]):
        self.occ = occ  # bool HxW, True = wall
        self.h, self.w = occ.shape
        self.res = res
        self.ox, self.oy = origin[0], origin[1]

    def world_to_px(self, x: float, y: float):
        col = (x - self.ox) / self.res
        row = (self.h - 1) - (y - self.oy) / self.res  # row 0 = top, origin = lower-left
        return int(round(col)), int(round(row))

    def cast(self, x: float, y: float, ux: float, uy: float, max_dist: float) -> float:
        """March from (x,y) along unit (ux,uy); return distance to first wall cell
        (or max_dist if none / map edge reached)."""
        step = self.res * 0.5
        n = int(max_dist / step)
        for k in range(1, n + 1):
            d = k * step
            col, row = self.world_to_px(x + ux * d, y + uy * d)
            if col < 0 or col >= self.w or row < 0 or row >= self.h:
                return max_dist  # ran off the map without hitting a wall
            if self.occ[row, col]:
                return d
        return max_dist


# ----------------------------- main ---------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", required=True, type=Path, help="map .yaml from map_saver_cli")
    ap.add_argument("--path", required=True, type=Path, help="manual_map driven-path CSV")
    ap.add_argument("--out", required=True, type=Path, help="output TUM track CSV")
    ap.add_argument("--xcol", default="x")
    ap.add_argument("--ycol", default="y")
    ap.add_argument("--min-step", type=float, default=0.03, help="drop path samples closer than this [m]")
    ap.add_argument("--smooth-xy", type=int, default=11, help="centerline smoothing window (odd)")
    ap.add_argument("--smooth-width", type=int, default=7, help="wall-width smoothing window (odd)")
    ap.add_argument("--max-wall", type=float, default=3.0, help="max ray distance [m]")
    ap.add_argument("--min-wall", type=float, default=0.10, help="clamp wall distance floor [m]")
    ap.add_argument("--occupied-cut", type=int, default=50, help="pixel <= this is treated as wall (fallback)")
    ap.add_argument("--close-loop", action="store_true", help="append first point to close the loop")
    ap.add_argument("--plot", type=Path, default=None, help="optional PNG sanity plot")
    args = ap.parse_args()

    meta = read_map_yaml(args.map)
    img = read_pgm(args.map.parent / meta["image"])
    # Occupancy: standard map_saver -> dark = occupied. Honor negate + occupied_thresh,
    # with a brightness fallback so it works regardless of yaml quirks.
    occ_prob = (img.astype(float) / 255.0) if meta["negate"] else (255.0 - img.astype(float)) / 255.0
    occupied = (occ_prob >= meta["occupied_thresh"]) | (img <= args.occupied_cut)
    grid = Grid(occupied, meta["resolution"], meta["origin"])

    xy = load_path(args.path, args.xcol, args.ycol, args.min_step)
    xy = smooth_xy(xy, args.smooth_xy)

    # heading from path tangent
    dx = np.gradient(xy[:, 0])
    dy = np.gradient(xy[:, 1])
    theta = np.arctan2(dy, dx)
    # left normal = (-sin, cos), right normal = (sin, -cos)
    lx, ly = -np.sin(theta), np.cos(theta)
    rx, ry = np.sin(theta), -np.cos(theta)

    n = len(xy)
    wl = np.empty(n)
    wr = np.empty(n)
    for i in range(n):
        wl[i] = grid.cast(xy[i, 0], xy[i, 1], lx[i], ly[i], args.max_wall)
        wr[i] = grid.cast(xy[i, 0], xy[i, 1], rx[i], ry[i], args.max_wall)
    wl = np.clip(moving_avg(wl, args.smooth_width), args.min_wall, args.max_wall)
    wr = np.clip(moving_avg(wr, args.smooth_width), args.min_wall, args.max_wall)

    out_xy = xy
    if args.close_loop:
        out_xy = np.vstack([xy, xy[0]])
        wl = np.r_[wl, wl[0]]
        wr = np.r_[wr, wr[0]]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write("# x_m,y_m,w_tr_right_m,w_tr_left_m  (walls ray-cast from Cartographer map)\n")
        fh.write("x_m,y_m,w_tr_right_m,w_tr_left_m\n")
        for i in range(len(out_xy)):
            fh.write(f"{out_xy[i,0]:.4f},{out_xy[i,1]:.4f},{wr[i]:.4f},{wl[i]:.4f}\n")

    width = wl + wr
    print(f"wrote {len(out_xy)} pts -> {args.out}")
    print(f"  track width [m]: min={width.min():.2f} med={np.median(width):.2f} max={width.max():.2f}")
    print(f"  left  [m]: med={np.median(wl):.2f}   right [m]: med={np.median(wr):.2f}")

    if args.plot is not None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        H, W = grid.h, grid.w
        ext = [grid.ox, grid.ox + W * grid.res, grid.oy, grid.oy + H * grid.res]
        fig, ax = plt.subplots(figsize=(9, 9))
        ax.imshow(img, cmap="gray", origin="upper", extent=ext, alpha=0.7)
        lwx, lwy = out_xy[:, 0] + 0, out_xy[:, 1] + 0
        ax.plot(out_xy[:, 0], out_xy[:, 1], "k-", lw=2, label="centerline")
        ax.plot(out_xy[:, 0] + (-np.sin(np.arctan2(np.gradient(out_xy[:,1]), np.gradient(out_xy[:,0]))) * wl),
                out_xy[:, 1] + (np.cos(np.arctan2(np.gradient(out_xy[:,1]), np.gradient(out_xy[:,0]))) * wl),
                color="#1f4e79", lw=1.5, label="left wall")
        ax.plot(out_xy[:, 0] + (np.sin(np.arctan2(np.gradient(out_xy[:,1]), np.gradient(out_xy[:,0]))) * wr),
                out_xy[:, 1] + (-np.cos(np.arctan2(np.gradient(out_xy[:,1]), np.gradient(out_xy[:,0]))) * wr),
                color="#c00000", lw=1.5, label="right wall")
        ax.scatter([out_xy[0, 0]], [out_xy[0, 1]], c="limegreen", s=90, marker="*", zorder=5, label="start")
        ax.set_aspect("equal")
        ax.legend(loc="best", fontsize=8)
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")
        ax.set_title(f"Map-raycast track  ({len(out_xy)} pts, width med {np.median(width):.2f} m)")
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.plot, dpi=160, bbox_inches="tight")
        plt.close(fig)
        print(f"  plot -> {args.plot}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
