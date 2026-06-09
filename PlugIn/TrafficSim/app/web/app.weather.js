(() => {
  const WEATHER_STEP_METERS = 100;
  const WEATHER_MAX_POINTS = 5200;
  const WEATHER_DRAW_MIN_MS = 120;
  const WEATHER_TIME_SPEED = 60.0;
  const WEATHER_DEFAULT_PRESET = "good";
  const WEATHER_TRANSITION_TAU = 2.2;
  const WEATHER_LOCAL_FADE_TAU = 2.0;
  const WEATHER_LOCAL_RADIUS_M = 1200;
  const WEATHER_PRESETS = ["good", "fair", "bad", "serious"];

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const lerp = (a, b, t) => a + (b - a) * t;

  const normalizeWindPreset = (value) => {
    const preset = String(value || "").toLowerCase();
    if (WEATHER_PRESETS.includes(preset)) {
      return preset;
    }
    return WEATHER_DEFAULT_PRESET;
  };

  const formatDistance = (meters) => {
    const value = Number(meters);
    if (!Number.isFinite(value)) {
      return "0 m";
    }
    if (value >= 1000) {
      return `${(value / 1000).toFixed(1)} km`;
    }
    return `${Math.round(value)} m`;
  };

  const formatPresetLabel = (preset) => {
    const value = normalizeWindPreset(preset);
    return value.charAt(0).toUpperCase() + value.slice(1);
  };

  const R = 6378137.0;
  const DEG2RAD = Math.PI / 180.0;
  const RAD2DEG = 180.0 / Math.PI;

  const lonToX = (lon) => R * lon * DEG2RAD;
  const latToY = (lat) => {
    const rad = lat * DEG2RAD;
    return R * Math.log(Math.tan(Math.PI / 4 + rad / 2));
  };
  const xToLon = (x) => (x / R) * RAD2DEG;
  const yToLat = (y) =>
    (2 * Math.atan(Math.exp(y / R)) - Math.PI / 2) * RAD2DEG;

  const radiusMetersToPixels = (map, lngLat, meters) => {
    if (!map || !lngLat || !Number.isFinite(meters)) {
      return 0;
    }
    const latRad = lngLat.lat * DEG2RAD;
    const dLng = (meters / (R * Math.cos(latRad))) * RAD2DEG;
    const p1 = map.project([lngLat.lng, lngLat.lat]);
    const p2 = map.project([lngLat.lng + dLng, lngLat.lat]);
    return Math.max(2, Math.abs(p2.x - p1.x));
  };

  const mulberry32 = (seed) => {
    let a = seed >>> 0;
    return () => {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };

  class Perlin3 {
    constructor(seed = 1337) {
      const rand = mulberry32(seed);
      const p = new Uint8Array(256);
      for (let i = 0; i < 256; i += 1) {
        p[i] = i;
      }

      for (let i = 255; i > 0; i -= 1) {
        const j = Math.floor(rand() * (i + 1));
        const tmp = p[i];
        p[i] = p[j];
        p[j] = tmp;
      }

      this.perm = new Uint8Array(512);
      for (let i = 0; i < 512; i += 1) {
        this.perm[i] = p[i & 255];
      }
    }

    fade(t) {
      return t * t * t * (t * (t * 6 - 15) + 10);
    }

    lerp(a, b, t) {
      return a + t * (b - a);
    }

    grad(hash, x, y, z) {
      const h = hash & 15;
      const u = h < 8 ? x : y;
      const v = h < 4 ? y : h === 12 || h === 14 ? x : z;
      const a = (h & 1) === 0 ? u : -u;
      const b = (h & 2) === 0 ? v : -v;
      return a + b;
    }

    noise(x, y, z) {
      const X = Math.floor(x) & 255;
      const Y = Math.floor(y) & 255;
      const Z = Math.floor(z) & 255;

      const xf = x - Math.floor(x);
      const yf = y - Math.floor(y);
      const zf = z - Math.floor(z);

      const u = this.fade(xf);
      const v = this.fade(yf);
      const w = this.fade(zf);

      const A = this.perm[X] + Y;
      const AA = this.perm[A] + Z;
      const AB = this.perm[A + 1] + Z;
      const B = this.perm[X + 1] + Y;
      const BA = this.perm[B] + Z;
      const BB = this.perm[B + 1] + Z;

      const x1 = this.lerp(
        this.grad(this.perm[AA], xf, yf, zf),
        this.grad(this.perm[BA], xf - 1, yf, zf),
        u,
      );
      const x2 = this.lerp(
        this.grad(this.perm[AB], xf, yf - 1, zf),
        this.grad(this.perm[BB], xf - 1, yf - 1, zf),
        u,
      );
      const y1 = this.lerp(x1, x2, v);

      const x3 = this.lerp(
        this.grad(this.perm[AA + 1], xf, yf, zf - 1),
        this.grad(this.perm[BA + 1], xf - 1, yf, zf - 1),
        u,
      );
      const x4 = this.lerp(
        this.grad(this.perm[AB + 1], xf, yf - 1, zf - 1),
        this.grad(this.perm[BB + 1], xf - 1, yf - 1, zf - 1),
        u,
      );
      const y2 = this.lerp(x3, x4, v);

      return this.lerp(y1, y2, w);
    }
  }

  const fbm = (perlin, x, y, z, octaves = 4, lacunarity = 2.0, gain = 0.5) => {
    let amp = 0.5;
    let freq = 1.0;
    let sum = 0.0;
    let norm = 0.0;
    for (let i = 0; i < octaves; i += 1) {
      sum += amp * perlin.noise(x * freq, y * freq, z * freq);
      norm += amp;
      amp *= gain;
      freq *= lacunarity;
    }
    return sum / Math.max(1e-9, norm);
  };

  class WindModel {
    constructor(opts = {}) {
      this.seed = opts.seed ?? 20260121;
      this.perlin = new Perlin3(this.seed);
      this.timeSpeed = opts.timeSpeed ?? WEATHER_TIME_SPEED;
      this.preset = normalizeWindPreset(opts.preset);
      this.baseSeverity = 0.25;
      this.baseSeverityTarget = this.baseSeverity;
      this.rangeMin = 1.0;
      this.rangeMax = 3.0;
      this.rangeMinTarget = this.rangeMin;
      this.rangeMaxTarget = this.rangeMax;
      this.transitionTau = Number.isFinite(opts.transitionTau)
        ? Math.max(0.1, opts.transitionTau)
        : WEATHER_TRANSITION_TAU;
      this.localZones = [];
      this.localFadeTau = Number.isFinite(opts.localFadeTau)
        ? Math.max(0.1, opts.localFadeTau)
        : WEATHER_LOCAL_FADE_TAU;
      this.setPreset(this.preset);

      const now = new Date();
      this.startRealS = performance.now() / 1000.0;
      this.lastTransitionRealS = this.startRealS;
      this.lastLocalUpdateRealS = this.startRealS;
      this.startLocalHour =
        now.getHours() + now.getMinutes() / 60.0 + now.getSeconds() / 3600.0;

      this.riverY = latToY(37.53);
    }

    setTimeSpeed(newSpeed, realS) {
      const nowRealS = realS ?? performance.now() / 1000.0;
      const simS = (nowRealS - this.startRealS) * this.timeSpeed;
      this.timeSpeed = Math.max(0.1, newSpeed);
      this.startRealS = nowRealS - simS / this.timeSpeed;
    }

    presetConfig(preset) {
      if (preset === "good") return { base: 0.25, min: 1, max: 3 };
      if (preset === "fair") return { base: 0.52, min: 1, max: 5 };
      if (preset === "bad") return { base: 0.78, min: 3, max: 10 };
      if (preset === "serious") return { base: 0.9, min: 5, max: 12 };
      return { base: 0.52, min: 1, max: 5 };
    }

    localPresetConfig(preset) {
      const baseConfig = this.presetConfig(preset);
      if (preset === "bad") {
        return {
          base: Math.min(1.0, baseConfig.base + 0.12),
          min: baseConfig.min + 2,
          max: baseConfig.max + 3,
        };
      }
      if (preset === "serious") {
        return {
          base: Math.min(1.0, baseConfig.base + 0.1),
          min: baseConfig.min + 3,
          max: Math.min(15, baseConfig.max + 4),
        };
      }
      return baseConfig;
    }

    setPreset(preset) {
      const next = normalizeWindPreset(preset);
      this.preset = next;
      const config = this.presetConfig(next);
      this.baseSeverityTarget = config.base;
      this.rangeMinTarget = config.min;
      this.rangeMaxTarget = config.max;
    }

    speedRange() {
      return { min: this.rangeMin, max: this.rangeMax };
    }

    setTransitionTau(tau) {
      if (Number.isFinite(tau) && tau > 0) {
        this.transitionTau = tau;
      }
    }

    setLocalFadeTau(tau) {
      if (Number.isFinite(tau) && tau > 0) {
        this.localFadeTau = tau;
      }
    }

    _updateTransitions(realS) {
      const nowRealS = Number.isFinite(realS)
        ? realS
        : performance.now() / 1000.0;
      const dt = Math.max(0, nowRealS - this.lastTransitionRealS);
      this.lastTransitionRealS = nowRealS;
      const alpha = 1 - Math.exp(-dt / Math.max(0.1, this.transitionTau));
      this.baseSeverity += (this.baseSeverityTarget - this.baseSeverity) * alpha;
      this.rangeMin += (this.rangeMinTarget - this.rangeMin) * alpha;
      this.rangeMax += (this.rangeMaxTarget - this.rangeMax) * alpha;
    }

    _updateLocalZones(realS) {
      const nowRealS = Number.isFinite(realS)
        ? realS
        : performance.now() / 1000.0;
      const dt = Math.max(0, nowRealS - this.lastLocalUpdateRealS);
      this.lastLocalUpdateRealS = nowRealS;
      const alpha = 1 - Math.exp(-dt / Math.max(0.1, this.localFadeTau));
      for (let i = this.localZones.length - 1; i >= 0; i -= 1) {
        const zone = this.localZones[i];
        zone.strength += (zone.targetStrength - zone.strength) * alpha;
        if (zone.targetStrength === 0 && zone.strength < 0.02) {
          this.localZones.splice(i, 1);
        }
      }
    }

    addLocalZone(xm, ym, radiusM, preset) {
      if (!Number.isFinite(radiusM) || radiusM <= 0) {
        return;
      }
      const config = this.localPresetConfig(normalizeWindPreset(preset));
      this.localZones.push({
        xm,
        ym,
        radiusM,
        baseSeverity: config.base,
        minSpeed: config.min,
        maxSpeed: config.max,
        strength: 0,
        targetStrength: 1,
      });
    }

    clearLocalZones() {
      this.localZones.forEach((zone) => {
        zone.targetStrength = 0;
      });
    }

    localConfigAt(xm, ym, simS, realS) {
      this._updateTransitions(realS);
      this._updateLocalZones(realS);
      let base = this.baseSeverity;
      let minSpeed = this.rangeMin;
      let maxSpeed = this.rangeMax;
      if (!this.localZones.length) {
        return { base, minSpeed, maxSpeed };
      }
      let totalW = 0;
      let baseSum = 0;
      let minSum = 0;
      let maxSum = 0;
      this.localZones.forEach((zone) => {
        const dx = xm - zone.xm;
        const dy = ym - zone.ym;
        const dist = Math.hypot(dx, dy);
        if (dist >= zone.radiusM) {
          return;
        }
        const t = clamp(1 - dist / zone.radiusM, 0, 1);
        const smooth = t * t * (3 - 2 * t);
        const w = smooth * zone.strength;
        if (w <= 0) {
          return;
        }
        totalW += w;
        baseSum += w * zone.baseSeverity;
        minSum += w * zone.minSpeed;
        maxSum += w * zone.maxSpeed;
      });
      if (totalW > 0) {
        const denom = 1 + totalW;
        base = (base + baseSum) / denom;
        minSpeed = (minSpeed + minSum) / denom;
        maxSpeed = (maxSpeed + maxSum) / denom;
      }
      return { base, minSpeed, maxSpeed };
    }

    seasonalBase(monthIndex0to11) {
      const m = monthIndex0to11 + 1;
      if (m === 12 || m === 1 || m === 2) return { dirToDeg: 135, speedMean: 6.0 };
      if (m >= 3 && m <= 5) return { dirToDeg: 95, speedMean: 4.6 };
      if (m >= 6 && m <= 8) return { dirToDeg: 10, speedMean: 3.8 };
      return { dirToDeg: 125, speedMean: 5.2 };
    }

    diurnalFactor(localHour0to24) {
      const x = (localHour0to24 - 14.0) / 24.0 * (2 * Math.PI);
      return 0.85 + 0.25 * Math.cos(x);
    }

    severity(simS) {
      const base = this.baseSeverity;
      const slow = fbm(this.perlin, 0.0, 0.0, simS * 0.00008, 4, 2.0, 0.5);
      const mid = this.perlin.noise(120.5, -77.3, simS * 0.00025);
      const pulse = Math.sin(simS * (2 * Math.PI) / (60.0 * 35.0));
      return clamp(base + 0.22 * slow + 0.1 * mid + 0.08 * pulse, 0.0, 1.0);
    }

    psi(xm, ym, simS, scale, tScale, octaves) {
      return fbm(this.perlin, xm * scale, ym * scale, simS * tScale, octaves, 2.0, 0.5);
    }

    perpGrad(xm, ym, simS, scale, tScale, octaves, deltaM) {
      const pN = this.psi(xm, ym + deltaM, simS, scale, tScale, octaves);
      const pS = this.psi(xm, ym - deltaM, simS, scale, tScale, octaves);
      const pE = this.psi(xm + deltaM, ym, simS, scale, tScale, octaves);
      const pW = this.psi(xm - deltaM, ym, simS, scale, tScale, octaves);

      const dPsi_dy = (pN - pS) / (2 * deltaM);
      const dPsi_dx = (pE - pW) / (2 * deltaM);

      return { u: dPsi_dy, v: -dPsi_dx };
    }

    windAtMercator(xm, ym, realS) {
      const simS = (realS - this.startRealS) * this.timeSpeed;

      const now = new Date();
      const month = now.getMonth();
      const base = this.seasonalBase(month);

      const localHour = (this.startLocalHour + simS / 3600.0) % 24.0;
      const mix = this.diurnalFactor(localHour);

      const localConfig = this.localConfigAt(xm, ym, simS, realS);
      let sev = this.severity(simS);
      sev = clamp(localConfig.base + (sev - this.baseSeverity), 0.0, 1.0);
      const range = { min: localConfig.minSpeed, max: localConfig.maxSpeed };

      const dirJitterDeg =
        (12.0 + 30.0 * sev) * this.perlin.noise(55.1, 9.7, simS * 0.0004);
      const spaceJitter =
        10.0 * fbm(this.perlin, xm * (1 / 18000), ym * (1 / 18000), simS * 0.00018, 3, 2.0, 0.5);

      const dirToDeg = base.dirToDeg + dirJitterDeg + spaceJitter;

      const meanBase = base.speedMean * (0.70 + 0.95 * sev) * mix;
      const meanTarget = lerp(range.min, range.max, sev) * mix;
      const speedScale = meanTarget / Math.max(0.1, meanBase);
      const mean = meanBase * speedScale;

      const band =
        (0.6 + 2.4 * sev) *
        fbm(this.perlin, xm * (1 / 12000), ym * (1 / 12000), simS * 0.00022, 3, 2.0, 0.5) *
        speedScale;

      const speed0 = Math.max(0.1, mean + band);

      const rad = dirToDeg * DEG2RAD;
      let u = Math.sin(rad) * speed0;
      let v = Math.cos(rad) * speed0;

      const g1 = this.perpGrad(xm, ym, simS, 1 / 4200, 0.00018, 4, 80);
      const amp1 = lerp(1800, 9000, sev) * speedScale;
      u += g1.u * amp1;
      v += g1.v * amp1;

      const g2 = this.perpGrad(xm, ym, simS, 1 / 1100, 0.00055, 3, 45);
      const amp2 = lerp(500, 2600, sev) * (0.7 + 0.6 * mix) * speedScale;
      u += g2.u * amp2;
      v += g2.v * amp2;

      const sp = Math.hypot(u, v);
      const ux = u / Math.max(1e-6, sp);
      const vx = v / Math.max(1e-6, sp);

      const gust = this.perlin.noise(xm * (1 / 350), ym * (1 / 350), simS * 0.0016);
      const gustAmp = lerp(0.4, 3.8, sev) * speedScale;
      u += ux * gust * gustAmp;
      v += vx * gust * gustAmp;

      const dy = ym - this.riverY;
      const riverFactor = Math.exp(-Math.pow(dy / 1200.0, 2));
      const riverAmp = lerp(0.0, 1.8, sev) * speedScale;
      const eastSign = Math.sin(rad) >= 0 ? 1.0 : -1.0;
      u += riverFactor * riverAmp * eastSign;

      const maxSpeed = lerp(18.0, 35.0, sev) * speedScale;
      const sFinal = Math.hypot(u, v);
      if (sFinal > maxSpeed) {
        const k = maxSpeed / Math.max(1e-6, sFinal);
        u *= k;
        v *= k;
      }

      return {
        u,
        v,
        speed: Math.hypot(u, v),
      };
    }
  }

  const speedToColor = (speed) => {
    const s = clamp(speed, 0, 15);
    const hue = 210 - (210 * (s / 15));
    return `hsla(${hue.toFixed(1)}, 90%, 50%, 0.50)`;
  };

  const drawArrow = (ctx, x, y, dx, dy, color) => {
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + dx, y + dy);
    ctx.stroke();

    const ang = Math.atan2(dy, dx);
    const head = 4.6;
    const a1 = ang - Math.PI / 6;
    const a2 = ang + Math.PI / 6;

    ctx.beginPath();
    ctx.moveTo(x + dx, y + dy);
    ctx.lineTo(x + dx - head * Math.cos(a1), y + dy - head * Math.sin(a1));
    ctx.lineTo(x + dx - head * Math.cos(a2), y + dy - head * Math.sin(a2));
    ctx.closePath();
    ctx.fill();
  };

  class WeatherLayer {
    constructor(map, model, options = {}) {
      this._map = map;
      this._model = model;
      this._options = options;

      this._canvas = null;
      this._ctx = null;
      this._running = false;
      this._raf = null;
      this._points = [];
      this._activeStep = options.stepMeters ?? WEATHER_STEP_METERS;
      this._lastDrawMs = 0;
      this._width = 0;
      this._height = 0;
      this._minDrawMs = options.minDrawMs ?? WEATHER_DRAW_MIN_MS;
      this._maxPoints = options.maxPoints ?? WEATHER_MAX_POINTS;
      this._isFading = false;

      this._onMapChange = this._onMapChange.bind(this);
      this._onMapStart = this._onMapStart.bind(this);
      this._loop = this._loop.bind(this);
    }

    start() {
      if (this._running || !this._map) {
        return;
      }
      this._running = true;
      this._ensureCanvas();
      if (this._canvas) {
        this._canvas.style.display = "block";
      }
      this._resetCanvas();
      this._rebuildGrid();
      this._lastDrawMs = 0;

      this._map.on("movestart", this._onMapStart);
      this._map.on("zoomstart", this._onMapStart);
      this._map.on("rotatestart", this._onMapStart);
      this._map.on("pitchstart", this._onMapStart);
      this._map.on("moveend", this._onMapChange);
      this._map.on("zoomend", this._onMapChange);
      this._map.on("rotateend", this._onMapChange);
      this._map.on("pitchend", this._onMapChange);
      this._map.on("resize", this._onMapChange);

      this._loop();
    }

    stop() {
      this._running = false;
      if (this._raf) {
        cancelAnimationFrame(this._raf);
        this._raf = null;
      }

      if (this._map) {
        this._map.off("movestart", this._onMapStart);
        this._map.off("zoomstart", this._onMapStart);
        this._map.off("rotatestart", this._onMapStart);
        this._map.off("pitchstart", this._onMapStart);
        this._map.off("moveend", this._onMapChange);
        this._map.off("zoomend", this._onMapChange);
        this._map.off("rotateend", this._onMapChange);
        this._map.off("pitchend", this._onMapChange);
        this._map.off("resize", this._onMapChange);
      }

      if (this._ctx && this._canvas) {
        this._ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);
      }

      if (this._canvas && this._canvas.parentNode) {
        this._canvas.parentNode.removeChild(this._canvas);
      }

      this._canvas = null;
      this._ctx = null;
      this._points = [];
    }

    prepare() {
      if (!this._map) {
        return;
      }
      this._ensureCanvas();
      if (this._canvas) {
        this._canvas.style.display = "none";
        this._canvas.classList.remove("is-fading");
      }
      this._resetCanvas();
      this._rebuildGrid();
      this._lastDrawMs = 0;
    }

    _ensureCanvas() {
      if (this._canvas) {
        return;
      }
      const canvas = document.createElement("canvas");
      canvas.className = "weather-canvas";
      this._canvas = canvas;
      this._ctx = canvas.getContext("2d");
      const container = this._map.getContainer();
      container.appendChild(canvas);
    }

    _resetCanvas() {
      if (!this._canvas || !this._ctx) {
        return;
      }
      const container = this._map.getContainer();
      const width = container.clientWidth;
      const height = container.clientHeight;
      const dpr = window.devicePixelRatio || 1;

      this._canvas.style.width = `${width}px`;
      this._canvas.style.height = `${height}px`;
      this._canvas.width = Math.floor(width * dpr);
      this._canvas.height = Math.floor(height * dpr);
      this._ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      this._width = width;
      this._height = height;
    }

    _onMapChange() {
      this._resetCanvas();
      this._rebuildGrid();
      this._lastDrawMs = 0;
      this._setFading(false);
    }

    _onMapStart() {
      this._setFading(true);
    }

    _setFading(next) {
      if (!this._canvas) {
        this._isFading = Boolean(next);
        return;
      }
      const value = Boolean(next);
      this._isFading = value;
      this._canvas.classList.toggle("is-fading", value);
    }

    _rebuildGrid() {
      if (!this._map) {
        return;
      }
      const bounds = this._map.getBounds();
      const ne = bounds.getNorthEast();
      const sw = bounds.getSouthWest();

      const xMin = lonToX(sw.lng);
      const xMax = lonToX(ne.lng);
      const yMin = latToY(sw.lat);
      const yMax = latToY(ne.lat);

      if (
        !Number.isFinite(xMin) ||
        !Number.isFinite(xMax) ||
        !Number.isFinite(yMin) ||
        !Number.isFinite(yMax)
      ) {
        this._points = [];
        return;
      }

      const width = Math.max(1.0, xMax - xMin);
      const height = Math.max(1.0, yMax - yMin);

      let step = this._options.stepMeters ?? WEATHER_STEP_METERS;
      const nx = Math.ceil(width / step) + 1;
      const ny = Math.ceil(height / step) + 1;
      const count = nx * ny;

      if (count > this._maxPoints) {
        const area = width * height;
        const suggested = Math.sqrt(area / this._maxPoints);
        step = Math.max(step, suggested);
      }

      this._activeStep = step;

      const x0 = Math.floor(xMin / step) * step;
      const y0 = Math.floor(yMin / step) * step;
      const pts = [];

      for (let x = x0; x <= xMax; x += step) {
        for (let y = y0; y <= yMax; y += step) {
          const lat = yToLat(y);
          const lon = xToLon(x);
          pts.push({ xm: x, ym: y, lat, lon });
        }
      }

      this._points = pts;
    }

    _loop() {
      if (!this._running) {
        return;
      }
      const now = performance.now();
      if (now - this._lastDrawMs >= this._minDrawMs) {
        this._drawFrame();
        this._lastDrawMs = now;
      }
      this._raf = requestAnimationFrame(this._loop);
    }

    _drawFrame() {
      if (!this._ctx || !this._map || this._isFading) {
        return;
      }
      if (
        typeof this._map.isStyleLoaded === "function" &&
        !this._map.isStyleLoaded()
      ) {
        return;
      }
      if (this._width <= 0 || this._height <= 0) {
        this._resetCanvas();
      }
      if (!this._points.length) {
        this._rebuildGrid();
        if (!this._points.length) {
          return;
        }
      }
      const ctx = this._ctx;
      ctx.clearRect(0, 0, this._width, this._height);
      const realS = performance.now() / 1000.0;
      const points = this._points;

      for (let i = 0; i < points.length; i += 1) {
        const p = points[i];
        const pt = this._map.project([p.lon, p.lat]);
        if (pt.x < -40 || pt.y < -40 || pt.x > this._width + 40 || pt.y > this._height + 40) {
          continue;
        }
        const w = this._model.windAtMercator(p.xm, p.ym, realS);
        const sp = w.speed;
        if (sp < 0.2) {
          continue;
        }
        const len = clamp(10 + sp * 1.9, 10, 34);
        const dx = (w.u / sp) * len;
        const dy = -(w.v / sp) * len;
        drawArrow(ctx, pt.x, pt.y, dx, dy, speedToColor(sp));
      }
    }
  }

  MapApp.prototype.initWeatherLayer = function () {
    this.weatherLayerButton = document.querySelector(
      '[data-action="layer-weather"]',
    );
    this.weatherLegend = document.getElementById("weather-legend");
    this.weatherEnabled = false;
    this.weatherLayer = null;
    this.weatherModel = null;
    this.weatherSpeedMultiplier = 1;
    this.windScenarioPreset = WEATHER_DEFAULT_PRESET;
    this.setWeatherLegendVisible(false);

    if (this.weatherLayerButton) {
      this.weatherLayerButton.addEventListener("click", () => {
        this.setWeatherEnabled(!this.weatherEnabled);
        if (this.setBaseListOpen) {
          this.setBaseListOpen(false);
        }
      });
    }
  };

  MapApp.prototype.prewarmWeatherLayer = function () {
    if (this.weatherPrewarmed || !this.map) {
      return;
    }
    const run = () => {
      if (this.weatherPrewarmed || !this.map) {
        return;
      }
      this.weatherPrewarmed = true;
      this.ensureWeatherModel();
      if (!this.weatherLayer) {
        this.weatherLayer = new WeatherLayer(this.map, this.weatherModel, {
          stepMeters: WEATHER_STEP_METERS,
          maxPoints: WEATHER_MAX_POINTS,
        });
      }
      if (this.weatherLayer && typeof this.weatherLayer.prepare === "function") {
        this.weatherLayer.prepare();
      }
    };
    if (this.map.loaded && !this.map.loaded()) {
      this.map.once("load", () => {
        requestAnimationFrame(run);
      });
      return;
    }
    if (typeof this.map.isStyleLoaded === "function" && !this.map.isStyleLoaded()) {
      this.map.once("idle", () => {
        requestAnimationFrame(run);
      });
      return;
    }
    requestAnimationFrame(run);
  };

  MapApp.prototype.ensureWeatherModel = function () {
    const preset = normalizeWindPreset(this.windScenarioPreset);
    if (!this.weatherModel) {
      this.weatherModel = new WindModel({
        seed: 20260121,
        timeSpeed: WEATHER_TIME_SPEED,
        preset,
      });
    }
    this.weatherModel.setPreset(preset);
    if (typeof this.setWeatherTimeSpeed === "function") {
      this.setWeatherTimeSpeed(this.weatherSpeedMultiplier || 1);
    }
  };

  MapApp.prototype.initWindScenario = function () {
    if (this.windScenarioInitialized) {
      return;
    }
    this.windScenarioInitialized = true;
    this.windScenarioPreset = normalizeWindPreset(this.windScenarioPreset);
    this.windApplyMode = false;
    this.windLocalRadiusM = WEATHER_LOCAL_RADIUS_M;
    this.windApplyCursor = null;
    this.windApplyCursorLabel = null;
    this.windApplyPopup = null;
    this.windApplyPendingLngLat = null;
    this.windApplyLastLngLat = null;

    this.windPresetButtons = Array.from(
      document.querySelectorAll("[data-wind-preset]"),
    );
    this.windApplyToggle = document.getElementById("scenario-wind-apply");
    this.windResetButton = document.getElementById("scenario-wind-reset");
    this.windRadiusInput = document.getElementById("scenario-wind-radius");
    this.windRadiusValue = document.getElementById("scenario-wind-radius-value");
    this.windStatus = document.getElementById("scenario-wind-status");

    if (this.windRadiusInput) {
      const value = Number(this.windRadiusInput.value);
      if (Number.isFinite(value) && value > 0) {
        this.windLocalRadiusM = value;
      }
      this.windRadiusInput.addEventListener("input", (event) => {
        const nextValue = Number(event.target.value);
        if (Number.isFinite(nextValue) && nextValue > 0) {
          this.windLocalRadiusM = nextValue;
          this.updateWindRadiusLabel();
          if (this.windApplyMode && this.windApplyLastLngLat) {
            this.updateWindApplyCursor(this.windApplyLastLngLat);
          }
        }
      });
    }

    this.updateWindPresetUI();
    this.updateWindRadiusLabel();
    const initialGrade = this.translateLiteral(formatPresetLabel(this.windScenarioPreset));
    this.setWindScenarioStatus(this.t("status.wind_grade", { grade: initialGrade }));

    this.windPresetButtons.forEach((button) => {
      button.addEventListener("click", () => {
        this.setWindScenarioPreset(button.dataset.windPreset);
      });
    });

    if (this.windApplyToggle) {
      this.windApplyToggle.addEventListener("click", () => {
        this.setWindApplyMode(!this.windApplyMode);
      });
    }

    if (this.windResetButton) {
      this.windResetButton.addEventListener("click", () => {
        this.clearWindLocalZones();
      });
    }

    if (this.map) {
      this.map.on("mousemove", (event) => {
        if (!this.windApplyMode) {
          return;
        }
        this.updateWindApplyCursor(event.lngLat);
      });
      this.map.on("click", (event) => {
        if (!this.windApplyMode) {
          return;
        }
        this.openWindApplyPopup(event.lngLat);
      });
      this.map.on("zoom", () => {
        if (this.windApplyMode && this.windApplyLastLngLat) {
          this.updateWindApplyCursor(this.windApplyLastLngLat);
        }
        this.updateWindApplyPopupPosition();
      });
      this.map.on("move", () => {
        if (this.windApplyMode && this.windApplyLastLngLat) {
          this.updateWindApplyCursor(this.windApplyLastLngLat);
        }
        this.updateWindApplyPopupPosition();
      });
      const container = this.map.getContainer();
      if (container) {
        container.addEventListener("mouseleave", () => {
          if (this.windApplyCursor) {
            this.windApplyCursor.style.display = "none";
          }
        });
        container.addEventListener("mouseenter", () => {
          if (this.windApplyMode && this.windApplyCursor && this.windApplyLastLngLat) {
            this.windApplyCursor.style.display = "block";
          }
        });
      }
    }
  };

  MapApp.prototype.updateWindPresetUI = function () {
    const preset = normalizeWindPreset(this.windScenarioPreset);
    this.windPresetButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.windPreset === preset);
    });
  };

  MapApp.prototype.updateWindRadiusLabel = function () {
    if (this.windRadiusValue) {
      this.windRadiusValue.textContent = formatDistance(this.windLocalRadiusM);
    }
  };

  MapApp.prototype.setWindScenarioStatus = function (text) {
    if (this.windStatus) {
      this.windStatus.textContent = String(text || "");
    }
  };

  MapApp.prototype.setWindScenarioPreset = function (preset) {
    const next = normalizeWindPreset(preset);
    this.windScenarioPreset = next;
    this.updateWindPresetUI();
    this.ensureWeatherModel();
    if (this.webApiEnabled && typeof this.sendWebRequest === "function") {
      this.sendWebRequest("api/wind", { preset: next });
    }
    const grade = this.translateLiteral(formatPresetLabel(next));
    this.setWindScenarioStatus(this.t("status.wind_grade_set", { grade }));
  };

  MapApp.prototype.setWindApplyMode = function (enabled) {
    const next = Boolean(enabled);
    this.windApplyMode = next;
    if (this.windApplyToggle) {
      this.windApplyToggle.textContent = this.translateLiteral(
        next ? "Apply mode: ON" : "Apply mode: OFF",
      );
      this.windApplyToggle.classList.toggle("is-active", next);
    }
    if (this.map && this.map.getCanvas) {
      this.map.getCanvas().style.cursor = next ? "crosshair" : "";
    }
    this.ensureWindApplyOverlay();
    if (this.windApplyCursor) {
      this.windApplyCursor.style.display =
        next && this.windApplyLastLngLat ? "block" : "none";
    }
    if (!next) {
      this.closeWindApplyPopup();
    }
    this.setWindScenarioStatus(
      next ? this.t("status.apply_mode_on") : this.t("status.apply_mode_off"),
    );
  };

  MapApp.prototype.ensureWindApplyOverlay = function () {
    if (this.windApplyCursor || !this.map) {
      return;
    }
    const container = this.map.getContainer();
    if (!container) {
      return;
    }

    const cursor = document.createElement("div");
    cursor.className = "wind-apply-cursor";
    cursor.style.display = "none";
    const label = document.createElement("div");
    label.className = "wind-apply-label";
    cursor.appendChild(label);
    container.appendChild(cursor);
    this.windApplyCursor = cursor;
    this.windApplyCursorLabel = label;

    const popup = document.createElement("div");
    popup.className = "wind-apply-popup";
    popup.setAttribute("aria-hidden", "true");

    const title = document.createElement("div");
    title.className = "popup-title";
    title.textContent = this.translateLiteral("Local wind");
    popup.appendChild(title);

    const row = document.createElement("div");
    row.className = "popup-row";
    WEATHER_PRESETS.forEach((preset) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.preset = preset;
      button.textContent = this.translateLiteral(formatPresetLabel(preset));
      row.appendChild(button);
    });
    popup.appendChild(row);

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "secondary";
    cancel.dataset.action = "cancel";
    cancel.textContent = this.translateLiteral("Cancel");
    popup.appendChild(cancel);

    container.appendChild(popup);
    this.windApplyPopup = popup;

    popup.addEventListener("mousedown", (event) => event.stopPropagation());
    popup.addEventListener("wheel", (event) => event.stopPropagation());
    popup.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      const button = target.closest("button");
      if (!button) {
        return;
      }
      const preset = button.dataset.preset;
      if (preset) {
        this.applyLocalWindPreset(preset);
        return;
      }
      if (button.dataset.action === "cancel") {
        this.closeWindApplyPopup();
      }
    });
  };

  MapApp.prototype.updateWindApplyCursor = function (lngLat) {
    if (!this.map || !this.windApplyCursor || !lngLat) {
      return;
    }
    this.windApplyLastLngLat = lngLat;
    const radiusPx = radiusMetersToPixels(this.map, lngLat, this.windLocalRadiusM);
    const point = this.map.project([lngLat.lng, lngLat.lat]);
    this.windApplyCursor.style.width = `${radiusPx * 2}px`;
    this.windApplyCursor.style.height = `${radiusPx * 2}px`;
    this.windApplyCursor.style.left = `${point.x}px`;
    this.windApplyCursor.style.top = `${point.y}px`;
    if (this.windApplyCursorLabel) {
      this.windApplyCursorLabel.textContent = `D ${formatDistance(
        this.windLocalRadiusM * 2,
      )}`;
    }
  };

  MapApp.prototype.updateWindApplyPopupPosition = function () {
    if (!this.map || !this.windApplyPopup || !this.windApplyPendingLngLat) {
      return;
    }
    const lngLat = this.windApplyPendingLngLat;
    const point = this.map.project([lngLat.lng, lngLat.lat]);
    this.windApplyPopup.style.left = `${point.x}px`;
    this.windApplyPopup.style.top = `${point.y}px`;
  };

  MapApp.prototype.openWindApplyPopup = function (lngLat) {
    if (!lngLat) {
      return;
    }
    this.ensureWindApplyOverlay();
    if (!this.windApplyPopup) {
      return;
    }
    this.windApplyPendingLngLat = lngLat;
    this.updateWindApplyPopupPosition();
    this.windApplyPopup.style.display = "block";
    this.windApplyPopup.setAttribute("aria-hidden", "false");
  };

  MapApp.prototype.closeWindApplyPopup = function () {
    if (!this.windApplyPopup) {
      return;
    }
    this.windApplyPendingLngLat = null;
    this.windApplyPopup.style.display = "none";
    this.windApplyPopup.setAttribute("aria-hidden", "true");
  };

  MapApp.prototype.applyLocalWindPreset = function (preset) {
    if (!this.windApplyPendingLngLat) {
      return;
    }
    const next = normalizeWindPreset(preset);
    const lngLat = this.windApplyPendingLngLat;
    this.ensureWeatherModel();
    const xm = lonToX(lngLat.lng);
    const ym = latToY(lngLat.lat);
    this.weatherModel.addLocalZone(xm, ym, this.windLocalRadiusM, next);
    if (this.webApiEnabled && typeof this.sendWebRequest === "function") {
      this.sendWebRequest("api/wind", {
        local: {
          lon: lngLat.lng,
          lat: lngLat.lat,
          radius_m: this.windLocalRadiusM,
          preset: next,
        },
      });
    }
    const grade = this.translateLiteral(formatPresetLabel(next));
    const radius = formatDistance(this.windLocalRadiusM * 2);
    this.setWindScenarioStatus(this.t("status.local_wind_applied", { grade, radius }));
    this.closeWindApplyPopup();
  };

  MapApp.prototype.clearWindLocalZones = function () {
    this.ensureWeatherModel();
    if (this.weatherModel) {
      this.weatherModel.clearLocalZones();
    }
    if (this.webApiEnabled && typeof this.sendWebRequest === "function") {
      this.sendWebRequest("api/wind", { clear_local: true });
    }
    this.setWindScenarioStatus(this.t("status.local_wind_fade"));
  };

  MapApp.prototype.setWeatherEnabled = function (enabled) {
    const next = Boolean(enabled);
    this.weatherEnabled = next;
    if (this.weatherLayerButton) {
      this.weatherLayerButton.classList.toggle("is-active", next);
    }
    this.setWeatherLegendVisible(next);
    if (!next) {
      if (this.weatherLayer) {
        this.weatherLayer.stop();
      }
      return;
    }
    if (!this.map) {
      return;
    }
    this.ensureWeatherModel();
    if (!this.weatherLayer) {
      this.weatherLayer = new WeatherLayer(this.map, this.weatherModel, {
        stepMeters: WEATHER_STEP_METERS,
        maxPoints: WEATHER_MAX_POINTS,
      });
    }
    this.weatherLayer.start();
  };

  MapApp.prototype.setWeatherLegendVisible = function (visible) {
    if (!this.weatherLegend) {
      return;
    }
    const next = Boolean(visible);
    this.weatherLegend.classList.toggle("is-active", next);
    this.weatherLegend.setAttribute("aria-hidden", next ? "false" : "true");
  };

  MapApp.prototype.setWeatherTimeSpeed = function (multiplier) {
    const value = Number(multiplier);
    const next = Number.isFinite(value) && value > 0 ? value : 1;
    this.weatherSpeedMultiplier = next;
    const baseSpeed =
      this.rulesState && Number.isFinite(this.rulesState.wind_time_speed)
        ? this.rulesState.wind_time_speed
        : WEATHER_TIME_SPEED;
    if (this.weatherModel) {
      if (typeof this.weatherModel.setTimeSpeed === "function") {
        this.weatherModel.setTimeSpeed(baseSpeed * next);
      } else {
        this.weatherModel.timeSpeed = baseSpeed * next;
      }
    }
  };

  MapApp.prototype.getWeatherWindAt = function (lon, lat) {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      return null;
    }
    this.ensureWeatherModel();
    const xm = lonToX(lon);
    const ym = latToY(lat);
    return this.weatherModel.windAtMercator(xm, ym, performance.now() / 1000.0);
  };

  const baseUpdateFastLabel = MapApp.prototype.updateFastLabel;
  if (baseUpdateFastLabel) {
    MapApp.prototype.updateFastLabel = function (speed) {
      baseUpdateFastLabel.call(this, speed);
      this.setWeatherTimeSpeed(speed);
    };
  }

  const baseInit = MapApp.prototype.init;
  if (baseInit) {
    MapApp.prototype.init = function () {
      baseInit.call(this);
      this.initWeatherLayer();
      this.initWindScenario();
      this.prewarmWeatherLayer();
    };
  }
})();

