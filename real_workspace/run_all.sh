#!/bin/bash
# real_workspace/run_all.sh — Master Debugging Suite Launcher
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
python3 "$SCRIPT_DIR/debug_suite.py" "$@"
