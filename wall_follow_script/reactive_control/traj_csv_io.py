"""Load (x, y, yaw_rad) rows from TUM traj_race_cl.csv or compatible exports."""

from __future__ import annotations

import csv
import math
from pathlib import Path


def _finite(x: float) -> bool:
    return isinstance(x, float) and math.isfinite(x)


def _yaw_from_xy(points: list[tuple[float, float]]) -> list[float]:
    """Heading along polyline; last point reuses previous segment."""
    if len(points) < 2:
        return [0.0] * len(points)
    yaws: list[float] = []
    for i in range(len(points) - 1):
        dx = points[i + 1][0] - points[i][0]
        dy = points[i + 1][1] - points[i][1]
        yaws.append(math.atan2(dy, dx))
    yaws.append(yaws[-1])
    return yaws


def load_traj_xy_yaw(csv_path: Path) -> list[tuple[float, float, float]]:
    """
    Parse trajectory rows as (x_m, y_m, psi_rad).

    Supports:
    - TUM optimizer export: semicolon rows (s_m;x_m;y_m;psi_rad;...)
    - TUM numeric comma rows (s,x,y,psi,...)
    - Header CSV with x_m,y_m (psi computed from path if missing)
    """
    text = csv_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if not text:
        raise ValueError(f"Empty trajectory CSV: {csv_path}")

    first = text[0].strip().lower()
    if "x_m" in first and "y_m" in first:
        delim = ";" if ";" in first else ","
        reader = csv.DictReader(text, delimiter=delim)
        xs, ys, psis = [], [], []
        has_psi = reader.fieldnames and any(
            k in (reader.fieldnames or []) for k in ("psi_rad", "psi", "yaw_rad")
        )
        for row in reader:
            try:
                x = float(row["x_m"])
                y = float(row["y_m"])
            except (KeyError, ValueError):
                continue
            if not (_finite(x) and _finite(y)):
                continue
            xs.append(x)
            ys.append(y)
            if has_psi:
                for key in ("psi_rad", "psi", "yaw_rad"):
                    if key in row and row[key].strip():
                        try:
                            psis.append(float(row[key]))
                            break
                        except ValueError:
                            pass
                else:
                    psis.append(float("nan"))
        if len(xs) < 2:
            raise ValueError(f"Need >=2 points in {csv_path}")
        if has_psi and len(psis) == len(xs) and all(_finite(p) for p in psis):
            return list(zip(xs, ys, psis, strict=True))
        yaws = _yaw_from_xy(list(zip(xs, ys, strict=True)))
        return list(zip(xs, ys, yaws, strict=True))

    rows: list[tuple[float, float, float]] = []
    for line in text:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        delim = ";" if ";" in s else ","
        parts = [p.strip() for p in s.split(delim)]
        if len(parts) < 3:
            continue
        try:
            if len(parts) >= 7:
                x, y, psi = float(parts[1]), float(parts[2]), float(parts[3])
            elif len(parts) >= 4:
                x, y, psi = float(parts[1]), float(parts[2]), float(parts[3])
            else:
                x, y = float(parts[0]), float(parts[1])
                psi = float(parts[2]) if len(parts) > 2 else float("nan")
        except ValueError:
            continue
        if _finite(x) and _finite(y):
            rows.append((x, y, psi if _finite(psi) else float("nan")))

    if len(rows) < 2:
        raise ValueError(f"Need >=2 trajectory points after parsing {csv_path}")

    if any(not _finite(psi) for _, _, psi in rows):
        xy = [(x, y) for x, y, _ in rows]
        yaws = _yaw_from_xy(xy)
        rows = list(zip([p[0] for p in xy], [p[1] for p in xy], yaws, strict=True))

    return rows
