#!/usr/bin/env python3
"""Plot manual_map_logger CSV in map frame; trim leading stationary samples."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon


def trim_until_moved(
    df: pd.DataFrame,
    *,
    min_path_m: float,
    min_displacement_m: float,
) -> tuple[pd.DataFrame, int]:
    """Drop leading rows until the car has actually moved."""
    if df.empty:
        return df, 0

    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    x0, y0 = x[0], y[0]

    step = np.hypot(np.diff(x), np.diff(y))
    cum_path = np.concatenate([[0.0], np.cumsum(step)])
    disp = np.hypot(x - x0, y - y0)

    # Prefer displacement from first pose (jitter near origin can inflate cum_path).
    start = 0
    for i in range(len(df)):
        if disp[i] >= min_displacement_m:
            start = i
            break
    else:
        for i in range(len(df)):
            if cum_path[i] >= min_path_m:
                start = i
                break

    return df.iloc[start:].reset_index(drop=True), start


def wall_xy(
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


def dedupe_stationary(df: pd.DataFrame, min_step_m: float) -> pd.DataFrame:
    """Drop consecutive rows that barely move (duplicate scan stamps / joystick hold)."""
    if len(df) < 2:
        return df
    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    step = np.hypot(np.diff(x), np.diff(y))
    keep = np.concatenate([[True], step > min_step_m])
    return df.iloc[keep].reset_index(drop=True)


def trim_until_path(df: pd.DataFrame, min_path_m: float) -> tuple[pd.DataFrame, int]:
    if df.empty or min_path_m <= 0:
        return df, 0
    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    step = np.hypot(np.diff(x), np.diff(y))
    cum = np.cumsum(step)
    idx = int(np.argmax(cum >= min_path_m))
    if cum[idx] < min_path_m:
        return df, 0
    return df.iloc[idx:].reset_index(drop=True), idx


def keep_longest_continuous_segment(df: pd.DataFrame, max_step_m: float) -> tuple[pd.DataFrame, int]:
    """Split at large pose jumps (odom/SLAM glitches) and keep the longest segment."""
    if len(df) < 2 or max_step_m <= 0:
        return df, 0
    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    step = np.hypot(np.diff(x), np.diff(y))
    breaks = np.flatnonzero(step > max_step_m) + 1
    cuts = np.concatenate([[0], breaks, [len(df)]])
    best = (0, len(df), 0.0)
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 5:
            continue
        seg_len = float(step[a : b - 1].sum()) if b - a > 1 else 0.0
        if seg_len > best[2]:
            best = (a, b, seg_len)
    a, b, _ = best
    dropped = len(df) - (b - a)
    if a == 0 and b == len(df):
        return df, 0
    return df.iloc[a:b].reset_index(drop=True), dropped


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
    return sm[:n]


def trim_phase_window(
    u: np.ndarray,
    arrs: list[np.ndarray],
    trim_start_frac: float,
    trim_end_frac: float,
) -> tuple[np.ndarray, list[np.ndarray]]:
    t0 = float(np.clip(trim_start_frac, 0.0, 0.45))
    t1 = float(np.clip(trim_end_frac, 0.0, 0.45))
    if (t0 + t1) >= 0.90:
        return u, arrs
    mask = (u >= t0) & (u <= (1.0 - t1))
    if mask.sum() < 10:
        return u, arrs
    u2 = u[mask]
    span = max(float(u2[-1] - u2[0]), 1e-6)
    u2 = (u2 - u2[0]) / span
    return u2, [a[mask] for a in arrs]


def filter_2sd(vals: np.ndarray, n_sd: float) -> np.ndarray:
    """Return boolean mask keeping samples within n_sd of median absolute deviation."""
    if n_sd <= 0 or len(vals) == 0:
        return np.ones(len(vals), dtype=bool)
    v = vals[np.isfinite(vals)]
    if len(v) < 3:
        return np.isfinite(vals)
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    sigma = max(1.4826 * mad, 0.05)
    return np.isfinite(vals) & (np.abs(vals - med) <= n_sd * sigma)


def fuse_wall_distances_along_phase(
    u: np.ndarray,
    w_l: np.ndarray,
    w_r: np.ndarray,
    u_grid: np.ndarray,
    n_sd: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Median left/right range per lap station (matches hose spacing from /scan)."""
    n = len(u_grid)
    half_bin = 0.5 / max(n, 1)
    wl_out = np.full(n, np.nan)
    wr_out = np.full(n, np.nan)
    for j, ug in enumerate(u_grid):
        mask = np.abs(np.mod(u - ug + 0.5, 1.0) - 0.5) <= half_bin
        if not mask.any():
            continue
        wl = w_l[mask]
        wr = w_r[mask]
        wl = wl[np.isfinite(wl)]
        wr = wr[np.isfinite(wr)]
        if len(wl):
            keep = filter_2sd(wl, n_sd)
            if keep.any():
                wl_out[j] = float(np.median(wl[keep]))
        if len(wr):
            keep = filter_2sd(wr, n_sd)
            if keep.any():
                wr_out[j] = float(np.median(wr[keep]))
    wl_out = pd.Series(wl_out).interpolate(limit_direction="both").to_numpy()
    wr_out = pd.Series(wr_out).interpolate(limit_direction="both").to_numpy()
    return wl_out, wr_out


