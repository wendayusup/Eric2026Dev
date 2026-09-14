#!/usr/bin/env python3
import threading
import time
import math
import collections
import statistics
import cv2
from PIL import Image
import io
import base64
import json

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

# Import MAVROS and Standard messages
from mavros_msgs.msg import State, VfrHud, StatusText, PositionTarget, Waypoint, WaypointReached
from mavros_msgs.srv import CommandBool, SetMode, CommandTOL, ParamSet, StreamRate, CommandLong, WaypointPush, WaypointClear
from mavros_msgs.msg import ParamValue
from geometry_msgs.msg import PoseStamped, TwistStamped
from sensor_msgs.msg import NavSatFix, BatteryState, Imu, Range
from sensor_msgs.msg import Image as ROSImage
from std_msgs.msg import Float32, String

from cv_bridge import CvBridge

# Flask & Socket.IO
from flask import Flask, render_template, Response
from flask_socketio import SocketIO
from flask_cors import CORS

import os
def find_web_dir():
    curr = os.path.abspath(__file__)
    for _ in range(10):
        curr = os.path.dirname(curr)
        web_path = os.path.join(curr, 'web')
        if os.path.exists(web_path) and os.path.isdir(web_path):
            return web_path
    return '/home/wenda/krti_2026/web'

web_dir = find_web_dir()
app = Flask(
    __name__,
    template_folder=os.path.join(web_dir, 'templates'),
    static_folder=os.path.join(web_dir, 'static')
)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global Telemetry Storage
current_telemetry = {
    'connected': False,
    'alt': 0.0,
    'alt_front': 0.0,
    'alt_rear': 0.0,
    'heading_offset': 0.0,
    'alt_abs': 0.0,
    'lat': 0.0,
    'lng': 0.0,
    'is_armed': False,
    'current_wp_index': 0,
    'battery_remaining': 0,
    'voltage_battery': 0.0,
    'heading': 0.0,
    'nav_state': 0,
    'roll': 0.0,
    'pitch': 0.0,
    'yaw': 0.0,
    'speed': 0.0,
    'rssi_dbm': None,
    'mode': 'UNKNOWN'
}

latest_frames = {
    'front': None,
    'bottom': None
}
latest_frame_versions = {
    'front': 0,
    'bottom': 0
}
latest_camera_status = {
    'front': {'connected': False, 'rssi': -100},
    'bottom': {'connected': False, 'rssi': -100}
}
frame_lock = threading.Lock()

CAMERA_PROCESS_INTERVAL = 0.04  # detik (25 FPS)
_last_front_process = 0.0
_last_bottom_process = 0.0

bridge = CvBridge()
ros_node_instance = None
pi_wifi_rssi_val = -65

def haversine_distance_and_bearing(lat1, lon1, lat2, lon2):
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = R * c

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = math.atan2(y, x)
    return distance, bearing

# Setup ArUco Detector for Simulation Fallback (supports 4X4 for sim, 7X7 for real)
try:
    ARUCO_DICT_4X4 = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    ARUCO_DICT_7X7 = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_7X7_50)
    ARUCO_PARAMS = cv2.aruco.DetectorParameters()
    ARUCO_DETECTOR_4X4 = cv2.aruco.ArucoDetector(ARUCO_DICT_4X4, ARUCO_PARAMS)
    ARUCO_DETECTOR_7X7 = cv2.aruco.ArucoDetector(ARUCO_DICT_7X7, ARUCO_PARAMS)
    def detect_aruco_sim(img):
        corners, ids, _ = ARUCO_DETECTOR_4X4.detectMarkers(img)
        if ids is None or len(ids) == 0:
            corners, ids, _ = ARUCO_DETECTOR_7X7.detectMarkers(img)
        return corners, ids
except AttributeError:
    ARUCO_DICT_4X4 = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
    ARUCO_DICT_7X7 = cv2.aruco.Dictionary_get(cv2.aruco.DICT_7X7_50)
    ARUCO_PARAMS = cv2.aruco.DetectorParameters_create()
    def detect_aruco_sim(img):
        corners, ids, _ = cv2.aruco.detectMarkers(img, ARUCO_DICT_4X4, parameters=ARUCO_PARAMS)
        if ids is None or len(ids) == 0:
            corners, ids, _ = cv2.aruco.detectMarkers(img, ARUCO_DICT_7X7, parameters=ARUCO_PARAMS)
        return corners, ids

def get_offline_frame():
    try:
        img = Image.new('RGB', (320, 240), color=(18, 18, 18))
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue()
    except Exception:
        return b''

offline_frame = get_offline_frame()

@app.route('/')
def index():
    return render_template('index.html')

def gen_video(camera_id):
    last_version = -1
    while True:
        with frame_lock:
            version = latest_frame_versions.get(camera_id, 0)
            frame = latest_frames.get(camera_id)

        if version != last_version and frame is not None:
            last_version = version
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.01)
        elif frame is None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + offline_frame + b'\r\n')
            time.sleep(0.1)
        else:
            time.sleep(0.01)

