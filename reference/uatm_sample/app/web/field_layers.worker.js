const DEG_TO_RAD = Math.PI / 180;
const EARTH_RADIUS_M = 6378137;

const MODE_IMPACT = "impact";
const MODE_DENSITY = "density";
const MODE_CONGESTION = "congestion";

const EPSILON = 0.02;
const MIN_SIGMA_M = 8;
const MAX_SIGMA_M = 2600;
const MIN_RADIUS_M = 12;
const MAX_RADIUS_M = 12000;
const MODE_RADIUS_PX = {
  [MODE_IMPACT]: 60,
  [MODE_DENSITY]: 56,
  [MODE_CONGESTION]: 58,
};
const MODE_SCALE_FIXED = {
  [MODE_IMPACT]: 1.2,
  [MODE_DENSITY]: 0.95,
  [MODE_CONGESTION]: 1.6,
};

let baseCongestionConfig = null;
try {
  importScripts("field_congestion_config.js?v=20260227a");
  if (typeof self !== "undefined" && self.FIELD_CONGESTION_CONFIG) {
    baseCongestionConfig = self.FIELD_CONGESTION_CONFIG;
  }
} catch (_err) {
  baseCongestionConfig = null;
}

const DEFAULT_CONGESTION_CONFIG = {
  freeflow_mps: 50,
  delay_window_s: 30,
  delay_threshold_s: 5,
  delay_max_dt_s: 1.0,
  delay_merge_eps: 0.02,
  rho_sigma_parallel_m: 200,
  rho_sigma_perp_m: 200,
  rho_cutoff_sigma: 1.0,
  front_box_longitudinal_m: 1000,
  front_box_lateral_m: 500,
  neighbor_epsilon: 1e-6,
  rho_norm_quantile: 0.9,
  rho_norm_min: 0.25,
  rho_norm_cap: 1.0,
  neighbor_cell_m: 400,
  stale_state_s: 600,
  min_altitude_m: null,
  min_speed_mps: 1.0,
  field_scale_congestion: 1.0,
};

const delayStateById = new Map();
const delayLastSeen = new Map();

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const lerp = (a, b, t) => a + (b - a) * t;

const toMercator = (lon, lat) => {
  const x = EARTH_RADIUS_M * (lon * DEG_TO_RAD);
  const y = EARTH_RADIUS_M * Math.log(Math.tan(Math.PI / 4 + (lat * DEG_TO_RAD) / 2));
  return [x, y];
};

const sampleRamp = (mode, tRaw) => {
  const t = clamp(tRaw, 0, 1);
  let stops;
  if (mode === MODE_IMPACT) {
    stops = [
      [0.0, [17, 78, 158]],
      [0.38, [48, 148, 232]],
      [0.72, [97, 211, 255]],
      [1.0, [216, 247, 255]],
    ];
  } else if (mode === MODE_DENSITY) {
    stops = [
      [0.0, [41, 123, 84]],
      [0.36, [95, 172, 97]],
      [0.68, [198, 201, 84]],
      [1.0, [244, 136, 63]],
    ];
  } else {
    stops = [
      [0.0, [22, 9, 46]],
      [0.2, [60, 9, 94]],
      [0.4, [104, 22, 110]],
      [0.6, [163, 37, 85]],
      [0.8, [215, 78, 40]],
      [1.0, [252, 232, 58]],
    ];
  }
  for (let i = 0; i < stops.length - 1; i += 1) {
    const a = stops[i];
    const b = stops[i + 1];
    if (t <= b[0]) {
      const span = b[0] - a[0] || 1;
      const local = (t - a[0]) / span;
      return [
        Math.round(lerp(a[1][0], b[1][0], local)),
        Math.round(lerp(a[1][1], b[1][1], local)),
        Math.round(lerp(a[1][2], b[1][2], local)),
      ];
    }
  }
  const last = stops[stops.length - 1][1];
  return [last[0], last[1], last[2]];
};

const toFinite = (value, fallback = null) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const nowMs = () =>
  typeof performance !== "undefined" && typeof performance.now === "function"
    ? performance.now()
    : Date.now();

