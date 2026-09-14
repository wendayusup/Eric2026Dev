#!/usr/bin/env python3
"""
CUAV_debug/debug_gps.py — Debug GPS_RAW_INT & GLOBAL_POSITION_INT MAVLink Packets
"""
import sys
import time
from CUAV_debug import BOLD, CYAN, GREEN, RED, YELLOW, RESET, create_mavlink_connection

def debug_gps(conn_str="udp:127.0.0.1:14550", timeout_sec=3.0):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG GPS / GLOBAL POSITION (PYTHON) ━━━{RESET}")
    print(f"Opening MAVLink connection on {conn_str} ...")

    try:
        mav_conn = create_mavlink_connection(conn_str)
        print("Listening for GPS_RAW_INT & GLOBAL_POSITION_INT packets...")
        msg = mav_conn.recv_match(type=['GPS_RAW_INT', 'GLOBAL_POSITION_INT'], blocking=True, timeout=timeout_sec)

        if msg is not None:
            msg_type = msg.get_type()
            print(f"{GREEN}[MAVLINK PACKET RECEIVED: {msg_type}]{RESET}")
            if msg_type == 'GPS_RAW_INT':
                fix_type = msg.fix_type
                sats = msg.satellites_visible
                lat = msg.lat / 1e7
                lng = msg.lon / 1e7
                alt = msg.alt / 1000.0

                print(f"  ├─ GPS Fix Type     : {BOLD}Type {fix_type}{RESET} (3=3D Fix, 0=No Fix)")
                print(f"  ├─ Satellites Visible: {BOLD}{sats} Satellites{RESET}")
                print(f"  ├─ Latitude         : {BOLD}{lat:.7f}{RESET}°")
                print(f"  ├─ Longitude        : {BOLD}{lng:.7f}{RESET}°")
                print(f"  └─ Altitude MSL     : {BOLD}{alt:.2f} m{RESET}")
            elif msg_type == 'GLOBAL_POSITION_INT':
                lat = msg.lat / 1e7
                lng = msg.lon / 1e7
                alt_relative = msg.relative_alt / 1000.0
                hdg = msg.hdg / 100.0

                print(f"  ├─ Latitude         : {BOLD}{lat:.7f}{RESET}°")
                print(f"  ├─ Longitude        : {BOLD}{lng:.7f}{RESET}°")
                print(f"  ├─ Relative Altitude: {BOLD}{alt_relative:.2f} m{RESET}")
                print(f"  └─ Compass Heading  : {BOLD}{hdg:.1f}{RESET}°")
            return True
        else:
            print(f"{YELLOW}[FAILED] No GPS packets received within {timeout_sec}s.{RESET}")
            return False
    except Exception as e:
        print(f"{RED}[ERROR] Failed reading GPS data: {e}{RESET}")
        return False

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
    debug_gps(conn)
