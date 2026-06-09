'use strict';

/*
 * Flight Scheduler frontend controller
 *
 * 탭/도메인별 책임을 한 파일 안에서 명확히 구분해 둔다.
 * 큰 기능을 추가할 때는 아래 섹션 중 맞는 위치에 넣고, 섹션이 더 커지면
 * 별도 JS 모듈로 분리하는 것을 우선 검토한다.
 *
 * 0. 전역 설정/상태/공통 기체 배치 헬퍼
 * 1. 앱 셸: 탭 전환
 * 2. 사이드바: 접기/리사이즈
 * 3. 지도: MapLibre 초기화, 팝업, 공통 DOM/API 헬퍼
 * 4. 수요 탭: 수요 생성, OD/시간대 표 렌더링
 * 5. 분석 탭: 렌더링 없는 빠른 실행, 지표/CSV 저장
 * 6. 레이아웃 탭: 레이아웃 에디터, 버티포트별 레이아웃/기체 배치
 * 7. 시뮬레이션 탭: 실시간 다중 버티포트/공역 연계 시뮬레이션
 * 8. 경로 계산 패널 및 정적 항로/버티포트 오버레이
 */

/* ============================================================================
 * 0. Global configuration, state, and shared fleet helpers
 * ========================================================================== */

/* Visual home view for the sim map. It is intentionally centered on the
 * 서울 도심권 rather than all vertiports, because far-west outliers shift the
 * network too far left when fitBounds is used on load. */
const SIM_MAP_HOME_CENTER = [127.0000, 37.5520];
const SIM_MAP_HOME_ZOOM = 11.35;

const TAB_VIEW = {
  demand: 'demand-dashboard',
  layout: 'layout-workspace',
  sim: 'sim-map',
  analysis: 'analysis-dashboard',
};
const TAB_HAS_SIDEBAR = {
  demand: false,
  layout: false,
  sim: true,
  analysis: false,
};
const DEFAULT_TAB = 'demand';
const DEFAULT_LAYOUT_MODE = 'assign';
const LIVE_AIRSPACE_RIGHT_OFFSET_METERS = 120;
const FAST_ANALYSIS_YIELD_ITERATIONS = 100;
const MAX_ANALYSIS_GANTT_EVENTS = 6000;
const UI_SCALE_BASE_WIDTH = 1920;
const UI_SCALE_BASE_HEIGHT = 1080;
const UI_SCALE_MIN = 1;
const UI_SCALE_MAX = 1.5;

const AIRCRAFT_TYPES = [
  { id: 'a2', seats: 2, label: '2인승' },
  { id: 'a4', seats: 4, label: '4인승' },
  { id: 'a6', seats: 6, label: '6인승' },
  { id: 'a8', seats: 8, label: '8인승' },
];
const DEFAULT_AIRCRAFT_TYPE_ID = 'a4';

function emptyAircraftCounts() {
  return Object.fromEntries(AIRCRAFT_TYPES.map((t) => [t.id, 0]));
}

function aircraftCountsFromAssignments(assignments) {
  const counts = emptyAircraftCounts();
  for (const value of Object.values(assignments || {})) {
    if (value?.typeId && Object.prototype.hasOwnProperty.call(counts, value.typeId)) {
      counts[value.typeId] += 1;
    }
  }
  return counts;
}

function totalAircraftCount(counts) {
  return AIRCRAFT_TYPES.reduce((s, t) => s + (Number(counts?.[t.id]) || 0), 0);
}

function aircraftTypeById(typeId) {
  return AIRCRAFT_TYPES.find((type) => type.id === typeId) || null;
}

function assignmentForAircraftType(typeId) {
  const type = aircraftTypeById(typeId);
  return type ? { typeId: type.id, seats: type.seats } : null;
}

function sortLayoutGates(gates) {
  return [...(gates || [])].sort((a, b) => String(a.id).localeCompare(String(b.id), 'ko', { numeric: true }));
}

function normalizeGateAssignments(assignments, gates) {
  const result = {};
  const validGateIds = new Set((gates || []).map((gate) => gate.id));
  for (const [gateId, assignment] of Object.entries(assignments || {})) {
    const normalized = assignmentForAircraftType(assignment?.typeId);
    if (validGateIds.has(gateId) && normalized) result[gateId] = normalized;
  }
  return result;
}

/* Deterministic distribution: sort gates by id, then fill 2 -> 4 -> 6 -> 8.
 * The requested total is clamped to the number of available gates. */
function distributeAircraftToGates(counts, gates) {
  const sorted = sortLayoutGates(gates);
  const result = {};
  let i = 0;
  for (const type of AIRCRAFT_TYPES) {
    const want = Math.max(0, Number(counts?.[type.id]) || 0);
    const take = Math.min(want, sorted.length - i);
    for (let k = 0; k < take; k += 1, i += 1) {
      result[sorted[i].id] = { typeId: type.id, seats: type.seats };
    }
  }
  return result;
}

function defaultCountsForGateCount(gateCount) {
  const counts = emptyAircraftCounts();
  counts[DEFAULT_AIRCRAFT_TYPE_ID] = Math.max(0, gateCount);
  return counts;
}

const state = {
  map: null,
  vertiports: [],
  waypoints: [],
  vertiportMarkers: [],
  waypointLabelMarkers: [],
  activeTab: DEFAULT_TAB,
  layoutMode: DEFAULT_LAYOUT_MODE,
  routeCache: new Map(),
  demand: { scenario: null, originFilter: '' },
  analysis: {
    result: null,
    selectedVertiportId: '',
    saveManifest: null,
  },
  sim: {
    simulation: null,
    live: null,
    selectedVertiportId: null,
    currentTimeSeconds: 0,
    durationSeconds: 0,
    playing: false,
    timer: null,
    lastFrameMs: 0,
    mapInteractionsReady: false,
    activeAircraftPopup: {
      aircraftId: null,
      popup: null,
      contentKey: '',
    },
    vpModalOpen: false,
    renderCache: {
      routeStatsVersion: -1,
      geoJsonKey: '',
      logKey: '',
      detailKey: '',
      metricsKey: '',
      lastPanelMs: 0,
      lastMetricsMs: 0,
      lastDetailMs: 0,
      lastLogMs: 0,
      lastCanvasMs: 0,
      lastMapMs: 0,
      lastGeoJsonMs: 0,
    },
  },
  layout: {
    editor: null,
    library: [],
    selectedLibraryName: null,
    configsByVp: {},
    selectedVp: null,
    workingConfig: null,
    workingLayout: null,
  },
};

/* App bootstrap: wire static controls first, then load server-side data and map layers. */
document.addEventListener('DOMContentLoaded', () => {
  setupViewportScale();
  setupTabs();
  setupSidebarPanels();
  setupSidebarResizer();
  setupDemandForm();
  setupSimulationControls();
  setupAnalysisWorkspace();
  setupLayoutWorkspace();
  start();
});

function setupViewportScale() {
  let resizeFrame = null;
  const apply = () => {
    resizeFrame = null;
    const scale = calculateViewportScale();
    const root = document.documentElement;
    root.style.setProperty('--ui-scale', scale.toFixed(3));
    root.style.setProperty('--app-layout-w', `${(100 / scale).toFixed(4)}vw`);
    root.style.setProperty('--app-layout-h', `${(100 / scale).toFixed(4)}vh`);
    root.dataset.uiScale = scale.toFixed(2);
    requestAnimationFrame(() => {
      state.map?.resize();
      state.layout.editor?.resize();
    });
  };
  const schedule = () => {
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(apply);
  };

  apply();
  window.addEventListener('resize', schedule, { passive: true });
  window.visualViewport?.addEventListener('resize', schedule, { passive: true });
}

function calculateViewportScale() {
  const width = Math.max(1, Number(window.innerWidth) || UI_SCALE_BASE_WIDTH);
  const height = Math.max(1, Number(window.innerHeight) || UI_SCALE_BASE_HEIGHT);
  const fitScale = Math.min(width / UI_SCALE_BASE_WIDTH, height / UI_SCALE_BASE_HEIGHT);
  const scale = Math.min(UI_SCALE_MAX, Math.max(UI_SCALE_MIN, fitScale));
  return scale < 1.04 ? 1 : Math.round(scale * 100) / 100;
}

function currentUiScale() {
  const value = Number(getComputedStyle(document.documentElement).getPropertyValue('--ui-scale'));
  return Number.isFinite(value) && value > 0 ? value : 1;
}

async function start() {
  const tileStatus = await fetchJson('/tiles/status').catch(() => null);
  const useMbtiles = !!tileStatus?.available;
  setupMap(useMbtiles ? 'mbtiles' : 'fallback');
  await loadOverlays();
  await loadLayoutLibrary();
  await loadVertiportConfigs();
  rebuildAssignVpList();
  rebuildSimVertiportStatus();
  setupRoutePanel();
}

/* ============================================================================
 * 1. App shell: top-level tab switching
 * ========================================================================== */

function setupTabs() {
  document.querySelectorAll('[data-tab]').forEach((btn) => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tab));
  });
  activateTab(DEFAULT_TAB);
}

function activateTab(name) {
  if (!TAB_VIEW[name]) return;
  state.activeTab = name;
  document.querySelectorAll('[data-tab]').forEach((btn) => {
    const active = btn.dataset.tab === name;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  document.querySelectorAll('.sidebar-pane').forEach((pane) => {
    pane.classList.toggle('active', pane.dataset.pane === name);
  });
  const targetView = TAB_VIEW[name];
  document.querySelectorAll('.main-view').forEach((view) => {
    view.classList.toggle('active', view.dataset.view === targetView);
  });
  document.getElementById('app').classList.toggle('no-sidebar', !TAB_HAS_SIDEBAR[name]);

  if (targetView === 'sim-map' && state.map) {
    requestAnimationFrame(() => state.map.resize());
  }
  if (targetView === 'layout-workspace') {
    requestAnimationFrame(() => state.layout.editor?.resize());
  }
}

/* ============================================================================
 * 2. Sidebar: collapsible panels and user-resizable width
 * ========================================================================== */

function setupSidebarPanels() {
  document.querySelectorAll('button.panel-toggle').forEach((toggle) => {
    toggle.addEventListener('click', () => {
      const panel = toggle.closest('.panel');
      const body = panel.querySelector('.panel-body');
      const collapsed = toggle.classList.toggle('collapsed');
      const caret = toggle.querySelector('.caret');
      if (caret) caret.textContent = collapsed ? '▸' : '▾';
      if (body) body.hidden = collapsed;
    });
  });
}

function setupSidebarResizer() {
  const resizer = document.getElementById('sidebar-resizer');
  if (!resizer) return;
  const root = document.documentElement;
  const STORAGE_KEY = 'vert.sidebarWidth';
  const DEFAULT_WIDTH = 320;
  const bounds = () => {
    const styles = getComputedStyle(root);
    return {
      min: parseInt(styles.getPropertyValue('--sidebar-min-w'), 10) || 240,
      max: parseInt(styles.getPropertyValue('--sidebar-max-w'), 10) || 540,
    };
  };
  const applyWidth = (w) => {
    const { min, max } = bounds();
    const v = Math.max(min, Math.min(max, Math.round(w)));
    root.style.setProperty('--sidebar-w', `${v}px`);
    return v;
  };
  const saved = parseInt(localStorage.getItem(STORAGE_KEY) || '', 10);
  if (Number.isFinite(saved)) applyWidth(saved);

  let dragging = false;
  resizer.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    dragging = true;
    resizer.setPointerCapture(e.pointerId);
    resizer.classList.add('dragging');
    document.body.classList.add('is-resizing');
  });
  resizer.addEventListener('pointermove', (e) => {
    if (dragging) applyWidth(e.clientX / currentUiScale());
  });
  const stop = (e) => {
    if (!dragging) return;
    dragging = false;
    if (e?.pointerId !== undefined) {
      try { resizer.releasePointerCapture(e.pointerId); } catch (_) {}
    }
    resizer.classList.remove('dragging');
    document.body.classList.remove('is-resizing');
    const cur = parseInt(getComputedStyle(root).getPropertyValue('--sidebar-w'), 10);
    if (Number.isFinite(cur)) localStorage.setItem(STORAGE_KEY, String(cur));
    state.map?.resize();
    state.layout.editor?.resize();
  };
  resizer.addEventListener('pointerup', stop);
  resizer.addEventListener('pointercancel', stop);
  resizer.addEventListener('dblclick', () => {
    applyWidth(DEFAULT_WIDTH);
    localStorage.removeItem(STORAGE_KEY);
    state.map?.resize();
    state.layout.editor?.resize();
  });
}

/* ============================================================================
 * 3. Map: MapLibre setup, live aircraft popup, and shared UI helpers
 * ========================================================================== */

function setupMap(styleKey) {
  state.map = new maplibregl.Map({
    container: 'map',
    style: window.MAP_STYLES[styleKey](),
    center: SIM_MAP_HOME_CENTER,
    zoom: SIM_MAP_HOME_ZOOM,
    minZoom: 8,
    maxZoom: 18,
    attributionControl: false,
    dragRotate: false,
    pitchWithRotate: false,
    localIdeographFontFamily:
      '"Apple SD Gothic Neo", "Malgun Gothic", "맑은 고딕", -apple-system, sans-serif',
  });
  state.map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
  state.map.on('error', (e) => {
    if (!e?.error) return;
    if (String(e.error.message || '').includes('404')) return;
    console.warn('map error', e.error);
  });
  document.getElementById('zoom-in')?.addEventListener('click', () => state.map.zoomIn());
  document.getElementById('zoom-out')?.addEventListener('click', () => state.map.zoomOut());
  document.getElementById('recenter')?.addEventListener('click', () => resetSimulationMapView(500));
}

async function loadOverlays() {
  const [vertiportsRes, waypointsRes] = await Promise.all([
    fetchJson('/api/vertiports').catch(() => null),
    fetchJson('/api/waypoints').catch(() => null),
  ]);
  state.vertiports = vertiportsRes?.items || [];
  state.waypoints = waypointsRes?.items || [];
  setText('vertiport-count', state.vertiports.length);
  setText('vertiport-status-count', state.vertiports.length);
  whenStyleReady(() => {
    renderGeoSources();
    setupSimulationMapInteractions();
    placeVertiportMarkers();
    placeWaypointLabelMarkers();
    resetSimulationMapView(0);
  });
}

function setupSimulationMapInteractions() {
  if (!state.map || state.sim.mapInteractionsReady || !state.map.getLayer('sim-aircraft-circle')) return;
  state.sim.mapInteractionsReady = true;
  state.map.on('click', 'sim-aircraft-circle', (event) => {
    const feature = event.features?.[0];
    if (!feature) return;
    selectLiveAircraftPopup(feature);
  });
  state.map.on('mouseenter', 'sim-aircraft-circle', () => {
    state.map.getCanvas().style.cursor = 'pointer';
  });
  state.map.on('mouseleave', 'sim-aircraft-circle', () => {
    state.map.getCanvas().style.cursor = '';
  });
}

function selectLiveAircraftPopup(feature) {
  if (!state.map || typeof maplibregl === 'undefined') return;
  const aircraftId = String(feature.properties?.aircraftId || '');
  if (!aircraftId) return;
  let tracked = state.sim.activeAircraftPopup;
  if (!tracked?.popup) {
    const popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      offset: 14,
      className: 'sim-aircraft-popup',
    });
    popup.on('close', () => {
      if (state.sim.activeAircraftPopup?.popup === popup) {
        state.sim.activeAircraftPopup = { aircraftId: null, popup: null, contentKey: '' };
      }
    });
    tracked = { aircraftId, popup, contentKey: '' };
    state.sim.activeAircraftPopup = tracked;
  } else {
    tracked.aircraftId = aircraftId;
  }
  updateLiveAircraftPopupFromFeature(feature, true);
}

function updateLiveAircraftPopup(features) {
  const tracked = state.sim.activeAircraftPopup;
  if (!tracked?.popup || !tracked.aircraftId) return;
  const feature = (features || []).find((item) => String(item.properties?.aircraftId || '') === tracked.aircraftId);
  if (!feature) {
    tracked.popup.remove();
    return;
  }
  updateLiveAircraftPopupFromFeature(feature);
}

function updateLiveAircraftPopupFromFeature(feature, forceContent = false) {
  const tracked = state.sim.activeAircraftPopup;
  if (!tracked?.popup || !state.map) return;
  const coordinates = feature.geometry?.coordinates?.slice();
  if (!Array.isArray(coordinates) || coordinates.length < 2) return;
  tracked.popup.setLngLat(coordinates);
  const properties = feature.properties || {};
  const contentKey = aircraftPopupContentKey(properties);
  if (forceContent || tracked.contentKey !== contentKey) {
    tracked.contentKey = contentKey;
    tracked.popup.setHTML(renderAircraftPopup(properties));
  }
  if (typeof tracked.popup.isOpen !== 'function' || !tracked.popup.isOpen()) {
    tracked.popup.addTo(state.map);
  }
}

function aircraftPopupContentKey(properties) {
  return [
    properties.aircraftId || '',
    properties.flightPlanId || '',
    properties.typeId || '',
    properties.seats || '',
    properties.passengerCount || 0,
    properties.origin || '',
    properties.destination || '',
    properties.state || '',
  ].join('|');
}

function renderAircraftPopup(properties) {
  const typeId = normalizeAircraftTypeId(properties.typeId, properties.seats);
  const seats = Number(properties.seats) || Number(String(typeId).slice(1)) || '-';
  const passengerCount = Math.max(0, Math.floor(Number(properties.passengerCount) || 0));
  return `
    <div class="sim-aircraft-popup-card">
      <div class="sim-aircraft-popup-head">
        <span class="aircraft-chip ${typeId}">${escapeHtml(properties.aircraftId || '-')}</span>
        <strong>${escapeHtml(properties.flightPlanId || '-')}</strong>
      </div>
      <div class="sim-aircraft-popup-grid">
        <span>&#44592;&#52404; &#53440;&#51077;</span><b>${escapeHtml(String(seats))}&#51064;&#49849;</b>
        <span>&#54788;&#51116; &#53457;&#49849; &#51064;&#50896;</span><b>${escapeHtml(fmtNumber(passengerCount))} / ${escapeHtml(String(seats))}</b>
        <span>OD</span><b>${escapeHtml(properties.origin || '-')} &rarr; ${escapeHtml(properties.destination || '-')}</b>
        <span>&#49345;&#53468;</span><b>${escapeHtml(liveAircraftStateLabel(properties.state))}</b>
      </div>
    </div>
  `;
}
function liveAircraftStateLabel(value) {
  const labels = {
    airspace: '\uacf5\uc5ed \ube44\ud589 \uc911',
    departing: '\ucd9c\ubc1c \uc808\ucc28',
    landing: '\ucc29\ub959 \uc808\ucc28',
    arrivalHold: '\ub3c4\ucc29 \ub300\uae30',
    available: '\uc8fc\uae30',
  };
  return labels[value] || value || '-';
}
/* Shared low-level helpers used across tabs. Keep these UI/API/format utilities
 * generic; tab-specific calculations should stay inside their own section. */
function whenStyleReady(cb) {
  if (state.map.isStyleLoaded()) cb();
  else state.map.once('load', cb);
}

function fetchJson(url, options = {}) {
  const init = { ...options };
  if (init.body && !init.headers) init.headers = { 'Content-Type': 'application/json' };
  return fetch(url, init).then(async (r) => {
    if (!r.ok) {
      let detail = '';
      try { detail = (await r.json())?.detail || ''; } catch (_) {}
      throw new Error(`${url} → ${r.status}${detail ? ': ' + detail : ''}`);
    }
    return r.json();
  });
}
function setText(id, v) {
  const el = document.getElementById(id);
  const text = String(v);
  if (el && el.textContent !== text) el.textContent = text;
}
function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}
function fmtNumber(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return Number(n).toLocaleString('ko-KR');
}
function formatClockSeconds(value) {
  const total = Math.max(0, Math.floor(Number(value) || 0));
  const h = Math.floor((total / 3600) % 24);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const day = Math.floor(total / 86400);
  const label = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return day ? `${label}+${day}d` : label;
}

/* ============================================================================
 * 4. Demand tab: scenario generation and OD/hourly demand visualization
 * ========================================================================== */

const DEMAND_DEFAULTS = {
  baseTraffic: 13521125,
  transferRatioPercent: 0.8,
  operationStart: '06:30',
  operationEnd: '21:30',
  minOdDistanceKm: 0,
  randomSeed: 42,
  scenarioOffsetDays: 30,
};

function setupDemandForm() {
  const today = new Date();
  today.setDate(today.getDate() + DEMAND_DEFAULTS.scenarioOffsetDays);
  document.getElementById('demand-date').value = today.toISOString().slice(0, 10);
  document.getElementById('demand-base-traffic').value = String(DEMAND_DEFAULTS.baseTraffic);
  document.getElementById('demand-transfer-ratio').value = String(DEMAND_DEFAULTS.transferRatioPercent);
  document.getElementById('demand-operation-start').value = DEMAND_DEFAULTS.operationStart;
  document.getElementById('demand-operation-end').value = DEMAND_DEFAULTS.operationEnd;
  document.getElementById('demand-min-od-distance').value = String(DEMAND_DEFAULTS.minOdDistanceKm);
  document.getElementById('demand-random-seed').value = String(DEMAND_DEFAULTS.randomSeed);

  document.getElementById('demand-generate-btn').addEventListener('click', generateScenario);
  document.getElementById('origin-filter').addEventListener('change', onOriginFilterChange);
  document.getElementById('od-table').addEventListener('click', (event) => {
    const row = event.target.closest('tbody tr');
    if (!row || row.classList.contains('total-row')) return;
    const origin = row.dataset.origin;
    if (!origin) return;
    const sel = document.getElementById('origin-filter');
    const next = sel.value === origin ? '' : origin;
    sel.value = next;
    sel.dispatchEvent(new Event('change'));
  });
}

function collectDemandPayload() {
  const seed = document.getElementById('demand-random-seed').value;
  const minDistance = document.getElementById('demand-min-od-distance').value;
  return {
    scenarioDate: document.getElementById('demand-date').value,
    baseTraffic: Number(document.getElementById('demand-base-traffic').value),
    transferRatioPercent: Number(document.getElementById('demand-transfer-ratio').value),
    operationStart: document.getElementById('demand-operation-start').value,
    operationEnd: document.getElementById('demand-operation-end').value,
    minOdDistanceKm: minDistance === '' ? null : Number(minDistance),
    randomSeed: seed === '' ? null : Number(seed),
  };
}
function setDemandStatus(text, level) {
  const el = document.getElementById('demand-status');
  el.textContent = text;
  if (level) el.dataset.level = level; else el.removeAttribute('data-level');
}
async function generateScenario() {
  const btn = document.getElementById('demand-generate-btn');
  btn.disabled = true;
  setDemandStatus('생성 중...', 'busy');
  try {
    const scenario = await fetchJson('/api/demand/scenarios', {
      method: 'POST', body: JSON.stringify(collectDemandPayload()),
    });
    state.demand.scenario = scenario;
    state.demand.originFilter = '';
    renderDemand(scenario);
    setDemandStatus('완료', 'success');
  } catch (err) {
    console.error(err);
    setDemandStatus('실패', 'error');
    alert('수요 생성 실패\n' + (err.message || err));
  } finally {
    btn.disabled = false;
  }
}
function renderDemand(scenario) {
  const demand = scenario.demand || {};
  const allocation = scenario.allocation || {};
  const passengers = scenario.passengers || {};
  const timeline = scenario.timeline || {};
  const dataset = scenario.dataset || {};
  setText('m-scenario-id', scenario.scenarioId || '—');
  setText('m-window', fmtNumber(demand.windowAdjustedPassengers));
  setText('m-allocated', fmtNumber(allocation.allocatedPassengers ?? demand.allocatedPassengers));
  setText('m-generated', fmtNumber(demand.generatedPassengers));
  setText('m-peak', timeline.peakHourLabel ? `${timeline.peakHourLabel} · ${fmtNumber(timeline.peakHourCount)}명` : '—');
  renderWarnings(dataset.warnings || []);
  renderODTable(allocation);
  renderHourBars(clipTimelineToWindow(timeline, demand.operationStart, demand.operationEnd), '전체 버티포트 합산');
  populateOriginFilter(passengers.origins || []);
  renderPassengerTable(passengers.sample || []);
  updateCsvLink(scenario.scenarioId, '');
  updateSimulationScenarioLabel();
  updateAnalysisScenarioLabel();
  const meta = document.getElementById('od-meta');
  if (meta) {
    const cutoff = allocation.distanceCutoff || {};
    const baseMeta = allocation.activePairs ? `${fmtNumber(allocation.activePairs)} pair · ${fmtNumber(allocation.allocatedPassengers)}명` : '';
    const cutoffMeta = cutoff.enabled ? ` · cut ${fmtNumber(cutoff.excludedPairs)} pair` : '';
    meta.textContent = baseMeta + cutoffMeta;
  }
}
function renderWarnings(warnings) {
  const el = document.getElementById('demand-warnings');
  if (!warnings.length) { el.hidden = true; el.innerHTML = ''; return; }
  el.hidden = false;
  el.innerHTML = '<ul>' + warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join('') + '</ul>';
}
function renderODTable(allocation) {
  const table = document.getElementById('od-table');
  const dests = allocation.destinations || [];
  const rows = allocation.rows || [];
  if (!rows.length) {
    table.innerHTML = '<tbody><tr><td class="empty-row" colspan="2">데이터 없음</td></tr></tbody>';
    return;
  }
  const headCells = dests.map((d) => `<th>${escapeHtml(d)}</th>`).join('');
  const head = `<thead><tr><th>출발 \\ 도착</th>${headCells}<th>합계</th></tr></thead>`;
  const destTotals = (allocation.destinationTotals || []).map((d) => d.passengers || 0);
  const grandTotal = allocation.allocatedPassengers ?? rows.reduce((s, r) => s + (r.total || 0), 0);
  const bodyRows = rows.map((row) => {
    const cells = (row.cells || []).map((c) => {
      const cls = c ? '' : 'num-zero';
      return `<td class="${cls}">${c ? fmtNumber(c) : '—'}</td>`;
    }).join('');
    return `<tr data-origin="${escapeHtml(row.origin)}"><th class="row-head">${escapeHtml(row.origin)}</th>${cells}<td class="total-cell">${fmtNumber(row.total)}</td></tr>`;
  }).join('');
  const totalRowCells = destTotals.map((t) => `<td>${fmtNumber(t)}</td>`).join('');
  const totalRow = `<tr class="total-row"><th class="row-head">합계</th>${totalRowCells}<td class="total-cell">${fmtNumber(grandTotal)}</td></tr>`;
  table.innerHTML = head + `<tbody>${bodyRows}${totalRow}</tbody>`;
  updateODSelectionHighlight(state.demand.originFilter);
}
function updateODSelectionHighlight(origin) {
  document.querySelectorAll('#od-table tbody tr').forEach((tr) => {
    tr.classList.toggle('is-selected', !!origin && tr.dataset.origin === origin);
  });
}
function parseHHMMToMinutes(t) {
  const [h, m] = String(t || '').split(':').map(Number);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return null;
  return h * 60 + m;
}
function clipTimelineToWindow(timeline, opStart, opEnd) {
  const start = parseHHMMToMinutes(opStart);
  const end = parseHHMMToMinutes(opEnd);
  if (start == null || end == null || start === end) return timeline;
  const hours = timeline.hours || [];
  const counts = timeline.counts || [];
  const overlaps = (h) => {
    const s = h * 60, e = s + 60;
    if (start < end) return s < end && e > start;
    return e > start || s < end;
  };
  const fHours = [], fCounts = [];
  for (let h = 0; h < hours.length; h++) {
    if (overlaps(h)) { fHours.push(hours[h]); fCounts.push(counts[h] || 0); }
  }
  return { ...timeline, hours: fHours, counts: fCounts };
}
function renderHourBars(timeline, subtitle) {
  const el = document.getElementById('hour-bars');
  const hours = timeline.hours || [];
  const counts = timeline.counts || [];
  document.getElementById('hour-subtitle').textContent = subtitle || '';
  if (!hours.length) { el.innerHTML = '<p class="empty-row">데이터 없음</p>'; return; }
  const max = Math.max(1, ...counts);
  el.innerHTML = hours.map((h, i) => {
    const c = counts[i] || 0;
    const pct = (c / max) * 100;
    return `<div class="hour-row"><span>${escapeHtml(h)}</span><div class="hour-track"><div class="hour-fill" style="width:${pct.toFixed(2)}%"></div></div><span class="hour-count">${fmtNumber(c)}</span></div>`;
  }).join('');
}
function populateOriginFilter(origins) {
  const sel = document.getElementById('origin-filter');
  const opts = origins.map((o) => `<option value="${escapeHtml(o.origin)}">${escapeHtml(o.origin)} · ${fmtNumber(o.count)}</option>`).join('');
  sel.innerHTML = `<option value="">전체</option>` + opts;
  sel.disabled = origins.length === 0;
}
function renderPassengerTable(rows) {
  const tbody = document.getElementById('passenger-body');
  if (!rows.length) { tbody.innerHTML = '<tr><td class="empty-row" colspan="5">데이터 없음</td></tr>'; return; }
  tbody.innerHTML = rows.map((p) => `
    <tr>
      <td title="${escapeHtml(p.id)}">${escapeHtml(p.id)}</td>
      <td title="${escapeHtml(p.origin)}">${escapeHtml(p.origin)}</td>
      <td title="${escapeHtml(p.destination)}">${escapeHtml(p.destination)}</td>
      <td>${escapeHtml(p.arrivalTimeLabel || p.arrivalTime || '')}</td>
      <td class="num">${escapeHtml(p.arrivalHour ?? '')}</td>
    </tr>
  `).join('');
}
function updateCsvLink(scenarioId, origin) {
  const link = document.getElementById('csv-export');
  if (!scenarioId) {
    link.setAttribute('aria-disabled', 'true');
    link.removeAttribute('href');
    link.tabIndex = -1;
    return;
  }
  const qs = origin ? `?origin=${encodeURIComponent(origin)}` : '';
  link.href = `/api/demand/scenarios/${scenarioId}/passengers.csv${qs}`;
  link.setAttribute('aria-disabled', 'false');
  link.tabIndex = 0;
}
async function onOriginFilterChange(event) {
  const scenarioId = state.demand.scenario?.scenarioId;
  if (!scenarioId) return;
  const origin = event.target.value;
  state.demand.originFilter = origin;
  updateCsvLink(scenarioId, origin);
  updateODSelectionHighlight(origin);
  try {
    const [page, hours] = await Promise.all([
      fetchJson(`/api/demand/scenarios/${scenarioId}/passengers?limit=200${origin ? `&origin=${encodeURIComponent(origin)}` : ''}`),
      fetchJson(`/api/demand/scenarios/${scenarioId}/arrival-hours${origin ? `?origin=${encodeURIComponent(origin)}` : ''}`),
    ]);
    renderPassengerTable(page.items || []);
    renderHourBars(
      clipTimelineToWindow(hours, hours.operationStart, hours.operationEnd),
      origin ? `${origin} · ${fmtNumber(hours.total || 0)}명` : '전체 버티포트 합산'
    );
  } catch (err) { console.error(err); }
}

