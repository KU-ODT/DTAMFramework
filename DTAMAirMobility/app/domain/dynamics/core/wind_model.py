"""UAM Flight Simulator — 3-D Perlin-noise wind field model.

Extracted and self-contained from the UATM sample project.
Provides spatially-and-temporally varying wind vectors for realistic
UAM flight trajectory perturbation.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import List, Tuple

# ── Earth constants (Mercator helpers) ──────────────────────────
R_EARTH_M = 6_378_137.0
DEG2RAD = math.pi / 180.0


def _lon_to_x(lon_deg: float) -> float:
    return R_EARTH_M * lon_deg * DEG2RAD


def _lat_to_y(lat_deg: float) -> float:
    rad = lat_deg * DEG2RAD
    return R_EARTH_M * math.log(math.tan(math.pi / 4 + rad / 2))


# ── Deterministic PRNG (Mulberry32) ────────────────────────────
def _mulberry32(seed: int):
    a = seed & 0xFFFFFFFF
    def rand() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = (a ^ (a >> 15)) * (1 | a) & 0xFFFFFFFF
        t = (t + ((t ^ (t >> 7)) * (61 | t) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
    return rand


# ── 3-D Perlin noise ───────────────────────────────────────────
class Perlin3:
    def __init__(self, seed: int = 1337) -> None:
        rand = _mulberry32(seed)
        p = list(range(256))
        for i in range(255, -1, -1):
            j = int(rand() * (i + 1))
            p[i], p[j] = p[j], p[i]
        self.perm = [p[i & 255] for i in range(512)]

    @staticmethod
    def fade(t: float) -> float:
        return t * t * t * (t * (t * 6 - 15) + 10)

    @staticmethod
    def lerp(a: float, b: float, t: float) -> float:
        return a + t * (b - a)

    @staticmethod
    def grad(h: int, x: float, y: float, z: float) -> float:
        h &= 15
        u = x if h < 8 else y
        v = y if h < 4 else (x if h in (12, 14) else z)
        a = u if (h & 1) == 0 else -u
        b = v if (h & 2) == 0 else -v
        return a + b

    def noise(self, x: float, y: float, z: float) -> float:
        X = math.floor(x) & 255
        Y = math.floor(y) & 255
        Z = math.floor(z) & 255
        xf = x - math.floor(x)
        yf = y - math.floor(y)
        zf = z - math.floor(z)
        u = self.fade(xf)
        v = self.fade(yf)
        w = self.fade(zf)
        A = self.perm[X] + Y
        AA = self.perm[A] + Z
        AB = self.perm[A + 1] + Z
        B = self.perm[X + 1] + Y
        BA = self.perm[B] + Z
        BB = self.perm[B + 1] + Z
        x1 = self.lerp(self.grad(self.perm[AA], xf, yf, zf),
                        self.grad(self.perm[BA], xf - 1, yf, zf), u)
        x2 = self.lerp(self.grad(self.perm[AB], xf, yf - 1, zf),
                        self.grad(self.perm[BB], xf - 1, yf - 1, zf), u)
        y1 = self.lerp(x1, x2, v)
        x3 = self.lerp(self.grad(self.perm[AA + 1], xf, yf, zf - 1),
                        self.grad(self.perm[BA + 1], xf - 1, yf, zf - 1), u)
        x4 = self.lerp(self.grad(self.perm[AB + 1], xf, yf - 1, zf - 1),
                        self.grad(self.perm[BB + 1], xf - 1, yf - 1, zf - 1), u)
        y2 = self.lerp(x3, x4, v)
        return self.lerp(y1, y2, w)


def _fbm(perlin: Perlin3, x: float, y: float, z: float,
         octaves: int = 4, lacunarity: float = 2.0, gain: float = 0.5) -> float:
    amp = 0.5
    freq = 1.0
    total = 0.0
    norm = 0.0
    for _ in range(octaves):
        total += amp * perlin.noise(x * freq, y * freq, z * freq)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / max(1e-9, norm)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ── Wind vector output ─────────────────────────────────────────
@dataclass
class WindVector:
    u: float           # east component (m/s)
    v: float           # north component (m/s)
    speed: float       # magnitude (m/s)
    dir_to_deg: float  # wind blowing toward (0=N)
    dir_from_deg: float


# ── Local wind zone (weather patch) ────────────────────────────
@dataclass
class LocalWindZone:
    xm: float
    ym: float
    radius_m: float
    base_severity: float
    min_speed: float
    max_speed: float
    strength: float = 0.0
    target_strength: float = 1.0


# ── Main wind model ────────────────────────────────────────────
class WindModel:
    """3-D Perlin-noise wind field with seasonal, diurnal, and local
    weather-zone modulation.  Deterministic for a given seed + sim-time."""

    def __init__(
        self,
        seed: int = 20260121,
        time_speed: float = 60.0,
        preset: str = "good",
        start_local_hour: float = 9.0,
    ) -> None:
        self.seed = seed
        self.perlin = Perlin3(seed)
        self.time_speed = float(time_speed)
        self.preset = preset
        self.base_severity, self.range_min, self.range_max = self._preset_config(preset)
        self.start_local_hour = float(start_local_hour)
        self.local_zones: List[LocalWindZone] = []
        self.river_y = _lat_to_y(37.53)  # Han river latitude

    # ── Presets ──
    @staticmethod
    def _preset_config(preset: str) -> Tuple[float, float, float]:
        if preset == "good":
            return 0.25, 1.0, 3.0
        if preset == "fair":
            return 0.52, 1.0, 5.0
        if preset == "bad":
            return 0.78, 3.0, 10.0
        if preset == "serious":
            return 0.9, 5.0, 12.0
        return 0.52, 1.0, 5.0

    def set_preset(self, preset: str) -> None:
        self.preset = preset
        self.base_severity, self.range_min, self.range_max = self._preset_config(preset)

    # ── Local zones ──
    def add_local_zone(self, lon_deg: float, lat_deg: float,
                       radius_m: float, preset: str) -> None:
        if radius_m <= 0:
            return
        base, mn, mx = self._preset_config(preset)
        if preset == "bad":
            base = min(1.0, base + 0.12); mn += 2.0; mx += 3.0
        elif preset == "serious":
            base = min(1.0, base + 0.18); mn += 5.0; mx = min(15.0, mx + 6.0)
        self.local_zones.append(LocalWindZone(
            xm=_lon_to_x(lon_deg), ym=_lat_to_y(lat_deg),
            radius_m=float(radius_m), base_severity=base,
            min_speed=mn, max_speed=mx, strength=1.0,
        ))

    def clear_local_zones(self) -> None:
        self.local_zones.clear()

    def _local_config_at(self, xm: float, ym: float) -> Tuple[float, float, float]:
        base = self.base_severity
        mn = self.range_min
        mx = self.range_max
        if not self.local_zones:
            return base, mn, mx
        tw = 0.0; bs = 0.0; mns = 0.0; mxs = 0.0
        for z in self.local_zones:
            d = math.hypot(xm - z.xm, ym - z.ym)
            if d >= z.radius_m:
                continue
            t = _clamp(1.0 - d / z.radius_m, 0.0, 1.0)
            w = t * t * (3.0 - 2.0 * t) * z.strength
            if w <= 0.0:
                continue
            tw += w; bs += w * z.base_severity; mns += w * z.min_speed; mxs += w * z.max_speed
        if tw > 0.0:
            denom = 1.0 + tw
            base = (base + bs) / denom
            mn = (mn + mns) / denom
            mx = (mx + mxs) / denom
        return base, mn, mx

    # ── Seasonal / diurnal ──
    @staticmethod
    def _seasonal_base(month: int) -> Tuple[float, float]:
        if month in (12, 1, 2):
            return 135.0, 6.0
        if 3 <= month <= 5:
            return 95.0, 4.6
        if 6 <= month <= 8:
            return 10.0, 3.8
        return 125.0, 5.2

    @staticmethod
    def _diurnal_factor(local_hour: float) -> float:
        x = (local_hour - 14.0) / 24.0 * (2.0 * math.pi)
        return 0.85 + 0.25 * math.cos(x)

    def _severity(self, sim_s: float) -> float:
        slow = _fbm(self.perlin, 0.0, 0.0, sim_s * 0.00008, 4, 2.0, 0.5)
        mid = self.perlin.noise(120.5, -77.3, sim_s * 0.00025)
        pulse = math.sin(sim_s * (2.0 * math.pi) / (60.0 * 35.0))
        return _clamp(self.base_severity + 0.22 * slow + 0.1 * mid + 0.08 * pulse, 0.0, 1.0)

    # ── Curl-noise helpers ──
    def _psi(self, xm: float, ym: float, sim_s: float,
             scale: float, t_scale: float, octaves: int) -> float:
        return _fbm(self.perlin, xm * scale, ym * scale, sim_s * t_scale, octaves, 2.0, 0.5)

    def _perp_grad(self, xm: float, ym: float, sim_s: float,
                   scale: float, t_scale: float, octaves: int,
                   delta_m: float) -> Tuple[float, float]:
        pn = self._psi(xm, ym + delta_m, sim_s, scale, t_scale, octaves)
        ps = self._psi(xm, ym - delta_m, sim_s, scale, t_scale, octaves)
        pe = self._psi(xm + delta_m, ym, sim_s, scale, t_scale, octaves)
        pw = self._psi(xm - delta_m, ym, sim_s, scale, t_scale, octaves)
        return (pn - ps) / (2.0 * delta_m), -(pe - pw) / (2.0 * delta_m)

    # ── Public API ──────────────────────────────────────────────
    def wind_at(self, lon_deg: float, lat_deg: float,
                sim_elapsed_s: float, month: int = 4) -> WindVector:
        """Compute wind vector at a geographic point and simulation time.

        Args:
            lon_deg, lat_deg: geographic position
            sim_elapsed_s: seconds since simulation start
            month: calendar month (1-12) for seasonal modulation
        """
        sim_s = sim_elapsed_s * self.time_speed
        xm = _lon_to_x(lon_deg)
        ym = _lat_to_y(lat_deg)

        dir_to_deg, speed_mean = self._seasonal_base(month)
        local_hour = (self.start_local_hour + sim_s / 3600.0) % 24.0
        mix = self._diurnal_factor(local_hour)

        base_sev, mn, mx = self._local_config_at(xm, ym)
        sev = self._severity(sim_s)
        sev = _clamp(base_sev + (sev - self.base_severity), 0.0, 1.0)

        dir_jitter = (12.0 + 30.0 * sev) * self.perlin.noise(55.1, 9.7, sim_s * 0.0004)
        space_jitter = 10.0 * _fbm(self.perlin, xm / 18000.0, ym / 18000.0,
                                     sim_s * 0.00018, 3, 2.0, 0.5)
        dir_to_deg += dir_jitter + space_jitter

        mean_base = speed_mean * (0.70 + 0.95 * sev) * mix
        mean_target = _lerp(mn, mx, sev) * mix
        speed_scale = mean_target / max(0.1, mean_base)
        mean = mean_base * speed_scale

        band = (0.6 + 2.4 * sev) * _fbm(
            self.perlin, xm / 12000.0, ym / 12000.0,
            sim_s * 0.00022, 3, 2.0, 0.5) * speed_scale
        speed0 = max(0.1, mean + band)

        rad = math.radians(dir_to_deg)
        u = math.sin(rad) * speed0
        v = math.cos(rad) * speed0

        g1u, g1v = self._perp_grad(xm, ym, sim_s, 1 / 4200.0, 0.00018, 4, 80)
        amp1 = _lerp(1800.0, 9000.0, sev) * speed_scale
        u += g1u * amp1; v += g1v * amp1

        g2u, g2v = self._perp_grad(xm, ym, sim_s, 1 / 1100.0, 0.00055, 3, 45)
        amp2 = _lerp(500.0, 2600.0, sev) * (0.7 + 0.6 * mix) * speed_scale
        u += g2u * amp2; v += g2v * amp2

        sp = math.hypot(u, v)
        ux = u / max(1e-6, sp)
        vx = v / max(1e-6, sp)
        gust = self.perlin.noise(xm / 350.0, ym / 350.0, sim_s * 0.0016)
        gust_amp = _lerp(0.4, 3.8, sev) * speed_scale
        u += ux * gust * gust_amp; v += vx * gust * gust_amp

        # Han river enhancement
        dy = ym - self.river_y
        river_factor = math.exp(-(dy / 1200.0) ** 2)
        river_amp = _lerp(0.0, 1.8, sev) * speed_scale
        east_sign = 1.0 if math.sin(rad) >= 0.0 else -1.0
        u += river_factor * river_amp * east_sign

        max_spd = _lerp(18.0, 35.0, sev) * speed_scale
        speed_final = math.hypot(u, v)
        if speed_final > max_spd:
            k = max_spd / max(1e-6, speed_final)
            u *= k; v *= k
            speed_final = max_spd

        dt = (math.degrees(math.atan2(u, v)) + 360.0) % 360.0
        df = (dt + 180.0) % 360.0
        return WindVector(u=u, v=v, speed=speed_final, dir_to_deg=dt, dir_from_deg=df)
