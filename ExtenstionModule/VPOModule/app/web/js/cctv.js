const canvas = document.querySelector('#focus-canvas');
const streamImage = document.querySelector('#focus-stream');
const title = document.querySelector('#focus-title');
const subtitle = document.querySelector('#focus-subtitle');
const statusNode = document.querySelector('#focus-status');
const timeNode = document.querySelector('#focus-time');
const signalNode = document.querySelector('#focus-signal');
const latencyNode = document.querySelector('#focus-latency');
const motionNode = document.querySelector('#focus-motion');
const prevButton = document.querySelector('#focus-prev');
const nextButton = document.querySelector('#focus-next');
const requestButton = document.querySelector('#focus-request');

const pathParts = window.location.pathname.split('/').filter(Boolean);
const params = new URLSearchParams(window.location.search);
const vertiportId = params.get('vertiport_id') || '';

let currentCameraId = decodeURIComponent(pathParts[pathParts.length - 1] || '');
let camera = null;
let cameraList = [];
let frameImage = new Image();
let currentFrameUrl = '';
let currentStreamUrl = '';
let streamRequest = null;
let streamRetryAfter = 0;
let userRequestedStream = false;

function cameraSeed(id = '') {
  return [...String(id)].reduce((sum, ch, index) => sum + (ch.charCodeAt(0) * (index + 3)), 17);
}

function setCanvasSize(target) {
  const rect = target.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(rect.width * ratio));
  const height = Math.max(1, Math.floor(rect.height * ratio));
  if (target.width !== width || target.height !== height) {
    target.width = width;
    target.height = height;
  }
  return { width, height };
}

function cameraQuery() {
  return vertiportId ? `?vertiport_id=${encodeURIComponent(vertiportId)}` : '';
}

