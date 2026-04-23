const RAD = Math.PI / 180;
const EARTH_RADIUS_M = 6378137;
const LOG10 = Math.log(10);

const log10 = (value) => Math.log(value) / LOG10;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

let avgGridSize = 0;
let avgSumEnergy = null;
let avgSumTime = 0;

const resetAverage = () => {
  avgGridSize = 0;
  avgSumEnergy = null;
  avgSumTime = 0;
};

const exportAverage = () => {
  if (!avgSumEnergy || avgSumTime <= 0 || avgGridSize <= 0) {
    return null;
  }
  const copy = new Float64Array(avgSumEnergy);
  return { gridSize: avgGridSize, sumTime: avgSumTime, sumEnergy: copy };
};

const importAverage = (payload) => {
  if (!payload) {
    return false;
  }
  const gridSize = Number(payload.gridSize);
  const sumTime = Number(payload.sumTime);
  let sumEnergy = payload.sumEnergy;
  let energyArray = null;
  if (sumEnergy instanceof Float64Array) {
    energyArray = sumEnergy;
  } else if (sumEnergy instanceof ArrayBuffer) {
    energyArray = new Float64Array(sumEnergy);
  } else if (Array.isArray(sumEnergy)) {
    energyArray = new Float64Array(sumEnergy);
  }
  if (
    !energyArray ||
    !Number.isFinite(gridSize) ||
    gridSize <= 0 ||
    energyArray.length !== gridSize * gridSize
  ) {
    return false;
  }
  avgGridSize = gridSize;
  avgSumEnergy = energyArray;
  avgSumTime = Number.isFinite(sumTime) && sumTime >= 0 ? sumTime : 0;
  return true;
};

const toMercator = (lon, lat) => {
  const x = EARTH_RADIUS_M * (lon * RAD);
  const y =
    EARTH_RADIUS_M *
    Math.log(Math.tan(Math.PI / 4 + (lat * RAD) / 2));
  return [x, y];
};

const lerp = (a, b, t) => a + (b - a) * t;

