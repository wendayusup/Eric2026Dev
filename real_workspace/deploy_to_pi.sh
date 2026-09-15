#!/bin/bash
# deploy_to_pi.sh — Deploy latest KRTI code to Raspberry Pi
# Usage: bash deploy_to_pi.sh

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

TARGET_MAC_1="e4:5f:01:90:51:8d"  # Internal WiFi wlan0
TARGET_MAC_2="a4:e6:15:5c:b7:15"  # RTL8188ETV USB WiFi
PI_USER="polman"

echo "======================================================="
echo "   KRTI 2026 — DEPLOY TO RASPBERRY PI"
echo "======================================================="

# Ask sudo password upfront — avoids interactive SSH sudo timeout
read -s -p "[?] Enter Pi sudo password (for $PI_USER): " PI_SUDO_PASS
echo ""
echo ""

echo "[*] Searching for Raspberry Pi IP..."

# ─── Find Pi IP via ARP + SSH Port 22 Scan + Hostname ─────────────────────
SUBNET_PREFIX=$(ip -o -f inet addr show wlo1 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | cut -d. -f1-3)
if [ -z "$SUBNET_PREFIX" ]; then
    SUBNET_PREFIX=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
fi
SUBNET="${SUBNET_PREFIX}.0/24"
echo "[*] Detected Subnet: $SUBNET — Fast scanning for Pi..."

