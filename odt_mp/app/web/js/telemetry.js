/* telemetry.js - simulator telemetry rendering */
window.ODT = window.ODT || {};

ODT.Telemetry = (function () {
  let ws = null;
  let connected = false;
  let connecting = false;
  let manualClose = false;
  let pingHandle = 0;
  const vehicleStates = new Map();
  const TRACK_SOURCE_ID = 'telemetry-fleet-track';
  const TRACK_LAYER_ID = 'telemetry-fleet-track-line';
  const MAX_TRACK = 1200;
  const PING_INTERVAL_MS = 3000;
  const COLORS = ['#ef4444', '#22c55e', '#3b82f6', '#f59e0b', '#a855f7', '#06b6d4'];

  async function openRealtimeChannel() {
    if (connected || connecting) {
      return true;
    }

    connecting = true;
    manualClose = false;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/ws/telemetry`;

    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (!settled) {
          settled = true;
          resolve(value);
        }
      };

      try {
        ws = new WebSocket(url);
      } catch (_) {
        connecting = false;
        ws = null;
        finish(false);
        return;
      }

      ws.onopen = () => {
        connected = true;
        connecting = false;
        startPingLoop();
        finish(true);
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'telemetry') {
            onTelemetryData(msg);
          }
        } catch (_) {}
      };

      ws.onerror = () => {
        if (connecting) {
          connected = false;
          connecting = false;
          finish(false);
        }
      };

      ws.onclose = () => {
        stopPingLoop();
        connected = false;
        connecting = false;
        ws = null;
        finish(false);
        if (!manualClose) {
          ODT.OperatorLog?.warn(
            ODT.t('log_realtime_closed_title'),
            ODT.t('log_realtime_closed_message')
          );
        }
        manualClose = false;
      };
    });
  }

  async function closeRealtimeChannel() {
    manualClose = true;
    stopPingLoop();
    if (ws) {
      ws.close();
      ws = null;
    }
    connected = false;
    connecting = false;
    return true;
  }

  function isConnected() {
    return connected;
  }

  function startPingLoop() {
    stopPingLoop();
    pingHandle = window.setInterval(() => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      try {
        ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
      } catch (_) {}
    }, PING_INTERVAL_MS);
  }

  function stopPingLoop() {
    if (pingHandle) {
      window.clearInterval(pingHandle);
      pingHandle = 0;
    }
  }

  function getVehicleKey(data) {
    return (
      String(data?.vehicle_name || data?.name || data?.aircraft_id || 'SIM').trim() || 'SIM'
    );
  }

  function getVehicleColor(key) {
    const existing = vehicleStates.get(key);
    if (existing?.color) {
      return existing.color;
    }
    return COLORS[vehicleStates.size % COLORS.length];
  }

  function onTelemetryData(data) {
    const lat = Number(data?.lat);
    const lon = Number(data?.lon);
    const alt = Number(data?.alt_m);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      return;
    }

    const key = getVehicleKey(data);
    let state = vehicleStates.get(key);
    if (!state) {
      state = {
        key,
        color: getVehicleColor(key),
        marker: null,
        trackCoords: [],
      };
      vehicleStates.set(key, state);
    }

    updateReadout(key, lat, lon, alt);
    updateMarker(state, lon, lat);

    state.trackCoords.push([lon, lat]);
    if (state.trackCoords.length > MAX_TRACK) {
      state.trackCoords.shift();
    }
    updateTrackLayer();
  }

  function updateReadout(key, lat, lon, alt) {
    const telemLat = document.getElementById('telem-lat');
    const telemLon = document.getElementById('telem-lon');
    const telemAlt = document.getElementById('telem-alt');
    const readout = document.getElementById('telemetry-readout');
    if (telemLat) telemLat.textContent = ODT.formatCoord(lat, 6);
    if (telemLon) telemLon.textContent = ODT.formatCoord(lon, 6);
    if (telemAlt) telemAlt.textContent = ODT.formatAlt(alt);
    if (readout) {
      readout.title = key;
    }
  }

  function updateMarker(state, lon, lat) {
    const map = ODT.MapManager.getMap();
    if (!map) return;

    if (!state.marker) {
      const el = document.createElement('div');
      el.style.cssText = `
        display:flex;
        flex-direction:column;
        align-items:center;
        gap:4px;
      `;
      const dot = document.createElement('div');
      dot.style.cssText = `
        width: 16px;
        height: 16px;
        background: ${state.color};
        border: 2px solid white;
        border-radius: 50%;
        box-shadow: 0 0 12px ${state.color}99;
      `;
      const label = document.createElement('div');
      label.style.cssText = `
        padding: 2px 6px;
        border-radius: 999px;
        background: rgba(12, 16, 24, 0.78);
        color: white;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.02em;
        white-space: nowrap;
      `;
      label.textContent = state.key;
      el.appendChild(dot);
      el.appendChild(label);
      state.marker = new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(map);
    } else {
      state.marker.setLngLat([lon, lat]);
    }
  }

  function updateTrackLayer() {
    const map = ODT.MapManager.getMap();
    if (!map) return;

    const features = [];
    vehicleStates.forEach((state) => {
      if (state.trackCoords.length < 2) return;
      features.push({
        type: 'Feature',
        properties: {
          color: state.color,
          name: state.key,
        },
        geometry: {
          type: 'LineString',
          coordinates: state.trackCoords,
        },
      });
    });

    const data = {
      type: 'FeatureCollection',
      features,
    };

    if (map.getSource(TRACK_SOURCE_ID)) {
      map.getSource(TRACK_SOURCE_ID).setData(data);
      return;
    }

    map.addSource(TRACK_SOURCE_ID, {
      type: 'geojson',
      data,
    });
    map.addLayer({
      id: TRACK_LAYER_ID,
      type: 'line',
      source: TRACK_SOURCE_ID,
      paint: {
        'line-color': ['coalesce', ['get', 'color'], '#ef4444'],
        'line-width': 2.4,
        'line-opacity': 0.76,
      },
    });
  }

  function resetSimulationView() {
    vehicleStates.forEach((state) => {
      if (state.marker) {
        state.marker.remove();
      }
    });
    vehicleStates.clear();

    const map = ODT.MapManager.getMap();
    if (map && map.getLayer(TRACK_LAYER_ID)) {
      map.removeLayer(TRACK_LAYER_ID);
    }
    if (map && map.getSource(TRACK_SOURCE_ID)) {
      map.removeSource(TRACK_SOURCE_ID);
    }
  }

  return {
    connect: openRealtimeChannel,
    disconnect: closeRealtimeChannel,
    openRealtimeChannel,
    closeRealtimeChannel,
    isConnected,
    renderPacket: onTelemetryData,
    resetSimulationView,
  };
})();
