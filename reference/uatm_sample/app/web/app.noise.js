(() => {
  const NOISE_POPOUT_ID = "noise";
  const NOISE_L0_DB = 60.0;
  const NOISE_D0_M = 300.0;
  const NOISE_SLOPE = -20.0;
  const NOISE_MAX_DB = 80.0;
  const NOISE_MIN_DB_DEFAULT = 40;
  const NOISE_UPDATE_INTERVAL_MS = 1200;
  const NOISE_GRID_MIN = 80;
  const NOISE_GRID_MAX = 128;
  const NOISE_GRID_HIGH = 128;
  const NOISE_GRID_MED = 112;
  const NOISE_GRID_LOW = 96;
  const NOISE_GRID_EXPANDED_MIN = 160;
  const NOISE_GRID_EXPANDED_MAX = 256;
  const NOISE_GRID_EXPANDED_HIGH = 256;
  const NOISE_GRID_EXPANDED_MED = 224;
  const NOISE_GRID_EXPANDED_LOW = 192;
  const NOISE_DEM_ZOOM_CAP = 11;
  const NOISE_MINIMAP_ZOOM_OFFSET = -1.4;
  const NOISE_MINIMAP_MIN_ZOOM = 9;
  const NOISE_MINIMAP_LOCKED = false;
  const NOISE_SEOUL_BOUNDS = {
    west: 126.6,
    south: 37.35,
    east: 127.3,
    north: 37.8,
  };
  const NOISE_AVERAGE_CHANNEL = "noise-average";
  const DEG_TO_RAD = Math.PI / 180;
  const EARTH_RADIUS_M = 6378137;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const toMercator = (lon, lat) => {
    const x = EARTH_RADIUS_M * (lon * DEG_TO_RAD);
    const y = EARTH_RADIUS_M * Math.log(Math.tan(Math.PI / 4 + (lat * DEG_TO_RAD) / 2));
    return [x, y];
  };
  const readPanelParam = () => {
    if (typeof window === "undefined" || !window.location) {
      return "";
    }
    try {
      const params = new URLSearchParams(window.location.search);
      return String(params.get("panel") || "").toLowerCase();
    } catch (_err) {
      return "";
    }
  };
  const isNoisePopout = () => readPanelParam() === NOISE_POPOUT_ID;
  const buildPopoutUrl = (panelId) => {
    if (typeof window === "undefined" || !window.location) {
      return "";
    }
    const href = window.location.href;
    if (typeof URL === "function") {
      const url = new URL(href);
      url.searchParams.set("panel", panelId);
      return url.toString();
    }
    const base = href.split("#")[0];
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}panel=${encodeURIComponent(panelId)}`;
  };
  const openNoisePopout = () => {
    if (typeof window === "undefined" || !window.open) {
      return;
    }
    const url = buildPopoutUrl(NOISE_POPOUT_ID);
    if (!url) {
      return;
    }
    const popout = window.open(url, "noise-popout");
    if (popout && popout.focus) {
      popout.focus();
    }
  };

  if (isNoisePopout() && typeof document !== "undefined") {
    document.body.classList.add("panel-popout", "panel-popout-noise");
  }

  const NOISE_LAYER_PAINT = {
    background: "background-color",
    landcover: "fill-color",
    landuse: "fill-color",
    park: "fill-color",
    water: "fill-color",
    waterway: "line-color",
    boundary: "line-color",
    transportation: "line-color",
    building: "fill-color",
  };

  const NOISE_FALLBACK_PALETTES = {
    light: {
      background: "#eef2f3",
      landcover: "#dfe8d8",
      landuse: "#e8e6d8",
      park: "#cfe8c5",
      water: "#a8c8e6",
      waterway: "#90b7dd",
      boundary: "#9a9a9a",
      transportation: "#c2b59b",
      building: "#d0c7c2",
    },
    dark: {
      background: "#0f1820",
      landcover: "#182522",
      landuse: "#1b2320",
      park: "#1d3024",
      water: "#142a3e",
      waterway: "#1f425e",
      boundary: "#5e6872",
      transportation: "#4a453a",
      building: "#2f2c2a",
    },
  };

  const lonLatToTile = (lon, lat, zoom) => {
    const n = 2 ** zoom;
    const x = ((lon + 180) / 360) * n;
    const latRad = lat * DEG_TO_RAD;
    const y =
      (1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) /
      2 *
      n;
    return { x, y };
  };

  class NoiseDemSampler {
    constructor(tileUrl, tileSize, maxZoom) {
      this.tileUrl = tileUrl;
      this.tileSize = tileSize || 256;
      this.maxZoom = maxZoom || 12;
      this.zoom = Math.min(this.maxZoom, NOISE_DEM_ZOOM_CAP);
      this.cache = new Map();
      this.pending = new Map();
      this.cacheOrder = [];
      this.maxCacheTiles = 64;
      this.disabled = false;
      this.hasData = false;
      this.failureCount = 0;
      this.maxFailuresBeforeDisable = 6;
      this.canvas = null;
      this.ctx = null;
      if (typeof document !== "undefined") {
        const canvas = document.createElement("canvas");
        canvas.width = this.tileSize;
        canvas.height = this.tileSize;
        this.canvas = canvas;
        this.ctx = canvas.getContext("2d", { willReadFrequently: true });
      }
    }

    async _fetchImage(url) {
      try {
        const response = await fetch(url, { cache: "force-cache" });
        if (!response.ok) {
          return null;
        }
        const blob = await response.blob();
        if (typeof createImageBitmap === "function") {
          return await createImageBitmap(blob);
        }
        return await new Promise((resolve, reject) => {
          const img = new Image();
          const objectUrl = URL.createObjectURL(blob);
          img.onload = () => {
            URL.revokeObjectURL(objectUrl);
            resolve(img);
          };
          img.onerror = () => {
            URL.revokeObjectURL(objectUrl);
            reject(new Error("Image decode failed"));
          };
          img.src = objectUrl;
        });
      } catch (_err) {
        return null;
      }
    }

    _cacheTile(key, data) {
      if (this.cache.has(key)) {
        return;
      }
      this.cache.set(key, data);
      if (data) {
        this.hasData = true;
      }
      this.cacheOrder.push(key);
      if (this.cacheOrder.length > this.maxCacheTiles) {
        const oldest = this.cacheOrder.shift();
        if (oldest) {
          this.cache.delete(oldest);
        }
      }
    }

    async _getTile(z, x, y) {
      if (!this.tileUrl || this.disabled || !this.ctx) {
        return null;
      }
      const key = `${z}/${x}/${y}`;
      if (this.cache.has(key)) {
        return this.cache.get(key);
      }
      if (this.pending.has(key)) {
        return await this.pending.get(key);
      }
      const url = this.tileUrl
        .replace("{z}", String(z))
        .replace("{x}", String(x))
        .replace("{y}", String(y));
      const promise = (async () => {
        const image = await this._fetchImage(url);
        if (!image) {
          this.failureCount += 1;
          if (!this.hasData && this.failureCount >= this.maxFailuresBeforeDisable) {
            this.disabled = true;
          }
          this._cacheTile(key, null);
          return null;
        }
        this.failureCount = 0;
        this.ctx.clearRect(0, 0, this.tileSize, this.tileSize);
        this.ctx.drawImage(image, 0, 0, this.tileSize, this.tileSize);
        const pixels = this.ctx.getImageData(0, 0, this.tileSize, this.tileSize).data;
        const heights = new Float32Array(this.tileSize * this.tileSize);
        for (let idx = 0; idx < heights.length; idx += 1) {
          const base = idx * 4;
          const r = pixels[base];
          const g = pixels[base + 1];
          const b = pixels[base + 2];
          heights[idx] = r * 256 + g + b / 256 - 32768;
        }
        this._cacheTile(key, heights);
        return heights;
      })();
      this.pending.set(key, promise);
      try {
        return await promise;
      } finally {
        this.pending.delete(key);
      }
    }

    async sampleGrid(bounds, gridSize) {
      if (!this.tileUrl || this.disabled) {
        return null;
      }
      const z = this.zoom;
      const west = bounds.west;
      const east = bounds.east;
      const south = bounds.south;
      const north = bounds.north;
      if (
        !Number.isFinite(west) ||
        !Number.isFinite(east) ||
        !Number.isFinite(south) ||
        !Number.isFinite(north)
      ) {
        return null;
      }
      const lonStep = (east - west) / gridSize;
      const latStep = (north - south) / gridSize;
      const tileTasks = new Map();
      const tileInfo = new Array(gridSize * gridSize);
      const n = 2 ** z;
      for (let row = 0; row < gridSize; row += 1) {
        const lat = north - (row + 0.5) * latStep;
        for (let col = 0; col < gridSize; col += 1) {
          const lon = west + (col + 0.5) * lonStep;
          const tileCoord = lonLatToTile(lon, lat, z);
          let x = Math.floor(tileCoord.x);
          let y = Math.floor(tileCoord.y);
          if (x < 0 || x >= n || y < 0 || y >= n) {
            tileInfo[row * gridSize + col] = null;
            continue;
          }
          x = clamp(x, 0, n - 1);
          y = clamp(y, 0, n - 1);
          const px = Math.floor((tileCoord.x - x) * this.tileSize);
          const py = Math.floor((tileCoord.y - y) * this.tileSize);
          const key = `${z}/${x}/${y}`;
          tileInfo[row * gridSize + col] = { key, px, py };
          if (!tileTasks.has(key)) {
            tileTasks.set(key, this._getTile(z, x, y));
          }
        }
      }
      await Promise.all(tileTasks.values());
      const grid = new Float32Array(gridSize * gridSize);
      for (let idx = 0; idx < tileInfo.length; idx += 1) {
        const info = tileInfo[idx];
        if (!info) {
          grid[idx] = 0;
          continue;
        }
        const tile = this.cache.get(info.key);
        if (!tile) {
          grid[idx] = 0;
          continue;
        }
        const px = clamp(info.px, 0, this.tileSize - 1);
        const py = clamp(info.py, 0, this.tileSize - 1);
        grid[idx] = tile[py * this.tileSize + px];
      }
      return grid;
    }
  }

  MapApp.prototype.initNoiseLayer = function () {
    const popoutMode = isNoisePopout();
    this.noisePopoutMode = popoutMode;
    if (popoutMode && typeof document !== "undefined") {
      document.body.classList.add("panel-popout", "panel-popout-noise");
    }
    this.noisePanel = document.getElementById("noise-panel");
    this.noiseLayerButton = document.querySelector('[data-action="layer-noise"]');
    this.noiseMapContainer = document.getElementById("noise-map");
    this.noiseCanvas = document.getElementById("noise-canvas");
    this.noiseMinDbInput = document.getElementById("noise-min-db");
    this.noiseMinDbValue = document.getElementById("noise-min-db-value");
    this.noiseLegendMin = document.getElementById("noise-legend-min");
    this.noiseLegendMax = document.getElementById("noise-legend-max");
    this.noiseMeta = document.getElementById("noise-meta");
    this.noiseCloseButton = document.getElementById("noise-close");
    this.noiseExpandButton = document.getElementById("noise-expand");
    this.noiseModeButtons = {
      realtime: document.querySelector('[data-action="noise-mode-realtime"]'),
      average: document.querySelector('[data-action="noise-mode-average"]'),
    };
    this.noiseEnabled = false;
    this.noiseExpanded = popoutMode;
    this.noiseMode = "realtime";
    // JY - Noise average: state for cumulative average from sim start (even if layer is off).
    this.noiseAverageGridSize = null;
    this.noiseAverageResetPending = false;
    this.noiseAverageElapsed_s = 0;
    this.noiseAverageLastSimTime_s = null;
    this.noiseAverageLastMs = null;
    this.noiseAverageBoundsLocked = false;
    this.noiseAverageGround = null;
    this.noiseAverageGroundGridSize = null;
    this.noiseAverageLastUpdateMs = 0;
    this.noiseAverageUpdateTimer = null;
    this.noiseAverageMinDb = NOISE_MIN_DB_DEFAULT;
    this.noiseMinDb = NOISE_MIN_DB_DEFAULT;
    this.noiseMaxDb = NOISE_MAX_DB;
    this.noiseLastUpdateMs = 0;
    this.noiseUpdateTimer = null;
    this.noiseInFlight = false;
    this.noisePending = false;
    this.noiseRequestId = 0;
    this.noisePositions = [];
    this.noiseDemAvailable = false;
    this.noiseMiniMap = null;
    this.noiseMiniMapReady = false;
    this.noiseMiniMapZoomOffset = NOISE_MINIMAP_ZOOM_OFFSET;
    this.noiseMiniMapInteractive = false;
    this.noiseMiniMapHandlersBound = false;
    // JY - Noise hover: state for showing per-cell dB under cursor in expanded/popup view.
    this.noiseHoverPopup = null;
    this.noiseHoverField = null;
    this.noiseHoverRequest = null;
    this.noiseHoverHandlersBound = false;
    this.noiseHoverLngLat = null;
    this.noiseHoverMapRef = null;
    this.noiseHoverMoveHandler = null;
    this.noiseHoverLeaveHandler = null;
    this.noiseHoverLeaveTarget = null;
    this.noiseWorker = null;
    this.noiseBufferCanvas = null;
    this.noiseBufferCtx = null;
    this.noiseRenderMode = "realtime";
    this.noiseCanvasCtx = this.noiseCanvas ? this.noiseCanvas.getContext("2d") : null;
    this.noiseHeatmapMoveDepth = 0;
    this.noiseHeatmapRevealPending = false;
    this.noiseAverageChannel = null;
    this.noiseAverageChannelId = null;
    this.noiseAverageExportId = 0;
    this.noiseAverageExportPending = null;
    this.noiseAverageImportPending = false;

    if (this.config && this.config.dem) {
      this.noiseDemSampler = new NoiseDemSampler(
        this.config.dem.tileUrl,
        this.config.dem.tileSize,
        this.config.dem.maxZoom,
      );
    } else {
      this.noiseDemSampler = null;
    }

    if (typeof Worker === "function") {
      this.noiseWorker = new Worker("noise.worker.js");
      this.noiseWorker.onmessage = (event) => this.handleNoiseWorkerResult(event.data);
    }

    if (!popoutMode && this.map) {
      this.attachNoiseCanvasToMap();
    }

    this.initNoiseAverageSync(popoutMode);

    if (this.noiseMinDbInput) {
      this.noiseMinDbInput.value = String(this.noiseMinDb);
      this.updateNoiseMinDbLabel(this.noiseMinDb);
      this.noiseMinDbInput.addEventListener("input", (event) => {
        const next = Number(event.target.value);
        if (Number.isFinite(next)) {
          this.noiseMinDb = next;
          this.updateNoiseMinDbLabel(next);
          if (this.noiseMode !== "average" && this.noiseEnabled) {
            this.scheduleNoiseUpdate(true);
          }
        }
      });
    }

    if (this.noiseModeButtons.average) {
      this.noiseModeButtons.average.addEventListener("click", () => {
        const next = this.noiseMode === "average" ? "realtime" : "average";
        this.setNoiseMode(next);
      });
    }
    this.updateNoiseModeButtons();
    this.updateNoiseMinDbLock();

    if (this.noiseLayerButton) {
      this.noiseLayerButton.addEventListener("click", () => {
        this.setNoiseEnabled(!this.noiseEnabled);
        if (this.setBaseListOpen) {
          this.setBaseListOpen(false);
        }
      });
    }
    if (this.noiseCloseButton) {
      this.noiseCloseButton.addEventListener("click", () => {
        this.setNoiseEnabled(false);
      });
    }
    if (this.noiseExpandButton) {
      if (popoutMode) {
        this.noiseExpandButton.style.display = "none";
      } else {
        this.noiseExpandButton.addEventListener("click", () => {
          openNoisePopout();
        });
      }
    }

    if (this.map) {
      this.setupNoiseMapHandlers();
    }
    this.syncNoiseCanvasSize();
    this.updateNoiseMeta();
    this.updateNoiseExpandButton();
    if (popoutMode) {
      this.setNoiseEnabled(true);
      if (this.dismissStartScreen) {
        this.dismissStartScreen();
      }
    }
  };

  MapApp.prototype.updateNoiseMinDbLabel = function (value) {
    if (!this.noiseMinDbValue) {
      return;
    }
    const display = Number.isFinite(value) ? Math.round(value) : NOISE_MIN_DB_DEFAULT;
    this.noiseMinDbValue.textContent = `${display} dB`;
    if (this.noiseLegendMin) {
      this.noiseLegendMin.textContent = `${display} dB`;
    }
    if (this.noiseLegendMax) {
      this.noiseLegendMax.textContent = `${Math.round(this.noiseMaxDb)} dB`;
    }
  };

  MapApp.prototype.updateNoiseModeButtons = function () {
    const isAverage = this.noiseMode === "average";
    if (this.noiseModeButtons && this.noiseModeButtons.realtime) {
      this.noiseModeButtons.realtime.classList.toggle("is-active", !isAverage);
      this.noiseModeButtons.realtime.setAttribute("aria-pressed", String(!isAverage));
    }
    if (this.noiseModeButtons && this.noiseModeButtons.average) {
      this.noiseModeButtons.average.classList.toggle("is-active", isAverage);
      this.noiseModeButtons.average.setAttribute("aria-pressed", String(isAverage));
    }
  };

  MapApp.prototype.updateNoiseMinDbLock = function () {
    if (!this.noiseMinDbInput) {
      return;
    }
    const locked = this.noiseMode === "average";
    // JY - Noise average: lock the slider and show fixed average min dB.
    this.noiseMinDbInput.disabled = locked;
    this.noiseMinDbInput.setAttribute("aria-disabled", locked ? "true" : "false");
    const value = locked ? this.noiseAverageMinDb : this.noiseMinDb;
    if (Number.isFinite(value)) {
      this.noiseMinDbInput.value = String(value);
      this.updateNoiseMinDbLabel(value);
    }
  };

  MapApp.prototype.setNoiseMiniMapInteractive = function (interactive) {
    const next = Boolean(interactive);
    this.noiseMiniMapInteractive = next;
    if (!this.noiseMiniMap) {
      return;
    }
    const map = this.noiseMiniMap;
    if (next) {
      map.scrollZoom.enable();
      map.dragPan.enable();
      map.doubleClickZoom.enable();
      map.keyboard.enable();
      map.boxZoom.enable();
      map.touchZoomRotate.enable();
      if (map.dragRotate) {
        map.dragRotate.disable();
      }
      if (map.touchZoomRotate && map.touchZoomRotate.disableRotation) {
        map.touchZoomRotate.disableRotation();
      }
      map.getCanvas().style.cursor = "grab";
      return;
    }
    map.scrollZoom.disable();
    map.dragPan.disable();
    map.doubleClickZoom.disable();
    map.keyboard.disable();
    map.boxZoom.disable();
    map.touchZoomRotate.disable();
    if (map.dragRotate) {
      map.dragRotate.disable();
    }
    map.getCanvas().style.cursor = "";
  };

  MapApp.prototype.attachNoiseCanvasToMap = function () {
    if (this.noisePopoutMode || !this.noiseCanvas || !this.map) {
      return;
    }
    const container =
      typeof this.map.getCanvasContainer === "function"
        ? this.map.getCanvasContainer()
        : typeof this.map.getContainer === "function"
          ? this.map.getContainer()
          : null;
    if (!container) {
      return;
    }
    if (this.noiseCanvas.parentElement !== container) {
      container.appendChild(this.noiseCanvas);
    }
  };

  MapApp.prototype.setNoiseHeatmapFading = function (fading) {
    if (!this.noiseCanvas) {
      return;
    }
    this.noiseCanvas.classList.toggle("is-fading", Boolean(fading));
  };

  MapApp.prototype.startNoiseHeatmapMove = function () {
    if (!this.noiseEnabled) {
      return;
    }
    this.noiseHeatmapMoveDepth += 1;
    this.setNoiseHeatmapFading(true);
  };

  MapApp.prototype.endNoiseHeatmapMove = function () {
    if (!this.noiseEnabled) {
      return;
    }
    this.noiseHeatmapMoveDepth = Math.max(0, this.noiseHeatmapMoveDepth - 1);
    if (this.noiseHeatmapMoveDepth > 0) {
      return;
    }
    if (this.noiseHeatmapRevealPending) {
      this.noiseHeatmapRevealPending = false;
      this.setNoiseHeatmapFading(false);
    }
  };

  MapApp.prototype.markNoiseHeatmapDrawn = function () {
    if (!this.noiseEnabled) {
      return;
    }
    if (this.noiseHeatmapMoveDepth > 0) {
      this.noiseHeatmapRevealPending = true;
      return;
    }
    this.noiseHeatmapRevealPending = false;
    this.setNoiseHeatmapFading(false);
  };

  MapApp.prototype.resetNoiseHeatmapFade = function () {
    this.noiseHeatmapMoveDepth = 0;
    this.noiseHeatmapRevealPending = false;
    this.setNoiseHeatmapFading(false);
  };

  MapApp.prototype.bindNoiseMiniMapHandlers = function () {
    if (!this.noiseMiniMap || this.noiseMiniMapHandlersBound) {
      return;
    }
    this.noiseMiniMapHandlersBound = true;
    const handler = () => {
      if (this.noiseEnabled) {
        this.scheduleNoiseUpdate(true);
      }
    };
    const handleMoveStart = () => {
      this.startNoiseHeatmapMove();
    };
    const handleMoveEnd = () => {
      this.endNoiseHeatmapMove();
    };
    this.noiseMiniMap.on("movestart", handleMoveStart);
    this.noiseMiniMap.on("moveend", handleMoveEnd);
    this.noiseMiniMap.on("zoomend", handleMoveEnd);
    this.noiseMiniMap.on("moveend", handler);
    this.noiseMiniMap.on("zoomend", handler);
  };

  MapApp.prototype.shouldShowNoiseHover = function () {
    return this.noiseEnabled;
  };

  MapApp.prototype.getNoiseHoverContainer = function () {
    if (this.noiseCanvas && this.noiseCanvas.parentElement) {
      return this.noiseCanvas.parentElement;
    }
    if (this.noiseMiniMap && this.noiseMapContainer && this.noiseMapContainer.parentElement) {
      return this.noiseMapContainer.parentElement;
    }
    if (this.map && typeof this.map.getContainer === "function") {
      return this.map.getContainer();
    }
    return null;
  };

  MapApp.prototype.ensureNoiseHoverPopup = function () {
    if (this.noiseHoverPopup) {
      return;
    }
    const container = this.getNoiseHoverContainer();
    if (!container) {
      return;
    }
    // JY - Noise hover: HTML overlay so the tooltip stays above the heatmap canvas.
    const popup = document.createElement("div");
    popup.className = "noise-hover-popup";
    popup.setAttribute("aria-hidden", "true");
    popup.style.display = "none";
    container.appendChild(popup);
    this.noiseHoverPopup = popup;
  };

  MapApp.prototype.hideNoiseHover = function (clearState) {
    if (this.noiseHoverPopup) {
      this.noiseHoverPopup.style.display = "none";
      this.noiseHoverPopup.setAttribute("aria-hidden", "true");
    }
    if (clearState) {
      this.noiseHoverLngLat = null;
    }
  };

  MapApp.prototype.formatNoiseHoverLabel = function (value) {
    if (Number.isFinite(value)) {
      return `${Math.round(value)} dB`;
    }
    const field = this.noiseHoverField;
    if (field && Number.isFinite(field.minDb)) {
      return `< ${Math.round(field.minDb)} dB`;
    }
    return "";
  };

  MapApp.prototype.sampleNoiseLevelAtLngLat = function (lngLat) {
    const field = this.noiseHoverField;
    if (!field || !field.levels || !field.bounds || !Number.isFinite(field.gridSize)) {
      return null;
    }
    const lng = Array.isArray(lngLat) ? Number(lngLat[0]) : Number(lngLat && lngLat.lng);
    const lat = Array.isArray(lngLat) ? Number(lngLat[1]) : Number(lngLat && lngLat.lat);
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
      return null;
    }
    const [westX, southY] = toMercator(field.bounds.west, field.bounds.south);
    const [eastX, northY] = toMercator(field.bounds.east, field.bounds.north);
    const width = eastX - westX;
    const height = northY - southY;
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      return null;
    }
    const [x, y] = toMercator(lng, lat);
    const u = (x - westX) / width;
    const v = (northY - y) / height;
    if (u < 0 || u > 1 || v < 0 || v > 1) {
      return null;
    }
    const col = clamp(Math.floor(u * field.gridSize), 0, field.gridSize - 1);
    const row = clamp(Math.floor(v * field.gridSize), 0, field.gridSize - 1);
    const value = field.levels[row * field.gridSize + col];
    return Number.isFinite(value) ? value : null;
  };

  MapApp.prototype.updateNoiseHover = function (lngLat) {
    const mapRef = this.noiseMiniMap || this.map;
    if (!mapRef || !this.shouldShowNoiseHover()) {
      this.hideNoiseHover();
      return;
    }
    const lng = Array.isArray(lngLat) ? Number(lngLat[0]) : Number(lngLat && lngLat.lng);
    const lat = Array.isArray(lngLat) ? Number(lngLat[1]) : Number(lngLat && lngLat.lat);
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
      this.hideNoiseHover();
      return;
    }
    // JY - Noise hover: remember cursor position to refresh values on each update.
    this.noiseHoverLngLat = { lng, lat };
    if (!this.noiseHoverField || this.noiseHoverField.mode !== this.noiseRenderMode) {
      this.hideNoiseHover();
      return;
    }
    const value = this.sampleNoiseLevelAtLngLat({ lng, lat });
    const label = this.formatNoiseHoverLabel(value);
    if (!label) {
      this.hideNoiseHover();
      return;
    }
    this.ensureNoiseHoverPopup();
    if (!this.noiseHoverPopup) {
      return;
    }
    const point = mapRef.project([lng, lat]);
    this.noiseHoverPopup.textContent = label;
    this.noiseHoverPopup.style.left = `${point.x}px`;
    this.noiseHoverPopup.style.top = `${point.y}px`;
    this.noiseHoverPopup.style.display = "block";
    this.noiseHoverPopup.setAttribute("aria-hidden", "false");
  };

  MapApp.prototype.bindNoiseHoverHandlers = function () {
    const mapRef = this.noiseMiniMap || this.map;
    if (!mapRef || this.noiseHoverHandlersBound) {
      return;
    }
    this.noiseHoverHandlersBound = true;
    this.noiseHoverMapRef = mapRef;
    // JY - Noise hover: update tooltip position/value on mouse move.
    this.noiseHoverMoveHandler = (event) => {
      if (!event || !event.lngLat) {
        return;
      }
      this.updateNoiseHover(event.lngLat);
    };
    mapRef.on("mousemove", this.noiseHoverMoveHandler);
    const container = mapRef.getContainer ? mapRef.getContainer() : null;
    if (container) {
      this.noiseHoverLeaveTarget = container;
      this.noiseHoverLeaveHandler = () => {
        this.hideNoiseHover(true);
      };
      container.addEventListener("mouseleave", this.noiseHoverLeaveHandler);
    }
  };

  MapApp.prototype.unbindNoiseHoverHandlers = function () {
    if (!this.noiseHoverMapRef) {
      this.noiseHoverHandlersBound = false;
      return;
    }
    if (this.noiseHoverMoveHandler && this.noiseHoverMapRef.off) {
      this.noiseHoverMapRef.off("mousemove", this.noiseHoverMoveHandler);
    }
    if (this.noiseHoverLeaveTarget && this.noiseHoverLeaveHandler) {
      this.noiseHoverLeaveTarget.removeEventListener(
        "mouseleave",
        this.noiseHoverLeaveHandler,
      );
    }
    this.noiseHoverMapRef = null;
    this.noiseHoverMoveHandler = null;
    this.noiseHoverLeaveHandler = null;
    this.noiseHoverLeaveTarget = null;
    this.noiseHoverHandlersBound = false;
  };

  MapApp.prototype.resolveNoiseAverageSourceRect = function (viewBounds, gridSize) {
    if (!viewBounds || !Number.isFinite(gridSize) || gridSize <= 1) {
      return null;
    }
    const avgBounds = NOISE_SEOUL_BOUNDS;
    const [westX] = toMercator(avgBounds.west, 0);
    const [eastX] = toMercator(avgBounds.east, 0);
    const [, southY] = toMercator(0, avgBounds.south);
    const [, northY] = toMercator(0, avgBounds.north);
    const width = eastX - westX;
    const height = northY - southY;
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      return null;
    }
    const west = viewBounds.getWest ? viewBounds.getWest() : viewBounds.west;
    const east = viewBounds.getEast ? viewBounds.getEast() : viewBounds.east;
    const south = viewBounds.getSouth ? viewBounds.getSouth() : viewBounds.south;
    const north = viewBounds.getNorth ? viewBounds.getNorth() : viewBounds.north;
    if (
      !Number.isFinite(west) ||
      !Number.isFinite(east) ||
      !Number.isFinite(south) ||
      !Number.isFinite(north)
    ) {
      return null;
    }
    const [viewWestX] = toMercator(west, 0);
    const [viewEastX] = toMercator(east, 0);
    const [, viewSouthY] = toMercator(0, south);
    const [, viewNorthY] = toMercator(0, north);
    const left = clamp((viewWestX - westX) / width, 0, 1);
    const right = clamp((viewEastX - westX) / width, 0, 1);
    const top = clamp((northY - viewNorthY) / height, 0, 1);
    const bottom = clamp((northY - viewSouthY) / height, 0, 1);
    if (right <= left || bottom <= top) {
      return null;
    }
    let sx = Math.floor(left * gridSize);
    let sy = Math.floor(top * gridSize);
    let sw = Math.ceil((right - left) * gridSize);
    let sh = Math.ceil((bottom - top) * gridSize);
    if (sx < 0) {
      sw += sx;
      sx = 0;
    }
    if (sy < 0) {
      sh += sy;
      sy = 0;
    }
    sw = Math.min(sw, gridSize - sx);
    sh = Math.min(sh, gridSize - sy);
    if (sw <= 0 || sh <= 0) {
      return null;
    }
    return { sx, sy, sw, sh };
  };

  MapApp.prototype.resetNoiseAverage = function () {
    this.noiseAverageGridSize = null;
    this.noiseAverageElapsed_s = 0;
    this.noiseAverageLastSimTime_s = null;
    this.noiseAverageLastMs = null;
    this.noiseAverageBoundsLocked = false;
    this.noiseAverageGround = null;
    this.noiseAverageGroundGridSize = null;
    this.noiseAverageResetPending = true;
  };

  MapApp.prototype.setNoiseMode = function (mode) {
    const next = mode === "average" ? "average" : "realtime";
    if (this.noiseMode === next) {
      return;
    }
    this.noiseMode = next;
    this.updateNoiseModeButtons();
    this.updateNoiseMinDbLock();
    this.noiseAverageBoundsLocked = false;
    this.hideNoiseHover();
    if (this.noiseMiniMap && typeof this.noiseMiniMap.setMaxBounds === "function") {
      if (next === "average") {
        this.noiseMiniMap.setMaxBounds([
          [NOISE_SEOUL_BOUNDS.west, NOISE_SEOUL_BOUNDS.south],
          [NOISE_SEOUL_BOUNDS.east, NOISE_SEOUL_BOUNDS.north],
        ]);
      } else {
        this.noiseMiniMap.setMaxBounds(null);
      }
    }
    if (this.noiseEnabled) {
      this.scheduleNoiseUpdate(true);
    }
  };

  MapApp.prototype.resolveNoiseAverageGridSize = function () {
    if (Number.isFinite(this.noiseAverageGridSize) && this.noiseAverageGridSize > 0) {
      return this.noiseAverageGridSize;
    }
    const expanded = Boolean(this.noiseExpanded);
    const base = expanded ? NOISE_GRID_EXPANDED_MED : NOISE_GRID_MED;
    const min = expanded ? NOISE_GRID_EXPANDED_MIN : NOISE_GRID_MIN;
    const max = expanded ? NOISE_GRID_EXPANDED_MAX : NOISE_GRID_MAX;
    const resolved = clamp(base, min, max);
    this.noiseAverageGridSize = resolved;
    return resolved;
  };

  MapApp.prototype.updateNoiseMeta = function () {
    if (!this.noiseMeta) {
      return;
    }
    let demLabel = "DEM: OFF";
    if (this.noiseDemSampler) {
      if (this.noiseDemAvailable) {
        demLabel = "DEM: ON";
      } else if (this.noiseDemSampler.disabled) {
        demLabel = "DEM: MISSING";
      } else {
        demLabel = "DEM: LOADING";
      }
    }
    this.noiseMeta.textContent = this.translateLiteral(demLabel);
  };

  MapApp.prototype.updateNoiseExpandButton = function () {
    if (!this.noiseExpandButton) {
      return;
    }
    const label = this.translateLiteral("Open noise in external tab");
    this.noiseExpandButton.setAttribute("aria-pressed", "false");
    this.noiseExpandButton.setAttribute("aria-label", label);
    this.noiseExpandButton.setAttribute("title", label);
  };

  MapApp.prototype.initNoiseAverageSync = function (popoutMode) {
    if (typeof BroadcastChannel !== "function") {
      return;
    }
    this.noiseAverageChannel = new BroadcastChannel(NOISE_AVERAGE_CHANNEL);
    this.noiseAverageChannelId = `noise-${Math.random().toString(36).slice(2)}`;
    this.noiseAverageChannel.onmessage = (event) => {
      const message = event && event.data ? event.data : null;
      if (!message || message.sourceId === this.noiseAverageChannelId) {
        return;
      }
      if (message.type === "noise-average-request") {
        this.sendNoiseAverageState();
        return;
      }
      if (message.type === "noise-average-response" && isNoisePopout()) {
        this.importNoiseAverageState(message.payload);
      }
    };
    if (popoutMode) {
      this.noiseAverageImportPending = true;
      this.requestNoiseAverageState();
    }
  };

  MapApp.prototype.requestNoiseAverageState = function () {
    if (!this.noiseAverageChannel) {
      return;
    }
    this.noiseAverageChannel.postMessage({
      type: "noise-average-request",
      sourceId: this.noiseAverageChannelId,
    });
  };

  MapApp.prototype.sendNoiseAverageState = function () {
    if (!this.noiseAverageChannel) {
      return;
    }
    this.requestNoiseAverageExport().then((state) => {
      if (!state) {
        return;
      }
      this.noiseAverageChannel.postMessage({
        type: "noise-average-response",
        sourceId: this.noiseAverageChannelId,
        payload: state,
      });
    });
  };

  MapApp.prototype.requestNoiseAverageExport = function () {
    if (!this.noiseWorker) {
      return Promise.resolve(null);
    }
    if (this.noiseAverageExportPending) {
      return this.noiseAverageExportPending.promise;
    }
    const id = (this.noiseAverageExportId += 1);
    let resolve = null;
    const promise = new Promise((next) => {
      resolve = next;
    });
    this.noiseAverageExportPending = { id, resolve, promise };
    this.noiseWorker.postMessage({ type: "exportAverage", id });
    return promise;
  };

  MapApp.prototype.importNoiseAverageState = function (payload) {
    if (!payload || !this.noiseWorker) {
      return;
    }
    const gridSize = Number(payload.gridSize);
    const sumTime = Number(payload.sumTime);
    const lastSimTime = Number(payload.lastSimTime_s);
    let sumEnergy = payload.sumEnergy;
    let energyArray = null;
    if (sumEnergy instanceof Float64Array) {
      energyArray = sumEnergy;
    } else if (sumEnergy instanceof ArrayBuffer) {
      energyArray = new Float64Array(sumEnergy);
    } else if (Array.isArray(sumEnergy)) {
      energyArray = new Float64Array(sumEnergy);
    }
    if (!energyArray || !Number.isFinite(gridSize) || gridSize <= 0) {
      return;
    }
    if (energyArray.length !== gridSize * gridSize) {
      return;
    }
    this.noiseAverageGridSize = gridSize;
    this.noiseAverageElapsed_s = Number.isFinite(sumTime) && sumTime >= 0 ? sumTime : 0;
    if (Number.isFinite(lastSimTime)) {
      this.noiseAverageLastSimTime_s = lastSimTime;
      this.noiseAverageLastMs = null;
    } else {
      this.noiseAverageLastSimTime_s = null;
      this.noiseAverageLastMs = performance.now();
    }
    this.noiseAverageResetPending = false;
    this.noiseAverageGround = null;
    this.noiseAverageGroundGridSize = null;
    this.noiseAverageImportPending = false;
    this.noiseWorker.postMessage(
      {
        type: "importAverage",
        gridSize,
        sumTime: Number.isFinite(sumTime) && sumTime >= 0 ? sumTime : 0,
        sumEnergy: energyArray,
      },
      [energyArray.buffer],
    );
    if (this.noiseEnabled) {
      this.scheduleNoiseUpdate(true);
    }
  };

  MapApp.prototype.setupNoiseMapHandlers = function () {
    if (!this.map || this.noiseMapHandlersBound) {
      return;
    }
    this.noiseMapHandlersBound = true;
    if (!NOISE_MINIMAP_LOCKED) {
      const handler = () => {
        this.endNoiseHeatmapMove();
        this.syncNoiseMiniMapView();
        this.scheduleNoiseUpdate();
      };
      const handleMoveStart = () => {
        this.startNoiseHeatmapMove();
      };
      this.map.on("movestart", handleMoveStart);
      this.map.on("zoomstart", handleMoveStart);
      this.map.on("rotatestart", handleMoveStart);
      this.map.on("pitchstart", handleMoveStart);
      this.map.on("moveend", handler);
      this.map.on("zoomend", handler);
      this.map.on("rotateend", handler);
      this.map.on("pitchend", handler);
    }
    this.map.on("resize", () => {
      this.syncNoiseCanvasSize();
      this.syncNoiseMiniMapView(true);
      this.scheduleNoiseUpdate(true);
    });
  };

  MapApp.prototype.resolveNoiseMiniMapZoom = function () {
    if (NOISE_MINIMAP_LOCKED && this.noiseMiniMap) {
      return this.noiseMiniMap.getZoom();
    }
    const baseZoom = this.map ? this.map.getZoom() : this.config.startZoom || 10;
    const minZoom = Math.max(this.config.minZoom || 0, NOISE_MINIMAP_MIN_ZOOM);
    const maxZoom = this.config.maxZoom || baseZoom;
    const target = baseZoom + this.noiseMiniMapZoomOffset;
    return clamp(target, minZoom, maxZoom);
  };

  MapApp.prototype.buildNoiseMapStyle = function (theme) {
    if (!this.buildStyle) {
      return null;
    }
    const style = this.buildStyle();
    const useReal = theme === "real";
    const baseLayerIds =
      typeof BASE_MAP_LAYER_IDS !== "undefined"
        ? BASE_MAP_LAYER_IDS
        : Object.keys(NOISE_LAYER_PAINT);
    const realLayerId =
      typeof REAL_MAP_LAYER_ID !== "undefined" ? REAL_MAP_LAYER_ID : "real-raster";
    const palettes =
      typeof BASE_MAP_PALETTES !== "undefined" ? BASE_MAP_PALETTES : NOISE_FALLBACK_PALETTES;
    const palette = palettes[theme] || palettes.light || NOISE_FALLBACK_PALETTES.light;

    style.layers = style.layers.map((layer) => {
      const next = {
        ...layer,
        layout: layer.layout ? { ...layer.layout } : undefined,
        paint: layer.paint ? { ...layer.paint } : undefined,
      };
      if (layer.id === realLayerId) {
        next.layout = { ...(next.layout || {}), visibility: useReal ? "visible" : "none" };
        return next;
      }
      if (baseLayerIds.includes(layer.id)) {
        next.layout = { ...(next.layout || {}), visibility: useReal ? "none" : "visible" };
        if (!useReal) {
          const prop = NOISE_LAYER_PAINT[layer.id];
          const color = palette[layer.id];
          if (prop && color) {
            next.paint = { ...(next.paint || {}), [prop]: color };
          }
        }
      }
      return next;
    });
    return style;
  };

  MapApp.prototype.ensureNoiseMiniMap = function () {
    if (!this.noisePopoutMode) {
      return;
    }
    if (!this.map || !this.noiseMapContainer || this.noiseMiniMap || !window.maplibregl) {
      return;
    }
    const style = this.buildNoiseMapStyle(this.currentTheme || "light");
    if (!style) {
      return;
    }
    const baseCenter = NOISE_MINIMAP_LOCKED
      ? [(NOISE_SEOUL_BOUNDS.west + NOISE_SEOUL_BOUNDS.east) / 2,
        (NOISE_SEOUL_BOUNDS.south + NOISE_SEOUL_BOUNDS.north) / 2]
      : [this.map.getCenter().lng, this.map.getCenter().lat];
    const zoom = this.resolveNoiseMiniMapZoom();
    this.noiseMiniMap = new maplibregl.Map({
      container: this.noiseMapContainer,
      style,
      center: baseCenter,
      zoom,
      bearing: NOISE_MINIMAP_LOCKED ? 0 : this.map.getBearing(),
      pitch: 0,
      interactive: true,
      renderWorldCopies: false,
      attributionControl: false,
      fadeDuration: 0,
    });
    this.bindNoiseMiniMapHandlers();
    this.bindNoiseHoverHandlers();
    this.setNoiseMiniMapInteractive(this.noiseExpanded || isNoisePopout());
    this.noiseMiniMapReady = false;
    this.noiseMiniMap.once("load", () => {
      this.noiseMiniMapReady = true;
      this.noiseMiniMap.resize();
      if (NOISE_MINIMAP_LOCKED) {
        const bounds = [
          [NOISE_SEOUL_BOUNDS.west, NOISE_SEOUL_BOUNDS.south],
          [NOISE_SEOUL_BOUNDS.east, NOISE_SEOUL_BOUNDS.north],
        ];
        this.noiseMiniMap.fitBounds(bounds, { padding: 12, duration: 0 });
      } else {
        this.syncNoiseMiniMapView(true);
      }
    });
  };

  MapApp.prototype.destroyNoiseMiniMap = function () {
    if (!this.noiseMiniMap) {
      this.unbindNoiseHoverHandlers();
      return;
    }
    this.noiseMiniMap.remove();
    this.noiseMiniMap = null;
    this.noiseMiniMapReady = false;
    this.unbindNoiseHoverHandlers();
    if (this.noiseHoverPopup) {
      this.noiseHoverPopup.remove();
    }
    this.noiseHoverPopup = null;
    this.noiseHoverField = null;
    this.noiseHoverRequest = null;
    this.noiseHoverLngLat = null;
  };

  MapApp.prototype.syncNoiseMiniMapView = function (force) {
    if (!this.noiseMiniMap || !this.map || !this.noiseMiniMapReady) {
      return;
    }
    if (this.noiseMiniMapInteractive) {
      return;
    }
    if (this.noiseMode === "average") {
      if (this.noiseAverageBoundsLocked && !force) {
        return;
      }
      const bounds = [
        [NOISE_SEOUL_BOUNDS.west, NOISE_SEOUL_BOUNDS.south],
        [NOISE_SEOUL_BOUNDS.east, NOISE_SEOUL_BOUNDS.north],
      ];
      this.noiseMiniMap.fitBounds(bounds, { padding: 12, duration: 0 });
      this.noiseAverageBoundsLocked = true;
      return;
    }
    this.noiseAverageBoundsLocked = false;
    if (NOISE_MINIMAP_LOCKED) {
      if (force) {
        const bounds = [
          [NOISE_SEOUL_BOUNDS.west, NOISE_SEOUL_BOUNDS.south],
          [NOISE_SEOUL_BOUNDS.east, NOISE_SEOUL_BOUNDS.north],
        ];
        this.noiseMiniMap.fitBounds(bounds, { padding: 12, duration: 0 });
      }
      return;
    }
    const center = this.map.getCenter();
    const zoom = this.resolveNoiseMiniMapZoom();
    const bearing = this.map.getBearing();
    const current = this.noiseMiniMap.getCenter();
    const needsUpdate =
      force ||
      Math.abs(current.lng - center.lng) > 1e-5 ||
      Math.abs(current.lat - center.lat) > 1e-5 ||
      Math.abs(this.noiseMiniMap.getZoom() - zoom) > 1e-3 ||
      Math.abs(this.noiseMiniMap.getBearing() - bearing) > 0.1;
    if (!needsUpdate) {
      return;
    }
    this.noiseMiniMap.jumpTo({
      center: [center.lng, center.lat],
      zoom,
      bearing,
      pitch: 0,
    });
  };

  MapApp.prototype.updateNoiseMiniMapTheme = function (theme) {
    if (!this.noiseMiniMap) {
      return;
    }
    const style = this.buildNoiseMapStyle(theme);
    if (!style) {
      return;
    }
    const center = this.noiseMiniMap.getCenter();
    const zoom = this.noiseMiniMap.getZoom();
    const bearing = this.noiseMiniMap.getBearing();
    this.noiseMiniMapReady = false;
    this.noiseMiniMap.setStyle(style);
    this.noiseMiniMap.once("load", () => {
      this.noiseMiniMapReady = true;
      if (NOISE_MINIMAP_LOCKED) {
        const bounds = [
          [NOISE_SEOUL_BOUNDS.west, NOISE_SEOUL_BOUNDS.south],
          [NOISE_SEOUL_BOUNDS.east, NOISE_SEOUL_BOUNDS.north],
        ];
        this.noiseMiniMap.fitBounds(bounds, { padding: 12, duration: 0 });
      } else {
        this.noiseMiniMap.jumpTo({
          center: [center.lng, center.lat],
          zoom,
          bearing,
          pitch: 0,
        });
      }
    });
  };

  MapApp.prototype.syncNoiseCanvasSize = function () {
    if (!this.noiseCanvas || !this.noiseCanvasCtx) {
      return;
    }
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(this.noiseCanvas.clientWidth * ratio));
    const height = Math.max(1, Math.round(this.noiseCanvas.clientHeight * ratio));
    if (this.noiseCanvas.width !== width || this.noiseCanvas.height !== height) {
      this.noiseCanvas.width = width;
      this.noiseCanvas.height = height;
    }
    this.noiseCanvasCtx.clearRect(0, 0, width, height);
    if (this.noiseMiniMap) {
      this.noiseMiniMap.resize();
    }
  };

  MapApp.prototype.setNoiseExpanded = function (expanded) {
    const next = Boolean(expanded);
    this.noiseExpanded = next;
    if (this.noisePanel) {
      this.noisePanel.classList.toggle("is-expanded", next);
    }
    this.updateNoiseExpandButton();
    this.setNoiseMiniMapInteractive(next || isNoisePopout());
    if (!next) {
      this.hideNoiseHover(true);
    }
    if (!this.noiseEnabled) {
      return;
    }
    window.requestAnimationFrame(() => {
      this.syncNoiseCanvasSize();
      this.scheduleNoiseUpdate(true);
    });
  };

  MapApp.prototype.setNoiseEnabled = function (enabled) {
    const next = Boolean(enabled);
    if (next && typeof this.disableOtherBaseLayers === "function") {
      this.disableOtherBaseLayers("noise");
    }
    this.noiseEnabled = next;
    if (typeof this.syncOverlayPitchLock === "function") {
      this.syncOverlayPitchLock();
    }
    if (this.noiseAverageUpdateTimer) {
      window.clearTimeout(this.noiseAverageUpdateTimer);
      this.noiseAverageUpdateTimer = null;
    }
    if (typeof document !== "undefined") {
      document.body.classList.toggle("noise-visible", next);
    }
    if (this.noiseLayerButton) {
      this.noiseLayerButton.classList.toggle("is-active", next);
    }
    if (this.noisePanel) {
      this.noisePanel.classList.toggle("is-visible", next);
      this.noisePanel.setAttribute("aria-hidden", next ? "false" : "true");
    }
    if (!next) {
      this.hideNoiseHover(true);
      this.destroyNoiseMiniMap();
      this.clearNoiseCanvas();
      this.resetNoiseHeatmapFade();
      return;
    }
    this.resetNoiseHeatmapFade();
    this.attachNoiseCanvasToMap();
    this.ensureNoiseMiniMap();
    this.syncNoiseMiniMapView(true);
    this.updateNoiseMeta();
    this.bindNoiseHoverHandlers();
    window.requestAnimationFrame(() => {
      this.syncNoiseCanvasSize();
      this.scheduleNoiseUpdate(true);
    });
  };

  MapApp.prototype.clearNoiseCanvas = function () {
    if (!this.noiseCanvasCtx || !this.noiseCanvas) {
      return;
    }
    this.noiseCanvasCtx.clearRect(0, 0, this.noiseCanvas.width, this.noiseCanvas.height);
  };

  MapApp.prototype.scheduleNoiseUpdate = function (force) {
    if (!this.noiseEnabled || !this.noiseWorker || !this.map) {
      return;
    }
    if (!NOISE_MINIMAP_LOCKED) {
      this.syncNoiseMiniMapView();
    }
    const now = performance.now();
    const elapsed = now - this.noiseLastUpdateMs;
    const interval = Number.isFinite(this.noiseUpdateIntervalMs)
      ? this.noiseUpdateIntervalMs
      : NOISE_UPDATE_INTERVAL_MS;
    const delay = Math.max(0, interval - elapsed);
    if (!force && delay > 0) {
      if (this.noiseUpdateTimer) {
        return;
      }
      this.noiseUpdateTimer = window.setTimeout(() => {
        this.noiseUpdateTimer = null;
        this.refreshNoise();
      }, delay);
      return;
    }
    this.refreshNoise();
  };

  MapApp.prototype.scheduleNoiseAverageUpdate = function (force) {
    if (this.noiseEnabled || !this.noiseWorker) {
      return;
    }
    // JY - Noise average: keep accumulating in background even when layer is off.
    const now = performance.now();
    const elapsed = now - this.noiseAverageLastUpdateMs;
    const interval = Number.isFinite(this.noiseUpdateIntervalMs)
      ? this.noiseUpdateIntervalMs
      : NOISE_UPDATE_INTERVAL_MS;
    const delay = Math.max(0, interval - elapsed);
    if (!force && delay > 0) {
      if (this.noiseAverageUpdateTimer) {
        return;
      }
      this.noiseAverageUpdateTimer = window.setTimeout(() => {
        this.noiseAverageUpdateTimer = null;
        this.refreshNoise({ allowDisabled: true, forceAverage: true });
      }, delay);
      return;
    }
    if (this.noiseAverageUpdateTimer) {
      window.clearTimeout(this.noiseAverageUpdateTimer);
      this.noiseAverageUpdateTimer = null;
    }
    this.refreshNoise({ allowDisabled: true, forceAverage: true });
  };

  MapApp.prototype.resolveNoiseGridSize = function (flightCount) {
    const expanded = Boolean(this.noiseExpanded);
    let size = expanded ? NOISE_GRID_EXPANDED_HIGH : NOISE_GRID_HIGH;
    if (flightCount > 12000) {
      size = expanded ? NOISE_GRID_EXPANDED_LOW : NOISE_GRID_LOW;
    } else if (flightCount > 6000) {
      size = expanded ? NOISE_GRID_EXPANDED_MED : NOISE_GRID_MED;
    }
    const min = expanded ? NOISE_GRID_EXPANDED_MIN : NOISE_GRID_MIN;
    const max = expanded ? NOISE_GRID_EXPANDED_MAX : NOISE_GRID_MAX;
    return clamp(size, min, max);
  };

  MapApp.prototype.resolveNoiseUpdateInterval = function (flightCount) {
    if (flightCount > 12000) {
      return 2600;
    }
    if (flightCount > 6000) {
      return 2000;
    }
    if (flightCount > 2500) {
      return 1600;
    }
    return NOISE_UPDATE_INTERVAL_MS;
  };

  MapApp.prototype.computeNoiseRadius = function (minDbValue) {
    if (!Number.isFinite(NOISE_SLOPE) || NOISE_SLOPE === 0) {
      return 0;
    }
    const radius = NOISE_D0_M * Math.pow(10, (minDbValue - NOISE_L0_DB) / NOISE_SLOPE);
    return Number.isFinite(radius) && radius > 0 ? radius : 0;
  };

  MapApp.prototype.refreshNoise = async function (options = {}) {
    const allowDisabled = Boolean(options.allowDisabled);
    const forceAverage = Boolean(options.forceAverage);
    if ((!this.noiseEnabled && !allowDisabled) || !this.noiseWorker || !this.map) {
      return;
    }
    if (this.noiseInFlight) {
      this.noisePending = true;
      return;
    }
    this.noiseInFlight = true;
    if (this.noiseMiniMap && !this.noiseMiniMapReady) {
      this.noiseInFlight = false;
      return;
    }
    const isAverage = forceAverage || this.noiseMode === "average";
    this.noiseRenderMode = isAverage ? "average" : "realtime";
    const requestId = ++this.noiseRequestId;
    const positions = Array.isArray(this.noisePositions) ? this.noisePositions : [];
    const minDbRealtime = Number.isFinite(this.noiseMinDb) ? this.noiseMinDb : NOISE_MIN_DB_DEFAULT;
    const minDbAverage = Number.isFinite(this.noiseAverageMinDb)
      ? this.noiseAverageMinDb
      : NOISE_MIN_DB_DEFAULT;
    const radiusRealtime = this.computeNoiseRadius(minDbRealtime);
    const radiusAverage = this.computeNoiseRadius(minDbAverage);
    if (
      Number.isFinite(this.lastSimTime_s) &&
      Number.isFinite(this.noiseAverageLastSimTime_s) &&
      this.lastSimTime_s < this.noiseAverageLastSimTime_s
    ) {
      this.resetNoiseAverage();
    }
    // JY - Noise average: use fixed Seoul bounds for cumulative average grid.
    const averageBounds = { ...NOISE_SEOUL_BOUNDS };
    let bounds;
    if (isAverage || NOISE_MINIMAP_LOCKED) {
      bounds = { ...NOISE_SEOUL_BOUNDS };
    } else {
      const mapRef = this.noiseMiniMapReady ? this.noiseMiniMap : this.map;
      const boundsObj = mapRef.getBounds();
      bounds = {
        west: boundsObj.getWest(),
        south: boundsObj.getSouth(),
        east: boundsObj.getEast(),
        north: boundsObj.getNorth(),
      };
    }
    const buildFlights = (targetBounds, radius) => {
      if (!targetBounds || !positions.length) {
        return [];
      }
      const centerLat = (targetBounds.north + targetBounds.south) * 0.5;
      const latScale = 111320;
      const lonScale = 111320 * Math.max(0.2, Math.cos(centerLat * DEG_TO_RAD));
      const marginLat = radius / latScale;
      const marginLon = radius / lonScale;
      const west = targetBounds.west - marginLon;
      const east = targetBounds.east + marginLon;
      const south = targetBounds.south - marginLat;
      const north = targetBounds.north + marginLat;
      const flights = [];
      for (let i = 0; i < positions.length; i += 1) {
        const pos = positions[i];
        if (!pos) {
          continue;
        }
        const lon = Number(pos.lon);
        const lat = Number(pos.lat);
        const alt = Number(pos.altitude_m);
        if (!Number.isFinite(lon) || !Number.isFinite(lat) || !Number.isFinite(alt)) {
          continue;
        }
        if (lon < west || lon > east || lat < south || lat > north) {
          continue;
        }
        flights.push({ lon, lat, alt });
      }
      return flights;
    };
    const flights = buildFlights(bounds, isAverage ? radiusAverage : radiusRealtime);
    const averageFlights = isAverage ? flights : buildFlights(averageBounds, radiusAverage);
    const gridSize = isAverage
      ? this.resolveNoiseAverageGridSize()
      : this.resolveNoiseGridSize(flights.length);
    const averageGridSize = this.resolveNoiseAverageGridSize();
    let ground = null;
    let averageGround = null;
    if (this.noiseDemSampler) {
      if (!this.noiseAverageGround || this.noiseAverageGroundGridSize !== averageGridSize) {
        averageGround = await this.noiseDemSampler.sampleGrid(averageBounds, averageGridSize);
        this.noiseAverageGround = averageGround;
        this.noiseAverageGroundGridSize = averageGridSize;
      } else {
        averageGround = this.noiseAverageGround;
      }
      if (isAverage) {
        ground = averageGround;
      } else {
        ground = await this.noiseDemSampler.sampleGrid(bounds, gridSize);
      }
    }
    const demAvailable =
      Boolean(ground) &&
      Boolean(this.noiseDemSampler && this.noiseDemSampler.hasData && !this.noiseDemSampler.disabled);
    if (demAvailable !== this.noiseDemAvailable) {
      this.noiseDemAvailable = demAvailable;
      this.updateNoiseMeta();
    }
    if ((!this.noiseEnabled && !allowDisabled) || requestId !== this.noiseRequestId) {
      this.noiseInFlight = false;
      return;
    }
    // JY - Noise average: accumulate over sim time when available, else wall clock.
    let averageDt = 0;
    if (Number.isFinite(this.lastSimTime_s)) {
      if (Number.isFinite(this.noiseAverageLastSimTime_s)) {
        averageDt = this.lastSimTime_s - this.noiseAverageLastSimTime_s;
      }
      this.noiseAverageLastSimTime_s = this.lastSimTime_s;
      this.noiseAverageLastMs = null;
    } else {
      const nowMs = performance.now();
      if (Number.isFinite(this.noiseAverageLastMs)) {
        averageDt = (nowMs - this.noiseAverageLastMs) / 1000;
      }
      this.noiseAverageLastMs = nowMs;
      this.noiseAverageLastSimTime_s = null;
    }
    if (!Number.isFinite(averageDt) || averageDt < 0) {
      averageDt = 0;
    }
    if (averageDt > 0) {
      this.noiseAverageElapsed_s += averageDt;
    }
    // JY - Noise hover: request per-cell dB levels for tooltip when expanded/popup.
    const includeLevels = this.shouldShowNoiseHover();
    if (includeLevels) {
      this.noiseHoverRequest = {
        id: requestId,
        bounds: { ...bounds },
        gridSize,
        mode: this.noiseRenderMode,
        minDb: isAverage ? minDbAverage : minDbRealtime,
      };
    } else {
      this.noiseHoverRequest = null;
      this.noiseHoverField = null;
    }
    const payload = {
      type: "compute",
      id: requestId,
      bounds,
      gridSize,
      flights,
      ground,
      averageBounds,
      averageGridSize,
      averageFlights,
      averageGround,
      minDb: minDbRealtime,
      averageMinDb: minDbAverage,
      maxDb: NOISE_MAX_DB,
      l0: NOISE_L0_DB,
      d0: NOISE_D0_M,
      slope: NOISE_SLOPE,
      mode: isAverage ? "average" : "realtime",
      dt: averageDt,
      resetAverage: this.noiseAverageResetPending,
      accumulateAverage: true,
      includeLevels,
    };
    if (this.noiseAverageResetPending) {
      this.noiseAverageResetPending = false;
    }
    const transfer = [];
    if (ground && ground.buffer && ground !== averageGround) {
      transfer.push(ground.buffer);
    }
    this.noiseWorker.postMessage(payload, transfer);
  };

  MapApp.prototype.handleNoiseWorkerResult = function (payload) {
    if (!payload) {
      return;
    }
    if (payload.type === "average") {
      const pending = this.noiseAverageExportPending;
      if (pending && payload.id === pending.id) {
        this.noiseAverageExportPending = null;
        const state =
          payload.sumEnergy && Number.isFinite(payload.gridSize) && Number.isFinite(payload.sumTime)
            ? {
                gridSize: payload.gridSize,
                sumTime: payload.sumTime,
                sumEnergy: payload.sumEnergy,
                lastSimTime_s: this.lastSimTime_s,
              }
            : null;
        pending.resolve(state);
      }
      return;
    }
    if (payload.type !== "result") {
      return;
    }
    if (payload.id !== this.noiseRequestId) {
      this.noiseInFlight = false;
      return;
    }
    // JY - Noise hover: cache dB grid from worker to sample under the cursor.
    if (payload.levels && this.noiseHoverRequest && payload.id === this.noiseHoverRequest.id) {
      this.noiseHoverField = {
        levels: payload.levels,
        gridSize: payload.gridSize,
        bounds: { ...this.noiseHoverRequest.bounds },
        mode: this.noiseHoverRequest.mode,
        minDb: this.noiseHoverRequest.minDb,
      };
      this.noiseHoverRequest = null;
    } else if (payload.levels) {
      this.noiseHoverField = {
        levels: payload.levels,
        gridSize: payload.gridSize,
        bounds: null,
        mode: this.noiseRenderMode,
        minDb: null,
      };
      this.noiseHoverRequest = null;
    }
    if (this.noiseEnabled) {
      this.drawNoise(payload.pixels, payload.gridSize);
      this.noiseLastUpdateMs = performance.now();
    } else {
      this.noiseAverageLastUpdateMs = performance.now();
    }
    // JY - Noise hover: refresh tooltip while cursor is stationary.
    if (this.noiseHoverLngLat) {
      this.updateNoiseHover(this.noiseHoverLngLat);
    }
    this.noiseInFlight = false;
    if (this.noisePending) {
      this.noisePending = false;
      if (this.noiseEnabled) {
        this.scheduleNoiseUpdate(true);
      } else {
        this.scheduleNoiseAverageUpdate(true);
      }
    }
  };

  MapApp.prototype.drawNoise = function (pixels, gridSize) {
    if (!this.noiseCanvasCtx || !this.noiseCanvas || !pixels) {
      return;
    }
    if (!this.noiseBufferCanvas || this.noiseBufferCanvas.width !== gridSize) {
      const buffer = document.createElement("canvas");
      buffer.width = gridSize;
      buffer.height = gridSize;
      this.noiseBufferCanvas = buffer;
      this.noiseBufferCtx = buffer.getContext("2d");
    }
    if (!this.noiseBufferCtx) {
      return;
    }
    const imageData = new ImageData(pixels, gridSize, gridSize);
    this.noiseBufferCtx.putImageData(imageData, 0, 0);
    this.noiseCanvasCtx.clearRect(0, 0, this.noiseCanvas.width, this.noiseCanvas.height);
    this.noiseCanvasCtx.imageSmoothingEnabled = true;
    let source = null;
    const viewMap = this.noiseMiniMap || this.map;
    if (this.noiseRenderMode === "average" && viewMap) {
      // JY - Noise average: crop the average grid to the current view.
      source = this.resolveNoiseAverageSourceRect(viewMap.getBounds(), gridSize);
    }
    if (source) {
      this.noiseCanvasCtx.drawImage(
        this.noiseBufferCanvas,
        source.sx,
        source.sy,
        source.sw,
        source.sh,
        0,
        0,
        this.noiseCanvas.width,
        this.noiseCanvas.height,
      );
      this.markNoiseHeatmapDrawn();
      return;
    }
    this.noiseCanvasCtx.drawImage(
      this.noiseBufferCanvas,
      0,
      0,
      this.noiseCanvas.width,
      this.noiseCanvas.height,
    );
    this.markNoiseHeatmapDrawn();
  };

  const baseInit = MapApp.prototype.init;
  if (baseInit) {
    MapApp.prototype.init = function () {
      baseInit.call(this);
      this.initNoiseLayer();
    };
  }

  const baseApplyTheme = MapApp.prototype.applyTheme;
  if (baseApplyTheme) {
    MapApp.prototype.applyTheme = function (theme) {
      baseApplyTheme.call(this, theme);
      this.updateNoiseMiniMapTheme(theme);
    };
  }

  const baseUpdateTrafficPositions = MapApp.prototype.updateTrafficPositions;
  if (baseUpdateTrafficPositions) {
    MapApp.prototype.updateTrafficPositions = function (positions) {
      if (Array.isArray(positions)) {
        this.noisePositions = positions;
        this.noiseUpdateIntervalMs = this.resolveNoiseUpdateInterval(positions.length);
        if (this.noiseEnabled) {
          this.scheduleNoiseUpdate();
        } else {
          this.scheduleNoiseAverageUpdate();
        }
      }
      return baseUpdateTrafficPositions.call(this, positions);
    };
  }
})();
