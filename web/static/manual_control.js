// MANUAL CONTROL MODE LOGIC
// State variables (lastManualTargetLatLng, manualStartLatLng, manualTargetLatLng, manualSegments)
// are declared globally in script.js

function sendManualAction(action) {
    console.log("[FCS GCS] sendManualAction called with action:", action);
    const isTelemConnected = (Date.now() - lastTelemetryTime) < 5000;
    const hasGpsFix = isTelemConnected && globalTelemetry && globalTelemetry.lat && globalTelemetry.lat !== 0 && globalTelemetry.lng && globalTelemetry.lng !== 0;

    if (action === 'disarm') {
        updateMapStatus("EMERGENCY CUT (DISARM)", "#ff453a", true);
        if (typeof showToastAlert === 'function') {
            showToastAlert('EMERGENCY CUT', 'Force disarm / kill switch triggered!', 'error', 4000);
        }
    } else if (action === 'arm') {
        if (globalTelemetry && globalTelemetry.is_armed) {
            if (typeof showToastAlert === 'function') showToastAlert('NOTICE', 'Drone is already ARMED', 'info', 2500);
            return;
        }
        updateMapStatus("ARMING SENT", "#ff9500", true);
        if (typeof addSystemLog === 'function') addSystemLog('Command sent: ARM vehicle.', 'warning');
    } else if (action === 'land') {
        if (!hasGpsFix) {
            return showCustomAlert("GPS Lock Required", "GPS lock is missing! LAND command requires active GPS lock.", "error");
        }
        updateMapStatus("LANDING SENT", "#0071e3", true);
        if (typeof showToastAlert === 'function') showToastAlert('ACTION', 'Commanding LANDING mode...', 'info', 2500);
        if (typeof addSystemLog === 'function') addSystemLog('Command sent: LAND mode initiated.', 'info');
    } else if (action === 'hold') {
        if (typeof addSystemLog === 'function') addSystemLog('Command sent: HOLD / LOITER mode.', 'info');
    }
    socket.emit('manual_action', action);
}

function sendTakeoffAction() {
    const isTelemConnected = (Date.now() - lastTelemetryTime) < 5000;
    const hasGpsFix = isTelemConnected && globalTelemetry && globalTelemetry.lat && globalTelemetry.lat !== 0 && globalTelemetry.lng && globalTelemetry.lng !== 0;
    if (!hasGpsFix) {
        return showCustomAlert("GPS Lock Required", "GPS lock is missing! TAKEOFF command requires active GPS lock.", "error");
    }

    const altInput = document.getElementById('manual-alt');
    const altVal = altInput ? (parseFloat(altInput.value) || 1.0) : 1.0;
    console.log("[FCS GCS] Manual Takeoff target alt:", altVal);
    if (typeof showToastAlert === 'function') showToastAlert('TAKEOFF', `Commanding TAKEOFF to ${altVal}m...`, 'info', 2500);
    updateMapStatus(`TAKEOFF SENT (${altVal}m)`, "#0071e3", true);
    if (typeof addSystemLog === 'function') addSystemLog(`Command sent: TAKEOFF to ${altVal}m.`, 'success');
    socket.emit('manual_action', { action: 'takeoff', alt: altVal });
    socket.emit('takeoff', { alt: altVal });
}

function updateManualGuidedPath() {
    // SELALU bersihkan segment lama dari peta tanpa syarat agar tidak ada garis berbekas/numpuk
    if (typeof manualSegments !== 'undefined' && manualSegments.length > 0) {
        manualSegments.forEach(s => {
            if (s && map.hasLayer(s)) {
                map.removeLayer(s);
            }
        });
        manualSegments = [];
    }

    if (!manualTargetLatLng) return;

    // Gunakan posisi Drone Marker nyata jika ada GPS, atau fallback ke posisi marker default di peta
    let droneLat = (globalTelemetry && globalTelemetry.lat && globalTelemetry.lat !== 0) ? globalTelemetry.lat : DEFAULT_LAT;
    let droneLng = (globalTelemetry && globalTelemetry.lng && globalTelemetry.lng !== 0) ? globalTelemetry.lng : DEFAULT_LNG;

    const dronePos = [droneLat, droneLng];
    const targetPos = [manualTargetLatLng.lat, manualTargetLatLng.lng];

    // Gambar segment aktif murni (Drone -> Target) - Glowing Biru
    const glowLine = L.polyline([dronePos, targetPos], {
        color: 'var(--apple-blue)',
        weight: 10,
        opacity: 0.35,
        dashArray: '6, 12',
        className: 'manual-glow-line'
    }).addTo(map);

    const mainLine = L.polyline([dronePos, targetPos], {
        color: 'var(--apple-blue)',
        weight: 3,
        opacity: 0.9,
        dashArray: '6, 12',
        className: 'manual-main-line'
    }).addTo(map);

    manualSegments.push(glowLine, mainLine);
}

