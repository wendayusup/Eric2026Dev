#!/bin/bash
# test_camera.sh — Script pengujian fungsionalitas dual camera di Raspberry Pi

BOLD='\033[1m'
GREEN='\033[92m'
RED='\033[91m'
YELLOW='\033[93m'
CYAN='\033[96m'
RESET='\033[0m'

echo -e "${CYAN}${BOLD}━━━ RASPBERRY PI HARDWARE CAMERA FUNCTIONALITY TEST ━━━${RESET}"
echo ""

# 1. Periksa Device V4L2 di Kernel
echo -e "${BOLD}[1/3] Memeriksa Perangkat Kamera (/dev/video*)...${RESET}"
if ls /dev/video* >/dev/null 2>&1; then
    echo -e "  ${GREEN}[✓] Perangkat video terdeteksi:${RESET}"
    ls -l /dev/video* | awk '{print "      " $9}'
else
    echo -e "  ${RED}[!] TIDAK ADA PERANGKAT VIDEO TERDETEKSI! Periksa kabel USB kamera.${RESET}"
    exit 1
fi

echo ""
if [ -d "/dev/v4l/by-id" ]; then
    echo -e "  ${GREEN}[✓] Perangkat Kamera USB by-id:${RESET}"
    ls -l /dev/v4l/by-id/ | grep -v '^total' | awk '{print "      " $9 " -> " $11}'
else
    echo -e "  ${YELLOW}[!] /dev/v4l/by-id tidak ditemukan. Menggunakan indeks /dev/video standar.${RESET}"
fi

echo ""
# 2. Pengujian Capture Frame dengan Python & OpenCV
echo -e "${BOLD}[2/3] Menguji Tangkapan Frame (OpenCV MJPG 640x360)...${RESET}"

python3 - << 'EOF'
import cv2
import sys
import time
import glob

devices = sorted(glob.glob('/dev/video*'))
if not devices:
    print("  [!] Tidak ada /dev/video* ditemukan.")
    sys.exit(1)

working_cameras = []

for dev in devices:
    try:
        # Coba buka dengan V4L2
        cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(dev)
        
        if not cap.isOpened():
            continue
            
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        
        success = False
        frame_bytes = 0
        w, h = 0, 0
        
        for try_w, try_h in [(640, 480), (640, 360), (1280, 720)]:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, try_w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, try_h)
            for _ in range(3):
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    frame_bytes = frame.nbytes
                    success = True
                    break
                time.sleep(0.03)
            if success:
                break
        
        cap.release()
                h, w = frame.shape[:2]
                frame_bytes = frame.nbytes
                success = True
                break
            time.sleep(0.05)
            
        cap.release()
        
        if success and w > 0 and h > 0:
            print(f"  \033[92m[✓] {dev}: OK! Resolusi: {w}x{h} ({frame_bytes//1024} KB/frame)\033[0m")
            working_cameras.append((dev, w, h))
        else:
            pass
    except Exception as e:
        print(f"  \033[91m[!] Error pada {dev}: {e}\033[0m")

print("")
if len(working_cameras) >= 2:
    print(f"  \033[92m[SUCCESS] DUA KAMERA AKTIF DITEMUKAN: {[c[0] for c in working_cameras]}\033[0m")
elif len(working_cameras) == 1:
    print(f"  \033[93m[WARNING] HANYA 1 KAMERA AKTIF DITEMUKAN: {working_cameras[0][0]}\033[0m")
else:
    print("  \033[91m[ERROR] GAGAL MEMBACA FRAME DARI SELURUH KAMERA!\033[0m")
EOF

echo ""
# 3. Status Service & Log
echo -e "${BOLD}[3/3] Memeriksa Service & Log Sistem Kamera (krti_nodes)...${RESET}"
if systemctl is-active --quiet krti_nodes.service 2>/dev/null; then
    echo -e "  ${GREEN}[✓] Service krti_nodes.service: RUNNING${RESET}"
else
    echo -e "  ${YELLOW}[!] Service krti_nodes.service: STOPPED / INACTIVE${RESET}"
fi

if [ -f "/home/polman/pi_cam.log" ]; then
    echo -e "\n${CYAN}--- Log Terakhir Kamera (tail -15 /home/polman/pi_cam.log) ---${RESET}"
    tail -n 15 /home/polman/pi_cam.log
fi

echo -e "\n${CYAN}━━━ PENGUJIAN SELESAI ━━━${RESET}"