/* ============================================================================
 * 5. Analysis tab: fast non-rendered run, metrics, and CSV export
 * ========================================================================== */

function setupAnalysisWorkspace() {
  document.getElementById('analysis-run-btn')?.addEventListener('click', runAnalysisFast);
  document.getElementById('analysis-save-btn')?.addEventListener('click', saveAnalysisCsv);
  document.getElementById('analysis-vp-filter')?.addEventListener('change', (event) => {
    state.analysis.selectedVertiportId = event.target.value || '';
    renderAnalysisResult();
  });
  updateAnalysisScenarioLabel();
}

function updateAnalysisScenarioLabel() {
  const label = document.getElementById('analysis-scenario-label');
  if (!label) return;
  const scenario = state.demand.scenario;
  if (!scenario?.scenarioId) {
    label.textContent = '수요 생성 필요';
    label.dataset.level = 'empty';
    return;
  }
  const demand = scenario.demand || {};
  label.textContent = `${scenario.scenarioId} · ${demand.scenarioDate || ''} · ${fmtNumber(demand.generatedPassengers)}명`;
  label.dataset.level = 'ready';
}

function setAnalysisStatus(text, level) {
  const el = document.getElementById('analysis-status');
  if (!el) return;
  el.textContent = text;
  if (level) el.dataset.level = level; else el.removeAttribute('data-level');
}

/* Analysis fast-run: reuse the live simulation scheduler, skip map/canvas rendering,
 * then drain active flights so CSV metrics are comparable with visual simulation. */
async function runAnalysisFast() {
  const scenario = state.demand.scenario;
  if (!scenario?.scenarioId) {
    setAnalysisStatus('수요 생성 필요', 'error');
    alert('먼저 수요 탭에서 시나리오를 생성하세요.');
    return;
  }
  const btn = document.getElementById('analysis-run-btn');
  const saveBtn = document.getElementById('analysis-save-btn');
  const seed = document.getElementById('analysis-random-seed')?.value;
  if (btn) btn.disabled = true;
  if (saveBtn) saveBtn.disabled = true;
  state.analysis.saveManifest = null;
  setText('analysis-save-path', '저장 전');
  setAnalysisStatus('분석 초기화 중...', 'busy');
  try {
    const live = await buildLiveSimulation(scenario, seed === '' ? null : Number(seed));
    setAnalysisStatus('전체 OD 경로 로딩 중...', 'busy');
    await preloadAllLiveRoutes(live);
    setAnalysisStatus('렌더링 없이 빠른 실행 중...', 'busy');
    await runLiveSimulationToEndFast(live, (progress, detail = {}) => {
      if (detail.phase === 'drain') {
        setAnalysisStatus(
          `잔여 비행 정리 중 · 활성 ${fmtNumber(detail.active || 0)}대 · 홀딩 ${fmtNumber(detail.hold || 0)}대`,
          'busy'
        );
        return;
      }
      if (detail.phase === 'timeout') {
        setAnalysisStatus(`잔여 비행 ${fmtNumber(detail.unfinished || 0)}편 미완료 처리 중`, 'busy');
        return;
      }
      setAnalysisStatus(`빠른 실행 중 ${Math.round(progress * 100)}%`, 'busy');
    });
    const result = buildAnalysisResult(live);
    state.analysis.result = result;
    state.analysis.selectedVertiportId = '';
    populateAnalysisVertiportFilter(result);
    renderAnalysisResult();
    if (saveBtn) saveBtn.disabled = false;
    const unfinished = result.flights.filter((flight) => !flight.gate_in_time).length;
    setAnalysisStatus(
      unfinished
        ? `완료 · ${fmtNumber(result.summary.flightCount)}편 · 미완료 ${fmtNumber(unfinished)}편`
        : `완료 · ${fmtNumber(result.summary.flightCount)}편`,
      'success'
    );
  } catch (err) {
    console.error(err);
    setAnalysisStatus('실패', 'error');
    alert('분석 실행 실패\n' + (err.message || err));
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function preloadAllLiveRoutes(live) {
  let requested = 0;
  for (const originMap of live.hourlyDemand.values()) {
    for (const [originId, destMap] of originMap.entries()) {
      for (const destinationId of destMap.keys()) {
        if (!live.routeCache.has(routeKey(originId, destinationId))) {
          requestLiveRoute(live, originId, destinationId);
          requested += 1;
        }
      }
    }
  }
  while (live.pendingRoutes.size) {
    await Promise.allSettled([...live.pendingRoutes.values()]);
  }
  return requested;
}

async function runLiveSimulationToEndFast(live, onProgress) {
  const start = live.startSeconds;
  const end = live.endSeconds;
  let iterations = 0;
  while (live.nowSeconds < end && !live.ended) {
    syncLiveDemandHour(live);
    updateLiveAircraftStates(live);
    const scheduled = scheduleLiveDepartures(live);
    if (scheduled < 250) {
      live.nowSeconds = nextLiveFastAnalysisTime(live, end);
    }
    iterations += 1;
    if (iterations % FAST_ANALYSIS_YIELD_ITERATIONS === 0) {
      if (onProgress) onProgress((live.nowSeconds - start) / Math.max(1, end - start));
      await sleep(0);
    }
  }
  if (live.nowSeconds >= end && !live.ended) {
    syncLiveDemandHour(live);
    updateLiveAircraftStates(live);
    scheduleLiveDepartures(live);
    finalizeLiveCurrentDemand(live);
    live.ended = true;
  }
  await drainLiveActiveFlights(live, onProgress);
}

function nextLiveFastAnalysisTime(live, maxSeconds) {
  const now = live.nowSeconds;
  let next = maxSeconds;
  const nextHourBoundary = (Math.floor(now / 3600) + 1) * 3600;
  if (nextHourBoundary > now) next = Math.min(next, nextHourBoundary);

  for (const ac of live.aircraft.values()) {
    if (ac.state === 'available') {
      const availableAt = Number(ac.availableAt);
      if (Number.isFinite(availableAt) && availableAt > now) next = Math.min(next, availableAt);
      continue;
    }
    if (ac.state === 'departing' || ac.state === 'landing') {
      const endTime = Number(ac.internal?.endTime);
      if (Number.isFinite(endTime) && endTime > now) next = Math.min(next, endTime);
      continue;
    }
    if (ac.state === 'airspace') {
      const endTime = Number(ac.airspace?.endTime);
      if (Number.isFinite(endTime) && endTime > now) next = Math.min(next, endTime);
      continue;
    }
    if (ac.state === 'arrivalHold') {
      const destVp = live.vertiports.get(ac.destinationId);
      const releaseTime = nextLiveResourceRelease(destVp, now);
      if (Number.isFinite(releaseTime)) next = Math.min(next, releaseTime);
    }
  }

  if (hasAvailableLiveDemand(live)) {
    for (const vp of live.vertiports.values()) {
      const releaseTime = nextLiveResourceRelease(vp, now);
      if (Number.isFinite(releaseTime)) next = Math.min(next, releaseTime);
    }
  }

  if (!Number.isFinite(next)) return maxSeconds;
  return Math.min(maxSeconds, Math.max(now + 1, Math.ceil(next)));
}

function hasAvailableLiveDemand(live) {
  const now = live.nowSeconds;
  for (const ac of live.aircraft.values()) {
    if (ac.state !== 'available' || ac.availableAt > now || !ac.locationVertiportId || !ac.gateId) continue;
    const originVp = live.vertiports.get(ac.locationVertiportId);
    if (!originVp) continue;
    for (const [destinationId, remaining] of originVp.currentDemand.entries()) {
      if (
        Math.floor(Number(remaining) || 0) > 0
        && destinationId !== originVp.id
        && live.vertiports.has(destinationId)
        && !live.failedRoutes.has(routeKey(originVp.id, destinationId))
        && live.routeCache.has(routeKey(originVp.id, destinationId))
      ) {
        return true;
      }
    }
  }
  return false;
}

async function drainLiveActiveFlights(live, onProgress) {
  const maxDrainSeconds = live.endSeconds + 6 * 3600;
  let ticks = 0;
  while (live.nowSeconds < maxDrainSeconds && hasActiveLiveFlights(live)) {
    updateLiveAircraftStates(live);
    if (!hasActiveLiveFlights(live)) break;
    live.nowSeconds = nextLiveDrainTime(live, maxDrainSeconds);
    ticks += 1;
    if (ticks % 10 === 0) {
      if (onProgress) onProgress(1, { phase: 'drain', ...liveActiveStateCounts(live) });
      await sleep(0);
    }
  }
  updateLiveAircraftStates(live);
  if (hasActiveLiveFlights(live)) {
    const unfinished = markUnfinishedLiveFlights(live, 'analysis_timeout');
    live.warnings.push(`분석 drain 제한으로 잔여 비행 ${unfinished}편을 미완료 처리했습니다.`);
    if (onProgress) onProgress(1, { phase: 'timeout', unfinished });
    await sleep(0);
  }
}

function hasActiveLiveFlights(live) {
  return [...live.aircraft.values()].some((ac) => ac.state !== 'available');
}

function liveActiveStateCounts(live) {
  const counts = { active: 0, hold: 0 };
  for (const ac of live.aircraft.values()) {
    if (ac.state === 'available') continue;
    counts.active += 1;
    if (ac.state === 'arrivalHold') counts.hold += 1;
  }
  return counts;
}

function nextLiveDrainTime(live, maxDrainSeconds) {
  const now = live.nowSeconds;
  let next = Number.POSITIVE_INFINITY;
  for (const ac of live.aircraft.values()) {
    if (ac.state === 'departing' || ac.state === 'landing') {
      const endTime = Number(ac.internal?.endTime);
      if (Number.isFinite(endTime) && endTime > now) next = Math.min(next, endTime);
      continue;
    }
    if (ac.state === 'airspace') {
      const endTime = Number(ac.airspace?.endTime);
      if (Number.isFinite(endTime) && endTime > now) next = Math.min(next, endTime);
      continue;
    }
    if (ac.state === 'arrivalHold') {
      const destVp = live.vertiports.get(ac.destinationId);
      const releaseTime = nextLiveResourceRelease(destVp, now);
      if (Number.isFinite(releaseTime)) next = Math.min(next, releaseTime);
    }
  }
  if (!Number.isFinite(next)) return maxDrainSeconds;
  return Math.min(maxDrainSeconds, Math.max(now + 1, next));
}

function nextLiveResourceRelease(vp, now) {
  if (!vp?.resources) return Number.POSITIVE_INFINITY;
  let next = Number.POSITIVE_INFINITY;
  for (const resourceMap of [vp.resources.links, vp.resources.fatos, vp.resources.gates, vp.resources.nodes]) {
    for (const value of Object.values(resourceMap || {})) {
      const t = Number(value);
      if (Number.isFinite(t) && t > now) next = Math.min(next, t);
    }
  }
  for (const reservationMap of [vp.resources.linkReservations, vp.resources.nodeReservations]) {
    for (const reservations of Object.values(reservationMap || {})) {
      for (const item of reservations || []) {
        const start = Number(item.start);
        const end = Number(item.end);
        if (Number.isFinite(start) && start > now) next = Math.min(next, start);
        if (Number.isFinite(end) && end > now) next = Math.min(next, end);
      }
    }
  }
  return next;
}

function markUnfinishedLiveFlights(live, reason) {
  let count = 0;
  for (const ac of live.aircraft.values()) {
    if (ac.state === 'available') continue;
    const flight = findLiveFlight(live, ac.flightPlanId);
    if (flight) {
      flight.status = reason;
      flight.timeoutReason = reason;
      count += 1;
    }
    ac.state = 'available';
    ac.locationVertiportId = ac.destinationId || ac.locationVertiportId || ac.originId;
    ac.originId = null;
    ac.destinationId = null;
    ac.flightPlanId = null;
    ac.internal = null;
    ac.airspace = null;
    ac.availableAt = live.nowSeconds;
  }
  return count;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/* Fast analysis result builders. These consume the same live simulation state
 * used by the visual sim, but summarize it into table/export-friendly rows. */
function buildAnalysisResult(live) {
  const flights = live.flights.map((flight) => buildAnalysisFlightRow(live, flight));
  const hourlyMetrics = buildAnalysisHourlyMetrics(live, flights);
  const typeMetrics = buildAnalysisTypeMetrics(flights);
  const resourceEvents = buildAnalysisResourceEvents(flights);
  const bottlenecks = buildAnalysisBottlenecks(hourlyMetrics, flights);
  const summary = buildAnalysisSummary(live, flights, hourlyMetrics);
  return {
    scenarioId: live.scenarioId,
    scenarioDate: live.scenarioDate,
    randomSeed: live.randomSeed,
    generatedAt: new Date().toISOString(),
    summary,
    vertiports: [...live.vertiports.values()].map((vp) => ({ id: vp.id, code: vp.code, name: vp.name })),
    flights,
    hourlyMetrics,
    typeMetrics,
    bottlenecks,
    resourceEvents,
  };
}

function buildAnalysisFlightRow(live, flight) {
  const times = flight.times || {};
  const capacity = Number(flight.capacity) || 0;
  const pax = Number(flight.passengerCount) || 0;
  const gateOut = numberOrNull(times.gateOutSeconds);
  const takeoff = numberOrNull(times.takeoffSeconds);
  const landing = numberOrNull(times.landingSeconds);
  const gateIn = numberOrNull(times.gateInSeconds);
  const ready = numberOrNull(times.readySeconds);
  const enRouteSegments = Array.isArray(flight.enRouteSegments) ? flight.enRouteSegments : [];
  const row = {
    scenario_id: live.scenarioId,
    scenario_date: live.scenarioDate,
    fpl_id: flight.flightPlanId,
    aircraft_id: flight.aircraftId,
    aircraft_type: flight.aircraftTypeId,
    capacity,
    passenger_count: pax,
    load_factor: capacity ? roundNumber(pax / capacity, 4) : 0,
    origin_vertiport_id: flight.originId,
    origin_vertiport: flight.origin,
    destination_vertiport_id: flight.destinationId,
    destination_vertiport: flight.destination,
    demand_hour: flight.demandHour,
    departure_gate_id: formatFacilityNumber(flight.departureGateId, 'G'),
    departure_fato_id: formatFacilityNumber(flight.departureFatoId, 'F'),
    arrival_gate_id: formatFacilityNumber(flight.arrivalGateId, 'G'),
    arrival_fato_id: formatFacilityNumber(flight.arrivalFatoId, 'F'),
    gate_out_time: times.gateOutTime || '',
    takeoff_time: times.takeoffTime || '',
    landing_time: times.landingTime || '',
    gate_in_time: times.gateInTime || '',
    ready_time: times.readyTime || '',
    gate_to_takeoff_sec: diffSeconds(takeoff, gateOut),
    air_time_sec: diffSeconds(landing, takeoff),
    landing_to_gate_sec: diffSeconds(gateIn, landing),
    gate_to_gate_sec: diffSeconds(gateIn, gateOut),
    departure_wait_sec: sumSegmentDuration(flight.departureSegments, (s) => s.state === 'waiting'),
    arrival_wait_sec: sumSegmentDuration(flight.arrivalSegments, (s) => s.state === 'waiting'),
    status: flight.status,
    route_path: (flight.routePath?.length ? flight.routePath : [flight.origin, flight.destination]).join(' > '),
    route_distance_km: Number.isFinite(Number(flight.routeDistanceKm)) ? roundNumber(Number(flight.routeDistanceKm), 4) : '',
    segment_count: enRouteSegments.length,
    _enRouteSegments: enRouteSegments,
    _scheduledFlight: buildScheduledFlightPayload(flight, enRouteSegments),
    _departureSegments: flight.departureSegments || [],
    _arrivalSegments: flight.arrivalSegments || [],
  };
  enRouteSegments.forEach((segment, index) => {
    row[`segment_${String(index + 1).padStart(3, '0')}`] = segment;
  });
  return row;
}

function buildScheduledFlightPayload(flight, enRouteSegments) {
  const times = flight.times || {};
  return {
    flightPlanNumber: flightPlanNumberFromId(flight.flightPlanId, flight.sequence),
    planVersion: 1,
    planStatus: 'active',
    aircraftId: flight.aircraftId,
    departure: {
      vertiport: flight.origin,
      std: times.gateOutTime || times.takeoffTime || '',
      depGateNumber: formatFacilityNumber(flight.departureGateId, 'G'),
      eobt: times.gateOutTime || '',
      depFatoNumber: formatFacilityNumber(flight.departureFatoId, 'F'),
      etot: times.takeoffTime || '',
    },
    enRoute: (enRouteSegments || []).map((segment, index) => ({
      seq: index + 1,
      phase: segment.phase,
      startLLA: segment.startLLA,
      endLLA: segment.endLLA,
      targetSpeed: segment.targetSpeed,
    })),
    arrival: {
      vertiport: flight.destination,
      sta: times.gateInTime || times.landingTime || '',
      arrGateNumber: formatFacilityNumber(flight.arrivalGateId, 'G'),
      eibt: times.gateInTime || '',
      arrFatoNumber: formatFacilityNumber(flight.arrivalFatoId, 'F'),
      eldt: times.landingTime || '',
    },
  };
}

function formatFacilityNumber(value, prefix) {
  const text = String(value || '').trim();
  if (!text) return '';
  const upper = text.toUpperCase();
  if (new RegExp(`^${prefix}\\d+$`).test(upper)) return upper;
  const match = text.match(/\d+/);
  return match ? `${prefix}${Number(match[0])}` : text;
}

function flightPlanNumberFromId(flightPlanId, fallback) {
  const digits = String(flightPlanId || '').match(/\d+/g)?.join('');
  const value = Number(digits);
  return Number.isFinite(value) && value > 0 ? value : Number(fallback) || 1;
}

function buildAnalysisHourlyMetrics(live, flights) {
  const requested = new Map();
  for (const [hour, originMap] of live.hourlyDemand.entries()) {
    for (const [originId, destMap] of originMap.entries()) {
      const key = `${hour}|${originId}`;
      const total = [...destMap.values()].reduce((sum, value) => sum + (Number(value) || 0), 0);
      requested.set(key, total);
    }
  }
  const processed = new Map();
  const groupedFlights = new Map();
  for (const flight of flights) {
    const key = `${flight.demand_hour}|${flight.origin_vertiport_id}`;
    processed.set(key, (processed.get(key) || 0) + (Number(flight.passenger_count) || 0));
    if (!groupedFlights.has(key)) groupedFlights.set(key, []);
    groupedFlights.get(key).push(flight);
  }
  const keys = new Set([...requested.keys(), ...processed.keys()]);
  return [...keys].map((key) => {
    const [hourText, originId] = key.split('|');
    const hour = Number(hourText);
    const vp = live.vertiports.get(originId);
    const rows = groupedFlights.get(key) || [];
    const req = requested.get(key) || 0;
    const proc = processed.get(key) || 0;
    return {
      hour,
      hour_label: `${String(hour).padStart(2, '0')}:00`,
      vertiport_id: originId,
      vertiport: vp?.name || originId,
      requested: req,
      processed: proc,
      unserved: Math.max(0, req - proc),
      processing_rate: req ? roundNumber(proc / req, 4) : 0,
      flight_count: rows.length,
      avg_load_factor: average(rows.map((f) => Number(f.load_factor) || 0)),
      avg_gate_to_gate_sec: average(rows.map((f) => Number(f.gate_to_gate_sec) || 0).filter(Boolean)),
      avg_departure_wait_sec: average(rows.map((f) => Number(f.departure_wait_sec) || 0).filter(Boolean)),
      avg_arrival_wait_sec: average(rows.map((f) => Number(f.arrival_wait_sec) || 0).filter(Boolean)),
    };
  }).sort((a, b) => a.hour - b.hour || a.vertiport.localeCompare(b.vertiport));
}

function buildAnalysisTypeMetrics(flights) {
  const groups = new Map();
  for (const flight of flights) {
    const key = flight.aircraft_type || 'unknown';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(flight);
  }
  return [...groups.entries()].map(([typeId, rows]) => {
    const passengers = rows.reduce((sum, f) => sum + (Number(f.passenger_count) || 0), 0);
    const seats = rows.reduce((sum, f) => sum + (Number(f.capacity) || 0), 0);
    return {
      aircraft_type: typeId,
      flight_count: rows.length,
      passenger_count: passengers,
      seat_supply: seats,
      avg_load_factor: seats ? roundNumber(passengers / seats, 4) : 0,
      avg_gate_to_gate_sec: average(rows.map((f) => Number(f.gate_to_gate_sec) || 0).filter(Boolean)),
    };
  }).sort((a, b) => String(a.aircraft_type).localeCompare(String(b.aircraft_type)));
}

function buildAnalysisBottlenecks(hourlyMetrics, flights) {
  const rows = [];
  for (const item of hourlyMetrics.filter((row) => row.unserved > 0).sort((a, b) => b.unserved - a.unserved).slice(0, 12)) {
    rows.push({
      type: 'unserved_demand',
      vertiport_id: item.vertiport_id,
      vertiport: item.vertiport,
      bucket: item.hour_label,
      value: item.unserved,
      description: `시간대 미처리 수요 ${fmtNumber(item.unserved)}명`,
    });
  }
  const byOrigin = groupBy(flights, (f) => f.origin_vertiport_id);
  for (const [originId, rowsForVp] of byOrigin.entries()) {
    const avgWait = average(rowsForVp.map((f) => Number(f.departure_wait_sec) || 0).filter(Boolean));
    if (avgWait > 0) {
      rows.push({
        type: 'departure_wait',
        vertiport_id: originId,
        vertiport: rowsForVp[0]?.origin_vertiport || originId,
        bucket: 'departure',
        value: roundNumber(avgWait, 1),
        description: '평균 출발 절차 대기시간(sec)',
      });
    }
  }
  const byDestination = groupBy(flights, (f) => f.destination_vertiport_id);
  for (const [destId, rowsForVp] of byDestination.entries()) {
    const avgWait = average(rowsForVp.map((f) => Number(f.arrival_wait_sec) || 0).filter(Boolean));
    if (avgWait > 0) {
      rows.push({
        type: 'arrival_wait',
        vertiport_id: destId,
        vertiport: rowsForVp[0]?.destination_vertiport || destId,
        bucket: 'arrival',
        value: roundNumber(avgWait, 1),
        description: '평균 도착 절차 대기시간(sec)',
      });
    }
  }
  return rows.sort((a, b) => Number(b.value) - Number(a.value)).slice(0, 24);
}

function buildAnalysisResourceEvents(flights) {
  const events = [];
  for (const flight of flights) {
    appendAnalysisResourceEvents(events, flight, 'departure', flight.origin_vertiport_id, flight.origin_vertiport, flight._departureSegments);
    appendAnalysisResourceEvents(events, flight, 'arrival', flight.destination_vertiport_id, flight.destination_vertiport, flight._arrivalSegments);
  }
  return events.sort((a, b) => Number(a.start_sec) - Number(b.start_sec));
}

function appendAnalysisResourceEvents(events, flight, phase, vertiportId, vertiportName, segments) {
  for (const segment of segments || []) {
    const resource = analysisSegmentResource(segment);
    const start = numberOrNull(segment.start);
    const end = numberOrNull(segment.end);
    if (!resource || start === null || end === null || end <= start) continue;
    events.push({
      vertiport_id: vertiportId,
      vertiport: vertiportName,
      phase,
      resource_type: resource.type,
      resource_id: resource.id,
      fpl_id: flight.fpl_id,
      aircraft_id: flight.aircraft_id,
      state: segment.state || '',
      description: segment.description || '',
      start_sec: roundNumber(start, 2),
      end_sec: roundNumber(end, 2),
      start_time: formatClockSeconds(start),
      end_time: formatClockSeconds(end),
      duration_sec: roundNumber(end - start, 2),
    });
  }
}

function analysisSegmentResource(segment) {
  if (segment.at?.id && ['gate', 'fato'].includes(segment.at.type)) {
    return { type: segment.at.type, id: segment.at.id };
  }
  return null;
}

function buildAnalysisSummary(live, flights, hourlyMetrics) {
  const passengers = flights.reduce((sum, f) => sum + (Number(f.passenger_count) || 0), 0);
  const seats = flights.reduce((sum, f) => sum + (Number(f.capacity) || 0), 0);
  const unserved = hourlyMetrics.reduce((sum, row) => sum + (Number(row.unserved) || 0), 0);
  return {
    flightCount: flights.length,
    servedPassengers: passengers,
    unservedPassengers: unserved,
    avgLoadFactor: seats ? passengers / seats : 0,
    avgGateToGateSec: average(flights.map((f) => Number(f.gate_to_gate_sec) || 0).filter(Boolean)),
  };
}

function populateAnalysisVertiportFilter(result) {
  const select = document.getElementById('analysis-vp-filter');
  if (!select) return;
  select.innerHTML = '<option value="">전체</option>' + (result.vertiports || [])
    .map((vp) => `<option value="${escapeHtml(vp.id)}">${escapeHtml(vp.name)}</option>`)
    .join('');
  select.disabled = false;
  select.value = '';
}

function renderAnalysisResult() {
  const result = state.analysis.result;
  const selectedId = state.analysis.selectedVertiportId || '';
  if (!result) return;
  const flights = selectedId ? result.flights.filter((f) => f.origin_vertiport_id === selectedId) : result.flights;
  const hourly = selectedId ? result.hourlyMetrics.filter((row) => row.vertiport_id === selectedId) : result.hourlyMetrics;
  const bottlenecks = selectedId ? result.bottlenecks.filter((row) => row.vertiport_id === selectedId) : result.bottlenecks;
  setText('analysis-m-flights', fmtNumber(flights.length));
  setText('analysis-m-served', fmtNumber(flights.reduce((sum, f) => sum + (Number(f.passenger_count) || 0), 0)));
  setText('analysis-m-unserved', fmtNumber(hourly.reduce((sum, row) => sum + (Number(row.unserved) || 0), 0)));
  setText('analysis-m-load', formatPercent(average(flights.map((f) => Number(f.load_factor) || 0))));
  setText('analysis-m-g2g', formatDuration(average(flights.map((f) => Number(f.gate_to_gate_sec) || 0).filter(Boolean))));
  setText('analysis-fpl-meta', `${selectedId ? '선택 버티포트' : '전체'} · ${fmtNumber(flights.length)}편`);
  renderAnalysisFlights(flights);
  renderAnalysisHourly(hourly);
  renderAnalysisTypes(selectedId ? buildAnalysisTypeMetrics(flights) : result.typeMetrics);
  renderAnalysisBottlenecks(bottlenecks);
  renderAnalysisGantt(result);
}

function renderAnalysisFlights(flights) {
  const tbody = document.getElementById('analysis-fpl-body');
  if (!tbody) return;
  if (!flights.length) {
    tbody.innerHTML = '<tr><td class="empty-row" colspan="14">출발 비행계획 없음</td></tr>';
    return;
  }
  tbody.innerHTML = flights.slice(0, 500).map((f) => `
    <tr>
      <td title="${escapeHtml(f.fpl_id)}">${escapeHtml(f.fpl_id)}</td>
      <td>${aircraftTypeChip(f.aircraft_type, f.aircraft_id)}</td>
      <td title="${escapeHtml(f.origin_vertiport)}">${escapeHtml(f.origin_vertiport)}</td>
      <td title="${escapeHtml(f.destination_vertiport)}">${escapeHtml(f.destination_vertiport)}</td>
      <td class="num">${fmtNumber(f.passenger_count)}/${fmtNumber(f.capacity)}</td>
      <td>${escapeHtml(f.departure_gate_id || '-')}</td>
      <td>${escapeHtml(f.departure_fato_id || '-')}</td>
      <td>${escapeHtml(f.arrival_gate_id || '-')}</td>
      <td>${escapeHtml(f.arrival_fato_id || '-')}</td>
      <td>${escapeHtml(f.gate_out_time || '-')}</td>
      <td>${escapeHtml(f.takeoff_time || '-')}</td>
      <td>${escapeHtml(f.landing_time || '-')}</td>
      <td>${escapeHtml(f.gate_in_time || '-')}</td>
      <td>${formatDuration(f.gate_to_gate_sec)}</td>
    </tr>
  `).join('');
}

function renderAnalysisHourly(rows) {
  const tbody = document.getElementById('analysis-hourly-body');
  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td class="empty-row" colspan="6">시간대별 결과 없음</td></tr>';
    return;
  }
  tbody.innerHTML = rows.slice(0, 500).map((row) => `
    <tr>
      <td>${escapeHtml(row.hour_label)}</td>
      <td>${escapeHtml(row.vertiport)}</td>
      <td class="num">${fmtNumber(row.requested)}</td>
      <td class="num">${fmtNumber(row.processed)}</td>
      <td class="num">${fmtNumber(row.unserved)}</td>
      <td class="num">${formatPercent(row.processing_rate)}</td>
    </tr>
  `).join('');
}

function renderAnalysisTypes(rows) {
  const tbody = document.getElementById('analysis-type-body');
  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td class="empty-row" colspan="5">타입별 결과 없음</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((row) => `
    <tr>
      <td>${aircraftTypeChip(row.aircraft_type, `${String(row.aircraft_type || '').slice(1)}인승`)}</td>
      <td class="num">${fmtNumber(row.flight_count)}</td>
      <td class="num">${fmtNumber(row.passenger_count)}</td>
      <td class="num">${fmtNumber(row.seat_supply)}</td>
      <td class="num">${formatPercent(row.avg_load_factor)}</td>
    </tr>
  `).join('');
}

function renderAnalysisBottlenecks(rows) {
  const tbody = document.getElementById('analysis-bottleneck-body');
  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td class="empty-row" colspan="5">병목 없음</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((row) => `
    <tr>
      <td>${escapeHtml(row.type)}</td>
      <td>${escapeHtml(row.vertiport)}</td>
      <td>${escapeHtml(row.bucket)}</td>
      <td class="num">${fmtNumber(row.value)}</td>
      <td>${escapeHtml(row.description)}</td>
    </tr>
  `).join('');
}

function renderAnalysisGantt(result) {
  const el = document.getElementById('analysis-gantt');
  if (!el) return;
  const selectedId = state.analysis.selectedVertiportId || '';
  const baseEvents = selectedId ? result.resourceEvents.filter((event) => event.vertiport_id === selectedId) : result.resourceEvents;
  const allEvents = baseEvents
    .filter((event) => ['gate', 'fato'].includes(event.resource_type))
    .sort((a, b) => Number(a.start_sec) - Number(b.start_sec));
  const events = allEvents.slice(0, MAX_ANALYSIS_GANTT_EVENTS);
  if (!events.length) {
    el.innerHTML = '<p class="empty-row">Gate/FATO 사용 구간 없음</p>';
    return;
  }
  const minRaw = Math.min(...events.map((event) => Number(event.start_sec)));
  const maxRaw = Math.max(...events.map((event) => Number(event.end_sec)));
  const min = Math.floor(minRaw / 3600) * 3600;
  const max = Math.ceil(maxRaw / 3600) * 3600;
  const span = Math.max(1, max - min);
  const timelineWidth = Math.max(1440, Math.ceil(span / 3600) * 220);
  const tickInterval = span > 36 * 3600 ? 2 * 3600 : 3600;
  const ticks = [];
  for (let t = min; t <= max; t += tickInterval) {
    ticks.push({
      left: ((t - min) / span) * 100,
      label: formatClockSeconds(t),
    });
  }
  const groups = groupBy(events, (event) => `${event.vertiport} · ${event.resource_type.toUpperCase()} ${event.resource_id}`);
  const rows = [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b, 'ko'))
    .map(([label, rowEvents]) => `
    <div class="gantt-row">
      <div class="gantt-label" title="${escapeHtml(label)}">${escapeHtml(label)}</div>
      <div class="gantt-track">
        ${rowEvents.map((event) => {
          const left = ((Number(event.start_sec) - min) / span) * 100;
          const width = Math.max(0.5, ((Number(event.end_sec) - Number(event.start_sec)) / span) * 100);
          const title = `${event.fpl_id} · ${analysisPhaseLabel(event.phase)} · ${event.state} · ${event.start_time}-${event.end_time}`;
          return `<span class="gantt-bar ${escapeHtml(event.resource_type)} ${escapeHtml(event.phase)}" style="left:${left}%;width:${width}%;" title="${escapeHtml(title)}"><em>${escapeHtml(event.fpl_id || '')}</em></span>`;
        }).join('')}
      </div>
    </div>
  `).join('');
  const vpLabel = selectedId ? (result.vertiports.find((vp) => vp.id === selectedId)?.name || selectedId) : '전체';
  const eventCountLabel = events.length < allEvents.length
    ? `${fmtNumber(events.length)}/${fmtNumber(allEvents.length)}`
    : fmtNumber(events.length);
  setText('analysis-gantt-meta', `${vpLabel} · Gate/FATO · ${formatClockSeconds(minRaw)} ~ ${formatClockSeconds(maxRaw)} · ${eventCountLabel}구간 · 가로 스크롤`);
  el.innerHTML = `
    <div class="gantt-legend">
      <span><i class="gate"></i>Gate</span>
      <span><i class="fato"></i>FATO</span>
    </div>
    <div class="gantt-scroll">
      <div class="gantt-inner" style="--gantt-width:${timelineWidth}px;">
        <div class="gantt-scale">
          <div class="gantt-scale-spacer">Resource</div>
          <div class="gantt-scale-track">
            ${ticks.map((tick) => `<span class="gantt-tick" style="left:${tick.left}%">${escapeHtml(tick.label)}</span>`).join('')}
          </div>
        </div>
        ${rows}
      </div>
    </div>
  `;
}

function analysisPhaseLabel(phase) {
  if (phase === 'departure') return '출발';
  if (phase === 'arrival') return '도착';
  return phase || '-';
}

async function saveAnalysisCsv() {
  const result = state.analysis.result;
  if (!result) return;
  const btn = document.getElementById('analysis-save-btn');
  if (btn) btn.disabled = true;
  setAnalysisStatus('CSV 저장 중...', 'busy');
  try {
    const payload = {
      scenarioId: result.scenarioId,
      scenarioDate: result.scenarioDate,
      summary: result.summary,
      flights: result.flights.map(({ _departureSegments, _arrivalSegments, ...row }) => row),
      hourlyMetrics: result.hourlyMetrics,
      typeMetrics: result.typeMetrics,
      bottlenecks: result.bottlenecks,
      resourceEvents: result.resourceEvents,
    };
    const manifest = await fetchJson('/api/analysis/exports', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    state.analysis.saveManifest = manifest;
    setText('analysis-save-path', manifest.primaryFplFile || manifest.exportDirectory || '저장 완료');
    setAnalysisStatus('CSV 저장 완료', 'success');
  } catch (err) {
    console.error(err);
    setAnalysisStatus('CSV 저장 실패', 'error');
    alert('CSV 저장 실패\n' + (err.message || err));
  } finally {
    if (btn) btn.disabled = false;
  }
}

function diffSeconds(end, start) {
  if (end === null || start === null) return '';
  return roundNumber(Math.max(0, end - start), 2);
}

function numberOrNull(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function sumSegmentDuration(segments, predicate) {
  return roundNumber((segments || []).reduce((sum, segment) => (
    predicate(segment) ? sum + Math.max(0, (Number(segment.end) || 0) - (Number(segment.start) || 0)) : sum
  ), 0), 2);
}

function average(values) {
  const clean = values.filter((value) => Number.isFinite(Number(value)));
  if (!clean.length) return 0;
  return clean.reduce((sum, value) => sum + Number(value), 0) / clean.length;
}

function roundNumber(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round((Number(value) || 0) * factor) / factor;
}

function formatPercent(value) {
  return `${roundNumber((Number(value) || 0) * 100, 1)}%`;
}

function formatDuration(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return '-';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return mins ? `${mins}m ${secs}s` : `${secs}s`;
}

function groupBy(items, keyFn) {
  const map = new Map();
  for (const item of items || []) {
    const key = keyFn(item);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return map;
}

/* ============================================================================
 * 6. Layout tab: layout editor and per-vertiport fleet assignment
 * ========================================================================== */

function setupLayoutWorkspace() {
  const canvas = document.getElementById('layout-canvas');
  const editor = window.LayoutEditor.create(canvas);
  state.layout.editor = editor;

  /* sub-mode nav */
  document.querySelectorAll('[data-layout-mode]').forEach((btn) => {
    btn.addEventListener('click', () => activateLayoutMode(btn.dataset.layoutMode));
  });

  /* tools */
  document.querySelectorAll('.tool-btn[data-tool]').forEach((btn) => {
    btn.addEventListener('click', () => editor.setTool(btn.dataset.tool));
  });

  /* editor actions */
  document.getElementById('library-new-btn').addEventListener('click', () => {
    editor.loadLayout(window.LayoutEditor.blankLayout('새 레이아웃'));
    state.layout.selectedLibraryName = null;
    document.getElementById('editor-name').value = '새-레이아웃';
    document.getElementById('editor-hint').hidden = true;
    rebuildLibraryList();
  });
  document.getElementById('editor-fit-btn').addEventListener('click', () => editor.fit());
  document.getElementById('editor-clear-btn').addEventListener('click', () => {
    if (!confirm('현재 레이아웃의 모든 객체를 삭제할까요?')) return;
    editor.clearLayout();
  });
  document.getElementById('editor-save-btn').addEventListener('click', saveCurrentLayout);
  document.getElementById('library-delete-btn').addEventListener('click', async () => {
    const name = state.layout.selectedLibraryName;
    if (!name) return;
    if (!confirm(`레이아웃 '${name}'을(를) 삭제할까요?`)) return;
    try {
      await fetchJson(`/api/layouts/${encodeURIComponent(name)}`, { method: 'DELETE' });
      state.layout.selectedLibraryName = null;
      state.layout.editor.loadLayout(window.LayoutEditor.blankLayout());
      document.getElementById('editor-name').value = '';
      document.getElementById('editor-hint').hidden = false;
      invalidateLayoutCache(name);
      await loadLayoutLibrary();
    } catch (err) { alert('삭제 실패: ' + err.message); }
  });

  /* file import: open file picker → parse → load into editor as new layout */
  document.getElementById('layout-import-btn').addEventListener('click', () => {
    document.getElementById('layout-import-input').click();
  });
  document.getElementById('layout-import-input').addEventListener('change', (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const layout = JSON.parse(String(ev.target.result || ''));
        const err = validateLayoutShape(layout);
        if (err) throw new Error(err);
        editor.loadLayout(layout);
        const baseName = (file.name || 'layout').replace(/\.json$/i, '');
        document.getElementById('editor-name').value = baseName;
        document.getElementById('editor-hint').hidden = true;
        state.layout.selectedLibraryName = null;
        rebuildLibraryList();
      } catch (e) {
        alert('파일 불러오기 실패\n' + (e.message || e));
      }
    };
    reader.readAsText(file, 'utf-8');
  });


  document.getElementById('grid-width').addEventListener('change', (e) => {
    editor.setGridSize(Number(e.target.value), editor.layout?.grid.height);
  });
  document.getElementById('grid-height').addEventListener('change', (e) => {
    editor.setGridSize(editor.layout?.grid.width, Number(e.target.value));
  });
  document.getElementById('grid-fit-btn').addEventListener('click', () => editor.fitGridToContent());

  /* inspector */
  document.getElementById('ent-name').addEventListener('input', (e) => editor.updateEntity(editor.selectedId, { name: e.target.value }));
  document.getElementById('ent-x').addEventListener('change', (e) => editor.updateEntity(editor.selectedId, { x: Number(e.target.value) }));
  document.getElementById('ent-y').addEventListener('change', (e) => editor.updateEntity(editor.selectedId, { y: Number(e.target.value) }));
  document.getElementById('ent-altitude').addEventListener('change', (e) => editor.updateEntity(editor.selectedId, { altitude: Number(e.target.value) }));
  document.getElementById('ent-fato-mode').addEventListener('change', (e) => editor.updateEntity(editor.selectedId, { fatoMode: e.target.value }));
  document.getElementById('ent-delete-btn').addEventListener('click', () => editor.deleteSelected());
  document.getElementById('link-delete-btn').addEventListener('click', () => editor.deleteSelected());

  editor.addEventListener('change', () => updateEditorUI());

  /* bulk apply (top of the assign list) */
  document.getElementById('bulk-apply-btn').addEventListener('click', () => {
    const counts = {
      a2: Math.max(0, Math.floor(Number(document.getElementById('bulk-a2').value) || 0)),
      a4: Math.max(0, Math.floor(Number(document.getElementById('bulk-a4').value) || 0)),
      a6: Math.max(0, Math.floor(Number(document.getElementById('bulk-a6').value) || 0)),
      a8: Math.max(0, Math.floor(Number(document.getElementById('bulk-a8').value) || 0)),
    };
    applyBulkCounts(counts);
  });
  document.getElementById('bulk-default-btn').addEventListener('click', () => {
    /* "all 4인승" — let each vp use its own gate count, distribute 4인승 to fill */
    applyBulkCounts(null);
  });

  document.getElementById('bulk-layout-apply-btn')?.addEventListener('click', () => {
    const layoutName = document.getElementById('bulk-layout-select')?.value || '';
    applyBulkLayout(layoutName);
  });

  activateLayoutMode(DEFAULT_LAYOUT_MODE);
}

async function applyBulkCounts(counts) {
  const targets = state.vertiports.filter((vp) => state.layout.configsByVp[vp.id]?.layoutName);
  if (!targets.length) {
    setAssignStatus('레이아웃이 배정된 버티포트가 없습니다.', 'error');
    return;
  }
  const total = counts ? totalAircraftCount(counts) : -1;
  const summary = counts
    ? `${total}대 (2:${counts.a2} / 4:${counts.a4} / 6:${counts.a6} / 8:${counts.a8})`
    : '모든 게이트 4인승';
  if (!confirm(`레이아웃 배정된 ${targets.length}개 버티포트에 일괄 적용\n${summary}\n계속할까요?`)) return;

  setAssignStatus(`일괄 적용 중... (0/${targets.length})`, 'busy');
  let done = 0;
  for (const vp of targets) {
    const layoutName = state.layout.configsByVp[vp.id]?.layoutName;
    const layout = await fetchLayoutCached(layoutName);
    if (!layout) { done += 1; continue; }
    const gates = layout.entities.filter((e) => e.type === 'gate');
    const useCounts = counts ?? defaultCountsForGateCount(gates.length);
    const assignments = distributeAircraftToGates(useCounts, gates);
    const cfg = {
      vertiportId: vp.id,
      layoutName,
      fleet: { gateAssignments: assignments },
    };
    try {
      const saved = await fetchJson(`/api/vertiport-configs/${encodeURIComponent(vp.id)}`, {
        method: 'PUT', body: JSON.stringify(cfg),
      });
      state.layout.configsByVp[vp.id] = saved;
    } catch (err) { console.error('bulk apply failed for', vp.id, err); }
    done += 1;
    if (done % 4 === 0 || done === targets.length) {
      setAssignStatus(`일괄 적용 중... (${done}/${targets.length})`, 'busy');
    }
  }
  rebuildAssignVpList();
  rebuildSimVertiportStatus();
  setAssignStatus(`일괄 적용 완료 · ${targets.length}개`, 'success');
}

async function applyBulkLayout(layoutName) {
  const selectedLayout = String(layoutName || '').trim();
  if (!selectedLayout) {
    setAssignStatus('일괄 적용할 레이아웃을 선택하세요.', 'error');
    return;
  }
  const layout = await fetchLayoutCached(selectedLayout);
  if (!layout) {
    setAssignStatus(`레이아웃을 불러오지 못했습니다: ${selectedLayout}`, 'error');
    return;
  }
  const targets = state.vertiports || [];
  if (!targets.length) {
    setAssignStatus('적용할 버티포트가 없습니다.', 'error');
    return;
  }
  const gates = sortLayoutGates((layout.entities || []).filter((entity) => entity.type === 'gate'));
  const summary = gates.length
    ? `${selectedLayout} / Gate ${gates.length}개 / 기존 배정 유지, 없으면 기본 4인승`
    : `${selectedLayout} / Gate 없음`;
  if (!confirm(`모든 버티포트 ${targets.length}개에 레이아웃을 일괄 배정합니다.\n${summary}\n계속할까요?`)) return;

  setAssignStatus(`레이아웃 일괄 배정 중... (0/${targets.length})`, 'busy');
  let done = 0;
  let failed = 0;
  for (const vp of targets) {
    const cfg = buildVpConfigForLayout(vp.id, selectedLayout, layout, state.layout.configsByVp[vp.id]);
    try {
      const saved = await fetchJson(`/api/vertiport-configs/${encodeURIComponent(vp.id)}`, {
        method: 'PUT',
        body: JSON.stringify(cfg),
      });
      state.layout.configsByVp[vp.id] = saved;
    } catch (err) {
      failed += 1;
      console.error('bulk layout apply failed for', vp.id, err);
    }
    done += 1;
    if (done % 4 === 0 || done === targets.length) {
      setAssignStatus(`레이아웃 일괄 배정 중... (${done}/${targets.length})`, 'busy');
      await sleep(0);
    }
  }
  rebuildAssignVpList();
  rebuildSimVertiportStatus();
  refreshBulkLayoutSelect(selectedLayout);
  setAssignStatus(
    failed
      ? `레이아웃 일괄 배정 완료 · 실패 ${failed}개`
      : `레이아웃 일괄 배정 완료 · ${targets.length}개`,
    failed ? 'error' : 'success'
  );
}

function buildVpConfigForLayout(vpId, layoutName, layout, previousConfig = null) {
  const gates = sortLayoutGates((layout?.entities || []).filter((entity) => entity.type === 'gate'));
  const gateIds = new Set(gates.map((gate) => gate.id));
  const previousAssignments = previousConfig?.fleet?.gateAssignments || {};
  const cleaned = {};
  for (const [gateId, assignment] of Object.entries(previousAssignments)) {
    if (gateIds.has(gateId) && assignment) cleaned[gateId] = assignment;
  }
  const gateAssignments = Object.keys(cleaned).length || !gates.length
    ? normalizeGateAssignments(cleaned, gates)
    : distributeAircraftToGates(defaultCountsForGateCount(gates.length), gates);
  return {
    vertiportId: vpId,
    layoutName: layoutName || null,
    fleet: { gateAssignments },
  };
}

function activateLayoutMode(name) {
  state.layoutMode = name;
  document.querySelectorAll('[data-layout-mode]').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.layoutMode === name);
  });
  document.querySelectorAll('[data-layout-mode-view]').forEach((view) => {
    view.classList.toggle('active', view.dataset.layoutModeView === name);
  });
  document.querySelectorAll('[data-layout-side]').forEach((side) => {
    side.hidden = side.dataset.layoutSide !== name;
  });
  if (name === 'editor') requestAnimationFrame(() => state.layout.editor?.resize());
}

