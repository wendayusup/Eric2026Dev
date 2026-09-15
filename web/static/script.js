const DEFAULT_LAT = -6.8760782616578595;
const DEFAULT_LNG = 107.6214877492015;

const map = L.map('map', {
    maxZoom: 23,
    minZoom: 3
}).setView([DEFAULT_LAT, DEFAULT_LNG], 20);

// Definisi Map Layers (Terrain, Satellite, OpenStreetMap, Google Satellite)
const layers = {
    terrain: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', { 
        maxZoom: 23,
        maxNativeZoom: 18,
        attribution: 'Esri Topo' 
    }),
    satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { 
        maxZoom: 23,
        maxNativeZoom: 19,
        attribution: 'Esri Satellite' 
    }),
    osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 23,
        maxNativeZoom: 19,
        attribution: 'OpenStreetMap'
    }),
    googleSat: L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
        maxZoom: 23,
        maxNativeZoom: 20,
        attribution: 'Google Satellite'
    })
};

// Set Default Layer to Satellite
layers.satellite.addTo(map);
let activeLayerKey = 'satellite';

setTimeout(() => { if (map) map.invalidateSize(); }, 300);
window.addEventListener('resize', () => { if (map) map.invalidateSize(); });

function calculateDistanceAndBearing(lat1, lng1, lat2, lng2) {
    const R = 6371000; // Earth radius in meters
    const phi1 = lat1 * Math.PI / 180;
    const phi2 = lat2 * Math.PI / 180;
    const dPhi = (lat2 - lat1) * Math.PI / 180;
    const dLambda = (lng2 - lng1) * Math.PI / 180;

    const a = Math.sin(dPhi / 2) * Math.sin(dPhi / 2) +
              Math.cos(phi1) * Math.cos(phi2) *
              Math.sin(dLambda / 2) * Math.sin(dLambda / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const dist = R * c;

    const y = Math.sin(dLambda) * Math.cos(phi2);
    const x = Math.cos(phi1) * Math.sin(phi2) -
              Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda);
    let bearing = Math.atan2(y, x) * 180 / Math.PI;
    bearing = (bearing + 360) % 360;

    return { dist: dist, bearing: bearing };
}

function getWpLabelTextColor() {
    // SAR Tactical Orange (#ff6b00) for high visibility mission planning
    return '#ff6b00';
}

function getWpLabelHtml(labelText, customColor = null) {
    const textColor = customColor ? customColor : getWpLabelTextColor();
    const shadowColor = 'rgba(0,0,0,0.95)';
    return `<div class="wp-text-only-label" style="
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        color: ${textColor} !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        white-space: nowrap;
        text-shadow: -1px -1px 0 ${shadowColor}, 1px -1px 0 ${shadowColor}, -1px 1px 0 ${shadowColor}, 1px 1px 0 ${shadowColor};
        transform: translate(-50%, -20px);
        transition: color 0.3s ease;
    ">${labelText}</div>`;
}

function changeMapLayer(key) {
    if (layers[key]) {
        map.removeLayer(layers[activeLayerKey]);
        layers[key].addTo(map);
        activeLayerKey = key;

        if (currentMode === 'krti' && typeof redrawCalibrationWaypoints === 'function') redrawCalibrationWaypoints();
        if (currentMode === 'auto' && typeof redrawAutoMissionMap === 'function') redrawAutoMissionMap();
    }
}

const droneSVG = `<svg viewBox="0 0 34 34" width="34" height="34"><circle cx="17" cy="17" r="14" fill="rgba(255, 107, 0, 0.25)" stroke="#ff6b00" stroke-width="2"/><polygon points="17,5 24,24 17,20 10,24" fill="#ff6b00" stroke="#fff" stroke-width="1.5"/></svg>`;
const droneIcon = L.divIcon({ html: `<div id="drone-marker-element" style="transform: rotate(0deg); display:flex; justify-content:center; align-items:center; width:34px; height:34px; transform-origin: center center;">${droneSVG}</div>`, className: 'custom-icon', iconSize: [34, 34], iconAnchor: [17, 17] });
const droneMarker = L.marker([DEFAULT_LAT, DEFAULT_LNG], { icon: droneIcon, zIndexOffset: 1000 }).addTo(map);

let currentMode = 'manual';
let globalTelemetry = { alt: 0.0, lat: 0.0, lng: 0.0 };

let altChart = null;
let speedChart = null;
const maxChartPoints = 30;

function initTelemetryCharts() {
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
                    grid: { color: 'rgba(15, 23, 42, 0.08)' },
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
                    grid: { color: 'rgba(15, 23, 42, 0.08)' },
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
                    grid: { color: 'rgba(15, 23, 42, 0.08)' },
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
                    grid: { color: 'rgba(15, 23, 42, 0.08)' },
                    ticks: { color: '#ff6b00', font: { size: 9 } }
                }
            }
        }
    });
}

function updateTelemetryCharts(alt, speed) {
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

    // Update value displays
    const altValEl = document.getElementById('chart-alt-val');
    const speedValEl = document.getElementById('chart-speed-val');
    if (altValEl) altValEl.innerText = alt.toFixed(2) + " M";
    if (speedValEl) speedValEl.innerText = speed.toFixed(2) + " M/S";
}

let mapSelectedLatLng = null;
// lastManualTargetLatLng is declared in manual_control.js

