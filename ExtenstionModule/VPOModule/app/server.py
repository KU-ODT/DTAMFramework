"""FastAPI server for the Vertiport Operations Monitoring module."""
from __future__ import annotations

import csv
import json
import math
import os
import socket
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"
FRAMEWORK_ROOT = APP_DIR.parents[2]
VISUALIZATION_DIR = FRAMEWORK_ROOT / "VisualizationModule"
VISUALIZATION_DATA_DIR = VISUALIZATION_DIR / "data"
VISUALIZATION_CONFIG_PATH = VISUALIZATION_DATA_DIR / "configs" / "vm_config.json"
UNREAL_PROJECT_DIR = VISUALIZATION_DIR / "runtime" / "Unreal" / "Environments" / "DTAMVisualization"
UNREAL_DATA_DIR = UNREAL_PROJECT_DIR / "Data"
UNREAL_COORD_DIR = UNREAL_DATA_DIR / "coordinateDB"
UNREAL_GROUNDMAP_DIR = UNREAL_DATA_DIR / "groundmaps"
UNREAL_STAGED_WINDOWS_DIR = UNREAL_PROJECT_DIR / "Saved" / "StagedBuilds" / "Windows"
UNREAL_STAGED_PROJECT_COORD_DIR = UNREAL_STAGED_WINDOWS_DIR / "DTAMVisualization" / "Data" / "coordinateDB"
UNREAL_STAGED_LAUNCH_COORD_DIR = UNREAL_STAGED_WINDOWS_DIR / "Data" / "coordinateDB"
SOURCE_COORD_DIR = VISUALIZATION_DATA_DIR / "coordinateDB"
SOURCE_GROUNDMAP_DIR = VISUALIZATION_DATA_DIR / "groundmaps"
VPO_CAMERA_MANIFEST = "vpo_camera_views.csv"
VPO_CAMERA_LINK_DISABLED = os.getenv("DTAM_ENABLE_VPO_CAMERAS", "0").strip().lower() in {
    "0",
    "false",
    "no",
    "off",
}
VPO_CAMERA_LINK_ENABLED = not VPO_CAMERA_LINK_DISABLED
DEFAULT_VISUALIZATION_URL = os.getenv("DTAM_VISUALIZATION_URL", "http://127.0.0.1:8097")
DEFAULT_VPO_STREAM_FPS = float(os.getenv("DTAM_VPO_STREAM_FPS", "3") or 3)
DEFAULT_VPO_STREAM_QUALITY = int(os.getenv("DTAM_VPO_STREAM_QUALITY", "55") or 55)

STATUS_ROTATION = ["available", "occupied", "turnaround", "reserved"]
VEHICLE_STATES = ["approach", "landing", "taxi", "charging", "boarding", "departure"]

CAMERA_VIEW_TEMPLATES: List[Dict[str, Any]] = [
    {
        "suffix": "overview-top",
        "name": "Vertiport CCTV Top",
        "sector": "Vertiport Overview",
        "type": "Top-down CCTV",
        "angle": "24 mm",
        "lens_mm": 24,
        "fov_deg": 58,
    },
]

FALLBACK_VERTIPORTS: List[Dict[str, Any]] = [
    {
        "id": "seocho-skyport",
        "source_name": "Seocho Skyport",
        "name": "Seocho Skyport",
        "code": "VPO-SEL-01",
        "city": "Seoul",
        "subtitle": "Fallback monitoring preview",
        "class_name": "port",
        "seed": 0.2,
        "capacity": 36,
        "latitude": 37.496291,
        "longitude": 127.023303,
        "angle_deg": 69.0,
        "pads": [
            {"id": "FATO-1", "label": "F1", "x": 30, "y": 26, "type": "fato"},
            {"id": "FATO-2", "label": "F2", "x": 70, "y": 26, "type": "fato"},
            {"id": "STAND-A", "label": "A", "x": 23, "y": 62, "type": "stand"},
            {"id": "STAND-B", "label": "B", "x": 50, "y": 72, "type": "stand"},
            {"id": "STAND-C", "label": "C", "x": 77, "y": 62, "type": "stand"},
        ],
        "gates": [
            {"id": "G1", "label": "Gate 1", "x": 11, "y": 44},
            {"id": "G2", "label": "Gate 2", "x": 89, "y": 44},
            {"id": "MRO", "label": "MRO", "x": 50, "y": 91},
        ],
        "cameras": [],
    }
]


def _first_existing_path(candidates: Iterable[Path]) -> Optional[Path]:
    for path in candidates:
        if path.is_file():
            return path
    return None


