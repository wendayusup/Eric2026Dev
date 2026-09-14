#!/usr/bin/env python3
"""
pi_cam_node.py — KRTI 2026 VTOL | Raspberry Pi Camera Node
Perubahan dari versi sebelumnya:
  1. Grayscale conversion sebelum deteksi ArUco (akurasi & speed)
  2. Dictionary dipersempit ke DICT_7X7_50 saja (sesuai marker KRTI 2026)
  3. ArUcoFilter per-ID (tidak campur antar waypoint)
  4. marker_id ikut dikirim dalam event aruco_target_stable
  5. Prioritas marker: ID terkecil aktif (WP1 > WP2 > dst), bukan terdekat center
  6. Trailing space SSID 'discrete ' dibiarkan (sesuai aslinya), tapi diberi warning

Perbaikan (fix round):
  A. Race condition ThreadedCamera.isOpened() -> AttributeError saat cap masih None
     (thread streaming mati diam-diam, feed berhenti tanpa pesan error).
     Fix: isOpened() sekarang lock-protected + null-check, dan stream thread
     menunggu event 'ready' (frame pertama sukses) sebelum masuk loop utama.
  B. Kamera bottom/front bisa tertukar karena /dev/videoN tidak stabil urutannya
     saat reboot/replug. Fix: deteksi via /dev/v4l/by-id/ (stabil per device),
     dengan fallback ke metode index lama kalau ID belum di-set / tidak ditemukan.
  C. connect() dulu selalu emit status utk 'bottom' & 'front' meski salah satu
     belum/tidak terdeteksi -> GCS menampilkan box "connected" tanpa frame
     (efek blink). Fix: hanya emit status utk kamera yang benar-benar terdeteksi.
  D. Seluruh loop di camera_stream_thread dibungkus try/except supaya error
     apapun tidak mematikan thread secara permanen.
"""

import time
import threading
import subprocess
import cv2
import numpy as np
import socketio
import socket
import base64
import glob
import os
import json
from collections import deque

# ─── Localhost UDP IPC (Trigger Servo Otonom Tanpa Wi-Fi) ──────────────────────
LOCAL_SERVO_UDP_PORT = 9999
_udp_client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_local_servo_trigger(event: str, data: dict):
    """Kirim event langsung ke pi_servo_node via UDP localhost 127.0.0.1.
    Ini menjamin servo TERUJI dan TERBACA OTONOM tanpa butuh Wi-Fi sama sekali!"""
    try:
        msg = json.dumps({'event': event, 'data': data})
        _udp_client_sock.sendto(msg.encode('utf-8'), ('127.0.0.1', LOCAL_SERVO_UDP_PORT))
    except Exception:
        pass

# ─── Konfigurasi Global ───────────────────────────────────────────────────────

LAPTOP_IP       = "192.168.1.125"  # Default fallback untuk IP GCS Laptop
GCS_URL         = f"http://{LAPTOP_IP}:5000"
# [FIX E] Diturunkan dari 8.0 -> 3.0. wifi_watchdog.service (OS-level) sudah
# menangani reconnect WiFi sendiri; loop ini cukup jadi trigger cepat untuk
# memaksa Socket.IO reconnect begitu koneksi lama sudah pasti mati, bukan
# menambah antrian delay tersendiri di atas watchdog.
PING_TIMEOUT_SEC = 3.0

# Streaming adaptif: resolusi ringan 16:9 agar ultra-smooth dan bebas lag di Wi-Fi
STREAM_WIDTH    = 480
STREAM_HEIGHT   = 270
STREAM_FPS      = 12
JPEG_QUALITY    = 45
FRAME_INTERVAL  = 1.0 / STREAM_FPS

# Mode adaptive ultra-ringan untuk stabilitas jaringan Wi-Fi
ADAPTIVE_STREAM = True
STREAM_PROFILE_HIGH = {'width': 480, 'height': 270, 'fps': 12, 'quality': 45}
STREAM_PROFILE_MEDIUM = {'width': 400, 'height': 225, 'fps': 10, 'quality': 38}
STREAM_PROFILE_LOW = {'width': 320, 'height': 180, 'fps': 8, 'quality': 30}
CURRENT_STREAM_PROFILE = STREAM_PROFILE_HIGH

# Counter untuk menilai apakah koneksi web sedang berat
STREAM_FAILURES = 0
STREAM_FAILURE_THRESHOLD = 4

# Marker KRTI 2026: ArUco DICT_7X7_50, ID 1=WP1, 2=WP2, 3=WP3, 4=WP4
# Ukuran fisik marker 500mm (large) dan 100mm (small) — gunakan large untuk deteksi jauh
ARUCO_DICT_ID   = cv2.aruco.DICT_7X7_50
MARKER_SIZE_M   = 0.50   # 500mm marker besar untuk jarak jauh

# ─── Stable Camera Identity (fix B) ───────────────────────────────────────────
# Isi string ini dengan output dari: ls -la /dev/v4l/by-id/  di Raspberry Pi kamu.
# Contoh: "usb-046d_0825_ABCD1234-video-index0"
# Kalau dikosongkan (""), script otomatis fallback ke metode index lama
# (deteksi berurutan /dev/video0, /dev/video1, ...).
BOTTOM_CAM_BY_ID = ""   # <-- isi manual setelah cek by-id di Pi kamu
FRONT_CAM_BY_ID  = ""   # <-- isi manual setelah cek by-id di Pi kamu

