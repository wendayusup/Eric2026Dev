#!/usr/bin/env python3
"""
CUAV_debug/debug_distance.py — Debug MAVLink DISTANCE_SENSOR & ROS2 Rangefinder
"""
import sys
import time
from CUAV_debug import BOLD, CYAN, GREEN, RED, RESET, create_mavlink_connection

def debug_distance(connection_str='udp:127.0.0.1:14550', timeout_sec=10):
    print(f"\n{CYAN}{BOLD}━━━ DEBUG RANGEFINDER / DISTANCE_SENSOR (PYTHON) ━━━{RESET}")
    print(f"Membuka koneksi MAVLink di {connection_str} ...")

    try:
        mav = create_mavlink_connection(connection_str)
    except Exception as e:
        print(f"{RED}[ERROR] Gagal membuka koneksi MAVLink {connection_str}: {e}{RESET}")
        return False

    print("Mendengarkan paket DISTANCE_SENSOR (berjalan selama 10 detik)...")
    start = time.time()
    count = 0

    while time.time() - start < timeout_sec:
        msg = mav.recv_match(type='DISTANCE_SENSOR', blocking=True, timeout=1.0)
        if msg:
            count += 1
            dist_m = msg.current_distance / 100.0
            min_m = msg.min_distance / 100.0
            max_m = msg.max_distance / 100.0
            print(f"{GREEN}[PAKET #{count}] DISTANCE_SENSOR:{RESET}")
            print(f"  ├─ Sensor ID         : {msg.id}")
            print(f"  ├─ Sensor Type       : {msg.type} (0=LASER, 1=ULTRASOUND, 2=INFRARED)")
            print(f"  ├─ Current Distance  : {msg.current_distance} cm ({BOLD}{dist_m:.2f} m{RESET})")
            print(f"  ├─ Min Distance      : {msg.min_distance} cm ({min_m:.2f} m)")
            print(f"  ├─ Max Distance      : {msg.max_distance} cm ({max_m:.2f} m)")
            print(f"  └─ Orientation Enum  : {msg.orientation}")
            print("  ----------------------------------------")
            if count >= 5:
                break

    if count == 0:
        print(f"{RED}[GAGAL] Tidak menerima paket DISTANCE_SENSOR dalam {timeout_sec} detik.{RESET}")
        return False
    else:
        print(f"{GREEN}[SUKSES] Berhasil membaca {count} paket MAVLink DISTANCE_SENSOR!{RESET}")
        return True

if __name__ == '__main__':
    conn = sys.argv[1] if len(sys.argv) > 1 else 'udp:127.0.0.1:14550'
    debug_distance(conn)