const resolveCongestionConfig = (payload) => {
  const base = { ...DEFAULT_CONGESTION_CONFIG, ...(baseCongestionConfig || {}) };
  const next = { ...base };
  const override = payload && payload.config && typeof payload.config === "object" ? payload.config : null;
  if (override) {
    Object.keys(base).forEach((key) => {
      const value = Number(override[key]);
      if (Number.isFinite(value)) {
        next[key] = value;
      }
    });
  }
  next.freeflow_mps = clamp(toFinite(next.freeflow_mps, 50), 5, 120);
  next.delay_window_s = clamp(toFinite(next.delay_window_s, 120), 10, 900);
  next.delay_threshold_s = clamp(toFinite(next.delay_threshold_s, 30), 1, next.delay_window_s);
  next.delay_max_dt_s = clamp(toFinite(next.delay_max_dt_s, 2.0), 0.05, 10);
  next.delay_merge_eps = clamp(toFinite(next.delay_merge_eps, 0.02), 0, 0.5);
  next.rho_sigma_parallel_m = clamp(toFinite(next.rho_sigma_parallel_m, 600), 50, 8000);
  next.rho_sigma_perp_m = clamp(toFinite(next.rho_sigma_perp_m, 300), 50, 8000);
  next.rho_cutoff_sigma = clamp(toFinite(next.rho_cutoff_sigma, 3.0), 1.0, 6.0);
  next.front_box_longitudinal_m = clamp(toFinite(next.front_box_longitudinal_m, 1200), 50, 20000);
  next.front_box_lateral_m = clamp(toFinite(next.front_box_lateral_m, 600), 50, 10000);
  next.neighbor_epsilon = Math.max(1e-8, toFinite(next.neighbor_epsilon, 1e-6));
  next.rho_norm_quantile = clamp(toFinite(next.rho_norm_quantile, 0.9), 0.5, 0.99);
  next.rho_norm_min = clamp(toFinite(next.rho_norm_min, 0.25), 0.05, 10);
  next.rho_norm_cap = clamp(toFinite(next.rho_norm_cap, 1.0), 0.5, 5.0);
  next.neighbor_cell_m = clamp(toFinite(next.neighbor_cell_m, 400), 50, 5000);
  next.stale_state_s = clamp(toFinite(next.stale_state_s, 600), 30, 3600);
  if (next.min_altitude_m == null) {
    next.min_altitude_m = null;
  } else {
    const minAlt = toFinite(next.min_altitude_m, null);
    next.min_altitude_m = Number.isFinite(minAlt) ? Math.max(0, minAlt) : null;
  }
  next.min_speed_mps = clamp(toFinite(next.min_speed_mps, 1.0), 0, 50);
  next.field_scale_congestion = clamp(
    toFinite(next.field_scale_congestion, MODE_SCALE_FIXED[MODE_CONGESTION]),
    0.2,
    8,
  );
  return next;
};

const headingToUnit = (headingDeg) => {
  const heading = toFinite(headingDeg, null);
  if (!Number.isFinite(heading)) {
    return null;
  }
  const rad = heading * DEG_TO_RAD;
  return [Math.sin(rad), Math.cos(rad)];
};

