#!/bin/bash
# make_release.sh - Build, obfuscate, and package the release workspace

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
REPO_DIR=$(dirname "$SCRIPT_DIR")
RELEASE_DIR="$(dirname "$REPO_DIR")/krti_2026_release"

echo "========================================================="
echo "   KRTI 2026 — GENERATING OBFUSCATED RELEASE"
echo "========================================================="

# 1. Clean and build the ROS2 package
echo "[*] Building ROS2 workspace..."
cd "$REPO_DIR/ros2_ws"
colcon build --packages-select krti_autonomous

# 2. Obfuscate using PyArmor
SITE_PKG_DIR="$REPO_DIR/ros2_ws/install/krti_autonomous/lib/python3.10/site-packages"
PKG_DIR="$SITE_PKG_DIR/krti_autonomous"

echo "[*] Obfuscating Python nodes with PyArmor..."
cd "$PKG_DIR"

# Pastikan folder dist bersih
rm -rf dist

pyarmor gen real_gcs_bridge_node.py gcs_bridge_node.py visual_servo_node.py

if [ $? -ne 0 ]; then
    echo "[!] PyArmor obfuscation FAILED."
    exit 1
fi

# Move obfuscated scripts over the originals
mv dist/real_gcs_bridge_node.py real_gcs_bridge_node.py
mv dist/gcs_bridge_node.py gcs_bridge_node.py
mv dist/visual_servo_node.py visual_servo_node.py

# Move the pyarmor_runtime package to site-packages so it's a top-level module
rm -rf "$SITE_PKG_DIR"/pyarmor_runtime_*
mv dist/pyarmor_runtime_* "$SITE_PKG_DIR/"

# Clean up dist folder
rm -rf dist

# 3. Create the release folder structure
echo "[*] Cleaning release directory: $RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
find "$RELEASE_DIR" -mindepth 1 -maxdepth 1 ! -name ".git" ! -name ".gitignore" -exec rm -rf {} +
mkdir -p "$RELEASE_DIR/real_workspace"
mkdir -p "$RELEASE_DIR/ros2_ws"

# Create standard .gitignore in the release directory
cat << 'EOF' > "$RELEASE_DIR/.gitignore"
# Python Cache
__pycache__/
*.py[cod]
*$py.class

# IDE
.vscode/
.DS_Store
EOF

# Copy launcher scripts and configs
cp "$REPO_DIR/real_workspace/backend_real.py" "$RELEASE_DIR/real_workspace/"
cp "$REPO_DIR/real_workspace/connect_raspi.sh" "$RELEASE_DIR/real_workspace/"

# Copy web files
cp -r "$REPO_DIR/web" "$RELEASE_DIR/"

# Copy built ROS2 install folder
cp -r "$REPO_DIR/ros2_ws/install" "$RELEASE_DIR/ros2_ws/"

# Copy release README as the main README
cp "$REPO_DIR/README_RELEASE.md" "$RELEASE_DIR/README.md"

echo ""
echo "========================================================="
echo "[✓] RELEASE GENERATION COMPLETE!"
echo "    Location: $RELEASE_DIR"
echo "========================================================="
