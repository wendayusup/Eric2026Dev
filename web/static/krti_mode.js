// KRTI AUTONOMOUS MODE LOGIC
// State variables (altChart, speedChart, maxChartPoints) are declared globally in script.js

function sendKrtiAction(action) {
    if (action === 'start_auto') {
        const formattedWps = formatKrtiWaypoints();
        if (!formattedWps || formattedWps.length < 3) {
            showKrtiToast("Please save a valid KRTI Mission (min 3 WPs) first!", "warning");
            return;
        }
        socket.emit('transmit_auto_mission', formattedWps);
        showKrtiToast("KRTI Mission Uploaded & Auto Execution Started!", "success");
    } else {
        socket.emit('krti_command', { action: action });
        showKrtiToast(`KRTI Command: ${action.toUpperCase()} sent`, 'info');
    }
}

function initKrtiCharts() {
    const altCanvas = document.getElementById('chart-altitude');
    const speedCanvas = document.getElementById('chart-speed');
    if (!altCanvas || !speedCanvas) return;

    const altCtx = altCanvas.getContext('2d');
    altChart = new Chart(altCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Altitude',
                data: [],
                borderColor: '#0ea5e9',
                backgroundColor: 'rgba(14, 165, 233, 0.15)',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.08)' },
                    ticks: {
                        color: '#0ea5e9',
                        font: { size: 9 },
                        maxRotation: 0,
                        minRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 5
                    }
                },
                y: {
                    suggestedMin: 0,
                    suggestedMax: 5,
                    grid: { color: 'rgba(255, 255, 255, 0.08)' },
                    ticks: { color: '#0ea5e9', font: { size: 9 } }
                }
            }
        }
    });

    const speedCtx = speedCanvas.getContext('2d');
    speedChart = new Chart(speedCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Speed',
                data: [],
                borderColor: '#ff6b00',
                backgroundColor: 'rgba(255, 107, 0, 0.15)',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.08)' },
                    ticks: {
                        color: '#ff6b00',
                        font: { size: 9 },
                        maxRotation: 0,
                        minRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 5
                    }
                },
                y: {
                    suggestedMin: 0,
                    suggestedMax: 5,
                    grid: { color: 'rgba(255, 255, 255, 0.08)' },
                    ticks: { color: '#ff6b00', font: { size: 9 } }
                }
            }
        }
    });
}

function updateKrtiCharts(alt, speed) {
    if (!altChart || !speedChart) return;

    const timeLabel = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

    // Altitude Chart
    altChart.data.labels.push(timeLabel);
    altChart.data.datasets[0].data.push(alt);
    if (altChart.data.labels.length > maxChartPoints) {
        altChart.data.labels.shift();
        altChart.data.datasets[0].data.shift();
    }
    altChart.update('none');

    // Speed Chart
    speedChart.data.labels.push(timeLabel);
    speedChart.data.datasets[0].data.push(speed);
    if (speedChart.data.labels.length > maxChartPoints) {
        speedChart.data.labels.shift();
        speedChart.data.datasets[0].data.shift();
    }
    speedChart.update('none');

    // Update value displays (1:1 with bottom bar)
    const altValEl = document.getElementById('chart-alt-val');
    const speedValEl = document.getElementById('chart-speed-val');
    if (altValEl) altValEl.innerText = alt.toFixed(2) + " m";
    if (speedValEl) speedValEl.innerText = speed.toFixed(2) + " m/s";
}

// Initialize on script load
initKrtiCharts();

socket.on('krti_log', function (data) {
    const logContent = document.getElementById('krti-log-content');
    if (logContent) {
        // If it's the placeholder text, clear it first
        if (logContent.innerText.trim().startsWith('[Live logs')) {
            logContent.innerText = '';
        }

        const timestamp = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        logContent.innerText += `[${timestamp}] ${data.message}\n`;

        // Auto-scroll to bottom
        logContent.scrollTop = logContent.scrollHeight;
    }
});

socket.on('krti_status_update', function (data) {
    const badge = document.getElementById('krti-status-badge');
    if (badge) {
        badge.innerText = data.status.toUpperCase();

        // Style badge based on status
        if (data.status === 'IDLE' || data.status === 'STANDBY') {
            badge.style.color = 'var(--apple-green)';
            if (typeof clearKrtiLogs === 'function') clearKrtiLogs();
            if (typeof clearKrtiJson === 'function') clearKrtiJson();
        } else if (data.status.includes('FLYING')) {
            badge.style.color = 'var(--apple-blue)';
        } else if (data.status.includes('ROTATE') || data.status.includes('PAYLOAD')) {
            badge.style.color = 'var(--apple-orange)';
        } else if (data.status.includes('LANDING')) {
            badge.style.color = 'var(--apple-red)';
        }
    }
});

function clearKrtiLogs() {
    const logContent = document.getElementById('krti-log-content');
    if (logContent) {
        logContent.innerText = '[Logs cleared]\n';
    }
}

// KRTI Waypoint Status & Map Display
let krtiMarkers = [];
let krtiSegments = [];

socket.on('krti_wp_update', function (data) {
    const badgeEl = document.getElementById('krti-active-wp-badge');
    if (!badgeEl) return;

    if (data.name) {
        badgeEl.innerText = data.name.toUpperCase();
    } else if (data.wp) {
        badgeEl.innerText = `WP${data.wp}`;
    } else {
        badgeEl.innerText = 'STANDBY';
    }

    if (data.type === 'takeoff') {
        badgeEl.style.color = '#28a745';
        badgeEl.style.background = 'rgba(40, 167, 69, 0.1)';
        badgeEl.style.border = '1px solid rgba(40, 167, 69, 0.3)';
    } else if (data.type === 'landing') {
        badgeEl.style.color = '#ff3b30';
        badgeEl.style.background = 'rgba(255, 59, 48, 0.1)';
        badgeEl.style.border = '1px solid rgba(255, 59, 48, 0.3)';
    } else {
        badgeEl.style.color = '#0071e3';
        badgeEl.style.background = 'rgba(0, 113, 227, 0.1)';
        badgeEl.style.border = '1px solid rgba(0, 113, 227, 0.3)';
    }
});

