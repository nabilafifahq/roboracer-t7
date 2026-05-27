#!/usr/bin/env python3
"""Trim manual_map_logger CSV to first driving lap (moving + stop at first loop closure)."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import pandas as pd


def moving_mask(
    x: pd.Series | list[float],
    y: pd.Series | list[float],
    min_step_m: float = 0.005,
) -> list[bool]:
    xa = pd.Series(x).to_numpy(dtype=float)
    ya = pd.Series(y).to_numpy(dtype=float)
    if len(xa) == 0:
        return []
    step = [float(math.hypot(xa[i] - xa[i - 1], ya[i] - ya[i - 1])) for i in range(1, len(xa))]
    return [True] + [s > min_step_m for s in step]


def first_lap_end_index(
    x: list[float],
    y: list[float],
    *,
    near_start_m: float = 0.4,
    min_lap_path_m: float = 4.0,
) -> int:
    """Index (inclusive) of last row belonging to the first lap."""
    if len(x) < 2:
        return max(0, len(x) - 1)
    sx, sy = x[0], y[0]
    cum = 0.0
    for i in range(1, len(x)):
        cum += math.hypot(x[i] - x[i - 1], y[i] - y[i - 1])
        d0 = math.hypot(x[i] - sx, y[i] - sy)
        if cum >= min_lap_path_m and d0 <= near_start_m:
            return i
    return len(x) - 1


def trim_dataframe_one_lap(
    df: pd.DataFrame,
    *,
    min_step_m: float = 0.005,
    near_start_m: float = 0.4,
    min_lap_path_m: float = 4.0,
) -> pd.DataFrame:
    moving = df.loc[moving_mask(df["x"], df["y"], min_step_m=min_step_m)].reset_index(drop=True)
    if moving.empty:
        return moving
    x = moving["x"].to_numpy(dtype=float).tolist()
    y = moving["y"].to_numpy(dtype=float).tolist()
    end_pos = first_lap_end_index(
        x,
        y,
        near_start_m=near_start_m,
        min_lap_path_m=min_lap_path_m,
    )
    return moving.iloc[: end_pos + 1].reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=None)
    ap.add_argument("--near-start-m", type=float, default=0.4)
    ap.add_argument("--min-lap-path-m", type=float, default=4.0)
    args = ap.parse_args()
    df = pd.read_csv(args.csv)
    out_df = trim_dataframe_one_lap(
        df,
        near_start_m=args.near_start_m,
        min_lap_path_m=args.min_lap_path_m,
    )
    out = args.output or args.csv.with_name(f"{args.csv.stem}_one_lap.csv")
    out_df.to_csv(out, index=False)
    path_m = float(
        pd.Series(
            [
                0.0,
                *[
                    math.hypot(
                        out_df["x"].iloc[i] - out_df["x"].iloc[i - 1],
                        out_df["y"].iloc[i] - out_df["y"].iloc[i - 1],
                    )
                    for i in range(1, len(out_df))
                ],
            ]
        ).sum()
    )
    gap = math.hypot(
        out_df["x"].iloc[-1] - out_df["x"].iloc[0],
        out_df["y"].iloc[-1] - out_df["y"].iloc[0],
    )
    print(f"Wrote {out} rows={len(out_df)} path_m={path_m:.2f} start_end_gap_m={gap:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
