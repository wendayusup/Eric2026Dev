#!/bin/bash
# Script to stop all KRTI 2026 Gazebo SITL simulation nodes & backend processes

echo "========================================================="
echo "   KRTI 2026 — STOPPING ALL SIMULATION PROCESSES"
echo "========================================================="

echo "[*] Killing Gazebo Harmonic..."
pkill -9 -f "gz sim" 2>/dev/null

echo "[*] Killing ArduPilot SITL & MAVProxy..."
pkill -9 -f "sim_vehicle.py" 2>/dev/null
pkill -9 -f "arducopter" 2>/dev/null
pkill -9 -f "mavproxy" 2>/dev/null

echo "[*] Killing ROS2 & GCS Backend..."
pkill -9 -f "gcs_bridge_node" 2>/dev/null
pkill -9 -f "backend_gazebo.py" 2>/dev/null
pkill -9 -f "mavros" 2>/dev/null
pkill -9 -f "ros2 launch" 2>/dev/null

echo "========================================================="
echo "[✓] All simulation nodes and background tasks stopped!"
echo "========================================================="
