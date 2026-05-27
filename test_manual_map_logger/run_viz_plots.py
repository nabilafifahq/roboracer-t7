#!/usr/bin/env python3
"""Run Visualization Optimizer.ipynb plots for one CSV (untrimmed + trimmed)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parent / "Visualization Optimizer.ipynb"


def main() -> int:
    csv_name = os.environ.get("MANUAL_MAP_CSV", "manual_map_20260522_024408.csv")
    os.environ["MANUAL_MAP_CSV"] = csv_name
    os.environ.setdefault("MPLBACKEND", "Agg")
    mpl_dir = Path(__file__).resolve().parent / ".mplconfig"
    mpl_dir.mkdir(exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))

    import matplotlib

    matplotlib.use("Agg")

    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    g: dict = {"__name__": "__main__"}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell.get("source", []))
        lines = [ln for ln in src.splitlines() if not ln.strip().startswith("%matplotlib")]
        src = "\n".join(lines)
        if not src.strip():
            continue
        exec(compile(src, "<notebook>", "exec"), g, g)

    stem = Path(csv_name).stem
    plot_dir = Path(__file__).resolve().parent / "_plots"
    pngs = sorted(plot_dir.glob(f"{stem}_*.png"))
    print(f"Generated {len(pngs)} plots for {csv_name}")
    for p in pngs:
        print(" ", p.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
