#!/usr/bin/env python3
"""
Convert reactive_control manual_map_logger CSV -> TUM global_racetrajectory_optimization track CSV.

Use this when the CSV is *not* already TUM-shaped. If the file already has columns
  x_m, y_m, w_tr_right_m, w_tr_left_m
(and you only renamed it e.g. hallway.csv), skip conversion and copy straight to inputs/tracks/.

TUM import_track.py expects comma-separated rows (header optional only if first line is '#' comment):
  x_m, y_m, w_tr_right_m, w_tr_left_m

Logger columns expected by this script (see also older runs with different headers in docs):
  x, y, right_wall_m -> w_tr_right_m, left_wall_m -> w_tr_left_m

References:
  https://github.com/TUMFTM/global_racetrajectory_optimization
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TRIM_PKG = _REPO_ROOT / "test_manual_map_logger"


def _finite(x: str) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path, help="manual_map_*.csv from manual_map_logger")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output path, e.g. raceline_data/inputs/tracks/from_manual_map.csv",
    )
    ap.add_argument(
        "--drop-first",
        type=int,
        default=0,
        metavar="N",
        help="Drop first N valid rows after filtering (use 1 to remove SLAM startup pose snap)",
    )
    ap.add_argument(
        "--step",
        type=int,
        default=1,
        help="Keep every N-th valid row after filtering (default 1 = all)",
    )
    ap.add_argument(
        "--comment",
        action="store_true",
        help="Write a leading # comment line (TUM loadtxt ignores # lines)",
    )
    ap.add_argument(
        "--moving-min-step",
        type=float,
        default=0.0,
        metavar="M",
        help="Keep a row only if pose moved > M meters from the previous kept row (trim parked/stop clutter)",
    )
    ap.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse point order after filtering (race 'back' along the logged path)",
    )
    ap.add_argument(
        "--close-loop",
        action="store_true",
        help="Append first point at end so TUM periodic spline sees a closed circuit",
    )
    ap.add_argument(
        "--close-gap-m",
        type=float,
        default=1.0,
        metavar="M",
        help="With --close-loop: warn if last point is farther than M from first (default 1.0)",
    )
    ap.add_argument(
        "--min-wall-m",
        type=float,
        default=0.0,
        metavar="M",
        help="Clamp w_tr_right_m and w_tr_left_m to at least M (helps TUM on narrow corridors)",
    )
    ap.add_argument(
        "--one-lap",
        action="store_true",
        help="Trim multi-lap logger CSV to first loop closure (moving + near start)",
    )
    ap.add_argument(
        "--process-walls",
        action="store_true",
        help="Inner/outer wall separation (polar median); needs test_manual_map_logger/process_lap_inner_outer_walls.py",
    )
    args = ap.parse_args()
    if args.step < 1:
        ap.error("--step must be >= 1")

    input_csv = args.input_csv
    stem = input_csv.stem
    if args.one_lap or args.process_walls:
        if not _TRIM_PKG.is_dir():
            print(f"ERROR: missing {_TRIM_PKG} for --one-lap / --process-walls", file=sys.stderr)
            return 1
        sys.path.insert(0, str(_TRIM_PKG))
        import pandas as pd

        from process_lap_inner_outer_walls import process_lap as _process_lap
        from trim_one_lap import trim_dataframe_one_lap

        df = pd.read_csv(input_csv)
        if args.one_lap and not stem.endswith("_one_lap") and not stem.endswith("_one_lap_processed"):
            df = trim_dataframe_one_lap(df)
            print(f"--one-lap: trimmed to {len(df)} rows", file=sys.stderr)
        if args.process_walls and not stem.endswith("_one_lap_processed"):
            df, _meta = _process_lap(df)
            print(
                f"--process-walls: inner/outer half-widths (med L={df['left_wall_m'].median():.2f} "
                f"R={df['right_wall_m'].median():.2f} m)",
                file=sys.stderr,
            )
        tmp = input_csv.with_name(f"{stem}_tum_work.csv")
        df[["x", "y", "left_wall_m", "right_wall_m"]].to_csv(tmp, index=False)
        input_csv = tmp

    with input_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("ERROR: empty CSV or no header row", file=sys.stderr)
            return 1
        fields = {h.strip(): h for h in reader.fieldnames}

        def col(name: str) -> str | None:
            for key in (name, name.lower()):
                if key in fields:
                    return fields[key]
            return None

        cx, cy = col("x"), col("y")
        cl, cr = col("left_wall_m"), col("right_wall_m")
        if not all((cx, cy, cl, cr)):
            print(
                "ERROR: need columns x, y, left_wall_m, right_wall_m in header; got:",
                reader.fieldnames,
                file=sys.stderr,
            )
            return 1

        rows_out: list[tuple[float, float, float, float]] = []
        last_xy: tuple[float, float] | None = None
        min_step = float(args.moving_min_step)
        for row in reader:
            lv = (row.get(cl) or "").strip()
            rv = (row.get(cr) or "").strip()
            xv = (row.get(cx) or "").strip()
            yv = (row.get(cy) or "").strip()
            if not lv or not rv or not xv or not yv:
                continue
            if not (_finite(lv) and _finite(rv) and _finite(xv) and _finite(yv)):
                continue
            x, y = float(xv), float(yv)
            w_l, w_r = float(lv), float(rv)
            if w_l <= 0.0 or w_r <= 0.0:
                continue
            if min_step > 0.0 and last_xy is not None:
                if math.hypot(x - last_xy[0], y - last_xy[1]) <= min_step:
                    continue
            rows_out.append((x, y, w_r, w_l))
            last_xy = (x, y)

    if not rows_out:
        print("ERROR: no valid rows (need finite x,y and both wall distances)", file=sys.stderr)
        return 1

    drop = max(0, args.drop_first)
    if drop:
        rows_out = rows_out[drop:]
    if not rows_out:
        print("ERROR: no rows left after --drop-first", file=sys.stderr)
        return 1

    if args.reverse:
        rows_out = list(reversed(rows_out))

    if args.close_loop and len(rows_out) >= 2:
        gap = math.hypot(
            rows_out[-1][0] - rows_out[0][0],
            rows_out[-1][1] - rows_out[0][1],
        )
        if gap > args.close_gap_m:
            print(
                f"WARNING: loop gap {gap:.2f} m > --close-gap-m {args.close_gap_m}; "
                "lap may not be closed in odom",
                file=sys.stderr,
            )
        if rows_out[-1][:2] != rows_out[0][:2]:
            rows_out.append(rows_out[0])

    min_wall = float(args.min_wall_m)
    if min_wall > 0.0:
        rows_out = [
            (x, y, max(w_tr_r, min_wall), max(w_tr_l, min_wall))
            for x, y, w_tr_r, w_tr_l in rows_out
        ]

    thinned: list[tuple[float, float, float, float]] = rows_out[:: args.step]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as out:
        if args.comment:
            out.write(
                "# TUM track: x_m,y_m,w_tr_right_m,w_tr_left_m (from manual_map_logger; heuristic)\n"
            )
        w = csv.writer(out, lineterminator="\n")
        for x, y, w_tr_r, w_tr_l in thinned:
            w.writerow([f"{x:.6f}", f"{y:.6f}", f"{w_tr_r:.6f}", f"{w_tr_l:.6f}"])

    print(f"Wrote {len(thinned)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