/* Lightweight shape check before handing a parsed JSON to the editor.
 * The Python vp_sim has full validation; this is just the bare minimum to
 * avoid loading garbage that would crash the canvas renderer. */
const VALID_ENTITY_TYPES = new Set(['gate', 'fato', 'node', 'takeoffPoint', 'landingPoint', 'commonAirPoint']);
function validateLayoutShape(layout) {
  if (!layout || typeof layout !== 'object') return '레이아웃 객체가 아닙니다.';
  if (!Array.isArray(layout.entities)) return 'entities 배열이 없습니다.';
  if (!Array.isArray(layout.links)) return 'links 배열이 없습니다.';
  const ids = new Set();
  for (const e of layout.entities) {
    if (!e || typeof e !== 'object') return 'entity 항목이 객체가 아닙니다.';
    if (!e.id) return 'entity 에 id 가 없습니다.';
    if (ids.has(e.id)) return `중복된 entity id: ${e.id}`;
    ids.add(e.id);
    if (!VALID_ENTITY_TYPES.has(e.type)) return `알 수 없는 entity type: ${e.type}`;
    if (!Number.isFinite(Number(e.x)) || !Number.isFinite(Number(e.y))) {
      return `entity '${e.id}' 의 x/y 가 숫자가 아닙니다.`;
    }
  }
  for (const l of layout.links) {
    if (!l || typeof l !== 'object') return 'link 항목이 객체가 아닙니다.';
    if (!l.id || !l.from || !l.to) return 'link 에 id/from/to 가 없습니다.';
    if (!ids.has(l.from) || !ids.has(l.to)) return `link '${l.id}' 가 없는 entity 를 참조합니다.`;
  }
  return null;
}

/* Layout library CRUD: manages reusable vertiport layout JSON definitions. */
async function loadLayoutLibrary() {
  try {
    const [res, info] = await Promise.all([
      fetchJson('/api/layouts'),
      fetchJson('/api/layouts/_info').catch(() => null),
    ]);
    state.layout.library = res.items || [];
    if (info?.directory) {
      const hint = document.getElementById('save-path-hint');
      if (hint) hint.textContent = `저장 위치: ${info.directory}`;
      hint?.setAttribute('title', info.directory);
      state.layout.saveDirectory = info.directory;
    }
    rebuildLibraryList();
    refreshBulkLayoutSelect();
    /* refresh assign rows so their layout dropdowns show new/removed entries */
    refreshAssignDropdowns();
  } catch (err) {
    console.error('layout library load failed', err);
  }
}

function rebuildLibraryList() {
  /* Render layouts as a horizontal chip strip in the editor header. */
  const strip = document.getElementById('library-chips');
  if (!strip) return;
  strip.innerHTML = '';
  if (!state.layout.library.length) {
    const empty = document.createElement('span');
    empty.className = 'library-empty';
    empty.textContent = '저장된 레이아웃 없음';
    strip.appendChild(empty);
  } else {
    for (const item of state.layout.library) {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'lib-chip';
      chip.dataset.name = item.name;
      if (state.layout.selectedLibraryName === item.name) chip.classList.add('is-selected');
      chip.innerHTML = `
        <span class="chip-name"></span>
        <span class="chip-count"></span>
      `;
      chip.querySelector('.chip-name').textContent = item.displayName || item.name;
      chip.querySelector('.chip-count').textContent = `${item.entityCount}개체`;
      chip.addEventListener('click', () => loadLayoutFromLibrary(item.name));
      strip.appendChild(chip);
    }
  }
  /* Show/hide the contextual delete button. */
  const delBtn = document.getElementById('library-delete-btn');
  if (delBtn) {
    delBtn.hidden = !state.layout.selectedLibraryName;
  }
}

async function loadLayoutFromLibrary(name) {
  try {
    const layout = await fetchJson(`/api/layouts/${encodeURIComponent(name)}`);
    state.layout.editor.loadLayout(layout);
    state.layout.selectedLibraryName = name;
    document.getElementById('editor-name').value = name;
    document.getElementById('editor-hint').hidden = true;
    rebuildLibraryList();
  } catch (err) { alert('레이아웃 불러오기 실패: ' + err.message); }
}

async function saveCurrentLayout() {
  const editor = state.layout.editor;
  if (!editor.layout) { alert('저장할 레이아웃이 없습니다.'); return; }
  const nameInput = document.getElementById('editor-name');
  const name = (nameInput.value || '').trim();
  if (!name) { alert('레이아웃 이름을 입력하세요.'); nameInput.focus(); return; }
  if (/[\\/]|\.\./.test(name)) { alert('이름에 / \\ .. 사용 불가'); return; }
  const payload = editor.serialize();
  payload.meta = { ...(payload.meta || {}), name };
  try {
    await fetchJson(`/api/layouts/${encodeURIComponent(name)}`, {
      method: 'PUT', body: JSON.stringify(payload),
    });
    editor.markSaved();
    state.layout.selectedLibraryName = name;
    invalidateLayoutCache(name);
    flashSavePathHint(name);
    await loadLayoutLibrary();
  } catch (err) { alert('저장 실패: ' + err.message); }
}

function flashSavePathHint(name) {
  const hint = document.getElementById('save-path-hint');
  if (!hint) return;
  const dir = state.layout.saveDirectory || 'backend/data/layouts';
  hint.classList.add('is-saved');
  hint.textContent = `✓ 저장됨: ${dir}\\${name}.json`;
  clearTimeout(flashSavePathHint._t);
  flashSavePathHint._t = setTimeout(() => {
    hint.classList.remove('is-saved');
    hint.textContent = `저장 위치: ${dir}`;
  }, 4000);
}

