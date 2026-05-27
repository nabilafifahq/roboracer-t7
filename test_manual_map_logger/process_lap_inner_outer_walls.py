#!/usr/bin/env python3
"""
Heavy post-process for one-lap manual_map CSV: separate inner vs outer LiDAR hits.

Assumes a roughly circular loop. Uses geometry (radius from fitted center) so
"see-through" far readings (O-gap -> opposite outer wall) are dropped, and
inner / outer boundaries are rebuilt in polar bins.

Input: manual_map_*_one_lap.csv (or any lap CSV with x, y, yaw_rad, left/right_wall_m).
Output: *_processed.csv + debug plots under _plots/.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _left_normal(yaw: float) -> tuple[float, float]:
    return (-math.sin(yaw), math.cos(yaw))


def circle_fit(xy: np.ndarray) -> tuple[float, float, float]:
    """Algebraic circle fit (Kåsa): returns cx, cy, mean radius."""
    x = xy[:, 0].astype(float)
    y = xy[:, 1].astype(float)
    a = np.column_stack([x, y, np.ones(len(x))])
    b = x * x + y * y
    sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    cx, cy, c = sol[0] / 2.0, sol[1] / 2.0, sol[2]
    r = float(np.median(np.hypot(x - cx, y - cy)))
    return float(cx), float(cy), r


def wall_hits_world(df: pd.DataFrame) -> dict[str, np.ndarray]:
    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    yaw = np.unwrap(df["yaw_rad"].to_numpy(dtype=float))
    wl = df["left_wall_m"].to_numpy(dtype=float)
    wr = df["right_wall_m"].to_numpy(dtype=float)
    nx = -np.sin(yaw)
    ny = np.cos(yaw)
    lx = x + nx * wl
    ly = y + ny * wl
    rx = x - nx * wr
    ry = y - ny * wr
    return {
        "x": x,
        "y": y,
        "yaw": yaw,
        "wl": wl,
        "wr": wr,
        "lx": lx,
        "ly": ly,
        "rx": rx,
        "ry": ry,
    }


def classify_inner_outer(
    px: np.ndarray,
    py: np.ndarray,
    cx: float,
    cy: float,
    x_car: np.ndarray,
    y_car: np.ndarray,
    margin_m: float,
) -> np.ndarray:
    """True = hit closer to loop center than the car (inner boundary)."""
    r_hit = np.hypot(px - cx, py - cy)
    r_car = np.hypot(x_car - cx, y_car - cy)
    return r_hit < (r_car - margin_m)


def polar_median_curve(
    px: np.ndarray,
    py: np.ndarray,
    cx: float,
    cy: float,
    n_bins: int,
) -> tuple[np.ndarray, np.ndarray]:
    theta = np.arctan2(py - cy, px - cx)
    r = np.hypot(px - cx, py - cy)
    bins = np.linspace(-np.pi, np.pi, n_bins + 1)
    t_centers = 0.5 * (bins[:-1] + bins[1:])
    r_med = np.full(n_bins, np.nan, dtype=float)
    for k in range(n_bins):
        mask = (theta >= bins[k]) & (theta < bins[k + 1])
        if mask.any():
            r_med[k] = float(np.median(r[mask]))
    # wrap-aware interp for NaNs
    good = np.isfinite(r_med)
    if good.sum() < 3:
        return t_centers, r_med
    t_good = t_centers[good]
    r_good = r_med[good]
    order = np.argsort(t_good)
    t_good = t_good[order]
    r_good = r_good[order]
    t_wrap = np.concatenate([t_good - 2 * np.pi, t_good, t_good + 2 * np.pi])
    r_wrap = np.concatenate([r_good, r_good, r_good])
    r_fill = np.interp(t_centers, t_wrap, r_wrap)
    return t_centers, r_fill


def sample_polar_radius(theta_q: np.ndarray, t_centers: np.ndarray, r_curve: np.ndarray) -> np.ndarray:
    t_ext = np.concatenate([t_centers - 2 * np.pi, t_centers, t_centers + 2 * np.pi])
    r_ext = np.concatenate([r_curve, r_curve, r_curve])
    return np.interp(theta_q, t_ext, r_ext)


def process_lap(
    df: pd.DataFrame,
    *,
    inner_margin_m: float = 0.08,
    max_inner_hit_m: float = 1.35,
    max_outer_hit_m: float = 2.0,
    polar_bins: int = 72,
    smooth_win: int = 7,
) -> tuple[pd.DataFrame, dict]:
    hits = wall_hits_world(df)
    xy = np.column_stack([hits["x"], hits["y"]])
    cx, cy, r_car_med = circle_fit(xy)

    inner_l = classify_inner_outer(
        hits["lx"], hits["ly"], cx, cy, hits["x"], hits["y"], inner_margin_m
    )
    inner_r = classify_inner_outer(
        hits["rx"], hits["ry"], cx, cy, hits["x"], hits["y"], inner_margin_m
    )
    outer_l = ~inner_l
    outer_r = ~inner_r

    # Drop see-through / invalid
    valid_l = np.isfinite(hits["wl"]) & (hits["wl"] > 0.05)
    valid_r = np.isfinite(hits["wr"]) & (hits["wr"] > 0.05)
    use_inner_l = inner_l & valid_l & (hits["wl"] <= max_inner_hit_m)
    use_inner_r = inner_r & valid_r & (hits["wr"] <= max_inner_hit_m)
    use_outer_l = outer_l & valid_l & (hits["wl"] <= max_outer_hit_m)
    use_outer_r = outer_r & valid_r & (hits["wr"] <= max_outer_hit_m)

    inner_px = np.concatenate([hits["lx"][use_inner_l], hits["rx"][use_inner_r]])
    inner_py = np.concatenate([hits["ly"][use_inner_l], hits["ry"][use_inner_r]])
    outer_px = np.concatenate([hits["lx"][use_outer_l], hits["rx"][use_outer_r]])
    outer_py = np.concatenate([hits["ly"][use_outer_l], hits["ry"][use_outer_r]])

    t_in, r_in = polar_median_curve(inner_px, inner_py, cx, cy, polar_bins)
    t_out, r_out = polar_median_curve(outer_px, outer_py, cx, cy, polar_bins)

    theta_car = np.arctan2(hits["y"] - cy, hits["x"] - cx)
    r_inner_ref = sample_polar_radius(theta_car, t_in, r_in)
    r_outer_ref = sample_polar_radius(theta_car, t_out, r_out)
    r_car = np.hypot(hits["x"] - cx, hits["y"] - cy)

    # Half-widths toward inner/outer boundaries (meters along vehicle left/right normals)
    w_inner = np.clip(r_car - r_inner_ref, 0.12, max_inner_hit_m)
    w_outer = np.clip(r_outer_ref - r_car, 0.12, max_outer_hit_m)

    # Per-sample overrides when classified hit is trustworthy
    w_inner_meas = np.full(len(df), np.nan)
    w_outer_meas = np.full(len(df), np.nan)
    w_inner_meas[use_inner_r] = hits["wr"][use_inner_r]
    w_inner_meas[use_inner_l & ~use_inner_r] = hits["wl"][use_inner_l & ~use_inner_r]
    w_outer_meas[use_outer_l] = hits["wl"][use_outer_l]
    w_outer_meas[use_outer_r & ~use_outer_l] = hits["wr"][use_outer_r & ~use_outer_l]

    def _blend(model: np.ndarray, meas: np.ndarray) -> np.ndarray:
        out = model.copy()
        good = np.isfinite(meas)
        out[good] = 0.35 * model[good] + 0.65 * meas[good]
        return out

    w_inner_f = _blend(w_inner, w_inner_meas)
    w_outer_f = _blend(w_outer, w_outer_meas)

    if smooth_win > 1:
        k = smooth_win | 1
        kernel = np.ones(k) / k
        w_inner_f = np.convolve(w_inner_f, kernel, mode="same")
        w_outer_f = np.convolve(w_outer_f, kernel, mode="same")

    out = df.copy()
    # TUM / logger naming: left = outer half-width, right = inner half-width (CCW loop)
    out["left_wall_m"] = w_outer_f
    out["right_wall_m"] = w_inner_f
    out["w_outer_model_m"] = w_outer
    out["w_inner_model_m"] = w_inner
    out["left_wall_m_raw"] = hits["wl"]
    out["right_wall_m_raw"] = hits["wr"]
    out["hit_left_inner"] = inner_l.astype(int)
    out["hit_right_inner"] = inner_r.astype(int)

    meta = {
        "cx": cx,
        "cy": cy,
        "r_car_med": r_car_med,
        "t_in": t_in,
        "r_in": r_in,
        "t_out": t_out,
        "r_out": r_out,
        "hits": hits,
        "use_inner_l": use_inner_l,
        "use_inner_r": use_inner_r,
        "use_outer_l": use_outer_l,
        "use_outer_r": use_outer_r,
        "inner_px": inner_px,
        "inner_py": inner_py,
        "outer_px": outer_px,
        "outer_py": outer_py,
    }
    return out, meta


def plot_debug(
    stem: str,
    df_raw: pd.DataFrame,
    df_proc: pd.DataFrame,
    meta: dict,
    plot_dir: Path,
) -> None:
    hits = meta["hits"]
    cx, cy = meta["cx"], meta["cy"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5))

    ax = axes[0]
    ax.plot(hits["x"], hits["y"], "k--", lw=1.0, label="centerline")
    ax.scatter(meta["outer_px"], meta["outer_py"], s=10, c="#1f4e79", alpha=0.5, label="outer hits")
    ax.scatter(meta["inner_px"], meta["inner_py"], s=10, c="#c00000", alpha=0.5, label="inner hits")
    ax.scatter(cx, cy, s=80, c="gold", marker="x", zorder=6, label="fit center")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title(f"{stem} — classified hits (geom)")

    ax = axes[1]
    th = np.linspace(-np.pi, np.pi, 200)
    r_in = sample_polar_radius(th, meta["t_in"], meta["r_in"])
    r_out = sample_polar_radius(th, meta["t_out"], meta["r_out"])
    ax.plot(th, r_in, "r-", lw=2, label="inner r(θ) median")
    ax.plot(th, r_out, "b-", lw=2, label="outer r(θ) median")
    ax.set_xlabel("θ around center [rad]")
    ax.set_ylabel("radius [m]")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title("Polar boundary model")

    plt.tight_layout()
    p = plot_dir / f"{stem}_processed_classify.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", p)

    fig, ax = plt.subplots(figsize=(8, 7))
    yaw = hits["yaw"]
    nx, ny = -np.sin(yaw), np.cos(yaw)
    x, y = hits["x"], hits["y"]
    lo = df_proc["left_wall_m"].to_numpy()
    ri = df_proc["right_wall_m"].to_numpy()
    ax.plot(x, y, "k--", lw=1.2, label="centerline")
    ax.plot(x + nx * lo, y + ny * lo, color="#1f4e79", lw=1.2, label="outer (proc)")
    ax.plot(x - nx * ri, y - ny * ri, color="#c00000", lw=1.2, label="inner (proc)")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title(f"{stem} — processed corridor (inner≠outer wall)")
    plt.tight_layout()
    p = plot_dir / f"{stem}_processed_corridor.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", p)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df_raw["right_wall_m"], "0.6", alpha=0.7, label="right raw")
    ax.plot(df_proc["right_wall_m"], "r-", label="inner proc")
    ax.plot(df_raw["left_wall_m"], "0.4", alpha=0.7, label="left raw")
    ax.plot(df_proc["left_wall_m"], "b-", label="outer proc")
    ax.set_xlabel("index")
    ax.set_ylabel("half-width [m]")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title("Half-width along lap")
    plt.tight_layout()
    p = plot_dir / f"{stem}_processed_widths.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="One-lap (or single-lap) manual_map CSV")
    ap.add_argument("-o", "--output", type=Path, default=None)
    ap.add_argument("--plot-dir", type=Path, default=Path("_plots"))
    ap.add_argument("--inner-margin-m", type=float, default=0.08)
    ap.add_argument("--max-inner-hit-m", type=float, default=1.35)
    ap.add_argument("--max-outer-hit-m", type=float, default=2.0)
    ap.add_argument("--polar-bins", type=int, default=72)
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    proc, meta = process_lap(
        df,
        inner_margin_m=args.inner_margin_m,
        max_inner_hit_m=args.max_inner_hit_m,
        max_outer_hit_m=args.max_outer_hit_m,
        polar_bins=args.polar_bins,
    )
    out = args.output or args.csv.with_name(f"{args.csv.stem}_processed.csv")
    proc.to_csv(out, index=False)
    print(f"Wrote {out} rows={len(proc)}")
    print(
        f"  center=({meta['cx']:.3f},{meta['cy']:.3f}) r_car_med={meta['r_car_med']:.3f} m"
    )
    print(
        f"  outer half-width med={proc['left_wall_m'].median():.2f} m  "
        f"inner med={proc['right_wall_m'].median():.2f} m"
    )

    args.plot_dir.mkdir(parents=True, exist_ok=True)
    plot_debug(args.csv.stem, df, proc, meta, args.plot_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
