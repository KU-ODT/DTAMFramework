from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
import time

R_EARTH_M = 6378137.0
DEG2RAD = math.pi / 180.0


def lon_to_x(lon_deg: float) -> float:
    return R_EARTH_M * lon_deg * DEG2RAD


def lat_to_y(lat_deg: float) -> float:
    rad = lat_deg * DEG2RAD
    return R_EARTH_M * math.log(math.tan(math.pi / 4 + rad / 2))


def _mulberry32(seed: int):
    a = seed & 0xFFFFFFFF

    def rand() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = (a ^ (a >> 15)) * (1 | a) & 0xFFFFFFFF
        t = (t + ((t ^ (t >> 7)) * (61 | t) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rand


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

        x1 = self.lerp(
            self.grad(self.perm[AA], xf, yf, zf),
            self.grad(self.perm[BA], xf - 1, yf, zf),
            u,
        )
        x2 = self.lerp(
            self.grad(self.perm[AB], xf, yf - 1, zf),
            self.grad(self.perm[BB], xf - 1, yf - 1, zf),
            u,
        )
        y1 = self.lerp(x1, x2, v)

        x3 = self.lerp(
            self.grad(self.perm[AA + 1], xf, yf, zf - 1),
            self.grad(self.perm[BA + 1], xf - 1, yf, zf - 1),
            u,
        )
        x4 = self.lerp(
            self.grad(self.perm[AB + 1], xf, yf - 1, zf - 1),
            self.grad(self.perm[BB + 1], xf - 1, yf - 1, zf - 1),
            u,
        )
        y2 = self.lerp(x3, x4, v)

        return self.lerp(y1, y2, w)


def fbm(
    perlin: Perlin3,
    x: float,
    y: float,
    z: float,
    octaves: int = 4,
    lacunarity: float = 2.0,
    gain: float = 0.5,
) -> float:
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


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass
class WindVector:
    u: float
    v: float
    speed: float
    dir_to_deg: float
    dir_from_deg: float


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


class WindModel:
    def __init__(
        self,
        seed: int = 20260121,
        time_speed: float = 60.0,
        preset: str = "good",
        start_local_hour: float = 0.0,
        transition_tau: float = 2.2,
        local_fade_tau: float = 2.0,
    ) -> None:
        self.seed = seed
        self.perlin = Perlin3(seed)
        self.time_speed = float(time_speed)
        self.preset = preset
        self.base_severity = 0.25
        self.base_severity_target = self.base_severity
        self.range_min = 1.0
        self.range_max = 3.0
        self.range_min_target = self.range_min
        self.range_max_target = self.range_max
        self.transition_tau = max(0.1, float(transition_tau))
        self.last_transition_real_s = time.perf_counter()
        self.local_zones: list[LocalWindZone] = []
        self.local_fade_tau = max(0.1, float(local_fade_tau))
        self.last_local_real_s = time.perf_counter()
        self.set_preset(preset)
        self.start_local_hour = float(start_local_hour)
        self.river_y = lat_to_y(37.53)

    def preset_config(self, preset: str) -> tuple[float, float, float]:
        if preset == "good":
            return 0.25, 1.0, 3.0
        if preset == "fair":
            return 0.52, 1.0, 5.0
        if preset == "bad":
            return 0.78, 3.0, 10.0
        if preset == "serious":
            return 0.9, 5.0, 12.0
        return 0.52, 1.0, 5.0

    def local_preset_config(self, preset: str) -> tuple[float, float, float]:
        base, min_speed, max_speed = self.preset_config(preset)
        if preset == "bad":
            return min(1.0, base + 0.12), min_speed + 2.0, max_speed + 3.0
        if preset == "serious":
            return min(1.0, base + 0.18), min_speed + 5.0, min(15.0, max_speed + 6.0)
        return base, min_speed, max_speed

    def set_preset(self, preset: str) -> None:
        self.preset = preset
        base, min_speed, max_speed = self.preset_config(preset)
        self.base_severity_target = base
        self.range_min_target = min_speed
        self.range_max_target = max_speed

    def speed_range(self) -> tuple[float, float]:
        return self.range_min, self.range_max

    def set_transition_tau(self, tau: float) -> None:
        if math.isfinite(tau) and tau > 0:
            self.transition_tau = float(tau)

    def set_local_fade_tau(self, tau: float) -> None:
        if math.isfinite(tau) and tau > 0:
            self.local_fade_tau = float(tau)

    def _update_transitions(self, real_s: float | None = None) -> None:
        now_real_s = real_s if real_s is not None else time.perf_counter()
        dt = max(0.0, now_real_s - self.last_transition_real_s)
        self.last_transition_real_s = now_real_s
        alpha = 1.0 - math.exp(-dt / max(0.1, self.transition_tau))
        self.base_severity += (self.base_severity_target - self.base_severity) * alpha
        self.range_min += (self.range_min_target - self.range_min) * alpha
        self.range_max += (self.range_max_target - self.range_max) * alpha

    def _update_local_zones(self, real_s: float | None = None) -> None:
        now_real_s = real_s if real_s is not None else time.perf_counter()
        dt = max(0.0, now_real_s - self.last_local_real_s)
        self.last_local_real_s = now_real_s
        alpha = 1.0 - math.exp(-dt / max(0.1, self.local_fade_tau))
        for idx in range(len(self.local_zones) - 1, -1, -1):
            zone = self.local_zones[idx]
            zone.strength += (zone.target_strength - zone.strength) * alpha
            if zone.target_strength == 0.0 and zone.strength < 0.02:
                self.local_zones.pop(idx)

    def add_local_zone(self, lon_deg: float, lat_deg: float, radius_m: float, preset: str) -> None:
        if radius_m <= 0:
            return
        base, min_speed, max_speed = self.local_preset_config(preset)
        xm = lon_to_x(lon_deg)
        ym = lat_to_y(lat_deg)
        self.local_zones.append(
            LocalWindZone(
                xm=xm,
                ym=ym,
                radius_m=float(radius_m),
                base_severity=base,
                min_speed=min_speed,
                max_speed=max_speed,
            )
        )

    def clear_local_zones(self) -> None:
        for zone in self.local_zones:
            zone.target_strength = 0.0

    def local_config_at(
        self,
        xm: float,
        ym: float,
        sim_s: float,
        real_s: float | None = None,
    ) -> tuple[float, float, float]:
        self._update_transitions(real_s)
        self._update_local_zones(real_s)
        base = self.base_severity
        min_speed = self.range_min
        max_speed = self.range_max
        if not self.local_zones:
            return base, min_speed, max_speed
        total_w = 0.0
        base_sum = 0.0
        min_sum = 0.0
        max_sum = 0.0
        for zone in self.local_zones:
            dx = xm - zone.xm
            dy = ym - zone.ym
            dist = math.hypot(dx, dy)
            if dist >= zone.radius_m:
                continue
            t = clamp(1.0 - (dist / zone.radius_m), 0.0, 1.0)
            smooth = t * t * (3.0 - 2.0 * t)
            w = smooth * zone.strength
            if w <= 0.0:
                continue
            total_w += w
            base_sum += w * zone.base_severity
            min_sum += w * zone.min_speed
            max_sum += w * zone.max_speed
        if total_w > 0.0:
            denom = 1.0 + total_w
            base = (base + base_sum) / denom
            min_speed = (min_speed + min_sum) / denom
            max_speed = (max_speed + max_sum) / denom
        return base, min_speed, max_speed

    @staticmethod
    def seasonal_base(month_index0: int) -> tuple[float, float]:
        m = month_index0 + 1
        if m in (12, 1, 2):
            return 135.0, 6.0
        if 3 <= m <= 5:
            return 95.0, 4.6
        if 6 <= m <= 8:
            return 10.0, 3.8
        return 125.0, 5.2

    @staticmethod
    def diurnal_factor(local_hour: float) -> float:
        x = (local_hour - 14.0) / 24.0 * (2.0 * math.pi)
        return 0.85 + 0.25 * math.cos(x)

    def severity(self, sim_s: float) -> float:
        slow = fbm(self.perlin, 0.0, 0.0, sim_s * 0.00008, 4, 2.0, 0.5)
        mid = self.perlin.noise(120.5, -77.3, sim_s * 0.00025)
        pulse = math.sin(sim_s * (2.0 * math.pi) / (60.0 * 35.0))
        return clamp(self.base_severity + 0.22 * slow + 0.1 * mid + 0.08 * pulse, 0.0, 1.0)

    def psi(
        self,
        xm: float,
        ym: float,
        sim_s: float,
        scale: float,
        t_scale: float,
        octaves: int,
    ) -> float:
        return fbm(self.perlin, xm * scale, ym * scale, sim_s * t_scale, octaves, 2.0, 0.5)

    def perp_grad(
        self,
        xm: float,
        ym: float,
        sim_s: float,
        scale: float,
        t_scale: float,
        octaves: int,
        delta_m: float,
    ) -> tuple[float, float]:
        p_n = self.psi(xm, ym + delta_m, sim_s, scale, t_scale, octaves)
        p_s = self.psi(xm, ym - delta_m, sim_s, scale, t_scale, octaves)
        p_e = self.psi(xm + delta_m, ym, sim_s, scale, t_scale, octaves)
        p_w = self.psi(xm - delta_m, ym, sim_s, scale, t_scale, octaves)

        dpsi_dy = (p_n - p_s) / (2.0 * delta_m)
        dpsi_dx = (p_e - p_w) / (2.0 * delta_m)
        return dpsi_dy, -dpsi_dx

    def wind_at_mercator(self, xm: float, ym: float, sim_elapsed_s: float) -> WindVector:
        sim_s = sim_elapsed_s * self.time_speed
        real_s = time.perf_counter()
        now = datetime.now()
        dir_to_deg, speed_mean = self.seasonal_base(now.month - 1)
        local_hour = (self.start_local_hour + sim_s / 3600.0) % 24.0
        mix = self.diurnal_factor(local_hour)

        base_sev, min_speed, max_speed = self.local_config_at(xm, ym, sim_s, real_s)
        sev = self.severity(sim_s)
        sev = clamp(base_sev + (sev - self.base_severity), 0.0, 1.0)

        dir_jitter = (12.0 + 30.0 * sev) * self.perlin.noise(55.1, 9.7, sim_s * 0.0004)
        space_jitter = 10.0 * fbm(
            self.perlin,
            xm * (1.0 / 18000.0),
            ym * (1.0 / 18000.0),
            sim_s * 0.00018,
            3,
            2.0,
            0.5,
        )
        dir_to_deg = dir_to_deg + dir_jitter + space_jitter

        mean_base = speed_mean * (0.70 + 0.95 * sev) * mix
        mean_target = lerp(min_speed, max_speed, sev) * mix
        speed_scale = mean_target / max(0.1, mean_base)
        mean = mean_base * speed_scale

        band = (0.6 + 2.4 * sev) * fbm(
            self.perlin,
            xm * (1.0 / 12000.0),
            ym * (1.0 / 12000.0),
            sim_s * 0.00022,
            3,
            2.0,
            0.5,
        ) * speed_scale

        speed0 = max(0.1, mean + band)

        rad = math.radians(dir_to_deg)
        u = math.sin(rad) * speed0
        v = math.cos(rad) * speed0

        g1_u, g1_v = self.perp_grad(xm, ym, sim_s, 1.0 / 4200.0, 0.00018, 4, 80)
        amp1 = lerp(1800.0, 9000.0, sev) * speed_scale
        u += g1_u * amp1
        v += g1_v * amp1

        g2_u, g2_v = self.perp_grad(xm, ym, sim_s, 1.0 / 1100.0, 0.00055, 3, 45)
        amp2 = lerp(500.0, 2600.0, sev) * (0.7 + 0.6 * mix) * speed_scale
        u += g2_u * amp2
        v += g2_v * amp2

        sp = math.hypot(u, v)
        ux = u / max(1e-6, sp)
        vx = v / max(1e-6, sp)
        gust = self.perlin.noise(xm * (1.0 / 350.0), ym * (1.0 / 350.0), sim_s * 0.0016)
        gust_amp = lerp(0.4, 3.8, sev) * speed_scale
        u += ux * gust * gust_amp
        v += vx * gust * gust_amp

        dy = ym - self.river_y
        river_factor = math.exp(-math.pow(dy / 1200.0, 2))
        river_amp = lerp(0.0, 1.8, sev) * speed_scale
        east_sign = 1.0 if math.sin(rad) >= 0.0 else -1.0
        u += river_factor * river_amp * east_sign

        max_speed = lerp(18.0, 35.0, sev) * speed_scale
        speed_final = math.hypot(u, v)
        if speed_final > max_speed:
            k = max_speed / max(1e-6, speed_final)
            u *= k
            v *= k
            speed_final = max_speed

        dir_to = (math.degrees(math.atan2(u, v)) + 360.0) % 360.0
        dir_from = (dir_to + 180.0) % 360.0
        return WindVector(u=u, v=v, speed=speed_final, dir_to_deg=dir_to, dir_from_deg=dir_from)

    def wind_at(self, lon_deg: float, lat_deg: float, sim_elapsed_s: float) -> WindVector:
        xm = lon_to_x(lon_deg)
        ym = lat_to_y(lat_deg)
        return self.wind_at_mercator(xm, ym, sim_elapsed_s)
