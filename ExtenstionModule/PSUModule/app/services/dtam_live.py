"""Live DTAM/DT World data adapter for the PSU Monitoring console.

The StateServer `/ws/dtam` transport keeps one active socket per role.  PSU is an
extension UI and must not steal the OperationModule `monitoring` socket, so this
adapter consumes the already-normalised OperationModule 4001 cache and the local
StateServer 4001 DB/session snapshot instead of registering another monitoring
role.  The payload parsing still follows the ICD 4001 wire shape.
"""
from __future__ import annotations

import json
import math
import os
import re
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

APP_DIR = Path(__file__).resolve().parents[1]
MODULE_ROOT = APP_DIR.parent
EXTENSION_ROOT = MODULE_ROOT.parent
FRAMEWORK_ROOT = EXTENSION_ROOT.parent
VISUALIZATION_DIR = FRAMEWORK_ROOT / "VisualizationModule"
VISUALIZATION_CONFIG_PATH = VISUALIZATION_DIR / "data" / "configs" / "vm_config.json"
UNREAL_PROJECT_DIR = VISUALIZATION_DIR / "runtime" / "Unreal" / "Environments" / "DTAMVisualization"
DEFAULT_STATE_PORT = 8096
DEFAULT_OPERATION_PORTS = (8000, 8090)
STALE_AFTER_S = 3.0
DROP_AFTER_S = 45.0
POLL_INTERVAL_S = 1.0


def _iso_from_epoch(epoch_s: float) -> str:
    try:
        value = float(epoch_s)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(value) or value <= 0:
        return ""
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _first_number(*values: Any) -> float | None:
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _canonical_vehicle_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.fullmatch(r"([A-Za-z]+)[\s_-]*0*(\d+)", text)
    if not match:
        return text
    return f"{match.group(1).upper()}{match.group(2).zfill(4)}"


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _load_unreal_config() -> dict[str, Any]:
    if not VISUALIZATION_CONFIG_PATH.is_file():
        return {}
    return _load_json_file(VISUALIZATION_CONFIG_PATH)


def _is_tcp_port_open(host: str, port: int, timeout_s: float = 0.16) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return True
    except OSError:
        return False


def _is_process_running_by_name(executable: Path) -> bool:
    process_name = executable.name if executable else ""
    if not process_name:
        return False
    if os.name == "nt":
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=0.8,
            )
            lowered = output.lower()
            return process_name.lower() in lowered and "no tasks" not in lowered
        except Exception:
            return False
    try:
        output = subprocess.check_output(["pgrep", "-f", process_name], stderr=subprocess.DEVNULL, text=True, timeout=0.5)
        return bool(output.strip())
    except Exception:
        return False


def dt_world_status() -> dict[str, Any]:
    config = _load_unreal_config()
    unreal_cfg = dict(config.get("unreal") or {})
    airsim_cfg = dict(config.get("airsim") or {})
    executable = Path(
        str(
            unreal_cfg.get("executable")
            or UNREAL_PROJECT_DIR / "Saved" / "StagedBuilds" / "Windows" / "DTAMVisualization.exe"
        )
    )
    working_dir = Path(str(unreal_cfg.get("working_dir") or executable.parent))
    host = str(airsim_cfg.get("host") or os.environ.get("DTWORLD_HOST") or "127.0.0.1")
    port = int(airsim_cfg.get("port") or os.environ.get("DTWORLD_AIRSIM_PORT") or 41451)
    process_running = _is_process_running_by_name(executable)
    rpc_open = _is_tcp_port_open(host, port)
    connected = bool(process_running or rpc_open)
    return {
        "connected": connected,
        "process_running": process_running,
        "airsim_rpc_open": rpc_open,
        "airsim_rpc": {"host": host, "port": port, "open": rpc_open},
        "executable": str(executable),
        "working_dir": str(working_dir),
        "message": "DT World 연결됨" if connected else "DT World가 실행 중이 아닙니다.",
        "message_en": "DT World Connected" if connected else "DT World is not running.",
    }


