// AUTONOMOUS WAYPOINT MISSION LOGIC
// State variables (autoMissionArray, autoMarkers, autoSegments, passedWaypointIndices, missionActive)
// are declared globally in script.js

function addWaypointToPipeline(type) {
    let lat, lng;

    let hasTakeoff = autoMissionArray.some(wp => wp.type === 'takeoff');
    let hasLanding = autoMissionArray.some(wp => wp.type === 'landing');

    // Jika drone sedang terbang, bersihkan landing point lama saat menambah waypoint baru
    const isFlying = globalTelemetry && globalTelemetry.is_armed;
    if (isFlying && hasLanding && (type === 'waypoint' || type === 'takeoff')) {
        autoMissionArray = autoMissionArray.filter(wp => wp.type !== 'landing');
        hasLanding = false; // Reset status
        showCustomAlert("Route Edited Mid-Air", "Drone is flying! The old landing point has been cleared. Please append a new landing point at the end of your route when you are done.", "info");
    }

    if (type === 'takeoff') {
        if (hasTakeoff) {
            return showCustomAlert("Route Limit", "Warning: The route can only have 1 TAKEOFF point!", "warning");
        }
        // Jika drone sudah memiliki GPS Lock, gunakan koordinat drone
        if (globalTelemetry && globalTelemetry.lat && globalTelemetry.lat !== 0 && globalTelemetry.lng && globalTelemetry.lng !== 0) {
            lat = globalTelemetry.lat;
            lng = globalTelemetry.lng;
        } else if (mapSelectedLatLng) {
            // Fallback: Jika GPS drone belum fix, gunakan titik lokasi yang diklik di peta
            lat = mapSelectedLatLng.lat;
            lng = mapSelectedLatLng.lng;
            showCustomAlert("Takeoff from Map", "Drone GPS is not fixed yet. Takeoff point set to selected map coordinate.", "info");
        } else {
            return showCustomAlert("Select Map Location", "Drone GPS is not fixed yet! Please select a coordinate on the map for the TAKEOFF point.", "warning");
        }
    } else {
        if (type === 'landing' && hasLanding) {
            return showCustomAlert("Route Limit", "Warning: The route can only have 1 LANDING point!", "warning");
        }
        // Waypoint and Landing need map selection
        if (!mapSelectedLatLng) {
            return showCustomAlert("Select Map Location", `Please select a coordinate on the map first for the ${type.toUpperCase()} point!`, "warning");
        }
        lat = mapSelectedLatLng.lat;
        lng = mapSelectedLatLng.lng;
    }

    let speedVal = parseFloat(document.getElementById('auto-speed').value);
    if (isNaN(speedVal)) speedVal = 1.0;
    if (speedVal > 10.0) {
        speedVal = 10.0;
        document.getElementById('auto-speed').value = 10.0;
    }

    const wpData = { 
        index: 0, 
        type: type, 
        lat: lat, 
        lng: lng, 
        alt: type === 'landing' ? 0 : document.getElementById('auto-alt').value, 
        speed: type === 'landing' ? 0 : speedVal 
    };

    // Susun posisi secara logis
    if (type === 'takeoff') {
        // Takeoff selalu di awal rute (index 0)
        autoMissionArray.unshift(wpData);
    } else if (type === 'landing') {
        // Landing selalu di akhir rute
        autoMissionArray.push(wpData);
    } else {
        // Waypoint biasa disisipkan sebelum landing jika landing sudah ada
        if (hasLanding) {
            const landingIdx = autoMissionArray.findIndex(wp => wp.type === 'landing');
            autoMissionArray.splice(landingIdx, 0, wpData);
        } else {
            autoMissionArray.push(wpData);
        }
    }

    if (tempSelectionMarker) { map.removeLayer(tempSelectionMarker); tempSelectionMarker = null; }
    
    const autoCoordEl = document.getElementById('auto-target-coords');
    if (autoCoordEl) {
        autoCoordEl.innerText = 'NOT SELECTED';
    }

    // Panggil penggambaran ulang peta & UI
    redrawAutoMissionMap();
    renderAutoPipelineUI();
    mapSelectedLatLng = null;
}

