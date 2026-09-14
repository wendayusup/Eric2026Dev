#!/usr/bin/env python3
import time
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Inisialisasi Servos (SG90) menggunakan RPi.GPIO
SERVO1_PIN = 12  # GPIO12 (PWM0)
SERVO2_PIN = 19  # GPIO19 (PWM1)

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SERVO1_PIN, GPIO.OUT)
    GPIO.setup(SERVO2_PIN, GPIO.OUT)

    servo1 = GPIO.PWM(SERVO1_PIN, 50)  # 50Hz
    servo2 = GPIO.PWM(SERVO2_PIN, 50)  # 50Hz
    servo1.start(0)
    servo2.start(0)
    print("[+] Servo Node: GPIO / Servos berhasil diinisialisasi pada BCM Pin 12 dan 13.")
except ImportError:
    print("[!] Servo Node: Modul RPi.GPIO tidak ditemukan. Menjalankan dalam mode MOCK.")
    GPIO = None
    servo1 = None
    servo2 = None

def set_servo_angle(servo_obj, pin_num, angle):
    if not servo_obj:
        print(f"[MOCK] Menggerakkan Servo pada Pin {pin_num} ke {angle} derajat.")
        return

    # Map sudut 0-180 ke duty cycle 2.5% - 12.5%
    duty = 2.5 + (angle / 18.0)
    servo_obj.ChangeDutyCycle(duty)
    time.sleep(0.3)
    servo_obj.ChangeDutyCycle(0)  # Matikan sinyal untuk mencegah jittering
    print(f"[+] Servo Pin {pin_num} digerakkan ke {angle} derajat.")


class ServoNode(Node):
    def __init__(self):
        super().__init__('krti_servo_node')
        self.subscription = self.create_subscription(
            String,
            '/krti/servo_command',
            self.command_callback,
            10)
        self.get_logger().info('ROS2 Native Servo Node telah berjalan. Menunggu perintah...')

    def command_callback(self, msg):
        try:
            data = json.loads(msg.data)
            servo_id = data.get('servo_id')
            angle = int(data.get('angle', 90))

            self.get_logger().info(f"Menerima perintah servo: ID {servo_id} -> {angle} derajat")

            if servo_id == 1:
                set_servo_angle(servo1, SERVO1_PIN, angle)
            elif servo_id == 2:
                set_servo_angle(servo2, SERVO2_PIN, angle)
            else:
                self.get_logger().warning(f"Servo ID {servo_id} tidak dikenal.")
        except Exception as e:
            self.get_logger().error(f"Gagal memparsing perintah JSON: {e}")

def main(args=None):
    rclpy.init(args=args)
    servo_node = ServoNode()

    try:
        rclpy.spin(servo_node)
    except KeyboardInterrupt:
        pass
    finally:
        servo_node.destroy_node()
        rclpy.shutdown()
        if GPIO:
            GPIO.cleanup()

if __name__ == '__main__':
    main()
