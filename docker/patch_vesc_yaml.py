#!/usr/bin/env python3
"""
Patch f1tenth_system vesc.yaml so vesc_to_odom_node integrates speed with the correct sign.

Background
----------
vesc_ackermann/src/vesc_to_odom.cpp hard-codes a leading minus sign when integrating
the VESC reported speed into odometry::

    current_speed = (-state->state.speed - speed_to_erpm_offset_) / speed_to_erpm_gain_

The shared `/**:` block in vesc.yaml sets `speed_to_erpm_gain` (positive) so that
ackermann_to_vesc_node converts a positive commanded speed into a positive ERPM,
i.e. joystick forward -> wheels forward. With the same positive gain, the odom
integrator above ends up with the wrong sign and reports the car driving backwards
while it physically moves forward. That sign error is what produced the cyclical
"oval" trajectories in early manual_map_logger captures.

Fix
---
Add a per-node override under `vesc_to_odom_node:` that flips the sign of
`speed_to_erpm_gain`. ROS 2 parameter resolution makes this override beat the
`/**:` wildcard for that node only -- ackermann_to_vesc_node and the driver keep
the positive shared value, while the odom integrator uses the negative one.

Also set `publish_tf: false` on `vesc_to_odom_node` so `robot_localization`'s
`ekf_node` is the sole publisher of `odom` -> `base_link` (avoids duplicate TF).

This script is idempotent: it inserts the override only if it is not already
present, and aborts loudly if the upstream YAML structure changes in a way it
does not understand (so we notice rather than silently produce a broken image).
"""
from __future__ import annotations

from pathlib import Path

TARGET = Path("/race_ws/src/f1tenth_system/f1tenth_stack/config/vesc.yaml")
GAIN = 4614.0  # magnitude; sign is set per-node below.

# Anchor we expect to find inside the upstream `vesc_to_odom_node:` block.
NEEDLE = """vesc_to_odom_node:
  ros__parameters:
    odom_frame: odom"""

INJECT = f"""vesc_to_odom_node:
  ros__parameters:
    # Override /**: speed_to_erpm_gain so odom integrates with correct sign.
    # vesc_to_odom.cpp hard-codes a leading minus on the speed term, so a
    # positive shared gain (needed by ackermann_to_vesc_node for joy-forward
    # -> wheels-forward) makes the integrator decrease x while the car drives
    # forward. Inverting the gain only here keeps both behaviours correct.
    speed_to_erpm_gain: -{GAIN}
    odom_frame: odom
    # robot_localization EKF publishes odom->base_link; avoid duplicate TF.
    publish_tf: false"""


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"vesc.yaml not found at {TARGET}")

    text = TARGET.read_text(encoding="utf-8")

    if INJECT in text:
        print(f"vesc.yaml already patched ({TARGET})")
        return

    # Older images: gain override present but publish_tf not yet — append once.
    legacy_tail = f"    speed_to_erpm_gain: -{GAIN}\n    odom_frame: odom\n"
    if legacy_tail in text and "publish_tf: false" not in text:
        text = text.replace(
            legacy_tail,
            legacy_tail + "    # robot_localization EKF publishes odom->base_link; avoid duplicate TF.\n    publish_tf: false\n",
            1,
        )
        TARGET.write_text(text, encoding="utf-8")
        print(f"Added publish_tf: false to vesc_to_odom_node in {TARGET}")
        return

    if NEEDLE not in text:
        raise SystemExit(
            "vesc.yaml structure unexpected; could not find anchor block:\n"
            f"{NEEDLE}\nUpdate docker/patch_vesc_yaml.py to match upstream."
        )

    TARGET.write_text(text.replace(NEEDLE, INJECT), encoding="utf-8")
    print(f"Patched {TARGET}")


if __name__ == "__main__":
    main()
