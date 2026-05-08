#!/usr/bin/env python3
"""
Adapt TUM main_globaltraj.py for ROS Humble Docker (Python >= 3.10):

1. Remove unconditional `import opt_mintime_traj` (pulls in casadi even for mincurv).
2. Insert lazy `import opt_mintime_traj` inside `elif opt_type == 'mintime':`.
3. Remove strict pkg_resources.require() block (pins py3.7-era wheels).

Idempotent when MARKER is present.

Upstream: https://github.com/TUMFTM/global_racetrajectory_optimization
"""
from __future__ import annotations

import re
from pathlib import Path

TARGET = Path("/race_ws/tum_global_racetrajectory_optimization/main_globaltraj.py")
MARKER = "PATCHED_FOR_ROS_PY310_DEPENDENCIES_SKIP"


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        return

    text2 = re.sub(
        r"^import\s+opt_mintime_traj\s*\r?\n",
        "",
        text,
        count=1,
        flags=re.MULTILINE,
    )

    m = re.search(r"(elif\s+opt_type\s*==\s*'mintime':\s*\r?\n)", text2)
    if not m:
        raise RuntimeError("Could not locate `elif opt_type == 'mintime':` branch to patch.")

    tail = text2[m.end() :]
    indent = ""
    for ln in tail.splitlines(keepends=True):
        if ln.strip():
            indent = ln[: len(ln) - len(ln.lstrip(" \t"))]
            break
    if indent == "":
        indent = " "

    insert = indent + "import opt_mintime_traj\n"
    text3 = text2[: m.end()] + insert + tail

    text4, n = re.subn(
        r"(?ms)^#\s*read dependencies from requirements\.txt.*?^pkg_resources\.require\(dependencies\)\s*\r?\n",
        f"# Dependencies check skipped ({MARKER}) — Dockerfile installs Python 3 wheels.\n",
        text3,
        count=1,
    )
    if n != 1:
        raise RuntimeError("Could not replace pkg_resources requirements block.")

    TARGET.write_text(text4, encoding="utf-8")


if __name__ == "__main__":
    main()
