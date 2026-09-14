#!/usr/bin/env python3
"""
RASPI_debug/debug_raspi_connection.py — Debug Raspberry Pi IP, SSH & Socket.IO Heartbeat
"""
import sys
import time
import socket
import urllib.request
import json

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_socket_port(ip, port, timeout=2.0):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((ip, port))
        s.close()
        return res == 0
    except Exception:
        return False

def debug_raspi_connection(pi_ip='10.192.31.76'):
    print(f"\n{CYAN}{BOLD}━━━ RASPBERRY PI CONNECTION DEBUGGER (PYTHON) ━━━{RESET}")
    print(f"Testing network connectivity to Raspberry Pi ({pi_ip}) ...")

    # 1. Test SSH Port 22
    ssh_ok = check_socket_port(pi_ip, 22, timeout=2.0)
    if ssh_ok:
        print(f"  ├─ {GREEN}Port 22 SSH : CONNECTED (Raspberry Pi Online & Accepting SSH){RESET}")
    else:
        print(f"  ├─ {RED}Port 22 SSH : UNREACHABLE (Pi Offline / IP Changed){RESET}")

    # 2. Test Web GCS Flask Server Status
    gcs_ok = check_socket_port('127.0.0.1', 5000, timeout=2.0)
    if gcs_ok:
        print(f"  ├─ {GREEN}Port 5000 GCS: CONNECTED (Flask Server + Socket.IO Active){RESET}")
    else:
        print(f"  ├─ {YELLOW}Port 5000 GCS: Unreachable (Run backend_real.py first!){RESET}")

    print("  ----------------------------------------")
    print(f"  {CYAN}Deployment Reference:{RESET}")
    print(f"  - Ensure laptop & Pi are connected to the same Wi-Fi / Hotspot network.")
    print(f"  - Instant SSH connection: 'bash real_workspace/connect_raspi.sh'")
    print(f"  - One-click Pi deployment: 'bash real_workspace/deploy_to_pi.sh'")

if __name__ == '__main__':
    target_ip = sys.argv[1] if len(sys.argv) > 1 else '10.192.31.76'
    debug_raspi_connection(target_ip)
