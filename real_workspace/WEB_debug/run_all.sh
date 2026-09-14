#!/bin/bash
# WEB_debug/run_all.sh - Shell runner for Web GCS Flask & Socket.IO debugger
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
python3 "$SCRIPT_DIR/main.py" all
