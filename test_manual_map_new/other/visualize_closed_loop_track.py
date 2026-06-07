#!/usr/bin/env python3
"""
Chronological closed-loop map fusion for manual_map CSV runs.

This script treats each run as one lap-like trajectory, aligns runs by
phase shift (0..1 lap), then fuses centerline and corridor walls into a
single closed-loop map suitable for visualization and optimizer inputs.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_run(path: Path, moving_min_step: float) -> pd.DataFrame:
    df = pd.read_csv(path)
    needed = ["x", "y", "yaw_rad", "left_wall_m", "right_wall_m"]
    for col in needed:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["x", "y"]).reset_index(drop=True)

    if len(df) < 5:
        raise ValueError(f"{path.name}: too few valid rows")

    step = np.hypot(df["x"].diff().fillna(0.0), df["y"].diff().fillna(0.0))
    moving_idx = np.flatnonzero(step.to_numpy() > moving_min_step)
    start = int(moving_idx[0]) if len(moving_idx) else 0
    return df.iloc[start:].reset_index(drop=True)


def compute_phase(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    x = df["x"].to_numpy(float)
    y = df["y"].to_numpy(float)
    ds = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    if s[-1] <= 1e-9:
        raise ValueError("path length is zero")

    keep = np.concatenate([[True], np.diff(s) > 1e-9])
    s = s[keep]
    u = s / s[-1]
    return keep, u


def circular_interp(u: np.ndarray, vals: np.ndarray, uq: np.ndarray) -> np.ndarray:
    xp = np.concatenate([u, u + 1.0])
    fp = np.concatenate([vals, vals])
    return np.interp(np.mod(uq, 1.0), xp, fp)


def smooth_circular(vals: np.ndarray, window: int) -> np.ndarray:
    if window < 3:
        return vals.copy()
    if window % 2 == 0:
        window += 1
    n = len(vals)
    pad = window // 2
    ext = np.concatenate([vals[-pad:], vals, vals[:pad]])
    k = np.ones(window, dtype=float) / float(window)
    sm = np.convolve(ext, k, mode="valid")
    if len(sm) != n:
        sm = sm[:n]
    return sm


def trim_phase_window(
    u: np.ndarray,
    arrs: list[np.ndarray],
    trim_start_frac: float,
    trim_end_frac: float,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Trim early/late lap fractions then renormalize phase to [0, 1)."""
    t0 = float(np.clip(trim_start_frac, 0.0, 0.45))
    t1 = float(np.clip(trim_end_frac, 0.0, 0.45))
    if (t0 + t1) >= 0.90:
        return u, arrs
    mask = (u >= t0) & (u <= (1.0 - t1))
    if mask.sum() < 10:
        return u, arrs
    u2 = u[mask]
    span = max(u2[-1] - u2[0], 1e-6)
    u2 = (u2 - u2[0]) / span
    out = [a[mask] for a in arrs]
    return u2, out


def mad_reject_stack(stack: np.ndarray, z_thresh: float) -> np.ndarray:
    """
    Reject cross-run outliers per phase using MAD z-score.
    Returns a copy with outliers set to NaN.
    """
    if z_thresh <= 0:
        return stack.copy()
    med = np.nanmedian(stack, axis=0, keepdims=True)
    abs_dev = np.abs(stack - med)
    mad = np.nanmedian(abs_dev, axis=0, keepdims=True)
    sigma = np.maximum(1.4826 * mad, 1e-6)
    z = abs_dev / sigma
    out = stack.copy()
    out[z > z_thresh] = np.nan
    return out


def align_shift_to_reference(
    u: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    u_grid: np.ndarray,
    x_ref: np.ndarray,
    y_ref: np.ndarray,
    shift_grid_n: int,
) -> float:
    best_shift = 0.0
    best_cost = float("inf")
    for shift in np.linspace(0.0, 1.0, shift_grid_n, endpoint=False):
        xs = circular_interp(u, x, u_grid + shift)
        ys = circular_interp(u, y, u_grid + shift)
        cost = float(np.mean((xs - x_ref) ** 2 + (ys - y_ref) ** 2))
        if cost < best_cost:
            best_cost = cost
            best_shift = float(shift)
    return best_shift


