#!/usr/bin/env python3
"""
Read TUM global_racetrajectory_optimization outputs/traj_race_cl.csv and emit a simple waypoint list.

Upstream export format (export_traj_race.py):
  - Two leading comment lines (# uuid, # ggv hash)
  - Header: s_m; x_m; y_m; psi_rad; kappa_radpm; vx_mps; ax_mps2
  - Numeric rows: semicolon-separated floats

Outputs:
  yaml  — list of [x, y] or [x, y, psi] for copy into ROS params / configs
  csv   — comma-separated x,y(,psi) only (no header)
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path


def _finite(x: float) -> bool:
    return isinstance(x, float) and math.isfinite(x)


def load_traj_rows(path: Path) -> list[tuple[float, float, float]]:
    """Return (x_m, y_m, psi_rad) per valid data row."""
    out: list[tuple[float, float, float]] = []
    with path.open(encoding="utf-8", newline="") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            # Header line contains column names
            if "x_m" in s and "y_m" in s:
                continue
            parts = [p.strip() for p in s.split(";")]
            if len(parts) < 4:
                continue
            try:
                x = float(parts[1])
                y = float(parts[2])
                psi = float(parts[3])
            except ValueError:
                continue
            if _finite(x) and _finite(y) and _finite(psi):
                out.append((x, y, psi))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("traj_csv", type=Path, help="Path to traj_race_cl.csv")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write here (default: stdout)",
    )
    ap.add_argument(
        "--format",
        choices=("yaml", "csv"),
        default="yaml",
        help="yaml: nested lists; csv: x,y(,psi) comma-separated",
    )
    ap.add_argument(
        "--step",
        type=int,
        default=1,
        help="Keep every N-th waypoint (default 1 = all)",
    )
    ap.add_argument(
        "--include-psi",
        action="store_true",
        help="Include psi_rad as third value in each waypoint",
    )
    args = ap.parse_args()
    if args.step < 1:
        ap.error("--step must be >= 1")

    rows = load_traj_rows(args.traj_csv)
    if not rows:
        print("ERROR: no trajectory rows parsed (wrong file or format?)", file=sys.stderr)
        return 1

    picked = rows[:: args.step]
    sink = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    try:
        if args.format == "csv":
            for x, y, psi in picked:
                if args.include_psi:
                    sink.write(f"{x},{y},{psi}\n")
                else:
                    sink.write(f"{x},{y}\n")
        else:
            sink.write("# waypoints: list of [x_m, y_m")
            if args.include_psi:
                sink.write(", psi_rad")
            sink.write("] in the same frame as your trajectory / localization\n")
            sink.write("waypoints:\n")
            for x, y, psi in picked:
                if args.include_psi:
                    sink.write(f"  - [{x}, {y}, {psi}]\n")
                else:
                    sink.write(f"  - [{x}, {y}]\n")
    finally:
        if args.output:
            sink.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