const updateDelayState = (id, nowS, epsilon, config) => {
  if (id == null) {
    return 0;
  }
  const key = String(id);
  let state = delayStateById.get(key);
  if (!state) {
    state = {
      last_t: nowS,
      last_eps: epsilon,
      head: 0,
      durations: [],
      epsilons: [],
      sum: 0,
      window: 0,
    };
    delayStateById.set(key, state);
  }
  const dtRaw = nowS - state.last_t;
  const dt = clamp(Number.isFinite(dtRaw) ? dtRaw : 0, 0, config.delay_max_dt_s);
  if (dt > 0) {
    const prevEps = Number.isFinite(state.last_eps) ? state.last_eps : 0;
    const mergeEps = Math.abs(prevEps - (state.epsilons[state.epsilons.length - 1] ?? NaN));
    if (state.durations.length && mergeEps <= config.delay_merge_eps) {
      state.durations[state.durations.length - 1] += dt;
    } else {
      state.durations.push(dt);
      state.epsilons.push(prevEps);
    }
    state.sum += dt * prevEps;
    state.window += dt;
    state.last_t = nowS;
  }
  state.last_eps = epsilon;

  const windowLimit = config.delay_window_s;
  while (state.window > windowLimit && state.head < state.durations.length) {
    const overflow = state.window - windowLimit;
    const dur = state.durations[state.head];
    if (dur <= overflow + 1e-9) {
      state.sum -= dur * state.epsilons[state.head];
      state.window -= dur;
      state.head += 1;
    } else {
      state.durations[state.head] = dur - overflow;
      state.sum -= overflow * state.epsilons[state.head];
      state.window -= overflow;
      break;
    }
  }
  if (state.head > 64) {
    state.durations = state.durations.slice(state.head);
    state.epsilons = state.epsilons.slice(state.head);
    state.head = 0;
  }
  delayLastSeen.set(key, nowS);
  return Math.max(0, state.sum);
};

const pruneDelayStates = (nowS, staleS) => {
  if (!delayLastSeen.size) {
    return;
  }
  const cutoff = nowS - staleS;
  for (const [key, seen] of delayLastSeen.entries()) {
    if (seen < cutoff) {
      delayLastSeen.delete(key);
      delayStateById.delete(key);
    }
  }
};

const buildSpatialIndex = (xs, ys, cellSize) => {
  const grid = new Map();
  for (let i = 0; i < xs.length; i += 1) {
    const x = xs[i];
    const y = ys[i];
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      continue;
    }
    const ix = Math.floor(x / cellSize);
    const iy = Math.floor(y / cellSize);
    const key = `${ix},${iy}`;
    const bucket = grid.get(key);
    if (bucket) {
      bucket.push(i);
    } else {
      grid.set(key, [i]);
    }
  }
  return grid;
};

const computeCongestionWeights = (
  xs,
  ys,
  headingX,
  headingY,
  speeds,
  targetSpeeds,
  ids,
  nowS,
  config,
) => {
  const n = xs.length;
  const epsilons = new Float32Array(n);
  const delayed = new Uint8Array(n);

  for (let i = 0; i < n; i += 1) {
    const speed = speeds[i];
    const freeflow = config.freeflow_mps;
    const eps =
      Number.isFinite(speed) && freeflow > 0 ? Math.max(0, 1 - speed / freeflow) : 0;
    epsilons[i] = eps;
    const dInt = updateDelayState(ids[i], nowS, eps, config);
    delayed[i] = dInt >= config.delay_threshold_s ? 1 : 0;
  }

  const sigmaPar = config.rho_sigma_parallel_m;
  const sigmaPerp = config.rho_sigma_perp_m;
  const invTwoSigPar = 1 / (2 * sigmaPar * sigmaPar);
  const invTwoSigPerp = 1 / (2 * sigmaPerp * sigmaPerp);
  const cutoffPar = config.rho_cutoff_sigma * sigmaPar;
  const cutoffPerp = config.rho_cutoff_sigma * sigmaPerp;
  const frontL = config.front_box_longitudinal_m;
  const frontW = config.front_box_lateral_m;
  const searchRadius = Math.max(cutoffPar, cutoffPerp, frontL, frontW);
  const cellSize = Math.max(config.neighbor_cell_m, searchRadius);
  const grid = buildSpatialIndex(xs, ys, cellSize);
  const range = Math.max(1, Math.ceil(searchRadius / cellSize));

  const rho = new Float32Array(n);
  const forwardRatio = new Float32Array(n);

  for (let i = 0; i < n; i += 1) {
    const xi = xs[i];
    const yi = ys[i];
    if (!Number.isFinite(xi) || !Number.isFinite(yi)) {
      continue;
    }
    const hx = headingX[i];
    const hy = headingY[i];
    const ix0 = Math.floor(xi / cellSize);
    const iy0 = Math.floor(yi / cellSize);
    let frontCount = 0;
    let frontDelayed = 0;
    let rhoSum = 0;
    for (let ix = ix0 - range; ix <= ix0 + range; ix += 1) {
      for (let iy = iy0 - range; iy <= iy0 + range; iy += 1) {
        const bucket = grid.get(`${ix},${iy}`);
        if (!bucket) {
          continue;
        }
        for (let b = 0; b < bucket.length; b += 1) {
          const j = bucket[b];
          if (j === i) {
            continue;
          }
          const rx = xs[j] - xi;
          const ry = ys[j] - yi;
          if (!Number.isFinite(rx) || !Number.isFinite(ry)) {
            continue;
          }
          const dPar = rx * hx + ry * hy;
          const dPerp = -rx * hy + ry * hx;
          if (Math.abs(dPar) <= cutoffPar && Math.abs(dPerp) <= cutoffPerp) {
            const k = Math.exp(-(dPar * dPar) * invTwoSigPar - (dPerp * dPerp) * invTwoSigPerp);
            if (k > EPSILON * 0.2) {
              rhoSum += k;
            }
          }
          if (dPar > 0 && dPar <= frontL && Math.abs(dPerp) <= frontW) {
            frontCount += 1;
            frontDelayed += delayed[j];
          }
        }
      }
    }
    rho[i] = rhoSum;
    forwardRatio[i] =
      frontCount > 0 ? frontDelayed / (frontCount + config.neighbor_epsilon) : 0;
  }

  const rhoScale = resolveScaleFromQuantile(
    Array.from(rho),
    config.rho_norm_quantile,
    config.rho_norm_min,
  );

  const congestion = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    const rhoHat = rhoScale > 0 ? Math.min(config.rho_norm_cap, rho[i] / rhoScale) : 0;
    const aVal = Math.max(epsilons[i], forwardRatio[i]);
    congestion[i] = rhoHat * aVal;
  }

  pruneDelayStates(nowS, config.stale_state_s);

  return congestion;
};

