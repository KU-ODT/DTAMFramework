"""AirSim/Unreal connection bridge.

This module wraps the cosysairsim Python client and keeps DTAM communication
separate from direct AirSim RPC calls. It handles vehicle pose updates, weather,
camera capture for 4101, simulation reset, and mission guide rendering.

Thread-safe: inbound communication threads and REST requests may call this
bridge concurrently.
"""
from __future__ import annotations

import io
import json
import logging
import math
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Always prefer the bundled Cosys-AirSim Python client shipped with this
# VisualizationModule.  Some developer machines also have an older
# cosysairsim package installed globally; importing that copy would silently
# miss DTAM-only RPCs such as simSetVehicleNavigationTarget.
_MODULE_ROOT = Path(__file__).resolve().parents[2]
_AIRSIM_PY_ROOT = _MODULE_ROOT / "runtime" / "PythonClient"
if _AIRSIM_PY_ROOT.is_dir():
    _airsim_py_path = str(_AIRSIM_PY_ROOT)
    if _airsim_py_path in sys.path:
        sys.path.remove(_airsim_py_path)
    sys.path.insert(0, _airsim_py_path)

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
            position_val: Optional[Vector3r] = None,
            orientation_val: Optional[Quaternionr] = None,
        ) -> None:
            self.position = position_val or position or Vector3r()
            self.orientation = orientation_val or orientation or Quaternionr()

    class WeatherParameter:  # type: ignore[no-redef]
        Rain = 0
        Roadwetness = 1
        Snow = 2
        RoadSnow = 3
        MapleLeaf = 4
        RoadLeaf = 5
        Dust = 6
        Fog = 7
        Enabled = 8

from ..config import AirSimConfig, FRAMEWORK_ROOT

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


# Map SDK weather names to AirSim WeatherParameter values.
# The 1002 schema includes precipitation.type, precipitation.intensity, fog.intensity, and wind.grade.
WEATHER_PRECIP_ALIASES = {
    "rainy": "rain",
    "rain": "rain",
    "snowy": "snow",
    "snow": "snow",
    "none": "none",
    "clear": "none",
    "off": "none",
    "": "none",
}
WEATHER_PRECIP_MAP = {
    "rain": WeatherParameter.Rain,
    "snow": WeatherParameter.Snow,
}
WIND_GRADE_MULT = {
    "calm":   (0.0, 0.0, 0.0),
    "normal": (2.0, 0.0, 0.0),
    "warning": (6.0, 2.0, 0.0),
    "serious": (12.0, 4.0, 0.0),
    "strong": (6.0, 2.0, 0.0),
    "storm":  (12.0, 4.0, 0.0),
}