# ─── Kalibrasi Kamera (Auto-Load camera_params.npz jika ada) ──────────────────

CALIB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_params.npz")
if os.path.exists(CALIB_FILE):
    try:
        data = np.load(CALIB_FILE)
        CAMERA_MATRIX = data['camera_matrix']
        DIST_COEFFS   = data['dist_coeffs']
        print(f"[+] Successfully loaded camera calibration from '{CALIB_FILE}':")
        print(f"    Camera Matrix:\n{CAMERA_MATRIX}")
        print(f"    Distortion:\n{DIST_COEFFS}")
    except Exception as e:
        print(f"[!] Failed to read '{CALIB_FILE}': {e}")
        CAMERA_MATRIX = None
        DIST_COEFFS   = None
else:
    CAMERA_MATRIX = None
    DIST_COEFFS   = None


# ─── Auto-Discovery GCS IP ────────────────────────────────────────────────────
# [FIX E] Cache IP terakhir yang berhasil + timeout keras pada mDNS.
# Alasan: setelah WiFi reconnect, ARP cache biasanya masih dingin (miss),
# lalu script jatuh ke gethostbyname("f15.local") yang TIDAK PUNYA TIMEOUT
# di versi lama -> bisa nge-hang beberapa detik tanpa batas jika avahi lambat
# merespon. Ini kontributor besar ke "reconnect lama".
_last_known_gcs_ip = None

def _mdns_lookup_with_timeout(hostname: str, timeout: float = 1.5):
    """gethostbyname() tidak selalu menghormati socket.setdefaulttimeout()
    di semua sistem (resolver C library bisa mengabaikannya). Jalankan di
    thread terpisah dengan join(timeout) supaya benar-benar dibatasi."""
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

    # 0. [FIX E] Coba dulu IP terakhir yang sukses konek (paling cepat,
    #    biasanya IP laptop tidak berubah dalam satu sesi lomba/testing).
    if _last_known_gcs_ip:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        if sock.connect_ex((_last_known_gcs_ip, 5000)) == 0:
            sock.close()
            print(f"[+] GCS found via cache: {_last_known_gcs_ip}", flush=True)
            return _last_known_gcs_ip
        sock.close()

    # 1. Coba cari dari tabel ARP/neighbors (karena laptop pasti ada di sana jika sedang SSH/deploy)
    # Metode ini instan, menggunakan 0 thread, dan sangat andal saat terhubung wifi
    try:
        output = subprocess.check_output(["ip", "neigh", "show"]).decode('utf-8')
        for line in output.splitlines():
            if "FAILED" not in line and ("REACHABLE" in line or "DELAY" in line or "STALE" in line):
                parts = line.split()
                if len(parts) > 0:
                    ip = parts[0]
                    # Pastikan port 5000 (GCS Flask) terbuka
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.2)
                    if sock.connect_ex((ip, 5000)) == 0:
                        sock.close()
                        print(f"[+] GCS found via ARP table: {ip}", flush=True)
                        return ip
                    sock.close()
    except Exception as e:
        print(f"[-] Failed to read ARP table: {e}", flush=True)

    # 2. Coba mDNS hostname laptop — [FIX E] sekarang dibatasi waktu tegas.
    ip = _mdns_lookup_with_timeout("f15.local", timeout=1.5)
    if ip:
        print(f"[+] GCS found via mDNS f15.local: {ip}", flush=True)
        return ip

    # 3. Fallback to default IP
    print(f"[!] Fallback to default IP: {LAPTOP_IP}", flush=True)
    return LAPTOP_IP

# ─── Deteksi Kamera ───────────────────────────────────────────────────────────

bottom_dev = "OFFLINE"
front_dev = "OFFLINE"

def print_camera_status():
    global bottom_dev, front_dev
    print("\n" + "=" * 45, flush=True)
    print("           USB CAMERA DETECTION STATUS", flush=True)
    print("=" * 45, flush=True)
    print(f"  ● BOTTOM CAMERA : {bottom_dev:<14} -> {'ACTIVE' if bottom_dev != 'OFFLINE' else 'OFFLINE'}", flush=True)
    print(f"  ● FRONT CAMERA  : {front_dev:<14} -> {'ACTIVE' if front_dev != 'OFFLINE' else 'OFFLINE'}", flush=True)
    print("=" * 45 + "\n", flush=True)


def probe_camera_indices():
    available = []
    video_devices = glob.glob("/dev/video*")
    indices = []
    for path in video_devices:
        try:
            idx = int(path.replace("/dev/video", ""))
            indices.append(idx)
        except ValueError:
            pass
    indices = sorted(list(set(indices)))

    for i in indices:
        if i > 20: 
            continue
        try:
            with open(f"/sys/class/video4linux/video{i}/name", "r") as f:
                dev_name = f.read().strip().lower()
            
            # Abaikan endpoint BCM2835 ISP (internal Pi) dan endpoint metadata UVC
            if "bcm2835" in dev_name or "metadata" in dev_name or "association" in dev_name:
                continue
            
            # Pastikan ini adalah endpoint capture utama (index 0), bukan metadata (index 1)
            try:
                with open(f"/sys/class/video4linux/video{i}/index", "r") as f:
                    dev_index = int(f.read().strip())
                if dev_index != 0:
                    continue
            except Exception:
                pass
            
            available.append(i)
        except Exception:
            pass
    return available


