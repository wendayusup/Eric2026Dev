#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

import cv2
import numpy as np
import math
import time

from sensor_msgs.msg import Image as ROSImage
from std_msgs.msg import String

# MAVROS messages and services
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode, CommandTOL
from geometry_msgs.msg import PoseStamped, TwistStamped
from cv_bridge import CvBridge

try:
    ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    ARUCO_PARAMS = cv2.aruco.DetectorParameters()
    ARUCO_DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)
    def detect_aruco(img):
        corners, ids, _ = ARUCO_DETECTOR.detectMarkers(img)
        return corners, ids
except AttributeError:
    ARUCO_DICT = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
    ARUCO_PARAMS = cv2.aruco.DetectorParameters_create()
    def detect_aruco(img):
        corners, ids, _ = cv2.aruco.detectMarkers(img, ARUCO_DICT, parameters=ARUCO_PARAMS)
        return corners, ids

class KRTIAutonomousController(Node):
    def __init__(self):
        super().__init__('krti_visual_servo_node')
        self.get_logger().info('KRTI Visual Servo & Mission Node (MAVROS) Diinisialisasi.')

        self.bridge = CvBridge()

        # MAVROS Subscribers
        self.local_pos_sub = self.create_subscription(PoseStamped, '/mavros/local_position/pose', self.local_pos_callback, qos_profile_sensor_data)
        self.state_sub = self.create_subscription(State, '/mavros/state', self.state_callback, qos_profile_sensor_data)
        
        self.aruco_sub = self.create_subscription(String, '/krti/aruco_data', self.aruco_callback, 10)
        self.gcs_cmd_sub = self.create_subscription(String, '/krti/gcs_command', self.gcs_cmd_callback, 10)
        self.red_sub = self.create_subscription(String, '/krti/red_object_data', self.red_callback, 10)

        # MAVROS Publishers
        self.pos_setpoint_pub = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', 10)
        self.vel_setpoint_pub = self.create_publisher(TwistStamped, '/mavros/setpoint_velocity/cmd_vel', 10)
        self.status_pub = self.create_publisher(String, '/krti/status', 10)
        self.servo_pub = self.create_publisher(String, '/krti/servo_command', 10)

        # MAVROS Services
        self.arm_cli = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.set_mode_cli = self.create_client(SetMode, '/mavros/set_mode')
        self.land_cli = self.create_client(CommandTOL, '/mavros/cmd/land')

        self.local_x = 0.0
        self.local_y = 0.0
        self.local_z = 0.0
        self.local_yaw = 0.0
        self.is_armed = False
        self.current_mode = "UNKNOWN"

        self.mission_active = False
        self.current_wp = 0 
        self.wp_start_x = 0.0
        self.wp_start_y = 0.0
        self.wp_start_yaw = 0.0
        self.wp_state = "IDLE" 
        self.servo_action_start_time = 0.0

        self.kp_vel = 0.005
        self.max_vel = 1.0
        self.max_speed = 3.0

        self.target_position = [0.0, 0.0, 0.0]
        self.final_target_position = [0.0, 0.0, 0.0]
        self.setpoint_velocity = [0.0, 0.0, 0.0]
        self.target_velocity_cmd = [0.0, 0.0, 0.0]
        self.target_yaw = 0.0
        self.use_velocity_control = False

        self.timer = self.create_timer(0.05, self.control_loop)

    def quaternion_to_euler(self, q):
        w, x, y, z = q[0], q[1], q[2], q[3]
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1.0:
            pitch = math.copysign(math.pi / 2.0, sinp)
        else:
            pitch = math.asin(sinp)
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return roll, pitch, yaw
        
    def euler_to_quaternion(self, roll, pitch, yaw):
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return [w, x, y, z]

    def local_pos_callback(self, msg):
        self.local_x = msg.pose.position.x
        self.local_y = msg.pose.position.y
        self.local_z = msg.pose.position.z 
        
        q = [msg.pose.orientation.w, msg.pose.orientation.x, msg.pose.orientation.y, msg.pose.orientation.z]
        _, _, yaw = self.quaternion_to_euler(q)
        self.local_yaw = yaw

    def state_callback(self, msg):
        self.is_armed = msg.armed
        self.current_mode = msg.mode

    def gcs_cmd_callback(self, msg):
        cmd = msg.data
        if cmd == "START_AUTO":
            self.start_autonomous_mission()
        elif cmd == "STOP_AUTO":
            self.stop_autonomous_mission()

    def send_status(self, text):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)
        self.get_logger().info(text)

    def set_mode(self, mode_str):
        req = SetMode.Request()
        req.custom_mode = mode_str
        self.set_mode_cli.call_async(req)

    def land(self):
        req = CommandTOL.Request()
        self.land_cli.call_async(req)

    def start_autonomous_mission(self):
        if not self.is_armed:
            self.send_status("MISI DITOLAK: Drone belum ARMED!")
            return
        
        self.mission_active = True
        self.current_wp = 1
        self.wp_start_x = self.local_x
        self.wp_start_y = self.local_y
        self.wp_start_yaw = self.local_yaw
        self.wp_state = "YAWING"
        self.send_status("MEMULAI MISI OTONOM: Menyelaraskan Yaw ke Waypoint 1")
        
        # In ArduPilot, to follow offboard setpoints we use GUIDED mode
        self.set_mode("GUIDED")

    def stop_autonomous_mission(self):
        self.mission_active = False
        self.wp_state = "IDLE"
        self.set_mode("LOITER")
        self.send_status("MISI OTONOM DIBATALKAN: Beralih ke LOITER")

    def aruco_callback(self, msg):
        import json
        if not self.mission_active or self.wp_state != "SERVOING":
            return

        try:
            data = json.loads(msg.data)
            target_id = self.current_wp
            if data.get('id') == target_id:
                err_x = data.get('x', 0)
                err_y = data.get('y', 0)
                
                vy_body = err_x * self.kp_vel
                vx_body = -err_y * self.kp_vel

                vx_body = np.clip(vx_body, -self.max_vel, self.max_vel)
                vy_body = np.clip(vy_body, -self.max_vel, self.max_vel)

                yaw = self.local_yaw
                vx_ned = vx_body * math.cos(yaw) - vy_body * math.sin(yaw)
                vy_ned = vx_body * math.sin(yaw) + vy_body * math.cos(yaw)

                self.target_velocity_cmd = [vx_ned, vy_ned, 0.0]
                self.use_velocity_control = True

                if abs(err_x) < 15 and abs(err_y) < 15:
                    self.target_velocity_cmd = [0.0, 0.0, 0.0]
                    self.get_logger().info("Target ArUco Centered!")
                    self.trigger_waypoint_action()
            else:
                self.target_velocity_cmd = [0.0, 0.0, 0.0]
        except Exception as e:
            pass

    def red_callback(self, msg):
        import json
        if not self.mission_active or self.wp_state != "SERVOING":
            return
        try:
            data = json.loads(msg.data)
            if self.current_wp == 2 and data.get('centered'):
                self.get_logger().info("Target Objek Merah Terpusat! (OR Condition Drop)")
                self.trigger_waypoint_action()
        except Exception as e:
            pass

    def trigger_waypoint_action(self):
        if self.current_wp == 2:
            self.wp_state = "SERVO_ACTION"
            self.servo_action_start_time = time.time()
            self.send_status("SERVO AKTIF: Menjatuhkan Payload Utama (8 Detik)")
            import json
            msg = String()
            msg.data = json.dumps({"servo_id": 1, "angle": 180})
            self.servo_pub.publish(msg)
        elif self.current_wp == 4:
            self.wp_state = "SERVO_ACTION"
            self.send_status("MISI SELESAI: Melakukan Auto-Landing")
            self.land()
            self.mission_active = False

    def control_loop(self):
        if not self.mission_active:
            return

        if self.wp_state == "YAWING":
            self.use_velocity_control = False
            
            if self.current_wp == 1:
                target_x = self.wp_start_x + 4.0
                target_y = self.wp_start_y
            elif self.current_wp == 3:
                target_x = self.wp_start_x + 8.0 * math.cos(self.wp_start_yaw)
                target_y = self.wp_start_y + 8.0 * math.sin(self.wp_start_yaw)
            else:
                target_x = self.local_x
                target_y = self.local_y

            self.target_position = [self.wp_start_x, self.wp_start_y, self.local_z]
            self.target_yaw = math.atan2(target_y - self.wp_start_y, target_x - self.wp_start_x)

            yaw_err = math.atan2(math.sin(self.target_yaw - self.local_yaw), math.cos(self.target_yaw - self.local_yaw))
            
            if abs(yaw_err) < 0.15:
                self.wp_state = "NAVIGATING"
                self.send_status(f"Yaw Sejajar! Mulai bergerak maju ke Waypoint {self.current_wp}")

        elif self.wp_state == "NAVIGATING":
            self.use_velocity_control = False
            if self.current_wp == 1:
                self.final_target_position = [self.wp_start_x + 4.0, self.wp_start_y, self.local_z]
                dx = self.final_target_position[0] - self.local_x
                dy = self.final_target_position[1] - self.local_y
                dist = math.sqrt(dx*dx + dy*dy)

                if dist < 0.2:
                    self.current_wp = 2
                    self.wp_start_x = self.local_x
                    self.wp_start_y = self.local_y
                    self.wp_start_yaw = self.local_yaw - math.radians(90.0) 
                    self.send_status("Waypoint 1 Tercapai! Putar 90 deg CCW & Mencari ArUco ID 2")
                    self.wp_state = "SERVOING" 

            elif self.current_wp == 3:
                target_x = self.wp_start_x + 8.0 * math.cos(self.wp_start_yaw)
                target_y = self.wp_start_y + 8.0 * math.sin(self.wp_start_yaw)
                self.final_target_position = [target_x, target_y, self.local_z]

                dx = self.final_target_position[0] - self.local_x
                dy = self.final_target_position[1] - self.local_y
                dist = math.sqrt(dx*dx + dy*dy)

                if dist < 0.2:
                    self.current_wp = 4
                    self.wp_start_x = self.local_x
                    self.wp_start_y = self.local_y
                    self.wp_start_yaw = self.local_yaw
                    self.send_status("Waypoint 3 Tercapai! Mencari ArUco ID 4 untuk Precision Landing")
                    self.wp_state = "SERVOING"
            
            if self.wp_state == "NAVIGATING":
                dx_slew = self.final_target_position[0] - self.target_position[0]
                dy_slew = self.final_target_position[1] - self.target_position[1]
                dz_slew = self.final_target_position[2] - self.target_position[2]
                
                dist_slew = math.sqrt(dx_slew**2 + dy_slew**2 + dz_slew**2)
                dt = 0.05 
                a_max = 2.0 
                
                if dist_slew > 0.05:
                    des_vx = (dx_slew / dist_slew) * self.max_speed
                    des_vy = (dy_slew / dist_slew) * self.max_speed
                    des_vz = (dz_slew / dist_slew) * self.max_speed
                else:
                    des_vx, des_vy, des_vz = 0.0, 0.0, 0.0
                    self.target_position = list(self.final_target_position)
                    
                for i, des_v in enumerate([des_vx, des_vy, des_vz]):
                    if self.setpoint_velocity[i] < des_v:
                        self.setpoint_velocity[i] = min(self.setpoint_velocity[i] + a_max * dt, des_v)
                    else:
                        self.setpoint_velocity[i] = max(self.setpoint_velocity[i] - a_max * dt, des_v)
                
                if dist_slew > 0.05 or any(abs(v) > 0.01 for v in self.setpoint_velocity):
                    self.target_position[0] += self.setpoint_velocity[0] * dt
                    self.target_position[1] += self.setpoint_velocity[1] * dt
                    self.target_position[2] += self.setpoint_velocity[2] * dt

        elif self.wp_state == "SERVOING":
            self.target_yaw = self.wp_start_yaw

        elif self.wp_state == "SERVO_ACTION":
            self.use_velocity_control = False
            self.target_position = [self.local_x, self.local_y, self.local_z]
            self.target_yaw = self.local_yaw

            if self.current_wp == 2:
                elapsed = time.time() - self.servo_action_start_time
                if elapsed >= 8.0:
                    self.send_status("Aksi Dropping Selesai! Menuju Waypoint 3 (Terbang Maju 8m)")
                    self.current_wp = 3
                    self.wp_start_x = self.local_x
                    self.wp_start_y = self.local_y
                    self.wp_start_yaw = self.local_yaw
                    self.wp_state = "YAWING"

        # Publish Setpoint to MAVROS
        if self.use_velocity_control:
            msg = TwistStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.twist.linear.x = self.target_velocity_cmd[0]
            msg.twist.linear.y = self.target_velocity_cmd[1]
            msg.twist.linear.z = self.target_velocity_cmd[2]
            self.vel_setpoint_pub.publish(msg)
        else:
            msg = PoseStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.pose.position.x = self.target_position[0]
            msg.pose.position.y = self.target_position[1]
            msg.pose.position.z = self.target_position[2]
            
            q = self.euler_to_quaternion(0, 0, self.target_yaw)
            msg.pose.orientation.w = q[0]
            msg.pose.orientation.x = q[1]
            msg.pose.orientation.y = q[2]
            msg.pose.orientation.z = q[3]
            self.pos_setpoint_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = KRTIAutonomousController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except BaseException:
            pass
        try:
            rclpy.shutdown()
        except BaseException:
            pass

if __name__ == '__main__':
    main()
