#!/usr/bin/env python3
"""
WEB_debug/main.py — Master Interactive Web GCS Server Inspector
Usage:
  python3 real_workspace/WEB_debug/main.py [server|socketio|all]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WEB_debug.debug_web_server import debug_web_server
from WEB_debug.debug_web_socketio import debug_web_socketio
from WEB_debug import BOLD, CYAN, GREEN, YELLOW, RED, RESET, print_header

def run_all():
    print_header("WEB GCS FLASK & SOCKET.IO DEBUG SUITE")
    debug_web_server()
    debug_web_socketio()
    print(f"\n{GREEN}{BOLD}=== WEB GCS SERVER INSPECTION COMPLETE ==={RESET}\n")

def main():
    param = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'
    if param == 'server' or param == 'http': debug_web_server()
    elif param == 'socketio' or param == 'socket': debug_web_socketio()
    elif param == 'all': run_all()
    else:
        print_header("WEB GCS INSPECTOR (PYTHON)")
        print(f"{YELLOW}Parameter '{param}' not recognized.{RESET}")
        print("Usage: python3 real_workspace/WEB_debug/main.py [server|socketio|all]")

if __name__ == '__main__':
    main()
