#!/bin/bash
TARGET_MAC_1="e4:5f:01:90:51:8d"  # Internal WiFi wlan0
TARGET_MAC_2="a4:e6:15:5c:b7:15"  # RTL8188ETV USB WiFi

echo "[*] Searching for Raspberry Pi IP via MAC Addresses..."
echo "    - Internal: $TARGET_MAC_1"
echo "    - USB:      $TARGET_MAC_2"

# Get subnet of wlo1 (or active wifi interface)
SUBNET=$(ip -o -f inet addr show wlo1 2>/dev/null | awk '{print $4}')
if [ -z "$SUBNET" ]; then
    # If wlo1 is inactive, find another active network interface
    SUBNET=$(ip -o -f inet addr show | grep -v '127.0.0.1' | head -n 1 | awk '{print $4}')
fi

if [ -z "$SUBNET" ]; then
    echo "[!] Error: No active local IP interface found!"
    exit 1
fi

echo "[*] Detected Subnet: $SUBNET"
echo "[*] Performing fast network scan with nmap..."

# Perform quick ping scan
nmap -sn "$SUBNET" > /dev/null

# Search for IP in ARP / neighbors table
IP_CANDIDATES=$(ip neigh show | grep -E -i "($TARGET_MAC_1|$TARGET_MAC_2)" | grep -v -i "FAILED" | awk '{print $1}')

RASPI_IP=""
for ip in $IP_CANDIDATES; do
    # 1. Ensure device is online (responds to ping)
    if ping -c 1 -W 1 "$ip" > /dev/null 2>&1; then
        # 2. Ensure port 22 (SSH) is open and ready
        if timeout 3 bash -c "true &>/dev/null > /dev/tcp/$ip/22" >/dev/null 2>&1; then
            RASPI_IP="$ip"
            break
        fi
    fi
done

if [ -z "$RASPI_IP" ]; then
    # Try broadcast ping if not in ARP table
    echo "[*] Trying broadcast ping method..."
    ping -b -c 1 255.255.255.255 > /dev/null 2>&1
    IP_CANDIDATES=$(ip neigh show | grep -E -i "($TARGET_MAC_1|$TARGET_MAC_2)" | grep -v -i "FAILED" | awk '{print $1}')
    for ip in $IP_CANDIDATES; do
        if ping -c 1 -W 1 "$ip" > /dev/null 2>&1; then
            if timeout 3 bash -c "true &>/dev/null > /dev/tcp/$ip/22" >/dev/null 2>&1; then
                RASPI_IP="$ip"
                break
            fi
        fi
    done
fi

if [ -z "$RASPI_IP" ]; then
    echo "[*] SSH not ready, auto-waiting (max 60 seconds)..."
    for i in $(seq 1 12); do
        sleep 5
        printf "[*] Retrying... (%d/12)\r" "$i"
        IP_CANDIDATES=$(ip neigh show | grep -E -i "($TARGET_MAC_1|$TARGET_MAC_2)" | grep -v -i "FAILED" | awk '{print $1}')
        for ip in $IP_CANDIDATES; do
            if timeout 3 bash -c "true &>/dev/null > /dev/tcp/$ip/22" >/dev/null 2>&1; then
                RASPI_IP="$ip"
                break 2
            fi
        done
    done
fi

if [ -z "$RASPI_IP" ]; then
    echo ""
    echo "[!] Raspberry Pi could not be reached after 60 seconds."
    echo "    Make sure the Pi is powered on and connected to WiFi."
    exit 1
fi

echo "$RASPI_IP" > /tmp/last_pi_ip.txt 2>/dev/null
echo "[+] Found! Raspberry Pi IP active & SSH Ready: $RASPI_IP"
echo "[*] Connecting to SSH polman@$RASPI_IP..."
ssh -t \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o ServerAliveInterval=5 \
    -o ServerAliveCountMax=60 \
    "polman@$RASPI_IP"
