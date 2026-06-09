const $ = (id) => document.getElementById(id);

const fields = {
  visualUrl: $("visualUrl"),
  stateUrl: $("stateUrl"),
  vehicleId: $("vehicleId"),
  vehicleName: $("vehicleName"),
  cameraName: $("cameraName"),
  imageType: $("imageType"),
  fps: $("fps"),
  quality: $("quality"),
  displayScale: $("displayScale"),
};
const streamImg = $("streamImage");
const streamFrame = $("streamFrame");
const emptyHint = $("emptyHint");
const streamState = $("streamState");
const logBox = $("log");
const overlayImageSize = $("overlayImageSize");
const overlayFps = $("overlayFps");
const overlayCapture = $("overlayCapture");
const overlayWarning = $("overlayWarning");
let streamWatchdog = null;
let statsPoller = null;
let currentStreamUrl = "";
let currentDescriptor = null;
let currentValues = null;
let lastBlackWarningKey = "";

function values() {
  return {
    visualization_url: fields.visualUrl.value.trim(),
    state_url: fields.stateUrl.value.trim(),
    vehicle_id: fields.vehicleId.value.trim() || "UAM0001",
    vehicle_name: fields.vehicleName.value.trim(),
    camera_name: fields.cameraName.value.trim() || "front_center",
    image_type: Number(fields.imageType?.value || 0),
    fps: Number(fields.fps.value || 20),
    quality: Number(fields.quality.value || 60),
    display_scale: fields.displayScale?.value || "fit",
  };
}

function log(message, data = null) {
  const now = new Date().toLocaleTimeString();
  const body = data ? `\n${JSON.stringify(data, null, 2)}` : "";
  logBox.textContent = `[${now}] ${message}${body}\n\n${logBox.textContent}`.slice(0, 9000);
}

async function getJSON(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data?.detail || data?.error || `${res.status} ${res.statusText}`);
    err.data = data;
    throw err;
  }
  return data;
}

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data?.detail || data?.error || `${res.status} ${res.statusText}`);
    err.data = data;
    throw err;
  }
  return data;
}

function setState(label, mode = "idle") {
  streamState.textContent = label;
  streamState.className = `state ${mode}`;
}

function setHint(message) {
  emptyHint.textContent = message;
  emptyHint.style.display = "block";
}

function clearStreamImage() {
  if (streamWatchdog) {
    clearTimeout(streamWatchdog);
    streamWatchdog = null;
  }
  stopStatsPolling();
  streamImg.onload = null;
  streamImg.onerror = null;
  streamImg.removeAttribute("src");
  streamImg.style.width = "";
  streamImg.style.height = "";
  streamImg.style.objectFit = "";
  streamImg.style.maxWidth = "";
  streamImg.style.maxHeight = "";
  streamImg.style.minHeight = "";
  streamImg.style.display = "none";
  streamFrame.onload = null;
  streamFrame.onerror = null;
  streamFrame.removeAttribute("src");
  streamFrame.style.display = "none";
  currentStreamUrl = "";
  currentDescriptor = null;
  currentValues = null;
  lastBlackWarningKey = "";
  updateStreamOverlay({ imageSize: "--", fpsText: "--", captureText: "--", warningText: "" });
}

function populateImageTypeOptions(options = [], selected = 0) {
  if (!fields.imageType || !Array.isArray(options) || !options.length) return;
  const current = fields.imageType.value || String(selected ?? 0);
  fields.imageType.innerHTML = "";
  for (const option of options) {
    const opt = document.createElement("option");
    opt.value = String(option.value ?? 0);
    opt.textContent = String(option.label ?? option.value ?? "0");
    fields.imageType.appendChild(opt);
  }
  fields.imageType.value = [...fields.imageType.options].some((opt) => opt.value === current)
    ? current
    : String(selected ?? 0);
}

