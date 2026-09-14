#!/usr/bin/env python3
"""
DEBUG ARM REASON TOOL
Pings ArduPilot / MAVROS Arming Service and captures exact EKF / PreArm rejection reason.
"""

import sys
import time
import rclpy
from rclpy.node import Node
from mavros_msgs.srv import CommandBool, SetMode
from mavros_msgs.msg import State, StatusText
from rclpy.qos import qos_profile_sensor_data

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

class ArmReasonDebugger(Node):
    def __init__(self):
        super().__init__('debug_arm_reason_node')
        self.state_sub = self.create_subscription(State, '/mavros/state', self.state_cb, qos_profile_sensor_data)
        self.status_sub = self.create_subscription(StatusText, '/mavros/statustext/recv', self.status_cb, qos_profile_sensor_data)
        
        self.arm_cli = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.mode_cli = self.create_client(SetMode, '/mavros/set_mode')

        self.current_state = None
        self.last_status_text = []

    def state_cb(self, msg):
        self.current_state = msg

    def status_cb(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.last_status_text.append(f"[{timestamp}] (Severity {msg.severity}): {msg.text}")
        print(f"  {YELLOW}📢 [APM STATUSTEXT]{RESET} {msg.text}")

def main():
    print(f"\n{CYAN}{BOLD}━━━ CUAV X7 ARMING DIAGNOSTIC DEBUGGER ━━━{RESET}")
    rclpy.init()
    debugger = ArmReasonDebugger()

    print("Checking connection to MAVROS...")
    t0 = time.time()
    while rclpy.ok() and (time.time() - t0 < 3.0):
        rclpy.spin_once(debugger, timeout_sec=0.1)
        if debugger.current_state:
            break

    if not debugger.current_state:
        print(f"{RED}[ERROR] No connection to /mavros/state! Is backend_real.py running?{RESET}")
        rclpy.shutdown()
        return

    print(f"Current Flight Mode: {BOLD}{debugger.current_state.mode}{RESET}")
    print(f"Current Arming State: {BOLD}{'ARMED' if debugger.current_state.armed else 'DISARMED'}{RESET}\n")

    print(f"{CYAN}Sending ARM command to CUAV X7...{RESET}")
    if not debugger.arm_cli.wait_for_service(timeout_sec=2.0):
        print(f"{RED}[ERROR] Service /mavros/cmd/arming not available!{RESET}")
        rclpy.shutdown()
        return

    req = CommandBool.Request()
    req.value = True
    future = debugger.arm_cli.call_async(req)
    
    t_start = time.time()
    while rclpy.ok() and (time.time() - t_start < 4.0):
        rclpy.spin_once(debugger, timeout_sec=0.1)
        if future.done():
            break

    if future.done():
        res = future.result()
        if res.success:
            print(f"{GREEN}{BOLD}[SUCCESS] ARMED SUCCESSFULLY! Motor unlocked.{RESET}")
        else:
            print(f"{RED}{BOLD}[REJECTED] ArduPilot rejected ARM command (Result code {res.result}).{RESET}")
            print(f"\n{BOLD}Analysis of Rejection:{RESET}")
            if debugger.current_state.mode == 'GUIDED':
                print(f"  ├─ {YELLOW}Mode is GUIDED{RESET}: ArduPilot requires a valid 3D GPS Fix before arming in GUIDED mode.")
                print(f"  ├─ Check if indoor (no GPS) or GPS 3D Fix is missing.")
                print(f"  └─ Try testing in {GREEN}STABILIZE{RESET} mode to verify motors without GPS.")
            else:
                print(f"  └─ Check PreArm warnings above or Safety Switch status.")
    else:
        print(f"{RED}[TIMEOUT] No response from Flight Controller within 4s.{RESET}")

    print(f"\n{CYAN}Listening for APM StatusText messages for 3 seconds...{RESET}")
    t_end = time.time() + 3.0
    while rclpy.ok() and time.time() < t_end:
        rclpy.spin_once(debugger, timeout_sec=0.1)

    debugger.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
