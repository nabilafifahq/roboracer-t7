#!/usr/bin/env python3
"""
Convert reactive_control manual_map_logger CSV -> TUM global_racetrajectory_optimization track CSV.

TUM import_track.py expects comma-separated rows (header optional only if first line is '#' comment):
  x_m, y_m, w_tr_right_m, w_tr_left_m

manual_map columns used:
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
        help="Output path, e.g. raceline_data/inputs/tracks/hallway.csv",
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
    args = ap.parse_args()
    if args.step < 1:
        ap.error("--step must be >= 1")

    with args.input_csv.open(newline="", encoding="utf-8") as f:
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
            rows_out.append((x, y, w_r, w_l))

    if not rows_out:
        print("ERROR: no valid rows (need finite x,y and both wall distances)", file=sys.stderr)
        return 1

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
