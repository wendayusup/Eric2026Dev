#!/usr/bin/env python3
"""
WEB_debug/debug_web_socketio.py — Inspect Web GCS Socket.IO Live Telemetry Broadcast
"""
import sys
import time
import urllib.request
import json

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def debug_web_socketio(base_url='http://127.0.0.1:5000'):
    print(f"\n{CYAN}{BOLD}━━━ SOCKET.IO REALTIME BROADCAST DEBUGGER ━━━{RESET}")
    print(f"Testing Socket.IO engine handshake at {base_url}/socket.io/ ...")

    url = f"{base_url}/socket.io/?EIO=4&transport=polling"
    try:
        req = urllib.request.urlopen(url, timeout=3.0)
        data = req.read().decode('utf-8')
        if req.getcode() == 200:
            print(f"  ├─ {GREEN}Socket.IO Handshake SUCCESSFUL!{RESET}")
            print(f"  └─ Handshake Payload: {data[:100]}...")
            print(f"{GREEN}[SUCCESS] Socket.IO engine ready to stream telemetry to web clients!{RESET}")
            return True
        else:
            print(f"  └─ {YELLOW}Handshake Responded HTTP {req.getcode()}{RESET}")
            return False
    except Exception as e:
        print(f"  └─ {RED}Failed Socket.IO Handshake: {e}{RESET}")
        return False

if __name__ == '__main__':
    debug_web_socketio()
