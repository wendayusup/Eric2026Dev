#!/bin/bash
# Script Instalasi Otomatis ROS2 Humble untuk Raspberry Pi (Ubuntu 22.04)
# Dibuat untuk KRTI 2026 - Companion Computer

echo "=========================================================="
echo "    MEMULAI INSTALASI ROS2 HUMBLE (BASE) DI RASPBERRY PI  "
echo "=========================================================="
echo "Script ini akan menginstal ROS2 secara otomatis."
echo "Proses ini membutuhkan koneksi internet dan waktu sekitar 10-20 menit."
echo "Dimohon untuk tidak menutup terminal selama proses berlangsung."
sleep 3

# 1. Pastikan sistem mendukung locale UTF-8
echo "[1/6] Mengonfigurasi Locale (UTF-8)..."
sudo apt update && sudo apt install locales -y
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# 2. Aktifkan repository Ubuntu Universe
echo "[2/6] Mengaktifkan repository Universe..."
sudo apt install software-properties-common -y
sudo add-apt-repository universe -y

# 3. Tambahkan ROS2 GPG Key dan Repository
echo "[3/6] Menambahkan GPG Key dan Repository ROS2..."
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 4. Update dan Upgrade sistem
echo "[4/6] Memperbarui sistem (Update & Upgrade)..."
sudo apt update
sudo apt upgrade -y

# 5. Instalasi ROS2 Humble (Versi Base untuk efisiensi RAM Raspberry Pi)
echo "[5/6] Menginstal ROS2 Humble (ros-base)..."
sudo apt install ros-humble-ros-base -y
sudo apt install python3-colcon-common-extensions -y

# 6. Sourcing otomatis di bashrc
echo "[6/6] Mendaftarkan ROS2 ke ~/.bashrc..."
if ! grep -q "source /opt/ros/humble/setup.bash" ~/.bashrc; then
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
fi

echo "=========================================================="
echo "   INSTALASI SELESAI! ROS2 HUMBLE SIAP DIGUNAKAN!         "
echo "=========================================================="
echo "Silakan tutup terminal ini dan buka terminal SSH baru, atau jalankan perintah:"
echo "source ~/.bashrc"
