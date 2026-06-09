"""
VFDS Dynamics Dispatch System — Telemetry Normalizer

ICD MSG 4001 포맷의 NED(m) 데이터를 VFDS 대시보드용 LLA로 변환한다.
각 기체별 HOME 좌표를 참조하여 변환하며, HOME이 없는 경우 기본값을 사용한다.
"""

from __future__ import annotations

import math
from typing import Any

# 기본 HOME (레지스트리에 없는 기체용 폴백)
DEFAULT_HOME = {"lat": 37.525680, "lon": 126.922050, "alt": 0.0}

# 기체별 HOME 좌표 저장소 — 서버 시작 시 registry에서 주입됨
_aircraft_homes: dict[str, dict[str, float]] = {}


def register_home(aircraft_id: str, lat: float, lon: float, alt: float) -> None:
    """기체별 HOME 좌표를 등록한다."""
    _aircraft_homes[aircraft_id] = {"lat": lat, "lon": lon, "alt": alt}


def get_home(aircraft_id: str) -> dict[str, float]:
    """기체의 HOME 좌표를 반환한다."""
    return _aircraft_homes.get(aircraft_id, DEFAULT_HOME)


class TelemetryNormalizer:
    @staticmethod
    def normalize_4001(aircraft_id: str, vehicle_data: dict[str, Any], timestamp: str) -> dict[str, Any]:
        """
        ICD MSG 4001 비행체 하위 구조를 VFDS 정규형으로 변환한다.

        Args:
            aircraft_id: 비행체 ID (e.g. "UAM0001")
            vehicle_data: MSG 4001의 비행체 하위 딕셔너리
            timestamp: 원본 timestamp (ISO-8601)

        Returns:
            AircraftStatus 모델에 맞는 정규화된 딕셔너리
        """
        home = get_home(aircraft_id)

        # 1. Position: NED(m) → LLA
        pos_raw = vehicle_data.get("position", {})
        n_m = float(pos_raw.get("north", 0.0))
        e_m = float(pos_raw.get("east", 0.0))
        d_m = float(pos_raw.get("down", 0.0))

        lat, lon, alt = TelemetryNormalizer._ned_to_lla(
            n_m, e_m, d_m,
            home["lat"], home["lon"], home["alt"],
        )

        # 2. Attitude: ICD는 rad 단위 — 그대로 전달
        att_raw = vehicle_data.get("attitude", {})

        # 3. Actuator: ICD §2.3
        act_raw = vehicle_data.get("actuator", {})

        # 4. Propulsion: motor_rpm list
        prop_raw = vehicle_data.get("propulsion", {})
        motor_rpm = list(prop_raw.get("motor_rpm", [0.0, 0.0, 0.0, 0.0]))
        # 4개 미만이면 패딩
        while len(motor_rpm) < 4:
            motor_rpm.append(0.0)

        return {
            "aircraftId": aircraft_id,
            "flightPlanNumber": 0,
            "ts": timestamp,
            "missionState": "WAITING",
            "phase": "N/A",
            "seq": 0,
            "position": {
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "north": n_m,
                "east": e_m,
                "down": d_m,
            },
            "attitude": {
                "roll": float(att_raw.get("roll", 0.0)),
                "pitch": float(att_raw.get("pitch", 0.0)),
                "yaw": float(att_raw.get("yaw", 0.0)),
            },
            "actuator": {
                "tilt_left": float(act_raw.get("tilt_left", 0.0)),
                "tilt_right": float(act_raw.get("tilt_right", 0.0)),
                "aileron": float(act_raw.get("aileron", 0.0)),
                "rudder_left": float(act_raw.get("rudder_left", 0.0)),
                "rudder_right": float(act_raw.get("rudder_right", 0.0)),
            },
            "motorRpm": motor_rpm,
        }

    @staticmethod
    def _ned_to_lla(
        n_m: float, e_m: float, d_m: float,
        home_lat: float, home_lon: float, home_alt: float,
    ) -> tuple[float, float, float]:
        """
        Local NED (meters) → WGS84 LLA 변환.
        R = 6378137.0 (WGS84 준거타원체 장반경)
        """
        R = 6378137.0

        d_lat = n_m / R
        d_lon = e_m / (R * math.cos(math.pi * home_lat / 180.0))

        lat_deg = home_lat + (d_lat * 180.0 / math.pi)
        lon_deg = home_lon + (d_lon * 180.0 / math.pi)
        alt_m = home_alt - d_m  # NED down은 음수가 상승

        return lat_deg, lon_deg, alt_m

    @staticmethod
    def normalize(aircraft_id: str, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        레거시 호환: 기존 Reporter HTTP 텔레메트리 데이터를 정규화한다.
        Reporter가 이미 LLA로 보내주므로 position 변환은 불필요.
        """
        pos = raw_data.get("position", {})
        att = raw_data.get("attitude", {})
        vel = raw_data.get("velocityNed", {})
        act = raw_data.get("actuator", {})
        motor_rpm = raw_data.get("motorRpm", [0.0, 0.0, 0.0, 0.0])

        return {
            "aircraftId": aircraft_id,
            "flightPlanNumber": raw_data.get("flightPlanNumber", 0),
            "ts": raw_data.get("ts", ""),
            "missionState": raw_data.get("missionState", "EXECUTING"),
            "phase": raw_data.get("phase", "N/A"),
            "seq": raw_data.get("seq", 0),
            "position": {
                "lat": float(pos.get("lat", 0.0)),
                "lon": float(pos.get("lon", 0.0)),
                "alt": float(pos.get("alt", 0.0)),
                "north": float(pos.get("north", 0.0)),
                "east": float(pos.get("east", 0.0)),
                "down": float(pos.get("down", 0.0)),
            },
            "attitude": {
                "roll": float(att.get("roll", 0.0)),
                "pitch": float(att.get("pitch", 0.0)),
                "yaw": float(att.get("yaw", 0.0)),
            },
            "velocityNed": {
                "north": float(vel.get("north", 0.0)),
                "east": float(vel.get("east", 0.0)),
                "down": float(vel.get("down", 0.0)),
            },
            "actuator": {
                "tilt_left": float(act.get("tilt_left", 0.0)),
                "tilt_right": float(act.get("tilt_right", 0.0)),
                "aileron": float(act.get("aileron", 0.0)),
                "rudder_left": float(act.get("rudder_left", 0.0)),
                "rudder_right": float(act.get("rudder_right", 0.0)),
            },
            "motorRpm": motor_rpm,
        }
