# Workspace Rules for Raspberry Pi SD Card Injections

When performing SD Card injections for the Raspberry Pi Ubuntu Server:
1. ALWAYS use the **Pristine First-Boot Reset Method**:
   - Clear `/var/lib/cloud/*` and `/var/lib/NetworkManager/*`.
   - Clear custom `/etc/netplan/*` files.
   - Use standard `50-cloud-init.yaml` and `network-config` with plain-text SSID "discrete" and password "wakanda_31".
2. NEVER run `ip link set wlan0 down` or lock NetworkManager states dynamically via SSH.
3. Keep `eric_nodes.service` enabled at `/etc/systemd/system/multi-user.target.wants/eric_nodes.service`.
