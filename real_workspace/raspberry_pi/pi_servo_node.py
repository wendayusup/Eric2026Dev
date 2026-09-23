#!/usr/bin/env python3
"""
pi_servo_node.py — ERIC 2026 VTOL | Single Servo Node (OPEN/CLOSE on Pin 12)

Mode Servo Tunggal (Single Servo):
  - Servo terhubung ke GPIO 12 (Physical Pin 32, PWM0).
  - Posisi OPEN = 0° (650us pulse width)
  - Posisi CLOSE = 90° (1500us pulse width)
  - Menggunakan pigpio DMA Hardware PWM untuk stabilitas tinggi tanpa jitter.

SETUP DI RASPBERRY PI:
    sudo apt install pigpio python3-pigpio -y
    sudo systemctl enable pigpiod
    sudo systemctl start pigpiod
"""

import time
import socket
import subprocess
import threading

# ─── Configuration ─────────────────────────────────────────────────────────

LAPTOP_IP = "10.190.143.76"  # Default fallback IP GCS Laptop
GCS_URL = f"http://{LAPTOP_IP}:5000"

SERVO1_PIN = 12  # GPIO12 (PWM0, Physical Pin 32)

# Position values
SERVO1_CLOSE = 90  # Posisi Fisik Menutup / Terkunci (1500us)
SERVO1_OPEN  = 0   # Posisi Fisik Membuka / Rilis (650us)

INVERT_SERVO1 = False
    
# Kalibrasi Lebar Pulsa (Microseconds)
# SG90/MG90S: 0° = 650us (mencegah stall), 90° = 1500us
SERVO1_PULSE_0  = 650
SERVO1_PULSE_90 = 1500

# State tracking (1: servo_id -> current_angle)
current_servo_state = {
    1: None
}

_last_known_gcs_ip = None

def _mdns_lookup_with_timeout(hostname: str, timeout: float = 1.5):
    result = {'ip': None}
    def _resolve():
        try:
            result['ip'] = socket.gethostbyname(hostname)
        except Exception:
            result['ip'] = None
    t = threading.Thread(target=_resolve, daemon=True)
    t.start()
    t.join(timeout)
    return result['ip']

def find_gcs_ip():
    global _last_known_gcs_ip

    if _last_known_gcs_ip:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        if sock.connect_ex((_last_known_gcs_ip, 5000)) == 0:
            sock.close()
            print(f"[+] Servo Node: GCS found via cache: {_last_known_gcs_ip}")
            return _last_known_gcs_ip
        sock.close()

    try:
        output = subprocess.check_output(["ip", "neigh", "show"]).decode('utf-8')
        for line in output.splitlines():
            if "FAILED" not in line and ("REACHABLE" in line or "DELAY" in line or "STALE" in line):
                parts = line.split()
                if len(parts) > 0:
                    ip = parts[0]
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.2)
                    if sock.connect_ex((ip, 5000)) == 0:
                        sock.close()
                        print(f"[+] Servo Node: GCS found via ARP table: {ip}")
                        return ip
                    sock.close()
    except Exception as e:
        print(f"[-] Servo Node: Failed to read ARP table: {e}")

    ip = _mdns_lookup_with_timeout("f15.local", timeout=1.5)
    return ip if ip else LAPTOP_IP

# ─── Driver Hardware Init ──────────────────────────────────────────────────
DRIVER = 'mock'
GPIO_AVAILABLE = False
pi = None
servo1 = None

try:
    import pigpio
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("pigpiod tidak jalan (jalankan: sudo systemctl start pigpiod)")
    pi.set_mode(SERVO1_PIN, pigpio.OUTPUT)
    DRIVER = 'pigpio'
    GPIO_AVAILABLE = True
    print("[+] Servo Node: pigpio connected — using Hardware-Timed PWM on GPIO 12.")
except Exception as e:
    print(f"[!] Servo Node: pigpio tidak tersedia ({e}), coba fallback ke RPi.GPIO...")
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(SERVO1_PIN, GPIO.OUT)
        servo1 = GPIO.PWM(SERVO1_PIN, 50)
        servo1.start(0)
        DRIVER = 'rpigpio'
        GPIO_AVAILABLE = True
        print("[+] Servo Node: RPi.GPIO terhubung — pakai software PWM pada GPIO 12.")
    except Exception as e2:
        print(f"[!] Servo Node: RPi.GPIO juga tidak tersedia ({e2}).")


