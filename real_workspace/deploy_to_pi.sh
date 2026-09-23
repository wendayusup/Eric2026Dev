#!/bin/bash
# deploy_to_pi.sh — Deploy latest ERIC code to Raspberry Pi
# Usage: bash deploy_to_pi.sh

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

TARGET_MAC_1="e4:5f:01:90:51:8d"  # Internal WiFi wlan0
TARGET_MAC_2="a4:e6:15:5c:b7:15"  # RTL8188ETV USB WiFi
PI_USER="polman"

echo "======================================================="
echo "   ERIC 2026 — DEPLOY TO RASPBERRY PI"
echo "======================================================="

# Ask sudo password upfront — avoids interactive SSH sudo timeout
read -s -p "[?] Enter Pi sudo password (for $PI_USER): " PI_SUDO_PASS
echo ""
echo ""

echo "[*] Searching for Raspberry Pi IP..."

# Helper function to verify if an IP is active and has SSH port 22 open
check_ssh_ready() {
    local target_ip="$1"
    [ -z "$target_ip" ] && return 1
    ping -c 1 -W 1 "$target_ip" > /dev/null 2>&1 || return 1
    timeout 3 bash -c "true &>/dev/null > /dev/tcp/$target_ip/22" > /dev/null 2>&1
}

# ─── Find Pi IP ──────────────────────────────────────────────────────────────
RASPI_IP=""

# Method 0: Check cached IP from connect_raspi.sh or GCS node session first
SAVED_IP=""
if [ -f "/tmp/last_pi_ip.txt" ]; then
    SAVED_IP=$(cat /tmp/last_pi_ip.txt 2>/dev/null | tr -d ' \n\r')
    if check_ssh_ready "$SAVED_IP"; then
        RASPI_IP="$SAVED_IP"
        echo "[+] Detected Pi IP from saved session cache: $RASPI_IP"
    fi
fi

# Detect Subnet for scanning if needed
FULL_SUBNET=$(ip -o -f inet addr show wlo1 2>/dev/null | awk '{print $4}')
if [ -z "$FULL_SUBNET" ]; then
    FULL_SUBNET=$(ip -o -f inet addr show | grep -v '127.0.0.1' | head -n 1 | awk '{print $4}')
fi

SUBNET_PREFIX=$(echo "$FULL_SUBNET" | cut -d/ -f1 | cut -d. -f1-3)
if [ -z "$SUBNET_PREFIX" ]; then
    SUBNET_PREFIX=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
fi
SUBNET="${SUBNET_PREFIX}.0/24"

# Method 1: Check MAC match from ARP table (exact match like connect_raspi.sh)
if [ -z "$RASPI_IP" ]; then
    echo "[*] Detected Subnet: $SUBNET — Scanning for Pi via MAC address..."
    if command -v nmap >/dev/null 2>&1; then
        nmap -sn "$SUBNET" > /dev/null 2>&1
    fi

    MAC_CANDIDATES=$(ip neigh show | grep -E -i "($TARGET_MAC_1|$TARGET_MAC_2)" | grep -v -i "FAILED" | awk '{print $1}')
    for ip in $MAC_CANDIDATES; do
        if check_ssh_ready "$ip"; then
            RASPI_IP="$ip"
            echo "[+] Detected Pi IP via MAC address ARP scan: $RASPI_IP"
            break
        fi
    done
fi

# Method 2: Check active GCS connection on port 5000
if [ -z "$RASPI_IP" ]; then
    SOCKET_IPS=$(ss -H -tn state established '( sport = :5000 )' 2>/dev/null | awk '{print $4}' | cut -d: -f1 | grep -v '127.0.0.1' | sort -u)
    for ip in $SOCKET_IPS; do
        if check_ssh_ready "$ip"; then
            RASPI_IP="$ip"
            echo "[+] Detected Pi IP from active Web GCS connection: $RASPI_IP"
            break
        fi
    done
fi