async function loadConfig() {
  try {
    const cfg = await getJSON("/api/config");
    fields.visualUrl.value = cfg.visualization_url || fields.visualUrl.value;
    fields.stateUrl.value = cfg.state_url || fields.stateUrl.value;
    populateImageTypeOptions(cfg.image_type_options || [], cfg.default_image_type ?? 0);
    if (fields.imageType && cfg.default_image_type !== undefined) fields.imageType.value = String(cfg.default_image_type);
    fields.fps.value = String(cfg.default_fps ?? fields.fps.value);
    fields.quality.value = String(cfg.default_quality ?? fields.quality.value);
    if (fields.displayScale) fields.displayScale.value = cfg.default_display_scale || fields.displayScale.value;
    log("TestStream 준비 완료", cfg);
  } catch (err) {
    log("설정 로드 실패", { error: String(err) });
  }
}

async function startStream() {
  const v = values();
  const params = new URLSearchParams({
    visualization_url: v.visualization_url,
    vehicle_id: v.vehicle_id,
    vehicle_name: v.vehicle_name,
    camera_name: v.camera_name,
    image_type: String(v.image_type),
    fps: String(v.fps),
    quality: String(v.quality),
    announce: "true",
  });
  clearStreamImage();
  setState("opening", "opening");
  setHint("스트림 descriptor 요청 중입니다...");
  const data = await getJSON(`/api/streams?${params.toString()}`);
  const descriptor = data?.streams?.[0];
  if (!descriptor?.url) throw new Error("stream descriptor URL이 없습니다.");
  if (isPixelStreamingDescriptor(descriptor)) {
    throw new Error("Pixel Streaming descriptor가 반환되었습니다. 현재 TestStream은 direct MJPEG 카메라 스트림만 사용합니다. VisualizationModule 설정을 확인하세요.");
  }
  startMjpegStream(descriptor, data, v);
}

function isPixelStreamingDescriptor(descriptor) {
  const kind = `${descriptor?.stream_type || ""} ${descriptor?.transport || ""} ${descriptor?.encoding || ""}`.toLowerCase();
  return kind.includes("webrtc") || kind.includes("pixel");
}

function startMjpegStream(descriptor, data, v) {
  const separator = descriptor.url.includes("?") ? "&" : "?";
  currentStreamUrl = `${descriptor.url}${separator}_teststream=${Date.now()}`;
  currentDescriptor = descriptor;
  currentValues = v;
  updateStreamOverlay({
    imageSize: descriptorSizeText(descriptor),
    fpsText: `req ${formatNumber(descriptor.fps || v.fps || 0, 0)}`,
    captureText: "--",
    warningText: "",
  });

  let gotFirstFrame = false;
  const waitMs = Math.max(6000, Math.ceil((1000 / Math.max(0.2, v.fps || 20)) * 4));

  streamImg.onload = () => {
    gotFirstFrame = true;
    if (streamWatchdog) {
      clearTimeout(streamWatchdog);
      streamWatchdog = null;
    }
    streamImg.style.display = "block";
    applyDisplayScale();
    updateStreamOverlay({
      imageSize: naturalSizeText() || descriptorSizeText(descriptor),
      fpsText: `req ${formatNumber(descriptor.fps || v.fps || 0, 0)}`,
      captureText: "--",
    });
    startStatsPolling(v, descriptor);
    emptyHint.style.display = "none";
    setState("live", "live");
    log("첫 MJPEG 프레임 수신 확인", {
      stream_url: descriptor.url,
      fps: descriptor.fps,
      quality: descriptor.quality,
      image_type: descriptor.image_type ?? v.image_type,
      display_scale: v.display_scale,
      natural_width: streamImg.naturalWidth,
      natural_height: streamImg.naturalHeight,
    });
  };

  streamImg.onerror = () => {
    if (streamWatchdog) {
      clearTimeout(streamWatchdog);
      streamWatchdog = null;
    }
    streamImg.style.display = "none";
    setState("image error", "error");
    setHint("브라우저가 스트림 이미지를 로드하지 못했습니다. 아래 Log의 stream_url을 직접 열어 확인하세요.");
    log("MJPEG 이미지 로드 오류", { stream_url: descriptor.url });
  };

  streamWatchdog = setTimeout(async () => {
    if (gotFirstFrame || currentStreamUrl !== streamImg.src) return;
    streamImg.style.display = "none";
    setState("no frame", "error");
    setHint(`${Math.round(waitMs / 1000)}초 동안 첫 JPEG 프레임이 도착하지 않았습니다. 4102/URL은 열렸지만 media frame이 아직 없습니다.`);
    const noFramePayload = {
      waited_ms: waitMs,
      stream_url: descriptor.url,
      hint: "기존 live 표시는 src 설정 직후 켜지던 값이라 실제 프레임 수신 여부와 달랐습니다.",
    };
    log("첫 프레임 미수신", noFramePayload);

    const probeParams = new URLSearchParams({
      visualization_url: v.visualization_url,
      vehicle_id: v.vehicle_id,
      vehicle_name: v.vehicle_name,
      camera_name: v.camera_name,
      image_type: String(v.image_type),
      quality: String(v.quality),
    });
    try {
      log("단발 프레임 probe 결과", await getJSON(`/api/probe?${probeParams.toString()}`));
    } catch (err) {
      log("단발 프레임 probe 실패", err.data || { error: String(err) });
    }
  }, waitMs);

  setHint("스트림 URL을 열었습니다. 첫 JPEG 프레임을 기다리는 중입니다...");
  streamImg.src = currentStreamUrl;
  log("스트림 URL 열기 및 4102 공지 요청 완료", data);
}