class AirSimBridge:
    def __init__(self, config: AirSimConfig) -> None:
        self._lock = threading.RLock()
        self._media_lock = threading.RLock()
        self._config = config
        self._client: Optional[VehicleClient] = None
        self._media_client: Optional[VehicleClient] = None
        self._status = BridgeStatus(
            host=config.host,
            port=config.port,
        )
        # Cache aircraftId to AirSim vehicle name; resolve through map or prefix on first use.
        self._resolved_names: Dict[str, str] = {}
        self._last_vehicle_targets: Dict[str, str] = {}
        self._visual_state_rpc_available: Optional[bool] = None
        self._telemetry_rpc_available: Optional[bool] = None
        self._telemetry_battery_rpc_available: Optional[bool] = None
        self._primary_view_rpc_available: Optional[bool] = None
        self._camera_frame_rpc_available: Optional[bool] = None
        self._vpo_camera_rpc_available: Optional[bool] = None
        self._vpo_camera_rpc_unavailable_reason = ""
        self._pose_feedback_last_check: Dict[str, float] = {}
        self._last_telemetry_send_ts: Dict[str, float] = {}
        self._last_visual_state_send_ts: Dict[str, float] = {}

        # Cache aircraftId to AirSim vehicle name; resolve through map or prefix on first use.
    def connect(self, host: Optional[str] = None, port: Optional[int] = None) -> BridgeStatus:
        with self._lock:
            if host is not None:
                self._config.host = str(host)
            if port is not None:
                self._config.port = int(port)
            self._status.host = self._config.host
            self._status.port = self._config.port
            with self._media_lock:
                self._media_client = None
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
            with self._media_lock:
                self._media_client = None
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

    def run_console_command(self, command: str) -> Dict[str, Any]:
        """Run one Unreal console command through the AirSim RPC bridge.

        This is used by the VisualizationModule settings API for lightweight
        renderer CVars (FPS cap, render scale, scalability).  If DT World is not
        connected yet, callers still get a structured response instead of an
        exception.
        """
        safe_command = str(command or "").strip()
        if not safe_command:
            return {"ok": False, "command": "", "error": "empty command"}

        with self._lock:
            client = self._client
            connected = bool(self._status.connected)

            if client is None or not connected:
                self.connect()
                client = self._client
                connected = bool(self._status.connected)

            if client is None or not connected:
                return {
                    "ok": False,
                    "command": safe_command,
                    "error": self._status.last_error or "AirSim RPC is not connected",
                }

            try:
                result = client.simRunConsoleCommand(safe_command)
                return {"ok": bool(result), "command": safe_command, "result": result}
            except Exception as exc:
                # Console-command support is optional across AirSim/Cosys builds.
                # A command failure should not by itself mark the whole RPC bridge as
                # disconnected; pose/camera RPCs can still be healthy.
                self._status.last_error = f"{type(exc).__name__}: {exc}"
                return {
                    "ok": False,
                    "command": safe_command,
                    "error": f"{type(exc).__name__}: {exc}",
                }

    def set_ignore_collisions(self, ignore_collisions: bool) -> Dict[str, Any]:
        """Update the AirSim simSetVehiclePose collision policy at runtime."""
        with self._lock:
            self._config.ignore_collisions = bool(ignore_collisions)
            self._pose_feedback_last_check.clear()
            return {
                "ok": True,
                "ignore_collisions": bool(self._config.ignore_collisions),
                "mode": "teleport" if self._config.ignore_collisions else "sweep",
            }

    # Vehicle pose (4001)
    def apply_vehicle_status_frame(
        self,
        payload: Dict[str, Any],
        *,
        pose_feedback_check: bool = False,
        pose_feedback_error_threshold_m: float = 2.0,
        pose_feedback_sample_hz: float = 5.0,
        telemetry_hz: float = 10.0,
        visual_state_hz: float = 10.0,
    ) -> Dict[str, Any]:
        """Update all UAM poses from one 4001 Vehicle Status message.

        Returns: {"applied": n, "skipped": m, "errors": [...]}
        """
        total_started = time.perf_counter()
        normalize_started = time.perf_counter()
        vehicle_payloads = _normalize_4001_payload(payload)
        normalize_ms = (time.perf_counter() - normalize_started) * 1000.0
        perf: Dict[str, Any] = {
            "vehicle_count": len(vehicle_payloads),
            "normalize_ms": round(normalize_ms, 3),
            "pose_rpc_ms": 0.0,
            "pose_feedback_rpc_ms": 0.0,
            "telemetry_rpc_ms": 0.0,
            "visual_state_rpc_ms": 0.0,
            "total_ms": 0.0,
            "telemetry_sent": 0,
            "telemetry_skipped_by_throttle": 0,
            "visual_state_sent": 0,
            "visual_state_skipped_by_throttle": 0,
        }
        result: Dict[str, Any] = {
            "applied": 0,
            "skipped": 0,
            "errors": [],
            "ignore_collisions": bool(self._config.ignore_collisions),
            "collision_mode": "teleport" if self._config.ignore_collisions else "sweep",
            "pose_feedback": [],
            "perf": perf,
        }

        def _finish() -> Dict[str, Any]:
            perf["total_ms"] = round((time.perf_counter() - total_started) * 1000.0, 3)
            for key in ("pose_rpc_ms", "pose_feedback_rpc_ms", "telemetry_rpc_ms", "visual_state_rpc_ms"):
                perf[key] = round(float(perf.get(key, 0.0) or 0.0), 3)
            return result

        with self._lock:
            if self._client is None or not self._status.connected:
                result["skipped"] = len(vehicle_payloads)
                result["errors"].append("not connected")
                return _finish()

            for key, value in vehicle_payloads.items():
                vehicle_name = self._resolve_vehicle_name(key)
                self._last_vehicle_targets[str(key)] = vehicle_name
                try:
                    pose = _pose_from_4001(value)
                    if pose is None:
                        result["skipped"] += 1
                        continue
                    rpc_started = time.perf_counter()
                    self._client.simSetVehiclePose(pose, self._config.ignore_collisions, vehicle_name)
                    perf["pose_rpc_ms"] += (time.perf_counter() - rpc_started) * 1000.0
                    rpc_started = time.perf_counter()
                    feedback = self._sample_pose_feedback_unlocked(
                        aircraft_id=str(key),
                        vehicle_name=vehicle_name,
                        requested_pose=pose,
                        enabled=pose_feedback_check,
                        threshold_m=pose_feedback_error_threshold_m,
                        sample_hz=pose_feedback_sample_hz,
                    )
                    perf["pose_feedback_rpc_ms"] += (time.perf_counter() - rpc_started) * 1000.0
                    if feedback:
                        result["pose_feedback"].append(feedback)
                    telemetry_args = _telemetry_args_from_4001(key, value, vehicle_name)
                    if telemetry_args is not None:
                        if self._rate_limit_allows(self._last_telemetry_send_ts, vehicle_name, telemetry_hz):
                            try:
                                rpc_started = time.perf_counter()
                                send_args = (
                                    telemetry_args
                                    if self._telemetry_battery_rpc_available is not False
                                    else telemetry_args[:-1]
                                )
                                self._client.simSetVehicleTelemetry(*send_args)
                                perf["telemetry_rpc_ms"] += (time.perf_counter() - rpc_started) * 1000.0
                                perf["telemetry_sent"] += 1
                                self._telemetry_rpc_available = True
                                if len(send_args) == len(telemetry_args):
                                    self._telemetry_battery_rpc_available = True

                                navigation_args = _navigation_args_from_4001(key, value, vehicle_name)
                                if navigation_args is not None and hasattr(self._client, "simSetVehicleNavigationTarget"):
                                    try:
                                        rpc_started = time.perf_counter()
                                        self._client.simSetVehicleNavigationTarget(*navigation_args)
                                        perf["telemetry_rpc_ms"] += (time.perf_counter() - rpc_started) * 1000.0
                                    except Exception as nav_exc:
                                        logger.warning(
                                            "AirSim navigation-target RPC unavailable for %s: %s: %s",
                                            vehicle_name,
                                            type(nav_exc).__name__,
                                            nav_exc,
                                        )
                            except Exception as exc:
                                # Backward compatibility: older packaged DT World
                                # builds expose simSetVehicleTelemetry without
                                # the battery_fraction argument.  Retry once in
                                # legacy mode so velocity/GPS HUD still works;
                                # the HUD battery will remain ENERGY EST. until
                                # DT World is rebuilt with the new C++ bridge.
                                legacy_sent = False
                                if self._telemetry_battery_rpc_available is not False and len(telemetry_args) >= 2:
                                    try:
                                        rpc_started = time.perf_counter()
                                        self._client.simSetVehicleTelemetry(*telemetry_args[:-1])
                                        perf["telemetry_rpc_ms"] += (time.perf_counter() - rpc_started) * 1000.0
                                        perf["telemetry_sent"] += 1
                                        self._telemetry_rpc_available = True
                                        self._telemetry_battery_rpc_available = False
                                        legacy_sent = True
                                        logger.warning(
                                            "AirSim telemetry battery RPC unavailable for %s; "
                                            "using legacy telemetry without 4001 battery until DT World is rebuilt: %s: %s",
                                            vehicle_name,
                                            type(exc).__name__,
                                            exc,
                                        )
                                    except Exception as legacy_exc:
                                        exc = legacy_exc

                                if not legacy_sent and self._telemetry_rpc_available is not False:
                                    logger.warning(
                                        "AirSim telemetry RPC unavailable for %s: %s: %s",
                                        vehicle_name,
                                        type(exc).__name__,
                                        exc,
                                    )
                                if not legacy_sent:
                                    self._telemetry_rpc_available = False
                        else:
                            perf["telemetry_skipped_by_throttle"] += 1
                    visual_state = _visual_state_from_4001(value)
                    if visual_state is not None:
                        if self._rate_limit_allows(self._last_visual_state_send_ts, vehicle_name, visual_state_hz):
                            try:
                                rpc_started = time.perf_counter()
                                self._client.simSetVehicleVisualState(
                                    visual_state["tilt_left"],
                                    visual_state["tilt_right"],
                                    visual_state["aileron"],
                                    visual_state["rudder_left"],
                                    visual_state["rudder_right"],
                                    visual_state["motor_rpm"],
                                    vehicle_name,
                                )
                                perf["visual_state_rpc_ms"] += (time.perf_counter() - rpc_started) * 1000.0
                                perf["visual_state_sent"] += 1
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
                        else:
                            perf["visual_state_skipped_by_throttle"] += 1
                    result["applied"] += 1
                except Exception as exc:
                    result["skipped"] += 1
                    result["errors"].append(f"{key}->{vehicle_name}: {type(exc).__name__}: {exc}")
            return _finish()

    @staticmethod
    def _rate_limit_allows(last_sent: Dict[str, float], key: str, hz: float) -> bool:
        """Return True when a per-vehicle auxiliary RPC may be sent.

        ``simSetVehiclePose`` remains the high-rate critical path.  HUD
        telemetry and visual actuator state are auxiliary and can be sent at a
        lower rate to keep the AirSim RPC server responsive.
        """
        try:
            safe_hz = float(hz)
        except (TypeError, ValueError):
            safe_hz = 10.0
        if safe_hz <= 0.0:
            return True
        period_s = 1.0 / max(0.1, min(60.0, safe_hz))
        now = time.monotonic()
        safe_key = str(key or "__default__")
        last = float(last_sent.get(safe_key, 0.0) or 0.0)
        if now - last < period_s:
            return False
        last_sent[safe_key] = now
        return True

    def _sample_pose_feedback_unlocked(
        self,
        *,
        aircraft_id: str,
        vehicle_name: str,
        requested_pose: Pose,
        enabled: bool,
        threshold_m: float,
        sample_hz: float,
    ) -> Dict[str, Any]:
        """Best-effort movement-block diagnostic after simSetVehiclePose.

        This intentionally uses ``simGetVehiclePose`` only.  Calling
        ``simGetCollisionInfo`` here would reset AirSim's collision state and
        race the dedicated 4103 collision polling loop.
        """
        if not enabled or self._client is None:
            return {}
        sample_period_s = 1.0 / max(0.1, float(sample_hz or 0.0))
        now = time.monotonic()
        feedback_key = str(vehicle_name or aircraft_id or "")
        last = float(self._pose_feedback_last_check.get(feedback_key, 0.0) or 0.0)
        if now - last < sample_period_s:
            return {}
        self._pose_feedback_last_check[feedback_key] = now

        try:
            actual_pose = self._client.simGetVehiclePose(vehicle_name)
        except Exception as exc:
            return {
                "aircraftId": str(aircraft_id),
                "airsimVehicleName": str(vehicle_name),
                "ok": False,
                "error": f"simGetVehiclePose: {type(exc).__name__}: {exc}",
            }

        requested = _pose_to_dict(requested_pose)
        actual = _pose_to_dict(actual_pose)
        dn = float(actual.get("north", 0.0)) - float(requested.get("north", 0.0))
        de = float(actual.get("east", 0.0)) - float(requested.get("east", 0.0))
        dd = float(actual.get("down", 0.0)) - float(requested.get("down", 0.0))
        error_m = math.sqrt(dn * dn + de * de + dd * dd)
        threshold = max(0.05, float(threshold_m or 0.0))
        blocked = bool(error_m > threshold and not self._config.ignore_collisions)
        return {
            "aircraftId": str(aircraft_id),
            "airsimVehicleName": str(vehicle_name),
            "ok": True,
            "blocked_suspected": blocked,
            "error_m": round(float(error_m), 3),
            "threshold_m": threshold,
            "ignore_collisions": bool(self._config.ignore_collisions),
            "mode": "teleport" if self._config.ignore_collisions else "sweep",
            "requested": requested,
            "actual": actual,
        }

    # Collision (4103 preparation)
    def poll_collision_events(self, *, default_recommended_action: str = "hold") -> Dict[str, Any]:
        """Poll AirSim collision state for known DTAM vehicles.

        This is intentionally a read-only adapter method.  It normalizes
        ``simGetCollisionInfo(vehicle_name)`` into the 4103 ICD payload shape,
        but does not publish it to IntegrationHub.  The manager owns
        de-duplication and, in a later session, server transmission.
        """
        out: Dict[str, Any] = {
            "connected": False,
            "polled": 0,
            "events": [],
            "errors": [],
            "targets": [],
            "perf": {
                "target_count": 0,
                "collision_rpc_ms": 0.0,
                "max_collision_rpc_ms": 0.0,
                "total_ms": 0.0,
            },
        }
        total_started = time.perf_counter()

        def _finish() -> Dict[str, Any]:
            perf = out.setdefault("perf", {})
            perf["total_ms"] = round((time.perf_counter() - total_started) * 1000.0, 3)
            perf["collision_rpc_ms"] = round(float(perf.get("collision_rpc_ms", 0.0) or 0.0), 3)
            perf["max_collision_rpc_ms"] = round(float(perf.get("max_collision_rpc_ms", 0.0) or 0.0), 3)
            return out

        # The cosys/msgpack AirSim client is not safe for concurrent RPC calls
        # from multiple Python threads.  Keep listVehicles/simGetCollisionInfo
        # under the same bridge lock as simSetVehiclePose; otherwise the
        # vehicle-status worker and collision worker can race and leave the RPC
        # client in an "IOLoop is already running" / disconnected state.
        with self._lock:
            client = self._client
            connected = bool(self._status.connected and client is not None)
            targets = self._collision_targets_unlocked()

            out["connected"] = connected
            if not connected or client is None:
                out["targets"] = [
                    {"aircraftId": aircraft_id, "airsimVehicleName": vehicle_name}
                    for aircraft_id, vehicle_name in targets
                ]
                out["perf"]["target_count"] = len(targets)
                return _finish()

            # Collision polling must not depend solely on receiving at least one
            # 4001 first.  If Unreal/AirSim already has live vehicles, add them as
            # fallback targets and infer the DTAM aircraftId for standard DroneN
            # names.  Explicit 1003/4001 vehicle_map entries still take precedence.
            try:
                live_names = [
                    str(name).strip()
                    for name in (client.listVehicles() or [])
                    if str(name).strip()
                ]
            except Exception as exc:
                live_names = []
                out["errors"].append(f"listVehicles: {type(exc).__name__}: {exc}")
            if live_names:
                used_names = {str(vehicle_name or "").strip() for _, vehicle_name in targets if str(vehicle_name or "").strip()}
                target_by_aircraft = {str(aid or "").strip(): (str(aid or "").strip(), str(name or "").strip()) for aid, name in targets}
                for vehicle_name in live_names:
                    if vehicle_name in used_names:
                        continue
                    aircraft_id = _aircraft_id_from_vehicle_name(vehicle_name)
                    if aircraft_id in target_by_aircraft:
                        continue
                    target_by_aircraft[aircraft_id] = (aircraft_id, vehicle_name)
                    used_names.add(vehicle_name)
                targets = list(target_by_aircraft.values())

            out["targets"] = [
                {"aircraftId": aircraft_id, "airsimVehicleName": vehicle_name}
                for aircraft_id, vehicle_name in targets
            ]
            out["perf"]["target_count"] = len(targets)
            if not targets:
                return _finish()

            for aircraft_id, vehicle_name in targets:
                try:
                    rpc_started = time.perf_counter()
                    info = client.simGetCollisionInfo(vehicle_name)
                    rpc_ms = (time.perf_counter() - rpc_started) * 1000.0
                    out["perf"]["collision_rpc_ms"] += rpc_ms
                    out["perf"]["max_collision_rpc_ms"] = max(
                        float(out["perf"].get("max_collision_rpc_ms", 0.0) or 0.0),
                        rpc_ms,
                    )
                    out["polled"] += 1
                except Exception as exc:
                    out["errors"].append(
                        f"{aircraft_id}->{vehicle_name or '<default>'}: {type(exc).__name__}: {exc}"
                    )
                    continue
                event = _collision_info_to_4103_payload(
                    info,
                    aircraft_id=aircraft_id,
                    airsim_vehicle_name=vehicle_name,
                    default_recommended_action=default_recommended_action,
                )
                if event is not None:
                    out["events"].append(event)
        return _finish()

    # Weather (1002)
    def apply_simulation_setup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert 1002 Simulation Setup to simSetWeatherParameter calls."""
        out: Dict[str, Any] = {"applied": [], "errors": []}
        with self._lock:
            if self._client is None or not self._status.connected:
                out["errors"].append("not connected")
                return out

            weather = (
                (payload or {}).get("weatherEffect")
                or (payload or {}).get("weather_effect")
                or {}
            )
            precip = weather.get("precipitation") or {}
            fog = weather.get("fog") or {}
            wind = (payload or {}).get("wind") or {}

            try:
                self._client.simEnableWeather(True)
                self._status.weather_enabled = True
            except Exception as exc:
                out["errors"].append(f"enableWeather: {type(exc).__name__}: {exc}")

            ptype_raw = str(precip.get("type") or precip.get("precipitationType") or "none").strip().lower()
            ptype = WEATHER_PRECIP_ALIASES.get(ptype_raw, ptype_raw)
            pintensity = float(precip.get("intensity") or 0.0)
            if ptype == "none":
                pintensity = 0.0
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
                out["applied"].append(f"wind.grade={wind_grade} -> {vec}")
            except Exception:
                # Some AirSim builds do not support simSetWind; ignore quietly.
                pass

            # 1002 playbackSpeed by itself is not permission to run physics.
            # OperationModule includes playbackSpeed even for pause/reset
            # payloads, so unpausing here made Unreal continue before the
            # operator pressed Play.  Gate AirSim physics only by explicit
            # playState.
            play_state = str(
                payload.get("playState")
                or payload.get("play_state")
                or payload.get("state")
                or ""
            ).strip().lower()
            if play_state in {"play", "playing", "run", "running"}:
                try:
                    self._client.simPause(False)
                    out["applied"].append("simPause=False")
                except Exception as exc:
                    out["errors"].append(f"simPause(False): {type(exc).__name__}: {exc}")
            elif play_state in {"pause", "paused", "reset", "stop", "stopped"}:
                try:
                    self._client.simPause(True)
                    out["applied"].append("simPause=True")
                except Exception as exc:
                    out["errors"].append(f"simPause(True): {type(exc).__name__}: {exc}")
            return out

    # Scenario (1003): mainly used for vehicle-map metadata
    def apply_scenario_setup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Apply 1003 Scenario Setup metadata, mainly vehicle_map updates."""
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
                    out["applied"].append(f"{aid} -> {name}")
        return out

    # Reset (2002)
    def on_dtam_execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle 2002 DTAM Execute by resetting AirSim."""
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
            try:
                self._client.simPause(True)
                out["applied"].append("simulator paused")
            except Exception as exc:
                out["errors"].append(f"simPause(True): {type(exc).__name__}: {exc}")
            return out


    # Camera frame (for 4101)
    # ----- Mission guide plotting -------------------------------------------------
    def apply_mission_guides_from_file(self, path: Any) -> Dict[str, Any]:
        return {
            "applied": 0,
            "skipped": 1,
            "errors": [],
            "path": str(path),
            "disabled": True,
            "reason": "mission guide line rendering is disabled",
        }

        out: Dict[str, Any] = {
            "applied": 0,
    # Camera frame (for 4101)
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
        return {
            "applied": 0,
            "skipped": 1,
            "errors": [],
            "source": "3001",
            "disabled": True,
            "reason": "mission guide line rendering is disabled",
        }

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
        base_out["applied"] = 0
        base_out["skipped"] = int(base_out.get("skipped") or 0) + len(guides)
        base_out.setdefault("errors", [])
        base_out["disabled"] = True
        base_out["reason"] = "mission guide line rendering is disabled"
        return base_out

    def capture_camera_frame(
        self,
        camera_name: str,
        image_type: int,
        vehicle_name: str = "",
        quality: int = 80,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Return the latest camera frame as JPEG bytes and header metadata."""
        total_started = time.perf_counter()
        meta: Dict[str, Any] = {
            "camera_name": camera_name,
            "image_type": image_type,
            "vehicle_name": vehicle_name,
            "captured_ts": time.time(),
        }

        def _finish(frame: bytes, out_meta: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
            finished_meta = dict(out_meta or {})
            finished_meta["capture_total_ms"] = round((time.perf_counter() - total_started) * 1000.0, 3)
            return frame, finished_meta

        with self._lock:
            connected = bool(self._status.connected)
            main_client = self._client
        if main_client is None or not connected:
            # VPO can be opened independently from the Visualization Manager UI.
            # If DT World/AirSim is already up, attach lazily before reporting
            # the fixed CCTV stream as unavailable.
            self.connect()
            with self._lock:
                connected = bool(self._status.connected)
                main_client = self._client
            if main_client is None or not connected:
                meta["error"] = "not connected"
                return _finish(b"", meta)

        # Use a dedicated RPC client for high-rate media capture.  The main
        # client is shared with 4001 pose updates, 5002 camera controls, status
        # pings, and settings queries; keeping media on its own socket prevents
        # those calls from serializing the camera stream down to single-digit FPS.
        errors: List[str] = []
        lock_started = time.perf_counter()
        with self._media_lock:
            meta["media_lock_wait_ms"] = round((time.perf_counter() - lock_started) * 1000.0, 3)
            try:
                media_client = self._ensure_media_client_unlocked()
                frame, out_meta = self._capture_camera_frame_with_client(
                    media_client,
                    camera_name=camera_name,
                    image_type=image_type,
                    vehicle_name=vehicle_name,
                    quality=quality,
                    base_meta=meta,
                    errors=errors,
                    rpc_client_label="media",
                )
                if frame:
                    return _finish(frame, out_meta)
            except Exception as exc:
                errors.append(f"media client: {type(exc).__name__}: {exc}")
                self._media_client = None

        # Fallback to the main RPC client so diagnostics still work if a build
        # refuses a second msgpack-rpc connection.
        lock_started = time.perf_counter()
        with self._lock:
            meta["main_lock_wait_ms"] = round((time.perf_counter() - lock_started) * 1000.0, 3)
            if self._client is None or not self._status.connected:
                meta["error"] = "not connected"
                meta["fallback_errors"] = errors
                return _finish(b"", meta)
            frame, out_meta = self._capture_camera_frame_with_client(
                self._client,
                camera_name=camera_name,
                image_type=image_type,
                vehicle_name=vehicle_name,
                quality=quality,
                base_meta=meta,
                errors=errors,
                rpc_client_label="main-fallback",
            )
            return _finish(frame, out_meta)

    def capture_vpo_camera_frame(self, camera_id: str, quality: int = 70) -> Tuple[bytes, Dict[str, Any]]:
        """Return one on-demand VPO/vertiport SceneCapture frame as JPEG bytes."""
        total_started = time.perf_counter()
        safe_camera_id = str(camera_id or "").strip()
        safe_quality = max(10, min(95, int(quality or 70)))
        meta: Dict[str, Any] = {
            "camera_id": safe_camera_id,
            "quality": safe_quality,
            "captured_ts": time.time(),
            "source": "unreal_scene_capture",
        }

        def _finish(frame: bytes, out_meta: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
            finished_meta = dict(out_meta or {})
            finished_meta["capture_total_ms"] = round((time.perf_counter() - total_started) * 1000.0, 3)
            return frame, finished_meta

        if not safe_camera_id:
            meta["error"] = "missing camera_id"
            return _finish(b"", meta)

        if self._vpo_camera_rpc_available is False:
            meta["error"] = self._vpo_camera_rpc_unavailable_reason or "simGetVpoCameraFrame unavailable"
            meta["disabled"] = True
            meta["rpc_available"] = False
            return _finish(b"", meta)

        with self._lock:
            connected = bool(self._status.connected)
            main_client = self._client
        if main_client is None or not connected:
            meta["error"] = "not connected"
            return _finish(b"", meta)

        errors: List[str] = []

        def _call(client: VehicleClient, label: str) -> Tuple[bytes, Dict[str, Any]]:
            out_meta = dict(meta)
            out_meta["rpc_client"] = label
            rpc_started = time.perf_counter()
            try:
                data = client.simGetVpoCameraFrame(safe_camera_id, safe_quality)
            except Exception as exc:
                if self._is_missing_rpc_error(exc, "simGetVpoCameraFrame"):
                    self._vpo_camera_rpc_available = False
                    self._vpo_camera_rpc_unavailable_reason = (
                        f"simGetVpoCameraFrame unavailable: {type(exc).__name__}: {exc}"
                    )
                    out_meta["rpc_available"] = False
                    out_meta["disabled"] = True
                raise
            out_meta["simGetVpoCameraFrame_ms"] = round((time.perf_counter() - rpc_started) * 1000.0, 3)
            self._vpo_camera_rpc_available = True
            self._vpo_camera_rpc_unavailable_reason = ""
            out_meta["rpc_available"] = True
            if isinstance(data, str):
                data = data.encode("latin-1")
            if not data:
                raise RuntimeError("empty frame; VPO CCTV SceneCapture may be disabled or camera_id is unknown")
            frame = bytes(data)
            out_meta["bytes_len"] = len(frame)
            out_meta["capture_method"] = "simGetVpoCameraFrame"
            out_meta["has_jpeg_soi"] = frame.startswith(b"\xff\xd8")
            return frame, out_meta

        lock_started = time.perf_counter()
        with self._media_lock:
            meta["media_lock_wait_ms"] = round((time.perf_counter() - lock_started) * 1000.0, 3)
            try:
                media_client = self._ensure_media_client_unlocked()
                frame, out_meta = _call(media_client, "media")
                return _finish(frame, out_meta)
            except Exception as exc:
                errors.append(f"media client: {type(exc).__name__}: {exc}")
                self._media_client = None
                if self._vpo_camera_rpc_available is False:
                    meta["error"] = "; ".join(errors)
                    meta["fallback_errors"] = errors
                    meta["disabled"] = True
                    meta["rpc_available"] = False
                    return _finish(b"", meta)

        lock_started = time.perf_counter()
        with self._lock:
            meta["main_lock_wait_ms"] = round((time.perf_counter() - lock_started) * 1000.0, 3)
            if self._client is None or not self._status.connected:
                meta["error"] = "not connected"
                meta["fallback_errors"] = errors
                return _finish(b"", meta)
            try:
                frame, out_meta = _call(self._client, "main-fallback")
                out_meta["fallback_errors"] = errors
                return _finish(frame, out_meta)
            except Exception as exc:
                errors.append(f"main client: {type(exc).__name__}: {exc}")
                meta["error"] = "; ".join(errors)
                meta["fallback_errors"] = errors
                return _finish(b"", meta)

    def _ensure_media_client_unlocked(self) -> VehicleClient:
        if self._media_client is None:
            self._media_client = VehicleClient(
                ip=self._config.host,
                port=self._config.port,
                timeout_value=5,
            )
            try:
                self._media_client.ping()
            except Exception:
                # Some AirSim builds accept the first real call even if ping is
                # slow during startup.  Keep the client and let capture report
                # the concrete RPC error if the stream is still unavailable.
                pass
        return self._media_client

    def _capture_camera_frame_with_client(
        self,
        client: VehicleClient,
        *,
        camera_name: str,
        image_type: int,
        vehicle_name: str,
        quality: int,
        base_meta: Dict[str, Any],
        errors: List[str],
        rpc_client_label: str,
    ) -> Tuple[bytes, Dict[str, Any]]:
        meta = dict(base_meta)
        meta["rpc_client"] = rpc_client_label
        if self._camera_frame_rpc_available is not False:
            try:
                rpc_started = time.perf_counter()
                data = client.simGetCameraFrame(camera_name, image_type, vehicle_name, "", int(quality))
                meta["simGetCameraFrame_ms"] = round((time.perf_counter() - rpc_started) * 1000.0, 3)
                self._camera_frame_rpc_available = True
                if isinstance(data, str):
                    data = data.encode("latin-1")
                if data:
                    frame = bytes(data)
                    source_is_black = self._is_encoded_image_black(frame)
                    meta["source_api"] = "simGetCameraFrame"
                    meta["source_bytes_len"] = len(frame)
                    meta["source_format"] = "jpeg" if frame.startswith(b"\xff\xd8") else "compressed"
                    meta["has_jpeg_soi"] = bool(frame.startswith(b"\xff\xd8"))
                    meta["source_encoded_black"] = source_is_black
                    meta["converted_encoded_black"] = source_is_black
                    meta["bytes_len"] = len(frame)
                    meta["capture_method"] = "simGetCameraFrame"
                    if source_is_black:
                        errors.append("simGetCameraFrame: black frame")
                    meta["fallback_errors"] = list(errors)
                    return frame, meta
                errors.append("simGetCameraFrame: empty frame")
            except Exception as exc:
                errors.append(f"simGetCameraFrame: {type(exc).__name__}: {exc}")
                if self._is_missing_rpc_error(exc, "simGetCameraFrame"):
                    self._camera_frame_rpc_available = False
        else:
            meta["simGetCameraFrame_skipped"] = "rpc unavailable"

        # Older/stock AirSim builds may not expose simGetCameraFrame. Fall
        # back to the standard compressed image API and convert PNG -> JPEG
        # so the MJPEG endpoint can still emit browser-compatible parts.
        try:
            rpc_started = time.perf_counter()
            data = client.simGetImage(camera_name, image_type, vehicle_name, "")
            meta["simGetImage_ms"] = round((time.perf_counter() - rpc_started) * 1000.0, 3)
            if isinstance(data, str):
                data = data.encode("latin-1")
            if not data:
                meta["source_api"] = "simGetImage"
                errors.append("simGetImage: empty frame")
            else:
                raw = bytes(data)
                meta["source_api"] = "simGetImage"
                meta["source_bytes_len"] = len(raw)
                meta["source_format"] = "jpeg" if raw.startswith(b"\xff\xd8") else ("png" if raw.startswith(b"\x89PNG") else "compressed")
                meta["has_jpeg_soi"] = bool(raw.startswith(b"\xff\xd8"))
                raw_is_black = self._is_encoded_image_black(raw)
                meta["source_encoded_black"] = raw_is_black
                if raw_is_black:
                    errors.append("simGetImage: black frame")
                if raw.startswith(b"\xff\xd8"):
                    meta["bytes_len"] = len(raw)
                    meta["capture_method"] = "simGetImage-jpeg"
                    meta["converted_encoded_black"] = raw_is_black
                    meta["fallback_errors"] = list(errors)
                    return raw, meta
                try:
                    from PIL import Image  # type: ignore

                    convert_started = time.perf_counter()
                    with Image.open(io.BytesIO(raw)) as img:
                        rgb = img.convert("RGB")
                        out = io.BytesIO()
                        rgb.save(out, format="JPEG", quality=int(quality or 80))
                        frame = out.getvalue()
                    meta["convert_ms"] = round((time.perf_counter() - convert_started) * 1000.0, 3)
                    meta["bytes_len"] = len(frame)
                    meta["has_jpeg_soi"] = bool(frame.startswith(b"\xff\xd8"))
                    meta["converted_encoded_black"] = raw_is_black if raw_is_black else self._is_encoded_image_black(frame)
                    meta["capture_method"] = "simGetImage-converted"
                    meta["fallback_errors"] = list(errors)
                    return frame, meta
                except Exception as conv_exc:
                    errors.append(f"simGetImage convert: {type(conv_exc).__name__}: {conv_exc}")
        except Exception as exc:
            errors.append(f"simGetImage: {type(exc).__name__}: {exc}")

        meta["error"] = "; ".join(errors) if errors else "empty frame"
        meta["fallback_errors"] = list(errors)
        return b"", meta

    @staticmethod
    def _is_encoded_image_black(data: bytes, *, max_luma: int = 8, max_nonblack_pct: float = 0.1) -> bool:
        """Return True when an encoded JPEG/PNG is effectively all black."""
        if not data:
            return True
        try:
            from PIL import Image  # type: ignore

            with Image.open(io.BytesIO(data)) as img:
                rgb = img.convert("RGB")
                # Downsample for cheap high-rate stream checks.
                rgb.thumbnail((160, 90))
                pixels = list(rgb.getdata())
            if not pixels:
                return True
            max_channel = max(max(pixel) for pixel in pixels)
            if max_channel > max_luma:
                nonblack = sum(1 for pixel in pixels if max(pixel) > max_luma)
                return (100.0 * nonblack / len(pixels)) <= max_nonblack_pct
            return True
        except Exception:
            return False

    @staticmethod
    def _is_missing_rpc_error(exc: BaseException, method_name: str) -> bool:
        text = f"{type(exc).__name__}: {exc}".lower()
        method = method_name.lower()
        if method not in text and "attributeerror" not in text:
            return False
        return any(
            token in text
            for token in (
                "not found",
                "unknown function",
                "unknown method",
                "no method",
                "no function",
                "does not exist",
                "unable to find",
                "attributeerror",
            )
        )

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

    def apply_abnormal_situation_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Forward 5003 abnormal situation / obstacle commands to DT World."""
        raw = payload or {}
        position = raw.get("position") if isinstance(raw.get("position"), dict) else {}
        if not position and isinstance(raw.get("center"), dict):
            position = raw.get("center") or {}
        entity = raw.get("entity") if isinstance(raw.get("entity"), dict) else {}
        command_id = str(raw.get("commandId") or raw.get("eventId") or raw.get("obstacleId") or f"OBS-{int(time.time())}")
        abnormal_type = str(raw.get("abnormalType") or raw.get("obstacleType") or raw.get("eventType") or entity.get("type") or "bird_flock")
        action = str(raw.get("action") or "create")
        out: Dict[str, Any] = {
            "ok": False,
            "commandId": command_id,
            "abnormalType": abnormal_type,
            "action": action,
        }
        try:
            lat = float(_first_present(position.get("lat"), position.get("latitude")))
            lon = float(_first_present(position.get("lon"), position.get("lng"), position.get("longitude")))
        except Exception:
            out["error"] = "missing or invalid position.lat/lon"
            return out
        alt = _safe_float(_first_present(position.get("alt"), position.get("altitude"), position.get("height")))
        if alt is None:
            alt = 120.0
        radius_m = max(1.0, float(_first_present(raw.get("radiusM"), raw.get("radius"), raw.get("radius_m"), 800.0)))
        try:
            count = max(1, int(raw.get("count") if raw.get("count") is not None else entity.get("count", 9)))
        except Exception:
            count = 9
        speed_mps = max(0.1, float(_first_present(raw.get("speedMps"), raw.get("speed_mps"), entity.get("speedMps"), 12.0)))
        duration_sec = max(0.0, float(_first_present(raw.get("durationSec"), raw.get("duration_s"), raw.get("duration"), 0.0)))
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        asset_key = str(metadata.get("assetKey") or entity.get("assetKey") or "birds_fab_fbx")

        with self._lock:
            if self._client is None or not self._status.connected:
                out["error"] = "not connected"
                return out
            try:
                ok = bool(
                    self._client.simSpawnAbnormalObstacle(
                        command_id,
                        abnormal_type,
                        action,
                        float(lat),
                        float(lon),
                        float(alt),
                        float(radius_m),
                        int(count),
                        float(speed_mps),
                        float(duration_sec),
                        asset_key,
                    )
                )
                out.update({
                    "ok": ok,
                    "lat": lat,
                    "lon": lon,
                    "alt": alt,
                    "radiusM": radius_m,
                    "count": count,
                    "speedMps": speed_mps,
                    "durationSec": duration_sec,
                    "assetKey": asset_key,
                })
                if not ok:
                    out["error"] = "Unreal RPC returned false"
            except Exception as exc:
                out["error"] = f"{type(exc).__name__}: {exc}"
            return out

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

    # Internal helpers
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
                    self._last_vehicle_targets[key] = value
                else:
                    self._config.vehicle_map.pop(key, None)
                    self._resolved_names.pop(key, None)
                    self._last_vehicle_targets.pop(key, None)

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

    def _collision_targets_unlocked(self) -> List[Tuple[str, str]]:
        """Return unique aircraftId/AirSim-name pairs for collision polling."""
        pairs: Dict[str, Tuple[str, str]] = {}

        for aircraft_id, vehicle_name in self._config.vehicle_map.items():
            aid = str(aircraft_id or "").strip()
            name = str(vehicle_name or "").strip()
            if aid and name:
                pairs[aid] = (aid, name)

        for aircraft_id, vehicle_name in self._resolved_names.items():
            aid = str(aircraft_id or "").strip()
            name = str(vehicle_name or "").strip()
            if aid and name:
                pairs.setdefault(aid, (aid, name))

        for aircraft_id, vehicle_name in self._last_vehicle_targets.items():
            aid = str(aircraft_id or "").strip()
            name = str(vehicle_name or "").strip()
            if aid and name:
                pairs[aid] = (aid, name)

        return list(pairs.values())

    def list_vehicles(self) -> Dict[str, Any]:
        with self._lock:
            live_names: List[str] = []
            settings: Dict[str, Any] = {}
            default_pose: Optional[Dict[str, float]] = None
            default_pose_error = ""
            primary_view_vehicle_name = ""
            if self._client is not None:
                try:
                    settings_text = self._client.getSettingsString() or "{}"
                    settings = json.loads(str(settings_text))
                except Exception:
                    settings = {}
                try:
                    primary_view_vehicle_name = str(self._client.simGetPrimaryViewVehicle() or "").strip()
                except Exception:
                    primary_view_vehicle_name = ""
                try:
                    default_pose = _pose_to_dict(self._client.simGetVehiclePose(""))
                except Exception as exc:
                    default_pose_error = f"{type(exc).__name__}: {exc}"
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
            pose_by_name: Dict[str, Dict[str, float]] = {}

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
                        pose_by_name[name] = pose
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

            if primary_view_vehicle_name and primary_view_vehicle_name in set(known_names):
                default_vehicle_name = primary_view_vehicle_name
            else:
                default_vehicle_name = _match_pose_to_vehicle_name(default_pose, pose_by_name)
            if not default_vehicle_name and len(live_names) == 1:
                default_vehicle_name = live_names[0]

            for item in vehicles:
                item["is_default_view"] = bool(default_vehicle_name and item.get("name") == default_vehicle_name)

            return {
                "airsim": self.status().to_dict(),
                "origin_geopoint": _origin_geopoint_from_settings(settings),
                "vehicle_prefix": self._config.vehicle_prefix,
                "vehicle_map": vehicle_map,
                "default_vehicle_name": default_vehicle_name,
                "primary_view_vehicle_name": primary_view_vehicle_name,
                "default_vehicle_pose": default_pose or {},
                "default_vehicle_error": default_pose_error,
                "vehicles": vehicles,
            }



def _mission_points_to_vectors(points: List[Any]) -> Tuple[List[Vector3r], List[str]]:
    vectors: List[Vector3r] = []
    errors: List[str] = []
    for index, point in enumerate(points or []):
        if not isinstance(point, dict):
            errors.append(f"point[{index}] is not an object")
            continue
        try:
            vector = _mission_point_to_vector(point)
        except Exception as exc:
            errors.append(f"point[{index}]: {type(exc).__name__}: {exc}")
            continue
        vectors.append(vector)
    return vectors, errors

# -----------------------------------------------------------------------------
# 4001 payload to AirSim Pose conversion
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
    from MissionModule.app.domain.coord_transform import wgs84_to_airsim_ned

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
    """Convert a 4001 UAM sub-payload to a cosysairsim Pose.

    Position is NED (north/east/down, meters) in local replay coordinates.
    VM forwards 4001 values to simSetVehiclePose without additional correction.
    """
    pos = vehicle_payload.get("position") or {}
    att = vehicle_payload.get("attitude") or {}
    try:
        n = float(pos.get("north", pos.get("n", 0.0)))
        e = float(pos.get("east", pos.get("e", 0.0)))
        d = float(pos.get("down", pos.get("d", 0.0)))
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


def _float_from(mapping: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key not in mapping:
            continue
        value = _safe_float(mapping.get(key))
        if value is not None:
            return float(value)
    return float(default)


def _battery_fraction_from_4001(vehicle_payload: Dict[str, Any]) -> float:
    """Extract authoritative VehicleModule battery as 0..1 for Unreal HUD.

    If this is absent, return -1 so the Unreal side can keep its legacy
    ENERGY EST. fallback.  4001 energy is a remaining battery percentage, not
    an instantaneous speed/altitude estimate.
    """
    energy = vehicle_payload.get("energy") or {}
    if not isinstance(energy, dict):
        return -1.0

    for key in ("battery_fraction", "batteryFraction", "state_of_charge_fraction", "soc_fraction"):
        value = _safe_float(energy.get(key))
        if value is not None:
            return _clamp(float(value), 0.0, 1.0)

    for key in ("battery_pct", "batteryPct", "state_of_charge_pct", "stateOfChargePct", "soc_pct", "socPct"):
        value = _safe_float(energy.get(key))
        if value is not None:
            return _clamp(float(value) / 100.0, 0.0, 1.0)

    return -1.0


def _telemetry_args_from_4001(
    vehicle_id: str,
    vehicle_payload: Dict[str, Any],
    vehicle_name: str,
) -> Optional[Tuple[Any, ...]]:
    """Build the custom AirSim telemetry RPC args from a canonical 4001 payload.

    ``simSetVehiclePose`` moves the pawn, but AirSim's internal kinematics can
    remain near zero because the pose is externally injected.  The I-key HUD
    should display DTAM 4001 telemetry, so forward the 4001 GPS velocity fields
    explicitly to Unreal.
    """
    pos = vehicle_payload.get("position") or {}
    att = vehicle_payload.get("attitude") or {}
    gps = vehicle_payload.get("gps") or {}
    baro = vehicle_payload.get("barometer") or {}
    if not isinstance(pos, dict) or not isinstance(att, dict):
        return None
    if not isinstance(gps, dict):
        gps = {}
    if not isinstance(baro, dict):
        baro = {}

    try:
        n = float(pos.get("north", pos.get("n", 0.0)) or 0.0)
        e = float(pos.get("east", pos.get("e", 0.0)) or 0.0)
        d = float(pos.get("down", pos.get("d", 0.0)) or 0.0)
    except (TypeError, ValueError):
        return None

    gps_alt = _float_from(gps, "altitude", "alt", default=-d)
    return (
        str(vehicle_id),
        str(vehicle_payload.get("currentWaypointId") or ""),
        float(n),
        float(e),
        float(d),
        _float_from(gps, "latitude", "lat", default=0.0),
        _float_from(gps, "longitude", "lon", default=0.0),
        float(gps_alt),
        _float_from(baro, "altitude", default=gps_alt),
        _float_from(baro, "pressure", default=101325.0),
        _float_from(baro, "qnh", default=1013.25),
        _float_from(gps, "velocity_north", default=0.0),
        _float_from(gps, "velocity_east", default=0.0),
        _float_from(gps, "velocity_down", default=0.0),
        _float_from(att, "roll", default=0.0),
        _float_from(att, "pitch", default=0.0),
        _float_from(att, "yaw", default=0.0),
        str(vehicle_name),
        _battery_fraction_from_4001(vehicle_payload),
    )


def _navigation_args_from_4001(
    vehicle_id: str,
    vehicle_payload: Dict[str, Any],
    vehicle_name: str,
) -> Optional[Tuple[Any, ...]]:
    navigation = vehicle_payload.get("navigation") or {}
    if not isinstance(navigation, dict) or not navigation:
        return (
            str(vehicle_id),
            False,
            0.0,
            0.0,
            "",
            "",
            str(vehicle_name),
        )

    bearing = _safe_float(navigation.get("bearingToTargetDeg"))
    distance = _safe_float(navigation.get("distanceToTargetM"))
    if bearing is None:
        return (
            str(vehicle_id),
            False,
            0.0,
            0.0,
            "",
            "",
            str(vehicle_name),
        )

    return (
        str(vehicle_id),
        True,
        float(bearing),
        float(distance or 0.0),
        str(navigation.get("nextWaypointId") or navigation.get("targetWaypointId") or ""),
        str(navigation.get("source") or "4001.navigation"),
        str(vehicle_name),
    )


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
        "energy": dict(vehicle_payload.get("energy") or {}),
        "navigation": dict(vehicle_payload.get("navigation") or {}),
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


def _match_pose_to_vehicle_name(
    target_pose: Optional[Dict[str, float]],
    pose_by_name: Dict[str, Dict[str, float]],
) -> str:
    """Best-effort AirSim default/current-view vehicle detection.

    The Unreal 1/2/3 view switch updates AirSim's default vehicle.  The stock
    AirSim RPC API does not expose that name directly, so compare
    ``simGetVehiclePose("")`` with named vehicle poses.  This lets Python-side
    modules route keyboard/joystick authority to the vehicle currently shown by
    the main Unreal view without forcing a camera switch during Autopilot play.
    """
    if not target_pose or not pose_by_name:
        return ""

    best_name = ""
    best_score = float("inf")
    second_score = float("inf")
    for name, pose in pose_by_name.items():
        try:
            dn = float(target_pose.get("north", 0.0)) - float(pose.get("north", 0.0))
            de = float(target_pose.get("east", 0.0)) - float(pose.get("east", 0.0))
            dd = float(target_pose.get("down", 0.0)) - float(pose.get("down", 0.0))
            dist_m = math.sqrt(dn * dn + de * de + dd * dd)
            yaw_delta = abs(
                ((float(target_pose.get("yaw_deg", 0.0)) - float(pose.get("yaw_deg", 0.0)) + 180.0) % 360.0) - 180.0
            )
            score = dist_m + yaw_delta * 0.02
        except Exception:
            continue
        if score < best_score:
            second_score = best_score
            best_name = str(name or "")
            best_score = score
        elif score < second_score:
            second_score = score

    # Pose calls are sequential while the aircraft may be moving.  Keep a
    # generous gate; Seoul vertiport/route aircraft are normally far farther
    # apart than this, while same-vehicle samples differ only by a small amount.
    if not best_name or best_score > 50.0:
        return ""
    # If two named vehicles match the default pose nearly equally, the view
    # target is ambiguous (common at startup before aircraft separate).  Return
    # empty so VehicleModule falls back to the capture-start target rather than
    # routing input to the wrong aircraft.
    if second_score < float("inf") and (second_score - best_score) < 0.5:
        return ""
    return best_name


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


def _iso_ts_utc(now: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(time.time() if now is None else float(now), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _vector_to_ned_dict(value: Any) -> Dict[str, float]:
    """Convert AirSim Vector3r/dict to DTAM NED dict."""
    if isinstance(value, dict):
        north = _safe_float(_first_present(value.get("north"), value.get("n"), value.get("x"), value.get("x_val")))
        east = _safe_float(_first_present(value.get("east"), value.get("e"), value.get("y"), value.get("y_val")))
        down = _safe_float(_first_present(value.get("down"), value.get("d"), value.get("z"), value.get("z_val")))
    else:
        north = _safe_float(getattr(value, "x_val", None))
        east = _safe_float(getattr(value, "y_val", None))
        down = _safe_float(getattr(value, "z_val", None))
    return {
        "north": float(north or 0.0),
        "east": float(east or 0.0),
        "down": float(down or 0.0),
    }


def _collision_info_to_4103_payload(
    info: Any,
    *,
    aircraft_id: str,
    airsim_vehicle_name: str,
    default_recommended_action: str,
) -> Optional[Dict[str, Any]]:
    """Normalize AirSim CollisionInfo to the DTAM 4103 payload shape."""
    has_collided = bool(_field(info, "has_collided", False))
    if not has_collided:
        return None

    object_name = str(_field(info, "object_name", "") or "")
    object_id = int(_safe_float(_field(info, "object_id", -1)) or -1)
    penetration_depth = float(_safe_float(_field(info, "penetration_depth", 0.0)) or 0.0)
    collision_time_nanos = int(_safe_float(_field(info, "time_stamp", 0.0)) or 0)
    if collision_time_nanos <= 0:
        collision_time_nanos = int(time.time() * 1_000_000_000)

    safe_aircraft_id = str(aircraft_id or "").strip() or str(airsim_vehicle_name or "").strip() or "UNKNOWN"
    safe_vehicle_name = str(airsim_vehicle_name or "").strip()
    safe_object_token = object_name or str(object_id)
    dedup_key = f"{safe_aircraft_id}|{collision_time_nanos}|{safe_object_token}"
    event_id = f"COL-{safe_aircraft_id}-{collision_time_nanos}"

    if penetration_depth >= 1.0:
        severity = "critical"
    elif penetration_depth > 0.0:
        severity = "warning"
    else:
        severity = "info"

    return {
        "message_id": 4103,
        "message_name": "Vehicle Collision Event",
        "timestamp": _iso_ts_utc(),
        "eventId": event_id,
        "aircraftId": safe_aircraft_id,
        "airsimVehicleName": safe_vehicle_name,
        "hasCollided": True,
        "objectName": object_name,
        "objectId": object_id,
        "positionNed": _vector_to_ned_dict(_field(info, "position", None)),
        "impactPointNed": _vector_to_ned_dict(_field(info, "impact_point", None)),
        "normalNed": _vector_to_ned_dict(_field(info, "normal", None)),
        "penetrationDepth": penetration_depth,
        "collisionTimeNanos": collision_time_nanos,
        "impactSpeedMps": 0.0,
        "severity": severity,
        "recommendedAction": str(default_recommended_action or "hold"),
        "source": "airsim.simGetCollisionInfo",
        "metadata": {
            "dedupKey": dedup_key,
            "polling": True,
            "session": 2,
        },
    }


def _aircraft_id_from_vehicle_name(vehicle_name: str) -> str:
    """Infer a DTAM aircraftId for common AirSim vehicle names.

    AirSim default multirotors are often named ``Drone1``...``Drone5`` while
    DTAM uses ``UAM0001``...``UAM0005``.  This fallback only runs when an
    explicit scenario/4001 mapping is not available.
    """

    text = str(vehicle_name or "").strip()
    match = re.search(r"(\d+)$", text)
    if match:
        try:
            idx = int(match.group(1))
            if idx > 0:
                return f"UAM{idx:04d}"
        except ValueError:
            pass
    return text or "UNKNOWN"


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
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
