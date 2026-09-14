#!/usr/bin/env python3
"""
RASPI_debug/debug_raspi_servos.py — Test Servo 1 & Servo 2 SG90 (pigpio Hardware PWM)
"""
import sys
import time
import json
import urllib.request
import urllib.parse

BOLD = '\033[1m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def test_servo_http(servo_id, action):
    url = f"http://127.0.0.1:5000/test_servo"
    payload = json.dumps({'servo_id': servo_id, 'action': action, 'angle': 0 if action == 'open' else 90}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"  ├─ {GREEN}Servo {servo_id} {action.upper()} -> Server Response: {data}{RESET}")
            return True
    except Exception as e:
        print(f"  ├─ {RED}Failed triggering Servo {servo_id} {action.upper()} via HTTP: {e}{RESET}")
        return False

def debug_raspi_servos():
    print(f"\n{CYAN}{BOLD}━━━ RASPBERRY PI SG90 SERVO DEBUGGER (PIGPIO HARDWARE PWM) ━━━{RESET}")
    print("Transmitting test commands to GCS Server...")

    print(f"\n1. Testing Servo 1 (GPIO 12 - Hardware PWM0)...")
    test_servo_http(1, 'open')
    time.sleep(1.0)
    test_servo_http(1, 'close')

    print(f"\n2. Testing Servo 2 (GPIO 19 - Hardware PWM1)...")
    test_servo_http(2, 'open')
    time.sleep(1.0)
    test_servo_http(2, 'close')

    print("\n  ----------------------------------------")
    print(f"  {CYAN}Pi Hardware Servo Pinout Reference:{RESET}")
    print(f"  - Servo 1: GPIO12 (BCM Pin 12, PWM0)")
    print(f"  - Servo 2: GPIO19 (BCM Pin 19, PWM1)")
    print(f"  - Action OPEN  = Pulse 500µs (0° Angle)")
    print(f"  - Action CLOSE = Pulse 1500µs (90° Angle)")

if __name__ == '__main__':
    debug_raspi_servos()
