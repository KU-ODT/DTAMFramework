const { createApp } = Vue;

const app = createApp({
  data() {
    return {
      missionJson: '',
      missions: [],
      telemetry: {},
      selectedAircraft: '',
      toastMessage: '',
      toastType: 'success',
      map: null,
      markers: {},
      trails: {},
      missionRoutes: {},
      missionSpawns: {},
      ws: null,
      wsConnected: false,
      isDragOver: false,
      missionPollTimer: null,
      telemetryPollTimer: null,
      wsRetryTimer: null,
      simClockPollTimer: null,
      simClockTickTimer: null,
      simClockBusy: false,
      simClockRunning: false,
      simClockRate: 1,
      simTimeInput: '',
      simTimeInputFocused: false,
      simulationTime: {
        time: null,
        seconds: null,
        available: false,
        source: null,
      },
    };
  },
  computed: {
    availableAircraft() {
      return Object.keys(this.telemetry).sort();
    },
    activeMissionHint() {
      const activeStatuses = new Set([
        'QUEUED',
        'SCHEDULED',
        'COMPILING',
        'COMPILED',
        'UPLOADING',
        'UPLOADED',
        'EXECUTING',
      ]);
      return this.missions.find(m => activeStatuses.has(m.status) && (m.scheduledArmAt || m.scheduledStartAt))
        || this.missions.find(m => m.scheduledArmAt || m.scheduledStartAt)
        || null;
    }
  },
  watch: {
    telemetry: {
      deep: false,
      handler(newVal) {
        // Removed deep watcher to fix UI lag.
        // Map updates are now handled by requestAnimationFrame in mounted().
      }
    }
  },
  mounted() {
    this.initMap();
    this.fetchMissions();
    this.fetchTelemetrySnapshot();
    this.fetchSimulationTime();
    this.connectWebSocket();
    this.missionPollTimer = window.setInterval(() => this.fetchMissions(), 500);
    this.telemetryPollTimer = window.setInterval(() => this.fetchTelemetrySnapshot(), 1500);
    this.simClockPollTimer = window.setInterval(() => this.fetchSimulationTime(), 1000);

    // 60FPS Render Loop for Leaflet (Decoupled from Vue reactivity)
    const renderLoop = () => {
      this.updateMapMarkers();
      requestAnimationFrame(renderLoop);
    };
    requestAnimationFrame(renderLoop);
  },
  beforeUnmount() {
    if (this.missionPollTimer) {
      window.clearInterval(this.missionPollTimer);
    }
    if (this.telemetryPollTimer) {
      window.clearInterval(this.telemetryPollTimer);
    }
    if (this.wsRetryTimer) {
      window.clearTimeout(this.wsRetryTimer);
    }
    if (this.simClockPollTimer) {
      window.clearInterval(this.simClockPollTimer);
    }
    this.stopGuiClock();
    if (this.ws) {
      this.ws.close();
    }
  },
  methods: {
    fmt(val, decimals) {
      if (val === undefined || val === null || !Number.isFinite(val)) return '--';
      return val.toFixed(decimals);
    },
    fmtRpm(arr, idx) {
      if (!arr || idx >= arr.length) return '0';
      const v = arr[idx];
      return Number.isFinite(v) ? v.toFixed(0) : '0';
    },
    secondsToTime(seconds) {
      const clamped = Math.max(0, Math.min(24 * 3600 - 1, Number(seconds) || 0));
      const hh = Math.floor(clamped / 3600);
      const mm = Math.floor((clamped % 3600) / 60);
      const ss = Math.floor(clamped % 60);
      return [hh, mm, ss].map(v => String(v).padStart(2, '0')).join(':');
    },
    timeToSeconds(value) {
      if (typeof value !== 'string') return null;
      const match = value.trim().match(/^(\d{1,2}):(\d{1,2}):(\d{1,2})$/);
      if (!match) return null;
      const [, hRaw, mRaw, sRaw] = match;
      const h = Number(hRaw);
      const m = Number(mRaw);
      const s = Number(sRaw);
      if (![h, m, s].every(Number.isInteger)) return null;
      if (h < 0 || h > 23 || m < 0 || m > 59 || s < 0 || s > 59) return null;
      return h * 3600 + m * 60 + s;
    },
    normalizeTimeInput(value) {
      const seconds = this.timeToSeconds(value);
      return seconds === null ? null : this.secondsToTime(seconds);
    },
    clockText(value) {
      if (typeof value !== 'string') return '';
      const direct = this.normalizeTimeInput(value);
      if (direct) return direct;
      const isoTime = value.match(/T(\d{2}:\d{2}:\d{2})/);
      if (isoTime) return isoTime[1];
      const loose = value.match(/\b(\d{1,2}:\d{2}:\d{2})\b/);
      return loose ? this.normalizeTimeInput(loose[1]) || loose[1] : '';
    },
    stateColor(state) {
      const colors = {
        WAITING: '#64748b',
        QUEUED: '#64748b',
        SCHEDULED: '#14b8a6',
        COMPILING: '#f59e0b',
        UPLOADING: '#f59e0b',
        EXECUTING: '#3b82f6',
        COMPLETED: '#10b981',
        FAILED: '#ef4444'
      };
      return colors[state] || '#e2e8f0';
    },
    flightMode(aircraftId) {
      const ac = this.telemetry[aircraftId];
      if (!ac?.actuator) return null;
      const tilt = ((ac.actuator.tilt_left || 0) + (ac.actuator.tilt_right || 0)) / 2;
      if (tilt < 0.2) return 'MC';
      if (tilt > 0.8) return 'FW';
      return 'TRANS';
    },
    tiltBarStyle(val) {
      const v = val || 0;
      let color;
      if (v < 0.2) color = '#3b82f6';
      else if (v > 0.8) color = '#10b981';
      else color = '#f59e0b';
      return { width: `${(v * 100).toFixed(1)}%`, backgroundColor: color };
    },
    aircraftColor(aircraftId) {
      const colors = { 
        UAM0001: '#3b82f6', // Blue
        UAM0002: '#10b981', // Green
        UAM0003: '#f59e0b', // Amber
        UAM0004: '#ec4899', // Pink
        UAM0005: '#8b5cf6'  // Purple
      };
      return colors[aircraftId] || '#cbd5e1';
    },
    initMap() {
      this.map = L.map('map').setView([37.54, 126.87], 12);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 20
      }).addTo(this.map);
    },
    updateMapMarkers() {
      Object.keys(this.telemetry).forEach(aircraftId => {
        const data = this.telemetry[aircraftId];
        if (!data?.position || data.position.lat === undefined) return;

        const lat = data.position.lat;
        const lon = data.position.lon;

        // 위치가 0,0 근처면 GPS Fix 전이므로 마커를 그리지 않음
        if (Math.abs(lat) < 0.1 && Math.abs(lon) < 0.1) return;

        // 이제 서버에서 Degree 단위로 보내주므로 그대로 사용
        // MAVSDK yaw_deg 범위: -180~180 → 0~360으로 정규화
        let yawRaw = Number.isFinite(data.attitude?.yaw) ? data.attitude.yaw : 0;
        const yawDeg = ((yawRaw % 360) + 360) % 360;

        if (!this.markers[aircraftId]) {
          const color = this.aircraftColor(aircraftId);

          const icon = L.divIcon({
            className: 'custom-div-icon',
            html: `
              <div class="drone-marker" style="transform-origin: 12px 12px; width: 24px; height: 24px;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2L22 20L12 17L2 20L12 2Z" fill="${color}" stroke="white" stroke-width="1.5"/>
                </svg>
              </div>
            `,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
          });

          this.markers[aircraftId] = L.marker([lat, lon], { icon }).addTo(this.map);
          this.markers[aircraftId].bindTooltip(
            `<b>${aircraftId}</b>`,
            { permanent: true, direction: 'right', className: 'marker-tooltip' }
          );
          this.markers[aircraftId].__heading = yawDeg;
          this.trails[aircraftId] = L.polyline([], {
            color,
            weight: 2,
            opacity: 0.5,
            dashArray: '4 4'
          }).addTo(this.map);
          
          // 처음 생성 시에도 방향을 맞춰준다.
          const newEl = this.markers[aircraftId].getElement();
          if (newEl) {
            const innerDiv = newEl.querySelector('.drone-marker');
            if (innerDiv) {
              innerDiv.style.transform = `rotate(${yawDeg}deg)`;
            }
          }
          return;
        }

        this.markers[aircraftId].setLatLng([lat, lon]);

        const altStr = Number.isFinite(data.position.alt) ? data.position.alt.toFixed(0) : '?';
        this.markers[aircraftId].setTooltipContent(
          `<b>${aircraftId}</b><br>${data.phase || ''} ${data.missionState || ''}<br>ALT: ${altStr}m`
        );

        // CSS transition을 제거하고 10Hz 속도에 맞춰 즉시 스냅되도록 함 (360/0 경계 버그 방지)
        this.markers[aircraftId].__heading = yawDeg;

        const el = this.markers[aircraftId].getElement();
        if (el) {
          const innerDiv = el.querySelector('.drone-marker');
          if (innerDiv) {
            innerDiv.style.transform = `rotate(${yawDeg}deg)`;
          }
        }

        const trail = this.trails[aircraftId];
        if (trail) {
          const latlngs = trail.getLatLngs();
          latlngs.push(L.latLng(lat, lon));
          if (latlngs.length > 500) latlngs.shift();
          trail.setLatLngs(latlngs);
        }
      });
    },
    updateMissionRoutes() {
      const activeMissionIds = new Set(this.missions.map(m => m.missionId));

      Object.keys(this.missionRoutes).forEach(missionId => {
        if (!activeMissionIds.has(missionId)) {
          this.map.removeLayer(this.missionRoutes[missionId]);
          delete this.missionRoutes[missionId];
        }
      });

      Object.keys(this.missionSpawns).forEach(missionId => {
        if (!activeMissionIds.has(missionId)) {
          this.map.removeLayer(this.missionSpawns[missionId]);
          delete this.missionSpawns[missionId];
        }
      });

      this.missions.forEach(mission => {
        const points = Array.isArray(mission.routePoints) ? mission.routePoints : [];
        if (points.length < 2) return;

        const color = this.aircraftColor(mission.aircraftId);
        const latlngs = points.map(point => [point.lat, point.lon]);

        if (!this.missionRoutes[mission.missionId]) {
          this.missionRoutes[mission.missionId] = L.polyline(latlngs, {
            color,
            weight: 3,
            opacity: 0.85,
          }).addTo(this.map);
        } else {
          this.missionRoutes[mission.missionId].setLatLngs(latlngs);
          this.missionRoutes[mission.missionId].setStyle({ color });
        }

        const spawn = mission.spawnPoint;
        if (spawn?.lat !== undefined && spawn?.lon !== undefined) {
          if (!this.missionSpawns[mission.missionId]) {
            this.missionSpawns[mission.missionId] = L.circleMarker([spawn.lat, spawn.lon], {
              radius: 6,
              color,
              weight: 2,
              fillColor: color,
              fillOpacity: 0.9,
            }).addTo(this.map);
          } else {
            this.missionSpawns[mission.missionId].setLatLng([spawn.lat, spawn.lon]);
            this.missionSpawns[mission.missionId].setStyle({ color, fillColor: color });
          }

          this.missionSpawns[mission.missionId].bindTooltip(
            `<b>FP${mission.flightPlanNumber}</b><br>${mission.aircraftId} spawn`,
            { direction: 'top' }
          );
        }
      });
    },
    upsertTelemetry(data) {
      if (!data?.aircraftId) return;
      this.telemetry = {
        ...this.telemetry,
        [data.aircraftId]: data,
      };
      if (!this.selectedAircraft || !this.telemetry[this.selectedAircraft]) {
        this.selectedAircraft = data.aircraftId;
      }
    },
    updateSimulationTimeState(data) {
      const next = {
        time: typeof data?.time === 'string' ? data.time : null,
        seconds: Number.isInteger(data?.seconds) ? data.seconds : null,
        available: Boolean(data?.available),
        source: typeof data?.source === 'string' ? data.source : null,
      };
      this.simulationTime = next;
      if (!this.simTimeInputFocused && !this.simClockRunning && next.time) {
        this.simTimeInput = next.time;
      }
    },
    async fetchSimulationTime() {
      try {
        const res = await fetch('/api/v1/time', { cache: 'no-store' });
        if (!res.ok) return;
        const data = await res.json();
        this.updateSimulationTimeState(data);
      } catch (e) {
        // External clock may not be up yet; keep the UI usable.
      }
    },
    async postSimulationTime(timeText, { silent = false } = {}) {
      const normalized = this.normalizeTimeInput(timeText);
      if (!normalized) {
        if (!silent) this.showToast('Time must be HH:MM:SS, e.g. 15:52:10', 'error');
        return false;
      }

      try {
        const res = await fetch('/api/v1/time', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ time: normalized, source: 'dashboard-gui' }),
        });
        const data = await res.json();
        if (!res.ok) {
          if (!silent) this.showToast(data.message || 'Failed to set simulation time', 'error');
          return false;
        }
        this.updateSimulationTimeState(data);
        this.simTimeInput = data.time || normalized;
        if (!silent) this.showToast(`Simulation time set: ${this.simTimeInput}`);
        return true;
      } catch (e) {
        if (!silent) this.showToast(`Clock update failed: ${e.message}`, 'error');
        return false;
      }
    },
    postManualSimulationTime() {
      return this.postSimulationTime(this.simTimeInput);
    },
    syncInputFromServer() {
      if (this.simulationTime.time) {
        this.simTimeInput = this.simulationTime.time;
        this.showToast(`Synced from server: ${this.simTimeInput}`);
      } else {
        this.fetchSimulationTime().then(() => {
          if (this.simulationTime.time) {
            this.simTimeInput = this.simulationTime.time;
            this.showToast(`Synced from server: ${this.simTimeInput}`);
          } else {
            this.showToast('No simulation time received yet', 'error');
          }
        });
      }
    },
    nudgeSimulationTime(deltaSec) {
      const base =
        Number.isInteger(this.simulationTime.seconds) ? this.simulationTime.seconds :
        this.timeToSeconds(this.simTimeInput);
      if (base === null) {
        this.showToast('Set or sync a valid time first', 'error');
        return;
      }
      const next = this.secondsToTime(base + deltaSec);
      this.simTimeInput = next;
      this.postSimulationTime(next);
    },
    useMissionArmTime() {
      if (!this.activeMissionHint?.scheduledArmAt) {
        this.showToast('Active mission has no arm time yet', 'error');
        return;
      }
      this.simTimeInput = this.clockText(this.activeMissionHint.scheduledArmAt);
      this.postSimulationTime(this.simTimeInput);
    },
    useMissionStartTime() {
      if (!this.activeMissionHint?.scheduledStartAt) {
        this.showToast('Active mission has no start time yet', 'error');
        return;
      }
      this.simTimeInput = this.clockText(this.activeMissionHint.scheduledStartAt);
      this.postSimulationTime(this.simTimeInput);
    },
    startGuiClock() {
      const base =
        this.timeToSeconds(this.simTimeInput) ??
        (Number.isInteger(this.simulationTime.seconds) ? this.simulationTime.seconds : null);
      if (base === null) {
        this.showToast('Set or sync a valid HH:MM:SS time before Run', 'error');
        return;
      }

      this.simTimeInput = this.secondsToTime(base);
      this.simClockRunning = true;
      this.postSimulationTime(this.simTimeInput, { silent: true });
      this.showToast(`GUI clock running at ${this.simClockRate}x`);

      if (this.simClockTickTimer) {
        window.clearInterval(this.simClockTickTimer);
      }

      this.simClockTickTimer = window.setInterval(async () => {
        if (this.simClockBusy) return;
        this.simClockBusy = true;
        try {
          const current =
            Number.isInteger(this.simulationTime.seconds) ? this.simulationTime.seconds :
            this.timeToSeconds(this.simTimeInput);
          if (current === null) return;
          const next = this.secondsToTime(current + Number(this.simClockRate || 1));
          this.simTimeInput = next;
          await this.postSimulationTime(next, { silent: true });
        } finally {
          this.simClockBusy = false;
        }
      }, 1000);
    },
    stopGuiClock() {
      if (this.simClockTickTimer) {
        window.clearInterval(this.simClockTickTimer);
        this.simClockTickTimer = null;
      }
      if (this.simClockRunning) {
        this.showToast('GUI clock stopped');
      }
      this.simClockRunning = false;
    },
    mergeTelemetry(items) {
      if (!Array.isArray(items)) return;
      items.forEach(data => this.upsertTelemetry(data));
    },
    handleFileDrop(event) {
      this.isDragOver = false;
      const files = event.dataTransfer.files;
      if (files.length > 0) this.readFile(files[0]);
    },
    handleFileSelect(event) {
      const files = event.target.files;
      if (files.length > 0) this.readFile(files[0]);
      event.target.value = '';
    },
    readFile(file) {
      if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
        this.showToast('Please upload a valid JSON file', 'error');
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const obj = JSON.parse(e.target.result);
          this.missionJson = JSON.stringify(obj, null, 2);
          this.showToast('File loaded. You may now submit.');
        } catch (err) {
          this.showToast('Invalid JSON file format', 'error');
        }
      };
      reader.readAsText(file);
    },
    clearMissionJson() {
      this.missionJson = '';
    },
    async submitMission() {
      if (!this.missionJson.trim()) {
        this.showToast('Please enter Mission JSON', 'error');
        return;
      }

      try {
        const payload = JSON.parse(this.missionJson);
        const res = await fetch('/api/v1/missions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok) {
          this.showToast('Mission Accepted!');
          this.missionJson = '';
          this.fetchMissions();
        } else {
          this.showToast(`Error: ${JSON.stringify(data.validation_errors || data.message)}`, 'error');
        }
      } catch (e) {
        this.showToast('Invalid JSON syntax', 'error');
      }
    },
    async fetchMissions() {
      try {
        const res = await fetch('/api/v1/missions/status');
        const data = await res.json();
        if (data.missions) {
          this.missions = [...data.missions].reverse();
          this.updateMissionRoutes();
        }
      } catch (e) {
        // Ignore transient polling failures.
      }
    },
    async fetchTelemetrySnapshot() {
      try {
        const res = await fetch('/api/v1/telemetry');
        const data = await res.json();
        if (data.aircraft) {
          this.mergeTelemetry(data.aircraft);
        }
      } catch (e) {
        // Ignore transient polling failures.
      }
    },
    connectWebSocket() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        return;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      this.ws = new WebSocket(`${protocol}://${window.location.host}/api/v1/ws/live`);

      this.ws.onopen = () => {
        this.wsConnected = true;
        this.fetchTelemetrySnapshot();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.upsertTelemetry(data);
        } catch (e) {
          console.error('WS parse error', e);
        }
      };

      this.ws.onclose = () => {
        this.wsConnected = false;
        this.wsRetryTimer = window.setTimeout(() => this.connectWebSocket(), 3000);
      };

      this.ws.onerror = () => {
        this.wsConnected = false;
      };
    },
    showToast(msg, type = 'success') {
      this.toastMessage = msg;
      this.toastType = type;
      window.setTimeout(() => {
        this.toastMessage = '';
      }, 3000);
    }
  }
});

app.mount('#app');