function renderAutoPipelineUI() {
    const cont = document.getElementById('auto-pipeline-container');
    if (!cont) return;
    cont.innerHTML = '';
    if (autoMissionArray.length === 0) {
        cont.innerHTML = `<div style="font-size:11px; color:var(--text-muted); text-align:center; padding-top: 40px;">Pipeline empty. Please construct a route.</div>`;
        return;
    }
    autoMissionArray.forEach((n, idx) => {
        const isPassed = passedWaypointIndices.has(idx);
        let bg;
        let opacity = 1.0;
        let textDecoration = 'none';
        let statusText = '';
        
        if (isPassed) {
            bg = '#8e8e93';
            opacity = 0.5;
            textDecoration = 'line-through';
            statusText = ' <span style="font-size:9px; color:#aaa;">(PASSED)</span>';
        } else {
            bg = (n.type === 'takeoff' || n.type === 'landing') ? '#ff9500' : '#0071e3';
            if (globalTelemetry && globalTelemetry.is_armed && idx === globalTelemetry.current_wp_index) {
                statusText = ' <span style="font-size:9px; color:var(--apple-green); font-weight:bold;">(ACTIVE)</span>';
            }
        }
        
        let latStr = n.lat ? n.lat.toFixed(6) : '0.000000';
        let lngStr = n.lng ? n.lng.toFixed(6) : '0.000000';
        let detailText = n.type === 'landing' 
            ? `Lat: <b>${latStr}</b>, <b>${lngStr}</b>` 
            : `Alt: <b>${n.alt}m</b> | Spd: <b>${n.speed}m/s</b> | Lat: <b>${latStr}</b>, <b>${lngStr}</b>`;
        
        cont.innerHTML += `
            <div class="wp-node" style="opacity:${opacity}; text-decoration:${textDecoration}; flex-wrap: wrap; gap: 6px;">
                <span class="node-tag" style="background:${bg}">${n.type.toUpperCase()} #${n.index}</span>
                <span style="font-size: 10px;">${detailText}${statusText}</span>
            </div>
        `;
    });
}

let autoSegmentObjects = [];

function updateAutoMissionLinesAndLabels() {
    autoSegmentObjects.forEach(segObj => {
        const wpStart = autoMissionArray[segObj.wpStartIdx];
        const wpEnd = autoMissionArray[segObj.wpEndIdx];
        if (!wpStart || !wpEnd) return;

        const newLatLngs = [[wpStart.lat, wpStart.lng], [wpEnd.lat, wpEnd.lng]];
        if (segObj.glowLine) segObj.glowLine.setLatLngs(newLatLngs);
        if (segObj.mainLine) segObj.mainLine.setLatLngs(newLatLngs);
        if (segObj.grayLine) segObj.grayLine.setLatLngs(newLatLngs);

        const midLat = (wpStart.lat + wpEnd.lat) / 2;
        const midLng = (wpStart.lng + wpEnd.lng) / 2;
        const info = (typeof calculateDistanceAndBearing === 'function') 
            ? calculateDistanceAndBearing(wpStart.lat, wpStart.lng, wpEnd.lat, wpEnd.lng)
            : { dist: 0, bearing: 0 };

        if (segObj.badgeMarker) {
            segObj.badgeMarker.setLatLng([midLat, midLng]);
            segObj.badgeMarker.setIcon(L.divIcon({
                className: 'wp-seg-badge-auto',
                html: `<div style="background: none !important; border: none !important; color: #ffffff !important; font-size: 10.5px; font-weight: 800; transform: translate(-50%, -50%); white-space: nowrap; font-family: 'Poppins', sans-serif; text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000, 0 2px 4px rgba(0,0,0,0.8);">${info.dist.toFixed(1)}m / ${Math.round(info.bearing)}°</div>`,
                iconSize: [0, 0],
                iconAnchor: [0, 0]
            }));
        }
    });
}

