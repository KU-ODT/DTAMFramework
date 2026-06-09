const I18N = {
  ko: {
    vertiport: 'Vertiport',
    availablePads: '가용 패드',
    cctvOnline: 'CCTV 온라인',
    arrivalDeparture: '도착 / 출발',
    queue: '대기열',
    available: '가용',
    occupied: '점유',
    turnaround: '정비/회전',
    reserved: '예약',
    realtimeCctv: 'CCTV',
    more: '더 보기',
    scrollHint: '좌우 스크롤',
    operationsInfo: '운영 정보',
    activeCameraHelp: '카메라를 클릭하면 선택되고 더블클릭하면 별도 창으로 열립니다.',
    onTime: '정시율',
    turnaroundTime: '턴어라운드',
    passengerFlow: '승객 처리',
    energyLoad: '충전 부하',
    layoutTitle: '2D 레이아웃',
    dtWorldOffline: 'DT World가 켜지지 않았습니다.',
    dtWorldOfflineBody: 'Unreal 실행을 기다리는 중입니다. 켜지면 VPO가 자동으로 다시 연결됩니다.',
    dtWorldConnected: 'DT World 연결됨',
    dtWorldConnectedBody: 'Unreal View 수신 준비',
    dtWorldProcessOnly: '프로세스 감지됨',
    dtWorldRpcReady: 'AirSim RPC 연결',
    dtWorldLive: 'Live',
    dtWorldOff: 'DT World Off',
    frameWaiting: '프레임 대기',
    reconnecting: '신호 복구',
    online: 'online',
    drillTitle: '비상 대응 훈련 모드',
    drillBody: '가상의 접근 관제 이벤트가 추가되었습니다. 실제 운항에는 영향을 주지 않습니다.',
    loadingFail: 'VPOModule 로딩 실패',
    statusLabels: {
      available: '가용',
      occupied: '점유',
      turnaround: '정비/회전',
      reserved: '예약',
    },
  },
  en: {
    vertiport: 'Vertiport',
    availablePads: 'Available Pads',
    cctvOnline: 'CCTV Online',
    arrivalDeparture: 'Arrival / Departure',
    queue: 'Queue',
    available: 'Available',
    occupied: 'Occupied',
    turnaround: 'Turnaround',
    reserved: 'Reserved',
    realtimeCctv: 'CCTV',
    more: 'More',
    scrollHint: 'Horizontal scroll',
    operationsInfo: 'Operations',
    activeCameraHelp: 'Click a camera to activate it. Double-click to open a dedicated window.',
    onTime: 'On-time',
    turnaroundTime: 'Turnaround',
    passengerFlow: 'Passenger Flow',
    energyLoad: 'Energy Load',
    layoutTitle: '2D Layout',
    dtWorldOffline: 'DT World is not running.',
    dtWorldOfflineBody: 'Waiting for Unreal. VPO will reconnect automatically when it starts.',
    dtWorldConnected: 'DT World Connected',
    dtWorldConnectedBody: 'Unreal View ready',
    dtWorldProcessOnly: 'Process detected',
    dtWorldRpcReady: 'AirSim RPC linked',
    dtWorldLive: 'Live',
    dtWorldOff: 'DT World Off',
    frameWaiting: 'Frame waiting',
    reconnecting: 'Reconnecting',
    online: 'online',
    drillTitle: 'Emergency Drill Mode',
    drillBody: 'A simulated approach-control event has been added. Live operations are not affected.',
    loadingFail: 'VPOModule loading failed',
    statusLabels: {
      available: 'Available',
      occupied: 'Occupied',
      turnaround: 'Turnaround',
      reserved: 'Reserved',
    },
  },
};

const state = {
  vertiports: [],
  selectedVertiport: '',
  status: null,
  selectedCameraId: '',
  cameraCanvases: new Map(),
  cameraImages: new Map(),
  cameraStreams: new Map(),
  streamRequests: new Map(),
  showLabels: true,
  autoCycle: true,
  lastCycleAt: 0,
  drillMode: false,
  lang: localStorage.getItem('vpo-lang') || 'ko',
  theme: localStorage.getItem('vpo-theme') || 'light',
};

const $ = (selector) => document.querySelector(selector);
const rail = $('#camera-rail');
const overlay = $('#map-overlay');
const mapStage = $('#map-stage');
const dtWorldBanner = $('#dt-world-banner');
const dtWorldChip = $('#dt-world-chip');
const t = (key) => I18N[state.lang][key] ?? I18N.ko[key] ?? key;

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function statusLabel(status) {
  return t('statusLabels')[status] || status;
}