def wall_hits_lateral_envelope(
    u: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    yaw: np.ndarray,
    w_l: np.ndarray,
    w_r: np.ndarray,
    *,
    u_grid: np.ndarray,
    x_c: np.ndarray,
    y_c: np.ndarray,
    nx: np.ndarray,
    ny: np.ndarray,
    n_sd: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Outer envelope of raw lidar wall hits in track frame (honest, no synthetic offset)."""
    n = len(u_grid)
    half_bin = 0.5 / max(n, 1)
    left_bins: list[list[float]] = [[] for _ in range(n)]
    right_bins: list[list[float]] = [[] for _ in range(n)]
    bx = -np.sin(yaw)
    by = np.cos(yaw)

    for ui, xi, yi, wli, wri, bxi, byi in zip(u, x, y, w_l, w_r, bx, by):
        j = int(np.argmin(np.abs(np.mod(u_grid - ui + 0.5, 1.0) - 0.5)))
        cx, cy = x_c[j], y_c[j]
        nnx, nny = nx[j], ny[j]
        if np.isfinite(wli):
            lx = xi + bxi * wli
            ly = yi + byi * wli
            left_bins[j].append(float((lx - cx) * nnx + (ly - cy) * nny))
        if np.isfinite(wri):
            rx = xi - bxi * wri
            ry = yi - byi * wri
            right_bins[j].append(float((rx - cx) * nnx + (ry - cy) * nny))

    left_d = np.full(n, np.nan)
    right_d = np.full(n, np.nan)
    for j in range(n):
        if left_bins[j]:
            arr = np.asarray(left_bins[j], dtype=float)
            keep = filter_2sd(arr, n_sd)
            if keep.any():
                left_d[j] = float(np.max(arr[keep]))
        if right_bins[j]:
            arr = np.asarray(right_bins[j], dtype=float)
            keep = filter_2sd(arr, n_sd)
            if keep.any():
                right_d[j] = float(np.min(arr[keep]))

    left_d = pd.Series(left_d).interpolate(limit_direction="both").to_numpy()
    right_d = pd.Series(right_d).interpolate(limit_direction="both").to_numpy()
    if float(np.nanmedian(left_d - right_d)) < 0:
        left_d, right_d = right_d, left_d
    return left_d, right_d


def centerline_normals(x_c: np.ndarray, y_c: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    dx = np.gradient(np.r_[x_c, x_c[0]])
    dy = np.gradient(np.r_[y_c, y_c[0]])
    yaw_c = np.unwrap(np.arctan2(dy[:-1], dx[:-1]))
    nx = -np.sin(yaw_c)
    ny = np.cos(yaw_c)
    ds_loop = np.hypot(np.diff(np.r_[x_c, x_c[0]]), np.diff(np.r_[y_c, y_c[0]]))
    s_loop = np.r_[0.0, np.cumsum(ds_loop[:-1])]
    kappa = np.gradient(yaw_c, s_loop, edge_order=1)
    return nx, ny, yaw_c, kappa


def offset_boundaries(
    x_c: np.ndarray,
    y_c: np.ndarray,
    wl: np.ndarray,
    wr: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    nx, ny, _, _ = centerline_normals(x_c, y_c)
    lx = x_c + nx * wl
    ly = y_c + ny * wl
    rx = x_c - nx * wr
    ry = y_c - ny * wr
    return lx, ly, rx, ry


def cap_widths_for_curvature(
    wl: np.ndarray,
    wr: np.ndarray,
    kappa: np.ndarray,
    *,
    margin_m: float = 0.08,
    min_cap_m: float = 0.2,
) -> tuple[np.ndarray, np.ndarray]:
    """Limit inner-side offset where turn radius is tighter than the requested wall distance."""
    rho = 1.0 / (np.abs(kappa) + 1e-9)
    inner_cap = np.maximum(rho - margin_m, min_cap_m)
    wl_out = np.where(kappa > 0, np.minimum(wl, inner_cap), wl)
    wr_out = np.where(kappa < 0, np.minimum(wr, inner_cap), wr)
    return wl_out, wr_out


def boundaries_valid(lx: np.ndarray, ly: np.ndarray, rx: np.ndarray, ry: np.ndarray) -> bool:
    return not offset_loop_self_intersects(lx, ly) and not offset_loop_self_intersects(rx, ry)


def offset_loop_self_intersects(x: np.ndarray, y: np.ndarray, *, eps: float = 1e-4) -> bool:
    """True if closed polyline self-intersects (local segment pairs)."""
    n = len(x)
    if n < 4:
        return False
    pts = list(zip(x, y))

    def cross(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def seg_cross(i: int, j: int) -> bool:
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3, p4 = pts[j], pts[(j + 1) % n]
        d1 = cross(p1, p2, p3)
        d2 = cross(p1, p2, p4)
        d3 = cross(p3, p4, p1)
        d4 = cross(p3, p4, p2)
        if max(abs(d1), abs(d2), abs(d3), abs(d4)) < eps:
            return False
        return ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and (
            (d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)
        )

    min_gap = 5
    for i in range(n):
        for j in range(i + min_gap, n - min_gap if i == 0 else n):
            if j == (i + n - 1) % n:
                continue
            if seg_cross(i, j):
                return True
    return False


def build_honest_racetrack(
    df: pd.DataFrame,
    *,
    n_points: int,
    smooth_window: int,
    trim_start_frac: float,
    trim_end_frac: float,
    min_width_m: float,
    wall_n_sd: float,
) -> tuple[pd.DataFrame, int, float, float]:
    """
    Honest loop: smoothed driven centerline + boundaries from /scan median widths.
    Logged L/R medians are preserved in output columns; boundary geometry uses the
    symmetric half-width (avg of L/R) so tight SLAM kinks do not fold the corridor.
    """
    _ = wall_n_sd
    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    w_l = df["left_wall_m"].to_numpy(dtype=float)
    w_r = df["right_wall_m"].to_numpy(dtype=float)

    med_wl = float(np.nanmedian(w_l[np.isfinite(w_l)]))
    med_wr = float(np.nanmedian(w_r[np.isfinite(w_r)]))
    if not math.isfinite(med_wl) or med_wl <= 0:
        med_wl = 0.8
    if not math.isfinite(med_wr) or med_wr <= 0:
        med_wr = 0.8
    half_w = 0.5 * (med_wl + med_wr)

    ds = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    if s[-1] <= 1e-6:
        raise ValueError("path length is zero after trim")

    keep = np.concatenate([[True], np.diff(s) > 1e-9])
    u = s[keep] / s[-1]
    x, y, w_l, w_r = (a[keep] for a in (x, y, w_l, w_r))
    u, [x, y, w_l, w_r] = trim_phase_window(u, [x, y, w_l, w_r], trim_start_frac, trim_end_frac)

    u_grid = np.linspace(0.0, 1.0, n_points, endpoint=False)
    x_c = circular_interp(u, x, u_grid)
    y_c = circular_interp(u, y, u_grid)
    raw_loop_m = float(np.hypot(np.diff(np.r_[x_c, x_c[0]]), np.diff(np.r_[y_c, y_c[0]])).sum())

    if half_w < 0.5 * min_width_m:
        half_w = 0.5 * min_width_m

    used_smooth = smooth_window
    lx = ly = rx = ry = None
    for try_w in range(smooth_window, min(72, smooth_window + 41), 4):
        x_s = smooth_circular(x_c, try_w)
        y_s = smooth_circular(y_c, try_w)
        loop_m = float(np.hypot(np.diff(np.r_[x_s, x_s[0]]), np.diff(np.r_[y_s, y_s[0]])).sum())
        if loop_m < 0.85 * raw_loop_m:
            break
        lx_t, ly_t, rx_t, ry_t = offset_boundaries(
            x_s, y_s, np.full(len(u_grid), half_w), np.full(len(u_grid), half_w)
        )
        if boundaries_valid(lx_t, ly_t, rx_t, ry_t):
            x_c, y_c, used_smooth = x_s, y_s, try_w
            lx, ly, rx, ry = lx_t, ly_t, rx_t, ry_t
            break

    nx, ny, yaw_c, kappa = centerline_normals(x_c, y_c)
    wl = np.full(len(u_grid), med_wl)
    wr = np.full(len(u_grid), med_wr)
    if lx is None:
        lx, ly, rx, ry = offset_boundaries(
            x_c, y_c, np.full(len(u_grid), half_w), np.full(len(u_grid), half_w)
        )

    ds_loop = np.hypot(np.diff(np.r_[x_c, x_c[0]]), np.diff(np.r_[y_c, y_c[0]]))
    s_loop = np.r_[0.0, np.cumsum(ds_loop[:-1])]
    kappa = np.gradient(yaw_c, s_loop, edge_order=1)

    out = pd.DataFrame(
        {
            "phase_u": u_grid,
            "s_m": s_loop,
            "x_m": x_c,
            "y_m": y_c,
            "yaw_rad": yaw_c,
            "curvature_1pm": kappa,
            "left_wall_m": wl,
            "right_wall_m": wr,
            "track_width_m": wl + wr,
            "left_x_m": lx,
            "left_y_m": ly,
            "right_x_m": rx,
            "right_y_m": ry,
        }
    )
    out = pd.concat([out, out.iloc[[0]].assign(phase_u=1.0, s_m=float(ds_loop.sum()))], ignore_index=True)
    return out, used_smooth, med_wl, med_wr


def build_closed_loop_racetrack(
    df: pd.DataFrame,
    *,
    n_points: int,
    smooth_window: int,
    trim_start_frac: float,
    trim_end_frac: float,
    min_width_m: float,
    wall_n_sd: float,
) -> pd.DataFrame:
    """Resample one lap by phase, smooth centerline, fuse walls in track frame."""
    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    yaw = df["yaw_rad"].to_numpy(dtype=float)
    w_l = df["left_wall_m"].to_numpy(dtype=float)
    w_r = df["right_wall_m"].to_numpy(dtype=float)

    ds = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    if s[-1] <= 1e-6:
        raise ValueError("path length is zero after trim")

    keep = np.concatenate([[True], np.diff(s) > 1e-9])
    u = s[keep] / s[-1]
    x, y, yaw, w_l, w_r = (a[keep] for a in (x, y, yaw, w_l, w_r))
    u, [x, y, yaw, w_l, w_r] = trim_phase_window(
        u, [x, y, yaw, w_l, w_r], trim_start_frac, trim_end_frac
    )

    u_grid = np.linspace(0.0, 1.0, n_points, endpoint=False)
    x_c = circular_interp(u, x, u_grid)
    y_c = circular_interp(u, y, u_grid)
    x_c = smooth_circular(x_c, smooth_window)
    y_c = smooth_circular(y_c, smooth_window)

    dx = np.gradient(np.r_[x_c, x_c[0]])
    dy = np.gradient(np.r_[y_c, y_c[0]])
    yaw_c = np.unwrap(np.arctan2(dy[:-1], dx[:-1]))
    nx = -np.sin(yaw_c)
    ny = np.cos(yaw_c)

    left_d, right_d = fuse_wall_distances_along_phase(
        u, w_l, w_r, u_grid, wall_n_sd,
    )
    wl = smooth_circular(left_d, smooth_window)
    wr = smooth_circular(right_d, smooth_window)
    wl = np.clip(wl, 0.25, 2.5)
    wr = np.clip(wr, 0.25, 2.5)

    # Hose track is a symmetric corridor — average L/R like Berlin's parallel boundaries.
    half = 0.5 * (wl + wr)
    half = smooth_circular(half, max(smooth_window, 21))
    med_half = float(np.median(half))
    half = np.clip(half, 0.75 * med_half, 1.25 * med_half)
    half = np.maximum(half, 0.5 * min_width_m)
    wl = wr = half

    lx = x_c + nx * wl
    ly = y_c + ny * wl
    rx = x_c - nx * wr
    ry = y_c - ny * wr

    ds_loop = np.hypot(np.diff(np.r_[x_c, x_c[0]]), np.diff(np.r_[y_c, y_c[0]]))
    s_loop = np.r_[0.0, np.cumsum(ds_loop[:-1])]
    kappa = np.gradient(yaw_c, s_loop, edge_order=1)

    out = pd.DataFrame(
        {
            "phase_u": u_grid,
            "s_m": s_loop,
            "x_m": x_c,
            "y_m": y_c,
            "yaw_rad": yaw_c,
            "curvature_1pm": kappa,
            "left_wall_m": wl,
            "right_wall_m": wr,
            "track_width_m": wl + wr,
            "left_x_m": lx,
            "left_y_m": ly,
            "right_x_m": rx,
            "right_y_m": ry,
        }
    )
    return pd.concat([out, out.iloc[[0]].assign(phase_u=1.0, s_m=float(ds_loop.sum()))], ignore_index=True)


def plot_honest_racetrack_map(
    track: pd.DataFrame,
    *,
    title: str,
    out: Path,
    raw_xy: tuple[np.ndarray, np.ndarray],
    raw_walls: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    smooth_window: int,
    med_wl: float,
    med_wr: float,
) -> None:
    x_c = track["x_m"].iloc[:-1].to_numpy()
    y_c = track["y_m"].iloc[:-1].to_numpy()
    lx = track["left_x_m"].iloc[:-1].to_numpy()
    ly = track["left_y_m"].iloc[:-1].to_numpy()
    rx = track["right_x_m"].iloc[:-1].to_numpy()
    ry = track["right_y_m"].iloc[:-1].to_numpy()
    rx_s, ry_s, lx_s, ly_s = raw_walls

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.scatter(raw_xy[0], raw_xy[1], s=8, c="0.55", alpha=0.45, label="driven path (logged)", zorder=1)
    ax.scatter(lx_s, ly_s, s=5, c="#6fa8dc", alpha=0.25, label="left wall hits (/scan)", zorder=2)
    ax.scatter(rx_s, ry_s, s=5, c="#e06666", alpha=0.25, label="right wall hits (/scan)", zorder=2)

    fill_ok = not offset_loop_self_intersects(lx, ly) and not offset_loop_self_intersects(rx, ry)
    if fill_ok:
        verts = np.vstack([np.column_stack([lx, ly]), np.column_stack([rx[::-1], ry[::-1]])])
        ax.add_patch(Polygon(verts, closed=True, facecolor="#c8e6c9", edgecolor="none", alpha=0.4, zorder=3))

    ax.plot(lx, ly, color="#1f4e79", lw=2.0, label=f"left wall (~{0.5*(med_wl+med_wr):.2f} m half)", zorder=4)
    ax.plot(rx, ry, color="#c00000", lw=2.0, label=f"right wall (~{0.5*(med_wl+med_wr):.2f} m half)", zorder=4)
    ax.plot(x_c, y_c, "k-", lw=2.4, label=f"centerline (smooth w={smooth_window})", zorder=5)
    ax.scatter([x_c[0]], [y_c[0]], s=120, marker="*", c="limegreen", zorder=6, label="start")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_title(
        title
        + f"\nhonest /scan: L={med_wl:.2f} m R={med_wr:.2f} m (total {med_wl + med_wr:.2f} m); "
        f"corridor symmetric at {0.5 * (med_wl + med_wr):.2f} m half-width"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)


def plot_racetrack_map(
    track: pd.DataFrame,
    *,
    title: str,
    out: Path,
    raw_xy: tuple[np.ndarray, np.ndarray] | None = None,
) -> None:
    x_c = track["x_m"].iloc[:-1].to_numpy()
    y_c = track["y_m"].iloc[:-1].to_numpy()
    lx = track["left_x_m"].iloc[:-1].to_numpy()
    ly = track["left_y_m"].iloc[:-1].to_numpy()
    rx = track["right_x_m"].iloc[:-1].to_numpy()
    ry = track["right_y_m"].iloc[:-1].to_numpy()

    verts = np.vstack([np.column_stack([lx, ly]), np.column_stack([rx[::-1], ry[::-1]])])

    fig, ax = plt.subplots(figsize=(12, 8))
    if raw_xy is not None:
        ax.scatter(raw_xy[0], raw_xy[1], s=6, c="0.82", alpha=0.35, label="logged samples", zorder=1)
    ax.add_patch(Polygon(verts, closed=True, facecolor="#c8e6c9", edgecolor="none", alpha=0.55, zorder=2))
    ax.plot(lx, ly, color="#1f4e79", lw=2.2, label="left boundary", zorder=4)
    ax.plot(rx, ry, color="#c00000", lw=2.2, label="right boundary", zorder=4)
    ax.plot(x_c, y_c, "k-", lw=2.6, label="centerline", zorder=5)
    ax.scatter([x_c[0]], [y_c[0]], s=140, marker="*", c="limegreen", zorder=6, label="start")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_title(title)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="manual_map_logger output CSV")
    ap.add_argument("--out", type=Path, default=None, help="PNG output path")
    ap.add_argument(
        "--trim-until-path-m",
        type=float,
        default=1.0,
        help="Fallback: trim once cumulative path exceeds this [m] if displacement never triggers",
    )
    ap.add_argument(
        "--trim-until-displacement-m",
        type=float,
        default=0.20,
        help="Drop leading rows once distance from first pose exceeds this [m]",
    )
    ap.add_argument(
        "--save-trimmed-csv",
        type=Path,
        default=None,
        help="Optional path to write trimmed CSV",
    )
    ap.add_argument(
        "--racetrack",
        action="store_true",
        help="Closed-loop racetrack map: smooth centerline + corridor fill",
    )
    ap.add_argument(
        "--racetrack-honest",
        action="store_true",
        help="Honest racetrack: raw /scan wall scatter + envelope boundaries (no fake parallel walls)",
    )
    ap.add_argument("--n-points", type=int, default=360, help="Samples around loop (racetrack mode)")
    ap.add_argument("--smooth-window", type=int, default=31, help="Circular smooth window (racetrack)")
    ap.add_argument("--trim-phase-start", type=float, default=0.03, help="Trim lap fraction at start")
    ap.add_argument("--trim-phase-end", type=float, default=0.03, help="Trim lap fraction at end")
    ap.add_argument("--min-width-m", type=float, default=1.2, help="Minimum corridor width [m] (hose track ~1.5–2.0)")
    ap.add_argument("--wall-n-sd", type=float, default=2.0, help="Lateral wall outlier reject (track-frame bins)")
    ap.add_argument(
        "--skip-until-path-m",
        type=float,
        default=0.0,
        help="After displacement trim, drop rows until this path length [m] (skip pre-lap wiggle)",
    )
    ap.add_argument(
        "--dedupe-step-m",
        type=float,
        default=0.01,
        help="Drop consecutive rows moving less than this [m]",
    )
    ap.add_argument(
        "--save-racetrack-csv",
        type=Path,
        default=None,
        help="Write optimizer-style closed-loop CSV (racetrack mode)",
    )
    ap.add_argument(
        "--max-step-m",
        type=float,
        default=0.0,
        help="Split at pose jumps above this [m] and keep longest continuous segment",
    )
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    for c in ("x", "y", "yaw_rad", "left_wall_m", "right_wall_m"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["x", "y", "yaw_rad"]).reset_index(drop=True)

    raw_n = len(df)
    df, dropped = trim_until_moved(
        df,
        min_path_m=args.trim_until_path_m,
        min_displacement_m=args.trim_until_displacement_m,
    )
    if args.dedupe_step_m > 0:
        df = dedupe_stationary(df, args.dedupe_step_m)
    path_skipped = 0
    jump_dropped = 0
    if args.max_step_m > 0:
        df, jump_dropped = keep_longest_continuous_segment(df, args.max_step_m)
    if args.skip_until_path_m > 0:
        df, path_skipped = trim_until_path(df, args.skip_until_path_m)
    if (args.racetrack or args.racetrack_honest) and args.skip_until_path_m <= 0 and path_skipped == 0:
        # Skip small pre-lap orbit when building a closed loop from one drive.
        x = df["x"].to_numpy(dtype=float)
        y = df["y"].to_numpy(dtype=float)
        disp0 = np.hypot(x - x[0], y - y[0])
        if float(np.max(disp0)) < 0.35:
            df, path_skipped = trim_until_path(df, 2.5)

    x = df["x"].to_numpy()
    y = df["y"].to_numpy()
    yaw = df["yaw_rad"].to_numpy()
    w_l = df["left_wall_m"].to_numpy()
    w_r = df["right_wall_m"].to_numpy()
    lx, ly, rx, ry = wall_xy(x, y, yaw, w_l, w_r)

    if args.racetrack_honest or args.racetrack:
        if args.racetrack_honest:
            track, used_smooth, med_wl, med_wr = build_honest_racetrack(
                df,
                n_points=args.n_points,
                smooth_window=args.smooth_window,
                trim_start_frac=args.trim_phase_start,
                trim_end_frac=args.trim_phase_end,
                min_width_m=args.min_width_m,
                wall_n_sd=args.wall_n_sd,
            )
            suffix = "honest_racetrack"
            out = args.out or (args.csv.parent / "_plots" / f"{args.csv.stem}_{suffix}_map.png")
            plot_honest_racetrack_map(
                track,
                title=(
                    f"{args.csv.name} — honest racetrack ({args.n_points} pts, smooth={used_smooth})\n"
                    f"trimmed {dropped}/{raw_n}, path_skip={path_skipped}, jump_drop={jump_dropped}, "
                    f"loop≈{track['s_m'].iloc[-1]:.2f} m"
                ),
                out=out,
                raw_xy=(x, y),
                raw_walls=(rx, ry, lx, ly),
                smooth_window=used_smooth,
                med_wl=med_wl,
                med_wr=med_wr,
            )
        else:
            track = build_closed_loop_racetrack(
                df,
                n_points=args.n_points,
                smooth_window=args.smooth_window,
                trim_start_frac=args.trim_phase_start,
                trim_end_frac=args.trim_phase_end,
                min_width_m=args.min_width_m,
                wall_n_sd=args.wall_n_sd,
            )
            suffix = "racetrack"
            out = args.out or (args.csv.parent / "_plots" / f"{args.csv.stem}_{suffix}_map.png")
            plot_racetrack_map(
                track,
                title=(
                    f"{args.csv.name} — racetrack map ({args.n_points} pts)\n"
                    f"trimmed {dropped}/{raw_n}, path_skip={path_skipped}, jump_drop={jump_dropped}, "
                    f"loop≈{track['s_m'].iloc[-1]:.2f} m"
                ),
                out=out,
                raw_xy=(x, y),
            )
        racetrack_csv = args.save_racetrack_csv or (
            args.csv.parent / f"{args.csv.stem}_{suffix}_map_optimizer.csv"
        )
        track.to_csv(racetrack_csv, index=False)
        gap = math.hypot(
            track["x_m"].iloc[0] - track["x_m"].iloc[-2],
            track["y_m"].iloc[0] - track["y_m"].iloc[-2],
        )
        print(f"raw_rows={raw_n}  trimmed_rows={len(df)}  dropped_leading={dropped}  path_skip={path_skipped}  jump_drop={jump_dropped}")
        print(f"racetrack loop≈{track['s_m'].iloc[-1]:.2f} m  closure_gap={gap:.3f} m  width≈{track['track_width_m'].iloc[:-1].median():.2f} m")
        print(f"→ {out}")
        print(f"→ {racetrack_csv}")
        if args.save_trimmed_csv:
            args.save_trimmed_csv.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(args.save_trimmed_csv, index=False)
            print(f"→ {args.save_trimmed_csv}")
        return 0

    fig, ax = plt.subplots(figsize=(11, 9))
    ax.scatter(x, y, s=10, c="black", alpha=0.5, label="Centerline (map frame)")
    ax.scatter(lx, ly, s=6, c="blue", alpha=0.35, label="Left wall")
    ax.scatter(rx, ry, s=6, c="red", alpha=0.35, label="Right wall")
    ax.plot(x, y, color="0.45", lw=1.2, alpha=0.85, label="Driven path")
    ax.scatter([x[0]], [y[0]], s=140, marker="*", c="limegreen", zorder=6, label="trimmed start")
    ax.scatter([x[-1]], [y[-1]], s=90, marker="o", c="orange", zorder=6, label="end")

    # Closure hint
    gap = math.hypot(x[-1] - x[0], y[-1] - y[0])
    ax.plot([x[-1], x[0]], [y[-1], y[0]], "k--", lw=0.8, alpha=0.4, label=f"start↔end {gap:.2f} m")

    frame = str(df["frame_id"].iloc[0]) if "frame_id" in df.columns else "map"
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_title(
        f"{args.csv.name} — {frame} ({len(df)} rows, trimmed {dropped}/{raw_n})\n"
        f"Cartographer manual_map log"
    )

    out = args.out or (args.csv.parent / "_plots" / f"{args.csv.stem}_trimmed_map.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)

    if args.save_trimmed_csv:
        args.save_trimmed_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.save_trimmed_csv, index=False)

    path_len = float(np.hypot(np.diff(x), np.diff(y)).sum())
    print(f"raw_rows={raw_n}  trimmed_rows={len(df)}  dropped_leading={dropped}  path_skip={path_skipped}")
    print(f"x[{x.min():.2f},{x.max():.2f}]  y[{y.min():.2f},{y.max():.2f}]  path={path_len:.2f} m  closure_gap={gap:.2f} m")
    print(f"→ {out}")
    if args.save_trimmed_csv:
        print(f"→ {args.save_trimmed_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