function updateEditorUI() {
  const editor = state.layout.editor;
  /* tool buttons */
  document.querySelectorAll('.tool-btn[data-tool]').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tool === editor.tool);
  });
  /* dirty badge */
  document.getElementById('editor-dirty').hidden = !editor.dirty;
  /* grid inputs */
  if (editor.layout) {
    document.getElementById('grid-width').value = editor.layout.grid.width;
    document.getElementById('grid-height').value = editor.layout.grid.height;
  }
  /* stats */
  if (editor.layout) {
    setText('stat-gate', editor.layout.entities.filter((e) => e.type === 'gate').length);
    setText('stat-fato', editor.layout.entities.filter((e) => e.type === 'fato').length);
    setText('stat-node', editor.layout.entities.filter((e) => e.type === 'node').length);
    setText('stat-takeoff', editor.layout.entities.filter((e) => e.type === 'takeoffPoint').length);
    setText('stat-landing', editor.layout.entities.filter((e) => e.type === 'landingPoint').length);
    setText('stat-common-air', editor.layout.entities.filter((e) => e.type === 'commonAirPoint').length);
    setText('stat-link', editor.layout.links.length);
  }
  /* inspector */
  const ent = editor.selectedEntity;
  const link = editor.selectedLink;
  const empty = document.getElementById('inspector-empty');
  const entIns = document.getElementById('entity-inspector');
  const linkIns = document.getElementById('link-inspector');
  if (ent) {
    empty.hidden = true; entIns.hidden = false; linkIns.hidden = true;
    document.getElementById('ent-name').value = ent.name || '';
    document.getElementById('ent-x').value = ent.x;
    document.getElementById('ent-y').value = ent.y;
    const altWrap = document.getElementById('ent-altitude-wrap');
    if (isLayoutAirPoint(ent.type)) {
      altWrap.hidden = false;
      document.getElementById('ent-altitude').value = ent.altitude ?? 0;
    } else { altWrap.hidden = true; }
    const fmWrap = document.getElementById('ent-fato-mode-wrap');
    if (ent.type === 'fato') {
      fmWrap.hidden = false;
      document.getElementById('ent-fato-mode').value = ent.fatoMode || 'both';
    } else { fmWrap.hidden = true; }
  } else if (link) {
    empty.hidden = true; entIns.hidden = true; linkIns.hidden = false;
    const map = new Map(editor.layout.entities.map((e) => [e.id, e]));
    const a = map.get(link.from); const b = map.get(link.to);
    document.getElementById('link-endpoints').textContent = `${a?.name || link.from} ↔ ${b?.name || link.to}`;
    const dist = (a && b) ? Math.round(Math.hypot(a.x - b.x, a.y - b.y)) : 0;
    document.getElementById('link-distance').textContent = `${dist} m`;
  } else {
    empty.hidden = false; entIns.hidden = true; linkIns.hidden = true;
  }
}

/* ---------- vp assignment ---------- */
/* Vertiport assignment data: for each vertiport, store selected layout plus
 * gate-by-gate aircraft type assignments used by live simulation. */
async function loadVertiportConfigs() {
  try {
    const res = await fetchJson('/api/vertiport-configs');
    const map = {};
    for (const item of res.items || []) {
      map[item.vertiportId] = item;
    }
    state.layout.configsByVp = map;
  } catch (err) { console.error('vp configs load failed', err); }
}

/* ----- vertical accordion list of vertiports for the assign mode -----
 * Each row is a vertiport. Click to expand. Inside: layout dropdown + fleet
 * grid. Layout/fleet changes auto-save on every edit (PUT /api/vertiport-configs/{id}).
 */
function rebuildAssignVpList() {
  const list = document.getElementById('assign-list');
  if (!list) return;
  list.innerHTML = '';
  if (!state.vertiports.length) {
    list.innerHTML = '<p class="panel-empty">버티포트가 없습니다.</p>';
    return;
  }
  /* Single-expanded accordion: track at most one open row across re-renders. */
  const openId = state.layout.expandedAssignVpId || null;
  for (const vp of state.vertiports) {
    list.appendChild(buildAssignRow(vp, openId === vp.id));
  }
}

function buildAssignRow(vp, startExpanded) {
  const cfg = state.layout.configsByVp[vp.id];
  const layoutName = cfg?.layoutName || '';
  const assignmentCount = Object.values(cfg?.fleet?.gateAssignments || {}).filter(Boolean).length;

  const row = document.createElement('div');
  row.className = `assign-row${vp.class === 'hub' ? ' hub' : ''}`;
  row.dataset.vpId = vp.id;
  if (startExpanded) row.classList.add('is-expanded');

  const header = document.createElement('div');
  header.className = 'assign-row-header';
  header.innerHTML = `
    <span class="assign-caret">▶</span>
    <span class="assign-row-name">
      <span class="assign-row-pin"></span>
      <span class="assign-row-name-text"></span>
    </span>
    <span class="assign-row-tag">${vp.class === 'hub' ? 'HUB' : 'PORT'}</span>
    <span class="assign-row-meta">
      <span>레이아웃: ${
        layoutName
          ? `<strong></strong>`
          : `<strong class="miss-text">미배정</strong>`
      }</span>
      <span>기체: <strong>${assignmentCount}대</strong></span>
    </span>
    <span class="assign-row-status">
      <span class="status-cell ${layoutName ? 'ok' : 'miss'}" title="레이아웃"><span class="status-dot"></span>L</span>
      <span class="status-cell ${assignmentCount > 0 ? 'ok' : 'miss'}" title="기체"><span class="status-dot"></span>A</span>
    </span>
  `;
  header.querySelector('.assign-row-name-text').textContent = vp.name;
  if (layoutName) {
    header.querySelector('.assign-row-meta strong').textContent = layoutName;
  }
  header.addEventListener('click', () => toggleAssignRow(vp.id));

  const body = document.createElement('div');
  body.className = 'assign-row-body';
  body.innerHTML = `
    <div class="assign-row-layout-field">
      <label>레이아웃</label>
      <select class="row-layout-select"></select>
      <button class="ghost-btn small row-default-btn" type="button" title="모든 게이트를 기본값(4인승)으로 채움">기본값(모두 4인승)</button>
    </div>
    <div class="assign-row-fleet"></div>
  `;
  const select = body.querySelector('.row-layout-select');
  populateLayoutSelect(select, layoutName);
  select.addEventListener('change', (event) => onRowLayoutChange(vp.id, event.target.value));
  body.querySelector('.row-default-btn').addEventListener('click', () => applyDefaultFleet(vp.id));

  row.appendChild(header);
  row.appendChild(body);

  if (startExpanded) renderRowFleet(row, vp.id, layoutName);
  return row;
}

function populateLayoutSelect(select, currentName) {
  const opts = state.layout.library.map((l) =>
    `<option value="${escapeHtml(l.name)}" ${currentName === l.name ? 'selected' : ''}>${escapeHtml(l.displayName || l.name)}</option>`
  ).join('');
  select.innerHTML = `<option value="">— 미배정 —</option>${opts}`;
}

function refreshBulkLayoutSelect(preferredName = '') {
  const select = document.getElementById('bulk-layout-select');
  if (!select) return;
  const current = preferredName || select.value || '';
  populateLayoutSelect(select, current);
  if (current && [...select.options].some((option) => option.value === current)) {
    select.value = current;
  }
}

async function toggleAssignRow(vpId) {
  const row = findAssignRow(vpId);
  if (!row) return;
  const wasOpen = row.classList.contains('is-expanded');

  /* Single-expanded accordion: close every other row before opening this one. */
  document.querySelectorAll('.assign-row.is-expanded').forEach((other) => {
    if (other !== row) other.classList.remove('is-expanded');
  });

  if (wasOpen) {
    row.classList.remove('is-expanded');
    state.layout.expandedAssignVpId = null;
    return;
  }
  row.classList.add('is-expanded');
  state.layout.expandedAssignVpId = vpId;
  const layoutName = state.layout.configsByVp[vpId]?.layoutName || '';
  if (layoutName) await renderRowFleet(row, vpId, layoutName);
  else row.querySelector('.assign-row-fleet').innerHTML = '<p class="fleet-empty-note">레이아웃을 선택하면 게이트별 기체 슬롯이 표시됩니다.</p>';
  /* Keep the expanded controls visible even when the row was near the bottom
   * of the scroll area. `nearest` can leave the lower controls clipped. */
  row.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

async function onRowLayoutChange(vpId, layoutName) {
  const prev = state.layout.configsByVp[vpId];
  let cfg = {
    vertiportId: vpId,
    layoutName: layoutName || null,
    fleet: { gateAssignments: { ...(prev?.fleet?.gateAssignments || {}) } },
  };

  if (layoutName) {
    const layout = await fetchLayoutCached(layoutName);
    if (layout) {
      const gates = layout.entities.filter((e) => e.type === 'gate');
      const gateIds = new Set(gates.map((e) => e.id));
      /* keep only assignments that map to current layout's gates */
      const cleaned = {};
      for (const [k, v] of Object.entries(cfg.fleet.gateAssignments)) {
        if (gateIds.has(k) && v) cleaned[k] = v;
      }
      /* if no fleet was carried over, seed with all-4인승 default */
      if (Object.keys(cleaned).length === 0 && gates.length > 0) {
        cfg.fleet.gateAssignments = distributeAircraftToGates(
          defaultCountsForGateCount(gates.length),
          gates,
        );
      } else {
        cfg.fleet.gateAssignments = cleaned;
      }
    }
  } else {
    cfg.fleet.gateAssignments = {};
  }
  await persistVpConfig(vpId, cfg);
  const row = findAssignRow(vpId);
  if (row) {
    if (layoutName) await renderRowFleet(row, vpId, layoutName);
    else row.querySelector('.assign-row-fleet').innerHTML = '<p class="fleet-empty-note">레이아웃을 선택하면 기체 카운트가 표시됩니다.</p>';
    refreshAssignRowHeader(row, vpId);
  }
}

async function renderRowFleet(row, vpId, layoutName) {
  const wrap = row.querySelector('.assign-row-fleet');
  if (!layoutName) {
    wrap.innerHTML = '<p class="fleet-empty-note">레이아웃 미배정</p>';
    return;
  }
  const layout = await fetchLayoutCached(layoutName);
  if (!layout) {
    wrap.innerHTML = '<p class="fleet-empty-note">레이아웃 불러오기 실패</p>';
    return;
  }
  const gates = sortLayoutGates((layout.entities || []).filter((e) => e.type === 'gate'));
  if (!gates.length) {
    wrap.innerHTML = '<p class="fleet-empty-note">이 레이아웃엔 게이트가 없습니다.</p>';
    return;
  }
  const cfg = state.layout.configsByVp[vpId];
  let assignments = normalizeGateAssignments(cfg?.fleet?.gateAssignments || {}, gates);
  const counts = aircraftCountsFromAssignments(assignments);
  const totalGates = gates.length;
  const totalUsed = totalAircraftCount(counts);

  wrap.innerHTML = `
    <div class="fleet-assignment-editor">
      <section class="fleet-control-panel">
        <div class="fleet-counts">
          <div class="fleet-counts-header">
            <div>
              <span class="fleet-counts-title">인승별 대수 적용</span>
              <span class="fleet-counts-note">2/4/6/8인승 대수를 입력하고 적용하면 Gate 순서대로 자동 배치됩니다.</span>
            </div>
            <div class="fleet-counts-actions">
              <span class="fleet-counts-total">총 <strong>${totalUsed}</strong> / ${totalGates} 대</span>
              <button class="primary-btn small row-apply-counts-btn" type="button">인승별 적용</button>
            </div>
          </div>
          <div class="fleet-counts-grid">
            ${AIRCRAFT_TYPES.map((t) => `
              <label class="count-cell">
                <span class="count-label">${t.label}</span>
                <input class="count-input fleet-count-input" type="number" min="0" data-type="${t.id}" value="${counts[t.id]}" />
              </label>
            `).join('')}
          </div>
          <p class="fleet-warn" hidden>총 대수가 Gate 수(${totalGates})를 초과합니다. 적용 시 앞 타입부터 ${totalGates}대까지만 배치됩니다.</p>
        </div>

        <div class="gate-assignment-panel">
        <div class="gate-assignment-head">
          <div>
            <span class="fleet-counts-title">Gate별 직접 지정</span>
            <span class="fleet-counts-note">각 Gate의 기체 타입을 직접 바꾸면 즉시 저장됩니다. 비움은 해당 Gate에 초기 기체를 두지 않습니다.</span>
          </div>
        </div>
        <div class="gate-assignment-grid">
          ${gates.map((gate) => `
            <label class="gate-assignment-cell">
              <span class="gate-assignment-name">${escapeHtml(gate.name || gate.id)}</span>
              <span class="gate-assignment-id">${escapeHtml(gate.id)}</span>
              <select class="gate-type-select" data-gate-id="${escapeHtml(gate.id)}">
                ${renderGateTypeOptions(assignments[gate.id]?.typeId || '')}
              </select>
            </label>
          `).join('')}
        </div>
        </div>
      </section>

      <section class="gate-layout-panel">
        <div class="gate-assignment-head">
          <div>
            <span class="fleet-counts-title">레이아웃 / 배치 상태</span>
            <span class="fleet-counts-note">선택된 레이아웃의 Link, FATO, Gate와 Gate별 초기 기체 배치 상태입니다.</span>
          </div>
        </div>
        <div class="layout-state-strip">${renderFleetCountChips(counts)}</div>
        ${renderGateAssignmentMap(layout, gates, assignments)}
      </section>
    </div>
  `;

  const readCountInputs = (normalizeValues = true) => {
    const newCounts = emptyAircraftCounts();
    wrap.querySelectorAll('.fleet-count-input').forEach((inp) => {
      const v = Math.max(0, Math.floor(Number(inp.value) || 0));
      newCounts[inp.dataset.type] = v;
      if (normalizeValues) inp.value = String(v);
    });
    return newCounts;
  };
  const writeCountInputs = (nextCounts) => {
    wrap.querySelectorAll('.fleet-count-input').forEach((inp) => {
      inp.value = String(nextCounts[inp.dataset.type] ?? 0);
    });
  };
  const updateTotal = (nextCounts) => {
    wrap.querySelector('.fleet-counts-total strong').textContent = String(totalAircraftCount(nextCounts));
    const stateStrip = wrap.querySelector('.layout-state-strip');
    if (stateStrip) stateStrip.innerHTML = renderFleetCountChips(nextCounts);
  };
  const updateWarn = (nextCounts) => {
    const warn = wrap.querySelector('.fleet-warn');
    if (warn) warn.hidden = totalAircraftCount(nextCounts) <= totalGates;
  };
  const clampCountsToGateCount = (nextCounts) => {
    const clamped = { ...nextCounts };
    if (totalAircraftCount(clamped) > totalGates) {
      let remaining = totalGates;
      for (const t of AIRCRAFT_TYPES) {
        const take = Math.min(clamped[t.id], remaining);
        clamped[t.id] = take;
        remaining -= take;
      }
    }
    return clamped;
  };
  const syncGateControls = (nextAssignments) => {
    assignments = normalizeGateAssignments(nextAssignments, gates);
    wrap.querySelectorAll('.gate-type-select').forEach((select) => {
      select.value = assignments[select.dataset.gateId]?.typeId || '';
    });
    wrap.querySelectorAll('.gate-map-gate').forEach((marker) => {
      const typeId = assignments[marker.dataset.gateId]?.typeId || '';
      const type = aircraftTypeById(typeId);
      marker.dataset.type = typeId || 'empty';
      marker.setAttribute('class', `gate-map-gate ${typeId || 'empty'}`);
      const typeLabel = marker.querySelector('.gate-map-type');
      if (typeLabel) typeLabel.textContent = type ? `${type.seats}인` : '비움';
      const title = marker.querySelector('title');
      if (title) title.textContent = `${marker.dataset.gateName || marker.dataset.gateId} · ${type ? type.label : '비움'}`;
    });
  };
  const collectGateAssignments = () => {
    const nextAssignments = {};
    wrap.querySelectorAll('.gate-type-select').forEach((select) => {
      const assignment = assignmentForAircraftType(select.value);
      if (assignment) nextAssignments[select.dataset.gateId] = assignment;
    });
    return nextAssignments;
  };
  const applyCounts = async () => {
    const rawCounts = readCountInputs();
    updateWarn(rawCounts);
    const nextCounts = clampCountsToGateCount(rawCounts);
    writeCountInputs(nextCounts);
    updateTotal(nextCounts);
    const nextAssignments = distributeAircraftToGates(nextCounts, gates);
    syncGateControls(nextAssignments);
    await persistGateAssignments(vpId, layout, nextAssignments);
  };
  const applyGateSelects = async () => {
    const nextAssignments = collectGateAssignments();
    syncGateControls(nextAssignments);
    const nextCounts = aircraftCountsFromAssignments(nextAssignments);
    writeCountInputs(nextCounts);
    updateTotal(nextCounts);
    updateWarn(nextCounts);
    await persistGateAssignments(vpId, layout, nextAssignments);
  };

  wrap.querySelectorAll('.fleet-count-input').forEach((inp) => {
    inp.addEventListener('input', () => {
      const nextCounts = readCountInputs(false);
      updateTotal(nextCounts);
      updateWarn(nextCounts);
    });
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); applyCounts(); inp.blur(); }
    });
  });
  wrap.querySelector('.row-apply-counts-btn')?.addEventListener('click', applyCounts);
  wrap.querySelectorAll('.gate-type-select').forEach((select) => {
    select.addEventListener('change', applyGateSelects);
  });
  wrap.querySelectorAll('.gate-map-gate').forEach((marker) => {
    marker.addEventListener('click', () => {
      const select = [...wrap.querySelectorAll('.gate-type-select')]
        .find((item) => item.dataset.gateId === marker.dataset.gateId);
      if (select) {
        select.focus();
        select.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    });
  });
}

/* Assignment preview: draw the actual layout geometry and overlay aircraft type
 * chosen for each gate so users can verify placement before simulation. */
function renderGateAssignmentMap(layout, gates, assignments) {
  const grid = layout?.grid || {};
  const width = Number(grid.width) > 0 ? Number(grid.width) : 1000;
  const height = Number(grid.height) > 0 ? Number(grid.height) : 720;
  const entities = layout?.entities || [];
  const entityMap = new Map(entities.map((entity) => [entity.id, entity]));
  const links = (layout?.links || []).map((link) => {
    const from = entityMap.get(link.from);
    const to = entityMap.get(link.to);
    if (!from || !to) return '';
    const airLink = isLayoutAirPoint(from.type) || isLayoutAirPoint(to.type);
    return `<line class="layout-map-link ${airLink ? 'air' : 'ground'}" x1="${Number(from.x) || 0}" y1="${Number(from.y) || 0}" x2="${Number(to.x) || 0}" y2="${Number(to.y) || 0}" />`;
  }).join('');
  const nodes = entities.filter((entity) => entity.type === 'node').map((entity) => (
    `<circle class="layout-map-node" cx="${Number(entity.x) || 0}" cy="${Number(entity.y) || 0}" r="6"><title>${escapeHtml(entity.name || entity.id)}</title></circle>`
  )).join('');
  const fatos = entities.filter((entity) => entity.type === 'fato').map((entity) => (
    `<g class="layout-map-fato" transform="translate(${Number(entity.x) || 0} ${Number(entity.y) || 0})">
      <rect x="-34" y="-18" width="68" height="36" rx="9"></rect>
      <text y="4">${escapeHtml(entity.name || entity.id)}</text>
      <title>${escapeHtml(`${entity.name || entity.id} · ${entity.fatoMode || 'both'}`)}</title>
    </g>`
  )).join('');
  const airPoints = entities.filter((entity) => isLayoutAirPoint(entity.type)).map((entity) => (
    `<g class="layout-map-airpoint ${entity.type}" transform="translate(${Number(entity.x) || 0} ${Number(entity.y) || 0})">
      <circle r="8"></circle>
      <text y="-12">${escapeHtml(layoutAirPointLabel(entity.type))}</text>
      <title>${escapeHtml(entity.name || entity.id)}</title>
    </g>`
  )).join('');
  const markers = gates.map((gate) => {
    const typeId = assignments[gate.id]?.typeId || '';
    const type = aircraftTypeById(typeId);
    const gateLabel = gate.name || gate.id;
    return `
      <g
        class="gate-map-gate ${escapeHtml(typeId || 'empty')}"
        data-gate-id="${escapeHtml(gate.id)}"
        data-gate-name="${escapeHtml(gateLabel)}"
        data-type="${escapeHtml(typeId || 'empty')}"
        transform="translate(${Number(gate.x) || 0} ${Number(gate.y) || 0})"
        tabindex="0"
        role="button"
      >
        <rect x="-38" y="-22" width="76" height="44" rx="10"></rect>
        <text class="gate-map-name" y="-4">${escapeHtml(gate.name || gate.id)}</text>
        <text class="gate-map-type" y="12">${escapeHtml(type ? `${type.seats}인` : '비움')}</text>
        <title>${escapeHtml(`${gateLabel} · ${type ? type.label : '비움'}`)}</title>
      </g>
    `;
  }).join('');
  return `
    <div class="gate-layout-map" aria-label="Gate 배치도">
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img">
        <rect class="layout-map-bg" x="0" y="0" width="${width}" height="${height}" rx="18"></rect>
        <g class="layout-map-grid">
          ${renderLayoutGridLines(width, height, Number(grid.size) || 100)}
        </g>
        <g class="layout-map-links">${links}</g>
        <g class="layout-map-nodes">${nodes}</g>
        <g class="layout-map-airpoints">${airPoints}</g>
        <g class="layout-map-fatos">${fatos}</g>
        <g class="layout-map-gates">${markers}</g>
      </svg>
    </div>
  `;
}

function isLayoutAirPoint(type) {
  return type === 'takeoffPoint' || type === 'landingPoint' || type === 'commonAirPoint';
}

function layoutAirPointLabel(type) {
  if (type === 'takeoffPoint') return 'T';
  if (type === 'landingPoint') return 'L';
  return 'C';
}

function renderLayoutGridLines(width, height, rawStep) {
  const step = Math.max(80, Math.min(160, Number(rawStep) * 5 || 100));
  const lines = [];
  for (let x = step; x < width; x += step) {
    lines.push(`<line x1="${x}" y1="0" x2="${x}" y2="${height}"></line>`);
  }
  for (let y = step; y < height; y += step) {
    lines.push(`<line x1="0" y1="${y}" x2="${width}" y2="${y}"></line>`);
  }
  return lines.join('');
}

function renderFleetCountChips(counts) {
  return AIRCRAFT_TYPES.map((type) => (
    `<span class="layout-state-chip ${type.id}">${type.label} <strong>${fmtNumber(counts[type.id] || 0)}</strong></span>`
  )).join('');
}

function renderGateTypeOptions(currentTypeId) {
  return [
    `<option value="" ${currentTypeId ? '' : 'selected'}>비움</option>`,
    ...AIRCRAFT_TYPES.map((type) => (
      `<option value="${type.id}" ${currentTypeId === type.id ? 'selected' : ''}>${type.label}</option>`
    )),
  ].join('');
}

async function persistRowFleet(vpId, layout, counts) {
  const gates = sortLayoutGates((layout?.entities || []).filter((e) => e.type === 'gate'));
  const assignments = distributeAircraftToGates(counts, gates);
  await persistGateAssignments(vpId, layout, assignments);
}

async function persistGateAssignments(vpId, layout, assignments) {
  const current = state.layout.configsByVp[vpId];
  const cfg = {
    vertiportId: vpId,
    layoutName: current?.layoutName || layout?.meta?.name || null,
    fleet: {
      gateAssignments: normalizeGateAssignments(
        assignments,
        sortLayoutGates((layout?.entities || []).filter((e) => e.type === 'gate'))
      ),
    },
  };
  await persistVpConfig(vpId, cfg);
  const row = findAssignRow(vpId);
  if (row) refreshAssignRowHeader(row, vpId);
}

async function applyDefaultFleet(vpId) {
  const cfg = state.layout.configsByVp[vpId];
  const layoutName = cfg?.layoutName;
  if (!layoutName) {
    setAssignStatus('레이아웃을 먼저 선택하세요.', 'error');
    return;
  }
  const layout = await fetchLayoutCached(layoutName);
  if (!layout) return;
  const gates = sortLayoutGates(layout.entities.filter((e) => e.type === 'gate'));
  const counts = defaultCountsForGateCount(gates.length);
  await persistRowFleet(vpId, layout, counts);
  const row = findAssignRow(vpId);
  if (row) await renderRowFleet(row, vpId, layoutName);
}

async function persistVpConfig(vpId, cfg) {
  setAssignStatus(`${vpId} 저장 중...`, 'busy');
  try {
    const saved = await fetchJson(`/api/vertiport-configs/${encodeURIComponent(vpId)}`, {
      method: 'PUT', body: JSON.stringify(cfg),
    });
    state.layout.configsByVp[vpId] = saved;
    rebuildSimVertiportStatus();
    setAssignStatus(
      `${vpId} 저장됨 · ${new Date().toLocaleTimeString('ko-KR', { hour12: false })}`,
      'success'
    );
  } catch (err) {
    console.error(err);
    setAssignStatus(`저장 실패: ${err.message || err}`, 'error');
  }
}

function setAssignStatus(text, level) {
  const el = document.getElementById('assign-status');
  if (!el) return;
  el.textContent = text;
  if (level) el.dataset.level = level;
  else el.removeAttribute('data-level');
}

function findAssignRow(vpId) {
  return document.querySelector(`.assign-row[data-vp-id="${cssAttrEscape(vpId)}"]`);
}
function cssAttrEscape(s) {
  return String(s).replace(/(["\\])/g, '\\$1');
}

/* Re-render only the header of one row so meta + status chips reflect the
 * latest config without losing any open child select focus. */
function refreshAssignRowHeader(row, vpId) {
  const cfg = state.layout.configsByVp[vpId];
  const layoutName = cfg?.layoutName || '';
  const count = Object.values(cfg?.fleet?.gateAssignments || {}).filter(Boolean).length;
  const meta = row.querySelector('.assign-row-meta');
  if (meta) {
    meta.innerHTML = `
      <span>레이아웃: ${layoutName ? `<strong></strong>` : `<strong class="miss-text">미배정</strong>`}</span>
      <span>기체: <strong>${count}대</strong></span>
    `;
    if (layoutName) meta.querySelector('strong').textContent = layoutName;
  }
  const statuses = row.querySelector('.assign-row-status');
  if (statuses) {
    statuses.innerHTML = `
      <span class="status-cell ${layoutName ? 'ok' : 'miss'}" title="레이아웃"><span class="status-dot"></span>L</span>
      <span class="status-cell ${count > 0 ? 'ok' : 'miss'}" title="기체"><span class="status-dot"></span>A</span>
    `;
  }
}

/* Refresh layout dropdowns in every visible row when the library changes. */
function refreshAssignDropdowns() {
  document.querySelectorAll('.assign-row').forEach((row) => {
    const vpId = row.dataset.vpId;
    const cfg = state.layout.configsByVp[vpId];
    const select = row.querySelector('.row-layout-select');
    if (select) populateLayoutSelect(select, cfg?.layoutName || '');
  });
}

const _layoutCache = new Map();
async function fetchLayoutCached(name) {
  if (!name) return null;
  if (_layoutCache.has(name)) return _layoutCache.get(name);
  try {
    const layout = await fetchJson(`/api/layouts/${encodeURIComponent(name)}`);
    _layoutCache.set(name, layout);
    return layout;
  } catch (err) {
    console.error(err);
    return null;
  }
}
function invalidateLayoutCache(name) {
  if (name) _layoutCache.delete(name);
  else _layoutCache.clear();
}

/* ============================================================================
 * 7. Simulation tab: live multi-vertiport and airspace-linked execution
 * ========================================================================== */

function rebuildSimVertiportStatus() {
  const list = document.getElementById('vertiport-status-list');
  if (!list) return;
  list.innerHTML = '';
  for (const vp of state.vertiports) {
    const cfg = state.layout.configsByVp[vp.id];
    const layoutOk = !!cfg?.layoutName;
    const aircraftOk = !!cfg && Object.values(cfg.fleet?.gateAssignments || {}).some((g) => g);
    const li = document.createElement('li');
    li.className = vp.class === 'hub' ? 'hub' : '';
    li.dataset.id = vp.id;
    li.innerHTML = `
      <span class="entity-pin"></span>
      <span class="entity-name"></span>
      <span class="status-cell ${layoutOk ? 'ok' : 'miss'}" title="레이아웃"><span class="status-dot"></span>L</span>
      <span class="status-cell ${aircraftOk ? 'ok' : 'miss'}" title="기체"><span class="status-dot"></span>A</span>
    `;
    li.querySelector('.entity-name').textContent = vp.name;
    li.addEventListener('click', () => selectSimVertiport(vp.id));
    list.appendChild(li);
  }
}

function setupSimulationControls() {
  document.getElementById('sim-run-btn')?.addEventListener('click', runSimulation);
  document.getElementById('sim-play-btn')?.addEventListener('click', playSimulation);
  document.getElementById('sim-pause-btn')?.addEventListener('click', pauseSimulation);
  document.getElementById('sim-stop-btn')?.addEventListener('click', stopSimulation);
  document.getElementById('sim-time-range')?.addEventListener('input', (event) => {
    const live = state.sim.live;
    if (!live) return;
    const target = Number(event.target.value) || live.nowSeconds;
    if (target < live.nowSeconds) {
      event.target.value = String(Math.round(live.nowSeconds));
      return;
    }
    advanceLiveSimulation(live, target - live.nowSeconds);
    renderLiveSimulationFrame(true);
  });
  document.getElementById('sim-panel-close')?.addEventListener('click', () => {
    const panel = document.getElementById('sim-results-panel');
    if (panel) panel.hidden = true;
  });
  document.getElementById('sim-vp-modal-close')?.addEventListener('click', closeLiveVertiportModal);
  document.querySelector('[data-sim-vp-modal-close]')?.addEventListener('click', closeLiveVertiportModal);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.sim.vpModalOpen) closeLiveVertiportModal();
  });
  updateSimulationScenarioLabel();
}