@app.route('/video_feed/front')
def video_feed_front():
    return Response(gen_video('front'), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed/bottom')
def video_feed_bottom():
    return Response(gen_video('bottom'), mimetype='multipart/x-mixed-replace; boundary=frame')


class TelemetryFilter:
    """Exponential Moving Average (EMA) Low-Pass Filter dengan penanganan NaN/Inf."""
    def __init__(self, alpha=0.25):
        self.alpha = alpha
        self.value = None

    def filter(self, new_val):
        if new_val is None or math.isnan(new_val) or math.isinf(new_val):
            return self.value if self.value is not None else 0.0
        if self.value is None:
            self.value = float(new_val)
        else:
            self.value = self.alpha * float(new_val) + (1.0 - self.alpha) * self.value
        return self.value

    def reset(self):
        self.value = None


def is_valid_range(msg, min_dist=0.02, max_dist=45.0):
    if msg is None:
        return False
    dist = msg.range
    if math.isnan(dist) or math.isinf(dist):
        return False
    if dist < min_dist or dist > max_dist:
        return False
    min_r = getattr(msg, 'min_range', 0.0)
    max_r = getattr(msg, 'max_range', 0.0)
    if min_r > 0.0 and dist < min_r:
        return False
    if max_r > 0.0 and dist > max_r:
        return False
    return True


class ROS2GCSBridgeNode(Node):
    def __init__(self):
        super().__init__('krti_gcs_bridge_node')
        global ros_node_instance
        ros_node_instance = self

        self.get_logger().info('GCS Bridge Node (MAVROS) Diinisialisasi.')
        self.last_local_pos_time = 0.0
        self.last_rangefinder_time = 0.0
        self.last_any_data_time   = 0.0  # tracks any FCU data for connection watchdog
        # Dual I2C rangefinder - value clustering approach
        self.rf_buf_front = collections.deque(maxlen=7)
        self.rf_buf_rear  = collections.deque(maxlen=7)
        self.rf_center_front = None  # running mean for cluster A
        self.rf_center_rear  = None  # running mean for cluster B
        self.rf_last_val  = None
        self.rf_last_time = 0.0

        # Telemetry Filters for Parameter Stabilization
        self.filt_alt_front = TelemetryFilter(alpha=0.30)
        self.filt_alt_rear  = TelemetryFilter(alpha=0.30)
        self.filt_alt       = TelemetryFilter(alpha=0.25)
        self.filt_alt_abs   = TelemetryFilter(alpha=0.20)
        self.filt_speed     = TelemetryFilter(alpha=0.20)
        self.filt_roll      = TelemetryFilter(alpha=0.35)
        self.filt_pitch     = TelemetryFilter(alpha=0.35)
        self.filt_yaw       = TelemetryFilter(alpha=0.35)
        self.filt_voltage   = TelemetryFilter(alpha=0.10)

        camera_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )

        # MAVROS Subscribers
        self.state_sub = self.create_subscription(State, '/mavros/state', self.state_callback, qos_profile_sensor_data)
        self.local_pos_sub = self.create_subscription(PoseStamped, '/mavros/local_position/pose', self.local_pos_callback, qos_profile_sensor_data)
        self.local_vel_sub = self.create_subscription(TwistStamped, '/mavros/local_position/velocity_local', self.local_vel_callback, qos_profile_sensor_data)
        self.gps_sub = self.create_subscription(NavSatFix, '/mavros/global_position/global', self.gps_callback, qos_profile_sensor_data)
        self.battery_sub = self.create_subscription(BatteryState, '/mavros/battery', self.battery_callback, qos_profile_sensor_data)
        self.vfr_sub = self.create_subscription(VfrHud, '/mavros/vfr_hud', self.vfr_hud_callback, qos_profile_sensor_data)
        self.imu_sub = self.create_subscription(Imu, '/mavros/imu/data', self.imu_callback, qos_profile_sensor_data)
        self.statustext_sub = self.create_subscription(StatusText, '/mavros/statustext/recv', self.statustext_callback, qos_profile_sensor_data)
        self.rangefinder_sub = self.create_subscription(Range, '/mavros/rangefinder/rangefinder', self.rangefinder_callback, qos_profile_sensor_data)
        self.altitudefinder_sub = self.create_subscription(Range, '/mavros/rangefinder/rangefinder_sub', self.altitudefinder_callback, qos_profile_sensor_data)

        # Cameras and custom status
        self.front_cam_sub = self.create_subscription(ROSImage, '/camera/front', self.front_cam_callback, camera_qos)
        self.bottom_cam_sub = self.create_subscription(ROSImage, '/camera/bottom', self.bottom_cam_callback, camera_qos)
        self.status_topic_sub = self.create_subscription(String, '/krti/status', self.status_topic_callback, 10)

        # MAVROS Publishers
        self.pos_setpoint_pub = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', 10)
        # PositionTarget for direct, reliable altitude control in GUIDED mode
        self.pos_raw_pub = self.create_publisher(PositionTarget, '/mavros/setpoint_raw/local', 10)
        self.vel_setpoint_pub = self.create_publisher(TwistStamped, '/mavros/setpoint_velocity/cmd_vel', 10)

        # Custom Publishers
        self.gcs_cmd_pub = self.create_publisher(String, '/krti/gcs_command', 10)
        self.servo_pub = self.create_publisher(String, '/krti/servo_command', 10)
        self.aruco_pub = self.create_publisher(String, '/krti/aruco_data', 10)
        self.red_object_pub = self.create_publisher(String, '/krti/red_object_data', 10)

        # MAVROS Services
        self.arm_cli = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.set_mode_cli = self.create_client(SetMode, '/mavros/set_mode')
        self.takeoff_cli = self.create_client(CommandTOL, '/mavros/cmd/takeoff')
        self.land_cli = self.create_client(CommandTOL, '/mavros/cmd/land')
        self.param_set_cli = self.create_client(ParamSet, '/mavros/param/set')
        self.stream_rate_cli = self.create_client(StreamRate, '/mavros/set_stream_rate')
        self.command_cli = self.create_client(CommandLong, '/mavros/cmd/command')
        self.wp_push_cli = self.create_client(WaypointPush, '/mavros/mission/push')
        self.wp_clear_cli = self.create_client(WaypointClear, '/mavros/mission/clear')
        self.wp_reached_sub = self.create_subscription(WaypointReached, '/mavros/mission/reached', self.wp_reached_callback, 10)

        # Internal state tracking
        self._stream_rates_configured = False
        self._was_connected = False

        # Guided control state
        self.guided_active = False
        self.target_position = [0.0, 0.0, 0.0]
        self.final_target_position = [0.0, 0.0, 0.0]
        self.setpoint_velocity = [0.0, 0.0, 0.0]
        self.max_speed = 4.0
        self.is_yawing_to_target = False
        self.target_yaw = 0.0
        self.target_velocity_cmd = [0.0, 0.0, 0.0]
        self.use_velocity_control = False
        self.is_taking_off = False
        self.pending_takeoff_alt = None

        self.ref_lat = None
        self.ref_lon = None
        self.ref_alt = None
        self.local_x = 0.0
        self.local_y = 0.0
        self.local_z = 0.0
        # ENU yaw from local_position/pose quaternion — used for NAVIGATION.
        # DO NOT use current_telemetry['yaw'] for nav: that is NEGATED for compass display.
        self.current_yaw_rad = 0.0

        self.auto_mission_array = []
        self.current_auto_wp_index = 0
        self.auto_mission_active = False

        self.last_front_cam_time = None
        self.last_bottom_cam_time = None

        self.timer = self.create_timer(0.05, self.guided_timer_callback)
        self.create_timer(0.1, self.telemetry_broadcast_callback)

        # Start direct MAVLink DISTANCE_SENSOR listener thread for instant web UI telemetry
        threading.Thread(target=self._mavlink_distance_listener, daemon=True).start()

    def _mavlink_distance_listener(self):
        """
        Background listener for MAVLink DISTANCE_SENSOR packets on UDP 14550.
        Separately updates alt_rear (ALT R) for Sensor ID 10/2, or alt_front (RANGE F) for Sensor ID 0/1.
        """
        import time
        from pymavlink import mavutil

        mav_conn = None
        while rclpy.ok():
            try:
                if mav_conn is None:
                    mav_conn = mavutil.mavlink_connection('udp:127.0.0.1:14551', input=True)
                msg = mav_conn.recv_match(type='DISTANCE_SENSOR', blocking=True, timeout=1.0)
                if msg:
                    dist_m = msg.current_distance / 100.0
                    if 0.01 <= dist_m <= 50.0:
                        global current_telemetry
                        sensor_id = getattr(msg, 'id', 0)
                        if sensor_id == 10 or sensor_id == 2:
                            filt_r = self.filt_alt_rear.filter(dist_m)
                            current_telemetry['alt_rear'] = round(filt_r, 2)
                        else:
                            filt_f = self.filt_alt_front.filter(dist_m)
                            current_telemetry['alt_front'] = round(filt_f, 2)
                        self._update_alt_avg()
                        self.last_rangefinder_time = time.time()
            except Exception:
                mav_conn = None
                time.sleep(1.0)

    def state_callback(self, msg):
        global current_telemetry
        current_telemetry['connected'] = msg.connected
        current_telemetry['is_armed'] = msg.armed
        current_telemetry['mode'] = msg.mode
        if msg.connected:
            self.last_any_data_time = time.time()

        # Auto-configure stream rates on first successful connection
        if msg.connected and not self._stream_rates_configured:
            self._stream_rates_configured = True
            self.get_logger().info('[GCS] FCU Connected! Mengkonfigurasi SR0 stream rates...')
            threading.Thread(target=self._configure_stream_rates, daemon=True).start()

    def _configure_stream_rates(self):
        """
        Kirim REQUEST_DATA_STREAM via MAVROS service.
        """
        import time
        time.sleep(3.0)  # tunggu MAVROS selesai setup

        if not self.stream_rate_cli.wait_for_service(timeout_sec=5.0):
            self.get_logger().warn('[GCS] MAVROS StreamRate service tidak tersedia.')
            return

        # Request data stream rates
        streams = [
            (2, 2),   # STREAM_EXTENDED_STATUS = BATTERY
            (10, 4),  # STREAM_EXTRA1 = ATTITUDE
            (11, 2),  # STREAM_EXTRA2 = VFR_HUD
            (12, 2),   # STREAM_EXTRA3 = RANGEFINDER / HWSTATUS
            (6, 2),   # STREAM_POSITION = GPS
            (1, 1),   # STREAM_RAW_SENSORS = IMU
            (3, 1),   # STREAM_RC_CHANNELS = RC
        ]

        self.get_logger().info('[GCS] Mengirim REQUEST_DATA_STREAM via MAVROS...')
        for stream_id, rate in streams:
            req = StreamRate.Request()
            req.stream_id = stream_id
            req.message_rate = rate
            req.on_off = True

            try:
                future = self.stream_rate_cli.call_async(req)
                time.sleep(0.2)
            except Exception as e:
                self.get_logger().error(f'[GCS] Error calling stream_rate: {e}')

        self.get_logger().info('[GCS] REQUEST_DATA_STREAM terkirim! Data drone sekarang mengalir.')

        # Configure ArduPilot speed parameters for high-speed flight
        try:
            if self.param_set_cli.wait_for_service(timeout_sec=2.0):
                # Set SR0_EXTRA3 to 2 (Rangefinder stream)
                req_ex3 = ParamSet.Request()
                req_ex3.param_id = 'SR0_EXTRA3'
                req_ex3.value.integer = 2
                req_ex3.value.real = 0.0
                self.param_set_cli.call_async(req_ex3)

                # Set WPNAV_SPEED to 150 cm/s (1.5 m/s) — fixed cruise speed
                req_spd = ParamSet.Request()
                req_spd.param_id = 'WPNAV_SPEED'
                req_spd.value.integer = 0
                req_spd.value.real = 150.0  # 1.5 m/s
                self.param_set_cli.call_async(req_spd)

                # Set WPNAV_ACCEL to 500 (5 m/s^2)
                req_acc = ParamSet.Request()
                req_acc.param_id = 'WPNAV_ACCEL'
                req_acc.value.integer = 0
                req_acc.value.real = 500.0
                self.param_set_cli.call_async(req_acc)

                # Set LAND_SPEED to 150 (1.5 m/s touchdown landing speed)
                req_land_spd = ParamSet.Request()
                req_land_spd.param_id = 'LAND_SPEED'
                req_land_spd.value.integer = 0
                req_land_spd.value.real = 150.0
                self.param_set_cli.call_async(req_land_spd)

                self.get_logger().info('[GCS] ArduPilot flight params configured: WPNAV_SPEED = 1.5m/s, WPNAV_ACCEL = 5m/s^2, LAND_SPEED = 1.5m/s')
            else:
                self.get_logger().warn('[GCS] MAVROS ParamSet service tidak tersedia.')
        except Exception as e:
            self.get_logger().error(f'[GCS] Gagal menetapkan parameter terbang: {e}')


    def local_pos_callback(self, msg):
        global current_telemetry
        self.local_x = msg.pose.position.x
        self.local_y = msg.pose.position.y
        self.local_z = msg.pose.position.z
        self.last_local_pos_time = time.time()
        self.last_any_data_time = time.time()

        # Extract ENU yaw from quaternion for navigation (same as real drone)
        # MAVROS outputs orientation in ENU. self.current_yaw_rad tracks this,
        # NOT current_telemetry['yaw'] which is negated for compass display.
        q = msg.pose.orientation
        _, _, yaw = self.quaternion_to_euler([q.w, q.x, q.y, q.z])
        self.current_yaw_rad = yaw

        # Map Gazebo local_z directly to alt_rear (ALT R) & alt ONLY (do NOT fill RANGE F)
        current_telemetry['alt_rear'] = round(self.local_z, 2)
        current_telemetry['alt'] = round(self.local_z, 2)
        current_telemetry['connected'] = True

    def local_vel_callback(self, msg):
        global current_telemetry
        vx = msg.twist.linear.x
        vy = msg.twist.linear.y
        vz = msg.twist.linear.z
        if math.isnan(vx) or math.isinf(vx): vx = 0.0
        if math.isnan(vy) or math.isinf(vy): vy = 0.0
        if math.isnan(vz) or math.isinf(vz): vz = 0.0
        speed = math.sqrt(vx**2 + vy**2 + vz**2)
        filtered_speed = self.filt_speed.filter(speed)
        current_telemetry['speed'] = round(filtered_speed, 2)

    def gps_callback(self, msg):
        global current_telemetry
        lat = msg.latitude
        lng = msg.longitude
        alt = msg.altitude
        if math.isnan(lat) or math.isinf(lat): lat = 0.0
        if math.isnan(lng) or math.isinf(lng): lng = 0.0
        if math.isnan(alt) or math.isinf(alt): alt = 0.0

        current_telemetry['lat'] = lat
        current_telemetry['lng'] = lng
        filtered_alt_abs = self.filt_alt_abs.filter(alt)
        current_telemetry['alt_abs'] = round(filtered_alt_abs, 2)
        if self.ref_lat is None and msg.status.status >= 0 and lat != 0.0 and lng != 0.0:
            self.ref_lat = lat
            self.ref_lon = lng
            self.ref_alt = alt
        current_telemetry['connected'] = True
        self.last_any_data_time = time.time()

    def battery_callback(self, msg):
        global current_telemetry
        raw_voltage = msg.voltage if not (math.isnan(msg.voltage) or math.isinf(msg.voltage)) else 0.0
        pct = msg.percentage
        if raw_voltage > 0.0:
            voltage = self.filt_voltage.filter(raw_voltage)
        else:
            voltage = 0.0
        current_telemetry['voltage_battery'] = round(voltage, 2)
        if pct > 0.0 and not math.isnan(pct):
            current_telemetry['battery_remaining'] = int(pct * 100)
        elif voltage > 0.0:
            # Hitung persentase baterai 4S berdasarkan tegangan (maksimal 16.8V)
            calc_pct = int(min(100.0, max(0.0, (voltage / 16.8) * 100.0)))
            current_telemetry['battery_remaining'] = calc_pct
        else:
            current_telemetry['battery_remaining'] = 0
        current_telemetry['connected'] = True
        self.last_any_data_time = time.time()

    def vfr_hud_callback(self, msg):
        """VFR_HUD raw data: altitude (Baro QGC), speed, heading (dengan HDG Offset dari UI)."""
        global current_telemetry
        raw_hdg = msg.heading if not math.isnan(msg.heading) else 0.0
        offset = current_telemetry.get('heading_offset', 0.0)
        speed = msg.groundspeed if not math.isnan(msg.groundspeed) else 0.0
        filtered_speed = self.filt_speed.filter(speed)
        current_telemetry['speed'] = round(filtered_speed, 2)
        current_telemetry['heading'] = round((raw_hdg + offset) % 360.0, 1)

        # Relative altitude calculation (if VFR_HUD is emitting MSL, subtract ref_alt)
        alt = msg.altitude if not math.isnan(msg.altitude) else 0.0
        if getattr(self, 'ref_alt', None) is not None and alt > 100.0 and self.ref_alt > 100.0:
            alt = alt - self.ref_alt
        filtered_alt = self.filt_alt.filter(alt)
        current_telemetry['alt'] = round(filtered_alt, 2)
        current_telemetry['connected'] = True
        self.last_any_data_time = time.time()

    def imu_callback(self, msg):
        """IMU raw data: Roll, Pitch, Yaw in degrees matching drone orientation 1:1."""
        global current_telemetry
        q = [msg.orientation.w, msg.orientation.x, msg.orientation.y, msg.orientation.z]
        if any(math.isnan(val) or math.isinf(val) for val in q):
            return
        roll_rad, pitch_rad, yaw_rad = self.quaternion_to_euler(q)
        roll_deg = math.degrees(roll_rad)
        pitch_deg = math.degrees(pitch_rad)
        yaw_deg = math.degrees(yaw_rad)

        filt_r = self.filt_roll.filter(roll_deg)
        filt_p = self.filt_pitch.filter(pitch_deg)
        filt_y = self.filt_yaw.filter(yaw_deg)

        current_telemetry['roll'] = round(filt_r, 2)
        current_telemetry['pitch'] = round(filt_p, 2)
        current_telemetry['yaw'] = round(filt_y, 2)
        current_telemetry['connected'] = True
        self.last_any_data_time = time.time()
        if current_telemetry.get('heading', 0.0) == 0.0:
            current_telemetry['heading'] = round((90.0 - math.degrees(filt_y)) % 360.0, 1)

    def _update_alt_avg(self):
        global current_telemetry
        rf_f = current_telemetry.get('alt_front', 0.0)
        rf_r = current_telemetry.get('alt_rear', 0.0)
        if rf_f > 0.0 and rf_r > 0.0:
            raw_avg = (rf_f + rf_r) / 2.0
        elif rf_f > 0.0:
            raw_avg = rf_f
        elif rf_r > 0.0:
            raw_avg = rf_r
        else:
            return
        filtered_alt = self.filt_alt.filter(raw_avg)
        current_telemetry['alt'] = round(filtered_alt, 2)

    def rangefinder_callback(self, msg):
        """RANGEFINDER Primary (RANGE F) Callback."""
        global current_telemetry
        if not is_valid_range(msg):
            return
        distance = msg.range
        frame = (msg.header.frame_id or "").lower()
        self.get_logger().info(f"[RANGE F] Recv dist={distance:.2f}m, frame={frame}")
        filtered_front = self.filt_alt_front.filter(distance)
        current_telemetry['alt_front'] = round(filtered_front, 2)

        self._update_alt_avg()
        current_telemetry['connected'] = True
        self.last_any_data_time = time.time()
        self.last_rangefinder_time = time.time()

    def altitudefinder_callback(self, msg):
        """ALTITUDEFINDER Secondary (ALT R) Callback."""
        global current_telemetry
        if not is_valid_range(msg):
            return
        distance = msg.range
        frame = (msg.header.frame_id or "").lower()
        self.get_logger().info(f"[ALT R] Recv dist={distance:.2f}m, frame={frame}")
        filtered_rear = self.filt_alt_rear.filter(distance)
        current_telemetry['alt_rear'] = round(filtered_rear, 2)

        self._update_alt_avg()
        current_telemetry['connected'] = True
        self.last_any_data_time = time.time()
        self.last_rangefinder_time = time.time()

    def quaternion_to_euler(self, q):
        try:
            w, x, y, z = q[0], q[1], q[2], q[3]
            if any(math.isnan(val) or math.isinf(val) for val in [w, x, y, z]):
                return 0.0, 0.0, 0.0
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

            if any(math.isnan(val) or math.isinf(val) for val in [roll, pitch, yaw]):
                return 0.0, 0.0, 0.0
            return roll, pitch, yaw
        except Exception:
            return 0.0, 0.0, 0.0

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

    def front_cam_callback(self, msg):
        global _last_front_process
        now = time.time()
        self.last_front_cam_time = now
        if now - _last_front_process < CAMERA_PROCESS_INTERVAL:
            return
        _last_front_process = now
        try:
            cv_img = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            _, buffer = cv2.imencode('.jpg', cv_img, [cv2.IMWRITE_JPEG_QUALITY, 75])
            with frame_lock:
                latest_frames['front'] = buffer.tobytes()
                latest_frame_versions['front'] += 1
        except Exception as e:
            self.get_logger().error(f"Error in front_cam_callback: {e}")

    def bottom_cam_callback(self, msg):
        global _last_bottom_process
        now = time.time()
        self.last_bottom_cam_time = now
        if now - _last_bottom_process < CAMERA_PROCESS_INTERVAL:
            return
        _last_bottom_process = now
        try:
            cv_img = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # --- DETEKSI ARUCO UNTUK SIMULASI ---
            # Cari marker di frame bawah
            h, w = cv_img.shape[:2]
            cx, cy = w // 2, h // 2
            corners, ids = detect_aruco_sim(cv_img)
            if ids is not None and len(ids) > 0:
                import numpy as np
                marker_id = int(ids[0][0])
                marker_corners = corners[0][0]
                mc_x = int(np.mean(marker_corners[:, 0]))
                mc_y = int(np.mean(marker_corners[:, 1]))
                dx = mc_x - cx
                dy = cy - mc_y
                dz = float(np.max(marker_corners[:, 0]) - np.min(marker_corners[:, 0]))

                # Publish ke /krti/aruco_data
                aruco_msg = String()
                aruco_msg.data = json.dumps({
                    'id': marker_id,
                    'wp': f"WP{marker_id}",
                    'x': float(dx),
                    'y': float(dy),
                    'z': float(dz)
                })
                self.aruco_pub.publish(aruco_msg)

                # Overlay deteksi ke frame feed
                cv2.aruco.drawDetectedMarkers(cv_img, corners, ids)
                cv2.circle(cv_img, (mc_x, mc_y), 6, (0, 0, 255), -1)
                cv2.putText(cv_img, f"SIM DETECT: ID {marker_id}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            _, buffer = cv2.imencode('.jpg', cv_img, [cv2.IMWRITE_JPEG_QUALITY, 75])
            with frame_lock:
                latest_frames['bottom'] = buffer.tobytes()
                latest_frame_versions['bottom'] += 1
        except Exception as e:
            self.get_logger().error(f"Error in bottom_cam_callback: {e}")

    def status_topic_callback(self, msg):
        socketio.emit('status_msg', {'type': 'info', 'text': msg.data})

    def statustext_callback(self, msg):
        alert_type = 'info'
        if msg.severity in [0, 1, 2, 3]:
            alert_type = 'error'
        elif msg.severity == 4:
            alert_type = 'warning'
        self.get_logger().info(f"[APM Status] {msg.text} (severity={msg.severity})")
        socketio.emit('status_msg', {'type': alert_type, 'text': f"[APM] {msg.text}"})

    def set_mode(self, mode_str):
        req = SetMode.Request()
        req.custom_mode = mode_str
        self.set_mode_cli.call_async(req)

    def arm(self, state=True):
        req = CommandBool.Request()
        req.value = state
        self.arm_cli.call_async(req)

    def takeoff(self, altitude):
        req = CommandTOL.Request()
        req.altitude = float(altitude)
        req.latitude = current_telemetry.get('lat', 0.0)
        req.longitude = current_telemetry.get('lng', 0.0)
        self.takeoff_cli.call_async(req)

    def land(self):
        self.set_mode("LAND")

    def emergency_cut(self):
        self.get_logger().warn("[GCS] EMERGENCY CUTOFF TRIGGERED! Terminating flight...")
        self.arm(False)
        
        # Command MAV_CMD_DO_FLIGHTTERMINATION (ID 185)
        req_kill1 = CommandLong.Request()
        req_kill1.broadcast = False
        req_kill1.command = 185  # MAV_CMD_DO_FLIGHTTERMINATION
        req_kill1.confirmation = 0
        req_kill1.param1 = 1.0  # Terminate immediately
        self.command_cli.call_async(req_kill1)

        # Command MAV_CMD_COMPONENT_ARM_DISARM (ID 400 Force Disarm)
        req_kill2 = CommandLong.Request()
        req_kill2.broadcast = False
        req_kill2.command = 400  # MAV_CMD_COMPONENT_ARM_DISARM
        req_kill2.confirmation = 0
        req_kill2.param1 = 0.0  # Disarm
        req_kill2.param2 = 21196.0  # Magic Force Disarm Key
        self.command_cli.call_async(req_kill2)

    def guided_timer_callback(self):
        if not self.guided_active:
            return

        now_t = self.get_clock().now().nanoseconds / 1e9

        # Force GUIDED mode if guided is active and drone is not in GUIDED
        current_mode = current_telemetry.get('mode')
        if current_telemetry.get('connected') and current_mode and current_mode != 'GUIDED':
            # Throttle the mode change request to once every 20 cycles (1 second)
            if not hasattr(self, '_last_mode_req_time'):
                self._last_mode_req_time = 0
            now_ms = self.get_clock().now().nanoseconds / 1e6
            if now_ms - self._last_mode_req_time > 1000:
                self._last_mode_req_time = now_ms
                self.get_logger().info(f"[GCS] Forcing mode to GUIDED (current mode: {current_mode})...")
                self.set_mode("GUIDED")

            # If we are not waiting for a ground takeoff command, sync target_position to avoid running ahead
            if self.pending_takeoff_alt is None:
                self.target_position = [self.local_x, self.local_y, self.local_z]
                self.setpoint_velocity = [0.0, 0.0, 0.0]

        if self.pending_takeoff_alt is not None:
            if current_mode == 'GUIDED':
                alt = self.pending_takeoff_alt
                self.pending_takeoff_alt = None
                self._takeoff_start_t = now_t
                if not current_telemetry.get('is_armed', False):
                    self.get_logger().info("[GCS] Arming vehicle for takeoff...")
                    self.arm(True)
                self.get_logger().info(f"[GCS] Sending Takeoff command to {alt:.1f}m...")
                self.takeoff(alt)
                return
            else:
                if not hasattr(self, '_last_mode_req_time'): self._last_mode_req_time = 0
                now_ms = now_t * 1000.0
                if now_ms - self._last_mode_req_time > 500:
                    self._last_mode_req_time = now_ms
                    self.get_logger().info("[GCS] Target takeoff altitude set. Triggering GUIDED mode launch.")

    def wp_reached_callback(self, msg):
        global current_telemetry
        current_telemetry['current_wp_index'] = msg.wp_seq
        self.get_logger().info(f"[GCS] Waypoint MAVROS Reached: SEQ #{msg.wp_seq}")
        socketio.emit('krti_wp_update', {'wp': msg.wp_seq})

    def push_native_auto_mission(self, mission_array):
        global current_telemetry
        if not mission_array or len(mission_array) == 0:
            self.get_logger().warn("[GCS] Mission array empty, cancelling push to CUAV.")
            return False

        if self.ref_lat is None or self.ref_lat == 0.0:
            cur_lat = current_telemetry.get('lat', 0.0) or -6.876078
            cur_lng = current_telemetry.get('lng', 0.0) or 107.621487
            self.ref_lat = cur_lat
            self.ref_lon = cur_lng

        waypoints_list = []

        # Waypoint 0 (Home / Current Launch Ref)
        wp0 = Waypoint()
        wp0.frame = Waypoint.FRAME_GLOBAL_REL_ALT
        wp0.command = 16  # MAV_CMD_NAV_WAYPOINT
        wp0.is_current = True
        wp0.autocontinue = True
        wp0.x_lat = float(self.ref_lat)
        wp0.y_long = float(self.ref_lon)
        wp0.z_alt = 0.0
        waypoints_list.append(wp0)

        cruise_speed = 3.0

        # Waypoints 1..N
        for idx, item in enumerate(mission_array):
            wp_type = str(item.get('type', 'waypoint')).lower()
            lat_val = float(item.get('lat', 0.0) or self.ref_lat)
            lng_val = float(item.get('lng', 0.0) or self.ref_lon)
            alt_val = float(item.get('alt', 3.0) or 3.0)
            spd_val = float(item.get('speed', 3.0) or 3.0)

            if spd_val > 0.5:
                cruise_speed = spd_val

            wp = Waypoint()
            wp.frame = Waypoint.FRAME_GLOBAL_REL_ALT
            wp.autocontinue = True
            wp.x_lat = lat_val
            wp.y_long = lng_val

            if wp_type == 'takeoff' or (idx == 0 and self.local_z < 0.5):
                wp.command = 22  # MAV_CMD_NAV_TAKEOFF
                wp.param1 = 0.0
                wp.param4 = 0.0
                wp.z_alt = max(alt_val, 2.5)  # Minimum 2.5m takeoff altitude
            elif wp_type == 'landing':
                wp.command = 21  # MAV_CMD_NAV_LAND
                wp.param1 = 0.0
                wp.z_alt = 0.0
            else:
                wp.command = 16  # MAV_CMD_NAV_WAYPOINT
                wp.param1 = 0.0  # hold time
                wp.param2 = 1.0  # accept radius 1.0m
                wp.z_alt = alt_val

            waypoints_list.append(wp)

        # Clear existing mission first
        if self.wp_clear_cli.wait_for_service(timeout_sec=0.5):
            req_clear = WaypointClear.Request()
            self.wp_clear_cli.call_async(req_clear)
            time.sleep(0.1)

        # Push waypoints to FCU EEPROM/RAM
        if self.wp_push_cli.wait_for_service(timeout_sec=1.0):
            req_push = WaypointPush.Request()
            req_push.start_index = 0
            req_push.waypoints = waypoints_list
            self.wp_push_cli.call_async(req_push)
            self.get_logger().info(f"[GCS] Pushing {len(waypoints_list)} Native Mission Items to FCU CUAV EEPROM...")

        # Configure ArduPilot FCU Speed & Acceleration Parameters
        h_spd_cms = max(cruise_speed * 100.0, 100.0)
        v_up_cms = 250.0
        v_dn_cms = 150.0
        accel_cms = 250.0

        try:
            if self.param_set_cli.wait_for_service(timeout_sec=0.3):
                req_h = ParamSet.Request()
                req_h.param_id = 'WPNAV_SPEED'
                req_h.value.integer = 0
                req_h.value.real = h_spd_cms
                self.param_set_cli.call_async(req_h)

                req_acc = ParamSet.Request()
                req_acc.param_id = 'WPNAV_ACCEL'
                req_acc.value.integer = 0
                req_acc.value.real = accel_cms
                self.param_set_cli.call_async(req_acc)

                req_up = ParamSet.Request()
                req_up.param_id = 'PILOT_SPEED_UP'
                req_up.value.integer = 0
                req_up.value.real = v_up_cms
                self.param_set_cli.call_async(req_up)

                req_dn = ParamSet.Request()
                req_dn.param_id = 'PILOT_SPEED_DN'
                req_dn.value.integer = 0
                req_dn.value.real = v_dn_cms
                self.param_set_cli.call_async(req_dn)

                self.get_logger().info(
                    f"[GCS] CUAV Native FCU flight params set -> "
                    f"CRUISE: {h_spd_cms/100:.1f}m/s | ACCEL: {accel_cms/100:.1f}m/s² | "
                    f"CLIMB: {v_up_cms/100:.1f}m/s | DESCENT: {v_dn_cms/100:.1f}m/s"
                )
        except Exception as e:
            self.get_logger().error(f"[GCS] Failed to set FCU speed params: {e}")

        self.auto_mission_active = True
        self.guided_active = False  # Disable 20Hz GUIDED streaming — 100% Native CUAV Execution!

        if not current_telemetry.get('is_armed', False):
            self.get_logger().info("[GCS] Arming vehicle for Native AUTO launch...")
            self.arm(True)

        time.sleep(0.2)
        self.get_logger().info("[GCS] Switching mode to AUTO (100% Native CUAV Flight Controller Execution)...")
        self.set_mode("AUTO")
        return True

        if self.is_taking_off:
            now_t = self.get_clock().now().nanoseconds / 1e9
            if not hasattr(self, '_takeoff_start_t'):
                self._takeoff_start_t = now_t
            target_alt = self.final_target_position[2] if (hasattr(self, 'final_target_position') and len(self.final_target_position) > 2) else 3.0
            alt_reached = (self.local_z >= (target_alt - 0.8))
            takeoff_timeout = (now_t - self._takeoff_start_t) > 6.0

            if alt_reached or takeoff_timeout:
                self.is_taking_off = False
                self.target_position = [self.local_x, self.local_y, self.local_z]
                self.get_logger().info(f"[GCS] Takeoff selesai (alt={self.local_z:.2f}m, target={target_alt:.1f}m)! Advancing ke WP2...")
                if getattr(self, 'auto_mission_active', False):
                    self.current_auto_wp_index += 1
                    self.start_next_auto_waypoint()
                return
            else:
                return

        now_t = self.get_clock().now().nanoseconds / 1e9

        # PHASE 1: ALTITUDE ALIGNMENT FIRST (Station-keep XY, adjust Z)
        if getattr(self, 'is_climbing_to_wp_alt', False):
            target_z = self.final_target_position[2]
            alt_err = abs(target_z - self.local_z)
            if not hasattr(self, '_alt_start_t') or self._alt_start_t is None:
                self._alt_start_t = now_t
            alt_timeout = (now_t - self._alt_start_t) > 4.0

            if alt_err < 0.35 or alt_timeout:
                self.is_climbing_to_wp_alt = False
                self._yaw_start_t = now_t
                self.get_logger().info(f"[GCS] Phase 1 Alt Reached ({self.local_z:.2f}m -> target {target_z:.1f}m). Proceeding to Phase 2 Yaw Alignment.")
            else:
                if hasattr(self, 'segment_start_pos') and self.segment_start_pos is not None:
                    self.target_position[0] = self.segment_start_pos[0]
                    self.target_position[1] = self.segment_start_pos[1]
                self.target_position[2] = target_z

        # PHASE 2: YAW ORIENTATION ALIGNMENT — rotate on spot toward TRANSIT BEARING (straight to target WP)
        elif getattr(self, 'is_yawing_to_target', False):
            # Use ENU yaw from quaternion — same source as real drone, never negated compass yaw
            current_yaw = self.current_yaw_rad
            # Use phase2_yaw (transit bearing) — NOT target_yaw (which is the arrival heading post-WP)
            phase2_target = getattr(self, 'phase2_yaw', self.target_yaw)
            yaw_err = math.atan2(math.sin(phase2_target - current_yaw), math.cos(phase2_target - current_yaw))
            if not hasattr(self, '_yaw_start_t') or self._yaw_start_t is None:
                self._yaw_start_t = now_t
            yaw_timeout = (now_t - self._yaw_start_t) > 4.0

            # Command the transit bearing yaw DURING Phase 2
            self.target_yaw = phase2_target

            if abs(yaw_err) < 0.15 or yaw_timeout:  # ~8.5 deg alignment or 4s timeout
                self.is_yawing_to_target = False
                self.get_logger().info(f"[GCS] Phase 2 Yaw Aligned to transit bearing (err={math.degrees(yaw_err):.1f}°). Proceeding to Phase 3 Forward Transit!")
            else:
                if hasattr(self, 'segment_start_pos') and self.segment_start_pos is not None:
                    self.target_position[0] = self.segment_start_pos[0]
                    self.target_position[1] = self.segment_start_pos[1]
                self.target_position[2] = self.final_target_position[2]

        # PHASE 3: FORWARD TRANSIT ALONG PATH
        elif not self.use_velocity_control:
            # Set target position directly to final waypoint destination for smooth ArduPilot WPNAV execution
            self.target_position[0] = self.final_target_position[0]
            self.target_position[1] = self.final_target_position[1]
            self.target_position[2] = self.final_target_position[2]
            # LOCK yaw to transit bearing during flight — prevents drift from yaw fighting position controller
            self.target_yaw = getattr(self, 'transit_yaw', self.target_yaw)

            if getattr(self, 'auto_mission_active', False):
                real_dx = self.final_target_position[0] - self.local_x
                real_dy = self.final_target_position[1] - self.local_y
                real_dz = self.final_target_position[2] - self.local_z

                real_dist_2d = math.sqrt(real_dx*real_dx + real_dy*real_dy)

                # Guard against index out of range after last WP completes
                if self.current_auto_wp_index >= len(self.auto_mission_array):
                    self.auto_mission_active = False
                    return

                wp_type = self.auto_mission_array[self.current_auto_wp_index].get('type')

                # Debounce guard: prevent re-triggering within 1.5s
                if not hasattr(self, '_last_wp_advance_t'): self._last_wp_advance_t = 0
                now_sec = self.get_clock().now().nanoseconds / 1e9

                if not hasattr(self, '_wp_leg_start_t') or self._wp_leg_start_t is None:
                    self._wp_leg_start_t = now_sec

                if (now_sec - self._last_wp_advance_t) >= 1.5:
                    alt_reached = (abs(real_dz) < 0.5)
                    pos_reached = (real_dist_2d < 0.8)
                    safety_timeout = (now_sec - self._wp_leg_start_t) >= 60.0

                    if wp_type == 'landing':
                        is_reached = (real_dist_2d < 0.8 and alt_reached) or safety_timeout
                    elif wp_type == 'takeoff':
                        is_reached = False
                    else:
                        is_reached = (pos_reached and alt_reached) or safety_timeout

                    if is_reached:
                        self._last_wp_advance_t = now_sec
                        self._wp_leg_start_t = now_sec
                        self.get_logger().info(f"[GCS] WP {self.current_auto_wp_index} REACHED! (pos={real_dist_2d:.2f}m, alt_err={real_dz:.2f}m)")
                        current_wp = self.auto_mission_array[self.current_auto_wp_index]

                        # If this WP has an explicit target_heading, rotate to it NOW (on arrival) before advancing
                        if 'target_heading' in current_wp or 'heading' in current_wp:
                            hdg_deg = float(current_wp.get('target_heading', current_wp.get('heading', 0.0)))
                            arrival_yaw = math.atan2(math.sin(math.radians(90.0 - hdg_deg)), math.cos(math.radians(90.0 - hdg_deg)))
                            self.target_yaw = arrival_yaw
                            self.phase2_yaw = arrival_yaw
                            self.get_logger().info(f"[GCS] WP arrived — rotating to target_heading {hdg_deg:.1f}° before next WP")

                        # Apply WP target heading if present
                        if 'target_heading' in current_wp or 'heading' in current_wp:
                            hdg_deg = float(current_wp.get('target_heading', current_wp.get('heading', 0.0)))
                            target_enu_yaw = math.atan2(math.sin(math.radians(90.0 - hdg_deg)), math.cos(math.radians(90.0 - hdg_deg)))
                            self.target_yaw = target_enu_yaw

                        payload_cmd = current_wp.get('payload')
                        if payload_cmd == 'ON' or payload_cmd == 'SERVO_8S':
                            self.get_logger().info("[GCS] Waypoint Payload Active! Membuka Servo (8 detik)...")
                            servo_data_open = {'servo_id': 1, 'action': 'open', 'angle': 0}
                            msg_open = String()
                            msg_open.data = json.dumps(servo_data_open)
                            self.servo_pub.publish(msg_open)
                            socketio.emit('pi_servo_command', servo_data_open)

                            def close_servo_task():
                                time.sleep(8)
                                self.get_logger().info("[GCS] 8 Detik selesai. Menutup Servo...")
                                servo_data_close = {'servo_id': 1, 'action': 'close', 'angle': 90}
                                msg_close = String()
                                msg_close.data = json.dumps(servo_data_close)
                                self.servo_pub.publish(msg_close)
                                socketio.emit('pi_servo_command', servo_data_close)

                            threading.Thread(target=close_servo_task, daemon=True).start()

                        if wp_type == 'landing':
                            self.get_logger().info("[GCS] Waypoint Landing Tercapai. Melakukan Auto Land.")
                            self.guided_active = False
                            self.land()
                            self.auto_mission_active = False
                        else:
                            self.current_auto_wp_index += 1
                            self.start_next_auto_waypoint()

        if self.use_velocity_control:
            msg = TwistStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.twist.linear.x = self.target_velocity_cmd[0]
            msg.twist.linear.y = self.target_velocity_cmd[1]
            msg.twist.linear.z = self.target_velocity_cmd[2]
            self.vel_setpoint_pub.publish(msg)
        else:
            # PositionTarget via /mavros/setpoint_raw/local
            # IMPORTANT: MAVROS internally converts ENU→NED before sending to ArduPilot.
            # We must supply ENU values here (x=East, y=North, z=Up, yaw=ENU angle).
            # DO NOT manually convert — that would double-convert and crash the drone.
            POSITION_MASK = (
                PositionTarget.IGNORE_VX | PositionTarget.IGNORE_VY | PositionTarget.IGNORE_VZ |
                PositionTarget.IGNORE_AFX | PositionTarget.IGNORE_AFY | PositionTarget.IGNORE_AFZ |
                PositionTarget.IGNORE_YAW_RATE
            )
            pt = PositionTarget()
            pt.header.stamp = self.get_clock().now().to_msg()
            pt.header.frame_id = 'map'
            pt.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
            pt.type_mask = POSITION_MASK
            # ENU values — MAVROS converts these to NED internally:
            pt.position.x = float(self.target_position[0])  # East
            pt.position.y = float(self.target_position[1])  # North
            pt.position.z = float(self.target_position[2])  # Up (MAVROS negates for NED Down)
            pt.yaw = float(self.target_yaw)                 # ENU yaw (MAVROS converts to NED yaw)

            if not hasattr(self, '_last_pub_t'): self._last_pub_t = 0.0
            if now_t - self._last_pub_t >= 0.05:  # 20Hz
                self.pos_raw_pub.publish(pt)
                self._last_pub_t = now_t

    def telemetry_broadcast_callback(self):
        global current_telemetry
        # Jika tidak ada data dari FCU selama 5 detik, set connected=False
        if self.last_any_data_time > 0 and (time.time() - self.last_any_data_time) > 5.0:
            current_telemetry['connected'] = False
        # Sanitize current_telemetry to prevent nan/inf JSON serialization errors
        sanitized = {}
        for k, v in current_telemetry.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                sanitized[k] = 0.0
            elif isinstance(v, int) and (math.isnan(v) or math.isinf(v)):
                sanitized[k] = 0
            else:
                sanitized[k] = v
        socketio.emit('telemetry_data', sanitized)

        now = time.time()
        global pi_wifi_rssi_val
        front_connected = latest_camera_status['front'].get('connected', False)
        bottom_connected = latest_camera_status['bottom'].get('connected', False)
        if not front_connected and self.last_front_cam_time is not None:
            front_connected = (now - self.last_front_cam_time) < 2.0
        if not bottom_connected and self.last_bottom_cam_time is not None:
            bottom_connected = (now - self.last_bottom_cam_time) < 2.0

        front_rssi = latest_camera_status['front'].get('rssi', pi_wifi_rssi_val if front_connected else -100)
        bottom_rssi = latest_camera_status['bottom'].get('rssi', pi_wifi_rssi_val if bottom_connected else -100)

        socketio.emit('camera_status', {'camera': 'front', 'connected': front_connected, 'rssi': front_rssi})
        socketio.emit('camera_status', {'camera': 'bottom', 'connected': bottom_connected, 'rssi': bottom_rssi})

    def start_next_auto_waypoint(self):
        global current_telemetry
        if not self.auto_mission_active:
            return
        if self.current_auto_wp_index >= len(self.auto_mission_array):
            self.auto_mission_active = False
            self.get_logger().info("[GCS] Misi Otonom Selesai.")
            return

        wp = self.auto_mission_array[self.current_auto_wp_index]
        wp_type = wp.get('type')

        # Check if drone is already in the air when takeoff command is received
        is_on_ground = self.local_z < 0.5
        if wp_type == 'takeoff' and not is_on_ground:
            self.get_logger().info("[GCS] Drone sudah di udara. Melewati perintah Takeoff dan langsung menuju waypoint berikutnya.")
            self.current_auto_wp_index += 1
            if self.current_auto_wp_index < len(self.auto_mission_array):
                self.start_next_auto_waypoint()
            else:
                self.auto_mission_active = False
            return

        try:
            lat_raw = wp.get('lat')
            lng_raw = wp.get('lng')
            alt_raw = wp.get('alt')
            speed_raw = wp.get('speed')

            lat = float(lat_raw) if lat_raw is not None and str(lat_raw).strip() != "" else (self.ref_lat or 0.0)
            lng = float(lng_raw) if lng_raw is not None and str(lng_raw).strip() != "" else (self.ref_lon or 0.0)
            # alt_raw=0 is treated as 'not set' → fallback to 3.0 for takeoff, 5.0 for others
            if alt_raw is not None and str(alt_raw).strip() != "" and float(alt_raw) > 0:
                alt_rel = float(alt_raw)
            else:
                alt_rel = 3.0 if wp_type == 'takeoff' else (0.0 if wp_type == 'landing' else 3.0)

            # Takeoff altitude MUST be at least 2.5m so vehicle actually takes off into the air!
            if wp_type == 'takeoff' and alt_rel < 1.0:
                alt_rel = 3.0
            speed = float(speed_raw) if speed_raw is not None and str(speed_raw).strip() != "" and float(speed_raw) > 0 else 3.0
        except Exception as err:
            self.get_logger().error(f"[GCS] Error parsing waypoint data: {err}")
            lat = self.ref_lat or 0.0
            lng = self.ref_lon or 0.0
            alt_rel = 3.0
            speed = 3.0

        self.get_logger().info(
            f"[GCS] PARSED WP{wp.get('wp')} ({wp_type}) → "
            f"alt_raw={alt_raw!r} → alt_rel={alt_rel:.2f}m | "
            f"speed_raw={speed_raw!r} → speed={speed:.2f}m/s | "
            f"local_x={wp.get('local_x')!r}, local_y={wp.get('local_y')!r}"
        )

        # Handle landing transit behavior:
        # Drone flies to landing coordinate at cruise alt, then lands vertically on the spot
        if wp_type == 'landing':
            if speed <= 0.1:
                speed = 2.5  # Default safe transit speed to landing spot
            z = self.prev_target_position[2] if hasattr(self, 'prev_target_position') and self.prev_target_position is not None else alt_rel
        else:
            z = alt_rel

        # Fixed cruise speed: 1.5 m/s for all waypoints
        v_up_cms   = 150.0  # 1.5 m/s climb rate
        v_dn_cms   = 150.0  # 1.5 m/s descent rate
        h_spd_cms  = 150.0  # 1.5 m/s horizontal cruise speed (fixed)

        try:
            if self.param_set_cli.wait_for_service(timeout_sec=0.3):
                # Horizontal cruise speed (user-defined per WP)
                req_h = ParamSet.Request()
                req_h.param_id = 'WPNAV_SPEED'
                req_h.value.integer = 0
                req_h.value.real = h_spd_cms
                self.param_set_cli.call_async(req_h)

                # GUIDED mode climb rate
                req_up = ParamSet.Request()
                req_up.param_id = 'PILOT_SPEED_UP'
                req_up.value.integer = 0
                req_up.value.real = v_up_cms
                self.param_set_cli.call_async(req_up)

                # GUIDED mode descent rate
                req_dn = ParamSet.Request()
                req_dn.param_id = 'PILOT_SPEED_DN'
                req_dn.value.integer = 0
                req_dn.value.real = v_dn_cms
                self.param_set_cli.call_async(req_dn)

                self.get_logger().info(
                    f"[GCS] ArduPilot GUIDED speed params set -> "
                    f"CRUISE: {h_spd_cms/100:.1f}m/s | "
                    f"CLIMB: {v_up_cms/100:.1f}m/s (PILOT_SPEED_UP) | "
                    f"DESCENT: {v_dn_cms/100:.1f}m/s (PILOT_SPEED_DN)"
                )
        except Exception as e:
            self.get_logger().error(f'[GCS] Failed to set speed params: {e}')
            
        # Emit to UI
        socketio.emit('krti_wp_update', {
            'wp': wp.get('wp'),
            'name': wp.get('name'),
            'type': wp_type
        })

        # Compute ENU target position:
        # Prioritize GPS (lat, lng) conversion relative to Home reference GPS (ref_lat, ref_lon).
        # This makes KRTI Mode and Auto Waypoint Mode 100% identical in flight execution!
        local_x_raw = wp.get('local_x')
        local_y_raw = wp.get('local_y')
        if lat != 0.0 and lng != 0.0 and self.ref_lat is not None and self.ref_lon is not None and self.ref_lat != 0.0:
            dist_h, bearing_h = haversine_distance_and_bearing(self.ref_lat, self.ref_lon, lat, lng)
            x = dist_h * math.sin(bearing_h)   # ENU East from Home
            y = dist_h * math.cos(bearing_h)   # ENU North from Home
        elif local_x_raw is not None and local_y_raw is not None:
            if self.current_auto_wp_index == 0 or not hasattr(self, 'mission_origin_x'):
                self.mission_origin_x = self.local_x
                self.mission_origin_y = self.local_y
            x = self.mission_origin_x + float(local_x_raw)
            y = self.mission_origin_y + float(local_y_raw)
        else:
            x = self.local_x
            y = self.local_y

        self.final_target_position = [x, y, z]

        # Determine exact leg start position (prev WP coordinate if available, eliminating cumulative drift)
        if self.current_auto_wp_index > 0 and hasattr(self, 'prev_target_position'):
            start_x = self.prev_target_position[0]
            start_y = self.prev_target_position[1]
        else:
            start_x = self.local_x
            start_y = self.local_y

        self.segment_start_pos = [start_x, start_y, z]
        self.target_position = [start_x, start_y, z]
        self.prev_target_position = [x, y, z]

        dy = y - start_y
        dx = x - start_x
        dist = math.sqrt(dx*dx + dy*dy)
        self.expected_leg_time = max((dist / max(speed, 1.0)) + 6.0, 8.0)
        self._wp_leg_start_t = self.get_clock().now().nanoseconds / 1e9

        # TRANSIT YAW: bearing straight to the target WP — locked during Phase 3 flight (prevents drift)
        if dist > 0.5:
            self.transit_yaw = math.atan2(dy, dx)  # ENU: atan2(North, East)
        else:
            self.transit_yaw = getattr(self, 'target_yaw', 0.0)  # keep last heading for very short legs

        # ARRIVAL YAW: explicit heading to execute ON SPOT once drone ARRIVES at this WP
        # This is the heading the drone will rotate to (Phase 2) at the START of the NEXT leg,
        # i.e., after arriving at this WP and before flying to the following WP.
        if 'target_heading' in wp or 'heading' in wp:
            hdg_deg = float(wp.get('target_heading', wp.get('heading', 0.0)))
            self.target_yaw = math.atan2(math.sin(math.radians(90.0 - hdg_deg)), math.cos(math.radians(90.0 - hdg_deg)))
        else:
            # No explicit heading: yaw for NEXT leg will be set by that leg's start_next_auto_waypoint call
            self.target_yaw = self.transit_yaw

        # Phase 2 yaw: the drone must point toward the transit bearing (atan2 to target WP) BEFORE flying.
        # This is independent of target_heading (which takes effect AFTER arrival).
        self.phase2_yaw = self.transit_yaw

        # 3-Phase Sequential Execution Setup:
        # Phase 1: Check if altitude adjustment is needed first
        alt_diff = abs(z - self.local_z)
        if alt_diff > 0.4:
            self.is_climbing_to_wp_alt = True
            self._alt_start_t = self.get_clock().now().nanoseconds / 1e9
        else:
            self.is_climbing_to_wp_alt = False

        # Phase 2: Always yaw toward TRANSIT bearing (straight to target WP) before flying
        if dist > 0.3:
            self.is_yawing_to_target = True
            self._yaw_start_t = None
        else:
            self.is_yawing_to_target = False

        self.max_speed = speed
        self.use_velocity_control = False
        self.guided_active = True

        current_telemetry['current_wp_index'] = self.current_auto_wp_index + 1

        self.get_logger().info(
            f"[GCS] WP{wp.get('wp')} ({wp_type.upper()}) -> "
            f"Target: ({x:.2f}m, {y:.2f}m, {z:.2f}m) | "
            f"Current alt: {self.local_z:.2f}m | "
            f"Alt delta: {z - self.local_z:+.2f}m | "
            f"Speed: {speed:.1f}m/s"
        )

        # Automatically trigger arming and takeoff if on the ground on the first waypoint
        if wp_type == 'takeoff' or (self.current_auto_wp_index == 0 and is_on_ground):
            self.target_position = [self.local_x, self.local_y, self.local_z]
            self.final_target_position = [self.local_x, self.local_y, alt_rel]
            self.setpoint_velocity = [0.0, 0.0, 0.0]
            self.is_taking_off = True
            self.pending_takeoff_alt = alt_rel
            if not current_telemetry.get('is_armed', False):
                self.arm(True)
            self.set_mode("GUIDED")

@socketio.on('manual_action')
def handle_manual_action(data):
    if ros_node_instance is None: return
    if isinstance(data, dict):
        action_name = data.get('action')
        alt = float(data.get('alt', 2.5))
        speed = float(data.get('speed', 4.0))
    else:
        action_name = data
        alt = 2.5
        speed = 4.0

    if action_name in ['disarm', 'land', 'takeoff']:
        ros_node_instance.auto_mission_active = False

    if action_name == 'arm':
        ros_node_instance.arm(True)
        socketio.emit('upload_status', {'status': 'success', 'message': 'Sending ARM command'})
    elif action_name == 'disarm':
        ros_node_instance.guided_active = False
        ros_node_instance.emergency_cut()
        socketio.emit('upload_status', {'status': 'success', 'message': 'Sending EMERGENCY CUT command'})
    elif action_name == 'land':
        ros_node_instance.guided_active = False
        ros_node_instance.land()
        socketio.emit('upload_status', {'status': 'success', 'message': 'Sending Landing command'})
    elif action_name == 'hold':
        ros_node_instance.guided_active = False
        ros_node_instance.set_mode("LOITER")
        socketio.emit('upload_status', {'status': 'success', 'message': 'Sending HOLD / LOITER command'})
    elif action_name == 'takeoff':
        if ros_node_instance.local_z > 0.5:
            # Drone is already in the air (e.g. aborting landing)
            ros_node_instance.target_position = [ros_node_instance.local_x, ros_node_instance.local_y, ros_node_instance.local_z]
            ros_node_instance.final_target_position = [ros_node_instance.local_x, ros_node_instance.local_y, alt]
            ros_node_instance.target_yaw = current_telemetry.get('yaw', 0.0)
            ros_node_instance.is_yawing_to_target = False
            ros_node_instance.max_speed = speed
            ros_node_instance.use_velocity_control = False
            ros_node_instance.is_taking_off = False
            ros_node_instance.pending_takeoff_alt = None
            ros_node_instance.guided_active = True
            ros_node_instance.set_mode("GUIDED")
            socketio.emit('upload_status', {'status': 'success', 'message': f'Go-around: Climbing back to {alt}m'})
        else:
            # Drone is on the ground, standard takeoff
            ros_node_instance.target_position = [ros_node_instance.local_x, ros_node_instance.local_y, ros_node_instance.local_z]
            ros_node_instance.final_target_position = [ros_node_instance.local_x, ros_node_instance.local_y, alt]
            ros_node_instance.target_yaw = current_telemetry.get('yaw', 0.0)
            ros_node_instance.is_yawing_to_target = False
            ros_node_instance.max_speed = speed
            ros_node_instance.use_velocity_control = False
            ros_node_instance.is_taking_off = True
            ros_node_instance.pending_takeoff_alt = alt
            ros_node_instance.guided_active = True
            ros_node_instance.set_mode("GUIDED")
            socketio.emit('upload_status', {'status': 'success', 'message': 'Activating GUIDED mode & Taking off'})

@socketio.on('set_manual_target')
def handle_manual_target(data):
    if ros_node_instance is None: return
    try:
        lat = float(data['lat'])
        lng = float(data['lng'])
        alt_rel = float(data['alt'])
        speed = float(data.get('speed', 4.0))

        # Set WPNAV_SPEED in ArduPilot (cm/s)
        try:
            if ros_node_instance.param_set_cli.wait_for_service(timeout_sec=0.2):
                req_spd = ParamSet.Request()
                req_spd.param_id = 'WPNAV_SPEED'
                req_spd.value.integer = 0
                req_spd.value.real = float(speed * 100.0)
                ros_node_instance.param_set_cli.call_async(req_spd)
        except Exception as e:
            ros_node_instance.get_logger().error(f'[GCS] Failed to set WPNAV_SPEED: {e}')

        if ros_node_instance.ref_lat is None:
            socketio.emit('upload_status', {'status': 'error', 'message': 'GPS home not yet detected'})
            return

        if ros_node_instance.ref_lat is not None and ros_node_instance.ref_lon is not None and ros_node_instance.ref_lat != 0.0:
            dist_h, bearing_h = haversine_distance_and_bearing(ros_node_instance.ref_lat, ros_node_instance.ref_lon, lat, lng)
            x = dist_h * math.sin(bearing_h)
            y = dist_h * math.cos(bearing_h)
        else:
            x = ros_node_instance.local_x
            y = ros_node_instance.local_y
        z = alt_rel

        ros_node_instance.target_position = [ros_node_instance.local_x, ros_node_instance.local_y, ros_node_instance.local_z]
        ros_node_instance.final_target_position = [x, y, z]

        dy = y - ros_node_instance.local_y
        dx = x - ros_node_instance.local_x
        ros_node_instance.target_yaw = math.atan2(dy, dx)

        ros_node_instance.is_yawing_to_target = True
        ros_node_instance.max_speed = speed
        ros_node_instance.use_velocity_control = False
        ros_node_instance.guided_active = True
        ros_node_instance.auto_mission_active = False

        ros_node_instance.set_mode("GUIDED")
        socketio.emit('upload_status', {'status': 'success', 'message': 'Manual position command sent'})
    except Exception as e:
        pass

@socketio.on('force_hold_loiter')
def handle_force_hold():
    if ros_node_instance is None: return
    ros_node_instance.guided_active = False
    ros_node_instance.set_mode("LOITER")
    socketio.emit('upload_status', {'status': 'success', 'message': 'Changing mode to LOITER'})

@socketio.on('change_flight_mode')
def handle_change_flight_mode(data):
    if ros_node_instance is None: return
    mode = data.get('mode')
    ros_node_instance.get_logger().info(f"[GCS] Requesting flight mode: {mode}")
    ros_node_instance.set_mode(mode)

def start_auto_mission_execution():
    if ros_node_instance is None: return
    if len(ros_node_instance.auto_mission_array) > 0:
        ros_node_instance.get_logger().info("[GCS] Executing 100% Native CUAV AUTO Mission...")
        ros_node_instance.push_native_auto_mission(ros_node_instance.auto_mission_array)

@socketio.on('transmit_auto_mission')
def handle_transmit_auto_mission(data):
    if ros_node_instance is None: return

    ros_node_instance.auto_mission_array = data
    ros_node_instance.current_auto_wp_index = 0
    ros_node_instance.get_logger().info(f"[GCS] Mission published with {len(data)} waypoints. Starting execution...")
    socketio.emit('upload_status', {'status': 'success', 'message': 'Mission Uploaded! Auto-Arming & Launching...'})
    start_auto_mission_execution()

@socketio.on('krti_command')
def handle_krti_command(data):
    if ros_node_instance is None: return
    action = data.get('action')
    if action == 'start_auto':
        msg = String()
        msg.data = 'START_AUTO'
        ros_node_instance.gcs_cmd_pub.publish(msg)
        start_auto_mission_execution()
            
    elif action == 'stop_auto':
        msg = String()
        msg.data = 'STOP_AUTO'
        ros_node_instance.gcs_cmd_pub.publish(msg)
        ros_node_instance.auto_mission_active = False
        ros_node_instance.guided_active = False
        ros_node_instance.set_mode("LOITER")
    elif action == 'landing':
        ros_node_instance.guided_active = False
        ros_node_instance.auto_mission_active = False
        ros_node_instance.land()
    elif action == 'cutoff':
        ros_node_instance.guided_active = False
        ros_node_instance.auto_mission_active = False
        ros_node_instance.emergency_cut()

@socketio.on('trigger_servo')
def handle_trigger_servo(data):
    # 1. Broadcast langsung ke Pi via Socket.IO (selalu jalan bahkan jika FCU/MAVROS belum terhubung)
    socketio.emit('pi_servo_command', data)
    
    # 2. Publish ke topik ROS2 jika ros_node_instance aktif
    if ros_node_instance is not None:
        try:
            msg = String()
            msg.data = json.dumps(data)
            ros_node_instance.servo_pub.publish(msg)
        except Exception as e:
            pass

@socketio.on('pi_camera_status')
def handle_pi_camera_status(data):
    camera_id = data.get('camera')
    if camera_id not in ('front', 'bottom'):
        return

    connected = bool(data.get('connected', True))
    rssi = data.get('rssi', pi_wifi_rssi_val if connected else -100)
    with frame_lock:
        latest_camera_status[camera_id] = {'connected': connected, 'rssi': rssi}
    socketio.emit('camera_status', {'camera': camera_id, 'connected': connected, 'rssi': rssi})


@socketio.on('pi_camera_feed')
def handle_pi_camera_feed(data):
    camera_id = data.get('camera')
    img_b64 = data.get('image')
    if not camera_id or not img_b64:
        return

    try:
        jpeg_bytes = base64.b64decode(img_b64)
        if len(jpeg_bytes) < 100:
            return

        with frame_lock:
            latest_frames[camera_id] = jpeg_bytes
            latest_frame_versions[camera_id] = latest_frame_versions.get(camera_id, 0) + 1
            latest_camera_status[camera_id] = {'connected': True, 'rssi': latest_camera_status.get(camera_id, {}).get('rssi', pi_wifi_rssi_val)}

        now = time.time()
        if ros_node_instance is not None:
            if camera_id == 'front':
                ros_node_instance.last_front_cam_time = now
            elif camera_id == 'bottom':
                ros_node_instance.last_bottom_cam_time = now
    except Exception as e:
        print(f"[!] Failed to decode Pi camera frame for {camera_id}: {e}")

@socketio.on('aruco_target_centered')
def handle_aruco_target_centered(data):
    """Broadcast data ArUco Centered dari Pi ke pi_servo_node.py dan Web GCS UI."""
    socketio.emit('aruco_target_centered', data)
    if ros_node_instance is not None:
        try:
            msg = String()
            msg.data = json.dumps(data)
            ros_node_instance.aruco_pub.publish(msg)
        except Exception:
            pass

@socketio.on('pi_servo_status')
def handle_pi_servo_status(data):
    """Broadcast status servo dari Pi ke Web GCS UI."""
    socketio.emit('servo_status_update', data)

@socketio.on('aruco_target_stable')
def handle_aruco_target_stable(data):
    """Terima deteksi ArUco stabil dari Raspberry Pi dan forward ke topik ROS2."""
    socketio.emit('aruco_target_stable', data)
    if ros_node_instance is None: return
    msg = String()
    msg.data = json.dumps(data)
    ros_node_instance.aruco_pub.publish(msg)

@socketio.on('pi_wifi_status')
def handle_pi_wifi_status(data):
    """Terima status RSSI WiFi dari Pi dan broadcast ke semua klien GCS."""
    global pi_wifi_rssi_val
    rssi = data.get('rssi', -100)
    pi_wifi_rssi_val = rssi
    socketio.emit('pi_wifi_rssi', {'rssi': rssi})

@socketio.on('gate_detected')
def handle_gate_detected(data):
    """Terima data deteksi gawang dari Pi dan broadcast ke client GCS."""
    socketio.emit('gate_status', data)

@socketio.on('aruco_detected')
def handle_aruco_detected(data):
    """Terima data deteksi ArUco dari Pi dan broadcast ke client GCS."""
    socketio.emit('aruco_status', data)

@socketio.on('red_object_detected')
def handle_red_object_detected(data):
    """Terima deteksi objek merah dari Raspberry Pi, forward ke topik ROS2, dan broadcast ke GCS UI."""
    socketio.emit('red_object_status', data)
    if ros_node_instance is None: return
    msg = String()
    msg.data = json.dumps(data)
    ros_node_instance.red_object_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    flask_thread = threading.Thread(target=lambda: socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True))
    flask_thread.daemon = True
    flask_thread.start()

    node = ROS2GCSBridgeNode()
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
