#!/usr/bin/env python3
"""
CUAV_debug/debug_battery.py — Raw MAVLink Battery & System Power Inspector
Dumps 100% raw MAVLink packet fields (SYS_STATUS and BATTERY_STATUS).
"""
import sys
import time
import json
from pymavlink import mavutil

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def debug_battery(conn_str="udp:127.0.0.1:14550", timeout_sec=4.0):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG RAW MAVLINK BATTERY & SYS_STATUS ━━━{RESET}")
    print(f"Connecting to MAVLink endpoint: {conn_str} ...")

    try:
        if conn_str.startswith('/dev/'):
            if ':' in conn_str:
                device, baud_str = conn_str.split(':')
                mav = mavutil.mavlink_connection(device, baud=int(baud_str))
            else:
                mav = mavutil.mavlink_connection(conn_str, baud=57600)
        else:
            mav = mavutil.mavlink_connection(conn_str)

        t_start = time.time()
        print(f"Listening for raw MAVLink battery packets (SYS_STATUS, BATTERY_STATUS)...")

        received_count = 0
        while time.time() - t_start < timeout_sec:
            msg = mav.recv_match(type=['SYS_STATUS', 'BATTERY_STATUS'], blocking=True, timeout=1.0)
            if not msg:
                continue

            msg_type = msg.get_type()
            raw_dict = msg.to_dict()
            received_count += 1

            print(f"\n{GREEN}{BOLD}[RAW MAVLINK PACKET: {msg_type}]{RESET}")
            print(f"{CYAN}--- Raw JSON Data Structure ---{RESET}")
            print(json.dumps(raw_dict, indent=2))

            print(f"\n{YELLOW}--- Decoded Fields Summary ---{RESET}")
            if msg_type == 'SYS_STATUS':
                volt_mv = msg.voltage_battery
                curr_ca = msg.current_battery
                rem = msg.battery_remaining
                print(f"  ├─ RAW voltage_battery : {volt_mv} mV ({(volt_mv/1000.0):.2f} V)")
                print(f"  ├─ RAW current_battery : {curr_ca} cA ({(curr_ca/100.0):.2f} A)")
                print(f"  └─ RAW battery_remaining: {rem} %")
            elif msg_type == 'BATTERY_STATUS':
                id_val = getattr(msg, 'id', 0)
                voltages = getattr(msg, 'voltages', [])
                current_b = getattr(msg, 'current_battery', 0)
                current_cons = getattr(msg, 'current_consumed', 0)
                energy_cons = getattr(msg, 'energy_consumed', 0)
                temp = getattr(msg, 'temperature', 0)
                print(f"  ├─ RAW Battery ID       : {id_val}")
                print(f"  ├─ RAW Cell Voltages(mV): {voltages}")
                print(f"  ├─ RAW current_battery  : {current_b} cA")
                print(f"  ├─ RAW current_consumed : {current_cons} mAh")
                print(f"  └─ RAW energy_consumed  : {energy_cons} hJ")

            if received_count >= 2:
                break

        if received_count == 0:
            print(f"\n{YELLOW}[FAILED] No battery status packets received within {timeout_sec}s.{RESET}")
            print("Make sure CUAV X7 is powered and sending MAVLink streams!")
            return False

        return True
    except Exception as e:
        print(f"{RED}[ERROR] Failed reading battery packets: {e}{RESET}")
        return False

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
    debug_battery(conn)
