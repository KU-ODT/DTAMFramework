/* app.transmission.js (수정된 전체 파일) */

(() => {
  const TRANSMISSION_POPOUT_ID = "transmission";
  const TRANSMISSION_BS_HEIGHT_M = 25.0;
  const TRANSMISSION_FC_GHZ = 2.0;
  const TRANSMISSION_P_TX_DBM = 46.0;
  const TRANSMISSION_G_TX_DBI = 0.0;
  const TRANSMISSION_G_RX_DBI = 0.0;
  const TRANSMISSION_MISC_LOSS_DB = 0.0;
  const TRANSMISSION_RADIUS_M = 4000.0;
  const TRANSMISSION_MIN_DBM_DEFAULT = -135;
  const TRANSMISSION_MAX_DBM = -50;
  const TRANSMISSION_UPDATE_INTERVAL_MS = 1600;
  const TRANSMISSION_GRID_MIN = 96;
  const TRANSMISSION_GRID_MAX = 160;
  const TRANSMISSION_GRID_HIGH = 160;
  const TRANSMISSION_GRID_MED = 144;
  const TRANSMISSION_GRID_LOW = 128;
  const TRANSMISSION_GRID_EXPANDED_MIN = 224;
  const TRANSMISSION_GRID_EXPANDED_MAX = 320;
  const TRANSMISSION_GRID_EXPANDED_HIGH = 320;
  const TRANSMISSION_GRID_EXPANDED_MED = 288;
  const TRANSMISSION_GRID_EXPANDED_LOW = 256;
  const TRANSMISSION_DEM_ZOOM_CAP = 12;
  const TRANSMISSION_MINIMAP_ZOOM_OFFSET = -1.4;
  const TRANSMISSION_MINIMAP_MIN_ZOOM = 9;
  const TRANSMISSION_MINIMAP_LOCKED = false;
  const TRANSMISSION_HEIGHTS = [1.5, 50, 100, 200, 300];
  const TRANSMISSION_HEIGHT_DEFAULT = 50;
  const TRANSMISSION_LOS_STEP_M = 40;

  // [추가] UMa-AV 섹터 방위각/다운틸트/요소 이득 (36.777 시나리오에서 흔히 쓰는 값 계열)
  // - sectorAzDeg: 3 섹터 보어사이트 방위각(도)
  // - downtiltDeg: 기계/전기적 다운틸트(도) - 워커에서 로컬각 계산에 사용
  // - elementGainDb: 단일 요소 최대 이득(3GPP 안테나 요소 모델 계열에서 흔히 8 dBi)
  const TRANSMISSION_SECTOR_AZ_DEG = [30, 150, 270];
  const TRANSMISSION_DOWNTILT_DEG = 100;
  const TRANSMISSION_ELEMENT_GAIN_DB = 8;

  const TRANSMISSION_SEOUL_BOUNDS = {
    west: 126.6,
    south: 37.35,
    east: 127.3,
    north: 37.8,
  };
  const DEG_TO_RAD = Math.PI / 180;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
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
  const isTransmissionPopout = () => readPanelParam() === TRANSMISSION_POPOUT_ID;
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
  const openTransmissionPopout = () => {
    if (typeof window === "undefined" || !window.open) {
      return;
    }
    const url = buildPopoutUrl(TRANSMISSION_POPOUT_ID);
    if (!url) {
      return;
    }
    const popout = window.open(url, "transmission-popout");
    if (popout && popout.focus) {
      popout.focus();
    }
  };

  if (isTransmissionPopout() && typeof document !== "undefined") {
    document.body.classList.add("panel-popout", "panel-popout-transmission");
  }

  const TRANSMISSION_LAYER_PAINT = {
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

  const TRANSMISSION_FALLBACK_PALETTES = {
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
      ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) *
      n;
    return { x, y };
  };

  class TransmissionDemSampler {
    constructor(tileUrl, tileSize, maxZoom) {
      this.tileUrl = tileUrl;
      this.tileSize = tileSize || 256;
      this.maxZoom = maxZoom || 12;
      this.zoom = Math.min(this.maxZoom, TRANSMISSION_DEM_ZOOM_CAP);
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
      } catch (_error) {
        return null;
      }
    }

    _ensureCanvas() {
      if (!this.canvas || !this.ctx) {
        const canvas = document.createElement("canvas");
        canvas.width = this.tileSize;
        canvas.height = this.tileSize;
        this.canvas = canvas;
        this.ctx = canvas.getContext("2d", { willReadFrequently: true });
      }
      return Boolean(this.canvas && this.ctx);
    }

    _decodeTile(img) {
      if (!img || !this._ensureCanvas()) {
        return null;
      }
      const ctx = this.ctx;
      ctx.clearRect(0, 0, this.tileSize, this.tileSize);
      ctx.drawImage(img, 0, 0, this.tileSize, this.tileSize);
      const { data } = ctx.getImageData(0, 0, this.tileSize, this.tileSize);
      const out = new Float32Array(this.tileSize * this.tileSize);
      for (let i = 0; i < out.length; i += 1) {
        const base = i * 4;
        const r = data[base];
        const g = data[base + 1];
        const b = data[base + 2];
        out[i] = r * 256 + g + b / 256 - 32768;
      }
      return out;
    }

    _formatUrl(z, x, y) {
      if (!this.tileUrl) {
        return null;
      }
      return this.tileUrl
        .replace("{z}", String(z))
        .replace("{x}", String(x))
        .replace("{y}", String(y));
    }

    async _getTile(z, x, y) {
      const key = `${z}/${x}/${y}`;
      if (this.cache.has(key)) {
        return this.cache.get(key);
      }
      if (this.pending.has(key)) {
        return this.pending.get(key);
      }
      const url = this._formatUrl(z, x, y);
      if (!url) {
        return null;
      }
      const promise = (async () => {
        const img = await this._fetchImage(url);
        if (!img) {
          this.failureCount += 1;
          if (this.failureCount >= this.maxFailuresBeforeDisable) {
            this.disabled = true;
          }
          return null;
        }
        this.failureCount = 0;
        this.hasData = true;
        const tile = this._decodeTile(img);
        if (tile) {
          this.cache.set(key, tile);
          this.cacheOrder.push(key);
          while (this.cacheOrder.length > this.maxCacheTiles) {
            const oldest = this.cacheOrder.shift();
            if (oldest) {
              this.cache.delete(oldest);
            }
          }
        }
        return tile;
      })();
      this.pending.set(key, promise);
      const result = await promise;
      this.pending.delete(key);
      return result;
    }

    async sampleGrid(bounds, gridSize) {
      if (!bounds || !gridSize || this.disabled) {
        return null;
      }
      const z = this.zoom;
      const west = Number(bounds.west);
      const east = Number(bounds.east);
      const south = Number(bounds.south);
      const north = Number(bounds.north);
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

  MapApp.prototype.initTransmissionLayer = function () {
    const popoutMode = isTransmissionPopout();
    this.transmissionPopoutMode = popoutMode;
    if (popoutMode && typeof document !== "undefined") {
      document.body.classList.add("panel-popout", "panel-popout-transmission");
    }
    this.transmissionPanel = document.getElementById("transmission-panel");
    this.transmissionLayerButton = document.querySelector(
      '[data-action="layer-transmission"]'
    );
    this.transmissionMapContainer = document.getElementById("transmission-map");
    this.transmissionCanvas = document.getElementById("transmission-canvas");
    this.transmissionLegendMin = document.getElementById(
      "transmission-legend-min"
    );
    this.transmissionLegendMax = document.getElementById(
      "transmission-legend-max"
    );
    this.transmissionMeta = document.getElementById("transmission-meta");
    this.transmissionCloseButton =
      document.getElementById("transmission-close");
    this.transmissionExpandButton = document.getElementById(
      "transmission-expand"
    );
    this.transmissionHeightInput =
      document.getElementById("transmission-height");
    this.transmissionHeightValue =
      document.getElementById("transmission-height-value");
    this.transmissionEnabled = false;
    this.transmissionExpanded = popoutMode;
    this.transmissionMinDbm = TRANSMISSION_MIN_DBM_DEFAULT;
    this.transmissionMaxDbm = TRANSMISSION_MAX_DBM;
    this.transmissionHeight = TRANSMISSION_HEIGHT_DEFAULT;
    this.transmissionLastUpdateMs = 0;
    this.transmissionUpdateTimer = null;
    this.transmissionInFlight = false;
    this.transmissionPending = false;
    this.transmissionRequestId = 0;
    this.transmissionDemAvailable = false;
    this.transmissionMiniMap = null;
    this.transmissionMiniMapReady = false;
    this.transmissionMiniMapZoomOffset = TRANSMISSION_MINIMAP_ZOOM_OFFSET;
    this.transmissionMiniMapInteractive = false;
    this.transmissionMiniMapHandlersBound = false;
    this.transmissionWorker = null;
    this.transmissionBufferCanvas = null;
    this.transmissionBufferCtx = null;
    this.transmissionCanvasCtx = this.transmissionCanvas
      ? this.transmissionCanvas.getContext("2d")
      : null;
    this.transmissionHeatmapMoveDepth = 0;
    this.transmissionHeatmapRevealPending = false;

    if (this.config && this.config.dem) {
      this.transmissionDemSampler = new TransmissionDemSampler(
        this.config.dem.tileUrl,
        this.config.dem.tileSize,
        this.config.dem.maxZoom
      );
    } else {
      this.transmissionDemSampler = null;
    }

    if (typeof Worker === "function") {
      this.transmissionWorker = new Worker("transmission.worker.js");
      this.transmissionWorker.onmessage = (event) =>
        this.handleTransmissionWorkerResult(event.data);
    }

    if (!popoutMode && this.map) {
      this.attachTransmissionCanvasToMap();
    }

    if (this.transmissionHeightInput) {
      this.updateTransmissionHeightDisplay();
      this.transmissionHeightInput.addEventListener("input", (event) => {
        const nextValue = Number(event.target.value);
        if (Number.isFinite(nextValue)) {
          this.setTransmissionHeight(nextValue);
        }
      });
    }

    if (this.transmissionLayerButton) {
      this.transmissionLayerButton.addEventListener("click", () => {
        this.setTransmissionEnabled(!this.transmissionEnabled);
        if (this.setBaseListOpen) {
          this.setBaseListOpen(false);
        }
      });
    }
    if (this.transmissionCloseButton) {
      this.transmissionCloseButton.addEventListener("click", () => {
        this.setTransmissionEnabled(false);
      });
    }
    if (this.transmissionExpandButton) {
      if (popoutMode) {
        this.transmissionExpandButton.style.display = "none";
      } else {
        this.transmissionExpandButton.addEventListener("click", () => {
          openTransmissionPopout();
        });
      }
    }

    if (this.map) {
      this.setupTransmissionMapHandlers();
    }
    this.syncTransmissionCanvasSize();
    this.updateTransmissionMeta();
    this.updateTransmissionLegend();
    this.updateTransmissionExpandButton();
    if (popoutMode) {
      this.setTransmissionEnabled(true);
      if (this.dismissStartScreen) {
        this.dismissStartScreen();
      }
    }
  };

  MapApp.prototype.updateTransmissionLegend = function () {
    const minValue = Number.isFinite(this.transmissionMinDbm)
      ? this.transmissionMinDbm
      : TRANSMISSION_MIN_DBM_DEFAULT;
    const maxValue = Number.isFinite(this.transmissionMaxDbm)
      ? this.transmissionMaxDbm
      : TRANSMISSION_MAX_DBM;
    if (this.transmissionLegendMin) {
      this.transmissionLegendMin.textContent = `${Math.round(minValue)} dBm`;
    }
    if (this.transmissionLegendMax) {
      this.transmissionLegendMax.textContent = `${Math.round(maxValue)} dBm`;
    }
  };

  MapApp.prototype.updateTransmissionMeta = function () {
    if (!this.transmissionMeta) {
      return;
    }
    let demLabel = "DEM: OFF";
    if (this.transmissionDemSampler) {
      if (this.transmissionDemAvailable) {
        demLabel = "DEM: ON";
      } else if (this.transmissionDemSampler.disabled) {
        demLabel = "DEM: MISSING";
      } else {
        demLabel = "DEM: LOADING";
      }
    }
    demLabel = this.translateLiteral(demLabel);
    const heightValue = Number.isFinite(this.transmissionHeight)
      ? `hUT ${this.transmissionHeight}m`
      : "";
    const count = this.baseStationPointLookup
      ? this.baseStationPointLookup.size
      : 0;
    const parts = [demLabel];
    if (heightValue) {
      parts.push(heightValue);
    }
    if (count) {
      parts.push(`BS ${count}`);
    }
    this.transmissionMeta.textContent = parts.join(" / ");
  };

  MapApp.prototype.updateTransmissionExpandButton = function () {
    if (!this.transmissionExpandButton) {
      return;
    }
    const label = this.translateLiteral("Open radio propagation in external tab");
    this.transmissionExpandButton.setAttribute(
      "aria-pressed",
      "false"
    );
    this.transmissionExpandButton.setAttribute("aria-label", label);
    this.transmissionExpandButton.setAttribute("title", label);
  };

  MapApp.prototype.setTransmissionMiniMapInteractive = function (interactive) {
    const next = Boolean(interactive);
    this.transmissionMiniMapInteractive = next;
    if (!this.transmissionMiniMap) {
      return;
    }
    const map = this.transmissionMiniMap;
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

  MapApp.prototype.attachTransmissionCanvasToMap = function () {
    if (this.transmissionPopoutMode || !this.transmissionCanvas || !this.map) {
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
    if (this.transmissionCanvas.parentElement !== container) {
      container.appendChild(this.transmissionCanvas);
    }
  };

  MapApp.prototype.setTransmissionHeatmapFading = function (fading) {
    if (!this.transmissionCanvas) {
      return;
    }
    this.transmissionCanvas.classList.toggle("is-fading", Boolean(fading));
  };

  MapApp.prototype.startTransmissionHeatmapMove = function () {
    if (!this.transmissionEnabled) {
      return;
    }
    this.transmissionHeatmapMoveDepth += 1;
    this.setTransmissionHeatmapFading(true);
  };

  MapApp.prototype.endTransmissionHeatmapMove = function () {
    if (!this.transmissionEnabled) {
      return;
    }
    this.transmissionHeatmapMoveDepth = Math.max(
      0,
      this.transmissionHeatmapMoveDepth - 1
    );
    if (this.transmissionHeatmapMoveDepth > 0) {
      return;
    }
    if (this.transmissionHeatmapRevealPending) {
      this.transmissionHeatmapRevealPending = false;
      this.setTransmissionHeatmapFading(false);
    }
  };

  MapApp.prototype.markTransmissionHeatmapDrawn = function () {
    if (!this.transmissionEnabled) {
      return;
    }
    if (this.transmissionHeatmapMoveDepth > 0) {
      this.transmissionHeatmapRevealPending = true;
      return;
    }
    this.transmissionHeatmapRevealPending = false;
    this.setTransmissionHeatmapFading(false);
  };

  MapApp.prototype.resetTransmissionHeatmapFade = function () {
    this.transmissionHeatmapMoveDepth = 0;
    this.transmissionHeatmapRevealPending = false;
    this.setTransmissionHeatmapFading(false);
  };

  MapApp.prototype.bindTransmissionMiniMapHandlers = function () {
    if (!this.transmissionMiniMap || this.transmissionMiniMapHandlersBound) {
      return;
    }
    this.transmissionMiniMapHandlersBound = true;
    const handler = () => {
      if (this.transmissionEnabled) {
        this.scheduleTransmissionUpdate(true);
      }
    };
    const handleMoveStart = () => {
      this.startTransmissionHeatmapMove();
    };
    const handleMoveEnd = () => {
      this.endTransmissionHeatmapMove();
    };
    this.transmissionMiniMap.on("movestart", handleMoveStart);
    this.transmissionMiniMap.on("moveend", handleMoveEnd);
    this.transmissionMiniMap.on("zoomend", handleMoveEnd);
    this.transmissionMiniMap.on("moveend", handler);
    this.transmissionMiniMap.on("zoomend", handler);
  };

  MapApp.prototype.formatTransmissionHeight = function (value) {
    if (!Number.isFinite(value)) {
      return "";
    }
    const rounded =
      Math.abs(value - Math.round(value)) > 0.01
        ? value.toFixed(1)
        : String(Math.round(value));
    return `${rounded} m`;
  };

  MapApp.prototype.updateTransmissionHeightDisplay = function () {
    const value = Number.isFinite(this.transmissionHeight)
      ? this.transmissionHeight
      : TRANSMISSION_HEIGHT_DEFAULT;
    if (this.transmissionHeightInput) {
      this.transmissionHeightInput.value = String(value);
    }
    if (this.transmissionHeightValue) {
      this.transmissionHeightValue.textContent = this.formatTransmissionHeight(
        value
      );
    }
  };

  MapApp.prototype.setTransmissionHeight = function (value) {
    const next = Number(value);
    if (!Number.isFinite(next)) {
      return;
    }
    if (this.transmissionHeight === next) {
      return;
    }
    this.transmissionHeight = next;
    this.updateTransmissionHeightDisplay();
    this.updateTransmissionMeta();
    this.scheduleTransmissionUpdate(true);
  };

  MapApp.prototype.setupTransmissionMapHandlers = function () {
    if (!this.map || this.transmissionMapHandlersBound) {
      return;
    }
    this.transmissionMapHandlersBound = true;
    if (!TRANSMISSION_MINIMAP_LOCKED) {
      const handler = () => {
        this.endTransmissionHeatmapMove();
        this.syncTransmissionMiniMapView();
        this.scheduleTransmissionUpdate();
      };
      const handleMoveStart = () => {
        this.startTransmissionHeatmapMove();
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
      this.syncTransmissionCanvasSize();
      this.syncTransmissionMiniMapView(true);
      this.scheduleTransmissionUpdate(true);
    });
  };

  MapApp.prototype.resolveTransmissionMiniMapZoom = function () {
    if (TRANSMISSION_MINIMAP_LOCKED && this.transmissionMiniMap) {
      return this.transmissionMiniMap.getZoom();
    }
    const baseZoom = this.map
      ? this.map.getZoom()
      : this.config.startZoom || 10;
    const minZoom = Math.max(
      this.config.minZoom || 0,
      TRANSMISSION_MINIMAP_MIN_ZOOM
    );
    const maxZoom = this.config.maxZoom || baseZoom;
    const target = baseZoom + this.transmissionMiniMapZoomOffset;
    return clamp(target, minZoom, maxZoom);
  };

  MapApp.prototype.buildTransmissionMapStyle = function (theme) {
    if (!this.buildStyle) {
      return null;
    }
    const style = this.buildStyle();
    const useReal = theme === "real";
    const baseLayerIds =
      typeof BASE_MAP_LAYER_IDS !== "undefined"
        ? BASE_MAP_LAYER_IDS
        : Object.keys(TRANSMISSION_LAYER_PAINT);
    const realLayerId =
      typeof REAL_MAP_LAYER_ID !== "undefined"
        ? REAL_MAP_LAYER_ID
        : "real-raster";
    const palettes =
      typeof BASE_MAP_PALETTES !== "undefined"
        ? BASE_MAP_PALETTES
        : TRANSMISSION_FALLBACK_PALETTES;
    const palette =
      palettes[theme] || palettes.light || TRANSMISSION_FALLBACK_PALETTES.light;

    style.layers = style.layers.map((layer) => {
      const next = {
        ...layer,
        layout: layer.layout ? { ...layer.layout } : undefined,
        paint: layer.paint ? { ...layer.paint } : undefined,
      };
      if (layer.id === realLayerId) {
        next.layout = {
          ...(next.layout || {}),
          visibility: useReal ? "visible" : "none",
        };
        return next;
      }
      if (baseLayerIds.includes(layer.id)) {
        next.layout = {
          ...(next.layout || {}),
          visibility: useReal ? "none" : "visible",
        };
        if (!useReal) {
          const prop = TRANSMISSION_LAYER_PAINT[layer.id];
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

  MapApp.prototype.ensureTransmissionMiniMap = function () {
    if (!this.transmissionPopoutMode) {
      return;
    }
    if (
      !this.map ||
      !this.transmissionMapContainer ||
      this.transmissionMiniMap ||
      !window.maplibregl
    ) {
      return;
    }
    const style = this.buildTransmissionMapStyle(this.currentTheme || "light");
    if (!style) {
      return;
    }
    const baseCenter = TRANSMISSION_MINIMAP_LOCKED
      ? [
          (TRANSMISSION_SEOUL_BOUNDS.west + TRANSMISSION_SEOUL_BOUNDS.east) / 2,
          (TRANSMISSION_SEOUL_BOUNDS.south + TRANSMISSION_SEOUL_BOUNDS.north) /
            2,
        ]
      : [this.map.getCenter().lng, this.map.getCenter().lat];
    const zoom = this.resolveTransmissionMiniMapZoom();
    this.transmissionMiniMap = new maplibregl.Map({
      container: this.transmissionMapContainer,
      style,
      center: baseCenter,
      zoom,
      bearing: TRANSMISSION_MINIMAP_LOCKED ? 0 : this.map.getBearing(),
      pitch: 0,
      interactive: true,
      renderWorldCopies: false,
      attributionControl: false,
      fadeDuration: 0,
    });
    this.bindTransmissionMiniMapHandlers();
    this.setTransmissionMiniMapInteractive(this.transmissionExpanded || isTransmissionPopout());
    this.transmissionMiniMapReady = false;
    this.transmissionMiniMap.once("load", () => {
      this.transmissionMiniMapReady = true;
      this.transmissionMiniMap.resize();
      if (TRANSMISSION_MINIMAP_LOCKED) {
        const bounds = [
          [TRANSMISSION_SEOUL_BOUNDS.west, TRANSMISSION_SEOUL_BOUNDS.south],
          [TRANSMISSION_SEOUL_BOUNDS.east, TRANSMISSION_SEOUL_BOUNDS.north],
        ];
        this.transmissionMiniMap.fitBounds(bounds, {
          padding: 12,
          duration: 0,
        });
      } else {
        this.syncTransmissionMiniMapView(true);
      }
      if (this.transmissionEnabled) {
        this.scheduleTransmissionUpdate(true);
      }
    });
  };

  MapApp.prototype.destroyTransmissionMiniMap = function () {
    if (!this.transmissionMiniMap) {
      return;
    }
    this.transmissionMiniMap.remove();
    this.transmissionMiniMap = null;
    this.transmissionMiniMapReady = false;
  };

  MapApp.prototype.updateTransmissionMiniMapTheme = function (theme) {
    if (!this.transmissionMiniMap) {
      return;
    }
    const style = this.buildTransmissionMapStyle(theme);
    if (!style) {
      return;
    }
    const center = this.transmissionMiniMap.getCenter();
    const zoom = this.transmissionMiniMap.getZoom();
    const bearing = this.transmissionMiniMap.getBearing();
    this.transmissionMiniMapReady = false;
    this.transmissionMiniMap.setStyle(style);
    this.transmissionMiniMap.once("load", () => {
      this.transmissionMiniMapReady = true;
      if (TRANSMISSION_MINIMAP_LOCKED) {
        const bounds = [
          [TRANSMISSION_SEOUL_BOUNDS.west, TRANSMISSION_SEOUL_BOUNDS.south],
          [TRANSMISSION_SEOUL_BOUNDS.east, TRANSMISSION_SEOUL_BOUNDS.north],
        ];
        this.transmissionMiniMap.fitBounds(bounds, {
          padding: 12,
          duration: 0,
        });
      } else {
        this.transmissionMiniMap.jumpTo({
          center: [center.lng, center.lat],
          zoom,
          bearing,
          pitch: 0,
        });
      }
      if (this.transmissionEnabled) {
        this.scheduleTransmissionUpdate(true);
      }
    });
  };

  MapApp.prototype.syncTransmissionMiniMapView = function (force) {
    if (
      !this.transmissionMiniMap ||
      !this.map ||
      !this.transmissionMiniMapReady
    ) {
      return;
    }
    if (this.transmissionMiniMapInteractive) {
      return;
    }
    if (TRANSMISSION_MINIMAP_LOCKED) {
      if (force) {
        const bounds = [
          [TRANSMISSION_SEOUL_BOUNDS.west, TRANSMISSION_SEOUL_BOUNDS.south],
          [TRANSMISSION_SEOUL_BOUNDS.east, TRANSMISSION_SEOUL_BOUNDS.north],
        ];
        this.transmissionMiniMap.fitBounds(bounds, {
          padding: 12,
          duration: 0,
        });
      }
      return;
    }
    const center = this.map.getCenter();
    const zoom = this.resolveTransmissionMiniMapZoom();
    const bearing = this.map.getBearing();
    const current = this.transmissionMiniMap.getCenter();
    const needsUpdate =
      force ||
      Math.abs(current.lng - center.lng) > 1e-5 ||
      Math.abs(current.lat - center.lat) > 1e-5 ||
      Math.abs(this.transmissionMiniMap.getZoom() - zoom) > 1e-3 ||
      Math.abs(this.transmissionMiniMap.getBearing() - bearing) > 0.1;
    if (!needsUpdate) {
      return;
    }
    this.transmissionMiniMap.jumpTo({
      center: [center.lng, center.lat],
      zoom,
      bearing,
      pitch: 0,
    });
  };

  MapApp.prototype.syncTransmissionCanvasSize = function () {
    if (!this.transmissionCanvas || !this.transmissionCanvasCtx) {
      return;
    }
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(
      1,
      Math.round(this.transmissionCanvas.clientWidth * ratio)
    );
    const height = Math.max(
      1,
      Math.round(this.transmissionCanvas.clientHeight * ratio)
    );
    if (
      this.transmissionCanvas.width !== width ||
      this.transmissionCanvas.height !== height
    ) {
      this.transmissionCanvas.width = width;
      this.transmissionCanvas.height = height;
    }
    this.transmissionCanvasCtx.clearRect(0, 0, width, height);
    if (this.transmissionMiniMap) {
      this.transmissionMiniMap.resize();
    }
  };

  MapApp.prototype.setTransmissionExpanded = function (expanded) {
    const next = Boolean(expanded);
    this.transmissionExpanded = next;
    if (this.transmissionPanel) {
      this.transmissionPanel.classList.toggle("is-expanded", next);
    }
    this.updateTransmissionExpandButton();
    this.setTransmissionMiniMapInteractive(next || isTransmissionPopout());
    if (!this.transmissionEnabled) {
      return;
    }
    window.requestAnimationFrame(() => {
      this.syncTransmissionCanvasSize();
      this.scheduleTransmissionUpdate(true);
    });
  };

  MapApp.prototype.setTransmissionEnabled = function (enabled) {
    const next = Boolean(enabled);
    if (next && typeof this.disableOtherBaseLayers === "function") {
      this.disableOtherBaseLayers("transmission");
    }
    this.transmissionEnabled = next;
    if (typeof this.syncOverlayPitchLock === "function") {
      this.syncOverlayPitchLock();
    }
    if (typeof document !== "undefined") {
      document.body.classList.toggle("transmission-visible", next);
    }
    if (this.transmissionLayerButton) {
      this.transmissionLayerButton.classList.toggle("is-active", next);
    }
    if (this.transmissionPanel) {
      this.transmissionPanel.classList.toggle("is-visible", next);
      this.transmissionPanel.setAttribute(
        "aria-hidden",
        next ? "false" : "true"
      );
    }
    if (!next) {
      this.destroyTransmissionMiniMap();
      this.clearTransmissionCanvas();
      this.resetTransmissionHeatmapFade();
      return;
    }
    this.resetTransmissionHeatmapFade();
    this.attachTransmissionCanvasToMap();
    this.ensureTransmissionMiniMap();
    this.syncTransmissionMiniMapView(true);
    this.updateTransmissionMeta();
    this.updateTransmissionHeightDisplay();
    window.requestAnimationFrame(() => {
      this.syncTransmissionCanvasSize();
      this.scheduleTransmissionUpdate(true);
    });
  };

  MapApp.prototype.clearTransmissionCanvas = function () {
    if (!this.transmissionCanvasCtx || !this.transmissionCanvas) {
      return;
    }
    this.transmissionCanvasCtx.clearRect(
      0,
      0,
      this.transmissionCanvas.width,
      this.transmissionCanvas.height
    );
  };

  MapApp.prototype.scheduleTransmissionUpdate = function (force) {
    if (!this.transmissionEnabled || !this.transmissionWorker || !this.map) {
      return;
    }
    if (!TRANSMISSION_MINIMAP_LOCKED) {
      this.syncTransmissionMiniMapView();
    }
    const now = performance.now();
    const elapsed = now - this.transmissionLastUpdateMs;
    const interval = Number.isFinite(this.transmissionUpdateIntervalMs)
      ? this.transmissionUpdateIntervalMs
      : TRANSMISSION_UPDATE_INTERVAL_MS;
    const delay = Math.max(0, interval - elapsed);
    if (!force && delay > 0) {
      if (this.transmissionUpdateTimer) {
        return;
      }
      this.transmissionUpdateTimer = window.setTimeout(() => {
        this.transmissionUpdateTimer = null;
        this.refreshTransmission();
      }, delay);
      return;
    }
    this.refreshTransmission();
  };

  MapApp.prototype.resolveTransmissionGridSize = function (stationCount) {
    const expanded = Boolean(this.transmissionExpanded);
    let size = expanded
      ? TRANSMISSION_GRID_EXPANDED_HIGH
      : TRANSMISSION_GRID_HIGH;
    if (stationCount > 40) {
      size = expanded ? TRANSMISSION_GRID_EXPANDED_LOW : TRANSMISSION_GRID_LOW;
    } else if (stationCount > 20) {
      size = expanded ? TRANSMISSION_GRID_EXPANDED_MED : TRANSMISSION_GRID_MED;
    }
    const min = expanded
      ? TRANSMISSION_GRID_EXPANDED_MIN
      : TRANSMISSION_GRID_MIN;
    const max = expanded
      ? TRANSMISSION_GRID_EXPANDED_MAX
      : TRANSMISSION_GRID_MAX;
    return clamp(size, min, max);
  };

  MapApp.prototype.resolveTransmissionUpdateInterval = function (stationCount) {
    if (stationCount > 40) {
      return 2600;
    }
    if (stationCount > 20) {
      return 2000;
    }
    return TRANSMISSION_UPDATE_INTERVAL_MS;
  };

  MapApp.prototype.refreshTransmission = async function () {
    if (!this.transmissionEnabled || !this.transmissionWorker || !this.map) {
      return;
    }
    if (this.transmissionInFlight) {
      this.transmissionPending = true;
      return;
    }
    this.transmissionInFlight = true;
    if (this.transmissionMiniMap && !this.transmissionMiniMapReady) {
      this.transmissionInFlight = false;
      return;
    }
    const requestId = ++this.transmissionRequestId;
    const stationLookup = this.baseStationPointLookup;
    if (!stationLookup || stationLookup.size === 0) {
      this.clearTransmissionCanvas();
      this.transmissionInFlight = false;
      return;
    }

    let bounds;
    if (TRANSMISSION_MINIMAP_LOCKED) {
      bounds = { ...TRANSMISSION_SEOUL_BOUNDS };
    } else {
      const mapRef = this.transmissionMiniMapReady
        ? this.transmissionMiniMap
        : this.map;
      const boundsObj = mapRef.getBounds();
      bounds = {
        west: boundsObj.getWest(),
        south: boundsObj.getSouth(),
        east: boundsObj.getEast(),
        north: boundsObj.getNorth(),
      };
    }

    const centerLat = (bounds.north + bounds.south) * 0.5;
    const latScale = 111320;
    const lonScale = 111320 * Math.max(0.2, Math.cos(centerLat * DEG_TO_RAD));
    const marginLat = TRANSMISSION_RADIUS_M / latScale;
    const marginLon = TRANSMISSION_RADIUS_M / lonScale;
    const west = bounds.west - marginLon;
    const east = bounds.east + marginLon;
    const south = bounds.south - marginLat;
    const north = bounds.north + marginLat;

    const stations = [];
    let baseCount = 0;

    stationLookup.forEach((entry) => {
      if (!entry || !entry.coord) {
        return;
      }
      const lon = Number(entry.coord[0]);
      const lat = Number(entry.coord[1]);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return;
      }
      if (lon < west || lon > east || lat < south || lat > north) {
        return;
      }

      // [수정] 기존: stations.push({ lon, lat });
      //         변경: 1개 사이트를 3 섹터로 확장해서 워커로 전달
      baseCount += 1;
      for (let s = 0; s < TRANSMISSION_SECTOR_AZ_DEG.length; s += 1) {
        stations.push({
          lon,
          lat,
          sectorAzDeg: TRANSMISSION_SECTOR_AZ_DEG[s],
          downtiltDeg: TRANSMISSION_DOWNTILT_DEG,
          elementGainDb: TRANSMISSION_ELEMENT_GAIN_DB,
        });
      }
    });

    if (!stations.length) {
      this.clearTransmissionCanvas();
      this.transmissionInFlight = false;
      return;
    }

    // [수정] stations는 섹터 3배로 늘어나므로, gridSize/interval은 원래 BS 개수로 계산
    const sizingCount =
      baseCount ||
      Math.max(
        1,
        Math.floor(stations.length / TRANSMISSION_SECTOR_AZ_DEG.length)
      );
    const gridSize = this.resolveTransmissionGridSize(sizingCount);
    this.transmissionUpdateIntervalMs =
      this.resolveTransmissionUpdateInterval(sizingCount);

    let ground = null;
    if (this.transmissionDemSampler) {
      ground = await this.transmissionDemSampler.sampleGrid(bounds, gridSize);
    }
    const demAvailable =
      Boolean(ground) &&
      Boolean(
        this.transmissionDemSampler &&
          this.transmissionDemSampler.hasData &&
          !this.transmissionDemSampler.disabled
      );
    if (demAvailable !== this.transmissionDemAvailable) {
      this.transmissionDemAvailable = demAvailable;
      this.updateTransmissionMeta();
    }
    if (!this.transmissionEnabled || requestId !== this.transmissionRequestId) {
      this.transmissionInFlight = false;
      return;
    }

    const payload = {
      type: "compute",
      id: requestId,
      bounds,
      gridSize,
      stations,
      ground,
      minDbm: this.transmissionMinDbm,
      maxDbm: this.transmissionMaxDbm,
      radiusM: TRANSMISSION_RADIUS_M,
      utHeightM: this.transmissionHeight,
      bsHeightM: TRANSMISSION_BS_HEIGHT_M,
      fcGhz: TRANSMISSION_FC_GHZ,
      pTxDbm: TRANSMISSION_P_TX_DBM,
      gTxDbi: TRANSMISSION_G_TX_DBI,
      gRxDbi: TRANSMISSION_G_RX_DBI,
      miscLossDb: TRANSMISSION_MISC_LOSS_DB,
      losStepM: TRANSMISSION_LOS_STEP_M,
    };
    const transfer = [];
    if (ground && ground.buffer) {
      transfer.push(ground.buffer);
    }
    this.transmissionWorker.postMessage(payload, transfer);
  };

  MapApp.prototype.handleTransmissionWorkerResult = function (payload) {
    if (!payload || payload.type !== "result") {
      return;
    }
    if (
      !this.transmissionEnabled ||
      payload.id !== this.transmissionRequestId
    ) {
      this.transmissionInFlight = false;
      return;
    }
    this.drawTransmission(payload.pixels, payload.gridSize);
    this.transmissionLastUpdateMs = performance.now();
    this.transmissionInFlight = false;
    if (this.transmissionPending) {
      this.transmissionPending = false;
      this.scheduleTransmissionUpdate(true);
    }
  };

  MapApp.prototype.drawTransmission = function (pixels, gridSize) {
    if (!this.transmissionCanvasCtx || !this.transmissionCanvas || !pixels) {
      return;
    }
    if (
      !this.transmissionBufferCanvas ||
      this.transmissionBufferCanvas.width !== gridSize
    ) {
      const buffer = document.createElement("canvas");
      buffer.width = gridSize;
      buffer.height = gridSize;
      this.transmissionBufferCanvas = buffer;
      this.transmissionBufferCtx = buffer.getContext("2d");
    }
    if (!this.transmissionBufferCtx) {
      return;
    }
    const imageData = new ImageData(pixels, gridSize, gridSize);
    this.transmissionBufferCtx.putImageData(imageData, 0, 0);
    this.transmissionCanvasCtx.clearRect(
      0,
      0,
      this.transmissionCanvas.width,
      this.transmissionCanvas.height
    );
    this.transmissionCanvasCtx.imageSmoothingEnabled = true;
    this.transmissionCanvasCtx.drawImage(
      this.transmissionBufferCanvas,
      0,
      0,
      this.transmissionCanvas.width,
      this.transmissionCanvas.height
    );
    this.markTransmissionHeatmapDrawn();
  };

  const baseInit = MapApp.prototype.init;
  if (baseInit) {
    MapApp.prototype.init = function () {
      baseInit.call(this);
      this.initTransmissionLayer();
    };
  }

  const baseApplyTheme = MapApp.prototype.applyTheme;
  if (baseApplyTheme) {
    MapApp.prototype.applyTheme = function (theme) {
      baseApplyTheme.call(this, theme);
      this.updateTransmissionMiniMapTheme(theme);
    };
  }

  const baseUpdateBaseStationOverlayFromRows =
    MapApp.prototype.updateBaseStationOverlayFromRows;
  if (baseUpdateBaseStationOverlayFromRows) {
    MapApp.prototype.updateBaseStationOverlayFromRows = function (rows) {
      baseUpdateBaseStationOverlayFromRows.call(this, rows);
      this.updateTransmissionMeta();
      if (this.transmissionEnabled) {
        this.scheduleTransmissionUpdate(true);
      }
    };
  }
})();