# Method 3: Check SSH hostnames (polman.local, raspberrypi.local)
if [ -z "$RASPI_IP" ]; then
    for host in "polman.local" "raspberrypi.local"; do
        HOST_IP=$(getent hosts "$host" 2>/dev/null | awk '{print $1}')
        if [ -n "$HOST_IP" ] && check_ssh_ready "$HOST_IP"; then
            RASPI_IP="$HOST_IP"
            echo "[+] Detected Pi IP via MDNS hostname ($host): $RASPI_IP"
            break
        fi
    done
fi

# Method 4: Broadcast ping & auto-retry scan (same retry mechanism as connect_raspi.sh)
if [ -z "$RASPI_IP" ]; then
    echo "[*] Trying broadcast ping & auto-retry scan..."
    ping -b -c 1 255.255.255.255 > /dev/null 2>&1
    for i in $(seq 1 6); do
        sleep 3
        if command -v nmap >/dev/null 2>&1; then
            nmap -sn "$SUBNET" > /dev/null 2>&1
        fi
        MAC_CANDIDATES=$(ip neigh show | grep -E -i "($TARGET_MAC_1|$TARGET_MAC_2)" | grep -v -i "FAILED" | awk '{print $1}')
        for ip in $MAC_CANDIDATES; do
            if check_ssh_ready "$ip"; then
                RASPI_IP="$ip"
                echo "[+] Detected Pi IP via MAC retry scan: $RASPI_IP"
                break 2
            fi
        done
    done
fi

if [ -z "$RASPI_IP" ]; then
    echo "[!] Pi not found automatically on Wi-Fi ($SUBNET)."
    if [ -n "$SAVED_IP" ]; then
        read -p "    Enter Pi IP manually [Default: $SAVED_IP]: " INPUT_IP
        RASPI_IP="${INPUT_IP:-$SAVED_IP}"
    else
        read -p "    Enter Pi IP manually: " RASPI_IP
    fi

    if [ -z "$RASPI_IP" ]; then
        echo "[!] Deployment cancelled."
        exit 1
    fi
fi

# Save found IP for subsequent runs
echo "$RASPI_IP" > /tmp/last_pi_ip.txt 2>/dev/null

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
    -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=3 \
    raspberry_pi/pi_cam_node.py \
    raspberry_pi/pi_servo_node.py \
    raspberry_pi/pi_led_node.py \
    raspberry_pi/start_nodes.sh \
    raspberry_pi/eric_nodes.service \
    raspberry_pi/setup_wifi_reconnect.sh \
    raspberry_pi/setup_wifi_failover.sh \
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
    -o UserKnownHostsFile=/dev/null \
    -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=6 \
    -o ConnectTimeout=15 \
    "$PI_USER@$RASPI_IP" \
    "echo '$PI_SUDO_PASS' | sudo -S bash -c '
        echo \"[1/6] Setting executable permissions...\"
        chmod +x /home/polman/start_nodes.sh /home/polman/pi_cam_node.py /home/polman/pi_servo_node.py /home/polman/setup_wifi_reconnect.sh /home/polman/setup_wifi_failover.sh
        
        echo \"[2/6] Installing system packages (python3-pip, opencv, socketio)...\"
        apt update -y
        apt install -y python3-pip python3-opencv python3-socketio python3-websocket net-tools network-manager || pip3 install opencv-python python-socketio websocket-client
        
        echo \"[4/6] Setting up dual Wi-Fi antenna failover & auto-reconnect...\"
        bash /home/polman/setup_wifi_failover.sh
        bash /home/polman/setup_wifi_reconnect.sh
        
        echo \"[5/6] Registering eric_nodes.service...\"
        cp /home/polman/eric_nodes.service /etc/systemd/system/
        systemctl daemon-reload
        systemctl enable eric_nodes.service
        systemctl restart eric_nodes.service
        
        echo \"[6/6] Verifying eric_nodes.service status...\"
        systemctl status eric_nodes.service --no-pager | head -20
    '"

SSH_EXIT=$?

if [ $SSH_EXIT -eq 0 ]; then
    echo ""
    echo "[*] Reading camera and servo logs..."
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$PI_USER@$RASPI_IP" \
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
    echo "    Then run:     sudo systemctl restart eric_nodes.service"
    exit 1
fi
