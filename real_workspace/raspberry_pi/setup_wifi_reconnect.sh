#!/bin/bash
# setup_wifi_reconnect.sh - Menyetel auto-reconnect, custom SSID/Password, dan watchdog Wi-Fi di Raspberry Pi.
# Khusus memantau SSID "discrete" dengan password "wakanda_31".
# Penggunaan:
#   sudo bash setup_wifi_reconnect.sh

if [ "$EUID" -ne 0 ]; then
    echo "[!] Error: Script ini harus dijalankan sebagai root (gunakan sudo)!" >&2
    exit 1
fi

echo "============================================="
echo "[*] Memulai Konfigurasi Stabilitas Wi-Fi..."
echo "    Mendukung SSID Target: 'discrete'"
echo "============================================="

# 1. Pendaftaran SSID dan Password target ke NetworkManager
if systemctl is-active NetworkManager >/dev/null 2>&1; then
    echo "[*] Mendaftarkan profil Wi-Fi 'discrete' ke NetworkManager..."
    
    # Setup profil 'discrete' untuk semua interface Wi-Fi (Internal wlan0 & USB Dongle Antenna)
    nmcli connection delete "discrete" >/dev/null 2>&1
    nmcli connection delete "discrete-usb" >/dev/null 2>&1
    
    # Connection 1: wlan0 (Internal)
    nmcli connection add type wifi con-name "discrete" ifname wlan0 ssid "discrete" >/dev/null 2>&1
    nmcli connection modify "discrete" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "wakanda_31" >/dev/null 2>&1
    nmcli connection modify "discrete" connection.autoconnect yes connection.autoconnect-priority 50 connection.autoconnect-retries 0
    
    # Connection 2: USB Antenna (wlxa4e6155cb715 / wildcard)
    nmcli connection add type wifi con-name "discrete-usb" ifname "*" ssid "discrete" >/dev/null 2>&1
    nmcli connection modify "discrete-usb" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "wakanda_31" >/dev/null 2>&1
    nmcli connection modify "discrete-usb" connection.autoconnect yes connection.autoconnect-priority 100 connection.autoconnect-retries 0
    echo "[✓] Profil 'discrete' didaftarkan untuk Dual Wi-Fi (Internal & USB Antenna)."

    # Matikan power save secara permanen di NetworkManager
    if [ -d "/etc/NetworkManager/conf.d" ]; then
        cat << 'EOF' > /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf
[connection]
wifi.powersave = 2
EOF
    fi
    systemctl restart NetworkManager >/dev/null 2>&1
else
    # Fallback ke wpa_supplicant jika tidak menggunakan NetworkManager
    echo "[*] NetworkManager tidak terdeteksi. Menambahkan ke wpa_supplicant.conf..."
    cat << 'EOF' >> /etc/wpa_supplicant/wpa_supplicant.conf

network={
    ssid="discrete"
    psk="wakanda_31"
    priority=100
}
EOF
    echo "[✓] Profil ditambahkan ke wpa_supplicant.conf."
fi

# Matikan power save Wi-Fi secara langsung untuk sesi ini
iw dev wlan0 set power_save off 2>/dev/null
iwconfig wlan0 power off 2>/dev/null
echo "[✓] Power Saving pada wlan0 dinonaktifkan."

# 2. Membuat script watchdog berkala di /usr/local/bin/wifi_watchdog.sh
echo "[*] Membuat script watchdog (/usr/local/bin/wifi_watchdog.sh)..."
cat << 'EOF' > /usr/local/bin/wifi_watchdog.sh
#!/bin/bash
# wifi_watchdog.sh - Memantau koneksi Wi-Fi secara aman tanpa memutus SSH aktif.

LOG_FILE="/var/log/wifi_watchdog.log"
touch "$LOG_FILE"

# Matikan power save Wi-Fi secara permanen
iw dev wlan0 set power_save off 2>/dev/null
iwconfig wlan0 power off 2>/dev/null

FAIL_COUNT=0

echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Memulai pemantauan Wi-Fi stabil (SSID: discrete)..." >> "$LOG_FILE"

while true; do
    # Selalu pastikan Wi-Fi power save tetap off
    iw dev wlan0 set power_save off 2>/dev/null

    GATEWAY=$(ip route | grep default | awk '{print $3}' | head -n 1)
    
    CONNECTED=false
    if [ -n "$GATEWAY" ]; then
        # Ping gateway dengan 2 paket (timeout 2 detik)
        if ping -c 2 -W 2 "$GATEWAY" > /dev/null 2>&1; then
            CONNECTED=true
        fi
    fi

    if [ "$CONNECTED" = "true" ]; then
        FAIL_COUNT=0
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Peringatan: Ping gateway terputus ($FAIL_COUNT/5)..." >> "$LOG_FILE"

        # Hanya lakukan reconnect jika terputus berturut-turut 5x (~50 detik total)
        if [ "$FAIL_COUNT" -ge 5 ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Koneksi benar-benar terputus 5x berturut-turut. Mencoba reconnect ke 'discrete'..." >> "$LOG_FILE"

            # Hubungkan ulang ke 'discrete-usb' atau 'discrete'
            nmcli connection up "discrete-usb" >/dev/null 2>&1 || nmcli connection up "discrete" >/dev/null 2>&1

            sleep 5
            NEW_GW=$(ip route | grep default | awk '{print $3}' | head -n 1)
            if [ -n "$NEW_GW" ] && ping -c 1 -W 2 "$NEW_GW" > /dev/null 2>&1; then
                echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Berhasil terhubung kembali ke 'discrete'." >> "$LOG_FILE"
                FAIL_COUNT=0
            else
                echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Reconnect gagal. Mereload NetworkManager..." >> "$LOG_FILE"
                nmcli connection reload >/dev/null 2>&1
                FAIL_COUNT=0
            fi
        fi
    fi

    # Cek setiap 10 detik agar tidak membebani antarmuka Wi-Fi
    sleep 10
done
EOF

chmod +x /usr/local/bin/wifi_watchdog.sh
echo "[✓] Script watchdog selesai dibuat."

# 3. Membuat systemd service untuk watchdog agar berjalan di background secara persisten
echo "[*] Membuat systemd service untuk watchdog..."
cat << 'EOF' > /etc/systemd/system/wifi_watchdog.service
[Unit]
Description=Wi-Fi Auto-Reconnect Watchdog (discrete)
After=network.target

[Service]
Type=simple
ExecStart=/bin/bash /usr/local/bin/wifi_watchdog.sh
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 4. Hapus cron job lama agar tidak double
rm -f /etc/cron.d/wifi_watchdog

# Aktifkan dan jalankan watchdog service
systemctl daemon-reload
systemctl enable wifi_watchdog.service
systemctl restart wifi_watchdog.service

echo "============================================="
echo "[✓] SETUP SELESAI!"
echo "Watchdog hanya dikhususkan untuk SSID 'discrete'."
echo "============================================="
