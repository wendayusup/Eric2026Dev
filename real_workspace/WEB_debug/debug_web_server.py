#!/usr/bin/env python3
"""
WEB_debug/debug_web_server.py — Inspect Web GCS Flask Server HTTP Endpoints
"""
import sys
import time
import urllib.request

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_endpoint(url, name):
    try:
        req = urllib.request.urlopen(url, timeout=3.0)
        code = req.getcode()
        size = len(req.read())
        if code == 200:
            print(f"  ├─ {GREEN}[HTTP 200 OK] {name:22s} ({size} bytes loaded){RESET}")
            return True
        else:
            print(f"  ├─ {YELLOW}[HTTP {code}] {name:22s}{RESET}")
            return False
    except Exception as e:
        print(f"  ├─ {RED}[FAILED] {name:22s} -> Error: {e}{RESET}")
        return False

def debug_web_server(base_url='http://127.0.0.1:5000'):
    print(f"\n{CYAN}{BOLD}━━━ WEB GCS FLASK SERVER & HTTP ASSETS DEBUGGER ━━━{RESET}")
    print(f"Inspecting Flask Server endpoints at {base_url} ...")

    check_endpoint(f"{base_url}/", "GCS Main HTML Interface")
    check_endpoint(f"{base_url}/static/script.js", "Main Script.js Logic")
    check_endpoint(f"{base_url}/static/style.css", "Style.css CSS Styling")
    check_endpoint(f"{base_url}/static/manual_control.js", "Manual Control JS")
    check_endpoint(f"{base_url}/static/auto_waypoint.js", "Auto Waypoint JS")
    check_endpoint(f"{base_url}/static/krti_mode.js?v=2", "KRTI Mode JS Module")

    print("  ----------------------------------------")
    print(f"  {CYAN}Flask GCS Server Reference:{RESET}")
    print(f"  - Web GCS Server listens on Port 5000 (0.0.0.0:5000).")
    print(f"  - Accessible from any browser on laptop/phone at: 'http://localhost:5000/'")

if __name__ == '__main__':
    debug_web_server()
