#!/usr/bin/env python3
"""
CUAV_debug/debug_imu.py — Debug ATTITUDE & RAW_IMU MAVLink Packets
"""
import sys
import time
import math
from CUAV_debug import BOLD, CYAN, GREEN, RED, YELLOW, RESET, create_mavlink_connection

def debug_imu(conn_str="udp:127.0.0.1:14550", timeout_sec=3.0):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG IMU & ATTITUDE (PYTHON) ━━━{RESET}")
    print(f"Opening MAVLink connection on {conn_str} ...")

    try:
        mav_conn = create_mavlink_connection(conn_str)
        print("Listening for ATTITUDE & RAW_IMU packets...")
        msg = mav_conn.recv_match(type='ATTITUDE', blocking=True, timeout=timeout_sec)

        if msg is not None:
            r_deg = math.degrees(msg.roll)
            p_deg = math.degrees(msg.pitch)
            y_deg = (math.degrees(msg.yaw) + 360.0) % 360.0

            print(f"{GREEN}[MAVLINK ATTITUDE PACKET RECEIVED]{RESET}")
            print(f"  ├─ Roll  (Bank Left/Right)  : {BOLD}{r_deg:.2f}°{RESET} (rad: {msg.roll:.3f})")
            print(f"  ├─ Pitch (Nose Up/Down)    : {BOLD}{p_deg:.2f}°{RESET} (rad: {msg.pitch:.3f})")
            print(f"  ├─ Yaw   (Heading Direction): {BOLD}{y_deg:.2f}°{RESET} (rad: {msg.yaw:.3f})")
            print(f"  └─ Angular Speed (Roll/Pitch/Yaw): [{msg.rollspeed:.2f}, {msg.pitchspeed:.2f}, {msg.yawspeed:.2f}] rad/s")
            return True
        else:
            print(f"{YELLOW}[FAILED] No IMU/ATTITUDE packets received within {timeout_sec}s.{RESET}")
            return False
    except Exception as e:
        print(f"{RED}[ERROR] Failed reading IMU data: {e}{RESET}")
        return False

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
    debug_imu(conn)
