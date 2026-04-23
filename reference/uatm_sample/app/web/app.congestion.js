(() => {
  const SEGMENT_CONGESTION_BUTTON_SELECTOR = '[data-action="layer-segment-congestion"]';
  const CONGESTION_PANEL_ID = "congestion-panel";
  const CONGESTION_CLOSE_ID = "congestion-close";
  const CONGESTION_WINDOW_SELECTOR = "[data-congestion-window]";
  const CONGESTION_METRIC_SELECTOR = "[data-congestion-metric]";

  const UI_SCALE = Number.isFinite(typeof MAP_SIZE_SCALE === "number" ? MAP_SIZE_SCALE : NaN)
    ? MAP_SIZE_SCALE
    : 1;

  const SEGMENT_LENGTH_M = 1000;
  const KNOT_TO_MPS = 0.514444;

  const FREEFLOW_VERTIPORT_KTS = 50;
  const FREEFLOW_ROUTE_KTS = 100;
  const SPEED_RATIO_THRESHOLD = 0.7;

  const CONGESTION_BASE_LAYER_ID = "corridor-congestion-base-3d";
  const CONGESTION_DYNAMIC_LAYER_ID = "corridor-congestion-dynamic-3d";
  const CONGESTION_LABEL_SOURCE_ID = "corridor-congestion-labels";
  const CONGESTION_LABEL_LAYER_ID = "corridor-congestion-labels";

  const EMPTY_FLOAT32 = new Float32Array(0);

  const BASE_COLOR = "#f3f4f6";
  const BASE_ALPHA = 0.22;
  const BIN_ALPHA = 0.92;

  // Wide, area-like lanes in screen pixels.
  const LANE_WIDTH_PX = 14 * UI_SCALE;
  const LANE_GAP_PX = 1.8 * UI_SCALE;

  const LABEL_MIN_ZOOM = 12;
  const LABEL_OFFSET_SCALE = 2.4;
  const LABEL_COLLISION_PX = 140 * UI_SCALE;
  const CONGESTION_WINDOWS_MINUTES = [1, 5, 10, 30];
  const CONGESTION_MAX_WINDOW_MS = 30 * 60 * 1000;
  const CONGESTION_METRIC_CII = "cii";
  const CONGESTION_METRIC_CDI = "cdi";
  const CONGESTION_METRIC_CEI = "cei";
  const CONGESTION_METRICS = [
    CONGESTION_METRIC_CII,
    CONGESTION_METRIC_CDI,
    CONGESTION_METRIC_CEI,
  ];

  // Congestion intensity bins (CII, %).
  const CONGESTION_BINS = [
    { id: "c1", min: 1, max: 10, color: "#60a5fa" },
    { id: "c2", min: 11, max: 20, color: "#34d399" },
    { id: "c3", min: 21, max: 40, color: "#fbbf24" },
    { id: "c4", min: 41, max: 60, color: "#fb923c" },
    { id: "c5", min: 61, max: 80, color: "#ef4444" },
    { id: "c6", min: 81, max: 100, color: "#b91c1c" },
  ];

  const norm = (value) => String(value || "").trim();

  const directedKey = (from, to) => {
    const a = norm(from);
    const b = norm(to);
    if (!a || !b) {
      return "";
    }
    return `${a}|${b}`;
  };

  const undirectedKey = (from, to) => {
    const a = norm(from);
    const b = norm(to);
    if (!a || !b) {
      return "";
    }
    return [a, b].sort().join("|");
  };

  const mercatorToLngLat = (x, y) => {
    const xx = Number(x);
    const yy = Number(y);
    if (!Number.isFinite(xx) || !Number.isFinite(yy)) {
      return null;
    }
    const lng = xx * 360 - 180;
    const lat = (180 / Math.PI) * Math.atan(Math.sinh(Math.PI * (1 - 2 * yy)));
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
      return null;
    }
    return [lng, lat];
  };

  const approxUnitsPerMeter = (latDeg) => {
    const lat = Number(latDeg);
    if (!Number.isFinite(lat)) {
      return 0;
    }
    const cos = Math.cos((lat * Math.PI) / 180);
    if (!Number.isFinite(cos) || cos === 0) {
      return 0;
    }
    const earthCircumference = 40075016.68557849;
    return 1 / (earthCircumference * cos);
  };

  const getBeforeId = (map) => {
    if (!map || !map.getLayer) {
      return undefined;
    }
    return map.getLayer("corridor-edit-ring")
      ? "corridor-edit-ring"
      : map.getLayer("flight-plan-route")
        ? "flight-plan-route"
        : map.getLayer("traffic-predict-line")
          ? "traffic-predict-line"
          : undefined;
  };

  const findBinIndex = (value) => {
    const v = Math.max(0, Number(value) || 0);
    for (let i = 0; i < CONGESTION_BINS.length; i += 1) {
      const bin = CONGESTION_BINS[i];
      if (v >= bin.min && v <= bin.max) {
        return i;
      }
    }
    return -1;
  };

  const clamp01 = (value) => {
    const v = Number(value);
    if (!Number.isFinite(v)) {
      return 0;
    }
    return Math.max(0, Math.min(1, v));
  };

  const easeOutCubic = (t) => 1 - Math.pow(1 - clamp01(t), 3);

  const hexToRgbaVec = (hex, alpha = 1) => {
    const raw = String(hex || "").trim();
    const a = Number(alpha);
    const outAlpha = Number.isFinite(a) ? Math.max(0, Math.min(1, a)) : 1;
    if (!raw) {
      return new Float32Array([1, 1, 1, outAlpha]);
    }
    let value = raw.startsWith("#") ? raw.slice(1) : raw;
    if (value.length === 3) {
      value = value
        .split("")
        .map((ch) => ch + ch)
        .join("");
    }
    if (value.length !== 6) {
      return new Float32Array([1, 1, 1, outAlpha]);
    }
    const r = parseInt(value.slice(0, 2), 16);
    const g = parseInt(value.slice(2, 4), 16);
    const b = parseInt(value.slice(4, 6), 16);
    if (![r, g, b].every(Number.isFinite)) {
      return new Float32Array([1, 1, 1, outAlpha]);
    }
    return new Float32Array([r / 255, g / 255, b / 255, outAlpha]);
  };

  const createBinnedTrianglesLayer3d = (id, bins, alpha) => {
    const colors = Array.isArray(bins) ? bins.map((bin) => hexToRgbaVec(bin.color, alpha)) : [];
    while (colors.length < 6) {
      colors.push(hexToRgbaVec("#ffffff", alpha));
    }

    const layer = {
      id,
      type: "custom",
      renderingMode: "3d",
      _visible: true,
      _vertexCount: 0,
      _pendingPositions: null,
      _useDepth: false,
      _alpha: 1,
      setVisible(nextVisible) {
        this._visible = Boolean(nextVisible);
      },
      setAlpha(nextAlpha) {
        this._alpha = clamp01(nextAlpha);
      },
      updatePositions(positions) {
        this._pendingPositions = positions;
        if (!this._gl || !this._buffer) {
          return;
        }
        const gl = this._gl;
        const data =
          positions instanceof Float32Array
            ? positions
            : Array.isArray(positions)
              ? new Float32Array(positions)
              : EMPTY_FLOAT32;
        gl.bindBuffer(gl.ARRAY_BUFFER, this._buffer);
        gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW);
        this._vertexCount = Math.floor(data.length / 4);
        this._pendingPositions = null;
      },
      onAdd(_map, gl) {
        this._gl = gl;
        this._matrixScratch = new Float32Array(16);

        const vertexSource = `
          attribute vec3 a_pos;
          attribute float a_bin;
          uniform mat4 u_matrix;
          uniform vec4 u_bin0;
          uniform vec4 u_bin1;
          uniform vec4 u_bin2;
          uniform vec4 u_bin3;
          uniform vec4 u_bin4;
          uniform vec4 u_bin5;
          uniform float u_alpha;
          varying vec4 v_color;
          void main() {
            gl_Position = u_matrix * vec4(a_pos, 1.0);
            float b = a_bin;
            if (b < 0.5) {
              v_color = u_bin0;
            } else if (b < 1.5) {
              v_color = u_bin1;
            } else if (b < 2.5) {
              v_color = u_bin2;
            } else if (b < 3.5) {
              v_color = u_bin3;
            } else if (b < 4.5) {
              v_color = u_bin4;
            } else {
              v_color = u_bin5;
            }
          }
        `;
        const fragmentSource = `
          precision mediump float;
          varying vec4 v_color;
          uniform float u_alpha;
          void main() {
            gl_FragColor = vec4(v_color.rgb, v_color.a * u_alpha);
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
        this._aBin = gl.getAttribLocation(program, "a_bin");
        this._uMatrix = gl.getUniformLocation(program, "u_matrix");
        this._uBins = [
          gl.getUniformLocation(program, "u_bin0"),
          gl.getUniformLocation(program, "u_bin1"),
          gl.getUniformLocation(program, "u_bin2"),
          gl.getUniformLocation(program, "u_bin3"),
          gl.getUniformLocation(program, "u_bin4"),
          gl.getUniformLocation(program, "u_bin5"),
        ];
        this._uAlpha = gl.getUniformLocation(program, "u_alpha");

        this._buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, this._buffer);
        gl.bufferData(gl.ARRAY_BUFFER, EMPTY_FLOAT32, gl.DYNAMIC_DRAW);
        this._vertexCount = 0;

        gl.useProgram(this._program);
        for (let i = 0; i < this._uBins.length; i += 1) {
          const loc = this._uBins[i];
          if (loc) {
            gl.uniform4fv(loc, colors[i] || colors[colors.length - 1]);
          }
        }
        if (this._uAlpha) {
          gl.uniform1f(this._uAlpha, this._alpha);
        }

        if (this._pendingPositions) {
          this.updatePositions(this._pendingPositions);
        }
      },
      render(gl, matrix) {
        let drawMatrix = matrix;
        if (
          drawMatrix &&
          typeof drawMatrix.length !== "number" &&
          typeof drawMatrix.toArray === "function"
        ) {
          drawMatrix = drawMatrix.toArray();
        }
        if (!drawMatrix || typeof drawMatrix.length !== "number") {
          return;
        }
        if (!(drawMatrix instanceof Float32Array)) {
          const scratch = this._matrixScratch;
          if (!scratch || scratch.length !== drawMatrix.length) {
            this._matrixScratch = new Float32Array(drawMatrix);
          } else {
            for (let i = 0; i < scratch.length; i += 1) {
              scratch[i] = drawMatrix[i];
            }
          }
          drawMatrix = this._matrixScratch;
        }

        if (!this._program || !this._vertexCount || !this._visible) {
          return;
        }
        const depthWasEnabled = gl.isEnabled(gl.DEPTH_TEST);
        if (!this._useDepth) {
          gl.disable(gl.DEPTH_TEST);
        }
        gl.useProgram(this._program);
        gl.uniformMatrix4fv(this._uMatrix, false, drawMatrix);
        if (this._uAlpha) {
          gl.uniform1f(this._uAlpha, this._alpha);
        }
        gl.bindBuffer(gl.ARRAY_BUFFER, this._buffer);
        gl.enableVertexAttribArray(this._aPos);
        gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 16, 0);
        gl.enableVertexAttribArray(this._aBin);
        gl.vertexAttribPointer(this._aBin, 1, gl.FLOAT, false, 16, 12);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.drawArrays(gl.TRIANGLES, 0, this._vertexCount);
        if (!this._useDepth && depthWasEnabled) {
          gl.enable(gl.DEPTH_TEST);
        }
      },
    };
    return layer;
  };

  const resolveWindowMinutes = (value) => {
    const minutes = Number(value);
    if (Number.isFinite(minutes) && CONGESTION_WINDOWS_MINUTES.includes(minutes)) {
      return minutes;
    }
    return CONGESTION_WINDOWS_MINUTES[0];
  };

  const resolveCongestionMetric = (value) => {
    const metric = String(value || "").toLowerCase();
    if (CONGESTION_METRICS.includes(metric)) {
      return metric;
    }
    return CONGESTION_METRIC_CII;
  };

  const nowMs = () => {
    if (typeof performance !== "undefined" && typeof performance.now === "function") {
      return performance.now();
    }
    return Date.now();
  };

  MapApp.prototype.initCongestionLayer = function () {
    this.congestionEnabled = false;
    this.congestionLayerButton = document.querySelector(SEGMENT_CONGESTION_BUTTON_SELECTOR);
    this.congestionPanel = document.getElementById(CONGESTION_PANEL_ID);
    this.congestionCloseButton = document.getElementById(CONGESTION_CLOSE_ID);
    this.congestionWindowButtons = Array.from(
      document.querySelectorAll(CONGESTION_WINDOW_SELECTOR),
    );
    this.congestionMetricButtons = Array.from(
      document.querySelectorAll(CONGESTION_METRIC_SELECTOR),
    );
    this.congestionLegend = this.congestionPanel
      ? this.congestionPanel.querySelector(".congestion-legend")
      : document.querySelector(".congestion-legend");
    this.congestionLegendTitle = document.getElementById("congestion-legend-title");

    this.congestionWindowMinutes = resolveWindowMinutes(CONGESTION_WINDOWS_MINUTES[0]);
    this.congestionWindowMs = this.congestionWindowMinutes * 60000;
    this.congestionSpeedRatioThreshold = SPEED_RATIO_THRESHOLD;
    this.congestionMetric = resolveCongestionMetric(CONGESTION_METRIC_CII);

    this.congestionSampleMinIntervalMs = 1000;
    this.congestionLastSampleAt = 0;

    this.congestionSamples = new Map();
    this.congestionSegmentsByLine = new Map();
    this.congestionLineIndex = new Map();

    this.congestionUpdateScheduled = false;
    this.congestionUpdateForced = false;
    this.congestionUpdateLastAt = 0;
    this.congestionUpdateMinIntervalMs = 900;
    this.congestionUpdateTimer = null;
    this.congestionUpdateRafId = null;
    this.congestionGeometryDirty = true;
    this.congestionLastLabelsNonEmpty = false;
    this.congestionLastDynamicNonEmpty = false;
    this.congestionOverlayAlpha = 0;
    this.congestionFadeRafId = null;
    this.congestionFadeDurationMs = 220;
    this.congestionLabelCache = new Map();
    this.congestionLabelDirty = false;
    this.congestionUseHtmlLabels = true;
    this.congestionLabelMarkers = new Map();
    this.congestionLabelsVisible = false;
    this.congestionLabelDeclutterRafId = null;
    this.congestionLabelDeclutterBound = false;

    this.congestionBase3dLayer = null;
    this.congestionDynamic3dLayer = null;
    this.congestionResizeBound = false;

    if (this.congestionLayerButton) {
      this.congestionLayerButton.addEventListener("click", () => {
        this.setCongestionEnabled(!this.congestionEnabled);
        if (this.setBaseListOpen) {
          this.setBaseListOpen(false);
        }
      });
      this.congestionLayerButton.setAttribute("aria-pressed", "false");
    }

    if (this.congestionCloseButton) {
      this.congestionCloseButton.addEventListener("click", () => {
        this.setCongestionEnabled(false);
      });
    }

    if (this.congestionWindowButtons.length) {
      this.congestionWindowButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          const minutes = resolveWindowMinutes(btn.getAttribute("data-congestion-window"));
          this.setCongestionWindowMinutes(minutes);
        });
      });
    }
    this.updateCongestionWindowButtons();

    if (this.congestionMetricButtons.length) {
      this.congestionMetricButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          const metric = resolveCongestionMetric(btn.getAttribute("data-congestion-metric"));
          this.setCongestionMetric(metric);
        });
      });
    }
    this.updateCongestionMetricButtons();
    this.updateCongestionLegend();

    if (!this.map) {
      return;
    }
    const onReady = () => {
      this.ensureCongestionLayers();
      this.scheduleCongestionUpdate(true);
    };
    if (typeof this.map.isStyleLoaded === "function" && this.map.isStyleLoaded()) {
      onReady();
      return;
    }
    if (typeof this.map.once === "function") {
      this.map.once("load", () => onReady());
    }
  };

  MapApp.prototype.setCongestionWindowMinutes = function (minutes) {
    const next = resolveWindowMinutes(minutes);
    if (next === this.congestionWindowMinutes) {
      return;
    }
    this.congestionWindowMinutes = next;
    this.congestionWindowMs = next * 60000;
    this.updateCongestionWindowButtons();
    if (this.congestionEnabled) {
      this.scheduleCongestionUpdate(true);
    }
  };

  MapApp.prototype.updateCongestionWindowButtons = function () {
    if (!this.congestionWindowButtons || !this.congestionWindowButtons.length) {
      return;
    }
    this.congestionWindowButtons.forEach((btn) => {
      const minutes = resolveWindowMinutes(btn.getAttribute("data-congestion-window"));
      const active = minutes === this.congestionWindowMinutes;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
  };

  MapApp.prototype.setCongestionMetric = function (metric) {
    const next = resolveCongestionMetric(metric);
    if (next === this.congestionMetric) {
      return;
    }
    this.congestionMetric = next;
    this.updateCongestionMetricButtons();
    if (this.congestionEnabled) {
      this.scheduleCongestionUpdate(true);
    }
  };

  MapApp.prototype.updateCongestionMetricButtons = function () {
    if (!this.congestionMetricButtons || !this.congestionMetricButtons.length) {
      return;
    }
    this.congestionMetricButtons.forEach((btn) => {
      const metric = resolveCongestionMetric(btn.getAttribute("data-congestion-metric"));
      const active = metric === this.congestionMetric;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    this.updateCongestionLegend();
  };

  MapApp.prototype.getCongestionMetricLabel = function (metric) {
    const key = resolveCongestionMetric(metric);
    if (key === CONGESTION_METRIC_CDI) {
      return "지속";
    }
    if (key === CONGESTION_METRIC_CEI) {
      return "범위";
    }
    return "강도";
  };

  MapApp.prototype.updateCongestionLegend = function () {
    if (this.congestionLegendTitle) {
      const metricLabel = this.getCongestionMetricLabel(this.congestionMetric);
      this.congestionLegendTitle.textContent = `혼잡 ${metricLabel} (%)`;
    }
    if (this.congestionLegend) {
      const visible = Boolean(this.congestionEnabled);
      this.congestionLegend.setAttribute("aria-hidden", visible ? "false" : "true");
    }
  };

  MapApp.prototype.setCongestionPanelVisible = function (visible) {
    if (!this.congestionPanel) {
      return;
    }
    const next = Boolean(visible);
    this.congestionPanel.classList.toggle("is-visible", next);
    this.congestionPanel.setAttribute("aria-hidden", next ? "false" : "true");
  };

  MapApp.prototype.resetCongestionHistory = function () {
    this.congestionSamples = new Map();
    this.congestionSegmentsByLine = new Map();
    this.congestionLastSampleAt = 0;
    if (this.congestionLabelCache instanceof Map) {
      this.congestionLabelCache.clear();
    } else {
      this.congestionLabelCache = new Map();
    }
    if (this.congestionLabelMarkers instanceof Map) {
      for (const entry of this.congestionLabelMarkers.values()) {
        if (entry && entry.marker && typeof entry.marker.remove === "function") {
          entry.marker.remove();
        }
      }
      this.congestionLabelMarkers.clear();
    }
    this.congestionLabelDirty = true;
  };

  MapApp.prototype.getCongestionTimeMs = function () {
    if (Number.isFinite(this.lastSimTime_s)) {
      return this.lastSimTime_s * 1000;
    }
    return nowMs();
  };

  MapApp.prototype.setupCongestionResize = function () {
    if (!this.map || this.congestionResizeBound) {
      return;
    }
    this.congestionResizeBound = true;
    const update = () => {
      if (this.congestionEnabled) {
        this.congestionGeometryDirty = true;
        this.scheduleCongestionUpdate(true);
      }
    };
    this.map.on("zoomend", update);
    this.map.on("resize", update);
  };

  MapApp.prototype.setupCongestionLabelDeclutter = function () {
    if (!this.map || this.congestionLabelDeclutterBound) {
      return;
    }
    this.congestionLabelDeclutterBound = true;
    const schedule = () => {
      if (!this.congestionEnabled || !this.congestionUseHtmlLabels) {
        return;
      }
      if (this.congestionLabelDeclutterRafId != null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(this.congestionLabelDeclutterRafId);
      }
      this.congestionLabelDeclutterRafId = requestAnimationFrame(() => {
        this.congestionLabelDeclutterRafId = null;
        this.declutterCongestionLabelMarkers();
      });
    };
    this.map.on("move", schedule);
    this.map.on("resize", schedule);
  };

  MapApp.prototype.ensureCongestionLayers = function () {
    if (!this.map || typeof this.map.isStyleLoaded !== "function" || !this.map.isStyleLoaded()) {
      return;
    }

    const beforeId = getBeforeId(this.map);
    let changed = false;

    if (!this.map.getLayer(CONGESTION_BASE_LAYER_ID)) {
      const layer = this.createLineLayer3d(CONGESTION_BASE_LAYER_ID, BASE_COLOR, "TRIANGLES");
      if (layer) {
        if (layer.setVerticesPerLine) {
          layer.setVerticesPerLine(6);
        } else {
          layer._verticesPerLine = 6;
        }
        if (layer.setAlpha) {
          layer.setAlpha(BASE_ALPHA);
        } else {
          layer._colorAlpha = BASE_ALPHA;
        }
        if (layer.setVisible) {
          layer.setVisible(this.congestionEnabled);
        } else {
          layer._visible = this.congestionEnabled;
        }
        // Always treat congestion as a visualization overlay.
        layer._useDepth = false;
      }
      this.congestionBase3dLayer = layer;
      try {
        this.map.addLayer(layer, beforeId);
        changed = true;
      } catch (_err) {
        // ignore
      }
    }

    if (!this.map.getLayer(CONGESTION_DYNAMIC_LAYER_ID)) {
      const layer = createBinnedTrianglesLayer3d(CONGESTION_DYNAMIC_LAYER_ID, CONGESTION_BINS, BIN_ALPHA);
      if (layer) {
        if (layer.setVisible) {
          layer.setVisible(this.congestionEnabled);
        } else {
          layer._visible = this.congestionEnabled;
        }
        layer._useDepth = false;
      }
      this.congestionDynamic3dLayer = layer;
      try {
        this.map.addLayer(layer, beforeId);
        changed = true;
      } catch (_err) {
        // ignore
      }
    }

    const empty = { type: "FeatureCollection", features: [] };
    if (!this.map.getSource(CONGESTION_LABEL_SOURCE_ID)) {
      try {
        this.map.addSource(CONGESTION_LABEL_SOURCE_ID, { type: "geojson", data: empty });
        changed = true;
      } catch (_err) {
        // ignore
      }
    }

    const labelVisibility = this.congestionUseHtmlLabels ? "none" : this.congestionEnabled ? "visible" : "none";
    if (!this.map.getLayer(CONGESTION_LABEL_LAYER_ID)) {
      try {
        this.map.addLayer(
          {
            id: CONGESTION_LABEL_LAYER_ID,
            type: "symbol",
            source: CONGESTION_LABEL_SOURCE_ID,
            minzoom: LABEL_MIN_ZOOM,
            layout: {
              "text-field": ["get", "label"],
              "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
              "text-size": [
                "interpolate",
                ["linear"],
                ["zoom"],
                LABEL_MIN_ZOOM,
                10 * UI_SCALE,
                LABEL_MIN_ZOOM + 3,
                13 * UI_SCALE,
              ],
              "symbol-sort-key": ["-", ["get", "value"]],
              "text-allow-overlap": false,
              "text-ignore-placement": false,
              "text-padding": 2,
              "text-variable-anchor": ["top", "bottom", "left", "right"],
              "text-radial-offset": 0.6,
              "text-justify": "auto",
              "text-pitch-alignment": "map",
              "text-rotation-alignment": "map",
              visibility: labelVisibility,
            },
            paint: {
              "text-color": "#111827",
              "text-halo-color": "rgba(255, 255, 255, 0.85)",
              "text-halo-width": 1.2,
              "text-halo-blur": 0.4,
            },
          },
          beforeId,
        );
        changed = true;
      } catch (_err) {
        // ignore
      }
    } else {
      try {
        this.map.setLayoutProperty(CONGESTION_LABEL_LAYER_ID, "visibility", labelVisibility);
      } catch (_err) {
        // ignore
      }
    }

    this.setupCongestionResize();
    this.setupCongestionLabelDeclutter();
    if (changed && typeof this.reorderPlanLayers === "function") {
      this.reorderPlanLayers();
    }

    if (typeof this.applyCongestionOverlayAlpha === "function") {
      const fallbackAlpha = this.congestionEnabled ? 1 : 0;
      const nextAlpha = Number.isFinite(this.congestionOverlayAlpha)
        ? this.congestionOverlayAlpha
        : fallbackAlpha;
      this.applyCongestionOverlayAlpha(nextAlpha);
    }
  };

  MapApp.prototype.applyCongestionOverlayAlpha = function (alpha) {
    const next = clamp01(alpha);
    this.congestionOverlayAlpha = next;
    if (this.congestionBase3dLayer) {
      if (typeof this.congestionBase3dLayer.setAlpha === "function") {
        this.congestionBase3dLayer.setAlpha(BASE_ALPHA * next);
      } else {
        this.congestionBase3dLayer._colorAlpha = BASE_ALPHA * next;
      }
    }
    if (this.congestionDynamic3dLayer) {
      if (typeof this.congestionDynamic3dLayer.setAlpha === "function") {
        this.congestionDynamic3dLayer.setAlpha(next);
      } else {
        this.congestionDynamic3dLayer._alpha = next;
      }
    }
    if (this.map && this.map.getLayer && this.map.getLayer(CONGESTION_LABEL_LAYER_ID)) {
      try {
        this.map.setPaintProperty(CONGESTION_LABEL_LAYER_ID, "text-opacity", next);
        this.map.setPaintProperty(CONGESTION_LABEL_LAYER_ID, "text-halo-opacity", next);
      } catch (_err) {
        // ignore
      }
    }
    if (this.congestionLabelMarkers instanceof Map) {
      const show = Boolean(this.congestionLabelsVisible);
      for (const entry of this.congestionLabelMarkers.values()) {
        if (!entry || !entry.el) {
          continue;
        }
        entry.el.style.opacity = show ? String(next) : "0";
      }
    }
  };

  MapApp.prototype.setCongestionLabelFeature = function (line, offset, avgValue) {
    if (this.congestionUseHtmlLabels) {
      return this.setCongestionLabelMarker(line, offset, avgValue);
    }
    if (!line || !Number.isFinite(avgValue)) {
      return;
    }
    const labelOffset = Number.isFinite(offset) ? offset * LABEL_OFFSET_SCALE : 0;
    const mx = (line.start.x + line.end.x) / 2 + line.offsetDir.x * labelOffset;
    const my = (line.start.y + line.end.y) / 2 + line.offsetDir.y * labelOffset;
    const lngLat = mercatorToLngLat(mx, my);
    if (!lngLat) {
      return;
    }
    const key = line.key || directedKey(line.from, line.to);
    if (!key) {
      return;
    }
    const metricLabel = this.getCongestionMetricLabel(this.congestionMetric);
    const label = `${line.from} -> ${line.to}\n방향 혼잡(${metricLabel}): ${avgValue}%`;
    const prev = this.congestionLabelCache instanceof Map ? this.congestionLabelCache.get(key) : null;
    const prevCoords = prev && prev.geometry && Array.isArray(prev.geometry.coordinates)
      ? prev.geometry.coordinates
      : null;
    const sameLabel =
      prev &&
      prev.properties &&
      prev.properties.label === label &&
      prev.properties.value === avgValue &&
      prevCoords &&
      prevCoords[0] === lngLat[0] &&
      prevCoords[1] === lngLat[1];
    if (sameLabel) {
      return key;
    }
    const feature = {
      type: "Feature",
      geometry: { type: "Point", coordinates: lngLat },
      properties: {
        label,
        from: line.from,
        to: line.to,
        value: avgValue,
      },
    };
    if (!(this.congestionLabelCache instanceof Map)) {
      this.congestionLabelCache = new Map();
    }
    this.congestionLabelCache.set(key, feature);
    this.congestionLabelDirty = true;
    return key;
  };

  MapApp.prototype.setCongestionLabelMarker = function (line, offset, avgValue) {
    if (!line || !Number.isFinite(avgValue) || !this.map || typeof maplibregl === "undefined") {
      return;
    }
    const Marker = maplibregl.Marker;
    if (typeof Marker !== "function") {
      return;
    }
    const labelOffset = Number.isFinite(offset) ? offset * LABEL_OFFSET_SCALE : 0;
    const mx = (line.start.x + line.end.x) / 2 + line.offsetDir.x * labelOffset;
    const my = (line.start.y + line.end.y) / 2 + line.offsetDir.y * labelOffset;
    const lngLat = mercatorToLngLat(mx, my);
    if (!lngLat) {
      return;
    }
    const key = line.key || directedKey(line.from, line.to);
    if (!key) {
      return;
    }
    const metricLabel = this.getCongestionMetricLabel(this.congestionMetric);
    const label = `${line.from} -> ${line.to}\n방향 혼잡(${metricLabel}): ${avgValue}%`;

    if (!(this.congestionLabelMarkers instanceof Map)) {
      this.congestionLabelMarkers = new Map();
    }

    let entry = this.congestionLabelMarkers.get(key);
    if (!entry) {
      const el = document.createElement("div");
      el.className = "congestion-label-marker";
      el.textContent = label;
      el.style.opacity = this.congestionLabelsVisible
        ? String(Number.isFinite(this.congestionOverlayAlpha) ? this.congestionOverlayAlpha : 1)
        : "0";
      const marker = new Marker({ element: el, anchor: "center" }).setLngLat(lngLat).addTo(this.map);
      entry = {
        marker,
        el,
        value: avgValue,
        label,
        lngLat,
      };
      this.congestionLabelMarkers.set(key, entry);
      return key;
    }

    if (entry.value !== avgValue) {
      entry.value = avgValue;
    }
    if (entry.label !== label) {
      entry.label = label;
      entry.el.textContent = label;
    }
    const prev = entry.lngLat;
    if (!prev || prev[0] !== lngLat[0] || prev[1] !== lngLat[1]) {
      entry.lngLat = lngLat;
      if (entry.marker && typeof entry.marker.setLngLat === "function") {
        entry.marker.setLngLat(lngLat);
      }
    }
    return key;
  };

  MapApp.prototype.declutterCongestionLabelMarkers = function () {
    if (!this.map || !this.congestionUseHtmlLabels) {
      return;
    }
    if (!this.congestionLabelsVisible) {
      return;
    }
    if (!(this.congestionLabelMarkers instanceof Map) || !this.congestionLabelMarkers.size) {
      return;
    }
    if (typeof this.map.project !== "function") {
      return;
    }
    const minDist = Number.isFinite(LABEL_COLLISION_PX) ? LABEL_COLLISION_PX : 120;
    const minDist2 = minDist * minDist;
    const candidates = [];
    for (const entry of this.congestionLabelMarkers.values()) {
      if (!entry || !entry.el || !entry.lngLat) {
        continue;
      }
      const projected = this.map.project(entry.lngLat);
      if (!projected || !Number.isFinite(projected.x) || !Number.isFinite(projected.y)) {
        continue;
      }
      candidates.push({
        entry,
        x: projected.x,
        y: projected.y,
        value: Number(entry.value) || 0,
      });
    }
    if (!candidates.length) {
      return;
    }
    candidates.sort((a, b) => b.value - a.value);
    const accepted = [];
    for (const candidate of candidates) {
      let collides = false;
      for (const placed of accepted) {
        const dx = candidate.x - placed.x;
        const dy = candidate.y - placed.y;
        if (dx * dx + dy * dy < minDist2) {
          collides = true;
          break;
        }
      }
      const display = collides ? "none" : "";
      if (candidate.entry.el.style.display !== display) {
        candidate.entry.el.style.display = display;
      }
      if (!collides) {
        accepted.push(candidate);
      }
    }
  };

  MapApp.prototype.pruneCongestionLabelMarkers = function (activeKeys) {
    if (!(this.congestionLabelMarkers instanceof Map) || !this.congestionLabelMarkers.size) {
      return;
    }
    const keep = activeKeys instanceof Set ? activeKeys : new Set(activeKeys || []);
    for (const [key, entry] of this.congestionLabelMarkers.entries()) {
      if (keep.has(key)) {
        continue;
      }
      if (entry && entry.marker && typeof entry.marker.remove === "function") {
        entry.marker.remove();
      }
      this.congestionLabelMarkers.delete(key);
    }
  };

  MapApp.prototype.setCongestionLabelMarkersVisible = function (visible) {
    this.congestionLabelsVisible = Boolean(visible);
    if (!(this.congestionLabelMarkers instanceof Map)) {
      return;
    }
    const alpha = Number.isFinite(this.congestionOverlayAlpha) ? this.congestionOverlayAlpha : 1;
    const opacity = this.congestionLabelsVisible ? String(alpha) : "0";
    for (const entry of this.congestionLabelMarkers.values()) {
      if (entry && entry.el) {
        entry.el.style.opacity = opacity;
      }
    }
    if (this.congestionLabelsVisible) {
      this.declutterCongestionLabelMarkers();
    }
  };

  MapApp.prototype.startCongestionFade = function (visible) {
    const target = visible ? 1 : 0;
    const startAlpha = Number.isFinite(this.congestionOverlayAlpha)
      ? this.congestionOverlayAlpha
      : visible
        ? 0
        : 1;
    const duration = Math.max(
      0,
      Number.isFinite(this.congestionFadeDurationMs) ? this.congestionFadeDurationMs : 220,
    );

    if (this.congestionFadeRafId != null && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(this.congestionFadeRafId);
      this.congestionFadeRafId = null;
    }

    const startAt = nowMs();
    const tick = () => {
      const elapsed = nowMs() - startAt;
      const t = duration > 0 ? Math.min(1, elapsed / duration) : 1;
      const eased = easeOutCubic(t);
      const alpha = startAlpha + (target - startAlpha) * eased;
      this.applyCongestionOverlayAlpha(alpha);
      if (this.map && typeof this.map.triggerRepaint === "function") {
        this.map.triggerRepaint();
      }
      if (t < 1) {
        this.congestionFadeRafId = requestAnimationFrame(tick);
      } else {
        this.congestionFadeRafId = null;
        if (!visible) {
          const setVisible = (layer, value) => {
            if (!layer) {
              return;
            }
            if (typeof layer.setVisible === "function") {
              layer.setVisible(value);
            } else {
              layer._visible = value;
            }
          };
          setVisible(this.congestionBase3dLayer, false);
          setVisible(this.congestionDynamic3dLayer, false);
          try {
            this.map.setLayoutProperty(CONGESTION_LABEL_LAYER_ID, "visibility", "none");
          } catch (_err) {
            // ignore
          }
          const source = this.map.getSource && this.map.getSource(CONGESTION_LABEL_SOURCE_ID);
          if (source && typeof source.setData === "function") {
            source.setData({ type: "FeatureCollection", features: [] });
          }
          if (this.congestionLabelCache instanceof Map) {
            this.congestionLabelCache.clear();
          } else {
            this.congestionLabelCache = new Map();
          }
          if (this.congestionLabelMarkers instanceof Map) {
            for (const entry of this.congestionLabelMarkers.values()) {
              if (entry && entry.marker && typeof entry.marker.remove === "function") {
                entry.marker.remove();
              }
            }
            this.congestionLabelMarkers.clear();
          }
          this.congestionLabelDirty = false;
          this.congestionLastLabelsNonEmpty = false;
          this.congestionLastDynamicNonEmpty = false;
        }
      }
    };

    this.congestionFadeRafId = requestAnimationFrame(tick);
  };

  MapApp.prototype.setCongestionEnabled = function (enabled) {
    const next = Boolean(enabled);
    if (next && typeof this.disableOtherBaseLayers === "function") {
      this.disableOtherBaseLayers("segment-congestion");
    }
    this.congestionEnabled = next;

    if (typeof document !== "undefined") {
      document.body.classList.toggle("congestion-visible", next);
    }
    if (this.congestionLayerButton) {
      this.congestionLayerButton.classList.toggle("is-active", next);
      this.congestionLayerButton.setAttribute("aria-pressed", next ? "true" : "false");
    }
    this.setCongestionPanelVisible(next);
    if (typeof this.updateCongestionLegend === "function") {
      this.updateCongestionLegend();
    }

    if (!this.map) {
      return;
    }
    this.ensureCongestionLayers();

    const setVisible = (layer, visible) => {
      if (!layer) {
        return;
      }
      if (typeof layer.setVisible === "function") {
        layer.setVisible(visible);
      } else {
        layer._visible = visible;
      }
    };

    if (next) {
      setVisible(this.congestionBase3dLayer, true);
      setVisible(this.congestionDynamic3dLayer, true);
      try {
        this.map.setLayoutProperty(
          CONGESTION_LABEL_LAYER_ID,
          "visibility",
          this.congestionUseHtmlLabels ? "none" : "visible",
        );
      } catch (_err) {
        // ignore
      }
      this.congestionGeometryDirty = true;
      this.scheduleCongestionUpdate(true);
      try {
        this.updateCongestionOverlay(true);
      } catch (_err) {
        // ignore
      }
      this.startCongestionFade(true);
    } else {
      if (this.congestionUpdateTimer != null) {
        clearTimeout(this.congestionUpdateTimer);
        this.congestionUpdateTimer = null;
      }
      if (this.congestionUpdateRafId != null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(this.congestionUpdateRafId);
        this.congestionUpdateRafId = null;
      }
      this.congestionUpdateScheduled = false;
      this.congestionUpdateForced = false;
      this.startCongestionFade(false);
    }

    if (typeof this.map.triggerRepaint === "function") {
      this.map.triggerRepaint();
    }
  };

  MapApp.prototype.scheduleCongestionUpdate = function (force = false) {
    if (!this.map) {
      return;
    }
    if (force) {
      this.congestionUpdateForced = true;
    }
    const now = nowMs();
    const lastAt = Number.isFinite(this.congestionUpdateLastAt) ? this.congestionUpdateLastAt : 0;
    const minInterval = Math.max(
      0,
      Number.isFinite(this.congestionUpdateMinIntervalMs) ? this.congestionUpdateMinIntervalMs : 900,
    );
    const delay = force ? 0 : Math.max(0, minInterval - (now - lastAt));

    const run = () => {
      this.congestionUpdateRafId = null;
      this.congestionUpdateTimer = null;
      this.congestionUpdateScheduled = false;
      const forced = Boolean(this.congestionUpdateForced);
      this.congestionUpdateForced = false;
      this.congestionUpdateLastAt = nowMs();
      this.updateCongestionOverlay(forced);
    };

    const scheduleRaf = () => {
      if (this.congestionUpdateRafId != null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(this.congestionUpdateRafId);
      }
      this.congestionUpdateRafId = requestAnimationFrame(run);
    };

    if (this.congestionUpdateScheduled) {
      if (force && this.congestionUpdateTimer != null) {
        clearTimeout(this.congestionUpdateTimer);
        this.congestionUpdateTimer = null;
        scheduleRaf();
      }
      return;
    }

    this.congestionUpdateScheduled = true;
    if (delay <= 0) {
      scheduleRaf();
      return;
    }
    this.congestionUpdateTimer = setTimeout(scheduleRaf, delay);
  };

  MapApp.prototype.captureCongestionSamples = function (positions) {
    if (!Array.isArray(positions) || !positions.length) {
      return;
    }
    if (!this.congestionLineIndex || this.congestionLineIndex.size === 0) {
      const corridor = this.corridorData;
      const vertiport = this.vertiportData;
      if (corridor || vertiport) {
        this.buildCongestionLineIndex();
      }
    }
    if (!this.congestionLineIndex || this.congestionLineIndex.size === 0) {
      return;
    }
    const now =
      typeof this.getCongestionTimeMs === "function" ? this.getCongestionTimeMs() : nowMs();
    if (Number.isFinite(this.congestionLastSampleAt) && now < this.congestionLastSampleAt) {
      this.resetCongestionHistory();
    }
    if (now - this.congestionLastSampleAt < this.congestionSampleMinIntervalMs) {
      return;
    }
    this.congestionLastSampleAt = now;
    const maxWindowStart = now - CONGESTION_MAX_WINDOW_MS;

    const aggregated = new Map();
    positions.forEach((pos) => {
      if (!pos) {
        return;
      }
      const speed = Number(pos.speed_mps);
      if (!Number.isFinite(speed)) {
        return;
      }
      const from = pos.route_from ? String(pos.route_from) : "";
      const to = pos.route_to ? String(pos.route_to) : "";
      const key = directedKey(from, to);
      if (!key) {
        return;
      }
      const line = this.congestionLineIndex.get(key);
      if (!line) {
        return;
      }
      const lon = Number(pos.lon);
      const lat = Number(pos.lat);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return;
      }
      const segIndex = this.getCongestionSegmentIndex(line, lon, lat);
      if (segIndex == null) {
        return;
      }
      const segKey = `${key}|${segIndex}`;
      const entry = aggregated.get(segKey) || { lineKey: key, segIndex, sum: 0, count: 0 };
      entry.sum += speed;
      entry.count += 1;
      aggregated.set(segKey, entry);
    });

    aggregated.forEach((entry, segKey) => {
      if (!entry || !entry.count) {
        return;
      }
      const line = this.congestionLineIndex.get(entry.lineKey);
      const freeflowMps = line ? line.freeflowMps : 0;
      this.pruneCongestionSamples(
        segKey,
        maxWindowStart,
        maxWindowStart,
        now,
        entry.lineKey,
        entry.segIndex,
        freeflowMps,
        this.congestionSpeedRatioThreshold,
      );
      const samples = this.congestionSamples.get(segKey) || [];
      samples.push(now, entry.sum, entry.count);
      this.congestionSamples.set(segKey, samples);

      const segments = this.congestionSegmentsByLine.get(entry.lineKey) || new Set();
      segments.add(entry.segIndex);
      this.congestionSegmentsByLine.set(entry.lineKey, segments);
    });
  };

  MapApp.prototype.getCongestionSegmentIndex = function (line, lon, lat) {
    if (!line || !Number.isFinite(line.len2) || line.len2 <= 0) {
      return null;
    }
    const merc = maplibregl.MercatorCoordinate.fromLngLat([lon, lat]);
    const vx = merc.x - line.start.x;
    const vy = merc.y - line.start.y;
    const t = Math.max(0, Math.min(1, (vx * line.dx + vy * line.dy) / line.len2));
    const segCount = line.segCount || 1;
    const idx = Math.min(segCount - 1, Math.max(0, Math.floor(t * segCount)));
    return idx;
  };

  MapApp.prototype.pruneCongestionSamples = function (
    segKey,
    maxWindowStart,
    windowStart,
    nowMs,
    lineKey,
    segIndex,
    freeflowMps,
    threshold,
  ) {
    const samples = this.congestionSamples.get(segKey);
    if (!samples || samples.length < 3) {
      return null;
    }
    let write = 0;
    let sumSpeed = 0;
    let count = 0;
    for (let i = 0; i < samples.length; i += 3) {
      const t = samples[i];
      const sum = samples[i + 1];
      const sampleCount = samples[i + 2];
      if (t >= maxWindowStart) {
        samples[write] = t;
        samples[write + 1] = sum;
        samples[write + 2] = sampleCount;
        write += 3;
        if (t >= windowStart) {
          if (Number.isFinite(sum) && Number.isFinite(sampleCount) && sampleCount > 0) {
            sumSpeed += sum;
            count += sampleCount;
          }
        }
      }
    }
    samples.length = write;
    if (!write) {
      this.congestionSamples.delete(segKey);
      if (lineKey && this.congestionSegmentsByLine.has(lineKey)) {
        const set = this.congestionSegmentsByLine.get(lineKey);
        if (set) {
          set.delete(segIndex);
          if (!set.size) {
            this.congestionSegmentsByLine.delete(lineKey);
          }
        }
      }
      return null;
    }
    const meanSpeed = count ? sumSpeed / count : null;
    let congestedMs = 0;
    const windowMs = Math.max(1, Number(nowMs) - Number(windowStart));
    const useFreeflow = Number.isFinite(freeflowMps) ? Number(freeflowMps) : 0;
    const useThreshold = Number.isFinite(threshold) ? Number(threshold) : SPEED_RATIO_THRESHOLD;
    if (useFreeflow > 0 && write >= 3) {
      for (let i = 0; i < write; i += 3) {
        const t = samples[i];
        const sum = samples[i + 1];
        const sampleCount = samples[i + 2];
        const mean = sampleCount > 0 ? sum / sampleCount : null;
        if (!Number.isFinite(mean) || mean <= 0) {
          continue;
        }
        const nextT = i + 3 < write ? samples[i + 3] : nowMs;
        const start = Math.max(t, windowStart);
        const end = Math.min(nextT, nowMs);
        if (end <= start) {
          continue;
        }
        const ratio = mean / useFreeflow;
        if (Number.isFinite(ratio) && ratio < useThreshold) {
          congestedMs += end - start;
        }
      }
    }
    return {
      meanSpeed,
      congestedMs,
      windowMs,
    };
  };

  MapApp.prototype.buildCongestionLineIndex = function () {
    const index = new Map();
    const seen = new Set();

    const addUndirected = (line, kind) => {
      if (!line || !line.start || !line.end || !line.start.coord || !line.end.coord) {
        return;
      }
      const fromName = norm(line.from);
      const toName = norm(line.to);
      const key = undirectedKey(fromName, toName);
      if (!key || seen.has(key)) {
        return;
      }
      seen.add(key);

      const altA = Number(line.start.altitude_m);
      const altB = Number(line.end.altitude_m);
      const fallbackAlt =
        kind === "vertiport"
          ? typeof VERTIPORT_ALT_M === "number"
            ? VERTIPORT_ALT_M
            : 0
          : typeof CORRIDOR_ALT_M === "number"
            ? CORRIDOR_ALT_M
            : 0;
      const altA_m = Number.isFinite(altA) ? altA : fallbackAlt;
      const altB_m = Number.isFinite(altB) ? altB : fallbackAlt;

      const makeLine = (startCoord, endCoord, startAlt, endAlt, from, to) => {
        const lonA = Number(startCoord[0]);
        const latA = Number(startCoord[1]);
        const lonB = Number(endCoord[0]);
        const latB = Number(endCoord[1]);
        if (
          !Number.isFinite(lonA) ||
          !Number.isFinite(latA) ||
          !Number.isFinite(lonB) ||
          !Number.isFinite(latB)
        ) {
          return;
        }
        const start = maplibregl.MercatorCoordinate.fromLngLat([lonA, latA], startAlt);
        const end = maplibregl.MercatorCoordinate.fromLngLat([lonB, latB], endAlt);
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const dz = end.z - start.z;
        const len = Math.hypot(dx, dy);
        if (!Number.isFinite(len) || len === 0) {
          return;
        }
        const unitsPerMeter =
          typeof start.meterInMercatorCoordinateUnits === "function"
            ? start.meterInMercatorCoordinateUnits()
            : approxUnitsPerMeter(latA);
        const lengthMeters = unitsPerMeter > 0 ? len / unitsPerMeter : len;
        const segCount = Math.max(1, Math.ceil(lengthMeters / SEGMENT_LENGTH_M));
        const freeflowKts = kind === "vertiport" ? FREEFLOW_VERTIPORT_KTS : FREEFLOW_ROUTE_KTS;
        const freeflowMps = freeflowKts * KNOT_TO_MPS;
        // Right-hand traffic offset (MapLibre Mercator y increases south).
        const rx = -dy / len;
        const ry = dx / len;
        const px = dy / len;
        const py = -dx / len;

        const key = directedKey(from, to);
        if (!key) {
          return;
        }
        index.set(key, {
          key,
          from,
          to,
          start,
          end,
          dx,
          dy,
          dz,
          len,
          len2: len * len,
          segCount,
          freeflowMps,
          offsetDir: { x: rx, y: ry },
          perpDir: { x: px, y: py },
        });
      };

      makeLine(line.start.coord, line.end.coord, altA_m, altB_m, fromName, toName);
      makeLine(line.end.coord, line.start.coord, altB_m, altA_m, toName, fromName);
    };

    const corridor = this.corridorData;
    const corridorLines = corridor && Array.isArray(corridor.lines) ? corridor.lines : [];
    const spareLines = corridor && Array.isArray(corridor.spareLines) ? corridor.spareLines : [];
    const vertiport = this.vertiportData;
    const vertiportLines = vertiport && Array.isArray(vertiport.lines) ? vertiport.lines : [];

    corridorLines.forEach((line) => addUndirected(line, "main"));
    spareLines.forEach((line) => addUndirected(line, "spare"));
    vertiportLines.forEach((line) => addUndirected(line, "vertiport"));

    this.congestionLineIndex = index;
  };

  MapApp.prototype.updateCongestionOverlay = function (force = false) {
    if (!this.congestionEnabled && !force) {
      return;
    }
    if (!this.map) {
      return;
    }
    this.ensureCongestionLayers();

    const unitsPerPixel =
      typeof this.getMercatorUnitsPerPixel === "function" ? this.getMercatorUnitsPerPixel() : 0;
    if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
      if (this.congestionEnabled) {
        this.scheduleCongestionUpdate(true);
      }
      return;
    }

    const corridor = this.corridorData;
    const corridorLines = corridor && Array.isArray(corridor.lines) ? corridor.lines : [];
    const spareLines = corridor && Array.isArray(corridor.spareLines) ? corridor.spareLines : [];
    const vertiport = this.vertiportData;
    const vertiportLines = vertiport && Array.isArray(vertiport.lines) ? vertiport.lines : [];

    const clearAll = () => {
      if (
        this.congestionBase3dLayer &&
        typeof this.congestionBase3dLayer.updatePositions === "function"
      ) {
        this.congestionBase3dLayer.updatePositions([]);
      }
      if (
        this.congestionDynamic3dLayer &&
        typeof this.congestionDynamic3dLayer.updatePositions === "function"
      ) {
        this.congestionDynamic3dLayer.updatePositions(EMPTY_FLOAT32);
      }
      this.congestionLastDynamicNonEmpty = false;
      const labelSource = this.map.getSource && this.map.getSource(CONGESTION_LABEL_SOURCE_ID);
      if (labelSource && typeof labelSource.setData === "function") {
        labelSource.setData({ type: "FeatureCollection", features: [] });
      }
      if (this.congestionLabelCache instanceof Map) {
        this.congestionLabelCache.clear();
      } else {
        this.congestionLabelCache = new Map();
      }
      if (this.congestionLabelMarkers instanceof Map) {
        for (const entry of this.congestionLabelMarkers.values()) {
          if (entry && entry.marker && typeof entry.marker.remove === "function") {
            entry.marker.remove();
          }
        }
        this.congestionLabelMarkers.clear();
      }
      this.congestionLabelDirty = false;
      this.congestionLastLabelsNonEmpty = false;
      if (typeof this.map.triggerRepaint === "function") {
        this.map.triggerRepaint();
      }
    };

    if (!corridorLines.length && !spareLines.length && !vertiportLines.length) {
      clearAll();
      const dataReady = Boolean(corridor) || Boolean(vertiport);
      if (this.congestionEnabled && !dataReady) {
        this.scheduleCongestionUpdate(false);
      }
      return;
    }

    const baseLayer = this.congestionBase3dLayer;
    const baseLineCount =
      baseLayer && Number.isFinite(baseLayer._lineCount) ? baseLayer._lineCount : 0;
    const buildBase = Boolean(this.congestionGeometryDirty || !baseLayer || baseLineCount === 0);
    if (buildBase || !this.congestionLineIndex || !this.congestionLineIndex.size) {
      this.buildCongestionLineIndex();
    }

    const halfWidth = (LANE_WIDTH_PX * unitsPerPixel) / 2;
    const offset = ((LANE_WIDTH_PX / 2) + LANE_GAP_PX) * unitsPerPixel;

    const basePositions = buildBase ? [] : null;
    const coloredPositions = [];

    const zoom = typeof this.map.getZoom === "function" ? Number(this.map.getZoom()) : 0;
    const buildLabels = this.congestionEnabled && Number.isFinite(zoom) && zoom >= LABEL_MIN_ZOOM;
    const useHtmlLabels = Boolean(this.congestionUseHtmlLabels);
    const activeLabelKeys = useHtmlLabels ? new Set() : null;

    const now =
      typeof this.getCongestionTimeMs === "function" ? this.getCongestionTimeMs() : nowMs();
    const maxWindowStart = now - CONGESTION_MAX_WINDOW_MS;
    const windowStart = now - this.congestionWindowMs;
    const threshold = this.congestionSpeedRatioThreshold;
    const metric = resolveCongestionMetric(this.congestionMetric);

    const pushQuad = (arr, sx, sy, sz, ex, ey, ez, ox, oy) => {
      if (!arr) {
        return;
      }
      arr.push(
        sx + ox,
        sy + oy,
        sz,
        sx - ox,
        sy - oy,
        sz,
        ex + ox,
        ey + oy,
        ez,
        ex + ox,
        ey + oy,
        ez,
        sx - ox,
        sy - oy,
        sz,
        ex - ox,
        ey - oy,
        ez,
      );
    };

    const pushQuadBinned = (arr, sx, sy, sz, ex, ey, ez, ox, oy, binIndex) => {
      if (!arr) {
        return;
      }
      const b = Number.isFinite(binIndex) ? binIndex : 0;
      arr.push(
        sx + ox,
        sy + oy,
        sz,
        b,
        sx - ox,
        sy - oy,
        sz,
        b,
        ex + ox,
        ey + oy,
        ez,
        b,
        ex + ox,
        ey + oy,
        ez,
        b,
        sx - ox,
        sy - oy,
        sz,
        b,
        ex - ox,
        ey - oy,
        ez,
        b,
      );
    };

    const renderLineBase = (line) => {
      if (!buildBase || !line) {
        return;
      }
      const segCount = line.segCount || 1;
      const invSegCount = 1 / segCount;
      for (let i = 0; i < segCount; i += 1) {
        const t0 = i * invSegCount;
        const t1 = (i + 1) * invSegCount;
        const x0 = line.start.x + line.dx * t0;
        const y0 = line.start.y + line.dy * t0;
        const z0 = line.start.z + line.dz * t0;
        const x1 = line.start.x + line.dx * t1;
        const y1 = line.start.y + line.dy * t1;
        const z1 = line.start.z + line.dz * t1;
        const sx = x0 + line.offsetDir.x * offset;
        const sy = y0 + line.offsetDir.y * offset;
        const ex = x1 + line.offsetDir.x * offset;
        const ey = y1 + line.offsetDir.y * offset;
        pushQuad(
          basePositions,
          sx,
          sy,
          z0,
          ex,
          ey,
          z1,
          line.perpDir.x * halfWidth,
          line.perpDir.y * halfWidth,
        );
      }
    };

    const renderLineCongestion = (line, segmentsOverride) => {
      if (!line) {
        return;
      }
      const lineKey = line.key;
      const segments = segmentsOverride || this.congestionSegmentsByLine.get(lineKey);
      if (!segments || !segments.size) {
        return;
      }

      const segCount = line.segCount || 1;
      const invSegCount = 1 / segCount;
      let labelSum = 0;
      let labelCount = 0;
      let congestedSegCount = 0;
      const congestedSegmentIndices = metric === CONGESTION_METRIC_CEI ? [] : null;

      segments.forEach((segIndex) => {
        const segKey = `${lineKey}|${segIndex}`;
        const stats = this.pruneCongestionSamples(
          segKey,
          maxWindowStart,
          windowStart,
          now,
          lineKey,
          segIndex,
          line.freeflowMps,
          threshold,
        );
        const meanSpeed = stats ? stats.meanSpeed : null;
        if (!Number.isFinite(meanSpeed) || meanSpeed <= 0) {
          return;
        }
        const ratio = meanSpeed / line.freeflowMps;
        if (!Number.isFinite(ratio)) {
          return;
        }

        const congestedMs = stats && Number.isFinite(stats.congestedMs) ? stats.congestedMs : 0;
        if (congestedMs > 0) {
          congestedSegCount += 1;
          if (congestedSegmentIndices) {
            congestedSegmentIndices.push(segIndex);
          }
        }

        if (metric === CONGESTION_METRIC_CEI) {
          return;
        }

        let value = 0;
        if (metric === CONGESTION_METRIC_CDI) {
          const windowMs = stats && Number.isFinite(stats.windowMs) ? stats.windowMs : 0;
          if (windowMs > 0) {
            value = (congestedMs / windowMs) * 100;
          }
        } else {
          if (ratio >= threshold) {
            return;
          }
          value = (1 - ratio) * 100;
        }

        value = Math.max(0, Math.min(100, value));
        const valueRounded = Math.round(value);
        if (valueRounded <= 0) {
          return;
        }
        const binIndex = findBinIndex(valueRounded);
        if (binIndex < 0) {
          return;
        }
        const t0 = segIndex * invSegCount;
        const t1 = (segIndex + 1) * invSegCount;
        const x0 = line.start.x + line.dx * t0;
        const y0 = line.start.y + line.dy * t0;
        const z0 = line.start.z + line.dz * t0;
        const x1 = line.start.x + line.dx * t1;
        const y1 = line.start.y + line.dy * t1;
        const z1 = line.start.z + line.dz * t1;
        const sx = x0 + line.offsetDir.x * offset;
        const sy = y0 + line.offsetDir.y * offset;
        const ex = x1 + line.offsetDir.x * offset;
        const ey = y1 + line.offsetDir.y * offset;
        pushQuadBinned(
          coloredPositions,
          sx,
          sy,
          z0,
          ex,
          ey,
          z1,
          line.perpDir.x * halfWidth,
          line.perpDir.y * halfWidth,
          binIndex,
        );
        labelSum += valueRounded;
        labelCount += 1;
      });

      if (metric === CONGESTION_METRIC_CEI) {
        const extentValue = segCount > 0 ? (congestedSegCount / segCount) * 100 : 0;
        const valueRounded = Math.round(Math.max(0, Math.min(100, extentValue)));
        if (valueRounded > 0 && congestedSegmentIndices && congestedSegmentIndices.length) {
          const binIndex = findBinIndex(valueRounded);
          if (binIndex >= 0) {
            for (let i = 0; i < congestedSegmentIndices.length; i += 1) {
              const segIndex = congestedSegmentIndices[i];
              const t0 = segIndex * invSegCount;
              const t1 = (segIndex + 1) * invSegCount;
              const x0 = line.start.x + line.dx * t0;
              const y0 = line.start.y + line.dy * t0;
              const z0 = line.start.z + line.dz * t0;
              const x1 = line.start.x + line.dx * t1;
              const y1 = line.start.y + line.dy * t1;
              const z1 = line.start.z + line.dz * t1;
              const sx = x0 + line.offsetDir.x * offset;
              const sy = y0 + line.offsetDir.y * offset;
              const ex = x1 + line.offsetDir.x * offset;
              const ey = y1 + line.offsetDir.y * offset;
              pushQuadBinned(
                coloredPositions,
                sx,
                sy,
                z0,
                ex,
                ey,
                z1,
                line.perpDir.x * halfWidth,
                line.perpDir.y * halfWidth,
                binIndex,
              );
            }
            labelSum = valueRounded;
            labelCount = 1;
          }
        }
      }

      if (buildLabels && labelCount > 0) {
        const avgValue = Math.round(labelSum / labelCount);
        const labelKey = this.setCongestionLabelFeature(line, offset, avgValue);
        if (activeLabelKeys && labelKey) {
          activeLabelKeys.add(labelKey);
        }
      }
    };

    if (this.congestionLineIndex && this.congestionLineIndex.size) {
      if (buildBase) {
        for (const line of this.congestionLineIndex.values()) {
          renderLineBase(line);
        }
      }
      if (this.congestionSegmentsByLine instanceof Map && this.congestionSegmentsByLine.size) {
        for (const [lineKey, segments] of this.congestionSegmentsByLine.entries()) {
          const line = this.congestionLineIndex.get(lineKey);
          if (!line) {
            continue;
          }
          renderLineCongestion(line, segments);
        }
      }
    }

    if (
      buildBase &&
      this.congestionBase3dLayer &&
      typeof this.congestionBase3dLayer.updatePositions === "function"
    ) {
      this.congestionBase3dLayer.updatePositions(basePositions);
    }

    if (
      this.congestionDynamic3dLayer &&
      typeof this.congestionDynamic3dLayer.updatePositions === "function"
    ) {
      const nonEmpty = coloredPositions.length > 0;
      if (nonEmpty || this.congestionLastDynamicNonEmpty) {
        const data = nonEmpty ? new Float32Array(coloredPositions) : EMPTY_FLOAT32;
        this.congestionDynamic3dLayer.updatePositions(data);
      }
      this.congestionLastDynamicNonEmpty = nonEmpty;
    }

    if (useHtmlLabels) {
      this.pruneCongestionLabelMarkers(activeLabelKeys);
      this.setCongestionLabelMarkersVisible(buildLabels);
      this.declutterCongestionLabelMarkers();
      this.congestionLastLabelsNonEmpty = this.congestionLabelMarkers instanceof Map
        ? this.congestionLabelMarkers.size > 0
        : false;
      this.congestionLabelDirty = false;
    } else {
      const labelSource = this.map.getSource && this.map.getSource(CONGESTION_LABEL_SOURCE_ID);
      const labelFeatures =
        this.congestionLabelCache instanceof Map ? Array.from(this.congestionLabelCache.values()) : [];
      const labelsNonEmpty = labelFeatures.length > 0;
      const shouldUpdateLabels =
        this.congestionLabelDirty || labelsNonEmpty !== this.congestionLastLabelsNonEmpty;
      if (labelSource && typeof labelSource.setData === "function" && shouldUpdateLabels) {
        labelSource.setData({ type: "FeatureCollection", features: labelFeatures });
      }
      this.congestionLastLabelsNonEmpty = labelsNonEmpty;
      this.congestionLabelDirty = false;
    }

    if (typeof this.map.triggerRepaint === "function") {
      this.map.triggerRepaint();
    }

    if (buildBase) {
      this.congestionGeometryDirty = false;
    }
  };

  const baseInit = MapApp.prototype.init;
  if (baseInit) {
    MapApp.prototype.init = function () {
      baseInit.call(this);
      this.initCongestionLayer();
    };
  }

  const baseUpdateTrafficPositions = MapApp.prototype.updateTrafficPositions;
  if (baseUpdateTrafficPositions) {
    MapApp.prototype.updateTrafficPositions = function (positions) {
      const result = baseUpdateTrafficPositions.call(this, positions);
      if (Array.isArray(positions)) {
        this.captureCongestionSamples(positions);
        if (this.congestionEnabled) {
          this.scheduleCongestionUpdate(false);
        }
      }
      return result;
    };
  }

  const baseUpdateCorridorOverlayFromRows = MapApp.prototype.updateCorridorOverlayFromRows;
  if (baseUpdateCorridorOverlayFromRows) {
    MapApp.prototype.updateCorridorOverlayFromRows = function (rows) {
      const result = baseUpdateCorridorOverlayFromRows.call(this, rows);
      this.congestionGeometryDirty = true;
      this.resetCongestionHistory();
      this.congestionLineIndex = new Map();
      if (this.congestionEnabled) {
        this.scheduleCongestionUpdate(true);
      }
      return result;
    };
  }

  const baseUpdateVertiportOverlayFromRows = MapApp.prototype.updateVertiportOverlayFromRows;
  if (baseUpdateVertiportOverlayFromRows) {
    MapApp.prototype.updateVertiportOverlayFromRows = function (rows) {
      const result = baseUpdateVertiportOverlayFromRows.call(this, rows);
      this.congestionGeometryDirty = true;
      this.resetCongestionHistory();
      this.congestionLineIndex = new Map();
      if (this.congestionEnabled) {
        this.scheduleCongestionUpdate(true);
      }
      return result;
    };
  }

  const baseReorderPlanLayers = MapApp.prototype.reorderPlanLayers;
  if (baseReorderPlanLayers) {
    MapApp.prototype.reorderPlanLayers = function () {
      baseReorderPlanLayers.call(this);
      if (!this.map || !this.map.getLayer) {
        return;
      }
      const beforeId = getBeforeId(this.map) || null;

      const move = (id) => {
        if (!id || !this.map.getLayer(id)) {
          return;
        }
        try {
          if (beforeId) {
            this.map.moveLayer(id, beforeId);
          } else {
            this.map.moveLayer(id);
          }
        } catch (_err) {
          // ignore
        }
      };

      move(CONGESTION_BASE_LAYER_ID);
      move(CONGESTION_DYNAMIC_LAYER_ID);
      move(CONGESTION_LABEL_LAYER_ID);
    };
  }

  window.__CONGESTION_SEGMENT_LENGTH_M = SEGMENT_LENGTH_M;
})();
