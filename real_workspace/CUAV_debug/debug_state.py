#!/usr/bin/env python3
"""
CUAV_debug/debug_state.py — Debug HEARTBEAT MAVLink Packets & System State
"""
import sys
import time
from pymavlink import mavutil
from CUAV_debug import BOLD, CYAN, GREEN, RED, YELLOW, RESET, create_mavlink_connection

def debug_state(conn_str="udp:127.0.0.1:14550", timeout_sec=5.0):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG FCU STATE & HEARTBEAT (PYTHON) ━━━{RESET}")
    print(f"Opening MAVLink connection on {conn_str} ...")

    try:
        mav_conn = create_mavlink_connection(conn_str)
        print("Listening for HEARTBEAT packets...")
        t_start = time.time()
        count = 0

        while time.time() - t_start < timeout_sec:
            msg = mav_conn.recv_match(type='HEARTBEAT', blocking=True, timeout=1.0)
            if msg is not None:
                count += 1
                sys_id = mav_conn.target_system
                comp_id = mav_conn.target_component
                mode = mavutil.mode_string_v10(msg)
                armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0

                print(f"{GREEN}[HEARTBEAT #{count}]{RESET}")
                print(f"  ├─ System ID       : {sys_id}")
                print(f"  ├─ Component ID    : {comp_id}")
                print(f"  ├─ Flight Mode     : {mode} (custom_mode: {msg.custom_mode})")
                print(f"  ├─ Armed Status    : {'ARMED' if armed else 'DISARMED'}")
                print(f"  ├─ System State    : {msg.system_status}")
                print(f"  └─ MAVLink Version : {msg.mavlink_version}")
                print("  ----------------------------------------")
                if count >= 3:
                    break

        if count > 0:
            print(f"{GREEN}[SUCCESS] FCU Connection Active & Broadcasting Heartbeats!{RESET}")
            return True
        else:
            print(f"{RED}[FAILED] No HEARTBEAT packets received within {timeout_sec}s.{RESET}")
            return False
    except Exception as e:
        print(f"{RED}[ERROR] Failed reading HEARTBEAT packets: {e}{RESET}")
        return False

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
    debug_state(conn)
