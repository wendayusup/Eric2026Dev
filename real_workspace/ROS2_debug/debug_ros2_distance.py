#!/usr/bin/env python3
"""
ROS2_debug/debug_ros2_distance.py — Inspect /mavros/rangefinder Topics (ALT R & RANGE F)
"""
import sys
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Range

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

class RangeInspector(Node):
    def __init__(self):
        super().__init__('debug_range_node')
        self.received_primary = False
        self.received_secondary = False
        self.sub1 = self.create_subscription(Range, '/mavros/rangefinder/rangefinder', self.cb_primary, qos_profile_sensor_data)
        self.sub2 = self.create_subscription(Range, '/mavros/rangefinder/rangefinder_sub', self.cb_secondary, qos_profile_sensor_data)

    def cb_primary(self, msg):
        self.received_primary = True
        print(f"\n{GREEN}{BOLD}[ROS2 TOPIC: /mavros/rangefinder/rangefinder] (RANGE F - PRIMARY):{RESET}")
        print(f"  ├─ Frame ID     : '{msg.header.frame_id}'")
        print(f"  ├─ Current Range: {BOLD}{msg.range:.2f} m{RESET} ({msg.range*100.0:.0f} cm)")
        print(f"  └─ Min / Max    : {msg.min_range:.2f} m to {msg.max_range:.2f} m")

    def cb_secondary(self, msg):
        self.received_secondary = True
        print(f"\n{GREEN}{BOLD}[ROS2 TOPIC: /mavros/rangefinder/rangefinder_sub] (ALT R - SECONDARY / SENSOR ID 10):{RESET}")
        print(f"  ├─ Frame ID     : '{msg.header.frame_id}'")
        print(f"  ├─ Current Range: {BOLD}{msg.range:.2f} m{RESET} ({msg.range*100.0:.0f} cm)")
        print(f"  └─ Min / Max    : {msg.min_range:.2f} m to {msg.max_range:.2f} m")

def debug_ros2_distance(timeout_sec=5.0):
    print(f"\n{CYAN}{BOLD}━━━ INSPECTING ROS2 TOPICS: RANGEFINDER / LIDAR ━━━{RESET}")
    print("Listening to ROS 2 topics /mavros/rangefinder/rangefinder & rangefinder_sub ...")
    if not rclpy.ok():
        rclpy.init()
    node = RangeInspector()
    start = time.time()
    while time.time() - start < timeout_sec:
        rclpy.spin_once(node, timeout_sec=0.2)
        if node.received_primary and node.received_secondary:
            break
    
    if not node.received_primary:
        print(f"{YELLOW}[RANGE F] Topic /mavros/rangefinder/rangefinder has no data (Primary Sensor 1 not connected).{RESET}")
    if not node.received_secondary:
        print(f"{YELLOW}[ALT R] Topic /mavros/rangefinder/rangefinder_sub has no data (Sensor ID 10).{RESET}")
    node.destroy_node()

if __name__ == '__main__':
    debug_ros2_distance()