# Fast scan port 22 across subnet to populate ARP and find SSH servers
SSH_IPS=$(bash -c '
for i in $(seq 1 254); do
    ip="'$SUBNET_PREFIX'.$i"
    (timeout 0.2 bash -c "echo > /dev/tcp/$ip/22" 2>/dev/null && echo "$ip") &
done
wait
')

RASPI_IP=""

# Method 0: Check active GCS connection on port 5000 or saved IP (must match current subnet)
if [ -z "$RASPI_IP" ]; then
    SOCKET_IPS=$(ss -H -tn state established '( sport = :5000 )' 2>/dev/null | awk '{print $4}' | cut -d: -f1 | grep -v '127.0.0.1' | sort -u)
    for ip in $SOCKET_IPS; do
        if [ -n "$SUBNET_PREFIX" ] && [[ "$ip" == "$SUBNET_PREFIX"* ]]; then
            if timeout 1 bash -c "echo > /dev/tcp/$ip/22" > /dev/null 2>&1; then
                RASPI_IP="$ip"
                echo "[+] Detected Pi IP from active Web GCS connection: $RASPI_IP"
                break
            fi
        fi
    done
fi

if [ -z "$RASPI_IP" ] && [ -f "/tmp/last_pi_ip.txt" ]; then
    SAVED_IP=$(cat /tmp/last_pi_ip.txt 2>/dev/null | tr -d ' \n\r')
    if [ -n "$SAVED_IP" ] && [ -n "$SUBNET_PREFIX" ] && [[ "$SAVED_IP" == "$SUBNET_PREFIX"* ]]; then
        if timeout 1 bash -c "echo > /dev/tcp/$SAVED_IP/22" > /dev/null 2>&1; then
            RASPI_IP="$SAVED_IP"
            echo "[+] Detected Pi IP from saved Web GCS session: $RASPI_IP"
        fi
    fi
fi

# Method 1: Check MAC match from ARP table or test candidates on current subnet
if [ -z "$RASPI_IP" ]; then
    MAC_CANDIDATES=$(ip neigh show | grep -E -i "($TARGET_MAC_1|$TARGET_MAC_2)" | grep -v -i "FAILED" | awk '{print $1}')
    for ip in $MAC_CANDIDATES; do
        if timeout 1 bash -c "echo > /dev/tcp/$ip/22" > /dev/null 2>&1; then
            RASPI_IP="$ip"
            echo "[+] Detected Pi IP via network/ARP scan: $RASPI_IP"
            break
        fi
    done
fi

# Method 2: Check SSH hostnames (polman.local, raspberrypi.local)
if [ -z "$RASPI_IP" ]; then
    for host in "polman.local" "raspberrypi.local"; do
        HOST_IP=$(getent hosts "$host" 2>/dev/null | awk '{print $1}')
        if [ -n "$HOST_IP" ]; then
            if timeout 1 bash -c "echo > /dev/tcp/$HOST_IP/22" > /dev/null 2>&1; then
                RASPI_IP="$HOST_IP"
                break
            fi
        fi
    done
fi

# Method 3: Pick candidate from SSH Port 22 scan (exclude laptop own IP)
if [ -z "$RASPI_IP" ]; then
    MY_IP=$(hostname -I | awk '{print $1}')
    for ip in $SSH_IPS; do
        if [ "$ip" != "$MY_IP" ]; then
            RASPI_IP="$ip"
            break
        fi
    done
fi

if [ -z "$RASPI_IP" ]; then
    echo "[!] Pi not found automatically on Wi-Fi ($SUBNET)."
    echo "    (Please check if Raspberry Pi is powered ON and connected to hotspot)"
    read -p "    Enter Pi IP manually (or press Enter to retry): " RASPI_IP
    if [ -z "$RASPI_IP" ]; then
        echo "[!] Deployment cancelled."
        exit 1
    fi
fi

echo "[+] Pi found: $RASPI_IP"
echo ""

CURRENT_LAPTOP_IP=$(ip -o -f inet addr show wlo1 2>/dev/null | awk '{print $4}' | cut -d/ -f1)
if [ -z "$CURRENT_LAPTOP_IP" ]; then
    CURRENT_LAPTOP_IP=$(hostname -I | awk '{print $1}')
fi
if [ -n "$CURRENT_LAPTOP_IP" ]; then
    echo "[*] Injecting Laptop GCS IP ($CURRENT_LAPTOP_IP) into Pi nodes..."
    sed -i "s/LAPTOP_IP[[:space:]]*=[[:space:]]*\".*\"/LAPTOP_IP = \"$CURRENT_LAPTOP_IP\"/g" raspberry_pi/pi_cam_node.py
    sed -i "s/LAPTOP_IP[[:space:]]*=[[:space:]]*\".*\"/LAPTOP_IP = \"$CURRENT_LAPTOP_IP\"/g" raspberry_pi/pi_servo_node.py
fi

# ─── Copy files to Pi ─────────────────────────────────────────────────────────
echo "[*] Copying files to $PI_USER@$RASPI_IP:/home/$PI_USER/ ..."

scp -o StrictHostKeyChecking=no \
    -o ConnectTimeout=3 \
    raspberry_pi/pi_cam_node.py \
    raspberry_pi/pi_servo_node.py \
    raspberry_pi/pi_led_node.py \
    raspberry_pi/start_nodes.sh \
    raspberry_pi/krti_nodes.service \
    "$PI_USER@$RASPI_IP:/home/$PI_USER/"

if [ $? -ne 0 ]; then
    echo "[!] FAILED to copy files to Pi. Check SSH connection."
    exit 1
fi
echo "[+] Files copied successfully."
echo ""

# ─── Remote setup on Pi (non-interactive sudo via -S) ─────────────────────────
echo "[*] Configuring services and permissions on Pi..."

ssh -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=6 \
    -o ConnectTimeout=15 \
    "$PI_USER@$RASPI_IP" \
    "echo '$PI_SUDO_PASS' | sudo -S bash -c '
        chmod +x /home/polman/start_nodes.sh /home/polman/pi_cam_node.py /home/polman/pi_servo_node.py
        cp /home/polman/krti_nodes.service /etc/systemd/system/
        systemctl daemon-reload
        systemctl enable krti_nodes.service
        systemctl restart krti_nodes.service
        echo SERVICE_OK
    ' && systemctl status krti_nodes.service --no-pager | head -20"

SSH_EXIT=$?

if [ $SSH_EXIT -eq 0 ]; then
    echo ""
    echo "[*] Reading camera and servo logs..."
    ssh -o StrictHostKeyChecking=no "$PI_USER@$RASPI_IP" \
        "echo '  [Pi] Camera log (last 20 lines):' && (tail -20 /home/polman/pi_cam.log 2>/dev/null || echo '  (log empty)') && echo '' && echo '  [Pi] Servo log (last 20 lines):' && (tail -20 /home/polman/pi_servo.log 2>/dev/null || echo '  (log empty)')"

    echo ""
    echo "======================================================="
    echo "[+] DEPLOYMENT COMPLETE! Raspberry Pi is Plug & Play."
    echo "    Pi IP    : $RASPI_IP"
    echo "    GCS URL  : http://$(hostname -I | awk '{print $1}'):5000"
    echo ""
    echo "    To tail logs on Pi:"
    echo "    ssh $PI_USER@$RASPI_IP 'tail -f /home/$PI_USER/pi_cam.log'"
    echo "======================================================="
else
    echo ""
    echo "[!] Error during remote setup."
    echo "    Try manually: ssh $PI_USER@$RASPI_IP"
    echo "    Then run:     sudo systemctl restart krti_nodes.service"
    exit 1
fi