socket.on('krti_mission_coordinates', function (coordinates) {
    // Clear old KRTI markers and segments
    krtiMarkers.forEach(m => map.removeLayer(m));
    krtiMarkers = [];
    krtiSegments.forEach(s => map.removeLayer(s));
    krtiSegments = [];

    if (!coordinates || coordinates.length === 0) return;

    // Draw waypoints
    coordinates.forEach((wp) => {
        let color = wp.type === 'takeoff' ? '#28a745' : (wp.type === 'landing' ? '#ef4444' : '#0071e3');

        const marker = L.circleMarker([wp.lat, wp.lng], {
            radius: 8,
            fillColor: color,
            color: '#fff',
            weight: 2,
            fillOpacity: 0.9
        }).addTo(map);

        marker.bindPopup(`<b>KRTI WP${wp.wp} (${wp.type.toUpperCase()})</b><br>Heading: ${wp.heading.toFixed(1)}°`);
        krtiMarkers.push(marker);

        // Text-only label without background (Satellite: Purple/Pink, Standard: Yellow)
        const labelText = wp.name ? wp.name : `WP${wp.wp} (${wp.type.toUpperCase()})`;
        const labelIcon = L.divIcon({
            className: 'wp-map-label-krti',
            html: (typeof getWpLabelHtml === 'function') ? getWpLabelHtml(labelText) : `<div style="color:#ffcc00; font-weight:bold; font-size:11px; transform:translate(-50%, -20px); text-shadow:-1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;">${labelText}</div>`,
            iconSize: [0, 0],
            iconAnchor: [0, 0]
        });
        const labelMarker = L.marker([wp.lat, wp.lng], { icon: labelIcon, interactive: false }).addTo(map);
        krtiMarkers.push(labelMarker);
    });

    // Draw segments
    for (let i = 0; i < coordinates.length - 1; i++) {
        const start = coordinates[i];
        const end = coordinates[i + 1];

        const glowLine = L.polyline([[start.lat, start.lng], [end.lat, end.lng]], {
            color: 'var(--apple-blue)',
            weight: 10,
            opacity: 0.35,
            dashArray: '5, 10',
            className: 'waypoint-glow-line'
        }).addTo(map);

        const mainLine = L.polyline([[start.lat, start.lng], [end.lat, end.lng]], {
            color: 'var(--apple-blue)',
            weight: 3,
            opacity: 0.9,
            dashArray: '5, 10',
            className: 'waypoint-main-line'
        }).addTo(map);

        krtiSegments.push(glowLine, mainLine);
    }
});

// Real-time Waypoint JSON data logger handler
let krtiTestTargetMarker = null;
let krtiTestTargetLine = null;
let lastFittedWp = null;

function getGpsOffset(lat, lng, headingDeg, distanceM) {
    const R = 6378137.0; // Earth's radius in meters
    const headingRad = headingDeg * Math.PI / 180.0;
    const latRad = lat * Math.PI / 180.0;

    const deltaLat = (distanceM * Math.cos(headingRad)) / R;
    const deltaLng = (distanceM * Math.sin(headingRad)) / (R * Math.cos(latRad));

    const targetLat = lat + (deltaLat * 180.0 / Math.PI);
    const targetLng = lng + (deltaLng * 180.0 / Math.PI);

    return [targetLat, targetLng];
}

function drawDynamicTargetWaypoint(data) {
    // Clear previous test drawings if any
    if (krtiTestTargetMarker) {
        map.removeLayer(krtiTestTargetMarker);
        krtiTestTargetMarker = null;
    }
    if (krtiTestTargetLine) {
        map.removeLayer(krtiTestTargetLine);
        krtiTestTargetLine = null;
    }

    if (!data || data.distance_m === undefined || data.target_heading_deg === undefined) {
        return;
    }

    // Get current position or default/fallback
    let startLat = (globalTelemetry && globalTelemetry.lat !== 0) ? globalTelemetry.lat : -6.8760782616578595;
    let startLng = (globalTelemetry && globalTelemetry.lng !== 0) ? globalTelemetry.lng : 107.6214877492015;

    let targetCoords = getGpsOffset(startLat, startLng, data.target_heading_deg, data.distance_m);

    // If distance is 0 (like WP4 landing), target is the current position
    if (data.distance_m === 0) {
        targetCoords = [startLat, startLng];
    }

    // Draw target marker circle
    krtiTestTargetMarker = L.circle(targetCoords, {
        color: '#34c759',
        fillColor: '#34c759',
        fillOpacity: 0.15,
        radius: 2.0, // 2 meters radius
        weight: 2
    }).addTo(map);

    // Bind popup/tooltip
    krtiTestTargetMarker.bindTooltip(`Target WP${data.waypoint}`, { permanent: false, direction: 'top' });

    // Draw line connecting start and target if distance > 0
    if (data.distance_m > 0) {
        krtiTestTargetLine = L.polyline([[startLat, startLng], targetCoords], {
            color: '#30d158',
            weight: 3,
            dashArray: '5, 10',
            opacity: 0.8
        }).addTo(map);

        // Pan the map to fit both ONLY if the waypoint has changed
        if (typeof lastFittedWp === 'undefined' || lastFittedWp !== data.waypoint) {
            let bounds = L.latLngBounds([[startLat, startLng], targetCoords]);
            map.fitBounds(bounds, { padding: [50, 50] });
            lastFittedWp = data.waypoint;
        }
    }
}

