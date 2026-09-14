#!/bin/bash
# CUAV_debug/run_all.sh - Shell runner for master CUAV MAVLink debug suite
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
CONN="${1:-/dev/ttyUSB0:57600}"
python3 "$SCRIPT_DIR/main.py" "$CONN"