def run_pipeline(args: argparse.Namespace) -> int:
    paths = sorted(args.data_dir.glob(args.glob))
    if not paths:
        raise SystemExit(f"No files matching {args.glob} in {args.data_dir}")

    runs: list[dict] = []
    for p in paths:
        df = load_run(p, args.moving_min_step)
        keep, u = compute_phase(df)
        d = df.loc[keep].reset_index(drop=True)
        x = d["x"].to_numpy(float)
        y = d["y"].to_numpy(float)
        yaw = d["yaw_rad"].to_numpy(float)
        w_l = d["left_wall_m"].to_numpy(float)
        w_r = d["right_wall_m"].to_numpy(float)
        u, [x, y, yaw, w_l, w_r] = trim_phase_window(
            u, [x, y, yaw, w_l, w_r], args.trim_start_frac, args.trim_end_frac
        )
        runs.append(
            {
                "name": p.name,
                "df": d,
                "u": u,
                "x": x,
                "y": y,
                "yaw": yaw,
                "w_l": w_l,
                "w_r": w_r,
                "path_len_m": float(np.hypot(np.diff(x), np.diff(y)).sum()),
            }
        )

    if args.reference_run:
        matches = [i for i, r in enumerate(runs) if r["name"] == args.reference_run]
        if not matches:
            raise SystemExit(
                f"--reference-run '{args.reference_run}' not found. "
                f"Available: {', '.join(r['name'] for r in runs)}"
            )
        ref_idx = int(matches[0])
    else:
        ref_idx = int(np.argmax([r["path_len_m"] for r in runs]))
    ref = runs[ref_idx]
    u_grid = np.linspace(0.0, 1.0, args.n_points, endpoint=False)
    x_ref = circular_interp(ref["u"], ref["x"], u_grid)
    y_ref = circular_interp(ref["u"], ref["y"], u_grid)

    for r in runs:
        shift = align_shift_to_reference(
            r["u"], r["x"], r["y"], u_grid, x_ref, y_ref, args.shift_grid
        )
        r["shift"] = shift
        r["x_s"] = circular_interp(r["u"], r["x"], u_grid + shift)
        r["y_s"] = circular_interp(r["u"], r["y"], u_grid + shift)
        r["yaw_s"] = circular_interp(r["u"], r["yaw"], u_grid + shift)
        r["wl_s"] = circular_interp(r["u"], r["w_l"], u_grid + shift)
        r["wr_s"] = circular_interp(r["u"], r["w_r"], u_grid + shift)

    x_stack = np.vstack([r["x_s"] for r in runs])
    y_stack = np.vstack([r["y_s"] for r in runs])
    wl_stack = np.vstack([r["wl_s"] for r in runs])
    wr_stack = np.vstack([r["wr_s"] for r in runs])

    x_stack = mad_reject_stack(x_stack, args.cross_run_mad_z)
    y_stack = mad_reject_stack(y_stack, args.cross_run_mad_z)
    wl_stack = mad_reject_stack(wl_stack, args.cross_run_mad_z)
    wr_stack = mad_reject_stack(wr_stack, args.cross_run_mad_z)

    x_med = np.nanmedian(x_stack, axis=0)
    y_med = np.nanmedian(y_stack, axis=0)
    wl_med = np.nanmedian(wl_stack, axis=0)
    wr_med = np.nanmedian(wr_stack, axis=0)

    w_ref = float(np.clip(args.reference_weight, 0.0, 1.0))
    x_c = (1.0 - w_ref) * x_med + w_ref * ref["x_s"]
    y_c = (1.0 - w_ref) * y_med + w_ref * ref["y_s"]
    wl = (1.0 - w_ref) * wl_med + w_ref * ref["wl_s"]
    wr = (1.0 - w_ref) * wr_med + w_ref * ref["wr_s"]

    x_c = smooth_circular(x_c, args.smooth_window)
    y_c = smooth_circular(y_c, args.smooth_window)
    wl = smooth_circular(wl, args.smooth_window)
    wr = smooth_circular(wr, args.smooth_window)

    width = np.maximum(wl + wr, args.min_width_m)
    wl = 0.5 * width
    wr = 0.5 * width

    dx = np.gradient(np.r_[x_c, x_c[0]])
    dy = np.gradient(np.r_[y_c, y_c[0]])
    yaw = np.unwrap(np.arctan2(dy[:-1], dx[:-1]))
    nx = -np.sin(yaw)
    ny = np.cos(yaw)

    lx = x_c + nx * wl
    ly = y_c + ny * wl
    rx = x_c - nx * wr
    ry = y_c - ny * wr

    ds = np.hypot(np.diff(np.r_[x_c, x_c[0]]), np.diff(np.r_[y_c, y_c[0]]))
    s = np.r_[0.0, np.cumsum(ds[:-1])]
    kappa = np.gradient(yaw, s, edge_order=1)

    out = pd.DataFrame(
        {
            "phase_u": u_grid,
            "s_m": s,
            "x_m": x_c,
            "y_m": y_c,
            "yaw_rad": yaw,
            "curvature_1pm": kappa,
            "left_wall_m": wl,
            "right_wall_m": wr,
            "track_width_m": width,
            "left_x_m": lx,
            "left_y_m": ly,
            "right_x_m": rx,
            "right_y_m": ry,
            "n_runs": len(runs),
        }
    )
    out = pd.concat([out, out.iloc[[0]].assign(phase_u=1.0, s_m=float(ds.sum()))], ignore_index=True)

    out_csv = args.data_dir / f"{args.out_prefix}_map_optimizer.csv"
    out.to_csv(out_csv, index=False)

    plot_dir = args.plot_dir or (args.data_dir / "_plots")
    plot_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 9))
    for r in runs:
        ax.plot(r["x_s"], r["y_s"], lw=1.0, alpha=0.35, label=f"{r['name']} (shift={r['shift']:.3f})")
    ax.plot(x_c, y_c, "k-", lw=2.5, label="fused centerline")
    ax.plot(lx, ly, "b-", lw=2.0, label="fused left wall")
    ax.plot(rx, ry, "r-", lw=2.0, label="fused right wall")
    ax.scatter([x_c[0]], [y_c[0]], c="limegreen", s=120, marker="*", zorder=6, label="phase start")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_title(f"Chronological closed-loop fusion ({len(runs)} runs)")
    fig.savefig(plot_dir / f"{args.out_prefix}_xy.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(out["s_m"], out["left_wall_m"], "b-", lw=1.7, label="left wall distance")
    ax.plot(out["s_m"], out["right_wall_m"], "r-", lw=1.7, label="right wall distance")
    ax.plot(out["s_m"], out["track_width_m"], "k-", lw=2.0, label="track width")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_xlabel("s [m]")
    ax.set_ylabel("distance [m]")
    ax.set_title("Closed-loop wall profile")
    fig.savefig(plot_dir / f"{args.out_prefix}_wall_profile.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    print(f"Runs: {len(runs)}")
    print(f"Reference: {ref['name']}  (weight={w_ref:.2f})")
    print(
        f"Trim: start={args.trim_start_frac:.3f} end={args.trim_end_frac:.3f}  "
        f"cross-run MAD z<={args.cross_run_mad_z:.2f}"
    )
    for r in runs:
        print(f"  {r['name']}: path={r['path_len_m']:.2f}m shift={r['shift']:.4f}")
    print(f"Wrote: {out_csv}")
    print(f"Wrote: {plot_dir / f'{args.out_prefix}_xy.png'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--glob", default="manual_map*.csv")
    ap.add_argument("--n-points", type=int, default=360, help="Output samples per loop")
    ap.add_argument("--shift-grid", type=int, default=240, help="Phase-shift search resolution")
    ap.add_argument("--moving-min-step", type=float, default=0.005)
    ap.add_argument("--smooth-window", type=int, default=11, help="Circular smoothing window")
    ap.add_argument("--min-width-m", type=float, default=0.35, help="Minimum loop corridor width")
    ap.add_argument("--trim-start-frac", type=float, default=0.03, help="Trim this fraction from start of each run")
    ap.add_argument("--trim-end-frac", type=float, default=0.03, help="Trim this fraction from end of each run")
    ap.add_argument("--cross-run-mad-z", type=float, default=3.0, help="Cross-run outlier reject threshold (MAD z)")
    ap.add_argument("--reference-run", default=None, help="CSV filename to anchor shape (e.g. manual_map03.csv)")
    ap.add_argument("--reference-weight", type=float, default=0.50, help="Blend weight toward reference run [0..1]")
    ap.add_argument("--out-prefix", default="closed_loop", help="Output prefix for CSV and plots")
    ap.add_argument("--plot-dir", type=Path, default=None)
    args = ap.parse_args()
    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