function updateStreamOverlay({ imageSize = null, fpsText = null, captureText = null, warningText = null } = {}) {
  if (imageSize !== null && overlayImageSize) overlayImageSize.textContent = imageSize || "--";
  if (fpsText !== null && overlayFps) overlayFps.textContent = fpsText || "--";
  if (captureText !== null && overlayCapture) overlayCapture.textContent = captureText || "--";
  if (warningText !== null && overlayWarning) {
    overlayWarning.textContent = warningText || "--";
    overlayWarning.hidden = !warningText;
  }
}

function descriptorSizeText(descriptor) {
  const w = Number(descriptor?.width || 0);
  const h = Number(descriptor?.height || 0);
  return w > 0 && h > 0 ? `${w}×${h}` : "--";
}

function naturalSizeText() {
  const w = Number(streamImg.naturalWidth || 0);
  const h = Number(streamImg.naturalHeight || 0);
  return w > 0 && h > 0 ? `${w}×${h}` : "";
}

function formatNumber(value, digits = 1) {
  const n = Number(value || 0);
  if (!Number.isFinite(n) || n <= 0) return "--";
  return n.toFixed(digits);
}

function stopStatsPolling() {
  if (statsPoller) {
    clearInterval(statsPoller);
    statsPoller = null;
  }
}

function startStatsPolling(v, descriptor) {
  stopStatsPolling();
  pollStreamStats(v, descriptor).catch(() => {});
  statsPoller = setInterval(() => {
    pollStreamStats(v, descriptor).catch(() => {});
  }, 1000);
}

