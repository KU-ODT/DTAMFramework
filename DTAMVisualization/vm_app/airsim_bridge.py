"""AirSim/Unreal 단독 통신 창구.

cosysairsim Python 클라이언트를 래핑한다. DTAM 쪽 통신과 명확히 분리되어
있으며, 이 클래스만 AirSim RPC 호출을 직접 수행한다.

주요 기능:
 - connect / disconnect / ping
 - 차량 pose 업데이트 (4001 → simSetVehiclePose)
 - 날씨 효과 (1002 → simSetWeatherParameter)
 - 카메라 프레임 캡처 (→ 4101 송신용)
 - 시뮬레이션 reset

Thread-safe: 여러 스레드(송신 스레드 + REST 요청)가 동시에 호출 가능.
"""
from __future__ import annotations

import json
import logging
import math
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from cosysairsim.client import VehicleClient  # type: ignore
    from cosysairsim.types import (  # type: ignore
        Pose,
        Quaternionr,
        Vector3r,
        WeatherParameter,
    )
    _COSYSAIRSIM_IMPORT_ERROR: Optional[BaseException] = None
except Exception as exc:  # pragma: no cover - exercised on hosts without AirSim SDK
    _COSYSAIRSIM_IMPORT_ERROR = exc

    class VehicleClient:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError(f"cosysairsim is unavailable: {_COSYSAIRSIM_IMPORT_ERROR}")

    class Vector3r:  # type: ignore[no-redef]
        def __init__(self, x_val: float = 0.0, y_val: float = 0.0, z_val: float = 0.0) -> None:
            self.x_val = float(x_val)
            self.y_val = float(y_val)
            self.z_val = float(z_val)

    class Quaternionr:  # type: ignore[no-redef]
        def __init__(
            self,
            x_val: float = 0.0,
            y_val: float = 0.0,
            z_val: float = 0.0,
            w_val: float = 1.0,
        ) -> None:
            self.x_val = float(x_val)
            self.y_val = float(y_val)
            self.z_val = float(z_val)
            self.w_val = float(w_val)

    class Pose:  # type: ignore[no-redef]
        def __init__(
            self,
            position: Optional[Vector3r] = None,
            orientation: Optional[Quaternionr] = None,
        ) -> None:
            self.position = position or Vector3r()
            self.orientation = orientation or Quaternionr()

    class WeatherParameter:  # type: ignore[no-redef]
        Rain = 0
        Snow = 1
        Dust = 2

from .config import AirSimConfig, FRAMEWORK_ROOT

logger = logging.getLogger(__name__)


@dataclass
class BridgeStatus:
    connected: bool = False
    host: str = "127.0.0.1"
    port: int = 41451
    last_error: str = ""
    last_ping_ms: float = 0.0
    server_version: int = 0
    client_version: int = 0
    last_connected_ts: float = 0.0
    last_ping_ts: float = 0.0
    weather_enabled: bool = False
    time_of_day_enabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


# UAM 이름 → (SDK 의 WeatherParameter 이름 → 값) 매핑.
# 1002 스키마에는 precipitation.type, precipitation.intensity, fog.intensity, wind.grade 이 존재.
WEATHER_PRECIP_MAP = {
    "rain":  WeatherParameter.Rain,
    "snow":  WeatherParameter.Snow,
    "dust":  WeatherParameter.Dust,
}
WIND_GRADE_MULT = {
    "calm":   (0.0, 0.0, 0.0),
    "normal": (2.0, 0.0, 0.0),
    "strong": (6.0, 2.0, 0.0),
    "storm":  (12.0, 4.0, 0.0),
}


