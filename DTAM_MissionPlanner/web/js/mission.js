/* mission.js — mission planning (route + free waypoint modes) */
window.ODT = window.ODT || {};

ODT.Mission = (function () {
  let mode = 'route'; // 'route' | 'free'
  let routeData = null;
  let freeWaypoints = [];
  let freeMarkers = [];
  let routeLayerAdded = false;
  let corridorLayerAdded = false;
  let vertiportMarkers = [];
  let waypointLabelMarkers = [];
  let freeAltitudePopup = null;
  let freeAltitudePopupIndex = -1;
  let lastMissionIcd = null;
  let missionIcdRefreshHandle = 0;
  let waypointData = [];
  let vertiportData = [];
  let corridorVisiblePref = true;
  let corridorSceneHandle = 0;
  let routeMapPickEnabled = false;
  let simulationFleet = [];
  let simulationFleetSeed = 1;
  let activeMissionIndex = 0;
  const CORRIDOR_ALT_M = 304.8;
  const CORRIDOR_TOP_M = 311.0;
  const CORRIDOR_POINT_TOP_M = 320.0;
  const CORRIDOR_HALF_WIDTH_M = 18;
  const CORRIDOR_POINT_SIZE_M = 18;
  const CORRIDOR_DASH_M = 140;
  const CORRIDOR_GAP_M = 90;
  const CORRIDOR_CAP_SEGMENTS = 6;
  const ROUTE_HALF_WIDTH_M = 10;
  const ROUTE_TOP_BUFFER_M = 10;
  const ROUTE_NODE_SIZE_M = 14;
  const ROUTE_NODE_TOP_BUFFER_M = 24;
  const FREE_MISSION_HALF_WIDTH_M = 9;
  const FREE_MISSION_TOP_BUFFER_M = 10;
  const FREE_MISSION_NODE_SIZE_M = 14;
  const FREE_MISSION_NODE_TOP_BUFFER_M = 22;
  const FREE_WAYPOINT_DEFAULT_ALT_M = 300;
  const ROUTE_TURN_RADIUS_M = 400;
  const ROUTE_ARC_STEP_M = 40;
  const CORRIDOR_3D_PITCH_THRESHOLD = 14;
  const CORRIDOR_3D_ZOOM_THRESHOLD = 9.8;
  const ROUTE_3D_PITCH_THRESHOLD = 8;
  const ROUTE_3D_ZOOM_THRESHOLD = 8.8;
  const MAX_SIMULATION_FLEET = 12;

  function init() {
    // Mode buttons
    document.querySelectorAll('.mode-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        setMode(btn.getAttribute('data-mode'));
      });
    });

    // Compute route button
    const computeBtn = document.getElementById('compute-route-btn');
    if (computeBtn) computeBtn.addEventListener('click', computeRoute);

    const routeMapPickBtn = document.getElementById('route-map-pick-toggle');
    if (routeMapPickBtn) {
      routeMapPickBtn.addEventListener('click', toggleRouteMapPickMode);
    }

    const depSel = document.getElementById('departure-select');
    const arrSel = document.getElementById('arrival-select');
    depSel?.addEventListener('change', () => {
      syncSelectedVertiports();
      renderSimulationFleet();
      scheduleMissionIcdAutoRefresh();
    });
    arrSel?.addEventListener('change', () => {
      syncSelectedVertiports();
      renderSimulationFleet();
      scheduleMissionIcdAutoRefresh();
    });
    document.addEventListener('odt:languagechange', () => {
      syncSelectedVertiports();
      renderSimulationFleet();
      updateMissionEditorHeading();
    });

    // Free mission buttons
    const clearBtn = document.getElementById('clear-free-mission');
    if (clearBtn) clearBtn.addEventListener('click', clearFreeWaypoints);

    const execBtn = document.getElementById('execute-free-mission');
    if (execBtn) execBtn.addEventListener('click', executeMission);

    const saveIcdBtn = document.getElementById('save-mission-icd');
    if (saveIcdBtn) saveIcdBtn.addEventListener('click', saveMissionIcd);

    const sendDtamBtn = document.getElementById('send-mission-dtam');
    if (sendDtamBtn) sendDtamBtn.addEventListener('click', sendMissionToDtam);

    const dtamApplyBtn = document.getElementById('mission-sim-dtam-apply');
    if (dtamApplyBtn) dtamApplyBtn.addEventListener('click', async () => {
      const ip = document.getElementById('mission-sim-dtam-target-ip')?.value?.trim();
      const wsPort = parseInt(document.getElementById('mission-sim-dtam-ws-port')?.value, 10);
      try {
        await ODT.Dtam?.applyTargetConfig?.({
          target_ip: ip || undefined,
          ws_port: Number.isFinite(wsPort) ? wsPort : undefined,
        });
        ODT.OperatorLog?.success('DTAM target', `→ ws://${ip || '(unchanged)'}:${Number.isFinite(wsPort) ? wsPort : '(unchanged)'}/ws/dtam`);
      } catch (_) {}
    });
    const dtamRefreshBtn = document.getElementById('mission-sim-dtam-refresh');
    if (dtamRefreshBtn) dtamRefreshBtn.addEventListener('click', () => {
      ODT.Dtam?.refreshStatus?.(false);
    });

    ['mission-icd-flight-plan-number', 'mission-icd-std', 'mission-sim-replay-step'].forEach((id) => {
      const input = document.getElementById(id);
      input?.addEventListener('input', scheduleMissionIcdAutoRefresh);
      input?.addEventListener('change', scheduleMissionIcdAutoRefresh);
    });

    document.getElementById('mission-fleet-count')?.addEventListener('input', syncSimulationFleetCountFromInput);
    document.getElementById('mission-fleet-count')?.addEventListener('change', syncSimulationFleetCountFromInput);

    // Map click for free waypoints
    const map = ODT.MapManager.getMap();
    if (map) {
      map.on('click', onMapClick);
      map.on('contextmenu', onMapRightClick);
      map.on('pitch', scheduleCorridorSceneUpdate);
      map.on('zoom', scheduleCorridorSceneUpdate);
      map.on('terrain', scheduleCorridorSceneUpdate);
    }

    updateMapPickUI();
    initializeMissionIcdInputs();
    ensureSimulationFleet();
    renderSimulationFleet();
    loadActiveMissionIntoEditor({ preserveViewport: true });
    loadData();
  }

  async function loadData() {
    try {
      [vertiportData, waypointData] = await Promise.all([
        ODT.api('/api/vertiports'),
        ODT.api('/api/waypoints'),
      ]);

      populateSelects();
      renderVertiportList();
      renderWaypointList();
      addCorridorLayer();
      addVertiportMarkers();
      addWaypointLabelMarkers();
      syncSelectedVertiports();
      scheduleCorridorSceneUpdate();

      document.getElementById('vertiport-count').textContent = vertiportData.length;
      document.getElementById('waypoint-count').textContent = waypointData.length;
    } catch (e) {
      console.error('Failed to load data:', e);
      ODT.OperatorLog?.error(
        ODT.t('log_data_load_failed_title'),
        ODT.t('log_data_load_failed_message')
      );
    }
  }

  function populateSelects() {
    const depSel = document.getElementById('departure-select');
    const arrSel = document.getElementById('arrival-select');
    if (!depSel || !arrSel) return;

    const sorted = [...vertiportData].sort((a, b) => a.name.localeCompare(b.name));
    for (const vp of sorted) {
      const opt1 = new Option(vp.name, vp.name);
      const opt2 = new Option(vp.name, vp.name);
      depSel.appendChild(opt1);
      arrSel.appendChild(opt2);
    }
  }

  function getActiveMapPickTarget() {
    if (!routeMapPickEnabled || mode !== 'route') {
      return null;
    }
    const { departure, arrival } = getSelectedVertiportNames();
    if (!departure) return 'departure';
    if (!arrival) return 'arrival';
    return 'departure';
  }

  function announceMapPickTarget() {
    const target = getActiveMapPickTarget();
    if (!target) return;
    ODT.OperatorLog?.info(
      ODT.t('log_map_pick_started_title'),
      ODT.t(
        target === 'departure'
          ? 'log_map_pick_departure_message'
          : 'log_map_pick_arrival_message'
      )
    );
  }

  function toggleRouteMapPickMode() {
    routeMapPickEnabled = !routeMapPickEnabled;
    updateMapPickUI();
    if (routeMapPickEnabled) {
      announceMapPickTarget();
    }
  }

  function updateMapPickUI() {
    const routeMapPickBtn = document.getElementById('route-map-pick-toggle');
    const routeMapPickStatus = document.getElementById('route-map-pick-status');
    const target = getActiveMapPickTarget();
    const targetLabel = target ? ODT.t(target) : '';

    if (routeMapPickBtn) {
      routeMapPickBtn.classList.toggle('active', !!target);
      routeMapPickBtn.textContent = target
        ? `${ODT.t('map_pick')} · ${targetLabel}`
        : ODT.t('map_pick');
      if (target) {
        routeMapPickBtn.textContent = `${ODT.t('map_pick')} - ${targetLabel}`;
      }
      routeMapPickBtn.title = target
        ? ODT.t(
            target === 'departure'
              ? 'pick_departure_on_map'
              : 'pick_arrival_on_map'
          )
        : ODT.t('map_pick');
    }

    if (routeMapPickStatus) {
      routeMapPickStatus.textContent = target
        ? ODT.t(
            target === 'departure'
              ? 'log_map_pick_departure_message'
              : 'log_map_pick_arrival_message'
          )
        : '';
      routeMapPickStatus.classList.toggle('active', !!target);
    }

    const map = ODT.MapManager.getMap();
    if (map) {
      map.getCanvas().style.cursor = target ? 'crosshair' : '';
    }
  }

  function initializeMissionIcdInputs() {
    const stdInput = document.getElementById('mission-icd-std');
    if (stdInput) {
      stdInput.addEventListener('blur', () => {
        const normalized = normalizeMissionIcdStdValue(stdInput.value);
        if (normalized) {
          stdInput.value = normalized;
        }
      });
      stdInput.addEventListener('change', () => {
        const normalized = normalizeMissionIcdStdValue(stdInput.value);
        if (normalized) {
          stdInput.value = normalized;
        }
      });
    }
    if (stdInput && !stdInput.value) {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      const ss = String(now.getSeconds()).padStart(2, '0');
      stdInput.value = `${hh}:${mm}:${ss}`;
    }
    invalidateMissionIcdPreview();
  }

  function normalizeMissionIcdStdValue(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';

    const compact = raw.replace(/\s+/g, '');
    let parts = [];

    if (/^\d{1,2}:\d{1,2}(:\d{1,2})?$/.test(compact)) {
      parts = compact.split(':');
    } else if (/^\d{4}$/.test(compact)) {
      parts = [compact.slice(0, 2), compact.slice(2, 4), '00'];
    } else if (/^\d{6}$/.test(compact)) {
      parts = [compact.slice(0, 2), compact.slice(2, 4), compact.slice(4, 6)];
    } else {
      return '';
    }

    const hh = Number(parts[0]);
    const mm = Number(parts[1]);
    const ss = Number(parts[2] ?? '00');
    if (
      !Number.isInteger(hh) || !Number.isInteger(mm) || !Number.isInteger(ss) ||
      hh < 0 || hh > 23 || mm < 0 || mm > 59 || ss < 0 || ss > 59
    ) {
      return '';
    }
    return [
      String(hh).padStart(2, '0'),
      String(mm).padStart(2, '0'),
      String(ss).padStart(2, '0'),
    ].join(':');
  }

  function getMissionIcdMessages() {
    if (ODT.I18n?.getLanguage() === 'ko') {
      return {
        empty: '아직 생성된 ICD가 없습니다.',
        stale: '현재 미션 기준으로 ICD를 다시 생성해야 합니다.',
        missing: '먼저 route 계산 또는 free mission waypoint 구성이 필요합니다.',
        generatedTitle: 'Mission ICD 생성 완료',
        generatedMessage: 'Mission ICD v1 preview를 갱신했습니다.',
        savedTitle: 'Mission ICD 저장 완료',
        savedMessage: (savedPath) => `Mission ICD 파일을 저장했습니다.\n${savedPath}`,
        failedTitle: 'Mission ICD 처리 실패',
        failedMessage: 'Mission ICD를 생성하거나 저장하지 못했습니다.',
        invalidPrefix: 'Validation errors:',
        warningsPrefix: 'Warnings:',
      };
    }
    return {
      empty: 'No ICD generated yet.',
      stale: 'The active mission changed. Generate the ICD again.',
      missing: 'Compute a route or create a free mission before exporting ICD.',
      generatedTitle: 'Mission ICD generated',
      generatedMessage: 'Mission ICD v1 preview updated.',
      savedTitle: 'Mission ICD saved',
      savedMessage: (savedPath) => `Mission ICD file saved.\n${savedPath}`,
      failedTitle: 'Mission ICD failed',
      failedMessage: 'The mission ICD could not be generated or saved.',
      invalidPrefix: 'Validation errors:',
      warningsPrefix: 'Warnings:',
    };
  }

  function setMissionIcdStatus(text) {
    const statusEl = document.getElementById('mission-icd-status');
    if (statusEl) {
      statusEl.textContent = text;
    }
  }

  function invalidateMissionIcdPreview() {
    if (missionIcdRefreshHandle) {
      window.clearTimeout(missionIcdRefreshHandle);
      missionIcdRefreshHandle = 0;
    }
    lastMissionIcd = null;
    const previewEl = document.getElementById('mission-icd-preview');
    if (previewEl) {
      previewEl.textContent = '';
    }
    const messages = getMissionIcdMessages();
    const hasMission = !!routeData || freeWaypoints.length > 0;
    setMissionIcdStatus(hasMission ? messages.stale : messages.empty);
  }

  function scheduleMissionIcdAutoRefresh() {
    if (missionIcdRefreshHandle) {
      window.clearTimeout(missionIcdRefreshHandle);
      missionIcdRefreshHandle = 0;
    }
    if (!routeData && !freeWaypoints.length) {
      invalidateMissionIcdPreview();
      return;
    }
    setMissionIcdStatus(getMissionIcdMessages().stale);
    missionIcdRefreshHandle = window.setTimeout(() => {
      missionIcdRefreshHandle = 0;
      generateMissionIcd({ logSuccess: false, warnOnMissing: false });
    }, 120);
  }

  function getSimulationFleetMessages() {
    if (ODT.I18n?.getLanguage?.() === 'ko') {
      return {
        title: '시뮬레이션 편대',
        add: '기체 추가',
        remove: '삭제',
        aircraftId: 'Aircraft ID',
        vehicleName: 'Vehicle',
        empty: '비행체를 하나 이상 추가하세요.',
        fleetCount: (count) => `기체 ${count}대`,
      };
    }
    return {
      title: 'Simulation Fleet',
      add: 'Add Aircraft',
      remove: 'Remove',
      aircraftId: 'Aircraft ID',
      vehicleName: 'Vehicle',
      empty: 'Add at least one aircraft for replay.',
      fleetCount: (count) => `${count} aircraft`,
    };
  }

  function createSimulationFleetEntry(index = simulationFleet.length) {
    simulationFleetSeed += 1;
    return {
      id: `fleet-${Date.now()}-${simulationFleetSeed}`,
      aircraftId: `UAM${String(index + 1).padStart(4, '0')}`,
      vehicleName: `Drone${index + 1}`,
    };
  }

  function ensureSimulationFleet() {
    if (!simulationFleet.length) {
      simulationFleet = [createSimulationFleetEntry(0)];
    }
  }

  function sanitizeSimulationFleetEntry(entry, index) {
    const fallback = createSimulationFleetEntry(index);
    return {
      id: entry?.id || fallback.id,
      aircraftId: String(entry?.aircraftId || fallback.aircraftId).trim() || fallback.aircraftId,
      vehicleName: String(entry?.vehicleName || entry?.vehicle_name || fallback.vehicleName).trim() || fallback.vehicleName,
    };
  }

  function getSimulationFleetPayload() {
    ensureSimulationFleet();
    simulationFleet = simulationFleet.map((entry, index) => sanitizeSimulationFleetEntry(entry, index));
    return simulationFleet.map((entry) => ({
      aircraftId: entry.aircraftId,
      vehicleName: entry.vehicleName,
    }));
  }

  function validateSimulationFleet() {
    const fleet = getSimulationFleetPayload();
    const seen = new Set();
    for (const entry of fleet) {
      const vehicleKey = String(entry.vehicleName || '').trim().toLowerCase();
      if (!vehicleKey) {
        continue;
      }
      if (seen.has(vehicleKey)) {
        return ODT.I18n?.getLanguage?.() === 'ko'
          ? 'Vehicle 이름은 중복될 수 없습니다.'
          : 'Vehicle names must be unique.';
      }
      seen.add(vehicleKey);
    }
    return '';
  }

  function getSimulationReplayStep() {
    const replayStep = Number(document.getElementById('mission-sim-replay-step')?.value);
    return Number.isFinite(replayStep) && replayStep > 0 ? Math.max(replayStep, 0.1) : 0.1;
  }

  function getSimulationPlaybackSpeed() {
    const playbackSpeed = Number(ODT.Simulator?.getPlaybackSpeed?.());
    if (!Number.isFinite(playbackSpeed) || playbackSpeed <= 0) {
      return 1;
    }
    return Math.min(Math.max(playbackSpeed, 1), 8);
  }

  function updateSimulationFleetSummary() {
    const summaryEl = document.getElementById('mission-sim-fleet-count');
    if (summaryEl) {
      summaryEl.textContent = getSimulationFleetMessages().fleetCount(getSimulationFleetPayload().length);
    }
  }

  function renderSimulationFleet() {
    ensureSimulationFleet();
    simulationFleet = simulationFleet.map((entry, index) => sanitizeSimulationFleetEntry(entry, index));

    const messages = getSimulationFleetMessages();
    const titleEl = document.querySelector('#mission-sim-card .mission-sim-title');
    const addBtn = document.getElementById('mission-fleet-add');
    const listEl = document.getElementById('mission-fleet-list');

    if (titleEl) titleEl.textContent = messages.title;
    if (addBtn) addBtn.textContent = messages.add;
    if (!listEl) {
      updateSimulationFleetSummary();
      return;
    }

    listEl.innerHTML = '';
    if (!simulationFleet.length) {
      const empty = document.createElement('div');
      empty.className = 'mission-fleet-empty';
      empty.textContent = messages.empty;
      listEl.appendChild(empty);
      updateSimulationFleetSummary();
      return;
    }

    simulationFleet.forEach((entry, index) => {
      const row = document.createElement('div');
      row.className = 'mission-fleet-row';

      const aircraftField = document.createElement('label');
      aircraftField.className = 'mission-fleet-field';
      const aircraftLabel = document.createElement('span');
      aircraftLabel.className = 'mission-fleet-label';
      aircraftLabel.textContent = messages.aircraftId;
      const aircraftInput = document.createElement('input');
      aircraftInput.className = 'settings-input simulator-input';
      aircraftInput.type = 'text';
      aircraftInput.value = entry.aircraftId;
      aircraftInput.addEventListener('input', () => {
        simulationFleet[index].aircraftId = aircraftInput.value;
        scheduleMissionIcdAutoRefresh();
        updateSimulationFleetSummary();
      });

      const vehicleField = document.createElement('label');
      vehicleField.className = 'mission-fleet-field';
      const vehicleLabel = document.createElement('span');
      vehicleLabel.className = 'mission-fleet-label';
      vehicleLabel.textContent = messages.vehicleName;
      const vehicleInput = document.createElement('input');
      vehicleInput.className = 'settings-input simulator-input';
      vehicleInput.type = 'text';
      vehicleInput.value = entry.vehicleName;
      vehicleInput.addEventListener('input', () => {
        simulationFleet[index].vehicleName = vehicleInput.value;
        scheduleMissionIcdAutoRefresh();
      });

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-ghost btn-sm mission-fleet-remove';
      removeBtn.textContent = messages.remove;
      removeBtn.disabled = simulationFleet.length <= 1;
      removeBtn.addEventListener('click', () => {
        if (simulationFleet.length <= 1) return;
        simulationFleet.splice(index, 1);
        renderSimulationFleet();
        scheduleMissionIcdAutoRefresh();
      });

      aircraftField.appendChild(aircraftLabel);
      aircraftField.appendChild(aircraftInput);
      vehicleField.appendChild(vehicleLabel);
      vehicleField.appendChild(vehicleInput);
      row.appendChild(aircraftField);
      row.appendChild(vehicleField);
      row.appendChild(removeBtn);
      listEl.appendChild(row);
    });

    updateSimulationFleetSummary();
    ODT.Simulator?.refreshMissionState?.();
  }

  function addSimulationFleetEntry() {
    simulationFleet.push(createSimulationFleetEntry(simulationFleet.length));
    renderSimulationFleet();
    scheduleMissionIcdAutoRefresh();
  }

  function getMissionIcdOptions() {
    const stdInput = document.getElementById('mission-icd-std');
    const normalizedStd = normalizeMissionIcdStdValue(stdInput?.value || '');
    if (stdInput && normalizedStd && stdInput.value !== normalizedStd) {
      stdInput.value = normalizedStd;
    }
    const fleet = getSimulationFleetPayload();
    return {
      aircraftId: fleet[0]?.aircraftId || 'UAM0001',
      flightPlanNumber: document.getElementById('mission-icd-flight-plan-number')?.value?.trim() || '',
      std: normalizedStd || stdInput?.value || '',
      cruiseSpeedMps: parseFloat(document.getElementById('settings-speed')?.value) || 30,
    };
  }

  function buildMissionIcdPayload() {
    if (mode === 'route') {
      if (!routeData) return null;
      return {
        mode: 'route',
        departureName: document.getElementById('departure-select')?.value || routeData.path?.[0] || '',
        arrivalName: document.getElementById('arrival-select')?.value || routeData.path?.[routeData.path.length - 1] || '',
        routeData,
        fleet: getSimulationFleetPayload(),
        options: getMissionIcdOptions(),
      };
    }
    if (!freeWaypoints.length) return null;
    return {
      mode: 'free',
      freeWaypoints,
      fleet: getSimulationFleetPayload(),
      options: getMissionIcdOptions(),
    };
  }

  function renderMissionIcdPreview(result) {
    lastMissionIcd = result || null;
    const previewEl = document.getElementById('mission-icd-preview');
    if (previewEl) {
      previewEl.textContent = JSON.stringify(result?.record || {}, null, 2);
    }

    const messages = getMissionIcdMessages();
    const lines = [];
    if (result?.validation && !result.validation.valid && Array.isArray(result.validation.errors)) {
      lines.push(messages.invalidPrefix);
      result.validation.errors.forEach((item) => lines.push(`- ${item}`));
    }
    if (Array.isArray(result?.warnings) && result.warnings.length) {
      if (lines.length) lines.push('');
      lines.push(messages.warningsPrefix);
      result.warnings.forEach((item) => lines.push(`- ${item}`));
    }
    if (!lines.length) {
      lines.push(messages.generatedMessage);
    }
    setMissionIcdStatus(lines.join('\n'));
  }

  function downloadMissionIcdFile(result) {
    const filename = String(result?.filename || 'mission_icd_v1.json');
    const content = JSON.stringify(result?.record || {}, null, 2);
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
  }

  async function requestMissionIcd(endpoint, options = {}) {
    const { warnOnMissing = true } = options;
    const payload = buildMissionIcdPayload();
    if (!payload) {
      if (warnOnMissing) {
        const messages = getMissionIcdMessages();
        ODT.OperatorLog?.warn(messages.failedTitle, messages.missing);
        setMissionIcdStatus(messages.missing);
      }
      return null;
    }
    const result = await ODT.postJSON(endpoint, payload);
    renderMissionIcdPreview(result);
    return result;
  }

  async function generateMissionIcd(options = {}) {
    const { logSuccess = true, warnOnMissing = true } = options;
    const messages = getMissionIcdMessages();
    try {
      const result = await requestMissionIcd('/api/mission/icd/export', { warnOnMissing });
      if (!result) return;
      if (logSuccess) {
        ODT.OperatorLog?.success(messages.generatedTitle, messages.generatedMessage);
      }
    } catch (e) {
      ODT.OperatorLog?.error(messages.failedTitle, ODT.humanizeError(e, messages.failedMessage));
      setMissionIcdStatus(ODT.humanizeError(e, messages.failedMessage));
    }
  }

  async function saveMissionIcd() {
    const messages = getMissionIcdMessages();
    try {
      const result = await requestMissionIcd('/api/mission/icd/export');
      if (!result) return;
      if (result?.validation && !result.validation.valid) {
        const invalidLogMessage =
          ODT.I18n?.getLanguage() === 'ko'
            ? 'Mission ICD validation 오류가 있어 다운로드하지 않았습니다.'
            : 'Mission ICD was not downloaded because validation failed.';
        ODT.OperatorLog?.warn(messages.failedTitle, invalidLogMessage);
        return;
      }
      downloadMissionIcdFile(result);
      const savedLogMessage =
        ODT.I18n?.getLanguage() === 'ko'
          ? 'Mission ICD 파일을 현재 컴퓨터로 다운로드했습니다.'
          : 'Mission ICD was downloaded to this computer.';
      ODT.OperatorLog?.success(
        messages.savedTitle,
        savedLogMessage
      );
    } catch (e) {
      ODT.OperatorLog?.error(messages.failedTitle, ODT.humanizeError(e, messages.failedMessage));
      setMissionIcdStatus(ODT.humanizeError(e, messages.failedMessage));
    }
  }

  async function sendMissionToDtam() {
    const payload = buildMissionIcdPayload();
    if (!payload) {
      ODT.OperatorLog?.warn(
        ODT.t('log_mission_not_ready_title'),
        ODT.t('log_mission_not_ready_message')
      );
      return;
    }
    try {
      await ODT.Dtam?.sendMission?.(payload);
    } catch (_) {}
  }

  async function applyMapVertiportSelection(vp) {
    const target = getActiveMapPickTarget();
    if (!target) return false;

    const depSel = document.getElementById('departure-select');
    const arrSel = document.getElementById('arrival-select');
    if (!depSel || !arrSel) return false;

    if (target === 'departure') {
      const restartingSequence = !!depSel.value && !!arrSel.value;
      depSel.value = vp.name;
      if (restartingSequence) {
        arrSel.value = '';
      }
      syncSelectedVertiports();

      ODT.OperatorLog?.success(
        ODT.t('log_map_pick_applied_title'),
        ODT.t('log_map_pick_applied_message', {
          role: ODT.t('departure'),
          name: vp.name,
        })
      );

      updateMapPickUI();
      announceMapPickTarget();
      return true;
    }

    if (depSel.value === vp.name) {
      ODT.OperatorLog?.warn(
        ODT.t('log_route_same_title'),
        ODT.t('log_route_same_message')
      );
      return false;
    }

    arrSel.value = vp.name;
    syncSelectedVertiports();

    ODT.OperatorLog?.success(
      ODT.t('log_map_pick_applied_title'),
      ODT.t('log_map_pick_applied_message', {
        role: ODT.t('arrival'),
        name: vp.name,
      })
    );

    await computeRoute();
    updateMapPickUI();
    return true;
  }

  function getSelectedVertiportNames() {
    return {
      departure: document.getElementById('departure-select')?.value || '',
      arrival: document.getElementById('arrival-select')?.value || '',
    };
  }

  function getVertiportRole(name) {
    const selected = getSelectedVertiportNames();
    if (selected.departure === name) return 'departure';
    if (selected.arrival === name) return 'arrival';
    return null;
  }

  function syncSelectedVertiports() {
    syncRouteSelectionState();
    renderVertiportList();
    addVertiportMarkers();
    updateMapPickUI();
  }

  function syncRouteSelectionState() {
    if (!routeData) return;
    const { departure, arrival } = getSelectedVertiportNames();
    const routeStart = routeData?.path?.[0] || '';
    const routeEnd = routeData?.path?.[routeData.path.length - 1] || '';
    if (departure !== routeStart || arrival !== routeEnd) {
      clearRouteDisplay();
    }
  }

  function renderVertiportList() {
    const list = document.getElementById('vertiport-list');
    if (!list) return;
    list.innerHTML = '';
    for (const vp of vertiportData) {
      const role = getVertiportRole(vp.name);
      const item = document.createElement('div');
      item.className = 'data-list-item';
      if (role) item.classList.add(role);
      item.innerHTML = `
        <div class="data-list-dot ${vp.inr_km > 1 ? 'hub' : ''}"></div>
        <span class="data-list-name">${vp.name}</span>
        ${role ? `<span class="data-list-role ${role}">${ODT.t(role === 'departure' ? 'selected_departure' : 'selected_arrival')}</span>` : ''}
        <span class="data-list-coords">${vp.lat.toFixed(4)}, ${vp.lon.toFixed(4)}</span>
      `;
      item.addEventListener('click', () => {
        ODT.MapManager.flyTo([vp.lon, vp.lat], 14);
      });
      list.appendChild(item);
    }
  }

  function renderWaypointList() {
    const list = document.getElementById('waypoint-list');
    if (!list) return;
    list.innerHTML = '';
    for (const wp of waypointData) {
      const item = document.createElement('div');
      item.className = 'data-list-item';
      item.innerHTML = `
        <div class="data-list-dot"></div>
        <span class="data-list-name">${wp.name}</span>
        <span class="data-list-coords">${wp.alt_m ? wp.alt_m.toFixed(0) + 'm' : ''}</span>
      `;
      item.addEventListener('click', () => {
        ODT.MapManager.flyTo([wp.lon, wp.lat], 14);
      });
      list.appendChild(item);
    }
  }

  function addVertiportMarkers() {
    const map = ODT.MapManager.getMap();
    if (!map) return;

    // Remove existing
    vertiportMarkers.forEach((m) => m.remove());
    vertiportMarkers = [];

    for (const vp of vertiportData) {
      const role = getVertiportRole(vp.name);
      const target = getActiveMapPickTarget();
      const el = document.createElement('button');
      const inner = document.createElement('div');
      const label = document.createElement('div');
      const labelText = document.createElement('span');
      el.type = 'button';
      el.className = `vertiport-marker ${vp.inr_km > 1 ? 'hub' : ''} ${role ? `is-${role}` : ''} ${target ? 'is-pick-armed' : ''}`;
      inner.className = 'vertiport-pin';
      label.className = `vertiport-name-label ${role ? `is-${role}` : ''}`;
      labelText.textContent = vp.name;
      inner.textContent =
        role === 'departure'
          ? 'D'
          : role === 'arrival'
            ? 'A'
            : 'V';
      el.appendChild(inner);
      label.appendChild(labelText);
      if (role) {
        const badge = document.createElement('span');
        badge.className = `vertiport-role-badge ${role}`;
        badge.textContent = ODT.t(role === 'departure' ? 'departure_badge' : 'arrival_badge');
        label.appendChild(badge);
      }
      el.appendChild(label);
      el.title = vp.name;
      el.addEventListener('mouseenter', () => el.classList.add('is-hovered'));
      el.addEventListener('mouseleave', () => el.classList.remove('is-hovered'));
      el.addEventListener('click', async () => {
        if (mode === 'route') {
          await applyMapVertiportSelection(vp);
        }
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([vp.lon, vp.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 15, closeButton: false }).setHTML(
            `<div class="map-popup-title">${vp.name}</div>`
          )
        )
        .addTo(map);
      vertiportMarkers.push(marker);
    }
  }

  function addCorridorLayer() {
    const map = ODT.MapManager.getMap();
    if (!map || corridorLayerAdded) return;

    const features2d = [];
    const features3d = [];

    const wpMap = {};
    waypointData.forEach((wp) => (wpMap[wp.name] = wp));
    const addedEdges = new Set();

    for (const wp of waypointData) {
      for (const linkName of wp.links) {
        const target = wpMap[linkName];
        if (!target) continue;
        const edgeKey = [wp.name, linkName].sort().join('|');
        if (addedEdges.has(edgeKey)) continue;
        addedEdges.add(edgeKey);
        features2d.push({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [
              [wp.lon, wp.lat],
              [target.lon, target.lat],
            ],
          },
          properties: { type: 'corridor' },
        });
        features3d.push(
          ...buildCorridorDashFeatures(
            { lat: wp.lat, lon: wp.lon },
            { lat: target.lat, lon: target.lon },
            'corridor'
          )
        );
      }
    }

    for (const vp of vertiportData) {
      for (const linkName of vp.links) {
        const target = wpMap[linkName];
        if (!target) continue;
        features2d.push({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [
              [vp.lon, vp.lat],
              [target.lon, target.lat],
            ],
          },
          properties: { type: 'vertiport-link' },
        });
        features3d.push(
          ...buildCorridorDashFeatures(
            { lat: vp.lat, lon: vp.lon },
            { lat: target.lat, lon: target.lon },
            'vertiport-link'
          )
        );
      }
    }

    for (const wp of waypointData) {
      features2d.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [wp.lon, wp.lat] },
        properties: { name: wp.name, alt: wp.alt_m },
      });
      features3d.push(buildCorridorPointFeature(wp));
    }

    map.addSource('corridors', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: features2d },
    });

    map.addSource('corridors-3d', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: features3d },
    });

    map.addLayer({
      id: 'corridor-lines',
      type: 'line',
      source: 'corridors',
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: {
        'line-color': [
          'match',
          ['get', 'type'],
          'vertiport-link', '#60a5fa',
          '#f59e0b'
        ],
        'line-width': 1.55,
        'line-dasharray': [3.5, 3.5],
        'line-opacity': 0.5,
        'line-opacity-transition': { duration: 300 },
      },
    });

    map.addLayer({
      id: 'corridor-ribbon-3d',
      type: 'fill-extrusion',
      source: 'corridors-3d',
      filter: ['==', ['get', 'shape'], 'dash'],
      layout: { visibility: 'none' },
      paint: {
        'fill-extrusion-color': [
          'match',
          ['get', 'type'],
          'vertiport-link', 'rgba(59, 130, 246, 0.34)',
          'rgba(245, 158, 11, 0.42)'
        ],
        'fill-extrusion-base': ['get', 'base_m'],
        'fill-extrusion-height': ['get', 'height_m'],
        'fill-extrusion-opacity': 0.62,
      },
    });

    map.addLayer({
      id: 'corridor-nodes-3d',
      type: 'fill-extrusion',
      source: 'corridors-3d',
      filter: ['==', ['get', 'shape'], 'point'],
      layout: { visibility: 'none' },
      paint: {
        'fill-extrusion-color': '#f59e0b',
        'fill-extrusion-base': ['get', 'base_m'],
        'fill-extrusion-height': ['get', 'height_m'],
        'fill-extrusion-opacity': 0.72,
      },
    });

    map.addLayer({
      id: 'corridor-points',
      type: 'circle',
      source: 'corridors',
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 4.5,
        'circle-color': '#f59e0b',
        'circle-stroke-width': 1.5,
        'circle-stroke-color': ODT.getTheme() === 'dark' ? '#141824' : '#fff',
        'circle-opacity': 0.78,
      },
    });

    corridorLayerAdded = true;
  }

  function addWaypointLabelMarkers() {
    const map = ODT.MapManager.getMap();
    if (!map) return;

    waypointLabelMarkers.forEach((marker) => marker.remove());
    waypointLabelMarkers = [];

    for (const wp of waypointData) {
      const el = document.createElement('div');
      el.className = 'waypoint-name-label';
      el.textContent = wp.name;

      const marker = new maplibregl.Marker({
        element: el,
        anchor: 'top',
        offset: [0, 10],
      })
        .setLngLat([wp.lon, wp.lat])
        .addTo(map);

      waypointLabelMarkers.push(marker);
    }
  }

  function metersToLat(meters) {
    return meters / 111320;
  }

  function metersToLon(meters, lat) {
    const scale = Math.cos((lat * Math.PI) / 180);
    return meters / (111320 * Math.max(Math.abs(scale), 0.2));
  }

  function projectLocalMeters(from, to) {
    const midLat = (from.lat + to.lat) / 2;
    return {
      dx: (to.lon - from.lon) * 111320 * Math.cos((midLat * Math.PI) / 180),
      dy: (to.lat - from.lat) * 111320,
      midLat,
    };
  }

  function pointFromStart(start, dx, dy, midLat) {
    return [
      start.lon + metersToLon(dx, midLat),
      start.lat + metersToLat(dy),
    ];
  }

  function buildRibbonPolygon(start, end, halfWidthM) {
    const { dx, dy, midLat } = projectLocalMeters(start, end);
    const length = Math.hypot(dx, dy);
    if (length < 1) return null;

    const nx = dx / length;
    const ny = dy / length;
    const px = -ny * halfWidthM;
    const py = nx * halfWidthM;
    const polygon = [];

    for (let i = 0; i <= CORRIDOR_CAP_SEGMENTS; i += 1) {
      const theta = Math.PI / 2 - (Math.PI * i) / CORRIDOR_CAP_SEGMENTS;
      const along = -Math.cos(theta) * halfWidthM;
      const across = Math.sin(theta) * halfWidthM;
      polygon.push(pointFromSegmentBasis(start, nx, ny, px / halfWidthM, py / halfWidthM, along, across, midLat));
    }

    for (let i = 0; i <= CORRIDOR_CAP_SEGMENTS; i += 1) {
      const theta = -Math.PI / 2 + (Math.PI * i) / CORRIDOR_CAP_SEGMENTS;
      const along = Math.cos(theta) * halfWidthM;
      const across = Math.sin(theta) * halfWidthM;
      polygon.push(pointFromSegmentBasis(end, nx, ny, px / halfWidthM, py / halfWidthM, along, across, midLat));
    }

    polygon.push(polygon[0]);
    return polygon;
  }

  function pointFromSegmentBasis(center, nx, ny, px, py, along, across, midLat) {
    const dx = (nx * along) + (px * across);
    const dy = (ny * along) + (py * across);
    return pointFromStart(center, dx, dy, midLat);
  }

  function projectPointToLocal(point, refLon, refLat) {
    const scale = Math.cos((refLat * Math.PI) / 180);
    return {
      x: (point.lon - refLon) * 111320 * Math.max(Math.abs(scale), 0.2),
      y: (point.lat - refLat) * 111320,
    };
  }

  function projectPointFromLocal(point, refLon, refLat) {
    return [
      refLon + metersToLon(point.x, refLat),
      refLat + metersToLat(point.y),
    ];
  }

  function getSegmentNormal(from, to) {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy);
    if (length < 1e-6) return null;
    return {
      x: -dy / length,
      y: dx / length,
    };
  }

  function getRibbonOffset(localPoints, index, halfWidthM) {
    const prevNormal =
      index > 0 ? getSegmentNormal(localPoints[index - 1], localPoints[index]) : null;
    const nextNormal =
      index < localPoints.length - 1
        ? getSegmentNormal(localPoints[index], localPoints[index + 1])
        : null;

    if (!prevNormal && !nextNormal) {
      return { x: 0, y: halfWidthM };
    }
    if (!prevNormal) {
      return { x: nextNormal.x * halfWidthM, y: nextNormal.y * halfWidthM };
    }
    if (!nextNormal) {
      return { x: prevNormal.x * halfWidthM, y: prevNormal.y * halfWidthM };
    }

    const sumX = prevNormal.x + nextNormal.x;
    const sumY = prevNormal.y + nextNormal.y;
    const sumLength = Math.hypot(sumX, sumY);
    if (sumLength < 1e-6) {
      return { x: nextNormal.x * halfWidthM, y: nextNormal.y * halfWidthM };
    }

    const avgX = sumX / sumLength;
    const avgY = sumY / sumLength;
    const dot = Math.abs((avgX * nextNormal.x) + (avgY * nextNormal.y));
    const scale = halfWidthM / Math.max(dot, 0.35);
    const limitedScale = Math.min(scale, halfWidthM * 2.2);
    return {
      x: avgX * limitedScale,
      y: avgY * limitedScale,
    };
  }

  function buildRibbonPolygonFromPath(points, halfWidthM) {
    if (!Array.isArray(points) || points.length < 2) return null;

    const refLat =
      points.reduce((sum, point) => sum + point.lat, 0) / Math.max(points.length, 1);
    const refLon = points[0].lon;
    const localPoints = points.map((point) => projectPointToLocal(point, refLon, refLat));
    const leftSide = [];
    const rightSide = [];

    for (let i = 0; i < localPoints.length; i += 1) {
      const offset = getRibbonOffset(localPoints, i, halfWidthM);
      leftSide.push(
        projectPointFromLocal(
          {
            x: localPoints[i].x + offset.x,
            y: localPoints[i].y + offset.y,
          },
          refLon,
          refLat
        )
      );
      rightSide.push(
        projectPointFromLocal(
          {
            x: localPoints[i].x - offset.x,
            y: localPoints[i].y - offset.y,
          },
          refLon,
          refLat
        )
      );
    }

    const polygon = [...leftSide, ...rightSide.reverse()];
    if (polygon.length < 4) return null;
    polygon.push(leftSide[0]);
    return polygon;
  }

  function buildCorridorDashFeatures(from, to, type) {
    const { dx, dy, midLat } = projectLocalMeters(from, to);
    const length = Math.hypot(dx, dy);
    if (length < 1) return [];

    const nx = dx / length;
    const ny = dy / length;
    const features = [];
    // Keep corridor extrusion at a uniform absolute altitude so terrain does not
    // create per-segment stepping artifacts in pitched 3D views.
    const baseM = CORRIDOR_ALT_M;
    const topM = CORRIDOR_TOP_M;

    for (let offset = 0; offset < length; offset += CORRIDOR_DASH_M + CORRIDOR_GAP_M) {
      const segStart = offset;
      const segEnd = Math.min(length, offset + CORRIDOR_DASH_M);
      if (segEnd - segStart < 12) continue;
      const start = {
        lon: from.lon + metersToLon(nx * segStart, midLat),
        lat: from.lat + metersToLat(ny * segStart),
      };
      const end = {
        lon: from.lon + metersToLon(nx * segEnd, midLat),
        lat: from.lat + metersToLat(ny * segEnd),
      };
      const polygon = buildRibbonPolygon(start, end, CORRIDOR_HALF_WIDTH_M);
      if (!polygon) continue;
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [polygon],
        },
        properties: {
          shape: 'dash',
          type,
          base_m: baseM,
          height_m: topM,
        },
      });
    }
    return features;
  }

  function buildCorridorPointFeature(point) {
    const baseM = CORRIDOR_ALT_M;
    const topM = CORRIDOR_POINT_TOP_M;
    return buildElevatedSquareFeature(
      point,
      CORRIDOR_POINT_SIZE_M,
      'point',
      'corridor-node',
      baseM,
      topM
    );
  }

  function buildElevatedSquareFeature(point, sizeM, shape, type, baseM, heightM) {
    const sizeLat = metersToLat(sizeM);
    const sizeLon = metersToLon(sizeM, point.lat);
    return {
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [point.lon - sizeLon, point.lat - sizeLat],
          [point.lon + sizeLon, point.lat - sizeLat],
          [point.lon + sizeLon, point.lat + sizeLat],
          [point.lon - sizeLon, point.lat + sizeLat],
          [point.lon - sizeLon, point.lat - sizeLat],
        ]],
      },
      properties: {
        shape,
        type,
        base_m: baseM,
        height_m: heightM,
      },
    };
  }

  function getDefaultRouteAltitude() {
    return parseFloat(document.getElementById('settings-altitude')?.value) || 300;
  }

  function getDefaultFreeWaypointAltitude() {
    return FREE_WAYPOINT_DEFAULT_ALT_M;
  }

  async function fetchGroundElevationSample(lon, lat) {
    const query = new URLSearchParams({
      lon: String(lon),
      lat: String(lat),
    });
    return ODT.api(`/api/elevation?${query.toString()}`);
  }

  function parseGroundElevationM(value) {
    if (value == null || value === '') {
      return null;
    }
    const numericValue = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(numericValue) ? numericValue : null;
  }

  async function refreshFreeWaypointGroundSample(wp) {
    if (!wp) {
      return { available: false, ground_m: null };
    }

    const requestToken = Symbol('free-ground');
    wp.__groundRequestToken = requestToken;

    try {
      const sample = await fetchGroundElevationSample(wp.lon, wp.lat);
      if (wp.__groundRequestToken !== requestToken) {
        return null;
      }
      const groundM = parseGroundElevationM(sample?.ground_m);
      wp.ground_available = !!sample?.available && groundM !== null;
      wp.ground_m = groundM;
      return {
        available: wp.ground_available,
        ground_m: wp.ground_m,
      };
    } catch (_) {
      if (wp.__groundRequestToken !== requestToken) {
        return null;
      }
      wp.ground_available = false;
      wp.ground_m = null;
      return {
        available: false,
        ground_m: null,
      };
    }
  }

  function createRouteRenderPoint(localPoint, refLon, refLat, altitudeM) {
    const [lon, lat] = projectPointFromLocal(localPoint, refLon, refLat);
    return {
      lon,
      lat,
      alt_m: altitudeM,
      ground_m: 0,
    };
  }

  function pushUniqueRoutePoint(points, point) {
    const last = points[points.length - 1];
    if (
      last &&
      Math.abs((last.lon || 0) - (point.lon || 0)) < 1e-7 &&
      Math.abs((last.lat || 0) - (point.lat || 0)) < 1e-7
    ) {
      return;
    }
    points.push(point);
  }

  function buildRoundedRoutePoints(points, radiusM = ROUTE_TURN_RADIUS_M) {
    if (!Array.isArray(points) || points.length < 3 || radiusM <= 0) {
      return points || [];
    }

    const routeAltM = Number(points[0]?.alt_m) || getDefaultRouteAltitude();
    const refLat =
      points.reduce((sum, point) => sum + (Number(point.lat) || 0), 0) /
      Math.max(points.length, 1);
    const refLon = Number(points[0]?.lon) || 0;
    const localPoints = points.map((point) => projectPointToLocal(point, refLon, refLat));
    const rounded = [
      {
        lon: Number(points[0].lon) || 0,
        lat: Number(points[0].lat) || 0,
        alt_m: routeAltM,
        ground_m: 0,
      },
    ];

    for (let i = 1; i < localPoints.length - 1; i += 1) {
      const prev = localPoints[i - 1];
      const curr = localPoints[i];
      const next = localPoints[i + 1];
      const inVec = { x: prev.x - curr.x, y: prev.y - curr.y };
      const outVec = { x: next.x - curr.x, y: next.y - curr.y };
      const inLen = Math.hypot(inVec.x, inVec.y);
      const outLen = Math.hypot(outVec.x, outVec.y);

      if (inLen < 1 || outLen < 1) {
        pushUniqueRoutePoint(
          rounded,
          createRouteRenderPoint(curr, refLon, refLat, routeAltM)
        );
        continue;
      }

      const inUnit = { x: inVec.x / inLen, y: inVec.y / inLen };
      const outUnit = { x: outVec.x / outLen, y: outVec.y / outLen };
      const dot = Math.max(-1, Math.min(1, (inUnit.x * outUnit.x) + (inUnit.y * outUnit.y)));
      const angle = Math.acos(dot);

      if (angle >= Math.PI - 0.12 || angle <= 0.12) {
        pushUniqueRoutePoint(
          rounded,
          createRouteRenderPoint(curr, refLon, refLat, routeAltM)
        );
        continue;
      }

      const tangentDistanceRaw = radiusM / Math.tan(angle / 2);
      const tangentDistanceLimit = Math.min(inLen, outLen) * 0.45;
      const tangentDistance = Math.min(tangentDistanceRaw, tangentDistanceLimit);

      if (!Number.isFinite(tangentDistance) || tangentDistance <= 1) {
        pushUniqueRoutePoint(
          rounded,
          createRouteRenderPoint(curr, refLon, refLat, routeAltM)
        );
        continue;
      }

      const effectiveRadius = tangentDistance * Math.tan(angle / 2);
      const bisectorVec = { x: inUnit.x + outUnit.x, y: inUnit.y + outUnit.y };
      const bisectorLen = Math.hypot(bisectorVec.x, bisectorVec.y);

      if (bisectorLen < 1e-6) {
        pushUniqueRoutePoint(
          rounded,
          createRouteRenderPoint(curr, refLon, refLat, routeAltM)
        );
        continue;
      }

      const bisectorUnit = {
        x: bisectorVec.x / bisectorLen,
        y: bisectorVec.y / bisectorLen,
      };
      const centerDistance = effectiveRadius / Math.sin(angle / 2);
      const center = {
        x: curr.x + (bisectorUnit.x * centerDistance),
        y: curr.y + (bisectorUnit.y * centerDistance),
      };
      const tangentIn = {
        x: curr.x + (inUnit.x * tangentDistance),
        y: curr.y + (inUnit.y * tangentDistance),
      };
      const tangentOut = {
        x: curr.x + (outUnit.x * tangentDistance),
        y: curr.y + (outUnit.y * tangentDistance),
      };

      pushUniqueRoutePoint(
        rounded,
        createRouteRenderPoint(tangentIn, refLon, refLat, routeAltM)
      );

      const startAngle = Math.atan2(tangentIn.y - center.y, tangentIn.x - center.x);
      const endAngle = Math.atan2(tangentOut.y - center.y, tangentOut.x - center.x);
      const cross =
        ((tangentIn.x - center.x) * (tangentOut.y - center.y)) -
        ((tangentIn.y - center.y) * (tangentOut.x - center.x));

      let sweep = endAngle - startAngle;
      if (cross > 0 && sweep < 0) sweep += Math.PI * 2;
      if (cross < 0 && sweep > 0) sweep -= Math.PI * 2;

      const arcLength = Math.abs(sweep * effectiveRadius);
      const arcSteps = Math.max(4, Math.ceil(arcLength / ROUTE_ARC_STEP_M));

      for (let step = 1; step < arcSteps; step += 1) {
        const theta = startAngle + ((sweep * step) / arcSteps);
        pushUniqueRoutePoint(
          rounded,
          createRouteRenderPoint(
            {
              x: center.x + (Math.cos(theta) * effectiveRadius),
              y: center.y + (Math.sin(theta) * effectiveRadius),
            },
            refLon,
            refLat,
            routeAltM
          )
        );
      }

      pushUniqueRoutePoint(
        rounded,
        createRouteRenderPoint(tangentOut, refLon, refLat, routeAltM)
      );
    }

    pushUniqueRoutePoint(rounded, {
      lon: Number(points[points.length - 1].lon) || 0,
      lat: Number(points[points.length - 1].lat) || 0,
      alt_m: routeAltM,
      ground_m: 0,
    });

    return rounded;
  }

  function normalizeRoutePointList(points) {
    return (Array.isArray(points) ? points : []).map((point) => ({
      lon: Number(point.lon) || 0,
      lat: Number(point.lat) || 0,
      alt_m: Number(point.alt_m) || 0,
      ground_m: Number(point.ground_m) || 0,
    }));
  }

  function findNearestRoutePointIndex(points, target) {
    if (!Array.isArray(points) || !points.length || !target) return -1;
    let bestIndex = -1;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let i = 0; i < points.length; i += 1) {
      const dx = (Number(points[i].lon) || 0) - (Number(target.lon) || 0);
      const dy = (Number(points[i].lat) || 0) - (Number(target.lat) || 0);
      const distance = (dx * dx) + (dy * dy);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = i;
      }
    }
    return bestIndex;
  }

  function getPrimaryRouteWaypoints(data) {
    const rawWaypoints = Array.isArray(data?.waypoints) ? data.waypoints : [];
    const pathLength = Array.isArray(data?.path) ? data.path.length : 0;
    if (pathLength > 0 && rawWaypoints.length >= pathLength) {
      return rawWaypoints.slice(0, pathLength);
    }
    return rawWaypoints.filter((point) => point?.type !== 'arrival_touchdown');
  }

  function buildRouteRenderPoints(data) {
    const missionPoints = normalizeRoutePointList(data?.missionWaypoints);
    const originalPoints = missionPoints.length >= 2
      ? missionPoints
      : normalizeRoutePointList(data?.points);
    const waypoints = normalizeRoutePointList(getPrimaryRouteWaypoints(data));
    if (!data?.includeTurnArcs) {
      return originalPoints.length >= 3
        ? buildRoundedRoutePoints(originalPoints)
        : originalPoints;
    }
    if (originalPoints.length < 2) {
      return originalPoints;
    }
    if (waypoints.length < 4) {
      return originalPoints;
    }

    const firstTransition = waypoints[1];
    const lastTransition = waypoints[waypoints.length - 2];
    const firstTransitionIndex = findNearestRoutePointIndex(originalPoints, firstTransition);
    const lastTransitionIndex = findNearestRoutePointIndex(originalPoints, lastTransition);

    if (
      firstTransitionIndex <= 0 ||
      lastTransitionIndex <= firstTransitionIndex ||
      lastTransitionIndex >= originalPoints.length - 1
    ) {
      return originalPoints;
    }

    const departureArc = originalPoints.slice(0, firstTransitionIndex + 1);
    const arrivalArc = originalPoints.slice(lastTransitionIndex);
    const middleControlPoints = waypoints.slice(1, -1);
    const roundedMiddle = buildRoundedRoutePoints(middleControlPoints);

    if (roundedMiddle.length < 2) {
      return originalPoints;
    }

    const combined = [];
    departureArc.forEach((point) => pushUniqueRoutePoint(combined, point));
    roundedMiddle.forEach((point) => pushUniqueRoutePoint(combined, point));
    arrivalArc.forEach((point) => pushUniqueRoutePoint(combined, point));
    return combined;
  }

  function buildRoute3dFeatures(data) {
    const points = data?.points || [];
    if (points.length < 2) {
      return [];
    }

    const routeAltM = Number(points[0]?.alt_m) || getDefaultRouteAltitude();
    const features = [];
    const routePolygon = buildRibbonPolygonFromPath(points, ROUTE_HALF_WIDTH_M);
    if (routePolygon) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [routePolygon],
        },
        properties: {
          shape: 'route-ribbon',
          type: 'route',
          base_m: routeAltM,
          height_m: routeAltM + ROUTE_TOP_BUFFER_M,
        },
      });
    }

    for (const waypoint of data?.waypoints || []) {
      const baseM = routeAltM;
      const topM = routeAltM + ROUTE_NODE_TOP_BUFFER_M;
      features.push(
        buildElevatedSquareFeature(
          waypoint,
          ROUTE_NODE_SIZE_M,
          'route-node',
          'route-node',
          baseM,
          topM
        )
      );
    }

    return features;
  }

  function buildFreeMission3dFeatures(waypoints) {
    if (!Array.isArray(waypoints) || waypoints.length < 2) {
      return [];
    }

    const features = [];
    for (let i = 1; i < waypoints.length; i += 1) {
      const from = waypoints[i - 1];
      const to = waypoints[i];
      const polygon = buildRibbonPolygon(
        { lat: from.lat, lon: from.lon },
        { lat: to.lat, lon: to.lon },
        FREE_MISSION_HALF_WIDTH_M
      );
      if (!polygon) continue;

      const segmentAltM = ((Number(from.alt_m) || 0) + (Number(to.alt_m) || 0)) / 2;
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [polygon],
        },
        properties: {
          shape: 'free-route-ribbon',
          type: 'free-route',
          base_m: segmentAltM,
          height_m: segmentAltM + FREE_MISSION_TOP_BUFFER_M,
        },
      });
    }

    for (const waypoint of waypoints) {
      const baseM = Number(waypoint.alt_m) || getDefaultRouteAltitude();
      features.push(
        buildElevatedSquareFeature(
          waypoint,
          FREE_MISSION_NODE_SIZE_M,
          'free-route-node',
          'free-route-node',
          baseM,
          baseM + FREE_MISSION_NODE_TOP_BUFFER_M
        )
      );
    }

    return features;
  }

  function scheduleCorridorSceneUpdate() {
    if (corridorSceneHandle) return;
    corridorSceneHandle = window.requestAnimationFrame(() => {
      corridorSceneHandle = 0;
      updateCorridorScene();
    });
  }

  function updateCorridorScene() {
    const map = ODT.MapManager.getMap();
    if (!map || !corridorLayerAdded) return;
    const pitch = map.getPitch();
    const zoom = map.getZoom();
    const show3d =
      corridorVisiblePref &&
      pitch >= CORRIDOR_3D_PITCH_THRESHOLD &&
      zoom >= CORRIDOR_3D_ZOOM_THRESHOLD;
    const showWaypointLabels = corridorVisiblePref && zoom >= 11.2;

    setLayerVisibility(map, 'corridor-lines', corridorVisiblePref);
    setLayerVisibility(map, 'corridor-points', corridorVisiblePref);
    setLayerVisibility(map, 'corridor-ribbon-3d', show3d);
    setLayerVisibility(map, 'corridor-nodes-3d', show3d);
    setPaintValue(map, 'corridor-lines', 'line-opacity', show3d ? 0.42 : 0.56);
    setPaintValue(map, 'corridor-points', 'circle-opacity', show3d ? 0.62 : 0.84);
    setWaypointLabelVisibility(showWaypointLabels);
    updateRouteScene(map, pitch, zoom);
  }

  function setWaypointLabelVisibility(visible) {
    waypointLabelMarkers.forEach((marker) => {
      const el = marker.getElement();
      if (!el) return;
      el.style.display = visible ? '' : 'none';
    });
  }

  function updateRouteScene(map, pitch, zoom) {
    const show3d =
      !!routeData &&
      pitch >= ROUTE_3D_PITCH_THRESHOLD &&
      zoom >= ROUTE_3D_ZOOM_THRESHOLD;
    setLayerVisibility(map, 'route-line-shadow', !!routeData && !show3d);
    setLayerVisibility(map, 'route-line', !!routeData);
    setLayerVisibility(map, 'route-ribbon-3d', show3d);
    setLayerVisibility(map, 'route-nodes-3d', show3d);
    setPaintValue(map, 'route-line', 'line-opacity', show3d ? 0.72 : 0.96);
    updateFreeMissionScene(map, pitch, zoom);
  }

  function updateFreeMissionScene(map, pitch, zoom) {
    const show3d =
      freeWaypoints.length >= 2 &&
      pitch >= ROUTE_3D_PITCH_THRESHOLD &&
      zoom >= ROUTE_3D_ZOOM_THRESHOLD;
    const show2d = freeWaypoints.length >= 2 && !show3d;
    setLayerVisibility(map, 'free-mission-line', show2d);
    setLayerVisibility(map, 'free-mission-ribbon-3d', show3d);
    // Keep free-mission markers as the single waypoint reference. Showing
    // the 3D node blocks at the same time makes each waypoint appear twice.
    setLayerVisibility(map, 'free-mission-nodes-3d', false);
    setPaintValue(map, 'free-mission-line', 'line-opacity', show3d ? 0.64 : 0.94);
  }

  function setLayerVisibility(map, id, visible) {
    if (!map.getLayer(id)) return;
    const next = visible ? 'visible' : 'none';
    if (map.getLayoutProperty(id, 'visibility') === next) return;
    map.setLayoutProperty(id, 'visibility', next);
  }

  function setPaintValue(map, id, prop, value) {
    if (!map.getLayer(id)) return;
    const current = map.getPaintProperty(id, prop);
    if (current === value) return;
    map.setPaintProperty(id, prop, value);
  }

  function setMode(newMode) {
    mode = newMode;
    if (mode !== 'route') {
      routeMapPickEnabled = false;
    }
    document.querySelectorAll('.mode-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });
    document.getElementById('route-mode').style.display = mode === 'route' ? '' : 'none';
    document.getElementById('free-mode').style.display = mode === 'free' ? '' : 'none';

    if (mode === 'route') {
      clearFreeWaypoints();
    } else {
      clearRouteDisplay();
    }
    updateMapPickUI();
  }

  async function computeRoute() {
    const start = document.getElementById('departure-select').value;
    const end = document.getElementById('arrival-select').value;
    if (!start || !end) {
      ODT.OperatorLog?.warn(
        ODT.t('log_route_incomplete_title'),
        ODT.t('log_route_incomplete_message')
      );
      return;
    }
    if (start === end) {
      ODT.OperatorLog?.warn(
        ODT.t('log_route_same_title'),
        ODT.t('log_route_same_message')
      );
      return;
    }

    try {
      routeData = await ODT.postJSON('/api/route', {
        start,
        end,
        include_arcs: true,
      });
      displayRoute(routeData);
      ODT.OperatorLog?.success(
        ODT.t('log_route_computed_title'),
        ODT.t('log_route_computed_message', {
          start,
          end,
          distance: ODT.formatDist(routeData.distance_km),
        })
      );
      await generateMissionIcd({ logSuccess: false, warnOnMissing: false });
    } catch (e) {
      console.error('Route computation failed:', e);
      ODT.OperatorLog?.error(
        ODT.t('log_route_compute_failed_title'),
        ODT.humanizeError(e, ODT.t('log_route_compute_failed_message'))
      );
    }
  }

  function displayRoute(data) {
    const map = ODT.MapManager.getMap();
    if (!map) return;
    invalidateMissionIcdPreview();
    const renderedRoute = {
      ...data,
      points: buildRouteRenderPoints(data),
    };

    // Route info
    const infoEl = document.getElementById('route-info');
    document.getElementById('route-distance').textContent = ODT.formatDist(data.distance_km);
    document.getElementById('route-waypoint-count').textContent = data.path.length;
    document.getElementById('route-path').textContent = data.path.join(' -> ');
    document.getElementById('route-path').title = data.path.join(' -> ');
    infoEl.classList.add('visible');

    // Route line on map
    const coords = renderedRoute.points.map((p) => [p.lon, p.lat]);
    const route3dFeatures = buildRoute3dFeatures(renderedRoute);

    if (map.getSource('route')) {
      map.getSource('route').setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: coords },
      });
      if (map.getSource('route-3d')) {
        map.getSource('route-3d').setData({
          type: 'FeatureCollection',
          features: route3dFeatures,
        });
      }
    } else {
      map.addSource('route', {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: coords },
        },
      });

      map.addSource('route-3d', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: route3dFeatures,
        },
      });

      map.addLayer({
        id: 'route-line-shadow',
        type: 'line',
        source: 'route',
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
        paint: {
          'line-color': 'rgba(96, 165, 250, 0.22)',
          'line-width': 10,
          'line-blur': 5,
        },
      });

      map.addLayer({
        id: 'route-line',
        type: 'line',
        source: 'route',
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
        paint: {
          'line-color': '#60a5fa',
          'line-width': 4.2,
          'line-opacity': 1,
        },
      });

      map.addLayer({
        id: 'route-ribbon-3d',
        type: 'fill-extrusion',
        source: 'route-3d',
        filter: ['==', ['get', 'shape'], 'route-ribbon'],
        layout: { visibility: 'none' },
        paint: {
          'fill-extrusion-color': '#60a5fa',
          'fill-extrusion-base': ['get', 'base_m'],
          'fill-extrusion-height': ['get', 'height_m'],
          'fill-extrusion-opacity': 0.78,
        },
      });

      map.addLayer({
        id: 'route-nodes-3d',
        type: 'fill-extrusion',
        source: 'route-3d',
        filter: ['==', ['get', 'shape'], 'route-node'],
        layout: { visibility: 'none' },
        paint: {
          'fill-extrusion-color': '#93c5fd',
          'fill-extrusion-base': ['get', 'base_m'],
          'fill-extrusion-height': ['get', 'height_m'],
          'fill-extrusion-opacity': 0.82,
        },
      });

      routeLayerAdded = true;
    }

    // Fit bounds
    if (coords.length >= 2) {
      const bounds = coords.reduce(
        (b, c) => b.extend(c),
        new maplibregl.LngLatBounds(coords[0], coords[0])
      );
      map.fitBounds(bounds, { padding: 80, duration: 1000 });
    }

    // Mission table
    updateMissionTable(data.waypoints || []);

    // Altitude profile
    if (data.waypoints && data.waypoints.length >= 2) {
      ODT.AltitudeProfile.show(data.waypoints);
    }

    scheduleCorridorSceneUpdate();
  }

  function clearRouteDisplay() {
    const map = ODT.MapManager.getMap();
    if (map && map.getLayer('route-line')) {
      map.removeLayer('route-line');
      map.removeLayer('route-line-shadow');
      if (map.getLayer('route-ribbon-3d')) map.removeLayer('route-ribbon-3d');
      if (map.getLayer('route-nodes-3d')) map.removeLayer('route-nodes-3d');
      map.removeSource('route');
      if (map.getSource('route-3d')) map.removeSource('route-3d');
      routeLayerAdded = false;
    }
    routeData = null;
    document.getElementById('route-info').classList.remove('visible');
    ODT.AltitudeProfile.hide();
    updateMissionTable([]);
    invalidateMissionIcdPreview();
  }

  function onMapClick(e) {
    if (ODT.Converter?.isMapPickActive?.()) return;
    if (mode !== 'free') return;
    const lngLat = e.lngLat;
    const defaultAlt = getDefaultFreeWaypointAltitude();

    const wp = {
      name: 'WP' + (freeWaypoints.length + 1),
      lat: lngLat.lat,
      lon: lngLat.lng,
      alt_m: defaultAlt,
      ground_m: null,
      ground_available: undefined,
      type: 'free',
    };
    freeWaypoints.push(wp);
    const marker = addFreeWaypointMarker(wp, freeWaypoints.length - 1);
    updateFreeMissionLine();
    updateMissionTable(freeWaypoints);
    ODT.AltitudeProfile.show(freeWaypoints);
    scheduleMissionIcdAutoRefresh();
    if (marker) {
      openFreeWaypointAltitudeEditor(freeWaypoints.length - 1, marker);
    }
  }

  function onMapRightClick(e) {
    if (ODT.Converter?.isMapPickActive?.()) return;
    if (mode !== 'free') return;
    const threshold = 0.0005;
    const idx = freeWaypoints.findIndex(
      (wp) => Math.abs(wp.lat - e.lngLat.lat) < threshold && Math.abs(wp.lon - e.lngLat.lng) < threshold
    );
    if (idx >= 0) {
      e.preventDefault();
      removeFreeWaypoint(idx);
    }
  }

  function getFreeWaypointInvalidAltitudeText() {
    if (ODT.I18n?.getLanguage() === 'ko') {
      return {
        title: '고도 입력 오류',
        message: '0 이상의 숫자 고도를 입력해야 합니다.',
      };
    }
    return {
      title: 'Invalid altitude',
      message: 'Enter a numeric altitude greater than or equal to 0.',
    };
  }

  function getFreeWaypointAltitudeUpdatedText(index, altitudeM, wp) {
    const name = wp?.name || `WP${index + 1}`;
    if (ODT.I18n?.getLanguage() === 'ko') {
      return {
        title: '경유점 고도 변경',
        message: `${name} 고도를 ${Math.round(altitudeM)} m로 설정했습니다.`,
      };
    }
    return {
      title: 'Waypoint altitude updated',
      message: `${name} altitude set to ${Math.round(altitudeM)} m.`,
    };
  }

  function getFreeWaypointRemovedText(index, wp) {
    const name = wp?.name || `WP${index + 1}`;
    if (ODT.I18n?.getLanguage() === 'ko') {
      return {
        title: '경유점 삭제',
        message: `${name}을(를) 자유미션에서 삭제했습니다.`,
      };
    }
    return {
      title: 'Waypoint removed',
      message: `${name} was removed from the free mission.`,
    };
  }

  function closeFreeWaypointAltitudeEditor() {
    freeAltitudePopup?.remove();
    freeAltitudePopup = null;
    freeAltitudePopupIndex = -1;
  }

  function buildFreeWaypointAltitudeEditorLabels(index, wp) {
    const name = wp?.name || `WP${index + 1}`;
    if (ODT.I18n?.getLanguage() === 'ko') {
      return {
        title: `${name} \uace0\ub3c4`,
        subtitle: '\ubbf8\ud130',
        demLabel: 'DEM',
        demLoading: 'DEM \uace0\ub3c4 \ubd88\ub7ec\uc624\ub294 \uc911...',
        demUnavailable: 'DEM \uace0\ub3c4 \uc5c6\uc74c',
        save: '\ud655\uc778',
        cancel: '\ucde8\uc18c',
      };
    }
    return {
      title: `${name} Altitude`,
      subtitle: 'meters',
      demLabel: 'DEM',
      demLoading: 'Loading DEM...',
      demUnavailable: 'DEM unavailable',
      save: 'Apply',
      cancel: 'Cancel',
    };
  }

  function getFreeWaypointGroundDisplayText(wp, labels) {
    if (wp?.ground_available === false) {
      return labels.demUnavailable;
    }
    const groundM = parseGroundElevationM(wp?.ground_m);
    if (groundM !== null) {
      return `${Math.round(groundM)} m`;
    }
    return labels.demLoading;
  }

  function getFreeWaypointAltitudeEditorLabels(index, wp) {
    const name = wp?.name || `WP${index + 1}`;
    if (ODT.I18n?.getLanguage() === 'ko') {
      return {
        title: `${name} 고도`,
        subtitle: '미터 단위',
        save: '확인',
        cancel: '취소',
      };
    }
    return {
      title: `${name} Altitude`,
      subtitle: 'meters',
      save: 'Apply',
      cancel: 'Cancel',
    };
  }

  function openFreeWaypointAltitudeEditor(index, marker) {
    const map = ODT.MapManager.getMap();
    const wp = freeWaypoints[index];
    if (!map || !marker || !wp) return;

    if (freeAltitudePopupIndex === index && freeAltitudePopup) {
      closeFreeWaypointAltitudeEditor();
      return;
    }

    closeFreeWaypointAltitudeEditor();

    const labels = buildFreeWaypointAltitudeEditorLabels(index, wp);
    const currentAlt = Number(wp.alt_m) || getDefaultFreeWaypointAltitude();

    const container = document.createElement('div');
    container.className = 'free-altitude-popup';
    container.addEventListener('click', (evt) => {
      evt.stopPropagation();
    });

    const header = document.createElement('div');
    header.className = 'free-altitude-popup-header';

    const title = document.createElement('div');
    title.className = 'free-altitude-popup-title';
    title.textContent = labels.title;

    const subtitle = document.createElement('div');
    subtitle.className = 'free-altitude-popup-subtitle';
    subtitle.textContent = labels.subtitle;

    const inputRow = document.createElement('div');
    inputRow.className = 'free-altitude-popup-input-row';

    const input = document.createElement('input');
    input.className = 'free-altitude-popup-input';
    input.type = 'number';
    input.min = '0';
    input.step = '10';
    input.inputMode = 'numeric';
    input.value = String(Math.round(currentAlt));

    const unit = document.createElement('span');
    unit.className = 'free-altitude-popup-unit';
    unit.textContent = 'm';

    const demRow = document.createElement('div');
    demRow.className = 'free-altitude-popup-dem';

    const demLabel = document.createElement('span');
    demLabel.className = 'free-altitude-popup-dem-label';
    demLabel.textContent = labels.demLabel;

    const demValue = document.createElement('strong');
    demValue.className = 'free-altitude-popup-dem-value';
    demValue.textContent = getFreeWaypointGroundDisplayText(wp, labels);
    demValue.classList.toggle(
      'is-loading',
      parseGroundElevationM(wp?.ground_m) === null && wp?.ground_available !== false
    );

    const actions = document.createElement('div');
    actions.className = 'free-altitude-popup-actions';

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'free-altitude-popup-btn is-primary';
    saveBtn.textContent = labels.save;

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'free-altitude-popup-btn';
    cancelBtn.textContent = labels.cancel;

    const commit = () => {
      const altitudeM = Number(input.value);
      if (!Number.isFinite(altitudeM) || altitudeM < 0) {
        const invalid = getFreeWaypointInvalidAltitudeText();
        ODT.OperatorLog?.warn(invalid.title, invalid.message);
        input.focus();
        input.select();
        return;
      }

      wp.alt_m = altitudeM;
      updateMissionTable(freeWaypoints);
      ODT.AltitudeProfile.show(freeWaypoints);
      scheduleMissionIcdAutoRefresh();

      const updated = getFreeWaypointAltitudeUpdatedText(index, altitudeM, wp);
      ODT.OperatorLog?.info(updated.title, updated.message);
      closeFreeWaypointAltitudeEditor();
    };

    saveBtn.addEventListener('click', (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      commit();
    });
    cancelBtn.addEventListener('click', (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      closeFreeWaypointAltitudeEditor();
    });
    input.addEventListener('keydown', (evt) => {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        commit();
      } else if (evt.key === 'Escape') {
        evt.preventDefault();
        closeFreeWaypointAltitudeEditor();
      }
    });

    actions.appendChild(cancelBtn);
    actions.appendChild(saveBtn);
    header.appendChild(title);
    header.appendChild(subtitle);
    inputRow.appendChild(input);
    inputRow.appendChild(unit);
    demRow.appendChild(demLabel);
    demRow.appendChild(demValue);
    container.appendChild(header);
    container.appendChild(inputRow);
    container.appendChild(demRow);
    container.appendChild(actions);

    freeAltitudePopup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: true,
      offset: [0, -18],
      anchor: 'bottom',
      className: 'free-altitude-map-popup',
    })
      .setDOMContent(container)
      .setLngLat(marker.getLngLat())
      .addTo(map);

    freeAltitudePopupIndex = index;
    freeAltitudePopup.on('close', () => {
      freeAltitudePopup = null;
      freeAltitudePopupIndex = -1;
    });

    if (parseGroundElevationM(wp?.ground_m) === null && wp?.ground_available !== false) {
      refreshFreeWaypointGroundSample(wp).then((sample) => {
        if (!sample || freeAltitudePopupIndex !== index || freeAltitudePopup == null) {
          return;
        }
        demValue.textContent = getFreeWaypointGroundDisplayText(wp, labels);
        demValue.classList.toggle('is-loading', parseGroundElevationM(sample.ground_m) === null);
      });
    }

    window.setTimeout(() => {
      input.focus();
      input.select();
    }, 0);
  }

  function rebuildFreeWaypointMarkers() {
    closeFreeWaypointAltitudeEditor();
    freeMarkers.forEach((marker) => marker.remove());
    freeMarkers = [];

    freeWaypoints.forEach((wp, index) => {
      addFreeWaypointMarker(wp, index);
    });
  }

  function addFreeWaypointMarker(wp, index) {
    const map = ODT.MapManager.getMap();
    if (!map) return null;

    const el = document.createElement('div');
    const diamond = document.createElement('div');
    const inner = document.createElement('span');
    el.style.cssText = `
      width: 28px; height: 28px;
      display: flex; align-items: center; justify-content: center;
      cursor: grab;
    `;
    diamond.style.cssText = `
      width: 22px; height: 22px;
      background: #8b5cf6;
      border: 2px solid ${ODT.getTheme() === 'dark' ? '#141824' : '#fff'};
      border-radius: 3px;
      transform: rotate(45deg);
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      transition: transform 0.15s ease;
    `;
    inner.style.cssText = 'transform:rotate(-45deg);font-size:9px;font-weight:700;color:white';
    inner.textContent = index + 1;
    diamond.appendChild(inner);
    el.appendChild(diamond);

    const marker = new maplibregl.Marker({ element: el, draggable: true })
      .setLngLat([wp.lon, wp.lat])
      .addTo(map);

    marker.__suppressNextClick = false;
    marker.on('dragstart', () => {
      if (freeAltitudePopupIndex === index) {
        closeFreeWaypointAltitudeEditor();
      }
      marker.__suppressNextClick = true;
    });
    marker.on('dragend', () => {
      const pos = marker.getLngLat();
      freeWaypoints[index].lat = pos.lat;
      freeWaypoints[index].lon = pos.lng;
      freeWaypoints[index].ground_m = null;
      freeWaypoints[index].ground_available = undefined;
      updateFreeMissionLine();
      updateMissionTable(freeWaypoints);
      ODT.AltitudeProfile.show(freeWaypoints);
      scheduleMissionIcdAutoRefresh();
      refreshFreeWaypointGroundSample(freeWaypoints[index]);
    });

    el.addEventListener('click', (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      if (marker.__suppressNextClick) {
        marker.__suppressNextClick = false;
        return;
      }
      openFreeWaypointAltitudeEditor(index, marker);
    });

    el.addEventListener('contextmenu', (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      removeFreeWaypoint(index);
    });

    freeMarkers.push(marker);
    return marker;
  }

  function removeFreeWaypoint(index) {
    const removed = freeWaypoints[index];
    if (freeAltitudePopupIndex === index) {
      closeFreeWaypointAltitudeEditor();
    }
    freeWaypoints.splice(index, 1);
    rebuildFreeWaypointMarkers();
    updateFreeMissionLine();
    updateMissionTable(freeWaypoints);
    ODT.AltitudeProfile.show(freeWaypoints);
    scheduleMissionIcdAutoRefresh();

    const removedLog = getFreeWaypointRemovedText(index, removed);
    ODT.OperatorLog?.info(removedLog.title, removedLog.message);
  }

  function updateFreeMissionLine() {
    const map = ODT.MapManager.getMap();
    if (!map) return;

    const coords = freeWaypoints.map((wp) => [wp.lon, wp.lat]);
    const freeMission3dFeatures = buildFreeMission3dFeatures(freeWaypoints);

    if (coords.length < 2) {
      if (map.getLayer('free-mission-line')) {
        map.removeLayer('free-mission-line');
      }
      if (map.getLayer('free-mission-ribbon-3d')) {
        map.removeLayer('free-mission-ribbon-3d');
      }
      if (map.getLayer('free-mission-nodes-3d')) {
        map.removeLayer('free-mission-nodes-3d');
      }
      if (map.getSource('free-mission')) {
        map.removeSource('free-mission');
      }
      if (map.getSource('free-mission-3d')) {
        map.removeSource('free-mission-3d');
      }
      return;
    }

    if (map.getSource('free-mission')) {
      map.getSource('free-mission').setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: coords },
      });
      if (map.getSource('free-mission-3d')) {
        map.getSource('free-mission-3d').setData({
          type: 'FeatureCollection',
          features: freeMission3dFeatures,
        });
      }
    } else if (coords.length >= 2) {
      map.addSource('free-mission', {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: coords },
        },
      });
      map.addSource('free-mission-3d', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: freeMission3dFeatures,
        },
      });
      map.addLayer({
        id: 'free-mission-line',
        type: 'line',
        source: 'free-mission',
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
        paint: {
          'line-color': '#8b5cf6',
          'line-width': 2.5,
          'line-dasharray': [6, 3],
          'line-opacity': 0.94,
        },
      });
      map.addLayer({
        id: 'free-mission-ribbon-3d',
        type: 'fill-extrusion',
        source: 'free-mission-3d',
        filter: ['==', ['get', 'shape'], 'free-route-ribbon'],
        layout: { visibility: 'none' },
        paint: {
          'fill-extrusion-color': '#8b5cf6',
          'fill-extrusion-base': ['get', 'base_m'],
          'fill-extrusion-height': ['get', 'height_m'],
          'fill-extrusion-opacity': 0.78,
        },
      });
      map.addLayer({
        id: 'free-mission-nodes-3d',
        type: 'fill-extrusion',
        source: 'free-mission-3d',
        filter: ['==', ['get', 'shape'], 'free-route-node'],
        layout: { visibility: 'none' },
        paint: {
          'fill-extrusion-color': '#a78bfa',
          'fill-extrusion-base': ['get', 'base_m'],
          'fill-extrusion-height': ['get', 'height_m'],
          'fill-extrusion-opacity': 0.86,
        },
      });
    }

    scheduleCorridorSceneUpdate();
  }

  function clearFreeWaypoints() {
    closeFreeWaypointAltitudeEditor();
    freeMarkers.forEach((m) => m.remove());
    freeMarkers = [];
    freeWaypoints = [];
    invalidateMissionIcdPreview();
    const map = ODT.MapManager.getMap();
    if (map && map.getLayer('free-mission-line')) {
      map.removeLayer('free-mission-line');
      if (map.getLayer('free-mission-ribbon-3d')) map.removeLayer('free-mission-ribbon-3d');
      if (map.getLayer('free-mission-nodes-3d')) map.removeLayer('free-mission-nodes-3d');
      map.removeSource('free-mission');
      if (map.getSource('free-mission-3d')) map.removeSource('free-mission-3d');
    }
    updateMissionTable([]);
    ODT.AltitudeProfile.hide();
  }

  function updateMissionTable(wps) {
    const wrap = document.getElementById('mission-table-wrap');
    const tbody = document.getElementById('mission-table-body');
    if (!wrap || !tbody) return;

    if (!wps || wps.length === 0) {
      wrap.style.display = 'none';
      tbody.innerHTML = '';
      return;
    }

    wrap.style.display = '';
    tbody.innerHTML = '';
    wps.forEach((wp, i) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td>${wp.name || 'WP' + (i + 1)}</td>
        <td>${(wp.lat || 0).toFixed(5)}</td>
        <td>${(wp.lon || 0).toFixed(5)}</td>
        <td>${(wp.alt_m || 0).toFixed(0)}</td>
      `;
      tr.addEventListener('click', () => {
        ODT.MapManager.flyTo([wp.lon, wp.lat], 15);
      });
      tbody.appendChild(tr);
    });
  }

  function onAltitudeChange(index, newAlt) {
    if (mode === 'free' && freeWaypoints[index]) {
      freeWaypoints[index].alt_m = newAlt;
      updateMissionTable(freeWaypoints);
      updateFreeMissionLine();
      scheduleMissionIcdAutoRefresh();
    }
  }

  function getExecutionWaypoints() {
    if (mode === 'route' && routeData) {
      if (Array.isArray(routeData.points) && routeData.points.length > 1) {
        const departureGroundM = Number(routeData?.departureTakeoff?.ground_m);
        const arrivalGroundM = Number(routeData?.arrivalTouchdown?.alt_m);
        return routeData.points.map((point, index) => {
          const normalizedAlt = Number(point?.alt_m);
          let altM = Number.isFinite(normalizedAlt) ? normalizedAlt : 300;
          if (index === 0 && Number.isFinite(departureGroundM)) {
            altM = departureGroundM;
          }
          if (index === routeData.points.length - 1 && Number.isFinite(arrivalGroundM)) {
            altM = arrivalGroundM;
          }
          return {
            name: point?.name || `RT${index + 1}`,
            lat: Number(point?.lat) || 0,
            lon: Number(point?.lon) || 0,
            alt_m: altM,
            ground_m: Number(point?.ground_m) || 0,
            type: point?.type || 'route_point',
          };
        });
      }
      if (Array.isArray(routeData.missionWaypoints) && routeData.missionWaypoints.length) {
        return routeData.missionWaypoints;
      }
      return routeData.waypoints;
    }
    return freeWaypoints;
  }

  function resolveMissionWaypointAltitude(wp) {
    const altitudeM = Number(wp?.alt_m);
    return Number.isFinite(altitudeM) ? altitudeM : 300;
  }

  async function executeMission() {
    const payload = buildMissionIcdPayload();
    if (!payload) {
      ODT.OperatorLog?.warn(
        ODT.t('log_mission_not_ready_title'),
        ODT.t('log_mission_not_ready_message')
      );
      return;
    }
    if (!ODT.Simulator?.startMission) {
      ODT.OperatorLog?.error(
        ODT.t('log_mission_start_failed_title'),
        'Simulation service is not available in the browser.'
      );
      return;
    }
    try {
      await ODT.Simulator.startMission(payload, {
        replayStepS: getSimulationReplayStep(),
        playbackSpeedX: getSimulationPlaybackSpeed(),
      });
    } catch (_) {}
  }

  function setCorridorVisibility(visible) {
    const map = ODT.MapManager.getMap();
    if (!map) return;
    corridorVisiblePref = !!visible;
    scheduleCorridorSceneUpdate();
  }

  function setBuildingVisibility(visible) {
    if (ODT.MapManager && ODT.MapManager.setBuildingsVisible) {
      ODT.MapManager.setBuildingsVisible(visible);
      return;
    }
    const map = ODT.MapManager.getMap();
    if (!map) return;
    for (const id of ['building', 'building-3d']) {
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
      }
    }
  }

  function getSimulationFleetMessages() {
    if (ODT.I18n?.getLanguage?.() === 'ko') {
      return {
        title: 'UAM 임무',
        replayTitle: '재생 상태',
        count: 'UAM 대수',
        editing: '편집 중',
        aircraftId: 'Aircraft ID',
        vehicleName: 'Vehicle',
        missionMode: '임무 모드',
        departure: '출발',
        arrival: '도착',
        compute: '경로 계산',
        editMap: '지도 편집',
        empty: 'UAM을 1대 이상 설정하세요.',
        routeMode: 'Route',
        freeMode: 'Free',
        routePending: (departure, arrival) => `경로 대기 · ${departure || '--'} -> ${arrival || '--'}`,
        routeReady: (departure, arrival) => `${departure || '--'} -> ${arrival || '--'}`,
        freePending: '자유 임무 대기',
        freeReady: (count) => `자유 임무 · WP ${count}개`,
        fleetCount: (count) => `기체 ${count}대`,
        missingMission: (index) => `UAM ${index + 1} 임무가 아직 설정되지 않았습니다.`,
      };
    }
    return {
      title: 'UAM Missions',
      replayTitle: 'Replay Status',
      count: 'UAM Count',
      editing: 'Editing',
      aircraftId: 'Aircraft ID',
      vehicleName: 'Vehicle',
      missionMode: 'Mission Mode',
      departure: 'Departure',
      arrival: 'Arrival',
      compute: 'Compute',
      editMap: 'Edit on Map',
      empty: 'Set at least one UAM.',
      routeMode: 'Route',
      freeMode: 'Free',
      routePending: (departure, arrival) => `Route pending · ${departure || '--'} -> ${arrival || '--'}`,
      routeReady: (departure, arrival) => `${departure || '--'} -> ${arrival || '--'}`,
      freePending: 'Free mission pending',
      freeReady: (count) => `Free mission · ${count} WP`,
      fleetCount: (count) => `${count} aircraft`,
      missingMission: (index) => `Mission is missing for UAM ${index + 1}.`,
    };
  }

  function sanitizeMissionWaypoint(wp, index) {
    const altM = Number(wp?.alt_m);
    return {
      name: String(wp?.name || `WP${index + 1}`),
      lat: Number(wp?.lat) || 0,
      lon: Number(wp?.lon) || 0,
      alt_m: Number.isFinite(altM) ? altM : getDefaultFreeWaypointAltitude(),
      ground_m: parseGroundElevationM(wp?.ground_m),
      ground_available: typeof wp?.ground_available === 'boolean' ? wp.ground_available : undefined,
      type: String(wp?.type || 'free'),
    };
  }

  function createSimulationFleetEntry(index = simulationFleet.length) {
    simulationFleetSeed += 1;
    return {
      id: `fleet-${Date.now()}-${simulationFleetSeed}`,
      aircraftId: `UAM${String(index + 1).padStart(4, '0')}`,
      vehicleName: `Drone${index + 1}`,
      mode: 'route',
      departureName: '',
      arrivalName: '',
      routeData: null,
      freeWaypoints: [],
    };
  }

  function ensureSimulationFleet() {
    if (!simulationFleet.length) {
      simulationFleet = [createSimulationFleetEntry(0)];
    }
    if (activeMissionIndex >= simulationFleet.length) {
      activeMissionIndex = Math.max(simulationFleet.length - 1, 0);
    }
  }

  function sanitizeSimulationFleetEntry(entry, index) {
    const fallback = createSimulationFleetEntry(index);
    return {
      id: entry?.id || fallback.id,
      aircraftId: String(entry?.aircraftId || fallback.aircraftId).trim() || fallback.aircraftId,
      vehicleName: String(entry?.vehicleName || entry?.vehicle_name || fallback.vehicleName).trim() || fallback.vehicleName,
      mode: entry?.mode === 'free' ? 'free' : 'route',
      departureName: String(entry?.departureName || '').trim(),
      arrivalName: String(entry?.arrivalName || '').trim(),
      routeData: entry?.routeData && typeof entry.routeData === 'object' ? entry.routeData : null,
      freeWaypoints: Array.isArray(entry?.freeWaypoints)
        ? entry.freeWaypoints.map((wp, wpIndex) => sanitizeMissionWaypoint(wp, wpIndex))
        : [],
    };
  }

  function getActiveMissionEntry() {
    ensureSimulationFleet();
    simulationFleet = simulationFleet.map((entry, index) => sanitizeSimulationFleetEntry(entry, index));
    return simulationFleet[activeMissionIndex] || simulationFleet[0] || null;
  }

  function getMissionDisplayLabel(entry, index) {
    return entry?.aircraftId?.trim() || `UAM ${index + 1}`;
  }

  function getMissionSummaryText(entry) {
    const messages = getSimulationFleetMessages();
    if (!entry) return messages.empty;
    if (entry.mode === 'free') {
      return entry.freeWaypoints?.length
        ? messages.freeReady(entry.freeWaypoints.length)
        : messages.freePending;
    }
    if (entry.routeData) {
      const departure = entry.departureName || entry.routeData.path?.[0] || '';
      const arrival = entry.arrivalName || entry.routeData.path?.[entry.routeData.path.length - 1] || '';
      return messages.routeReady(departure, arrival);
    }
    return messages.routePending(entry.departureName, entry.arrivalName);
  }

  function updateMissionEditorHeading() {
    const messages = getSimulationFleetMessages();
    const activeEntry = getActiveMissionEntry();
    const labelEl = document.getElementById('mission-fleet-active-label');
    const fleetTitleEl = document.querySelector('#mission-fleet-card .mission-sim-title');
    const replayTitleEl = document.querySelector('#mission-sim-card .mission-sim-title');
    if (labelEl) {
      labelEl.textContent = `${getMissionDisplayLabel(activeEntry, activeMissionIndex)} (${activeMissionIndex + 1})`;
    }
    if (fleetTitleEl) fleetTitleEl.textContent = messages.title;
    if (replayTitleEl) replayTitleEl.textContent = messages.replayTitle;
  }

  function activateMissionEditor(index, options = {}) {
    if (index < 0 || index >= simulationFleet.length) return;
    routeMapPickEnabled = false;
    activeMissionIndex = index;
    loadActiveMissionIntoEditor({
      preserveViewport: options.preserveViewport !== false,
      suppressPreviewInvalidate: options.suppressPreviewInvalidate !== false,
    });
  }

  function buildVertiportOptionElements(selectEl, selectedValue) {
    if (!selectEl) return;
    const current = String(selectedValue || '');
    selectEl.innerHTML = '';
    const blank = new Option(ODT.t?.('select_vertiport') || 'Select vertiport...', '');
    selectEl.appendChild(blank);
    [...vertiportData]
      .sort((a, b) => a.name.localeCompare(b.name))
      .forEach((vp) => {
        selectEl.appendChild(new Option(vp.name, vp.name));
      });
    selectEl.value = current;
  }

  function syncSimulationFleetCountInput() {
    const input = document.getElementById('mission-fleet-count');
    if (!input) return;
    input.value = String(simulationFleet.length || 1);
    input.title = getSimulationFleetMessages().count;
  }

  function setSimulationFleetCount(count) {
    const nextCount = Math.max(1, Math.min(MAX_SIMULATION_FLEET, Number(count) || 1));
    ensureSimulationFleet();
    while (simulationFleet.length < nextCount) {
      simulationFleet.push(createSimulationFleetEntry(simulationFleet.length));
    }
    if (simulationFleet.length > nextCount) {
      simulationFleet = simulationFleet.slice(0, nextCount);
    }
    if (activeMissionIndex >= simulationFleet.length) {
      activeMissionIndex = simulationFleet.length - 1;
    }
    syncSimulationFleetCountInput();
  }

  function syncSimulationFleetCountFromInput() {
    const input = document.getElementById('mission-fleet-count');
    setSimulationFleetCount(input?.value);
    renderSimulationFleet();
    loadActiveMissionIntoEditor({ preserveViewport: true, suppressPreviewInvalidate: true });
    scheduleMissionIcdAutoRefresh();
  }

  function getSimulationFleetPayload() {
    ensureSimulationFleet();
    simulationFleet = simulationFleet.map((entry, index) => sanitizeSimulationFleetEntry(entry, index));
    return simulationFleet.map((entry) => ({
      aircraftId: entry.aircraftId,
      vehicleName: entry.vehicleName,
    }));
  }

  function validateSimulationFleet() {
    const fleet = getSimulationFleetPayload();
    const seen = new Set();
    for (const entry of fleet) {
      const vehicleKey = String(entry.vehicleName || '').trim().toLowerCase();
      if (!vehicleKey) continue;
      if (seen.has(vehicleKey)) {
        return ODT.I18n?.getLanguage?.() === 'ko'
          ? 'Vehicle 이름은 중복될 수 없습니다.'
          : 'Vehicle names must be unique.';
      }
      seen.add(vehicleKey);
    }
    return '';
  }

  function updateSimulationFleetSummary() {
    const summaryEl = document.getElementById('mission-sim-fleet-count');
    if (summaryEl) {
      summaryEl.textContent = getSimulationFleetMessages().fleetCount(getSimulationFleetPayload().length);
    }
  }

  function renderSimulationFleet() {
    ensureSimulationFleet();
    simulationFleet = simulationFleet.map((entry, index) => sanitizeSimulationFleetEntry(entry, index));

    const messages = getSimulationFleetMessages();
    const listEl = document.getElementById('mission-fleet-list');

    updateMissionEditorHeading();
    syncSimulationFleetCountInput();
    if (!listEl) {
      updateSimulationFleetSummary();
      return;
    }

    listEl.innerHTML = '';
    if (!simulationFleet.length) {
      const empty = document.createElement('div');
      empty.className = 'mission-fleet-empty';
      empty.textContent = messages.empty;
      listEl.appendChild(empty);
      updateSimulationFleetSummary();
      return;
    }

    simulationFleet.forEach((entry, index) => {
      const row = document.createElement('div');
      row.className = 'mission-fleet-row';
      if (index === activeMissionIndex) {
        row.classList.add('is-active');
      }
      row.addEventListener('click', () => {
        if (index === activeMissionIndex) return;
        routeMapPickEnabled = false;
        activeMissionIndex = index;
        loadActiveMissionIntoEditor({ preserveViewport: true, suppressPreviewInvalidate: true });
      });

      const header = document.createElement('div');
      header.className = 'mission-fleet-row-header';
      const indexEl = document.createElement('div');
      indexEl.className = 'mission-fleet-index';
      indexEl.textContent = `UAM ${index + 1}`;
      const modeBadge = document.createElement('span');
      modeBadge.className = `mission-fleet-mode ${entry.mode}`;
      modeBadge.textContent = entry.mode === 'free' ? messages.freeMode : messages.routeMode;

      const aircraftField = document.createElement('label');
      aircraftField.className = 'mission-fleet-field';
      const aircraftLabel = document.createElement('span');
      aircraftLabel.className = 'mission-fleet-label';
      aircraftLabel.textContent = messages.aircraftId;
      const aircraftInput = document.createElement('input');
      aircraftInput.className = 'settings-input simulator-input';
      aircraftInput.type = 'text';
      aircraftInput.value = entry.aircraftId;
      aircraftInput.addEventListener('click', (evt) => evt.stopPropagation());
      aircraftInput.addEventListener('input', () => {
        simulationFleet[index].aircraftId = aircraftInput.value;
        scheduleMissionIcdAutoRefresh();
        updateSimulationFleetSummary();
        updateMissionEditorHeading();
      });

      const vehicleField = document.createElement('label');
      vehicleField.className = 'mission-fleet-field';
      const vehicleLabel = document.createElement('span');
      vehicleLabel.className = 'mission-fleet-label';
      vehicleLabel.textContent = messages.vehicleName;
      const vehicleInput = document.createElement('input');
      vehicleInput.className = 'settings-input simulator-input';
      vehicleInput.type = 'text';
      vehicleInput.value = entry.vehicleName;
      vehicleInput.addEventListener('click', (evt) => evt.stopPropagation());
      vehicleInput.addEventListener('input', () => {
        simulationFleet[index].vehicleName = vehicleInput.value;
        scheduleMissionIcdAutoRefresh();
        updateMissionEditorHeading();
      });

      const summary = document.createElement('div');
      summary.className = 'mission-fleet-summary';
      summary.textContent = getMissionSummaryText(entry);

      const missionBlock = document.createElement('div');
      missionBlock.className = 'mission-fleet-mission';

      const modeField = document.createElement('label');
      modeField.className = 'mission-fleet-field';
      const modeLabel = document.createElement('span');
      modeLabel.className = 'mission-fleet-label';
      modeLabel.textContent = messages.missionMode;
      const modeSelect = document.createElement('select');
      modeSelect.className = 'port-select mission-fleet-mode-select';
      modeSelect.appendChild(new Option(messages.routeMode, 'route'));
      modeSelect.appendChild(new Option(messages.freeMode, 'free'));
      modeSelect.value = entry.mode;
      modeSelect.addEventListener('click', (evt) => evt.stopPropagation());
      modeSelect.addEventListener('change', () => {
        simulationFleet[index].mode = modeSelect.value === 'free' ? 'free' : 'route';
        if (index === activeMissionIndex) {
          setMode(simulationFleet[index].mode);
        } else {
          renderSimulationFleet();
          scheduleMissionIcdAutoRefresh();
        }
      });
      modeField.appendChild(modeLabel);
      modeField.appendChild(modeSelect);
      missionBlock.appendChild(modeField);

      if (entry.mode === 'route') {
        const controls = document.createElement('div');
        controls.className = 'mission-fleet-controls';

        const depField = document.createElement('label');
        depField.className = 'mission-fleet-field';
        const depLabel = document.createElement('span');
        depLabel.className = 'mission-fleet-label';
        depLabel.textContent = messages.departure;
        const depSelect = document.createElement('select');
        depSelect.className = 'port-select mission-fleet-select';
        buildVertiportOptionElements(depSelect, entry.departureName);
        depSelect.addEventListener('click', (evt) => evt.stopPropagation());
        depSelect.addEventListener('change', () => {
          simulationFleet[index].departureName = depSelect.value;
          if (simulationFleet[index].routeData) {
            const routeStart = simulationFleet[index].routeData.path?.[0] || '';
            if (depSelect.value !== routeStart) {
              simulationFleet[index].routeData = null;
            }
          }
          if (index === activeMissionIndex) {
            const topSelect = document.getElementById('departure-select');
            if (topSelect) topSelect.value = depSelect.value;
            syncSelectedVertiports();
          } else {
            renderSimulationFleet();
          }
          scheduleMissionIcdAutoRefresh();
        });
        depField.appendChild(depLabel);
        depField.appendChild(depSelect);

        const arrField = document.createElement('label');
        arrField.className = 'mission-fleet-field';
        const arrLabel = document.createElement('span');
        arrLabel.className = 'mission-fleet-label';
        arrLabel.textContent = messages.arrival;
        const arrSelect = document.createElement('select');
        arrSelect.className = 'port-select mission-fleet-select';
        buildVertiportOptionElements(arrSelect, entry.arrivalName);
        arrSelect.addEventListener('click', (evt) => evt.stopPropagation());
        arrSelect.addEventListener('change', () => {
          simulationFleet[index].arrivalName = arrSelect.value;
          if (simulationFleet[index].routeData) {
            const routeEnd =
              simulationFleet[index].routeData.path?.[simulationFleet[index].routeData.path.length - 1] || '';
            if (arrSelect.value !== routeEnd) {
              simulationFleet[index].routeData = null;
            }
          }
          if (index === activeMissionIndex) {
            const topSelect = document.getElementById('arrival-select');
            if (topSelect) topSelect.value = arrSelect.value;
            syncSelectedVertiports();
          } else {
            renderSimulationFleet();
          }
          scheduleMissionIcdAutoRefresh();
        });
        arrField.appendChild(arrLabel);
        arrField.appendChild(arrSelect);

        const computeBtn = document.createElement('button');
        computeBtn.type = 'button';
        computeBtn.className = 'btn btn-primary btn-sm mission-fleet-button';
        computeBtn.textContent = messages.compute;
        computeBtn.disabled =
          !entry.departureName ||
          !entry.arrivalName ||
          entry.departureName === entry.arrivalName;
        computeBtn.addEventListener('click', async (evt) => {
          evt.preventDefault();
          evt.stopPropagation();
          activateMissionEditor(index, {
            preserveViewport: true,
            suppressPreviewInvalidate: true,
          });
          const topDep = document.getElementById('departure-select');
          const topArr = document.getElementById('arrival-select');
          if (topDep) topDep.value = simulationFleet[index].departureName || '';
          if (topArr) topArr.value = simulationFleet[index].arrivalName || '';
          simulationFleet[index].mode = 'route';
          syncSelectedVertiports();
          await computeRoute();
        });

        controls.appendChild(depField);
        controls.appendChild(arrField);
        controls.appendChild(computeBtn);
        missionBlock.appendChild(controls);
      } else {
        const freeRow = document.createElement('div');
        freeRow.className = 'mission-fleet-free-row';

        const freeNote = document.createElement('div');
        freeNote.className = 'mission-fleet-note';
        freeNote.textContent = entry.freeWaypoints?.length
          ? messages.freeReady(entry.freeWaypoints.length)
          : messages.freePending;

        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'btn btn-ghost btn-sm mission-fleet-button';
        editBtn.textContent = messages.editMap;
        editBtn.addEventListener('click', (evt) => {
          evt.preventDefault();
          evt.stopPropagation();
          simulationFleet[index].mode = 'free';
          activateMissionEditor(index, {
            preserveViewport: true,
            suppressPreviewInvalidate: true,
          });
          if (mode !== 'free') {
            setMode('free');
          }
        });

        freeRow.appendChild(freeNote);
        freeRow.appendChild(editBtn);
        missionBlock.appendChild(freeRow);
      }

      header.appendChild(indexEl);
      header.appendChild(modeBadge);
      aircraftField.appendChild(aircraftLabel);
      aircraftField.appendChild(aircraftInput);
      vehicleField.appendChild(vehicleLabel);
      vehicleField.appendChild(vehicleInput);
      row.appendChild(header);
      row.appendChild(aircraftField);
      row.appendChild(vehicleField);
      row.appendChild(missionBlock);
      row.appendChild(summary);
      listEl.appendChild(row);
    });

    updateSimulationFleetSummary();
    ODT.Simulator?.refreshMissionState?.();
  }

  function resetMissionEditorVisuals() {
    closeFreeWaypointAltitudeEditor();
    freeMarkers.forEach((marker) => marker.remove());
    freeMarkers = [];

    const map = ODT.MapManager.getMap();
    if (map && map.getLayer('route-line')) {
      map.removeLayer('route-line');
      map.removeLayer('route-line-shadow');
      if (map.getLayer('route-ribbon-3d')) map.removeLayer('route-ribbon-3d');
      if (map.getLayer('route-nodes-3d')) map.removeLayer('route-nodes-3d');
      map.removeSource('route');
      if (map.getSource('route-3d')) map.removeSource('route-3d');
      routeLayerAdded = false;
    }
    if (map && map.getLayer('free-mission-line')) {
      map.removeLayer('free-mission-line');
      if (map.getLayer('free-mission-ribbon-3d')) map.removeLayer('free-mission-ribbon-3d');
      if (map.getLayer('free-mission-nodes-3d')) map.removeLayer('free-mission-nodes-3d');
      map.removeSource('free-mission');
      if (map.getSource('free-mission-3d')) map.removeSource('free-mission-3d');
    }

    document.getElementById('route-info')?.classList.remove('visible');
    updateMissionTable([]);
    ODT.AltitudeProfile.hide();
  }

  function syncModeUI() {
    document.querySelectorAll('.mode-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });
    document.getElementById('route-mode').style.display = mode === 'route' ? '' : 'none';
    document.getElementById('free-mode').style.display = mode === 'free' ? '' : 'none';
  }

  function loadActiveMissionIntoEditor(options = {}) {
    const { preserveViewport = true, suppressPreviewInvalidate = true } = options;
    const mission = getActiveMissionEntry();
    resetMissionEditorVisuals();

    mode = mission?.mode === 'free' ? 'free' : 'route';
    routeData = mission?.routeData || null;
    freeWaypoints = Array.isArray(mission?.freeWaypoints) ? mission.freeWaypoints : [];

    if (mission) {
      mission.mode = mode;
      mission.routeData = routeData;
      mission.freeWaypoints = freeWaypoints;
    }

    const depSel = document.getElementById('departure-select');
    const arrSel = document.getElementById('arrival-select');
    if (depSel) depSel.value = mission?.departureName || '';
    if (arrSel) arrSel.value = mission?.arrivalName || '';

    syncModeUI();
    if (mode === 'route' && routeData) {
      displayRoute(routeData, {
        preserveViewport,
        suppressInvalidate: suppressPreviewInvalidate,
      });
    } else if (mode === 'free' && freeWaypoints.length) {
      rebuildFreeWaypointMarkers();
      updateFreeMissionLine();
      updateMissionTable(freeWaypoints);
      ODT.AltitudeProfile.show(freeWaypoints);
    } else {
      updateMissionTable([]);
      ODT.AltitudeProfile.hide();
    }

    syncSelectedVertiports();
    updateMissionEditorHeading();
    renderSimulationFleet();
  }

  function getMissionBaseOptions() {
    const stdInput = document.getElementById('mission-icd-std');
    const normalizedStd = normalizeMissionIcdStdValue(stdInput?.value || '');
    if (stdInput && normalizedStd && stdInput.value !== normalizedStd) {
      stdInput.value = normalizedStd;
    }
    return {
      flightPlanNumber: document.getElementById('mission-icd-flight-plan-number')?.value?.trim() || '',
      std: normalizedStd || stdInput?.value || '',
      cruiseSpeedMps: parseFloat(document.getElementById('settings-speed')?.value) || 30,
    };
  }

  function getMissionPreviewOptions() {
    const fleet = getSimulationFleetPayload();
    return {
      ...getMissionBaseOptions(),
      aircraftId: fleet[0]?.aircraftId || 'UAM0001',
    };
  }

  function buildMissionPayloadForEntry(entry, options = {}) {
    const { includeOptions = false, missionOptions = null } = options;
    if (!entry) return null;
    if (entry.mode === 'free') {
      if (!entry.freeWaypoints?.length) return null;
      return {
        mode: 'free',
        freeWaypoints: entry.freeWaypoints,
        ...(includeOptions ? { options: missionOptions || getMissionPreviewOptions() } : {}),
      };
    }
    if (!entry.routeData) return null;
    return {
      mode: 'route',
      departureName: entry.departureName || entry.routeData.path?.[0] || '',
      arrivalName: entry.arrivalName || entry.routeData.path?.[entry.routeData.path.length - 1] || '',
      routeData: entry.routeData,
      ...(includeOptions ? { options: missionOptions || getMissionPreviewOptions() } : {}),
    };
  }

  function buildMissionSimulationPayload() {
    ensureSimulationFleet();
    simulationFleet = simulationFleet.map((entry, index) => sanitizeSimulationFleetEntry(entry, index));
    const missions = simulationFleet
      .map((entry) => buildMissionPayloadForEntry(entry))
      .filter(Boolean);
    if (!missions.length || missions.length !== simulationFleet.length) {
      return null;
    }
    return {
      missions,
      fleet: getSimulationFleetPayload(),
      options: getMissionBaseOptions(),
    };
  }

  function getMissionSimulationValidationError() {
    ensureSimulationFleet();
    simulationFleet = simulationFleet.map((entry, index) => sanitizeSimulationFleetEntry(entry, index));
    const messages = getSimulationFleetMessages();
    for (let index = 0; index < simulationFleet.length; index += 1) {
      if (!buildMissionPayloadForEntry(simulationFleet[index])) {
        return messages.missingMission(index);
      }
    }
    return '';
  }

  function buildMissionIcdPayload() {
    ensureSimulationFleet();
    simulationFleet = simulationFleet.map((entry, index) => sanitizeSimulationFleetEntry(entry, index));
    return buildMissionPayloadForEntry(simulationFleet[0], {
      includeOptions: true,
      missionOptions: getMissionPreviewOptions(),
    });
  }

  function invalidateMissionIcdPreview() {
    if (missionIcdRefreshHandle) {
      window.clearTimeout(missionIcdRefreshHandle);
      missionIcdRefreshHandle = 0;
    }
    lastMissionIcd = null;
    const previewEl = document.getElementById('mission-icd-preview');
    if (previewEl) {
      previewEl.textContent = '';
    }
    const messages = getMissionIcdMessages();
    const hasMission = !!buildMissionIcdPayload();
    setMissionIcdStatus(hasMission ? messages.stale : messages.empty);
  }

  function scheduleMissionIcdAutoRefresh() {
    if (missionIcdRefreshHandle) {
      window.clearTimeout(missionIcdRefreshHandle);
      missionIcdRefreshHandle = 0;
    }
    if (!buildMissionIcdPayload()) {
      invalidateMissionIcdPreview();
      return;
    }
    setMissionIcdStatus(getMissionIcdMessages().stale);
    missionIcdRefreshHandle = window.setTimeout(() => {
      missionIcdRefreshHandle = 0;
      generateMissionIcd({ logSuccess: false, warnOnMissing: false });
    }, 120);
  }

  function syncSelectedVertiports() {
    const mission = getActiveMissionEntry();
    if (mission) {
      mission.departureName = document.getElementById('departure-select')?.value || '';
      mission.arrivalName = document.getElementById('arrival-select')?.value || '';
    }
    syncRouteSelectionState();
    renderVertiportList();
    addVertiportMarkers();
    renderSimulationFleet();
    updateMapPickUI();
  }

  function setMode(newMode) {
    mode = newMode === 'free' ? 'free' : 'route';
    const mission = getActiveMissionEntry();
    if (mission) {
      mission.mode = mode;
    }
    if (mode !== 'route') {
      routeMapPickEnabled = false;
    }
    syncModeUI();

    if (mode === 'route') {
      clearFreeWaypoints();
      if (mission) mission.mode = mode;
    } else {
      clearRouteDisplay();
      if (mission) mission.mode = mode;
    }
    renderSimulationFleet();
    updateMapPickUI();
  }

  async function computeRoute() {
    const start = document.getElementById('departure-select').value;
    const end = document.getElementById('arrival-select').value;
    if (!start || !end) {
      ODT.OperatorLog?.warn(
        ODT.t('log_route_incomplete_title'),
        ODT.t('log_route_incomplete_message')
      );
      return;
    }
    if (start === end) {
      ODT.OperatorLog?.warn(
        ODT.t('log_route_same_title'),
        ODT.t('log_route_same_message')
      );
      return;
    }

    try {
      routeData = await ODT.postJSON('/api/route', {
        start,
        end,
        include_arcs: true,
      });
      const mission = getActiveMissionEntry();
      if (mission) {
        mission.mode = 'route';
        mission.departureName = start;
        mission.arrivalName = end;
        mission.routeData = routeData;
      }
      displayRoute(routeData);
      ODT.OperatorLog?.success(
        ODT.t('log_route_computed_title'),
        ODT.t('log_route_computed_message', {
          start,
          end,
          distance: ODT.formatDist(routeData.distance_km),
        })
      );
      await generateMissionIcd({ logSuccess: false, warnOnMissing: false });
    } catch (e) {
      console.error('Route computation failed:', e);
      ODT.OperatorLog?.error(
        ODT.t('log_route_compute_failed_title'),
        ODT.humanizeError(e, ODT.t('log_route_compute_failed_message'))
      );
    }
  }

  function displayRoute(data, options = {}) {
    const { preserveViewport = false, suppressInvalidate = false } = options;
    const map = ODT.MapManager.getMap();
    if (!map) return;
    if (!suppressInvalidate) {
      invalidateMissionIcdPreview();
    }
    const mission = getActiveMissionEntry();
    if (mission) {
      mission.mode = 'route';
      mission.routeData = data;
      mission.departureName = document.getElementById('departure-select')?.value || data.path?.[0] || '';
      mission.arrivalName =
        document.getElementById('arrival-select')?.value ||
        data.path?.[data.path.length - 1] ||
        '';
    }

    const renderedRoute = {
      ...data,
      points: buildRouteRenderPoints(data),
    };

    const infoEl = document.getElementById('route-info');
    document.getElementById('route-distance').textContent = ODT.formatDist(data.distance_km);
    document.getElementById('route-waypoint-count').textContent = data.path.length;
    document.getElementById('route-path').textContent = data.path.join(' -> ');
    document.getElementById('route-path').title = data.path.join(' -> ');
    infoEl.classList.add('visible');

    const coords = renderedRoute.points.map((point) => [point.lon, point.lat]);
    const route3dFeatures = buildRoute3dFeatures(renderedRoute);

    if (map.getSource('route')) {
      map.getSource('route').setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: coords },
      });
      if (map.getSource('route-3d')) {
        map.getSource('route-3d').setData({
          type: 'FeatureCollection',
          features: route3dFeatures,
        });
      }
    } else {
      map.addSource('route', {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: coords },
        },
      });

      map.addSource('route-3d', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: route3dFeatures,
        },
      });

      map.addLayer({
        id: 'route-line-shadow',
        type: 'line',
        source: 'route',
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
        paint: {
          'line-color': 'rgba(96, 165, 250, 0.22)',
          'line-width': 10,
          'line-blur': 5,
        },
      });

      map.addLayer({
        id: 'route-line',
        type: 'line',
        source: 'route',
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
        paint: {
          'line-color': '#60a5fa',
          'line-width': 4.2,
          'line-opacity': 1,
        },
      });

      map.addLayer({
        id: 'route-ribbon-3d',
        type: 'fill-extrusion',
        source: 'route-3d',
        filter: ['==', ['get', 'shape'], 'route-ribbon'],
        layout: { visibility: 'none' },
        paint: {
          'fill-extrusion-color': '#60a5fa',
          'fill-extrusion-base': ['get', 'base_m'],
          'fill-extrusion-height': ['get', 'height_m'],
          'fill-extrusion-opacity': 0.78,
        },
      });

      map.addLayer({
        id: 'route-nodes-3d',
        type: 'fill-extrusion',
        source: 'route-3d',
        filter: ['==', ['get', 'shape'], 'route-node'],
        layout: { visibility: 'none' },
        paint: {
          'fill-extrusion-color': '#93c5fd',
          'fill-extrusion-base': ['get', 'base_m'],
          'fill-extrusion-height': ['get', 'height_m'],
          'fill-extrusion-opacity': 0.82,
        },
      });

      routeLayerAdded = true;
    }

    if (!preserveViewport && coords.length >= 2) {
      const bounds = coords.reduce(
        (acc, coord) => acc.extend(coord),
        new maplibregl.LngLatBounds(coords[0], coords[0])
      );
      map.fitBounds(bounds, { padding: 80, duration: 1000 });
    }

    updateMissionTable(data.waypoints || []);
    if (data.waypoints && data.waypoints.length >= 2) {
      ODT.AltitudeProfile.show(data.waypoints);
    }

    renderSimulationFleet();
    scheduleCorridorSceneUpdate();
  }

  function clearRouteDisplay() {
    const map = ODT.MapManager.getMap();
    if (map && map.getLayer('route-line')) {
      map.removeLayer('route-line');
      map.removeLayer('route-line-shadow');
      if (map.getLayer('route-ribbon-3d')) map.removeLayer('route-ribbon-3d');
      if (map.getLayer('route-nodes-3d')) map.removeLayer('route-nodes-3d');
      map.removeSource('route');
      if (map.getSource('route-3d')) map.removeSource('route-3d');
      routeLayerAdded = false;
    }
    routeData = null;
    const mission = getActiveMissionEntry();
    if (mission) {
      mission.routeData = null;
    }
    document.getElementById('route-info').classList.remove('visible');
    ODT.AltitudeProfile.hide();
    updateMissionTable([]);
    renderSimulationFleet();
    invalidateMissionIcdPreview();
  }

  function onMapClick(e) {
    if (ODT.Converter?.isMapPickActive?.()) return;
    if (mode !== 'free') return;
    const lngLat = e.lngLat;
    const defaultAlt = getDefaultFreeWaypointAltitude();

    const wp = {
      name: 'WP' + (freeWaypoints.length + 1),
      lat: lngLat.lat,
      lon: lngLat.lng,
      alt_m: defaultAlt,
      ground_m: null,
      ground_available: undefined,
      type: 'free',
    };
    freeWaypoints.push(wp);
    const mission = getActiveMissionEntry();
    if (mission) {
      mission.mode = 'free';
      mission.freeWaypoints = freeWaypoints;
    }
    const marker = addFreeWaypointMarker(wp, freeWaypoints.length - 1);
    updateFreeMissionLine();
    updateMissionTable(freeWaypoints);
    ODT.AltitudeProfile.show(freeWaypoints);
    renderSimulationFleet();
    scheduleMissionIcdAutoRefresh();
    if (marker) {
      openFreeWaypointAltitudeEditor(freeWaypoints.length - 1, marker);
    }
  }

  function removeFreeWaypoint(index) {
    const removed = freeWaypoints[index];
    if (freeAltitudePopupIndex === index) {
      closeFreeWaypointAltitudeEditor();
    }
    freeWaypoints.splice(index, 1);
    const mission = getActiveMissionEntry();
    if (mission) {
      mission.freeWaypoints = freeWaypoints;
    }
    rebuildFreeWaypointMarkers();
    updateFreeMissionLine();
    updateMissionTable(freeWaypoints);
    ODT.AltitudeProfile.show(freeWaypoints);
    renderSimulationFleet();
    scheduleMissionIcdAutoRefresh();

    const removedLog = getFreeWaypointRemovedText(index, removed);
    ODT.OperatorLog?.info(removedLog.title, removedLog.message);
  }

  function clearFreeWaypoints() {
    closeFreeWaypointAltitudeEditor();
    freeMarkers.forEach((marker) => marker.remove());
    freeMarkers = [];
    freeWaypoints = [];
    const mission = getActiveMissionEntry();
    if (mission) {
      mission.freeWaypoints = freeWaypoints;
    }
    const map = ODT.MapManager.getMap();
    if (map && map.getLayer('free-mission-line')) {
      map.removeLayer('free-mission-line');
      if (map.getLayer('free-mission-ribbon-3d')) map.removeLayer('free-mission-ribbon-3d');
      if (map.getLayer('free-mission-nodes-3d')) map.removeLayer('free-mission-nodes-3d');
      map.removeSource('free-mission');
      if (map.getSource('free-mission-3d')) map.removeSource('free-mission-3d');
    }
    updateMissionTable([]);
    ODT.AltitudeProfile.hide();
    renderSimulationFleet();
    invalidateMissionIcdPreview();
  }

  function onAltitudeChange(index, newAlt) {
    if (mode === 'free' && freeWaypoints[index]) {
      freeWaypoints[index].alt_m = newAlt;
      const mission = getActiveMissionEntry();
      if (mission) {
        mission.freeWaypoints = freeWaypoints;
      }
      updateMissionTable(freeWaypoints);
      updateFreeMissionLine();
      renderSimulationFleet();
      scheduleMissionIcdAutoRefresh();
    }
  }

  async function executeMission() {
    const missionError = getMissionSimulationValidationError();
    if (missionError) {
      ODT.OperatorLog?.warn(
        ODT.t('log_mission_not_ready_title'),
        missionError
      );
      return;
    }
    const payload = buildMissionSimulationPayload();
    if (!payload) {
      ODT.OperatorLog?.warn(
        ODT.t('log_mission_not_ready_title'),
        ODT.t('log_mission_not_ready_message')
      );
      return;
    }
    if (!ODT.Simulator?.startMission) {
      ODT.OperatorLog?.error(
        ODT.t('log_mission_start_failed_title'),
        'Simulation service is not available in the browser.'
      );
      return;
    }
    try {
      await ODT.Simulator.startMission(payload, {
        replayStepS: getSimulationReplayStep(),
        playbackSpeedX: getSimulationPlaybackSpeed(),
      });
    } catch (_) {}
  }

  return {
    init,
    computeRoute,
    executeMission,
    sendMissionToDtam,
    onAltitudeChange,
    setCorridorVisibility,
    setBuildingVisibility,
    getMissionIcdPayload: buildMissionIcdPayload,
    getSimulationFleet: getSimulationFleetPayload,
    getSimulationReplayStep,
    getSimulationPlaybackSpeed,
    validateSimulationFleet,
    getRouteData: () => routeData,
    getFreeWaypoints: () => freeWaypoints,
    getMode: () => mode,
  };
})();
