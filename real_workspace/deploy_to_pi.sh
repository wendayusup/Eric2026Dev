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

# ─── Find Pi IP via ARP ───────────────────────────────────────────────────────
SUBNET=$(ip -o -f inet addr show wlo1 2>/dev/null | awk '{print $4}')
if [ -z "$SUBNET" ]; then
    SUBNET=$(ip -o -f inet addr show | grep -v '127.0.0.1' | head -n 1 | awk '{print $4}')
fi

if [ -z "$SUBNET" ]; then
    echo "[!] Error: No active local IP interface found!"
    exit 1
fi

echo "[*] Detected Subnet: $SUBNET — Fast scanning..."
nmap -sn "$SUBNET" > /dev/null 2>&1

RASPI_IP=""
IP_CANDIDATES=$(ip neigh show | grep -E -i "($TARGET_MAC_1|$TARGET_MAC_2)" | grep -v -i "FAILED" | awk '{print $1}')

for ip in $IP_CANDIDATES; do
    if ping -c 1 -W 1 "$ip" > /dev/null 2>&1; then
        if timeout 2 bash -c "true &>/dev/null > /dev/tcp/$ip/22" > /dev/null 2>&1; then
            RASPI_IP="$ip"
            break
        fi
    fi
done

if [ -z "$RASPI_IP" ]; then
    echo "[!] Pi not found automatically."
    read -p "    Enter Pi IP manually (or Ctrl+C to cancel): " RASPI_IP
    if [ -z "$RASPI_IP" ]; then
        echo "[!] Deployment cancelled."
        exit 1
    fi
fi

echo "[+] Pi found: $RASPI_IP"
echo ""

# ─── Copy files to Pi ─────────────────────────────────────────────────────────
echo "[*] Copying files to $PI_USER@$RASPI_IP:/home/$PI_USER/ ..."

scp -o StrictHostKeyChecking=no \
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
