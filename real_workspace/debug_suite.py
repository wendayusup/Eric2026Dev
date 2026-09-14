#!/usr/bin/env python3
"""
debug_suite.py — Master Unified Python Debugging Suite for KRTI Autonomous Drone System
Usage:
  python3 real_workspace/debug_suite.py [ros2|cuav|raspi|web|all]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ROS2_debug.main import main as run_ros2
from CUAV_debug.main import main as run_cuav
from RASPI_debug.main import main as run_raspi
from WEB_debug.main import main as run_web

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
MAGENTA = '\033[95m'
RESET = '\033[0m'

def print_banner():
    print(f"\n{CYAN}{BOLD}========================================================={RESET}")
    print(f"{CYAN}{BOLD}  KRTI 2026 AUTONOMOUS DRONE MASTER PYTHON DEBUG SUITE   {RESET}")
    print(f"{CYAN}{BOLD}========================================================={RESET}")
    print(f"Pure Python Debugging Suite (Shell Script-Free Architecture)\n")

def main():
    print_banner()

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
    else:
        print(f"{BOLD}Select System Module to Debug:{RESET}")
        print("  1. ROS 2 Topic & Communication Debugger   (ROS2_debug)")
        print("  2. CUAV X7 / MAVLink Stream Debugger      (CUAV_debug)")
        print("  3. Raspberry Pi Hardware & Cameras        (RASPI_debug)")
        print("  4. Web GCS & Socket.IO Server             (WEB_debug)")
        print("  5. FULL AUDIT (Run All Debug Inspections)")
        print("  0. Exit\n")
        try:
            choice = input(f"{BOLD}Enter Choice (0-5): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            return

        mapping = {'1': 'ros2', '2': 'cuav', '3': 'raspi', '4': 'web', '5': 'all', '0': 'exit'}
        cmd = mapping.get(choice, 'all')

    if cmd == 'exit' or cmd == '0':
        print("Exiting debug suite.")
        return

    if cmd == 'ros2' or cmd == '1':
        print(f"{MAGENTA}{BOLD}>>> LAUNCHING ROS2 COMMUNICATION DEBUGGER <<<{RESET}")
        sys.argv = ['main.py', 'all']
        run_ros2()

    elif cmd == 'cuav' or cmd == '2':
        print(f"{MAGENTA}{BOLD}>>> LAUNCHING CUAV X7 MAVLINK DEBUGGER <<<{RESET}")
        sys.argv = ['main.py', 'all']
        run_cuav()

    elif cmd == 'raspi' or cmd == '3':
        print(f"{MAGENTA}{BOLD}>>> LAUNCHING RASPBERRY PI HARDWARE DEBUGGER <<<{RESET}")
        sys.argv = ['main.py', 'all']
        run_raspi()

    elif cmd == 'web' or cmd == '4':
        print(f"{MAGENTA}{BOLD}>>> LAUNCHING WEB GCS SERVER DEBUGGER <<<{RESET}")
        sys.argv = ['main.py', 'all']
        run_web()

    elif cmd == 'all' or cmd == '5':
        print(f"{MAGENTA}{BOLD}>>> LAUNCHING FULL SYSTEM AUDIT <<<{RESET}")
        sys.argv = ['main.py', 'all']
        run_ros2()
        sys.argv = ['main.py', 'all']
        run_web()
        sys.argv = ['main.py', 'all']
        run_raspi()
        sys.argv = ['main.py', 'all']
        run_cuav()

    print(f"\n{GREEN}{BOLD}✅ Audit Complete! All system modules inspected successfully.{RESET}\n")

if __name__ == '__main__':
    main()