function redrawAutoMissionMap() {
    // Hapus semua marker lama dari peta
    autoMarkers.forEach(m => map.removeLayer(m));
    autoMarkers = [];

    // Hapus semua segment lama dari peta
    autoSegments.forEach(s => map.removeLayer(s));
    autoSegments = [];
    autoSegmentObjects = [];

    // STRICT MODE CHECK: Do not draw Auto Mission markers unless currentMode is 'auto'
    if (typeof currentMode !== 'undefined' && currentMode !== 'auto') {
        return;
    }

    // Gambar ulang semua marker sesuai urutan array saat ini
    let wpCount = 0;
    autoMissionArray.forEach((wp, idx) => {
        wp.index = idx + 1; // Sinkronisasi index 1-indexed

        // Cek apakah waypoint ini sudah dilewati
        const isPassed = passedWaypointIndices.has(idx);
        let color;
        let fillOpacity = 1;
        let labelText = '';

        if (wp.type === 'takeoff') {
            labelText = 'TAKEOFF';
            color = isPassed ? '#8e8e93' : '#ff9500'; // Dim Gray if passed, Bright Orange if active
        } else if (wp.type === 'landing') {
            labelText = 'LANDING';
            color = isPassed ? '#8e8e93' : '#ff9500'; // Dim Gray if passed, Bright Orange if active
        } else {
            wpCount++;
            labelText = 'WP' + wpCount;
            color = isPassed ? '#8e8e93' : '#0071e3'; // Dim Gray if passed, Bright Electric Blue if active
        }

        const opacity = isPassed ? 0.45 : 1.0;

        const triangleHtml = `
            <div style="position: relative; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; opacity: ${opacity};">
                <svg viewBox="0 0 22 22" width="22" height="22" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.6));">
                    <polygon points="11,1 21,20 1,20" fill="${color}" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/>
                </svg>
                <span style="position: absolute; top: 7px; color: #ffffff; font-weight: 800; font-size: 8.5px; font-family: 'Poppins', sans-serif; text-shadow: 0 1px 2px rgba(0,0,0,0.8);">${wp.index}</span>
            </div>
        `;

        const triangleIcon = L.divIcon({
            className: 'wp-triangle-icon',
            html: triangleHtml,
            iconSize: [22, 22],
            iconAnchor: [11, 11]
        });

        // DRAGGABLE MARKER FOR MISSION MODE WAYPOINTS
        const marker = L.marker([wp.lat, wp.lng], { icon: triangleIcon, draggable: true, zIndexOffset: 1000 }).addTo(map);

        marker.bindPopup(`<b>${wp.type.toUpperCase()} #${wp.index}</b>${isPassed ? ' (PASSED)' : ''}<br>Alt: ${wp.alt}m<br>Spd: ${wp.speed}m/s<br>Lat: ${wp.lat.toFixed(6)}, Lng: ${wp.lng.toFixed(6)}`);
        autoMarkers.push(marker);

        // Rich map label card with Light Gray (#f2f2f7) background for MISSION mode
        const labelTitle = wp.type === 'takeoff' ? 'TAKEOFF' : (wp.type === 'landing' ? 'LANDING' : `WP${wpCount}`);
        const latStr = wp.lat.toFixed(6);
        const lngStr = wp.lng.toFixed(6);
        const detailsText = `Alt:${wp.alt}m | Spd:${wp.speed}m/s | Lat:${latStr}, ${lngStr}`;

        const richLabelHtml = `
            <div style="transform: translate(-50%, -42px); display: flex; flex-direction: column; align-items: center; pointer-events: none; opacity: ${opacity};">
                <div style="background: #f2f2f7; border: 1px solid #d1d1d6; border-radius: 6px; padding: 3px 8px; color: #1d1d1f; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-family: 'Poppins', sans-serif; white-space: nowrap;">
                    <div style="font-weight: 800; font-size: 10.5px; color: ${color}; letter-spacing: 0.3px;">${labelTitle} #${wp.index}</div>
                    <div style="font-size: 9px; color: #0f172a; font-weight: 600; margin-top: 1px;">${detailsText}</div>
                </div>
            </div>
        `;

        const labelIcon = L.divIcon({
            className: 'wp-map-rich-label-auto',
            html: richLabelHtml,
            iconSize: [0, 0],
            iconAnchor: [0, 0]
        });
        const labelMarker = L.marker([wp.lat, wp.lng], { icon: labelIcon, interactive: false, zIndexOffset: 200 }).addTo(map);
        autoMarkers.push(labelMarker);

        // Real-Time Dynamic Dragging Event Handlers
        marker.on('drag', function (e) {
            const newPos = e.target.getLatLng();
            wp.lat = newPos.lat;
            wp.lng = newPos.lng;

            // 1. Update rich label marker position & Lat/Lng details in real time
            if (labelMarker) {
                labelMarker.setLatLng(newPos);
                const curLatStr = newPos.lat.toFixed(6);
                const curLngStr = newPos.lng.toFixed(6);
                const curDetailsText = `Alt:${wp.alt}m | Spd:${wp.speed}m/s | Lat:${curLatStr}, ${curLngStr}`;

                const curRichHtml = `
                    <div style="transform: translate(-50%, -42px); display: flex; flex-direction: column; align-items: center; pointer-events: none; opacity: ${opacity};">
                        <div style="background: #f2f2f7; border: 1px solid #d1d1d6; border-radius: 6px; padding: 3px 8px; color: #1d1d1f; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-family: 'Poppins', sans-serif; white-space: nowrap;">
                            <div style="font-weight: 800; font-size: 10.5px; color: ${color}; letter-spacing: 0.3px;">${labelTitle} #${wp.index}</div>
                            <div style="font-size: 9px; color: #0f172a; font-weight: 600; margin-top: 1px;">${curDetailsText}</div>
                        </div>
                    </div>
                `;

                labelMarker.setIcon(L.divIcon({
                    className: 'wp-map-rich-label-auto',
                    html: curRichHtml,
                    iconSize: [0, 0],
                    iconAnchor: [0, 0]
                }));
            }

            // 2. Dynamically update connecting dashed lines & segment distance/bearing badges (e.g. 5.2m / 270°)
            updateAutoMissionLinesAndLabels();
        });

        marker.on('dragend', function (e) {
            const newPos = e.target.getLatLng();
            wp.lat = newPos.lat;
            wp.lng = newPos.lng;

            if (selectedAutoWpIndex === idx) {
                const coordEl = document.getElementById('auto-target-coords');
                if (coordEl) coordEl.innerText = `${newPos.lat.toFixed(6)}, ${newPos.lng.toFixed(6)}`;
            }

            renderAutoPipelineUI();
            saveAutoMissionToStorage();
            redrawAutoMissionMap();
        });
    });

    // Gambar segment antar waypoint dengan warna hijau glow stabilo (#30d158) & badge jarak/arah (5m / 270°)
    for (let i = 0; i < autoMissionArray.length - 1; i++) {
        const wpStart = autoMissionArray[i];
        const wpEnd = autoMissionArray[i+1];

        // Segment i→i+1 terlewati jika waypoint i+1 sudah masuk ke passedWaypointIndices
        const isPassed = passedWaypointIndices.has(i + 1);

        let glowLine = null;
        let mainLine = null;
        let grayLine = null;

        if (isPassed) {
            // Segment abu-abu
            grayLine = L.polyline([[wpStart.lat, wpStart.lng], [wpEnd.lat, wpEnd.lng]], {
                color: '#8e8e93',
                weight: 3,
                opacity: 0.6,
                dashArray: '6, 12'
            }).addTo(map);
            autoSegments.push(grayLine);
        } else {
            // Segment hijau glow stabilo (#30d158)
            glowLine = L.polyline([[wpStart.lat, wpStart.lng], [wpEnd.lat, wpEnd.lng]], {
                color: '#30d158',
                weight: 10,
                opacity: 0.45,
                dashArray: '6, 12',
                className: 'waypoint-glow-line'
            }).addTo(map);
            
            mainLine = L.polyline([[wpStart.lat, wpStart.lng], [wpEnd.lat, wpEnd.lng]], {
                color: '#30d158',
                weight: 3.5,
                opacity: 0.95,
                dashArray: '6, 12',
                className: 'waypoint-main-line'
            }).addTo(map);
            
            autoSegments.push(glowLine, mainLine);
        }

        // Midpoint Segment Badge displaying real-world distance & heading angle (e.g. 5m / 270°)
        const midLat = (wpStart.lat + wpEnd.lat) / 2;
        const midLng = (wpStart.lng + wpEnd.lng) / 2;
        const info = (typeof calculateDistanceAndBearing === 'function') 
            ? calculateDistanceAndBearing(wpStart.lat, wpStart.lng, wpEnd.lat, wpEnd.lng)
            : { dist: 0, bearing: 0 };

        const distBadgeIcon = L.divIcon({
            className: 'wp-seg-badge-auto',
            html: `<div style="background: none !important; border: none !important; color: #ffffff !important; font-size: 10.5px; font-weight: 800; transform: translate(-50%, -50%); white-space: nowrap; font-family: 'Poppins', sans-serif; text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000, 0 2px 4px rgba(0,0,0,0.8);">${info.dist.toFixed(1)}m / ${Math.round(info.bearing)}°</div>`,
            iconSize: [0, 0],
            iconAnchor: [0, 0]
        });
        const segMarker = L.marker([midLat, midLng], { icon: distBadgeIcon, interactive: false }).addTo(map);
        autoSegments.push(segMarker);

        autoSegmentObjects.push({
            wpStartIdx: i,
            wpEndIdx: i + 1,
            glowLine: glowLine,
            mainLine: mainLine,
            grayLine: grayLine,
            badgeMarker: segMarker
        });
    }
}

