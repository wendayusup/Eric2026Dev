#!/usr/bin/env python3
import subprocess
import sys

def main():
    print("=========================================================")
    print("   MEMULAI ARSITEKTUR KONTROL OTONOM REAL DRONE ROS2     ")
    print("=========================================================")
    
    # Sourcing ROS2 Humble & workspace kemudian menjalankan real_drone_launch.py
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    setup_path = os.path.join(project_root, "ros2_ws", "install", "setup.bash")
    cmd = f"bash -c 'export PYTHONUNBUFFERED=1 && source /opt/ros/humble/setup.bash && source {setup_path} && ros2 launch krti_autonomous real_drone_launch.py fcu_url:=/dev/ttyUSB0:57600 gcs_url:=udp://@127.0.0.1:14550'"
    
    try:
        process = subprocess.Popen(cmd, shell=True)
        process.wait()
    except KeyboardInterrupt:
        print("\nMenerima sinyal keluar. Menghentikan arsitektur ROS2 Real Drone...")
    except Exception as e:
        print(f"Gagal mengeksekusi stack ROS2: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
