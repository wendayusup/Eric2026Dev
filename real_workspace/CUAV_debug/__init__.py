# CUAV_debug package initialization
"""
CUAV_debug - Modular Python Telemetry Debugging Suite for CUAV X7 / ArduPilot / ROS2
"""
import sys
import time
from pymavlink import mavutil

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
MAGENTA = '\033[95m'
RESET = '\033[0m'

def print_header(title: str):
    print(f"\n{CYAN}{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

def create_mavlink_connection(conn_str="udp:127.0.0.1:14550"):
    if conn_str.startswith('/dev/'):
        if ':' in conn_str:
            device, baud_str = conn_str.split(':')
            return mavutil.mavlink_connection(device, baud=int(baud_str))
        else:
            return mavutil.mavlink_connection(conn_str, baud=57600)
    else:
        return mavutil.mavlink_connection(conn_str)