def _angle_to_pulsewidth_us(pin_num: int, angle: int) -> int:
    """Konversi sudut ke pulsewidth (us) dengan kalibrasi per-servo."""
    angle = max(0, min(180, int(angle)))
    pw_0  = SERVO1_PULSE_0
    pw_90 = SERVO1_PULSE_90

    if angle == 0:
        return pw_0
    elif angle == 90:
        return pw_90
    else:
        return int(pw_0 + (angle / 90.0) * (pw_90 - pw_0))


def set_servo_angle_direct(pin_num: int, angle: int):
    """Set pulsewidth kontinyu ke driver pigpio DMA / RPi.GPIO."""
    angle = max(0, min(180, int(angle)))
    pulsewidth = _angle_to_pulsewidth_us(pin_num, angle)

    if DRIVER == 'pigpio' and pi is not None:
        try:
            pi.set_servo_pulsewidth(SERVO1_PIN, pulsewidth)
            print(f"[+] (pigpio DMA PWM) Pin {SERVO1_PIN} -> {angle}° (PW: {pulsewidth}us)")
        except Exception as e:
            print(f"[!] Gagal pigpio pin {SERVO1_PIN}: {e}")

    elif DRIVER == 'rpigpio':
        duty = (pulsewidth / 20000.0) * 100.0
        try:
            if servo1:
                servo1.ChangeDutyCycle(duty)
                print(f"[+] (RPi.GPIO) Pin {SERVO1_PIN} -> {angle}° (Duty: {duty:.2f}%)")
        except Exception as e:
            print(f"[!] Gagal RPi.GPIO pin {SERVO1_PIN}: {e}")
    else:
        print(f"[MOCK] Pin {SERVO1_PIN} -> {angle}° (pulsewidth: {pulsewidth}us)")


def init_servos_to_close():
    print("[*] Initializing Single Servo (Pin 12) to LOCKED/CLOSE position (90°)...")
    set_servo_angle_direct(SERVO1_PIN, SERVO1_CLOSE)
    current_servo_state[1] = SERVO1_CLOSE


def cleanup_servos():
    global pi, GPIO, servo1
    if DRIVER == 'pigpio' and pi is not None:
        try:
            pi.set_servo_pulsewidth(SERVO1_PIN, 0)
            pi.stop()
        except Exception as e:
            print(f"[!] Gagal membersihkan pigpio: {e}")
    elif DRIVER == 'rpigpio' and GPIO is not None:
        try:
            if servo1 is not None:
                servo1.stop()
            GPIO.cleanup()
        except Exception as e:
            print(f"[!] Gagal membersihkan GPIO servo: {e}")


# ─── Socket.IO Client Setup ────────────────────────────────────────────────

try:
    import socketio
except ImportError:
    print("[!] Error: python-socketio tidak ditemukan! Jalankan: pip install python-socketio websocket-client")

sio = socketio.Client()

@sio.event
def connect():
    print("[+] Servo Node: Successfully connected to GCS Laptop Server!")

@sio.event
def disconnect():
    print("[-] Servo Node: Terputus dari GCS Laptop Server.")


# Marker WP2 Drop ID (ArUco ID 2 = Waypoint 2 Payload Drop)
WP2_ARUCO_ID = 2

# Latch flag supaya trigger ArUco WP2 HANYA BERAKSI 1 KALI saja per-misi (mencegah multi-drop)
wp2_auto_triggered = False

# Latch flag terpisah untuk Black Object & Red Box drop
black_drop_triggered = False
red_drop_triggered = False

def reset_wp2_trigger():
    global wp2_auto_triggered
    wp2_auto_triggered = False
    print("[*] Latch Trigger ArUco WP2 di-reset.")

def reset_red_trigger():
    global red_drop_triggered
    red_drop_triggered = False
    print("[*] Latch Trigger Red Box di-reset.")

def reset_black_trigger():
    global black_drop_triggered
    black_drop_triggered = False
    print("[*] Latch Trigger Black Object di-reset.")

