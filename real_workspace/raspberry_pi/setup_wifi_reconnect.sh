#!/bin/bash
# setup_wifi_reconnect.sh - Menyetel auto-reconnect, custom SSID/Password, dan watchdog Wi-Fi di Raspberry Pi.
# Memantau SSID "discrete" dan "wakanda_31" setiap 3 detik.
# Penggunaan:
#   sudo bash setup_wifi_reconnect.sh

if [ "$EUID" -ne 0 ]; then
    echo "[!] Error: Script ini harus dijalankan sebagai root (gunakan sudo)!" >&2
    exit 1
fi

echo "============================================="
echo "[*] Memulai Konfigurasi Stabilitas Wi-Fi..."
echo "    Mendukung SSID: 'discrete' & 'wakanda_31'"
echo "============================================="

# 1. Pendaftaran SSID dan Password target ke NetworkManager
if systemctl is-active NetworkManager >/dev/null 2>&1; then
    echo "[*] Mendaftarkan profil Wi-Fi ke NetworkManager..."
    
    # Setup profil 'discrete'
    nmcli connection delete "discrete" >/dev/null 2>&1
    nmcli connection add type wifi con-name "discrete" ifname wlan0 ssid "discrete" >/dev/null 2>&1
    nmcli connection modify "discrete" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "wakanda_31" >/dev/null 2>&1
    nmcli connection modify "discrete" connection.autoconnect yes connection.autoconnect-priority 100 connection.autoconnect-retries 0
    echo "[✓] Profil 'discrete' didaftarkan (Prioritas: TINGGI)."

    # Setup profil 'wakanda_31'
    nmcli connection delete "wakanda_31" >/dev/null 2>&1
    nmcli connection add type wifi con-name "wakanda_31" ifname wlan0 ssid "wakanda_31" >/dev/null 2>&1
    nmcli connection modify "wakanda_31" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "wakanda_31" >/dev/null 2>&1
    nmcli connection modify "wakanda_31" connection.autoconnect yes connection.autoconnect-priority 90 connection.autoconnect-retries 0
    echo "[✓] Profil 'wakanda_31' didaftarkan (Prioritas: SEDANG)."

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

network={
    ssid="wakanda_31"
    psk="wakanda_31"
    priority=90
}
EOF
    echo "[✓] Profil ditambahkan ke wpa_supplicant.conf."
fi

# Matikan power save Wi-Fi secara langsung untuk sesi ini
iw dev wlan0 set power_save off 2>/dev/null
iwconfig wlan0 power off 2>/dev/null
echo "[✓] Power Saving pada wlan0 dinonaktifkan."

# 2. Membuat script watchdog loop 3 detik di /usr/local/bin/wifi_watchdog.sh
echo "[*] Membuat script watchdog (/usr/local/bin/wifi_watchdog.sh)..."
cat << 'EOF' > /usr/local/bin/wifi_watchdog.sh
#!/bin/bash
# wifi_watchdog.sh - Memantau koneksi Wi-Fi dan memastikan terhubung ke 'discrete' atau 'wakanda_31' setiap 3 detik.

LOG_FILE="/var/log/wifi_watchdog.log"
touch "$LOG_FILE"

# Matikan power save Wi-Fi secara berkala
iw dev wlan0 set power_save off 2>/dev/null
iwconfig wlan0 power off 2>/dev/null

echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Memulai pemantauan Wi-Fi..." >> "$LOG_FILE"

while true; do
    # Cek SSID aktif saat ini
    ACTIVE_SSID=$(nmcli -t -f active,ssid dev wifi | grep '^yes' | cut -d: -f2 | head -n 1)
    GATEWAY=$(ip route | grep default | awk '{print $3}' | head -n 1)
    
    IS_CONNECTED=false
    if [ "$ACTIVE_SSID" = "discrete" ] || [ "$ACTIVE_SSID" = "wakanda_31" ]; then
        if [ -n "$GATEWAY" ]; then
            # Ping cepat ke gateway
            ping -c 1 -W 1 "$GATEWAY" > /dev/null 2>&1
            if [ $? -eq 0 ]; then
                IS_CONNECTED=true
            fi
        fi
    fi
    
    if [ "$IS_CONNECTED" = "false" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Koneksi terputus! (SSID aktif: '$ACTIVE_SSID'). Mencoba menyambungkan kembali..." >> "$LOG_FILE"
        
        # Scan AP sekitar
        nmcli device wifi rescan >/dev/null 2>&1
        sleep 2
        
        # Ambil daftar SSID terdekat
        SSIDS_AVAILABLE=$(nmcli -t -f ssid dev wifi list | grep -E "^(discrete|wakanda_31)$")
        
        CONNECTED=false
        
        # Coba hubungkan ke discrete jika ada
        if echo "$SSIDS_AVAILABLE" | grep -q "discrete"; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Menemukan SSID 'discrete'. Menghubungkan..." >> "$LOG_FILE"
            nmcli connection up "discrete" >/dev/null 2>&1
            if [ $? -eq 0 ]; then
                echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Berhasil menyambungkan ulang ke 'discrete'." >> "$LOG_FILE"
                CONNECTED=true
            fi
        fi
        
        # Coba hubungkan ke wakanda_31 jika discrete tidak ada atau gagal
        if [ "$CONNECTED" = "false" ] && echo "$SSIDS_AVAILABLE" | grep -q "wakanda_31"; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Menemukan SSID 'wakanda_31'. Menghubungkan..." >> "$LOG_FILE"
            nmcli connection up "wakanda_31" >/dev/null 2>&1
            if [ $? -eq 0 ]; then
                echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Berhasil menyambungkan ulang ke 'wakanda_31'." >> "$LOG_FILE"
                CONNECTED=true
            fi
        fi
        
        # Jika keduanya gagal/tidak ada, reset modul wifi
        if [ "$CONNECTED" = "false" ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Tidak ada target SSID yang tersedia atau gagal terhubung. Mereset interface..." >> "$LOG_FILE"
            nmcli radio wifi off
            sleep 2
            nmcli radio wifi on
            sleep 5
        fi
    fi
    
    sleep 3
done
EOF

chmod +x /usr/local/bin/wifi_watchdog.sh
echo "[✓] Script watchdog selesai dibuat."

# 3. Membuat systemd service untuk watchdog agar berjalan di background secara persisten
echo "[*] Membuat systemd service untuk watchdog..."
cat << 'EOF' > /etc/systemd/system/wifi_watchdog.service
[Unit]
Description=Wi-Fi Auto-Reconnect Watchdog
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
echo "Watchdog berjalan sebagai systemd service."
echo "Log dapat dilihat di: /var/log/wifi_watchdog.log atau journalctl -u wifi_watchdog"
echo "============================================="