def _read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            return []
    return []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_node_name(value: Any) -> str:
    return str(value or "").replace("\ufeff", "").replace('"', "").strip()


def _resolve_camera_frame_path(frame_name: Any) -> Optional[Path]:
    if not VPO_CAMERA_LINK_ENABLED:
        return None

    safe_name = Path(_normalize_node_name(frame_name)).name
    if not safe_name:
        return None

    candidates = [
        UNREAL_STAGED_PROJECT_COORD_DIR / "vpo_camera_frames" / safe_name,
        UNREAL_STAGED_LAUNCH_COORD_DIR / "vpo_camera_frames" / safe_name,
        UNREAL_COORD_DIR / "vpo_camera_frames" / safe_name,
        SOURCE_COORD_DIR / "vpo_camera_frames" / safe_name,
    ]
    return _first_existing_path(candidates)


def _camera_frame_url(frame_name: Any) -> str:
    if not VPO_CAMERA_LINK_ENABLED:
        return ""

    safe_name = Path(_normalize_node_name(frame_name)).name
    if not safe_name:
        return ""
    if not _resolve_camera_frame_path(safe_name):
        return ""
    return f"/api/camera-frames/{safe_name}"


def _wave(now: float, offset: float, period: float = 1.0) -> float:
    return (math.sin((now / max(period, 0.1)) + offset) + 1.0) / 2.0


def _seed_for_name(name: str, index: int) -> float:
    total = sum((idx + 3) * ord(ch) for idx, ch in enumerate(name))
    return (index + 1) * 0.71 + (total % 97) / 37.0