async function pollStreamStats(v, descriptor) {
  const params = new URLSearchParams({ visualization_url: v.visualization_url });
  const data = await getJSON(`/api/media-stats?${params.toString()}`);
  const stream = pickMatchingStream(data?.streams || [], v, descriptor);
  const imgText = naturalSizeText() || descriptorSizeText(descriptor);
  if (!stream) {
    updateStreamOverlay({
      imageSize: imgText,
      fpsText: `req ${formatNumber(descriptor?.fps || v.fps || 0, 0)}`,
      captureText: "--",
      warningText: "",
    });
    return;
  }
  const actual = Number(stream.actual_fps || 0);
  const target = Number(stream.target_fps || descriptor?.fps || v.fps || 0);
  const bytes = Number(stream.latest_bytes_len || 0);
  const captureMs = Number(stream.latest_capture_ms || 0);
  const meta = stream.latest_meta || {};
  const method = String(meta.capture_method || "").replace("simGet", "");
  const rpcClient = String(meta.rpc_client || "");
  const errors = Array.isArray(meta.fallback_errors)
    ? meta.fallback_errors.map(String)
    : (meta.fallback_errors ? [String(meta.fallback_errors)] : []);
  const errorText = errors.join("; ");
  const blackFrame = Boolean(meta.source_encoded_black || meta.converted_encoded_black || /black frame/i.test(errorText));
  const sourceLabel = meta.source_format ? ` · ${meta.source_format}` : "";
  const blackSuffix = blackFrame ? " · BLACK" : "";
  const kb = bytes > 0 ? ` · ${Math.round(bytes / 1024)}KB` : "";
  updateStreamOverlay({
    imageSize: imgText,
    fpsText: `${formatNumber(actual, 1)} / ${formatNumber(target, 0)}${kb}`,
    captureText: `${formatNumber(captureMs, 0)}ms${method ? ` · ${method}` : ""}${sourceLabel}${rpcClient ? ` · ${rpcClient}` : ""}${blackSuffix}`,
    warningText: blackFrame ? "AirSim API 원본 프레임이 검정입니다" : "",
  });
  if (blackFrame) {
    setState("black frame", "warn");
    const key = `${v.vehicle_id}/${v.camera_name}/${v.image_type}/${method}/${errorText}`;
    if (key !== lastBlackWarningKey) {
      lastBlackWarningKey = key;
      log("AirSim API 원본 프레임 블랙 감지", {
        vehicle_id: v.vehicle_id,
        vehicle_name: v.vehicle_name,
        camera_name: v.camera_name,
        image_type: v.image_type,
        capture_method: meta.capture_method,
        source_format: meta.source_format,
        source_encoded_black: meta.source_encoded_black,
        converted_encoded_black: meta.converted_encoded_black,
        fallback_errors: errors,
      });
    }
  } else if (streamImg.style.display !== "none") {
    setState("live", "live");
    lastBlackWarningKey = "";
  }
}

function pickMatchingStream(streams, v, descriptor) {
  const camera = String(descriptor?.camera_name || v.camera_name || "");
  const aircraft = String(descriptor?.vehicle_id || v.vehicle_id || "");
  const quality = Number(descriptor?.quality || v.quality || 0);
  const imageType = Number(descriptor?.image_type ?? v.image_type ?? 0);
  return streams.find((item) =>
    String(item.camera_name || "") === camera &&
    String(item.aircraft_id || "") === aircraft &&
    Number(item.image_type || 0) === imageType &&
    (!quality || Number(item.quality || 0) === quality)
  ) || streams.find((item) =>
    String(item.camera_name || "") === camera &&
    String(item.aircraft_id || "") === aircraft &&
    Number(item.image_type || 0) === imageType
  ) || streams.find((item) => String(item.camera_name || "") === camera) || streams[0] || null;
}

function applyDisplayScale() {
  const mode = fields.displayScale?.value || "fit";
  streamImg.style.maxWidth = "";
  streamImg.style.maxHeight = "";
  if (mode === "fit") {
    streamImg.style.minHeight = "540px";
    streamImg.style.width = "100%";
    streamImg.style.height = "100%";
    streamImg.style.objectFit = "contain";
    return;
  }
  if (mode === "fill") {
    streamImg.style.minHeight = "540px";
    streamImg.style.width = "100%";
    streamImg.style.height = "100%";
    streamImg.style.objectFit = "cover";
    return;
  }
  const scale = Number(mode || 1);
  const width = streamImg.naturalWidth || 640;
  const height = streamImg.naturalHeight || 360;
  streamImg.style.minHeight = "0";
  streamImg.style.width = `${Math.max(1, Math.round(width * scale))}px`;
  streamImg.style.height = `${Math.max(1, Math.round(height * scale))}px`;
  streamImg.style.objectFit = "contain";
}

function stopStream() {
  clearStreamImage();
  setHint("아직 스트림을 열지 않았습니다. 아래 설정 후 “스트림 시작”을 누르세요.");
  setState("idle", "idle");
  log("스트림 정지");
}