def resolve_index_from_by_id(by_id_name: str):
    """Mengubah nama stabil /dev/v4l/by-id/<by_id_name> menjadi index /dev/videoN.
    Return None jika tidak ditemukan (device belum plug, atau nama salah)."""
    if not by_id_name:
        return None
    path = os.path.join("/dev/v4l/by-id", by_id_name)
    if not os.path.exists(path):
        return None
    try:
        real = os.path.realpath(path)          # -> /dev/videoN
        idx = int(real.replace("/dev/video", ""))
        return idx
    except Exception:
        return None


def list_available_by_id():
    """Bantu debugging: tampilkan semua by-id path yang ada saat ini."""
    try:
        return sorted(glob.glob('/dev/v4l/by-id/*'))
    except Exception:
        return []


class ThreadedCamera:
    """Mengambil frame kamera secara asinkron di background thread untuk menghindari I/O blocking."""
    def __init__(self, index, name):
        self.index = index
        self.name = name
        self.cap = None
        self.grabbed = False
        self.frame = None
        self.started = False
        self.ready = threading.Event()   # [FIX A] signal: frame pertama sudah berhasil dibaca
        self.read_lock = threading.Lock()

    def _open(self):
        if self.cap is not None and self.cap.isOpened():
            return True
        cap = cv2.VideoCapture(self.index)
        if not cap.isOpened():
            return False
        
        # [FIX] Set FOURCC (MJPG) PERTAMA KALI sebelum set resolusi!
        # Kamera murah (Jieli/USB 2.0) akan menolak (errno=19) jika 
        # kita paksa resolusi tinggi dalam format default (YUYV) karena 
        # melampaui limit bandwidth USB saat 2 kamera dipasang.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        
        # Resolusi dikembalikan ke 720p (1280x720) sesuai permintaan
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FPS, 30)
        with self.read_lock:
            self.cap = cap
        return True

    def start(self):
        if self.started:
            return self
        self.started = True
        self.thread = threading.Thread(target=self.update, args=(), name=f"cam_thread_{self.name}")
        self.thread.daemon = True
        self.thread.start()
        return self

    def update(self):
        while self.started:
            if not self.isOpened():
                if not self._open():
                    time.sleep(0.3)
                    continue
            with self.read_lock:
                cap_ref = self.cap
            ret, frame = cap_ref.read() if cap_ref is not None else (False, None)
            if ret and frame is not None:
                with self.read_lock:
                    self.grabbed = True
                    self.frame = frame
                self.ready.set()   # [FIX A] baru set setelah benar-benar ada frame
            else:
                with self.read_lock:
                    if self.cap is not None:
                        self.cap.release()
                    self.cap = None
                time.sleep(0.1)
            time.sleep(0.005)

    def read(self):
        with self.read_lock:
            if not self.grabbed or self.frame is None:
                return False, None
            return True, self.frame.copy()

    def isOpened(self):
        # [FIX A] lock-protected + null-check, tidak akan pernah AttributeError
        with self.read_lock:
            return self.cap is not None and self.cap.isOpened()

    def release(self):
        self.started = False
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        with self.read_lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None

def detect_cameras():
    global bottom_dev, front_dev
    cameras = {}
    bottom_dev = "OFFLINE"
    front_dev = "OFFLINE"

    # [FIX B] Coba dulu via by-id (stabil), baru fallback ke index berurutan.
    bottom_index = resolve_index_from_by_id(BOTTOM_CAM_BY_ID)
    front_index  = resolve_index_from_by_id(FRONT_CAM_BY_ID)

    if bottom_index is not None or front_index is not None:
        print("[+] Using stable camera mapping via /dev/v4l/by-id/", flush=True)
        if bottom_index is not None:
            cameras['bottom'] = ThreadedCamera(bottom_index, 'bottom').start()
            bottom_dev = f"/dev/video{bottom_index} (by-id)"
        if front_index is not None:
            cameras['front'] = ThreadedCamera(front_index, 'front').start()
            front_dev = f"/dev/video{front_index} (by-id)"
        print_camera_status()
        return cameras

    # Fallback: metode lama (index berurutan). Peringatan: urutan bisa tertukar
    # antar reboot/replug — isi BOTTOM_CAM_BY_ID / FRONT_CAM_BY_ID untuk fix permanen.
    print("[!] BOTTOM_CAM_BY_ID / FRONT_CAM_BY_ID not set — using index detection (might swap).", flush=True)
    print("[i] Currently detected by-id devices:", flush=True)
    for p in list_available_by_id():
        print(f"    {p}", flush=True)

    available = []
    # Jalankan probe berulang untuk memberi waktu kedua kamera siap (terutama saat cold boot)
    # Kita tidak langsung break pada len >= 1 agar kamera kedua juga berkesempatan terdeteksi
    for attempt in range(10):
        available = probe_camera_indices()
        if len(available) >= 2:
            print(f"[+] Both cameras detected at attempt {attempt + 1}.", flush=True)
            break
        print(f"[*] Waiting for USB cameras... Found {len(available)} kamera ({attempt + 1}/10)", flush=True)
        time.sleep(0.5)

    if len(available) >= 2:
        idx_bottom = available[0]
        idx_front = available[1]
        cameras['bottom'] = ThreadedCamera(idx_bottom, 'bottom').start()
        cameras['front'] = ThreadedCamera(idx_front, 'front').start()
        bottom_dev = f"/dev/video{idx_bottom}"
        front_dev = f"/dev/video{idx_front}"
    elif len(available) == 1:
        idx_bottom = available[0]
        cameras['bottom'] = ThreadedCamera(idx_bottom, 'bottom').start()
        bottom_dev = f"/dev/video{idx_bottom}"
        print("[!] Only 1 camera detected. Front camera OFFLINE.")
    else:
        print("[!] No USB cameras detected on startup.")

    print_camera_status()
    return cameras

