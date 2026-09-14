#!/usr/bin/env python3
import subprocess
import sys

def main():
    print("=========================================================")
    print("   MEMULAI ARSITEKTUR KONTROL OTONOM DRONE ROS2 HUMBLE   ")
    print("=========================================================")
    
    # Sourcing ROS2 Humble & workspace kemudian menjalankan launch file (RViz dimatikan untuk hemat CPU)
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    setup_path = os.path.join(project_root, "ros2_ws", "install", "setup.bash")
    cmd = f"bash -c 'export GZ_IP=127.0.0.1 && export GZ_VERSION=harmonic && source /opt/ros/humble/setup.bash && source {setup_path} && ros2 launch krti_autonomous sim_autonomous_launch.py launch_rviz:=false'"
    
    try:
        process = subprocess.Popen(cmd, shell=True)
        process.wait()
    except KeyboardInterrupt:
        print("\nMenerima sinyal keluar. Menghentikan arsitektur ROS2...")
    except Exception as e:
        print(f"Gagal mengeksekusi stack ROS2: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
