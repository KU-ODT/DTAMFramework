"""DT World / ODT mission replay pose-frame adapter.

This mirrors the coordinate/yaw convention used by the packaged KP2A map:
WGS84 trajectory -> ODT custom Unreal frame -> AirSim pose.

Important: AirSim names the pose fields N/E/D, but the DT World map assets are
not laid out on pure geographic north/east axes.  For this map, the visual pose
frame is approximately X=east, Y=south(-north), Z=down.  GPS/LLA remains the
truth for Operation's 2D map; this adapter exists only to drive Unreal's
vehicle pose in the same frame as the visual vertiports.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TypeVar

from .coord_transform import wgs84_to_local_ned


DEFAULT_CUSTOM_X_AXIS_HEADING_DEG = 90.0
DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG = 180.0
DEFAULT_TURN_RATE_DEG_S = 12.0
POSE_FRAME_TYPE = "odt_mission_relative_custom_frame"

_T = TypeVar("_T")


def _find_framework_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "VisualizationModule").exists() and (parent / "VehicleModule").exists():
            return parent
    return here.parents[4]


_FRAMEWORK_ROOT = _find_framework_root()
_PROJECT_AIRSIM_SETTINGS_PATH = (
    _FRAMEWORK_ROOT
    / "VisualizationModule"
    / "runtime"
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "settings.json"
)
_VM_CONFIG_PATH = _FRAMEWORK_ROOT / "VisualizationModule" / "data" / "configs" / "vm_config.json"
_DOCUMENTS_AIRSIM_SETTINGS_PATH = Path.home() / "Documents" / "AirSim" / "settings.json"


@dataclass
class SpawnPose:
    x_m: float = 0.0
    y_m: float = 0.0
    z_m: float = 0.0
    yaw_deg: float = 0.0
    vehicle_name: str = ""
    source: str = ""


@dataclass
class OdtPoseFrameState:
    origin_lat: float
    origin_lon: float
    origin_alt_m: float
    spawn_pose: SpawnPose
    x_axis_heading_deg: float = DEFAULT_CUSTOM_X_AXIS_HEADING_DEG
    y_axis_heading_deg: float = DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG
    yaw_rate_deg_s: float = DEFAULT_TURN_RATE_DEG_S
    last_yaw_deg: Optional[float] = None
    last_yaw_time_s: Optional[float] = None

    def project(
        self,
        *,
        lat: float,
        lon: float,
        alt_m: float,
        heading_deg: float,
        time_s: Optional[float],
    ) -> Dict[str, Any]:
        offset = convert_target_to_unreal(
            player_start_lat=self.origin_lat,
            player_start_lon=self.origin_lon,
            player_start_alt_m=self.origin_alt_m,
            target_lat=float(lat),
            target_lon=float(lon),
            target_alt_m=float(alt_m),
            x_axis_heading_deg=self.x_axis_heading_deg,
            y_axis_heading_deg=self.y_axis_heading_deg,
        )
        # AirSim/Cosys-AirSim applies Pose.position directly to the Unreal
        # actor through its local NED wrapper.  In the packaged DT World scene
        # the actor/map axes are the ODT visual axes, so the authoritative
        # 4001 pose must use custom_unreal_m, not pure geographic local_ned_m.
        rel = offset["custom_unreal_m"]
        relative_position = {
            "north": float(rel["x"]),
            "east": float(rel["y"]),
            "down": float(rel["z"]),
        }
        absolute_position = {
            "north": float(self.spawn_pose.x_m) + relative_position["north"],
            "east": float(self.spawn_pose.y_m) + relative_position["east"],
            "down": float(self.spawn_pose.z_m) + relative_position["down"],
        }
        target_yaw_deg = geo_heading_to_frame_yaw(
            float(heading_deg),
            self.x_axis_heading_deg,
            self.y_axis_heading_deg,
        )
        yaw_deg = self._resolve_yaw(target_yaw_deg, time_s)
        return {
            "position": absolute_position,
            "relative_position": dict(relative_position),
            "settings_spawn_position": {
                "north": float(self.spawn_pose.x_m),
                "east": float(self.spawn_pose.y_m),
                "down": float(self.spawn_pose.z_m),
            },
            "yaw_deg": float(yaw_deg),
            "pose_frame": {
                "type": POSE_FRAME_TYPE,
                "spawn_x_m": float(self.spawn_pose.x_m),
                "spawn_y_m": float(self.spawn_pose.y_m),
                "spawn_z_m": float(self.spawn_pose.z_m),
                "spawn_yaw_deg": float(self.spawn_pose.yaw_deg),
                "vehicle_name": str(self.spawn_pose.vehicle_name or ""),
                "source": str(self.spawn_pose.source or ""),
                "origin_lat": float(self.origin_lat),
                "origin_lon": float(self.origin_lon),
                "origin_alt_m": float(self.origin_alt_m),
                "frame_x_heading_deg": float(self.x_axis_heading_deg),
                "frame_y_heading_deg": float(self.y_axis_heading_deg),
            },
            "target_frame_yaw_deg": float(target_yaw_deg),
            "offset": offset,
        }

    def _resolve_yaw(self, target_frame_yaw_deg: float, time_s: Optional[float]) -> float:
        if self.last_yaw_deg is None:
            self.last_yaw_deg = float(self.spawn_pose.yaw_deg)

        current_time = _to_float(time_s)
        dt = (
            0.0
            if current_time is None or self.last_yaw_time_s is None
            else max(0.0, float(current_time) - float(self.last_yaw_time_s))
        )
        yaw = slew_angle_deg(
            float(self.last_yaw_deg),
            float(target_frame_yaw_deg),
            max(0.0, float(self.yaw_rate_deg_s)) * dt,
        )
        yaw = normalize_angle_deg(yaw)
        self.last_yaw_deg = yaw
        if current_time is not None:
            self.last_yaw_time_s = float(current_time)
        return yaw


def convert_target_to_unreal(
    *,
    player_start_lat: float,
    player_start_lon: float,
    player_start_alt_m: float,
    target_lat: float,
    target_lon: float,
    target_alt_m: float,
    x_axis_heading_deg: float,
    y_axis_heading_deg: float,
) -> Dict[str, Any]:
    north_m, east_m, down_m = wgs84_to_local_ned(
        target_lat,
        target_lon,
        target_alt_m,
        player_start_lat,
        player_start_lon,
        player_start_alt_m,
    )
    x_axis = heading_to_ne_unit(x_axis_heading_deg)
    y_axis = heading_to_ne_unit(y_axis_heading_deg)
    x_m = (north_m * x_axis[0]) + (east_m * x_axis[1])
    y_m = (north_m * y_axis[0]) + (east_m * y_axis[1])
    axis_delta_deg = normalize_angle_deg(y_axis_heading_deg - x_axis_heading_deg)
    orthogonality_error_deg = min(
        abs(axis_delta_deg - 90.0),
        abs(axis_delta_deg + 90.0),
        abs(abs(axis_delta_deg) - 270.0),
    )
    horizontal_distance_m = math.hypot(north_m, east_m)
    bearing_deg = normalize_heading_deg(math.degrees(math.atan2(east_m, north_m)))
    return {
        "local_ned_m": {
            "north": float(north_m),
            "east": float(east_m),
            "down": float(down_m),
        },
        "custom_unreal_m": {
            "x": float(x_m),
            "y": float(y_m),
            "z": float(down_m),
        },
        "distance_m": float(horizontal_distance_m),
        "bearing_deg": float(bearing_deg),
        "axis_delta_deg": float(axis_delta_deg),
        "orthogonality_error_deg": float(orthogonality_error_deg),
    }


def load_spawn_pose_for_aircraft(aircraft_id: str) -> SpawnPose:
    vehicle_name = _vehicle_name_for_aircraft(aircraft_id)
    settings, source = _load_airsim_settings()
    vehicles = settings.get("Vehicles") if isinstance(settings, dict) else None
    if not isinstance(vehicles, dict) or not vehicles:
        return SpawnPose(vehicle_name=vehicle_name, source=source)

    selected_name = vehicle_name if vehicle_name in vehicles else ""
    if not selected_name:
        fallback = _default_vehicle_name_for_aircraft(aircraft_id)
        if fallback in vehicles:
            selected_name = fallback
    if not selected_name and len(vehicles) == 1:
        selected_name = str(next(iter(vehicles.keys())))
    if not selected_name:
        selected_name = vehicle_name or "Drone1"

    vehicle = vehicles.get(selected_name) if isinstance(vehicles, dict) else None
    if not isinstance(vehicle, dict):
        return SpawnPose(vehicle_name=selected_name, source=source)
    return SpawnPose(
        x_m=float(_to_float(vehicle.get("X")) or 0.0),
        y_m=float(_to_float(vehicle.get("Y")) or 0.0),
        z_m=float(_to_float(vehicle.get("Z")) or 0.0),
        yaw_deg=float(_to_float(vehicle.get("Yaw")) or 0.0),
        vehicle_name=selected_name,
        source=source,
    )


def trim_airsim_sync_trajectory(trajectory: Sequence[_T]) -> List[_T]:
    items = list(trajectory)
    if not items:
        return []

    start_index = 0
    while start_index < len(items) - 1 and _phase(items[start_index]) == "A":
        start_index += 1

    end_index = len(items) - 1
    if _phase(items[end_index]) == "K":
        first_trailing_k = end_index
        while first_trailing_k > start_index and _phase(items[first_trailing_k - 1]) == "K":
            first_trailing_k -= 1
        end_index = first_trailing_k

    trimmed = items[start_index : end_index + 1]
    return trimmed or items


def heading_to_ne_unit(heading_deg: float) -> tuple[float, float]:
    radians = math.radians(float(heading_deg))
    return math.cos(radians), math.sin(radians)


def geo_heading_to_frame_yaw(
    heading_deg: float,
    x_axis_heading_deg: float,
    y_axis_heading_deg: float,
) -> float:
    north, east = heading_to_ne_unit(heading_deg)
    x_axis_n, x_axis_e = heading_to_ne_unit(x_axis_heading_deg)
    y_axis_n, y_axis_e = heading_to_ne_unit(y_axis_heading_deg)
    x_component = (north * x_axis_n) + (east * x_axis_e)
    y_component = (north * y_axis_n) + (east * y_axis_e)
    return float(math.degrees(math.atan2(y_component, x_component)))


def normalize_heading_deg(angle_deg: float) -> float:
    value = float(angle_deg) % 360.0
    return value if value >= 0 else value + 360.0


def normalize_angle_deg(value: float) -> float:
    return ((float(value) + 180.0) % 360.0) - 180.0


def signed_angle_delta_deg(target_deg: float, current_deg: float) -> float:
    return normalize_angle_deg(float(target_deg) - float(current_deg))


def slew_angle_deg(current_deg: float, target_deg: float, max_delta_deg: float) -> float:
    delta = signed_angle_delta_deg(target_deg, current_deg)
    limit = abs(float(max_delta_deg))
    if abs(delta) <= limit:
        return normalize_angle_deg(target_deg)
    return normalize_angle_deg(float(current_deg) + math.copysign(limit, delta))


def _vehicle_name_for_aircraft(aircraft_id: str) -> str:
    config = _read_json(_VM_CONFIG_PATH)
    airsim = config.get("airsim") if isinstance(config, dict) else None
    vehicle_map = airsim.get("vehicle_map") if isinstance(airsim, dict) else None
    aid = str(aircraft_id or "").strip()
    if isinstance(vehicle_map, dict):
        mapped = str(vehicle_map.get(aid) or "").strip()
        if mapped:
            return mapped
    return _default_vehicle_name_for_aircraft(aid)


def _default_vehicle_name_for_aircraft(aircraft_id: str) -> str:
    match = re.search(r"(\d{4})$", str(aircraft_id or ""))
    if not match:
        return "Drone1"
    index = max(1, int(match.group(1)))
    return f"Drone{index}"


def _load_airsim_settings() -> tuple[Dict[str, Any], str]:
    for path in (_PROJECT_AIRSIM_SETTINGS_PATH, _DOCUMENTS_AIRSIM_SETTINGS_PATH):
        payload = _read_json(path)
        if payload:
            return payload, str(path)
    return {}, ""


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _phase(point: Any) -> str:
    return str(getattr(point, "phase", "") or "").strip().upper()


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
