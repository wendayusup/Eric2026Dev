#!/bin/bash
# setup_wifi_failover.sh
# Sets up automatic failover from internal Wi-Fi to USB Wi-Fi on the Raspberry Pi

# Disable destructive udev rules that forcibly bring wlan0 down on USB re-enumeration
if [ -f "/etc/udev/rules.d/99-usb-wifi.rules" ]; then
    echo "[*] Removing aggressive USB Wi-Fi udev rules..."
    sudo rm -f /etc/udev/rules.d/99-usb-wifi.rules /usr/local/bin/wifi_switch.sh
    sudo udevadm control --reload-rules
fi

echo "[*] Disabling USB Wi-Fi power suspend for Realtek 8188ETV..."
cat << 'EOF' | sudo tee /etc/modprobe.d/8188eu.conf > /dev/null
options r8188eu rtw_power_mgnt=0 rtw_enusbss=0
options 8188eu rtw_power_mgnt=0 rtw_enusbss=0
EOF

echo "[✓] Dual Wi-Fi stability fix applied."