const resolveInfluenceRadiusPx = (flight, mode) => {
  const speed = clamp(toFinite(flight.speed_mps, 20), 0, 60);
  const base = Number(MODE_RADIUS_PX[mode] || MODE_RADIUS_PX[MODE_DENSITY]);
  const speedFactor = 0.94 + (speed / 60) * 0.14;
  return clamp(base * speedFactor, 36, 88);
};

const radiusToSigma = (radiusMeters) => {
  const sigma = radiusMeters / Math.sqrt(2 * Math.log(1 / EPSILON));
  return clamp(sigma, MIN_SIGMA_M, MAX_SIGMA_M);
};

const resolveImpactWeight = (flight) => {
  const speed = clamp(toFinite(flight.speed_mps, 20), 0, 60);
  const delay = clamp(toFinite(flight.delay_s, 0), 0, 600);
  const tti = clamp(toFinite(flight.tti, 1), 1, 4);
  const speedFactor = speed / 25;
  const delayFactor = delay / 240;
  const ttiFactor = (tti - 1) / 0.8;
  return 0.65 + speedFactor * 0.56 + delayFactor * 0.48 + ttiFactor * 0.44;
};

const resolveScaleFromQuantile = (values, quantile, minFallback) => {
  const positives = [];
  for (let i = 0; i < values.length; i += 1) {
    const value = values[i];
    if (Number.isFinite(value) && value > 0) {
      positives.push(value);
    }
  }
  if (!positives.length) {
    return minFallback;
  }
  positives.sort((a, b) => a - b);
  const index = clamp(Math.floor((positives.length - 1) * quantile), 0, positives.length - 1);
  return Math.max(minFallback, positives[index]);
};

