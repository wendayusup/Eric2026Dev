#!/usr/bin/env python3
"""
CUAV_debug/debug_range_f.py — Debug RANGE F (Primary Rangefinder - Sensor ID 0/1)
"""
import sys
import time
from CUAV_debug import BOLD, CYAN, GREEN, RED, YELLOW, RESET, create_mavlink_connection

def debug_range_f(conn_str="udp:127.0.0.1:14550", timeout_sec=5.0):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG RANGE F (PRIMARY RANGEFINDER - SENSOR ID 0/1) ━━━{RESET}")
    print(f"Opening MAVLink connection on {conn_str} ...")

    try:
        mav_conn = create_mavlink_connection(conn_str)
        print("Filtering specifically for RANGE F (Sensor ID 0 or 1) packets...")
        t_start = time.time()
        received = False

        while time.time() - t_start < timeout_sec:
            msg = mav_conn.recv_match(type='DISTANCE_SENSOR', blocking=True, timeout=1.0)
            if msg is not None:
                sensor_id = getattr(msg, 'id', None)
                if sensor_id in [0, 1]:
                    received = True
                    curr_dist = msg.current_distance
                    min_d = msg.min_distance
                    max_d = msg.max_distance
                    orient = msg.orientation
                    print(f"{GREEN}[RANGE F - SENSOR ID {sensor_id} RECEIVED]{RESET}")
                    print(f"  ├─ Current Distance: {BOLD}{curr_dist} cm{RESET} ({curr_dist/100.0:.2f} m)")
                    print(f"  ├─ Range Limits    : {min_d} cm to {max_d} cm")
                    print(f"  └─ Orientation     : {orient} (0 = Downward / ROTATION_NONE)")
                    break

        if not received:
            print(f"{YELLOW}[NO DATA] No RANGE F packets (Sensor ID 0/1) received. Primary Sensor might not be plugged in yet.{RESET}")
    except Exception as e:
        print(f"{RED}[ERROR] Failed reading RANGE F data: {e}{RESET}")

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
    debug_range_f(conn)