function updateSimulationScenarioLabel() {
  const label = document.getElementById('sim-scenario-label');
  if (!label) return;
  const scenario = state.demand.scenario;
  if (!scenario?.scenarioId) {
    label.textContent = '수요 생성 필요';
    label.dataset.level = 'empty';
    return;
  }
  const demand = scenario.demand || {};
  label.textContent = `${scenario.scenarioId} · ${demand.scenarioDate || ''} · ${fmtNumber(demand.generatedPassengers)}명`;
  label.dataset.level = 'ready';
}

function setSimRunStatus(text, level) {
  const el = document.getElementById('sim-run-status');
  if (!el) return;
  el.textContent = text;
  el.hidden = !text;
  if (level) el.dataset.level = level; else el.removeAttribute('data-level');
}

const LIVE_NODE_CLEARANCE_SECONDS = 10;
const LIVE_LINK_CLEARANCE_SECONDS = 8;
const LIVE_MAX_ADVANCE_STEP_SECONDS = 5;
const LIVE_AIR_POINT_TYPES = new Set(['takeoffPoint', 'landingPoint', 'commonAirPoint']);
const DEMAND_VERTIPORT_ALIASES = {
  '영등포·여의도': '여의도',
  '상암·수색': '상암',
  '사당·이수': '사당',
  '연신내·불광': '연신내',
  '천호·길동': '천호',
  '가산·대림': '가산',
  '수서·문정': '수서',
};

/* Starts the visual, real-time simulation. The simulation state is advanced in
 * the browser so aircraft, selected vertiport detail, and flight logs remain live. */
async function runSimulation() {
  const scenario = state.demand.scenario;
  if (!scenario?.scenarioId) {
    setSimRunStatus('먼저 수요 탭에서 수요를 생성하세요.', 'error');
    return;
  }
  const btn = document.getElementById('sim-run-btn');
  const seed = document.getElementById('sim-random-seed')?.value;
  btn.disabled = true;
  pauseSimulation();
  closeLiveVertiportModal();
  clearLiveMapOverlays();
  resetLiveRenderCache();
  setSimRunStatus('실시간 시뮬레이션 초기화 중...', 'busy');
  try {
    const live = await buildLiveSimulation(scenario, seed === '' ? null : Number(seed));
    state.sim.simulation = null;
    state.sim.live = live;
    state.sim.selectedVertiportId = pickDefaultLiveVertiport(live);
    renderLiveSimulationShell(live);
    playSimulation();
    setSimRunStatus(`실시간 실행 중 · 기체 ${fmtNumber(live.aircraft.size)}대`, 'success');
  } catch (err) {
    console.error(err);
    setSimRunStatus('실패: ' + (err.message || err), 'error');
  } finally {
    btn.disabled = false;
  }
}

/* Build the in-memory simulation state shared by:
 * - visual simulation tab
 * - analysis fast-run tab
 *
 * Demand is loaded by hour, layouts are loaded per vertiport, and each initial
 * aircraft is created from the gate assignment saved in the layout tab. */
async function buildLiveSimulation(scenario, randomSeed) {
  const [odHours] = await Promise.all([
    fetchJson(`/api/demand/scenarios/${encodeURIComponent(scenario.scenarioId)}/od-hours`),
  ]);
  const startSeconds = parseClockToSeconds(odHours.operationStart || scenario.demand?.operationStart || '06:30');
  let endSeconds = parseClockToSeconds(odHours.operationEnd || scenario.demand?.operationEnd || '21:30');
  if (endSeconds <= startSeconds) endSeconds += 24 * 3600;

  const nameIndex = buildDemandVertiportIndex();
  const hourlyDemand = buildLiveHourlyDemand(odHours, nameIndex);
  const portCodes = new Map(state.vertiports.map((vp, index) => [vp.id, String(index + 1).padStart(2, '0')]));
  const live = {
    mode: 'frontend-live',
    scenarioId: scenario.scenarioId,
    scenarioDate: odHours.scenarioDate || scenario.demand?.scenarioDate || '',
    startSeconds,
    endSeconds,
    nowSeconds: startSeconds,
    randomSeed: Number.isFinite(Number(randomSeed)) ? Number(randomSeed) : 42,
    rng: makeSeededRandom(Number.isFinite(Number(randomSeed)) ? Number(randomSeed) : 42),
    currentHour: null,
    hourlyDemand,
    vertiports: new Map(),
    aircraft: new Map(),
    initialAircraftSpecs: [],
    routeCache: new Map(),
    pendingRoutes: new Map(),
    failedRoutes: new Set(),
    routeStats: new Map(),
    routeStatsVersion: 0,
    portCodes,
    odCounters: new Map(),
    flights: [],
    flightByPlanId: new Map(),
    flightCount: 0,
    assignedPassengers: 0,
    servedPassengers: 0,
    unservedPassengers: 0,
    warnings: [],
    ended: false,
    lastRenderMs: 0,
  };

  let aircraftIndex = 1;
  for (const vp of state.vertiports) {
    const cfg = state.layout.configsByVp[vp.id] || {};
    const layout = cfg.layoutName ? await fetchLayoutCached(cfg.layoutName) : null;
    if (!layout) {
      live.warnings.push(`${vp.name}: 레이아웃 미배정`);
      continue;
    }
    const model = buildLiveLayoutModel(layout);
    const runtime = {
      id: vp.id,
      name: vp.name,
      code: portCodes.get(vp.id) || '--',
      lat: Number(vp.lat),
      lon: Number(vp.lon),
      layoutName: cfg.layoutName,
      layout,
      model,
      resources: initLiveResources(model),
      currentDemand: new Map(),
      currentRequested: new Map(),
      currentProcessed: new Map(),
      departures: 0,
      arrivals: 0,
      processedPassengers: 0,
      servedPassengers: 0,
      unservedPassengers: 0,
    };
    live.vertiports.set(vp.id, runtime);

    const assignments = cfg.fleet?.gateAssignments || {};
    for (const [gateId, assignment] of Object.entries(assignments).sort(([a], [b]) => String(a).localeCompare(String(b)))) {
      if (!assignment?.typeId || !runtime.model.entities.has(gateId)) continue;
      const type = AIRCRAFT_TYPES.find((item) => item.id === assignment.typeId) || AIRCRAFT_TYPES[1];
      const aircraftId = `UAM${String(aircraftIndex).padStart(4, '0')}`;
      aircraftIndex += 1;
      live.initialAircraftSpecs.push({
        id: aircraftId,
        typeId: type.id,
        capacity: Number(assignment.seats || type.seats),
        vertiportId: vp.id,
        gateId,
      });
    }
  }

  if (!live.vertiports.size) {
    throw new Error('레이아웃이 배정된 버티포트가 없습니다.');
  }
  if (!live.initialAircraftSpecs.length) {
    throw new Error('초기 배치 기체가 없습니다. 레이아웃 탭에서 GATE별 기체 타입을 배정하세요.');
  }

  resetLiveRuntime(live);
  warmLiveRoutesForCurrentHour(live);
  return live;
}

function resetLiveRuntime(live) {
  live.nowSeconds = live.startSeconds;
  live.rng = makeSeededRandom(live.randomSeed);
  live.currentHour = null;
  live.aircraft = new Map();
  live.routeStats = new Map();
  live.failedRoutes = new Set();
  live.routeStatsVersion = 0;
  live.odCounters = new Map();
  live.flights = [];
  live.flightByPlanId = new Map();
  live.flightCount = 0;
  live.assignedPassengers = 0;
  live.servedPassengers = 0;
  live.unservedPassengers = 0;
  live.ended = false;
  for (const vp of live.vertiports.values()) {
    vp.resources = initLiveResources(vp.model);
    vp.currentDemand = new Map();
    vp.currentRequested = new Map();
    vp.currentProcessed = new Map();
    vp.departures = 0;
    vp.arrivals = 0;
    vp.processedPassengers = 0;
    vp.servedPassengers = 0;
    vp.unservedPassengers = 0;
  }
  for (const spec of live.initialAircraftSpecs) {
    const vp = live.vertiports.get(spec.vertiportId);
    if (!vp) continue;
    vp.resources.gates[spec.gateId] = Number.POSITIVE_INFINITY;
    live.aircraft.set(spec.id, {
      ...spec,
      state: 'available',
      locationVertiportId: spec.vertiportId,
      originId: null,
      destinationId: null,
      flightPlanId: null,
      gateId: spec.gateId,
      availableAt: live.startSeconds,
      internal: null,
      airspace: null,
      countedGateIn: false,
    });
  }
  syncLiveDemandHour(live);
}

function buildDemandVertiportIndex() {
  const index = new Map();
  for (const vp of state.vertiports) {
    index.set(vp.id, vp.id);
    index.set(vp.name, vp.id);
  }
  for (const [from, to] of Object.entries(DEMAND_VERTIPORT_ALIASES)) {
    if (index.has(to)) index.set(from, index.get(to));
  }
  return index;
}

function buildLiveHourlyDemand(odHours, nameIndex) {
  const result = new Map();
  for (const hourRow of odHours.hours || []) {
    const originMap = new Map();
    for (const originRow of hourRow.origins || []) {
      const originId = nameIndex.get(originRow.origin);
      if (!originId) continue;
      const destMap = new Map();
      for (const destRow of originRow.destinations || []) {
        const destinationId = nameIndex.get(destRow.destination);
        const count = Math.max(0, Math.floor(Number(destRow.passengers) || 0));
        if (!destinationId || destinationId === originId || count <= 0) continue;
        destMap.set(destinationId, (destMap.get(destinationId) || 0) + count);
      }
      if (destMap.size) originMap.set(originId, destMap);
    }
    result.set(Number(hourRow.hour), originMap);
  }
  return result;
}

function pickDefaultLiveVertiport(live) {
  const currentHourDemand = live.hourlyDemand.get(live.currentHour) || new Map();
  for (const originId of currentHourDemand.keys()) {
    if (live.vertiports.has(originId)) return originId;
  }
  return live.vertiports.keys().next().value || state.vertiports[0]?.id || null;
}

/* Render shell only once when a scenario starts; frame updates below should
 * mutate only changing DOM/map sources to avoid flicker and heavy re-rendering. */
function renderLiveSimulationShell(live) {
  const panel = document.getElementById('sim-results-panel');
  if (panel) panel.hidden = false;
  state.sim.durationSeconds = live.endSeconds;
  state.sim.currentTimeSeconds = live.nowSeconds;
  configureSimulationClockControls(true);
  setText('sim-result-title', `${live.scenarioId} · ${live.scenarioDate} · frontend-live`);
  if (state.sim.selectedVertiportId) selectSimVertiport(state.sim.selectedVertiportId);
  else renderLiveSimulationFrame(true);
}

function configureSimulationClockControls(enabled) {
  ['sim-play-btn', 'sim-pause-btn', 'sim-stop-btn', 'sim-speed-select', 'sim-time-range'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.disabled = !enabled;
  });
  const range = document.getElementById('sim-time-range');
  const live = state.sim.live;
  if (range) {
    range.min = String(live?.startSeconds || 0);
    range.max = String(live?.endSeconds || 1);
    range.value = String(state.sim.currentTimeSeconds || 0);
  }
  updateSimulationClockLabel();
}

function playSimulation() {
  if (!state.sim.live) {
    runSimulation();
    return;
  }
  if (state.sim.playing) return;
  state.sim.playing = true;
  state.sim.lastFrameMs = performance.now();
  state.sim.timer = requestAnimationFrame(liveAnimationFrame);
}

function pauseSimulation() {
  state.sim.playing = false;
  if (state.sim.timer) {
    cancelAnimationFrame(state.sim.timer);
    state.sim.timer = null;
  }
}

function stopSimulation() {
  const live = state.sim.live;
  pauseSimulation();
  if (!live) return;
  resetLiveRuntime(live);
  warmLiveRoutesForCurrentHour(live);
  clearLiveMapOverlays();
  resetLiveRenderCache();
  setSimRunStatus('정지 · 초기 상태로 복귀', 'success');
  renderLiveSimulationFrame(true);
}

function liveAnimationFrame(nowMs) {
  if (!state.sim.playing || !state.sim.live) return;
  const live = state.sim.live;
  const elapsed = Math.max(0, (nowMs - (state.sim.lastFrameMs || nowMs)) / 1000);
  state.sim.lastFrameMs = nowMs;
  const speed = getSimulationSpeed();
  advanceLiveSimulation(live, elapsed * speed);
  if (nowMs - (live.lastRenderMs || 0) > 120 || live.nowSeconds >= live.endSeconds) {
    live.lastRenderMs = nowMs;
    renderLiveSimulationFrame(false, nowMs);
  }
  if (live.nowSeconds >= live.endSeconds) {
    pauseSimulation();
    setSimRunStatus(`종료 · 미처리 ${fmtNumber(live.unservedPassengers)}명`, 'success');
    return;
  }
  state.sim.timer = requestAnimationFrame(liveAnimationFrame);
}

function getSimulationSpeed() {
  return Number(String(document.getElementById('sim-speed-select')?.value || '1').replace('×', '')) || 1;
}

function updateSimulationClockLabel() {
  const rounded = Math.round(state.sim.currentTimeSeconds || 0);
  setText('sim-clock-label', formatClockSeconds(rounded));
  const range = document.getElementById('sim-time-range');
  if (range && document.activeElement !== range) {
    const nextValue = String(rounded);
    if (range.value !== nextValue) range.value = nextValue;
  }
}

/* Advances logical time. Hour boundaries finalize unmet demand; within each step
 * aircraft states are updated before new departures are scheduled. */
function advanceLiveSimulation(live, deltaSeconds) {
  if (!live || live.ended) return;
  const delta = Math.max(0, Number(deltaSeconds) || 0);
  const targetSeconds = Math.min(live.endSeconds, live.nowSeconds + delta);
  while (live.nowSeconds < targetSeconds && !live.ended) {
    const nextHourBoundary = (Math.floor(live.nowSeconds / 3600) + 1) * 3600;
    const nextStepBoundary = live.nowSeconds + LIVE_MAX_ADVANCE_STEP_SECONDS;
    live.nowSeconds = Math.min(targetSeconds, nextHourBoundary, nextStepBoundary, live.endSeconds);
    syncLiveDemandHour(live);
    updateLiveAircraftStates(live);
    scheduleLiveDepartures(live);
  }
  if (live.nowSeconds >= live.endSeconds && !live.ended) {
    finalizeLiveCurrentDemand(live);
    live.ended = true;
  }
}

function syncLiveDemandHour(live) {
  const hour = Math.floor((((live.nowSeconds % 86400) + 86400) % 86400) / 3600);
  if (live.currentHour === hour) return;
  if (live.currentHour !== null) finalizeLiveCurrentDemand(live);
  live.currentHour = hour;
  for (const vp of live.vertiports.values()) {
    vp.currentDemand = new Map();
    vp.currentRequested = new Map();
    vp.currentProcessed = new Map();
  }
  const originMap = live.hourlyDemand.get(hour) || new Map();
  for (const [originId, destMap] of originMap.entries()) {
    const vp = live.vertiports.get(originId);
    if (!vp) continue;
    for (const [destinationId, count] of destMap.entries()) {
      vp.currentDemand.set(destinationId, count);
      vp.currentRequested.set(destinationId, count);
      vp.currentProcessed.set(destinationId, 0);
    }
  }
  warmLiveRoutesForCurrentHour(live);
}

function finalizeLiveCurrentDemand(live) {
  let unserved = 0;
  for (const vp of live.vertiports.values()) {
    for (const count of vp.currentDemand.values()) {
      unserved += Math.max(0, Math.floor(Number(count) || 0));
    }
    vp.unservedPassengers += [...vp.currentDemand.values()].reduce((s, c) => s + Math.max(0, Number(c) || 0), 0);
    vp.currentDemand = new Map();
    vp.currentRequested = new Map();
    vp.currentProcessed = new Map();
  }
  live.unservedPassengers += unserved;
}

function updateLiveAircraftStates(live) {
  const now = live.nowSeconds;
  for (const ac of live.aircraft.values()) {
    if (ac.state === 'departing' && ac.internal?.endTime <= now) {
      const route = ac.airspace?.route;
      ac.state = 'airspace';
      ac.locationVertiportId = null;
      ac.gateId = null;
      ac.internal = null;
      const airStart = ac.airspace.startTime;
      ac.airspace.endTime = airStart + route.airDurationSeconds;
      const flight = findLiveFlight(live, ac.flightPlanId);
      if (flight) {
        flight.status = 'airspace';
        flight.times.takeoffSeconds = airStart;
        flight.times.takeoffTime = formatClockSeconds(airStart);
      }
    }

    if (ac.state === 'airspace' && ac.airspace?.endTime <= now) {
      const destVp = live.vertiports.get(ac.destinationId);
      const flight = findLiveFlight(live, ac.flightPlanId);
      if (!destVp) {
        finishLiveFlightWithoutLanding(live, ac, flight);
        continue;
      }
      const landing = scheduleLiveLanding(destVp, ac, ac.airspace.endTime);
      if (!landing) {
        ac.state = 'arrivalHold';
        ac.locationVertiportId = null;
        ac.holdStart = ac.airspace.endTime;
        continue;
      }
      ac.state = 'landing';
      ac.locationVertiportId = destVp.id;
      ac.gateId = landing.gateId;
      ac.internal = {
        kind: 'landing',
        vertiportId: destVp.id,
        segments: landing.segments,
        startTime: landing.startTime,
        gateInTime: landing.gateArrivalTime,
        endTime: landing.readyTime,
      };
      ac.airspace = null;
      ac.availableAt = landing.readyTime;
      ac.countedGateIn = false;
      if (flight) {
        flight.status = 'landing';
        flight.arrivalGateId = landing.gateId;
        flight.arrivalFatoId = landing.fatoId;
        flight.arrivalSegments = structuredClone(landing.segments || []);
        flight.times.landingSeconds = landing.touchdownTime;
        flight.times.landingTime = formatClockSeconds(landing.touchdownTime);
        flight.times.gateInSeconds = landing.gateArrivalTime;
        flight.times.gateInTime = formatClockSeconds(landing.gateArrivalTime);
        flight.times.readySeconds = landing.readyTime;
        flight.times.readyTime = formatClockSeconds(landing.readyTime);
      }
    }

    if (ac.state === 'arrivalHold') {
      const destVp = live.vertiports.get(ac.destinationId);
      const flight = findLiveFlight(live, ac.flightPlanId);
      const landing = destVp ? scheduleLiveLanding(destVp, ac, now) : null;
      if (landing) {
        ac.state = 'landing';
        ac.locationVertiportId = destVp.id;
        ac.gateId = landing.gateId;
        ac.internal = {
          kind: 'landing',
          vertiportId: destVp.id,
          segments: landing.segments,
          startTime: landing.startTime,
          gateInTime: landing.gateArrivalTime,
          endTime: landing.readyTime,
        };
        ac.airspace = null;
        ac.availableAt = landing.readyTime;
        ac.countedGateIn = false;
        if (flight) {
          flight.status = 'landing';
          flight.arrivalGateId = landing.gateId;
          flight.arrivalFatoId = landing.fatoId;
          flight.arrivalSegments = structuredClone(landing.segments || []);
          flight.times.landingSeconds = landing.touchdownTime;
          flight.times.landingTime = formatClockSeconds(landing.touchdownTime);
          flight.times.gateInSeconds = landing.gateArrivalTime;
          flight.times.gateInTime = formatClockSeconds(landing.gateArrivalTime);
          flight.times.readySeconds = landing.readyTime;
          flight.times.readyTime = formatClockSeconds(landing.readyTime);
        }
      }
    }

    if (ac.state === 'landing') {
      const flight = findLiveFlight(live, ac.flightPlanId);
      if (flight && !flight.countedGateIn && flight.times.gateInSeconds <= now) {
        flight.countedGateIn = true;
        live.servedPassengers += flight.passengerCount;
        const destVp = live.vertiports.get(flight.destinationId);
        if (destVp) {
          destVp.arrivals += 1;
          destVp.servedPassengers += flight.passengerCount;
        }
      }
      if (ac.internal?.endTime <= now) {
        if (flight) flight.status = 'ready';
        ac.state = 'available';
        ac.locationVertiportId = ac.destinationId;
        ac.originId = null;
        ac.destinationId = null;
        ac.flightPlanId = null;
        ac.internal = null;
        ac.availableAt = now;
        ac.countedGateIn = false;
      }
    }
  }
}

/* Schedule all currently available aircraft against remaining demand.
 * Destination choice follows the requested policy: full-load candidates are
 * selected probabilistically by remaining demand; otherwise best load factor wins. */
function scheduleLiveDepartures(live) {
  const now = live.nowSeconds;
  let scheduled = 0;
  const aircraft = [...live.aircraft.values()].sort((a, b) => a.id.localeCompare(b.id));
  for (const ac of aircraft) {
    if (scheduled >= 250) break;
    if (ac.state !== 'available' || ac.availableAt > now || !ac.locationVertiportId || !ac.gateId) continue;
    const originVp = live.vertiports.get(ac.locationVertiportId);
    if (!originVp) continue;
    const choice = chooseLiveDestination(live, originVp, ac);
    if (!choice) continue;
    const route = live.routeCache.get(routeKey(originVp.id, choice.destinationId));
    if (!route) continue;
    const destinationVp = live.vertiports.get(choice.destinationId);
    const departure = scheduleLiveDeparture(originVp, ac, now);
    if (!departure) continue;

    const passengerCount = Math.min(choice.remaining, ac.capacity);
    originVp.currentDemand.set(choice.destinationId, choice.remaining - passengerCount);
    originVp.currentProcessed.set(
      choice.destinationId,
      (originVp.currentProcessed.get(choice.destinationId) || 0) + passengerCount
    );
    originVp.departures += 1;
    originVp.processedPassengers += passengerCount;
    live.assignedPassengers += passengerCount;

    const fpl = nextLiveFlightPlanId(live, originVp.id, choice.destinationId);
    const flight = {
      sequence: live.flightCount + 1,
      flightPlanId: fpl,
      aircraftId: ac.id,
      aircraftTypeId: ac.typeId,
      capacity: ac.capacity,
      passengerCount,
      originId: originVp.id,
      destinationId: choice.destinationId,
      origin: originVp.name,
      destination: destinationVp?.name || choice.destinationId,
      demandHour: live.currentHour,
      departureGateId: ac.gateId,
      departureFatoId: departure.fatoId,
      arrivalGateId: '',
      arrivalFatoId: '',
      status: 'departure',
      routePath: route.path || [originVp.name, destinationVp?.name || choice.destinationId],
      routeDistanceKm: route.distanceKm,
      routeGeometry: structuredClone(route.geometry || []),
      missionProfile: structuredClone(route.missionProfile || null),
      enRouteSegments: buildScheduledFlightSegments(route, originVp, destinationVp),
      times: {
        gateOutSeconds: departure.gateReleaseTime,
        gateOutTime: formatClockSeconds(departure.gateReleaseTime),
        takeoffSeconds: departure.completionTime,
        takeoffTime: formatClockSeconds(departure.completionTime),
        landingSeconds: null,
        landingTime: '',
        gateInSeconds: null,
        gateInTime: '',
      },
      departureSegments: structuredClone(departure.segments || []),
      arrivalSegments: [],
      countedGateIn: false,
    };
    live.flights.push(flight);
    live.flightByPlanId.set(fpl, flight);
    live.flightCount += 1;
    incrementLiveRouteStats(live, originVp.id, choice.destinationId, passengerCount);

    ac.state = 'departing';
    ac.originId = originVp.id;
    ac.destinationId = choice.destinationId;
    ac.flightPlanId = fpl;
    ac.internal = {
      kind: 'departure',
      vertiportId: originVp.id,
      segments: departure.segments,
      startTime: now,
      endTime: departure.completionTime,
    };
    ac.airspace = {
      route,
      startTime: departure.completionTime,
      endTime: departure.completionTime + route.airDurationSeconds,
    };
    scheduled += 1;
  }
  return scheduled;
}

function chooseLiveDestination(live, originVp, aircraft) {
  const entries = [...originVp.currentDemand.entries()]
    .map(([destinationId, remaining]) => ({ destinationId, remaining: Math.max(0, Math.floor(Number(remaining) || 0)) }))
    .filter((item) => (
      item.remaining > 0
      && item.destinationId !== originVp.id
      && live.vertiports.has(item.destinationId)
      && !live.failedRoutes.has(routeKey(originVp.id, item.destinationId))
    ));
  if (!entries.length) return null;
  for (const item of entries) requestLiveRoute(live, originVp.id, item.destinationId);
  const ready = entries.filter((item) => live.routeCache.has(routeKey(originVp.id, item.destinationId)));
  if (!ready.length) return null;
  const fullCandidates = ready.filter((item) => item.remaining >= aircraft.capacity);
  if (fullCandidates.length) {
    const total = fullCandidates.reduce((sum, item) => sum + item.remaining, 0);
    let pick = live.rng() * total;
    for (const item of fullCandidates) {
      pick -= item.remaining;
      if (pick <= 0) return item;
    }
    return fullCandidates[fullCandidates.length - 1];
  }
  return ready.sort((a, b) => b.remaining - a.remaining || a.destinationId.localeCompare(b.destinationId))[0] || null;
}

/* Single live frame renderer. Expensive parts are throttled independently:
 * metrics/logs, selected vertiport canvas, route lines, and airspace aircraft. */
function renderLiveSimulationFrame(force, renderMs = performance.now()) {
  const live = state.sim.live;
  if (!live) return;
  const cache = state.sim.renderCache;
  state.sim.currentTimeSeconds = live.nowSeconds;
  updateSimulationClockLabel();
  const selected = live.vertiports.get(state.sim.selectedVertiportId);
  const selectedId = selected?.id || null;
  const shouldUpdatePanel = force || renderMs - cache.lastPanelMs > 500;
  if (shouldUpdatePanel) {
    cache.lastPanelMs = renderMs;
    const stats = selected ? getSelectedLivePanelStats(live, selected.id) : getGlobalLivePanelStats(live);
    const metricsKey = `${selectedId || 'all'}|${stats.flightCount}|${stats.passengerCount}|${stats.unservedCount}|${stats.airspaceCount}`;
    if (force || cache.metricsKey !== metricsKey) {
      cache.metricsKey = metricsKey;
      cache.lastMetricsMs = renderMs;
      setText('sim-m-flight', fmtNumber(stats.flightCount));
      setText('sim-m-served', fmtNumber(stats.passengerCount));
      setText('sim-m-unserved', fmtNumber(stats.unservedCount));
      setText('sim-m-fleet', fmtNumber(stats.airspaceCount));
    }
    renderLiveFlightLog(live, selectedId, force, renderMs);
  }
  if (force || cache.routeStatsVersion !== live.routeStatsVersion) {
    cache.routeStatsVersion = live.routeStatsVersion;
    drawLiveRoutes(live);
  }
  if (force || renderMs - cache.lastMapMs > 120) {
    cache.lastMapMs = renderMs;
    drawAirspaceAircraft(getLiveAirspaceAircraft(live), { force, renderMs });
  }
  if (selected) {
    if (shouldUpdatePanel) {
      const detailKey = buildLiveDetailKey(live, selected);
      updateSimVertiportHeader(selected, live);
      if (force || cache.detailKey !== detailKey) {
        cache.detailKey = detailKey;
        cache.lastDetailMs = renderMs;
        renderSimVertiportDetail(selected);
      }
    }
    if (force || renderMs - cache.lastCanvasMs > 250) {
      cache.lastCanvasMs = renderMs;
      const snapshot = buildLiveVertiportSnapshot(live, selected);
      renderVertiportSnapshotCanvas(snapshot);
      renderLiveVertiportModal(snapshot, selected, live);
    }
  } else if (force) {
    cache.detailKey = '';
    renderSimVertiportDetail(null);
  }
}