let tempSelectionMarker = null;

let followDrone = true; // Auto-center map on drone position by default
let lastCurrentWpIndex = -1;
let lastTelemetryTime = 0;
let lastRaspiTime = 0;
let isConnectedState = false;
let statusTimeout = null;

function updateMapStatus(statusText, color, temp = false) {
    const el = document.getElementById('map-status-telem');
    if (el) {
        el.innerText = statusText.toUpperCase();
        el.style.color = color;
    }
    if (statusTimeout) {
        clearTimeout(statusTimeout);
        statusTimeout = null;
    }
    if (temp) {
        statusTimeout = setTimeout(() => {
            const isConnected = (Date.now() - lastTelemetryTime) < 5000;
            if (isConnected) {
                updateMapStatus("CONNECTED", "#34c759", false);
            } else {
                updateMapStatus("DISCONNECTED", "#ff453a", false);
            }
        }, 3000);
    }
}

function updateRaspiStatus(statusText, color) {
    const el = document.getElementById('map-status-raspi');
    if (el) {
        el.innerText = statusText.toUpperCase();
        el.style.color = color;
    }
}

function markRaspiActive() {
    lastRaspiTime = Date.now();
    updateRaspiStatus("CONNECTED", "#34c759");
}

// Connection checker interval for Telem & Raspi
setInterval(() => {
    // 1. Telemetry Check
    if (Date.now() - lastTelemetryTime > 5000) {
        isConnectedState = false;
        if (!statusTimeout) {
            updateMapStatus("DISCONNECTED", "#ff453a", false);
        }
    }
    // 2. Raspi Check
    if (Date.now() - lastRaspiTime > 5000) {
        updateRaspiStatus("DISCONNECTED", "#ff453a");
    }
}, 1000);

function recenterMap() {
    if (globalTelemetry && globalTelemetry.lat && globalTelemetry.lat !== 0) {
        map.setView([globalTelemetry.lat, globalTelemetry.lng]);
    } else if (typeof krtiCalMarkers !== 'undefined' && krtiCalMarkers.length > 0) {
        const firstMarker = krtiCalMarkers[0];
        if (firstMarker) {
            map.setView(firstMarker.getLatLng(), 20);
        }
    } else {
        map.setView([DEFAULT_LAT, DEFAULT_LNG], 20);
    }
}

function toggleFollowDrone() {
    followDrone = !followDrone;
    const btn = document.getElementById('btn-follow');
    const ind = document.getElementById('follow-indicator');
    if (followDrone) {
        btn.style.background = '#86868b'; // Gray when following
        ind.style.backgroundColor = '#fff';
        recenterMap();
    } else {
        btn.style.background = 'var(--apple-green)'; // Green when NOT following
        ind.style.backgroundColor = '#fff';
    }
}

// Disable follow mode if user manually drags/pans the map
map.on('dragstart', function () {
    if (followDrone) {
        toggleFollowDrone();
    }
});

// Shared state — declared here so all module JS files can access them
// (manual_control.js, auto_waypoint.js, krti_mode.js are loaded after this file)
let lastManualTargetLatLng = null;
let manualStartLatLng = null;
let manualTargetLatLng = null;
let manualSegments = [];

let autoMissionArray = [];
let autoMarkers = [];
let autoSegments = [];
let passedWaypointIndices = new Set();
let missionActive = false;

map.on('click', function (e) {
    mapSelectedLatLng = e.latlng;

    if (tempSelectionMarker) { map.removeLayer(tempSelectionMarker); }

    tempSelectionMarker = L.circleMarker(mapSelectedLatLng, {
        radius: 8, fillColor: '#86868b', color: '#1d1d1f', weight: 2, fillOpacity: 0.5, dashArray: '3, 3'
    }).addTo(map);

    if (currentMode === 'manual') {
        document.getElementById('manual-target-coords').innerText = `${mapSelectedLatLng.lat.toFixed(5)}, ${mapSelectedLatLng.lng.toFixed(5)}`;
    } else if (currentMode === 'krti') {
        // In KRTI mode: clicking map sets the GPS for current selected slot and opens modal
        window._capturedLat = mapSelectedLatLng.lat;
        window._capturedLng = mapSelectedLatLng.lng;
        const displayEl = document.getElementById('krti-cal-gps-display');
        if (displayEl) {
            displayEl.innerText = `${mapSelectedLatLng.lat.toFixed(6)}, ${mapSelectedLatLng.lng.toFixed(6)}`;
        }
        if (typeof openKrtiCalModal === 'function') {
            openKrtiCalModal();
        }
    } else {
        document.getElementById('panel-auto-waypoint').style.borderColor = 'var(--apple-orange)';
        const autoCoordEl = document.getElementById('auto-target-coords');
        if (autoCoordEl) {
            autoCoordEl.innerText = `${mapSelectedLatLng.lat.toFixed(5)}, ${mapSelectedLatLng.lng.toFixed(5)}`;
        }
    }
});