socket.on('krti_wp_json', function (data) {
    const badgeEl = document.getElementById('krti-json-wp-badge');
    const actionEl = document.getElementById('krti-json-action');
    const headingEl = document.getElementById('krti-json-heading');
    const distanceEl = document.getElementById('krti-json-distance');
    const payloadEl = document.getElementById('krti-json-payload');
    const speedEl = document.getElementById('krti-json-speed');
    const altEl = document.getElementById('krti-json-alt');

    if (badgeEl) {
        badgeEl.innerText = data && data.waypoint ? `WP: ${data.waypoint}` : 'WP: NONE';
    }

    if (data) {
        if (actionEl) actionEl.innerText = data.action || '-';
        if (headingEl) headingEl.innerText = data.target_heading_deg !== undefined ? `${data.target_heading_deg}°` : '-';
        if (distanceEl) distanceEl.innerText = data.distance_m !== undefined ? `${data.distance_m} m` : '-';
        if (payloadEl) payloadEl.innerText = data.payload_servo || '-';
        if (speedEl) speedEl.innerText = data.speed_limit_mps !== undefined ? `${data.speed_limit_mps} m/s` : '-';
        if (altEl) altEl.innerText = data.target_alt_m !== undefined ? `${data.target_alt_m} m` : '-';

        // Draw target on map
        drawDynamicTargetWaypoint(data);
    } else {
        if (actionEl) actionEl.innerText = '-';
        if (headingEl) headingEl.innerText = '-';
        if (distanceEl) distanceEl.innerText = '-';
        if (payloadEl) payloadEl.innerText = '-';
        if (speedEl) speedEl.innerText = '-';
        if (altEl) altEl.innerText = '-';

        // Clear drawings
        if (krtiTestTargetMarker) {
            map.removeLayer(krtiTestTargetMarker);
            krtiTestTargetMarker = null;
        }
        if (krtiTestTargetLine) {
            map.removeLayer(krtiTestTargetLine);
            krtiTestTargetLine = null;
        }
    }
});

function clearKrtiJson() {
    const badgeEl = document.getElementById('krti-json-wp-badge');
    const actionEl = document.getElementById('krti-json-action');
    const headingEl = document.getElementById('krti-json-heading');
    const distanceEl = document.getElementById('krti-json-distance');
    const payloadEl = document.getElementById('krti-json-payload');
    const speedEl = document.getElementById('krti-json-speed');
    const altEl = document.getElementById('krti-json-alt');
    if (badgeEl) badgeEl.innerText = 'WP: NONE';
    if (actionEl) actionEl.innerText = '-';
    if (headingEl) headingEl.innerText = '-';
    if (distanceEl) distanceEl.innerText = '-';
    if (payloadEl) payloadEl.innerText = '-';
    if (speedEl) speedEl.innerText = '-';
    if (altEl) altEl.innerText = '-';

    lastFittedWp = null;

    if (krtiTestTargetMarker) {
        map.removeLayer(krtiTestTargetMarker);
        krtiTestTargetMarker = null;
    }
    if (krtiTestTargetLine) {
        map.removeLayer(krtiTestTargetLine);
        krtiTestTargetLine = null;
    }
}

// ─── KRTI Toast Notification (auto-dismiss, no OK button needed) ───────────
let _krtiToastTimer = null;
function showKrtiToast(message, type = 'info') {
    let toast = document.getElementById('krti-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'krti-toast';
        toast.style.cssText = [
            'position:fixed', 'bottom:24px', 'left:50%', 'transform:translateX(-50%) translateY(60px)',
            'padding:9px 18px', 'border-radius:10px', 'font-size:11px', 'font-weight:700',
            'letter-spacing:0.4px', 'z-index:9999', 'transition:transform 0.25s ease,opacity 0.25s ease',
            'opacity:0', 'pointer-events:none', 'text-align:center', 'max-width:320px'
        ].join(';');
        document.body.appendChild(toast);
    }

    const colors = {
        success: { bg: 'rgba(52,199,89,0.92)', border: '#34c759', text: '#fff' },
        error: { bg: 'rgba(255,69,58,0.92)', border: '#ff453a', text: '#fff' },
        warning: { bg: 'rgba(255,159,10,0.92)', border: '#ff9f0a', text: '#fff' },
        info: { bg: 'rgba(0,122,255,0.92)', border: '#007aff', text: '#fff' },
    };
    const c = colors[type] || colors.info;
    toast.style.background = c.bg;
    toast.style.border = `1px solid ${c.border}`;
    toast.style.color = c.text;
    toast.innerText = message;

    // Animate in
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(-50%) translateY(0)';
    });

    // Auto-dismiss after 2s
    if (_krtiToastTimer) clearTimeout(_krtiToastTimer);
    _krtiToastTimer = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(60px)';
    }, 2000);
}

// Intercept upload_status for KRTI mode — use toast, not modal
window._krtiModeActive = false;
socket.on('krti_status_update', d => { window._krtiModeActive = (d.status !== 'IDLE' && d.status !== 'STANDBY'); });

