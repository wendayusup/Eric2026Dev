#!/usr/bin/env python3
"""
CUAV_debug/main.py — Master Interactive CUAV X7 Telemetry Debugger
Usage:
  python3 real_workspace/CUAV_debug/main.py [conn|alt_r|range_f|distance|gps|battery|imu|vfr|state|all]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from CUAV_debug.debug_connection import debug_connection
from CUAV_debug.debug_alt_r import debug_alt_r
from CUAV_debug.debug_range_f import debug_range_f
from CUAV_debug.debug_distance import debug_distance
from CUAV_debug.debug_gps import debug_gps
from CUAV_debug.debug_battery import debug_battery
from CUAV_debug.debug_imu import debug_imu
from CUAV_debug.debug_vfr import debug_vfr
from CUAV_debug.debug_state import debug_state
from CUAV_debug import BOLD, CYAN, GREEN, YELLOW, RED, RESET, print_header

def run_all(conn_str):
    print_header("CUAV X7 FULL TELEMETRY DEBUG SUITE (PYTHON)")
    print(f"Target Connection: {conn_str}")

    debug_connection(conn_str, timeout_sec=3)
    debug_state(conn_str, timeout_sec=3)
    debug_alt_r(conn_str, timeout_sec=3)
    debug_range_f(conn_str, timeout_sec=3)
    debug_battery(conn_str, timeout_sec=3)
    debug_vfr(conn_str, timeout_sec=3)
    debug_imu(conn_str, timeout_sec=3)
    debug_gps(conn_str, timeout_sec=3)

    print(f"\n{GREEN}{BOLD}=== CUAV X7 TELEMETRY INSPECTION COMPLETE ==={RESET}\n")

def main():
    conn_str = "udp:127.0.0.1:14550"
    param = 'all'

    for arg in sys.argv[1:]:
        if arg.startswith("udp:") or arg.startswith("tcp:") or arg.startswith("/dev/"):
            conn_str = arg
        else:
            param = arg.lower()

    if param == 'conn' or param == 'ping': debug_connection(conn_str)
    elif param == 'alt_r': debug_alt_r(conn_str)
    elif param == 'range_f': debug_range_f(conn_str)
    elif param == 'distance' or param == 'lidar': debug_distance(conn_str)
    elif param == 'gps': debug_gps(conn_str)
    elif param == 'battery': debug_battery(conn_str)
    elif param == 'imu': debug_imu(conn_str)
    elif param == 'vfr': debug_vfr(conn_str)
    elif param == 'state': debug_state(conn_str)
    elif param == 'all': run_all(conn_str)
    else:
        print_header("CUAV X7 TELEMETRY INSPECTOR (PYTHON)")
        print(f"{YELLOW}Parameter '{param}' not recognized.{RESET}")
        print("Usage: python3 real_workspace/CUAV_debug/main.py [conn|alt_r|range_f|distance|gps|battery|imu|vfr|state|all]")

if __name__ == '__main__':
    main()