def trigger_8s_payload_drop(source: str = 'unknown'):
    """Fungsi Otonom 8-Detik Payload Drop Single Servo (Pin 12):
    Membuka Servo (GPIO 12) ke 0° (650us), tahan 8 detik,
    lalu menutup kembali Servo ke 90° (1500us).
    `source`: label string untuk log ('aruco_wp2' / 'black_object' / 'red_box' / 'manual')
    """
    def _routine():
        print(f"[*] [SINGLE SERVO DROP] Sumber: '{source}' — MEMBUKA Servo (Pin 12) ke 0° (650us) selama 8 detik...")
        set_servo_angle_direct(SERVO1_PIN, SERVO1_OPEN)
        current_servo_state[1] = SERVO1_OPEN

        try:
            sio.emit('pi_servo_status', {
                'state': 'OPEN_8S',
                'source': source,
                'msg': f'Servo Membuka (8s Drop Active — sumber: {source})'
            })
        except Exception:
            pass

        time.sleep(8.0)

        print(f"[*] [SINGLE SERVO DROP] 8 Detik Selesai! MENUTUP Kembali Servo ke 90° (1500us)...")
        set_servo_angle_direct(SERVO1_PIN, SERVO1_CLOSE)
        current_servo_state[1] = SERVO1_CLOSE

        try:
            sio.emit('pi_servo_status', {
                'state': 'CLOSED',
                'source': source,
                'msg': f'Servo Menutup (Drop Complete — sumber: {source})'
            })
        except Exception:
            pass

        # Reset latch otomatis setelah 2 detik cooldown
        time.sleep(2.0)
        if source == 'aruco_wp2':
            reset_wp2_trigger()
        elif source == 'black_object':
            reset_black_trigger()
        elif source == 'red_box':
            reset_red_trigger()
        else:
            reset_wp2_trigger()
            reset_black_trigger()
            reset_red_trigger()

    threading.Thread(target=_routine, daemon=True).start()


def _resolve_target_angle(servo_id: int, data: dict):
    close_val = SERVO1_CLOSE
    open_val  = SERVO1_OPEN

    action = data.get('action')
    if action is not None:
        action_str = str(action).strip().lower()
        if action_str in ('open', 'buka', 'on', 'true', '1'):
            return open_val
        if action_str in ('close', 'tutup', 'off', 'false', '0'):
            return close_val
        if action_str in ('servo_8s', 'open_8s', 'drop_8s', 'on_8s'):
            trigger_8s_payload_drop()
            return None

    if 'angle' in data:
        try:
            raw_angle = int(data.get('angle', 0))
            return max(0, min(180, raw_angle))
        except Exception:
            print(f"[!] Servo Node: angle tidak valid: {data.get('angle')}")
            return None

    print(f"[!] Servo Node: payload tidak punya 'action' atau 'angle' yang valid: {data}")
    return None


# ─── JALUR PERINTAH 1: DARI WEB GCS / TELEMETRI LAPTOP ────────────────────────
@sio.on('pi_servo_command')
def handle_pi_servo_command(data):
    servo_id = 1
    target_angle = _resolve_target_angle(servo_id, data)
    if target_angle is None:
        return

    close_val = SERVO1_CLOSE
    open_val  = SERVO1_OPEN
    invert = INVERT_SERVO1

    cmd_label = "OPEN" if target_angle == open_val else "CLOSE"
    angle_to_send = target_angle
    if invert:
        angle_to_send = close_val if target_angle == open_val else open_val

    print(f"[*] Perintah Servo (Web/Tele): Pin 12 -> {cmd_label} (Target: {target_angle}°, Fisik: {angle_to_send}°)")
    
    current_servo_state[1] = target_angle
    set_servo_angle_direct(SERVO1_PIN, angle_to_send)


# ─── JALUR PERINTAH 2: DETEKSI LANGSUNG PRESISI KAMERA PI (ARUCO WP2 CENTERED)
@sio.on('aruco_target_centered')
def handle_aruco_target_centered(data):
    """Trigger servo dari ArUco WP2 — PRESISI: drone harus tepat di atas marker."""
    global wp2_auto_triggered
    try:
        marker_id = int(data.get('marker_id', 0))
        dx = data.get('x', 999)
        dy = data.get('y', 999)

        # Hanya rilis jika ArUco WP2 (ID 2), belum pernah dipicu, dan posisi presisi tepat di tengah (error <= 25px)
        if marker_id == WP2_ARUCO_ID and not wp2_auto_triggered and abs(dx) <= 25 and abs(dy) <= 25:
            wp2_auto_triggered = True
            print(f"[*] [ARUCO WP2 PRECISION TRIGGER] Drone TEPAT DI ATAS WP2! (DX:{dx}, DY:{dy}) — Membuka Servo Pin 12 (8 Detik)...")
            trigger_8s_payload_drop(source='aruco_wp2')
    except Exception as e:
        print(f"[!] Error handle_aruco_target_centered: {e}")


