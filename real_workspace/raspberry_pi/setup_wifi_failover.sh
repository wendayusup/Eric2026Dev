#!/bin/bash
# setup_wifi_failover.sh
# Sets up automatic failover from internal Wi-Fi to USB Wi-Fi on the Raspberry Pi

echo "[*] Setting up Wi-Fi Switcher script..."

cat << 'EOF' | sudo tee /usr/local/bin/wifi_switch.sh > /dev/null
#!/bin/bash
# wifi_switch.sh - Triggered by udev when Realtek USB Wi-Fi is plugged/unplugged

ACTION=$1

if [ "$ACTION" == "add" ]; then
    echo "[$(date)] USB Wi-Fi Added. Disabling internal wlan0..." >> /var/log/wifi_switch.log
    ip link set wlan0 down
elif [ "$ACTION" == "remove" ]; then
    echo "[$(date)] USB Wi-Fi Removed. Enabling internal wlan0..." >> /var/log/wifi_switch.log
    ip link set wlan0 up
fi
EOF

sudo chmod +x /usr/local/bin/wifi_switch.sh

echo "[*] Setting up udev rules for Realtek RTL8188ETV (0bda:0179)..."

cat << 'EOF' | sudo tee /etc/udev/rules.d/99-usb-wifi.rules > /dev/null
# Disable internal wlan0 when RTL8188ETV is plugged in
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="0179", RUN+="/usr/local/bin/wifi_switch.sh add"

# Re-enable internal wlan0 when RTL8188ETV is removed
ACTION=="remove", SUBSYSTEM=="usb", ENV{PRODUCT}=="bda/179/*", RUN+="/usr/local/bin/wifi_switch.sh remove"
EOF

echo "[*] Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "[✓] Dual Wi-Fi Fallback setup complete."
