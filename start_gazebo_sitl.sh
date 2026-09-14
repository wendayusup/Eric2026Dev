#!/bin/bash
# Script to launch KRTI 2026 Simulation (Gazebo + ArduPilot SITL + ROS2 Backend)
# Requires gnome-terminal (default in Ubuntu)

echo "========================================================="
echo "   KRTI 2026 — STARTING GAZEBO SITL SIMULATION"
echo "========================================================="

# 1. Start Gazebo in a new terminal window
echo "[*] Launching Gazebo Harmonic..."
gnome-terminal --window --title="Gazebo" -- bash -c "
export GZ_VERSION=harmonic
export GZ_SIM_SYSTEM_PLUGIN_PATH=\$HOME/krti_2026/ardupilot_gazebo/build:\$GZ_SIM_SYSTEM_PLUGIN_PATH
export GZ_SIM_RESOURCE_PATH=\$HOME/krti_2026/ardupilot_gazebo/models:\$HOME/krti_2026/ardupilot_gazebo/worlds:\$GZ_SIM_RESOURCE_PATH
echo 'Starting Gazebo... Please wait.'
gz sim -v4 -r krti_world.sdf
exec bash"

sleep 3

# 2. Start ArduPilot SITL in a new tab
echo "[*] Launching ArduPilot SITL..."
gnome-terminal --window --title="ArduPilot SITL" -- bash -c "
export SITL_RITW_TERMINAL=\"gnome-terminal -- \"
cd \$HOME/krti_2026/ardupilot/ArduCopter
echo 'Starting ArduPilot SITL...'
../Tools/autotest/sim_vehicle.py -w -v ArduCopter -f gazebo-iris --model JSON --add-param-file=../Tools/autotest/default_params/gazebo-iris.parm --map --console
exec bash"

sleep 5

# 3. Start ROS2 Backend in a new tab
echo "[*] Launching ROS2 GCS Backend..."
gnome-terminal --window --title="ROS2 GCS Backend" -- bash -c "
cd \$HOME/krti_2026
python3 gazebo_workspace/backend_gazebo.py
exec bash"

echo "========================================================="
echo "[✓] All simulation nodes launched in separate windows!"
echo "    1. Wait for the drone to appear in Gazebo."
echo "    2. Wait for ArduPilot SITL to initialize."
echo "    3. Open http://localhost:5000 in your browser."
echo "========================================================="