class DtamLiveGateway:
    """Poll and normalise live 4001 vehicle status for the PSU map."""

    def __init__(self) -> None:
        self.target_ip = str(os.environ.get("DTAM_TARGET_IP") or "127.0.0.1")
        self.state_port = int(os.environ.get("DTAM_WS_PORT") or DEFAULT_STATE_PORT)
        self.state_base_url = f"http://{self.target_ip}:{self.state_port}"
        self.poll_interval_s = float(os.environ.get("PSU_LIVE_POLL_INTERVAL_S") or POLL_INTERVAL_S)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._vehicles: dict[str, dict[str, Any]] = {}
        self._rx_count = 0
        self._last_message_ts = ""
        self._last_received_epoch = 0.0
        self._last_error = ""
        self._last_source = "no-4001-source"
        self._state_connected = False
        self._state_last_error = ""
        self._state_db_session_dir = ""
        self._operation_url = ""
        self._operation_connected = False
        self._operation_last_error = ""
        self._operation_vehicle_count = 0
        self._last_poll_epoch = 0.0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="psu-dtam-live", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2.0)

    def _operation_status_urls(self) -> list[str]:
        urls: list[str] = []
        configured = str(os.environ.get("PSU_OPERATION_STATUS_URL") or "").strip()
        if configured:
            urls.append(configured)
        hosts = ["127.0.0.1"]
        if self.target_ip not in {"127.0.0.1", "localhost", "0.0.0.0"}:
            hosts.append(self.target_ip)
        for host in hosts:
            for port in DEFAULT_OPERATION_PORTS:
                urls.append(f"http://{host}:{port}/api/v1/simulation/vehicle-status")
        deduped: list[str] = []
        for url in urls:
            if url and url not in deduped:
                deduped.append(url)
        return deduped

    def _fetch_json(self, url: str, timeout_s: float = 0.55) -> dict[str, Any]:
        req = urllib_request.Request(url, headers={"Accept": "application/json"}, method="GET")
        with urllib_request.urlopen(req, timeout=timeout_s) as response:
            data = response.read().decode("utf-8")
        parsed = json.loads(data)
        return parsed if isinstance(parsed, dict) else {}

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh_once()
            except Exception as exc:
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
            self._stop.wait(max(0.25, self.poll_interval_s))

    def refresh_once(self) -> None:
        now = time.time()
        self._last_poll_epoch = now
        updates: dict[str, dict[str, Any]] = {}
        source = ""

        self._refresh_state_status()

        operation_updates = self._vehicles_from_operation(now)
        if operation_updates:
            updates.update(operation_updates)
            source = self._last_source

        db_updates = self._vehicles_from_state_db(now)
        if db_updates:
            updates.update(db_updates)
            source = "StateServerDB/4001"

        latest_updates = self._vehicles_from_state_latest(now)
        if latest_updates:
            updates.update(latest_updates)
            source = "StateServerREST/4001"

        if updates:
            with self._lock:
                for vehicle_id, vehicle in updates.items():
                    current = self._vehicles.get(vehicle_id)
                    current_epoch = _first_number((current or {}).get("receivedAtEpoch"), 0.0) or 0.0
                    new_epoch = _first_number(vehicle.get("receivedAtEpoch"), 0.0) or 0.0
                    if current is None or new_epoch >= current_epoch:
                        self._vehicles[vehicle_id] = vehicle
                self._rx_count += 1
                self._last_message_ts = max(
                    [str(v.get("messageTimestamp") or "") for v in updates.values()] + [self._last_message_ts]
                )
                self._last_received_epoch = max(
                    [_first_number(v.get("receivedAtEpoch"), 0.0) or 0.0 for v in updates.values()] + [self._last_received_epoch]
                )
                self._last_error = ""
                if source:
                    self._last_source = source

    def inject_4001_payload(self, payload: dict[str, Any], *, source: str = "PSUTestEmulator/4001") -> dict[str, Any]:
        """Inject one temporary 4001 payload directly into the PSU live cache.

        This is for running the PSU module without the full DTAM stack. The
        payload still uses the normal MSG 4001 wire shape, then passes through
        the same normalizer used for StateServer DB/REST data.
        """
        now = time.time()
        updates = self._vehicles_from_4001_payload(payload, source=source, received_epoch=now)
        with self._lock:
            for vehicle_id, vehicle in updates.items():
                self._vehicles[vehicle_id] = vehicle
            if updates:
                self._rx_count += 1
                self._last_message_ts = max(
                    [str(v.get("messageTimestamp") or "") for v in updates.values()] + [self._last_message_ts]
                )
                self._last_received_epoch = now
                self._last_error = ""
                self._last_source = source
        return {
            "ok": bool(updates),
            "source": source,
            "vehicle_count": len(updates),
            "vehicles": sorted(updates.keys()),
        }

    def _refresh_state_status(self) -> None:
        try:
            state = self._fetch_json(f"{self.state_base_url}/api/state", timeout_s=0.45)
            db = state.get("db") if isinstance(state.get("db"), dict) else {}
            session_dir = str(db.get("session_dir") or "")
            with self._lock:
                self._state_connected = True
                self._state_last_error = ""
                self._state_db_session_dir = session_dir
        except (OSError, TimeoutError, urllib_error.URLError, json.JSONDecodeError) as exc:
            with self._lock:
                self._state_connected = False
                self._state_last_error = str(exc)
        except Exception as exc:
            with self._lock:
                self._state_connected = False
                self._state_last_error = f"{type(exc).__name__}: {exc}"

    def _vehicles_from_operation(self, now: float) -> dict[str, dict[str, Any]]:
        last_error = ""
        for url in self._operation_status_urls():
            try:
                payload = self._fetch_json(url, timeout_s=0.45)
            except Exception as exc:
                last_error = str(exc)
                continue
            raw_vehicles = payload.get("vehicles")
            if not isinstance(raw_vehicles, list):
                last_error = "OperationModule 4001 endpoint response has no vehicles list."
                continue

            vehicles: dict[str, dict[str, Any]] = {}
            for raw in raw_vehicles:
                if not isinstance(raw, dict):
                    continue
                vehicle = self._normalize_vehicle(raw, source="OperationModule/4001", received_epoch=now)
                if vehicle:
                    vehicles[str(vehicle["aircraft_id"])] = vehicle

            with self._lock:
                self._operation_url = url
                self._operation_connected = True
                self._operation_last_error = ""
                self._operation_vehicle_count = len(raw_vehicles)
                self._last_source = "OperationModule/4001"
            return vehicles

        with self._lock:
            self._operation_connected = False
            self._operation_last_error = last_error
            self._operation_vehicle_count = 0
        return {}

    def _vehicles_from_state_latest(self, now: float) -> dict[str, dict[str, Any]]:
        try:
            latest = self._fetch_json(f"{self.state_base_url}/api/db/messages/4001/latest", timeout_s=0.45)
        except Exception:
            return {}
        payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
        modified_at = str(latest.get("modified_at") or "")
        epoch = self._epoch_from_iso(modified_at) or now
        return self._vehicles_from_4001_payload(payload, source="StateServerREST/4001", received_epoch=epoch)

    def _vehicles_from_state_db(self, now: float) -> dict[str, dict[str, Any]]:
        with self._lock:
            session_dir = self._state_db_session_dir
        if not session_dir:
            return {}
        folder = Path(session_dir) / "VehicleStatus"
        if not folder.is_dir():
            return {}
        try:
            candidates = sorted(
                (path for path in folder.glob("*.json") if path.is_file()),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )[:700]
        except Exception:
            return {}
        vehicles: dict[str, dict[str, Any]] = {}
        for path in candidates:
            if len(vehicles) >= 80:
                break
            payload = _load_json_file(path)
            if not payload:
                continue
            epoch = path.stat().st_mtime if path.exists() else now
            parsed = self._vehicles_from_4001_payload(payload, source="StateServerDB/4001", received_epoch=epoch)
            for vehicle_id, vehicle in parsed.items():
                vehicles.setdefault(vehicle_id, vehicle)
        return vehicles

    def _vehicles_from_4001_payload(
        self,
        payload: dict[str, Any],
        *,
        source: str,
        received_epoch: float,
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(payload, dict):
            return {}
        timestamp = str(payload.get("timestamp") or "")
        vehicles: dict[str, dict[str, Any]] = {}

        raw_vehicles = payload.get("vehicles") if isinstance(payload.get("vehicles"), dict) else None
        if raw_vehicles is not None:
            iterator = raw_vehicles.items()
        elif any(key in payload for key in ("aircraftId", "vehicleId", "vehicle_id")):
            iterator = [(payload.get("aircraftId") or payload.get("vehicleId") or payload.get("vehicle_id"), payload)]
        else:
            iterator = ((key, value) for key, value in payload.items() if key != "timestamp" and isinstance(value, dict))

        for vehicle_id, raw in iterator:
            if not isinstance(raw, dict):
                continue
            merged = dict(raw)
            merged.setdefault("aircraftId", vehicle_id)
            if timestamp:
                merged.setdefault("messageTimestamp", timestamp)
            vehicle = self._normalize_vehicle(merged, source=source, received_epoch=received_epoch)
            if vehicle:
                vehicles[str(vehicle["aircraft_id"])] = vehicle
        return vehicles

    @staticmethod
    def _epoch_from_iso(value: str) -> float:
        if not value:
            return 0.0
        text = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).timestamp()
        except Exception:
            return 0.0

    def _normalize_vehicle(
        self,
        raw: dict[str, Any],
        *,
        source: str,
        received_epoch: float,
    ) -> dict[str, Any] | None:
        gps = raw.get("gps") if isinstance(raw.get("gps"), dict) else {}
        position = raw.get("position") if isinstance(raw.get("position"), dict) else {}
        attitude = raw.get("attitude") if isinstance(raw.get("attitude"), dict) else {}
        vehicle_id = _canonical_vehicle_id(
            raw.get("aircraftId")
            or raw.get("aircraft_id")
            or raw.get("id")
            or raw.get("vehicle_id")
            or raw.get("vehicleId")
            or ""
        )
        lat = _first_number(gps.get("latitude"), raw.get("latitude"), raw.get("lat"))
        lon = _first_number(gps.get("longitude"), raw.get("longitude"), raw.get("lon"), raw.get("lng"))
        if not vehicle_id or lat is None or lon is None:
            return None
        alt = _first_number(gps.get("altitude"), raw.get("altitudeM"), raw.get("altitude"), raw.get("altitude_m"), 0.0) or 0.0
        vn = _first_number(gps.get("velocity_north"), gps.get("velocityNorth"), raw.get("velocity_north"), raw.get("velocityNorth"), 0.0) or 0.0
        ve = _first_number(gps.get("velocity_east"), gps.get("velocityEast"), raw.get("velocity_east"), raw.get("velocityEast"), 0.0) or 0.0
        vd = _first_number(gps.get("velocity_down"), gps.get("velocityDown"), raw.get("velocity_down"), raw.get("velocityDown"), 0.0) or 0.0
        speed_mps = _first_number(raw.get("speedMps"), raw.get("groundSpeedMps"), raw.get("speed_mps"))
        if speed_mps is None:
            speed_mps = math.hypot(vn, ve, vd)
        yaw = _first_number(attitude.get("yaw"), raw.get("yaw"))
        heading = _first_number(raw.get("headingDeg"), raw.get("heading_deg"), raw.get("heading"))
        if yaw is not None:
            heading = (yaw * 180.0 / math.pi + 360.0) % 360.0
        elif heading is None:
            heading = (math.atan2(ve, vn) * 180.0 / math.pi + 360.0) % 360.0 if (vn or ve) else 0.0

        message_ts = str(raw.get("messageTimestamp") or raw.get("timestamp") or "")
        epoch = _first_number(raw.get("receivedAtEpoch"), received_epoch) or received_epoch
        if epoch <= 0:
            epoch = time.time()
        return _json_safe(
            {
                **raw,
                "id": vehicle_id,
                "aircraftId": vehicle_id,
                "aircraft_id": vehicle_id,
                "vehicle_id": vehicle_id,
                "flight_plan_id": raw.get("flight_plan_id") or raw.get("flightPlanId") or raw.get("flightPlanNumber"),
                "current_waypoint_id": raw.get("currentWaypointId") or raw.get("current_waypoint_id") or "",
                "currentWaypointId": raw.get("currentWaypointId") or raw.get("current_waypoint_id") or "",
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "altitude_m": alt,
                "speed_mps": speed_mps,
                "ground_speed_mps": speed_mps,
                "heading": heading,
                "heading_deg": heading,
                "position": position,
                "attitude": attitude,
                "gps": gps,
                "messageTimestamp": message_ts,
                "receivedAt": _iso_from_epoch(epoch),
                "receivedAtEpoch": epoch,
                "source": source,
            }
        )

    def vehicle_snapshot(self, *, include_stale: bool = True) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            items = []
            for vehicle in self._vehicles.values():
                received_epoch = _first_number(vehicle.get("receivedAtEpoch"), 0.0) or 0.0
                age_s = max(0.0, now - received_epoch) if received_epoch else None
                if age_s is not None and age_s > DROP_AFTER_S and not include_stale:
                    continue
                item = dict(vehicle)
                item["age_s"] = round(age_s, 3) if age_s is not None else None
                item["stale"] = bool(age_s is not None and age_s > STALE_AFTER_S)
                if not include_stale and item["stale"]:
                    continue
                items.append(_json_safe(item))
            items.sort(key=lambda item: str(item.get("aircraft_id") or item.get("aircraftId") or ""))
            return {
                "listening": self.running,
                "transport": "rest-db-poll",
                "state_server": {
                    "url": self.state_base_url,
                    "connected": self._state_connected,
                    "db_session_dir": self._state_db_session_dir,
                    "last_error": self._state_last_error,
                },
                "operation_status": {
                    "url": self._operation_url,
                    "connected": self._operation_connected,
                    "vehicle_count": self._operation_vehicle_count,
                    "last_error": self._operation_last_error,
                },
                "operation_status_url": self._operation_url,
                "source": self._last_source,
                "rx_count": self._rx_count,
                "last_message_timestamp": self._last_message_ts,
                "last_received_at": _iso_from_epoch(self._last_received_epoch) if self._last_received_epoch else "",
                "last_error": self._last_error,
                "vehicles": items,
            }

    def live_tracks(self, *, include_stale: bool = False) -> list[dict[str, Any]]:
        snapshot = self.vehicle_snapshot(include_stale=include_stale)
        tracks: list[dict[str, Any]] = []
        for vehicle in snapshot.get("vehicles") or []:
            if not include_stale and vehicle.get("stale"):
                continue
            tracks.append(
                {
                    "aircraft_id": vehicle.get("aircraft_id") or vehicle.get("aircraftId"),
                    "flight_plan_id": vehicle.get("flight_plan_id"),
                    "latitude": vehicle.get("latitude"),
                    "longitude": vehicle.get("longitude"),
                    "altitude": vehicle.get("altitude"),
                    "ground_speed": vehicle.get("ground_speed_mps"),
                    "ground_speed_mps": vehicle.get("ground_speed_mps"),
                    "heading": vehicle.get("heading"),
                    "heading_deg": vehicle.get("heading_deg"),
                    "current_waypoint_id": vehicle.get("current_waypoint_id") or vehicle.get("currentWaypointId"),
                    "flight_status": "STALE" if vehicle.get("stale") else "ACTIVE",
                    "status": "ACTIVE" if not vehicle.get("stale") else "CAUTION",
                    "severity": "NORMAL" if not vehicle.get("stale") else "CAUTION",
                    "timestamp": vehicle.get("messageTimestamp") or vehicle.get("receivedAt"),
                    "received_at": vehicle.get("receivedAt"),
                    "age_s": vehicle.get("age_s"),
                    "source": vehicle.get("source") or "ICD-4001",
                    "data_source": "ICD-4001",
                }
            )
        return tracks

    def status(self) -> dict[str, Any]:
        dt_world = dt_world_status()
        vehicles = self.vehicle_snapshot(include_stale=True)
        fresh_count = sum(1 for item in vehicles.get("vehicles") or [] if not item.get("stale"))
        state_server = vehicles.get("state_server") if isinstance(vehicles.get("state_server"), dict) else {}
        operation_status = vehicles.get("operation_status") if isinstance(vehicles.get("operation_status"), dict) else {}
        server_connected = bool(fresh_count > 0 or state_server.get("connected") or operation_status.get("connected"))
        with self._lock:
            data_link = "LIVE_4001" if fresh_count else "WAITING_4001" if server_connected else "OFFLINE"
            if fresh_count:
                message = f"4001 실시간 수신 중 · {fresh_count} UAM"
            elif server_connected:
                message = "4001 서버 연결됨 · 실시간 비행체 대기"
            else:
                message = "4001 서버 연결 안 됨"
            return {
                # This connection flag is intentionally ICD 4001 server readiness,
                # not DT World/Unreal process status.
                "connected": server_connected,
                "dt_world": dt_world,
                "state_server": state_server,
                "operation_status": operation_status,
                "vehicle_stream": {
                    "connected": fresh_count > 0,
                    "server_connected": server_connected,
                    "fresh_vehicle_count": fresh_count,
                    "total_vehicle_count": len(vehicles.get("vehicles") or []),
                    "source": self._last_source,
                    "rx_count": self._rx_count,
                    "last_received_at": vehicles.get("last_received_at"),
                },
                "data_link_health": data_link,
                "message": message,
            }


_gateway: DtamLiveGateway | None = None
_gateway_lock = threading.Lock()


def get_live_gateway() -> DtamLiveGateway:
    global _gateway
    with _gateway_lock:
        if _gateway is None:
            _gateway = DtamLiveGateway()
        return _gateway


__all__ = ["DtamLiveGateway", "dt_world_status", "get_live_gateway"]