function getSelectedLivePanelStats(live, vertiportId) {
  const vp = live.vertiports.get(vertiportId);
  const flights = live.flights.filter((flight) => isFlightRelatedToVertiport(flight, vertiportId));
  const currentResidual = vp
    ? [...vp.currentDemand.values()].reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0)
    : 0;
  return {
    flightCount: flights.length,
    passengerCount: flights.reduce((sum, flight) => sum + (Number(flight.passengerCount) || 0), 0),
    unservedCount: (vp?.unservedPassengers || 0) + currentResidual,
    airspaceCount: countLiveAirspaceAircraft(live, vertiportId),
  };
}

function getGlobalLivePanelStats(live) {
  return {
    flightCount: live.flightCount,
    passengerCount: live.assignedPassengers,
    unservedCount: live.unservedPassengers,
    airspaceCount: countLiveAirspaceAircraft(live),
  };
}

function buildLiveDetailKey(live, vp) {
  const demandKey = [...vp.currentDemand.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([destinationId, count]) => `${destinationId}:${count}:${vp.currentProcessed.get(destinationId) || 0}`)
    .join('|');
  const aircraftKey = buildLiveAircraftRows(live, vp)
    .map((item) => [
      item.aircraftId,
      item.state,
      item.flightPlanId,
      item.routeLabel,
    ].join(':'))
    .join('|');
  return [
    vp.id,
    live.currentHour,
    vp.departures,
    vp.arrivals,
    vp.processedPassengers,
    vp.unservedPassengers,
    demandKey,
    aircraftKey,
  ].join('~');
}

function renderLiveFlightLog(live, selectedVertiportId = null, force = false, renderMs = performance.now()) {
  const tbody = document.getElementById('sim-flight-body');
  const meta = document.getElementById('sim-flight-meta');
  const outboundRows = selectedVertiportId
    ? live.flights.filter((flight) => flight.originId === selectedVertiportId)
    : live.flights;
  const inboundRows = selectedVertiportId
    ? live.flights.filter((flight) => flight.destinationId === selectedVertiportId)
    : [];
  const totalRows = outboundRows.length + inboundRows.length;
  const grouped = selectedVertiportId ? buildSelectedLiveFlightLogGroups(live, selectedVertiportId) : null;
  const logRows = selectedVertiportId
    ? grouped.flatMap((group) => group.rows)
    : outboundRows.slice(-80).reverse();
  const prefix = selectedVertiportId ? `${live.vertiports.get(selectedVertiportId)?.name || selectedVertiportId}` : '전체';
  const groupKey = grouped
    ? grouped.map((group) => `${group.kind}:${group.total}:${group.rows.length}`).join('|')
    : '';
  const logKey = `${selectedVertiportId || 'all'}|out:${outboundRows.length}|in:${inboundRows.length}|${groupKey}|${logRows.slice(0, 40).map((flight) => [
    flight.flightPlanId,
    flight.status,
    flight.times?.takeoffTime || '',
    flight.times?.landingTime || '',
    flight.times?.gateInTime || '',
  ].join(':')).join('|')}`;
  const cache = state.sim.renderCache;
  if (!force && cache.logKey === logKey) return;
  cache.logKey = logKey;
  cache.lastLogMs = renderMs;
  if (meta) {
    meta.textContent = selectedVertiportId
      ? `${prefix} 출발 ${fmtNumber(outboundRows.length)}편 · 도착 ${fmtNumber(inboundRows.length)}편`
      : `전체 ${fmtNumber(outboundRows.length)}편 · 최근 ${fmtNumber(logRows.length)}편`;
  }
  if (!tbody) return;
  if (!totalRows) {
    tbody.innerHTML = '<tr><td class="empty-row" colspan="7">선택한 버티포트 관련 비행편이 아직 없습니다.</td></tr>';
    return;
  }
  if (!selectedVertiportId) {
    tbody.innerHTML = renderLiveFlightRows(logRows);
    return;
  }
  tbody.innerHTML = grouped.map((group) => renderLiveFlightSection(group.title, group.total, group.rows, group.kind)).join('');
}

function buildSelectedLiveFlightLogGroups(live, vertiportId) {
  const now = Number(live.nowSeconds) || 0;
  const byNewest = (timeFn) => (a, b) => (timeFn(b) || 0) - (timeFn(a) || 0);
  const bySoonest = (timeFn) => (a, b) => (timeFn(a) || Number.POSITIVE_INFINITY) - (timeFn(b) || Number.POSITIVE_INFINITY);
  const outbound = live.flights.filter((flight) => flight.originId === vertiportId);
  const inbound = live.flights.filter((flight) => flight.destinationId === vertiportId);
  const departureActive = outbound
    .filter((flight) => !flight.times?.takeoffSeconds || Number(flight.times.takeoffSeconds) > now)
    .sort(bySoonest((flight) => Number(flight.times?.takeoffSeconds) || Number(flight.times?.gateOutSeconds)));
  const departureDone = outbound
    .filter((flight) => Number(flight.times?.takeoffSeconds) && Number(flight.times.takeoffSeconds) <= now)
    .sort(byNewest((flight) => Number(flight.times?.takeoffSeconds)));
  const arrivalPlanned = inbound
    .filter((flight) => !flight.times?.gateInSeconds || Number(flight.times.gateInSeconds) > now)
    .sort(bySoonest((flight) => Number(flight.times?.gateInSeconds) || Number(flight.times?.landingSeconds) || Number(flight.times?.takeoffSeconds)));
  const arrivalDone = inbound
    .filter((flight) => Number(flight.times?.gateInSeconds) && Number(flight.times.gateInSeconds) <= now)
    .sort(byNewest((flight) => Number(flight.times?.gateInSeconds)));
  return [
    { kind: 'departure-active', title: '출발 중', total: departureActive.length, rows: departureActive.slice(0, 30) },
    { kind: 'departure-done', title: '출발 완료', total: departureDone.length, rows: departureDone.slice(0, 30) },
    { kind: 'arrival-planned', title: '도착 예정', total: arrivalPlanned.length, rows: arrivalPlanned.slice(0, 30) },
    { kind: 'arrival-done', title: '도착 완료', total: arrivalDone.length, rows: arrivalDone.slice(0, 30) },
  ];
}

function renderLiveFlightSection(title, total, rows, direction) {
  const emptyText = {
    'departure-active': '현재 출발 절차 중인 비행편 없음',
    'departure-done': '출발 완료 비행편 없음',
    'arrival-planned': '현재 도착 예정 비행편 없음',
    'arrival-done': '도착 완료 비행편 없음',
  }[direction] || '표시할 비행편 없음';
  return `
    <tr class="sim-flight-section ${direction}">
      <td colspan="7"><span>${escapeHtml(title)}</span><em>${fmtNumber(total)}편</em></td>
    </tr>
    ${rows.length ? renderLiveFlightRows(rows, direction) : `<tr><td class="empty-row" colspan="7">${emptyText}</td></tr>`}
  `;
}

function renderLiveFlightRows(rows, direction = '') {
  return rows.map((f) => `
    <tr class="${direction ? `sim-flight-row ${direction}` : ''}" data-origin="${escapeHtml(f.origin)}" data-destination="${escapeHtml(f.destination)}">
      <td title="${escapeHtml(f.flightPlanId)}">${escapeHtml(f.flightPlanId)}</td>
      <td>${aircraftTypeChip(f.aircraftTypeId, f.aircraftId)}</td>
      <td title="${escapeHtml(f.origin)}">${escapeHtml(f.origin)}</td>
      <td title="${escapeHtml(f.destination)}">${escapeHtml(f.destination)}</td>
      <td class="num">${fmtNumber(f.passengerCount)}/${fmtNumber(f.capacity)}</td>
      <td>${escapeHtml(f.times?.takeoffTime || '')}</td>
      <td>${escapeHtml(f.times?.landingTime || '')}</td>
    </tr>
  `).join('');
}

function selectSimVertiport(vertiportId) {
  if (!vertiportId) return;
  state.sim.selectedVertiportId = vertiportId;
  document.querySelectorAll('#vertiport-status-list li').forEach((li) => {
    li.classList.toggle('is-selected', li.dataset.id === vertiportId);
  });
  document.querySelectorAll('.vertiport-marker').forEach((marker) => {
    marker.classList.toggle('is-selected', marker.dataset.id === vertiportId);
  });
  const live = state.sim.live;
  if (!live) return;
  renderLiveSimulationFrame(true);
}

function updateSimVertiportHeader(vp, live = state.sim.live) {
  if (!vp) return;
  setText('sim-vp-title', `${vp.code || '—'} · ${vp.name}`);
  setText('sim-vp-meta', `출발 ${fmtNumber(vp.departures)}편 · 도착 ${fmtNumber(vp.arrivals)}편 · ${formatClockSeconds(live?.nowSeconds || 0)}`);
}

function renderSimVertiportDetail(vp) {
  const title = document.getElementById('sim-vp-title');
  const meta = document.getElementById('sim-vp-meta');
  const body = document.getElementById('sim-vp-detail');
  if (!body) return;
  if (!vp) {
    if (title) title.textContent = '버티포트 선택';
    if (meta) meta.textContent = '지도에서 버티포트를 클릭하세요.';
    body.innerHTML = '<p class="empty-row">선택된 버티포트 없음</p>';
    return;
  }
  const live = state.sim.live;
  updateSimVertiportHeader(vp, live);
  const resourceText = `${fmtNumber(vp.model.gates.length)} / ${fmtNumber(vp.model.fatos.length)}`;
  const requestedPassengers = [...vp.currentRequested.values()].reduce((sum, value) => sum + (Number(value) || 0), 0);
  const demandRows = buildLiveDemandRows(live, vp)
    .filter((d) => d.requested || d.served || d.unserved)
    .sort((a, b) => (b.requested || 0) - (a.requested || 0))
    .slice(0, 12);
  const allAircraftRows = buildLiveAircraftRows(live, vp);
  const aircraftRows = allAircraftRows.slice(0, 18);
  const fleetCounts = countLiveFleetInVertiport(live, vp.id);
  body.innerHTML = `
    <button class="sim-vp-canvas-wrap sim-vp-canvas-open" id="sim-vp-expand-btn" type="button" title="버티포트 내부 시뮬레이션 크게 보기">
      <canvas id="sim-vp-canvas" width="520" height="360"></canvas>
      <span class="sim-vp-expand-label">확대 보기</span>
    </button>
    <div class="sim-kv-grid">
      <div><span>현재 수요</span><strong>${fmtNumber(requestedPassengers)}</strong></div>
      <div><span>처리</span><strong>${fmtNumber(vp.processedPassengers)}</strong></div>
      <div><span>미처리</span><strong>${fmtNumber(vp.unservedPassengers)}</strong></div>
      <div><span>Gate/FATO</span><strong>${resourceText}</strong></div>
    </div>
    <div class="sim-fleet-row">
      ${fleetTypeChips(fleetCounts)}
    </div>
    <h4>현재 시간대 목적지별 잔여 수요</h4>
    ${renderMiniDemandTable(demandRows)}
    <h4>버티포트 처리 중 기체</h4>
    <p class="sim-section-note">주기 중, 출발 지상절차, 도착 지상절차 기체만 표시합니다. 공역 비행 중인 기체는 지도에서 표시됩니다.</p>
    ${renderMiniAircraftList(aircraftRows, allAircraftRows.length)}
  `;
  body.querySelector('#sim-vp-expand-btn')?.addEventListener('click', openLiveVertiportModal);
}

function buildLiveDemandRows(live, vp) {
  if (!live || !vp) return [];
  const destinations = new Set([
    ...vp.currentRequested.keys(),
    ...vp.currentDemand.keys(),
    ...vp.currentProcessed.keys(),
  ]);
  return [...destinations].map((destinationId) => ({
    destination: live.vertiports.get(destinationId)?.name || destinationId,
    requested: vp.currentRequested.get(destinationId) || 0,
    served: vp.currentProcessed.get(destinationId) || 0,
    unserved: vp.currentDemand.get(destinationId) || 0,
  }));
}

function buildLiveAircraftRows(live, vp) {
  if (!live || !vp) return [];
  return [...live.aircraft.values()]
    .filter((ac) => aircraftBelongsToVertiport(ac, vp.id))
    .sort((a, b) => a.id.localeCompare(b.id))
    .map((ac) => {
      const flight = findLiveFlight(live, ac.flightPlanId);
      const segment = currentLiveSegment(ac.internal?.segments, live.nowSeconds);
      return {
        aircraftId: ac.id,
        typeId: ac.typeId,
        state: ac.state,
        stateLabel: liveAircraftStateLabel(ac.state),
        resourceLabel: liveAircraftResourceLabel(ac, segment),
        flightPlanId: ac.flightPlanId || '',
        routeLabel: flight ? `${flight.origin} → ${flight.destination}` : '',
      };
    });
}

function liveAircraftResourceLabel(ac, segment) {
  if (ac.state === 'available') return ac.gateId ? `주기 Gate ${ac.gateId}` : '주기';
  if (segment?.at?.id) return `${liveEntityTypeLabel(segment.at.type)} ${segment.at.id}`;
  if (segment?.from?.id && segment?.to?.id) {
    return `이동 ${segment.from.id} → ${segment.to.id}`;
  }
  if (ac.state === 'departing') return '출발 절차';
  if (ac.state === 'landing') return '착륙 절차';
  return ac.state || '-';
}

function liveEntityTypeLabel(type) {
  if (type === 'gate') return 'Gate';
  if (type === 'fato') return 'FATO';
  if (type === 'node') return 'Node';
  if (type === 'takeoffPoint') return '이륙점';
  if (type === 'landingPoint') return '착륙점';
  if (type === 'commonAirPoint') return '공용점';
  return type || '위치';
}

function renderMiniDemandTable(rows) {
  if (!rows.length) return '<p class="empty-row">목적지별 수요 없음</p>';
  return `
    <table class="data-table sim-mini-table">
      <thead><tr><th>목적지</th><th class="num">수요</th><th class="num">처리</th><th class="num">미처리</th></tr></thead>
      <tbody>${rows.map((d) => `
        <tr><td>${escapeHtml(d.destination)}</td><td class="num">${fmtNumber(d.requested)}</td><td class="num">${fmtNumber(d.served)}</td><td class="num">${fmtNumber(d.unserved)}</td></tr>
      `).join('')}</tbody>
    </table>
  `;
}

function renderMiniAircraftList(rows, total) {
  if (!rows.length) return '<p class="empty-row">기체 없음</p>';
  return `
    <div class="sim-aircraft-list">
      ${rows.map((a) => `
        <div class="sim-aircraft-item state-${escapeHtml(a.state)}" title="${escapeHtml(a.routeLabel || a.resourceLabel)}">
          <div class="sim-aircraft-main">
            ${aircraftTypeChip(a.typeId, a.aircraftId)}
            <em class="sim-aircraft-state">${escapeHtml(a.stateLabel)}</em>
            ${a.flightPlanId ? `<em class="sim-aircraft-fpl">${escapeHtml(a.flightPlanId)}</em>` : ''}
          </div>
          <div class="sim-aircraft-sub">
            <em class="sim-aircraft-resource">현재 ${escapeHtml(a.resourceLabel)}</em>
            ${a.routeLabel ? `<em class="sim-aircraft-route">${escapeHtml(a.routeLabel)}</em>` : ''}
          </div>
        </div>
      `).join('')}
      ${total > rows.length ? `<span class="sim-more">+${fmtNumber(total - rows.length)}대</span>` : ''}
    </div>
  `;
}

function fleetTypeChips(counts) {
  return ['a2', 'a4', 'a6', 'a8'].map((typeId) => {
    const seats = typeId.slice(1);
    return `<span class="fleet-chip ${typeId}">${seats}인승 <strong>${fmtNumber(counts[typeId] || 0)}</strong></span>`;
  }).join('');
}

function aircraftTypeChip(typeId, text) {
  const safeType = ['a2', 'a4', 'a6', 'a8'].includes(typeId) ? typeId : 'a4';
  return `<span class="aircraft-chip ${safeType}">${escapeHtml(text || safeType)}</span>`;
}

function drawLiveRoutes(live) {
  const routeSource = state.map?.getSource('overlay-sim-routes');
  if (routeSource) {
    routeSource.setData({
      type: 'FeatureCollection',
      features: [...live.routeStats.entries()].map(([key, stats]) => {
        const route = live.routeCache.get(key);
        if (!route) return null;
        return {
        type: 'Feature',
        properties: {
          routeKey: route.key,
          origin: route.origin,
          destination: route.destination,
          flightCount: stats.flightCount || 0,
          passengerCount: stats.passengerCount || 0,
        },
        geometry: { type: 'LineString', coordinates: route.geometry || [] },
        };
      }).filter(Boolean),
    });
  }
}

function drawAirspaceAircraft(items, options = {}) {
  const { force = false, renderMs = performance.now() } = options;
  const aircraftSource = state.map?.getSource('overlay-sim-aircraft');
  const features = (items || []).map((item) => ({
    type: 'Feature',
    properties: {
      aircraftId: item.aircraftId,
      flightPlanId: item.flightPlanId,
      typeId: item.typeId,
      seats: item.capacity,
      passengerCount: item.passengerCount,
      origin: item.origin,
      destination: item.destination,
      state: item.state,
    },
    geometry: { type: 'Point', coordinates: [Number(item.lon), Number(item.lat)] },
  })).filter((feature) => Number.isFinite(feature.geometry.coordinates[0]) && Number.isFinite(feature.geometry.coordinates[1]));
  const cache = state.sim.renderCache;
  const geoJsonKey = features
    .map((feature) => `${feature.properties.aircraftId}:${feature.properties.state}:${feature.geometry.coordinates.map((v) => v.toFixed(4)).join(',')}`)
    .join('|');
  if (aircraftSource && (force || cache.geoJsonKey !== geoJsonKey)) {
    cache.geoJsonKey = geoJsonKey;
    cache.lastGeoJsonMs = renderMs;
    aircraftSource.setData({
      type: 'FeatureCollection',
      features,
    });
  }
  updateLiveAircraftPopup(features);
}

function clearLiveMapOverlays() {
  state.sim.activeAircraftPopup?.popup?.remove();
  state.sim.activeAircraftPopup = { aircraftId: null, popup: null, contentKey: '' };
  drawAirspaceAircraft([], { force: true });
  const routeSource = state.map?.getSource('overlay-sim-routes');
  if (routeSource) routeSource.setData({ type: 'FeatureCollection', features: [] });
  document.querySelectorAll('.sim-aircraft-marker').forEach((el) => el.remove());
}

function resetLiveRenderCache() {
  state.sim.renderCache = {
    routeStatsVersion: -1,
    geoJsonKey: '',
    logKey: '',
    detailKey: '',
    metricsKey: '',
    lastPanelMs: 0,
    lastMetricsMs: 0,
    lastDetailMs: 0,
    lastLogMs: 0,
    lastCanvasMs: 0,
    lastMapMs: 0,
    lastGeoJsonMs: 0,
  };
}
function normalizeAircraftTypeId(typeId, capacity) {
  if (['a2', 'a4', 'a6', 'a8'].includes(typeId)) return typeId;
  const seats = Number(capacity);
  if (seats <= 2) return 'a2';
  if (seats <= 4) return 'a4';
  if (seats <= 6) return 'a6';
  return 'a8';
}

function buildLiveVertiportSnapshot(live, vp) {
  if (!live || !vp) return null;
  const aircraft = [];
  let queuedAircraft = 0;
  let activeAircraft = 0;
  for (const ac of live.aircraft.values()) {
    if (ac.state === 'available' && ac.locationVertiportId === vp.id && ac.gateId) {
      const gate = vp.model.entities.get(ac.gateId);
      if (gate) {
        aircraft.push({ id: ac.id, typeId: ac.typeId, state: ac.state, x: gate.x, y: gate.y });
      }
      continue;
    }
    if (ac.internal?.vertiportId !== vp.id) continue;
    const segment = currentLiveSegment(ac.internal.segments, live.nowSeconds);
    const position = segment ? liveSegmentPosition(segment, live.nowSeconds) : null;
    if (!position) continue;
    activeAircraft += 1;
    if (segment.state === 'waiting' || segment.state === 'clearance') queuedAircraft += 1;
    aircraft.push({
      id: ac.id,
      typeId: ac.typeId,
      state: segment.state,
      x: position.x,
      y: position.y,
      altitude: position.altitude || 0,
    });
  }
  return {
    layout: vp.layout,
    timeLabel: formatClockSeconds(live.nowSeconds),
    aircraft,
    stats: { activeAircraft, queuedAircraft },
  };
}

function openLiveVertiportModal() {
  const live = state.sim.live;
  const vp = live?.vertiports.get(state.sim.selectedVertiportId);
  if (!live || !vp) return;
  state.sim.vpModalOpen = true;
  const modal = document.getElementById('sim-vp-modal');
  if (modal) modal.hidden = false;
  document.body.classList.add('has-sim-vp-modal');
  renderLiveVertiportModal(buildLiveVertiportSnapshot(live, vp), vp, live, true);
}

function closeLiveVertiportModal() {
  state.sim.vpModalOpen = false;
  const modal = document.getElementById('sim-vp-modal');
  if (modal) modal.hidden = true;
  document.body.classList.remove('has-sim-vp-modal');
}

function renderLiveVertiportModal(snapshot, vp, live = state.sim.live, force = false) {
  if (!state.sim.vpModalOpen && !force) return;
  const modal = document.getElementById('sim-vp-modal');
  if (!modal || modal.hidden || !snapshot?.layout || !vp) return;
  setText('sim-vp-modal-title', `${vp.code || '-'} · ${vp.name}`);
  setText(
    'sim-vp-modal-meta',
    `출발 ${fmtNumber(vp.departures)}편 · 도착 ${fmtNumber(vp.arrivals)}편 · ${formatClockSeconds(live?.nowSeconds || 0)}`
  );
  drawVertiportSnapshotToCanvas(document.getElementById('sim-vp-modal-canvas'), snapshot);
}

function renderVertiportSnapshotCanvas(snapshot) {
  const canvas = document.getElementById('sim-vp-canvas');
  drawVertiportSnapshotToCanvas(canvas, snapshot);
}