# ─── ArUco Filter per-ID ─────────────────────────────────────────────────────

class ArUcoFilter:
    """Rolling buffer filter per marker ID untuk meredam noise/flicker."""

    def __init__(self, size=15, min_detections=8, max_variance=150):
        self.size           = size
        self.min_detections = min_detections
        self.max_variance   = max_variance
        self.x_buf  = deque(maxlen=size)
        self.y_buf  = deque(maxlen=size)
        self.z_buf  = deque(maxlen=size)
        self.last_emit_time = 0
        self.last_raw_emit_time = 0

    def add(self, x, y, z):
        self.x_buf.append(x)
        self.y_buf.append(y)
        self.z_buf.append(z)

    def add_empty(self):
        self.x_buf.append(None)
        self.y_buf.append(None)
        self.z_buf.append(None)

    def get(self):
        vx = [v for v in self.x_buf if v is not None]
        vy = [v for v in self.y_buf if v is not None]
        vz = [v for v in self.z_buf if v is not None]

        if len(vx) < self.min_detections:
            return None

        if np.var(vx) > self.max_variance or np.var(vy) > self.max_variance:
            return None

        return {
            'x': float(np.mean(vx)),
            'y': float(np.mean(vy)),
            'z': float(np.mean(vz))
        }

# Filter per marker ID — key = marker_id (int)
aruco_filters: dict[int, ArUcoFilter] = {}

def get_filter(marker_id: int) -> ArUcoFilter:
    if marker_id not in aruco_filters:
        aruco_filters[marker_id] = ArUcoFilter()
    return aruco_filters[marker_id]

# ─── Setup ArUco Detector ─────────────────────────────────────────────────────
# KRTI 2026 marker: DICT_7X7_50 saja — tidak perlu scan semua dict (lebih cepat & akurat)

_aruco_dict   = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)

try:
    _aruco_params = cv2.aruco.DetectorParameters()
except AttributeError:
    _aruco_params = cv2.aruco.DetectorParameters_create()


try:
    _detector = cv2.aruco.ArucoDetector(_aruco_dict, _aruco_params)
    def detect_aruco(gray):
        return _detector.detectMarkers(gray)
except AttributeError:
    # Fallback OpenCV < 4.7
    def detect_aruco(gray):
        return cv2.aruco.detectMarkers(gray, _aruco_dict, parameters=_aruco_params)


# ─── Constant Arrays untuk Pemrosesan Citra Cepat (Zero-Allocation Loop) ───────
LOWER_RED1   = np.array([0, 120, 120], dtype=np.uint8)
UPPER_RED1   = np.array([10, 255, 255], dtype=np.uint8)
LOWER_RED2   = np.array([170, 120, 120], dtype=np.uint8)
UPPER_RED2   = np.array([180, 255, 255], dtype=np.uint8)
MORPH_KERNEL = np.ones((3, 3), dtype=np.uint8)

# Throttle untuk emit bottom_cam_object ke web (hindari spam)
_bottom_cam_object_emit_time = 0.0

def detect_red_object(work_frame):
    """Mendeteksi kontur fisik Red Box (3D Object) pada frame kecil (work_frame).
    Optimasi: Menggunakan constant arrays di tingkat modul tanpa alokasi memori berulang.
    Returns (detected, cx, cy, area, x_min, y_min, x_max, y_max) dalam koordinat work_frame."""
    try:
        hsv = cv2.cvtColor(work_frame, cv2.COLOR_BGR2HSV)

        mask1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
        mask2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
        mask  = cv2.bitwise_or(mask1, mask2)

        # Pembersihan noise cepat dengan kernel 3x3
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, MORPH_KERNEL)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            if area > 1200:  # Threshold area minimal untuk fisik Red Box asli
                M = cv2.moments(largest)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    bx, by, bw, bh = cv2.boundingRect(largest)
                    margin = max(4, int(min(bw, bh) * 0.15))
                    rx_min = max(0, bx - margin)
                    ry_min = max(0, by - margin)
                    rx_max = min(work_frame.shape[1], bx + bw + margin)
                    ry_max = min(work_frame.shape[0], by + bh + margin)
                    return True, cx, cy, area, rx_min, ry_min, rx_max, ry_max
    except Exception:
        pass
    return False, 0, 0, 0, 0, 0, 0, 0


