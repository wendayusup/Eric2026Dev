#!/bin/bash
# start_nodes.sh — Startup script untuk semua node KRTI 2026 di Raspberry Pi
# Jalankan via systemd (krti_nodes.service) atau manual: bash start_nodes.sh

LOG_DIR="/home/polman"

# Pastikan proses lama mati agar tidak ada bentrokan port/kamera
echo "[*] Cleaning up old Python processes..."
killall -9 python3 2>/dev/null

# [FIX] Restart pigpiod menggunakan timer PWM (-t 0) alih-alih PCM (default)
# Ini wajib karena GPIO 19 bentrok dengan hardware PCM Raspberry Pi yang bikin bug/crash!
echo "[*] Securing pigpio driver..."
if [ "$(id -u)" -ne 0 ]; then
    SUDO=sudo
else
    SUDO=
fi
$SUDO systemctl stop pigpiod 2>/dev/null
$SUDO killall -9 pigpiod 2>/dev/null
$SUDO pigpiod

sleep 1

# Node-node KRTI 2026 berjalan 100% independen (tanpa butuh Wi-Fi)
# Jika Wi-Fi ada, Socket.IO akan otomatis terhubung ke Web GCS di background.

# Jalankan node node secara stabil dan dipisah, bukan memaksa semua proses berhenti jika satu gagal
# Node 1: LED Status Indicator

echo "[*] Menjalankan Node LED..."
python3 -u "$LOG_DIR/pi_led_node.py" > "$LOG_DIR/pi_led.log" 2>&1 &

# Node 2: Kamera & Vision

echo "[*] Menjalankan Node Kamera & Vision..."
python3 -u "$LOG_DIR/pi_cam_node.py" > "$LOG_DIR/pi_cam.log" 2>&1 &

# Node 3: Servo via Socket.IO

echo "[*] Menjalankan Node Servo (Socket.IO)..."
python3 -u "$LOG_DIR/pi_servo_node.py" > "$LOG_DIR/pi_servo.log" 2>&1 &

echo "[✓] Semua node KRTI 2026 berhasil dijalankan di background!"
echo "    Log kamera : $LOG_DIR/pi_cam.log"
echo "    Log servo  : $LOG_DIR/pi_servo.log"
echo "    Log LED    : $LOG_DIR/pi_led.log"

# Tunggu anak proses, tapi jangan mematikan service jika satu node crash
wait -n
exit 0
