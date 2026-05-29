#!/usr/bin/env python3
"""Quick wall-map visualizer for ONE manual_map run CSV (your notebook math)."""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--drop-stationary", action="store_true",
                    help="Drop leading frozen (x=y=0) rows before moving")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    for c in ("x", "y", "yaw_rad", "left_wall_m", "right_wall_m"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["x", "y", "yaw_rad"])

    if args.drop_stationary:
        moving = (df["x"].abs() > 1e-6) | (df["y"].abs() > 1e-6)
        if moving.any():
            df = df.loc[moving.idxmax():]

    x = df["x"].to_numpy()
    y = df["y"].to_numpy()
    yaw = df["yaw_rad"].to_numpy()
    wL = df["left_wall_m"].to_numpy()
    wR = df["right_wall_m"].to_numpy()

    nx, ny = -np.sin(yaw), np.cos(yaw)
    left_x = np.where(np.isfinite(wL), x + nx * wL, np.nan)
    left_y = np.where(np.isfinite(wL), y + ny * wL, np.nan)
    right_x = np.where(np.isfinite(wR), x - nx * wR, np.nan)
    right_y = np.where(np.isfinite(wR), y - ny * wR, np.nan)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(x, y, s=12, c="black", label="Centerline (pose)")
    ax.scatter(left_x, left_y, s=12, c="blue", label="Left wall")
    ax.scatter(right_x, right_y, s=12, c="red", label="Right wall")
    ax.plot(x, y, color="0.6", lw=0.8, alpha=0.7)
    ax.scatter([x[0]], [y[0]], s=160, marker="*", c="green", zorder=5, label="start")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(f"Track wall map — {args.csv.name} ({len(df)} rows)")

    out = args.out or (args.csv.parent / "_plots" / f"{args.csv.stem}_map.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)

    moved = float(np.hypot(np.diff(x), np.diff(y)).sum())
    print(f"rows={len(df)}  x[{x.min():.2f},{x.max():.2f}]  y[{y.min():.2f},{y.max():.2f}]  path={moved:.2f} m")
    print(f"left_wall finite={np.isfinite(wL).sum()}  right_wall finite={np.isfinite(wR).sum()}")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