function switchMode(mode) {
    currentMode = mode;
    const manualBtn = document.getElementById('mode-manual-trigger');
    const autoBtn = document.getElementById('mode-auto-trigger');
    const krtiBtn = document.getElementById('mode-krti-trigger');
    
    if (manualBtn) manualBtn.classList.toggle('active', mode === 'manual');
    if (autoBtn) autoBtn.classList.toggle('active', mode === 'auto');
    if (krtiBtn) krtiBtn.classList.toggle('active', mode === 'krti');

    const panelManual = document.getElementById('panel-manual-control');
    const panelAuto = document.getElementById('panel-auto-waypoint');
    const panelKrti = document.getElementById('panel-krti-mode');

    if (panelManual) panelManual.style.display = mode === 'manual' ? 'flex' : 'none';
    if (panelAuto) panelAuto.style.display = mode === 'auto' ? 'flex' : 'none';
    if (panelKrti) panelKrti.style.display = mode === 'krti' ? 'flex' : 'none';

    const calBtnTrigger = document.getElementById('btn-krti-cal-trigger');
    if (calBtnTrigger) {
        calBtnTrigger.style.display = mode === 'krti' ? 'flex' : 'none';
    }
    if (mode !== 'krti' && typeof closeKrtiCalModal === 'function') {
        closeKrtiCalModal();
    }

    // Toggle Map Marker Visibility based on Active Mode (prevent mixing markers)
    if (mode === 'krti') {
        // Hide Auto Waypoint Markers & Lines
        autoMarkers.forEach(m => { if (m && map.hasLayer(m)) map.removeLayer(m); });
        autoSegments.forEach(s => { if (s && map.hasLayer(s)) map.removeLayer(s); });
        // Redraw KRTI Mode Markers & Lines
        if (typeof redrawCalibrationWaypoints === 'function') {
            redrawCalibrationWaypoints();
        }
    } else {
        // Hide KRTI Mode Markers & Lines
        if (typeof krtiCalMarkers !== 'undefined') {
            krtiCalMarkers.forEach(m => { if (m && map.hasLayer(m)) map.removeLayer(m); });
        }
        if (typeof krtiCalSegments !== 'undefined') {
            krtiCalSegments.forEach(s => { if (s && map.hasLayer(s)) map.removeLayer(s); });
        }
        // Redraw Auto Waypoint Markers & Lines if in auto mode
        if (mode === 'auto' && typeof redrawAutoMissionMap === 'function') {
            redrawAutoMissionMap();
        }
    }

    // Force Chart.js resize untuk memicu penggambaran ulang grafik sesuai tinggi kontainer baru
    if (mode === 'krti') {
        setTimeout(() => {
            if (typeof altChart !== 'undefined' && altChart) altChart.resize();
            if (typeof speedChart !== 'undefined' && speedChart) speedChart.resize();
        }, 50);
    }

    if (tempSelectionMarker) { map.removeLayer(tempSelectionMarker); tempSelectionMarker = null; }
    document.getElementById('manual-target-coords').innerText = 'NOT SELECTED';
    const autoCoordEl = document.getElementById('auto-target-coords');
    if (autoCoordEl) {
        autoCoordEl.innerText = 'NOT SELECTED';
    }
    mapSelectedLatLng = null;
    lastManualTargetLatLng = null;

    // Bersihkan manual guided segments saat berganti mode
    if (manualSegments.length > 0) {
        manualSegments.forEach(s => map.removeLayer(s));
        manualSegments = [];
    }
    manualStartLatLng = null;
    manualTargetLatLng = null;
}

// sendKrtiAction is moved to krti_mode.js