# ─── JALUR PERINTAH 3: DETEKSI OBJEK HITAM — GRAYSCALE BOTTOM CAMERA
@sio.on('black_object_detected')
def handle_black_object_detected(data):
    """Trigger servo dari Objek Hitam — Kamera Bottom Grayscale terarah ke target hitam."""
    global black_drop_triggered
    try:
        in_frame = data.get('in_frame', False)
        centered = data.get('centered', False)

        if in_frame and centered and not black_drop_triggered:
            black_drop_triggered = True
            print(f"[*] [BLACK OBJECT TRIGGER] Objek hitam terdeteksi dan terarah! — Membuka Servo Pin 12 (8 Detik)...")
            trigger_8s_payload_drop(source='black_object')
    except Exception as e:
        print(f"[!] Error handle_black_object_detected: {e}")


# ─── JALUR PERINTAH 4: DETEKSI RED BOX — NON-PRESISI (KAMERA CUKUP MENGARAH)
@sio.on('red_object_detected')
def handle_red_object_detected(data):
    """Trigger servo dari Red Box — NON-PRESISI: cukup kamera mengarah ke area merah.
    Threshold lebih longgar (80px). Tidak perlu drone presisi di atas marker.
    """
    global red_drop_triggered
    try:
        in_frame = data.get('in_frame', False)
        centered = data.get('centered', False)  # True = dalam 80px dari center kamera

        if in_frame and centered and not red_drop_triggered:
            red_drop_triggered = True
            print(f"[*] [RED BOX NON-PRECISION TRIGGER] Red Box terdeteksi dalam frame dan terarah! — Membuka Servo Pin 12 (8 Detik)...")
            trigger_8s_payload_drop(source='red_box')
    except Exception as e:
        print(f"[!] Error handle_red_object_detected: {e}")


@sio.on('reset_wp2_latch')
def handle_reset_wp2_latch(data=None):
    reset_wp2_trigger()


@sio.on('reset_black_latch')
def handle_reset_black_latch(data=None):
    reset_black_trigger()


@sio.on('reset_red_latch')
def handle_reset_red_latch(data=None):
    reset_red_trigger()


# ─── LOCAL IPC (UDP SERVER 127.0.0.1:9999) UNTUK OTONOM INDEPENDEN TANPA WIFI ───
LOCAL_UDP_PORT = 9999

def start_local_udp_server():
    """Server UDP lokal 127.0.0.1 agar pi_cam_node dapat men-trigger servo secara langsung
    tanpa memerlukan koneksi Wi-Fi / Socket.IO ke Laptop GCS."""
    def _udp_worker():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', LOCAL_UDP_PORT))
            print(f"[+] Servo Node: Localhost UDP server ACTIVE on 127.0.0.1:{LOCAL_UDP_PORT} (Otonom tanpa Wi-Fi Ready!)", flush=True)
        except Exception as e:
            print(f"[!] Servo Node: Gagal bind localhost UDP server: {e}", flush=True)
            return

        import json
        while True:
            try:
                data, _ = sock.recvfrom(4096)
                if not data:
                    continue
                msg = json.loads(data.decode('utf-8'))
                event = msg.get('event')
                payload = msg.get('data', {})

                if event == 'aruco_target_centered':
                    handle_aruco_target_centered(payload)
                elif event == 'black_object_detected':
                    handle_black_object_detected(payload)
                elif event == 'red_object_detected':
                    handle_red_object_detected(payload)
                elif event == 'pi_servo_command':
                    handle_pi_servo_command(payload)
                elif event == 'reset_wp2_latch':
                    handle_reset_wp2_latch(payload)
                elif event == 'reset_black_latch':
                    handle_reset_black_latch(payload)
                elif event == 'reset_red_latch':
                    handle_reset_red_latch(payload)
            except Exception as e:
                time.sleep(0.01)

    t = threading.Thread(target=_udp_worker, daemon=True, name="local_udp_servo_listener")
    t.start()


if __name__ == '__main__':
    print("[*] FRESH STARTUP: Waiting 2 seconds for driver stabilization...", flush=True)
    time.sleep(2.0)
    init_servos_to_close()
    start_local_udp_server()
    print("[+] Servo Node READY! Single Servo on Pin 12 active.", flush=True)
    try:
        while True:
            if not sio.connected:
                try:
                    LAPTOP_IP = find_gcs_ip()
                    GCS_URL = f"http://{LAPTOP_IP}:5000"
                    print(f"[*] Servo Node: Contacting GCS Server at: {GCS_URL}")
                    sio.connect(GCS_URL)
                    _last_known_gcs_ip = LAPTOP_IP
                except Exception as e:
                    print(f"[-] Servo Node: Failed to connect to GCS: {e}")
                    time.sleep(3.0)
                    continue
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[-] Servo Node: Dihentikan.")
    finally:
        cleanup_servos()