class AirSimBridge:
    def __init__(self, config: AirSimConfig) -> None:
        self._lock = threading.RLock()
        self._config = config
        self._client: Optional[VehicleClient] = None
        self._status = BridgeStatus(
            host=config.host,
            port=config.port,
        )
        # 외부 aircraftId → AirSim vehicle name 캐시. 처음 만나면 map 또는 prefix 로 결정.
        self._resolved_names: Dict[str, str] = {}
        self._visual_state_rpc_available: Optional[bool] = None
        self._primary_view_rpc_available: Optional[bool] = None

    # ── 연결 ──────────────────────────────────────────────────
    def connect(self, host: Optional[str] = None, port: Optional[int] = None) -> BridgeStatus:
        with self._lock:
            if host is not None:
                self._config.host = str(host)
            if port is not None:
                self._config.port = int(port)
            self._status.host = self._config.host
            self._status.port = self._config.port
            try:
                self._client = VehicleClient(ip=self._config.host, port=self._config.port, timeout_value=5)
                ok = bool(self._client.ping())
                if not ok:
                    raise RuntimeError("ping returned False")
                self._status.connected = True
                self._status.last_error = ""
                self._status.server_version = int(self._client.getServerVersion() or 0)
                self._status.client_version = int(self._client.getClientVersion() or 0)
                self._status.last_connected_ts = time.time()
                self._status.last_ping_ts = self._status.last_connected_ts
            except Exception as exc:
                self._client = None
                self._status.connected = False
                self._status.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("AirSim connect failed: %s", self._status.last_error)
            return BridgeStatus(**self._status.__dict__)

    def disconnect(self) -> BridgeStatus:
        with self._lock:
            self._client = None
            self._status.connected = False
            return BridgeStatus(**self._status.__dict__)

    def ping(self) -> bool:
        with self._lock:
            if self._client is None:
                return False
            try:
                start = time.time()
                ok = bool(self._client.ping())
                self._status.last_ping_ms = (time.time() - start) * 1000.0
                self._status.last_ping_ts = time.time()
                if ok:
                    self._status.connected = True
                    self._status.last_error = ""
                else:
                    self._status.connected = False
                    self._status.last_error = "ping returned False"
                return ok
            except Exception as exc:
                self._status.connected = False
                self._status.last_error = f"{type(exc).__name__}: {exc}"
                return False

    def status(self) -> BridgeStatus:
        return BridgeStatus(**self._status.__dict__)

    # ── Vehicle pose (4001) ──────────────────────────────────
    def apply_vehicle_status_frame(self, payload: Dict[str, Any]) -> Dict[str, int]:
        """4001 Vehicle Status 메시지 하나를 받아 모든 UAM 의 pose 를 업데이트.

        반환: {"applied": n, "skipped": m, "errors": [...]}
        """
        result: Dict[str, Any] = {"applied": 0, "skipped": 0, "errors": []}
        vehicle_payloads = _normalize_4001_payload(payload)
        with self._lock:
            if self._client is None or not self._status.connected:
                result["skipped"] = len(vehicle_payloads)
                result["errors"].append("not connected")
                return result

            for key, value in vehicle_payloads.items():
                vehicle_name = self._resolve_vehicle_name(key)
                try:
                    pose = _pose_from_4001(value)
                    if pose is None:
                        result["skipped"] += 1
                        continue
                    self._client.simSetVehiclePose(pose, self._config.ignore_collisions, vehicle_name)
                    visual_state = _visual_state_from_4001(value)
                    if visual_state is not None:
                        try:
                            self._client.simSetVehicleVisualState(
                                visual_state["tilt_left"],
                                visual_state["tilt_right"],
                                visual_state["aileron"],
                                visual_state["rudder_left"],
                                visual_state["rudder_right"],
                                visual_state["motor_rpm"],
                                vehicle_name,
                            )
                            self._visual_state_rpc_available = True
                        except Exception as exc:
                            if self._visual_state_rpc_available is not False:
                                logger.warning(
                                    "AirSim visual-state RPC unavailable for %s: %s: %s",
                                    vehicle_name,
                                    type(exc).__name__,
                                    exc,
                                )
                            self._visual_state_rpc_available = False
                    result["applied"] += 1
                except Exception as exc:
                    result["skipped"] += 1
                    result["errors"].append(f"{key}->{vehicle_name}: {type(exc).__name__}: {exc}")
            return result

    # ── Weather (1002) ───────────────────────────────────────
    def apply_simulation_setup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """1002 Simulation Setup → simSetWeatherParameter 등으로 변환."""
        out: Dict[str, Any] = {"applied": [], "errors": []}
        with self._lock:
            if self._client is None or not self._status.connected:
                out["errors"].append("not connected")
                return out

            weather = (payload or {}).get("weatherEffect") or {}
            precip = weather.get("precipitation") or {}
            fog = weather.get("fog") or {}
            wind = (payload or {}).get("wind") or {}

            try:
                self._client.simEnableWeather(True)
                self._status.weather_enabled = True
            except Exception as exc:
                out["errors"].append(f"enableWeather: {type(exc).__name__}: {exc}")

            ptype = str(precip.get("type") or "none").strip().lower()
            pintensity = float(precip.get("intensity") or 0.0)
            for name, param in WEATHER_PRECIP_MAP.items():
                value = pintensity if name == ptype else 0.0
                try:
                    self._client.simSetWeatherParameter(param, float(max(0.0, min(1.0, value))))
                    out["applied"].append(f"precipitation.{name}={value:.2f}")
                except Exception as exc:
                    out["errors"].append(f"precip.{name}: {type(exc).__name__}: {exc}")

            fog_intensity = float(fog.get("intensity") or 0.0)
            try:
                self._client.simSetWeatherParameter(WeatherParameter.Fog, float(max(0.0, min(1.0, fog_intensity))))
                out["applied"].append(f"fog={fog_intensity:.2f}")
            except Exception as exc:
                out["errors"].append(f"fog: {type(exc).__name__}: {exc}")

            wind_grade = str(wind.get("grade") or "normal").strip().lower()
            vec = WIND_GRADE_MULT.get(wind_grade, WIND_GRADE_MULT["normal"])
            try:
                self._client.simSetWind(Vector3r(vec[0], vec[1], vec[2]))
                out["applied"].append(f"wind.grade={wind_grade} → {vec}")
            except Exception:
                # simSetWind 가 미지원인 빌드도 있으니 조용히 넘어간다.
                pass

            # Optional: playback speed (clock speed) — 있으면 시도
            speed = payload.get("playbackSpeed")
            if speed is not None:
                try:
                    self._client.simPause(False)
                    out["applied"].append(f"play_state={payload.get('playState', 'play')}")
                except Exception:
                    pass
            return out

    # ── Scenario (1003) — 주로 메타 정보 저장용 ──────────────
    def apply_scenario_setup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """1003 Scenario Setup → AirSim 측에는 적용할 직접 API 가 적으므로
        주로 vehicle_map 갱신(aircraftId ↔ AirSim vehicle name) 에 사용."""
        out: Dict[str, Any] = {"applied": [], "errors": []}
        aircraft_list = (payload or {}).get("aircraftList") or []
        with self._lock:
            for item in aircraft_list if isinstance(aircraft_list, list) else []:
                if not isinstance(item, dict):
                    continue
                aid = str(item.get("aircraftId") or "").strip()
                name = str(item.get("vehicleName") or item.get("airsimName") or "").strip()
                if aid and name:
                    self._config.vehicle_map[aid] = name
                    self._resolved_names[aid] = name
                    out["applied"].append(f"{aid} → {name}")
        return out

    # ── Reset (2002) ─────────────────────────────────────────
    def on_dtam_execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """2002 DTAM Execute — 시뮬레이션 시작 신호. AirSim 을 reset 한다."""
        out: Dict[str, Any] = {"applied": [], "errors": []}
        with self._lock:
            if self._client is None or not self._status.connected:
                out["errors"].append("not connected")
                return out
            try:
                self._client.reset()
                out["applied"].append("simulator reset")
            except Exception as exc:
                out["errors"].append(f"reset: {type(exc).__name__}: {exc}")
            return out

    # ── Camera frame (for 4101) ──────────────────────────────
    # ----- Mission guide plotting -------------------------------------------------
    def apply_mission_guides_from_file(self, path: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "applied": 0,
            "skipped": 0,
            "errors": [],
            "path": str(path),
        }
        guide_path = Path(path)
        if not guide_path.is_file():
            out["errors"].append("mission guide file not found")
            return out

        try:
            data = json.loads(guide_path.read_text(encoding="utf-8"))
        except Exception as exc:
            out["errors"].append(f"read mission guide: {type(exc).__name__}: {exc}")
            return out

        vehicles = data.get("vehicles") if isinstance(data, dict) else None
        if not isinstance(vehicles, list):
            out["errors"].append("mission guide has no vehicles list")
            return out

        with self._lock:
            return self._plot_mission_guides_unlocked(vehicles, flush=True, base_out=out)

    def apply_scheduled_flight_guide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        guide = _scheduled_flight_to_mission_guide(payload)
        out: Dict[str, Any] = {"applied": 0, "skipped": 0, "errors": [], "source": "3001"}
        if not guide.get("points"):
            out["errors"].append("3001 has no plottable route points")
            return out
        with self._lock:
            return self._plot_mission_guides_unlocked([guide], flush=False, base_out=out)

    def clear_mission_guides(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"ok": False, "errors": []}
        with self._lock:
            if self._client is None or not self._status.connected:
                out["errors"].append("not connected")
                return out
            try:
                self._client.simFlushPersistentMarkers()
                out["ok"] = True
            except Exception as exc:
                out["errors"].append(f"flush markers: {type(exc).__name__}: {exc}")
        return out

    def _plot_mission_guides_unlocked(
        self,
        guides: List[Dict[str, Any]],
        *,
        flush: bool,
        base_out: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self._client is None or not self._status.connected:
            base_out["skipped"] += len(guides)
            base_out["errors"].append("not connected")
            return base_out

        if flush:
            try:
                self._client.simFlushPersistentMarkers()
            except Exception as exc:
                base_out["errors"].append(f"flush markers: {type(exc).__name__}: {exc}")

        for guide in guides:
            aircraft_id = str(guide.get("aircraft_id") or guide.get("aircraftId") or "").strip() or "UAM"
            points = guide.get("points")
            if not isinstance(points, list):
                base_out["skipped"] += 1
                base_out["errors"].append(f"{aircraft_id}: points is not a list")
                continue

            vectors, errors = _mission_points_to_vectors(points)
            base_out["errors"].extend(f"{aircraft_id}: {err}" for err in errors)
            if len(vectors) < 2:
                base_out["skipped"] += 1
                base_out["errors"].append(f"{aircraft_id}: fewer than 2 valid points")
                continue

            smooth_vectors = _densify_vectors(vectors, max_step_m=80.0)
            try:
                self._client.simPlotLineStrip(
                    smooth_vectors,
                    color_rgba=[0.15, 0.85, 1.0, 0.35],
                    thickness=3.0,
                    duration=-1.0,
                    is_persistent=True,
                )
                base_out["applied"] += 1
            except Exception as exc:
                base_out["skipped"] += 1
                base_out["errors"].append(f"{aircraft_id}: plot: {type(exc).__name__}: {exc}")
        return base_out

    def capture_camera_frame(
        self,
        camera_name: str,
        image_type: int,
        vehicle_name: str = "",
        quality: int = 80,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """최신 카메라 프레임을 JPEG bytes 로 반환. header dict 와 함께 리턴."""
        meta: Dict[str, Any] = {
            "camera_name": camera_name,
            "image_type": image_type,
            "vehicle_name": vehicle_name,
            "bytes_len": 0,
            "captured_ts": time.time(),
        }
        with self._lock:
            if self._client is None or not self._status.connected:
                meta["error"] = "not connected"
                return b"", meta
            try:
                data = self._client.simGetCameraFrame(camera_name, image_type, vehicle_name, "", int(quality))
                if not data:
                    meta["error"] = "empty frame"
                    return b"", meta
                if isinstance(data, str):
                    data = data.encode("latin-1")
                meta["bytes_len"] = len(data)
                return bytes(data), meta
            except Exception as exc:
                meta["error"] = f"{type(exc).__name__}: {exc}"
                return b"", meta

    def adjust_camera_view(
        self,
        *,
        camera_name: str,
        vehicle_name: str = "",
        yaw_delta_deg: float = 0.0,
        pitch_delta_deg: float = 0.0,
        focal_length_delta: float = 0.0,
        min_pitch_deg: float = -80.0,
        max_pitch_deg: float = 80.0,
        min_focal_length: float = 18.0,
        max_focal_length: float = 120.0,
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "camera_name": str(camera_name),
            "vehicle_name": str(vehicle_name or ""),
            "yaw_delta_deg": float(yaw_delta_deg),
            "pitch_delta_deg": float(pitch_delta_deg),
            "focal_length_delta": float(focal_length_delta),
        }
        with self._lock:
            if self._client is None or not self._status.connected:
                out["error"] = "not connected"
                return out

            zoom_input = 0.0
            if float(focal_length_delta) > 1e-6:
                zoom_input = 1.0
            elif float(focal_length_delta) < -1e-6:
                zoom_input = -1.0

            if abs(float(yaw_delta_deg)) > 1e-6 or abs(float(zoom_input)) > 1e-6:
                try:
                    applied = bool(
                        self._client.simAdjustPrimaryView(
                            float(yaw_delta_deg),
                            float(zoom_input),
                            vehicle_name,
                        )
                    )
                    self._primary_view_rpc_available = True
                    if applied:
                        out["ok"] = True
                        out["zoom_input"] = float(zoom_input)
                        out["control_target"] = "camera_director"
                        return out
                except Exception as exc:
                    if self._primary_view_rpc_available is not False:
                        logger.warning(
                            "AirSim primary-view RPC unavailable for %s: %s: %s",
                            vehicle_name,
                            type(exc).__name__,
                            exc,
                        )
                    self._primary_view_rpc_available = False

            try:
                info = self._client.simGetCameraInfo(camera_name, vehicle_name)
                pose = info.pose
                roll_deg, pitch_deg, yaw_deg = _quaternion_to_euler_deg(pose.orientation)
                new_pitch_deg = _clamp(pitch_deg + float(pitch_delta_deg), float(min_pitch_deg), float(max_pitch_deg))
                new_yaw_deg = _wrap_deg_signed(yaw_deg + float(yaw_delta_deg))
                new_orientation = _euler_deg_to_quaternion(roll_deg, new_pitch_deg, new_yaw_deg)
                self._client.simSetCameraPose(
                    camera_name,
                    Pose(
                        Vector3r(
                            float(pose.position.x_val),
                            float(pose.position.y_val),
                            float(pose.position.z_val),
                        ),
                        new_orientation,
                    ),
                    vehicle_name,
                )
                out["pose"] = {
                    "roll_deg": float(roll_deg),
                    "pitch_deg": float(new_pitch_deg),
                    "yaw_deg": float(new_yaw_deg),
                }
            except Exception as exc:
                out["error"] = f"camera pose: {type(exc).__name__}: {exc}"
                return out

            try:
                current_focal = float(self._client.simGetFocalLength(camera_name, vehicle_name) or 35.0)
                new_focal = _clamp(
                    current_focal + float(focal_length_delta),
                    float(min_focal_length),
                    float(max_focal_length),
                )
                if abs(new_focal - current_focal) > 1e-6:
                    self._client.simSetFocalLength(float(new_focal), camera_name, vehicle_name)
                out["focal_length"] = float(new_focal)
            except Exception as exc:
                out["error"] = f"camera focal: {type(exc).__name__}: {exc}"
                return out

            out["ok"] = True
            return out

    # ── 내부 유틸 ───────────────────────────────────────────
    def _resolve_vehicle_name(self, aircraft_id: str) -> str:
        cached = self._resolved_names.get(aircraft_id)
        if cached is not None:
            return cached
        if aircraft_id in self._config.vehicle_map:
            name = self._config.vehicle_map[aircraft_id]
        elif self._config.vehicle_prefix:
            name = f"{self._config.vehicle_prefix}{aircraft_id}"
        else:
            name = aircraft_id
        self._resolved_names[aircraft_id] = name
        return name

    def update_vehicle_map(self, mapping: Dict[str, str]) -> None:
        with self._lock:
            for k, v in (mapping or {}).items():
                key = str(k).strip()
                value = str(v).strip()
                if not key:
                    continue
                if value:
                    self._config.vehicle_map[key] = value
                    self._resolved_names[key] = value
                else:
                    self._config.vehicle_map.pop(key, None)
                    self._resolved_names.pop(key, None)

    def get_vehicle_map(self) -> Dict[str, str]:
        with self._lock:
            return {
                str(k): str(v)
                for k, v in self._config.vehicle_map.items()
                if str(v).strip()
            }

    def resolve_vehicle_name(self, aircraft_id: str) -> str:
        with self._lock:
            return self._resolve_vehicle_name(str(aircraft_id or "").strip())

    def list_vehicles(self) -> Dict[str, Any]:
        with self._lock:
            live_names: List[str] = []
            settings: Dict[str, Any] = {}
            if self._client is not None:
                try:
                    settings_text = self._client.getSettingsString() or "{}"
                    settings = json.loads(str(settings_text))
                except Exception:
                    settings = {}
                try:
                    raw_names = self._client.listVehicles() or []
                    live_names = sorted({str(name).strip() for name in raw_names if str(name).strip()})
                    self._status.connected = True
                    self._status.last_error = ""
                except Exception as exc:
                    self._status.connected = False
                    self._status.last_error = f"{type(exc).__name__}: {exc}"
                    logger.debug("AirSim listVehicles failed: %s", self._status.last_error)

            settings_names = _settings_vehicle_names(settings)
            live_name_set = set(live_names)
            known_names = sorted(set(live_names) | set(settings_names))
            vehicle_map = self.get_vehicle_map()
            mapped_ids_by_name: Dict[str, List[str]] = {}
            for aircraft_id, vehicle_name in vehicle_map.items():
                mapped_ids_by_name.setdefault(vehicle_name, []).append(aircraft_id)

            vehicles: List[Dict[str, Any]] = []
            seen_names = set()

            for name in known_names:
                available = name in live_name_set or (
                    bool(self._status.connected) and not live_name_set and name in settings_names
                )
                source = "airsim" if name in live_name_set else "settings"
                pose: Optional[Dict[str, Any]] = None
                pose_error = ""
                if available and self._client is not None:
                    try:
                        pose = _pose_to_dict(self._client.simGetVehiclePose(name))
                    except Exception as exc:
                        pose_error = f"{type(exc).__name__}: {exc}"
                vehicles.append({
                    "name": name,
                    "available": available,
                    "source": source,
                    "mapped_ids": sorted(mapped_ids_by_name.get(name, [])),
                    "pose": pose,
                })
                if pose_error:
                    vehicles[-1]["pose_error"] = pose_error
                seen_names.add(name)

            for name in sorted(mapped_ids_by_name):
                if name in seen_names:
                    continue
                vehicles.append({
                    "name": name,
                    "available": False,
                    "source": "vehicle_map",
                    "mapped_ids": sorted(mapped_ids_by_name.get(name, [])),
                    "pose": None,
                })

            return {
                "airsim": self.status().to_dict(),
                "origin_geopoint": _origin_geopoint_from_settings(settings),
                "vehicle_prefix": self._config.vehicle_prefix,
                "vehicle_map": vehicle_map,
                "vehicles": vehicles,
            }


# ────────────────────────────────────────────────────────────
# 4001 payload → AirSim Pose 변환
# ────────────────────────────────────────────────────────────

def _mission_points_to_vectors(points: List[Any]) -> Tuple[List[Vector3r], List[str]]:
    vectors: List[Vector3r] = []
    errors: List[str] = []
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            errors.append(f"point[{index}] is not an object")
            continue
        try:
            vector = _mission_point_to_vector(point)
        except Exception as exc:
            errors.append(f"point[{index}]: {type(exc).__name__}: {exc}")
            continue
        if vector is None:
            errors.append(f"point[{index}] has no valid coordinate")
            continue
        if vectors and _same_vector(vectors[-1], vector):
            continue
        vectors.append(vector)
    return vectors, errors


def _mission_point_to_vector(point: Dict[str, Any]) -> Optional[Vector3r]:
    ned = point.get("ned")
    if isinstance(ned, dict):
        n = _safe_float(ned.get("north", ned.get("n")))
        e = _safe_float(ned.get("east", ned.get("e")))
        d = _safe_float(ned.get("down", ned.get("d")))
        if n is not None and e is not None and d is not None:
            return Vector3r(n, e, d)

    n = _safe_float(point.get("north", point.get("n")))
    e = _safe_float(point.get("east", point.get("e")))
    d = _safe_float(point.get("down", point.get("d")))
    if n is not None and e is not None and d is not None:
        return Vector3r(n, e, d)

    lat = _safe_float(point.get("lat", point.get("latitude")))
    lon = _safe_float(point.get("lon", point.get("longitude")))
    alt = _safe_float(point.get("alt_m", point.get("alt", point.get("altitude"))))
    if lat is None or lon is None:
        return None
    if alt is None:
        alt = 0.0
    n, e, d = _wgs84_to_airsim_ned(lat, lon, alt)
    return Vector3r(float(n), float(e), float(d))


def _scheduled_flight_to_mission_guide(payload: Dict[str, Any]) -> Dict[str, Any]:
    points: List[Dict[str, Any]] = []
    enroute = payload.get("enRoute") if isinstance(payload, dict) else None
    if isinstance(enroute, list):
        for segment in enroute:
            if not isinstance(segment, dict):
                continue
            for key in ("startLLA", "endLLA"):
                lla = segment.get(key)
                if not isinstance(lla, dict):
                    continue
                points.append({
                    "lat": lla.get("lat"),
                    "lon": lla.get("lon"),
                    "alt_m": lla.get("alt"),
                })
    return {
        "aircraft_id": str(payload.get("aircraftId") or "").strip() if isinstance(payload, dict) else "",
        "points": points,
    }


def _wgs84_to_airsim_ned(lat: float, lon: float, alt_m: float) -> Tuple[float, float, float]:
    root = str(FRAMEWORK_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from DTAM_MissionPlanner.app.domain.coord_transform import wgs84_to_airsim_ned

    return wgs84_to_airsim_ned(float(lat), float(lon), float(alt_m))


def _same_vector(a: Vector3r, b: Vector3r, eps: float = 1e-3) -> bool:
    return (
        abs(float(a.x_val) - float(b.x_val)) <= eps
        and abs(float(a.y_val) - float(b.y_val)) <= eps
        and abs(float(a.z_val) - float(b.z_val)) <= eps
    )


def _densify_vectors(vectors: List[Vector3r], max_step_m: float) -> List[Vector3r]:
    if len(vectors) < 2:
        return vectors
    max_step = max(1.0, float(max_step_m))
    dense: List[Vector3r] = [vectors[0]]
    for start, end in zip(vectors, vectors[1:]):
        dx = float(end.x_val) - float(start.x_val)
        dy = float(end.y_val) - float(start.y_val)
        dz = float(end.z_val) - float(start.z_val)
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        steps = max(1, int(math.ceil(distance / max_step)))
        for index in range(1, steps + 1):
            ratio = index / steps
            dense.append(Vector3r(
                float(start.x_val) + dx * ratio,
                float(start.y_val) + dy * ratio,
                float(start.z_val) + dz * ratio,
            ))
    return dense


def _pose_from_4001(vehicle_payload: Dict[str, Any]) -> Optional[Pose]:
    """4001 의 한 UAM sub-payload 를 cosysairsim Pose 로 변환.

    position 은 NED (north/east/down, meters) 이며, mission replay 에서는
    첫 송출 trajectory point 기준 local replay 좌표로 들어온다.
    VM 은 4001 값을 다시 보정하지 않고 simSetVehiclePose 에 그대로 전달한다.
    """
    pos = vehicle_payload.get("position") or {}
    att = vehicle_payload.get("attitude") or {}
    try:
        n = float(pos.get("north", 0.0))
        e = float(pos.get("east", 0.0))
        d = float(pos.get("down", 0.0))
    except (TypeError, ValueError):
        return None
    roll = float(att.get("roll") or 0.0)
    pitch = float(att.get("pitch") or 0.0)
    yaw = float(att.get("yaw") or 0.0)

    cr = math.cos(roll * 0.5);  sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5); sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5);   sy = math.sin(yaw * 0.5)
    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy

    return Pose(
        position_val=Vector3r(n, e, d),
        orientation_val=Quaternionr(x_val=qx, y_val=qy, z_val=qz, w_val=qw),
    )


def _normalize_4001_payload(payload: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}

    canonical: Dict[str, Dict[str, Any]] = {}

    for key, value in payload.items():
        if key in ("timestamp", "ok", "errors"):
            continue
        if isinstance(value, dict) and "position" in value and "attitude" in value:
            canonical[str(key)] = _canonical_vehicle_payload(value)
    if canonical:
        return canonical

    vehicles = payload.get("vehicles")
    if isinstance(vehicles, list):
        for item in vehicles:
            if not isinstance(item, dict):
                continue
            vehicle_id = str(item.get("vehicle_id") or item.get("aircraftId") or "").strip()
            if not vehicle_id:
                continue
            canonical[vehicle_id] = _canonical_vehicle_payload(item)
    if canonical:
        return canonical

    vehicle_id = str(payload.get("aircraftId") or payload.get("vehicle_id") or "").strip()
    if vehicle_id and isinstance(payload.get("position"), dict) and isinstance(payload.get("attitude"), dict):
        canonical[vehicle_id] = _canonical_vehicle_payload(payload)
    return canonical


def _canonical_vehicle_payload(vehicle_payload: Dict[str, Any]) -> Dict[str, Any]:
    propulsion = vehicle_payload.get("propulsion")
    motor_rpm = vehicle_payload.get("motor_rpm")
    if not isinstance(propulsion, dict):
        propulsion = {}
    if "motor_rpm" not in propulsion and isinstance(motor_rpm, list):
        propulsion = dict(propulsion)
        propulsion["motor_rpm"] = list(motor_rpm)

    return {
        "currentWaypointId": vehicle_payload.get("currentWaypointId", ""),
        "position": dict(vehicle_payload.get("position") or {}),
        "attitude": dict(vehicle_payload.get("attitude") or {}),
        "actuator": dict(vehicle_payload.get("actuator") or {}),
        "propulsion": propulsion,
        "gps": dict(vehicle_payload.get("gps") or {}),
        "imu": dict(vehicle_payload.get("imu") or {}),
        "barometer": dict(vehicle_payload.get("barometer") or {}),
    }


def _visual_state_from_4001(vehicle_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    actuator = vehicle_payload.get("actuator") or {}
    propulsion = vehicle_payload.get("propulsion") or {}
    motor_rpm = propulsion.get("motor_rpm")
    if not isinstance(actuator, dict) or not isinstance(motor_rpm, list) or len(motor_rpm) < 4:
        return None

    try:
        return {
            "tilt_left": float(actuator.get("tilt_left", 0.5) or 0.5),
            "tilt_right": float(actuator.get("tilt_right", 0.5) or 0.5),
            "aileron": float(actuator.get("aileron", 0.0) or 0.0),
            "rudder_left": float(actuator.get("rudder_left", 0.0) or 0.0),
            "rudder_right": float(actuator.get("rudder_right", 0.0) or 0.0),
            "motor_rpm": [float(motor_rpm[index] or 0.0) for index in range(4)],
        }
    except (TypeError, ValueError):
        return None


def _settings_vehicle_names(settings: Dict[str, Any]) -> List[str]:
    vehicles = settings.get("Vehicles") if isinstance(settings, dict) else None
    if not isinstance(vehicles, dict):
        return []
    return sorted({
        str(name).strip()
        for name in vehicles.keys()
        if str(name).strip()
    })


def _origin_geopoint_from_settings(settings: Dict[str, Any]) -> Dict[str, float]:
    origin = settings.get("OriginGeopoint") if isinstance(settings, dict) else None
    if not isinstance(origin, dict):
        return {}
    lat = _safe_float(origin.get("Latitude", origin.get("latitude")))
    lon = _safe_float(origin.get("Longitude", origin.get("longitude")))
    alt = _safe_float(origin.get("Altitude", origin.get("altitude")))
    out: Dict[str, float] = {}
    if lat is not None:
        out["latitude"] = lat
    if lon is not None:
        out["longitude"] = lon
    if alt is not None:
        out["altitude"] = alt
    return out


def _pose_to_dict(pose: Pose) -> Dict[str, float]:
    roll_deg, pitch_deg, yaw_deg = _quaternion_to_euler_deg(pose.orientation)
    return {
        "north": float(pose.position.x_val),
        "east": float(pose.position.y_val),
        "down": float(pose.position.z_val),
        "roll_deg": roll_deg,
        "pitch_deg": pitch_deg,
        "yaw_deg": yaw_deg,
    }


def _quaternion_to_euler_deg(q: Quaternionr) -> Tuple[float, float, float]:
    x = float(q.x_val)
    y = float(q.y_val)
    z = float(q.z_val)
    w = float(q.w_val)

    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    if sinp >= 1.0:
        pitch = math.pi / 2.0
    elif sinp <= -1.0:
        pitch = -math.pi / 2.0
    else:
        pitch = math.asin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return (
        math.degrees(roll),
        math.degrees(pitch),
        math.degrees(yaw) % 360.0,
    )


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _euler_deg_to_quaternion(roll_deg: float, pitch_deg: float, yaw_deg: float) -> Quaternionr:
    roll = math.radians(float(roll_deg))
    pitch = math.radians(float(pitch_deg))
    yaw = math.radians(float(yaw_deg))

    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)

    return Quaternionr(
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def _wrap_deg_signed(value: float) -> float:
    wrapped = (float(value) + 180.0) % 360.0 - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped


__all__ = ["AirSimBridge", "BridgeStatus"]