def draw_artificial_box(frame, x_min, y_min, x_max, y_max, cx_f, cy_f, is_centered, label):
    """Menggambar kotak buatan (artificial marker box) di atas frame output.
    - Border MERAH  jika belum terpusat (kotak belum pas dengan kamera)
    - Border HIJAU  jika sudah terpusat (siap drop / aligned)
    - Red dot (●) di center kotak
    - Label nama objek di atas kotak
    """
    border_color  = (0, 255, 0) if is_centered else (0, 0, 255)   # Hijau / Merah
    corner_len    = max(8, int((x_max - x_min) * 0.22))           # Panjang sudut dekoratif
    thickness     = 2

    # ── Kotak utama (tipis, warna border) ──
    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), border_color, 1)

    # ── Sudut tebal (corner decorations) ──
    for (sx, sy, dx, dy) in [
        (x_min, y_min,  1,  1),   # kiri-atas
        (x_max, y_min, -1,  1),   # kanan-atas
        (x_min, y_max,  1, -1),   # kiri-bawah
        (x_max, y_max, -1, -1),   # kanan-bawah
    ]:
        cv2.line(frame, (sx, sy), (sx + dx * corner_len, sy),              border_color, thickness)
        cv2.line(frame, (sx, sy), (sx,              sy + dy * corner_len), border_color, thickness)

    # ── Center red dot ──
    cv2.circle(frame, (cx_f, cy_f), 4, (0, 0, 255), -1)     # Titik tengah merah solid
    cv2.circle(frame, (cx_f, cy_f), 8, (0, 0, 255), 1)       # Lingkaran kecil di sekitarnya

    # ── Crosshair kecil di center ──
    cross = 6
    cv2.line(frame, (cx_f - cross, cy_f), (cx_f + cross, cy_f), (0, 0, 255), 1)
    cv2.line(frame, (cx_f, cy_f - cross), (cx_f, cy_f + cross), (0, 0, 255), 1)

    # ── Label nama objek (di atas kotak) ──
    lx = max(0, x_min)
    ly = max(12, y_min - 4)
    font_scale = 0.38
    cv2.putText(frame, label, (lx, ly),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, border_color, 1, cv2.LINE_AA)

    # ── Status alignment di pojok kiri bawah kotak ──
    status_txt = "ALIGNED" if is_centered else "ALIGNING..."
    cv2.putText(frame, status_txt, (lx, y_max + 11),
                cv2.FONT_HERSHEY_SIMPLEX, 0.30, border_color, 1, cv2.LINE_AA)