function testServo(servoId, val) {
    console.log("[FCS GCS] testServo called with servoId:", servoId, "val:", val);
    if (val === 'open' || val === 'close') {
        if (typeof showToastAlert === 'function') showToastAlert('INFO', `Sending command: Servo ${servoId} ${val.toUpperCase()}`, 'info', 2000);
        socket.emit('trigger_servo', { servo_id: servoId, action: val });
    } else {
        if (typeof showToastAlert === 'function') showToastAlert('INFO', `Sending command: Servo ${servoId} to ${val}°`, 'info', 2000);
        socket.emit('trigger_servo', { servo_id: servoId, action: 'angle', angle: parseInt(val) });
    }
}

function testBothServos(val) {
    const actionVal = val || 'open';
    console.log("[FCS GCS] testBothServos called with action:", actionVal);
    if (typeof showToastAlert === 'function') showToastAlert('SERVO', `Setting Servo to ${actionVal.toUpperCase()}`, 'info', 2000);
    socket.emit('trigger_servo', { servo_id: 'all', action: actionVal });
}

// Socket IO Listeners for Servo Status & Black Object Precision Centered Status
if (typeof socket !== 'undefined' && socket) {
    socket.on('servo_status_update', function(data) {
        console.log("[FCS GCS] Servo Status Update:", data);
        if (typeof markRaspiActive === 'function') markRaspiActive();
        if (typeof showToastAlert === 'function') {
            showToastAlert('SUCCESS', data.msg || `Servo ${data.servo_id} Status: ${data.state}`, 'success', 2500);
        }
    });

    socket.on('black_object_detected', function(data) {
        console.log("[FCS GCS] Black Object Target Event:", data);
        if (data && data.centered && typeof showToastAlert === 'function') {
            showToastAlert('TARGET CENTERED', 'Black Object is perfectly centered!', 'success', 2500);
        }
    });
}

function changeFlightMode(mode) {
    console.log("[FCS GCS] changeFlightMode called with mode:", mode);
    socket.emit('change_flight_mode', { mode: mode });
    if (typeof showToastAlert === 'function') {
        showToastAlert('MODE CHANGE', `Requesting mode: ${mode}`, 'info', 2000);
    }
}

function applyHeadingOffset() {
    const val = parseFloat(document.getElementById('heading-offset-input').value) || 0;
    socket.emit('set_heading_offset', { offset: val });
    if (typeof showToastAlert === 'function') {
        showToastAlert('COMPASS OFFSET', `Heading offset set to ${val}°`, 'info', 2500);
    }
    updateMapStatus(`HDG OFFSET: ${val}°`, "#ff9500", true);
}

function resetHeadingOffset() {
    document.getElementById('heading-offset-input').value = 0;
    socket.emit('set_heading_offset', { offset: 0 });
    if (typeof showToastAlert === 'function') {
        showToastAlert('COMPASS OFFSET', 'Heading offset reset to 0°', 'info', 2000);
    }
}

function changeCameraResolution(profile) {
    console.log("[FCS GCS] changeCameraResolution called with profile:", profile);
    const selectors = document.querySelectorAll('.cam-res-select');
    selectors.forEach(sel => {
        sel.value = profile;
    });

    if (typeof socket !== 'undefined' && socket) {
        socket.emit('set_camera_resolution', { profile: profile });
    }

    if (typeof showToastAlert === 'function') {
        const labels = {
            'hd': 'HD 640x360 (High Quality)',
            'high': 'High 480x270 (Standard)',
            'medium': 'Balanced 400x225 (Smooth)',
            'low': 'Low Latency 320x180 (Ultra Fast)',
            'auto': 'Auto Adaptive Network'
        };
        const labelText = labels[profile] || profile;
        showToastAlert('CAMERA RES', `Stream profile set to: ${labelText}`, 'info', 2500);
    }
}