function triggerUploadProcess(type) {
    if (type === 'manual') {
        const targetLatLng = mapSelectedLatLng || lastManualTargetLatLng;
        if (!targetLatLng) return showCustomAlert("Notification", "Please select 1 point on the map first!", "warning");
        const isFlying = globalTelemetry && globalTelemetry.is_armed && globalTelemetry.alt >= 0.5;
        if (!isFlying) return showCustomAlert("Manual Guided Failed", "FAILED! Drone must be armed and flying (alt >= 0.5m) before executing manual guided.", "error");
    } else if (type === 'auto') {
        const takeoffs = autoMissionArray.filter(wp => wp.type === 'takeoff').length;
        const waypoints = autoMissionArray.filter(wp => wp.type === 'waypoint').length;
        const landings = autoMissionArray.filter(wp => wp.type === 'landing').length;
        const isFlying = globalTelemetry && globalTelemetry.is_armed && globalTelemetry.alt >= 0.5;

        if (isFlying) {
            // Drone is already flying: Takeoff is optional (max 1)
            if (takeoffs > 1) {
                showCustomAlert("Invalid Flight Plan", "Route can have at most 1 TAKEOFF point.", "warning");
                return;
            }
            if (takeoffs === 1 && autoMissionArray[0].type !== 'takeoff') {
                showCustomAlert("Invalid Flight Plan", "If a TAKEOFF point is present, the route must begin with it.", "warning");
                return;
            }
        } else {
            // Drone is on the ground: Takeoff is mandatory
            if (takeoffs !== 1) {
                showCustomAlert("Invalid Flight Plan", "Route must have exactly 1 TAKEOFF point when on the ground.", "warning");
                return;
            }
            if (autoMissionArray[0].type !== 'takeoff') {
                showCustomAlert("Invalid Flight Plan", "Route must begin with a TAKEOFF point.", "warning");
                return;
            }
        }

        if (waypoints < 1) {
            showCustomAlert("Invalid Flight Plan", "Route must have at least 1 standard WAYPOINT.", "warning");
            return;
        }
        if (landings !== 1) {
            showCustomAlert("Invalid Flight Plan", "Route must have exactly 1 LANDING point.", "warning");
            return;
        }
        if (autoMissionArray[autoMissionArray.length - 1].type !== 'landing') {
            showCustomAlert("Invalid Flight Plan", "Route must end with a LANDING point.", "warning");
            return;
        }
    }

    if (type === 'manual') {
        updateMapStatus("SENDING GUIDED TARGET...", "#0071e3", true);
        if (typeof addSystemLog === 'function') addSystemLog('Sending guided target coordinates to vehicle...', 'info');
    } else {
        updateMapStatus("UPLOADING MISSION...", "#ff9500", true);
        if (typeof addSystemLog === 'function') addSystemLog(`Mission upload started: ${autoMissionArray.length} waypoints.`, 'warning');
    }

    const btn = document.getElementById(`btn-upload-${type}`);
    const progBar = document.getElementById(`prog-${type}`);
    const txt = document.getElementById(`txt-${type}`);
    const originalText = txt.innerText;

    btn.disabled = true;
    progBar.style.width = "0%";
    txt.innerHTML = `<span style="display:inline-block; width:11px; height:11px; border:2px solid #fff; border-radius:50%; border-top-color:transparent; animation:krti-spin 0.8s linear infinite; margin-right:6px; vertical-align:middle;"></span>UPLOADING... 0%`;

    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.floor(Math.random() * 15) + 5;
        if (progress > 100) progress = 100;
        progBar.style.width = `${progress}%`;
        txt.innerHTML = `<span style="display:inline-block; width:11px; height:11px; border:2px solid #fff; border-radius:50%; border-top-color:transparent; animation:krti-spin 0.8s linear infinite; margin-right:6px; vertical-align:middle;"></span>UPLOADING... ${progress}%`;

        if (progress === 100) {
            clearInterval(interval);
            txt.innerText = "✓ SUCCESS!";

            setTimeout(() => {
                if (type === 'manual') {
                    if (manualSegments.length > 0) {
                        manualSegments.forEach(s => map.removeLayer(s));
                        manualSegments = [];
                    }
                    const targetLatLng = mapSelectedLatLng || lastManualTargetLatLng;
                    manualStartLatLng = { lat: globalTelemetry.lat, lng: globalTelemetry.lng };
                    manualTargetLatLng = { lat: targetLatLng.lat, lng: targetLatLng.lng };

                    let speedVal = parseFloat(document.getElementById('manual-speed').value);
                    if (isNaN(speedVal)) speedVal = 4.0;
                    if (speedVal > 10.0) {
                        speedVal = 10.0;
                        document.getElementById('manual-speed').value = 10.0;
                    }

                    socket.emit('set_manual_target', {
                        lat: targetLatLng.lat,
                        lng: targetLatLng.lng,
                        alt: document.getElementById('manual-alt').value,
                        speed: speedVal
                    });

                    lastManualTargetLatLng = targetLatLng;
                    if (tempSelectionMarker) {
                        tempSelectionMarker.setStyle({ fillColor: 'var(--apple-blue)', fillOpacity: 1, dashArray: '' });
                    }
                    mapSelectedLatLng = null;

                    updateManualGuidedPath();
                } else {
                    passedWaypointIndices.clear(); // Reset passed state untuk misi baru
                    missionActive = true;          // Aktifkan tracking setelah upload
                    socket.emit('transmit_auto_mission', autoMissionArray);
                }

                btn.disabled = false;
                progBar.style.width = "0%";
                txt.innerText = originalText;
            }, 1000);
        }
    }, 300);
}

// Mode-specific execution functions are moved to manual_control.js and auto_waypoint.js

const socket = io(`${window.location.protocol}//${window.location.hostname}:5000`);

socket.on('upload_status', (data) => {
    const type = data.status === 'success' ? 'success' : 'error';
    const title = data.status === 'success' ? 'UPLOAD SUCCESS' : 'UPLOAD FAILED';
    
    // Always use non-blocking toast notification instead of modal popups requiring OK click!
    if (typeof showToastAlert === 'function') {
        showToastAlert(title, data.message, type, 4000);
    }
    
    if (data.status === 'success') {
        updateMapStatus("AUTO MISSION ACTIVE", "#34c759", true);
    } else {
        updateMapStatus("UPLOAD FAILED", "#ff453a", true);
    }
});

socket.on('status_msg', (data) => {
    console.log("[FCS GCS] Received status_msg:", data);
    const alertType = data.type === 'error' ? 'error' : (data.type === 'warning' ? 'warning' : 'info');
    const title = data.type === 'error' ? 'DRONE ERROR' : (data.type === 'warning' ? 'DRONE WARNING' : 'DRONE STATUS');
    const msgText = data.text || '';
    if (msgText) {
        if (typeof showToastAlert === 'function') {
            showToastAlert(title, msgText, alertType, 4000);
        }
    }
});

// APM Real-time Warning & Status Message History Console
let apmLogMessages = [];

function openApmLogModal() {
    const modal = document.getElementById('apm-log-modal');
    if (modal) modal.style.display = 'flex';
    const badge = document.getElementById('apm-log-count-badge');
    if (badge) badge.innerText = '0';
}

function closeApmLogModal() {
    const modal = document.getElementById('apm-log-modal');
    if (modal) modal.style.display = 'none';
}

