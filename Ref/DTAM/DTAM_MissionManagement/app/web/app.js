(() => {
  const body = document.body;
  const demConfig = {
    tileUrl: "/dem/{z}/{x}/{y}.png",
    tileSize: 256,
    maxZoom: 12,
    encoding: "terrarium",
    exaggeration: 1.0,
    pitchThreshold: 2,
  };
  const viewConfig = {
    maxZoomBuffer: 2,
    maxPitch: 85,
  };
  const dataConfig = {
    vertiportCsv: body.dataset.vertiportCsv || "/data/vertiport_default.csv",
    waypointCsv: body.dataset.waypointCsv || "/data/waypoint_default.csv",
  };
  const airsimConfig = {
    host: body.dataset.airsimHost || "127.0.0.1",
    port: Number(body.dataset.airsimPort) || 41451,
  };
  const config = {
    tileUrl: body.dataset.tileUrl,
    minZoom: Number(body.dataset.minZoom),
    maxZoom: Number(body.dataset.maxZoom),
    center: [Number(body.dataset.centerLon), Number(body.dataset.centerLat)],
    startZoom: Number(body.dataset.startZoom),
    bounds: body.dataset.bounds ? JSON.parse(body.dataset.bounds) : null,
    dem: demConfig,
    view: viewConfig,
    data: dataConfig,
    airsim: airsimConfig,
  };

  const parseCsvRows = (text) => {
    const rows = [];
    let row = [];
    let field = "";
    let inQuotes = false;

    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      if (inQuotes) {
        if (char === "\"") {
          if (text[i + 1] === "\"") {
            field += "\"";
            i += 1;
          } else {
            inQuotes = false;
          }
        } else {
          field += char;
        }
        continue;
      }

      if (char === "\"") {
        inQuotes = true;
      } else if (char === ",") {
        row.push(field);
        field = "";
      } else if (char === "\n") {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
      } else if (char !== "\r") {
        field += char;
      }
    }

    if (field.length > 0 || row.length > 0) {
      row.push(field);
      rows.push(row);
    }
    return rows;
  };

  const normalizeRows = (rows) =>
    rows.filter((row) => row.some((cell) => cell.trim().length > 0));
  const getDataRows = (text) => {
    const rows = normalizeRows(parseCsvRows(text));
    return rows.length > 1 ? rows.slice(1) : [];
  };
  const getFileName = (value) => {
    if (!value) {
      return "";
    }
    const parts = value.split(/[\\/]/);
    return parts[parts.length - 1];
  };

  const readCell = (row, index) => (row[index] ? row[index].trim() : "");
  const BASE_MAP_PALETTES = {
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
  const FT_TO_M = 0.3048;
  const parseAltitudeMeters = (value) => {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed)) {
      return null;
    }
    return parsed * FT_TO_M;
  };
  const formatAltitudeMeters = (value) => {
    const meters = parseAltitudeMeters(value);
    if (meters === null) {
      return "";
    }
    return meters.toFixed(1);
  };
  const hexToRgba = (hex, alpha = 1) => {
    const cleaned = hex.replace("#", "");
    const full =
      cleaned.length === 3
        ? cleaned
            .split("")
            .map((char) => char + char)
            .join("")
        : cleaned;
    const value = Number.parseInt(full, 16);
    if (!Number.isFinite(value)) {
      return new Float32Array([1, 1, 1, alpha]);
    }
    const r = ((value >> 16) & 255) / 255;
    const g = ((value >> 8) & 255) / 255;
    const b = (value & 255) / 255;
    return new Float32Array([r, g, b, alpha]);
  };
  const HOVER_OUTLINE_COLOR = "#ffe600";
  const MAP_SIZE_SCALE = 1.2;
  const VERTIPORT_ICON_ID = "vertiport-icon";
  const VERTIPORT_LINE_COLOR = "#2ecc71";
  const WGS84_A = 6378137.0;
  const WGS84_F = 1.0 / 298.257223563;
  const WGS84_E2 = WGS84_F * (2.0 - WGS84_F);
  const CITY_HALL_LAT = 37.566831;
  const CITY_HALL_LON = 126.978445;
  const CITY_HALL_UE = [217063.379391, -1013419.868553, -220649.796452];
  const AIRSIM_M = [
    [100.0281442606, -0.04714072563858, -14.48008452807, 217305.0259003],
    [-0.01400319634319, -99.95926827854, 22.17141115113, -1014189.34958],
    [-0.07523184332042, -0.06232285328839, 44.59215490766, -221718.536035],
  ];
  const AIRSIM_D_BIAS = 3.0;
  const TELEMETRY_ROTATION_DEG = 90;

  const degToRad = (value) => (value * Math.PI) / 180.0;
  const geodeticToEcef = (latDeg, lonDeg, hMeters = 0) => {
    const lat = degToRad(latDeg);
    const lon = degToRad(lonDeg);
    const sinLat = Math.sin(lat);
    const cosLat = Math.cos(lat);
    const n = WGS84_A / Math.sqrt(1.0 - WGS84_E2 * sinLat * sinLat);
    const x = (n + hMeters) * cosLat * Math.cos(lon);
    const y = (n + hMeters) * cosLat * Math.sin(lon);
    const z = ((1.0 - WGS84_E2) * n + hMeters) * sinLat;
    return [x, y, z];
  };
  const ecefToEnu = (xyz, lat0Deg, lon0Deg, h0Meters = 0) => {
    const [x0, y0, z0] = geodeticToEcef(lat0Deg, lon0Deg, h0Meters);
    const dx = xyz[0] - x0;
    const dy = xyz[1] - y0;
    const dz = xyz[2] - z0;
    const lat0 = degToRad(lat0Deg);
    const lon0 = degToRad(lon0Deg);
    const sinLat = Math.sin(lat0);
    const cosLat = Math.cos(lat0);
    const sinLon = Math.sin(lon0);
    const cosLon = Math.cos(lon0);
    const e = -sinLon * dx + cosLon * dy;
    const n = -sinLat * cosLon * dx - sinLat * sinLon * dy + cosLat * dz;
    const u = cosLat * cosLon * dx + cosLat * sinLon * dy + sinLat * dz;
    return [e, n, u];
  };
  const geodeticToEnu = (latDeg, lonDeg, lat0Deg, lon0Deg, hMeters = 0, h0Meters = 0) =>
    ecefToEnu(geodeticToEcef(latDeg, lonDeg, hMeters), lat0Deg, lon0Deg, h0Meters);
  const metersPerDegLat = (latRad) =>
    111132.92 -
    559.82 * Math.cos(2 * latRad) +
    1.175 * Math.cos(4 * latRad) -
    0.0023 * Math.cos(6 * latRad);
  const metersPerDegLon = (latRad) =>
    111412.84 * Math.cos(latRad) - 93.5 * Math.cos(3 * latRad) + 0.118 * Math.cos(5 * latRad);
  const enuToGeodetic = (e, n, u, lat0Deg, lon0Deg, h0Meters = 0) => {
    const latRad = degToRad(lat0Deg);
    const mLat = metersPerDegLat(latRad);
    const mLon = metersPerDegLon(latRad);
    if (!Number.isFinite(mLat) || !Number.isFinite(mLon) || mLat === 0 || mLon === 0) {
      return { lat: lat0Deg, lon: lon0Deg, alt: h0Meters + u };
    }
    return {
      lat: lat0Deg + n / mLat,
      lon: lon0Deg + e / mLon,
      alt: h0Meters + u,
    };
  };
  const rotateEnu = (e, n, rotationDeg) => {
    if (!rotationDeg) {
      return [e, n];
    }
    const angle = degToRad(-rotationDeg);
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return [e * cos - n * sin, e * sin + n * cos];
  };

  class AirsimConverter {
    constructor() {
      this.lat0 = CITY_HALL_LAT;
      this.lon0 = CITY_HALL_LON;
      this.cityHall = CITY_HALL_UE;
      this.matrix = AIRSIM_M;
    }

    geodeticToUe(latDeg, lonDeg, hMeters = 0) {
      const [e, n, u] = geodeticToEnu(latDeg, lonDeg, this.lat0, this.lon0, hMeters, 0);
      const v = [e, n, u, 1.0];
      const x =
        this.matrix[0][0] * v[0] +
        this.matrix[0][1] * v[1] +
        this.matrix[0][2] * v[2] +
        this.matrix[0][3] * v[3];
      const y =
        this.matrix[1][0] * v[0] +
        this.matrix[1][1] * v[1] +
        this.matrix[1][2] * v[2] +
        this.matrix[1][3] * v[3];
      const z =
        this.matrix[2][0] * v[0] +
        this.matrix[2][1] * v[1] +
        this.matrix[2][2] * v[2] +
        this.matrix[2][3] * v[3];
      return [x, y, z];
    }

    wgs84ToAirsimNed(latDeg, lonDeg, altMeters = 0) {
      const [xAbs, yAbs, zAbs] = this.geodeticToUe(latDeg, lonDeg, altMeters);
      const [chx, chy, chz] = this.cityHall;
      const xCm = xAbs - chx;
      const yCm = yAbs - chy;
      const zCm = zAbs - chz;
      const n = xCm / 100.0;
      const e = yCm / 100.0;
      const d = -zCm / 100.0 + AIRSIM_D_BIAS;
      return [n, e, d];
    }
  }

  class CenterControl {
    constructor(onClick) {
      this._onClick = onClick;
      this._container = null;
      this._button = null;
      this._handleClick = () => {
        if (this._onClick) {
          this._onClick();
        }
      };
    }

    onAdd(map) {
      this._map = map;
      const container = document.createElement("div");
      container.className = "maplibregl-ctrl maplibregl-ctrl-group center-control";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "center-control-btn";
      button.title = "Reset view";
      const dot = document.createElement("span");
      dot.className = "center-control-dot";
      button.appendChild(dot);
      button.addEventListener("click", this._handleClick);
      container.appendChild(button);
      this._container = container;
      this._button = button;
      return container;
    }

    onRemove() {
      if (this._button) {
        this._button.removeEventListener("click", this._handleClick);
      }
      if (this._container && this._container.parentNode) {
        this._container.parentNode.removeChild(this._container);
      }
      this._map = undefined;
    }
  }

  class MapApp {
    constructor(config) {
      this.config = config;
      this.map = null;
      this.mapContainer = document.getElementById("map");
      this.playbackPanel = document.getElementById("playback-panel");
      this.playbackConnectButton = null;
      this.playbackPlayButton = null;
      this.playbackStopButton = null;
      this.themeButtons = Array.from(document.querySelectorAll(".theme-card"));
      this.actionButtons = Array.from(document.querySelectorAll(".ui-btn"));
      this.closeButtons = Array.from(document.querySelectorAll(".panel-close"));
      this.panels = {
        vertiport: document.getElementById("vertiport-panel"),
        corridor: document.getElementById("corridor-panel"),
        plan: document.getElementById("plan-panel"),
        settings: document.getElementById("settings-panel"),
      };
      this.tableBodies = {
        vertiport: document.getElementById("vertiport-table-body"),
        corridor: document.getElementById("corridor-table-body"),
      };
      this.fileControls = {
        vertiport: {
          nameInput: document.getElementById("vertiport-file-name"),
          openButton: document.querySelector('[data-action="open-vertiport"]'),
          resetButton: document.querySelector('[data-action="reset-vertiport"]'),
        },
        corridor: {
          nameInput: document.getElementById("corridor-file-name"),
          openButton: document.querySelector('[data-action="open-corridor"]'),
          resetButton: document.querySelector('[data-action="reset-corridor"]'),
        },
      };
      this.planControls = {
        selectButton: document.querySelector('[data-action="plan-select"]'),
        resetButton: document.querySelector('[data-action="plan-reset"]'),
        applyButton: document.querySelector('[data-action="plan-apply"]'),
      };
      this.settingsControls = {
        hostInput: document.getElementById("settings-airsim-host"),
        portInput: document.getElementById("settings-airsim-port"),
        applyButton: document.querySelector('[data-action="settings-apply"]'),
        resetButton: document.querySelector('[data-action="settings-reset"]'),
      };
      this.filePickers = {};
      this.defaultFiles = {
        vertiport: {
          url: this.config.data.vertiportCsv,
          name: getFileName(this.config.data.vertiportCsv),
        },
        corridor: {
          url: this.config.data.waypointCsv,
          name: getFileName(this.config.data.waypointCsv),
        },
      };
      this.currentTheme = "light";
      this.terrainEnabled = false;
      this.homeView = null;
      this.airsimDefaults = {
        host: this.config.airsim.host,
        port: this.config.airsim.port,
      };
      this.airsimHost = this.config.airsim.host;
      this.airsimPort = this.config.airsim.port;
      this.airsimChannel = null;
      this.airsimBridge = null;
      this.telemetryMarker = null;
      this.telemetryLabel = null;
      this.telemetryName = "UAM1";
      this.telemetryConnected = false;
      this.telemetryLogAt = 0;
      this.telemetryAltFlipLogAt = 0;
      this.telemetryActive = false;
      this.telemetryPosition = null;
      this.telemetryAltitude = null;
      this.telemetryTrackEnabled = false;
      this.telemetryTrackCoords = [];
      this.telemetryTrackMaxPoints = 1200;
      this.telemetryTrackLayer = null;
      this.telemetryCalibration = null;
      this.telemetryRotationDeg = TELEMETRY_ROTATION_DEG;
      this.isPlaying = false;
      this.airsimConverter = new AirsimConverter();
      this.corridorLayer = null;
      this.corridorHitData = null;
      this.corridorHover = null;
      this.corridorHoverLabel = null;
      this.pendingCorridorRows = null;
      this.lastCorridorRows = null;
      this.corridorEnsured = false;
      this.corridorPointLookup = new Map();
      this.corridorData = null;
      this.vertiportHover = null;
      this.vertiportHoverId = null;
      this.vertiportLinkHover = null;
      this.vertiportLinkHoverId = null;
      this.vertiportHoverLabel = null;
      this.vertiportHoverName = null;
      this.vertiportLabels = [];
      this.lastVertiportRows = null;
      this.pendingVertiportRows = null;
      this.vertiportIconPromise = null;
      this.vertiportData = null;
      this.vertiportPointLookup = new Map();
      this.vertiportLinkLookup = new Map();
      this.vertiportAltLookup = new Map();
      this.vertiportResourceLookup = new Map();
      this.resourcesVpLoaded = false;
      this.routeGraph = null;
      this.routeNodeLookup = new Map();
      this.routeNodeXY = new Map();
      this.routeProjection = null;
      this.planRoute = [];
      this.appliedPlan = [];
      this.planSelectionMarkers = { start: null, end: null };
      this.planState = {
        enabled: false,
        mode: null,
        selection: [],
        viaNodes: [],
        manualPath: [],
        manualPrev: null,
        manualCurrent: null,
      };
      this.activeEdges = [];
      this.planLayersReady = false;
      this.planRouteLayer3d = null;
      this.vertiportLinks3dLayer = null;
    }

    init() {
      this.map = this.createMap();
      this.normalizeThemeButtons();
      this.bindThemeButtons();
      this.bindActionButtons();
      this.bindCloseButtons();
      this.bindFileControls();
      this.bindPlaybackControls();
      this.bindPlanControls();
      this.bindSettingsControls();
      this.connectAirsimBridge();
      this.syncFileNames();
      this.refreshAirsimInputs();
      this.applyTheme(this.currentTheme);
      this.loadDefaultTables();
      this.loadResourcesVp();
      this.setupScaleObserver();
      this.setupTerrainToggle();
      this.setupCorridorHover();
      this.setupVertiportHover();
      this.setupPlanInteractions();
    }

    createMap() {
      const style = this.buildStyle();
      const map = new maplibregl.Map({
        container: "map",
        style: style,
        center: this.config.center,
        zoom: this.config.startZoom,
        minZoom: this.config.minZoom,
        maxZoom: this.config.maxZoom + this.config.view.maxZoomBuffer,
        maxPitch: this.config.view.maxPitch,
        attributionControl: false,
      });

      map.addControl(new CenterControl(() => this.resetView()), "bottom-right");
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

      map.once("load", async () => {
        this.updateMapTheme(this.currentTheme);
        this.ensurePlanLayers();
        await this.ensureVertiportIcon();
        if (this.pendingCorridorRows) {
          const rows = this.pendingCorridorRows;
          this.pendingCorridorRows = null;
          this.updateCorridorOverlayFromRows(rows);
        } else {
          await this.loadCorridorOverlay();
        }
        if (this.pendingVertiportRows) {
          const rows = this.pendingVertiportRows;
          this.pendingVertiportRows = null;
          this.updateVertiportOverlayFromRows(rows);
        } else {
          await this.loadVertiportOverlay();
        }
        if (this.config.bounds) {
          map.fitBounds(this.config.bounds, { padding: 20, duration: 0 });
          map.once("idle", () => {
            this.captureHomeView();
            this.ensureCorridorReady();
          });
        } else {
          this.captureHomeView();
          map.once("idle", () => this.ensureCorridorReady());
        }
      });
      return map;
    }

    buildStyle() {
      return {
        version: 8,
        sources: {
          mbtiles: {
            type: "vector",
            tiles: [this.config.tileUrl],
            minzoom: this.config.minZoom,
            maxzoom: this.config.maxZoom,
          },
          dem: {
            type: "raster-dem",
            tiles: [this.config.dem.tileUrl],
            tileSize: this.config.dem.tileSize,
            maxzoom: this.config.dem.maxZoom,
            encoding: this.config.dem.encoding,
          },
        },
        layers: [
          {
            id: "background",
            type: "background",
            paint: { "background-color": "#eef2f3" },
          },
          {
            id: "landcover",
            type: "fill",
            source: "mbtiles",
            "source-layer": "landcover",
            paint: { "fill-color": "#dfe8d8", "fill-opacity": 0.7 },
          },
          {
            id: "landuse",
            type: "fill",
            source: "mbtiles",
            "source-layer": "landuse",
            paint: { "fill-color": "#e8e6d8", "fill-opacity": 0.7 },
          },
          {
            id: "park",
            type: "fill",
            source: "mbtiles",
            "source-layer": "park",
            paint: { "fill-color": "#cfe8c5", "fill-opacity": 0.85 },
          },
          {
            id: "water",
            type: "fill",
            source: "mbtiles",
            "source-layer": "water",
            paint: { "fill-color": "#a8c8e6" },
          },
          {
            id: "waterway",
            type: "line",
            source: "mbtiles",
            "source-layer": "waterway",
            paint: { "line-color": "#90b7dd", "line-width": 1 },
          },
          {
            id: "boundary",
            type: "line",
            source: "mbtiles",
            "source-layer": "boundary",
            paint: { "line-color": "#9a9a9a", "line-width": 1, "line-dasharray": [2, 2] },
          },
          {
            id: "transportation",
            type: "line",
            source: "mbtiles",
            "source-layer": "transportation",
            paint: { "line-color": "#c2b59b", "line-width": 1 },
          },
          {
            id: "building",
            type: "fill",
            source: "mbtiles",
            "source-layer": "building",
            minzoom: 13,
            paint: { "fill-color": "#d0c7c2", "fill-opacity": 0.6 },
          },
        ],
      };
    }

    bindThemeButtons() {
      this.themeButtons.forEach((button) => {
        button.addEventListener("click", () => {
          const theme = button.dataset.theme || "light";
          console.warn(`[UI] Theme click: ${theme}`);
          this.setTheme(theme);
        });
      });
    }

    normalizeThemeButtons() {
      this.themeButtons.forEach((button) => {
        const label = button.querySelector(".label");
        if (!label) {
          return;
        }
        const text = label.textContent.trim().toLowerCase();
        if (text === "dark") {
          button.dataset.theme = "dark";
        } else if (text === "white" || text === "light") {
          button.dataset.theme = "light";
        }
      });
    }

    bindActionButtons() {
      this.actionButtons.forEach((button) => {
        const action = button.dataset.action;
        if (!action) {
          return;
        }
        button.addEventListener("click", () => {
          this.handleAction(action);
        });
      });
    }

    bindCloseButtons() {
      this.closeButtons.forEach((button) => {
        const action = button.dataset.action;
        if (!action || !action.startsWith("close-")) {
          return;
        }
        const panelName = action.replace("close-", "");
        button.addEventListener("click", () => {
          this.hidePanel(panelName);
        });
      });
    }

    bindPlaybackControls() {
      if (!this.playbackPanel) {
        return;
      }
      this.playbackConnectButton = this.playbackPanel.querySelector(".playback-btn-connect");
      this.playbackPlayButton = this.playbackPanel.querySelector(".playback-btn-play");
      this.playbackStopButton = this.playbackPanel.querySelector(".playback-btn-stop");
      if (this.playbackConnectButton) {
        this.playbackConnectButton.addEventListener("click", () => this.handleConnect());
      }
      if (this.playbackPlayButton) {
        this.playbackPlayButton.addEventListener("click", () => this.handlePlay());
      }
      if (this.playbackStopButton) {
        this.playbackStopButton.addEventListener("click", () => this.handleStop());
      }
    }

    bindFileControls() {
      this.filePickers.vertiport = this.createFilePicker((text, fileName) => {
        const rows = getDataRows(text);
        if (this.tableBodies.vertiport) {
          this.populateVertiportTable(this.tableBodies.vertiport, rows);
        }
        this.updateVertiportOverlayFromRows(rows);
        this.updatePanelFileName("vertiport", fileName);
      });
      this.filePickers.corridor = this.createFilePicker((text, fileName) => {
        const rows = getDataRows(text);
        if (this.tableBodies.corridor) {
          this.populateCorridorTable(this.tableBodies.corridor, rows);
        }
        this.updateCorridorOverlayFromRows(rows);
        this.updatePanelFileName("corridor", fileName);
      });

      const vertiport = this.fileControls.vertiport;
      if (vertiport && vertiport.openButton) {
        vertiport.openButton.addEventListener("click", () => {
          this.filePickers.vertiport.click();
        });
      }
      if (vertiport && vertiport.resetButton) {
        vertiport.resetButton.addEventListener("click", () => {
          this.resetVertiport();
        });
      }

      const corridor = this.fileControls.corridor;
      if (corridor && corridor.openButton) {
        corridor.openButton.addEventListener("click", () => {
          this.filePickers.corridor.click();
        });
      }
      if (corridor && corridor.resetButton) {
        corridor.resetButton.addEventListener("click", () => {
          this.resetCorridor();
        });
      }
    }

    bindPlanControls() {
      if (this.planControls.selectButton) {
        this.planControls.selectButton.addEventListener("click", () =>
          this.togglePlanSelection(),
        );
      }
      if (this.planControls.resetButton) {
        this.planControls.resetButton.addEventListener("click", () => this.resetPlan());
      }
      if (this.planControls.applyButton) {
        this.planControls.applyButton.addEventListener("click", () => this.applyPlan());
      }
    }

    bindSettingsControls() {
      if (this.settingsControls.applyButton) {
        this.settingsControls.applyButton.addEventListener("click", () =>
          this.applyAirsimSettings(),
        );
      }
      if (this.settingsControls.resetButton) {
        this.settingsControls.resetButton.addEventListener("click", () =>
          this.resetAirsimSettings(),
        );
      }
    }

    connectAirsimBridge() {
      if (!window.qt || !window.QWebChannel) {
        return;
      }
      try {
        this.airsimChannel = new QWebChannel(window.qt.webChannelTransport, (channel) => {
          this.airsimBridge = channel.objects.airsimBridge || null;
          if (!this.airsimBridge) {
            console.warn("[AirSim] QWebChannel connected but bridge missing.");
          }
          if (
            this.airsimBridge &&
            this.airsimBridge.positionUpdated &&
            !this.telemetryConnected
          ) {
            this.airsimBridge.positionUpdated.connect((payload) => {
              this.handleTelemetryUpdate(payload);
            });
            this.telemetryConnected = true;
            console.warn("[AirSim] Telemetry signal connected.");
          } else if (this.airsimBridge && !this.airsimBridge.positionUpdated) {
            console.warn("[AirSim] positionUpdated signal not available.");
          }
        });
      } catch (error) {
        console.warn("Failed to connect AirSim bridge.", error);
      }
    }

    refreshAirsimInputs() {
      if (this.settingsControls.hostInput) {
        this.settingsControls.hostInput.value = this.airsimHost;
      }
      if (this.settingsControls.portInput) {
        this.settingsControls.portInput.value = String(this.airsimPort);
      }
    }

    applyAirsimSettings() {
      const hostInput = this.settingsControls.hostInput
        ? this.settingsControls.hostInput.value.trim()
        : "";
      const portInput = this.settingsControls.portInput
        ? Number.parseInt(this.settingsControls.portInput.value, 10)
        : NaN;
      this.airsimHost = hostInput || this.airsimDefaults.host;
      this.airsimPort = Number.isFinite(portInput) ? portInput : this.airsimDefaults.port;
      this.refreshAirsimInputs();
    }

    resetAirsimSettings() {
      this.airsimHost = this.airsimDefaults.host;
      this.airsimPort = this.airsimDefaults.port;
      this.refreshAirsimInputs();
    }

    syncFileNames() {
      Object.entries(this.defaultFiles).forEach(([key, info]) => {
        this.updatePanelFileName(key, info.name);
      });
    }

    updatePanelFileName(key, name) {
      const control = this.fileControls[key];
      if (!control || !control.nameInput) {
        return;
      }
      control.nameInput.value = name || "";
    }

    createFilePicker(onSelect) {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".csv,text/csv";
      input.style.display = "none";
      input.addEventListener("change", () => {
        const file = input.files && input.files[0];
        if (!file) {
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          const text = typeof reader.result === "string" ? reader.result : "";
          onSelect(text, file.name);
        };
        reader.onerror = () => {
          console.warn("Failed to read csv file.");
        };
        reader.readAsText(file);
        input.value = "";
      });
      document.body.appendChild(input);
      return input;
    }

    resetVertiport() {
      const info = this.defaultFiles.vertiport;
      if (info) {
        this.updatePanelFileName("vertiport", info.name);
        this.loadVertiportTable(info.url);
      }
    }

    resetCorridor() {
      const info = this.defaultFiles.corridor;
      if (info) {
        this.updatePanelFileName("corridor", info.name);
        this.loadCorridorData(info.url);
      }
    }

    async loadDefaultTables() {
      await Promise.all([
        this.loadVertiportTable(this.config.data.vertiportCsv),
        this.loadCorridorTable(this.config.data.waypointCsv),
      ]);
    }

    async loadVertiportTable(url) {
      const body = this.tableBodies.vertiport;
      if (!body) {
        return;
      }
      try {
        const rows = await this.fetchCsvRows(url);
        this.populateVertiportTable(body, rows);
        this.updateVertiportOverlayFromRows(rows);
      } catch (error) {
        console.warn("Failed to load vertiport data.", error);
      }
    }

    async loadCorridorTable(url) {
      await this.loadCorridorData(url);
    }

    async loadCorridorData(url) {
      const body = this.tableBodies.corridor;
      if (!body) {
        return;
      }
      try {
        const rows = await this.fetchCsvRows(url);
        this.populateCorridorTable(body, rows);
        this.updateCorridorOverlayFromRows(rows);
      } catch (error) {
        console.warn("Failed to load corridor data.", error);
      }
    }

    async fetchCsvRows(url) {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      const text = await response.text();
      return getDataRows(text);
    }

    populateVertiportTable(body, rows) {
      body.innerHTML = "";
      rows.forEach((row, index) => {
        const cells = [
          String(index + 1),
          readCell(row, 0),
          readCell(row, 3),
          readCell(row, 2),
          readCell(row, 1),
        ];
        body.appendChild(this.createTableRow(cells));
      });
    }

    populateCorridorTable(body, rows) {
      body.innerHTML = "";
      rows.forEach((row, index) => {
        const cells = [
          String(index + 1),
          readCell(row, 0),
          readCell(row, 2),
          readCell(row, 1),
          formatAltitudeMeters(readCell(row, 3)),
          readCell(row, 4),
        ];
        body.appendChild(this.createTableRow(cells));
      });
    }

    createTableRow(values) {
      const row = document.createElement("tr");
      values.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      return row;
    }

    handleAction(action) {
      switch (action) {
        case "vertiport":
          this.handleVertiportAction();
          break;
        case "corridor":
          this.handleCorridorAction();
          break;
        case "plan":
          this.handlePlanAction();
          break;
        case "settings":
          this.handleSettingsAction();
          break;
        case "playback":
          this.togglePlaybackPanel();
          break;
        default:
          break;
      }
    }

    handleVertiportAction() {
      this.togglePanel("vertiport");
    }

    handleCorridorAction() {
      this.togglePanel("corridor");
    }

    handlePlanAction() {
      this.togglePanel("plan");
    }

    handleSettingsAction() {
      this.togglePanel("settings");
    }

    togglePlaybackPanel() {
      if (!this.playbackPanel) {
        return;
      }
      const isOpen = this.playbackPanel.classList.contains("is-open");
      this.playbackPanel.classList.toggle("is-open", !isOpen);
      this.playbackPanel.setAttribute("aria-hidden", isOpen ? "true" : "false");
      this.setActionButtonActive("playback", !isOpen);
    }

    handlePlay() {
      if (!this.airsimBridge || !this.airsimBridge.startMission) {
        console.warn("AirSim bridge not available.");
        return;
      }
      const plan = this.getPlanForMission();
      if (!plan.length) {
        console.warn("No flight plan to send.");
        return;
      }
      this.setTelemetryCalibrationFromPlan();
      const payload = {
        host: this.airsimHost,
        port: this.airsimPort,
        relative_to_start: true,
        body_relative: true,
        yaw_follow: true,
        route: plan.map((entry) => ({
          name: entry.name,
          lat: entry.lat,
          lon: entry.lon,
          alt_m: entry.altitude_m,
          ned: { n: entry.n, e: entry.e, d: entry.d },
        })),
      };
      let payloadText = "";
      try {
        payloadText = JSON.stringify(payload);
      } catch (error) {
        payloadText = String(payload);
      }
      console.warn(`[AirSim] payload: ${payloadText}`);
      this.airsimBridge.startMission(payload);
      this.setPlayActive(true);
    }

    handleConnect() {
      if (!this.airsimBridge) {
        console.warn("[AirSim] Bridge not available.");
        return;
      }
      if (this.telemetryActive) {
        if (this.airsimBridge.stopTelemetry) {
          this.airsimBridge.stopTelemetry();
          console.warn("[AirSim] Telemetry stopped.");
        }
        this.setTelemetryActive(false);
        this.resetTelemetryCalibration();
        return;
      }
      if (!this.airsimBridge.startTelemetry) {
        console.warn("[AirSim] Telemetry not supported.");
        return;
      }
      const payload = {
        host: this.airsimHost,
        port: this.airsimPort,
        vehicle_name: this.telemetryName || "",
      };
      console.warn(
        `[AirSim] Telemetry connect: ${payload.host}:${payload.port} ${payload.vehicle_name || "default"}`,
      );
      this.resetTelemetryCalibration();
      this.setTelemetryCalibrationFromPlan();
      this.airsimBridge.startTelemetry(payload);
      this.setTelemetryActive(true);
    }

    handleStop() {
      if (this.airsimBridge && this.airsimBridge.stopMission) {
        this.airsimBridge.stopMission();
      }
      if (this.airsimBridge && this.airsimBridge.stopTelemetry) {
        this.airsimBridge.stopTelemetry();
      }
      this.setTelemetryActive(false);
      this.setPlayActive(false);
      this.resetTelemetryCalibration();
      this.resetAirsimSettings();
    }

    handleTelemetryUpdate(payload) {
      if (!payload || !this.map) {
        return;
      }
      const rawLat = Number(payload.lat);
      const rawLon = Number(payload.lon);
      let alt = Number(payload.alt_m);
      if (!Number.isFinite(rawLat) || !Number.isFinite(rawLon)) {
        return;
      }
      if (Number.isFinite(alt) && alt < 0) {
        alt = -alt;
        const now = Date.now();
        if (now - this.telemetryAltFlipLogAt > 2000) {
          this.telemetryAltFlipLogAt = now;
          console.warn("[AirSim] Telemetry altitude flipped from NED.");
        }
      }
      const adjusted = this.applyTelemetryCalibration(rawLat, rawLon, alt);
      const lat = adjusted.lat;
      const lon = adjusted.lon;
      alt = adjusted.alt;
      const name = payload.name ? String(payload.name) : this.telemetryName;
      this.telemetryName = name;
      this.telemetryPosition = [lon, lat];
      this.telemetryAltitude = Number.isFinite(alt) ? alt : null;
      if (!this.telemetryActive) {
        this.setTelemetryActive(true);
      }
      const now = Date.now();
      if (now - this.telemetryLogAt > 2000) {
        this.telemetryLogAt = now;
        console.warn(`[AirSim] Telemetry JS: ${name} ${lat.toFixed(6)}, ${lon.toFixed(6)}, ${alt.toFixed(2)}`);
      }
      this.ensureTelemetryMarker();
      if (!this.telemetryMarker) {
        return;
      }
      this.telemetryMarker.setLngLat([lon, lat]);
      if (this.telemetryLabel) {
        const altText = Number.isFinite(alt) ? `${alt.toFixed(1)} m` : "";
        this.telemetryLabel.textContent = altText ? `${name}\n${altText}` : name;
      }
      this.updateTelemetryTrack([lon, lat, Number.isFinite(alt) ? alt : 0]);
    }

    ensureTelemetryMarker() {
      if (this.telemetryMarker || !this.map) {
        return;
      }
      const marker = document.createElement("div");
      marker.className = "telemetry-marker";
      marker.addEventListener("click", (event) => {
        event.stopPropagation();
        this.toggleTelemetryTrack();
      });
      const dot = document.createElement("div");
      dot.className = "telemetry-marker-dot";
      const label = document.createElement("div");
      label.className = "telemetry-marker-label";
      label.textContent = this.telemetryName;
      marker.appendChild(dot);
      marker.appendChild(label);
      this.telemetryLabel = label;
      this.telemetryMarker = new maplibregl.Marker({
        element: marker,
        anchor: "bottom",
      })
        .setLngLat(this.map.getCenter().toArray())
        .addTo(this.map);
      console.warn("[AirSim] Telemetry marker created.");
    }

    ensureTelemetryTrackLayer() {
      if (!this.map || !this.map.isStyleLoaded()) {
        return false;
      }
      if (this.telemetryTrackLayer && this.map.getLayer(this.telemetryTrackLayer.id)) {
        return true;
      }
      const layer = this.createTelemetryTrackLayer();
      this.telemetryTrackLayer = layer;
      this.map.addLayer(layer);
      return true;
    }

    updateTelemetryTrack(coord) {
      if (!this.ensureTelemetryTrackLayer()) {
        return;
      }
      const last = this.telemetryTrackCoords[this.telemetryTrackCoords.length - 1];
      if (
        !last ||
        Math.abs(last[0] - coord[0]) > 1e-6 ||
        Math.abs(last[1] - coord[1]) > 1e-6 ||
        Math.abs((last[2] || 0) - (coord[2] || 0)) > 0.5
      ) {
        this.telemetryTrackCoords.push(coord);
        if (this.telemetryTrackCoords.length > this.telemetryTrackMaxPoints) {
          this.telemetryTrackCoords.splice(
            0,
            this.telemetryTrackCoords.length - this.telemetryTrackMaxPoints,
          );
        }
      }
      const buffers = this.buildTelemetryTrackBuffers();
      if (this.telemetryTrackLayer && this.telemetryTrackLayer.updateBuffers) {
        this.telemetryTrackLayer.updateBuffers(buffers);
      }
      if (this.telemetryTrackEnabled && this.map) {
        this.map.triggerRepaint();
      }
    }

    toggleTelemetryTrack() {
      this.telemetryTrackEnabled = !this.telemetryTrackEnabled;
      if (!this.map || !this.map.isStyleLoaded()) {
        return;
      }
      if (!this.ensureTelemetryTrackLayer()) {
        return;
      }
      if (this.telemetryTrackLayer && this.telemetryTrackLayer.setVisible) {
        this.telemetryTrackLayer.setVisible(this.telemetryTrackEnabled);
      }
      if (this.telemetryTrackEnabled) {
        const altitude = Number.isFinite(this.telemetryAltitude) ? this.telemetryAltitude : 0;
        const coord = this.telemetryPosition
          ? [this.telemetryPosition[0], this.telemetryPosition[1], altitude]
          : [...this.map.getCenter().toArray(), 0];
        this.updateTelemetryTrack(coord);
      }
      if (this.map) {
        this.map.triggerRepaint();
      }
      console.warn(
        `[AirSim] Telemetry track ${this.telemetryTrackEnabled ? "enabled" : "disabled"}.`,
      );
    }

    buildTelemetryTrackBuffers() {
      const linePositions = [];
      for (let i = 1; i < this.telemetryTrackCoords.length; i += 1) {
        const prev = this.telemetryTrackCoords[i - 1];
        const next = this.telemetryTrackCoords[i];
        const startAlt = Number.isFinite(prev[2]) ? prev[2] : 0;
        const endAlt = Number.isFinite(next[2]) ? next[2] : 0;
        const start = maplibregl.MercatorCoordinate.fromLngLat([prev[0], prev[1]], startAlt);
        const end = maplibregl.MercatorCoordinate.fromLngLat([next[0], next[1]], endAlt);
        linePositions.push(start.x, start.y, start.z, end.x, end.y, end.z);
      }
      return { linePositions };
    }

    createTelemetryTrackLayer() {
      const color = "#ffd447";
      const layer = {
        id: "telemetry-track-3d",
        type: "custom",
        renderingMode: "3d",
        _color: color,
        _lineCount: 0,
        _visible: false,
        setVisible(nextVisible) {
          this._visible = Boolean(nextVisible);
        },
        updateBuffers(buffers) {
          this._pendingBuffers = buffers;
          if (!this._gl || !this._lineBuffer) {
            return;
          }
          const gl = this._gl;
          const lineData = new Float32Array(buffers.linePositions);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, lineData, gl.STATIC_DRAW);
          this._lineCount = lineData.length / 3;
          this._pendingBuffers = null;
        },
        onAdd(_map, gl) {
          this._gl = gl;
          const vertexSource = `
            attribute vec3 a_pos;
            uniform mat4 u_matrix;
            void main() {
              gl_Position = u_matrix * vec4(a_pos, 1.0);
            }
          `;
          const fragmentSource = `
            precision mediump float;
            uniform vec4 u_color;
            void main() {
              gl_FragColor = u_color;
            }
          `;
          const compile = (type, source) => {
            const shader = gl.createShader(type);
            gl.shaderSource(shader, source);
            gl.compileShader(shader);
            return shader;
          };
          const vertexShader = compile(gl.VERTEX_SHADER, vertexSource);
          const fragmentShader = compile(gl.FRAGMENT_SHADER, fragmentSource);
          const program = gl.createProgram();
          gl.attachShader(program, vertexShader);
          gl.attachShader(program, fragmentShader);
          gl.linkProgram(program);
          this._program = program;
          this._aPos = gl.getAttribLocation(program, "a_pos");
          this._uMatrix = gl.getUniformLocation(program, "u_matrix");
          this._uColor = gl.getUniformLocation(program, "u_color");
          this._lineBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([]), gl.STATIC_DRAW);
          if (this._pendingBuffers) {
            this.updateBuffers(this._pendingBuffers);
          }
        },
        render(gl, matrix) {
          if (!this._program || !this._visible) {
            return;
          }
          gl.useProgram(this._program);
          gl.uniformMatrix4fv(this._uMatrix, false, matrix);
          const rgba = hexToRgba(this._color, 0.95);
          gl.uniform4fv(this._uColor, rgba);
          gl.enableVertexAttribArray(this._aPos);
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          if (this._lineCount > 0) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.lineWidth(2 * MAP_SIZE_SCALE);
            gl.drawArrays(gl.LINES, 0, this._lineCount);
          }
        },
      };
      return layer;
    }

    setTelemetryActive(isActive) {
      this.telemetryActive = isActive;
      if (this.playbackConnectButton) {
        this.playbackConnectButton.classList.toggle("is-active", isActive);
      }
    }

    setPlayActive(isActive) {
      this.isPlaying = isActive;
      if (this.playbackPlayButton) {
        this.playbackPlayButton.classList.toggle("is-active", isActive);
      }
    }

    resetTelemetryCalibration() {
      this.telemetryCalibration = null;
    }

    setTelemetryCalibrationTarget(target) {
      if (!target) {
        return;
      }
      const lat = Number(target.lat);
      const lon = Number(target.lon);
      const alt = Number(target.alt_m);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return;
      }
      this.telemetryCalibration = {
        target: {
          lat,
          lon,
          alt_m: Number.isFinite(alt) ? alt : 0,
        },
        source: null,
        rotation_deg: this.telemetryRotationDeg,
      };
      console.warn(
        `[AirSim] Telemetry calibration target: ${lat.toFixed(6)}, ${lon.toFixed(6)}, ` +
          `${Number.isFinite(alt) ? alt.toFixed(2) : "0.00"}`,
      );
      console.warn(
        `[AirSim] Telemetry calibration rotation: ${this.telemetryRotationDeg.toFixed(1)} deg`,
      );
    }

    setTelemetryCalibrationFromPlan() {
      let target = null;
      if (this.planState && Array.isArray(this.planState.selection) && this.planState.selection.length) {
        const name = this.planState.selection[0];
        const geo = this.resolveNodeGeodetic(name);
        if (geo && Number.isFinite(geo.lat) && Number.isFinite(geo.lon)) {
          target = {
            lat: geo.lat,
            lon: geo.lon,
            alt_m: Number.isFinite(geo.altitude_m) ? geo.altitude_m : 0,
          };
        }
      }
      if (!target && this.appliedPlan.length) {
        const start = this.appliedPlan[0];
        target = {
          lat: start.lat,
          lon: start.lon,
          alt_m: start.altitude_m,
        };
      }
      if (!target) {
        return;
      }
      this.setTelemetryCalibrationTarget(target);
    }

    applyTelemetryCalibration(lat, lon, alt) {
      if (!this.telemetryCalibration || !this.telemetryCalibration.target) {
        return { lat, lon, alt, calibrated: false };
      }
      const target = this.telemetryCalibration.target;
      if (!this.telemetryCalibration.source) {
        const baseAlt = Number.isFinite(alt) ? alt : target.alt_m;
        this.telemetryCalibration.source = {
          lat,
          lon,
          alt_m: baseAlt,
        };
        console.warn(
          `[AirSim] Telemetry calibration source: ${lat.toFixed(6)}, ${lon.toFixed(6)}, ` +
            `${Number.isFinite(baseAlt) ? baseAlt.toFixed(2) : "0.00"}`,
        );
      }
      const source = this.telemetryCalibration.source;
      const baseAlt = Number.isFinite(alt) ? alt : source.alt_m;
      const [e, n, u] = geodeticToEnu(lat, lon, source.lat, source.lon, baseAlt, source.alt_m);
      const [eRot, nRot] = rotateEnu(e, n, this.telemetryCalibration.rotation_deg);
      const adjusted = enuToGeodetic(eRot, nRot, u, target.lat, target.lon, target.alt_m);
      return {
        lat: adjusted.lat,
        lon: adjusted.lon,
        alt: adjusted.alt,
        calibrated: true,
      };
    }

    setupPlanInteractions() {
      if (!this.map) {
        return;
      }
      this.map.on("click", (event) => this.handlePlanClick(event));
      window.addEventListener("keydown", (event) => this.handlePlanKeyDown(event));
    }

    togglePlanSelection() {
      this.planState.enabled = !this.planState.enabled;
      console.warn(`[UI] Plan select ${this.planState.enabled ? "on" : "off"}`);
      if (this.planControls.selectButton) {
        this.planControls.selectButton.classList.toggle("is-active", this.planState.enabled);
      }
      if (this.planState.enabled && this.planState.selection.length < 2) {
        this.clearCorridorHover();
        this.clearVertiportHover();
      }
      if (!this.planState.enabled && this.map) {
        this.map.getCanvas().style.cursor = "";
      }
    }

    resetPlan() {
      this.resetPlanState();
      this.appliedPlan = [];
      this.planRoute = [];
      this.resetTelemetryCalibration();
    }

    applyPlan() {
      const result = this.computePlanRoute();
      if (!result || !result.path.length) {
        console.warn("No route to apply.");
        return;
      }
      this.planRoute = result.path;
      this.setPlanRoute(result.path);
      this.appliedPlan = this.buildPlanPoints(result.path);
      this.printPlanRoute(this.appliedPlan);
      this.setTelemetryCalibrationFromPlan();
      this.activeEdges = [];
      this.updateActiveEdges();
      this.planState.manualPath = [];
      this.planState.manualPrev = null;
      this.planState.manualCurrent = null;
      this.updateManualPreview();
      this.hidePanel("plan");
    }

    getPlanForMission() {
      if (this.appliedPlan.length) {
        return this.appliedPlan;
      }
      const result = this.computePlanRoute();
      if (!result || !result.path.length) {
        return [];
      }
      this.planRoute = result.path;
      this.setPlanRoute(result.path);
      this.appliedPlan = this.buildPlanPoints(result.path);
      return this.appliedPlan;
    }

    resetPlanState() {
      this.planState.mode = null;
      this.planState.selection = [];
      this.planState.viaNodes = [];
      this.planState.manualPath = [];
      this.planState.manualPrev = null;
      this.planState.manualCurrent = null;
      this.activeEdges = [];
      this.clearPlanRoute();
      this.updatePlanSelection();
      this.updateViaPoints();
      this.updateActiveEdges();
      this.updateManualPreview();
    }

    handlePlanClick(event) {
      if (!this.planState.enabled || !this.map || !this.map.isStyleLoaded()) {
        return;
      }
      const selection = this.planState.selection;
      const portPick = this.pickVertiportAt(event.point);
      if (selection.length < 2) {
        if (!portPick) {
          console.warn("[UI] Plan pick miss.");
          return;
        }
        console.warn(`[UI] Plan pick: ${portPick}`);
        if (!selection.length) {
          this.planState.selection = [portPick];
          this.updatePlanSelection();
          return;
        }
        if (portPick === selection[0]) {
          return;
        }
        this.planState.selection = [selection[0], portPick];
        this.planState.mode = null;
        this.planState.viaNodes = [];
        this.planState.manualPath = [];
        this.planState.manualPrev = null;
        this.planState.manualCurrent = null;
        this.updatePlanSelection();
        this.updateViaPoints();
        this.updateManualPreview();
        this.setActiveEdges(this.planState.selection[0], null);
        return;
      }

      if (portPick) {
        this.resetPlanState();
        this.planState.selection = [portPick];
        this.updatePlanSelection();
        return;
      }

      if (!this.planState.mode) {
        const edgePick = this.pickActiveEdge(event.point);
        if (edgePick) {
          this.planState.mode = "manual";
          this.planState.manualPath = [edgePick.from, edgePick.to];
          this.planState.manualPrev = edgePick.from;
          this.planState.manualCurrent = edgePick.to;
          this.updateManualPreview();
          if (edgePick.to === selection[1]) {
            this.activeEdges = [];
            this.updateActiveEdges();
          } else {
            this.setActiveEdges(edgePick.to, edgePick.from);
          }
          return;
        }

        const wpPick = this.pickCorridorPoint(event.point);
        if (wpPick) {
          this.planState.mode = "via";
          this.addViaNode(wpPick);
          return;
        }
        return;
      }

      if (this.planState.mode === "manual") {
        const edgePick = this.pickActiveEdge(event.point);
        if (!edgePick) {
          return;
        }
        if (!this.planState.manualCurrent) {
          return;
        }
        const nextNode = edgePick.to;
        this.planState.manualPath = [...this.planState.manualPath, nextNode];
        this.planState.manualPrev = this.planState.manualCurrent;
        this.planState.manualCurrent = nextNode;
        this.updateManualPreview();
        if (nextNode === selection[1]) {
          this.activeEdges = [];
          this.updateActiveEdges();
        } else {
          this.setActiveEdges(nextNode, this.planState.manualPrev);
        }
        return;
      }

      if (this.planState.mode === "via") {
        const wpPick = this.pickCorridorPoint(event.point);
        if (!wpPick) {
          return;
        }
        this.addViaNode(wpPick);
      }
    }

    pickVertiportAt(point) {
      if (!this.map) {
        return null;
      }
      const layers = [];
      if (this.map.getLayer("vertiport-icon")) {
        layers.push("vertiport-icon");
      }
      if (this.map.getLayer("vertiport-circle")) {
        layers.push("vertiport-circle");
      }
      if (!layers.length) {
        return null;
      }
      const features = this.map.queryRenderedFeatures(point, { layers });
      if (!features.length) {
        return null;
      }
      const name = features[0].properties ? String(features[0].properties.name || "") : "";
      return name || null;
    }

    pickCorridorPoint(point) {
      if (!this.corridorLayer || !this.corridorLayer.getMatrix) {
        return null;
      }
      const matrix = this.corridorLayer.getMatrix();
      if (!matrix) {
        return null;
      }
      const target = this.findCorridorHoverTarget(point, matrix);
      if (!target || target.type !== "point") {
        return null;
      }
      return target.name || null;
    }

    pickActiveEdge(point) {
      if (!this.map || !this.map.getLayer("flight-plan-active-links-hit")) {
        return null;
      }
      const features = this.map.queryRenderedFeatures(point, {
        layers: ["flight-plan-active-links-hit"],
      });
      if (!features.length) {
        return null;
      }
      const feature = features[0];
      const from = feature.properties ? String(feature.properties.from || "") : "";
      const to = feature.properties ? String(feature.properties.to || "") : "";
      if (!from || !to) {
        return null;
      }
      return { from, to };
    }

    addViaNode(name) {
      if (this.planState.viaNodes.includes(name)) {
        return;
      }
      this.planState.viaNodes = [...this.planState.viaNodes, name];
      this.updateViaPoints();
      this.updatePlanRoutePreview();
    }

    handlePlanKeyDown(event) {
      if (event.key !== "Enter") {
        return;
      }
      const target = event.target;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.tagName === "BUTTON" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (!this.planState.selection || this.planState.selection.length < 2) {
        return;
      }
      const result = this.computePlanRoute();
      if (!result || !result.path.length) {
        console.warn("No route to plan.");
        return;
      }
      this.planRoute = result.path;
      this.setPlanRoute(result.path);
      this.printPlanRoute(this.buildPlanPoints(result.path));
      this.activeEdges = [];
      this.updateActiveEdges();
      this.updateManualPreview();
      event.preventDefault();
    }

    updatePlanSelection() {
      if (!this.map) {
        return;
      }
      if (!this.map.getSource("flight-plan-selection")) {
        this.updatePlanSelectionMarkers();
        return;
      }
      const features = [];
      const [start, end] = this.planState.selection;
      if (start && this.vertiportPointLookup.has(start)) {
        const entry = this.vertiportPointLookup.get(start);
        features.push({
          type: "Feature",
          geometry: { type: "Point", coordinates: entry.coord },
          properties: { role: "start", name: entry.name },
        });
      }
      if (end && this.vertiportPointLookup.has(end)) {
        const entry = this.vertiportPointLookup.get(end);
        features.push({
          type: "Feature",
          geometry: { type: "Point", coordinates: entry.coord },
          properties: { role: "end", name: entry.name },
        });
      }
      this.map.getSource("flight-plan-selection").setData({
        type: "FeatureCollection",
        features,
      });
      this.updatePlanSelectionMarkers();
    }

    updatePlanSelectionMarkers() {
      if (!this.map) {
        return;
      }
      const [start, end] = this.planState.selection;
      this.updatePlanSelectionMarker("start", start, "S");
      this.updatePlanSelectionMarker("end", end, "E");
    }

    updatePlanSelectionMarker(key, name, label) {
      const current = this.planSelectionMarkers[key];
      if (!name || !this.vertiportPointLookup.has(name)) {
        if (current) {
          current.remove();
          this.planSelectionMarkers[key] = null;
        }
        return;
      }
      const entry = this.vertiportPointLookup.get(name);
      if (!entry) {
        return;
      }
      if (current) {
        current.setLngLat(entry.coord);
        current.getElement().textContent = label;
        return;
      }
      const marker = document.createElement("div");
      marker.className = "flight-plan-label";
      marker.textContent = label;
      this.planSelectionMarkers[key] = new maplibregl.Marker({
        element: marker,
        anchor: "center",
      })
        .setLngLat(entry.coord)
        .addTo(this.map);
    }

    updateViaPoints() {
      if (!this.map || !this.map.getSource("flight-plan-via")) {
        return;
      }
      const features = this.planState.viaNodes
        .map((name) => {
          const entry = this.routeNodeLookup.get(name);
          if (!entry) {
            return null;
          }
          return {
            type: "Feature",
            geometry: { type: "Point", coordinates: entry.coord },
            properties: { name: entry.name },
          };
        })
        .filter(Boolean);
      this.map.getSource("flight-plan-via").setData({
        type: "FeatureCollection",
        features,
      });
    }

    setActiveEdges(current, prev) {
      if (!this.routeGraph || !current) {
        this.activeEdges = [];
        this.updateActiveEdges();
        return;
      }
      const neighbors = this.routeGraph.get(current) || [];
      const endPort = this.planState.selection[1];
      const isPort = (name) => this.vertiportPointLookup.has(name);
      this.activeEdges = neighbors
        .filter((name) => name !== prev)
        .filter((name) => !isPort(name) || name === endPort)
        .map((name) => ({ from: current, to: name }));
      this.updateActiveEdges();
    }

    updateActiveEdges() {
      if (!this.map || !this.map.getSource("flight-plan-active-links")) {
        return;
      }
      const features = this.activeEdges
        .map((edge, index) => {
          const start = this.routeNodeLookup.get(edge.from);
          const end = this.routeNodeLookup.get(edge.to);
          if (!start || !end) {
            return null;
          }
          return {
            type: "Feature",
            id: index,
            geometry: {
              type: "LineString",
              coordinates: [start.coord, end.coord],
            },
            properties: { from: edge.from, to: edge.to },
          };
        })
        .filter(Boolean);
      const collection = { type: "FeatureCollection", features };
      this.map.getSource("flight-plan-active-links").setData(collection);
      if (this.map.getSource("flight-plan-active-links-hit")) {
        this.map.getSource("flight-plan-active-links-hit").setData(collection);
      }
    }

    updateManualPreview() {
      if (!this.map || !this.map.getSource("flight-plan-manual-preview")) {
        return;
      }
      const coords = this.planState.manualPath
        .map((name) => this.routeNodeLookup.get(name))
        .filter(Boolean)
        .map((entry) => entry.coord);
      const features =
        coords.length >= 2
          ? [
              {
                type: "Feature",
                geometry: { type: "LineString", coordinates: coords },
                properties: {},
              },
            ]
          : [];
      this.map.getSource("flight-plan-manual-preview").setData({
        type: "FeatureCollection",
        features,
      });
    }

    updatePlanRoutePreview() {
      if (!this.planState.mode || this.planState.mode === "manual") {
        return;
      }
      const result = this.computePlanRoute();
      if (!result || !result.path.length) {
        this.clearPlanRoute();
        return;
      }
      this.setPlanRoute(result.path);
    }

    refreshRouteGraph() {
      if (!this.corridorData || !this.vertiportData) {
        return;
      }
      const nodeLookup = new Map();
      this.corridorData.points.forEach((entry) => nodeLookup.set(entry.name, entry));
      this.vertiportData.points.forEach((entry) => nodeLookup.set(entry.name, entry));
      this.routeNodeLookup = nodeLookup;

      const nodes = Array.from(nodeLookup.values());
      if (!nodes.length) {
        return;
      }
      const lon0 = nodes.reduce((sum, entry) => sum + entry.coord[0], 0) / nodes.length;
      const lat0 = nodes.reduce((sum, entry) => sum + entry.coord[1], 0) / nodes.length;
      const kmPerDegLat = 111.32;
      const kmPerDegLon = 111.32 * Math.cos((lat0 * Math.PI) / 180);
      this.routeProjection = { lon0, lat0, kmPerDegLat, kmPerDegLon };
      const nodeXY = new Map();
      nodes.forEach((entry) => {
        const dx = (entry.coord[0] - lon0) * kmPerDegLon;
        const dy = (entry.coord[1] - lat0) * kmPerDegLat;
        nodeXY.set(entry.name, [dx, dy]);
      });
      this.routeNodeXY = nodeXY;

      const graph = new Map();
      const addEdge = (a, b) => {
        if (!graph.has(a)) {
          graph.set(a, new Set());
        }
        graph.get(a).add(b);
      };

      this.corridorData.lines.forEach((line) => {
        addEdge(line.from, line.to);
        addEdge(line.to, line.from);
      });
      this.vertiportData.lines.forEach((line) => {
        addEdge(line.from, line.to);
        addEdge(line.to, line.from);
      });

      const finalized = new Map();
      nodeLookup.forEach((_entry, name) => {
        finalized.set(name, graph.has(name) ? Array.from(graph.get(name)) : []);
      });
      this.routeGraph = finalized;
      this.updatePlanSelection();
      this.updateViaPoints();
      this.updateActiveEdges();
      this.updateManualPreview();
      this.updatePlanRoutePreview();
    }

    computePlanRoute() {
      const selection = this.planState.selection;
      if (!selection || selection.length < 2) {
        return null;
      }
      this.ensureRouteGraph();
      if (!this.routeGraph) {
        return null;
      }
      const start = selection[0];
      const end = selection[1];
      if (this.planState.mode === "manual" && this.planState.manualPath.length) {
        const manualPath = this.planState.manualPath;
        let total = 0;
        for (let i = 0; i < manualPath.length - 1; i += 1) {
          total += this.distanceKm(manualPath[i], manualPath[i + 1]);
        }
        const combined = [...manualPath];
        if (manualPath[manualPath.length - 1] !== end) {
          const tail = this.shortestPath(manualPath[manualPath.length - 1], end);
          if (!tail || !tail.path.length) {
            return null;
          }
          combined.push(...tail.path.slice(1));
          total += tail.distanceKm;
        }
        return { path: combined, distanceKm: total };
      }
      if (this.planState.mode === "via" && this.planState.viaNodes.length) {
        return this.findRouteVia(start, end, this.planState.viaNodes);
      }
      return this.shortestPath(start, end);
    }

    ensureRouteGraph() {
      if (this.routeGraph) {
        return;
      }
      if (!this.corridorData && this.lastCorridorRows) {
        this.corridorData = this.buildCorridorFeatures(this.lastCorridorRows);
        this.corridorPointLookup = new Map(
          this.corridorData.points.map((entry) => [entry.name, entry]),
        );
      }
      if (!this.vertiportData && this.lastVertiportRows) {
        this.vertiportData = this.buildVertiportFeatures(this.lastVertiportRows);
        this.vertiportPointLookup = new Map(
          this.vertiportData.points.map((entry) => [entry.name, entry]),
        );
        this.vertiportLinkLookup = new Map(
          this.vertiportData.points.map((entry) => [entry.name, entry.links || []]),
        );
      }
      if (this.corridorData && this.vertiportData) {
        this.refreshRouteGraph();
      }
    }

    findRouteVia(start, end, viaNodes) {
      const sequence = [start, ...viaNodes, end];
      let fullPath = [];
      let total = 0;
      for (let i = 0; i < sequence.length - 1; i += 1) {
        const segment = this.shortestPath(sequence[i], sequence[i + 1]);
        if (!segment || !segment.path.length) {
          return null;
        }
        if (fullPath.length) {
          fullPath = [...fullPath, ...segment.path.slice(1)];
        } else {
          fullPath = [...segment.path];
        }
        total += segment.distanceKm;
      }
      return { path: fullPath, distanceKm: total };
    }

    shortestPath(start, end) {
      if (!this.routeGraph || !this.routeGraph.has(start) || !this.routeGraph.has(end)) {
        return null;
      }
      if (start === end) {
        return { path: [start], distanceKm: 0 };
      }
      const dist = new Map([[start, 0]]);
      const prev = new Map([[start, null]]);
      const queue = [[0, start]];
      const isPort = (name) => this.vertiportPointLookup.has(name);

      while (queue.length) {
        queue.sort((a, b) => a[0] - b[0]);
        const [cost, node] = queue.shift();
        if (node === end) {
          break;
        }
        if (cost !== dist.get(node)) {
          continue;
        }
        const neighbors = this.routeGraph.get(node) || [];
        neighbors.forEach((nxt) => {
          if (isPort(nxt) && nxt !== end) {
            return;
          }
          const nextCost = cost + this.distanceKm(node, nxt);
          const existing = dist.get(nxt);
          if (existing === undefined || nextCost < existing) {
            dist.set(nxt, nextCost);
            prev.set(nxt, node);
            queue.push([nextCost, nxt]);
          }
        });
      }

      if (!dist.has(end)) {
        return null;
      }
      const path = [];
      let cur = end;
      while (cur) {
        path.push(cur);
        cur = prev.get(cur);
      }
      path.reverse();
      return { path, distanceKm: dist.get(end) || 0 };
    }

    distanceKm(a, b) {
      const axy = this.routeNodeXY.get(a);
      const bxy = this.routeNodeXY.get(b);
      if (!axy || !bxy) {
        return 0;
      }
      const dx = bxy[0] - axy[0];
      const dy = bxy[1] - axy[1];
      return Math.hypot(dx, dy);
    }

    ensurePlanLayers() {
      if (!this.map || !this.map.isStyleLoaded() || this.planLayersReady) {
        return;
      }
      const map = this.map;
      const empty = { type: "FeatureCollection", features: [] };
      if (!map.getSource("flight-plan-selection")) {
        map.addSource("flight-plan-selection", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-route")) {
        map.addSource("flight-plan-route", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-via")) {
        map.addSource("flight-plan-via", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-active-links")) {
        map.addSource("flight-plan-active-links", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-active-links-hit")) {
        map.addSource("flight-plan-active-links-hit", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-manual-preview")) {
        map.addSource("flight-plan-manual-preview", { type: "geojson", data: empty });
      }

      if (!map.getLayer("flight-plan-route")) {
        map.addLayer({
          id: "flight-plan-route",
          type: "line",
          source: "flight-plan-route",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#ff2fd6",
            "line-width": 2 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!map.getLayer("flight-plan-manual-preview")) {
        map.addLayer({
          id: "flight-plan-manual-preview",
          type: "line",
          source: "flight-plan-manual-preview",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#7cff62",
            "line-width": 2 * MAP_SIZE_SCALE,
            "line-dasharray": [1.5, 1.2],
          },
        });
      }

      if (!map.getLayer("flight-plan-active-links")) {
        map.addLayer({
          id: "flight-plan-active-links",
          type: "line",
          source: "flight-plan-active-links",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#7cff62",
            "line-width": 2.5 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!map.getLayer("flight-plan-active-links-hit")) {
        map.addLayer({
          id: "flight-plan-active-links-hit",
          type: "line",
          source: "flight-plan-active-links-hit",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#000000",
            "line-opacity": 0.01,
            "line-width": 10 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!map.getLayer("flight-plan-via-points")) {
        map.addLayer({
          id: "flight-plan-via-points",
          type: "circle",
          source: "flight-plan-via",
          paint: {
            "circle-radius": 6 * MAP_SIZE_SCALE,
            "circle-color": "#8d6bff",
            "circle-stroke-color": "#1a1a1a",
            "circle-stroke-width": 1.5 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!map.getLayer("flight-plan-selection")) {
        map.addLayer({
          id: "flight-plan-selection",
          type: "circle",
          source: "flight-plan-selection",
          paint: {
            "circle-radius": 7 * MAP_SIZE_SCALE,
            "circle-color": [
              "case",
              ["==", ["get", "role"], "start"],
              "#2ecc71",
              "#ff5f5f",
            ],
            "circle-stroke-color": "#1a1a1a",
            "circle-stroke-width": 2 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!this.planRouteLayer3d) {
        this.planRouteLayer3d = this.createLineLayer3d(
          "flight-plan-route-3d",
          "#ff2fd6",
          "LINE_STRIP",
        );
        map.addLayer(this.planRouteLayer3d);
      }

      if (!this.vertiportLinks3dLayer) {
        this.vertiportLinks3dLayer = this.createLineLayer3d(
          "vertiport-links-3d",
          VERTIPORT_LINE_COLOR,
          "LINES",
        );
        map.addLayer(this.vertiportLinks3dLayer);
      }
      this.reorderPlanLayers();
      this.planLayersReady = true;
    }

    reorderPlanLayers() {
      if (!this.map) {
        return;
      }
      [
        "vertiport-links-line",
        "vertiport-links-hit",
        "vertiport-circle",
        "vertiport-icon",
        "vertiport-hover-ring",
        "vertiport-links-3d",
        "flight-plan-route",
        "flight-plan-route-3d",
        "flight-plan-manual-preview",
        "flight-plan-active-links",
        "flight-plan-active-links-hit",
        "flight-plan-via-points",
        "flight-plan-selection",
      ].forEach((layerId) => {
        if (this.map.getLayer(layerId)) {
          this.map.moveLayer(layerId);
        }
      });
    }

    createLineLayer3d(id, color, drawModeName) {
      const layer = {
        id,
        type: "custom",
        renderingMode: "3d",
        _color: color,
        _drawModeName: drawModeName,
        _lineCount: 0,
        setColor(nextColor) {
          this._color = nextColor;
        },
        updatePositions(positions) {
          this._pendingPositions = positions;
          if (!this._gl || !this._lineBuffer) {
            return;
          }
          const gl = this._gl;
          const data = new Float32Array(positions);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
          this._lineCount = data.length / 3;
          this._pendingPositions = null;
        },
        onAdd(_map, gl) {
          this._gl = gl;
          const vertexSource = `
            attribute vec3 a_pos;
            uniform mat4 u_matrix;
            void main() {
              gl_Position = u_matrix * vec4(a_pos, 1.0);
            }
          `;
          const fragmentSource = `
            precision mediump float;
            uniform vec4 u_color;
            void main() {
              gl_FragColor = u_color;
            }
          `;
          const compile = (type, source) => {
            const shader = gl.createShader(type);
            gl.shaderSource(shader, source);
            gl.compileShader(shader);
            return shader;
          };
          const vertexShader = compile(gl.VERTEX_SHADER, vertexSource);
          const fragmentShader = compile(gl.FRAGMENT_SHADER, fragmentSource);
          const program = gl.createProgram();
          gl.attachShader(program, vertexShader);
          gl.attachShader(program, fragmentShader);
          gl.linkProgram(program);
          this._program = program;
          this._aPos = gl.getAttribLocation(program, "a_pos");
          this._uMatrix = gl.getUniformLocation(program, "u_matrix");
          this._uColor = gl.getUniformLocation(program, "u_color");

          this._lineBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([]), gl.STATIC_DRAW);
          this._lineCount = 0;
          this._drawMode =
            this._drawModeName === "LINE_STRIP" ? gl.LINE_STRIP : gl.LINES;

          if (this._pendingPositions) {
            this.updatePositions(this._pendingPositions);
          }
        },
        render(gl, matrix) {
          if (!this._program || !this._lineCount) {
            return;
          }
          gl.useProgram(this._program);
          gl.uniformMatrix4fv(this._uMatrix, false, matrix);
          gl.uniform4fv(this._uColor, hexToRgba(this._color, 0.95));
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.enableVertexAttribArray(this._aPos);
          gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          gl.lineWidth(2 * MAP_SIZE_SCALE);
          gl.drawArrays(this._drawMode, 0, this._lineCount);
        },
      };
      return layer;
    }

    setPlanRoute(path) {
      if (!this.map || !this.map.getSource("flight-plan-route")) {
        return;
      }
      const coords = path
        .map((name) => this.routeNodeLookup.get(name))
        .filter(Boolean)
        .map((entry) => entry.coord);
      const features =
        coords.length >= 2
          ? [
              {
                type: "Feature",
                geometry: { type: "LineString", coordinates: coords },
                properties: {},
              },
            ]
          : [];
      this.map.getSource("flight-plan-route").setData({
        type: "FeatureCollection",
        features,
      });
      this.setPlanRoute3dPositions(path);
    }

    clearPlanRoute() {
      if (this.map && this.map.getSource("flight-plan-route")) {
        this.map.getSource("flight-plan-route").setData({
          type: "FeatureCollection",
          features: [],
        });
      }
      this.setPlanRoute3dPositions([]);
    }

    setPlanRoute3dPositions(path) {
      if (!this.planLayersReady) {
        this.ensurePlanLayers();
      }
      if (!this.planRouteLayer3d || !this.planRouteLayer3d.updatePositions || !this.map) {
        return;
      }
      const positions = [];
      path.forEach((name) => {
        const entry = this.routeNodeLookup.get(name);
        if (!entry) {
          return;
        }
        const altitude = this.resolveNodeAltitude(name);
        const merc = maplibregl.MercatorCoordinate.fromLngLat(entry.coord, altitude);
        positions.push(merc.x, merc.y, merc.z);
      });
      this.planRouteLayer3d.updatePositions(positions);
      this.map.triggerRepaint();
    }

    updateVertiportLinks3dLayer(data) {
      if (!this.planLayersReady) {
        this.ensurePlanLayers();
      }
      if (!this.vertiportLinks3dLayer || !this.map) {
        return;
      }
      const positions = [];
      data.lines.forEach((line) => {
        const startAlt = line.start.altitude_m ?? 0;
        const endAlt = line.end.altitude_m ?? 0;
        const start = maplibregl.MercatorCoordinate.fromLngLat(line.start.coord, startAlt);
        const end = maplibregl.MercatorCoordinate.fromLngLat(line.end.coord, endAlt);
        positions.push(start.x, start.y, start.z, end.x, end.y, end.z);
      });
      if (this.vertiportLinks3dLayer.updatePositions) {
        this.vertiportLinks3dLayer.updatePositions(positions);
      }
      this.map.triggerRepaint();
    }

    resolveNodeAltitude(name) {
      const corridor = this.corridorPointLookup.get(name);
      if (corridor && Number.isFinite(corridor.altitude_m)) {
        return corridor.altitude_m;
      }
      const port = this.vertiportPointLookup.get(name);
      if (port && Number.isFinite(port.altitude_m)) {
        return port.altitude_m;
      }
      return 0;
    }

    computeUeMeters(lat, lon, altitude_m) {
      const [absX, absY, absZ] = this.airsimConverter.geodeticToUe(lat, lon, altitude_m);
      const [chx, chy, chz] = this.airsimConverter.cityHall;
      return [(absX - chx) / 100.0, (absY - chy) / 100.0, (absZ - chz) / 100.0];
    }

    resolveNodeGeodetic(name) {
      const resource = this.vertiportResourceLookup.get(name);
      if (resource) {
        const lat = Number(resource.lat);
        const lon = Number(resource.lon);
        const alt =
          resource.alt_m != null && Number.isFinite(resource.alt_m)
            ? Number(resource.alt_m)
            : this.resolveNodeAltitude(name);
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          return {
            lat,
            lon,
            altitude_m: alt,
            ue_x: resource.ue_x,
            ue_y: resource.ue_y,
            ue_z: resource.ue_z,
          };
        }
      }
      const entry = this.routeNodeLookup.get(name);
      if (!entry) {
        return null;
      }
      const [lon, lat] = entry.coord;
      const altitude = this.resolveNodeAltitude(name);
      return { lat, lon, altitude_m: altitude };
    }

    buildPlanPoints(path) {
      const points = [];
      path.forEach((name) => {
        const geo = this.resolveNodeGeodetic(name);
        if (!geo) {
          return;
        }
        const { lat, lon, altitude_m } = geo;
        const [n, e, d] = this.airsimConverter.wgs84ToAirsimNed(lat, lon, altitude_m);
        let ueX = geo.ue_x;
        let ueY = geo.ue_y;
        let ueZ = geo.ue_z;
        if (
          !Number.isFinite(ueX) ||
          !Number.isFinite(ueY) ||
          !Number.isFinite(ueZ)
        ) {
          [ueX, ueY, ueZ] = this.computeUeMeters(lat, lon, altitude_m);
        }
        points.push({
          name,
          lat,
          lon,
          altitude_m,
          ue_x: ueX,
          ue_y: ueY,
          ue_z: ueZ,
          n,
          e,
          d,
        });
      });
      return points;
    }

    printPlanRoute(planPoints) {
      if (!planPoints || !planPoints.length) {
        console.warn("[Flight Plan] empty.");
        return;
      }
      const format = (value, digits) =>
        Number.isFinite(value) ? Number(value).toFixed(digits) : "";
      console.warn("[Flight Plan]");
      planPoints.forEach((point) => {
        const lat = format(point.lat, 6);
        const lon = format(point.lon, 6);
        const alt = format(point.altitude_m, 3);
        const ux = format(point.ue_x, 3);
        const uy = format(point.ue_y, 3);
        const uz = format(point.ue_z, 3);
        console.warn(`${point.name} : ${lat} : ${lon} : ${alt} : ${ux} : ${uy} : ${uz}`);
      });
    }

    captureHomeView() {
      if (!this.map) {
        return;
      }
      const center = this.map.getCenter();
      this.homeView = {
        center: [center.lng, center.lat],
        zoom: this.map.getZoom(),
        bearing: this.map.getBearing(),
        pitch: this.map.getPitch(),
      };
    }

    resetView() {
      if (!this.map) {
        return;
      }
      if (this.centerOnTelemetry()) {
        return;
      }
      if (!this.homeView) {
        return;
      }
      this.map.easeTo({
        center: this.homeView.center,
        zoom: this.homeView.zoom,
        bearing: this.homeView.bearing,
        pitch: this.homeView.pitch,
        duration: 400,
      });
    }

    centerOnTelemetry() {
      if (!this.map || !this.telemetryPosition) {
        return false;
      }
      const zoom = Math.max(this.map.getZoom(), 15);
      this.map.easeTo({
        center: this.telemetryPosition,
        zoom,
        duration: 500,
      });
      return true;
    }

    togglePanel(name) {
      const panel = this.panels[name];
      if (!panel) {
        return;
      }
      const isVisible = panel.classList.contains("is-visible");
      if (isVisible) {
        this.hidePanel(name);
      } else {
        this.showPanel(name);
      }
    }

    showPanel(name) {
      Object.entries(this.panels).forEach(([key, panel]) => {
        const isTarget = key === name;
        panel.classList.toggle("is-visible", isTarget);
        panel.setAttribute("aria-hidden", isTarget ? "false" : "true");
        this.setActionButtonActive(key, isTarget);
      });
    }

    hidePanel(name) {
      const panel = this.panels[name];
      if (!panel) {
        return;
      }
      panel.classList.remove("is-visible");
      panel.setAttribute("aria-hidden", "true");
      this.setActionButtonActive(name, false);
    }

    setActionButtonActive(action, isActive) {
      this.actionButtons.forEach((button) => {
        if (button.dataset.action === action) {
          button.classList.toggle("is-active", isActive);
        }
      });
    }

    setTheme(theme) {
      if (theme === this.currentTheme) {
        return;
      }
      this.currentTheme = theme;
      this.applyTheme(theme);
    }

    applyTheme(theme) {
      const isDark = theme === "dark";
      this.mapContainer.classList.toggle("theme-dark", isDark);
      this.themeButtons.forEach((button) => {
        button.classList.toggle("is-active", button.dataset.theme === theme);
      });
      this.updateMapTheme(theme);
      this.updateCorridorTheme(theme);
    }

    getCorridorColor(theme) {
      return theme === "dark" ? "#0efcff" : "#2c6dff";
    }

    updateMapTheme(theme) {
      if (!this.map || !this.map.isStyleLoaded()) {
        return;
      }
      const palette = BASE_MAP_PALETTES[theme] || BASE_MAP_PALETTES.light;
      this.map.setPaintProperty("background", "background-color", palette.background);
      this.map.setPaintProperty("landcover", "fill-color", palette.landcover);
      this.map.setPaintProperty("landuse", "fill-color", palette.landuse);
      this.map.setPaintProperty("park", "fill-color", palette.park);
      this.map.setPaintProperty("water", "fill-color", palette.water);
      this.map.setPaintProperty("waterway", "line-color", palette.waterway);
      this.map.setPaintProperty("boundary", "line-color", palette.boundary);
      this.map.setPaintProperty("transportation", "line-color", palette.transportation);
      this.map.setPaintProperty("building", "fill-color", palette.building);
    }

    updateCorridorTheme(theme) {
      if (!this.map) {
        return;
      }
      const color = this.getCorridorColor(theme);
      if (this.corridorLayer && this.corridorLayer.setColor) {
        this.corridorLayer.setColor(color);
        this.map.triggerRepaint();
      }
    }

    async loadVertiportOverlay() {
      if (!this.map) {
        return;
      }
      try {
        console.warn(`[Vertiport] loading ${this.config.data.vertiportCsv}`);
        const rows = await this.fetchCsvRows(this.config.data.vertiportCsv);
        console.warn(`[Vertiport] loaded ${rows.length} rows.`);
        this.updateVertiportOverlayFromRows(rows);
      } catch (error) {
        console.warn("Failed to load vertiport overlay.", error);
      }
    }

    async loadResourcesVp() {
      if (this.resourcesVpLoaded) {
        return;
      }
      this.resourcesVpLoaded = true;
      try {
        const response = await fetch("/data/resources_vp.csv", { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        const text = await response.text();
        const rows = normalizeRows(parseCsvRows(text));
        if (!rows.length) {
          return;
        }
        const header = rows[0].map((cell) => cell.trim().toLowerCase());
        const idxVertiport = header.indexOf("vertiport");
        const idxLabel = header.indexOf("label");
        const idxZ = header.indexOf("z_m");
        const idxXm = header.indexOf("x_m");
        const idxYm = header.indexOf("y_m");
        const idxXcm = header.indexOf("x_cm");
        const idxYcm = header.indexOf("y_cm");
        const idxZcm = header.indexOf("z_cm");
        const idxLat = header.indexOf("pt_lat_deg");
        const idxLon = header.indexOf("pt_lon_deg");
        if (idxVertiport < 0 || idxLabel < 0 || idxZ < 0) {
          return;
        }
        const altLookup = new Map();
        const resourceLookup = new Map();
        const readNumber = (row, index) => {
          if (index < 0) {
            return NaN;
          }
          const value = Number.parseFloat(readCell(row, index));
          return Number.isFinite(value) ? value : NaN;
        };
        rows.slice(1).forEach((row) => {
          const vp = readCell(row, idxVertiport);
          const label = readCell(row, idxLabel).toUpperCase();
          if (!vp || label !== "FATO 2") {
            return;
          }
          const z = readNumber(row, idxZ);
          if (Number.isFinite(z)) {
            altLookup.set(vp, z);
          }
          const lat = readNumber(row, idxLat);
          const lon = readNumber(row, idxLon);
          const ueX = readNumber(row, idxXm);
          const ueY = readNumber(row, idxYm);
          const ueZ = readNumber(row, idxZ);
          const ueXcm = readNumber(row, idxXcm);
          const ueYcm = readNumber(row, idxYcm);
          const ueZcm = readNumber(row, idxZcm);
          const resolvedUx = Number.isFinite(ueX)
            ? ueX
            : Number.isFinite(ueXcm)
              ? ueXcm / 100.0
              : null;
          const resolvedUy = Number.isFinite(ueY)
            ? ueY
            : Number.isFinite(ueYcm)
              ? ueYcm / 100.0
              : null;
          const resolvedUz = Number.isFinite(ueZ)
            ? ueZ
            : Number.isFinite(ueZcm)
              ? ueZcm / 100.0
              : null;
          if (Number.isFinite(lat) && Number.isFinite(lon)) {
            resourceLookup.set(vp, {
              lat,
              lon,
              alt_m: Number.isFinite(z) ? z : null,
              ue_x: resolvedUx,
              ue_y: resolvedUy,
              ue_z: resolvedUz,
            });
          }
        });
        if (altLookup.size) {
          this.vertiportAltLookup = altLookup;
          if (this.lastVertiportRows) {
            this.updateVertiportOverlayFromRows(this.lastVertiportRows);
          }
        }
        if (resourceLookup.size) {
          this.vertiportResourceLookup = resourceLookup;
        }
      } catch (error) {
        console.warn("Failed to load resources_vp.csv.", error);
      }
    }

    ensureVertiportIcon() {
      if (!this.map) {
        return Promise.resolve(false);
      }
      if (this.vertiportIconPromise) {
        return this.vertiportIconPromise;
      }
      if (this.map.hasImage(VERTIPORT_ICON_ID)) {
        this.vertiportIconPromise = Promise.resolve(true);
        return this.vertiportIconPromise;
      }
      this.vertiportIconPromise = new Promise((resolve) => {
        this.map.loadImage("/resources/v_sign.png", (error, image) => {
          if (!error && image && !this.map.hasImage(VERTIPORT_ICON_ID)) {
            this.map.addImage(VERTIPORT_ICON_ID, image);
          }
          if (!error) {
            this.addVertiportIconLayer();
          }
          resolve(!error);
        });
      });
      return this.vertiportIconPromise;
    }

    updateVertiportOverlayFromRows(rows) {
      this.lastVertiportRows = rows;
      this.clearVertiportHover();
      this.setVertiportHoverFilter(null);
      if (!this.map || !this.map.isStyleLoaded()) {
        this.pendingVertiportRows = rows;
        return;
      }
      this.pendingVertiportRows = null;
      const data = this.buildVertiportFeatures(rows);
      this.vertiportData = data;
      this.vertiportPointLookup = new Map(data.points.map((entry) => [entry.name, entry]));
      this.vertiportLinkLookup = new Map(
        data.points.map((entry) => [entry.name, entry.links || []]),
      );
      this.refreshRouteGraph();
      const applyLayers = () => {
        this.setVertiportLayers(data);
        this.setVertiportLabels(data.points);
        this.updateVertiportLinks3dLayer(data);
        this.map.triggerRepaint();
        this.reorderPlanLayers();
      };
      if (this.map.hasImage(VERTIPORT_ICON_ID)) {
        applyLayers();
        return;
      }
      this.ensureVertiportIcon().then(applyLayers);
    }

    buildVertiportFeatures(rows) {
      const points = [];
      const lines = [];
      const lookup = new Map();
      const corridorLookup = this.corridorPointLookup || new Map();
      const linkStats = {
        total: 0,
        resolved: 0,
        missing: new Set(),
      };
      const parseLinks = (row) => {
        const linkCell = readCell(row, Math.max(0, row.length - 1));
        if (!linkCell) {
          return [];
        }
        return linkCell
          .split(",")
          .map((value) => value.trim())
          .filter((value) => value.length > 0);
      };

      rows.forEach((row) => {
        const name = readCell(row, 0);
        const lat = Number.parseFloat(readCell(row, 2));
        const lon = Number.parseFloat(readCell(row, 3));
        if (!name || !Number.isFinite(lat) || !Number.isFinite(lon)) {
          return;
        }
        const altitude = this.vertiportAltLookup.get(name);
        const entry = {
          id: name,
          name,
          coord: [lon, lat],
          className: readCell(row, 1),
          altitude_m: altitude ?? 0,
          links: parseLinks(row),
        };
        lookup.set(name, entry);
        points.push(entry);
      });

      const seen = new Set();
      let lineIndex = 0;
      rows.forEach((row) => {
        const name = readCell(row, 0);
        const startEntry = lookup.get(name);
        if (!startEntry) {
          return;
        }
        if (!startEntry.links || startEntry.links.length === 0) {
          return;
        }
        startEntry.links.forEach((target) => {
          if (!target) {
            return;
          }
          linkStats.total += 1;
          const endEntry = corridorLookup.get(target) || lookup.get(target);
          if (!endEntry) {
            linkStats.missing.add(target);
            return;
          }
          linkStats.resolved += 1;
          const key = [name, target].sort().join("|");
          if (seen.has(key)) {
            return;
          }
          seen.add(key);
          lines.push({
            id: lineIndex,
            from: name,
            to: target,
            start: startEntry,
            end: endEntry,
          });
          lineIndex += 1;
        });
      });

      if (linkStats.total) {
        const missing = Array.from(linkStats.missing);
        console.warn(
          `[Vertiport Links] corridor nodes: ${corridorLookup.size}, resolved ${linkStats.resolved}/${linkStats.total}, unique lines: ${lines.length}.`,
        );
        if (missing.length) {
          console.warn("[Vertiport Links] missing targets:", missing);
        }
      } else {
        console.warn("[Vertiport Links] no link entries found.");
      }
      return { points, lines };
    }

    buildVertiportPointGeoJson(points) {
      return {
        type: "FeatureCollection",
        features: points.map((entry) => ({
          type: "Feature",
          id: entry.id,
          geometry: {
            type: "Point",
            coordinates: entry.coord,
          },
          properties: {
            name: entry.name,
            class: entry.className || "",
          },
        })),
      };
    }

    buildVertiportLineGeoJson(lines) {
      return {
        type: "FeatureCollection",
        features: lines.map((line) => ({
          type: "Feature",
          id: line.id,
          geometry: {
            type: "LineString",
            coordinates: [line.start.coord, line.end.coord],
          },
          properties: {
            from: line.from,
            to: line.to,
            name: `${line.from} - ${line.to}`,
          },
        })),
      };
    }

    setVertiportLayers(data) {
      const map = this.map;
      if (!map) {
        return;
      }
      const pointSourceId = "vertiport-points";
      const lineSourceId = "vertiport-links";
      const pointData = this.buildVertiportPointGeoJson(data.points);
      const lineData = this.buildVertiportLineGeoJson(data.lines);

      if (map.getSource(pointSourceId)) {
        map.getSource(pointSourceId).setData(pointData);
      } else {
        map.addSource(pointSourceId, { type: "geojson", data: pointData });
      }

      if (map.getSource(lineSourceId)) {
        map.getSource(lineSourceId).setData(lineData);
      } else {
        map.addSource(lineSourceId, { type: "geojson", data: lineData });
      }

      const beforeId = map.getLayer("corridor-3d") ? "corridor-3d" : undefined;
      if (!map.getLayer("vertiport-links-line")) {
        map.addLayer(
          {
            id: "vertiport-links-line",
            type: "line",
            source: lineSourceId,
            layout: {
              "line-join": "round",
              "line-cap": "round",
            },
            paint: {
              "line-color": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                "#8dffbb",
                VERTIPORT_LINE_COLOR,
              ],
              "line-width": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                3 * MAP_SIZE_SCALE,
                2 * MAP_SIZE_SCALE,
              ],
              "line-dasharray": [1.5, 1.5],
              "line-opacity": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                1,
                0.9,
              ],
            },
          },
          beforeId,
        );
      }

      if (!map.getLayer("vertiport-links-hit")) {
        map.addLayer(
          {
            id: "vertiport-links-hit",
            type: "line",
            source: lineSourceId,
            layout: {
              "line-join": "round",
              "line-cap": "round",
            },
            paint: {
              "line-color": "#000000",
              "line-opacity": 0.01,
              "line-width": 10 * MAP_SIZE_SCALE,
            },
          },
          beforeId,
        );
      }

      if (!map.getLayer("vertiport-circle")) {
        map.addLayer(
          {
            id: "vertiport-circle",
            type: "circle",
            source: pointSourceId,
            paint: {
              "circle-radius": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                10 * MAP_SIZE_SCALE,
                8 * MAP_SIZE_SCALE,
              ],
              "circle-color": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                "#f2fff8",
                "#ffffff",
              ],
              "circle-stroke-color": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                "#8dffbb",
                "#1a1a1a",
              ],
              "circle-stroke-width": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                3 * MAP_SIZE_SCALE,
                1 * MAP_SIZE_SCALE,
              ],
            },
          },
          beforeId,
        );
      }

      if (map.hasImage(VERTIPORT_ICON_ID)) {
        this.addVertiportIconLayer(beforeId);
      }
      this.addVertiportHoverRing(beforeId);
    }

    addVertiportHoverRing(beforeId) {
      const map = this.map;
      if (!map || !map.getSource("vertiport-points")) {
        return;
      }
      if (map.getLayer("vertiport-hover-ring")) {
        return;
      }
      map.addLayer(
        {
          id: "vertiport-hover-ring",
          type: "circle",
          source: "vertiport-points",
          filter: ["==", ["get", "name"], ""],
          paint: {
            "circle-radius": 12 * MAP_SIZE_SCALE,
            "circle-color": "#000000",
            "circle-opacity": 0,
            "circle-stroke-color": "#8dffbb",
            "circle-stroke-opacity": 0.95,
            "circle-stroke-width": 3.5 * MAP_SIZE_SCALE,
          },
        },
        beforeId,
      );
    }

    setVertiportHoverFilter(name) {
      if (!this.map || !this.map.getLayer("vertiport-hover-ring")) {
        return;
      }
      if (this.vertiportHoverName === name) {
        return;
      }
      this.vertiportHoverName = name || "";
      this.map.setFilter("vertiport-hover-ring", [
        "==",
        ["get", "name"],
        this.vertiportHoverName,
      ]);
    }

    clearVertiportLabels() {
      this.vertiportLabels.forEach((marker) => marker.remove());
      this.vertiportLabels = [];
    }

    setVertiportLabels(points) {
      if (!this.map) {
        return;
      }
      this.clearVertiportLabels();
      points.forEach((entry) => {
        const label = document.createElement("div");
        label.className = "vertiport-static-label";
        label.textContent = entry.name;
        const marker = new maplibregl.Marker({
          element: label,
          anchor: "top",
          offset: [0, 8 * MAP_SIZE_SCALE],
        })
          .setLngLat(entry.coord)
          .addTo(this.map);
        this.vertiportLabels.push(marker);
      });
    }

    addVertiportIconLayer(beforeId) {
      const map = this.map;
      if (!map || !map.getSource("vertiport-points")) {
        return;
      }
      if (map.getLayer("vertiport-icon")) {
        return;
      }
      map.addLayer(
        {
          id: "vertiport-icon",
          type: "symbol",
          source: "vertiport-points",
          layout: {
            "icon-image": VERTIPORT_ICON_ID,
            "icon-size": 0.04 * MAP_SIZE_SCALE,
            "icon-allow-overlap": true,
            "icon-anchor": "center",
            "icon-rotation-alignment": "viewport",
            "icon-pitch-alignment": "viewport",
          },
        },
        beforeId,
      );
    }

    async loadCorridorOverlay() {
      if (!this.map) {
        return;
      }
      try {
        console.warn(`[Corridor] loading ${this.config.data.waypointCsv}`);
        const rows = await this.fetchCsvRows(this.config.data.waypointCsv);
        console.warn(`[Corridor] loaded ${rows.length} rows.`);
        this.updateCorridorOverlayFromRows(rows);
      } catch (error) {
        console.warn("Failed to load corridor overlay.", error);
      }
    }

    ensureCorridorReady() {
      if (!this.map || this.corridorEnsured) {
        return;
      }
      this.corridorEnsured = true;
      if (this.pendingCorridorRows) {
        const rows = this.pendingCorridorRows;
        this.pendingCorridorRows = null;
        this.updateCorridorOverlayFromRows(rows);
        return;
      }
      if (this.lastCorridorRows) {
        this.updateCorridorOverlayFromRows(this.lastCorridorRows);
        return;
      }
      const info = this.defaultFiles.corridor;
      if (info && info.url) {
        this.loadCorridorData(info.url);
      }
    }

    updateCorridorOverlayFromRows(rows) {
      this.lastCorridorRows = rows;
      if (!this.map || !this.map.isStyleLoaded()) {
        this.pendingCorridorRows = rows;
        return;
      }
      this.pendingCorridorRows = null;
      const data = this.buildCorridorFeatures(rows);
      console.warn(
        `[Corridor] points: ${data.points.length}, links: ${data.lines.length}.`,
      );
      this.corridorData = data;
      this.corridorPointLookup = new Map(data.points.map((entry) => [entry.name, entry]));
      this.corridorHitData = this.buildCorridorHitData(data);
      this.clearCorridorHover();
      this.refreshRouteGraph();
      const hasLayer =
        this.corridorLayer && this.map.getLayer && this.map.getLayer(this.corridorLayer.id);
      if (hasLayer && this.corridorLayer.updateBuffers) {
        const buffers = this.buildCorridorBuffers(data);
        this.corridorLayer.updateBuffers(buffers);
      } else {
        this.setCorridorLayer(data);
      }
      this.updateCorridorTheme(this.currentTheme);
      this.map.triggerRepaint();
      this.reorderPlanLayers();
      requestAnimationFrame(() => {
        if (this.map) {
          this.map.triggerRepaint();
        }
      });
      if (this.lastVertiportRows) {
        this.updateVertiportOverlayFromRows(this.lastVertiportRows);
      }
    }

    buildCorridorFeatures(rows) {
      const points = [];
      const lines = [];
      const lookup = new Map();
      rows.forEach((row) => {
        const name = readCell(row, 0);
        const lat = Number.parseFloat(readCell(row, 1));
        const lon = Number.parseFloat(readCell(row, 2));
        if (!name || !Number.isFinite(lat) || !Number.isFinite(lon)) {
          return;
        }
        const altitudeMeters = parseAltitudeMeters(readCell(row, 3));
        const coord = [lon, lat];
        const entry = { name, coord, altitude_m: altitudeMeters ?? 0 };
        lookup.set(name, entry);
        points.push(entry);
      });

      const seen = new Set();
      rows.forEach((row) => {
        const name = readCell(row, 0);
        const startEntry = lookup.get(name);
        if (!startEntry) {
          return;
        }
        const linkCell = readCell(row, 4);
        if (!linkCell) {
          return;
        }
        linkCell.split(",").forEach((raw) => {
          const target = raw.trim();
          if (!target) {
            return;
          }
          const endEntry = lookup.get(target);
          if (!endEntry) {
            return;
          }
          const key = [name, target].sort().join("|");
          if (seen.has(key)) {
            return;
          }
          seen.add(key);
          lines.push({
            from: name,
            to: target,
            start: startEntry,
            end: endEntry,
          });
        });
      });

      return { points, lines };
    }

    setCorridorLayer(data) {
      const map = this.map;
      if (!map) {
        return;
      }
      if (this.corridorLayer && map.getLayer(this.corridorLayer.id)) {
        return;
      }
      const layer = this.createCorridorLayer(data);
      this.corridorLayer = layer;
      map.addLayer(layer);
    }

    buildCorridorBuffers(data) {
      const pointPositions = [];
      const linePositions = [];
      data.points.forEach((entry) => {
        const merc = maplibregl.MercatorCoordinate.fromLngLat(
          entry.coord,
          entry.altitude_m ?? 0,
        );
        pointPositions.push(merc.x, merc.y, merc.z);
      });
      data.lines.forEach((line) => {
        const startAlt = line.start.altitude_m ?? 0;
        const endAlt = line.end.altitude_m ?? 0;
        const start = maplibregl.MercatorCoordinate.fromLngLat(line.start.coord, startAlt);
        const end = maplibregl.MercatorCoordinate.fromLngLat(line.end.coord, endAlt);
        linePositions.push(start.x, start.y, start.z, end.x, end.y, end.z);
      });
      return {
        pointPositions,
        linePositions,
      };
    }

    buildCorridorHitData(data) {
      const points = data.points.map((entry, index) => {
        const altitude = entry.altitude_m ?? 0;
        const mercator = maplibregl.MercatorCoordinate.fromLngLat(entry.coord, altitude);
        return {
          index,
          name: entry.name,
          coord: entry.coord,
          altitude_m: altitude,
          mercator,
        };
      });
      const lines = data.lines.map((line, index) => {
        const startAlt = line.start.altitude_m ?? 0;
        const endAlt = line.end.altitude_m ?? 0;
        const mercStart = maplibregl.MercatorCoordinate.fromLngLat(line.start.coord, startAlt);
        const mercEnd = maplibregl.MercatorCoordinate.fromLngLat(line.end.coord, endAlt);
        return {
          index,
          name: `${line.from} - ${line.to}`,
          start: line.start,
          end: line.end,
          mercStart,
          mercEnd,
        };
      });
      return { points, lines };
    }

    projectMercatorToScreen(mercator, matrix) {
      if (!this.map || !mercator || !matrix) {
        return null;
      }
      const x = mercator.x;
      const y = mercator.y;
      const z = mercator.z;
      const w = 1;
      const clipX = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12] * w;
      const clipY = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13] * w;
      const clipW = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15] * w;
      if (!Number.isFinite(clipW) || clipW === 0) {
        return null;
      }
      const ndcX = clipX / clipW;
      const ndcY = clipY / clipW;
      const canvas = this.map.getCanvas();
      const pixelRatio =
        canvas.clientWidth > 0 ? canvas.width / canvas.clientWidth : window.devicePixelRatio || 1;
      const width = canvas.width / pixelRatio;
      const height = canvas.height / pixelRatio;
      return {
        x: (ndcX + 1) * 0.5 * width,
        y: (1 - ndcY) * 0.5 * height,
      };
    }

    distanceToSegment(point, start, end) {
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      if (dx === 0 && dy === 0) {
        return Math.hypot(point.x - start.x, point.y - start.y);
      }
      const t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy);
      const clamped = Math.max(0, Math.min(1, t));
      const projX = start.x + clamped * dx;
      const projY = start.y + clamped * dy;
      return Math.hypot(point.x - projX, point.y - projY);
    }

    findCorridorHoverTarget(pointer, matrix) {
      if (!this.corridorHitData) {
        return null;
      }
      const pointThreshold = 10 * MAP_SIZE_SCALE;
      const lineThreshold = 8 * MAP_SIZE_SCALE;
      let bestPoint = null;
      let bestPointDist = Infinity;
      this.corridorHitData.points.forEach((entry) => {
        const screen = this.projectMercatorToScreen(entry.mercator, matrix);
        if (!screen) {
          return;
        }
        const dist = Math.hypot(pointer.x - screen.x, pointer.y - screen.y);
        if (dist <= pointThreshold && dist < bestPointDist) {
          bestPointDist = dist;
          bestPoint = {
            type: "point",
            index: entry.index,
            name: entry.name,
          };
        }
      });
      if (bestPoint) {
        return bestPoint;
      }
      let bestLine = null;
      let bestLineDist = Infinity;
      this.corridorHitData.lines.forEach((entry) => {
        const start = this.projectMercatorToScreen(entry.mercStart, matrix);
        const end = this.projectMercatorToScreen(entry.mercEnd, matrix);
        if (!start || !end) {
          return;
        }
        const dist = this.distanceToSegment(pointer, start, end);
        if (dist <= lineThreshold && dist < bestLineDist) {
          bestLineDist = dist;
          bestLine = {
            type: "line",
            index: entry.index,
            name: entry.name,
          };
        }
      });
      return bestLine;
    }

    createCorridorLayer(data) {
      const buffers = this.buildCorridorBuffers(data);
      const color = this.getCorridorColor(this.currentTheme);
      const pointSize = 6 * MAP_SIZE_SCALE * (window.devicePixelRatio || 1);
      const layer = {
        id: "corridor-3d",
        type: "custom",
        renderingMode: "3d",
        _color: color,
        _pointSize: pointSize,
        _hoverPoint: -1,
        _hoverLine: -1,
        _highlightColor: HOVER_OUTLINE_COLOR,
        _hoverPointSize: 6 * MAP_SIZE_SCALE * (window.devicePixelRatio || 1),
        _ringWidth: 0.12,
        setColor(nextColor) {
          this._color = nextColor;
        },
        updateBuffers(nextBuffers) {
          this._pendingBuffers = nextBuffers;
          if (!this._gl || !this._pointBuffer || !this._lineBuffer) {
            return;
          }
          const gl = this._gl;
          const pointData = new Float32Array(nextBuffers.pointPositions);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, pointData, gl.STATIC_DRAW);
          this._pointCount = pointData.length / 3;

          const lineData = new Float32Array(nextBuffers.linePositions);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, lineData, gl.STATIC_DRAW);
          this._lineCount = lineData.length / 3;
          this._pendingBuffers = null;
        },
        setHover(hover) {
          this._hoverPoint = hover && hover.type === "point" ? hover.index : -1;
          this._hoverLine = hover && hover.type === "line" ? hover.index : -1;
        },
        clearHover() {
          this._hoverPoint = -1;
          this._hoverLine = -1;
        },
        getMatrix() {
          return this._lastMatrix;
        },
        onAdd(_map, gl) {
          this._gl = gl;
          const vertexSource = `
            attribute vec3 a_pos;
            uniform mat4 u_matrix;
            uniform float u_pointSize;
            void main() {
              gl_Position = u_matrix * vec4(a_pos, 1.0);
              gl_PointSize = u_pointSize;
            }
          `;
          const fragmentSource = `
            precision mediump float;
            uniform vec4 u_color;
            uniform float u_isPoint;
            uniform float u_ring;
            uniform float u_ringWidth;
            void main() {
              if (u_isPoint > 0.5) {
                float dist = length(gl_PointCoord - vec2(0.5));
                if (dist > 0.5) {
                  discard;
                }
                if (u_ring > 0.5) {
                  if (dist < (0.5 - u_ringWidth)) {
                    discard;
                  }
                }
              }
              gl_FragColor = u_color;
            }
          `;
          const compile = (type, source) => {
            const shader = gl.createShader(type);
            gl.shaderSource(shader, source);
            gl.compileShader(shader);
            return shader;
          };
          const vertexShader = compile(gl.VERTEX_SHADER, vertexSource);
          const fragmentShader = compile(gl.FRAGMENT_SHADER, fragmentSource);
          const program = gl.createProgram();
          gl.attachShader(program, vertexShader);
          gl.attachShader(program, fragmentShader);
          gl.linkProgram(program);
          this._program = program;
          this._aPos = gl.getAttribLocation(program, "a_pos");
          this._uMatrix = gl.getUniformLocation(program, "u_matrix");
          this._uColor = gl.getUniformLocation(program, "u_color");
          this._uPointSize = gl.getUniformLocation(program, "u_pointSize");
          this._uIsPoint = gl.getUniformLocation(program, "u_isPoint");
          this._uRing = gl.getUniformLocation(program, "u_ring");
          this._uRingWidth = gl.getUniformLocation(program, "u_ringWidth");

          this._pointBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.bufferData(
            gl.ARRAY_BUFFER,
            new Float32Array(buffers.pointPositions),
            gl.STATIC_DRAW,
          );
          this._pointCount = buffers.pointPositions.length / 3;

          this._lineBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(
            gl.ARRAY_BUFFER,
            new Float32Array(buffers.linePositions),
            gl.STATIC_DRAW,
          );
          this._lineCount = buffers.linePositions.length / 3;

          if (this._pendingBuffers) {
            this.updateBuffers(this._pendingBuffers);
          }
        },
        render(gl, matrix) {
          if (!this._program) {
            return;
          }
          this._lastMatrix = matrix;
          gl.useProgram(this._program);
          gl.uniformMatrix4fv(this._uMatrix, false, matrix);
          gl.uniform1f(this._uPointSize, this._pointSize);
          gl.uniform1f(this._uRing, 0);
          gl.uniform1f(this._uRingWidth, this._ringWidth);
          gl.enableVertexAttribArray(this._aPos);
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

          const color = hexToRgba(this._color, 0.95);
          gl.uniform4fv(this._uColor, color);

          if (this._lineCount > 0) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform1f(this._uIsPoint, 0);
            gl.lineWidth(1 * MAP_SIZE_SCALE);
            gl.drawArrays(gl.LINES, 0, this._lineCount);
          }

          if (this._pointCount > 0) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform1f(this._uIsPoint, 1);
            gl.drawArrays(gl.POINTS, 0, this._pointCount);
          }

          const highlightColor = hexToRgba(this._highlightColor, 0.95);
          if (this._hoverLine > -1) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform4fv(this._uColor, highlightColor);
            gl.uniform1f(this._uIsPoint, 0);
            gl.uniform1f(this._uRing, 0);
            gl.lineWidth(2 * MAP_SIZE_SCALE);
            gl.drawArrays(gl.LINES, this._hoverLine * 2, 2);
          }

          if (this._hoverPoint > -1) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform4fv(this._uColor, highlightColor);
            gl.uniform1f(this._uIsPoint, 1);
            gl.uniform1f(this._uRing, 1);
            gl.uniform1f(this._uPointSize, this._pointSize + this._hoverPointSize);
            gl.drawArrays(gl.POINTS, this._hoverPoint, 1);
          }
        },
      };
      return layer;
    }

    setupCorridorHover() {
      if (!this.map) {
        return;
      }
      const label = document.createElement("div");
      label.className = "corridor-hover-label";
      this.map.getContainer().appendChild(label);
      this.corridorHoverLabel = label;

      this.map.on("mousemove", (event) => this.handleCorridorHover(event));
      this.map.on("mouseleave", () => this.clearCorridorHover());
      this.map.on("movestart", () => this.clearCorridorHover());
      this.map.on("dragstart", () => this.clearCorridorHover());
      this.map.on("zoomstart", () => this.clearCorridorHover());
      this.map.on("pitchstart", () => this.clearCorridorHover());
      this.map.on("rotatestart", () => this.clearCorridorHover());
    }

    handleCorridorHover(event) {
      if (this.isPlanSelectingPorts()) {
        this.clearCorridorHover();
        return;
      }
      if (!this.map || !this.corridorLayer || !this.corridorLayer.getMatrix) {
        return;
      }
      const matrix = this.corridorLayer.getMatrix();
      if (!matrix) {
        return;
      }
      const target = this.findCorridorHoverTarget(event.point, matrix);
      if (!target) {
        this.clearCorridorHover();
        return;
      }

      const isSame =
        this.corridorHover &&
        this.corridorHover.type === target.type &&
        this.corridorHover.index === target.index;
      this.corridorHover = target;
      if (this.corridorLayer.setHover) {
        this.corridorLayer.setHover(target);
      }
      if (!isSame) {
        this.map.triggerRepaint();
      }
      this.showCorridorLabel(`C : ${target.name}`, event.point);
      this.map.getCanvas().style.cursor = "pointer";
    }

    showCorridorLabel(text, point) {
      if (!this.corridorHoverLabel) {
        return;
      }
      this.corridorHoverLabel.textContent = text;
      this.corridorHoverLabel.style.left = `${point.x}px`;
      this.corridorHoverLabel.style.top = `${point.y}px`;
      this.corridorHoverLabel.classList.add("is-visible");
    }

    clearCorridorHover() {
      if (!this.map) {
        return;
      }
      const hadHover = Boolean(this.corridorHover);
      this.corridorHover = null;
      if (this.corridorLayer && this.corridorLayer.clearHover) {
        this.corridorLayer.clearHover();
      }
      if (hadHover) {
        this.map.triggerRepaint();
      }
      if (this.corridorHoverLabel) {
        this.corridorHoverLabel.classList.remove("is-visible");
      }
      this.map.getCanvas().style.cursor = "";
    }

    setupVertiportHover() {
      if (!this.map) {
        return;
      }
      const label = document.createElement("div");
      label.className = "vertiport-hover-label";
      this.map.getContainer().appendChild(label);
      this.vertiportHoverLabel = label;

      this.map.on("mousemove", (event) => this.handleVertiportHover(event));
      this.map.on("mouseleave", () => this.clearVertiportHover());
      this.map.on("movestart", () => this.clearVertiportHover());
      this.map.on("dragstart", () => this.clearVertiportHover());
      this.map.on("zoomstart", () => this.clearVertiportHover());
      this.map.on("pitchstart", () => this.clearVertiportHover());
      this.map.on("rotatestart", () => this.clearVertiportHover());
    }

    handleVertiportHover(event) {
      if (!this.map) {
        return;
      }
      const restrictToPorts = this.isPlanSelectingPorts();
      if (this.corridorHover) {
        this.clearVertiportHover();
        return;
      }
      const pointLayers = [];
      if (this.map.getLayer("vertiport-icon")) {
        pointLayers.push("vertiport-icon");
      }
      if (this.map.getLayer("vertiport-circle")) {
        pointLayers.push("vertiport-circle");
      }
      if (pointLayers.length) {
        const features = this.map.queryRenderedFeatures(event.point, {
          layers: pointLayers,
        });
        if (features.length) {
          const feature = features[0];
          const name = feature && feature.properties ? String(feature.properties.name || "") : "";
          if (name) {
            const id = feature.id != null ? feature.id : name;
            if (this.vertiportLinkHoverId != null) {
              this.setVertiportLinkHoverState(null);
            }
            if (this.vertiportHoverId !== id) {
              this.setVertiportHoverState(id);
            }
            this.setVertiportHoverFilter(name);
            this.vertiportHover = { id, name };
            this.vertiportLinkHover = null;
            this.showVertiportLabel(`V : ${name}`, event.point);
            this.map.getCanvas().style.cursor = "pointer";
            return;
          }
        }
      }

      if (!restrictToPorts && this.map.getLayer("vertiport-links-line")) {
        const features = this.map.queryRenderedFeatures(event.point, {
          layers: this.map.getLayer("vertiport-links-hit")
            ? ["vertiport-links-hit"]
            : ["vertiport-links-line"],
        });
        if (features.length) {
          const feature = features[0];
          const name = feature && feature.properties ? String(feature.properties.name || "") : "";
          if (name) {
            const id = feature.id != null ? feature.id : null;
            if (this.vertiportHoverId != null) {
              this.setVertiportHoverState(null);
            }
            if (id != null && this.vertiportLinkHoverId !== id) {
              this.setVertiportLinkHoverState(id);
            }
            this.setVertiportHoverFilter(null);
            this.vertiportHover = null;
            this.vertiportLinkHover = { id, name };
            this.showVertiportLabel(`VL : ${name}`, event.point);
            this.map.getCanvas().style.cursor = "pointer";
            return;
          }
        }
      }

      this.clearVertiportHover();
    }

    setVertiportHoverState(nextId) {
      if (!this.map) {
        return;
      }
      const sourceId = "vertiport-points";
      if (this.map.isStyleLoaded() && this.map.getSource(sourceId) && this.vertiportHoverId != null) {
        this.map.setFeatureState(
          { source: sourceId, id: this.vertiportHoverId },
          { hover: false },
        );
      }
      if (this.map.isStyleLoaded() && this.map.getSource(sourceId) && nextId != null) {
        this.map.setFeatureState({ source: sourceId, id: nextId }, { hover: true });
      }
      this.vertiportHoverId = nextId;
    }

    setVertiportLinkHoverState(nextId) {
      if (!this.map) {
        return;
      }
      const sourceId = "vertiport-links";
      if (
        this.map.isStyleLoaded() &&
        this.map.getSource(sourceId) &&
        this.vertiportLinkHoverId != null
      ) {
        this.map.setFeatureState(
          { source: sourceId, id: this.vertiportLinkHoverId },
          { hover: false },
        );
      }
      if (this.map.isStyleLoaded() && this.map.getSource(sourceId) && nextId != null) {
        this.map.setFeatureState({ source: sourceId, id: nextId }, { hover: true });
      }
      this.vertiportLinkHoverId = nextId;
    }

    showVertiportLabel(text, point) {
      if (!this.vertiportHoverLabel) {
        return;
      }
      this.vertiportHoverLabel.textContent = text;
      this.vertiportHoverLabel.style.left = `${point.x}px`;
      this.vertiportHoverLabel.style.top = `${point.y}px`;
      this.vertiportHoverLabel.classList.add("is-visible");
    }

    clearVertiportHover() {
      if (!this.map) {
        return;
      }
      if (
        this.vertiportHoverId != null &&
        this.map.isStyleLoaded() &&
        this.map.getSource("vertiport-points")
      ) {
        this.map.setFeatureState(
          { source: "vertiport-points", id: this.vertiportHoverId },
          { hover: false },
        );
      }
      if (
        this.vertiportLinkHoverId != null &&
        this.map.isStyleLoaded() &&
        this.map.getSource("vertiport-links")
      ) {
        this.map.setFeatureState(
          { source: "vertiport-links", id: this.vertiportLinkHoverId },
          { hover: false },
        );
      }
      this.vertiportHover = null;
      this.vertiportHoverId = null;
      this.vertiportLinkHover = null;
      this.vertiportLinkHoverId = null;
      this.setVertiportHoverFilter(null);
      if (this.vertiportHoverLabel) {
        this.vertiportHoverLabel.classList.remove("is-visible");
      }
      if (!this.corridorHover) {
        this.map.getCanvas().style.cursor = "";
      }
    }

    setupTerrainToggle() {
      const updateTerrain = () => {
        const shouldEnable = this.map.getPitch() >= this.config.dem.pitchThreshold;
        if (shouldEnable === this.terrainEnabled) {
          return;
        }
        if (shouldEnable) {
          if (this.map.getSource("dem")) {
            this.map.setTerrain({
              source: "dem",
              exaggeration: this.config.dem.exaggeration,
            });
          }
        } else {
          this.map.setTerrain(null);
        }
        this.terrainEnabled = shouldEnable;
      };

      this.map.on("load", () => {
        updateTerrain();
        this.map.on("pitch", updateTerrain);
      });
    }

    isPlanSelectingPorts() {
      return this.planState.enabled && this.planState.selection.length < 2;
    }

    setupScaleObserver() {
      const root = document.documentElement;
      const baseWidth = 1200;
      const baseHeight = 900;

      const getViewportSize = () => {
        if (window.visualViewport) {
          return { width: window.visualViewport.width, height: window.visualViewport.height };
        }
        return { width: window.innerWidth, height: window.innerHeight };
      };

      const updateScale = () => {
        const { width, height } = getViewportSize();
        if (!width || !height) {
          return;
        }
        const scale = Math.min(width / baseWidth, height / baseHeight);
        const clamped = Math.max(0.75, Math.min(scale, 1.25));
        root.style.setProperty("--ui-scale", clamped.toFixed(3));
        if (this.map) {
          requestAnimationFrame(() => this.map.resize());
        }
      };

      updateScale();
      window.addEventListener("resize", updateScale);
      if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", updateScale);
      }

      if (window.ResizeObserver) {
        const observer = new ResizeObserver(updateScale);
        observer.observe(document.documentElement);
      }
    }
  }

  const app = new MapApp(config);
  app.init();
} )();
