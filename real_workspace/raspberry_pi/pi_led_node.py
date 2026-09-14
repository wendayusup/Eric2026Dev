#!/usr/bin/env python3
import time
import socket
import os
import subprocess
import threading

# Configuration
USE_ONBOARD_LED = False  # Set ke True untuk memakai LED ACT bawaan Raspi
LED_GPIO_PIN = 27        # Pin GPIO untuk LED eksternal (jika USE_ONBOARD_LED = False)
LAPTOP_IP = "10.250.27.76" # Dynamic fallback untuk discrete/wakanda

# LED nyala saat koneksi Wi-Fi/GCS terdeteksi, mati/berkedip saat tidak ada koneksi

# Inisialisasi GPIO jika menggunakan LED Eksternal
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED_GPIO_PIN, GPIO.OUT)
    GPIO_AVAILABLE = True
    print(f"[+] LED Node: GPIO LED eksternal berhasil diinisialisasi pada BCM Pin {LED_GPIO_PIN}.")
except ImportError:
    GPIO_AVAILABLE = False
    print("[!] LED Node: RPi.GPIO tidak tersedia, berjalan dalam mode mock/onboard saja.")

# Fungsi kontrol LED
def set_led_state(state):
    """state: True untuk menyala (ON), False untuk mati (OFF)"""
    if USE_ONBOARD_LED:
        # Menulis ke brightness LED ACT Raspi (membutuhkan sudo)
        try:
            # Matikan trigger bawaan disk activity jika belum
            if not os.path.exists("/tmp/act_led_configured"):
                os.system("echo none | sudo tee /sys/class/leds/ACT/trigger > /dev/null 2>&1")
                # Jika fail (misal Raspberry Pi 5 memakai led0/PWR), sesuaikan:
                os.system("echo none | sudo tee /sys/class/leds/led0/trigger > /dev/null 2>&1")
                with open("/tmp/act_led_configured", "w") as f:
                    f.write("configured")

            val = "1" if state else "0"
            os.system(f"echo {val} | sudo tee /sys/class/leds/ACT/brightness > /dev/null 2>&1")
            os.system(f"echo {val} | sudo tee /sys/class/leds/led0/brightness > /dev/null 2>&1")
        except Exception:
            pass
    else:
        if GPIO_AVAILABLE:
            GPIO.output(LED_GPIO_PIN, GPIO.HIGH if state else GPIO.LOW)
        else:
            # Mock mode jika dijalankan di laptop
            pass

# Fungsi pendeteksian IP GCS
def find_gcs_ip():
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
                        return ip
                    sock.close()
    except Exception:
        pass

    # 2. Coba mDNS hostname laptop (f15.local)
    try:
        ip = socket.gethostbyname("f15.local")
        return ip
    except Exception:
        pass

    return LAPTOP_IP

if __name__ == '__main__':
    print("[+] LED Node: Berjalan.")
    last_ping_time = 0
    gcs_online = False

    try:
        while True:
            now = time.time()
            # Lakukan cek koneksi setiap 3 detik
            if now - last_ping_time > 3.0:
                last_ping_time = now
                LAPTOP_IP = find_gcs_ip()
                # Uji koneksi dengan ping cepat
                ping_check = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", LAPTOP_IP],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                gcs_online = (ping_check.returncode == 0)
                print(f"[LED Status] GCS Online: {gcs_online} (Target IP: {LAPTOP_IP})")

            # Pola LED: solid saat Wi-Fi/GCS terhubung, berkedip per detik saat terputus/mencari
            if gcs_online:
                set_led_state(True)
                time.sleep(1.0)
            else:
                set_led_state(True)
                time.sleep(0.5)
                set_led_state(False)
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("[-] LED Node: Dihentikan.")
        if GPIO_AVAILABLE:
            GPIO.cleanup()