function closeApmLogModalOnBackdrop(e) {
    if (e.target.id === 'apm-log-modal') {
        closeApmLogModal();
    }
}

function clearApmLogs() {
    apmLogMessages = [];
    renderApmConsoleLogs();
}

function appendApmLogMessage(data) {
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    const type = data.type || 'info';
    const text = data.text || '';

    if (text) {
        addSystemLog(text, type);
    }

    apmLogMessages.push({
        time: timeStr,
        type: type,
        text: text
    });

    if (apmLogMessages.length > 200) {
        apmLogMessages.shift();
    }

    const modal = document.getElementById('apm-log-modal');
    if (!modal || modal.style.display === 'none') {
        const badge = document.getElementById('apm-log-count-badge');
        if (badge) {
            let current = parseInt(badge.innerText) || 0;
            badge.innerText = (current + 1).toString();
        }
    }

    renderApmConsoleLogs();
}

function renderApmConsoleLogs() {
    const consoleBox = document.getElementById('apm-log-console-box');
    const totalBadge = document.getElementById('apm-log-total-badge');

    if (totalBadge) {
        totalBadge.innerText = `${apmLogMessages.length} MESSAGES`;
    }

    if (!consoleBox) return;

    if (apmLogMessages.length === 0) {
        consoleBox.innerHTML = '<div id="apm-log-empty-msg" style="text-align: center; color: #8e8e93; font-style: italic; padding: 40px 0;">No status or warning messages received from CUAV X7 yet.</div>';
        return;
    }

    let htmlStr = '';
    apmLogMessages.forEach(msg => {
        let badgeColor = '#007aff';
        let badgeText = 'INFO';
        if (msg.type === 'error') {
            badgeColor = '#ff453a';
            badgeText = 'ERROR';
        } else if (msg.type === 'warning') {
            badgeColor = '#ff9500';
            badgeText = 'WARN';
        }

        htmlStr += `
            <div style="display: flex; align-items: flex-start; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 4px;">
                <span style="color: #8e8e93; font-size: 10px; min-width: 60px;">[${msg.time}]</span>
                <span style="background: ${badgeColor}22; color: ${badgeColor}; border: 1px solid ${badgeColor}66; padding: 0 5px; border-radius: 4px; font-size: 9px; font-weight: bold; min-width: 44px; text-align: center;">${badgeText}</span>
                <span style="color: #ffffff; word-break: break-word; flex: 1;">${msg.text}</span>
            </div>
        `;
    });

    consoleBox.innerHTML = htmlStr;
    consoleBox.scrollTop = consoleBox.scrollHeight;
}

// Custom alert functions
function showCustomAlert(title, message, type = 'info') {
    const overlay = document.getElementById('custom-alert-modal');
    const iconEl = document.getElementById('custom-alert-icon');
    const titleEl = document.getElementById('custom-alert-title');
    const msgEl = document.getElementById('custom-alert-message');
    const cardEl = overlay.querySelector('.custom-alert-card');

    titleEl.innerText = title;
    msgEl.innerText = message;

    cardEl.className = 'custom-alert-card';
    if (type === 'success') {
        iconEl.innerText = '✅';
        cardEl.classList.add('alert-success');
    } else if (type === 'error') {
        iconEl.innerText = '❌';
        cardEl.classList.add('alert-error');
    } else if (type === 'warning') {
        iconEl.innerText = '⚠️';
        cardEl.classList.add('alert-warning');
    } else {
        iconEl.innerText = 'ℹ️';
        cardEl.classList.add('alert-info');
    }

    overlay.style.display = 'flex';
    setTimeout(() => {
        overlay.classList.add('show');
    }, 10);
}

function closeCustomAlert() {
    const overlay = document.getElementById('custom-alert-modal');
    overlay.classList.remove('show');
    setTimeout(() => {
        overlay.style.display = 'none';
    }, 250);
}

// Toast notification: displays visual pop-up on screen AND logs Telemetry/FCU events to System Event Log
function showToastAlert(title, message, type = 'info', duration = 4000) {
    let level = 'info';
    if (type === 'success') level = 'success';
    else if (type === 'error') level = 'error';
    else if (type === 'warning') level = 'warning';

    // 1. Catat ke System Event Log HANYA untuk Telemetri / FCU / Drone Status (Servo & non-telemetri diblokir)
    const isServoLog = (title && title.toUpperCase().includes('SERVO')) || (message && message.toLowerCase().includes('servo'));
    if (!isServoLog && typeof addSystemLog === 'function') {
        const logText = (title && message && !message.startsWith(title)) ? `${title}: ${message}` : (message || title);
        if (logText) {
            addSystemLog(logText, level);
        }
    }

    // 2. Render visual Pop-up Toast card dengan timer progress bar di layar
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const existingToasts = container.querySelectorAll('.toast');
    existingToasts.forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    else if (type === 'error') icon = '⚠️';
    else if (type === 'warning') icon = '⚡';

    toast.innerHTML = `
        <div class="toast-header">${icon} ${title}</div>
        <div class="toast-body">${message}</div>
        <div class="toast-progress"></div>
    `;

    container.appendChild(toast);

    // Trigger slide-in animation
    setTimeout(() => toast.classList.add('show'), 20);

    // Animate progress bar timer line
    const progress = toast.querySelector('.toast-progress');
    if (progress) {
        progress.style.transition = `transform ${duration}ms linear`;
        setTimeout(() => {
            progress.style.transform = 'scaleX(0)';
        }, 50);
    }

    // Auto-remove toast after duration
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    }, duration);
}

