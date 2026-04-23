const DEFAULT_LATERAL_LIMIT_M = 54;
const clampTrafficValue = (value, min, max) => Math.min(max, Math.max(min, value));

Object.assign(MapApp.prototype, {
    ensureTrafficIcons() {
      if (!this.map) {
        return Promise.resolve(false);
      }
      if (this.trafficIconsReady) {
        return Promise.resolve(true);
      }
      if (this.trafficIconsPromise) {
        return this.trafficIconsPromise;
      }
      const map = this.map;
      this.trafficIconsPromise = new Promise((resolve) => {
        const loaders = TRAFFIC_ICON_IDS.map((iconId) => {
          const url = TRAFFIC_ICON_URLS[iconId];
          return new Promise((done) => {
            map.loadImage(url, (error, image) => {
              if (!error && image && !map.hasImage(iconId)) {
                map.addImage(iconId, image);
                this.createTrafficGlowImage(iconId, image);
              }
              if (!error && image) {
                this.trafficIconImages.set(iconId, image);
                this.createTrafficGlowImage(iconId, image);
              }
              done(!error);
            });
          });
        });
        Promise.all(loaders).then(() => {
          const sizes = TRAFFIC_ICON_IDS.map((iconId) => {
            const image = this.trafficIconImages.get(iconId);
            if (!image) {
              return null;
            }
            const width = image.width || (image.data && image.data.width) || 0;
            const height = image.height || (image.data && image.data.height) || 0;
            if (!width || !height) {
              return null;
            }
            return { iconId, width, height, max: Math.max(width, height) };
          }).filter(Boolean);
          if (sizes.length) {
            const dims = sizes
              .map((entry) => entry.max)
              .filter((value) => value > 0)
              .sort((a, b) => a - b);
            let baseSize = dims.length ? dims[Math.floor(dims.length / 2)] : 0;
            if (!Number.isFinite(baseSize) || baseSize <= 0) {
              baseSize = dims.length ? dims[dims.length - 1] : 0;
            }
            if (baseSize > 0) {
              this.trafficIconBaseSize = baseSize;
              const scales = new Map();
              sizes.forEach((entry) => {
                const scale = entry.max ? baseSize / entry.max : 1;
                scales.set(entry.iconId, scale);
              });
              this.trafficIconScales = scales;
            }
          }
          const ready = map.hasImage(TRAFFIC_FALLBACK_ICON);
          this.trafficIconsReady = ready;
          resolve(ready);
        });
      });
      return this.trafficIconsPromise;
    },

    buildTrafficAtlas() {
      if (this.trafficAtlas) {
        return this.trafficAtlas;
      }
      if (!this.trafficIconImages || this.trafficIconImages.size === 0) {
        return null;
      }
      const fallbackImage = this.trafficIconImages.get(TRAFFIC_FALLBACK_ICON);
      if (!fallbackImage) {
        return null;
      }
      const images = TRAFFIC_ICON_IDS.map(
        (iconId) => this.trafficIconImages.get(iconId) || fallbackImage,
      );
      const sizes = images.map((img) => ({
        width: img.width || (img.data && img.data.width) || 0,
        height: img.height || (img.data && img.data.height) || 0,
      }));
      const dimensions = sizes.map((size) => Math.max(size.width, size.height)).filter(Boolean);
      if (!dimensions.length) {
        return null;
      }
      let baseSize = Number.isFinite(this.trafficIconBaseSize) ? this.trafficIconBaseSize : 0;
      if (!baseSize) {
        const sorted = dimensions.slice().sort((a, b) => a - b);
        baseSize = sorted[Math.floor(sorted.length / 2)] || 0;
      }
      if (!baseSize) {
        return null;
      }
      const iconSize = Math.round(baseSize);
      if (!iconSize) {
        return null;
      }
      this.trafficIconBaseSize = iconSize;
      if (!this.trafficIconScales || this.trafficIconScales.size === 0) {
        const scales = new Map();
        sizes.forEach((size, index) => {
          const maxDim = Math.max(size.width, size.height);
          const iconId = TRAFFIC_ICON_IDS[index];
          if (!iconId) {
            return;
          }
          scales.set(iconId, maxDim ? iconSize / maxDim : 1);
        });
        this.trafficIconScales = scales;
      }
      const padding = 2;
      const cellWidth = iconSize + padding * 2;
      const cellHeight = iconSize + padding * 2;
      const canvas = document.createElement("canvas");
      canvas.width = cellWidth * images.length;
      canvas.height = cellHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return null;
      }
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      images.forEach((img, index) => {
        const size = sizes[index];
        if (!size.width || !size.height) {
          return;
        }
        const maxDim = Math.max(size.width, size.height);
        const scale = maxDim ? iconSize / maxDim : 1;
        const drawWidth = Math.max(1, Math.round(size.width * scale));
        const drawHeight = Math.max(1, Math.round(size.height * scale));
        const x = index * cellWidth + Math.round((cellWidth - drawWidth) / 2);
        const y = Math.round((cellHeight - drawHeight) / 2);
        ctx.drawImage(img, x, y, drawWidth, drawHeight);
      });
      this.trafficAtlas = {
        canvas,
        cellWidth,
        cellHeight,
        iconWidth: iconSize,
        iconHeight: iconSize,
        iconCount: images.length,
      };
      return this.trafficAtlas;
    },

    computeTrafficPointSize(atlas) {
      const pixelRatio = window.devicePixelRatio || 1;
      const size = TRAFFIC_3D_POINT_SIZE * pixelRatio;
      if (!Number.isFinite(size) || size <= 0) {
        return TRAFFIC_3D_MIN_POINT_SIZE;
      }
      return Math.max(TRAFFIC_3D_MIN_POINT_SIZE, size);
    },

    computeTrafficIconPointSize() {
      const pixelRatio = window.devicePixelRatio || 1;
      const size = TRAFFIC_3D_ICON_POINT_SIZE * pixelRatio;
      if (!Number.isFinite(size) || size <= 0) {
        return TRAFFIC_3D_MIN_POINT_SIZE;
      }
      return Math.max(TRAFFIC_3D_MIN_POINT_SIZE, size);
    },

    ensureTraffic3dLayer() {
      if (!this.map) {
        return false;
      }
      if (this.traffic3dLayer && this.map.getLayer(this.traffic3dLayer.id)) {
        return true;
      }
      this.traffic3dLayer = this.createTrafficLayer3d();
      this.map.addLayer(this.traffic3dLayer);
      this.reorderPlanLayers();
      this.updateTrafficLayerVisibility();
      return true;
    },

    ensureTraffic3dIconLayer() {
      if (!TRAFFIC_USE_3D_ICON_LAYER) {
        return false;
      }
      if (!this.map) {
        return false;
      }
      if (this.traffic3dIconLayer && this.map.getLayer(this.traffic3dIconLayer.id)) {
        return true;
      }
      if (this.traffic3dIconInitScheduled) {
        return false;
      }
      this.traffic3dIconInitScheduled = true;
      this.ensureTrafficIcons().then((ready) => {
        this.traffic3dIconInitScheduled = false;
        if (!ready || !this.map) {
          return;
        }
        if (this.traffic3dIconLayer && this.map.getLayer(this.traffic3dIconLayer.id)) {
          return;
        }
        const atlas = this.buildTrafficAtlas();
        if (!atlas) {
          return;
        }
        this.traffic3dIconLayer = this.createTrafficIconLayer3d(atlas);
        this.map.addLayer(this.traffic3dIconLayer);
        this.reorderPlanLayers();
        if (this.traffic3dIconLayer.setVisible) {
          this.traffic3dIconLayer.setVisible(this.traffic3dVisible);
        }
        if (this.lastTraffic3dEntries.length) {
          this.updateTraffic3dIconLayer(this.lastTraffic3dEntries);
          if (this.traffic3dVisible) {
            this.scheduleMapRepaint();
          }
        }
      });
      return false;
    },

    ensureTraffic2dLayer() {
      if (!this.map) {
        return false;
      }
      if (this.map.getLayer("traffic-points") && this.map.getSource("traffic-points")) {
        return true;
      }
      if (this.traffic2dInitScheduled) {
        return false;
      }
      this.traffic2dInitScheduled = true;
      this.ensureTrafficIcons().then((ready) => {
        this.traffic2dInitScheduled = false;
        if (!ready || !this.map) {
          return;
        }
        if (!this.map.getSource("traffic-points")) {
          this.map.addSource("traffic-points", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: [],
            },
          });
        }
        if (!this.map.getLayer("traffic-risk")) {
          this.map.addLayer({
            id: "traffic-risk",
            type: "circle",
            source: "traffic-points",
            paint: {
              "circle-radius": TRAFFIC_RISK_RADIUS,
              "circle-color": TRAFFIC_RISK_COLOR_EXPR,
              "circle-blur": TRAFFIC_RISK_BLUR,
              "circle-opacity": TRAFFIC_RISK_OPACITY,
            },
          });
        }
        if (!this.map.getLayer("traffic-halo")) {
          this.map.addLayer({
            id: "traffic-halo",
            type: "circle",
            source: "traffic-points",
            paint: {
              "circle-radius": TRAFFIC_2D_HALO_RADIUS,
              "circle-color": TRAFFIC_2D_HALO_COLOR,
              "circle-blur": TRAFFIC_2D_HALO_BLUR,
              "circle-opacity": [
                "case",
                [
                  "all",
                  ["boolean", ["get", "selected"], false],
                  ["<=", ["get", "risk_level"], 0],
                ],
                1,
                0,
              ],
            },
          });
        }
        if (!this.map.getLayer("traffic-halo-core")) {
          this.map.addLayer({
            id: "traffic-halo-core",
            type: "circle",
            source: "traffic-points",
            paint: {
              "circle-radius": TRAFFIC_2D_HALO_RADIUS * 0.7,
              "circle-color": "rgba(0, 0, 0, 0)",
              "circle-stroke-color": TRAFFIC_2D_HALO_RING_COLOR,
              "circle-stroke-width": TRAFFIC_2D_HALO_RING_WIDTH,
              "circle-stroke-opacity": TRAFFIC_2D_HALO_RING_OPACITY,
              "circle-opacity": [
                "case",
                [
                  "all",
                  ["boolean", ["get", "selected"], false],
                  ["<=", ["get", "risk_level"], 0],
                ],
                1,
                0,
              ],
            },
          });
        }
        if (!this.map.getLayer("traffic-points")) {
          this.map.addLayer({
            id: "traffic-points",
            type: "symbol",
            source: "traffic-points",
            layout: {
              "icon-image": ["coalesce", ["get", "icon"], TRAFFIC_FALLBACK_ICON],
              "icon-size": [
                "*",
                TRAFFIC_2D_ICON_SIZE,
                ["coalesce", ["get", "scale"], 1],
              ],
              "icon-rotate": ["get", "heading"],
              "icon-rotation-alignment": "map",
              "icon-allow-overlap": true,
              "icon-ignore-placement": true,
            },
            paint: {
              "icon-opacity": 1,
            },
          });
        }
        this.reorderPlanLayers();
        if (this.lastTraffic3dEntries.length) {
          this.updateTraffic2dLayer(this.lastTraffic3dEntries);
        }
        this.updateTrafficLayerVisibility();
      });
      return false;
    },

    ensureTrafficPredictionLayers() {
      if (!this.map) {
        return;
      }
      if (!this.map.getSource("traffic-predict")) {
        this.map.addSource("traffic-predict", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: [],
          },
        });
      }
      if (!this.map.getLayer("traffic-predict-line")) {
        this.map.addLayer({
          id: "traffic-predict-line",
          type: "line",
          source: "traffic-predict",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": TRAFFIC_PREDICT_COLOR,
            "line-width": TRAFFIC_PREDICT_WIDTH,
            "line-opacity": TRAFFIC_PREDICT_OPACITY,
          },
        });
      }
      const hasPredict3d =
        this.trafficPredictLayer3d &&
        this.map.getLayer &&
        this.map.getLayer(this.trafficPredictLayer3d.id);
      if (!this.trafficPredictLayer3d) {
        this.trafficPredictLayer3d = this.createLineLayer3d(
          "traffic-predict-3d",
          TRAFFIC_PREDICT_COLOR,
          "TRIANGLES",
          null,
          TRAFFIC_PREDICT_WIDTH_3D,
          TRAFFIC_PREDICT_OPACITY,
        );
      }
      if (!hasPredict3d && this.trafficPredictLayer3d) {
        this.map.addLayer(this.trafficPredictLayer3d);
      }
      this.reorderPlanLayers();
    },

    createTrafficLayer3d() {
      const layer = {
        id: "traffic-3d",
        type: "custom",
        renderingMode: "3d",
        _pointCount: 0,
        _visible: false,
        _pointSize: this.computeTrafficPointSize(),
        _color: TRAFFIC_3D_COLOR,
        _hoverColor: TRAFFIC_3D_HOVER_TINT,
        _lastMatrix: null,
        setVisible(nextVisible) {
          this._visible = Boolean(nextVisible);
        },
        getMatrix() {
          return this._lastMatrix;
        },
        updateBuffers(buffers) {
          this._pendingBuffers = buffers;
          if (!this._gl || !this._pointBuffer) {
            return;
          }
          const gl = this._gl;
          const data = new Float32Array(buffers.points || []);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
          this._pointCount = data.length / 7;
          if (Number.isFinite(buffers.pointSize)) {
            this._pointSize = buffers.pointSize;
          }
          if (buffers.color && buffers.color.length === 3) {
            this._color = buffers.color;
          }
          if (buffers.hoverColor && buffers.hoverColor.length === 3) {
            this._hoverColor = buffers.hoverColor;
          }
          this._pendingBuffers = null;
        },
        onAdd(_map, gl) {
          this._gl = gl;
          const vertexSource = `
            attribute vec3 a_pos;
            attribute float a_heading;
            attribute float a_icon;
            attribute float a_hover;
            attribute float a_risk;
            uniform mat4 u_matrix;
            uniform float u_pointSize;
            uniform float u_hoverScale;
            varying float v_heading;
            varying float v_icon;
            varying float v_hover;
            varying float v_risk;
            void main() {
              gl_Position = u_matrix * vec4(a_pos, 1.0);
              v_heading = a_heading;
              v_icon = a_icon;
              v_hover = a_hover;
              v_risk = a_risk;
              gl_PointSize = u_pointSize * (1.0 + a_hover * (u_hoverScale - 1.0));
            }
          `;
          const fragmentSource = `
            precision mediump float;
            uniform vec3 u_color;
            uniform vec3 u_hoverColor;
            varying float v_heading;
            varying float v_icon;
            varying float v_hover;
            varying float v_risk;
            void main() {
              vec2 uv = gl_PointCoord - 0.5;
              float r = length(uv);
              if (r > 0.5) {
                discard;
              }
              float z = sqrt(max(0.0, 0.25 - r * r)) / 0.5;
              vec3 normal = normalize(vec3(uv / 0.5, z));
            float rad = v_heading * 0.017453292519943295;
            float c = cos(rad);
            float s = sin(rad);
            vec3 lightDir = normalize(vec3(-0.35 * c - 0.45 * s, -0.35 * s + 0.45 * c, 0.85));
            float diffuse = clamp(dot(normal, lightDir), 0.0, 1.0);
            float rim = smoothstep(0.35, 0.5, r);
            float variation = fract(v_icon * 0.137) * 0.06;
            vec3 riskColor = u_color;
            if (v_risk > 2.5) {
              riskColor = vec3(1.0, 0.23, 0.19);
            } else if (v_risk > 1.5) {
              riskColor = vec3(0.55, 0.36, 0.96);
            } else if (v_risk > 0.5) {
              riskColor = vec3(1.0, 0.84, 0.04);
            }
            float hoverMix = v_hover * (v_risk > 0.5 ? 0.0 : 0.8);
            vec3 base = mix(riskColor, u_hoverColor, hoverMix) + vec3(variation);
            vec3 color = base * (0.55 + 0.45 * diffuse) + rim * 0.15;
            gl_FragColor = vec4(color, 1.0);
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
          this._aHeading = gl.getAttribLocation(program, "a_heading");
          this._aIcon = gl.getAttribLocation(program, "a_icon");
          this._aHover = gl.getAttribLocation(program, "a_hover");
          this._aRisk = gl.getAttribLocation(program, "a_risk");
          this._uMatrix = gl.getUniformLocation(program, "u_matrix");
          this._uPointSize = gl.getUniformLocation(program, "u_pointSize");
          this._uHoverScale = gl.getUniformLocation(program, "u_hoverScale");
          this._uColor = gl.getUniformLocation(program, "u_color");
          this._uHoverColor = gl.getUniformLocation(program, "u_hoverColor");

          this._pointBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([]), gl.STATIC_DRAW);
          this._pointCount = 0;

          if (this._pendingBuffers) {
            this.updateBuffers(this._pendingBuffers);
          }
        },
        render(gl, matrix) {
          this._lastMatrix = matrix;
          if (!this._program || !this._visible || !this._pointCount) {
            return;
          }
          gl.useProgram(this._program);
          gl.uniformMatrix4fv(this._uMatrix, false, matrix);
          gl.uniform1f(this._uPointSize, this._pointSize);
          gl.uniform1f(this._uHoverScale, TRAFFIC_3D_HOVER_SCALE);
          gl.uniform3fv(this._uColor, this._color);
          gl.uniform3fv(this._uHoverColor, this._hoverColor);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.enableVertexAttribArray(this._aPos);
          gl.enableVertexAttribArray(this._aHeading);
          gl.enableVertexAttribArray(this._aIcon);
          gl.enableVertexAttribArray(this._aHover);
          gl.enableVertexAttribArray(this._aRisk);
          const stride = 7 * 4;
          gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, stride, 0);
          gl.vertexAttribPointer(this._aHeading, 1, gl.FLOAT, false, stride, 3 * 4);
          gl.vertexAttribPointer(this._aIcon, 1, gl.FLOAT, false, stride, 4 * 4);
          gl.vertexAttribPointer(this._aHover, 1, gl.FLOAT, false, stride, 5 * 4);
          gl.vertexAttribPointer(this._aRisk, 1, gl.FLOAT, false, stride, 6 * 4);
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          gl.drawArrays(gl.POINTS, 0, this._pointCount);
        },
      };
      return layer;
    },

    createTrafficIconLayer3d(atlas) {
      const layer = {
        id: "traffic-3d-icon",
        type: "custom",
        renderingMode: "3d",
        _pointCount: 0,
        _visible: false,
        _pointSize: this.computeTrafficIconPointSize(),
        _atlas: atlas,
        _lastMatrix: null,
        setVisible(nextVisible) {
          this._visible = Boolean(nextVisible);
        },
        getMatrix() {
          return this._lastMatrix;
        },
        updateBuffers(buffers) {
          this._pendingBuffers = buffers;
          if (!this._gl || !this._pointBuffer) {
            return;
          }
          const gl = this._gl;
          const data = new Float32Array(buffers.points || []);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
          this._pointCount = data.length / 5;
          if (Number.isFinite(buffers.pointSize)) {
            this._pointSize = buffers.pointSize;
          }
          this._pendingBuffers = null;
        },
        onAdd(_map, gl) {
          this._gl = gl;
          const vertexSource = `
            attribute vec3 a_pos;
            attribute float a_heading;
            attribute float a_icon;
            uniform mat4 u_matrix;
            uniform float u_pointSize;
            varying float v_heading;
            varying float v_icon;
            void main() {
              gl_Position = u_matrix * vec4(a_pos, 1.0);
              v_heading = a_heading;
              v_icon = a_icon;
              gl_PointSize = u_pointSize;
            }
          `;
          const fragmentSource = `
            precision mediump float;
            uniform sampler2D u_texture;
            uniform vec2 u_atlasSize;
            uniform vec2 u_cellSize;
            uniform float u_alpha;
            varying float v_heading;
            varying float v_icon;
            void main() {
              vec2 uv = gl_PointCoord - 0.5;
              float rad = v_heading * 0.017453292519943295;
              float c = cos(rad);
              float s = sin(rad);
              vec2 rotated = vec2(uv.x * c - uv.y * s, uv.x * s + uv.y * c) + 0.5;
              if (rotated.x < 0.0 || rotated.x > 1.0 || rotated.y < 0.0 || rotated.y > 1.0) {
                discard;
              }
              float iconIndex = floor(v_icon + 0.5);
              vec2 cellOrigin = vec2(iconIndex * u_cellSize.x, 0.0);
              vec2 texCoord = (cellOrigin + rotated * u_cellSize) / u_atlasSize;
              vec4 tex = texture2D(u_texture, texCoord);
              if (tex.a < 0.05) {
                discard;
              }
              gl_FragColor = vec4(tex.rgb, tex.a * u_alpha);
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
          this._aHeading = gl.getAttribLocation(program, "a_heading");
          this._aIcon = gl.getAttribLocation(program, "a_icon");
          this._uMatrix = gl.getUniformLocation(program, "u_matrix");
          this._uPointSize = gl.getUniformLocation(program, "u_pointSize");
          this._uTexture = gl.getUniformLocation(program, "u_texture");
          this._uAtlasSize = gl.getUniformLocation(program, "u_atlasSize");
          this._uCellSize = gl.getUniformLocation(program, "u_cellSize");
          this._uAlpha = gl.getUniformLocation(program, "u_alpha");

          this._pointBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([]), gl.STATIC_DRAW);
          this._pointCount = 0;

          const atlasCanvas = this._atlas && this._atlas.canvas;
          if (atlasCanvas) {
            this._atlasSizeValue = [atlasCanvas.width, atlasCanvas.height];
            this._cellSizeValue = [
              Number(this._atlas.cellWidth) || atlasCanvas.width,
              Number(this._atlas.cellHeight) || atlasCanvas.height,
            ];
            this._texture = gl.createTexture();
            gl.bindTexture(gl.TEXTURE_2D, this._texture);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
            gl.texImage2D(
              gl.TEXTURE_2D,
              0,
              gl.RGBA,
              gl.RGBA,
              gl.UNSIGNED_BYTE,
              atlasCanvas,
            );
          }

          if (this._pendingBuffers) {
            this.updateBuffers(this._pendingBuffers);
          }
        },
        render(gl, matrix) {
          this._lastMatrix = matrix;
          if (!this._program || !this._visible || !this._pointCount) {
            return;
          }
          if (!this._texture || !this._atlasSizeValue || !this._cellSizeValue) {
            return;
          }
          gl.useProgram(this._program);
          gl.uniformMatrix4fv(this._uMatrix, false, matrix);
          gl.uniform1f(this._uPointSize, this._pointSize);
          gl.uniform1f(this._uAlpha, TRAFFIC_3D_ICON_ALPHA);
          gl.uniform2f(this._uAtlasSize, this._atlasSizeValue[0], this._atlasSizeValue[1]);
          gl.uniform2f(this._uCellSize, this._cellSizeValue[0], this._cellSizeValue[1]);
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, this._texture);
          gl.uniform1i(this._uTexture, 0);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.enableVertexAttribArray(this._aPos);
          gl.enableVertexAttribArray(this._aHeading);
          gl.enableVertexAttribArray(this._aIcon);
          const stride = 5 * 4;
          gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, stride, 0);
          gl.vertexAttribPointer(this._aHeading, 1, gl.FLOAT, false, stride, 3 * 4);
          gl.vertexAttribPointer(this._aIcon, 1, gl.FLOAT, false, stride, 4 * 4);
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          gl.drawArrays(gl.POINTS, 0, this._pointCount);
        },
      };
      return layer;
    },

    updateTraffic3dLayer(entries) {
      if (!this.map) {
        return;
      }
      if (!entries || !entries.length) {
        if (this.traffic3dLayer && this.traffic3dLayer.updateBuffers) {
          this.traffic3dLayer.updateBuffers({ points: [] });
        }
        return;
      }
      if (!this.ensureTraffic3dLayer()) {
        return;
      }
      if (!this.traffic3dLayer || !this.traffic3dLayer.updateBuffers) {
        return;
      }
      const points = [];
      entries.forEach((entry) => {
        const lon = Number(entry.lon);
        const lat = Number(entry.lat);
        const altitude = Number(entry.altitude_m);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          return;
        }
        const alt_m = Number.isFinite(altitude) ? altitude : 0;
        const merc =
          entry.mercator ||
          maplibregl.MercatorCoordinate.fromLngLat([lon, lat], toTrafficAltitude(alt_m));
        const hover = this.isTrafficHighlighted(entry.id) ? 1 : 0;
        const iconIndex = Math.max(0, TRAFFIC_ICON_IDS.indexOf(entry.icon || ""));
        const riskLevel = this.coerceRiskLevel(entry.risk_level ?? entry.risk);
        points.push(merc.x, merc.y, merc.z, entry.heading, iconIndex, hover, riskLevel);
      });
      this.traffic3dLayer.updateBuffers({
        points,
        pointSize: this.computeTrafficPointSize(),
        color: TRAFFIC_3D_COLOR,
        hoverColor: TRAFFIC_3D_HOVER_TINT,
      });
    },

    updateTraffic3dIconLayer(entries) {
      if (!TRAFFIC_USE_3D_ICON_LAYER) {
        return;
      }
      if (!this.map) {
        return;
      }
      if (!entries || !entries.length) {
        if (this.traffic3dIconLayer && this.traffic3dIconLayer.updateBuffers) {
          this.traffic3dIconLayer.updateBuffers({ points: [] });
        }
        return;
      }
      if (!this.ensureTraffic3dIconLayer()) {
        return;
      }
      if (!this.traffic3dIconLayer || !this.traffic3dIconLayer.updateBuffers) {
        return;
      }
      const points = [];
      entries.forEach((entry) => {
        const lon = Number(entry.lon);
        const lat = Number(entry.lat);
        const altitude = Number(entry.altitude_m);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          return;
        }
        const alt_m = Number.isFinite(altitude) ? altitude : 0;
        const iconAltitude = toTrafficAltitude(alt_m + TRAFFIC_ICON_ALTITUDE_OFFSET_M);
        const merc = maplibregl.MercatorCoordinate.fromLngLat([lon, lat], iconAltitude);
        const iconIndex = Math.max(0, TRAFFIC_ICON_IDS.indexOf(entry.icon || ""));
        points.push(merc.x, merc.y, merc.z, entry.heading, iconIndex);
      });
      this.traffic3dIconLayer.updateBuffers({
        points,
        pointSize: this.computeTrafficIconPointSize(),
      });
    },

    updateTraffic2dLayer(entries) {
      if (!this.map) {
        return;
      }
      if (!entries || !entries.length) {
        const source = this.map.getSource("traffic-points");
        if (source && source.setData) {
          source.setData({ type: "FeatureCollection", features: [] });
        }
        return;
      }
      const layerExists = this.map.getLayer && this.map.getLayer("traffic-points");
      if (!layerExists && !this.traffic2dVisible) {
        return;
      }
      if (!layerExists && !this.ensureTraffic2dLayer()) {
        return;
      }
      const source = this.map.getSource("traffic-points");
      if (!source || !source.setData) {
        return;
      }
      const features = [];
      entries.forEach((entry) => {
        const lon = Number(entry.lon);
        const lat = Number(entry.lat);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          return;
        }
        const icon = entry.icon && TRAFFIC_ICON_IDS.includes(entry.icon)
          ? entry.icon
          : TRAFFIC_FALLBACK_ICON;
        const scale = this.trafficIconScales.get(icon) || 1;
        const riskLevel = this.coerceRiskLevel(entry.risk_level ?? entry.risk);
        features.push({
          type: "Feature",
          id: entry.id,
          geometry: {
            type: "Point",
            coordinates: [lon, lat],
          },
          properties: {
            icon,
            heading: entry.heading || 0,
            scale,
            risk_level: riskLevel,
            selected: this.isTrafficHighlighted(entry.id),
          },
        });
      });
      source.setData({
        type: "FeatureCollection",
        features,
      });
    },

    clearTrafficPrediction() {
      if (!this.map) {
        return;
      }
      this.trafficPredictVisible = false;
      this.stopPredictionFade();
      this.setPredictionOpacity(0);
      const source = this.map.getSource("traffic-predict");
      if (source && source.setData) {
        source.setData({ type: "FeatureCollection", features: [] });
      }
      if (this.trafficPredictLayer3d && this.trafficPredictLayer3d.updatePositions) {
        this.trafficPredictLayer3d.updatePositions([]);
      }
      this.scheduleMapRepaint();
    },

    setPredictionOpacity(value) {
      const opacity = Math.max(0, Math.min(1, Number(value)));
      if (!Number.isFinite(opacity)) {
        return;
      }
      this.trafficPredictOpacity = opacity;
      if (this.map && this.map.getLayer && this.map.getLayer("traffic-predict-line")) {
        this.map.setPaintProperty("traffic-predict-line", "line-opacity", opacity);
      }
      if (this.trafficPredictLayer3d && this.trafficPredictLayer3d.setAlpha) {
        this.trafficPredictLayer3d.setAlpha(opacity);
      }
      this.scheduleMapRepaint();
    },

    setHistoryOpacity(value) {
      const opacity = Math.max(0, Math.min(1, Number(value)));
      if (!Number.isFinite(opacity)) {
        return;
      }
      this.trafficHistoryOpacity = opacity;
      if (this.map && this.map.getLayer && this.map.getLayer("traffic-history-line")) {
        this.map.setPaintProperty("traffic-history-line", "line-opacity", opacity);
      }
      if (this.map && this.map.getLayer && this.map.getLayer("traffic-history-dots")) {
        this.map.setPaintProperty("traffic-history-dots", "circle-opacity", opacity * 0.8);
      }
      if (this.trafficHistoryLayer3d && this.trafficHistoryLayer3d.setAlpha) {
        this.trafficHistoryLayer3d.setAlpha(opacity);
      }
      this.scheduleMapRepaint();
    },

    stopPredictionFade() {
      if (this.trafficPredictFadeTimer) {
        cancelAnimationFrame(this.trafficPredictFadeTimer);
        this.trafficPredictFadeTimer = null;
      }
    },

    startPredictionFade(targetOpacity = TRAFFIC_PREDICT_OPACITY) {
      const goal = Math.max(0, Math.min(1, Number(targetOpacity)));
      if (!Number.isFinite(goal)) {
        return;
      }
      this.stopPredictionFade();
      const startOpacity = Number(this.trafficPredictOpacity) || 0;
      const startTime = performance.now();
      const duration = TRAFFIC_PREDICT_FADE_MS;
      const animate = (now) => {
        const elapsed = now - startTime;
        const t = Math.min(1, elapsed / duration);
        const nextOpacity = startOpacity + (goal - startOpacity) * t;
        this.setPredictionOpacity(nextOpacity);
        if (t < 1) {
          this.trafficPredictFadeTimer = requestAnimationFrame(animate);
        } else {
          this.trafficPredictFadeTimer = null;
        }
      };
      this.trafficPredictFadeTimer = requestAnimationFrame(animate);
    },

    stopHistoryFade() {
      if (this.trafficHistoryFadeTimer) {
        cancelAnimationFrame(this.trafficHistoryFadeTimer);
        this.trafficHistoryFadeTimer = null;
      }
    },

    startHistoryFade(targetOpacity = TRAFFIC_HISTORY_OPACITY) {
      const goal = Math.max(0, Math.min(1, Number(targetOpacity)));
      if (!Number.isFinite(goal)) {
        return;
      }
      this.stopHistoryFade();
      const startOpacity = Number(this.trafficHistoryOpacity) || 0;
      const startTime = performance.now();
      const duration = TRAFFIC_HISTORY_FADE_MS;
      const animate = (now) => {
        const elapsed = now - startTime;
        const t = Math.min(1, elapsed / duration);
        const nextOpacity = startOpacity + (goal - startOpacity) * t;
        this.setHistoryOpacity(nextOpacity);
        if (t < 1) {
          this.trafficHistoryFadeTimer = requestAnimationFrame(animate);
        } else {
          this.trafficHistoryFadeTimer = null;
        }
      };
      this.trafficHistoryFadeTimer = requestAnimationFrame(animate);
    },

    ensureTrafficHistoryLayers() {
      if (!this.map) {
        return;
      }
      if (!this.map.getSource("traffic-history")) {
        this.map.addSource("traffic-history", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: [],
          },
        });
      }
      if (!this.map.getSource("traffic-history-dots")) {
        this.map.addSource("traffic-history-dots", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: [],
          },
        });
      }
      if (!this.map.getLayer("traffic-history-line")) {
        this.map.addLayer({
          id: "traffic-history-line",
          type: "line",
          source: "traffic-history",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": TRAFFIC_HISTORY_COLOR,
            "line-width": TRAFFIC_HISTORY_WIDTH,
            "line-opacity": TRAFFIC_HISTORY_OPACITY,
          },
        });
      }
      if (!this.map.getLayer("traffic-history-dots")) {
        this.map.addLayer({
          id: "traffic-history-dots",
          type: "circle",
          source: "traffic-history-dots",
          paint: {
            "circle-radius": TRAFFIC_HISTORY_DOT_RADIUS,
            "circle-color": TRAFFIC_HISTORY_DOT_COLOR,
            "circle-opacity": TRAFFIC_HISTORY_DOT_OPACITY,
          },
        });
      }
      const hasHistory3d =
        this.trafficHistoryLayer3d &&
        this.map.getLayer &&
        this.map.getLayer(this.trafficHistoryLayer3d.id);
      if (!this.trafficHistoryLayer3d) {
        this.trafficHistoryLayer3d = this.createLineLayer3d(
          "traffic-history-3d",
          TRAFFIC_HISTORY_COLOR_3D,
          "TRIANGLES",
          null,
          TRAFFIC_HISTORY_WIDTH_3D,
          TRAFFIC_HISTORY_OPACITY,
        );
      }
      if (!hasHistory3d && this.trafficHistoryLayer3d) {
        this.map.addLayer(this.trafficHistoryLayer3d);
      }
      this.setHistoryOpacity(this.trafficHistoryOpacity);
      this.reorderPlanLayers();
    },

    updateTrafficHistoryLine() {
      if (!this.map || !this.map.isStyleLoaded()) {
        return;
      }
      this.ensureTrafficHistoryLayers();
      const restartFade = Boolean(this.trafficHistoryRestartFade);
      this.trafficHistoryRestartFade = false;
      const source = this.map.getSource("traffic-history");
      const dotSource = this.map.getSource("traffic-history-dots");
      if (!source || !source.setData) {
        return;
      }
      const points = Array.isArray(this.trafficHistoryPoints)
        ? this.trafficHistoryPoints
        : [];
      if (!points.length || points.length < 2) {
        source.setData({ type: "FeatureCollection", features: [] });
        if (dotSource && dotSource.setData) {
          dotSource.setData({ type: "FeatureCollection", features: [] });
        }
        if (this.trafficHistoryLayer3d && this.trafficHistoryLayer3d.updatePositions) {
          this.trafficHistoryLayer3d.updatePositions([]);
        }
        if (this.trafficHistoryVisible) {
          this.trafficHistoryVisible = false;
          this.stopHistoryFade();
          this.setHistoryOpacity(0);
        }
        return;
      }
      const rawCoords = [];
      const update3d = Boolean(
        this.trafficHistoryLayer3d && this.trafficHistoryLayer3d.updatePositions,
      );
      const altitudes = update3d ? [] : null;
      const dotIndices = [];
      const offsetMeters = this.getTrafficLaneOffsetMeters();
      let lastDotTime = null;
      let fallbackCount = 0;
      points.forEach((point) => {
        if (!Array.isArray(point) || point.length < 2) {
          return;
        }
        const lon = Number(point[0]);
        const lat = Number(point[1]);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          return;
        }
        rawCoords.push([lon, lat]);
        if (update3d) {
          const altValue = point.length > 2 ? Number(point[2]) : NaN;
          const alt_m = Number.isFinite(altValue) ? altValue : FLIGHT_ALT_M;
          if (altitudes) {
            altitudes.push(alt_m);
          }
        }
        const timeValue = point.length > 3 ? Number(point[3]) : NaN;
        if (Number.isFinite(timeValue)) {
          if (lastDotTime == null || timeValue - lastDotTime >= TRAFFIC_HISTORY_DOT_INTERVAL_S) {
            dotIndices.push(rawCoords.length - 1);
            lastDotTime = timeValue;
          }
        } else {
          fallbackCount += 1;
          if (fallbackCount % TRAFFIC_HISTORY_DOT_FALLBACK_STEP === 0) {
            dotIndices.push(rawCoords.length - 1);
          }
        }
      });
      if (rawCoords.length < 2) {
        source.setData({ type: "FeatureCollection", features: [] });
        if (dotSource && dotSource.setData) {
          dotSource.setData({ type: "FeatureCollection", features: [] });
        }
        if (update3d) {
          this.trafficHistoryLayer3d.updatePositions([]);
        }
        if (this.trafficHistoryVisible) {
          this.trafficHistoryVisible = false;
          this.stopHistoryFade();
          this.setHistoryOpacity(0);
        }
        return;
      }
      const coords =
        offsetMeters > 0 ? this.offsetCoordsByPath(rawCoords, offsetMeters) : rawCoords;
      const dotFeatures = dotIndices
        .map((index) => coords[index])
        .filter(Boolean)
        .map((coord) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: coord },
          properties: {},
        }));
      source.setData({
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            geometry: {
              type: "LineString",
              coordinates: coords,
            },
            properties: {},
          },
        ],
      });
      if (dotSource && dotSource.setData) {
        dotSource.setData({
          type: "FeatureCollection",
          features: dotFeatures,
        });
      }
      if (update3d) {
        const positions = this.buildThickLinePositions(
          coords,
          altitudes || [],
          TRAFFIC_HISTORY_WIDTH_3D,
        );
        this.trafficHistoryLayer3d.updatePositions(positions);
      }
      if (!this.trafficHistoryVisible || restartFade) {
        this.trafficHistoryVisible = true;
        this.setHistoryOpacity(0);
        this.startHistoryFade(TRAFFIC_HISTORY_OPACITY);
      } else if (this.trafficHistoryOpacity !== TRAFFIC_HISTORY_OPACITY) {
        this.setHistoryOpacity(TRAFFIC_HISTORY_OPACITY);
      }
      this.map.triggerRepaint();
    },

    clearTrafficHistory() {
      this.trafficHistoryName = "";
      this.trafficHistoryPoints = [];
      this.trafficHistoryLoading = false;
      this.trafficHistoryLoadingName = "";
      this.trafficHistoryWaitStart = null;
      this.trafficHistoryVisible = false;
      this.stopHistoryFade();
      this.setHistoryOpacity(0);
      this.stopHistoryRefresh();
      this.updateTrafficHistoryLine();
    },

    resetTrafficHistoryByName(name) {
      const target = String(name || "").trim();
      if (!target) {
        this.clearTrafficHistory();
        return;
      }
      if (target === this.trafficHistoryName && this.trafficHistoryPoints.length) {
        return;
      }
      this.trafficHistoryName = target;
      this.trafficHistoryPoints = [];
      this.trafficHistoryLoading = true;
      this.trafficHistoryLoadingName = target;
      this.trafficHistoryWaitStart = performance.now();
      this.updateTrafficHistoryLine();
      this.clearTrafficPrediction();
      this.startHistoryRefresh();
    },

    async fetchTrafficHistory(name) {
      if (!this.webApiEnabled) {
        return;
      }
      const target = String(name || "").trim();
      if (!target) {
        return;
      }
      const requestId = (this.trafficHistoryRequestId += 1);
      const url = this.resolveApiUrl(
        `api/history?name=${encodeURIComponent(target)}`,
      );
      const finalize = (forceUpdate = false) => {
        if (requestId !== this.trafficHistoryRequestId) {
          return;
        }
        if (target !== this.trafficHistoryName) {
          return;
        }
        if (this.trafficHistoryLoading && this.trafficHistoryLoadingName === target) {
          this.trafficHistoryLoading = false;
          this.trafficHistoryLoadingName = "";
        }
        if (forceUpdate) {
          this.updateTrafficPrediction();
        }
      };
      try {
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) {
          finalize(true);
          return;
        }
        const payload = await response.json();
        if (requestId !== this.trafficHistoryRequestId) {
          return;
        }
        if (!payload || !Array.isArray(payload.points)) {
          finalize(true);
          return;
        }
        const points = payload.points
          .map((point) => {
            if (!Array.isArray(point) || point.length < 2) {
              return null;
            }
            const lon = Number(point[0]);
            const lat = Number(point[1]);
            if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
              return null;
            }
            const altValue = point.length > 2 ? Number(point[2]) : NaN;
            const alt_m = Number.isFinite(altValue) ? altValue : FLIGHT_ALT_M;
            const timeValue = point.length > 3 ? Number(point[3]) : NaN;
            const time_s = Number.isFinite(timeValue) ? timeValue : NaN;
            return [lon, lat, alt_m, time_s];
          })
          .filter(Boolean);
        if (target !== this.trafficHistoryName) {
          return;
        }
        const current = this.trafficHistoryPoints;
        const wasEmpty = !current || current.length < 2;
        const next = points;
        let shouldUpdate = next.length >= current.length;
        if (!shouldUpdate && next.length && current.length) {
          const lastNext = next[next.length - 1];
          const lastCurrent = current[current.length - 1];
          shouldUpdate = Boolean(
            lastNext &&
              lastCurrent &&
              (lastNext[0] !== lastCurrent[0] ||
                lastNext[1] !== lastCurrent[1] ||
                lastNext[2] !== lastCurrent[2]),
          );
        }
        if (shouldUpdate) {
          this.trafficHistoryPoints = next;
          if (wasEmpty && next.length >= 2) {
            this.trafficHistoryRestartFade = true;
          }
          this.updateTrafficHistoryLine();
        }
        finalize(true);
      } catch (error) {
        finalize(true);
        return;
      }
    },

    startHistoryRefresh() {
      this.stopHistoryRefresh();
      const target = this.trafficHistoryName;
      if (!target) {
        return;
      }
      this.fetchTrafficHistory(target);
      this.trafficHistoryRefreshTimer = window.setInterval(() => {
        if (!this.trafficHistoryName) {
          return;
        }
        this.fetchTrafficHistory(this.trafficHistoryName);
      }, this.trafficHistoryRefreshIntervalMs);
    },

    stopHistoryRefresh() {
      if (this.trafficHistoryRefreshTimer) {
        window.clearInterval(this.trafficHistoryRefreshTimer);
        this.trafficHistoryRefreshTimer = null;
      }
    },

    appendTrafficHistory() {
      if (this.trafficSelectedId == null || !this.trafficHistoryName) {
        return;
      }
      if (
        this.trafficHistoryLoading &&
        this.trafficHistoryLoadingName === this.trafficHistoryName
      ) {
        return;
      }
      const entry = this.trafficById.get(this.trafficSelectedId);
      if (!entry || !entry.coords || !entry.props) {
        return;
      }
      const name = String(entry.props.name || "").trim();
      if (!name || name !== this.trafficHistoryName) {
        return;
      }
      const baseCoords =
        entry.rawCoords && entry.rawCoords.length >= 2 ? entry.rawCoords : entry.coords;
      const lon = Number(baseCoords[0]);
      const lat = Number(baseCoords[1]);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return;
      }
      const altValue = Number(entry.props.altitude_m);
      const alt_m = Number.isFinite(altValue) ? altValue : FLIGHT_ALT_M;
      const time_s = Number.isFinite(this.lastSimTime_s) ? this.lastSimTime_s : NaN;
      const last = this.trafficHistoryPoints[this.trafficHistoryPoints.length - 1];
      if (
        last &&
        last[0] === lon &&
        last[1] === lat &&
        last[2] === alt_m &&
        last[3] === time_s
      ) {
        return;
      }
      this.trafficHistoryPoints.push([lon, lat, alt_m, time_s]);
      this.updateTrafficHistoryLine();
    },

    updateTrafficPrediction() {
      if (!this.map) {
        return;
      }
      if (this.trafficSelectedId == null) {
        this.clearTrafficPrediction();
        return;
      }
      if (this.trafficPredictEnableAt) {
        const now = performance.now();
        if (now < this.trafficPredictEnableAt) {
          this.clearTrafficPrediction();
          return;
        }
      }
      if (this.trafficHistoryName) {
        const points = Array.isArray(this.trafficHistoryPoints)
          ? this.trafficHistoryPoints
          : [];
        const historyLoading =
          this.trafficHistoryLoading && this.trafficHistoryLoadingName === this.trafficHistoryName;
        const historyShort = points.length < 2;
        if (historyLoading || historyShort) {
          const waitStart = Number(this.trafficHistoryWaitStart);
          const waitElapsed = Number.isFinite(waitStart) ? performance.now() - waitStart : 0;
          if (!Number.isFinite(waitStart) || waitElapsed < TRAFFIC_PREDICT_HISTORY_GRACE_MS) {
            this.clearTrafficPrediction();
            return;
          }
        }
      }
      const entry = this.trafficById.get(this.trafficSelectedId);
      if (!entry || !entry.coords || entry.coords.length < 2 || !entry.props) {
        this.clearTrafficPrediction();
        return;
      }
      let rawPath = Array.isArray(entry.props.predict_path)
        ? entry.props.predict_path
        : null;
      let rawKind = rawPath ? "predict" : "";
      if (!rawPath) {
        const holdPath = Array.isArray(entry.props.hold_path) ? entry.props.hold_path : null;
        if (holdPath) {
          rawPath = holdPath;
          rawKind = "hold";
        }
      }
      if (!rawPath || rawPath.length < 2) {
        this.clearTrafficPrediction();
        return;
      }
      const coords = rawPath
        .map((item) => {
          if (!Array.isArray(item) || item.length < 2) {
            return null;
          }
          const lon = Number(item[0]);
          const lat = Number(item[1]);
          if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
            return null;
          }
          return [lon, lat];
        })
        .filter(Boolean);
      if (!coords || coords.length < 2) {
        this.clearTrafficPrediction();
        return;
      }
      const offsetMeters = this.getTrafficLaneOffsetMeters();
      let displayCoords = coords;
      if (offsetMeters > 0) {
        if (rawKind === "hold") {
          const routeFrom = entry.props.route_from ? String(entry.props.route_from) : "";
          const routeTo = entry.props.route_to ? String(entry.props.route_to) : "";
          const offsetVec = this.getRouteOffsetVector(routeFrom, routeTo, offsetMeters);
          displayCoords = this.offsetCoordsByVector(coords, offsetVec);
        } else {
          displayCoords = this.offsetCoordsByPath(coords, offsetMeters);
        }
      }
      const wasVisible = this.trafficPredictVisible;
      this.ensureTrafficPredictionLayers();
      const source = this.map.getSource("traffic-predict");
      if (source && source.setData) {
        source.setData({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: {
                type: "LineString",
                coordinates: displayCoords,
              },
              properties: {},
            },
          ],
        });
      }
      if (this.trafficPredictLayer3d && this.trafficPredictLayer3d.updatePositions) {
        const altitude = Number(entry.props.altitude_m);
        const alt_m = Number.isFinite(altitude) ? altitude : FLIGHT_ALT_M;
        const positions = this.buildThickLinePositions(
          displayCoords,
          alt_m,
          TRAFFIC_PREDICT_WIDTH_3D,
        );
        this.trafficPredictLayer3d.updatePositions(positions);
      }
      this.trafficPredictVisible = true;
      if (!wasVisible) {
        this.setPredictionOpacity(0);
        this.startPredictionFade(TRAFFIC_PREDICT_OPACITY);
      } else if (this.trafficPredictOpacity !== TRAFFIC_PREDICT_OPACITY) {
        this.setPredictionOpacity(TRAFFIC_PREDICT_OPACITY);
      }
      this.map.triggerRepaint();
    },

    scheduleTraffic3dInit() {
      if (this.traffic3dInitScheduled) {
        return;
      }
      this.traffic3dInitScheduled = true;
      requestAnimationFrame(() => {
        this.traffic3dInitScheduled = false;
        if (!this.map) {
          return;
        }
        if (!this.ensureTraffic3dLayer()) {
          return;
        }
        this.ensureTraffic3dIconLayer();
        if (this.lastTraffic3dEntries.length) {
          this.updateTraffic3dLayer(this.lastTraffic3dEntries);
          this.updateTraffic3dIconLayer(this.lastTraffic3dEntries);
        }
        this.updateTrafficLayerVisibility();
      });
    },

    scheduleMapRepaint() {
      if (this.mapRepaintScheduled || !this.map) {
        return;
      }
      this.mapRepaintScheduled = true;
      requestAnimationFrame(() => {
        this.mapRepaintScheduled = false;
        if (!this.map) {
          return;
        }
        try {
          this.map.triggerRepaint();
        } catch (error) {
          console.warn("Map repaint skipped.", error);
        }
      });
    },

    setLayerVisibility(layerId, visible) {
      if (!this.map || !this.map.getLayer || !this.map.getLayer(layerId)) {
        return;
      }
      const next = visible ? "visible" : "none";
      this.map.setLayoutProperty(layerId, "visibility", next);
    },

    setupTrafficVisibility() {
      if (!this.map) {
        return;
      }
      const update = () => this.updateTrafficLayerVisibility();
      this.map.on("pitch", update);
      this.map.on("load", update);
    },

    removeTraffic2dLayers() {
      if (!this.map) {
        return;
      }
      [
        "traffic-hit",
        "traffic-points",
        "traffic-glow",
        "traffic-risk",
        "traffic-halo",
        "traffic-halo-core",
        "traffic-history-line",
        "traffic-history-dots",
        "traffic-predict-line",
      ].forEach((layerId) => {
        if (this.map.getLayer(layerId)) {
          this.map.removeLayer(layerId);
        }
      });
      if (this.map.getSource("traffic-points")) {
        this.map.removeSource("traffic-points");
      }
      if (this.map.getSource("traffic-predict")) {
        this.map.removeSource("traffic-predict");
      }
      if (this.map.getSource("traffic-history")) {
        this.map.removeSource("traffic-history");
      }
      if (this.map.getSource("traffic-history-dots")) {
        this.map.removeSource("traffic-history-dots");
      }
    },

    updateTrafficLayerVisibility() {
      if (!this.map) {
        return;
      }
      const pitch = this.map.getPitch ? this.map.getPitch() : 0;
      const show2d = pitch <= TRAFFIC_2D_MAX_PITCH;
      const show3d = !show2d;

      if (show2d) {
        this.ensureTraffic2dLayer();
      }

      const layerExists =
        this.map.getLayer && this.map.getLayer("traffic-3d") ? true : false;
      if (show3d && !layerExists) {
        this.ensureTraffic3dLayer();
      }
      if (show3d && TRAFFIC_USE_3D_ICON_LAYER) {
        const iconLayerExists =
          this.map.getLayer && this.map.getLayer("traffic-3d-icon") ? true : false;
        if (!iconLayerExists) {
          this.ensureTraffic3dIconLayer();
        }
      }

      this.traffic3dVisible = show3d;
      this.traffic2dVisible = show2d;
      if (this.traffic3dLayer && this.traffic3dLayer.setVisible) {
        this.traffic3dLayer.setVisible(show3d);
      }
      if (this.traffic3dIconLayer && this.traffic3dIconLayer.setVisible) {
        this.traffic3dIconLayer.setVisible(show3d && TRAFFIC_USE_3D_ICON_LAYER);
      }

      this.setLayerVisibility("traffic-points", show2d);
      this.setLayerVisibility("traffic-risk", show2d);
      this.setLayerVisibility("traffic-halo", show2d);
      this.setLayerVisibility("traffic-halo-core", show2d);
      this.setLayerVisibility("traffic-hit", show2d);
      this.setLayerVisibility("traffic-glow", false);
      const showHistory2d = show2d;
      this.setLayerVisibility("traffic-history-line", showHistory2d);
      this.setLayerVisibility("traffic-history-dots", showHistory2d);
      const showPredict2d = show2d;
      this.setLayerVisibility("traffic-predict-line", showPredict2d);
      if (this.trafficHistoryLayer3d && this.trafficHistoryLayer3d.setVisible) {
        this.trafficHistoryLayer3d.setVisible(show3d);
      }
      if (this.trafficPredictLayer3d && this.trafficPredictLayer3d.setVisible) {
        this.trafficPredictLayer3d.setVisible(show3d);
      }
      if (this.trafficPopup && this.trafficPopup.setOffset) {
        const anchor = this.trafficPopupAnchor || "right";
        this.trafficPopup.setOffset(this.getTrafficPopupOffset(anchor));
      }
    },

    setupTrafficInteractions() {
      if (!this.map || this.trafficInteractionsBound) {
        return;
      }
      this.trafficInteractionsBound = true;
      this.map.on("click", (event) => {
        this.handleTrafficNameClick(event);
      });
      this.map.on("contextmenu", (event) => {
        if (this.scaleCopyActive) {
          return;
        }
        if (event && typeof event.preventDefault === "function") {
          event.preventDefault();
        }
        if (
          event &&
          event.originalEvent &&
          typeof event.originalEvent.preventDefault === "function"
        ) {
          event.originalEvent.preventDefault();
        }
        this.handleTraffic3dClick(event);
      });
    },

    setupTrafficHover() {
      if (!this.map) {
        return;
      }
      this.map.on("mousemove", (event) => this.handleTrafficHover(event));
      this.map.on("mouseleave", () => this.clearTrafficHover());
      this.map.on("movestart", () => this.clearTrafficHover());
      this.map.on("dragstart", () => this.clearTrafficHover());
      this.map.on("zoomstart", () => this.clearTrafficHover());
      this.map.on("pitchstart", () => this.clearTrafficHover());
      this.map.on("rotatestart", () => this.clearTrafficHover());
    },

    handleTrafficHover(event) {
      if (!this.map) {
        return;
      }
      if (this.isEmergencyLandingMode && this.isEmergencyLandingMode()) {
        this.clearTrafficHover();
        return;
      }
      if (this.isForceMoveMode && this.isForceMoveMode()) {
        this.clearTrafficHover();
        return;
      }
      if (this.trafficPopupFlightId != null || this.trafficNamePopupId != null) {
        this.clearTrafficHover();
        return;
      }
      if (this.corridorHover || this.vertiportHover) {
        this.clearTrafficHover();
        return;
      }
      const entry = this.pickTrafficHoverEntry(event.point);
      if (!entry || !entry.props) {
        this.clearTrafficHover();
        return;
      }
      const name = String(entry.props.name || "").trim();
      const coords = entry.coords && entry.coords.length >= 2 ? entry.coords : null;
      if (!name || !coords) {
        this.clearTrafficHover();
        return;
      }
      if (this.trafficHoverId !== entry.id || this.trafficHoverName !== name) {
        this.showTrafficHoverPopup(entry.props, coords, entry.id);
        this.trafficHoverName = name;
      } else if (this.trafficHoverPopup) {
        this.trafficHoverPopup.setLngLat(coords);
      }
      this.map.getCanvas().style.cursor = "pointer";
    },

    pickTrafficHoverEntry(point) {
      if (!this.map) {
        return null;
      }
      const pitch = this.map.getPitch ? this.map.getPitch() : 0;
      if (pitch <= TRAFFIC_2D_MAX_PITCH && this.map.queryRenderedFeatures) {
        const features = this.map.queryRenderedFeatures(point, {
          layers: ["traffic-points"],
        });
        if (features && features.length) {
          const entry = this.resolveTrafficEntryFromFeature(features[0]);
          if (entry) {
            return entry;
          }
        }
      }
      if (!this.traffic3dLayer || !this.traffic3dLayer.getMatrix) {
        return null;
      }
      const matrix = this.traffic3dLayer.getMatrix();
      if (!matrix) {
        return null;
      }
      const target = this.findTraffic3dHoverTarget(point, matrix);
      if (!target || target.id == null) {
        return null;
      }
      return this.trafficById.get(target.id) || null;
    },

    resolveTrafficEntryFromFeature(feature) {
      if (!feature) {
        return null;
      }
      let featureId = feature.id;
      if (featureId == null && feature.properties) {
        featureId = feature.properties.id;
      }
      if (featureId == null) {
        return null;
      }
      let entry = this.trafficById.get(featureId);
      if (!entry && typeof featureId === "string") {
        entry = this.trafficById.get(Number(featureId));
      }
      return entry || null;
    },

    showTrafficHoverPopup(props, lngLat, flightId) {
      if (!this.map) {
        return;
      }
      const numericId = Number(flightId);
      this.trafficHoverId = Number.isFinite(numericId) ? numericId : null;
      if (!this.trafficHoverPopup) {
        this.trafficHoverPopup = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          className: "traffic-hover-popup",
          offset: [0, -24],
        });
      }
      this.trafficHoverPopup
        .setLngLat(lngLat)
        .setDOMContent(this.buildTrafficHoverContent(props))
        .addTo(this.map);
    },

    showTrafficNamePopup(props, lngLat, flightId) {
      if (!this.map) {
        return;
      }
      this.trafficNamePopupId = flightId != null ? flightId : null;
      this.trafficNamePopupName = props && props.name ? String(props.name) : "";
      if (!this.trafficNamePopup) {
        this.trafficNamePopup = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          className: "traffic-hover-popup",
          offset: [0, -24],
        });
      }
      this.trafficNamePopup
        .setLngLat(lngLat)
        .setDOMContent(this.buildTrafficNameContent(props))
        .addTo(this.map);
    },

    buildTrafficHoverContent(props) {
      const card = document.createElement("div");
      card.className = "traffic-hover-card";
      const title = document.createElement("div");
      title.className = "traffic-hover-name";
      title.textContent = props.name ? String(props.name) : "Flight";
      const route = document.createElement("div");
      route.className = "traffic-hover-route";
      const from = props.from ? String(props.from) : "-";
      const to = props.to ? String(props.to) : "-";
      route.textContent = `${from} -> ${to}`;
      card.appendChild(title);
      card.appendChild(route);
      return card;
    },

    buildTrafficNameContent(props) {
      const card = document.createElement("div");
      card.className = "traffic-hover-card";
      const fields = {};
      const title = document.createElement("div");
      title.className = "traffic-hover-name";
      title.textContent = props.name ? String(props.name) : "Flight";
      title.dataset.field = "name";
      fields.name = title;
      const from = props.from ? String(props.from) : "-";
      const to = props.to ? String(props.to) : "-";
      const routeFrom = props.route_from ? String(props.route_from) : "";
      const routeTo = props.route_to ? String(props.route_to) : "";
      const routeText = routeFrom && routeTo ? `${routeFrom} -> ${routeTo}` : "-";
      const speedValue = Number(props.speed_mps);
      const speedText = Number.isFinite(speedValue)
        ? `${speedValue.toFixed(0)} m/s`
        : "-";
      const batteryValue = Number(props.battery_pct);
      const batteryText = Number.isFinite(batteryValue) ? `${batteryValue.toFixed(0)}%` : "-";
      const meta = document.createElement("div");
      meta.className = "traffic-hover-meta";
      const addRow = (label, value, field) => {
        const row = document.createElement("div");
        row.className = "traffic-hover-meta-row";
        const name = document.createElement("span");
        name.className = "traffic-hover-meta-label";
        name.textContent = label;
        const val = document.createElement("span");
        val.className = "traffic-hover-meta-value";
        val.textContent = value;
        if (field) {
          val.dataset.field = field;
          fields[field] = val;
        }
        row.appendChild(name);
        row.appendChild(val);
        meta.appendChild(row);
      };
      addRow("From", from, "from");
      addRow("To", to, "to");
      addRow("Route", routeText, "route");
      addRow("Speed", speedText, "speed");
      addRow("Battery", batteryText, "battery");
      card.appendChild(title);
      card.appendChild(meta);
      this.trafficNamePopupFields = fields;
      return card;
    },

    clearTrafficHover() {
      if (!this.map) {
        return;
      }
      this.hideTrafficHoverPopup();
      if (this.isEmergencyLandingMode && this.isEmergencyLandingMode()) {
        this.map.getCanvas().style.cursor = "crosshair";
        return;
      }
      if (this.isForceMoveMode && this.isForceMoveMode()) {
        this.map.getCanvas().style.cursor = "crosshair";
        return;
      }
      if (!this.corridorHover && !this.vertiportHover) {
        this.map.getCanvas().style.cursor = "";
      }
    },

    hideTrafficHoverPopup() {
      if (this.trafficHoverPopup) {
        this.trafficHoverPopup.remove();
      }
      this.trafficHoverId = null;
      this.trafficHoverName = "";
    },

    hideTrafficNamePopup() {
      if (this.trafficNamePopup) {
        this.trafficNamePopup.remove();
      }
      this.trafficNamePopupId = null;
      this.trafficNamePopupName = "";
      this.trafficNamePopupFields = null;
    },

    setTrafficSelectedState(nextId) {
      if (!this.map) {
        return;
      }
      const prevId = this.trafficSelectedId;
      if (nextId == null) {
        this.trafficSelectedId = null;
        this.hideTrafficPopup();
        this.hideTrafficHoverPopup();
        if (this.lastTraffic3dEntries.length) {
          this.updateTraffic3dLayer(this.lastTraffic3dEntries);
          this.updateTraffic2dLayer(this.lastTraffic3dEntries);
          if (this.traffic3dVisible || this.traffic2dVisible) {
            this.scheduleMapRepaint();
          }
        }
      } else if (this.trafficSelectedId !== nextId) {
        this.trafficSelectedId = nextId;
      }
      const changed = prevId !== this.trafficSelectedId;
      if (changed) {
        if (this.trafficSelectedId == null) {
          this.clearTrafficHistory();
          this.trafficPredictEnableAt = 0;
          this.trafficPredictVisible = false;
          this.stopPredictionFade();
          this.setPredictionOpacity(0);
          this.clearTrafficPrediction();
        } else {
          const entry = this.trafficById.get(this.trafficSelectedId);
          const name = entry && entry.props ? entry.props.name : "";
          this.resetTrafficHistoryByName(name);
          this.trafficPredictEnableAt = performance.now() + TRAFFIC_PREDICT_DELAY_MS;
          this.trafficPredictVisible = false;
          this.stopPredictionFade();
          this.setPredictionOpacity(0);
        }
      }
      if (this.lastTraffic3dEntries.length) {
        this.updateTraffic3dLayer(this.lastTraffic3dEntries);
        this.updateTraffic2dLayer(this.lastTraffic3dEntries);
        if (this.traffic3dVisible || this.traffic2dVisible) {
          this.scheduleMapRepaint();
        }
      }
      this.updateTrafficPrediction();
      if (this.trafficSelectedId == null) {
        this.setDashboardSelection("");
      } else {
        const entry = this.trafficById.get(this.trafficSelectedId);
        this.setDashboardSelection(entry && entry.props ? entry.props.name : "");
      }
    },

    isTrafficHighlighted(id) {
      if (id == null) {
        return false;
      }
      return this.trafficSelectedId != null && id === this.trafficSelectedId;
    },

    isTrafficHoverTarget(point) {
      if (!this.map || !this.traffic3dLayer || !this.traffic3dLayer.getMatrix) {
        return false;
      }
      const matrix = this.traffic3dLayer.getMatrix();
      if (!matrix) {
        return false;
      }
      const target = this.findTraffic3dHoverTarget(point, matrix);
      return Boolean(target && target.id != null);
    },

    handleTraffic3dClick(event) {
      if (!this.map) {
        return;
      }
      const hasEvent = Boolean(event && event.point);
      const point = hasEvent ? event.point : event;
      if (this.isEmergencyLandingMode && this.isEmergencyLandingMode()) {
        if (this.handleEmergencyLandingClick) {
          if (hasEvent) {
            this.handleEmergencyLandingClick(event);
          } else {
            const lngLat =
              point && this.map.unproject ? this.map.unproject(point) : null;
            this.handleEmergencyLandingClick({ point, lngLat });
          }
        }
        return;
      }
      if (this.isForceMoveMode && this.isForceMoveMode()) {
        if (this.handleForceMoveClick) {
          if (hasEvent) {
            this.handleForceMoveClick(event);
          } else {
            const lngLat =
              point && this.map.unproject ? this.map.unproject(point) : null;
            this.handleForceMoveClick({ point, lngLat });
          }
        }
        return;
      }
      const entry = this.pickTrafficHoverEntry(point);
      if (!entry || !entry.props || !entry.coords) {
        this.setTrafficSelectedState(null);
        this.hideTrafficNamePopup();
        this.notifySelectionCleared();
        return;
      }
      if (this.trafficSelectedId !== entry.id) {
        this.setTrafficSelectedState(entry.id);
      }
      this.hideTrafficNamePopup();
      this.hideTrafficHoverPopup();
      this.showTrafficPopup(entry.props, entry.coords, entry.id);
      if (entry.props && entry.props.name) {
        this.notifyFlightSelection(entry.props.name);
      }
    },

    handleTrafficNameClick(event) {
      if (!this.map) {
        return;
      }
      const hasEvent = Boolean(event && event.point);
      const point = hasEvent ? event.point : event;
      if (this.isEmergencyLandingMode && this.isEmergencyLandingMode()) {
        if (this.handleEmergencyLandingClick) {
          if (hasEvent) {
            this.handleEmergencyLandingClick(event);
          } else {
            const lngLat =
              point && this.map.unproject ? this.map.unproject(point) : null;
            this.handleEmergencyLandingClick({ point, lngLat });
          }
        }
        return;
      }
      if (this.isForceMoveMode && this.isForceMoveMode()) {
        if (this.handleForceMoveClick) {
          if (hasEvent) {
            this.handleForceMoveClick(event);
          } else {
            const lngLat =
              point && this.map.unproject ? this.map.unproject(point) : null;
            this.handleForceMoveClick({ point, lngLat });
          }
        }
        return;
      }
      const entry = this.pickTrafficHoverEntry(point);
      if (!entry || !entry.props || !entry.coords) {
        if (this.trafficSelectedId != null) {
          this.setTrafficSelectedState(null);
          this.notifySelectionCleared();
        }
        this.hideTrafficNamePopup();
        return;
      }
      if (
        point &&
        entry.id != null &&
        this.shouldTriggerRepeatTapContext &&
        this.shouldTriggerRepeatTapContext(`traffic-${entry.id}`, point)
      ) {
        const lngLat = entry.coords;
        const synthetic = this.buildSyntheticContextMenuEvent
          ? this.buildSyntheticContextMenuEvent(point, lngLat)
          : { point, lngLat, originalEvent: { preventDefault() {}, stopPropagation() {} } };
        this.handleTraffic3dClick(synthetic);
        return;
      }
      if (this.trafficNamePopupId === entry.id) {
        this.setTrafficSelectedState(null);
        this.notifySelectionCleared();
        this.hideTrafficNamePopup();
        return;
      }
      this.setTrafficSelectedState(entry.id);
      this.hideTrafficPopup();
      this.hideTrafficHoverPopup();
      this.showTrafficNamePopup(entry.props, entry.coords, entry.id);
      if (entry.props && entry.props.name) {
        this.notifyFlightSelection(entry.props.name);
      }
    },

    isEmergencyLandingMode() {
      return Boolean(this.emergencyLandingActive && this.emergencyLandingFlightId != null);
    },

    isForceMoveMode() {
      return Boolean(this.forceMoveActive && this.forceMoveFlightId != null);
    },

    startEmergencyLandingMode(flightId, flightName) {
      const id = Number(flightId);
      if (!Number.isFinite(id)) {
        this.addStatusMessage({
          text: this.t("status.select_valid_flight"),
          level: "warn",
          ttlMs: 2200,
        });
        return;
      }
      if (this.isForceMoveMode && this.isForceMoveMode()) {
        this.exitForceMoveMode("deny");
      }
      this.emergencyLandingActive = true;
      this.emergencyLandingFlightId = id;
      this.emergencyLandingFlightName = flightName ? String(flightName) : "";
      this.clearEmergencyLandingTarget();
      if (this.mapContainer) {
        this.mapContainer.classList.add("is-emergency");
      }
      if (this.map && this.map.getCanvas) {
        this.map.getCanvas().style.cursor = "crosshair";
      }
      this.hideTrafficPopup();
      this.hideTrafficHoverPopup();
      this.hideTrafficNamePopup();
      this.addStatusMessage({
        text: this.t("status.emergency_select_target"),
        level: "warn",
        ttlMs: 3500,
      });
    },

    startForceMoveMode(flightId, flightName) {
      const id = Number(flightId);
      if (!Number.isFinite(id)) {
        this.addStatusMessage({
          text: this.t("status.select_valid_flight"),
          level: "warn",
          ttlMs: 2200,
        });
        return;
      }
      if (this.isForceMoveMode && this.isForceMoveMode() && this.forceMoveFlightId === id) {
        this.exitForceMoveMode("deny");
        return;
      }
      if (this.isEmergencyLandingMode && this.isEmergencyLandingMode()) {
        this.exitEmergencyLandingMode("deny");
      }
      this.forceMoveActive = true;
      this.forceMoveFlightId = id;
      this.forceMoveFlightName = flightName ? String(flightName) : "";
      this.forceMoveHandled = false;
      if (this.map && this.map.getCanvas) {
        this.map.getCanvas().style.cursor = "crosshair";
      }
      this.hideTrafficPopup();
      this.hideTrafficHoverPopup();
      this.hideTrafficNamePopup();
      this.addStatusMessage({
        text: this.t("status.force_move_select_wp"),
        level: "warn",
        ttlMs: 3500,
      });
    },

    exitEmergencyLandingMode(reason) {
      this.emergencyLandingActive = false;
      this.emergencyLandingFlightId = null;
      this.emergencyLandingFlightName = "";
      this.clearEmergencyLandingTarget();
      if (this.mapContainer) {
        this.mapContainer.classList.remove("is-emergency");
      }
      if (this.map && this.map.getCanvas) {
        if (!(this.isForceMoveMode && this.isForceMoveMode())) {
          this.map.getCanvas().style.cursor = "";
        }
      }
      if (reason === "deny") {
        this.addStatusMessage({
          text: this.t("status.emergency_canceled"),
          level: "info",
          ttlMs: 2000,
        });
      }
    },

    exitForceMoveMode(reason) {
      this.forceMoveActive = false;
      this.forceMoveFlightId = null;
      this.forceMoveFlightName = "";
      this.forceMoveHandled = false;
      if (this.map && this.map.getCanvas) {
        if (!(this.isEmergencyLandingMode && this.isEmergencyLandingMode())) {
          this.map.getCanvas().style.cursor = "";
        }
      }
      if (reason === "deny") {
        this.addStatusMessage({
          text: this.t("status.force_move_canceled"),
          level: "info",
          ttlMs: 2000,
        });
      }
    },

    clearEmergencyLandingTarget() {
      if (this.emergencyLandingPopup) {
        this.emergencyLandingPopup.remove();
      }
      if (this.emergencyLandingMarker) {
        this.emergencyLandingMarker.remove();
      }
      this.emergencyLandingPopup = null;
      this.emergencyLandingMarker = null;
      this.emergencyLandingTarget = null;
      this.updateEmergencyLandingSource();
    },

    ensureEmergencyLandingLayer() {
      if (!this.map) {
        return;
      }
      const sourceId = "emergency-landing";
      if (!this.map.getSource(sourceId)) {
        this.map.addSource(sourceId, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!this.map.getLayer("emergency-landing-point")) {
        this.map.addLayer({
          id: "emergency-landing-point",
          type: "circle",
          source: sourceId,
          paint: {
            "circle-radius": 8 * MAP_SIZE_SCALE,
            "circle-color": "rgba(255, 95, 95, 0.25)",
            "circle-stroke-color": "#ff5f5f",
            "circle-stroke-width": 2 * MAP_SIZE_SCALE,
          },
        });
      }
    },

    updateEmergencyLandingSource() {
      if (!this.map) {
        return;
      }
      this.ensureEmergencyLandingLayer();
      const source = this.map.getSource("emergency-landing");
      if (!source || !source.setData) {
        return;
      }
      const features = [];
      if (this.emergencyLandingTarget) {
        features.push({
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [this.emergencyLandingTarget.lon, this.emergencyLandingTarget.lat],
          },
          properties: {
            label: this.emergencyLandingTarget.label || "",
          },
        });
      }
      source.setData({ type: "FeatureCollection", features });
    },

    setEmergencyLandingTarget(target) {
      if (!this.map || !target) {
        return;
      }
      this.emergencyLandingTarget = target;
      this.updateEmergencyLandingSource();
    },

    buildEmergencyLandingPopupContent(target) {
      const card = document.createElement("div");
      card.className = "emergency-landing-card";
      const title = document.createElement("div");
      title.className = "emergency-landing-title";
      title.textContent = this.t("label.landing_confirm");
      const detail = document.createElement("div");
      detail.className = "emergency-landing-detail";
      const label = target && target.label ? String(target.label) : this.translateLiteral("Point");
      detail.textContent = this.t("label.target_prefix", { label });
      const actions = document.createElement("div");
      actions.className = "emergency-landing-actions";
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = "emergency-landing-btn is-confirm";
      confirm.textContent = "Confirm";
      const deny = document.createElement("button");
      deny.type = "button";
      deny.className = "emergency-landing-btn is-deny";
      deny.textContent = "Deny";
      confirm.addEventListener("click", (event) => {
        if (event) {
          event.preventDefault();
          event.stopPropagation();
        }
        this.confirmEmergencyLanding();
      });
      deny.addEventListener("click", (event) => {
        if (event) {
          event.preventDefault();
          event.stopPropagation();
        }
        this.exitEmergencyLandingMode("deny");
      });
      actions.appendChild(confirm);
      actions.appendChild(deny);
      card.appendChild(title);
      card.appendChild(detail);
      card.appendChild(actions);
      return card;
    },

    showEmergencyLandingPopup(target, lngLat) {
      if (!this.map || !lngLat) {
        return;
      }
      if (!this.emergencyLandingPopup) {
        this.emergencyLandingPopup = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          className: "emergency-landing-popup",
          offset: [0, -12],
        });
      }
      this.emergencyLandingPopup
        .setLngLat(lngLat)
        .setDOMContent(this.buildEmergencyLandingPopupContent(target))
        .addTo(this.map);
    },

    confirmEmergencyLanding() {
      if (!this.emergencyLandingTarget || this.emergencyLandingFlightId == null) {
        this.addStatusMessage({
          text: this.t("status.pick_landing_point"),
          level: "warn",
          ttlMs: 2200,
        });
        return;
      }
      const target = this.emergencyLandingTarget;
      const altValue = Number(target.alt_m);
      const alt_m = Number.isFinite(altValue) ? altValue : VERTIPORT_ALT_M;
      const sent = this.sendControlCommand(
        "setEmergencyLanding",
        Number(this.emergencyLandingFlightId),
        Number(target.lon),
        Number(target.lat),
        target.label || "",
        alt_m,
      );
      if (!sent) {
        return;
      }
      if (typeof this.recordHumanIntervention === "function") {
        this.recordHumanIntervention("emergency", {
          flight_id: Number(this.emergencyLandingFlightId),
          flight_name: this.emergencyLandingFlightName || this.translateLiteral("Flight"),
          target: target.label || this.translateLiteral("Emergency Point"),
          lon: Number(target.lon),
          lat: Number(target.lat),
          alt_m,
        });
      }
      const flightName = this.emergencyLandingFlightName || this.translateLiteral("Flight");
      const label = target.label ? String(target.label) : this.translateLiteral("point");
      this.addStatusMessage({
        text: this.t("status.emergency_set", { flight: flightName, label }),
        level: "warn",
        ttlMs: 3000,
      });
      this.exitEmergencyLandingMode();
    },

    resolveEmergencyLandingTarget(point, lngLat) {
      const normalizeLngLat = (value) => {
        if (!value) {
          return { lon: Number.NaN, lat: Number.NaN };
        }
        if (Array.isArray(value)) {
          return { lon: Number(value[0]), lat: Number(value[1]) };
        }
        if (value.lng != null || value.lat != null) {
          return { lon: Number(value.lng), lat: Number(value.lat) };
        }
        if (value.lon != null || value.lat != null) {
          return { lon: Number(value.lon), lat: Number(value.lat) };
        }
        return { lon: Number.NaN, lat: Number.NaN };
      };
      const name = point ? this.pickVertiportAt(point) : null;
      if (name) {
        const entry = this.vertiportPointLookup.get(name);
        const coord = entry && entry.coord ? entry.coord : null;
        const fallback = normalizeLngLat(lngLat);
        const lon = coord ? Number(coord[0]) : fallback.lon;
        const lat = coord ? Number(coord[1]) : fallback.lat;
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          return null;
        }
        let altitude = VERTIPORT_ALT_M;
        if (this.resolveNodeAltitude) {
          const resolved = this.resolveNodeAltitude(name);
          if (Number.isFinite(resolved)) {
            altitude = resolved;
          }
        }
        return {
          lon,
          lat,
          label: name,
          alt_m: altitude,
          kind: "vertiport",
        };
      }
      if (!lngLat) {
        return null;
      }
      const resolved = normalizeLngLat(lngLat);
      const lon = resolved.lon;
      const lat = resolved.lat;
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return null;
      }
      return {
        lon,
        lat,
        label: "Emergency Point",
        alt_m: VERTIPORT_ALT_M,
        kind: "point",
      };
    },

    resolveForceMoveTarget(point) {
      if (!point) {
        return null;
      }
      const wpName = this.pickCorridorPoint ? this.pickCorridorPoint(point) : null;
      if (wpName) {
        return { name: String(wpName), kind: "corridor" };
      }
      const portName = this.pickVertiportAt ? this.pickVertiportAt(point) : null;
      if (portName) {
        return { name: String(portName), kind: "vertiport" };
      }
      return null;
    },

    handleForceMoveClick(event) {
      if (!this.isForceMoveMode || !this.isForceMoveMode()) {
        return false;
      }
      if (this.forceMoveHandled) {
        return true;
      }
      if (event && typeof event.preventDefault === "function") {
        event.preventDefault();
      }
      if (event && event.originalEvent) {
        if (typeof event.originalEvent.preventDefault === "function") {
          event.originalEvent.preventDefault();
        }
        if (typeof event.originalEvent.stopPropagation === "function") {
          event.originalEvent.stopPropagation();
        }
      }
      const pointer = this.resolveMapPointer
        ? this.resolveMapPointer(event)
        : {
            point: event && event.point ? event.point : null,
            lngLat: event && event.lngLat ? event.lngLat : null,
          };
      let point = pointer ? pointer.point : null;
      const lngLat = pointer ? pointer.lngLat : null;
      if (!point && lngLat && this.map && this.map.project) {
        point = this.map.project(lngLat);
      }
      if (!point) {
        return true;
      }
      const target = this.resolveForceMoveTarget(point);
      if (!target || !target.name) {
        this.addStatusMessage({
          text: this.t("status.force_move_select_wp"),
          level: "warn",
          ttlMs: 2000,
        });
        return true;
      }
      if (this.forceMoveFlightId == null) {
        this.addStatusMessage({
          text: this.t("status.select_valid_flight"),
          level: "warn",
          ttlMs: 2200,
        });
        return true;
      }
      const flightName = this.forceMoveFlightName || this.translateLiteral("Flight");
      const sent = this.sendControlCommand(
        "forceMoveVia",
        Number(this.forceMoveFlightId),
        target.name,
      );
      if (sent) {
        this.forceMoveHandled = true;
        this.addStatusMessage({
          text: this.t("status.force_move_requested", { flight: flightName, wp: target.name }),
          level: "info",
          ttlMs: 2500,
        });
        if (typeof window !== "undefined" && window.setTimeout) {
          window.setTimeout(() => this.exitForceMoveMode(), 0);
        } else {
          this.exitForceMoveMode();
        }
      }
      return true;
    },

    handleEmergencyLandingClick(event) {
      if (!this.isEmergencyLandingMode()) {
        return false;
      }
      if (this.emergencyLandingTarget) {
        if (!this.emergencyLandingPopup && this.emergencyLandingTarget) {
          this.showEmergencyLandingPopup(this.emergencyLandingTarget, {
            lng: this.emergencyLandingTarget.lon,
            lat: this.emergencyLandingTarget.lat,
          });
        }
        return true;
      }
      if (event && typeof event.preventDefault === "function") {
        event.preventDefault();
      }
      if (event && event.originalEvent) {
        if (typeof event.originalEvent.preventDefault === "function") {
          event.originalEvent.preventDefault();
        }
        if (typeof event.originalEvent.stopPropagation === "function") {
          event.originalEvent.stopPropagation();
        }
      }
      const pointer = this.resolveMapPointer
        ? this.resolveMapPointer(event)
        : {
            point: event && event.point ? event.point : null,
            lngLat: event && event.lngLat ? event.lngLat : null,
          };
      let point = pointer ? pointer.point : null;
      let lngLat = pointer ? pointer.lngLat : null;
      if (!point && lngLat && this.map && this.map.project) {
        point = this.map.project(lngLat);
      }
      if (!lngLat && point && this.map && this.map.unproject) {
        lngLat = this.map.unproject(point);
      }
      if (!point && !lngLat) {
        return true;
      }
      const target = this.resolveEmergencyLandingTarget(point, lngLat);
      if (!target) {
        return true;
      }
      this.setEmergencyLandingTarget(target);
      this.showEmergencyLandingPopup(target, { lng: target.lon, lat: target.lat });
      return true;
    },

    getTrafficHoverThreshold() {
      const base = TRAFFIC_HIT_RADIUS * 1.1;
      if (!this.map || !this.traffic3dLayer) {
        return base;
      }
      const pointSize = this.traffic3dLayer._pointSize;
      if (!Number.isFinite(pointSize) || pointSize <= 0) {
        return base;
      }
      const canvas = this.map.getCanvas();
      const pixelRatio =
        canvas.clientWidth > 0 ? canvas.width / canvas.clientWidth : window.devicePixelRatio || 1;
      const sizeCss = pointSize / pixelRatio;
      return Math.max(base, sizeCss * 0.55);
    },

    resolveAltitudeValue(entry) {
      if (!entry) {
        return NaN;
      }
      const raw =
        entry.altitude_m != null
          ? entry.altitude_m
          : entry.alt_m != null
            ? entry.alt_m
            : entry.altitude != null
              ? entry.altitude
              : entry.alt;
      const value = Number.parseFloat(raw);
      return Number.isFinite(value) ? value : NaN;
    },

    coerceRiskLevel(value) {
      if (value == null) {
        return 0;
      }
      const numeric = Number(value);
      if (Number.isFinite(numeric)) {
        return Math.max(0, Math.min(3, Math.round(numeric)));
      }
      const text = String(value);
      const match = text.match(/\d/);
      if (match) {
        const parsed = Number(match[0]);
        if (Number.isFinite(parsed)) {
          return Math.max(0, Math.min(3, Math.round(parsed)));
        }
      }
      return 0;
    },

    resolveTrafficEntryByKey(id, name) {
      if (!this.trafficById || !this.trafficByName) {
        return null;
      }
      const candidates = [];
      if (id != null) {
        candidates.push(id);
        const numeric = Number(id);
        if (Number.isFinite(numeric) && numeric !== id) {
          candidates.push(numeric);
        }
        const stringId = String(id);
        if (stringId !== id) {
          candidates.push(stringId);
        }
      }
      for (const key of candidates) {
        const entry = this.trafficById.get(key);
        if (entry) {
          return entry;
        }
      }
      if (name) {
        return this.trafficByName.get(name) || null;
      }
      return null;
    },

    resolveTrafficPopupEntry() {
      let entry = this.resolveTrafficEntryByKey(
        this.trafficPopupFlightId,
        this.trafficPopupFlightName,
      );
      if (entry) {
        return entry;
      }
      if (this.trafficSelectedId != null) {
        entry = this.resolveTrafficEntryByKey(this.trafficSelectedId, "");
        if (entry) {
          return entry;
        }
      }
      if (this.trafficNamePopupId != null || this.trafficNamePopupName) {
        entry = this.resolveTrafficEntryByKey(this.trafficNamePopupId, this.trafficNamePopupName);
        if (entry) {
          return entry;
        }
      }
      return null;
    },

    resolvePopupAltitude(props, entry) {
      const fallback = this.resolveAltitudeValue(props);
      if (!this.trafficAltitudeById || this.trafficAltitudeById.size === 0) {
        return fallback;
      }
      const target = entry || this.resolveTrafficPopupEntry();
      if (target && target.id != null) {
        const direct = this.trafficAltitudeById.get(target.id);
        if (Number.isFinite(direct)) {
          return direct;
        }
        const numeric = Number(target.id);
        if (Number.isFinite(numeric)) {
          const viaNumeric = this.trafficAltitudeById.get(numeric);
          if (Number.isFinite(viaNumeric)) {
            return viaNumeric;
          }
        }
        const viaString = this.trafficAltitudeById.get(String(target.id));
        if (Number.isFinite(viaString)) {
          return viaString;
        }
      }
      return fallback;
    },

    resolveWindText(lon, lat) {
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return "-";
      }
      if (typeof this.getWeatherWindAt !== "function") {
        return "-";
      }
      const wind = this.getWeatherWindAt(lon, lat);
      if (!wind || !Number.isFinite(wind.speed) || !Number.isFinite(wind.u) || !Number.isFinite(wind.v)) {
        return "-";
      }
      const speed = wind.speed;
      const dirTo = (Math.atan2(wind.u, wind.v) * 180 / Math.PI + 360) % 360;
      const dirFrom = (dirTo + 180) % 360;
      if (!Number.isFinite(speed) || !Number.isFinite(dirFrom)) {
        return "-";
      }
      return this.t("label.wind_readout", {
        speed: speed.toFixed(1),
        dir: dirFrom.toFixed(0),
      });
    },

    resolveWindTextFromEntry(entry) {
      if (!entry || !Array.isArray(entry.coords) || entry.coords.length < 2) {
        return "-";
      }
      const [lon, lat] = entry.coords;
      return this.resolveWindText(lon, lat);
    },

    getLateralDeviationInfo(value) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) {
        return { text: "-", percent: 50, isOver: false };
      }
      let limit = DEFAULT_LATERAL_LIMIT_M;
      if (this.rulesState && Number.isFinite(this.rulesState.rnp_max_lat_m)) {
        limit = Math.max(0, Number(this.rulesState.rnp_max_lat_m));
      }
      if (!Number.isFinite(limit) || limit <= 0) {
        return { text: "-", percent: 50, isOver: false };
      }
      const absValue = Math.abs(parsed);
      const dir = parsed >= 0 ? this.t("direction.right") : this.t("direction.left");
      const signed = `${parsed >= 0 ? "+" : "-"}${absValue.toFixed(0)} m`;
      const clamped = clampTrafficValue(parsed, -limit, limit);
      const percent = ((clamped / limit) + 1) * 50;
      return {
        text: `${signed} (${dir})`,
        percent,
        isOver: absValue > limit,
      };
    },

    updateLateralDeviationDisplay(value, markerEl, valueEl) {
      if (!markerEl && !valueEl) {
        return;
      }
      const info = this.getLateralDeviationInfo(value);
      if (valueEl) {
        valueEl.textContent = info.text;
        valueEl.classList.toggle("is-over", info.isOver);
      }
      if (markerEl) {
        markerEl.style.left = `${info.percent.toFixed(1)}%`;
        markerEl.classList.toggle("is-over", info.isOver);
      }
    },

    formatTrafficMetricTime(seconds) {
      const value = Number(seconds);
      if (!Number.isFinite(value)) {
        return "-";
      }
      if (typeof this.formatDashboardTime === "function") {
        return this.formatDashboardTime(value);
      }
      if (typeof this.formatTime === "function") {
        return this.formatTime(value);
      }
      return `${Math.round(value)}s`;
    },

    formatTrafficMetricDelay(seconds) {
      const value = Number(seconds);
      if (!Number.isFinite(value)) {
        return "-";
      }
      const rounded = Math.round(value);
      if (!rounded) {
        return "0s";
      }
      const sign = rounded > 0 ? "+" : "-";
      const absValue = Math.abs(rounded);
      if (absValue >= 3600) {
        return `${sign}${(absValue / 3600).toFixed(1)}h`;
      }
      if (absValue >= 60) {
        return `${sign}${Math.round(absValue / 60)}m`;
      }
      return `${sign}${absValue}s`;
    },

    formatTrafficMetricTti(value) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed) || parsed < 0) {
        return "-";
      }
      return `${parsed.toFixed(2)}x`;
    },

    formatTrafficMetricCongestion(value) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed) || parsed < 0) {
        return "-";
      }
      return parsed.toFixed(2);
    },

    resolveTrafficCongestionScore(props, entryId) {
      const direct = Number(props && props.congestion_score);
      if (Number.isFinite(direct)) {
        return direct;
      }
      const map =
        this.congestionScoreById instanceof Map ? this.congestionScoreById : null;
      if (!map) {
        return null;
      }
      const id = entryId != null ? entryId : props && props.id != null ? props.id : null;
      if (id == null) {
        return null;
      }
      const score = map.get(id);
      return Number.isFinite(score) ? score : null;
    },

    buildTrafficPopupContent(props, flightId, lngLat) {
      const card = document.createElement("div");
      card.className = "traffic-card";
      const fields = {};
      const title = document.createElement("div");
      title.className = "traffic-card-title";
      const name = props.name ? String(props.name) : "Flight";
      title.textContent = name;
      card.appendChild(title);

      const grid = document.createElement("div");
      grid.className = "traffic-card-grid";
      const addRow = (label, value, field) => {
        const row = document.createElement("div");
        row.className = "traffic-card-row";
        const key = document.createElement("span");
        key.className = "traffic-card-key";
        key.textContent = label;
        const val = document.createElement("span");
        val.className = "traffic-card-value";
        val.textContent = value;
        if (field) {
          val.dataset.field = field;
          fields[field] = val;
        }
        row.appendChild(key);
        row.appendChild(val);
        grid.appendChild(row);
      };

      const from = props.from ? String(props.from) : "-";
      const to = props.to ? String(props.to) : "-";
      const routeFrom = props.route_from ? String(props.route_from) : "";
      const routeTo = props.route_to ? String(props.route_to) : "";
      const routeText = routeFrom && routeTo ? `${routeFrom} -> ${routeTo}` : "-";
      const risk = props.risk ? String(props.risk) : "-";
      const riskReason = props.risk_reason ? String(props.risk_reason) : "-";
      const speed = Number(props.speed_mps);
      const speedText = Number.isFinite(speed) ? `${speed.toFixed(0)} m/s` : "-";
      const targetSpeedValue = Number(props.speed_target_mps);
      let targetSpeed = Number.isFinite(targetSpeedValue) ? targetSpeedValue : Number.NaN;
      if (!Number.isFinite(targetSpeed)) {
        const ruleSpeed =
          this.rulesState && Number.isFinite(this.rulesState.speed_mps)
            ? Number(this.rulesState.speed_mps)
            : Number.NaN;
        targetSpeed = Number.isFinite(ruleSpeed)
          ? ruleSpeed
          : Number.isFinite(speed)
            ? speed
            : Number.NaN;
      }
      const battery = Number(props.battery_pct);
      const batteryText = Number.isFinite(battery) ? `${battery.toFixed(0)}%` : "-";
      const heading = Number(props.heading);
      const headingText = Number.isFinite(heading) ? `${heading.toFixed(0)} deg` : "-";
      const altitude = this.resolvePopupAltitude(props);
      const altitudeText = Number.isFinite(altitude)
        ? `${altitude.toFixed(0)} m (${(altitude / FT_TO_M).toFixed(0)} ft)`
        : "-";
      const windText =
        Array.isArray(lngLat) && lngLat.length >= 2
          ? this.resolveWindText(lngLat[0], lngLat[1])
          : "-";
      addRow("From", from, "from");
      addRow("To", to, "to");
      addRow("Route", routeText, "route");
      addRow("Speed", speedText, "speed");
      addRow("Battery", batteryText, "battery");
      addRow("HDG", headingText, "heading");
      addRow("Wind", windText, "wind");
      addRow("Altitude", altitudeText, "altitude");
      addRow("Risk", risk, "risk");
      addRow("Reason", riskReason, "riskReason");
      card.appendChild(grid);
      const metricsWrap = document.createElement("div");
      metricsWrap.className = "traffic-metrics";
      const metricsTitle = document.createElement("div");
      metricsTitle.className = "traffic-metrics-title";
      metricsTitle.textContent = "Schedule / ETA";
      metricsWrap.appendChild(metricsTitle);
      const metricsGrid = document.createElement("div");
      metricsGrid.className = "traffic-metrics-grid";
      const addMetric = (label, value, field) => {
        const row = document.createElement("div");
        row.className = "traffic-metrics-row";
        const key = document.createElement("span");
        key.className = "traffic-metrics-key";
        key.textContent = label;
        const val = document.createElement("span");
        val.className = "traffic-metrics-value";
        val.textContent = value;
        if (field) {
          val.dataset.field = field;
          fields[field] = val;
        }
        row.appendChild(key);
        row.appendChild(val);
        metricsGrid.appendChild(row);
      };
      addMetric("STD", this.formatTrafficMetricTime(props.std_s), "std");
      addMetric("STA", this.formatTrafficMetricTime(props.sta_s), "sta");
      addMetric("ETA", this.formatTrafficMetricTime(props.eta_s), "eta");
      addMetric("ATA", this.formatTrafficMetricTime(props.ata_s), "ata");
      addMetric("Delay", this.formatTrafficMetricDelay(props.delay_s), "delay");
      addMetric(
        "Congestion",
        this.formatTrafficMetricCongestion(this.resolveTrafficCongestionScore(props, flightId)),
        "congestion",
      );
      addMetric("TTI", this.formatTrafficMetricTti(props.tti), "tti");
      metricsWrap.appendChild(metricsGrid);
      card.appendChild(metricsWrap);
      const lateralValue = Number(props.lateral_dev_m);
      let lateralLimit = DEFAULT_LATERAL_LIMIT_M;
      if (this.rulesState && Number.isFinite(this.rulesState.rnp_max_lat_m)) {
        lateralLimit = Math.max(0, Number(this.rulesState.rnp_max_lat_m));
      }
      const lateralWrap = document.createElement("div");
      lateralWrap.className = "traffic-lateral";
      const lateralHeader = document.createElement("div");
      lateralHeader.className = "traffic-lateral-header";
      const lateralTitle = document.createElement("span");
      lateralTitle.className = "traffic-lateral-title";
      lateralTitle.textContent = "Lateral Deviation (d_lat)";
      const lateralValueEl = document.createElement("span");
      lateralValueEl.className = "traffic-lateral-value";
      lateralValueEl.dataset.field = "lateral-value";
      fields.lateralValue = lateralValueEl;
      lateralHeader.appendChild(lateralTitle);
      lateralHeader.appendChild(lateralValueEl);
      const lateralScale = document.createElement("div");
      lateralScale.className = "traffic-lateral-scale";
      const lateralLeft = document.createElement("span");
      lateralLeft.textContent = `-${Math.round(lateralLimit)}m`;
      const lateralRight = document.createElement("span");
      lateralRight.textContent = `+${Math.round(lateralLimit)}m`;
      lateralScale.appendChild(lateralLeft);
      lateralScale.appendChild(lateralRight);
      const lateralBar = document.createElement("div");
      lateralBar.className = "traffic-lateral-bar";
      const lateralLine = document.createElement("div");
      lateralLine.className = "traffic-lateral-line";
      const lateralCenter = document.createElement("div");
      lateralCenter.className = "traffic-lateral-center";
      const lateralMarker = document.createElement("div");
      lateralMarker.className = "traffic-lateral-marker";
      lateralMarker.dataset.field = "lateral-marker";
      fields.lateralMarker = lateralMarker;
      lateralBar.appendChild(lateralLine);
      lateralBar.appendChild(lateralCenter);
      lateralBar.appendChild(lateralMarker);
      lateralWrap.appendChild(lateralHeader);
      lateralWrap.appendChild(lateralScale);
      lateralWrap.appendChild(lateralBar);
      card.appendChild(lateralWrap);
      this.updateLateralDeviationDisplay(lateralValue, lateralMarker, lateralValueEl);
      const controls = document.createElement("div");
      controls.className = "traffic-control";
      const controlTitle = document.createElement("div");
      controlTitle.className = "traffic-control-title";
      controlTitle.textContent = "Control";
      controls.appendChild(controlTitle);

      const speedRow = document.createElement("div");
      speedRow.className = "traffic-control-row";
      const speedLabel = document.createElement("span");
      speedLabel.className = "traffic-control-label";
      speedLabel.textContent = "Target Speed";
      const speedInput = document.createElement("input");
      speedInput.className = "traffic-control-input";
      speedInput.type = "number";
      speedInput.min = "0";
      speedInput.step = "3";
      speedInput.placeholder = "m/s";
      speedInput.dataset.field = "speed-input";
      if (Number.isFinite(targetSpeed)) {
        speedInput.value = targetSpeed.toFixed(1);
      }
      fields.speedInput = speedInput;
      const speedUnit = document.createElement("span");
      speedUnit.className = "traffic-control-unit";
      speedUnit.textContent = "m/s";
      const speedApply = document.createElement("button");
      speedApply.type = "button";
      speedApply.className = "traffic-control-btn is-primary";
      speedApply.textContent = "Apply";
      const speedReset = document.createElement("button");
      speedReset.type = "button";
      speedReset.className = "traffic-control-btn";
      speedReset.textContent = "Reset";
      speedRow.appendChild(speedLabel);
      speedRow.appendChild(speedInput);
      speedRow.appendChild(speedUnit);
      speedRow.appendChild(speedApply);
      speedRow.appendChild(speedReset);
      controls.appendChild(speedRow);

      const holdRow = document.createElement("div");
      holdRow.className = "traffic-control-row";
      const holdLabel = document.createElement("span");
      holdLabel.className = "traffic-control-label";
      holdLabel.textContent = "Holding";
      const holdInput = document.createElement("input");
      holdInput.className = "traffic-control-input";
      holdInput.type = "number";
      holdInput.min = "1";
      holdInput.step = "1";
      holdInput.value = "1";
      const holdUnit = document.createElement("span");
      holdUnit.className = "traffic-control-unit";
      holdUnit.textContent = "loops";
      const holdStart = document.createElement("button");
      holdStart.type = "button";
      holdStart.className = "traffic-control-btn is-primary";
      holdStart.textContent = "Hold";
      const holdStop = document.createElement("button");
      holdStop.type = "button";
      holdStop.className = "traffic-control-btn";
      holdStop.textContent = "Resume";
      holdRow.appendChild(holdLabel);
      holdRow.appendChild(holdInput);
      holdRow.appendChild(holdUnit);
      holdRow.appendChild(holdStart);
      holdRow.appendChild(holdStop);
      controls.appendChild(holdRow);

      const hint = document.createElement("div");
      hint.className = "traffic-control-hint";
      hint.textContent = "Right-turn holding circle (radius from turn-rate rule).";
      controls.appendChild(hint);

      const windRow = document.createElement("div");
      windRow.className = "traffic-control-row traffic-control-row-inline";
      const windLabel = document.createElement("span");
      windLabel.className = "traffic-control-label";
      windLabel.textContent = "Route keep";
      const windStrong = document.createElement("button");
      windStrong.type = "button";
      windStrong.className = "traffic-control-btn";
      windStrong.textContent = "Strong";
      const windMiddle = document.createElement("button");
      windMiddle.type = "button";
      windMiddle.className = "traffic-control-btn";
      windMiddle.textContent = "Normal";
      windRow.appendChild(windLabel);
      windRow.appendChild(windStrong);
      windRow.appendChild(windMiddle);
      controls.appendChild(windRow);

      const forceMoveRow = document.createElement("div");
      forceMoveRow.className = "traffic-control-row";
      const forceMoveButton = document.createElement("button");
      forceMoveButton.type = "button";
      forceMoveButton.className = "traffic-control-btn";
      forceMoveButton.textContent = "Force Move (WP)";
      forceMoveRow.appendChild(forceMoveButton);
      controls.appendChild(forceMoveRow);

      const emergencyRow = document.createElement("div");
      emergencyRow.className = "traffic-control-row";
      const emergencyButton = document.createElement("button");
      emergencyButton.type = "button";
      emergencyButton.className = "traffic-control-btn is-danger";
      emergencyButton.textContent = "Emergency Landing";
      emergencyRow.appendChild(emergencyButton);
      controls.appendChild(emergencyRow);

      const controlId = Number(flightId);
      const controlsEnabled = this.isControlBridgeReady() && Number.isFinite(controlId);
      const setWindActive = (level) => {
        windStrong.classList.toggle("is-active", level === "strong");
        windMiddle.classList.toggle("is-active", level === "normal");
      };
      [
        speedApply,
        speedReset,
        holdStart,
        holdStop,
        speedInput,
        holdInput,
        windStrong,
        windMiddle,
        forceMoveButton,
        emergencyButton,
      ].forEach((el) => {
        el.disabled = !controlsEnabled;
      });

      speedApply.addEventListener("click", () => {
        const value = Number.parseFloat(speedInput.value);
        if (!Number.isFinite(value) || value <= 0) {
          this.addStatusMessage({
            text: this.t("status.enter_valid_speed"),
            level: "warn",
            ttlMs: 2000,
          });
          return;
        }
        if (
          Number.isFinite(controlId) &&
          this.sendControlCommand("setFlightSpeed", controlId, value)
        ) {
          this.addStatusMessage({
            text: this.t("status.speed_set", { name }),
            level: "info",
            ttlMs: 2000,
          });
          if (typeof this.recordHumanIntervention === "function") {
            this.recordHumanIntervention("speed", {
              flight_id: controlId,
              flight_name: name,
              action: "set",
              speed_mps: value,
            });
          }
        }
      });
      speedReset.addEventListener("click", () => {
        if (Number.isFinite(controlId) && this.sendControlCommand("clearFlightSpeed", controlId)) {
          this.addStatusMessage({
            text: this.t("status.speed_reset", { name }),
            level: "info",
            ttlMs: 2000,
          });
          if (typeof this.recordHumanIntervention === "function") {
            this.recordHumanIntervention("speed", {
              flight_id: controlId,
              flight_name: name,
              action: "reset",
              speed_mps: null,
            });
          }
        }
      });
      holdStart.addEventListener("click", () => {
        const loops = Math.max(1, Number.parseInt(holdInput.value, 10) || 1);
        if (Number.isFinite(controlId) && this.sendControlCommand("startHolding", controlId, loops)) {
          this.addStatusMessage({
            text: this.t("status.holding_started", { name }),
            level: "info",
            ttlMs: 2200,
          });
          if (typeof this.recordHumanIntervention === "function") {
            this.recordHumanIntervention("speed", {
              flight_id: controlId,
              flight_name: name,
              action: `hold-start (${loops} loops)`,
              speed_mps: null,
            });
          }
        }
      });
      holdStop.addEventListener("click", () => {
        if (Number.isFinite(controlId) && this.sendControlCommand("stopHolding", controlId)) {
          this.addStatusMessage({
            text: this.t("status.holding_exit", { name }),
            level: "info",
            ttlMs: 2600,
          });
          if (typeof this.recordHumanIntervention === "function") {
            this.recordHumanIntervention("speed", {
              flight_id: controlId,
              flight_name: name,
              action: "hold-stop",
              speed_mps: null,
            });
          }
        }
      });
      windStrong.addEventListener("click", () => {
        if (Number.isFinite(controlId) && this.sendControlCommand("setWindHold", controlId, 0.3, 7)) {
          setWindActive("strong");
          this.addStatusMessage({
            text: this.t("status.wind_hold_strong", { name }),
            level: "info",
            ttlMs: 2200,
          });
        }
      });
      windMiddle.addEventListener("click", () => {
        if (
          Number.isFinite(controlId) &&
          this.sendControlCommand("setWindHold", controlId, 0.5, 12)
        ) {
          setWindActive("normal");
          this.addStatusMessage({
            text: this.t("status.wind_hold_normal", { name }),
            level: "info",
            ttlMs: 2200,
          });
        }
      });
      forceMoveButton.addEventListener("click", (event) => {
        if (event) {
          event.preventDefault();
          event.stopPropagation();
        }
        if (Number.isFinite(controlId)) {
          this.startForceMoveMode(controlId, name);
        }
      });
      emergencyButton.addEventListener("click", (event) => {
        if (event) {
          event.preventDefault();
          event.stopPropagation();
        }
        if (Number.isFinite(controlId)) {
          this.startEmergencyLandingMode(controlId, name);
        }
      });

      card.appendChild(controls);
      this.trafficPopupFields = fields;
      return card;
    },

    showTrafficPopup(props, lngLat, flightId) {
      if (!this.map) {
        return;
      }
      this.trafficPopupFlightId = flightId != null ? flightId : null;
      this.trafficPopupFlightName = props && props.name ? String(props.name) : "";
      const anchor = this.getTrafficPopupAnchor(lngLat);
      if (!this.trafficPopup || this.trafficPopupAnchor !== anchor) {
        if (this.trafficPopup) {
          this.trafficPopup.remove();
        }
        this.trafficPopup = new maplibregl.Popup({
          closeButton: true,
          closeOnClick: true,
          className: "traffic-popup",
          anchor,
        });
        if (this.trafficPopup.on) {
          this.trafficPopup.on("close", () => {
            this.trafficPopupFlightId = null;
            this.trafficPopupFlightName = "";
            this.trafficPopupFields = null;
            this.trafficPopupAnchor = null;
          });
        }
        this.trafficPopupAnchor = anchor;
      }
      if (this.trafficPopup.setOffset) {
        this.trafficPopup.setOffset(this.getTrafficPopupOffset(this.trafficPopupAnchor));
      }
      this.trafficPopup
        .setLngLat(lngLat)
        .setDOMContent(this.buildTrafficPopupContent(props, flightId, lngLat))
        .addTo(this.map);
    },

    hideTrafficPopup() {
      if (this.trafficPopup) {
        this.trafficPopup.remove();
      }
      this.trafficPopupFlightId = null;
      this.trafficPopupFlightName = "";
      this.trafficPopupFields = null;
      this.trafficPopupAnchor = null;
    },

    syncTrafficPopupPosition() {
      if (!this.trafficPopup) {
        return;
      }
      if (this.trafficPopup.isOpen && !this.trafficPopup.isOpen()) {
        return;
      }
      const entry = this.resolveTrafficPopupEntry();
      if (!entry || !entry.coords || entry.coords.length < 2) {
        return;
      }
      const [lon, lat] = entry.coords;
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return;
      }
      const anchor = this.trafficPopupAnchor || this.getTrafficPopupAnchor([lon, lat]);
      if (anchor !== this.trafficPopupAnchor) {
        this.showTrafficPopup(entry.props, [lon, lat], entry.id);
        return;
      }
      if (this.trafficPopup.setOffset) {
        this.trafficPopup.setOffset(this.getTrafficPopupOffset(anchor));
      }
      this.trafficPopup.setLngLat([lon, lat]);
      if (entry.props) {
        this.updateTrafficPopupContent(entry.props, entry);
      }
    },

    syncTrafficNamePopupPosition() {
      if (!this.trafficNamePopup || (this.trafficNamePopupId == null && !this.trafficNamePopupName)) {
        return;
      }
      const entry = this.resolveTrafficEntryByKey(
        this.trafficNamePopupId,
        this.trafficNamePopupName,
      );
      if (!entry || !entry.coords || entry.coords.length < 2) {
        this.hideTrafficNamePopup();
        return;
      }
      const [lon, lat] = entry.coords;
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return;
      }
      this.trafficNamePopup.setLngLat([lon, lat]);
      if (entry.props) {
        this.updateTrafficNamePopupContent(entry.props);
      }
    },

    updateTrafficPopupContent(props, entry) {
      if (!props) {
        return;
      }
      const fields = this.trafficPopupFields || null;
      const popupEl =
        this.trafficPopup && this.trafficPopup.getElement
          ? this.trafficPopup.getElement()
          : null;
      if (!popupEl && !fields) {
        return;
      }
      const setField = (field, text) => {
        if (fields && fields[field]) {
          fields[field].textContent = text;
          return;
        }
        if (!popupEl) {
          return;
        }
        const el = popupEl.querySelector(`[data-field="${field}"]`);
        if (el) {
          el.textContent = text;
        }
      };
      const from = props.from ? String(props.from) : "-";
      const to = props.to ? String(props.to) : "-";
      const routeFrom = props.route_from ? String(props.route_from) : "";
      const routeTo = props.route_to ? String(props.route_to) : "";
      const routeText = routeFrom && routeTo ? `${routeFrom} -> ${routeTo}` : "-";
      const risk = props.risk ? String(props.risk) : "-";
      const riskReason = props.risk_reason ? String(props.risk_reason) : "-";
      const speed = Number(props.speed_mps);
      const speedText = Number.isFinite(speed) ? `${speed.toFixed(0)} m/s` : "-";
      const targetSpeedValue = Number(props.speed_target_mps);
      let targetSpeed = Number.isFinite(targetSpeedValue) ? targetSpeedValue : Number.NaN;
      if (!Number.isFinite(targetSpeed)) {
        const ruleSpeed =
          this.rulesState && Number.isFinite(this.rulesState.speed_mps)
            ? Number(this.rulesState.speed_mps)
            : Number.NaN;
        targetSpeed = Number.isFinite(ruleSpeed)
          ? ruleSpeed
          : Number.isFinite(speed)
            ? speed
            : Number.NaN;
      }
      const battery = Number(props.battery_pct);
      const batteryText = Number.isFinite(battery) ? `${battery.toFixed(0)}%` : "-";
      const heading = Number(props.heading);
      const headingText = Number.isFinite(heading) ? `${heading.toFixed(0)} deg` : "-";
      const altitude = this.resolvePopupAltitude(props, entry);
      const altitudeText = Number.isFinite(altitude)
        ? `${altitude.toFixed(0)} m (${(altitude / FT_TO_M).toFixed(0)} ft)`
        : "-";
      const windText = this.resolveWindTextFromEntry(entry);
      setField("from", from);
      setField("to", to);
      setField("route", routeText);
      setField("speed", speedText);
      setField("battery", batteryText);
      setField("heading", headingText);
      setField("wind", windText);
      setField("altitude", altitudeText);
      setField("risk", risk);
      setField("riskReason", riskReason);
      setField("std", this.formatTrafficMetricTime(props.std_s));
      setField("sta", this.formatTrafficMetricTime(props.sta_s));
      setField("eta", this.formatTrafficMetricTime(props.eta_s));
      setField("ata", this.formatTrafficMetricTime(props.ata_s));
      setField("delay", this.formatTrafficMetricDelay(props.delay_s));
      setField(
        "congestion",
        this.formatTrafficMetricCongestion(
          this.resolveTrafficCongestionScore(props, entry ? entry.id : null),
        ),
      );
      setField("tti", this.formatTrafficMetricTti(props.tti));
      const lateralValue = Number(props.lateral_dev_m);
      const lateralMarker =
        fields && fields.lateralMarker
          ? fields.lateralMarker
          : popupEl
            ? popupEl.querySelector('[data-field="lateral-marker"]')
            : null;
      const lateralValueEl =
        fields && fields.lateralValue
          ? fields.lateralValue
          : popupEl
            ? popupEl.querySelector('[data-field="lateral-value"]')
            : null;
      this.updateLateralDeviationDisplay(lateralValue, lateralMarker, lateralValueEl);
      const speedInput =
        fields && fields.speedInput
          ? fields.speedInput
          : popupEl
            ? popupEl.querySelector('[data-field="speed-input"]')
            : null;
      if (speedInput && document.activeElement !== speedInput) {
        speedInput.value = Number.isFinite(targetSpeed) ? targetSpeed.toFixed(1) : "";
      }
    },

    updateTrafficNamePopupContent(props) {
      if (!props) {
        return;
      }
      const fields = this.trafficNamePopupFields || null;
      const popupEl =
        this.trafficNamePopup && this.trafficNamePopup.getElement
          ? this.trafficNamePopup.getElement()
          : null;
      if (!popupEl && !fields) {
        return;
      }
      const setField = (field, text) => {
        if (fields && fields[field]) {
          fields[field].textContent = text;
          return;
        }
        if (!popupEl) {
          return;
        }
        const el = popupEl.querySelector(`[data-field="${field}"]`);
        if (el) {
          el.textContent = text;
        }
      };
      const name = props.name ? String(props.name) : "Flight";
      const from = props.from ? String(props.from) : "-";
      const to = props.to ? String(props.to) : "-";
      const routeFrom = props.route_from ? String(props.route_from) : "";
      const routeTo = props.route_to ? String(props.route_to) : "";
      const routeText = routeFrom && routeTo ? `${routeFrom} -> ${routeTo}` : "-";
      const speedValue = Number(props.speed_mps);
      const speedText = Number.isFinite(speedValue) ? `${speedValue.toFixed(0)} m/s` : "-";
      const batteryValue = Number(props.battery_pct);
      const batteryText = Number.isFinite(batteryValue) ? `${batteryValue.toFixed(0)}%` : "-";
      setField("name", name);
      setField("from", from);
      setField("to", to);
      setField("route", routeText);
      setField("speed", speedText);
      setField("battery", batteryText);
    },

    getTrafficPopupAnchor(lngLat) {
      if (!this.map || !this.map.project || !lngLat) {
        return "right";
      }
      const canvas = this.map.getCanvas ? this.map.getCanvas() : null;
      const width = canvas ? canvas.clientWidth || canvas.width : 0;
      if (!width) {
        return "right";
      }
      const point = this.map.project(lngLat);
      if (!point || !Number.isFinite(point.x)) {
        return "right";
      }
      return point.x > width * 0.55 ? "left" : "right";
    },

    getTrafficPopupOffset(anchor) {
      const offsetX = 40 * MAP_SIZE_SCALE;
      const pitch = this.map && this.map.getPitch ? this.map.getPitch() : 0;
      const offsetY = pitch > TRAFFIC_2D_MAX_PITCH ? -28 : -22;
      if (anchor === "left") {
        return [offsetX, offsetY];
      }
      if (anchor === "right") {
        return [-offsetX, offsetY];
      }
      return [0, offsetY];
    },

    mercatorToLngLat(x, y) {
      const lon = x * 360 - 180;
      const lat = (180 / Math.PI) * Math.atan(Math.sinh(Math.PI * (1 - 2 * y)));
      return [lon, lat];
    },

    getTrafficLaneOffsetMeters() {
      return 0;
    },

    getRouteOffsetVector(routeFrom, routeTo, offsetMeters) {
      if (!offsetMeters || !routeFrom || !routeTo || !this.routeNodeLookup) {
        return null;
      }
      const start = this.routeNodeLookup.get(routeFrom);
      const end = this.routeNodeLookup.get(routeTo);
      if (
        !start ||
        !end ||
        !Array.isArray(start.coord) ||
        !Array.isArray(end.coord) ||
        start.coord.length < 2 ||
        end.coord.length < 2
      ) {
        return null;
      }
      const startMerc = maplibregl.MercatorCoordinate.fromLngLat(start.coord);
      const endMerc = maplibregl.MercatorCoordinate.fromLngLat(end.coord);
      const midLon = (start.coord[0] + end.coord[0]) / 2;
      const midLat = (start.coord[1] + end.coord[1]) / 2;
      const unitsPerMeter = this.getMercatorUnitsPerMeter(midLon, midLat);
      if (!Number.isFinite(unitsPerMeter) || unitsPerMeter <= 0) {
        return null;
      }
      const offsetUnits = offsetMeters * unitsPerMeter;
      const dx = endMerc.x - startMerc.x;
      const dy = endMerc.y - startMerc.y;
      const len = Math.hypot(dx, dy);
      if (!Number.isFinite(len) || len === 0) {
        return null;
      }
      const px = -dy / len;
      const py = dx / len;
      return { x: px * offsetUnits, y: py * offsetUnits };
    },

    getHeadingOffsetVector(headingDeg, lon, lat, offsetMeters) {
      if (!offsetMeters || !Number.isFinite(headingDeg)) {
        return null;
      }
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return null;
      }
      const unitsPerMeter = this.getMercatorUnitsPerMeter(lon, lat);
      if (!Number.isFinite(unitsPerMeter) || unitsPerMeter <= 0) {
        return null;
      }
      const headingRad = (headingDeg * Math.PI) / 180;
      const dx = Math.sin(headingRad);
      const dy = Math.cos(headingRad);
      const px = -dy;
      const py = dx;
      const offsetUnits = offsetMeters * unitsPerMeter;
      return { x: px * offsetUnits, y: py * offsetUnits };
    },

    offsetLngLatByVector(lngLat, altitude, offsetVec) {
      const mercator = maplibregl.MercatorCoordinate.fromLngLat(lngLat, altitude);
      if (!offsetVec) {
        return { lngLat, mercator };
      }
      mercator.x += offsetVec.x;
      mercator.y += offsetVec.y;
      const [lon, lat] = this.mercatorToLngLat(mercator.x, mercator.y);
      return { lngLat: [lon, lat], mercator };
    },

    offsetCoordsByPath(coords, offsetMeters) {
      if (!offsetMeters || !Array.isArray(coords) || coords.length < 2) {
        return coords;
      }
      const mercators = coords.map((coord) => {
        const lon = Number(coord[0]);
        const lat = Number(coord[1]);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          return null;
        }
        return maplibregl.MercatorCoordinate.fromLngLat([lon, lat]);
      });
      const output = [];
      for (let i = 0; i < coords.length; i += 1) {
        const current = mercators[i];
        if (!current) {
          output.push(coords[i]);
          continue;
        }
        const prev = mercators[i - 1] || current;
        const next = mercators[i + 1] || current;
        const dx = next.x - prev.x;
        const dy = next.y - prev.y;
        const len = Math.hypot(dx, dy);
        if (!Number.isFinite(len) || len === 0) {
          output.push(coords[i]);
          continue;
        }
        const lon = Number(coords[i][0]);
        const lat = Number(coords[i][1]);
        const unitsPerMeter = this.getMercatorUnitsPerMeter(lon, lat);
        if (!Number.isFinite(unitsPerMeter) || unitsPerMeter <= 0) {
          output.push(coords[i]);
          continue;
        }
        const offsetUnits = offsetMeters * unitsPerMeter;
        const px = -dy / len;
        const py = dx / len;
        const x = current.x + px * offsetUnits;
        const y = current.y + py * offsetUnits;
        output.push(this.mercatorToLngLat(x, y));
      }
      return output;
    },

    offsetCoordsByVector(coords, offsetVec) {
      if (!offsetVec || !Array.isArray(coords) || coords.length < 2) {
        return coords;
      }
      return coords.map((coord) => {
        const lon = Number(coord[0]);
        const lat = Number(coord[1]);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
          return coord;
        }
        const merc = maplibregl.MercatorCoordinate.fromLngLat([lon, lat]);
        merc.x += offsetVec.x;
        merc.y += offsetVec.y;
        return this.mercatorToLngLat(merc.x, merc.y);
      });
    },

    focusTrafficByName(name) {
      if (!this.map) {
        return;
      }
      const key = name ? String(name) : "";
      if (!key) {
        return;
      }
      const entry = this.trafficByName.get(key);
      if (!entry || !entry.coords || entry.coords.length < 2) {
        return;
      }
      const [lon, lat] = entry.coords;
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return;
      }
      this.map.easeTo({
        center: [lon, lat],
        duration: 900,
      });
      if (entry.id != null) {
        this.setTrafficSelectedState(entry.id);
      }
      if (entry.props) {
        this.showTrafficPopup(entry.props, [lon, lat], entry.id);
      }
      this.notifyFlightSelection(key);
    },

    applyTrafficPositions(positions) {
      if (!this.map || !this.map.isStyleLoaded()) {
        this.pendingTrafficPositions = positions;
        return;
      }
      this.pendingTrafficPositions = null;
      const nextPositions = new Map();
      const traffic3dEntries = [];
      const byName = new Map();
      const byId = new Map();
      const altitudeById = new Map();
      const laneOffsetMeters = this.getTrafficLaneOffsetMeters();
      positions.forEach((pos, index) => {
        const rawLon = Number(pos.lon);
        const rawLat = Number(pos.lat);
        if (!Number.isFinite(rawLon) || !Number.isFinite(rawLat)) {
          return;
        }
        const icon = pos.icon ? String(pos.icon) : "";
        const speed = Number(pos.speed_mps);
        const targetSpeed = Number(pos.speed_target_mps);
        const battery = Number(pos.battery_pct);
        const lateralDev = Number(pos.lateral_dev_m);
        const std_s = Number(pos.std_s);
        const sta_s = Number(pos.sta_s);
        const eta_s = Number(pos.eta_s);
        const ata_s = Number(pos.ata_s);
        const delay_s = Number(pos.delay_s);
        const tti = Number(pos.tti);
        const riskLevel = this.coerceRiskLevel(pos.risk_level ?? pos.risk);
        const riskLabelRaw = pos.risk != null ? String(pos.risk).trim() : "";
        const riskLabel = riskLabelRaw ? riskLabelRaw : String(riskLevel);
        const altitude = this.resolveAltitudeValue(pos);
        const altitude_m_raw = Number.isFinite(altitude) ? altitude : null;
        const altitude_m = Number.isFinite(altitude) ? altitude : FLIGHT_ALT_M;
        const altitude_visual_m = toTrafficAltitude(altitude_m);
        const featureId = pos.id != null ? pos.id : index;
        altitudeById.set(featureId, altitude_m);
        const previous = this.trafficLastPositions.get(featureId);
        const headingFromData = Number(pos.heading_deg);
        let heading = Number.isFinite(headingFromData) ? headingFromData : 0;
        if (!Number.isFinite(headingFromData)) {
          if (previous && Number.isFinite(previous.lon) && Number.isFinite(previous.lat)) {
            if (
              Number.isFinite(previous.heading) &&
              previous.lon === rawLon &&
              previous.lat === rawLat
            ) {
              heading = previous.heading;
            } else {
              heading = computeBearing(previous.lon, previous.lat, rawLon, rawLat);
            }
          }
        }
        nextPositions.set(featureId, { lon: rawLon, lat: rawLat, heading });
        const routeFrom = pos.route_from ? String(pos.route_from) : "";
        const routeTo = pos.route_to ? String(pos.route_to) : "";
        const props = {
          icon,
          name: pos.name ? String(pos.name) : "",
          from: pos.from ? String(pos.from) : "",
          to: pos.to ? String(pos.to) : "",
          route_from: routeFrom,
          route_to: routeTo,
          risk: riskLabel,
          risk_level: riskLevel,
          risk_reason: pos.risk_reason != null ? String(pos.risk_reason) : "",
          speed_mps: Number.isFinite(speed) ? speed : null,
          speed_target_mps: Number.isFinite(targetSpeed) ? targetSpeed : null,
          lateral_dev_m: Number.isFinite(lateralDev) ? lateralDev : null,
          battery_pct: Number.isFinite(battery) ? battery : null,
          std_s: Number.isFinite(std_s) ? std_s : null,
          sta_s: Number.isFinite(sta_s) ? sta_s : null,
          eta_s: Number.isFinite(eta_s) ? eta_s : null,
          ata_s: Number.isFinite(ata_s) ? ata_s : null,
          delay_s: Number.isFinite(delay_s) ? delay_s : null,
          tti: Number.isFinite(tti) ? tti : null,
          altitude_m,
          altitude_m_raw,
          mode: pos.mode ? String(pos.mode) : "",
          predict_path: Array.isArray(pos.predict_path) ? pos.predict_path : null,
          hold_path: Array.isArray(pos.hold_path) ? pos.hold_path : null,
          heading,
        };
        const congestionMap =
          this.congestionScoreById instanceof Map ? this.congestionScoreById : null;
        if (congestionMap) {
          const numericId = Number(featureId);
          const score = congestionMap.get(Number.isFinite(numericId) ? numericId : featureId);
          if (Number.isFinite(score)) {
            props.congestion_score = score;
          }
        }
        let displayLon = rawLon;
        let displayLat = rawLat;
        let mercator = null;
        if (laneOffsetMeters > 0) {
          let offsetVec = null;
          if (routeFrom && routeTo) {
            offsetVec = this.getRouteOffsetVector(routeFrom, routeTo, laneOffsetMeters);
          }
          if (!offsetVec) {
            offsetVec = this.getHeadingOffsetVector(
              heading,
              rawLon,
              rawLat,
              laneOffsetMeters,
            );
          }
          if (offsetVec) {
            const offsetResult = this.offsetLngLatByVector(
              [rawLon, rawLat],
              altitude_visual_m,
              offsetVec,
            );
            displayLon = offsetResult.lngLat[0];
            displayLat = offsetResult.lngLat[1];
            mercator = offsetResult.mercator;
          }
        }
        if (!mercator) {
          mercator = maplibregl.MercatorCoordinate.fromLngLat(
            [displayLon, displayLat],
            altitude_visual_m,
          );
        }
        if (props.name) {
          byName.set(props.name, {
            id: featureId,
            props,
            coords: [displayLon, displayLat],
            rawCoords: [rawLon, rawLat],
          });
        }
        if (featureId != null) {
          byId.set(featureId, {
            id: featureId,
            props,
            coords: [displayLon, displayLat],
            rawCoords: [rawLon, rawLat],
          });
        }
        traffic3dEntries.push({
          id: featureId,
          lon: displayLon,
          lat: displayLat,
          altitude_m,
          heading,
          icon,
          mercator,
          risk: riskLabel,
          risk_level: riskLevel,
        });
      });
      this.trafficLastPositions = nextPositions;
      this.trafficAltitudeById = altitudeById;
      this.lastTraffic3dEntries = traffic3dEntries;
      if (this.trafficSelectedId != null && !nextPositions.has(this.trafficSelectedId)) {
        this.trafficSelectedId = null;
        this.hideTrafficPopup();
        this.hideTrafficNamePopup();
      }
      this.trafficByName = byName;
      this.trafficById = byId;
      if (this.trafficSelectedId != null) {
        const selectedEntry = byId.get(this.trafficSelectedId);
        const selectedName =
          selectedEntry && selectedEntry.props ? selectedEntry.props.name : "";
        if (selectedName && selectedName !== this.trafficHistoryName) {
          this.resetTrafficHistoryByName(selectedName);
        }
      }
      if (this.trafficPopup) {
        const popupEntry = this.resolveTrafficPopupEntry();
        if (popupEntry && popupEntry.props) {
          this.updateTrafficPopupContent(popupEntry.props, popupEntry);
        }
      }
      if (this.trafficNamePopupId != null || this.trafficNamePopupName) {
        const popupEntry = this.resolveTrafficEntryByKey(
          this.trafficNamePopupId,
          this.trafficNamePopupName,
        );
        if (popupEntry && popupEntry.props) {
          this.updateTrafficNamePopupContent(popupEntry.props);
        }
      }
      this.syncTrafficPopupPosition();
      this.syncTrafficNamePopupPosition();
      this.updateTraffic3dLayer(traffic3dEntries);
      this.updateTraffic3dIconLayer(traffic3dEntries);
      this.updateTraffic2dLayer(traffic3dEntries);
      this.updateTrafficPrediction();
      this.appendTrafficHistory();
      this.scheduleMapRepaint();
      this.updateTrafficLayerVisibility();
      this.setupTrafficInteractions();
      this.updateDashboardFromPositions(positions);
    },

    updateTrafficPositions(positions) {
      if (!Array.isArray(positions)) {
        return;
      }
      this.pendingTrafficPositions = positions;
      if (this.trafficUpdateScheduled) {
        return;
      }
      this.trafficUpdateScheduled = true;
      requestAnimationFrame(() => {
        this.trafficUpdateScheduled = false;
        const pending = this.pendingTrafficPositions;
        if (!pending) {
          return;
        }
        this.pendingTrafficPositions = null;
        this.applyTrafficPositions(pending);
      });
    }

});

