#!/usr/bin/env python3
"""
calibrate_camera.py — Kalibrasi Kamera Web-Enabled untuk KRTI 2026
[ignoring loop detection]
==================================================================
Script ini didesain untuk berjalan secara headless (tanpa GUI desktop)
di Raspberry Pi. Video feed dari kamera (yang dilengkapi dengan overlay
deteksi checkerboard) akan dipancarkan ke Dashboard GCS di Laptop Anda.
Anda cukup memantau dari browser dan menekan ENTER di terminal SSH
untuk melakukan capture gambar kalibrasi.
"""

import cv2
import numpy as np
import os
import time
import socketio
import threading
import sys
import socket
import base64

# ─── Konfigurasi Checkerboard ─────────────────────────────────────────────────
BOARD_W      = 9       # jumlah inner corner horizontal
BOARD_H      = 6       # jumlah inner corner vertikal
SQUARE_SIZE  = 0.025   # ukuran satu kotak dalam meter (25mm)
MIN_CAPTURES = 20      # target jumlah capture

# ─── Setup ────────────────────────────────────────────────────────────────────
SAVE_DIR = "calib_frames"
os.makedirs(SAVE_DIR, exist_ok=True)

# Titik 3D dunia nyata
objp = np.zeros((BOARD_H * BOARD_W, 3), np.float32)
objp[:, :2] = np.mgrid[0:BOARD_W, 0:BOARD_H].T.reshape(-1, 2)
objp *= SQUARE_SIZE

objpoints = []   # titik 3D
imgpoints = []   # titik 2D

criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# ─── Auto-Discovery GCS IP ────────────────────────────────────────────────────
LAPTOP_IP = "192.168.0.104"

def find_gcs_ip():
    try:
        ip = socket.gethostbyname("f15.local")
        return ip
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        subnet_prefix = ".".join(local_ip.split(".")[:3]) + "."
        found_ips = []
        def check_ip(suffix):
            target = f"{subnet_prefix}{suffix}"
            if target == local_ip: return
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            if sock.connect_ex((target, 5000)) == 0:
                found_ips.append(target)
            sock.close()
        threads = [threading.Thread(target=check_ip, args=(i,)) for i in range(1, 255)]
        for t in threads: t.start()
        for t in threads: t.join()
        if found_ips: return found_ips[0]
    except Exception:
        pass
    return LAPTOP_IP

# ─── Deteksi Kamera Otomatis ──────────────────────────────────────────────────
def detect_camera_index():
    available = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available.append(i)
            cap.release()
    if len(available) > 0:
        print(f"[+] Kamera aktif ditemukan pada index: {available}")
        return available[0]
    return 0

# ─── Input Terminal Non-Blocking ──────────────────────────────────────────────
capture_requested = False
quit_requested = False

