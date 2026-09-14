#!/bin/bash
# ROS2_debug/run_all.sh - Shell runner for master ROS 2 topics inspector
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
python3 "$SCRIPT_DIR/main.py" all