async function announceOnly() {
  const data = await postJSON("/api/announce", values());
  log("4102 공지 완료", data);
}

async function probeFrame() {
  const v = values();
  const params = new URLSearchParams({
    visualization_url: v.visualization_url,
    vehicle_id: v.vehicle_id,
    vehicle_name: v.vehicle_name,
    camera_name: v.camera_name,
    image_type: String(v.image_type),
    quality: String(v.quality),
  });
  const data = await getJSON(`/api/probe?${params.toString()}`);
  const errors = Array.isArray(data?.meta?.fallback_errors)
    ? data.meta.fallback_errors.join("; ")
    : String(data?.meta?.fallback_errors || "");
  if (data?.meta?.source_encoded_black || data?.meta?.converted_encoded_black || /black frame/i.test(errors)) {
    setState("probe black", "warn");
  }
  log("단발 프레임 probe 결과", data);
}

async function sendControl(delta) {
  const payload = { ...values(), ...delta };
  const data = await postJSON("/api/control", payload);
  log("5002 카메라 제어 전송", data);
}

async function launchUnreal() {
  setState("launching", "opening");
  setHint("Unreal 런타임을 일반 AirSim/MJPEG 경로로 시작하는 중입니다...");
  const data = await postJSON("/api/unreal/launch", {
    visualization_url: values().visualization_url,
    pixel_streaming: false,
  });
  log("Unreal 실행 요청 완료", data);
  setState("ready", "opening");
  setHint("Unreal 실행 요청이 완료되었습니다. 준비되면 “스트림 시작 + 4102 공지”를 누르세요.");
}

$("launchUnrealBtn").addEventListener("click", () => launchUnreal().catch((err) => {
  setState("launch error", "error");
  log("Unreal 실행 실패", err.data || { error: String(err) });
}));
$("startBtn").addEventListener("click", () => startStream().catch((err) => {
  setState("error", "error");
  log("스트림 시작 실패", err.data || { error: String(err) });
}));
$("stopBtn").addEventListener("click", stopStream);
$("announceBtn").addEventListener("click", () => announceOnly().catch((err) => log("4102 공지 실패", err.data || { error: String(err) })));
$("statusBtn").addEventListener("click", async () => {
  const v = values();
  const params = new URLSearchParams({ visualization_url: v.visualization_url, state_url: v.state_url });
  try { log("상태 확인", await getJSON(`/api/status?${params.toString()}`)); }
  catch (err) { log("상태 확인 실패", err.data || { error: String(err) }); }
});
$("mediaStatsBtn").addEventListener("click", async () => {
  const v = values();
  const params = new URLSearchParams({ visualization_url: v.visualization_url });
  try { log("스트림 producer/cache 통계", await getJSON(`/api/media-stats?${params.toString()}`)); }
  catch (err) { log("스트림 통계 확인 실패", err.data || { error: String(err) }); }
});
$("probeBtn").addEventListener("click", () => probeFrame().catch((err) => {
  log("단발 프레임 probe 실패", err.data || { error: String(err) });
}));
fields.displayScale?.addEventListener("change", () => {
  if (streamImg.style.display !== "none") {
    applyDisplayScale();
    log("표시 업스케일 변경", { display_scale: fields.displayScale.value });
  }
});

document.querySelectorAll("[data-cam]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const action = btn.getAttribute("data-cam");
    const step = 6;
    const zoomStep = 2.5;
    const map = {
      up: { pitch_delta_deg: step },
      down: { pitch_delta_deg: -step },
      left: { yaw_delta_deg: -step },
      right: { yaw_delta_deg: step },
      home: { yaw_delta_deg: 0, pitch_delta_deg: 0, focal_length_delta: 0 },
      zoomIn: { focal_length_delta: zoomStep },
      zoomOut: { focal_length_delta: -zoomStep },
    };
    sendControl(map[action] || {}).catch((err) => log("5002 전송 실패", err.data || { error: String(err) }));
  });
});

window.addEventListener("beforeunload", stopStream);
loadConfig();