function cacheBusted(url = '') {
  if (!url) return '';
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}t=${Date.now()}`;
}

function statusText(status = '') {
  if (status === 'offline') return 'DT WORLD OFF';
  if (status === 'waiting_frame') return 'FRAME WAITING';
  if (status === 'standby') return 'STANDBY';
  if (status === 'reconnecting') return 'RECONNECTING';
  return 'ONLINE';
}

async function loadCameraList() {
  const response = await fetch(`/api/status${cameraQuery()}`, {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  });
  if (!response.ok) return;
  const data = await response.json();
  cameraList = data.cameras || [];
  if (!currentCameraId && cameraList.length) currentCameraId = cameraList[0].id;
}

function syncUrl() {
  const query = vertiportId ? `?vertiport_id=${encodeURIComponent(vertiportId)}` : '';
  const nextUrl = `/cctv/${encodeURIComponent(currentCameraId)}${query}`;
  window.history.replaceState({}, '', nextUrl);
}

function updateFrameImage(nextUrl) {
  if (!nextUrl) {
    currentFrameUrl = '';
    frameImage = new Image();
    return;
  }
  if (nextUrl !== currentFrameUrl || !frameImage.src) {
    currentFrameUrl = nextUrl;
    frameImage = new Image();
  }
  frameImage.src = cacheBusted(nextUrl);
}

function setStreamUrl(nextUrl = '') {
  if (!streamImage) return;
  if (!nextUrl) {
    currentStreamUrl = '';
    streamImage.removeAttribute('src');
    streamImage.classList.remove('active');
    canvas.classList.remove('stream-covered');
    return;
  }
  if (nextUrl !== currentStreamUrl) {
    currentStreamUrl = nextUrl;
    streamImage.src = nextUrl;
  }
  streamImage.classList.add('active');
  canvas.classList.add('stream-covered');
}

function updateRequestButton() {
  if (!requestButton) return;
  const unavailable = !camera || camera.status === 'offline' || camera.status === 'waiting_frame';
  requestButton.disabled = unavailable || Boolean(streamRequest);
  requestButton.classList.toggle('hidden', Boolean(currentStreamUrl) || Boolean(camera?.frame_url));
  if (streamRequest) {
    requestButton.textContent = '요청 중...';
  } else if (unavailable) {
    requestButton.textContent = 'CCTV 대기';
  } else {
    requestButton.textContent = 'CCTV 요청';
  }
}

async function requestCameraStream(cameraId) {
  if (!cameraId) return null;
  if (currentStreamUrl && cameraId === camera?.id) return currentStreamUrl;
  if (Date.now() < streamRetryAfter) return null;
  if (streamRequest) return streamRequest;
  const query = new URLSearchParams({
    camera_id: cameraId,
    announce: 'true',
    connect: 'true',
  });
  if (vertiportId) query.set('vertiport_id', vertiportId);
  streamRequest = fetch(`/api/streams?${query.toString()}`, {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  })
    .then((response) => {
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return response.json();
    })
    .then((data) => {
      const descriptor = data.streams?.[0] || data.descriptor || null;
      if (descriptor?.url && camera?.id === cameraId) {
        setStreamUrl(descriptor.url);
      } else if (descriptor?.frame_url && camera?.id === cameraId) {
        updateFrameImage(descriptor.frame_url);
        streamRetryAfter = Date.now() + 10000;
      } else {
        streamRetryAfter = Date.now() + 10000;
      }
      updateRequestButton();
      return descriptor;
    })
    .catch((error) => {
      console.warn('VPO CCTV focus stream request failed:', error);
      setStreamUrl('');
      streamRetryAfter = Date.now() + 10000;
      updateRequestButton();
      return null;
    })
    .finally(() => {
      streamRequest = null;
      updateRequestButton();
    });
  updateRequestButton();
  return streamRequest;
}

async function requestCurrentCameraStream() {
  if (!camera || camera.status === 'offline' || camera.status === 'waiting_frame') return;
  userRequestedStream = true;
  streamRetryAfter = 0;
  await requestCameraStream(camera.id);
}

async function fetchCamera() {
  if (!currentCameraId) return;
  const response = await fetch(`/api/cameras/${encodeURIComponent(currentCameraId)}${cameraQuery()}`, {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  const data = await response.json();
  camera = data.camera;
  title.textContent = `${camera.id} · ${camera.name}`;
  subtitle.textContent = camera.status === 'offline'
    ? `${data.vertiport.name} / DT World가 켜지지 않았습니다.`
    : camera.status === 'waiting_frame'
      ? `${data.vertiport.name} / Unreal SceneCapture 프레임 대기 중`
      : camera.status === 'standby'
        ? `${data.vertiport.name} / 상시 캡처 OFF · 선택 CCTV만 요청`
        : `${data.vertiport.name} / ${camera.sector} / ${camera.type} / ${camera.angle}`;
  statusNode.textContent = statusText(camera.status);
  signalNode.textContent = `Signal ${camera.signal_pct}%`;
  latencyNode.textContent = `Latency ${camera.latency_ms}ms`;
  motionNode.textContent = `Motion ${camera.motion_pct}%`;
  updateFrameImage(camera.frame_url || '');
  if (camera.status === 'offline' || camera.status === 'waiting_frame') {
    setStreamUrl('');
  } else if (userRequestedStream && !camera.frame_url) {
    requestCameraStream(camera.id).catch(() => {});
  } else {
    setStreamUrl('');
  }
  updateRequestButton();
}

async function switchCamera(delta) {
  if (!cameraList.length) await loadCameraList();
  if (!cameraList.length) return;
  const index = cameraList.findIndex((item) => item.id === currentCameraId);
  const safeIndex = index >= 0 ? index : 0;
  const nextIndex = (safeIndex + delta + cameraList.length) % cameraList.length;
  currentCameraId = cameraList[nextIndex].id;
  syncUrl();
  camera = null;
  currentFrameUrl = '';
  streamRetryAfter = 0;
  userRequestedStream = false;
  setStreamUrl('');
  await fetchCamera();
}

window.vpoSwitchCamera = (delta) => switchCamera(Number(delta) || 1).catch(console.error);

function drawCover(ctx, image, w, h) {
  const iw = image.naturalWidth || image.width;
  const ih = image.naturalHeight || image.height;
  if (!iw || !ih) return false;
  const scale = Math.max(w / iw, h / ih);
  const dw = iw * scale;
  const dh = ih * scale;
  const dx = (w - dw) / 2;
  const dy = (h - dh) / 2;
  ctx.drawImage(image, dx, dy, dw, dh);
  return true;
}

function drawPlaceholder(ctx, w, h, seed, t) {
  const hueA = 205 + (seed % 42);
  const hueB = 168 + (seed % 78);
  const centerX = w * (0.43 + Math.sin(seed * 0.13) * 0.11);
  const centerY = h * (0.63 + Math.cos(seed * 0.11) * 0.08);
  const grd = ctx.createLinearGradient(0, 0, w, h);
  grd.addColorStop(0, `hsl(${hueA} 58% 12%)`);
  grd.addColorStop(0.48, `hsl(${hueA + 12} 48% 14%)`);
  grd.addColorStop(1, `hsl(${hueB} 58% 12%)`);
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, w, h);

  ctx.save();
  ctx.globalAlpha = 0.18;
  ctx.strokeStyle = '#9fe8ff';
  ctx.lineWidth = 1;
  const grid = 72;
  for (let x = ((t / 28) + seed) % grid; x < w + grid; x += grid) {
    const skew = 0.14 + ((seed % 9) * 0.018);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x - w * skew, h);
    ctx.stroke();
  }
  for (let y = h * 0.35; y < h + grid; y += grid) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y + Math.sin(t / 700 + y + seed) * 16);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.translate(centerX, centerY);
  ctx.scale(1, 0.23);
  for (let r = w * 0.12; r < w * 0.76; r += w * 0.10) {
    ctx.strokeStyle = `rgba(126, 231, 255, ${0.30 - r / w * 0.16})`;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function drawCenteredMessage(ctx, w, h, main, sub) {
  ctx.fillStyle = 'rgba(6, 12, 24, 0.52)';
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = 'rgba(255,255,255,0.94)';
  ctx.font = `26px ${getComputedStyle(document.body).fontFamily}`;
  ctx.textAlign = 'center';
  ctx.fillText(main, w / 2, h / 2 - 8);
  ctx.font = `15px ${getComputedStyle(document.body).fontFamily}`;
  ctx.fillStyle = 'rgba(255,255,255,0.72)';
  ctx.fillText(sub, w / 2, h / 2 + 26);
}

function draw(t) {
  const ctx = canvas.getContext('2d');
  const { width: w, height: h } = setCanvasSize(canvas);
  const active = camera;
  const seed = cameraSeed(active?.id || 'VPO');

  if (active?.frame_url && frameImage.complete && frameImage.naturalWidth > 0) {
    drawCover(ctx, frameImage, w, h);
  } else {
    drawPlaceholder(ctx, w, h, seed, t);
    if (active?.status === 'offline') {
      drawCenteredMessage(ctx, w, h, 'DT WORLD OFFLINE', 'Unreal 실행 후 자동으로 다시 연결됩니다');
    } else if (active?.status === 'waiting_frame') {
      drawCenteredMessage(ctx, w, h, 'WAITING UNREAL FRAME', 'SceneCapture PNG export is not ready');
    } else if (active?.status === 'standby') {
      drawCenteredMessage(ctx, w, h, 'CCTV STANDBY', 'Always-on capture is off for performance');
    } else if (!active) {
      drawCenteredMessage(ctx, w, h, 'LOADING CCTV', 'Fetching camera data');
    }
  }

  if (active) {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.34)';
    ctx.fillRect(0, h - 56, w, 56);
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    ctx.font = `22px ${getComputedStyle(document.body).fontFamily}`;
    ctx.textAlign = 'left';
    ctx.fillText(`${active.id}  ${active.name}`, 24, h - 20);

    ctx.textAlign = 'right';
    ctx.font = `13px ${getComputedStyle(document.body).fontFamily}`;
    ctx.fillStyle = 'rgba(255,255,255,0.72)';
    ctx.fillText(`${active.sector} · ${active.type}`, w - 24, 32);
  }

  timeNode.textContent = new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date());

  requestAnimationFrame(draw);
}

document.querySelector('#close-window').addEventListener('click', () => window.close());
requestButton?.addEventListener('click', () => requestCurrentCameraStream().catch(console.error));
prevButton.addEventListener('click', () => switchCamera(-1).catch(console.error));
nextButton.addEventListener('click', () => switchCamera(1).catch(console.error));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') window.close();
  if (event.key === 'ArrowLeft') switchCamera(-1).catch(console.error);
  if (event.key === 'ArrowRight') switchCamera(1).catch(console.error);
});

loadCameraList()
  .then(fetchCamera)
  .catch((error) => {
    title.textContent = 'CCTV 로딩 실패';
    subtitle.textContent = error.message;
  });
setInterval(() => fetchCamera().catch(() => {}), 1400);
setInterval(() => loadCameraList().catch(() => {}), 3200);
requestAnimationFrame(draw);