function drawVertiportSnapshotToCanvas(canvas, snapshot) {
  if (!canvas || !snapshot?.layout) return;
  const ctx = canvas.getContext('2d');
  const layout = snapshot.layout || {};
  const grid = layout.grid || {};
  const width = Number(grid.width || 1000);
  const height = Number(grid.height || 720);
  const sx = canvas.width / Math.max(1, width);
  const sy = canvas.height / Math.max(1, height);
  const scale = Math.min(sx, sy);
  const ox = (canvas.width - width * scale) / 2;
  const oy = (canvas.height - height * scale) / 2;
  const x = (v) => ox + Number(v || 0) * scale;
  const y = (v) => oy + Number(v || 0) * scale;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#0b1420';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#203148';
  ctx.lineWidth = 1;
  ctx.strokeRect(ox, oy, width * scale, height * scale);

  const entities = new Map((layout.entities || []).map((entity) => [entity.id, entity]));
  ctx.lineWidth = 1.4;
  for (const link of layout.links || []) {
    const a = entities.get(link.from);
    const b = entities.get(link.to);
    if (!a || !b) continue;
    ctx.strokeStyle = (a.type === 'fato' || b.type === 'fato') ? '#35557c' : '#263b55';
    ctx.beginPath();
    ctx.moveTo(x(a.x), y(a.y));
    ctx.lineTo(x(b.x), y(b.y));
    ctx.stroke();
  }

  for (const entity of layout.entities || []) {
    const px = x(entity.x), py = y(entity.y);
    if (entity.type === 'gate') {
      ctx.fillStyle = '#143a2b';
      ctx.strokeStyle = '#34d399';
      ctx.fillRect(px - 9, py - 7, 18, 14);
      ctx.strokeRect(px - 9, py - 7, 18, 14);
    } else if (entity.type === 'fato') {
      ctx.fillStyle = '#1d3555';
      ctx.strokeStyle = '#38bdf8';
      ctx.beginPath();
      ctx.arc(px, py, 11, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    } else if (LIVE_AIR_POINT_TYPES.has(entity.type)) {
      ctx.fillStyle = entity.type === 'takeoffPoint' ? '#f59e0b' : entity.type === 'landingPoint' ? '#a78bfa' : '#22d3ee';
      ctx.beginPath();
      ctx.arc(px, py, 5, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.fillStyle = '#64748b';
      ctx.beginPath();
      ctx.arc(px, py, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  for (const ac of snapshot.aircraft || []) {
    ctx.fillStyle = aircraftColor(ac.typeId);
    ctx.strokeStyle = '#08111f';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x(ac.x), y(ac.y), 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#e6edf5';
    ctx.font = '10px monospace';
    ctx.fillText(String(ac.id || '').slice(-4), x(ac.x) + 9, y(ac.y) + 3);
  }

  const stats = snapshot.stats || {};
  ctx.fillStyle = '#aab6c5';
  ctx.font = '11px monospace';
  ctx.fillText(`${snapshot.timeLabel || ''}  active ${stats.activeAircraft || 0}  queued ${stats.queuedAircraft || 0}`, 10, canvas.height - 10);
}

function aircraftColor(typeId) {
  if (typeId === 'a2') return '#94a3b8';
  if (typeId === 'a4') return '#38bdf8';
  if (typeId === 'a6') return '#34d399';
  if (typeId === 'a8') return '#f59e0b';
  return '#e5e7eb';
}

/* Convert editor layout JSON into a routing/resource model.
 * Ground links are used for gate <-> FATO movement; air links connect FATO to
 * takeoff/landing points for vertical procedure timing. */
function buildLiveLayoutModel(layout) {
  const normalized = {
    ...layout,
    simulationParameters: {
      vehicle: {
        groundSpeedMps: 5,
        airSpeedMps: 35,
        verticalSpeedMps: 3,
        ...(layout.simulationParameters?.vehicle || {}),
      },
      gateProcedure: {
        engineStartAndTowDisconnectMinutes: 4,
        engineStopAndTowConnectMinutes: 3,
        groundHandlingMinutes: 10,
        ...(layout.simulationParameters?.gateProcedure || {}),
      },
      fatoProcedure: {
        postOperationLockMinutes: 1,
        ...(layout.simulationParameters?.fatoProcedure || {}),
      },
    },
  };
  const entities = new Map((normalized.entities || []).map((entity) => [entity.id, { ...entity }]));
  const links = [];
  for (const link of normalized.links || []) {
    const from = entities.get(link.from);
    const to = entities.get(link.to);
    if (!from || !to) continue;
    links.push({
      ...link,
      fromEntity: from,
      toEntity: to,
      ends: [from, to],
      distance: liveDistance(from, to),
      isAirLink: LIVE_AIR_POINT_TYPES.has(from.type) || LIVE_AIR_POINT_TYPES.has(to.type),
    });
  }
  const groundLinks = links.filter((link) => !link.isAirLink);
  const airLinks = links.filter((link) => link.isAirLink);
  const groundAdjacency = {};
  for (const id of entities.keys()) groundAdjacency[id] = [];
  for (const link of groundLinks) {
    groundAdjacency[link.from]?.push({ node: link.to, link, cost: link.distance });
    groundAdjacency[link.to]?.push({ node: link.from, link, cost: link.distance });
  }
  return {
    layout: normalized,
    entities,
    links,
    groundLinks,
    airLinks,
    groundAdjacency,
    gates: [...entities.values()].filter((entity) => entity.type === 'gate'),
    fatos: [...entities.values()].filter((entity) => entity.type === 'fato'),
    nodes: [...entities.values()].filter((entity) => entity.type === 'node'),
    candidateCache: {
      takeoff: new Map(),
      landing: new Map(),
    },
  };
}

function initLiveResources(model) {
  return {
    links: Object.fromEntries(model.links.map((link) => [link.id, 0])),
    fatos: Object.fromEntries(model.fatos.map((fato) => [fato.id, 0])),
    gates: Object.fromEntries(model.gates.map((gate) => [gate.id, 0])),
    nodes: Object.fromEntries(model.nodes.map((node) => [node.id, 0])),
    linkReservations: Object.fromEntries(model.links.map((link) => [link.id, []])),
    nodeReservations: Object.fromEntries(model.nodes.map((node) => [node.id, []])),
  };
}

/* Reserve gate/FATO/link/node resources for one departure and return the full
 * timed segment list. This is the browser-side counterpart of vp_sim routing. */
function scheduleLiveDeparture(vp, aircraft, requestTime) {
  const candidates = buildLiveTakeoffCandidates(aircraft.gateId, vp.model);
  const parameters = vp.layout.simulationParameters;
  const startProcedureSeconds = minutesToSeconds(parameters.gateProcedure.engineStartAndTowDisconnectMinutes);
  const lockSeconds = minutesToSeconds(parameters.fatoProcedure.postOperationLockMinutes);
  const groundSpeed = positiveNumber(parameters.vehicle.groundSpeedMps, 1);
  const airSpeed = positiveNumber(parameters.vehicle.airSpeedMps, 1);
  const verticalSpeed = positiveNumber(parameters.vehicle.verticalSpeedMps, 1);
  let best = null;
  for (const candidate of candidates) {
    let pathStartTime = requestTime;
    for (let attempt = 0; attempt < 16; attempt += 1) {
      const resources = cloneLiveResources(vp.resources);
      const airTravelSeconds = liveAirTravelTime(candidate.fato, candidate.airPoint, airSpeed, verticalSpeed);
      const terminalReadyTime = Math.max(
        resources.fatos[candidate.fato.id] || 0,
        resources.links[candidate.airLink.id] || 0
      );
      const segments = [];
      const ground = reserveLivePath({
        path: candidate.groundPath,
        startTime: pathStartTime,
        resources,
        model: vp.model,
        speed: groundSpeed,
        terminalResourceId: candidate.fato.id,
        terminalResourceMap: resources.fatos,
        terminalReadyTime,
        terminalEntryRequiresResourceClear: true,
        terminalWaitDescription: 'FATO/takeoff path wait',
      });
      if (ground.blockedUntil) {
        pathStartTime += Math.max(1, Number(ground.waitDelay) || 1);
        continue;
      }
      if (pathStartTime > requestTime) {
        const gateEntity = vp.model.entities.get(aircraft.gateId);
        if (gateEntity) segments.push(stationaryLiveSegment(gateEntity, requestTime, pathStartTime, 'waiting', 'gate hold'));
      }
      segments.push(...ground.segments);
      let procedureStart = ground.endTime;
      let airStart = procedureStart + startProcedureSeconds;
      const reservedAirStart = findLiveReservationStart(
        resources.linkReservations?.[candidate.airLink.id],
        airStart,
        airTravelSeconds + LIVE_LINK_CLEARANCE_SECONDS
      );
      if (!Number.isFinite(reservedAirStart)) break;
      if (reservedAirStart > airStart) {
        const waitEnd = Math.max(procedureStart, reservedAirStart - startProcedureSeconds);
        if (waitEnd > procedureStart) {
          segments.push(stationaryLiveSegment(candidate.fato, procedureStart, waitEnd, 'waiting', 'air corridor wait'));
        }
        procedureStart = waitEnd;
        airStart = reservedAirStart;
      }
      segments.push(stationaryLiveSegment(candidate.fato, procedureStart, airStart, 'procedure', 'engine start'));
      const airEnd = airStart + airTravelSeconds;
      resources.fatos[candidate.fato.id] = airEnd + lockSeconds;
      reserveLiveAirLink(resources, candidate.airLink.id, airStart, airEnd);
      segments.push(movingLiveSegment(candidate.fato, candidate.airPoint, airStart, airEnd, 'airborne', 'takeoff'));
      const gateReleaseTime = firstLiveMovementStart(segments) || pathStartTime;
      resources.gates[aircraft.gateId] = gateReleaseTime;
      if (!Number.isFinite(airEnd)) break;
      if (!best || airEnd < best.completionTime) {
        best = {
          resources,
          segments,
          gateReleaseTime,
          completionTime: airEnd,
          fatoId: candidate.fato.id,
        };
      }
      break;
    }
  }
  if (!best) return null;
  commitLiveResources(vp.resources, best.resources);
  return best;
}

/* Reserve destination FATO/gate resources for one arrival. The aircraft remains
 * in arrivalHold until a feasible landing path is available. */
function scheduleLiveLanding(vp, aircraft, requestTime) {
  const parameters = vp.layout.simulationParameters;
  const stopAndConnectSeconds = minutesToSeconds(parameters.gateProcedure.engineStopAndTowConnectMinutes);
  const handlingSeconds = minutesToSeconds(parameters.gateProcedure.groundHandlingMinutes);
  const lockSeconds = minutesToSeconds(parameters.fatoProcedure.postOperationLockMinutes);
  const groundSpeed = positiveNumber(parameters.vehicle.groundSpeedMps, 1);
  const airSpeed = positiveNumber(parameters.vehicle.airSpeedMps, 1);
  const verticalSpeed = positiveNumber(parameters.vehicle.verticalSpeedMps, 1);
  let best = null;
  for (const gate of vp.model.gates) {
    const candidates = buildLiveLandingCandidates(gate.id, vp.model);
    for (const candidate of candidates) {
      let landingRequestTime = requestTime;
      for (let attempt = 0; attempt < 16; attempt += 1) {
        const resources = cloneLiveResources(vp.resources);
        const segments = [];
        const airTravelSeconds = liveAirTravelTime(candidate.airPoint, candidate.fato, airSpeed, verticalSpeed);
        const airStart = Math.max(
          landingRequestTime,
          resources.links[candidate.airLink.id] || 0,
          resources.fatos[candidate.fato.id] || 0
        );
        if (!Number.isFinite(airStart)) break;
        const touchdownTime = airStart + airTravelSeconds;
        const linkReserveStart = landingRequestTime;
        const linkConflictEnd = findLiveReservationConflictEnd(
          resources.linkReservations?.[candidate.airLink.id],
          linkReserveStart,
          touchdownTime + LIVE_LINK_CLEARANCE_SECONDS
        );
        if (Number.isFinite(linkConflictEnd)) {
          landingRequestTime = Math.max(landingRequestTime + 1, linkConflictEnd);
          continue;
        }
        reserveLiveAirLink(resources, candidate.airLink.id, linkReserveStart, touchdownTime);
        const groundStart = touchdownTime + lockSeconds + stopAndConnectSeconds;
        const ground = reserveLivePath({
          path: candidate.groundPath,
          startTime: groundStart,
          resources,
          model: vp.model,
          speed: groundSpeed,
          terminalResourceId: gate.id,
          terminalResourceMap: resources.gates,
          terminalWaitDescription: 'gate wait',
        });
        if (ground.blockedUntil) {
          landingRequestTime += Math.max(1, Number(ground.waitDelay) || 1);
          continue;
        }
        if (landingRequestTime > requestTime) {
          segments.push(externalLiveWaitingSegment(requestTime, landingRequestTime, 'waiting', 'external arrival hold'));
        }
        if (airStart > landingRequestTime) {
          segments.push(stationaryLiveSegment(candidate.airPoint, landingRequestTime, airStart, 'waiting', 'arrival hold'));
        }
        segments.push(movingLiveSegment(candidate.airPoint, candidate.fato, airStart, touchdownTime, 'airborne', 'landing'));
        segments.push(stationaryLiveSegment(candidate.fato, touchdownTime, touchdownTime + lockSeconds, 'fatoLock', 'fato lock'));
        segments.push(stationaryLiveSegment(candidate.fato, touchdownTime + lockSeconds, groundStart, 'procedure', 'engine stop'));
        segments.push(...ground.segments);
        const fatoExitTime = firstLiveMovementFromEntityEnd(ground.segments, candidate.fato.id, groundStart);
        resources.fatos[candidate.fato.id] = Math.max(groundStart, fatoExitTime);
        const gateArrivalTime = ground.endTime;
        const readyTime = gateArrivalTime + handlingSeconds;
        resources.gates[gate.id] = Number.POSITIVE_INFINITY;
        segments.push(stationaryLiveSegment(gate, gateArrivalTime, readyTime, 'handling', 'turnaround'));
        if (!Number.isFinite(readyTime)) break;
        if (!best || gateArrivalTime < best.gateArrivalTime) {
          best = {
            resources,
            segments,
            gateId: gate.id,
            fatoId: candidate.fato.id,
            startTime: requestTime,
            touchdownTime,
            gateArrivalTime,
            readyTime,
          };
        }
        break;
      }
    }
  }
  if (!best) return null;
  commitLiveResources(vp.resources, best.resources);
  return best;
}

/* Conflict avoidance core: walks a path and reserves links/nodes/terminal
 * resources so overlapping movements wait instead of crossing through each other. */
function reserveLivePath(options) {
  const {
    path,
    startTime,
    resources,
    model,
    speed,
    terminalResourceId,
    terminalResourceMap,
    terminalReadyTime,
    terminalEntryRequiresResourceClear,
    terminalWaitDescription,
  } = options;
  const segments = [];
  let currentTime = startTime;
  if (!path?.links?.length) return { segments, endTime: currentTime };
  for (let index = 0; index < path.links.length; index += 1) {
    const link = path.links[index];
    const fromEntity = model.entities.get(path.nodes[index]);
    const toEntity = model.entities.get(path.nodes[index + 1]);
    if (!fromEntity || !toEntity) continue;
    const travelSeconds = link.distance / speed;
    const linkReservationSeconds = travelSeconds + LIVE_LINK_CLEARANCE_SECONDS;
    const isTerminalLink = !!(
      terminalResourceId &&
      index === path.links.length - 1 &&
      toEntity.id === terminalResourceId
    );
    let terminalReadyStart = 0;
    if (isTerminalLink) {
      const readyTime = terminalReadyTime ?? (terminalResourceMap?.[terminalResourceId] || 0);
      terminalReadyStart = terminalEntryRequiresResourceClear ? readyTime : readyTime - travelSeconds;
    }
    let linkStart = Math.max(currentTime, terminalReadyStart);
    let linkEnd = linkStart + travelSeconds;
    for (let attempt = 0; attempt < 8; attempt += 1) {
      linkStart = findLiveReservationStart(resources.linkReservations?.[link.id], linkStart, linkReservationSeconds);
      if (fromEntity.type === 'node') {
        linkStart = findLiveReservationStart(
          resources.nodeReservations?.[fromEntity.id],
          linkStart,
          LIVE_NODE_CLEARANCE_SECONDS
        );
      }
      linkEnd = linkStart + travelSeconds;
      if (toEntity.type !== 'node') break;
      const targetNodeStart = findLiveReservationStart(
        resources.nodeReservations?.[toEntity.id],
        linkStart,
        travelSeconds + LIVE_NODE_CLEARANCE_SECONDS
      );
      if (targetNodeStart <= linkStart + 0.001) break;
      linkStart = targetNodeStart;
    }
    if (!Number.isFinite(linkStart)) return { segments, endTime: Number.POSITIVE_INFINITY };
    if (linkStart > currentTime) {
      if (fromEntity.type === 'node') {
        // A node may be used as a short queue point only while no other aircraft
        // is scheduled to occupy that same node during the waiting window.
        const conflictEnd = findLiveReservationConflictEnd(
          resources.nodeReservations?.[fromEntity.id],
          currentTime,
          linkStart + LIVE_NODE_CLEARANCE_SECONDS
        );
        if (Number.isFinite(conflictEnd)) {
          return {
            segments,
            endTime: Number.POSITIVE_INFINITY,
            blockedUntil: conflictEnd,
            blockedAtTime: currentTime,
            waitDelay: Math.max(1, conflictEnd - currentTime),
            waitAt: fromEntity.id,
          };
        }
      }
      reserveLiveWaitingPosition(resources, fromEntity, currentTime, linkStart);
      segments.push(stationaryLiveSegment(
        fromEntity,
        currentTime,
        linkStart,
        'waiting',
        isTerminalLink && terminalReadyStart > currentTime ? terminalWaitDescription : 'link/node wait'
      ));
    }
    addLiveReservation(resources.linkReservations, link.id, linkStart, linkEnd + LIVE_LINK_CLEARANCE_SECONDS);
    reserveLiveDepartingNode(resources, fromEntity, linkStart);
    segments.push(movingLiveSegment(fromEntity, toEntity, linkStart, linkEnd, 'taxi', 'ground move'));
    currentTime = linkEnd;
    if (toEntity.type === 'node') {
      const clearTime = currentTime + LIVE_NODE_CLEARANCE_SECONDS;
      // Claim the next node from movement start, not only from arrival. This
      // keeps following aircraft from rolling early toward an occupied node.
      addLiveReservation(resources.nodeReservations, toEntity.id, linkStart, clearTime);
      segments.push(stationaryLiveSegment(toEntity, currentTime, clearTime, 'clearance', 'node clearance'));
      currentTime = clearTime;
    }
  }
  return { segments, endTime: currentTime };
}

function buildLiveTakeoffCandidates(gateId, model) {
  const cached = model.candidateCache?.takeoff?.get(gateId);
  if (cached) return cached;
  const candidates = [];
  for (const airLink of model.airLinks) {
    const fato = airLink.ends.find((entity) => entity.type === 'fato');
    const airPoint = airLink.ends.find((entity) => isLiveTakeoffAirPoint(entity));
    if (!fato || !airPoint || !canUseLiveFatoForAirPoint(fato, airPoint)) continue;
    const groundPath = liveDijkstra(model.groundAdjacency, gateId, fato.id);
    if (groundPath) candidates.push({ fato, airPoint, airLink, groundPath });
  }
  model.candidateCache?.takeoff?.set(gateId, candidates);
  return candidates;
}

function buildLiveLandingCandidates(gateId, model) {
  const cached = model.candidateCache?.landing?.get(gateId);
  if (cached) return cached;
  const candidates = [];
  for (const airLink of model.airLinks) {
    const fato = airLink.ends.find((entity) => entity.type === 'fato');
    const airPoint = airLink.ends.find((entity) => isLiveLandingAirPoint(entity));
    if (!fato || !airPoint || !canUseLiveFatoForAirPoint(fato, airPoint)) continue;
    const groundPath = liveDijkstra(model.groundAdjacency, fato.id, gateId);
    if (groundPath) candidates.push({ fato, airPoint, airLink, groundPath });
  }
  model.candidateCache?.landing?.set(gateId, candidates);
  return candidates;
}

function liveDijkstra(adjacency, start, goal) {
  if (start === goal) return { nodes: [start], links: [], cost: 0 };
  const distances = { [start]: 0 };
  const previous = {};
  const unvisited = new Set(Object.keys(adjacency));
  while (unvisited.size) {
    let current = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (const node of unvisited) {
      const distanceValue = distances[node] ?? Number.POSITIVE_INFINITY;
      if (distanceValue < bestDistance) {
        current = node;
        bestDistance = distanceValue;
      }
    }
    if (!current || bestDistance === Number.POSITIVE_INFINITY) break;
    unvisited.delete(current);
    if (current === goal) break;
    for (const edge of adjacency[current] || []) {
      if (!unvisited.has(edge.node)) continue;
      const alt = bestDistance + edge.cost;
      if (alt < (distances[edge.node] ?? Number.POSITIVE_INFINITY)) {
        distances[edge.node] = alt;
        previous[edge.node] = { node: current, link: edge.link };
      }
    }
  }
  if (!previous[goal]) return null;
  const nodes = [goal];
  const links = [];
  let current = goal;
  while (current !== start) {
    const step = previous[current];
    if (!step) return null;
    links.unshift(step.link);
    nodes.unshift(step.node);
    current = step.node;
  }
  return { nodes, links, cost: distances[goal] };
}

function requestLiveRoute(live, originId, destinationId) {
  const key = routeKey(originId, destinationId);
  if (live.failedRoutes.has(key)) return null;
  if (live.routeCache.has(key)) return live.routeCache.get(key);
  if (state.routeCache?.has(key)) {
    const cached = state.routeCache.get(key);
    live.routeCache.set(key, cached);
    return cached;
  }
  if (live.pendingRoutes.has(key)) return null;
  const origin = live.vertiports.get(originId);
  const destination = live.vertiports.get(destinationId);
  if (!origin || !destination) return null;
  const promise = fetchJson('/api/route', {
    method: 'POST',
    body: JSON.stringify({ from: origin.name, to: destination.name, withProfile: true }),
  })
    .then((route) => {
      const normalized = normalizeLiveRoute(route, origin, destination);
      live.routeCache.set(key, normalized);
      state.routeCache?.set(key, normalized);
    })
    .catch((err) => {
      console.error('route load failed', key, err);
      live.failedRoutes.add(key);
    })
    .finally(() => live.pendingRoutes.delete(key));
  live.pendingRoutes.set(key, promise);
  return null;
}

function warmLiveRoutesForCurrentHour(live) {
  const originMap = live.hourlyDemand.get(live.currentHour) || new Map();
  let requested = 0;
  for (const [originId, destMap] of originMap.entries()) {
    for (const destinationId of destMap.keys()) {
      requestLiveRoute(live, originId, destinationId);
      requested += 1;
      if (requested >= 48) return;
    }
  }
}

function normalizeLiveRoute(route, origin, destination) {
  let geometry = (route.geometry?.length ? route.geometry : [[origin.lon, origin.lat], [destination.lon, destination.lat]])
    .map((point) => [Number(point[0]), Number(point[1])])
    .filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));
  if (!isLiveGeometryInBounds(geometry)) {
    const swapped = geometry.map((point) => [point[1], point[0]]);
    if (isLiveGeometryInBounds(swapped)) geometry = swapped;
  }
  if (geometry.length < 2 || !isLiveGeometryInBounds(geometry)) {
    throw new Error(`Invalid route geometry: ${origin.name} -> ${destination.name}`);
  }
  geometry = anchorLiveRouteGeometry(geometry, origin, destination);
  const totalMeters = Math.max(Number(route.distanceKm || 0) * 1000, liveGeometryDistanceMeters(geometry), 1);
  const profileDuration = (route.missionProfile?.phases || [])
    .filter((phase) => ['C', 'E', 'F', 'G', 'I'].includes(phase.code))
    .reduce((sum, phase) => sum + (Number(phase.durationS) || 0), 0);
  return {
    key: routeKey(origin.id, destination.id),
    origin: origin.name,
    destination: destination.name,
    path: Array.isArray(route.path) && route.path.length ? route.path.map((item) => String(item)) : [origin.name, destination.name],
    geometry,
    distanceKm: totalMeters / 1000,
    missionProfile: route.missionProfile || null,
    airDurationSeconds: Math.max(60, profileDuration || (totalMeters / 51.4) + 180),
  };
}

function buildScheduledFlightSegments(route, origin, destination) {
  const geometry = Array.isArray(route?.geometry) && route.geometry.length >= 2
    ? route.geometry
    : [[Number(origin?.lon), Number(origin?.lat)], [Number(destination?.lon), Number(destination?.lat)]];
  const validGeometry = geometry
    .map((point) => [Number(point?.[0]), Number(point?.[1])])
    .filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));
  if (validGeometry.length < 2) return [];

  const phases = Array.isArray(route?.missionProfile?.phases) ? route.missionProfile.phases : [];
  const phaseByCode = new Map(phases.map((phase) => [String(phase.code || phase.phase || '').toUpperCase(), phase]));
  const originPoint = validGeometry[0];
  const destinationPoint = validGeometry[validGeometry.length - 1];
  const segments = [];

  const phaseA = scheduledPhaseWithFallback(phaseByCode.get('A'), 'A');
  const phaseB = scheduledPhaseWithFallback(phaseByCode.get('B'), 'B');
  segments.push(scheduledPointSegment(phaseA, originPoint));
  segments.push(scheduledPointSegment(phaseB, originPoint));

  const airPhases = phases
    .filter((phase) => ['C', 'E', 'F', 'G', 'I'].includes(String(phase.code || '').toUpperCase()))
    .map((phase) => scheduledPhaseWithFallback(phase, String(phase.code || '').toUpperCase()));
  segments.push(...buildScheduledAirSegments(validGeometry, airPhases.length ? airPhases : [scheduledPhaseWithFallback(null, 'F')]));

  const phaseJ = scheduledPhaseWithFallback(phaseByCode.get('J'), 'J');
  const phaseK = scheduledPhaseWithFallback(phaseByCode.get('K'), 'K');
  segments.push(scheduledPointSegment(phaseJ, destinationPoint));
  segments.push(scheduledPointSegment(phaseK, destinationPoint));

  return segments.map((segment, index) => ({ ...segment, seq: index + 1 }));
}

function scheduledPhaseWithFallback(phase, code) {
  const defaults = {
    A: { altStartM: 0, altEndM: 0, speedStartMps: 3, speedEndMps: 3, distanceM: 0 },
    B: { altStartM: 0, altEndM: 15, speedStartMps: 10, speedEndMps: 10, distanceM: 15 },
    C: { altStartM: 15, altEndM: 100, speedStartMps: 36, speedEndMps: 36, distanceM: 1000 },
    E: { altStartM: 100, altEndM: 305, speedStartMps: 36, speedEndMps: 51.4, distanceM: 3000 },
    F: { altStartM: 305, altEndM: 305, speedStartMps: 51.4, speedEndMps: 51.4, distanceM: 1000 },
    G: { altStartM: 305, altEndM: 100, speedStartMps: 51.4, speedEndMps: 36, distanceM: 3000 },
    I: { altStartM: 100, altEndM: 15, speedStartMps: 36, speedEndMps: 30, distanceM: 1000 },
    J: { altStartM: 15, altEndM: 0, speedStartMps: 10, speedEndMps: 10, distanceM: 15 },
    K: { altStartM: 0, altEndM: 0, speedStartMps: 3, speedEndMps: 3, distanceM: 0 },
  };
  const fallback = defaults[code] || defaults.F;
  const source = phase || {};
  return {
    code,
    altStartM: finiteNumber(source.altStartM, fallback.altStartM),
    altEndM: finiteNumber(source.altEndM, fallback.altEndM),
    speedStartMps: finiteNumber(source.speedStartMps, fallback.speedStartMps),
    speedEndMps: finiteNumber(source.speedEndMps, fallback.speedEndMps),
    distanceM: finiteNumber(source.distanceM, fallback.distanceM),
  };
}

function buildScheduledAirSegments(geometry, phases) {
  const totalMeters = Math.max(1, liveGeometryDistanceMeters(geometry));
  const phaseSpans = scheduledPhaseSpans(phases, totalMeters);
  if (!phaseSpans.length) return [];

  const checkpoints = [0, totalMeters];
  let cursor = 0;
  for (let i = 1; i < geometry.length; i += 1) {
    cursor += haversineMeters(geometry[i - 1], geometry[i]);
    checkpoints.push(clampNumber(cursor, 0, totalMeters));
  }
  for (const span of phaseSpans) {
    checkpoints.push(span.startM, span.endM);
  }

  const ordered = [...new Set(checkpoints
    .filter((value) => Number.isFinite(Number(value)))
    .map((value) => roundNumber(clampNumber(value, 0, totalMeters), 3)))]
    .sort((a, b) => a - b);

  const segments = [];
  for (let i = 1; i < ordered.length; i += 1) {
    const startM = ordered[i - 1];
    const endM = ordered[i];
    if (endM - startM < 0.5) continue;
    const midM = (startM + endM) / 2;
    const span = phaseSpans.find((item) => midM >= item.startM && midM <= item.endM) || phaseSpans[phaseSpans.length - 1];
    const startPoint = pointAtGeometryDistance(geometry, startM);
    const endPoint = pointAtGeometryDistance(geometry, endM);
    segments.push({
      phase: span.phase.code,
      startLLA: scheduledLla(startPoint, scheduledAltitudeAtDistance(span, startM)),
      endLLA: scheduledLla(endPoint, scheduledAltitudeAtDistance(span, endM)),
      targetSpeed: scheduledTargetSpeed(span.phase),
    });
  }
  return segments;
}

function scheduledPhaseSpans(phases, totalMeters) {
  const weighted = phases.map((phase) => ({
    phase,
    meters: Math.max(0, scheduledPhaseHorizontalMeters(phase)),
  }));
  let totalWeight = weighted.reduce((sum, item) => sum + item.meters, 0);
  if (totalWeight <= 0) {
    totalWeight = weighted.length || 1;
    for (const item of weighted) item.meters = 1;
  }
  let cursor = 0;
  return weighted.map((item, index) => {
    const width = index === weighted.length - 1 ? totalMeters - cursor : (item.meters / totalWeight) * totalMeters;
    const span = {
      phase: item.phase,
      startM: cursor,
      endM: Math.min(totalMeters, cursor + Math.max(0, width)),
    };
    cursor = span.endM;
    return span;
  }).filter((span) => span.endM > span.startM);
}

function scheduledPhaseHorizontalMeters(phase) {
  const distance = Math.max(0, Number(phase?.distanceM) || 0);
  const altDelta = Math.abs((Number(phase?.altEndM) || 0) - (Number(phase?.altStartM) || 0));
  if (distance > altDelta) return Math.sqrt(Math.max(0, distance ** 2 - altDelta ** 2));
  if (String(phase?.code || '').toUpperCase() === 'F') return distance;
  return 0;
}

function scheduledPointSegment(phase, point) {
  return {
    phase: phase.code,
    startLLA: scheduledLla(point, phase.altStartM),
    endLLA: scheduledLla(point, phase.altEndM),
    targetSpeed: scheduledTargetSpeed(phase),
  };
}

function scheduledAltitudeAtDistance(span, distanceM) {
  const width = Math.max(1, span.endM - span.startM);
  const progress = clampNumber((distanceM - span.startM) / width, 0, 1);
  return roundNumber(span.phase.altStartM + (span.phase.altEndM - span.phase.altStartM) * progress, 2);
}

function scheduledTargetSpeed(phase) {
  return roundNumber(finiteNumber(phase?.speedEndMps, phase?.speedStartMps || 0), 3);
}

function scheduledLla(point, altM) {
  return {
    lat: roundNumber(Number(point?.[1]) || 0, 6),
    lon: roundNumber(Number(point?.[0]) || 0, 6),
    alt: roundNumber(Number(altM) || 0, 2),
  };
}

function pointAtGeometryDistance(geometry, distanceM) {
  const totalMeters = Math.max(1, liveGeometryDistanceMeters(geometry));
  return interpolateLiveGeometry(geometry, clampNumber(distanceM / totalMeters, 0, 1));
}

function finiteNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

/* Map-facing airspace snapshot. Aircraft are interpolated along the route
 * geometry and offset to the right of the centerline for visual separation. */
function getLiveAirspaceAircraft(live) {
  return [...live.aircraft.values()].filter((ac) => (
    ac.state === 'airspace' && ac.airspace?.route
  )).map((ac) => {
    const flight = findLiveFlight(live, ac.flightPlanId);
    const route = ac.airspace.route;
    const progress = clampNumber((live.nowSeconds - ac.airspace.startTime) / Math.max(1, ac.airspace.endTime - ac.airspace.startTime), 0, 1);
    const track = interpolateLiveGeometryTrack(route.geometry, progress);
    const offsetPoint = offsetLivePointRightOfTrack(track.point, track.from, track.to, LIVE_AIRSPACE_RIGHT_OFFSET_METERS);
    const point = isLiveCoordinateInBounds(offsetPoint[0], offsetPoint[1]) ? offsetPoint : track.point;
    if (!isLiveCoordinateInBounds(point[0], point[1])) return null;
    const typeId = normalizeAircraftTypeId(ac.typeId, ac.capacity);
    return {
      aircraftId: ac.id,
      flightPlanId: ac.flightPlanId,
      typeId,
      capacity: ac.capacity,
      passengerCount: flight?.passengerCount || 0,
      origin: live.vertiports.get(ac.originId)?.name || ac.originId,
      destination: live.vertiports.get(ac.destinationId)?.name || ac.destinationId,
      state: ac.state,
      lon: point[0],
      lat: point[1],
    };
  }).filter(Boolean);
}

function countLiveAirspaceAircraft(live, vertiportId = null) {
  return [...live.aircraft.values()].filter((ac) => {
    const inAir = ac.state === 'airspace' || ac.state === 'arrivalHold';
    if (!inAir) return false;
    if (!vertiportId) return true;
    return ac.originId === vertiportId || ac.destinationId === vertiportId;
  }).length;
}

function countLiveFleetInVertiport(live, vertiportId) {
  const counts = emptyAircraftCounts();
  for (const ac of live.aircraft.values()) {
    if (aircraftBelongsToVertiport(ac, vertiportId)) counts[ac.typeId] = (counts[ac.typeId] || 0) + 1;
  }
  return counts;
}

function aircraftBelongsToVertiport(ac, vertiportId) {
  if (!ac || !vertiportId) return false;
  if (ac.state === 'available') return ac.locationVertiportId === vertiportId;
  if (ac.state === 'departing') return ac.originId === vertiportId;
  if (ac.state === 'landing') return ac.destinationId === vertiportId;
  return false;
}

function isFlightRelatedToVertiport(flight, vertiportId) {
  return !!flight && !!vertiportId && (flight.originId === vertiportId || flight.destinationId === vertiportId);
}

function findLiveFlight(live, flightPlanId) {
  if (!flightPlanId) return null;
  if (live.flightByPlanId?.has(flightPlanId)) return live.flightByPlanId.get(flightPlanId);
  return live.flights.find((flight) => flight.flightPlanId === flightPlanId) || null;
}

function finishLiveFlightWithoutLanding(live, ac, flight) {
  if (flight && !flight.countedGateIn) {
    flight.countedGateIn = true;
    flight.status = 'arrived';
    live.servedPassengers += flight.passengerCount;
  }
  ac.state = 'available';
  ac.locationVertiportId = ac.destinationId;
  ac.originId = null;
  ac.destinationId = null;
  ac.flightPlanId = null;
  ac.internal = null;
  ac.airspace = null;
}

function nextLiveFlightPlanId(live, originId, destinationId) {
  const key = routeKey(originId, destinationId);
  const next = (live.odCounters.get(key) || 0) + 1;
  live.odCounters.set(key, next);
  return `FPL${live.portCodes.get(originId) || '00'}${live.portCodes.get(destinationId) || '00'}${String(next).padStart(3, '0')}`;
}

function incrementLiveRouteStats(live, originId, destinationId, passengerCount) {
  const key = routeKey(originId, destinationId);
  const stats = live.routeStats.get(key) || { flightCount: 0, passengerCount: 0 };
  stats.flightCount += 1;
  stats.passengerCount += passengerCount;
  live.routeStats.set(key, stats);
  live.routeStatsVersion += 1;
}

function routeKey(originId, destinationId) {
  return `${originId}->${destinationId}`;
}

function makeSeededRandom(seed) {
  let value = (Math.floor(Number(seed) || 1) >>> 0) || 1;
  return () => {
    value = Math.imul(1664525, value) + 1013904223;
    return ((value >>> 0) / 4294967296);
  };
}

function parseClockToSeconds(value) {
  const [h, m, s] = String(value || '00:00:00').split(':').map(Number);
  return (Number.isFinite(h) ? h : 0) * 3600
    + (Number.isFinite(m) ? m : 0) * 60
    + (Number.isFinite(s) ? s : 0);
}

function minutesToSeconds(value) {
  return Math.max(0, Number(value) || 0) * 60;
}

function positiveNumber(value, fallback) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : fallback;
}