def process_aruco_markers(frame):
    global _bottom_cam_object_emit_time
    h, w = frame.shape[:2]
    cx_frame, cy_frame = w // 2, h // 2

    # ── Scale factors antara work frame (kecil) dan output frame ──
    work_w, work_h = 240, 180
    scale_x = w / work_w
    scale_y = h / work_h

    # Deteksi dilakukan pada frame yang lebih kecil untuk menjaga performa Pi
    work = cv2.resize(frame, (work_w, work_h), interpolation=cv2.INTER_LINEAR)
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detect_aruco(gray)

    # ── State untuk emit ke web ──
    detected_object_type = None   # 'WP1'/'WP2'/... / 'RED_BOX' / None
    detected_object_centered = False

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Deteksi & visualisasi ArUco marker (prioritas: ID terkecil yang aktif)
    # ─────────────────────────────────────────────────────────────────────────
    aruco_found = (ids is not None and len(ids) > 0)
    if aruco_found:
        id_list = ids.flatten().tolist()
        best_idx = int(np.argmin(id_list))
        marker_id = int(ids[best_idx][0])
        marker_corners = corners[best_idx][0]

        # Hitung posisi center marker di output frame
        mc_x = int(np.mean(marker_corners[:, 0]) * scale_x)
        mc_y = int(np.mean(marker_corners[:, 1]) * scale_y)
        dx = mc_x - cx_frame
        dy = cy_frame - mc_y   # positif = target di atas center

        # Bounding box marker di output frame
        x_min = int(np.min(marker_corners[:, 0]) * scale_x)
        x_max = int(np.max(marker_corners[:, 0]) * scale_x)
        y_min = int(np.min(marker_corners[:, 1]) * scale_y)
        y_max = int(np.max(marker_corners[:, 1]) * scale_y)

        # Beri margin pada kotak buatan agar lebih besar dari marker asli
        box_margin = max(6, int((x_max - x_min) * 0.2))
        bx_min = max(0, x_min - box_margin)
        bx_max = min(w - 1, x_max + box_margin)
        by_min = max(0, y_min - box_margin)
        by_max = min(h - 1, y_max + box_margin)

        # Pose estimation (jika kamera sudah dikalibrasi)
        if CAMERA_MATRIX is not None and DIST_COEFFS is not None:
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                [corners[best_idx]], MARKER_SIZE_M, CAMERA_MATRIX, DIST_COEFFS
            )
            dz = float(tvecs[0][0][2])
            dz_label = f"Z:{dz:.2f}m"
        else:
            dz = float((x_max - x_min + y_max - y_min) / 2.0)
            dz_label = f"Z:{dz:.0f}px"

        f_obj = get_filter(marker_id)
        f_obj.add(dx, dy, dz)

        now = time.time()

        # Emit raw detection (throttled)
        if now - f_obj.last_raw_emit_time > 1.0:
            f_obj.last_raw_emit_time = now
            if sio.connected:
                try:
                    sio.emit('aruco_detected', {'id': int(marker_id)})
                except Exception:
                    pass

        # Update filter untuk ID lain (add_empty)
        for fid, fobj in aruco_filters.items():
            if fid != marker_id:
                fobj.add_empty()

        mapped_wp_name = "WP4" if marker_id == 3 else ("WP3" if marker_id == 4 else f"WP{marker_id}")

        filtered = f_obj.get()
        if filtered is not None:
            is_centered = (abs(filtered['x']) <= 25 and abs(filtered['y']) <= 25)
            detected_object_centered = is_centered

            # ── Gambar kotak buatan ArUco ──
            draw_artificial_box(
                frame,
                bx_min, by_min, bx_max, by_max,
                mc_x, mc_y,
                is_centered,
                mapped_wp_name
            )

            # ── Info DX / DY di bawah frame ──
            cv2.putText(frame, f"DX:{filtered['x']:+.0f} DY:{filtered['y']:+.0f} | {dz_label}",
                        (10, h - 26), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (200, 200, 200), 1, cv2.LINE_AA)

            # ── Reticle center frame: hijau jika centered, oranye jika tidak ──
            reticle_color = (0, 255, 0) if is_centered else (0, 165, 255)
            reticle_r = 22
            cv2.circle(frame, (cx_frame, cy_frame), reticle_r, reticle_color, 1)
            cv2.line(frame, (cx_frame - reticle_r - 4, cy_frame), (cx_frame + reticle_r + 4, cy_frame), reticle_color, 1)
            cv2.line(frame, (cx_frame, cy_frame - reticle_r - 4), (cx_frame, cy_frame + reticle_r + 4), reticle_color, 1)

            if is_centered:
                cv2.putText(frame, "CENTERED - DROP ACTIVE!",
                            (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 0), 1, cv2.LINE_AA)

            # ── Emit aruco_target_centered (presisi untuk servo WP2) ──
            if is_centered:
                # Kirim ke localhost UDP dulu (Otonom tanpa Wi-Fi!)
                send_local_servo_trigger('aruco_target_centered', {
                    'marker_id': int(marker_id),
                    'wp': mapped_wp_name,
                    'x': filtered['x'],
                    'y': filtered['y'],
                    'z': filtered['z']
                })
                if sio.connected:
                    try:
                        sio.emit('aruco_target_centered', {
                            'marker_id': int(marker_id),
                            'wp': mapped_wp_name,
                            'x': filtered['x'],
                            'y': filtered['y'],
                            'z': filtered['z']
                        })
                        print(f"[🎯 CENTERED] {mapped_wp_name} | dx:{filtered['x']:.0f} dy:{filtered['y']:.0f}")
                    except Exception:
                        pass

            # ── Emit aruco_target_stable (throttled) ──
            if now - f_obj.last_emit_time > 1.2:
                f_obj.last_emit_time = now
                if sio.connected:
                    try:
                        sio.emit('aruco_target_stable', {
                            'id': int(marker_id),
                            'wp': mapped_wp_name,
                            'x': filtered['x'],
                            'y': filtered['y'],
                            'z': filtered['z'],
                            'centered': is_centered
                        })
                    except Exception:
                        pass

            detected_object_type = mapped_wp_name

        else:
            # Filter belum stable tapi marker terlihat — gambar kotak sementara
            draw_artificial_box(
                frame,
                bx_min, by_min, bx_max, by_max,
                mc_x, mc_y,
                False,
                f"{mapped_wp_name} (acq...)"
            )

    else:
        # Tidak ada ArUco — kosongkan semua filter
        for f_obj in aruco_filters.values():
            f_obj.add_empty()

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Deteksi & visualisasi Red Box
    #    (hanya gambar jika ArUco tidak ditemukan, untuk menghindari confusion;
    #    tapi emit ke servo/web selalu terjadi independen dari ArUco)
    # ─────────────────────────────────────────────────────────────────────────
    red_result = detect_red_object(work)
    red_detected = red_result[0]

    if red_detected:
        _,  rx_w, ry_w, red_area, rx_min_w, ry_min_w, rx_max_w, ry_max_w = red_result

        # Konversi ke koordinat output frame
        rc_x   = int(rx_w  * scale_x)
        rc_y   = int(ry_w  * scale_y)
        rx_min = int(rx_min_w * scale_x)
        ry_min = int(ry_min_w * scale_y)
        rx_max = int(rx_max_w * scale_x)
        ry_max = int(ry_max_w * scale_y)

        rdx = rc_x - cx_frame
        rdy = cy_frame - rc_y
        # Presisi Red Box: kamera harus berada tepat di atas target (radius 35px)
        is_red_in_frame  = True   # Sudah pasti: kita masuk sini karena terdeteksi
        is_red_centered  = (abs(rdx) <= 35 and abs(rdy) <= 35)

        # ── Gambar kotak buatan Red Box ──
        draw_artificial_box(
            frame,
            rx_min, ry_min, rx_max, ry_max,
            rc_x, rc_y,
            is_red_centered,
            "RED BOX"
        )

        # ── Emit ke servo node (non-presisi, in_frame saja sudah cukup) ──
        if is_red_centered:
            # Kirim ke localhost UDP dulu (Otonom tanpa Wi-Fi!)
            send_local_servo_trigger('red_object_detected', {
                'x':        int(rdx),
                'y':        int(rdy),
                'centered': bool(is_red_centered),
                'in_frame': True
            })
        if sio.connected:
            try:
                sio.emit('red_object_detected', {
                    'x':        int(rdx),
                    'y':        int(rdy),
                    'centered': bool(is_red_centered),
                    'in_frame': True
                })
            except Exception:
                pass

        # Jika ArUco tidak terdeteksi, red box yang jadi "primary" objek
        if not aruco_found:
            detected_object_type    = "RED_BOX"
            detected_object_centered = is_red_centered

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Emit bottom_cam_object ke web (throttled 0.8s)
    # ─────────────────────────────────────────────────────────────────────────
    now = time.time()
    if sio.connected and now - _bottom_cam_object_emit_time > 0.8:
        _bottom_cam_object_emit_time = now
        try:
            sio.emit('bottom_cam_object', {
                'type':     detected_object_type,    # None / 'WP1' / 'WP2' / ... / 'RED_BOX'
                'centered': detected_object_centered
            })
        except Exception:
            pass
    elif not red_detected and not aruco_found and sio.connected and now - _bottom_cam_object_emit_time > 2.0:
        # Tidak ada objek — emit None agar web tahu scanning
        _bottom_cam_object_emit_time = now
        try:
            sio.emit('bottom_cam_object', {'type': None, 'centered': False})
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Warning kalibrasi
    # ─────────────────────────────────────────────────────────────────────────
    if CAMERA_MATRIX is None or DIST_COEFFS is None:
        cv2.putText(frame, "UNCALIBRATED", (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 0, 255), 1, cv2.LINE_AA)

    return frame