const sampleRamp = (t) => {
  const stops = [
    [0.0, [46, 88, 202]],
    [0.12, [70, 170, 152]],
    [0.35, [236, 210, 96]],
    [0.7, [238, 142, 62]],
    [1.0, [220, 60, 60]],
  ];
  const clamped = clamp(t, 0, 1);
  for (let i = 0; i < stops.length - 1; i += 1) {
    const a = stops[i];
    const b = stops[i + 1];
    if (clamped <= b[0]) {
      const span = b[0] - a[0] || 1;
      const local = (clamped - a[0]) / span;
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

const computeEnergy = (bounds, gridSize, flights, ground, minDbValue, l0, d0, slope) => {
  const energy = new Float32Array(gridSize * gridSize);
  if (!bounds || !flights || flights.length === 0) {
    return energy;
  }
  const [westX, southY] = toMercator(bounds.west, bounds.south);
  const [eastX, northY] = toMercator(bounds.east, bounds.north);
  const width = eastX - westX;
  const height = northY - southY;
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return energy;
  }
  const dx = width / gridSize;
  const dy = height / gridSize;
  const xCoords = new Float64Array(gridSize);
  const yCoords = new Float64Array(gridSize);
  for (let i = 0; i < gridSize; i += 1) {
    xCoords[i] = westX + (i + 0.5) * dx;
    yCoords[i] = northY - (i + 0.5) * dy;
  }

  let radius = 0;
  if (Number.isFinite(slope) && slope !== 0) {
    radius = d0 * Math.pow(10, (minDbValue - l0) / slope);
  }
  if (!Number.isFinite(radius) || radius <= 0) {
    radius = 0;
  }

  const hasGround = Boolean(ground && ground.length === energy.length);
  for (let i = 0; i < flights.length; i += 1) {
    const flight = flights[i];
    if (!flight) {
      continue;
    }
    const lon = Number(flight.lon);
    const lat = Number(flight.lat);
    const alt = Number(flight.alt);
    if (!Number.isFinite(lon) || !Number.isFinite(lat) || !Number.isFinite(alt)) {
      continue;
    }
    const [fx, fy] = toMercator(lon, lat);
    const colStart = clamp(Math.floor((fx - radius - westX) / dx), 0, gridSize - 1);
    const colEnd = clamp(Math.ceil((fx + radius - westX) / dx), 0, gridSize - 1);
    const rowStart = clamp(Math.floor((northY - (fy + radius)) / dy), 0, gridSize - 1);
    const rowEnd = clamp(Math.ceil((northY - (fy - radius)) / dy), 0, gridSize - 1);
    for (let row = rowStart; row <= rowEnd; row += 1) {
      const dyM = yCoords[row] - fy;
      const baseIndex = row * gridSize;
      for (let col = colStart; col <= colEnd; col += 1) {
        const dxM = xCoords[col] - fx;
        const horizontal = Math.hypot(dxM, dyM);
        const idx = baseIndex + col;
        const groundAlt = hasGround ? ground[idx] : 0;
        const deltaH = alt - groundAlt;
        const distance = Math.hypot(horizontal, deltaH);
        if (distance <= 0) {
          continue;
        }
        const level = l0 + slope * log10(distance / d0);
        if (level < minDbValue) {
          continue;
        }
        energy[idx] += Math.pow(10, level * 0.1);
      }
    }
  }

  return energy;
};

const energyToPixels = (energy, gridSize, minDbValue, maxDbValue, levelsOut) => {
  const pixels = new Uint8ClampedArray(gridSize * gridSize * 4);
  const range = maxDbValue - minDbValue || 1;
  const hasLevels = Boolean(levelsOut);
  for (let idx = 0; idx < energy.length; idx += 1) {
    const value = energy[idx];
    const offset = idx * 4;
    if (!Number.isFinite(value) || value <= 0) {
      pixels[offset + 3] = 0;
      if (hasLevels) {
        levelsOut[idx] = Number.NaN;
      }
      continue;
    }
    const level = 10 * log10(value);
    if (hasLevels) {
      levelsOut[idx] = level;
    }
    if (level < minDbValue) {
      pixels[offset + 3] = 0;
      continue;
    }
    const t = clamp((level - minDbValue) / range, 0, 1);
    const color = sampleRamp(t);
    pixels[offset] = color[0];
    pixels[offset + 1] = color[1];
    pixels[offset + 2] = color[2];
    pixels[offset + 3] = 190;
  }
  return pixels;
};

const updateAverage = (energy, gridSize, step, resetAvg) => {
  if (!avgSumEnergy || avgGridSize !== gridSize || resetAvg) {
    resetAverage();
    avgGridSize = gridSize;
    avgSumEnergy = new Float64Array(gridSize * gridSize);
  }
  if (step > 0 && avgSumEnergy) {
    for (let idx = 0; idx < energy.length; idx += 1) {
      avgSumEnergy[idx] += energy[idx] * step;
    }
    avgSumTime += step;
  }
};

const averageToPixels = (gridSize, minDbValue, maxDbValue, levelsOut) => {
  const pixels = new Uint8ClampedArray(gridSize * gridSize * 4);
  const range = maxDbValue - minDbValue || 1;
  const hasLevels = Boolean(levelsOut);
  if (hasLevels) {
    levelsOut.fill(Number.NaN);
  }
  if (avgSumTime <= 0 || !avgSumEnergy || avgGridSize !== gridSize) {
    return pixels;
  }
  for (let idx = 0; idx < avgSumEnergy.length; idx += 1) {
    const value = avgSumEnergy[idx] / avgSumTime;
    const offset = idx * 4;
    if (!Number.isFinite(value) || value <= 0) {
      pixels[offset + 3] = 0;
      continue;
    }
    const level = 10 * log10(value);
    if (hasLevels) {
      levelsOut[idx] = level;
    }
    if (level < minDbValue) {
      pixels[offset + 3] = 0;
      continue;
    }
    const t = clamp((level - minDbValue) / range, 0, 1);
    const color = sampleRamp(t);
    pixels[offset] = color[0];
    pixels[offset + 1] = color[1];
    pixels[offset + 2] = color[2];
    pixels[offset + 3] = 190;
  }
  return pixels;
};

const computeNoise = (payload) => {
  const {
    id,
    bounds,
    gridSize,
    flights,
    ground,
    averageBounds,
    averageGridSize,
    averageFlights,
    averageGround,
    minDb,
    averageMinDb,
    maxDb,
    l0,
    d0,
    slope,
    mode,
    dt,
    resetAverage: resetAvg,
    accumulateAverage,
    includeLevels,
  } = payload;
  const minDbValue = Number.isFinite(minDb) ? minDb : 0;
  const avgMinDbValue = Number.isFinite(averageMinDb) ? averageMinDb : minDbValue;
  const maxDbValue = Number.isFinite(maxDb) && maxDb > minDbValue ? maxDb : minDbValue + 40;
  const avgMaxDbValue = Number.isFinite(maxDb) && maxDb > avgMinDbValue ? maxDb : avgMinDbValue + 40;
  const step = Number.isFinite(dt) ? Math.max(0, dt) : 0;
  const isAverage = mode === "average";

  if (isAverage) {
    const avgBounds = averageBounds || bounds;
    const avgSize = Number.isFinite(averageGridSize) && averageGridSize > 0 ? averageGridSize : gridSize;
    const avgFlights = Array.isArray(averageFlights) ? averageFlights : flights || [];
    const avgGround = averageGround || ground;
    const avgEnergy = computeEnergy(avgBounds, avgSize, avgFlights, avgGround, avgMinDbValue, l0, d0, slope);
    // JY - Noise average: accumulate energy over time for cumulative average.
    updateAverage(avgEnergy, avgSize, step, resetAvg);
    // JY - Noise hover: include per-cell dB levels when requested.
    const levels = includeLevels ? new Float32Array(avgSize * avgSize) : null;
    const pixels = averageToPixels(avgSize, avgMinDbValue, avgMaxDbValue, levels);
    return { id, gridSize: avgSize, pixels, levels };
  }

  const energy = computeEnergy(bounds, gridSize, Array.isArray(flights) ? flights : [], ground, minDbValue, l0, d0, slope);
  // JY - Noise hover: include per-cell dB levels when requested.
  const levels = includeLevels ? new Float32Array(gridSize * gridSize) : null;
  const pixels = energyToPixels(energy, gridSize, minDbValue, maxDbValue, levels);

  if (accumulateAverage && averageBounds && Number.isFinite(averageGridSize) && averageGridSize > 0) {
    const avgFlights = Array.isArray(averageFlights) ? averageFlights : [];
    const avgEnergy = computeEnergy(
      averageBounds,
      averageGridSize,
      avgFlights,
      averageGround,
      avgMinDbValue,
      l0,
      d0,
      slope,
    );
    updateAverage(avgEnergy, averageGridSize, step, resetAvg);
  }

  return { id, gridSize, pixels, levels };
};

self.onmessage = (event) => {
  const payload = event && event.data ? event.data : null;
  if (!payload) {
    return;
  }
  if (payload.type === "exportAverage") {
    const state = exportAverage();
    if (!state) {
      return;
    }
    const message = {
      type: "average",
      id: payload.id,
      gridSize: state.gridSize,
      sumTime: state.sumTime,
      sumEnergy: state.sumEnergy,
    };
    self.postMessage(message, [state.sumEnergy.buffer]);
    return;
  }
  if (payload.type === "importAverage") {
    importAverage(payload);
    return;
  }
  if (payload.type !== "compute") {
    return;
  }
  const result = computeNoise(payload);
  if (!result || !result.pixels) {
    return;
  }
  const message = {
    type: "result",
    id: result.id,
    gridSize: result.gridSize,
    pixels: result.pixels,
  };
  const transfer = [result.pixels.buffer];
  if (result.levels) {
    message.levels = result.levels;
    transfer.push(result.levels.buffer);
  }
  self.postMessage(message, transfer);
};
