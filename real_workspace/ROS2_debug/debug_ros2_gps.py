#!/usr/bin/env python3
"""
ROS2_debug/debug_ros2_gps.py — Inspect /mavros/global_position/global & GPS Status
"""
import sys
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import NavSatFix

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

class GpsInspector(Node):
    def __init__(self):
        super().__init__('debug_gps_node')
        self.received = False
        self.sub = self.create_subscription(NavSatFix, '/mavros/global_position/global', self.cb, qos_profile_sensor_data)

    def cb(self, msg):
        self.received = True
        status_str = "3D FIX OK (Strong Satellite Signal)" if msg.status.status >= 0 else "NO FIX (Acquiring Satellites...)"

        print(f"\n{GREEN}{BOLD}[ROS2 TOPIC: /mavros/global_position/global] RECEIVED:{RESET}")
        print(f"  ├─ GPS Fix Status : {BOLD}{status_str}{RESET} (status_code={msg.status.status})")
        print(f"  ├─ Latitude       : {BOLD}{msg.latitude:.7f}{RESET}°")
        print(f"  ├─ Longitude      : {BOLD}{msg.longitude:.7f}{RESET}°")
        print(f"  └─ Altitude MSL   : {BOLD}{msg.altitude:.2f} m{RESET} (Above Mean Sea Level)")
        print("  ----------------------------------------")
        print(f"  {CYAN}GPS Fix Reference:{RESET}")
        print(f"  - Status >= 0 indicates the drone has locked a valid 3D GPS Fix (min 6 satellites).")
        print(f"  - Latitude & Longitude coordinates populate Leaflet Map markers on Web GCS.")

def debug_ros2_gps(timeout_sec=5.0):
    print(f"\n{CYAN}{BOLD}━━━ INSPECTING ROS2 TOPIC: GPS GLOBAL POSITION ━━━{RESET}")
    print("Listening to ROS 2 topic /mavros/global_position/global ...")
    if not rclpy.ok():
        rclpy.init()
    node = GpsInspector()
    start = time.time()
    while time.time() - start < timeout_sec and not node.received:
        rclpy.spin_once(node, timeout_sec=0.5)
    
    if not node.received:
        print(f"{RED}[FAILED] No message received on /mavros/global_position/global within {timeout_sec}s.{RESET}")
    node.destroy_node()

if __name__ == '__main__':
    debug_ros2_gps()