def _load_unreal_config() -> Dict[str, Any]:
    if not VISUALIZATION_CONFIG_PATH.is_file():
        return {}
    try:
        return json.loads(VISUALIZATION_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _is_tcp_port_open(host: str, port: int, timeout_s: float = 0.16) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return True
    except OSError:
        return False


def _base_url(value: Any, default: str = DEFAULT_VISUALIZATION_URL) -> str:
    text = str(value or default).strip().rstrip("/")
    if not text.startswith(("http://", "https://")):
        text = "http://" + text
    return text.rstrip("/")


def _json_request(method: str, url: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 2.0) -> Dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = UrlRequest(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return {"ok": True, "status": int(response.status)}
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {"ok": True, "data": parsed, "status": int(response.status)}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {"ok": False, "status": int(exc.code), "error": detail or str(exc)}
    except (OSError, URLError, TimeoutError) as exc:
        return {"ok": False, "error": str(exc)}
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid JSON response: {exc}"}


def _vpo_stream_descriptor_fallback(
    *,
    camera_id: str,
    vertiport: Dict[str, Any],
    fps: float,
    quality: int,
    frame_url: str = "",
    warning: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    safe_fps = max(0.2, min(12.0, float(fps or DEFAULT_VPO_STREAM_FPS)))
    safe_quality = max(10, min(95, int(quality or DEFAULT_VPO_STREAM_QUALITY)))
    return {
        "message_id": 4102,
        "message_name": "Camera Stream Descriptor",
        "stream_id": f"{vertiport.get('id') or 'VPO'}-{camera_id}-vpo-mjpeg",
        "vehicle_id": vertiport.get("id") or "VPO",
        "camera_id": camera_id,
        "camera_name": camera_id,
        "vertiport_id": vertiport.get("id") or "",
        "vertiport_name": vertiport.get("name") or "",
        "stream_type": "mjpeg",
        "transport": "http",
        "codec": "mjpeg",
        "encoding": "jpeg",
        "url": "",
        "frame_url": frame_url,
        "fps": safe_fps,
        "quality": safe_quality,
        "width": 960,
        "height": 540,
        "status": "snapshot-fallback",
        "source": "unreal_scene_capture",
        "media_plane": "local-vpo-frame",
        "cache_policy": "latest-frame-only",
        "warning": warning,
    }


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


def _dt_world_status() -> Dict[str, Any]:
    config = _load_unreal_config()
    unreal_cfg = dict(config.get("unreal") or {})
    airsim_cfg = dict(config.get("airsim") or {})

    executable = Path(str(unreal_cfg.get("executable") or UNREAL_PROJECT_DIR / "Saved" / "StagedBuilds" / "Windows" / "DTAMVisualization.exe"))
    working_dir = Path(str(unreal_cfg.get("working_dir") or executable.parent))
    host = str(airsim_cfg.get("host") or "127.0.0.1")
    port = int(airsim_cfg.get("port") or 41451)

    # VPO is detached by default: no TCP connect and no Visualization REST call here.
    # CCTV/video requests may touch Unreal only through /api/streams?connect=true.
    process_running = _is_process_running_by_name(executable)
    rpc_open = False
    connected = bool(process_running)
    message = "DT World 프로세스 감지됨 - VPO 요청 대기" if process_running else "DT World가 켜지지 않았습니다."

    return {
        "connected": connected,
        "dt_world_available": process_running,
        "link_mode": "detached",
        "link_message": "VPO는 자동 연결하지 않습니다. CCTV 요청 시에만 연결을 시도합니다.",
        "process_running": process_running,
        "airsim_rpc_open": rpc_open,
        "airsim_rpc": {"host": host, "port": port, "open": rpc_open},
        "executable": str(executable),
        "working_dir": str(working_dir),
        "message": message,
        "message_en": "DT World process detected; VPO is waiting for an explicit CCTV request." if process_running else "DT World is not running.",
    }


def _load_layout() -> Dict[str, List[Dict[str, Any]]]:
    path = _first_existing_path([
        UNREAL_COORD_DIR / "vertiportMap_KU.csv",
        SOURCE_COORD_DIR / "vertiportMap_KU.csv",
    ])
    if not path:
        return {"pads": deepcopy(FALLBACK_VERTIPORTS[0]["pads"]), "gates": deepcopy(FALLBACK_VERTIPORTS[0]["gates"])}

    rows = _read_csv_rows(path)
    relevant = [row for row in rows if _normalize_node_name(row.get("node_type")).lower() in {"gate", "pad"}]
    if not relevant:
        return {"pads": deepcopy(FALLBACK_VERTIPORTS[0]["pads"]), "gates": deepcopy(FALLBACK_VERTIPORTS[0]["gates"])}

    xs = [_safe_float(row.get("local_x_cm")) for row in relevant]
    ys = [_safe_float(row.get("local_y_cm")) for row in relevant]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    def to_percent(row: Dict[str, Any]) -> tuple[float, float]:
        x = _safe_float(row.get("local_x_cm"))
        y = _safe_float(row.get("local_y_cm"))
        x_pct = 13.0 + ((x - min_x) / max(max_x - min_x, 1.0)) * 74.0
        y_pct = 26.0 + ((y - min_y) / max(max_y - min_y, 1.0)) * 46.0
        return round(x_pct, 2), round(y_pct, 2)

    gates: List[Dict[str, Any]] = []
    pads: List[Dict[str, Any]] = []
    for row in relevant:
        node_type = _normalize_node_name(row.get("node_type")).lower()
        semantic_id = _normalize_node_name(row.get("semantic_id")) or _normalize_node_name(row.get("node_id"))
        x_pct, y_pct = to_percent(row)
        if node_type == "pad":
            pads.append({
                "id": semantic_id or f"PAD-{len(pads) + 1}",
                "label": semantic_id or f"P{len(pads) + 1}",
                "x": x_pct,
                "y": y_pct,
                "type": "fato" if semantic_id.upper().startswith("F") else "stand",
                "source_node_id": _normalize_node_name(row.get("node_id")),
            })
        else:
            gates.append({
                "id": semantic_id or f"GATE-{len(gates) + 1}",
                "label": semantic_id or f"Gate {len(gates) + 1}",
                "x": x_pct,
                "y": y_pct,
                "source_node_id": _normalize_node_name(row.get("node_id")),
            })

    return {"pads": pads or deepcopy(FALLBACK_VERTIPORTS[0]["pads"]), "gates": gates or deepcopy(FALLBACK_VERTIPORTS[0]["gates"])}


def _load_camera_manifest() -> Dict[str, List[Dict[str, Any]]]:
    path = _first_existing_path([
        UNREAL_STAGED_PROJECT_COORD_DIR / VPO_CAMERA_MANIFEST,
        UNREAL_STAGED_LAUNCH_COORD_DIR / VPO_CAMERA_MANIFEST,
        UNREAL_COORD_DIR / VPO_CAMERA_MANIFEST,
        SOURCE_COORD_DIR / VPO_CAMERA_MANIFEST,
    ])
    if not path:
        return {}

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in _read_csv_rows(path):
        vertiport_name = _normalize_node_name(row.get("vertiport_name"))
        camera_id = _normalize_node_name(row.get("camera_id"))
        if not vertiport_name or not camera_id:
            continue
        lens_mm = _safe_float(row.get("lens_mm"), 0.0)
        frame_file = _normalize_node_name(row.get("frame_file")) or f"{camera_id}.png"
        frame_relative_path = _normalize_node_name(row.get("frame_relative_path"))
        frame_url = _camera_frame_url(frame_file)
        camera = {
            "id": camera_id,
            "name": _normalize_node_name(row.get("view_name")) or camera_id,
            "sector": _normalize_node_name(row.get("sector")) or "DT World View",
            "angle": f"{lens_mm:g} mm" if lens_mm > 0 else "24 mm",
            "type": _normalize_node_name(row.get("camera_type")) or "SceneCapture",
            "source": _normalize_node_name(row.get("source")) or "unreal_scene_capture",
            "view_suffix": _normalize_node_name(row.get("view_suffix")),
            "unreal_actor": _normalize_node_name(row.get("unreal_actor")),
            "frame_file": frame_file,
            "frame_relative_path": frame_relative_path or f"vpo_camera_frames/{frame_file}",
            "frame_url": frame_url,
            "has_frame": bool(frame_url),
            "pose": {
                "local_cm": {
                    "x": _safe_float(row.get("local_x_cm")),
                    "y": _safe_float(row.get("local_y_cm")),
                    "z": _safe_float(row.get("local_z_cm")),
                },
                "world_cm": {
                    "x": _safe_float(row.get("world_x_cm")),
                    "y": _safe_float(row.get("world_y_cm")),
                    "z": _safe_float(row.get("world_z_cm")),
                },
                "rotation_deg": {
                    "pitch": _safe_float(row.get("pitch_deg")),
                    "yaw": _safe_float(row.get("yaw_deg")),
                    "roll": _safe_float(row.get("roll_deg")),
                },
            },
        }
        grouped.setdefault(vertiport_name, []).append(camera)

    return grouped


def _default_cameras_for_vertiport(vertiport_index: int) -> List[Dict[str, Any]]:
    cameras: List[Dict[str, Any]] = []
    for view_index, template in enumerate(CAMERA_VIEW_TEMPLATES, start=1):
        camera_id = f"VPO-{vertiport_index + 1:03d}-{view_index:02d}"
        frame_file = f"{camera_id}.png"
        frame_url = _camera_frame_url(frame_file)
        cameras.append({
            "id": camera_id,
            "name": template["name"],
            "sector": template["sector"],
            "angle": template["angle"],
            "type": template["type"],
            "source": "planned_unreal_scene_capture",
            "view_suffix": template["suffix"],
            "lens_mm": template["lens_mm"],
            "fov_deg": template["fov_deg"],
            "frame_file": frame_file,
            "frame_relative_path": f"vpo_camera_frames/{frame_file}",
            "frame_url": frame_url,
            "has_frame": bool(frame_url),
        })
    return cameras


def _load_vertiports() -> List[Dict[str, Any]]:
    vertiport_path = _first_existing_path([
        UNREAL_COORD_DIR / "vertiport_UE.csv",
        SOURCE_COORD_DIR / "vertiport_UE.csv",
    ])
    if not vertiport_path:
        fallback = deepcopy(FALLBACK_VERTIPORTS)
        fallback[0]["cameras"] = _default_cameras_for_vertiport(0)
        return fallback

    layout = _load_layout()
    manifest = _load_camera_manifest()
    rows = _read_csv_rows(vertiport_path)
    vertiports: List[Dict[str, Any]] = []

    for index, row in enumerate(rows):
        name = _normalize_node_name(row.get("Name"))
        if not name:
            continue
        class_name = _normalize_node_name(row.get("Class")) or "port"
        cameras = manifest.get(name) or _default_cameras_for_vertiport(index)
        is_hub = class_name.lower() == "hub"
        vertiports.append({
            "id": f"dtw-{index + 1:03d}",
            "source_name": name,
            "name": name,
            "code": f"DTW-{index + 1:03d}",
            "city": "Seoul / Capital Area",
            "subtitle": "DT World Hub" if is_hub else "DT World Vertiport",
            "class_name": class_name,
            "seed": _seed_for_name(name, index),
            "capacity": 44 if is_hub else 28,
            "latitude": _safe_float(row.get("Latitude")),
            "longitude": _safe_float(row.get("Longitude")),
            "angle_deg": _safe_float(row.get("AngleDegrees")),
            "pads": deepcopy(layout["pads"]),
            "gates": deepcopy(layout["gates"]),
            "cameras": deepcopy(cameras),
        })

    if not vertiports:
        fallback = deepcopy(FALLBACK_VERTIPORTS)
        fallback[0]["cameras"] = _default_cameras_for_vertiport(0)
        return fallback
    return vertiports


def _find_vertiport(vertiport_id: str | None) -> Dict[str, Any]:
    vertiports = _load_vertiports()
    if not vertiport_id:
        return vertiports[0]
    for vertiport in vertiports:
        if vertiport["id"] == vertiport_id or vertiport.get("source_name") == vertiport_id or vertiport["name"] == vertiport_id:
            return vertiport
    raise HTTPException(status_code=404, detail=f"Unknown vertiport: {vertiport_id}")


def _build_pads(vertiport: Dict[str, Any], now: float) -> List[Dict[str, Any]]:
    pads = []
    seed = float(vertiport["seed"])
    for idx, pad in enumerate(vertiport["pads"]):
        status_index = int((now / 16.0) + idx + seed) % len(STATUS_ROTATION)
        status = STATUS_ROTATION[status_index]
        eta = int(2 + (_wave(now, seed + idx, 8.0) * 13))
        pads.append({
            **pad,
            "status": status,
            "eta_min": eta,
            "battery_target_pct": int(72 + _wave(now, idx + seed, 11.0) * 24),
            "surface_clear": status != "turnaround",
        })
    return pads


def _build_vehicles(vertiport: Dict[str, Any], now: float, dt_world: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not dt_world.get("connected"):
        return []
    vehicles = []
    seed = float(vertiport["seed"])
    count = 4 + int(_wave(now, seed, 14.0) * 4)
    for idx in range(count):
        phase = (now * 0.035) + seed + (idx * math.tau / max(count, 1))
        lane = 0.78 if idx % 2 else 1.0
        x = 50 + math.cos(phase) * 34 * lane
        y = 50 + math.sin(phase) * 23 * lane
        status = VEHICLE_STATES[(idx + int(now / 18.0)) % len(VEHICLE_STATES)]
        vehicles.append({
            "id": f"UAM-{idx + 1:04d}",
            "callsign": f"SKY{120 + idx}",
            "x": max(7, min(93, round(x, 2))),
            "y": max(9, min(91, round(y, 2))),
            "heading_deg": round((math.degrees(phase) + 90) % 360, 1),
            "altitude_m": int(0 if status in {"taxi", "charging", "boarding"} else 18 + _wave(now, idx, 7.0) * 82),
            "speed_kmh": int(4 + _wave(now, idx + seed, 6.0) * (82 if status in {"approach", "departure"} else 18)),
            "state": status,
            "battery_pct": int(48 + _wave(now, idx + 0.4, 9.0) * 49),
        })
    return vehicles


def _build_cameras(vertiport: Dict[str, Any], now: float, dt_world: Dict[str, Any]) -> List[Dict[str, Any]]:
    cameras = []
    seed = float(vertiport["seed"])
    connected = bool(dt_world.get("connected"))
    for idx, camera in enumerate(vertiport["cameras"]):
        frame_file = camera.get("frame_file") or f"{camera.get('id', f'camera-{idx + 1}')}.png"
        frame_url = _camera_frame_url(frame_file)
        base_camera = {
            **camera,
            "frame_file": frame_file,
            "frame_url": frame_url,
            "has_frame": bool(frame_url),
            "stream_url": camera.get("stream_url") or "",
            "stream_endpoint": (
                f"/api/streams?vertiport_id={vertiport.get('id', '')}&camera_id={camera.get('id', '')}"
            ),
            "supports_stream": True,
            "stream_type": "mjpeg",
        }
        if not connected:
            cameras.append({
                **base_camera,
                "status": "offline",
                "signal_pct": 0,
                "latency_ms": 0,
                "motion_pct": 0,
                "ai_label": "DT World offline",
                "recording": False,
            })
            continue

        reconnecting = int(now / 51.0 + idx + seed) % 23 == 0
        motion = int(12 + _wave(now, idx + seed, 5.4) * 84)
        if not frame_url:
            cameras.append({
                **base_camera,
                "status": "standby",
                "signal_pct": int(45 + _wave(now, idx + seed, 10.0) * 20),
                "latency_ms": 0,
                "motion_pct": 0,
                "ai_label": "on-demand CCTV standby",
                "recording": False,
            })
            continue
        cameras.append({
            **base_camera,
            "status": "reconnecting" if reconnecting else "online",
            "signal_pct": int(68 + _wave(now, idx + seed, 10.0) * 31),
            "latency_ms": int(42 + _wave(now, idx + 1.3, 6.0) * 54),
            "motion_pct": motion,
            "ai_label": "UAM detected" if motion > 68 else "clear apron",
            "recording": not reconnecting,
        })
    return cameras


def _build_alerts(
    vertiport: Dict[str, Any],
    now: float,
    pads: List[Dict[str, Any]],
    cameras: List[Dict[str, Any]],
    dt_world: Dict[str, Any],
) -> List[Dict[str, str]]:
    alerts: List[Dict[str, str]] = []
    if not dt_world.get("connected"):
        alerts.append({
            "level": "warning",
            "title": "DT World가 켜지지 않았습니다.",
            "body": "Unreal/DT World 실행을 기다리는 중입니다. 켜지면 VPO가 자동으로 다시 연결됩니다.",
            "title_en": "DT World is not running.",
            "body_en": "Waiting for Unreal/DT World. VPO reconnects automatically when it starts.",
        })
        return alerts

    occupied = sum(1 for pad in pads if pad["status"] == "occupied")
    waiting_frames = [camera for camera in cameras if camera["status"] == "waiting_frame"]
    reconnecting = [camera for camera in cameras if camera["status"] != "online"]
    if waiting_frames:
        alerts.append({
            "level": "warning",
            "title": "Unreal 카메라 프레임 대기",
            "body": f"{waiting_frames[0]['id']} SceneCapture 프레임이 아직 생성되지 않았습니다. 최신 DT World 빌드를 실행해 주세요.",
            "title_en": "Waiting for Unreal camera frames",
            "body_en": f"{waiting_frames[0]['id']} SceneCapture frame has not been exported yet. Run the latest DT World build.",
        })
    if occupied >= max(2, len(pads) // 2):
        alerts.append({
            "level": "notice",
            "title": "패드 사용률 상승",
            "body": f"{occupied}개 패드가 사용 중입니다. 지상 이동 간격을 유지하세요.",
            "title_en": "Pad Utilization Rising",
            "body_en": f"{occupied} pads are in use. Maintain safe ground movement spacing.",
        })
    reconnecting_only = [camera for camera in reconnecting if camera["status"] == "reconnecting"]
    if reconnecting_only:
        alerts.append({
            "level": "warning",
            "title": "CCTV 신호 복구 중",
            "body": f"{reconnecting_only[0]['id']} 영상 신호가 복구 중입니다.",
            "title_en": "CCTV Reconnecting",
            "body_en": f"{reconnecting_only[0]['id']} video signal is recovering.",
        })
    if _wave(now, float(vertiport["seed"]), 19.0) > 0.86:
        alerts.append({
            "level": "success",
            "title": "정시 운항 양호",
            "body": "최근 15분 동안 도착·출발 슬롯이 안정적으로 유지되었습니다.",
            "title_en": "On-Time Performance Strong",
            "body_en": "Arrival and departure slots have stayed stable for the last 15 minutes.",
        })
    if not alerts:
        alerts.append({
            "level": "success",
            "title": "운영 상태 정상",
            "body": "감시 구역, 패드, 터미널 흐름이 정상 범위입니다.",
            "title_en": "Operations Normal",
            "body_en": "Surveillance zones, pads, and terminal flows are within normal range.",
        })
    return alerts[:3]


def _build_status(vertiport_id: str | None) -> Dict[str, Any]:
    vertiport = deepcopy(_find_vertiport(vertiport_id))
    dt_world = _dt_world_status()
    now = time.time()
    seed = float(vertiport["seed"])
    pads = _build_pads(vertiport, now)
    vehicles = _build_vehicles(vertiport, now, dt_world)
    cameras = _build_cameras(vertiport, now, dt_world)
    online_count = sum(1 for camera in cameras if camera["status"] == "online")
    available_pads = sum(1 for pad in pads if pad["status"] == "available") if dt_world.get("connected") else 0
    queue = int(3 + _wave(now, seed + 1.2, 8.0) * 7) if dt_world.get("connected") else 0
    departures = int(8 + _wave(now, seed, 11.0) * 9) if dt_world.get("connected") else 0
    arrivals = int(7 + _wave(now, seed + 0.6, 10.0) * 10) if dt_world.get("connected") else 0
    pax = int(118 + _wave(now, seed + 2.3, 13.0) * 170) if dt_world.get("connected") else 0
    wind = 4.2 + _wave(now, seed + 0.5, 12.0) * 7.4

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dt_world": dt_world,
        "vertiport": {
            "id": vertiport["id"],
            "source_name": vertiport.get("source_name", vertiport["name"]),
            "name": vertiport["name"],
            "code": vertiport["code"],
            "city": vertiport["city"],
            "subtitle": vertiport["subtitle"],
            "class_name": vertiport.get("class_name", "port"),
            "capacity": vertiport["capacity"],
            "latitude": vertiport.get("latitude"),
            "longitude": vertiport.get("longitude"),
            "angle_deg": vertiport.get("angle_deg"),
        },
        "layout": {
            "pads": pads,
            "gates": vertiport["gates"],
            "corridors": [
                {"id": "north-final", "label": "North Final", "status": "clear"},
                {"id": "ground-alpha", "label": "Ground Alpha", "status": "metered" if queue > 7 else "clear"},
                {"id": "south-departure", "label": "South Departure", "status": "clear"},
            ],
        },
        "vehicles": vehicles,
        "cameras": cameras,
        "metrics": {
            "available_pads": available_pads,
            "total_pads": len(pads),
            "camera_online": online_count,
            "camera_total": len(cameras),
            "arrivals_30m": arrivals,
            "departures_30m": departures,
            "queue": queue,
            "passenger_flow_h": pax,
            "on_time_pct": round(91 + _wave(now, seed, 10.0) * 7.8, 1) if dt_world.get("connected") else 0,
            "turnaround_min": round(7.2 + _wave(now, seed + 0.3, 8.0) * 4.8, 1) if dt_world.get("connected") else 0,
            "energy_load_kw": int(420 + _wave(now, seed + 2.0, 10.0) * 390) if dt_world.get("connected") else 0,
        },
        "weather": {
            "condition": "Clear" if wind < 8.8 else "Gust Watch",
            "wind_kts": round(wind, 1),
            "gust_kts": round(wind + 2.0 + _wave(now, seed + 1.7, 7.0) * 4.0, 1),
            "visibility_km": round(9.4 + _wave(now, seed + 1.1, 16.0) * 5.6, 1),
            "temperature_c": round(18 + _wave(now, seed + 2.1, 20.0) * 7, 1),
            "qnh_hpa": int(1008 + _wave(now, seed + 0.9, 30.0) * 12),
        },
        "alerts": _build_alerts(vertiport, now, pads, cameras, dt_world),
        "timeline": [
            {
                "time": "+02",
                "title": "UAM-0003 FATO 접근" if dt_world.get("connected") else "DT World 연결 대기",
                "detail": "North Final corridor" if dt_world.get("connected") else "Unreal 실행 후 자동 연결",
                "title_en": "UAM-0003 approaching FATO" if dt_world.get("connected") else "Waiting for DT World",
                "detail_en": "North Final corridor" if dt_world.get("connected") else "Auto-reconnect after Unreal starts",
            },
            {
                "time": "+06",
                "title": "STAND-B 충전 완료",
                "detail": "배터리 목표 92%",
                "title_en": "STAND-B charging complete",
                "detail_en": "Battery target 92%",
            },
            {
                "time": "+11",
                "title": "SKY124 탑승 마감",
                "detail": "Gate 2 → FATO-2",
                "title_en": "SKY124 boarding closes",
                "detail_en": "Gate 2 → FATO-2",
            },
            {
                "time": "+18",
                "title": "남측 출발 슬롯",
                "detail": "분리 간격 90초 유지",
                "title_en": "South departure slot",
                "detail_en": "Maintain 90 sec separation",
            },
        ],
    }


def _camera_detail(camera_id: str, vertiport_id: str | None = None) -> Dict[str, Any]:
    status = _build_status(vertiport_id)
    for camera in status["cameras"]:
        if camera["id"] == camera_id:
            return {
                "vertiport": status["vertiport"],
                "dt_world": status["dt_world"],
                "camera": camera,
                "timestamp": status["timestamp"],
            }
    raise HTTPException(status_code=404, detail=f"Unknown camera: {camera_id}")


def create_app() -> FastAPI:
    app = FastAPI(
        title="VPOModule Vertiport Monitoring",
        summary="Premium vertiport CCTV/layout/operations monitoring dashboard.",
        version="0.2.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))

    @app.get("/cctv/{camera_id}", response_class=HTMLResponse)
    async def cctv_focus(camera_id: str) -> HTMLResponse:  # noqa: ARG001 - path is read by JS
        return HTMLResponse((WEB_DIR / "cctv.html").read_text(encoding="utf-8"))

    @app.get("/api/health")
    async def health() -> Dict[str, Any]:
        return {"ok": "true", "module": "VPOModule", "dt_world": _dt_world_status()}

    @app.get("/api/dt-world")
    async def dt_world() -> Dict[str, Any]:
        return _dt_world_status()

    @app.get("/api/vertiports")
    async def vertiports() -> Dict[str, Any]:
        dt_world_status = _dt_world_status()
        items = _load_vertiports()
        return {
            "dt_world": dt_world_status,
            "items": [
                {
                    "id": item["id"],
                    "source_name": item.get("source_name", item["name"]),
                    "name": item["name"],
                    "code": item["code"],
                    "city": item["city"],
                    "subtitle": item["subtitle"],
                    "class_name": item.get("class_name", "port"),
                    "capacity": item["capacity"],
                    "camera_count": len(item["cameras"]),
                    "pad_count": len(item["pads"]),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "angle_deg": item.get("angle_deg"),
                }
                for item in items
            ],
        }

    @app.get("/api/status")
    async def status(vertiport_id: str | None = Query(default=None)) -> Dict[str, Any]:
        return _build_status(vertiport_id)

    @app.get("/api/cameras/{camera_id}")
    async def camera(camera_id: str, vertiport_id: str | None = Query(default=None)) -> Dict[str, Any]:
        return _camera_detail(camera_id, vertiport_id)

    @app.get("/api/streams")
    async def streams(
        vertiport_id: str | None = Query(default=None),
        camera_id: str = Query(default=""),
        visualization_url: str = Query(default=DEFAULT_VISUALIZATION_URL),
        fps: float = Query(default=DEFAULT_VPO_STREAM_FPS),
        quality: int = Query(default=DEFAULT_VPO_STREAM_QUALITY),
        announce: bool = Query(default=False),
        connect: bool = Query(default=False),
    ) -> Dict[str, Any]:
        vertiport = deepcopy(_find_vertiport(vertiport_id))
        safe_camera_id = _normalize_node_name(camera_id)
        cameras = list(vertiport.get("cameras") or [])
        selected_camera = next((item for item in cameras if item.get("id") == safe_camera_id), None)
        if selected_camera is None:
            raise HTTPException(status_code=404, detail=f"Unknown camera: {safe_camera_id}")

        visual = _base_url(visualization_url, DEFAULT_VISUALIZATION_URL)
        safe_fps = max(0.2, min(12.0, float(fps or DEFAULT_VPO_STREAM_FPS)))
        safe_quality = max(10, min(95, int(quality or DEFAULT_VPO_STREAM_QUALITY)))
        frame_file = selected_camera.get("frame_file") or f"{safe_camera_id}.png"
        if not connect:
            descriptor = _vpo_stream_descriptor_fallback(
                camera_id=safe_camera_id,
                vertiport=vertiport,
                fps=safe_fps,
                quality=safe_quality,
                frame_url=_camera_frame_url(frame_file),
                warning={
                    "ok": False,
                    "detached": True,
                    "reason": "VPO is detached by default. Pass connect=true only after an explicit user request.",
                },
            )
            return {
                "streams": [descriptor],
                "publish": None,
                "warning": descriptor["warning"],
                "visualization_url": "",
                "detached": True,
                "vertiport": {
                    "id": vertiport.get("id"),
                    "name": vertiport.get("name"),
                    "source_name": vertiport.get("source_name"),
                    "code": vertiport.get("code"),
                },
                "camera": selected_camera,
            }
        query = urlencode({
            "camera_id": safe_camera_id,
            "vertiport_id": vertiport.get("id") or "",
            "vertiport_name": vertiport.get("name") or "",
            "fps": safe_fps,
            "quality": safe_quality,
            "announce": "true" if announce else "false",
        })
        result = _json_request("GET", f"{visual}/api/vpo/camera-streams?{query}", timeout=0.8)
        if result.get("ok") is False or not result.get("streams"):
            descriptor = _vpo_stream_descriptor_fallback(
                camera_id=safe_camera_id,
                vertiport=vertiport,
                fps=safe_fps,
                quality=safe_quality,
                frame_url=_camera_frame_url(frame_file),
                warning=result,
            )
            result = {
                "streams": [descriptor],
                "publish": None,
                "warning": result,
            }

        return {
            **result,
            "visualization_url": visual,
            "vertiport": {
                "id": vertiport.get("id"),
                "name": vertiport.get("name"),
                "source_name": vertiport.get("source_name"),
                "code": vertiport.get("code"),
            },
            "camera": selected_camera,
        }

    @app.get("/api/camera-frames/{frame_name}")
    async def camera_frame(frame_name: str) -> FileResponse:
        safe_name = Path(frame_name).name
        frame_path = _resolve_camera_frame_path(safe_name)
        if not frame_path:
            raise HTTPException(status_code=404, detail=f"Camera frame is not available: {safe_name}")
        return FileResponse(
            path=str(frame_path),
            media_type="image/png",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
    return app


app = create_app()
