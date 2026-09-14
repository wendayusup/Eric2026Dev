#!/usr/bin/env python3
"""
ROS2_debug/debug_ros2_imu.py — Inspect /mavros/imu/data Topic & Orientation Math
"""
import sys
import time
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def quaternion_to_euler(q):
    w, x, y, z = q.w, q.x, q.y, q.z
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return roll, pitch, yaw

class ImuInspector(Node):
    def __init__(self):
        super().__init__('debug_imu_node')
        self.received = False
        self.sub = self.create_subscription(Imu, '/mavros/imu/data', self.cb, qos_profile_sensor_data)

    def cb(self, msg):
        self.received = True
        roll_rad, pitch_rad, yaw_rad = quaternion_to_euler(msg.orientation)
        r_deg = math.degrees(roll_rad)
        p_deg = math.degrees(-pitch_rad) # Reversed for ENU Web alignment
        y_deg = (math.degrees(-yaw_rad) + 360.0) % 360.0

        print(f"\n{GREEN}{BOLD}[ROS2 TOPIC: /mavros/imu/data] RECEIVED:{RESET}")
        print(f"  ├─ Frame ID         : '{msg.header.frame_id}'")
        print(f"  ├─ Quaternion RAW   : [w={msg.orientation.w:.4f}, x={msg.orientation.x:.4f}, y={msg.orientation.y:.4f}, z={msg.orientation.z:.4f}]")
        print(f"  ├─ Roll  (Bank Left/Right)  : {BOLD}{r_deg:.2f}°{RESET} (rad: {roll_rad:.3f})")
        print(f"  ├─ Pitch (Nose Up/Down)    : {BOLD}{p_deg:.2f}°{RESET} (rad: {-pitch_rad:.3f}) [ENU Inverted]")
        print(f"  ├─ Yaw   (Heading Direction): {BOLD}{y_deg:.2f}°{RESET} (rad: {-yaw_rad:.3f}) [ENU Inverted]")
        print(f"  ├─ Gyro Angular Velocity    : X={msg.angular_velocity.x:.3f}, Y={msg.angular_velocity.y:.3f}, Z={msg.angular_velocity.z:.3f} rad/s")
        print(f"  └─ Accel Linear Acceleration: X={msg.linear_acceleration.x:.3f}, Y={msg.linear_acceleration.y:.3f}, Z={msg.linear_acceleration.z:.3f} m/s²")
        print("  ----------------------------------------")
        print(f"  {CYAN}IMU Physics Reference:{RESET}")
        print(f"  - Accelerometer Z ~ 9.81 m/s² indicates standard Earth gravity.")
        print(f"  - Pitch & Yaw inversions (-pitch, -yaw) align ArduPilot NED frame 1:1 with ROS 2 ENU Web visualizer.")

def debug_ros2_imu(timeout_sec=5.0):
    print(f"\n{CYAN}{BOLD}━━━ INSPECTING ROS2 TOPIC: /mavros/imu/data ━━━{RESET}")
    print("Listening to ROS 2 topic /mavros/imu/data ...")
    if not rclpy.ok():
        rclpy.init()
    node = ImuInspector()
    start = time.time()
    while time.time() - start < timeout_sec and not node.received:
        rclpy.spin_once(node, timeout_sec=0.5)
    
    if not node.received:
        print(f"{RED}[FAILED] No message received on /mavros/imu/data within {timeout_sec}s.{RESET}")
    node.destroy_node()

if __name__ == '__main__':
    debug_ros2_imu()