// KRTI upload status notification (spinner below Altitude field)
socket.on('krti_upload_status', function (data) {
    const statusEl = document.getElementById('krti-upload-status');
    const labelEl = document.getElementById('krti-upload-label');
    if (!statusEl) return;

    if (data.loading) {
        if (labelEl) labelEl.innerText = `UPLOADING WP${data.wp} TO VEHICLE...`;
        statusEl.style.display = 'block';
    } else {
        // Show success briefly then hide
        if (labelEl) labelEl.innerText = `✓ WP${data.wp} UPLOADED`;
        statusEl.style.background = 'rgba(52, 199, 89, 0.10)';
        statusEl.style.borderColor = 'rgba(52, 199, 89, 0.35)';
        if (labelEl) labelEl.style.color = '#34c759';
        const spinnerEl = document.getElementById('krti-upload-spinner');
        if (spinnerEl) { spinnerEl.innerText = '✓'; spinnerEl.style.animation = 'none'; }

        setTimeout(() => {
            statusEl.style.display = 'none';
            statusEl.style.background = 'rgba(0, 122, 255, 0.08)';
            statusEl.style.borderColor = 'rgba(0, 122, 255, 0.25)';
            if (labelEl) labelEl.style.color = '#007aff';
            const sp = document.getElementById('krti-upload-spinner');
            if (sp) { sp.innerText = '⟳'; sp.style.animation = 'krti-spin 1s linear infinite'; }
        }, 2000);
    }
});

function sendKrtiAction(action) {
    if (action === 'start_auto') {
        const startBtn = document.getElementById('krti-start-btn');
        if (startBtn) {
            startBtn.disabled = true;
            startBtn.style.background = '#0071e3';
            startBtn.style.cursor = 'not-allowed';
            startBtn.innerHTML = '<span style="display:inline-block; width:10px; height:10px; border:2px solid #fff; border-radius:50%; border-top-color:transparent; animation:krti-spin 1s linear infinite; margin-right:6px; vertical-align:middle;"></span>PUBLISHING...';
        }

        // Format and transmit waypoints first
        const formattedWps = formatKrtiWaypoints();
        console.log("%c[KRTI START AUTO] Publishing waypoints dynamically:", "color: #0071e3; font-weight: bold; font-size: 13px;", formattedWps);
        socket.emit('transmit_auto_mission', formattedWps);

        // Simulate publish/upload delay of 2 seconds before launching the drone
        setTimeout(() => {
            if (startBtn) {
                startBtn.innerHTML = 'AUTO ACTIVE';
                startBtn.style.background = '#28a745';
            }

            const badgeEl = document.getElementById('krti-active-wp-badge');
            if (badgeEl) {
                const firstWpName = krtiCalWaypoints.length > 0 ? krtiCalWaypoints[0].name.toUpperCase() : 'WP1 (TAKEOFF)';
                badgeEl.innerText = firstWpName;
                badgeEl.style.color = '#28a745';
                badgeEl.style.background = 'rgba(40, 167, 69, 0.1)';
                badgeEl.style.border = '1px solid rgba(40, 167, 69, 0.3)';
            }

            socket.emit('krti_command', { action: 'start_auto' });
            showKrtiToast(`KRTI Command: START_AUTO sent`, 'info');
        }, 2000);

    } else {
        socket.emit('krti_command', { action: action });
        showKrtiToast(`KRTI Command: ${action.toUpperCase()} sent`, 'info');
    }
}

// ─── KRTI WAYPOINT CALIBRATION LOGIC (DYNAMIC INLINE BUILDER - WHITE THEME) ───────────
let krtiCalWaypoints = [];
let krtiCalMarkers = [];
let krtiCalSegments = [];
let krtiMissionPublished = false;

function openKrtiCalModal() {
    const modal = document.getElementById('krti-cal-modal');
    if (modal) {
        modal.style.display = 'flex';
        setTimeout(() => modal.classList.add('show'), 10);
        // If list is empty, automatically add WP1 Takeoff
        if (krtiCalWaypoints.length === 0) {
            addCustomWaypoint(true);
        }
        renderCalibrationListUI();
    }
}

function closeKrtiCalModal() {
    const modal = document.getElementById('krti-cal-modal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 200);
    }
}

function closeKrtiCalModalOnBackdrop(e) {
    if (e.target && e.target.id === 'krti-cal-modal') {
        closeKrtiCalModal();
    }
}

function updateWaypointRolesAndIndexes() {
    const total = krtiCalWaypoints.length;
    krtiCalWaypoints.forEach((wp, idx) => {
        wp.wp = idx + 1;
        if (idx === 0) {
            wp.type = 'takeoff';
            wp.name = 'WP1 (TAKEOFF)';
            wp.color = '#28a745'; // Green
            wp.note = 'Arm & Takeoff to target altitude.';
        } else if (idx === total - 1 && total > 1) {
            wp.type = 'landing';
            wp.name = `WP${idx + 1} (LANDING)`;
            wp.color = '#ff3b30'; // Red
            wp.note = 'Navigate to target point & AUTO LAND.';
        } else {
            wp.type = 'waypoint';
            wp.name = `WP${idx + 1} (JETPOINT)`;
            wp.color = '#0071e3'; // Blue
            wp.note = 'Autonomous transit waypoint.';
        }
    });
}

function addCustomWaypoint(silent = false) {
    const newIdx = krtiCalWaypoints.length;
    const defaultWp = {
        wp: newIdx + 1,
        type: newIdx === 0 ? 'takeoff' : 'waypoint',
        name: newIdx === 0 ? 'WP1 (TAKEOFF)' : `WP${newIdx + 1} (JETPOINT)`,
        headingDelta: 0,
        distance: newIdx === 0 ? 0 : 5,
        alt: 3,
        speed: 3
    };

    krtiCalWaypoints.push(defaultWp);
    updateWaypointRolesAndIndexes();
    saveCalWaypointsToStorage();
    renderCalibrationListUI();
    redrawCalibrationWaypoints();

    if (!silent) {
        showKrtiToast(`Waypoint WP${krtiCalWaypoints.length} added!`, 'success');
    }
}

