(() => {
  const FIELD_MODE_IMPACT = "impact-field";
  const FIELD_MODE_DENSITY = "density-field";
  const FIELD_MODE_CONGESTION = "congestion-field";
  const FIELD_MODES = [FIELD_MODE_IMPACT, FIELD_MODE_DENSITY, FIELD_MODE_CONGESTION];

  const FIELD_BUTTON_SELECTOR = {
    [FIELD_MODE_IMPACT]: '[data-action="layer-impact-field"]',
    [FIELD_MODE_DENSITY]: '[data-action="layer-density-field"]',
    [FIELD_MODE_CONGESTION]: '[data-action="layer-congestion-field"]',
  };

  const FIELD_SOURCE_ID = "traffic-field-heatmap-source";
  const FIELD_LAYER_MAIN_ID = "traffic-field-heatmap-main-layer";
  const FIELD_LAYER_LINK_ID = "traffic-field-heatmap-link-layer";
  const FIELD_WORKER_URL = "field_layers.worker.js?v=20260303h";
  const FIELD_UPDATE_MIN_INTERVAL_MS = 220;
  const FIELD_WATCHDOG_INTERVAL_MS = 1000;
  const FIELD_EMPTY_HOLD_MS = 1200;
  const FIELD_MAX_FEATURES = 1800;
  const FIELD_MEASURED_MODES = new Set(["takeoff", "cruise", "hold"]);
  const FIELD_CONGESTION_ONLY_MODES = new Set(["cruise"]);
  const FIELD_CONGESTION_MIN_SPEED_MPS = 1.0;
  const DEG_TO_RAD = Math.PI / 180;
  const EARTH_RADIUS_M = 6378137;
  const FIELD_RADIUS_IMPACT_PX = 48;
  const FIELD_RADIUS_DENSITY_PX = 54;
  const FIELD_RADIUS_CONGESTION_PX = 52;
  const FIELD_GRID_MIN = 112;
  const FIELD_GRID_MAX = 224;
  const FIELD_ROUTE_GROUP_MAIN = "main";
  const FIELD_ROUTE_GROUP_LINK = "link";

  const FIELD_CONGESTION_CONFIG =
    typeof window !== "undefined" && window.FIELD_CONGESTION_CONFIG
      ? window.FIELD_CONGESTION_CONFIG
      : null;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const nowMs = () =>
    typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now()
      : Date.now();

  const toFinite = (value, fallback = null) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const toFiniteOrNull = (value) => {
    if (value == null) {
      return null;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const normalizeName = (value) => String(value || "").trim();

  const cloneConfig = (config) => (config ? { ...config } : null);

  const resolveCongestionExclusionRadiusM = () => {
    if (!FIELD_CONGESTION_CONFIG) {
      return 0;
    }
    const value = Number(FIELD_CONGESTION_CONFIG.exclude_vertiport_radius_m);
    return Number.isFinite(value) ? Math.max(0, value) : 0;
  };

  const FALLBACK_CONGESTION_MIN_ALT_RATIO = 0.9;
  const FALLBACK_CONGESTION_MIN_ALT_M = 274.32;
  const FALLBACK_CONGESTION_MIN_SPEED_MPS = 1.0;

  const resolveCongestionMinAltitudeM = () => {
    const sourceConfig = FIELD_CONGESTION_CONFIG || null;
    const explicit = sourceConfig ? Number(sourceConfig.min_altitude_m) : NaN;
    if (Number.isFinite(explicit)) {
      return Math.max(0, explicit);
    }
    const ratio = sourceConfig
      ? Number(sourceConfig.min_altitude_ratio)
      : FALLBACK_CONGESTION_MIN_ALT_RATIO;
    const cruiseAlt =
      typeof FLIGHT_ALT_M === "number" && Number.isFinite(FLIGHT_ALT_M) ? FLIGHT_ALT_M : null;
    if (Number.isFinite(ratio)) {
      if (Number.isFinite(cruiseAlt)) {
        return Math.max(0, cruiseAlt * ratio);
      }
      return Math.max(0, FALLBACK_CONGESTION_MIN_ALT_M);
    }
    return Number.isFinite(cruiseAlt) ? Math.max(0, cruiseAlt * FALLBACK_CONGESTION_MIN_ALT_RATIO) : null;
  };

  const resolveAltitudeValue = (value) => {
    if (!value || typeof value !== "object") {
      return toFiniteOrNull(value);
    }
    if (Object.prototype.hasOwnProperty.call(value, "altitude_m_raw")) {
      return toFiniteOrNull(value.altitude_m_raw);
    }
    const raw =
      value.altitude_m != null
        ? value.altitude_m
        : value.alt_m != null
          ? value.alt_m
          : value.altitude != null
            ? value.altitude
            : value.alt;
    return toFiniteOrNull(raw);
  };

  const toMercatorMeters = (lon, lat) => {
    const x = EARTH_RADIUS_M * (lon * DEG_TO_RAD);
    const y = EARTH_RADIUS_M * Math.log(Math.tan(Math.PI / 4 + (lat * DEG_TO_RAD) / 2));
    return [x, y];
  };

  const isNearVertiport = (lon, lat, lookup, radiusM) => {
    if (!lookup || radiusM <= 0) {
      return false;
    }
    const [x, y] = toMercatorMeters(lon, lat);
    const r2 = radiusM * radiusM;
    for (const entry of lookup.values()) {
      if (!entry || !Array.isArray(entry.coord) || entry.coord.length < 2) {
        continue;
      }
      const vx = Number(entry.coord[0]);
      const vy = Number(entry.coord[1]);
      if (!Number.isFinite(vx) || !Number.isFinite(vy)) {
        continue;
      }
      const [px, py] = toMercatorMeters(vx, vy);
      const dx = x - px;
      const dy = y - py;
      if (dx * dx + dy * dy <= r2) {
        return true;
      }
    }
    return false;
  };

  const resolveBeforeId = (map) => {
    if (!map || !map.getLayer) {
      return undefined;
    }
    const preferred = [
      "traffic-points",
      "traffic-risk",
      "traffic-halo",
      "traffic-halo-core",
      "traffic-history-line",
      "traffic-predict-line",
      "flight-plan-route",
      "corridor-edit-ring",
    ];
    for (let i = 0; i < preferred.length; i += 1) {
      if (map.getLayer(preferred[i])) {
        return preferred[i];
      }
    }
    return undefined;
  };

  const emptyFeatureCollection = () => ({
    type: "FeatureCollection",
    features: [],
  });

  const resolveImpactWeight = (pos) => {
    const speed = clamp(toFinite(pos.speed_mps, 18), 0, 70);
    const delay = clamp(toFinite(pos.delay_s, 0), 0, 1200);
    const tti = clamp(toFinite(pos.tti, 1), 1, 4);
    const speedTerm = speed / 22;
    const delayTerm = delay / 220;
    const ttiTerm = (tti - 1) / 0.75;
    return clamp(0.65 + speedTerm * 0.7 + delayTerm * 0.5 + ttiTerm * 0.6, 0.05, 5.5);
  };

  const resolveCongestionWeight = (pos) => {
    const delay = clamp(toFinite(pos.delay_s, 0), 0, 1800);
    const tti = clamp(toFinite(pos.tti, 1), 1, 5);
    const delayNorm = delay / 200;
    const ttiNorm = (tti - 1) / 0.7;
    return clamp(Math.max(delayNorm, ttiNorm), 0, 6);
  };

  const isMeasuredPhasePosition = (pos, layerMode) => {
    if (!pos || typeof pos !== "object") {
      return false;
    }
    const mode = String(pos.mode || "")
      .trim()
      .toLowerCase();
    if (layerMode === FIELD_MODE_CONGESTION) {
      if (!FIELD_CONGESTION_ONLY_MODES.has(mode)) {
        return false;
      }
      if (pos.near_vertiport) {
        return false;
      }
      const speed = toFinite(pos.speed_mps, null);
      if (!Number.isFinite(speed) || speed < FIELD_CONGESTION_MIN_SPEED_MPS) {
        return false;
      }
      const minAltM = resolveCongestionMinAltitudeM();
      if (Number.isFinite(minAltM)) {
        const altitude = resolveAltitudeValue(pos);
        if (!Number.isFinite(altitude) || altitude < minAltM) {
          return false;
        }
      }
      return true;
    }
    return FIELD_MEASURED_MODES.has(mode);
  };

  const buildFieldFeatures = (positions, layerMode) => {
    if (!Array.isArray(positions) || !positions.length) {
      return emptyFeatureCollection();
    }
    const features = [];
    for (let i = 0; i < positions.length; i += 1) {
      if (features.length >= FIELD_MAX_FEATURES) {
        break;
      }
      const pos = positions[i];
      if (!pos) {
        continue;
      }
      if (!isMeasuredPhasePosition(pos, layerMode)) {
        continue;
      }
      const lon = toFinite(pos.lon, null);
      const lat = toFinite(pos.lat, null);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        continue;
      }
      features.push({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [lon, lat],
        },
        properties: {
          density_weight: 1,
          impact_weight: resolveImpactWeight(pos),
          congestion_weight: resolveCongestionWeight(pos),
          route_group:
            String(pos.route_group || "").toLowerCase() === FIELD_ROUTE_GROUP_LINK
              ? FIELD_ROUTE_GROUP_LINK
              : FIELD_ROUTE_GROUP_MAIN,
        },
      });
    }
    return {
      type: "FeatureCollection",
      features,
    };
  };

  const buildPaintForMode = (mode) => {
    if (mode === FIELD_MODE_IMPACT) {
      return {
        "heatmap-weight": ["coalesce", ["get", "impact_weight"], 0],
        "heatmap-intensity": 1.0,
        "heatmap-radius": FIELD_RADIUS_IMPACT_PX,
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0.0,
          "rgba(11,56,119,0.0)",
          0.18,
          "rgba(28,92,190,0.55)",
          0.45,
          "rgba(46,151,226,0.72)",
          0.72,
          "rgba(89,211,246,0.82)",
          1.0,
          "rgba(224,247,255,0.96)",
        ],
        "heatmap-opacity": 0.93,
      };
    }
    if (mode === FIELD_MODE_DENSITY) {
      return {
        "heatmap-weight": ["coalesce", ["get", "density_weight"], 0],
        "heatmap-intensity": 1.05,
        "heatmap-radius": FIELD_RADIUS_DENSITY_PX,
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0.0,
          "rgba(29,95,62,0.0)",
          0.2,
          "rgba(47,126,73,0.56)",
          0.44,
          "rgba(94,177,86,0.76)",
          0.7,
          "rgba(200,203,88,0.84)",
          1.0,
          "rgba(245,137,62,0.95)",
        ],
        "heatmap-opacity": 0.9,
      };
    }
    return {
      "heatmap-weight": ["coalesce", ["get", "congestion_weight"], 0],
      "heatmap-intensity": 1.08,
      "heatmap-radius": FIELD_RADIUS_CONGESTION_PX,
      "heatmap-color": [
        "interpolate",
        ["linear"],
        ["heatmap-density"],
        0.0,
        "rgba(253,231,161,0.0)",
        0.22,
        "rgba(251,186,116,0.6)",
        0.5,
        "rgba(245,130,76,0.82)",
        0.75,
        "rgba(230,86,66,0.92)",
        1.0,
        "rgba(183,42,56,0.98)",
      ],
      "heatmap-opacity": 0.95,
    };
  };

  MapApp.prototype.initFieldLayers = function () {
    this.fieldLayerButtons = {};
    FIELD_MODES.forEach((mode) => {
      this.fieldLayerButtons[mode] = document.querySelector(FIELD_BUTTON_SELECTOR[mode]);
    });

    this.fieldLayerMode = null;
    this.fieldLayerPositions = [];
    this.fieldLayerLatestPositions = null;
    this.fieldLayerUpdateTimer = null;
    this.fieldLayerWatchdogTimer = null;
    this.fieldLayerUpdateLastAt = 0;
    this.fieldLayerMapHandlersBound = false;
    this.fieldLayerLastNonEmptyData = null;
    this.fieldLayerLastNonEmptyAt = 0;
    this.fieldLayerCanvas = null;
    this.fieldLayerCanvasCtx = null;
    this.fieldLayerBufferCanvas = null;
    this.fieldLayerBufferCtx = null;
    this.fieldLayerWorker = null;
    this.fieldLayerWorkerReqId = 0;
    this.fieldLayerWorkerInFlight = false;
    this.fieldLayerWorkerPending = false;
    this.fieldLayerViewMoving = false;
    this.fieldLayerMoveEndTimer = null;

    FIELD_MODES.forEach((mode) => {
      const button = this.fieldLayerButtons[mode];
      if (!button) {
        return;
      }
      button.addEventListener("click", () => {
        const next = this.fieldLayerMode === mode ? null : mode;
        this.setFieldLayerMode(next);
        if (typeof this.setBaseListOpen === "function") {
          this.setBaseListOpen(false);
        }
      });
      button.setAttribute("aria-pressed", "false");
    });

    this.updateFieldLayerButtonStates();
    this.setupFieldLayerMapHandlers();
  };

  MapApp.prototype.updateFieldLayerButtonStates = function () {
    const mode = this.fieldLayerMode;
    FIELD_MODES.forEach((key) => {
      const button = this.fieldLayerButtons ? this.fieldLayerButtons[key] : null;
      if (!button) {
        return;
      }
      const active = mode === key;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    if (typeof document !== "undefined") {
      document.body.classList.toggle("field-layer-visible", Boolean(mode));
      document.body.classList.toggle("field-layer-impact-visible", mode === FIELD_MODE_IMPACT);
      document.body.classList.toggle("field-layer-density-visible", mode === FIELD_MODE_DENSITY);
      document.body.classList.toggle(
        "field-layer-congestion-visible",
        mode === FIELD_MODE_CONGESTION,
      );
    }
    this.applyFieldLayerTrafficFocus(mode);
  };

  MapApp.prototype.applyFieldLayerTrafficFocus = function (mode) {
    if (!this.map || !this.map.getLayer || !this.map.getPaintProperty) {
      return;
    }
    const enabled = mode === FIELD_MODE_CONGESTION;
    if (!this.fieldLayerTrafficPaintCache) {
      this.fieldLayerTrafficPaintCache = new Map();
    }
    const cache = this.fieldLayerTrafficPaintCache;
    const adjustments = [
      { layer: "traffic-points", props: { "icon-opacity": enabled ? 0.6 : null } },
      { layer: "traffic-risk", props: { "circle-opacity": enabled ? 0.35 : null } },
      { layer: "traffic-halo", props: { "circle-opacity": enabled ? 0.35 : null } },
      {
        layer: "traffic-halo-core",
        props: {
          "circle-stroke-opacity": enabled ? 0.35 : null,
          "circle-opacity": enabled ? 0.3 : null,
        },
      },
      { layer: "traffic-history-line", props: { "line-opacity": enabled ? 0.2 : null } },
      { layer: "traffic-history-dots", props: { "circle-opacity": enabled ? 0.15 : null } },
      { layer: "traffic-predict-line", props: { "line-opacity": enabled ? 0.2 : null } },
    ];
    adjustments.forEach((entry) => {
      if (!this.map.getLayer(entry.layer)) {
        return;
      }
      Object.keys(entry.props).forEach((prop) => {
        const key = `${entry.layer}:${prop}`;
        if (!cache.has(key)) {
          cache.set(key, this.map.getPaintProperty(entry.layer, prop));
        }
        const target = entry.props[prop];
        const value = target == null ? cache.get(key) : target;
        try {
          this.map.setPaintProperty(entry.layer, prop, value);
        } catch (_err) {
          // best-effort
        }
      });
    });
  };

  MapApp.prototype.ensureFieldLayerCanvas = function () {
    if (typeof document === "undefined" || !this.map || !this.map.getContainer) {
      return false;
    }
    if (!this.fieldLayerCanvas) {
      const canvas = document.createElement("canvas");
      canvas.className = "field-layer-canvas";
      canvas.style.position = "absolute";
      canvas.style.inset = "0";
      canvas.style.width = "100%";
      canvas.style.height = "100%";
      canvas.style.pointerEvents = "none";
      canvas.style.zIndex = "2";
      canvas.classList.add("is-hidden");
      this.fieldLayerCanvas = canvas;
      this.fieldLayerCanvasCtx = canvas.getContext("2d");
    }
    const container = this.map.getContainer();
    if (this.fieldLayerCanvas.parentElement !== container) {
      container.appendChild(this.fieldLayerCanvas);
    }
    const containerWidth = Math.max(1, Number(container.clientWidth || 0));
    const containerHeight = Math.max(1, Number(container.clientHeight || 0));
    const ratio =
      typeof window !== "undefined" && Number.isFinite(window.devicePixelRatio)
        ? Math.max(1, window.devicePixelRatio)
        : 1;
    const width = Math.max(1, Math.round(containerWidth * ratio));
    const height = Math.max(1, Math.round(containerHeight * ratio));
    if (this.fieldLayerCanvas.width !== width || this.fieldLayerCanvas.height !== height) {
      this.fieldLayerCanvas.width = width;
      this.fieldLayerCanvas.height = height;
    }
    return Boolean(this.fieldLayerCanvasCtx);
  };

  MapApp.prototype.setFieldLayerCanvasVisible = function (visible) {
    if (!this.fieldLayerCanvas) {
      return;
    }
    this.fieldLayerCanvas.classList.toggle("is-hidden", !visible);
    if (!visible) {
      this.fieldLayerCanvas.classList.remove("is-fading");
    }
  };

  MapApp.prototype.setFieldLayerCanvasFading = function (fading) {
    if (!this.fieldLayerCanvas) {
      return;
    }
    if (this.fieldLayerCanvas.classList.contains("is-hidden")) {
      return;
    }
    this.fieldLayerCanvas.classList.toggle("is-fading", Boolean(fading));
  };

  MapApp.prototype.clearFieldLayerCanvas = function () {
    if (!this.fieldLayerCanvasCtx || !this.fieldLayerCanvas) {
      return;
    }
    this.fieldLayerCanvasCtx.clearRect(0, 0, this.fieldLayerCanvas.width, this.fieldLayerCanvas.height);
  };

  MapApp.prototype.ensureFieldLayerWorker = function () {
    if (this.fieldLayerWorker || typeof Worker === "undefined") {
      return Boolean(this.fieldLayerWorker);
    }
    try {
      this.fieldLayerWorker = new Worker(FIELD_WORKER_URL);
    } catch (_err) {
      this.fieldLayerWorker = null;
      return false;
    }
    this.fieldLayerWorker.onmessage = (event) => {
      const payload = event && event.data ? event.data : null;
      if (!payload || !Number.isFinite(Number(payload.id))) {
        this.fieldLayerWorkerInFlight = false;
        return;
      }
      if (Number(payload.id) !== this.fieldLayerWorkerReqId) {
        return;
      }
      this.fieldLayerWorkerInFlight = false;
      if (!this.fieldLayerMode) {
        return;
      }
      if (String(payload.mode || "") === "congestion") {
        const ids = ArrayBuffer.isView(payload.congestionIds)
          ? payload.congestionIds
          : Array.isArray(payload.congestionIds)
            ? payload.congestionIds
            : null;
        const scores = ArrayBuffer.isView(payload.congestionScores)
          ? payload.congestionScores
          : Array.isArray(payload.congestionScores)
            ? payload.congestionScores
            : null;
        const map = new Map();
        if (ids && scores && ids.length === scores.length) {
          for (let i = 0; i < scores.length; i += 1) {
            const id = Number(ids[i]);
            const score = Number(scores[i]);
            if (Number.isFinite(id) && Number.isFinite(score)) {
              map.set(id, score);
            }
          }
        }
        this.congestionScoreById = map;
      } else {
        this.congestionScoreById = null;
      }
      if (!this.ensureFieldLayerCanvas()) {
        return;
      }
      const pixels = payload.pixels instanceof Uint8ClampedArray ? payload.pixels : null;
      const gridSize = Number(payload.gridSize);
      if (!pixels || !Number.isFinite(gridSize) || gridSize <= 0) {
        this.clearFieldLayerCanvas();
      } else {
        if (!this.fieldLayerBufferCanvas || this.fieldLayerBufferCanvas.width !== gridSize) {
          const buffer = document.createElement("canvas");
          buffer.width = gridSize;
          buffer.height = gridSize;
          this.fieldLayerBufferCanvas = buffer;
          this.fieldLayerBufferCtx = buffer.getContext("2d");
        }
        if (this.fieldLayerBufferCtx && this.fieldLayerCanvasCtx) {
          const imageData = new ImageData(pixels, gridSize, gridSize);
          this.fieldLayerBufferCtx.putImageData(imageData, 0, 0);
          this.fieldLayerCanvasCtx.clearRect(
            0,
            0,
            this.fieldLayerCanvas.width,
            this.fieldLayerCanvas.height,
          );
          this.fieldLayerCanvasCtx.imageSmoothingEnabled = true;
          this.fieldLayerCanvasCtx.drawImage(
            this.fieldLayerBufferCanvas,
            0,
            0,
            this.fieldLayerCanvas.width,
            this.fieldLayerCanvas.height,
          );
          this.fieldLayerLastNonEmptyAt = nowMs();
          if (!this.fieldLayerViewMoving) {
            this.setFieldLayerCanvasFading(false);
          }
        }
      }
      if (this.fieldLayerWorkerPending) {
        this.fieldLayerWorkerPending = false;
        this.scheduleFieldLayerUpdate(false);
      }
    };
    return true;
  };

  MapApp.prototype.resolveFieldLayerWorkerMode = function () {
    if (this.fieldLayerMode === FIELD_MODE_IMPACT) {
      return "impact";
    }
    if (this.fieldLayerMode === FIELD_MODE_CONGESTION) {
      return "congestion";
    }
    return "density";
  };

  MapApp.prototype.resolveFieldLayerGridSize = function () {
    const canvas =
      this.fieldLayerCanvas && Number.isFinite(Number(this.fieldLayerCanvas.width))
        ? this.fieldLayerCanvas
        : null;
    if (!canvas) {
      return clamp(160, FIELD_GRID_MIN, FIELD_GRID_MAX);
    }
    // Keep field resolution tied to viewport pixels, not flight count,
    // so zoom changes do not alter perceived blob size.
    const maxSide = Math.max(1, Number(canvas.width || 0), Number(canvas.height || 0));
    const base = Math.round(maxSide / 9);
    return clamp(base, FIELD_GRID_MIN, FIELD_GRID_MAX);
  };

  MapApp.prototype.resolveFieldLayerCongestionConfig = function () {
    const config = cloneConfig(FIELD_CONGESTION_CONFIG) || {};
    if (this.rulesState && Number.isFinite(Number(this.rulesState.speed_mps))) {
      config.freeflow_mps = Number(this.rulesState.speed_mps);
    }
    if (!Number.isFinite(Number(config.min_speed_mps))) {
      config.min_speed_mps = FALLBACK_CONGESTION_MIN_SPEED_MPS;
    }
    const minAltM = resolveCongestionMinAltitudeM();
    if (Number.isFinite(minAltM)) {
      config.min_altitude_m = minAltM;
    }
    return Object.keys(config).length ? config : null;
  };


  MapApp.prototype.ensureFieldLayerSourceAndLayer = function () {
    if (!this.map || !this.map.isStyleLoaded || !this.map.isStyleLoaded()) {
      return false;
    }
    if (!this.map.getSource(FIELD_SOURCE_ID)) {
      this.map.addSource(FIELD_SOURCE_ID, {
        type: "geojson",
        data: emptyFeatureCollection(),
      });
    }
    if (!this.map.getLayer(FIELD_LAYER_MAIN_ID)) {
      const beforeId = resolveBeforeId(this.map);
      const layer = {
        id: FIELD_LAYER_MAIN_ID,
        type: "heatmap",
        source: FIELD_SOURCE_ID,
        filter: ["==", ["coalesce", ["get", "route_group"], FIELD_ROUTE_GROUP_MAIN], FIELD_ROUTE_GROUP_MAIN],
        paint: buildPaintForMode(this.fieldLayerMode || FIELD_MODE_DENSITY),
      };
      if (beforeId) {
        this.map.addLayer(layer, beforeId);
      } else {
        this.map.addLayer(layer);
      }
    }
    if (!this.map.getLayer(FIELD_LAYER_LINK_ID)) {
      const beforeId = this.map.getLayer(FIELD_LAYER_MAIN_ID)
        ? FIELD_LAYER_MAIN_ID
        : resolveBeforeId(this.map);
      const layer = {
        id: FIELD_LAYER_LINK_ID,
        type: "heatmap",
        source: FIELD_SOURCE_ID,
        filter: ["==", ["coalesce", ["get", "route_group"], FIELD_ROUTE_GROUP_MAIN], FIELD_ROUTE_GROUP_LINK],
        paint: buildPaintForMode(this.fieldLayerMode || FIELD_MODE_DENSITY),
      };
      if (beforeId) {
        this.map.addLayer(layer, beforeId);
      } else {
        this.map.addLayer(layer);
      }
    }
    return true;
  };

  MapApp.prototype.setFieldLayerVisibility = function (visible) {
    if (!this.map || !this.map.getLayer) {
      return;
    }
    [FIELD_LAYER_MAIN_ID, FIELD_LAYER_LINK_ID].forEach((layerId) => {
      if (!this.map.getLayer(layerId)) {
        return;
      }
      try {
        this.map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
      } catch (_err) {
        // best-effort
      }
    });
  };

  MapApp.prototype.updateFieldLayerPaint = function () {
    if (!this.map || !this.map.getLayer) {
      return;
    }
    const paint = buildPaintForMode(this.fieldLayerMode || FIELD_MODE_DENSITY);
    [FIELD_LAYER_MAIN_ID, FIELD_LAYER_LINK_ID].forEach((layerId) => {
      if (!this.map.getLayer(layerId)) {
        return;
      }
      Object.keys(paint).forEach((key) => {
        try {
          this.map.setPaintProperty(layerId, key, paint[key]);
        } catch (_err) {
          // best-effort
        }
      });
    });
  };

  MapApp.prototype.updateFieldLayerData = function () {
    if (!this.fieldLayerMode || !this.map) {
      return;
    }
    if (this.fieldLayerViewMoving) {
      return;
    }
    if (!this.map.getBounds) {
      return;
    }
    if (!this.ensureFieldLayerCanvas()) {
      return;
    }
    if (!this.ensureFieldLayerWorker()) {
      return;
    }
    this.setFieldLayerVisibility(false);
    this.setFieldLayerCanvasVisible(true);
    const flights = [];
    if (Array.isArray(this.fieldLayerPositions) && this.fieldLayerPositions.length) {
      for (let i = 0; i < this.fieldLayerPositions.length; i += 1) {
        const pos = this.fieldLayerPositions[i];
        if (!isMeasuredPhasePosition(pos, this.fieldLayerMode)) {
          continue;
        }
        const lon = toFinite(pos.lon, null);
        const lat = toFinite(pos.lat, null);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          continue;
        }
        flights.push({
          id: toFinite(pos.id, null),
          lon,
          lat,
          mode: pos.mode ? String(pos.mode) : "",
          near_vertiport: Boolean(pos.near_vertiport),
          speed_mps: toFinite(pos.speed_mps, null),
          speed_target_mps: toFinite(pos.speed_target_mps, null),
          heading_deg: toFinite(pos.track_heading_deg ?? pos.heading_deg, null),
          delay_s: toFinite(pos.delay_s, null),
          tti: toFinite(pos.tti, null),
          altitude_m: toFinite(pos.altitude_m, null),
          altitude_m_raw: toFiniteOrNull(pos.altitude_m_raw),
        });
        if (flights.length >= FIELD_MAX_FEATURES) {
          break;
        }
      }
    }
    if (!flights.length) {
      const current = nowMs();
      if (current - Number(this.fieldLayerLastNonEmptyAt || 0) > FIELD_EMPTY_HOLD_MS) {
        this.clearFieldLayerCanvas();
        this.setFieldLayerCanvasFading(true);
      }
      return;
    }
    if (this.fieldLayerWorkerInFlight) {
      this.fieldLayerWorkerPending = true;
      return;
    }
    const bounds = this.map.getBounds();
    if (!bounds) {
      return;
    }
    const gridSize = this.resolveFieldLayerGridSize();
    const payload = {
      type: "compute",
      id: this.fieldLayerWorkerReqId + 1,
      mode: this.resolveFieldLayerWorkerMode(),
      nowMs: nowMs(),
      bounds: {
        west: Number(bounds.getWest()),
        south: Number(bounds.getSouth()),
        east: Number(bounds.getEast()),
        north: Number(bounds.getNorth()),
      },
      gridSize,
      viewport: {
        width: Math.max(1, Number(this.fieldLayerCanvas ? this.fieldLayerCanvas.width : gridSize)),
        height: Math.max(1, Number(this.fieldLayerCanvas ? this.fieldLayerCanvas.height : gridSize)),
      },
      flights,
    };
    const congestionConfig = this.resolveFieldLayerCongestionConfig();
    if (congestionConfig) {
      payload.config = congestionConfig;
    }
    this.fieldLayerWorkerReqId = Number(payload.id);
    this.fieldLayerWorkerInFlight = true;
    try {
      this.fieldLayerWorker.postMessage(payload);
    } catch (_err) {
      this.fieldLayerWorkerInFlight = false;
    }
  };

  MapApp.prototype.captureFieldLayerPositionsFromRendered = function (fallbackPositions) {
    const next = [];
    const resolveRouteGroup = (routeFromValue, routeToValue, modeValue) => {
      const routeFrom = normalizeName(routeFromValue);
      const routeTo = normalizeName(routeToValue);
      const mode = String(modeValue || "")
        .trim()
        .toLowerCase();
      const lookup = this.vertiportPointLookup instanceof Map ? this.vertiportPointLookup : null;
      const isVertiportNode = (name) => Boolean(lookup && name && lookup.has(name));
      const fromIsPort = isVertiportNode(routeFrom);
      const toIsPort = isVertiportNode(routeTo);
      if ((fromIsPort || toIsPort) && (routeFrom || routeTo)) {
        return FIELD_ROUTE_GROUP_LINK;
      }
      if (mode === "landing" && (fromIsPort || toIsPort)) {
        return FIELD_ROUTE_GROUP_LINK;
      }
      return FIELD_ROUTE_GROUP_MAIN;
    };

    const exclusionRadiusM =
      this.fieldLayerMode === FIELD_MODE_CONGESTION ? resolveCongestionExclusionRadiusM() : 0;
    const vertiportLookup =
      this.vertiportPointLookup instanceof Map ? this.vertiportPointLookup : null;

    if (this.trafficById instanceof Map && this.trafficById.size > 0) {
      this.trafficById.forEach((entry) => {
        if (!entry || !entry.props) {
          return;
        }
        const coords = Array.isArray(entry.coords)
          ? entry.coords
          : Array.isArray(entry.rawCoords)
            ? entry.rawCoords
            : null;
        if (!coords || coords.length < 2) {
          return;
        }
        const lon = toFinite(coords[0], null);
        const lat = toFinite(coords[1], null);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          return;
        }
        const props = entry.props || {};
        const routeFrom = normalizeName(props.route_from);
        const routeTo = normalizeName(props.route_to);
        const altitudeM = resolveAltitudeValue(props);
        const altitudeRawM = toFiniteOrNull(props.altitude_m_raw);
        const nearVertiport =
          this.fieldLayerMode === FIELD_MODE_CONGESTION &&
          exclusionRadiusM > 0 &&
          isNearVertiport(lon, lat, vertiportLookup, exclusionRadiusM);
        const headingDeg = toFinite(
          props.track_heading_deg ?? props.heading_deg ?? props.heading,
          null,
        );
        const trackHeadingDeg = toFinite(props.track_heading_deg, null);
        next.push({
          id: toFinite(entry.id ?? props.id, null),
          lon,
          lat,
          mode: props.mode ? String(props.mode) : "",
          route_from: routeFrom,
          route_to: routeTo,
          route_group: resolveRouteGroup(routeFrom, routeTo, props.mode),
          near_vertiport: nearVertiport,
          speed_mps: toFinite(props.speed_mps, null),
          speed_target_mps: toFinite(props.speed_target_mps, null),
          heading_deg: headingDeg,
          track_heading_deg: trackHeadingDeg,
          delay_s: toFinite(props.delay_s, null),
          tti: toFinite(props.tti, null),
          altitude_m: altitudeM,
          altitude_m_raw: altitudeRawM,
        });
      });
    }
    if (!next.length && Array.isArray(fallbackPositions)) {
      for (let i = 0; i < fallbackPositions.length; i += 1) {
        const pos = fallbackPositions[i];
        if (!pos) {
          continue;
        }
        const lon = toFinite(pos.lon, null);
        const lat = toFinite(pos.lat, null);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          continue;
        }
        const altitudeM = resolveAltitudeValue(pos);
        const altitudeRawM = toFiniteOrNull(pos.altitude_m_raw);
        const routeFrom = normalizeName(pos.route_from);
        const routeTo = normalizeName(pos.route_to);
        const nearVertiport =
          this.fieldLayerMode === FIELD_MODE_CONGESTION &&
          exclusionRadiusM > 0 &&
          isNearVertiport(lon, lat, vertiportLookup, exclusionRadiusM);
        const headingDeg = toFinite(
          pos.track_heading_deg ?? pos.heading_deg ?? pos.heading,
          null,
        );
        const trackHeadingDeg = toFinite(pos.track_heading_deg, null);
        next.push({
          id: toFinite(pos.id, null),
          lon,
          lat,
          mode: pos.mode ? String(pos.mode) : "",
          route_from: routeFrom,
          route_to: routeTo,
          route_group: resolveRouteGroup(routeFrom, routeTo, pos.mode),
          near_vertiport: nearVertiport,
          speed_mps: toFinite(pos.speed_mps, null),
          speed_target_mps: toFinite(pos.speed_target_mps, null),
          heading_deg: headingDeg,
          track_heading_deg: trackHeadingDeg,
          delay_s: toFinite(pos.delay_s, null),
          tti: toFinite(pos.tti, null),
          altitude_m: altitudeM,
          altitude_m_raw: altitudeRawM,
        });
      }
    }
    this.fieldLayerPositions = next;
  };

  MapApp.prototype.getFieldLayerFallbackPositions = function () {
    if (Array.isArray(this.fieldLayerLatestPositions) && this.fieldLayerLatestPositions.length) {
      return this.fieldLayerLatestPositions;
    }
    if (this.webPositionsCache instanceof Map && this.webPositionsCache.size > 0) {
      return Array.from(this.webPositionsCache.values());
    }
    if (Array.isArray(this.pendingTrafficPositions) && this.pendingTrafficPositions.length) {
      return this.pendingTrafficPositions;
    }
    return null;
  };

  MapApp.prototype.scheduleFieldLayerUpdate = function (force = false) {
    if (!this.fieldLayerMode) {
      return;
    }
    if (this.fieldLayerViewMoving) {
      return;
    }
    if (!this.map || !this.map.isStyleLoaded || !this.map.isStyleLoaded()) {
      return;
    }
    if (force) {
      if (this.fieldLayerUpdateTimer != null) {
        clearTimeout(this.fieldLayerUpdateTimer);
        this.fieldLayerUpdateTimer = null;
      }
      this.fieldLayerUpdateLastAt = nowMs();
      this.updateFieldLayerData();
      return;
    }
    if (this.fieldLayerUpdateTimer != null) {
      return;
    }
    const current = nowMs();
    const elapsed = current - (Number(this.fieldLayerUpdateLastAt) || 0);
    const waitMs = force ? 0 : Math.max(0, FIELD_UPDATE_MIN_INTERVAL_MS - elapsed);
    this.fieldLayerUpdateTimer = window.setTimeout(() => {
      this.fieldLayerUpdateTimer = null;
      this.fieldLayerUpdateLastAt = nowMs();
      this.updateFieldLayerData();
    }, waitMs);
  };

  MapApp.prototype.clearFieldLayerData = function () {
    this.fieldLayerWorkerPending = false;
    this.fieldLayerViewMoving = false;
    if (this.fieldLayerMoveEndTimer != null) {
      clearTimeout(this.fieldLayerMoveEndTimer);
      this.fieldLayerMoveEndTimer = null;
    }
    if (!this.map) {
      this.clearFieldLayerCanvas();
      this.setFieldLayerCanvasVisible(false);
      return;
    }
    if (this.fieldLayerWorker) {
      try {
        this.fieldLayerWorker.postMessage({ type: "reset" });
      } catch (_err) {
        // best-effort
      }
    }
    const source = this.map.getSource ? this.map.getSource(FIELD_SOURCE_ID) : null;
    if (source && typeof source.setData === "function") {
      source.setData(emptyFeatureCollection());
    }
    this.fieldLayerLastNonEmptyData = null;
    this.fieldLayerLastNonEmptyAt = 0;
    this.clearFieldLayerCanvas();
    this.setFieldLayerCanvasVisible(false);
    this.setFieldLayerVisibility(false);
  };

  MapApp.prototype.startFieldLayerWatchdog = function () {
    if (this.fieldLayerWatchdogTimer != null) {
      return;
    }
    this.fieldLayerWatchdogTimer = window.setInterval(() => {
      if (!this.fieldLayerMode) {
        return;
      }
      if (this.fieldLayerViewMoving) {
        return;
      }
      const last = Number(this.fieldLayerUpdateLastAt || 0);
      const elapsed = nowMs() - last;
      if (elapsed < FIELD_WATCHDOG_INTERVAL_MS) {
        return;
      }
      const fallback = this.getFieldLayerFallbackPositions();
      this.captureFieldLayerPositionsFromRendered(fallback);
      this.scheduleFieldLayerUpdate(false);
    }, FIELD_WATCHDOG_INTERVAL_MS);
  };

  MapApp.prototype.stopFieldLayerWatchdog = function () {
    if (this.fieldLayerWatchdogTimer == null) {
      return;
    }
    clearInterval(this.fieldLayerWatchdogTimer);
    this.fieldLayerWatchdogTimer = null;
  };

  MapApp.prototype.setFieldLayerMode = function (mode) {
    const next = FIELD_MODES.includes(mode) ? mode : null;
    if (next && typeof this.disableOtherBaseLayers === "function") {
      this.disableOtherBaseLayers(next);
    }
    this.fieldLayerMode = next;
    this.updateFieldLayerButtonStates();
    if (next !== FIELD_MODE_CONGESTION) {
      this.congestionScoreById = null;
    }

    if (!next) {
      if (this.fieldLayerUpdateTimer != null) {
        clearTimeout(this.fieldLayerUpdateTimer);
        this.fieldLayerUpdateTimer = null;
      }
      this.stopFieldLayerWatchdog();
      this.clearFieldLayerData();
      return;
    }
    this.startFieldLayerWatchdog();
    this.setFieldLayerVisibility(false);
    this.fieldLayerViewMoving = false;
    this.setFieldLayerCanvasVisible(true);
    this.setFieldLayerCanvasFading(true);
    // Capture currently rendered aircraft first so the layer appears immediately on click.
    const fallbackPositions = this.getFieldLayerFallbackPositions();
    this.captureFieldLayerPositionsFromRendered(fallbackPositions);
    this.scheduleFieldLayerUpdate(true);
    // Trigger one more frame-aligned update to reduce first-frame miss during UI/style timing.
    if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
      const modeAtRequest = next;
      window.requestAnimationFrame(() => {
        if (this.fieldLayerMode === modeAtRequest) {
          const fallback = this.getFieldLayerFallbackPositions();
          this.captureFieldLayerPositionsFromRendered(fallback);
          this.scheduleFieldLayerUpdate(false);
        }
      });
    }
  };

  MapApp.prototype.setupFieldLayerMapHandlers = function () {
    if (!this.map || this.fieldLayerMapHandlersBound) {
      return;
    }
    this.fieldLayerMapHandlersBound = true;
    const beginMove = () => {
      if (!this.fieldLayerMode) {
        return;
      }
      this.fieldLayerViewMoving = true;
      this.setFieldLayerCanvasFading(true);
    };
    const refresh = () => {
      if (!this.fieldLayerMode) {
        return;
      }
      const fallback = this.getFieldLayerFallbackPositions();
      this.captureFieldLayerPositionsFromRendered(fallback);
      this.scheduleFieldLayerUpdate(true);
    };
    const endMove = () => {
      if (!this.fieldLayerMode) {
        return;
      }
      if (this.fieldLayerMoveEndTimer != null) {
        clearTimeout(this.fieldLayerMoveEndTimer);
      }
      this.fieldLayerMoveEndTimer = window.setTimeout(() => {
        this.fieldLayerMoveEndTimer = null;
        if (!this.map || (typeof this.map.isMoving === "function" && this.map.isMoving())) {
          return;
        }
        this.fieldLayerViewMoving = false;
        refresh();
      }, 40);
    };
    this.map.on("styledata", refresh);
    this.map.on("movestart", beginMove);
    this.map.on("zoomstart", beginMove);
    this.map.on("rotatestart", beginMove);
    this.map.on("pitchstart", beginMove);
    this.map.on("moveend", endMove);
    this.map.on("zoomend", endMove);
    this.map.on("rotateend", endMove);
    this.map.on("pitchend", endMove);
    this.map.on("resize", () => {
      if (!this.fieldLayerMode) {
        return;
      }
      this.setFieldLayerCanvasFading(true);
      this.fieldLayerViewMoving = false;
      refresh();
    });
  };

  const baseInit = MapApp.prototype.init;
  if (baseInit) {
    MapApp.prototype.init = function () {
      baseInit.call(this);
      this.initFieldLayers();
    };
  }

  const baseUpdateTrafficPositions = MapApp.prototype.updateTrafficPositions;
  if (baseUpdateTrafficPositions) {
    MapApp.prototype.updateTrafficPositions = function (positions) {
      const result = baseUpdateTrafficPositions.call(this, positions);
      if (Array.isArray(positions)) {
        this.fieldLayerLatestPositions = positions;
      }
      return result;
    };
  }

  const baseApplyWebPositions = MapApp.prototype.applyWebPositions;
  if (baseApplyWebPositions) {
    MapApp.prototype.applyWebPositions = function (payload) {
      const result = baseApplyWebPositions.call(this, payload);
      if (this.fieldLayerMode && !this.fieldLayerViewMoving) {
        const fallback = this.getFieldLayerFallbackPositions();
        this.captureFieldLayerPositionsFromRendered(fallback);
        this.scheduleFieldLayerUpdate(false);
      }
      return result;
    };
  }

  const baseApplyTrafficPositions = MapApp.prototype.applyTrafficPositions;
  if (baseApplyTrafficPositions) {
    MapApp.prototype.applyTrafficPositions = function (positions) {
      const result = baseApplyTrafficPositions.call(this, positions);
      if (Array.isArray(positions)) {
        this.fieldLayerLatestPositions = positions;
      }
      if (this.fieldLayerMode && !this.fieldLayerViewMoving) {
        const fallback = this.getFieldLayerFallbackPositions();
        this.captureFieldLayerPositionsFromRendered(fallback);
        this.scheduleFieldLayerUpdate(true);
      }
      return result;
    };
  }
})();
