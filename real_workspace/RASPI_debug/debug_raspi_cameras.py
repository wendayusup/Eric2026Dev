#!/usr/bin/env python3
"""
RASPI_debug/debug_raspi_cameras.py — Debug Dual Camera MJPEG Streams (Front & Bottom)
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

def check_mjpeg_stream(url, name):
    print(f"Testing {name} Video Stream at {url} ...")
    try:
        req = urllib.request.urlopen(url, timeout=3.0)
        code = req.getcode()
        content_type = req.headers.get('Content-Type', '')
        if code == 200 and 'multipart/x-mixed-replace' in content_type:
            print(f"  ├─ {GREEN}{name} Stream ACTIVE (HTTP 200, Content-Type: {content_type}){RESET}")
            chunk = req.read(2048)
            print(f"  └─ {GREEN}Received MJPEG frame chunk ({len(chunk)} bytes stream data){RESET}")
            return True
        else:
            print(f"  └─ {YELLOW}{name} Stream Responded HTTP {code} ({content_type}){RESET}")
            return False
    except Exception as e:
        print(f"  └─ {RED}Failed connecting to {name} Stream: {e}{RESET}")
        return False

def debug_raspi_cameras():
    print(f"\n{CYAN}{BOLD}━━━ RASPBERRY PI DUAL CAMERA STREAM DEBUGGER (FRONT & BOTTOM) ━━━{RESET}")

    check_mjpeg_stream("http://127.0.0.1:5000/video_feed/bottom", "BOTTOM CAMERA")
    print("")
    check_mjpeg_stream("http://127.0.0.1:5000/video_feed/front", "FRONT CAMERA")

    print("\n  ----------------------------------------")
    print(f"  {CYAN}Pi Dual Camera Purpose Reference:{RESET}")
    print(f"  - Bottom Camera (Downward) = Used for ArUco Marker ID visual detection & precision payload dropping.")
    print(f"  - Front Camera (Forward)   = Used for visual gate navigation & obstacle detection.")

if __name__ == '__main__':
    debug_raspi_cameras()
