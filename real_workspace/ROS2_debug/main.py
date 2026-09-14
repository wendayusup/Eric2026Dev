#!/usr/bin/env python3
"""
ROS2_debug/main.py — Master Interactive ROS2 Topics Inspector
Usage:
  python3 real_workspace/ROS2_debug/main.py [state|imu|distance|battery|gps|all]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ROS2_debug.debug_ros2_state import debug_ros2_state
from ROS2_debug.debug_ros2_imu import debug_ros2_imu
from ROS2_debug.debug_ros2_distance import debug_ros2_distance
from ROS2_debug.debug_ros2_battery import debug_ros2_battery
from ROS2_debug.debug_ros2_gps import debug_ros2_gps
from ROS2_debug.debug_arm_reason import main as debug_arm_main
from ROS2_debug import BOLD, CYAN, GREEN, YELLOW, RED, RESET, print_header

def run_all():
    print_header("ROS2 TOPICS & COMMUNICATION DEBUG SUITE")
    debug_ros2_state(timeout_sec=2.0)
    debug_ros2_distance(timeout_sec=2.0)
    debug_ros2_battery(timeout_sec=2.0)
    debug_ros2_imu(timeout_sec=2.0)
    debug_ros2_gps(timeout_sec=2.0)
    print(f"\n{GREEN}{BOLD}=== ROS2 TOPIC INSPECTION COMPLETE ==={RESET}\n")

def main():
    param = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'
    if param == 'state': debug_ros2_state()
    elif param == 'arm': debug_arm_main()
    elif param == 'imu': debug_ros2_imu()
    elif param == 'distance' or param == 'lidar': debug_ros2_distance()
    elif param == 'battery': debug_ros2_battery()
    elif param == 'gps': debug_ros2_gps()
    elif param == 'all': run_all()
    else:
        print_header("ROS2 TOPICS INSPECTOR (PYTHON)")
        print(f"{YELLOW}Parameter '{param}' not recognized.{RESET}")
        print("Usage: python3 real_workspace/ROS2_debug/main.py [state|arm|imu|distance|battery|gps|all]")

if __name__ == '__main__':
    main()