function updateWpField(idx, field, val) {
    if (idx >= 0 && idx < krtiCalWaypoints.length) {
        const numVal = parseFloat(val) || 0;
        krtiCalWaypoints[idx][field] = numVal;
        saveCalWaypointsToStorage();
        redrawCalibrationWaypoints();
    }
}

function deleteCalibrationWaypoint(idx) {
    if (idx >= 0 && idx < krtiCalWaypoints.length) {
        const deletedName = krtiCalWaypoints[idx].name;
        krtiCalWaypoints.splice(idx, 1);
        updateWaypointRolesAndIndexes();

        saveCalWaypointsToStorage();
        renderCalibrationListUI();
        redrawCalibrationWaypoints();

        if (krtiCalWaypoints.length === 0) {
            updateStartAutoButtonState(false);
        }

        showKrtiToast(`${deletedName} deleted!`, "info");
    }
}

function clearCalibrationWaypoints() {
    if (krtiCalWaypoints.length === 0) return;
    if (confirm("Delete all calibration waypoints?")) {
        krtiCalWaypoints = [];
        krtiMissionPublished = false;

        saveCalWaypointsToStorage();
        renderCalibrationListUI();
        redrawCalibrationWaypoints();
        updateStartAutoButtonState(false);

        showKrtiToast("All calibration waypoints cleared!", "info");
    }
}

function updateStartAutoButtonState(enabled) {
    const startBtn = document.getElementById('krti-start-btn');
    if (!startBtn) return;

    if (enabled) {
        startBtn.className = 'action-btn btn-blue';
        startBtn.disabled = false;
        startBtn.style.background = '#0071e3';
        startBtn.style.color = '#fff';
        startBtn.style.cursor = 'pointer';
        startBtn.style.opacity = '1';
    } else {
        startBtn.className = 'action-btn btn-disabled';
        startBtn.disabled = true;
        startBtn.style.background = '#8e8e93';
        startBtn.style.color = '#fff';
        startBtn.style.cursor = 'not-allowed';
        startBtn.style.opacity = '0.6';
    }
}

let krtiTakeoffOverrideLat = null;
let krtiTakeoffOverrideLng = null;

function resetKrtiTakeoffToDroneGps() {
    krtiTakeoffOverrideLat = null;
    krtiTakeoffOverrideLng = null;
    if (typeof showKrtiToast === 'function') {
        showKrtiToast("Takeoff WP1 reset to Drone Real-time GPS!", "info");
    }
    redrawCalibrationWaypoints();
}

function formatKrtiWaypoints() {
    let prevLat = (typeof krtiTakeoffOverrideLat === 'number' && krtiTakeoffOverrideLat !== 0)
        ? krtiTakeoffOverrideLat
        : ((globalTelemetry && globalTelemetry.lat && globalTelemetry.lat !== 0) ? globalTelemetry.lat : -6.8760782616578595);
    let prevLng = (typeof krtiTakeoffOverrideLng === 'number' && krtiTakeoffOverrideLng !== 0)
        ? krtiTakeoffOverrideLng
        : ((globalTelemetry && globalTelemetry.lng && globalTelemetry.lng !== 0) ? globalTelemetry.lng : 107.6214877492015);
    let cumulativeHeading = (globalTelemetry && globalTelemetry.heading) ? globalTelemetry.heading : 0.0;

    let localX = 0.0;
    let localY = 0.0;

    return krtiCalWaypoints.map((wp) => {
        const deltaYaw = parseFloat(wp.headingDelta) || 0;
        cumulativeHeading = (cumulativeHeading + deltaYaw + 360) % 360;

        let coords = [prevLat, prevLng];
        const dist = parseFloat(wp.distance) || 0;

        if (dist > 0) {
            // Calculate target Lat/Lng using Haversine offset FROM THE PREVIOUS POINT (prevLat, prevLng)
            coords = getGpsOffset(prevLat, prevLng, cumulativeHeading, dist);
            prevLat = coords[0];
            prevLng = coords[1];

            // Accumulate local ENU position (meters from home/starting point):
            const hRad = cumulativeHeading * Math.PI / 180.0;
            localX += dist * Math.sin(hRad);  // East (X)
            localY += dist * Math.cos(hRad);  // North (Y)
        }

        let targetAlt = parseFloat(wp.alt);
        if (isNaN(targetAlt) || (wp.type === 'takeoff' && targetAlt <= 0)) {
            targetAlt = (wp.type === 'takeoff') ? 3.0 : (wp.type === 'landing' ? 0.0 : 3.0);
        }

        return {
            index: idx + 1,
            type: wp.type,
            lat: coords[0],
            lng: coords[1],
            alt: targetAlt,
            speed: parseFloat(wp.speed) || 3.0
        };
    });
}

function saveWaypoints() {
    if (krtiCalWaypoints.length < 3) {
        showKrtiToast("Minimum 3 waypoints required: WP1 (TAKEOFF), WP2 (JETPOINT), and WP3 (LANDING)!", "warning");
        return;
    }

    updateWaypointRolesAndIndexes();
    saveCalWaypointsToStorage();
    redrawCalibrationWaypoints();

    // Enable START AUTO button
    krtiMissionPublished = true;
    updateStartAutoButtonState(true);

    showKrtiToast(`Mission with ${krtiCalWaypoints.length} Waypoints Saved locally!`, "success");
    closeKrtiCalModal();
}