function cameraStatusLabel(camera = {}) {
  if (camera.status === 'offline') return t('dtWorldOff');
  if (camera.status === 'waiting_frame') return t('frameWaiting');
  if (camera.status === 'standby') return state.lang === 'ko' ? '대기' : 'Standby';
  if (camera.status === 'reconnecting') return t('reconnecting');
  return `${t('online')} · ${camera.signal_pct || 0}%`;
}

function cameraImageUrl(camera = {}) {
  const descriptor = state.cameraStreams.get(camera.id);
  if (descriptor?.url) return descriptor.url;
  if (!camera.frame_url) return '';
  const separator = camera.frame_url.includes('?') ? '&' : '?';
  return `${camera.frame_url}${separator}t=${Date.now()}`;
}

function applyCameraStreamToCard(cameraId, streamUrl) {
  if (!cameraId || !streamUrl) return;
  const card = [...(rail?.querySelectorAll('.camera-card') || [])]
    .find((item) => item.dataset.cameraId === cameraId);
  if (!card) return;
  let image = state.cameraImages.get(cameraId);
  if (!image) {
    const canvas = state.cameraCanvases.get(cameraId) || card.querySelector('canvas');
    image = document.createElement('img');
    image.className = 'camera-frame';
    image.alt = `${cameraId} VPO CCTV stream`;
    if (canvas) {
      canvas.replaceWith(image);
      state.cameraCanvases.delete(cameraId);
    } else {
      card.prepend(image);
    }
    state.cameraImages.set(cameraId, image);
  }
  image.src = streamUrl;
  card.classList.add('streaming');
  const badge = card.querySelector('.camera-badge');
  if (badge) badge.textContent = 'MJPEG Live';
}

async function requestCameraStream(cameraId) {
  if (!cameraId || !state.selectedVertiport) return null;
  const existing = state.cameraStreams.get(cameraId);
  if (existing?.url) {
    applyCameraStreamToCard(cameraId, existing.url);
    return existing;
  }
  const pending = state.streamRequests.get(cameraId);
  if (pending) return pending;

  const query = new URLSearchParams({
    vertiport_id: state.selectedVertiport,
    camera_id: cameraId,
    announce: 'false',
  });
  const request = fetchJson(`/api/streams?${query.toString()}`)
    .then((data) => {
      const descriptor = data.streams?.[0] || data.descriptor || null;
      if (descriptor?.url) {
        state.cameraStreams.set(cameraId, descriptor);
        applyCameraStreamToCard(cameraId, descriptor.url);
      }
      return descriptor;
    })
    .catch((error) => {
      console.warn('VPO CCTV stream request failed:', error);
      return null;
    })
    .finally(() => {
      state.streamRequests.delete(cameraId);
    });

  state.streamRequests.set(cameraId, request);
  return request;
}

function applyLanguage() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll('[data-i18n]').forEach((node) => {
    const key = node.dataset.i18n;
    const value = t(key);
    if (typeof value === 'string') node.textContent = value;
  });
  const langToggle = $('#lang-toggle');
  const langValue = langToggle.querySelector('strong') || langToggle;
  langValue.textContent = state.lang === 'ko' ? 'EN' : 'KO';
  langToggle.setAttribute('aria-label', state.lang === 'ko' ? 'Switch to English' : '한국어로 전환');
  updateClock();
  if (state.status) renderStatus(state.status);
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  const button = $('#theme-toggle');
  const isDark = state.theme === 'dark';
  button.dataset.state = isDark ? 'dark' : 'light';
  const label = button.querySelector('.theme-toggle__label');
  if (label) label.textContent = isDark ? 'Dark' : 'Light';
  button.setAttribute('aria-label', isDark ? '라이트 테마로 전환' : '다크 테마로 전환');
}

