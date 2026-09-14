#!/usr/bin/env python3
"""
CUAV_debug/debug_vfr.py — Debug VFR_HUD MAVLink Packets (Baro Alt, Airspeed, Heading)
"""
import sys
import time
from CUAV_debug import BOLD, CYAN, GREEN, RED, YELLOW, RESET, create_mavlink_connection

def debug_vfr(conn_str="udp:127.0.0.1:14550", timeout_sec=3.0):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG VFR_HUD / ALTITUDE & SPEED (PYTHON) ━━━{RESET}")
    print(f"Opening MAVLink connection on {conn_str} ...")

    try:
        mav_conn = create_mavlink_connection(conn_str)
        print("Listening for VFR_HUD packets...")
        msg = mav_conn.recv_match(type='VFR_HUD', blocking=True, timeout=timeout_sec)

        if msg is not None:
            alt = msg.alt
            airspeed = msg.airspeed
            groundspeed = msg.groundspeed
            heading = msg.heading
            climb = msg.climb

            print(f"{GREEN}[MAVLINK VFR_HUD PACKET RECEIVED]{RESET}")
            print(f"  ├─ Barometer Alt   : {BOLD}{alt:.2f} m{RESET}")
            print(f"  ├─ Airspeed        : {airspeed:.2f} m/s")
            print(f"  ├─ Groundspeed     : {BOLD}{groundspeed:.2f} m/s{RESET}")
            print(f"  ├─ Compass Heading : {BOLD}{heading}°{RESET}")
            print(f"  └─ Climb Rate      : {climb:.2f} m/s")
            return True
        else:
            print(f"{YELLOW}[FAILED] No VFR_HUD packets received within {timeout_sec}s.{RESET}")
            return False
    except Exception as e:
        print(f"{RED}[ERROR] Failed reading VFR_HUD data: {e}{RESET}")
        return False

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
    debug_vfr(conn)
