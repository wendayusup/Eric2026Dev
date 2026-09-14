#!/usr/bin/env python3
"""
ROS2_debug/debug_ros2_battery.py — Inspect /mavros/battery Topic
"""
import sys
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

class BatteryInspector(Node):
    def __init__(self):
        super().__init__('debug_battery_node')
        self.received = False
        self.sub = self.create_subscription(BatteryState, '/mavros/battery', self.cb, qos_profile_sensor_data)

    def cb(self, msg):
        self.received = True
        volt = msg.voltage
        curr = msg.current
        pct = int(msg.percentage * 100) if msg.percentage > 0 else int(min(100.0, max(0.0, (volt/16.8)*100.0)))

        print(f"\n{GREEN}{BOLD}[ROS2 TOPIC: /mavros/battery] RECEIVED:{RESET}")
        print(f"  ├─ Battery Voltage: {BOLD}{volt:.2f} V{RESET} (4S LiPo Max Voltage: 16.80V)")
        print(f"  ├─ Current Draw   : {curr:.2f} A")
        print(f"  ├─ Remaining Power: {BOLD}{pct}%{RESET}")
        print(f"  └─ Cell Voltages  : {[round(c, 2) for c in msg.cell_voltage]}")
        print("  ----------------------------------------")
        print(f"  {CYAN}4S LiPo Battery Reference:{RESET}")
        print(f"  - 16.8V = 100% Fully Charged (4.2V/cell)")
        print(f"  - 14.8V = ~50% Nominal Voltage (3.7V/cell)")
        print(f"  - 14.0V = Critical Voltage Warning (3.5V/cell)")

def debug_ros2_battery(timeout_sec=5.0):
    print(f"\n{CYAN}{BOLD}━━━ INSPECTING ROS2 TOPIC: /mavros/battery ━━━{RESET}")
    print("Listening to ROS 2 topic /mavros/battery ...")
    if not rclpy.ok():
        rclpy.init()
    node = BatteryInspector()
    start = time.time()
    while time.time() - start < timeout_sec and not node.received:
        rclpy.spin_once(node, timeout_sec=0.5)
    
    if not node.received:
        print(f"{RED}[FAILED] No message received on /mavros/battery within {timeout_sec}s.{RESET}")
    node.destroy_node()

if __name__ == '__main__':
    debug_ros2_battery()