const computeField = (payload) => {
  const id = Number(payload.id) || 0;
  const mode = String(payload.mode || "");
  const bounds = payload.bounds || null;
  const flights = Array.isArray(payload.flights) ? payload.flights : [];
  const gridSize = clamp(Number(payload.gridSize) || 120, 80, 320);
  const pixelCount = gridSize * gridSize;
  const pixels = new Uint8ClampedArray(pixelCount * 4);

  if (
    !bounds ||
    !Number.isFinite(Number(bounds.west)) ||
    !Number.isFinite(Number(bounds.east)) ||
    !Number.isFinite(Number(bounds.south)) ||
    !Number.isFinite(Number(bounds.north))
  ) {
    return { id, mode, gridSize, bounds, pixels, stats: { flights: 0, max: 0, scale: 1 } };
  }

  const west = Number(bounds.west);
  const east = Number(bounds.east);
  const south = Number(bounds.south);
  const north = Number(bounds.north);
  if (east <= west || north <= south || !flights.length) {
    return { id, mode, gridSize, bounds, pixels, stats: { flights: 0, max: 0, scale: 1 } };
  }

  const [westX, southY] = toMercator(west, south);
  const [eastX, northY] = toMercator(east, north);
  const width = eastX - westX;
  const height = northY - southY;
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return { id, mode, gridSize, bounds, pixels, stats: { flights: 0, max: 0, scale: 1 } };
  }

  const dx = width / gridSize;
  const dy = height / gridSize;
  const viewport = payload.viewport || null;
  const viewportWidth = clamp(
    Number(viewport && viewport.width) || gridSize,
    1,
    20000,
  );
  const viewportHeight = clamp(
    Number(viewport && viewport.height) || gridSize,
    1,
    20000,
  );
  const metersPerPixel = Math.max(0.01, (width / viewportWidth + height / viewportHeight) * 0.5);
  const xCoords = new Float64Array(gridSize);
  const yCoords = new Float64Array(gridSize);
  for (let i = 0; i < gridSize; i += 1) {
    xCoords[i] = westX + (i + 0.5) * dx;
    yCoords[i] = northY - (i + 0.5) * dy;
  }

  const congestionConfig = mode === MODE_CONGESTION ? resolveCongestionConfig(payload) : null;
  const minAltM =
    congestionConfig && Number.isFinite(congestionConfig.min_altitude_m)
      ? congestionConfig.min_altitude_m
      : null;
  const minSpeedMps =
    congestionConfig && Number.isFinite(congestionConfig.min_speed_mps)
      ? congestionConfig.min_speed_mps
      : null;

  const density = new Float32Array(pixelCount);
  const flightRefs = [];
  const xs = [];
  const ys = [];
  const speeds = [];
  const targetSpeeds = [];
  const headingX = [];
  const headingY = [];
  const ids = [];

  for (let i = 0; i < flights.length; i += 1) {
    const flight = flights[i];
    if (!flight) {
      continue;
    }
    const lon = toFinite(flight.lon, null);
    const lat = toFinite(flight.lat, null);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      continue;
    }
    const [fx, fy] = toMercator(lon, lat);
    if (!Number.isFinite(fx) || !Number.isFinite(fy)) {
      continue;
    }
    if (mode === MODE_CONGESTION) {
      const modeValue = String(flight.mode || "").trim().toLowerCase();
      if (modeValue !== "cruise") {
        continue;
      }
      if (
        flight.near_vertiport &&
        congestionConfig &&
        Number(congestionConfig.exclude_vertiport_radius_m) > 0
      ) {
        continue;
      }
    }
    if (minAltM != null) {
      const altitudeRaw =
        flight.altitude_m_raw != null ? toFinite(flight.altitude_m_raw, null) : null;
      const altitude = Number.isFinite(altitudeRaw)
        ? altitudeRaw
        : toFinite(flight.altitude_m, null);
      if (!Number.isFinite(altitude) || altitude < minAltM) {
        continue;
      }
    }
    if (minSpeedMps != null) {
      const speed = toFinite(flight.speed_mps, null);
      if (!Number.isFinite(speed) || speed < minSpeedMps) {
        continue;
      }
    }
    const hv = headingToUnit(flight.heading_deg);
    const hx = hv ? hv[0] : 0;
    const hy = hv ? hv[1] : 1;
    flightRefs.push(flight);
    xs.push(fx);
    ys.push(fy);
    speeds.push(toFinite(flight.speed_mps, null));
    targetSpeeds.push(toFinite(flight.speed_target_mps, null));
    headingX.push(hx);
    headingY.push(hy);
    ids.push(toFinite(flight.id, null));
  }

  const validFlights = flightRefs.length;
  const nowValue = toFinite(payload.nowMs, null);
  const nowS = (Number.isFinite(nowValue) ? nowValue : nowMs()) / 1000;
  const congestionWeights =
    mode === MODE_CONGESTION && congestionConfig && xs.length
      ? computeCongestionWeights(
        xs,
        ys,
        headingX,
        headingY,
        speeds,
        targetSpeeds,
        ids,
        nowS,
        congestionConfig,
      )
      : null;

  const isCongestionMode = mode === MODE_CONGESTION && congestionConfig;
  const congSigmaPar = isCongestionMode ? Number(congestionConfig.rho_sigma_parallel_m) : null;
  const congSigmaPerp = isCongestionMode ? Number(congestionConfig.rho_sigma_perp_m) : null;
  const congCutoffPar = isCongestionMode
    ? Number(congestionConfig.rho_cutoff_sigma) * congSigmaPar
    : null;
  const congCutoffPerp = isCongestionMode
    ? Number(congestionConfig.rho_cutoff_sigma) * congSigmaPerp
    : null;
  const congInvTwoSigPar = isCongestionMode
    ? 1 / (2 * congSigmaPar * congSigmaPar)
    : null;
  const congInvTwoSigPerp = isCongestionMode
    ? 1 / (2 * congSigmaPerp * congSigmaPerp)
    : null;
  const congRadius = isCongestionMode
    ? Math.max(congCutoffPar, congCutoffPerp)
    : null;

  for (let i = 0; i < flightRefs.length; i += 1) {
    const flight = flightRefs[i];
    const fx = xs[i];
    const fy = ys[i];
    let alpha = 1;
    if (mode === MODE_IMPACT) {
      alpha = resolveImpactWeight(flight);
    } else if (mode === MODE_CONGESTION) {
      alpha = congestionWeights ? congestionWeights[i] : 0;
      if (!Number.isFinite(alpha) || alpha <= 0) {
        continue;
      }
      if (isCongestionMode) {
        const hx = headingX[i];
        const hy = headingY[i];
        const radius = congRadius;
        const colStart = clamp(Math.floor((fx - radius - westX) / dx), 0, gridSize - 1);
        const colEnd = clamp(Math.ceil((fx + radius - westX) / dx), 0, gridSize - 1);
        const rowStart = clamp(Math.floor((northY - (fy + radius)) / dy), 0, gridSize - 1);
        const rowEnd = clamp(Math.ceil((northY - (fy - radius)) / dy), 0, gridSize - 1);

        for (let row = rowStart; row <= rowEnd; row += 1) {
          const dyM = yCoords[row] - fy;
          const baseIndex = row * gridSize;
          for (let col = colStart; col <= colEnd; col += 1) {
            const dxM = xCoords[col] - fx;
            const dPar = dxM * hx + dyM * hy;
            if (Math.abs(dPar) > congCutoffPar) {
              continue;
            }
            const dPerp = -dxM * hy + dyM * hx;
            if (Math.abs(dPerp) > congCutoffPerp) {
              continue;
            }
            const kernel = Math.exp(
              -(dPar * dPar) * congInvTwoSigPar - (dPerp * dPerp) * congInvTwoSigPerp,
            );
            if (kernel < EPSILON * 0.45) {
              continue;
            }
            const idx = baseIndex + col;
            density[idx] += kernel * alpha;
          }
        }
        continue;
      }
    }

    const radiusPx = resolveInfluenceRadiusPx(flight, mode);
    const radius = clamp(radiusPx * metersPerPixel, MIN_RADIUS_M, MAX_RADIUS_M);
    const sigma = radiusToSigma(radius);
    const sigmaSq = sigma * sigma;
    if (!Number.isFinite(sigmaSq) || sigmaSq <= 0) {
      continue;
    }
    const invTwoSigmaSq = 1 / (2 * sigmaSq);
    const radiusSq = radius * radius;

    const colStart = clamp(Math.floor((fx - radius - westX) / dx), 0, gridSize - 1);
    const colEnd = clamp(Math.ceil((fx + radius - westX) / dx), 0, gridSize - 1);
    const rowStart = clamp(Math.floor((northY - (fy + radius)) / dy), 0, gridSize - 1);
    const rowEnd = clamp(Math.ceil((northY - (fy - radius)) / dy), 0, gridSize - 1);

    for (let row = rowStart; row <= rowEnd; row += 1) {
      const dyM = yCoords[row] - fy;
      const baseIndex = row * gridSize;
      for (let col = colStart; col <= colEnd; col += 1) {
        const dxM = xCoords[col] - fx;
        const distSq = dxM * dxM + dyM * dyM;
        if (distSq > radiusSq) {
          continue;
        }
        const kernel = Math.exp(-distSq * invTwoSigmaSq);
        if (kernel < EPSILON * 0.45) {
          continue;
        }
        const idx = baseIndex + col;
        density[idx] += kernel * alpha;
      }
    }
  }

  const scalar = new Float32Array(pixelCount);
  scalar.set(density);

  let maxValue = 0;
  for (let i = 0; i < scalar.length; i += 1) {
    if (scalar[i] > maxValue) {
      maxValue = scalar[i];
    }
  }
  const scale =
    mode === MODE_CONGESTION && congestionConfig
      ? Number(congestionConfig.field_scale_congestion)
      : Number(MODE_SCALE_FIXED[mode] || MODE_SCALE_FIXED[MODE_DENSITY]);
  const effectiveScale = mode === MODE_CONGESTION ? Math.max(scale * 0.7, 0.00001) : scale;
  const alphaBase = mode === MODE_IMPACT ? 214 : mode === MODE_DENSITY ? 206 : 255;

  for (let idx = 0; idx < scalar.length; idx += 1) {
    const value = scalar[idx];
    const offset = idx * 4;
    if (!Number.isFinite(value) || value <= 0) {
      pixels[offset + 3] = 0;
      continue;
    }
    const normalized = clamp(1 - Math.exp(-value / Math.max(effectiveScale, 0.00001)), 0, 1);
    const eased = Math.pow(normalized, mode === MODE_CONGESTION ? 0.85 : 0.74);
    const color = sampleRamp(mode, eased);
    const alpha = Math.round(
      alphaBase * Math.pow(eased, mode === MODE_CONGESTION ? 0.78 : 0.72),
    );
    if (alpha < 8) {
      pixels[offset + 3] = 0;
      continue;
    }
    pixels[offset] = color[0];
    pixels[offset + 1] = color[1];
    pixels[offset + 2] = color[2];
    pixels[offset + 3] = clamp(alpha, 0, 244);
  }

  let congestionIds = null;
  let congestionScores = null;
  if (isCongestionMode && congestionWeights) {
    congestionIds = new Float64Array(ids.length);
    congestionScores = new Float32Array(ids.length);
    for (let i = 0; i < ids.length; i += 1) {
      const id = ids[i];
      congestionIds[i] = Number.isFinite(id) ? id : Number.NaN;
      const score = congestionWeights[i];
      congestionScores[i] = Number.isFinite(score) ? score : 0;
    }
  }

  return {
    id,
    mode,
    gridSize,
    bounds,
    pixels,
    congestionIds,
    congestionScores,
    stats: {
      flights: validFlights,
      max: maxValue,
      scale,
    },
  };
};

self.onmessage = (event) => {
  const payload = event && event.data ? event.data : null;
  if (!payload || !payload.type) {
    return;
  }
  if (payload.type === "reset") {
    delayStateById.clear();
    delayLastSeen.clear();
    return;
  }
  if (payload.type !== "compute") {
    return;
  }
  const result = computeField(payload);
  if (!result || !result.pixels) {
    return;
  }
  const transfer = [result.pixels.buffer];
  if (result.congestionIds && result.congestionIds.buffer) {
    transfer.push(result.congestionIds.buffer);
  }
  if (result.congestionScores && result.congestionScores.buffer) {
    transfer.push(result.congestionScores.buffer);
  }
  self.postMessage(result, transfer);
};