# ─── Socket.IO ────────────────────────────────────────────────────────────────

sio = socketio.Client()

# [FIX C] diisi oleh __main__ setelah detect_cameras() dijalankan, sebelum sio.connect()
detected_cameras: dict = {}

@sio.event
def connect():
    print("[+] Connected to GCS!", flush=True)
    print_camera_status()
    # [FIX C] hanya kirim status utk kamera yang benar-benar terdeteksi,
    # supaya GCS tidak menampilkan box "connected" untuk kamera yang tidak ada.
    for camera_name in detected_cameras.keys():
        try:
            sio.emit('pi_camera_status', {'camera': camera_name, 'connected': True, 'rssi': get_wifi_rssi()})
        except Exception:
            pass

@sio.event
def disconnect():
    print("[-] Disconnected from GCS.", flush=True)

# ─── WiFi Monitor ─────────────────────────────────────────────────────────────

def get_wifi_rssi():
    try:
        with open("/proc/net/wireless") as f:
            lines = f.readlines()
        if len(lines) > 2:
            parts    = lines[2].split()
            rssi_str = parts[3].replace('.', '')
            rssi     = int(rssi_str)
            return (-100 + rssi) if rssi > 0 else rssi
    except Exception:
        pass
    return -65

def wifi_monitor_loop():
    global LAPTOP_IP
    last_ok = time.time()
    while True:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", LAPTOP_IP],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                last_ok = time.time()
            else:
                elapsed = time.time() - last_ok
                print(f"[!] WiFi to GCS disconnected {elapsed:.1f}s")
                if elapsed >= PING_TIMEOUT_SEC:
                    print("[*] Reconnect WiFi soft trigger (disconnecting Socket.IO to force main loop reconnection)...")
                    if sio.connected:
                        try:
                            sio.disconnect()
                        except Exception:
                            pass
                    # [FIX E] Diturunkan dari 5.0 -> 1.0. Tidak perlu menunggu lama di sini;
                    # main loop akan langsung mencoba reconnect via find_gcs_ip() yang
                    # sekarang sudah cepat (cache IP + mDNS timeout).
                    time.sleep(1.0)
                    last_ok = time.time()
        except Exception as e:
            print(f"[!] wifi_monitor error: {e}")
        time.sleep(2.0)

def telemetry_rssi_loop():
    while True:
        if sio.connected:
            try:
                sio.emit('pi_wifi_status', {'rssi': get_wifi_rssi()})
            except Exception:
                pass
        time.sleep(1.0)

