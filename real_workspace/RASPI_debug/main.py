#!/usr/bin/env python3
"""
RASPI_debug/main.py — Master Interactive Raspberry Pi Inspector
Usage:
  python3 real_workspace/RASPI_debug/main.py [conn|servos|cameras|all]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from RASPI_debug.debug_raspi_connection import debug_raspi_connection
from RASPI_debug.debug_raspi_servos import debug_raspi_servos
from RASPI_debug.debug_raspi_cameras import debug_raspi_cameras
from RASPI_debug import BOLD, CYAN, GREEN, YELLOW, RED, RESET, print_header

def run_all():
    print_header("RASPBERRY PI HARDWARE & CAMERAS DEBUG SUITE")
    debug_raspi_connection()
    debug_raspi_servos()
    debug_raspi_cameras()
    print(f"\n{GREEN}{BOLD}=== RASPBERRY PI INSPECTION COMPLETE ==={RESET}\n")

def main():
    param = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'
    if param == 'conn' or param == 'ssh': debug_raspi_connection()
    elif param == 'servos' or param == 'servo': debug_raspi_servos()
    elif param == 'cameras' or param == 'camera': debug_raspi_cameras()
    elif param == 'all': run_all()
    else:
        print_header("RASPBERRY PI INSPECTOR (PYTHON)")
        print(f"{YELLOW}Parameter '{param}' not recognized.{RESET}")
        print("Usage: python3 real_workspace/RASPI_debug/main.py [conn|servos|cameras|all]")

if __name__ == '__main__':
    main()
