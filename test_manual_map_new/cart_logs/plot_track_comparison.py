#!/usr/bin/env python3
"""Side-by-side racetrack visualization: TUM reference vs manual_map cart log."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon


def load_berlin(path: Path) -> pd.DataFrame:
    rows: list[list[float]] = []
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or ln.startswith("Source") or ln.startswith("Title"):
            continue
        if ln.lower().startswith("x_m"):
            continue
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) >= 4:
            rows.append([float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])])
    df = pd.DataFrame(rows, columns=["x_m", "y_m", "w_tr_right_m", "w_tr_left_m"])
    return walls_from_tum(df)


def walls_from_tum(df: pd.DataFrame) -> pd.DataFrame:
    x = df["x_m"].to_numpy(float)
    y = df["y_m"].to_numpy(float)
    wr = df["w_tr_right_m"].to_numpy(float)
    wl = df["w_tr_left_m"].to_numpy(float)
    dx = np.gradient(np.r_[x, x[0]])
    dy = np.gradient(np.r_[y, y[0]])
    yaw = np.unwrap(np.arctan2(dy[:-1], dx[:-1]))
    nx = -np.sin(yaw)
    ny = np.cos(yaw)
    out = df.copy()
    out["left_x_m"] = x + nx * wl
    out["left_y_m"] = y + ny * wl
    out["right_x_m"] = x - nx * wr
    out["right_y_m"] = y - ny * wr
    out["track_width_m"] = wl + wr
    return out


def load_optimizer(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.iloc[-1]["x_m"] == df.iloc[0]["x_m"] and df.iloc[-1]["y_m"] == df.iloc[0]["y_m"]:
        df = df.iloc[:-1].copy()
    return df


def path_len_m(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.hypot(np.diff(x), np.diff(y)).sum())


def draw_track(ax, df: pd.DataFrame, *, title: str, subtitle: str) -> None:
    x = df["x_m"].to_numpy(float)
    y = df["y_m"].to_numpy(float)
    lx = df["left_x_m"].to_numpy(float)
    ly = df["left_y_m"].to_numpy(float)
    rx = df["right_x_m"].to_numpy(float)
    ry = df["right_y_m"].to_numpy(float)
    verts = np.vstack([np.column_stack([lx, ly]), np.column_stack([rx[::-1], ry[::-1]])])
    ax.add_patch(Polygon(verts, closed=True, facecolor="#c8e6c9", edgecolor="none", alpha=0.55, zorder=2))
    ax.plot(lx, ly, color="#1f4e79", lw=1.8, label="left boundary", zorder=4)
    ax.plot(rx, ry, color="#c00000", lw=1.8, label="right boundary", zorder=4)
    ax.plot(x, y, "k-", lw=2.2, label="centerline", zorder=5)
    ax.scatter([x[0]], [y[0]], s=100, marker="*", c="limegreen", zorder=6, label="start")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_title(f"{title}\n{subtitle}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--berlin", type=Path, required=True)
    ap.add_argument("--ours", type=Path, required=True, help="racetrack_map_optimizer.csv")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    berlin = load_berlin(args.berlin)
    ours = load_optimizer(args.ours)

    b_len = path_len_m(berlin.x_m.to_numpy(), berlin.y_m.to_numpy())
    o_len = float(ours["s_m"].iloc[-1]) if "s_m" in ours.columns else path_len_m(
        ours.x_m.to_numpy(), ours.y_m.to_numpy()
    )

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    draw_track(
        axes[0],
        berlin,
        title="Berlin 2018 (TUM Formula Student track)",
        subtitle=f"{len(berlin)} pts · {b_len/1000:.2f} km · width ≈ {berlin.track_width_m.median():.1f} m",
    )
    draw_track(
        axes[1],
        ours,
        title="UCSD hose track (Cartographer manual_map)",
        subtitle=f"{len(ours)} pts · {o_len:.1f} m · width ≈ {ours.track_width_m.median():.2f} m",
    )
    fig.suptitle(
        "RoboRacer track comparison — Berlin is hand-designed survey data; ours is one SLAM lap",
        fontsize=11,
        y=1.02,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
