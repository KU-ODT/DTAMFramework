/* transmission.worker.js (수정된 전체 파일) */

const RAD = Math.PI / 180;
const EARTH_RADIUS_M = 6378137;
const LOG10 = Math.log(10);

const log10 = (value) => Math.log(value) / LOG10;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const toMercator = (lon, lat) => {
  const x = EARTH_RADIUS_M * (lon * RAD);
  const y = EARTH_RADIUS_M * Math.log(Math.tan(Math.PI / 4 + (lat * RAD) / 2));
  return [x, y];
};

const lerp = (a, b, t) => a + (b - a) * t;

const sampleRamp = (t) => {
  const stops = [
    [0.0, [217, 43, 43]],
    [0.3, [242, 140, 40]],
    [0.6, [98, 199, 107]],
    [1.0, [106, 183, 255]],
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

const sampleGroundAt = (x, y, ground, gridSize, westX, northY, dx, dy) => {
  if (!ground) {
    return 0;
  }
  const colF = (x - westX) / dx - 0.5;
  const rowF = (northY - y) / dy - 0.5;
  const c0 = Math.floor(colF);
  const r0 = Math.floor(rowF);
  const c1 = c0 + 1;
  const r1 = r0 + 1;
  if (c0 < 0 || r0 < 0 || c1 >= gridSize || r1 >= gridSize) {
    return NaN;
  }
  const dc = colF - c0;
  const dr = rowF - r0;
  const idx00 = r0 * gridSize + c0;
  const idx01 = r0 * gridSize + c1;
  const idx10 = r1 * gridSize + c0;
  const idx11 = r1 * gridSize + c1;
  const z00 = ground[idx00];
  const z01 = ground[idx01];
  const z10 = ground[idx10];
  const z11 = ground[idx11];
  const z0 = z00 * (1 - dc) + z01 * dc;
  const z1 = z10 * (1 - dc) + z11 * dc;
  return z0 * (1 - dr) + z1 * dr;
};

const isLosTerrain = (
  bs,
  ut,
  ground,
  gridSize,
  westX,
  northY,
  dx,
  dy,
  stepM,
  clearanceM
) => {
  if (!ground) {
    return true;
  }
  const dxM = ut.x - bs.x;
  const dyM = ut.y - bs.y;
  const d2d = Math.hypot(dxM, dyM);
  if (d2d < 1e-3) {
    return true;
  }
  const steps = Math.max(2, Math.ceil(d2d / stepM));
  for (let i = 1; i < steps; i += 1) {
    const t = i / steps;
    const x = bs.x + t * dxM;
    const y = bs.y + t * dyM;
    const zLine = bs.z + t * (ut.z - bs.z);
    const zTerrain = sampleGroundAt(
      x,
      y,
      ground,
      gridSize,
      westX,
      northY,
      dx,
      dy
    );
    if (!Number.isFinite(zTerrain)) {
      continue;
    }
    if (zTerrain > zLine - clearanceM) {
      return false;
    }
  }
  return true;
};

const clipMinDistance = (value, minValue) => Math.max(value, minValue);

const pathloss38901UmaLos = (fcGhz, d2d, d3d, hBs, hUt) => {
  const c = 3.0e8;
  const fcHz = fcGhz * 1e9;
  const hE = 1.0;
  const hBsP = hBs - hE;
  const hUtP = hUt - hE;
  const dBp = (4.0 * hBsP * hUtP * fcHz) / c;
  const d2dClip = clipMinDistance(d2d, 10.0);
  const d3dClip = clipMinDistance(d3d, 10.0);
  const pl1 = 28.0 + 22.0 * log10(d3dClip) + 20.0 * log10(fcGhz);
  const pl2 =
    28.0 +
    40.0 * log10(d3dClip) +
    20.0 * log10(fcGhz) -
    9.0 * log10(dBp * dBp + (hBs - hUt) ** 2);
  return d2dClip <= dBp ? pl1 : pl2;
};

const pathloss38901UmaNlos = (fcGhz, d2d, d3d, hBs, hUt) => {
  const d3dClip = clipMinDistance(d3d, 10.0);
  const plLos = pathloss38901UmaLos(fcGhz, d2d, d3d, hBs, hUt);
  const plNlosP =
    13.54 + 39.08 * log10(d3dClip) + 20.0 * log10(fcGhz) - 0.6 * (hUt - 1.5);
  return Math.max(plLos, plNlosP);
};

const pathloss36777UmaAvLos = (fcGhz, d3d) => {
  const d3dClip = clipMinDistance(d3d, 10.0);
  return 28.0 + 22.0 * log10(d3dClip) + 20.0 * log10(fcGhz);
};

const pathloss36777UmaAvNlos = (fcGhz, d3d, hUt) => {
  const d3dClip = clipMinDistance(d3d, 10.0);
  return (
    -17.5 +
    (46.0 - 7.0 * log10(hUt)) * log10(d3dClip) +
    20.0 * log10((40.0 * Math.PI * fcGhz) / 3.0)
  );
};

const pathlossUmav = (fcGhz, d2d, d3d, hBs, hUt, isLos) => {
  if (hUt <= 22.5) {
    const plLos = pathloss38901UmaLos(fcGhz, d2d, d3d, hBs, hUt);
    const plNlos = pathloss38901UmaNlos(fcGhz, d2d, d3d, hBs, hUt);
    return isLos ? plLos : plNlos;
  }
  if (hUt <= 300.0) {
    const plLos = pathloss36777UmaAvLos(fcGhz, d3d);
    if (hUt <= 100.0) {
      const plNlos = pathloss36777UmaAvNlos(fcGhz, d3d, hUt);
      return isLos ? plLos : plNlos;
    }
    return plLos;
  }
  return NaN;
};

const rsrpProxyDbm = (pTxDbm, gTxDbi, gRxDbi, miscLossDb, pathlossDb) =>
  pTxDbm + gTxDbi + gRxDbi - pathlossDb - miscLossDb;

// ----------------------------
// [추가] 3GPP 스타일 안테나 방위각/다운틸트 적용 유틸
// ----------------------------

const wrapPi = (rad) => {
  let x = (rad + Math.PI) % (2 * Math.PI);
  if (x < 0) x += 2 * Math.PI;
  return x - Math.PI; // [-pi, pi)
};

/**
 * GCS(theta,phi) -> LCS(theta',phi') 변환
 * - theta: zenith angle [0..pi]
 * - phi: azimuth angle [-pi..pi]
 * - alpha: 섹터 방위각(boresight) [rad]
 * - beta: 다운틸트 [rad]
 */
const gcsToLcsAngles = (theta, phi, alpha, beta) => {
  const phiWrapped = wrapPi(phi);
  const dPhi = wrapPi(phiWrapped - alpha);

  const thetaPrime = Math.acos(
    Math.cos(beta) * Math.cos(theta) +
      Math.sin(beta) * Math.cos(dPhi) * Math.sin(theta)
  );

  const y = Math.sin(dPhi) * Math.sin(theta);
  const x =
    Math.cos(beta) * Math.sin(theta) * Math.cos(dPhi) -
    Math.sin(beta) * Math.cos(theta);
  const phiPrime = Math.atan2(y, x);

  return { thetaPrime, phiPrime };
};

/**
 * 3GPP 단일 요소(요소 패턴) 기반의 간단 이득 모델
 * - elementGainDb: 요소 최대 이득(예: 8 dBi)
 * - thetaPrime: LCS zenith [rad]
 * - phiPrime: LCS azimuth [rad]
 *
 * 여기서는 널리 쓰이는 3GPP 요소 패턴 형태(수평/수직 3dB 빔폭 65°, 최대 감쇠 30dB 계열)로 구현.
 */
const elementGain3gppDb = (thetaPrime, phiPrime, elementGainDb) => {
  const thetaDeg = thetaPrime / RAD; // rad -> deg
  const phiDeg = phiPrime / RAD;

  // 전형적인 3GPP 요소 패턴 파라미터(UMa/UMi 계열에서 널리 쓰이는 값)
  const THETA_3DB = 65.0;
  const PHI_3DB = 65.0;
  const SLA_V = 30.0;
  const A_MAX = 30.0;

  // Vertical attenuation (dB)
  const A_v = Math.min(SLA_V, 12.0 * ((thetaDeg - 90.0) / THETA_3DB) ** 2);

  // Horizontal attenuation (dB)
  const A_h = Math.min(A_MAX, 12.0 * (phiDeg / PHI_3DB) ** 2);

  // Total attenuation (dB)
  const A = Math.min(A_MAX, A_v + A_h);

  // Element gain (dBi)
  return (Number.isFinite(elementGainDb) ? elementGainDb : 8.0) - A;
};

// ----------------------------

const computeTransmission = (payload) => {
  const {
    id,
    bounds,
    gridSize,
    stations,
    ground,
    minDbm,
    maxDbm,
    radiusM,
    utHeightM,
    bsHeightM,
    fcGhz,
    pTxDbm,
    gTxDbi,
    gRxDbi,
    miscLossDb,
    losStepM,
  } = payload;

  const pixels = new Uint8ClampedArray(gridSize * gridSize * 4);
  if (!bounds || !stations || stations.length === 0) {
    return { id, gridSize, pixels };
  }

  const [westX, southY] = toMercator(bounds.west, bounds.south);
  const [eastX, northY] = toMercator(bounds.east, bounds.north);
  const width = eastX - westX;
  const height = northY - southY;
  if (
    !Number.isFinite(width) ||
    !Number.isFinite(height) ||
    width <= 0 ||
    height <= 0
  ) {
    return { id, gridSize, pixels };
  }
  const dx = width / gridSize;
  const dy = height / gridSize;
  const xCoords = new Float64Array(gridSize);
  const yCoords = new Float64Array(gridSize);
  for (let i = 0; i < gridSize; i += 1) {
    xCoords[i] = westX + (i + 0.5) * dx;
    yCoords[i] = northY - (i + 0.5) * dy;
  }

  const rsrpMax = new Float32Array(gridSize * gridSize);
  rsrpMax.fill(-Infinity);

  const heightUt = Number(utHeightM);
  const useLos = Number.isFinite(heightUt) && heightUt <= 100.0;
  const stepM =
    Number.isFinite(losStepM) && losStepM > 0 ? losStepM : Math.max(dx, dy);

  for (let i = 0; i < stations.length; i += 1) {
    const station = stations[i];
    if (!station) {
      continue;
    }
    const lon = Number(station.lon);
    const lat = Number(station.lat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      continue;
    }
    const [bsX, bsY] = toMercator(lon, lat);
    const bsGround = sampleGroundAt(
      bsX,
      bsY,
      ground,
      gridSize,
      westX,
      northY,
      dx,
      dy
    );
    const bsZ = (Number.isFinite(bsGround) ? bsGround : 0) + bsHeightM;
    const colStart = clamp(
      Math.floor((bsX - radiusM - westX) / dx),
      0,
      gridSize - 1
    );
    const colEnd = clamp(
      Math.ceil((bsX + radiusM - westX) / dx),
      0,
      gridSize - 1
    );
    const rowStart = clamp(
      Math.floor((northY - (bsY + radiusM)) / dy),
      0,
      gridSize - 1
    );
    const rowEnd = clamp(
      Math.ceil((northY - (bsY - radiusM)) / dy),
      0,
      gridSize - 1
    );

    for (let row = rowStart; row <= rowEnd; row += 1) {
      const dyM = yCoords[row] - bsY;
      const baseIndex = row * gridSize;
      for (let col = colStart; col <= colEnd; col += 1) {
        const dxM = xCoords[col] - bsX;
        const d2d = Math.hypot(dxM, dyM);
        if (!Number.isFinite(d2d) || d2d > radiusM) {
          continue;
        }
        const idx = baseIndex + col;
        const groundAlt = ground ? ground[idx] : 0;
        const utZ = (Number.isFinite(groundAlt) ? groundAlt : 0) + heightUt;
        const d3d = Math.hypot(d2d, utZ - bsZ);
        if (!Number.isFinite(d3d) || d3d <= 0) {
          continue;
        }

        let los = true;
        if (useLos && ground) {
          los = isLosTerrain(
            { x: bsX, y: bsY, z: bsZ },
            { x: xCoords[col], y: yCoords[row], z: utZ },
            ground,
            gridSize,
            westX,
            northY,
            dx,
            dy,
            stepM,
            0.0
          );
        }

        const pl = pathlossUmav(fcGhz, d2d, d3d, bsHeightM, heightUt, los);
        if (!Number.isFinite(pl)) {
          continue;
        }

        const dz = utZ - bsZ;

        // GCS 각도 정의: theta(zenith)=[0..pi], phi(azimuth)=[-pi..pi]
        const theta = Math.acos(clamp(dz / d3d, -1, 1));
        const phi = Math.atan2(dyM, dxM);

        const sectorAzDeg = Number(station.sectorAzDeg);
        const downtiltDeg = Number(station.downtiltDeg);
        const elementGainDb = Number(station.elementGainDb);

        const alpha = Number.isFinite(sectorAzDeg) ? sectorAzDeg * RAD : 0;
        const beta = Number.isFinite(downtiltDeg) ? downtiltDeg * RAD : 0;

        const { thetaPrime, phiPrime } = gcsToLcsAngles(
          theta,
          phi,
          alpha,
          beta
        );
        const gTxDbiLocal = elementGain3gppDb(
          thetaPrime,
          phiPrime,
          Number.isFinite(elementGainDb) ? elementGainDb : 8
        );

        // 기존 gTxDbi는 payload로 유지(호환), 실제 계산은 gTxDbiLocal 사용
        const rsrp = rsrpProxyDbm(pTxDbm, gTxDbiLocal, gRxDbi, miscLossDb, pl);
        if (rsrp > rsrpMax[idx]) {
          rsrpMax[idx] = rsrp;
        }
      }
    }
  }

  const minValue = Number.isFinite(minDbm) ? minDbm : -120;
  const maxValue =
    Number.isFinite(maxDbm) && maxDbm > minValue ? maxDbm : minValue + 40;
  const range = maxValue - minValue || 1;

  for (let idx = 0; idx < rsrpMax.length; idx += 1) {
    const value = rsrpMax[idx];
    const offset = idx * 4;
    if (!Number.isFinite(value) || value <= minValue) {
      pixels[offset + 3] = 0;
      continue;
    }
    const t = clamp((value - minValue) / range, 0, 1);
    const color = sampleRamp(t);
    pixels[offset] = color[0];
    pixels[offset + 1] = color[1];
    pixels[offset + 2] = color[2];
    pixels[offset + 3] = 190;
  }

  return { id, gridSize, pixels };
};

self.onmessage = (event) => {
  const payload = event.data;
  if (!payload || payload.type !== "compute") {
    return;
  }
  const result = computeTransmission(payload);
  if (!result || !result.pixels) {
    return;
  }
  self.postMessage(
    {
      type: "result",
      id: result.id,
      gridSize: result.gridSize,
      pixels: result.pixels,
    },
    [result.pixels.buffer]
  );
};