function liveDistance(a, b) {
  return Math.hypot((Number(a?.x) || 0) - (Number(b?.x) || 0), (Number(a?.y) || 0) - (Number(b?.y) || 0));
}

function liveAirTravelTime(fromEntity, toEntity, airSpeed, verticalSpeed) {
  const horizontal = liveDistance(fromEntity, toEntity);
  const altitude = Math.abs(entityLiveAltitude(fromEntity) - entityLiveAltitude(toEntity));
  return Math.max(horizontal / airSpeed, altitude / verticalSpeed);
}

function entityLiveAltitude(entity) {
  return LIVE_AIR_POINT_TYPES.has(entity?.type) ? Math.max(0, Number(entity.altitude) || 0) : 0;
}

function pointFromLiveEntity(entity) {
  return {
    id: entity.id,
    type: entity.type,
    x: Number(entity.x) || 0,
    y: Number(entity.y) || 0,
    altitude: entityLiveAltitude(entity),
  };
}

function movingLiveSegment(fromEntity, toEntity, start, end, stateName, description) {
  return {
    state: stateName,
    description,
    start,
    end,
    from: pointFromLiveEntity(fromEntity),
    to: pointFromLiveEntity(toEntity),
    fromAltitude: entityLiveAltitude(fromEntity),
    toAltitude: entityLiveAltitude(toEntity),
  };
}

function stationaryLiveSegment(entity, start, end, stateName, description) {
  return { state: stateName, description, start, end, at: pointFromLiveEntity(entity) };
}

function externalLiveWaitingSegment(start, end, stateName, description) {
  return { state: stateName, description, start, end };
}

function currentLiveSegment(segments, timeSeconds) {
  const active = (segments || []).find((segment) => segment.start <= timeSeconds && timeSeconds < segment.end);
  if (active) return active;
  for (let i = (segments || []).length - 1; i >= 0; i -= 1) {
    if (segments[i].end <= timeSeconds) return segments[i];
  }
  return null;
}

function liveSegmentPosition(segment, timeSeconds) {
  if (!segment) return null;
  if (segment.at) return segment.at;
  if (!segment.from || !segment.to) return null;
  const progress = clampNumber((timeSeconds - segment.start) / Math.max(0.001, segment.end - segment.start), 0, 1);
  return {
    x: segment.from.x + (segment.to.x - segment.from.x) * progress,
    y: segment.from.y + (segment.to.y - segment.from.y) * progress,
    altitude: (segment.fromAltitude || 0) + ((segment.toAltitude || 0) - (segment.fromAltitude || 0)) * progress,
  };
}

function firstLiveMovementStart(segments) {
  const movement = segments.find((segment) => segment.from && segment.to);
  return movement ? movement.start : null;
}

function firstLiveMovementFromEntityEnd(segments, entityId, fallback) {
  const movement = segments.find((segment) => segment.from?.id === entityId && segment.to);
  return movement ? movement.end : fallback;
}

function canUseLiveFatoForAirPoint(fato, airPoint) {
  const mode = fato.fatoMode || 'both';
  if (airPoint.type === 'takeoffPoint') return mode === 'takeoff' || mode === 'both';
  if (airPoint.type === 'landingPoint') return mode === 'landing' || mode === 'both';
  if (airPoint.type === 'commonAirPoint') return mode === 'both';
  return false;
}

function isLiveTakeoffAirPoint(entity) {
  return entity?.type === 'takeoffPoint' || entity?.type === 'commonAirPoint';
}

function isLiveLandingAirPoint(entity) {
  return entity?.type === 'landingPoint' || entity?.type === 'commonAirPoint';
}

function cloneLiveResources(resources) {
  return {
    links: { ...resources.links },
    fatos: { ...resources.fatos },
    gates: { ...resources.gates },
    nodes: { ...resources.nodes },
    linkReservations: cloneLiveReservationMap(resources.linkReservations),
    nodeReservations: cloneLiveReservationMap(resources.nodeReservations),
  };
}

function commitLiveResources(target, source) {
  target.links = { ...source.links };
  target.fatos = { ...source.fatos };
  target.gates = { ...source.gates };
  target.nodes = { ...source.nodes };
  target.linkReservations = cloneLiveReservationMap(source.linkReservations);
  target.nodeReservations = cloneLiveReservationMap(source.nodeReservations);
}

function cloneLiveReservationMap(map) {
  return Object.fromEntries(
    Object.entries(map || {}).map(([id, reservations]) => [
      id,
      (reservations || []).map((item) => ({ start: item.start, end: item.end })),
    ])
  );
}

function addLiveReservation(map, id, start, end) {
  if (!map || !id || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) return;
  if (!map[id]) map[id] = [];
  const reservations = map[id];
  reservations.push({ start, end });
  const previous = reservations[reservations.length - 2];
  if (previous && (previous.start > start || (previous.start === start && previous.end > end))) {
    reservations.sort((a, b) => a.start - b.start || a.end - b.end);
  }
}

function reserveLiveAirLink(resources, linkId, start, end) {
  const releaseTime = end + LIVE_LINK_CLEARANCE_SECONDS;
  resources.links[linkId] = Math.max(resources.links[linkId] || 0, releaseTime);
  addLiveReservation(resources.linkReservations, linkId, start, releaseTime);
}

function findLiveReservationStart(reservations, desiredStart, duration) {
  let start = Math.max(0, Number(desiredStart) || 0);
  const span = Math.max(0, Number(duration) || 0);
  if (!Number.isFinite(start) || !Number.isFinite(span)) return Number.POSITIVE_INFINITY;
  for (const reservation of reservations || []) {
    const reservedStart = Number(reservation.start);
    const reservedEnd = Number(reservation.end);
    if (!Number.isFinite(reservedStart) || !Number.isFinite(reservedEnd) || reservedEnd <= reservedStart) continue;
    if (start + span <= reservedStart) return start;
    if (start < reservedEnd && start + span > reservedStart) start = reservedEnd;
  }
  return start;
}

function findLiveReservationConflictEnd(reservations, startTime, endTime) {
  const start = Number(startTime);
  const end = Number(endTime);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
  for (const reservation of reservations || []) {
    const reservedStart = Number(reservation.start);
    const reservedEnd = Number(reservation.end);
    if (!Number.isFinite(reservedStart) || !Number.isFinite(reservedEnd) || reservedEnd <= reservedStart) continue;
    if (end <= reservedStart) return null;
    if (start < reservedEnd && end > reservedStart) return reservedEnd;
  }
  return null;
}

function reserveLiveWaitingPosition(resources, entity, startTime, releaseTime) {
  if (entity.type === 'node') addLiveReservation(resources.nodeReservations, entity.id, startTime, releaseTime + LIVE_NODE_CLEARANCE_SECONDS);
  if (entity.type === 'fato') resources.fatos[entity.id] = Math.max(resources.fatos[entity.id] || 0, releaseTime);
  if (entity.type === 'gate') resources.gates[entity.id] = Math.max(resources.gates[entity.id] || 0, releaseTime);
}

function reserveLiveDepartingNode(resources, entity, departureTime) {
  if (entity.type !== 'node') return;
  addLiveReservation(resources.nodeReservations, entity.id, departureTime, departureTime + LIVE_NODE_CLEARANCE_SECONDS);
}

function liveGeometryDistanceMeters(geometry) {
  let total = 0;
  for (let i = 1; i < geometry.length; i += 1) total += haversineMeters(geometry[i - 1], geometry[i]);
  return total;
}

function anchorLiveRouteGeometry(geometry, origin, destination) {
  const points = [...geometry];
  const originPoint = [Number(origin.lon), Number(origin.lat)];
  const destinationPoint = [Number(destination.lon), Number(destination.lat)];
  if (!isLiveCoordinateInBounds(originPoint[0], originPoint[1]) || !isLiveCoordinateInBounds(destinationPoint[0], destinationPoint[1])) {
    throw new Error(`Invalid route endpoints: ${origin.name} -> ${destination.name}`);
  }
  if (haversineMeters(points[0], originPoint) > 50) points.unshift(originPoint);
  if (haversineMeters(points[points.length - 1], destinationPoint) > 50) points.push(destinationPoint);
  const deduped = [];
  for (const point of points) {
    const prev = deduped[deduped.length - 1];
    if (!prev || haversineMeters(prev, point) > 1) deduped.push(point);
  }
  return deduped;
}

function getLiveAirspaceBounds() {
  const points = [
    ...state.vertiports.map((item) => [Number(item.lon), Number(item.lat)]),
    ...state.waypoints.map((item) => [Number(item.lon), Number(item.lat)]),
  ].filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));
  if (!points.length) {
    return { minLon: 126.35, maxLon: 127.2, minLat: 37.4, maxLat: 37.7 };
  }
  return {
    minLon: Math.min(...points.map((point) => point[0])) - 0.035,
    maxLon: Math.max(...points.map((point) => point[0])) + 0.035,
    minLat: Math.min(...points.map((point) => point[1])) - 0.035,
    maxLat: Math.max(...points.map((point) => point[1])) + 0.035,
  };
}

function isLiveCoordinateInBounds(lon, lat) {
  const x = Number(lon);
  const y = Number(lat);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
  const bounds = getLiveAirspaceBounds();
  return x >= bounds.minLon && x <= bounds.maxLon && y >= bounds.minLat && y <= bounds.maxLat;
}

function isLiveGeometryInBounds(geometry) {
  return Array.isArray(geometry)
    && geometry.length >= 2
    && geometry.every((point) => isLiveCoordinateInBounds(point[0], point[1]));
}

function interpolateLiveGeometry(geometry, progress) {
  return interpolateLiveGeometryTrack(geometry, progress).point;
}

function interpolateLiveGeometryTrack(geometry, progress) {
  if (!geometry?.length) return { point: [0, 0], from: [0, 0], to: [0, 0] };
  if (geometry.length === 1) return { point: geometry[0], from: geometry[0], to: geometry[0] };
  const total = liveGeometryDistanceMeters(geometry);
  let target = total * clampNumber(progress, 0, 1);
  for (let i = 1; i < geometry.length; i += 1) {
    const a = geometry[i - 1];
    const b = geometry[i];
    const dist = haversineMeters(a, b);
    if (target <= dist || i === geometry.length - 1) {
      const t = dist <= 0 ? 0 : clampNumber(target / dist, 0, 1);
      return {
        point: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t],
        from: a,
        to: b,
      };
    }
    target -= dist;
  }
  const last = geometry[geometry.length - 1];
  return { point: last, from: geometry[geometry.length - 2] || last, to: last };
}

function offsetLivePointRightOfTrack(point, from, to, meters) {
  const lon = Number(point?.[0]);
  const lat = Number(point?.[1]);
  const fromLon = Number(from?.[0]);
  const fromLat = Number(from?.[1]);
  const toLon = Number(to?.[0]);
  const toLat = Number(to?.[1]);
  const offsetMeters = Number(meters) || 0;
  if (![lon, lat, fromLon, fromLat, toLon, toLat].every(Number.isFinite) || offsetMeters <= 0) return point;
  const metersPerLatDegree = 111320;
  const avgLatRad = ((fromLat + toLat) / 2) * Math.PI / 180;
  const metersPerLonDegree = Math.max(1, metersPerLatDegree * Math.cos(avgLatRad));
  const dx = (toLon - fromLon) * metersPerLonDegree;
  const dy = (toLat - fromLat) * metersPerLatDegree;
  const length = Math.hypot(dx, dy);
  if (length <= 0.001) return point;
  const rightEast = dy / length;
  const rightNorth = -dx / length;
  return [
    lon + (rightEast * offsetMeters) / metersPerLonDegree,
    lat + (rightNorth * offsetMeters) / metersPerLatDegree,
  ];
}

function haversineMeters(a, b) {
  const rad = Math.PI / 180;
  const lat1 = Number(a[1]) * rad;
  const lat2 = Number(b[1]) * rad;
  const dLat = (Number(b[1]) - Number(a[1])) * rad;
  const dLon = (Number(b[0]) - Number(a[0])) * rad;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
}

function clampNumber(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

/* ============================================================================
 * 8. Route calculation panel and static map overlays
 * ========================================================================== */

function setupRoutePanel() {
  const from = document.getElementById('route-from');
  const to = document.getElementById('route-to');
  if (!from || !to) return;
  const opts = state.vertiports
    .map((v) => `<option value="${escapeHtml(v.id)}">${escapeHtml(v.name)}</option>`)
    .join('');
  from.innerHTML = `<option value="">—</option>${opts}`;
  to.innerHTML = `<option value="">—</option>${opts}`;
  /* sensible defaults: pick first port and first hub if available */
  const firstPort = state.vertiports[0];
  const firstHub = state.vertiports.find((v) => v.class === 'hub');
  if (firstPort) from.value = firstPort.id;
  if (firstHub && firstHub.id !== firstPort?.id) to.value = firstHub.id;

  document.getElementById('route-calc-btn').addEventListener('click', calculateRoute);
  document.getElementById('route-clear-btn').addEventListener('click', clearRoute);
  document.getElementById('mp-close')?.addEventListener('click', hideMissionProfile);
}

async function calculateRoute() {
  const from = document.getElementById('route-from').value;
  const to = document.getElementById('route-to').value;
  const errEl = document.getElementById('route-error');
  const resEl = document.getElementById('route-result');
  errEl.hidden = true;
  if (!from || !to) {
    errEl.textContent = '출발지와 도착지를 모두 선택하세요.';
    errEl.hidden = false;
    return;
  }
  if (from === to) {
    errEl.textContent = '출발지와 도착지가 같습니다.';
    errEl.hidden = false;
    return;
  }
  try {
    const res = await fetchJson('/api/route', {
      method: 'POST',
      body: JSON.stringify({
        from, to,
        withProfile: true,
      }),
    });
    drawRoute(res);
    document.getElementById('rr-distance').textContent = `${fmtNumber(res.distanceKm)} km`;
    document.getElementById('rr-hops').textContent = `${(res.path || []).length - 2}개 wp`;
    document.getElementById('rr-path').textContent = (res.path || []).join(' → ');
    resEl.hidden = false;
    if (res.missionProfile) renderMissionProfile(res.missionProfile, res.from, res.to);
  } catch (err) {
    console.error(err);
    errEl.textContent = '경로 계산 실패: ' + (err.message || err);
    errEl.hidden = false;
    resEl.hidden = true;
    hideMissionProfile();
  }
}

function clearRoute() {
  const src = state.map?.getSource('overlay-route');
  if (src) src.setData({ type: 'FeatureCollection', features: [] });
  document.getElementById('route-result').hidden = true;
  document.getElementById('route-error').hidden = true;
  hideMissionProfile();
}

/* ----- mission profile chart (floating panel on sim map) ----- */
const PHASE_COLORS = {
  A: '#6f7f93',  /* taxi grey */
  B: '#a78bfa',  /* vertical purple */
  C: '#22d3ee',  /* sloped climb cyan */
  E: '#fbbf24',  /* accel amber */
  F: '#34d399',  /* cruise green */
  G: '#f59e0b',  /* decel orange */
  I: '#22d3ee',  /* sloped descent cyan */
  J: '#a78bfa',  /* vertical purple */
  K: '#6f7f93',  /* taxi grey */
};

function renderMissionProfile(profile, fromName, toName) {
  const panel = document.getElementById('mission-profile-panel');
  const chart = document.getElementById('mp-chart');
  const labels = document.getElementById('mp-axis-labels');
  if (!panel || !chart) return;

  const phases = profile.phases || [];
  if (!phases.length) { hideMissionProfile(); return; }

  /* ----- header text ----- */
  document.getElementById('mp-route').textContent = `${fromName} → ${toName}`;
  const totalSec = Math.round(profile.totalDurationS || 0);
  const mm = Math.floor(totalSec / 60);
  const ss = totalSec % 60;
  const peakKt = (profile.peakSpeedMps || 0) * 1.94384;
  document.getElementById('mp-meta').innerHTML = `
    <span class="mp-meta-item">⏱ <strong>${mm}분 ${ss}초</strong></span>
    <span class="mp-meta-item">📏 <strong>${(profile.totalDistanceM / 1000).toFixed(2)} km</strong></span>
    <span class="mp-meta-item">🚀 peak <strong>${peakKt.toFixed(0)} kt</strong></span>
    <span class="mp-meta-item">↕ cruise <strong>${profile.cruiseAltM} m</strong></span>
  `;

  /* ----- chart geometry ----- */
  const W = 800, H = 220;
  const padL = 50, padR = 14, padT = 18, padB = 36;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const totalDist = phases.reduce((s, p) => s + p.distanceM, 0) || 1;
  const maxAlt = Math.max(profile.cruiseAltM || 305, ...phases.map((p) => Math.max(p.altStartM, p.altEndM))) || 1;
  const altPad = maxAlt * 0.15;
  const altMax = maxAlt + altPad;

  const xOf = (d) => padL + (d / totalDist) * innerW;
  const yOf = (alt) => padT + innerH - (alt / altMax) * innerH;

  /* ----- build SVG content ----- */
  const parts = [];

  /* axes grid (horizontal lines at 0, 100, 200, 300m etc.) */
  const altSteps = altMax > 300 ? [0, 100, 200, 300, 400] : [0, 50, 100, 150, 200];
  for (const a of altSteps) {
    if (a > altMax) break;
    const y = yOf(a);
    parts.push(`<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="#26354c" stroke-width="0.6" />`);
    parts.push(`<text x="${padL - 6}" y="${y + 3}" fill="#7a8fab" font-size="10" text-anchor="end" font-family="monospace">${a}</text>`);
  }
  /* corridor altitude reference line */
  const corridorY = yOf(profile.cruiseAltM || 305);
  parts.push(`<line x1="${padL}" y1="${corridorY}" x2="${W - padR}" y2="${corridorY}"
                    stroke="#34d399" stroke-width="0.8" stroke-dasharray="4,4" opacity="0.5" />`);
  parts.push(`<text x="${W - padR - 4}" y="${corridorY - 4}" fill="#34d399" font-size="9.5"
                    text-anchor="end" font-family="monospace">corridor ${profile.cruiseAltM}m</text>`);

  /* phase areas: trapezoid below altitude curve, color-coded */
  let cum = 0;
  for (const p of phases) {
    const x0 = xOf(cum);
    const x1 = xOf(cum + p.distanceM);
    const y0 = yOf(p.altStartM);
    const y1 = yOf(p.altEndM);
    const yBase = padT + innerH;
    const color = PHASE_COLORS[p.code] || '#54657c';

    /* fill area under altitude curve */
    parts.push(`<path d="M ${x0} ${yBase} L ${x0} ${y0} L ${x1} ${y1} L ${x1} ${yBase} Z"
                       fill="${color}" opacity="0.18" />`);
    /* altitude line */
    parts.push(`<line x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}"
                       stroke="${color}" stroke-width="2.2" stroke-linecap="round" />`);
    /* phase boundary marker (vertical line) */
    if (cum > 0) {
      parts.push(`<line x1="${x0}" y1="${padT}" x2="${x0}" y2="${yBase}"
                         stroke="#3d567a" stroke-width="0.5" stroke-dasharray="2,3" opacity="0.5" />`);
    }
    /* phase letter label centered above */
    if (x1 - x0 > 14) {
      const cx = (x0 + x1) / 2;
      parts.push(`<text x="${cx}" y="${padT + 12}" fill="${color}" font-size="11"
                         font-weight="700" text-anchor="middle" font-family="monospace">${p.code}</text>`);
      /* speed label below the letter when phase is wide enough */
      if (x1 - x0 > 36) {
        const spd = p.speedStartMps === p.speedEndMps
          ? `${Math.round(p.speedStartMps)}`
          : `${Math.round(p.speedStartMps)}→${Math.round(p.speedEndMps)}`;
        parts.push(`<text x="${cx}" y="${yBase + 14}" fill="#aab6c5" font-size="9"
                           text-anchor="middle" font-family="monospace">${spd} m/s</text>`);
      }
    }
    cum += p.distanceM;
  }

  /* baseline */
  parts.push(`<line x1="${padL}" y1="${padT + innerH}" x2="${W - padR}" y2="${padT + innerH}"
                    stroke="#5a7aa8" stroke-width="1" />`);

  /* x-axis distance labels (km) at 0/25/50/75/100% */
  const totalKm = totalDist / 1000;
  const kmDigits = totalKm > 10 ? 0 : 1;
  for (let i = 0; i <= 4; i++) {
    const ratio = i / 4;
    const x = padL + ratio * innerW;
    const km = (totalKm * ratio).toFixed(kmDigits);
    parts.push(`<text x="${x}" y="${H - 4}" fill="#7a8fab" font-size="9"
                       text-anchor="middle" font-family="monospace">${km} km</text>`);
  }

  chart.innerHTML = parts.join('\n');

  /* phase legend below the chart */
  labels.innerHTML = phases.map((p) => `
    <span class="mp-legend-item">
      <span class="mp-legend-dot" style="background:${PHASE_COLORS[p.code] || '#54657c'}"></span>
      <span class="mp-legend-code">${p.code}</span>
      <span class="mp-legend-name">${p.name}</span>
    </span>
  `).join('');

  panel.hidden = false;
}

function hideMissionProfile() {
  const panel = document.getElementById('mission-profile-panel');
  if (panel) panel.hidden = true;
}

function drawRoute(res) {
  const src = state.map?.getSource('overlay-route');
  if (!src) return;
  src.setData({
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { from: res.from, to: res.to, distanceKm: res.distanceKm },
      geometry: { type: 'LineString', coordinates: res.geometry || [] },
    }],
  });
  /* fly to bounds of the route so user can see the whole thing */
  const coords = res.geometry || [];
  if (coords.length >= 2 && state.map) {
    const bounds = new maplibregl.LngLatBounds();
    coords.forEach((c) => bounds.extend(c));
    state.map.fitBounds(bounds, {
      padding: { top: 80, bottom: 80, left: 60, right: 60 },
      duration: 600,
      maxZoom: 12.5,
    });
  }
}

/* Static overlays: route network corridors, waypoint labels, and vertiport pins. */
function buildCorridorFeatureCollection() {
  const wpByName = new Map(state.waypoints.map((wp) => [wp.name, wp]));
  const features = [];
  const seen = new Set();
  for (const wp of state.waypoints) {
    for (const linkName of wp.links || []) {
      const target = wpByName.get(linkName);
      if (!target) continue;
      const key = [wp.name, linkName].sort().join('|');
      if (seen.has(key)) continue;
      seen.add(key);
      features.push({
        type: 'Feature',
        properties: { type: 'corridor' },
        geometry: { type: 'LineString', coordinates: [[wp.lon, wp.lat], [target.lon, target.lat]] },
      });
    }
  }
  for (const vp of state.vertiports) {
    for (const linkName of vp.links || []) {
      const target = wpByName.get(linkName);
      if (!target) continue;
      features.push({
        type: 'Feature',
        properties: { type: 'vertiport-link' },
        geometry: { type: 'LineString', coordinates: [[vp.lon, vp.lat], [target.lon, target.lat]] },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}
function buildWaypointFeatureCollection() {
  return {
    type: 'FeatureCollection',
    features: state.waypoints.map((wp) => ({
      type: 'Feature',
      properties: { name: wp.name, altFt: wp.altFt },
      geometry: { type: 'Point', coordinates: [wp.lon, wp.lat] },
    })),
  };
}
function renderGeoSources() {
  const corridorSource = state.map.getSource('overlay-corridors');
  if (corridorSource) corridorSource.setData(buildCorridorFeatureCollection());
  const waypointSource = state.map.getSource('overlay-waypoints');
  if (waypointSource) waypointSource.setData(buildWaypointFeatureCollection());
}
function placeVertiportMarkers() {
  state.vertiportMarkers.forEach((m) => m.remove());
  state.vertiportMarkers = state.vertiports.map((vertiport) => {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = `vertiport-marker${vertiport.class === 'hub' ? ' hub' : ''}`;
    el.dataset.id = vertiport.id;
    el.title = vertiport.name;
    const pin = document.createElement('div');
    pin.className = 'vertiport-pin';
    pin.textContent = 'V';
    el.appendChild(pin);
    const label = document.createElement('div');
    label.className = 'vertiport-name-label';
    label.textContent = vertiport.name;
    el.appendChild(label);
    el.addEventListener('click', () => selectSimVertiport(vertiport.id));
    return new maplibregl.Marker({ element: el })
      .setLngLat([vertiport.lon, vertiport.lat])
      .addTo(state.map);
  });
}
function placeWaypointLabelMarkers() {
  state.waypointLabelMarkers.forEach((m) => m.remove());
  state.waypointLabelMarkers = state.waypoints.map((wp) => {
    const el = document.createElement('div');
    el.className = 'waypoint-name-label';
    el.textContent = wp.name;
    return new maplibregl.Marker({ element: el, anchor: 'top', offset: [0, 8] })
      .setLngLat([wp.lon, wp.lat])
      .addTo(state.map);
  });
}

function resetSimulationMapView(duration = 0) {
  if (!state.map) return;
  state.map.easeTo({
    center: SIM_MAP_HOME_CENTER,
    zoom: SIM_MAP_HOME_ZOOM,
    duration,
    essential: true,
  });
}

function fitToVertiports() {
  if (!state.map || state.vertiports.length === 0) return;
  const bounds = new maplibregl.LngLatBounds();
  state.vertiports.forEach((v) => bounds.extend([v.lon, v.lat]));
  state.map.fitBounds(bounds, {
    padding: { top: 80, bottom: 80, left: 60, right: 60 },
    duration: 0,
    maxZoom: 11.5,
  });
}
