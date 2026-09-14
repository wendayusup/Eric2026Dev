# Autonomous Drone GCS (Ground Control Station) & Telemetry Stack

This repository contains the Ground Control Station (GCS) and telemetry system for autonomous VTOL/multirotor drones. It allows real-time monitoring of drone telemetry, live dual-camera video feeds, interactive map waypoint management, and payload servo control.

---

## System Prerequisites

Before running the GCS, ensure your ground workstation meets the following requirements:

1. **Operating System:** Ubuntu 22.04 LTS
2. **ROS 2:** ROS 2 Humble (Desktop or Base)
3. **MAVROS & ROS 2 Dependencies:**
   ```bash
   sudo apt update
   sudo apt install ros-humble-mavros ros-humble-mavros-msgs ros-humble-mavros-extras ros-humble-cv-bridge -y
   ```
4. **Python Dependencies:**
   ```bash
   pip install flask flask-socketio flask-cors python-socketio websocket-client
   ```

---

## How to Run the GCS

Follow these steps to start the GCS dashboard:

### 1. Connect to Local WiFi Network
Ensure your ground computer is connected to the same WiFi network or hotspot as the drone's companion computer (Raspberry Pi) for telemetry and camera feed streaming.

### 2. Start the GCS Web Backend
Run the backend server from the project root:
```bash
python3 real_workspace/backend_real.py
```
Wait until the server starts and binds to port `5000`.

### 3. Open the Dashboard in Browser
Open your web browser (Google Chrome or Firefox) and navigate to:
**http://localhost:5000**

---

## GCS Web Interface Features

The Ground Control Station web dashboard is organized into intuitive tabs (`MANUAL` and `MISSION`) with unified controls:

### 1. Unified Action Header (`ARM` | `TAKEOFF / START AUTO` | `LAND` | `CUTOFF`)
- **ARM:** Arm flight controller motors.
- **TAKEOFF / START AUTO:** Command automated takeoff or start mission pipeline.
- **LAND:** Command immediate vertical landing.
- **CUTOFF:** Emergency Kill Switch (`MAV_CMD_DO_FLIGHTTERMINATION` + motor disarm).

### 2. Interactive Map & Mission Management
- **Interactive Leaflet Map:** Switch between Satellite and Standard vector map tiles with Light and Dark themes.
- **Waypoint Operations:** Click map to place Waypoints (Takeoff, Waypoint, Landing). Drag markers to update GPS coordinates (`lat`, `lng`) in real time with distance and heading polyline overlays.
- **Native Flight Controller Mission Sync (`UPLOAD MISSION`):** Pushes mission array directly to FCU EEPROM via `/mavros/mission/push`.

### 3. Dual Camera & Telemetry Dashboard
- **Front & Bottom Webcams:** Full aspect ratio (`100% cover/fill`) camera streaming.
- **Live Event Log Panel:** Slide-in system event log with theme-adaptive Light (White) and Dark (Navy) modes.
- **Real-Time Telemetry & Charts:** Displays Altitude, Speed, Battery, GPS lock, Satellites, Roll/Pitch/Yaw, and live telemetry scrolling charts.
- **Permanent Servo Control:** Quick-access payload drop controls (**OPEN / CLOSE**).

---

## Companion Computer & Diagnostics

- **Raspberry Pi SSH Helper:**
  ```bash
  bash real_workspace/connect_raspi.sh
  ```
- **Unified Diagnostic Suite:**
  ```bash
  python3 real_workspace/debug_suite.py
  ```
