#!/usr/bin/env python3
"""
ROS2_debug/debug_ros2_state.py — Inspect /mavros/state Topic
"""
import sys
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from mavros_msgs.msg import State

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

class StateInspector(Node):
    def __init__(self):
        super().__init__('debug_state_node')
        self.received = False
        self.sub = self.create_subscription(State, '/mavros/state', self.cb, qos_profile_sensor_data)

    def cb(self, msg):
        self.received = True
        print(f"\n{GREEN}{BOLD}[ROS2 TOPIC: /mavros/state] RECEIVED:{RESET}")
        print(f"  ├─ FCU Connected  : {BOLD}{'YES (Connected = True)' if msg.connected else 'NO (FCU Disconnected)'}{RESET}")
        print(f"  ├─ Arming Status  : {BOLD}{'ARMED (Motors Active/Unlocked)' if msg.armed else 'DISARMED (Motors Locked)'}{RESET}")
        print(f"  ├─ Flight Mode    : {BOLD}{msg.mode}{RESET} (e.g. STABILIZE, LOITER, GUIDED, RTL, LAND)")
        print(f"  ├─ Manual Input   : {'Active (RC Transmitter Connected)' if msg.manual_input else 'No Manual RC Input'}")
        print(f"  └─ System Status  : Enum Code {msg.system_status} (3=STANDBY, 4=ACTIVE)")
        print("  ----------------------------------------")
        print(f"  {CYAN}Flight Mode Reference:{RESET}")
        print(f"  - 'STABILIZE' = Manual pitch/roll control with gyro stabilization.")
        print(f"  - 'GUIDED'    = Autonomous ROS 2 / Web GCS waypoint control mode.")
        print(f"  - 'LOITER'    = GPS position-hold mode.")

def debug_ros2_state(timeout_sec=5.0):
    print(f"\n{CYAN}{BOLD}━━━ INSPECTING ROS2 TOPIC: /mavros/state ━━━{RESET}")
    print("Listening to ROS 2 topic /mavros/state ...")
    if not rclpy.ok():
        rclpy.init()
    node = StateInspector()
    start = time.time()
    while time.time() - start < timeout_sec and not node.received:
        rclpy.spin_once(node, timeout_sec=0.5)
    
    if not node.received:
        print(f"{RED}[FAILED] No message received on /mavros/state within {timeout_sec}s.{RESET}")
        print(f"{YELLOW}Make sure backend_real.py or mavros_node is currently running!{RESET}")
    node.destroy_node()

if __name__ == '__main__':
    debug_ros2_state()