function formatDate(now = new Date()) {
  const parts = new Intl.DateTimeFormat(state.lang === 'en' ? 'en-US' : 'ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  }).formatToParts(now);
  const get = (type) => parts.find((part) => part.type === type)?.value || '';
  return state.lang === 'en'
    ? `${get('month')}.${get('day')} ${get('weekday')}`
    : `${get('month')}.${get('day')}(${get('weekday')})`;
}

function formatTime(now = new Date()) {
  return new Intl.DateTimeFormat(state.lang === 'en' ? 'en-US' : 'ko-KR', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(now);
}

function updateClock() {
  const now = new Date();
  $('#date-value').textContent = formatDate(now);
  $('#time-value').textContent = formatTime(now);
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: 'application/json' }, cache: 'no-store' });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function loadVertiports() {
  const data = await fetchJson('/api/vertiports');
  const previousSelection = state.selectedVertiport;
  state.vertiports = data.items || [];
  const select = $('#vertiport-select');
  select.innerHTML = state.vertiports.map((item) => (
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} · ${escapeHtml(item.code)}</option>`
  )).join('');
  state.selectedVertiport = state.vertiports.some((item) => item.id === previousSelection)
    ? previousSelection
    : (state.vertiports[0]?.id || '');
  select.value = state.selectedVertiport;
  select.addEventListener('change', () => {
    state.selectedVertiport = select.value;
    state.selectedCameraId = '';
    state.cameraCanvases.clear();
    state.cameraImages.clear();
    state.cameraStreams.clear();
    state.streamRequests.clear();
    rail.innerHTML = '';
    refreshStatus();
  });
}

async function refreshStatus() {
  if (!state.selectedVertiport) return;
  const data = await fetchJson(`/api/status?vertiport_id=${encodeURIComponent(state.selectedVertiport)}`);
  state.status = data;
  if (!state.selectedCameraId && data.cameras?.length) {
    state.selectedCameraId = data.cameras[0].id;
  }
  renderStatus(data);
}

function renderDtWorld(dtWorld = {}) {
  const connected = Boolean(dtWorld.connected);
  document.body.classList.toggle('dt-world-offline', !connected);

  if (dtWorldBanner) {
    dtWorldBanner.classList.add('hidden');
    const title = dtWorldBanner.querySelector('strong');
    const body = dtWorldBanner.querySelector('span');
    if (title) title.textContent = t('dtWorldOffline');
    if (body) body.textContent = t('dtWorldOfflineBody');
  }

  if (dtWorldChip) {
    dtWorldChip.classList.toggle('is-online', connected);
    dtWorldChip.classList.toggle('is-offline', !connected);
    dtWorldChip.classList.remove('is-checking');
    const title = dtWorldChip.querySelector('b');
    const detail = dtWorldChip.querySelector('small');
    if (title) title.textContent = connected ? t('dtWorldConnected') : t('dtWorldOffline');
    if (detail) {
      detail.textContent = connected
        ? (dtWorld.airsim_rpc_open ? t('dtWorldRpcReady') : t('dtWorldProcessOnly'))
        : t('dtWorldOfflineBody');
    }
  }

  const layoutStatus = $('#layout-status');
  layoutStatus.textContent = connected ? t('dtWorldLive') : t('dtWorldOff');
  layoutStatus.classList.toggle('offline', !connected);
}

function renderStatus(data) {
  renderDtWorld(data.dt_world || {});
  $('#layout-title').textContent = t('layoutTitle');
  $('#metric-pads').textContent = `${data.metrics.available_pads}/${data.metrics.total_pads}`;
  $('#metric-cameras').textContent = `${data.metrics.camera_online}/${data.metrics.camera_total}`;
  $('#metric-traffic').textContent = `${data.metrics.arrivals_30m}/${data.metrics.departures_30m}`;
  $('#metric-queue').textContent = state.lang === 'ko' ? `${data.metrics.queue}대` : `${data.metrics.queue}`;

  $('#weather-condition').textContent = data.weather.condition;
  $('#weather-wind').textContent = `${data.weather.wind_kts} kt`;
  $('#weather-gust').textContent = `${data.weather.gust_kts} kt`;
  $('#weather-visibility').textContent = `${data.weather.visibility_km} km`;
  $('#weather-qnh').textContent = `${data.weather.qnh_hpa}`;

  $('#perf-on-time').textContent = `${data.metrics.on_time_pct}%`;
  $('#perf-turnaround').textContent = `${data.metrics.turnaround_min} min`;
  $('#perf-pax').textContent = `${data.metrics.passenger_flow_h}/h`;
  $('#perf-energy').textContent = `${data.metrics.energy_load_kw} kW`;

  renderLayout(data);
  renderCameras(data.cameras || []);
  renderActiveCamera();
  renderAlerts(data.alerts || []);
  renderTimeline(data.timeline || []);
}

function renderLayout(data) {
  overlay.innerHTML = '';
  mapStage.classList.toggle('labels-hidden', !state.showLabels);

  data.layout.gates.forEach((gate) => {
    const node = document.createElement('div');
    node.className = 'gate-marker';
    node.style.left = `${gate.x}%`;
    node.style.top = `${gate.y}%`;
    node.textContent = gate.label;
    overlay.appendChild(node);
  });

  data.layout.pads.forEach((pad) => {
    const node = document.createElement('div');
    node.className = `pad-marker ${pad.status}`;
    node.style.left = `${pad.x}%`;
    node.style.top = `${pad.y}%`;
    node.dataset.eta = `${statusLabel(pad.status)} · ETA ${pad.eta_min}${state.lang === 'ko' ? '분' : 'm'}`;
    node.title = `${pad.id} · ${statusLabel(pad.status)} · battery target ${pad.battery_target_pct}%`;
    node.textContent = pad.label;
    overlay.appendChild(node);
  });

  data.vehicles.forEach((vehicle) => {
    const node = document.createElement('div');
    node.className = 'vehicle-marker';
    node.style.left = `${vehicle.x}%`;
    node.style.top = `${vehicle.y}%`;
    node.style.transform = `translate(-50%, -50%) rotate(${vehicle.heading_deg}deg)`;
    node.title = `${vehicle.id} · ${vehicle.state} · ${vehicle.speed_kmh}km/h`;
    const label = document.createElement('span');
    label.className = 'vehicle-label';
    label.textContent = vehicle.callsign;
    node.appendChild(label);
    overlay.appendChild(node);
  });
}

function renderCameras(cameras = []) {
  const signature = cameras.map((camera) => `${camera.id}:${camera.frame_url ? 1 : 0}`).join('|');
  const rebuild = rail.dataset.cameraSignature !== signature;

  if (rebuild) {
    rail.dataset.cameraSignature = signature;
    rail.innerHTML = '';
    state.cameraCanvases.clear();
    state.cameraImages.clear();
    cameras.forEach((camera) => {
      const card = document.createElement('article');
      card.className = 'camera-card';
      card.dataset.cameraId = camera.id;
      const sourceLabel = (camera.source || '').includes('unreal') ? 'DT World View' : 'VPO View';
      const mediaUrl = cameraImageUrl(camera);
      const media = mediaUrl
        ? `<img class="camera-frame" alt="${escapeHtml(camera.name)} CCTV frame" src="${escapeHtml(mediaUrl)}" />`
        : `<canvas class="camera-canvas" aria-label="${escapeHtml(camera.name)} CCTV placeholder"></canvas>`;
      card.innerHTML = `
        ${media}
        <div class="camera-overlay">
          <span class="camera-code">${escapeHtml(camera.id)}</span>
          <span class="camera-ai">${escapeHtml(camera.ai_label || '')}</span>
        </div>
        <div class="camera-meta">
          <div>
            <strong>${escapeHtml(camera.name)}</strong>
            <span>${escapeHtml(camera.sector)} · ${escapeHtml(camera.type)} · ${escapeHtml(camera.angle)} · ${sourceLabel}</span>
          </div>
          <div class="camera-badge">${escapeHtml(cameraStatusLabel(camera))}</div>
        </div>`;
      card.addEventListener('click', () => {
        state.selectedCameraId = camera.id;
        renderActiveCamera();
        updateCameraSelection();
      });
      card.addEventListener('dblclick', () => {
        const url = `/cctv/${encodeURIComponent(camera.id)}?vertiport_id=${encodeURIComponent(state.selectedVertiport)}`;
        window.open(url, `vpo-cctv-${camera.id}`, 'width=1280,height=820,menubar=no,toolbar=no,location=no');
      });
      const canvas = card.querySelector('canvas');
      const image = card.querySelector('img');
      if (canvas) state.cameraCanvases.set(camera.id, canvas);
      if (image) state.cameraImages.set(camera.id, image);
      rail.appendChild(card);
    });
  }

  cameras.forEach((camera) => {
    const card = [...rail.querySelectorAll('.camera-card')].find((item) => item.dataset.cameraId === camera.id);
    if (!card) return;
    const badge = card.querySelector('.camera-badge');
    const ai = card.querySelector('.camera-ai');
    const image = state.cameraImages.get(camera.id);
    const notLive = camera.status === 'offline' || camera.status === 'waiting_frame';
    card.classList.toggle('offline', notLive);
    badge.textContent = cameraStatusLabel(camera);
    badge.classList.toggle('reconnecting', camera.status === 'reconnecting' || camera.status === 'waiting_frame');
    badge.classList.toggle('offline', notLive);
    ai.textContent = camera.status === 'waiting_frame'
      ? t('frameWaiting')
      : `${camera.ai_label || ''}${camera.latency_ms ? ` · ${camera.latency_ms}ms` : ''}`;
    if (image && (camera.frame_url || state.cameraStreams.has(camera.id))) {
      image.src = cameraImageUrl(camera);
    }
  });
  updateCameraSelection();
}

function updateCameraSelection() {
  rail.querySelectorAll('.camera-card').forEach((card) => {
    card.classList.toggle('active', card.dataset.cameraId === state.selectedCameraId);
  });
}

function renderActiveCamera() {
  const camera = state.status?.cameras?.find((item) => item.id === state.selectedCameraId);
  if (!camera) return;
  $('#active-camera-name').textContent = `${camera.id} · ${camera.name}`;
  if (camera.status === 'offline') {
    $('#active-camera-meta').textContent = t('dtWorldOfflineBody');
  } else if (camera.status === 'waiting_frame') {
    $('#active-camera-meta').textContent = state.lang === 'ko'
      ? 'DT World는 감지됐지만 Unreal SceneCapture 프레임 파일이 아직 생성되지 않았습니다.'
      : 'DT World is detected, but the Unreal SceneCapture frame file has not been exported yet.';
  } else if (camera.status === 'standby') {
    $('#active-camera-meta').textContent = state.lang === 'ko'
      ? '상시 CCTV 캡처는 꺼져 있습니다. 더블클릭하면 선택 CCTV만 저부하로 요청합니다.'
      : 'Always-on CCTV capture is off. Double-click to request only the selected CCTV stream.';
  } else {
    $('#active-camera-meta').textContent = `${camera.sector} / ${camera.type} / Signal ${camera.signal_pct}% / Motion ${camera.motion_pct}%`;
  }
}

function renderAlerts(alerts = []) {
  $('#alert-list').innerHTML = alerts.map((alert) => {
    const title = state.lang === 'en' ? (alert.title_en || alert.title) : alert.title;
    const body = state.lang === 'en' ? (alert.body_en || alert.body) : alert.body;
    return `
      <div class="alert-item ${escapeHtml(alert.level)}">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(body)}</span>
      </div>`;
  }).join('');
}

function renderTimeline(items = []) {
  $('#timeline-list').innerHTML = items.map((item) => {
    const title = state.lang === 'en' ? (item.title_en || item.title) : item.title;
    const detail = state.lang === 'en' ? (item.detail_en || item.detail) : item.detail;
    return `
      <div class="timeline-item">
        <time>${escapeHtml(item.time)}</time>
        <div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span></div>
      </div>`;
  }).join('');
}

function setCanvasSize(canvas) {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(rect.width * ratio));
  const height = Math.max(1, Math.floor(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  return { width, height };
}

function drawCamera(canvas, camera, tValue) {
  const ctx = canvas.getContext('2d');
  const { width: w, height: h } = setCanvasSize(canvas);
  const hue = (camera.id.charCodeAt(camera.id.length - 1) * 23) % 360;
  const grd = ctx.createLinearGradient(0, 0, w, h);
  grd.addColorStop(0, `hsl(${210 + (hue % 20)} 55% 12%)`);
  grd.addColorStop(0.55, `hsl(${225 + (hue % 30)} 48% 9%)`);
  grd.addColorStop(1, `hsl(${185 + (hue % 36)} 60% 15%)`);
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, w, h);

  ctx.save();
  ctx.globalAlpha = 0.18;
  ctx.strokeStyle = '#a8d8ff';
  ctx.lineWidth = 1;
  const grid = 34;
  for (let x = (tValue * 10) % grid; x < w; x += grid) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x - w * 0.24, h);
    ctx.stroke();
  }
  for (let y = h * 0.52; y < h; y += grid) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y + Math.sin(tValue + y) * 8);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.translate(w * 0.5, h * 0.68);
  ctx.scale(1, 0.28);
  ctx.strokeStyle = 'rgba(126, 231, 255, 0.38)';
  ctx.lineWidth = Math.max(2, w * 0.004);
  for (let r = w * 0.16; r < w * 0.72; r += w * 0.14) {
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();

  const message = camera.status === 'offline'
    ? 'DT WORLD OFFLINE'
    : camera.status === 'waiting_frame'
      ? 'WAITING UNREAL FRAME'
      : camera.status === 'standby'
        ? 'CCTV STANDBY'
        : camera.status === 'reconnecting'
          ? 'RECONNECTING SIGNAL'
          : 'UNREAL FRAME NOT FOUND';

  ctx.fillStyle = camera.status === 'offline' ? 'rgba(16, 24, 40, 0.58)' : 'rgba(16, 24, 40, 0.38)';
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = 'rgba(255,255,255,0.94)';
  ctx.font = `${Math.max(14, w * 0.034)}px ${getComputedStyle(document.body).fontFamily}`;
  ctx.textAlign = 'center';
  ctx.fillText(message, w / 2, h / 2 - 6);
  ctx.font = `${Math.max(11, w * 0.022)}px ${getComputedStyle(document.body).fontFamily}`;
  ctx.fillStyle = 'rgba(255,255,255,0.70)';
  const sub = camera.status === 'waiting_frame'
    ? 'SceneCapture PNG export is not ready'
    : camera.status === 'standby'
      ? 'Always-on capture is off for performance'
      : 'Run DT World / Unreal and wait for reconnect';
  ctx.fillText(sub, w / 2, h / 2 + 24);

  ctx.fillStyle = 'rgba(0,0,0,0.30)';
  ctx.fillRect(0, h - 30, w, 30);
  ctx.fillStyle = 'rgba(255,255,255,0.88)';
  ctx.font = `11px ${getComputedStyle(document.body).fontFamily}`;
  ctx.textAlign = 'left';
  ctx.fillText(`${camera.id}  ${camera.name}`, 12, h - 11);
}

function animateCameras(now) {
  const tValue = now / 1000;
  const cameras = state.status?.cameras || [];
  cameras.forEach((camera) => {
    const canvas = state.cameraCanvases.get(camera.id);
    if (canvas) drawCamera(canvas, camera, tValue);
  });

  if (state.autoCycle && cameras.length && now - state.lastCycleAt > 5200) {
    state.lastCycleAt = now;
    const index = cameras.findIndex((item) => item.id === state.selectedCameraId);
    const next = cameras[(index + 1) % cameras.length];
    if (next) {
      state.selectedCameraId = next.id;
      renderActiveCamera();
      updateCameraSelection();
    }
  }
  requestAnimationFrame(animateCameras);
}

function bindActions() {
  $('#theme-toggle').addEventListener('click', () => {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('vpo-theme', state.theme);
    applyTheme();
  });

  $('#lang-toggle').addEventListener('click', () => {
    state.lang = state.lang === 'ko' ? 'en' : 'ko';
    localStorage.setItem('vpo-lang', state.lang);
    applyLanguage();
  });

  document.querySelectorAll('[data-scroll]').forEach((button) => {
    button.addEventListener('click', () => {
      const dir = button.dataset.scroll === 'left' ? -1 : 1;
      rail.scrollBy({ left: dir * Math.max(320, rail.clientWidth * 0.72), behavior: 'smooth' });
    });
  });

  $('#btn-cycle').addEventListener('click', (event) => {
    state.autoCycle = !state.autoCycle;
    event.currentTarget.classList.toggle('active', state.autoCycle);
  });

  $('#btn-labels').addEventListener('click', (event) => {
    state.showLabels = !state.showLabels;
    event.currentTarget.classList.toggle('active', state.showLabels);
    if (state.status) renderLayout(state.status);
  });

  $('#btn-drill').addEventListener('click', (event) => {
    state.drillMode = !state.drillMode;
    event.currentTarget.classList.toggle('active', state.drillMode);
    const drill = {
      level: 'warning',
      title: t('drillTitle'),
      body: t('drillBody'),
      title_en: I18N.en.drillTitle,
      body_en: I18N.en.drillBody,
    };
    if (state.status) {
      const alerts = state.drillMode ? [drill, ...(state.status.alerts || [])] : state.status.alerts;
      renderAlerts(alerts);
    }
  });
}

async function boot() {
  applyTheme();
  applyLanguage();
  updateClock();
  setInterval(updateClock, 1000);
  bindActions();
  await loadVertiports();
  await refreshStatus();
  setInterval(() => {
    refreshStatus().catch(() => {
      /* Keep the dashboard quiet during temporary backend reconnects. */
    });
  }, 2400);
  requestAnimationFrame(animateCameras);
}

boot().catch((error) => {
  console.error(error);
  document.body.insertAdjacentHTML(
    'afterbegin',
    `<div style="position:fixed;z-index:10;left:20px;right:20px;top:20px;padding:16px;border-radius:10px;background:#ff453a;color:white;font-weight:800">${escapeHtml(t('loadingFail'))}: ${escapeHtml(error.message)}</div>`,
  );
});