function clearAutoMission() {
    autoMissionArray = [];
    passedWaypointIndices.clear();
    missionActive = false;

    autoMarkers.forEach(m => {
        if (m && typeof map !== 'undefined' && map.hasLayer(m)) map.removeLayer(m);
    });
    autoMarkers = [];

    autoSegments.forEach(s => {
        if (s && typeof map !== 'undefined' && map.hasLayer(s)) map.removeLayer(s);
    });
    autoSegments = [];

    if (typeof tempSelectionMarker !== 'undefined' && tempSelectionMarker && map.hasLayer(tempSelectionMarker)) {
        map.removeLayer(tempSelectionMarker);
        tempSelectionMarker = null;
    }
    mapSelectedLatLng = null;

    const autoCoordEl = document.getElementById('auto-target-coords');
    if (autoCoordEl) {
        autoCoordEl.innerText = 'NOT SELECTED';
    }

    renderAutoPipelineUI();
    if (typeof updateWaypointsMapUI === 'function') {
        updateWaypointsMapUI();
    }

    // Inform backend that route is cleared
    if (typeof socket !== 'undefined' && socket) {
        socket.emit('transmit_auto_mission', []);
    }

    if (typeof showToastAlert === 'function') {
        showToastAlert("AUTO MISSION", "Route cleared successfully!", "warning");
    }
}