def terminal_input_thread():
    global capture_requested, quit_requested
    while not quit_requested:
        try:
            line = input()
            # Bersihkan karakter newline/whitespace
            cmd = line.strip().lower()
            if cmd == 'q':
                quit_requested = True
                break
            else:
                capture_requested = True
        except (KeyboardInterrupt, EOFError):
            quit_requested = True
            break

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Cari IP GCS dan hubungkan Socket.IO
    gcs_ip = find_gcs_ip()
    GCS_URL = f"http://{gcs_ip}:5000"
    
    sio = socketio.Client()
    print(f"[*] Menghubungkan ke server GCS di: {GCS_URL}")
    try:
        sio.connect(GCS_URL)
        print("[✓] Terhubung ke GCS! Tampilan kamera kalibrasi disalurkan ke web.")
    except Exception as e:
        print(f"[!] Gagal terhubung ke GCS: {e}. Berjalan offline (tanpa streaming dashboard).")

    camera_idx = detect_camera_index()
    print(f"[*] Membuka kamera index {camera_idx}...")
    cap = cv2.VideoCapture(camera_idx)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    # Set timeout v4l2 agar tidak ngehang
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print(f"[!] Gagal membuka kamera index {camera_idx}.")
        sys.exit(1)

    print("\n" + "=" * 55)
    print("  KALIBRASI KAMERA WEB-ENABLED (HEADLESS) KRTI 2026")
    print("=" * 55)
    print(f"  Checkerboard: {BOARD_W}x{BOARD_H} inner corners")
    print("  Video feed dikirim ke: Dashboard GCS (Bottom Camera)")
    print("\n  PETUNJUK KONTROL TERMINAL SSH:")
    print("  - Tekan [ENTER] (kosong) → Capture frame saat ini")
    print("  - Ketik [q] lalu [ENTER]  → Selesai & hitung kalibrasi")
    print("=" * 55 + "\n")

    # Jalankan thread input
    threading.Thread(target=terminal_input_thread, daemon=True).start()

    n_captures = 0
    last_flash = 0
    flash_active = False

    while not quit_requested:
        ret, frame = cap.read()
        if not ret:
            # Delay kecil agar CPU tidak 100% saat frame belum siap
            time.sleep(0.01)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        display = frame.copy()

        # Deteksi checkerboard
        found, corners = cv2.findChessboardCorners(
            gray, (BOARD_W, BOARD_H),
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        status_color = (0, 0, 255)
        status_text = f"Mencari Checkerboard... [{n_captures}/{MIN_CAPTURES}]"

        if found:
            corners_refined = cv2.cornerSubPix(
                gray, corners, (11, 11), (-1, -1), criteria
            )
            cv2.drawChessboardCorners(display, (BOARD_W, BOARD_H), corners_refined, found)
            status_color = (0, 255, 0)
            status_text = f"SIAP CAPTURE! Tekan ENTER [{n_captures}/{MIN_CAPTURES}]"

            if capture_requested:
                capture_requested = False
                objpoints.append(objp)
                imgpoints.append(corners_refined)
                n_captures += 1
                last_flash = time.time()
                flash_active = True
                
                # Simpan frame ke folder lokal
                fname = os.path.join(SAVE_DIR, f"frame_{n_captures:03d}.jpg")
                cv2.imwrite(fname, frame)
                print(f"  [+] Capture {n_captures:2d} disimpan → {fname}")
        else:
            if capture_requested:
                capture_requested = False
                print("  [!] Gagal: Checkerboard tidak terdeteksi dalam frame ini!")

        # Flash hijau indikator capture sukses
        if flash_active:
            if time.time() - last_flash < 0.4:
                cv2.rectangle(display, (0, 0), (320, 240), (0, 255, 0), 4)
            else:
                flash_active = False

        # Tambah HUD label
        cv2.rectangle(display, (0, 0), (320, 18), (0, 0, 0), -1)
        cv2.putText(display, status_text, (4, 13),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, status_color, 1, cv2.LINE_AA)

        # Pancarkan live-stream gambar ke server GCS Laptop
        if sio.connected:
            ret_enc, jpeg = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret_enc:
                try:
                    img_base64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
                    sio.emit('pi_camera_feed', {
                        'camera': 'bottom',
                        'image': img_base64
                    })
                except Exception:
                    pass

        time.sleep(0.033)  # ~30 FPS

    cap.release()
    try:
        sio.disconnect()
    except Exception:
        pass

    # ─── Hitung Kalibrasi Kamera ──────────────────────────────────────────────
    if n_captures < 5:
        print(f"\n[!] Batal: Jumlah capture terlalu sedikit ({n_captures}). Butuh minimal 5.")
        sys.exit(1)

    print(f"\n[*] Memulai kalkulasi kalibrasi dari {n_captures} gambar...")
    ret_rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, (320, 240), None, None
    )

    print(f"[+] RMS Reprojection Error: {ret_rms:.4f} px")
    if ret_rms < 0.5:
        print("    ✓ Sangat Presisi (< 0.5px)")
    elif ret_rms < 1.0:
        print("    ✓ Cukup Bagus (< 1.0px)")
    else:
        print("    ⚠ Kurang Akurat (> 1.0px) - disarankan kalibrasi ulang dengan sudut lebih bervariasi")

    # Simpan hasil secara lokal ke file npz
    npz_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_params.npz")
    np.savez(npz_path,
             camera_matrix=camera_matrix,
             dist_coeffs=dist_coeffs,
             rms=ret_rms)
    print(f"[✓] Parameter disimpan di: {npz_path}")

    # Print hasil siap pakai
    fx = camera_matrix[0, 0]
    fy = camera_matrix[1, 1]
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]
    d  = dist_coeffs.flatten()

    print("\n" + "=" * 55)
    print("  TEMPEL PARAMETER BERIKUT (JIKA INGIN SECARA MANUAL):")
    print("=" * 55)
    print(f"""
CAMERA_MATRIX = np.array([
    [{fx:.4f}, 0,        {cx:.4f}],
    [0,        {fy:.4f}, {cy:.4f}],
    [0,        0,        1       ]
], dtype=np.float64)

DIST_COEFFS = np.array([[{d[0]:.6f}, {d[1]:.6f}, {d[2]:.6f}, {d[3]:.6f}, {d[4]:.6f}]],
                        dtype=np.float64)
""")
    print("=" * 55 + "\n")