// Camera badges will remain offline until Raspberry Pi camera integration is implemented

socket.on('telemetry_data', (data) => {
    globalTelemetry = data;

    // ── Status Bar: selalu update berdasarkan data.connected ──────────────────
    if (data.connected) {
        lastTelemetryTime = Date.now();
        isConnectedState = true;
        const rssiText = (data.rssi_dbm !== undefined && data.rssi_dbm !== null)
            ? `CONNECTED (${data.rssi_dbm} dBm)` : "CONNECTED";
        updateMapStatus(rssiText, "#34c759", false);
    } else {
        isConnectedState = false;
        updateMapStatus("DISCONNECTED", "#ff453a", false);
    }

    // ── Sensor data: SELALU diupdate meski connected=false ──────────────────
    // IMU tidak butuh GPS — roll/pitch/yaw tersedia selama telemetri tercolok
    const elAlt = document.getElementById('lbl-alt');
    if (elAlt) elAlt.innerText = (data.alt || 0).toFixed(2);
    const elAltFront = document.getElementById('lbl-alt-front');
    if (elAltFront) elAltFront.innerText = (data.alt_front || 0).toFixed(2);
    const elAltRear = document.getElementById('lbl-alt-rear');
    if (elAltRear) elAltRear.innerText  = (data.alt_rear  || 0).toFixed(2);
    const elSpeed = document.getElementById('lbl-speed');
    if (elSpeed) elSpeed.innerText = (data.speed || 0).toFixed(2);
    const elHdg = document.getElementById('lbl-hdg');
    if (elHdg) elHdg.innerText   = (data.heading || 0).toFixed(1);
    const elRoll = document.getElementById('lbl-roll');
    if (elRoll) elRoll.innerText  = (data.roll  || 0).toFixed(2);
    const elPitch = document.getElementById('lbl-pitch');
    if (elPitch) elPitch.innerText = (data.pitch || 0).toFixed(2);
    const elYaw = document.getElementById('lbl-yaw');
    if (elYaw) elYaw.innerText   = (data.yaw   || 0).toFixed(2);

    // Battery: tampilkan N/A hanya jika tidak ada data (0 dianggap belum terima)
    const bat = data.battery_remaining;
    document.getElementById('lbl-bat-percent').innerText = (bat > 0) ? bat : 'N/A';
    const volt = data.voltage_battery;
    document.getElementById('lbl-bat-volt').innerText = (volt > 0.1) ? volt.toFixed(2) : 'N/A';

    // GPS: tampilkan 0.0000000 jika belum ada fix
    document.getElementById('lbl-lat').innerText = (data.lat || 0).toFixed(7);
    document.getElementById('lbl-lng').innerText = (data.lng || 0).toFixed(7);

    updateTelemetryCharts(data.alt || 0, data.speed || 0);

    // Control Mode Badge
    const controlBadge = document.getElementById('control-mode-badge');
    if (controlBadge) {
        if (!data.connected) {
            controlBadge.innerText = "DISCONNECTED";
            controlBadge.style.color = "var(--text-muted)";
            controlBadge.style.background = "rgba(0, 0, 0, 0.05)";
        } else if (!data.is_armed) {
            controlBadge.innerText = `DISARMED (${data.mode})`;
            controlBadge.style.color = "var(--text-muted)";
            controlBadge.style.background = "rgba(0, 0, 0, 0.05)";
        } else {
            controlBadge.innerText = `ARMED (${data.mode})`;
            if (data.mode === 'LAND') {
                controlBadge.style.color = "#ff453a";
                controlBadge.style.background = "rgba(255, 69, 58, 0.1)";
            } else if (data.mode === 'GUIDED') {
                controlBadge.style.color = "#34c759";
                controlBadge.style.background = "rgba(52, 199, 89, 0.1)";
            } else {
                controlBadge.style.color = "#007aff";
                controlBadge.style.background = "rgba(0, 122, 255, 0.1)";
            }
        }
    }

    // Sync Flight Mode dropdown
    const modeSelect = document.getElementById('flight-mode-select');
    if (modeSelect && data.mode && document.activeElement !== modeSelect) {
        modeSelect.value = data.mode;
    }

    // Drone marker on map
    if (data.lat && data.lat !== 0) {
        droneMarker.setLatLng([data.lat, data.lng]);
        if (followDrone) map.panTo([data.lat, data.lng]);
    }
    const el = document.getElementById('drone-marker-element');
    if (el) el.style.transform = `rotate(${data.heading || 0}deg)`;

    updateManualGuidedPath();

    if (data.is_armed && data.current_wp_index > 1) {
        passedWaypointIndices.clear();
        for (let i = 0; i < data.current_wp_index - 1; i++) {
            passedWaypointIndices.add(i);
        }
    } else if (!data.is_armed || data.current_wp_index <= 1) {
        if (passedWaypointIndices.size > 0 && data.current_wp_index <= 1) {
            passedWaypointIndices.clear();
        }
    }

    if (data.current_wp_index !== lastCurrentWpIndex) {
        lastCurrentWpIndex = data.current_wp_index;
        if (typeof redrawAutoMissionMap === 'function') redrawAutoMissionMap();
        if (typeof renderAutoPipelineUI === 'function') renderAutoPipelineUI();
    }

    // QGC-style panels update (GPS, HDOP, Flight Timer, Home Distance, Live Log)
    updateQGCPanels(data);
});