# ─── Front Camera: Tidak ada processing (stream langsung tanpa CV) ──────────
# Gate detection dihapus. Front camera hanya mengirim video feed mentah.
# Tidak ada CPU overhead dari OpenCV pada kamera depan.


def camera_stream_thread(name, cap):
    global STREAM_FAILURES, CURRENT_STREAM_PROFILE
    print(f"[+] Streaming thread for camera started.", flush=True)

    # [FIX A] Tunggu sampai frame pertama benar-benar berhasil dibaca,
    # daripada langsung memanggil cap.isOpened() yang bisa race dengan
    # thread update() saat self.cap masih None.
    print(f"[*] Waiting for first frame from '{name}'...", flush=True)
    cap.ready.wait()
    print(f"[+] Camera ready, starting streaming.", flush=True)

    last_emit = 0.0
    stream_ready = False

    while True:
        # [FIX D] seluruh isi loop dibungkus try/except: error apapun
        # tidak akan mematikan thread ini secara permanen lagi.
        try:
            if not cap.isOpened():
                time.sleep(0.1)
                continue

            now = time.time()
            profile = CURRENT_STREAM_PROFILE
            frame_interval = 1.0 / profile['fps']
            if now - last_emit < frame_interval:
                time.sleep(0.01)
                continue

            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            last_emit = now
            # Pertahankan rasio asli kamera agar tidak gepeng/lebar
            h_orig, w_orig = frame.shape[:2]
            target_w = profile['width']
            target_h = int(target_w * (h_orig / w_orig))
            frame_out = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            if name == 'bottom':
                # Processing ArUco WP1-WP4 dan Red Box SELALU dieksekusi otonom!
                frame_out = process_aruco_markers(frame_out)
            # Front camera: tidak ada CV processing — langsung stream

            # Hanya kirim stream gambar base64 ke web JIKA Wi-Fi/GCS terhubung
            if sio.connected:
                ret_enc, jpeg = cv2.imencode('.jpg', frame_out, [cv2.IMWRITE_JPEG_QUALITY, profile['quality']])
                if ret_enc:
                    try:
                        img_base64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
                        if not stream_ready:
                            stream_ready = True
                            sio.emit('pi_camera_status', {'camera': name, 'connected': True, 'rssi': get_wifi_rssi()})
                        sio.emit('pi_camera_feed', {
                            'camera': name,
                            'image': img_base64
                        })
                        STREAM_FAILURES = max(0, STREAM_FAILURES - 1)
                    except Exception as e:
                        print(f"[!] Emit feed error on '{name}': {e}", flush=True)
                        STREAM_FAILURES += 1
                        if ADAPTIVE_STREAM:
                            if STREAM_FAILURES >= STREAM_FAILURE_THRESHOLD:
                                if CURRENT_STREAM_PROFILE != STREAM_PROFILE_MEDIUM:
                                    CURRENT_STREAM_PROFILE = STREAM_PROFILE_MEDIUM
                                    print(f"[+] Downgrading stream profile to MEDIUM due to heavy web connection: {CURRENT_STREAM_PROFILE}", flush=True)
                                elif CURRENT_STREAM_PROFILE != STREAM_PROFILE_LOW:
                                    CURRENT_STREAM_PROFILE = STREAM_PROFILE_LOW
                                    print(f"[+] Downgrading stream profile to LOW due to heavy web connection: {CURRENT_STREAM_PROFILE}", flush=True)
                        time.sleep(0.2)

            time.sleep(0.01)

        except Exception as e:
            # [FIX D] safety net terakhir — thread tetap hidup, retry terus.
            print(f"[!] stream_thread '{name}' encountered unexpected error: {e}", flush=True)
            STREAM_FAILURES += 1
            time.sleep(0.3)

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("[*] FAST STARTUP: Initializing USB hardware modules...", flush=True)
    time.sleep(1.0)

    threading.Thread(target=wifi_monitor_loop,  daemon=True).start()
    threading.Thread(target=telemetry_rssi_loop, daemon=True).start()

    cameras = detect_cameras()
    detected_cameras = cameras   # [FIX C] populate sebelum sio.connect() bisa trigger connect()

    # Jalankan streaming setiap kamera di thread-nya masing-masing
    for name, cap in cameras.items():
        t = threading.Thread(target=camera_stream_thread, args=(name, cap), name=f"stream_{name}", daemon=True)
        t.start()

    print("[*] Waiting for camera hardware to be ready to capture frames before sending to Web...", flush=True)
    for _ in range(30):
        if any(c.grabbed for c in cameras.values()):
            print("[+] Camera Hardware READY! Proceeding to connect to Web GCS...", flush=True)
            break
        time.sleep(1.0)

    while True:
        if not sio.connected:
            try:
                LAPTOP_IP = find_gcs_ip()
                GCS_URL   = f"http://{LAPTOP_IP}:5000"
                print(f"[*] Connecting to GCS: {GCS_URL}", flush=True)
                sio.connect(GCS_URL)
                _last_known_gcs_ip = LAPTOP_IP  # [FIX E] simpan untuk reconnect cepat berikutnya
            except Exception as e:
                print(f"[-] Failed to connect to GCS: {e}", flush=True)
                time.sleep(2.0)
                continue
        time.sleep(1.0)