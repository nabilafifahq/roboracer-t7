#!/usr/bin/env bash
# Install team ackermann_mux_topics.yaml into the built workspace (includes /nav2_cmd_ackermann).
set -euo pipefail

SRC="/race_ws/config/ackermann_mux_topics.yaml"
test -f "$SRC"

while IFS= read -r dest; do
  cp "$SRC" "$dest"
  echo "OK: mux config -> $dest"
done < <(find /race_ws/install -name 'ackermann_mux_topics.yaml' 2>/dev/null || true)