function refreshCameraImage(cameraName) {
    const img = document.getElementById(`webcam-img-${cameraName}`);
    if (img) {
        const src = img.getAttribute('src') || '';
        const base = src.split('?')[0];
        img.setAttribute('src', `${base}?ts=${Date.now()}`);
    }
}

socket.on('connect', () => {
    ['bottom', 'front'].forEach(refreshCameraImage);
});

socket.on('camera_status', (data) => {
    if (data && data.connected) {
        markRaspiActive();
    }
    const badge = document.getElementById(`camera-rssi-badge-${data.camera}`);
    const img = document.getElementById(`webcam-img-${data.camera}`);
    const placeholder = document.getElementById(`webcam-placeholder-${data.camera}`);
    const overlay = document.getElementById(`camera-status-text-${data.camera}`);
    const reticle = document.getElementById(`reticle-${data.camera}`);

    if (badge) {
        if (data.connected) {
            if (data.rssi >= -60) {
                badge.innerText = `● LIVE (GOOD)`;
                badge.className = "rssi-pill rssi-good";
            } else if (data.rssi < -60 && data.rssi >= -78) {
                badge.innerText = `● LIVE (FAIR)`;
                badge.className = "rssi-pill rssi-fair";
            } else {
                badge.innerText = `● LIVE (POOR)`;
                badge.className = "rssi-pill rssi-poor";
            }
            if (img) img.style.display = "block";
            if (placeholder) placeholder.style.display = "none";
            if (overlay) overlay.style.display = "block";
            if (reticle) reticle.style.display = "block";
        } else {
            badge.innerText = `● OFFLINE`;
            badge.className = "rssi-pill rssi-poor";
            if (img) img.style.display = "none";
            if (placeholder) placeholder.style.display = "block";
            if (overlay) overlay.style.display = "none";
            if (reticle) reticle.style.display = "none";
        }
    }
});



// Dynamic Camera Overlay Status Handlers
let bottomStatusTimeout = null;
let frontStatusTimeout = null;

socket.on('gate_status', (data) => {
    // Front camera is clean raw video display only
});

socket.on('krti_status_update', (data) => {
    const badge = document.getElementById('krti-status-badge');
    if (badge) {
        badge.innerText = data.status;
        if (data.status === 'RUNNING') {
            badge.style.color = 'var(--apple-blue)';
        } else {
            badge.style.color = 'var(--apple-green)';
        }
    }
});

let currentTheme = localStorage.getItem('gcs_theme') || 'light';

function applyTheme(theme) {
    currentTheme = theme;
    localStorage.setItem('gcs_theme', theme);
    const btn = document.getElementById('btn-theme-toggle');
    
    if (theme === 'dark') {
        document.body.classList.add('theme-dark');
        document.body.classList.remove('theme-light');
        if (btn) {
            btn.innerText = '☀️ LIGHT MODE';
            btn.style.background = '#ffffff';
            btn.style.color = '#0f172a';
            btn.style.border = '1px solid #cbd5e1';
        }
    } else {
        document.body.classList.remove('theme-dark');
        document.body.classList.add('theme-light');
        if (btn) {
            btn.innerText = '🌙 DARK MODE';
            btn.style.background = '#0f172a';
            btn.style.color = '#ffffff';
            btn.style.border = '1px solid #0f172a';
        }
    }
}

function toggleTheme() {
    const nextTheme = currentTheme === 'light' ? 'dark' : 'light';
    applyTheme(nextTheme);
}

// Initial load cleanup to ensure Manual mode starts clean without leaking KRTI or MISSION markers
document.addEventListener('DOMContentLoaded', () => {
    applyTheme(currentTheme);
    initTelemetryCharts();
    switchMode('manual');
    addSystemLog('GCS initialized. Waiting for telemetry...', 'info');
});

// ─── SLIDE-IN LOG PANEL TOGGLE ────────────────────────────────────────────────
let logPanelOpen = false;

function toggleLogPanel() {
    const console_el = document.getElementById('sys-log-console');
    if (console_el) {
        console_el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        console_el.scrollTop = console_el.scrollHeight;
    }
}

// ─── QGC-STYLE FLIGHT TIMER ───────────────────────────────────────────────────
let flightTimerInterval = null;
let flightStartTime = null;
let wasArmed = false;

function startFlightTimer() {
    if (flightTimerInterval) return;
    flightStartTime = Date.now();
    flightTimerInterval = setInterval(() => {
        const elapsed = Date.now() - flightStartTime;
        const h = Math.floor(elapsed / 3600000).toString().padStart(2, '0');
        const m = Math.floor((elapsed % 3600000) / 60000).toString().padStart(2, '0');
        const s = Math.floor((elapsed % 60000) / 1000).toString().padStart(2, '0');
        const el = document.getElementById('lbl-qgc-timer');
        if (el) el.innerText = `${h}:${m}:${s}`;
    }, 1000);
}

function stopFlightTimer() {
    if (flightTimerInterval) {
        clearInterval(flightTimerInterval);
        flightTimerInterval = null;
    }
    const el = document.getElementById('lbl-qgc-timer');
    if (el) el.innerText = '00:00:00';
}

