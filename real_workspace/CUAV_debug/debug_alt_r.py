#!/usr/bin/env python3
"""
CUAV_debug/debug_alt_r.py — Debug ALT R (Secondary Rangefinder - Sensor ID 10)
"""
import sys
import time
from CUAV_debug import BOLD, CYAN, GREEN, RED, YELLOW, RESET, create_mavlink_connection

def debug_alt_r(conn_str="udp:127.0.0.1:14550", timeout_sec=5.0):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG ALT R (SECONDARY RANGEFINDER - SENSOR ID 10) ━━━{RESET}")
    print(f"Opening MAVLink connection on {conn_str} ...")

    try:
        mav_conn = create_mavlink_connection(conn_str)
        print("Filtering specifically for ALT R (Sensor ID 10) packets...")
        t_start = time.time()
        received = False

        while time.time() - t_start < timeout_sec:
            msg = mav_conn.recv_match(type='DISTANCE_SENSOR', blocking=True, timeout=1.0)
            if msg is not None:
                sensor_id = getattr(msg, 'id', None)
                if sensor_id == 10:
                    received = True
                    curr_dist = msg.current_distance
                    min_d = msg.min_distance
                    max_d = msg.max_distance
                    orient = msg.orientation
                    print(f"{GREEN}[ALT R - SENSOR ID 10 DITERIMA]{RESET}")
                    print(f"  ├─ Current Distance: {BOLD}{curr_dist} cm{RESET} ({curr_dist/100.0:.2f} m)")
                    print(f"  ├─ Range Limits    : {min_d} cm to {max_d} cm")
                    print(f"  └─ Orientation     : {orient} (0 = Downward / ROTATION_NONE)")
                    break

        if not received:
            print(f"{YELLOW}[NO DATA] No ALT R packets (Sensor ID 10) received.{RESET}")
    except Exception as e:
        print(f"{RED}[ERROR] Failed reading ALT R data: {e}{RESET}")

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
    debug_alt_r(conn)
