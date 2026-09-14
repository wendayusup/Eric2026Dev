#!/bin/bash
# RASPI_debug/run_all.sh - Shell runner for Raspberry Pi & Dual Camera debugger
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
python3 "$SCRIPT_DIR/main.py" all