function exportCalibrationWaypoints() {
    if (krtiCalWaypoints.length === 0) {
        showKrtiToast("No waypoints to export!", "warning");
        return;
    }
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(krtiCalWaypoints, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "krti_calibration_mission.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    showKrtiToast("Calibration Mission exported to JSON file!", "success");
}

function redrawCalibrationWaypoints() {
    krtiCalMarkers.forEach(m => map.removeLayer(m));
    krtiCalMarkers = [];
    krtiCalSegments.forEach(s => map.removeLayer(s));
    krtiCalSegments = [];

    // STRICT MODE CHECK: Do not draw KRTI markers unless currentMode is 'krti'
    if (typeof currentMode !== 'undefined' && currentMode !== 'krti') {
        return;
    }

    if (!krtiCalWaypoints || krtiCalWaypoints.length === 0) return;

    let baseHeading = (globalTelemetry && globalTelemetry.heading) ? globalTelemetry.heading : 0;
    let droneLat = (typeof krtiTakeoffOverrideLat === 'number' && krtiTakeoffOverrideLat !== 0)
        ? krtiTakeoffOverrideLat
        : ((globalTelemetry && globalTelemetry.lat && globalTelemetry.lat !== 0) ? globalTelemetry.lat : -6.8760782616578595);

    let droneLng = (typeof krtiTakeoffOverrideLng === 'number' && krtiTakeoffOverrideLng !== 0)
        ? krtiTakeoffOverrideLng
        : ((globalTelemetry && globalTelemetry.lng && globalTelemetry.lng !== 0) ? globalTelemetry.lng : 107.6214877492015);

    let prevLat = droneLat;
    let prevLng = droneLng;
    let cumulativeHeading = baseHeading;
    const computedPoints = [];

    krtiCalWaypoints.forEach((wp, idx) => {
        const deltaYaw = parseFloat(wp.headingDelta) || 0;
        cumulativeHeading = (cumulativeHeading + deltaYaw + 360) % 360;
        const dist = parseFloat(wp.distance) || 0;

        let coords = [prevLat, prevLng];
        if (dist > 0) {
            // Chained coordinate calculation from previous point (prevLat, prevLng)
            coords = getGpsOffset(prevLat, prevLng, cumulativeHeading, dist);
            prevLat = coords[0];
            prevLng = coords[1];
        }
        computedPoints.push({ coords: coords, wp: wp, heading: cumulativeHeading, index: idx + 1 });
    });

    // 1. Draw continuous connecting path lines starting from DRONE NOSE/POSITION (Hijau Stabilo Glow #30d158 + dashed main line + segment distance badges)
    const fullPathCoords = [ [droneLat, droneLng], ...computedPoints.map(p => p.coords) ];

    const glowLine = L.polyline(fullPathCoords, {
        color: '#30d158',
        weight: 10,
        opacity: 0.45,
        className: 'waypoint-glow-line'
    }).addTo(map);
    krtiCalSegments.push(glowLine);

    const mainLine = L.polyline(fullPathCoords, {
        color: '#30d158',
        weight: 3.5,
        opacity: 0.95,
        dashArray: '6, 6',
        className: 'waypoint-main-line'
    }).addTo(map);
    krtiCalSegments.push(mainLine);

    // Segment distance & heading indicators at midpoints (including from Drone nose to WP1)
    const allSegmentNodes = [ { coords: [droneLat, droneLng], heading: baseHeading }, ...computedPoints ];
    for (let i = 0; i < allSegmentNodes.length - 1; i++) {
        const p1 = allSegmentNodes[i];
        const p2 = allSegmentNodes[i + 1];
        if (p2.wp && p2.wp.distance > 0) {
            const midLat = (p1.coords[0] + p2.coords[0]) / 2;
            const midLng = (p1.coords[1] + p2.coords[1]) / 2;
            const distBadgeIcon = L.divIcon({
                className: 'wp-seg-badge',
                html: `<div style="background: none !important; border: none !important; box-shadow: none !important; color: #ffffff !important; font-size: 10.5px; font-weight: 800; transform: translate(-50%, -50%); white-space: nowrap; font-family: 'Poppins', sans-serif; text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000, 0 2px 4px rgba(0,0,0,0.8);">${p2.wp.distance}m / ${p2.heading.toFixed(0)}°</div>`,
                iconSize: [0, 0],
                iconAnchor: [0, 0]
            });
            const segMarker = L.marker([midLat, midLng], { icon: distBadgeIcon, interactive: false }).addTo(map);
            krtiCalSegments.push(segMarker);
        }
    }

    // 2. Draw vector triangle markers with directional yaw indicators and Lat/Lng info labels
    computedPoints.forEach((pt) => {
        const wp = pt.wp;
        const coords = pt.coords;
        const cumulativeHeading = pt.heading;

        // Color match with Auto Waypoint: Takeoff/Landing = Orange (#ff9500), Waypoints = Blue (#0071e3)
        let color = (wp.type === 'takeoff' || wp.type === 'landing') ? '#ff9500' : '#0071e3';

        const triangleHtml = `
            <div style="position: relative; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center;">
                <svg viewBox="0 0 22 22" width="22" height="22" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.6));">
                    <polygon points="11,1 21,20 1,20" fill="${color}" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/>
                </svg>
                <span style="position: absolute; top: 7px; color: #ffffff; font-weight: 800; font-size: 8.5px; font-family: 'Poppins', sans-serif; text-shadow: 0 1px 2px rgba(0,0,0,0.8);">${wp.wp}</span>
            </div>
        `;

        const customMarkerIcon = L.divIcon({
            className: 'wp-custom-node-krti',
            html: triangleHtml,
            iconSize: [22, 22],
            iconAnchor: [11, 11]
        });

        const isTakeoffMarker = (wp.type === 'takeoff' || pt.index === 1);
        const marker = L.marker(coords, {
            icon: customMarkerIcon,
            zIndexOffset: 1000,
            draggable: isTakeoffMarker
        }).addTo(map);

        if (isTakeoffMarker) {
            marker.on('dragend', function (e) {
                const newPos = e.target.getLatLng();
                krtiTakeoffOverrideLat = newPos.lat;
                krtiTakeoffOverrideLng = newPos.lng;
                showKrtiToast(`Takeoff WP1 position set on map: ${newPos.lat.toFixed(6)}, ${newPos.lng.toFixed(6)}`, 'info');
                redrawCalibrationWaypoints();
            });
        }

        const yawStr = `${wp.headingDelta >= 0 ? '+' : ''}${wp.headingDelta}°`;
        marker.bindPopup(`
            <div style="font-family: 'Poppins', sans-serif; padding: 2px;">
                <b style="color: ${color}; font-size: 13px;">${wp.name || 'WP ' + wp.wp}</b><br>
                <div style="margin-top: 4px; font-size: 11.5px; line-height: 1.5; color: #1c1c1e;">
                    📍 <b>Distance:</b> ${wp.distance} m<br>
                    📐 <b>Yaw Δ:</b> ${yawStr} (Target HDG: <b>${cumulativeHeading.toFixed(1)}°</b>)<br>
                    🏔️ <b>Altitude:</b> ${wp.alt} m | ⚡ <b>Speed:</b> ${wp.speed} m/s<br>
                    🌐 <b>Lat:</b> ${coords[0].toFixed(6)} | <b>Lng:</b> ${coords[1].toFixed(6)}
                </div>
            </div>
        `);
        krtiCalMarkers.push(marker);

        // Rich map label with clean White background displaying WP details
        const labelTitle = wp.name ? wp.name : `WP${wp.wp} (${wp.type.toUpperCase()})`;
        const latStr = coords[0].toFixed(6);
        const lngStr = coords[1].toFixed(6);
        const detailsText = `Alt:${wp.alt}m | Spd:${wp.speed}m/s | Lat:${latStr}, ${lngStr}`;

        const richLabelHtml = `
            <div style="transform: translate(-50%, -42px); display: flex; flex-direction: column; align-items: center; pointer-events: none;">
                <div style="background: #ffffff; border: 1px solid var(--border-soft); border-radius: 6px; padding: 3px 8px; color: #1d1d1f; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.2); font-family: 'Poppins', sans-serif; white-space: nowrap;">
                    <div style="font-weight: 800; font-size: 10.5px; color: ${color}; letter-spacing: 0.3px;">${labelTitle}</div>
                    <div style="font-size: 9px; color: var(--text-muted); font-weight: 600; margin-top: 1px;">${detailsText}</div>
                </div>
            </div>
        `;

        const labelIcon = L.divIcon({
            className: 'wp-map-rich-label-krti',
            html: richLabelHtml,
            iconSize: [0, 0],
            iconAnchor: [0, 0]
        });
        const labelMarker = L.marker(coords, { icon: labelIcon, interactive: false, zIndexOffset: 200 }).addTo(map);
        krtiCalMarkers.push(labelMarker);
    });
}

function renderCalibrationListUI() {
    const container = document.getElementById('krti-cal-list-container');
    const badgeMap = document.getElementById('krti-wp-count-badge');
    const badgeModal = document.getElementById('krti-modal-wp-count-badge');

    const total = krtiCalWaypoints.length;
    const countStr = `TOTAL WP: ${total}`;
    if (badgeMap) badgeMap.innerText = countStr;
    if (badgeModal) badgeModal.innerText = countStr;

    if (!container) return;

    if (total === 0) {
        container.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-muted); font-style: italic; font-size: 11px;" id="krti-cal-empty-text">No waypoints added yet. Click "+ Add Waypoint" above to start.</div>`;
        return;
    }

    let html = '';
    krtiCalWaypoints.forEach((wp, idx) => {
        // ── Sync defaults to data model on every render (ensures data model = what UI shows)
        if (wp.alt === undefined || wp.alt === null) wp.alt = (wp.type === 'takeoff' ? 3 : (wp.type === 'landing' ? 0 : 3));
        if (wp.speed === undefined || wp.speed === null) wp.speed = (wp.type === 'landing' ? 0 : 3);
        if (wp.distance === undefined || wp.distance === null) wp.distance = (wp.type === 'takeoff' ? 0 : 5);

        let typeColor = wp.color || (wp.type === 'takeoff' ? '#28a745' : (wp.type === 'landing' ? '#ff3b30' : '#0071e3'));
        let bgStyle = wp.type === 'takeoff' ? 'rgba(40, 167, 69, 0.08)' : (wp.type === 'landing' ? 'rgba(255, 59, 48, 0.08)' : 'rgba(0, 113, 227, 0.08)');
        let borderStyle = wp.type === 'takeoff' ? 'rgba(40, 167, 69, 0.25)' : (wp.type === 'landing' ? 'rgba(255, 59, 48, 0.25)' : 'rgba(0, 113, 227, 0.25)');

        const isLanding = (wp.type === 'landing');
        const landingAltDisabled = isLanding ? 'disabled="disabled"' : '';
        const landingAltStyle = isLanding ? 'opacity: 0.45; cursor: not-allowed; background: #e5e5ea; color: #8e8e93;' : 'background: #ffffff; color: var(--text-dark);';

        html += `
            <div class="krti-wp-card" style="background: #f9f9fb; border: 1px solid var(--border-soft); border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-soft); padding-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-weight: 800; font-size: 11px; color: ${typeColor}; text-transform: uppercase; background: ${bgStyle}; padding: 3px 8px; border-radius: 6px; border: 1px solid ${borderStyle};">${wp.name}</span>
                        <span style="font-size: 9.5px; color: var(--text-muted); font-weight: 500;">${wp.note || ''}</span>
                    </div>
                    <button type="button" onclick="deleteCalibrationWaypoint(${idx})" style="background: rgba(255, 59, 48, 0.08); border: 1px solid rgba(255, 59, 48, 0.25); color: #ff3b30; font-size: 10.5px; font-weight: 700; border-radius: 6px; padding: 3px 10px; cursor: pointer; transition: all 0.2s ease;" title="Delete this Waypoint">✕ Delete</button>
                </div>

                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; align-items: center;">
                    <div style="display: flex; flex-direction: column; gap: 3px;">
                        <label style="font-size: 8.5px; color: var(--text-muted); font-weight: 700; letter-spacing: 0.3px;">YAW Δ (°)</label>
                        <input type="number" value="${wp.headingDelta || 0}" min="-180" max="180" oninput="updateWpField(${idx}, 'headingDelta', this.value)" onchange="updateWpField(${idx}, 'headingDelta', this.value)" class="apple-input" style="height: 30px; padding: 2px 6px; font-size: 12px; font-weight: 700; width: 100%; border-radius: 6px; border: 1px solid #d1d1d6; background: #ffffff; color: var(--text-dark); text-align: center; box-sizing: border-box;">
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 3px;">
                        <label style="font-size: 8.5px; color: var(--text-muted); font-weight: 700; letter-spacing: 0.3px;">DIST (M)</label>
                        <input type="number" value="${wp.distance !== undefined ? wp.distance : (isLanding ? 0 : 5)}" min="0" oninput="updateWpField(${idx}, 'distance', this.value)" onchange="updateWpField(${idx}, 'distance', this.value)" class="apple-input" style="height: 30px; padding: 2px 6px; font-size: 12px; font-weight: 700; width: 100%; border-radius: 6px; border: 1px solid #d1d1d6; background: #ffffff; color: var(--text-dark); text-align: center; box-sizing: border-box;">
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 3px;">
                        <label style="font-size: 8.5px; color: var(--text-muted); font-weight: 700; letter-spacing: 0.3px;">ALT (M)</label>
                        <input type="number" value="${isLanding ? 0 : (wp.alt !== undefined && wp.alt !== null ? wp.alt : 3)}" ${landingAltDisabled} min="0" step="0.5" oninput="updateWpField(${idx}, 'alt', this.value)" class="apple-input" style="height: 30px; padding: 2px 6px; font-size: 12px; font-weight: 700; width: 100%; border-radius: 6px; border: 1px solid #d1d1d6; ${landingAltStyle} text-align: center; box-sizing: border-box;">
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 3px;">
                        <label style="font-size: 8.5px; color: var(--text-muted); font-weight: 700; letter-spacing: 0.3px;">SPEED (M/S)</label>
                        <input type="number" value="${isLanding ? 0 : (wp.speed || 3)}" ${landingAltDisabled} min="0" step="0.5" oninput="updateWpField(${idx}, 'speed', this.value)" class="apple-input" style="height: 30px; padding: 2px 6px; font-size: 12px; font-weight: 700; width: 100%; border-radius: 6px; border: 1px solid #d1d1d6; ${landingAltStyle} text-align: center; box-sizing: border-box;">
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    const savePublishBtn = document.getElementById('krti-save-publish-btn');
    if (savePublishBtn) {
        if (total < 3) {
            savePublishBtn.disabled = true;
            savePublishBtn.style.background = '#8e8e93';
            savePublishBtn.style.borderColor = '#8e8e93';
            savePublishBtn.style.cursor = 'not-allowed';
            savePublishBtn.style.opacity = '0.6';
            savePublishBtn.style.boxShadow = 'none';
            savePublishBtn.innerText = 'SAVE MISSION (MIN 3 WP)';
        } else {
            savePublishBtn.disabled = false;
            savePublishBtn.style.background = 'var(--apple-blue)';
            savePublishBtn.style.borderColor = 'var(--apple-blue)';
            savePublishBtn.style.cursor = 'pointer';
            savePublishBtn.style.opacity = '1';
            savePublishBtn.style.boxShadow = '0 4px 12px rgba(0, 113, 227, 0.3)';
            savePublishBtn.innerText = 'SAVE MISSION';
        }
    }
}

function loadCalWaypointsFromStorage() {
    try {
        const stored = localStorage.getItem('krtiCalWaypoints');
        if (stored) {
            const arr = JSON.parse(stored);
            if (Array.isArray(arr) && arr.length > 0) {
                krtiCalWaypoints = arr;
                updateWaypointRolesAndIndexes();
                krtiMissionPublished = false;
                updateStartAutoButtonState(false);
            }
        }
    } catch (e) {
        console.error("Failed to load calibration waypoints:", e);
    }
}

function saveCalWaypointsToStorage() {
    try {
        localStorage.setItem('krtiCalWaypoints', JSON.stringify(krtiCalWaypoints));
    } catch (e) {
        console.error("Failed to save calibration waypoints to localStorage:", e);
    }
}

// Initialize calibration waypoints on startup
loadCalWaypointsFromStorage();
setTimeout(() => {
    if (typeof map !== 'undefined' && map) {
        redrawCalibrationWaypoints();
    }
    renderCalibrationListUI();
}, 1000);