// ─── HOME POSITION (SET ON FIRST ARM) ─────────────────────────────────────────
let homeLatLng = null;

function getDistanceMeters(lat1, lng1, lat2, lng2) {
    const R = 6371000;
    const phi1 = lat1 * Math.PI / 180;
    const phi2 = lat2 * Math.PI / 180;
    const dphi = (lat2 - lat1) * Math.PI / 180;
    const dlam = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlam / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ─── LIVE SYSTEM EVENT LOG (HIGH PERFORMANCE & LAG-FREE) ───────────────────
let lastLogMsg = '';
let lastLogTime = 0;

function addSystemLog(message, level = 'normal') {
    if (!message) return;
    
    // Filter out internal high-frequency spam logs that cause UI lag
    if (message.includes('param #') || message.includes('timesync') || message.includes('RTT too high')) return;

    // Deduplicate identical consecutive messages within 1.5s
    const nowTs = Date.now();
    if (message === lastLogMsg && (nowTs - lastLogTime) < 1500) return;
    lastLogMsg = message;
    lastLogTime = nowTs;

    const console_el = document.getElementById('sys-log-console');
    if (!console_el) return;

    const now = new Date();
    const ts = now.getHours().toString().padStart(2,'0') + ':' +
                now.getMinutes().toString().padStart(2,'0') + ':' +
                now.getSeconds().toString().padStart(2,'0');
    const colorMap = {
        'info'    : '#0ea5e9',
        'success' : '#10b981',
        'warning' : '#ff6b00',
        'error'   : '#ef4444',
        'normal'  : '#ffffff'
    };
    const color = colorMap[level] || '#ffffff';
    const div = document.createElement('div');
    div.style.color = color;
    div.style.whiteSpace = 'nowrap';
    div.style.overflow = 'hidden';
    div.style.textOverflow = 'ellipsis';
    div.textContent = `[${ts}] ${message}`;

    console_el.appendChild(div);

    // Keep DOM light (max 60 entries) to guarantee 60FPS smooth scrolling
    while (console_el.children.length > 60) {
        console_el.removeChild(console_el.firstChild);
    }

    requestAnimationFrame(() => {
        console_el.scrollTop = console_el.scrollHeight;
    });
}

function clearSystemLog() {
    const console_el = document.getElementById('sys-log-console');
    if (console_el) console_el.innerHTML = '';
    addSystemLog('Log cleared.', 'info');
}

// ─── QGC TELEMETRY UPDATES (GPS LOCK, HDOP, HOME DIST) ───────────────────────
let lastMode = null;
let lastConnectedState = null;

function updateQGCPanels(data) {
    // GPS Lock / Satellites
    const satsEl = document.getElementById('lbl-qgc-sats');
    if (satsEl) {
        const sats = data.satellites_visible || 0;
        const gpsType = data.gps_fix_type || 0;
        const fixLabel = gpsType >= 3 ? '3D FIX' : gpsType === 2 ? '2D FIX' : 'NO FIX';
        satsEl.innerText = `${sats} (${fixLabel})`;
        satsEl.style.color = gpsType >= 3 ? '#0ea5e9' : gpsType === 2 ? '#ff6b00' : '#ef4444';
    }

    // HDOP Accuracy
    const hdopEl = document.getElementById('lbl-qgc-hdop');
    if (hdopEl) {
        const hdop = data.eph !== undefined ? (data.eph / 100).toFixed(2) : '—';
        hdopEl.innerText = hdop !== '—' ? `${hdop} M` : '— M';
        const hdopVal = parseFloat(hdop);
        hdopEl.style.color = hdopVal < 1.0 ? '#10b981' : hdopVal < 2.0 ? '#ff6b00' : '#ef4444';
    }

    // Flight Timer
    if (data.is_armed && !wasArmed) {
        // Just armed — set home, start timer
        if (data.lat && data.lat !== 0) homeLatLng = { lat: data.lat, lng: data.lng };
        startFlightTimer();
        addSystemLog('ARMED — Flight timer started.', 'success');
        wasArmed = true;
    } else if (!data.is_armed && wasArmed) {
        stopFlightTimer();
        homeLatLng = null;
        addSystemLog('DISARMED — Flight timer stopped.', 'warning');
        wasArmed = false;
    }

    // Home Distance
    const distEl = document.getElementById('lbl-qgc-dist');
    if (distEl) {
        if (homeLatLng && data.lat && data.lat !== 0) {
            const dist = getDistanceMeters(homeLatLng.lat, homeLatLng.lng, data.lat, data.lng);
            distEl.innerText = `${dist.toFixed(1)} M`;
        } else {
            distEl.innerText = '0.0 M';
        }
    }

    // Log mode changes
    if (data.mode && data.mode !== lastMode) {
        if (lastMode !== null) addSystemLog(`Flight mode changed: ${lastMode} → ${data.mode}`, 'info');
        lastMode = data.mode;
    }

    // Log connection changes
    if (data.connected !== lastConnectedState) {
        if (data.connected) {
            addSystemLog('Telemetry link CONNECTED.', 'success');
        } else {
            addSystemLog('Telemetry link DISCONNECTED!', 'error');
        }
        lastConnectedState = data.connected;
    }
}
