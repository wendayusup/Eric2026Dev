// MANUAL CONTROL MODE LOGIC
// State variables (lastManualTargetLatLng, manualStartLatLng, manualTargetLatLng, manualSegments)
// are declared globally in script.js

function sendManualAction(action) {
    console.log("[FCS GCS] sendManualAction called with action:", action);
    if (action === 'disarm') {
        if (!confirm("⚠️ EMERGENCY CUT (KILL SWITCH)\n\nAre you sure you want to FORCE DISARM the drone? This will instantly shut off all motors!")) {
            return;
        }
        updateMapStatus("EMERGENCY CUT (DISARM)", "#ff453a", true);
        if (typeof addSystemLog === 'function') addSystemLog('EMERGENCY: Force disarm / kill switch triggered!', 'error');
    } else if (action === 'arm') {
        if (globalTelemetry && globalTelemetry.is_armed) {
            if (typeof showToastAlert === 'function') showToastAlert('NOTICE', 'Drone is already ARMED', 'info', 2500);
            return;
        }
        updateMapStatus("ARMING SENT", "#ff9500", true);
        if (typeof addSystemLog === 'function') addSystemLog('Command sent: ARM vehicle.', 'warning');
    } else if (action === 'land') {
        updateMapStatus("LANDING SENT", "#0071e3", true);
        if (typeof showToastAlert === 'function') showToastAlert('ACTION', 'Commanding LANDING mode...', 'info', 2500);
        if (typeof addSystemLog === 'function') addSystemLog('Command sent: LAND mode initiated.', 'info');
    } else if (action === 'hold') {
        if (typeof addSystemLog === 'function') addSystemLog('Command sent: HOLD / LOITER mode.', 'info');
    }
    socket.emit('manual_action', action);
}

function sendTakeoffAction() {
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
    if (!manualStartLatLng || !manualTargetLatLng) return;
    if (globalTelemetry.lat === 0 || globalTelemetry.lng === 0) return;

    // Bersihkan segment lama dari peta
    manualSegments.forEach(s => map.removeLayer(s));
    manualSegments = [];

    const dronePos = [globalTelemetry.lat, globalTelemetry.lng];
    const targetPos = [manualTargetLatLng.lat, manualTargetLatLng.lng];

    // Hitung jarak tersisa dari drone ke target
    const distance = map.distance(L.latLng(dronePos), L.latLng(targetPos));

    if (distance < 2.0) {
        // Sudah sampai target, gambar seluruh garis sebagai abu-abu
        const grayLine = L.polyline([[manualStartLatLng.lat, manualStartLatLng.lng], targetPos], {
            color: '#8e8e93',
            weight: 3,
            opacity: 0.6,
            dashArray: '6, 12'
        }).addTo(map);
        manualSegments.push(grayLine);

        // Ubah warna selection marker target jadi abu-abu
        if (tempSelectionMarker) {
            tempSelectionMarker.setStyle({ fillColor: '#8e8e93' });
        }
    } else {
        // Belum sampai target:
        // 1. Gambar segment yang sudah dilewati (Start -> Drone)
        const distFromStart = map.distance(L.latLng([manualStartLatLng.lat, manualStartLatLng.lng]), L.latLng(dronePos));
        if (distFromStart > 1.0) {
            const passedLine = L.polyline([[manualStartLatLng.lat, manualStartLatLng.lng], dronePos], {
                color: '#8e8e93',
                weight: 3,
                opacity: 0.6,
                dashArray: '6, 12'
            }).addTo(map);
            manualSegments.push(passedLine);
        }

        // 2. Gambar segment aktif yang akan dilewati (Drone -> Target) - Glowing Biru
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
    if (typeof showToastAlert === 'function') showToastAlert('SERVO', `Setting BOTH Servos to ${actionVal.toUpperCase()}`, 'info', 2000);
    socket.emit('trigger_servo', { servo_id: 'all', action: actionVal });
    socket.emit('trigger_servo', { servo_id: 1, action: actionVal });
    socket.emit('trigger_servo', { servo_id: 2, action: actionVal });
}

// Socket IO Listeners for Servo Status & ArUco Precision Centered Status
if (typeof socket !== 'undefined' && socket) {
    socket.on('servo_status_update', function(data) {
        console.log("[FCS GCS] Servo Status Update:", data);
        if (typeof markRaspiActive === 'function') markRaspiActive();
        if (typeof showToastAlert === 'function') {
            showToastAlert('SUCCESS', data.msg || `Servo ${data.servo_id} Status: ${data.state}`, 'success', 2500);
        }
    });

    socket.on('aruco_target_centered', function(data) {
        console.log("[FCS GCS] ArUco Target Centered Event:", data);
        if (typeof showToastAlert === 'function') {
            showToastAlert('TARGET CENTERED', `ArUco ${data.wp || data.marker_id} is perfectly centered!`, 'success', 2500);
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
