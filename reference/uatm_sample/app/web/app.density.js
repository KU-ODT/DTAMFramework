(() => {
  const DENSITY_BUTTON_SELECTOR = '[data-action="layer-density"]';

  const UI_SCALE = Number.isFinite(typeof MAP_SIZE_SCALE === "number" ? MAP_SIZE_SCALE : NaN)
    ? MAP_SIZE_SCALE
    : 1;

  const DENSITY_BASE_LAYER_ID = "corridor-density-base-3d";
  const DENSITY_DYNAMIC_LAYER_ID = "corridor-density-dynamic-3d";
  const DENSITY_LABEL_SOURCE_ID = "corridor-density-labels";
  const DENSITY_LABEL_LAYER_ID = "corridor-density-labels";

  const EMPTY_FLOAT32 = new Float32Array(0);

  const BASE_COLOR = "#f3f4f6";
  const BASE_ALPHA = 0.22;
  const BIN_ALPHA = 0.92;

  // Wide, area-like lanes in screen pixels.
  const LANE_WIDTH_PX = 14 * UI_SCALE;
  const LANE_GAP_PX = 1.8 * UI_SCALE;

  const DENSITY_SEGMENT_LENGTH_M = 1000;

  const LABEL_MIN_ZOOM = 12;

  const DENSITY_BINS = [
    { id: "b1", min: 1, max: 1, color: "#60a5fa" },
    { id: "b2", min: 2, max: 3, color: "#34d399" },
    { id: "b3", min: 4, max: 5, color: "#fbbf24" },
    { id: "b4", min: 6, max: 9, color: "#fb923c" },
    { id: "b5", min: 10, max: 19, color: "#ef4444" },
    { id: "b6", min: 20, max: Number.POSITIVE_INFINITY, color: "#b91c1c" },
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

  const segmentKey = (lineKey, segmentIndex) => `${lineKey}::${segmentIndex}`;

  const parseSegmentKey = (key) => {
    const text = String(key || "");
    const marker = "::";
    const idx = text.lastIndexOf(marker);
    if (idx < 0) {
      return null;
    }
    const lineKey = text.slice(0, idx);
    const segmentText = text.slice(idx + marker.length);
    const segmentIndex = Number.parseInt(segmentText, 10);
    if (!lineKey || !Number.isFinite(segmentIndex)) {
      return null;
    }
    return { lineKey, segmentIndex };
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

  const degToRad = (value) => (Number(value) * Math.PI) / 180;

  const distanceMeters = (lon1, lat1, lon2, lat2) => {
    const r = 6371000;
    const phi1 = degToRad(lat1);
    const phi2 = degToRad(lat2);
    const dPhi = phi2 - phi1;
    const dLam = degToRad(lon2 - lon1);
    if (![phi1, phi2, dPhi, dLam].every(Number.isFinite)) {
      return 0;
    }
    const a =
      Math.sin(dPhi / 2) * Math.sin(dPhi / 2) +
      Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLam / 2) * Math.sin(dLam / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return r * c;
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

  const findBinIndex = (count) => {
    const value = Math.max(0, Number(count) || 0);
    for (let i = 0; i < DENSITY_BINS.length; i += 1) {
      const bin = DENSITY_BINS[i];
      if (value >= bin.min && value <= bin.max) {
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

  const nowMs = () =>
    typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now()
      : Date.now();

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

  MapApp.prototype.initDensityLayer = function () {
    this.densityEnabled = false;
    this.densityLayerButton = document.querySelector(DENSITY_BUTTON_SELECTOR);
    this.densityPositions = [];
    this.densityPositionsVersion = 0;
    this.densityCountsVersion = -1;
    this.densitySegmentCounts = new Map();

    this.densityUpdateScheduled = false;
    this.densityUpdateForced = false;
    this.densityUpdateLastAt = 0;
    this.densityUpdateMinIntervalMs = 700;
    this.densityUpdateTimer = null;
    this.densityUpdateRafId = null;
    this.densityGeometryDirty = true;
    this.densityLineIndex = null;
    this.densityLastLabelsNonEmpty = false;
    this.densityLastDynamicNonEmpty = false;
    this.densityOverlayAlpha = 0;
    this.densityFadeRafId = null;
    this.densityFadeDurationMs = 220;
    this.densityLabelUpdateMinIntervalMs = 900;
    this.densityLabelLastAt = 0;

    this.densityBase3dLayer = null;
    this.densityDynamic3dLayer = null;
    this.densityResizeBound = false;

    if (this.densityLayerButton) {
      this.densityLayerButton.addEventListener("click", () => {
        this.setDensityEnabled(!this.densityEnabled);
        if (this.setBaseListOpen) {
          this.setBaseListOpen(false);
        }
      });
      this.densityLayerButton.setAttribute("aria-pressed", "false");
    }

    if (!this.map) {
      return;
    }
    const onReady = () => {
      this.ensureDensityLayers();
      this.scheduleDensityUpdate(true);
    };
    if (typeof this.map.isStyleLoaded === "function" && this.map.isStyleLoaded()) {
      onReady();
      return;
    }
    if (typeof this.map.once === "function") {
      this.map.once("load", () => onReady());
    }
  };

  MapApp.prototype.setupDensityResize = function () {
    if (!this.map || this.densityResizeBound) {
      return;
    }
    this.densityResizeBound = true;
    const update = () => {
      if (this.densityEnabled) {
        this.densityGeometryDirty = true;
        this.densityLineIndex = null;
        this.scheduleDensityUpdate(true);
      }
    };
    this.map.on("zoomend", update);
    this.map.on("resize", update);
  };

  MapApp.prototype.ensureDensityLayers = function () {
    if (!this.map || typeof this.map.isStyleLoaded !== "function" || !this.map.isStyleLoaded()) {
      return;
    }

    const beforeId = getBeforeId(this.map);
    let changed = false;

    if (!this.map.getLayer(DENSITY_BASE_LAYER_ID)) {
      const layer = this.createLineLayer3d(DENSITY_BASE_LAYER_ID, BASE_COLOR, "TRIANGLES");
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
          layer.setVisible(this.densityEnabled);
        } else {
          layer._visible = this.densityEnabled;
        }
        // Always treat density as a visualization overlay.
        layer._useDepth = false;
      }
      this.densityBase3dLayer = layer;
      try {
        this.map.addLayer(layer, beforeId);
        changed = true;
      } catch (_err) {
        // ignore
      }
    }

    if (!this.map.getLayer(DENSITY_DYNAMIC_LAYER_ID)) {
      const layer = createBinnedTrianglesLayer3d(DENSITY_DYNAMIC_LAYER_ID, DENSITY_BINS, BIN_ALPHA);
      if (layer) {
        if (layer.setVisible) {
          layer.setVisible(this.densityEnabled);
        } else {
          layer._visible = this.densityEnabled;
        }
        layer._useDepth = false;
      }
      this.densityDynamic3dLayer = layer;
      try {
        this.map.addLayer(layer, beforeId);
        changed = true;
      } catch (_err) {
        // ignore
      }
    }

    const empty = { type: "FeatureCollection", features: [] };
    if (!this.map.getSource(DENSITY_LABEL_SOURCE_ID)) {
      try {
        this.map.addSource(DENSITY_LABEL_SOURCE_ID, { type: "geojson", data: empty });
        changed = true;
      } catch (_err) {
        // ignore
      }
    }

    if (!this.map.getLayer(DENSITY_LABEL_LAYER_ID)) {
      try {
        this.map.addLayer(
          {
            id: DENSITY_LABEL_LAYER_ID,
            type: "symbol",
            source: DENSITY_LABEL_SOURCE_ID,
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
              // Let MapLibre handle decluttering via collision detection.
              // Prioritize higher density labels via sort-key.
              "symbol-sort-key": ["-", ["get", "count"]],
              "text-allow-overlap": false,
              "text-ignore-placement": false,
              "text-padding": 2,
              "text-variable-anchor": ["top", "bottom", "left", "right"],
              "text-radial-offset": 0.6,
              "text-justify": "auto",
              "text-pitch-alignment": "map",
              "text-rotation-alignment": "map",
              visibility: this.densityEnabled ? "visible" : "none",
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
        this.map.setLayoutProperty(
          DENSITY_LABEL_LAYER_ID,
          "visibility",
          this.densityEnabled ? "visible" : "none",
        );
      } catch (_err) {
        // ignore
      }
    }

    this.setupDensityResize();
    if (changed && typeof this.reorderPlanLayers === "function") {
      this.reorderPlanLayers();
    }

    if (typeof this.applyDensityOverlayAlpha === "function") {
      const fallbackAlpha = this.densityEnabled ? 1 : 0;
      const nextAlpha = Number.isFinite(this.densityOverlayAlpha)
        ? this.densityOverlayAlpha
        : fallbackAlpha;
      this.applyDensityOverlayAlpha(nextAlpha);
    }
  };

  MapApp.prototype.applyDensityOverlayAlpha = function (alpha) {
    const next = clamp01(alpha);
    this.densityOverlayAlpha = next;
    if (this.densityBase3dLayer) {
      if (typeof this.densityBase3dLayer.setAlpha === "function") {
        this.densityBase3dLayer.setAlpha(BASE_ALPHA * next);
      } else {
        this.densityBase3dLayer._colorAlpha = BASE_ALPHA * next;
      }
    }
    if (this.densityDynamic3dLayer) {
      if (typeof this.densityDynamic3dLayer.setAlpha === "function") {
        this.densityDynamic3dLayer.setAlpha(next);
      } else {
        this.densityDynamic3dLayer._alpha = next;
      }
    }
    if (this.map && this.map.getLayer && this.map.getLayer(DENSITY_LABEL_LAYER_ID)) {
      try {
        this.map.setPaintProperty(DENSITY_LABEL_LAYER_ID, "text-opacity", next);
        this.map.setPaintProperty(DENSITY_LABEL_LAYER_ID, "text-halo-opacity", next);
      } catch (_err) {
        // ignore
      }
    }
  };

  MapApp.prototype.startDensityFade = function (visible) {
    const target = visible ? 1 : 0;
    const startAlpha = Number.isFinite(this.densityOverlayAlpha)
      ? this.densityOverlayAlpha
      : visible
        ? 0
        : 1;
    const duration = Math.max(
      0,
      Number.isFinite(this.densityFadeDurationMs) ? this.densityFadeDurationMs : 220,
    );

    if (this.densityFadeRafId != null && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(this.densityFadeRafId);
      this.densityFadeRafId = null;
    }

    const startAt = nowMs();
    const tick = () => {
      const elapsed = nowMs() - startAt;
      const t = duration > 0 ? Math.min(1, elapsed / duration) : 1;
      const eased = easeOutCubic(t);
      const alpha = startAlpha + (target - startAlpha) * eased;
      this.applyDensityOverlayAlpha(alpha);
      if (this.map && typeof this.map.triggerRepaint === "function") {
        this.map.triggerRepaint();
      }
      if (t < 1) {
        this.densityFadeRafId = requestAnimationFrame(tick);
      } else {
        this.densityFadeRafId = null;
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
          setVisible(this.densityBase3dLayer, false);
          setVisible(this.densityDynamic3dLayer, false);
          try {
            this.map.setLayoutProperty(DENSITY_LABEL_LAYER_ID, "visibility", "none");
          } catch (_err) {
            // ignore
          }
          const source = this.map.getSource && this.map.getSource(DENSITY_LABEL_SOURCE_ID);
          if (source && typeof source.setData === "function") {
            source.setData({ type: "FeatureCollection", features: [] });
          }
          this.densityLastLabelsNonEmpty = false;
          this.densityLastDynamicNonEmpty = false;
        }
      }
    };

    this.densityFadeRafId = requestAnimationFrame(tick);
  };

  MapApp.prototype.setDensityEnabled = function (enabled) {
    const next = Boolean(enabled);
    if (next && typeof this.disableOtherBaseLayers === "function") {
      this.disableOtherBaseLayers("density");
    }
    this.densityEnabled = next;

    if (typeof document !== "undefined") {
      document.body.classList.toggle("density-visible", next);
    }
    if (this.densityLayerButton) {
      this.densityLayerButton.classList.toggle("is-active", next);
      this.densityLayerButton.setAttribute("aria-pressed", next ? "true" : "false");
    }

    if (!this.map) {
      return;
    }
    this.ensureDensityLayers();

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
      setVisible(this.densityBase3dLayer, true);
      setVisible(this.densityDynamic3dLayer, true);
      try {
        this.map.setLayoutProperty(DENSITY_LABEL_LAYER_ID, "visibility", "visible");
      } catch (_err) {
        // ignore
      }
      this.densityGeometryDirty = true;
      this.densityLineIndex = null;
      this.scheduleDensityUpdate(true);
      try {
        this.updateDensityOverlay(true);
      } catch (_err) {
        // ignore
      }
      this.startDensityFade(true);
    } else {
      if (this.densityUpdateTimer != null) {
        clearTimeout(this.densityUpdateTimer);
        this.densityUpdateTimer = null;
      }
      if (this.densityUpdateRafId != null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(this.densityUpdateRafId);
        this.densityUpdateRafId = null;
      }
      this.densityUpdateScheduled = false;
      this.densityUpdateForced = false;
      this.startDensityFade(false);
    }

    if (typeof this.map.triggerRepaint === "function") {
      this.map.triggerRepaint();
    }
  };

  MapApp.prototype.scheduleDensityUpdate = function (force = false) {
    if (!this.map) {
      return;
    }
    if (force) {
      this.densityUpdateForced = true;
    }
    const now =
      typeof performance !== "undefined" && typeof performance.now === "function"
        ? performance.now()
        : Date.now();
    const lastAt = Number.isFinite(this.densityUpdateLastAt) ? this.densityUpdateLastAt : 0;
    const minInterval = Math.max(
      0,
      Number.isFinite(this.densityUpdateMinIntervalMs) ? this.densityUpdateMinIntervalMs : 160,
    );
    const delay = force ? 0 : Math.max(0, minInterval - (now - lastAt));

    const run = () => {
      this.densityUpdateRafId = null;
      this.densityUpdateTimer = null;
      this.densityUpdateScheduled = false;
      const forced = Boolean(this.densityUpdateForced);
      this.densityUpdateForced = false;
      this.densityUpdateLastAt =
        typeof performance !== "undefined" && typeof performance.now === "function"
          ? performance.now()
          : Date.now();
      this.updateDensityOverlay(forced);
    };

    const scheduleRaf = () => {
      if (this.densityUpdateRafId != null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(this.densityUpdateRafId);
      }
      this.densityUpdateRafId = requestAnimationFrame(run);
    };

    if (this.densityUpdateScheduled) {
      // Upgrade delayed updates to immediate when force is requested.
      if (force && this.densityUpdateTimer != null) {
        clearTimeout(this.densityUpdateTimer);
        this.densityUpdateTimer = null;
        scheduleRaf();
      }
      return;
    }

    this.densityUpdateScheduled = true;
    if (delay <= 0) {
      scheduleRaf();
      return;
    }
    this.densityUpdateTimer = setTimeout(scheduleRaf, delay);
  };

  MapApp.prototype.buildDensityLineIndex = function () {
    const corridor = this.corridorData;
    const corridorLines = corridor && Array.isArray(corridor.lines) ? corridor.lines : [];
    const spareLines = corridor && Array.isArray(corridor.spareLines) ? corridor.spareLines : [];
    const vertiport = this.vertiportData;
    const vertiportLines = vertiport && Array.isArray(vertiport.lines) ? vertiport.lines : [];

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

      const addDirected = (startCoord, endCoord, startAlt, endAlt, from, to) => {
        if (!Array.isArray(startCoord) || !Array.isArray(endCoord)) {
          return;
        }
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
        const lenMerc = Math.hypot(dx, dy);
        if (!Number.isFinite(lenMerc) || lenMerc === 0) {
          return;
        }

        const directed = directedKey(from, to);
        if (!directed) {
          return;
        }

        let unitsPerMeter = 0;
        let unitsPerMeterCount = 0;
        if (typeof start.meterInMercatorCoordinateUnits === "function") {
          const startUnits = start.meterInMercatorCoordinateUnits();
          if (Number.isFinite(startUnits) && startUnits > 0) {
            unitsPerMeter += startUnits;
            unitsPerMeterCount += 1;
          }
        }
        if (typeof end.meterInMercatorCoordinateUnits === "function") {
          const endUnits = end.meterInMercatorCoordinateUnits();
          if (Number.isFinite(endUnits) && endUnits > 0) {
            unitsPerMeter += endUnits;
            unitsPerMeterCount += 1;
          }
        }
        if (unitsPerMeterCount > 0) {
          unitsPerMeter /= unitsPerMeterCount;
        } else {
          unitsPerMeter = 0;
        }

        let lengthM =
          unitsPerMeter > 0
            ? lenMerc / unitsPerMeter
            : distanceMeters(lonA, latA, lonB, latB);
        if (!Number.isFinite(lengthM) || lengthM <= 0) {
          lengthM = 0;
        }
        const metersPerMerc = lengthM > 0 ? lengthM / lenMerc : 0;
        const segCount =
          lengthM > 0 ? Math.max(1, Math.ceil(lengthM / DENSITY_SEGMENT_LENGTH_M)) : 1;

        // Right-hand traffic offset (MapLibre Mercator y increases south).
        const rx = -dy / lenMerc;
        const ry = dx / lenMerc;

        // Perpendicular direction for lane width.
        const px = dy / lenMerc;
        const py = -dx / lenMerc;

        index.set(directed, {
          key: directed,
          from,
          to,
          start,
          end,
          offsetDir: { x: rx, y: ry },
          perpDir: { x: px, y: py },
          mid: { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 },
          dir: { x: dx / lenMerc, y: dy / lenMerc },
          lengthMerc: lenMerc,
          lengthM: lengthM,
          metersPerMerc: metersPerMerc,
          segmentCount: segCount,
        });
      };

      addDirected(line.start.coord, line.end.coord, altA_m, altB_m, fromName, toName);
      addDirected(line.end.coord, line.start.coord, altB_m, altA_m, toName, fromName);
    };

    corridorLines.forEach((line) => addUndirected(line, "main"));
    spareLines.forEach((line) => addUndirected(line, "spare"));
    vertiportLines.forEach((line) => addUndirected(line, "vertiport"));

    this.densityLineIndex = index;
    this.densityCountsVersion = -1;
    if (this.densitySegmentCounts instanceof Map) {
      this.densitySegmentCounts.clear();
    } else {
      this.densitySegmentCounts = new Map();
    }
  };

  MapApp.prototype.updateDensityOverlay = function (force = false) {
    if (!this.densityEnabled && !force) {
      return;
    }
    if (!this.map) {
      return;
    }
    this.ensureDensityLayers();

    const unitsPerPixel =
      typeof this.getMercatorUnitsPerPixel === "function" ? this.getMercatorUnitsPerPixel() : 0;
    if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
      if (this.densityEnabled) {
        this.scheduleDensityUpdate(true);
      }
      return;
    }

    const clearAll = () => {
      if (this.densityBase3dLayer && typeof this.densityBase3dLayer.updatePositions === "function") {
        this.densityBase3dLayer.updatePositions([]);
      }
      if (
        this.densityDynamic3dLayer &&
        typeof this.densityDynamic3dLayer.updatePositions === "function"
      ) {
        this.densityDynamic3dLayer.updatePositions(EMPTY_FLOAT32);
      }
      this.densityLastDynamicNonEmpty = false;
      const labelSource = this.map.getSource && this.map.getSource(DENSITY_LABEL_SOURCE_ID);
      if (labelSource && typeof labelSource.setData === "function") {
        labelSource.setData({ type: "FeatureCollection", features: [] });
      }
      this.densityLastLabelsNonEmpty = false;
      if (typeof this.map.triggerRepaint === "function") {
        this.map.triggerRepaint();
      }
    };

    const baseLayer = this.densityBase3dLayer;
    const baseLineCount =
      baseLayer && Number.isFinite(baseLayer._lineCount) ? baseLayer._lineCount : 0;
    const buildBase = Boolean(
      this.densityGeometryDirty || !baseLayer || baseLineCount === 0,
    );
    if (buildBase || !(this.densityLineIndex instanceof Map)) {
      this.buildDensityLineIndex();
    }
    const lineIndex = this.densityLineIndex instanceof Map ? this.densityLineIndex : null;
    if (!lineIndex || !lineIndex.size) {
      clearAll();
      this.densityGeometryDirty = false;
      const corridor = this.corridorData;
      const vertiport = this.vertiportData;
      const dataReady = Boolean(corridor) || Boolean(vertiport);
      if (this.densityEnabled && !dataReady) {
        this.scheduleDensityUpdate(false);
      }
      return;
    }

    const positions = Array.isArray(this.densityPositions) ? this.densityPositions : [];
    const positionsVersion = Number.isFinite(this.densityPositionsVersion)
      ? this.densityPositionsVersion
      : 0;
    const countsVersion = Number.isFinite(this.densityCountsVersion) ? this.densityCountsVersion : -1;
    let segmentCounts =
      this.densitySegmentCounts instanceof Map ? this.densitySegmentCounts : new Map();
    if (positionsVersion !== countsVersion || !segmentCounts.size) {
      segmentCounts = new Map();
      for (let i = 0; i < positions.length; i += 1) {
        const pos = positions[i];
        if (!pos) {
          continue;
        }
        const key = directedKey(pos.route_from, pos.route_to);
        if (!key) {
          continue;
        }
        const line = lineIndex.get(key);
        if (
          !line ||
          !Number.isFinite(line.lengthM) ||
          line.lengthM <= 0 ||
          !Number.isFinite(line.metersPerMerc) ||
          line.metersPerMerc <= 0 ||
          !line.dir
        ) {
          continue;
        }
        const lon = Number(pos.lon);
        const lat = Number(pos.lat);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          continue;
        }
        const coord = maplibregl.MercatorCoordinate.fromLngLat([lon, lat], 0);
        const vx = coord.x - line.start.x;
        const vy = coord.y - line.start.y;
        const alongMerc = vx * line.dir.x + vy * line.dir.y;
        if (!Number.isFinite(alongMerc)) {
          continue;
        }
        let alongM = alongMerc * line.metersPerMerc;
        if (!Number.isFinite(alongM)) {
          continue;
        }
        alongM = Math.max(0, Math.min(line.lengthM, alongM));
        const segIndex = Math.max(
          0,
          Math.min(
            line.segmentCount > 0 ? line.segmentCount - 1 : 0,
            Math.floor(alongM / DENSITY_SEGMENT_LENGTH_M),
          ),
        );
        const segKey = segmentKey(line.key, segIndex);
        segmentCounts.set(segKey, (segmentCounts.get(segKey) || 0) + 1);
      }
      this.densitySegmentCounts = segmentCounts;
      this.densityCountsVersion = positionsVersion;
    }

    const halfWidth = (LANE_WIDTH_PX * unitsPerPixel) / 2;
    const offset = ((LANE_WIDTH_PX / 2) + LANE_GAP_PX) * unitsPerPixel;

    const basePositions = buildBase ? [] : null;
    const coloredPositions = [];

    const labelFeatures = [];
    const zoom = typeof this.map.getZoom === "function" ? Number(this.map.getZoom()) : 0;
    const buildLabels = this.densityEnabled && Number.isFinite(zoom) && zoom >= LABEL_MIN_ZOOM;

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

    const getSegmentSlice = (line, segmentIndex) => {
      if (!line || !line.dir) {
        return null;
      }
      const lengthMerc = Number.isFinite(line.lengthMerc) ? line.lengthMerc : 0;
      if (lengthMerc <= 0) {
        return null;
      }
      const lengthM = Number.isFinite(line.lengthM) ? line.lengthM : 0;
      const metersPerMerc = Number.isFinite(line.metersPerMerc) ? line.metersPerMerc : 0;
      const segCount = line.segmentCount && line.segmentCount > 0 ? line.segmentCount : 1;
      if (segmentIndex < 0 || segmentIndex >= segCount) {
        return null;
      }
      if (!lengthM || metersPerMerc <= 0) {
        if (segmentIndex !== 0) {
          return null;
        }
        return {
          startMerc: 0,
          endMerc: lengthMerc,
          startZ: line.start.z,
          endZ: line.end.z,
        };
      }
      const segStartM = segmentIndex * DENSITY_SEGMENT_LENGTH_M;
      if (segStartM >= lengthM) {
        return null;
      }
      const segEndM = Math.min(lengthM, segStartM + DENSITY_SEGMENT_LENGTH_M);
      const startMerc = segStartM / metersPerMerc;
      const endMerc = segEndM / metersPerMerc;
      const ratioStart = lengthMerc > 0 ? startMerc / lengthMerc : 0;
      const ratioEnd = lengthMerc > 0 ? endMerc / lengthMerc : 1;
      const startZ = line.start.z + (line.end.z - line.start.z) * ratioStart;
      const endZ = line.start.z + (line.end.z - line.start.z) * ratioEnd;
      return { startMerc, endMerc, startZ, endZ };
    };

    if (buildBase) {
      for (const line of lineIndex.values()) {
        const segCount = line.segmentCount && line.segmentCount > 0 ? line.segmentCount : 1;
        for (let segIndex = 0; segIndex < segCount; segIndex += 1) {
          const seg = getSegmentSlice(line, segIndex);
          if (!seg) {
            continue;
          }
          const sx = line.start.x + line.dir.x * seg.startMerc + line.offsetDir.x * offset;
          const sy = line.start.y + line.dir.y * seg.startMerc + line.offsetDir.y * offset;
          const ex = line.start.x + line.dir.x * seg.endMerc + line.offsetDir.x * offset;
          const ey = line.start.y + line.dir.y * seg.endMerc + line.offsetDir.y * offset;
          const ox = line.perpDir.x * halfWidth;
          const oy = line.perpDir.y * halfWidth;
          pushQuad(basePositions, sx, sy, seg.startZ, ex, ey, seg.endZ, ox, oy);
        }
      }
    }

    segmentCounts.forEach((count, key) => {
      if (!count) {
        return;
      }
      const parsed = parseSegmentKey(key);
      if (!parsed) {
        return;
      }
      const line = lineIndex.get(parsed.lineKey);
      if (!line) {
        return;
      }
      const seg = getSegmentSlice(line, parsed.segmentIndex);
      if (!seg) {
        return;
      }
      const sx = line.start.x + line.dir.x * seg.startMerc + line.offsetDir.x * offset;
      const sy = line.start.y + line.dir.y * seg.startMerc + line.offsetDir.y * offset;
      const ex = line.start.x + line.dir.x * seg.endMerc + line.offsetDir.x * offset;
      const ey = line.start.y + line.dir.y * seg.endMerc + line.offsetDir.y * offset;
      const ox = line.perpDir.x * halfWidth;
      const oy = line.perpDir.y * halfWidth;

      const binIndex = findBinIndex(count);
      if (binIndex >= 0) {
        pushQuadBinned(coloredPositions, sx, sy, seg.startZ, ex, ey, seg.endZ, ox, oy, binIndex);
      }

      if (buildLabels && count > 0) {
        const midMerc = (seg.startMerc + seg.endMerc) / 2;
        const midX = line.start.x + line.dir.x * midMerc + line.offsetDir.x * offset;
        const midY = line.start.y + line.dir.y * midMerc + line.offsetDir.y * offset;
        const lngLat = mercatorToLngLat(midX, midY);
        if (lngLat) {
          const countText = String(count).padStart(2, "0");
          labelFeatures.push({
            type: "Feature",
            geometry: { type: "Point", coordinates: lngLat },
            properties: {
              label: `${countText}`,
              count,
            },
          });
        }
      }
    });
    if (
      buildBase &&
      this.densityBase3dLayer &&
      typeof this.densityBase3dLayer.updatePositions === "function"
    ) {
      this.densityBase3dLayer.updatePositions(basePositions);
    }

    if (this.densityDynamic3dLayer && typeof this.densityDynamic3dLayer.updatePositions === "function") {
      const nonEmpty = coloredPositions.length > 0;
      if (nonEmpty || this.densityLastDynamicNonEmpty) {
        const data = nonEmpty ? new Float32Array(coloredPositions) : EMPTY_FLOAT32;
        this.densityDynamic3dLayer.updatePositions(data);
      }
      this.densityLastDynamicNonEmpty = nonEmpty;
    }

    const labelSource = this.map.getSource && this.map.getSource(DENSITY_LABEL_SOURCE_ID);
    const labelsNonEmpty = labelFeatures.length > 0;
    if (labelSource && typeof labelSource.setData === "function") {
      if (labelsNonEmpty || this.densityLastLabelsNonEmpty) {
        labelSource.setData({ type: "FeatureCollection", features: labelFeatures });
      }
    }
    this.densityLastLabelsNonEmpty = labelsNonEmpty;

    if (typeof this.map.triggerRepaint === "function") {
      this.map.triggerRepaint();
    }

    if (buildBase) {
      this.densityGeometryDirty = false;
    }
  };

  const baseInit = MapApp.prototype.init;
  if (baseInit) {
    MapApp.prototype.init = function () {
      baseInit.call(this);
      this.initDensityLayer();
    };
  }

  const baseUpdateTrafficPositions = MapApp.prototype.updateTrafficPositions;
  if (baseUpdateTrafficPositions) {
    MapApp.prototype.updateTrafficPositions = function (positions) {
      const result = baseUpdateTrafficPositions.call(this, positions);
      if (Array.isArray(positions)) {
        this.densityPositions = positions;
        this.densityPositionsVersion =
          Number.isFinite(this.densityPositionsVersion) ? this.densityPositionsVersion + 1 : 1;
        if (this.densityEnabled) {
          this.scheduleDensityUpdate(false);
        }
      }
      return result;
    };
  }

  const baseUpdateCorridorOverlayFromRows = MapApp.prototype.updateCorridorOverlayFromRows;
  if (baseUpdateCorridorOverlayFromRows) {
    MapApp.prototype.updateCorridorOverlayFromRows = function (rows) {
      const result = baseUpdateCorridorOverlayFromRows.call(this, rows);
      if (this.densityEnabled) {
        this.densityGeometryDirty = true;
        this.densityLineIndex = null;
        this.scheduleDensityUpdate(true);
      }
      return result;
    };
  }

  const baseUpdateVertiportOverlayFromRows = MapApp.prototype.updateVertiportOverlayFromRows;
  if (baseUpdateVertiportOverlayFromRows) {
    MapApp.prototype.updateVertiportOverlayFromRows = function (rows) {
      const result = baseUpdateVertiportOverlayFromRows.call(this, rows);
      if (this.densityEnabled) {
        this.densityGeometryDirty = true;
        this.densityLineIndex = null;
        this.scheduleDensityUpdate(true);
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

      // Bottom -> top.
      move(DENSITY_BASE_LAYER_ID);
      move(DENSITY_DYNAMIC_LAYER_ID);
      move(DENSITY_LABEL_LAYER_ID);
    };
  }
})();
