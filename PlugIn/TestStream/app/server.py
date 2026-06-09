"""DTAM TestStream plug-in server.

Purpose:
- Receive direct MJPEG stream descriptors from VisualizationModule.
- Discover/announce the stream through MSG 4102 CameraStreamDescriptor.
- Send camera movement commands through IntegrationHub as MSG 5002.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "app" / "web"
DEFAULT_VISUALIZATION_URL = os.environ.get("DTAM_VISUALIZATION_URL", "http://127.0.0.1:8097")
DEFAULT_STATE_URL = os.environ.get("DTAM_STATE_URL", "http://127.0.0.1:8096")
DEFAULT_STREAM_FPS = float(os.environ.get("DTAM_TESTSTREAM_DEFAULT_FPS", "20.0") or 20.0)
DEFAULT_IMAGE_TYPE = int(os.environ.get("DTAM_TESTSTREAM_DEFAULT_IMAGE_TYPE", "0") or 0)

app = FastAPI(title="DTAM TestStream Plug-in")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _json_request(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 3.0) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = UrlRequest(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as response:
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


def _base_url(value: Any, default: str) -> str:
    text = str(value or default).strip().rstrip("/")
    if not text.startswith(("http://", "https://")):
        text = "http://" + text
    return text.rstrip("/")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "module": "TestStream"})


@app.get("/api/config")
async def config() -> JSONResponse:
    return JSONResponse({
        "visualization_url": DEFAULT_VISUALIZATION_URL,
        "state_url": DEFAULT_STATE_URL,
        "default_fps": DEFAULT_STREAM_FPS,
        "default_quality": 60,
        "default_image_type": DEFAULT_IMAGE_TYPE,
        "image_type_options": [
            {"value": 0, "label": "0 - Scene / RGB"},
            {"value": 1, "label": "1 - DepthPlanar"},
            {"value": 2, "label": "2 - DepthPerspective"},
            {"value": 3, "label": "3 - DepthVis"},
            {"value": 5, "label": "5 - Segmentation"},
            {"value": 6, "label": "6 - SurfaceNormals"},
            {"value": 7, "label": "7 - Infrared"},
        ],
        "default_display_scale": "fit",
        "transport": "direct-mjpeg latest-frame-cache + ICD4102/5002",
    })


@app.get("/api/status")
async def status(visualization_url: str = DEFAULT_VISUALIZATION_URL, state_url: str = DEFAULT_STATE_URL) -> JSONResponse:
    visual = _json_request("GET", f"{_base_url(visualization_url, DEFAULT_VISUALIZATION_URL)}/api/state", timeout=1.2)
    streams = _json_request("GET", f"{_base_url(state_url, DEFAULT_STATE_URL)}/api/camera-streams", timeout=1.2)
    return JSONResponse({"visualization": visual, "state_streams": streams})


@app.get("/api/streams")
async def streams(
    visualization_url: str = DEFAULT_VISUALIZATION_URL,
    vehicle_id: str = "UAM0001",
    vehicle_name: str = "",
    camera_name: str = "front_center",
    image_type: int = DEFAULT_IMAGE_TYPE,
    fps: float = DEFAULT_STREAM_FPS,
    quality: int = 60,
    announce: bool = False,
) -> JSONResponse:
    visual = _base_url(visualization_url, DEFAULT_VISUALIZATION_URL)
    safe_image_type = int(image_type or 0)
    query = urlencode({
        "vehicle_id": vehicle_id or "UAM0001",
        "vehicle_name": vehicle_name or "",
        "camera_name": camera_name or "front_center",
        "image_type": safe_image_type,
        "fps": max(0.2, min(30.0, float(fps or DEFAULT_STREAM_FPS))),
        "quality": max(10, min(95, int(quality or 60))),
        "announce": "true" if announce else "false",
    })
    result = _json_request("GET", f"{visual}/api/media/streams?{query}", timeout=2.0)
    if result.get("ok") is False:
        fallback_fps = max(0.2, min(30.0, float(fps or DEFAULT_STREAM_FPS)))
        fallback_quality = max(10, min(95, int(quality or 60)))
        stream_query = urlencode({
            "vehicle_id": vehicle_id or "UAM0001",
            "vehicle_name": vehicle_name or "",
            "camera_name": camera_name or "front_center",
            "image_type": safe_image_type,
            "fps": fallback_fps,
            "quality": fallback_quality,
        })
        stream_url = f"{visual}/api/media/stream?{stream_query}"
        result = {
            "streams": [{
                "message_id": 4102,
                "message_name": "Camera Stream Descriptor",
                "timestamp": _iso_ts(),
                "stream_id": f"{vehicle_id or 'UAM0001'}-{camera_name or 'front_center'}-type{safe_image_type}-mjpeg",
                "vehicle_id": vehicle_id or "UAM0001",
                "airsim_vehicle_name": vehicle_name or "",
                "camera_name": camera_name or "front_center",
                "image_type": safe_image_type,
                "stream_type": "mjpeg",
                "transport": "http-multipart",
                "codec": "mjpeg",
                "encoding": "jpeg",
                "url": stream_url,
                "control_mid": "5002",
                "fps": fallback_fps,
                "quality": fallback_quality,
                "status": "local-fallback",
                "source": "airsim",
                "media_plane": "direct-mjpeg",
                "cache_policy": "latest-frame-only",
                "note": "Visualization descriptor endpoint was unavailable; using direct MJPEG media URL fallback.",
            }],
            "publish": None,
            "warning": result,
        }
    return JSONResponse(result)


@app.get("/api/probe")
async def probe(
    visualization_url: str = DEFAULT_VISUALIZATION_URL,
    vehicle_id: str = "UAM0001",
    vehicle_name: str = "",
    camera_name: str = "front_center",
    image_type: int = DEFAULT_IMAGE_TYPE,
    quality: int = 60,
) -> JSONResponse:
    visual = _base_url(visualization_url, DEFAULT_VISUALIZATION_URL)
    query = urlencode({
        "vehicle_id": vehicle_id or "UAM0001",
        "vehicle_name": vehicle_name or "",
        "camera_name": camera_name or "front_center",
        "image_type": int(image_type or 0),
        "quality": max(10, min(95, int(quality or 60))),
    })
    result = _json_request("GET", f"{visual}/api/media/probe?{query}", timeout=5.0)
    return JSONResponse(result, status_code=200 if result.get("ok", True) is not False else 502)


@app.get("/api/media-stats")
async def media_stats(visualization_url: str = DEFAULT_VISUALIZATION_URL) -> JSONResponse:
    visual = _base_url(visualization_url, DEFAULT_VISUALIZATION_URL)
    result = _json_request("GET", f"{visual}/api/media/stats", timeout=2.0)
    return JSONResponse(result, status_code=200 if result.get("ok", True) is not False else 502)


@app.post("/api/unreal/launch")
async def unreal_launch(request: Request) -> JSONResponse:
    body = await _safe_json(request)
    visual = _base_url(body.get("visualization_url"), DEFAULT_VISUALIZATION_URL)
    result = _json_request(
        "POST",
        f"{visual}/api/unreal/launch",
        {"pixel_streaming": False},
        timeout=10.0,
    )
    return JSONResponse(result, status_code=200 if result.get("ok", True) is not False else 502)


@app.post("/api/announce")
async def announce(request: Request) -> JSONResponse:
    body = await _safe_json(request)
    visual = _base_url(body.get("visualization_url"), DEFAULT_VISUALIZATION_URL)
    payload = {
        "vehicle_id": body.get("vehicle_id") or "UAM0001",
        "vehicle_name": body.get("vehicle_name") or "",
        "camera_name": body.get("camera_name") or "front_center",
        "image_type": int(body.get("image_type") or body.get("imageType") or DEFAULT_IMAGE_TYPE),
        "fps": max(0.2, min(30.0, float(body.get("fps") or DEFAULT_STREAM_FPS))),
        "quality": max(10, min(95, int(body.get("quality") or 60))),
        "note": "Announced by PlugIn/TestStream.",
    }
    result = _json_request("POST", f"{visual}/api/media/announce", payload, timeout=2.0)
    return JSONResponse(result, status_code=200 if result.get("ok", True) is not False else 502)


@app.post("/api/control")
async def control(request: Request) -> JSONResponse:
    body = await _safe_json(request)
    state = _base_url(body.get("state_url"), DEFAULT_STATE_URL)
    sequence = int(time.time() * 1000) & 0xFFFFFFFF
    payload = {
        "timestamp": _iso_ts(),
        "aircraftId": str(body.get("vehicle_id") or body.get("aircraftId") or "UAM0001"),
        "vehicleName": str(body.get("vehicle_name") or body.get("vehicleName") or ""),
        "cameraName": str(body.get("camera_name") or body.get("cameraName") or "front_center"),
        "source": "teststream",
        "action": str(body.get("action") or "adjust"),
        "sequence": sequence,
        "yawDeltaDeg": float(body.get("yaw_delta_deg") or body.get("yawDeltaDeg") or 0.0),
        "pitchDeltaDeg": float(body.get("pitch_delta_deg") or body.get("pitchDeltaDeg") or 0.0),
        "focalLengthDelta": float(body.get("focal_length_delta") or body.get("focalLengthDelta") or 0.0),
    }
    result = _json_request("POST", f"{state}/api/msg/5002", {"payload": payload}, timeout=2.0)
    return JSONResponse({"sent": payload, "result": result}, status_code=200 if result.get("ok", True) is not False else 502)


async def _safe_json(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}
