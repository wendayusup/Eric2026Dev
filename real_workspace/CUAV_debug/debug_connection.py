#!/usr/bin/env python3
"""
CUAV_debug/debug_connection.py — Debug USB Serial Port & MAVLink Heartbeat Ping
"""
import sys
import time
import os
from pymavlink import mavutil

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def scan_usb_ports():
    print(f"[USB SCAN] Checking Local USB Serial Ports...")
    candidate_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']
    found = []
    for port in candidate_ports:
        if os.path.exists(port):
            print(f"  ├─ Port {port} FOUND (Available)")
            found.append(port)
        else:
            print(f"  ├─ Port {port} not found")
    return found

def debug_connection(conn_str="udp:127.0.0.1:14550", timeout_sec=3.0):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG MAVLINK CONNECTION & HEARTBEAT (PYTHON) ━━━{RESET}")
    scan_usb_ports()
    print(f"\nOpening MAVLink connection on {conn_str} ...")

    try:
        if conn_str.startswith('/dev/'):
            if ':' in conn_str:
                device, baud_str = conn_str.split(':')
                mav_conn = mavutil.mavlink_connection(device, baud=int(baud_str))
            else:
                mav_conn = mavutil.mavlink_connection(conn_str, baud=57600)
        else:
            mav_conn = mavutil.mavlink_connection(conn_str)
        t_start = time.time()
        print(f"Pinging Flight Controller Heartbeat (timeout {timeout_sec}s)...")
        hb = mav_conn.wait_heartbeat(timeout=timeout_sec)
        rtt_ms = (time.time() - t_start) * 1000.0

        if hb is not None:
            sys_id = mav_conn.target_system
            comp_id = mav_conn.target_component
            mode = mavutil.mode_string_v10(hb)
            armed = (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0

            print(f"\n{GREEN}{BOLD}[SUCCESS] FLIGHT CONTROLLER CONNECTED!{RESET}")
            print(f"  ├─ System ID       : {sys_id}")
            print(f"  ├─ Component ID    : {comp_id}")
            print(f"  ├─ Flight Mode     : {mode}")
            print(f"  ├─ Arming Status   : {'ARMED' if armed else 'DISARMED'}")
            print(f"  └─ Ping RTT Latency: {rtt_ms:.1f} ms")
            return True
        else:
            print(f"\n{RED}[FAILED] No MAVLink Heartbeat received within {timeout_sec}s.{RESET}")
            print(f"{YELLOW}Make sure CUAV X7 USB telemetry cable is plugged in or backend_real.py is running.{RESET}")
            return False
    except Exception as e:
        print(f"\n{RED}[ERROR] Failed opening connection on {conn_str}: {e}{RESET}")
        return False

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
    debug_connection(conn)
