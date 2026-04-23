from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import queue
import shutil
import threading
import time
import webbrowser
import zipfile
from collections import deque
from dataclasses import asdict, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Optional
from urllib.parse import parse_qs, urlparse

from app.config import (
    APP_TITLE,
    AIRSIM_HOST,
    AIRSIM_PORT,
    BUNDLE_DIR,
    DATA_DIR,
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    DEFAULT_START_ZOOM,
    DEM_DIR,
    DEM_MAX_ZOOM,
    DEM_TILE_SIZE,
    ENABLE_FLIGHTPLAN_MODE,
    LOG_DIR,
    MBTILES_PATH,
    OPEN_BROWSER,
    RESOURCES_DIR,
    SERVER_HOST,
    SERVER_PORT,
    USE_BOUNDS,
    WEB_DIR,
)
from app.datafile_service import DatafileService
from app.dem import load_dem_provider
from app.schedule_flightplan_mode import parse_flightplan_payload
from app.mbtiles import MBTiles
from app.pathplanner import RoutePlanner
from app.sim_core import (
    DEFAULT_FATO_PREP_S,
    DEFAULT_GATE_WAIT_S,
    DEFAULT_GROUND_TAXI_S,
    DEFAULT_TURNAROUND_S,
    DEFAULT_RULES,
    FlightSchedule,
    SIM_START_SECONDS,
    SIM_TICK_MS,
    Simulation,
    SimulationRules,
    TRAFFIC_LEVELS,
)


class WebHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        mbtiles: MBTiles,
        web_dir: Path,
        resources_dir: Path,
        data_dir: Path,
        api: "SimulationApi",
        dem_provider: Optional[object],
    ) -> None:
        super().__init__(server_address, WebRequestHandler)
        self.mbtiles = mbtiles
        self.web_dir = Path(web_dir)
        self.resources_dir = Path(resources_dir)
        self.data_dir = Path(data_dir)
        self.api = api
        self.datafile_service = DatafileService(self.data_dir, self.api)
        self.dem_provider = dem_provider

    def tile_url(self) -> str:
        host, port = self.server_address
        ext = _normalize_format(self.mbtiles.info.tile_format)
        return f"http://{host}:{port}/tiles/{{z}}/{{x}}/{{y}}.{ext}"

    def base_url(self) -> str:
        host, port = self.server_address
        return f"http://{host}:{port}/"


class WebRequestHandler(BaseHTTPRequestHandler):
    server: WebHTTPServer

    def do_GET(self) -> None:
        path = self._path()
        if path in ("/", "/index.html"):
            self._serve_index()
            return
        if path == "/api/state":
            self._serve_state()
            return
        if path.startswith("/api/history"):
            self._serve_history()
            return
        if path.startswith("/api/logs.zip"):
            self._serve_logs_zip()
            return
        if path.startswith("/tiles/"):
            self._serve_tile(path)
            return
        if path.startswith("/dem/"):
            self._serve_dem(path)
            return
        if path.startswith("/resources/"):
            self._serve_resource(path)
            return
        if path.startswith("/data/"):
            self._serve_data(path)
            return
        self._serve_static(path)

    def do_POST(self) -> None:
        path = self._path()
        if path.startswith("/api/"):
            self._handle_api(path)
            return
        self._send_text(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _path(self) -> str:
        return self.path.split("?", 1)[0]

    def _serve_index(self) -> None:
        template_path = self.server.web_dir / "index.html"
        if not template_path.exists():
            self._send_text(HTTPStatus.NOT_FOUND, "Missing index.html")
            return
        html = template_path.read_text(encoding="utf-8")
        info = self.server.mbtiles.info
        center_lat, center_lon, start_zoom = info.start_view()
        if DEFAULT_CENTER_LAT is not None and DEFAULT_CENTER_LON is not None:
            center_lat = float(DEFAULT_CENTER_LAT)
            center_lon = float(DEFAULT_CENTER_LON)
        if DEFAULT_START_ZOOM is not None:
            start_zoom = float(DEFAULT_START_ZOOM)
        bounds_json = _format_bounds(info.bounds) if USE_BOUNDS else "null"
        html = (
            html.replace("__TILE_URL__", self.server.tile_url())
            .replace("__MIN_ZOOM__", str(info.min_zoom))
            .replace("__MAX_ZOOM__", str(info.max_zoom))
            .replace("__CENTER_LAT__", f"{center_lat:.6f}")
            .replace("__CENTER_LON__", f"{center_lon:.6f}")
            .replace("__START_ZOOM__", str(start_zoom))
            .replace("__BOUNDS_JSON__", bounds_json)
            .replace("__AIRSIM_HOST__", str(AIRSIM_HOST))
            .replace("__AIRSIM_PORT__", str(AIRSIM_PORT))
        )
        self._send_bytes(HTTPStatus.OK, html.encode("utf-8"), "text/html; charset=utf-8")

    def _serve_state(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        positions_rev: int | None = None
        if params.get("positions_rev"):
            raw = str(params["positions_rev"][0]).strip()
            try:
                parsed_rev = int(raw)
            except ValueError:
                parsed_rev = -1
            if parsed_rev >= 0:
                positions_rev = parsed_rev
        payload = self.server.api.get_state(positions_rev=positions_rev)
        self._send_json(HTTPStatus.OK, payload)

    def _serve_history(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        name = ""
        if params.get("name"):
            name = params["name"][0]
        points = self.server.api.get_history(name)
        self._send_json(HTTPStatus.OK, {"name": name, "points": points})

    def _serve_logs_zip(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        lang = str(params.get("lang", ["en"])[0] or "en").lower()
        if lang not in ("en", "ko"):
            lang = "en"
        vertiport_path = self._resolve_datafile_path(params.get("vertiport", [""])[0])
        corridor_path = self._resolve_datafile_path(params.get("corridor", [""])[0])
        basestation_path = self._resolve_datafile_path(params.get("basestation", [""])[0])
        result = self.server.api.get_logs_zip(
            lang,
            vertiport_path=vertiport_path,
            corridor_path=corridor_path,
            basestation_path=basestation_path,
        )
        if not result:
            self._send_text(HTTPStatus.NOT_FOUND, "No log session available")
            return
        data, filename = result
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_api(self, path: str) -> None:
        payload = self._read_json()
        if payload is None:
            self._send_text(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return
        if path == "/api/control":
            self.server.api.handle_control(payload)
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/selection":
            self.server.api.set_selection(payload)
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/traffic":
            self.server.api.set_traffic(payload)
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/rules":
            rules = self.server.api.set_rules(payload)
            self._send_json(HTTPStatus.OK, {"ok": True, "rules": rules})
            return
        if path == "/api/wind":
            wind_state = self.server.api.set_wind(payload)
            self._send_json(HTTPStatus.OK, {"ok": True, "wind": wind_state})
            return
        if path == "/api/sim/start":
            self.server.api.start_simulation(payload)
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/sim/pause":
            self.server.api.pause_simulation()
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/sim/stop":
            self.server.api.stop_simulation()
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/sim/fast":
            self.server.api.fast_simulation()
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/sim/speed":
            speed_value = self.server.api.set_simulation_speed(payload)
            self._send_json(HTTPStatus.OK, {"ok": True, "speed": speed_value})
            return
        if path == "/api/datafiles/clone":
            result = self._clone_datafile(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(status, result)
            return
        if path == "/api/datafiles/append":
            result = self._append_datafile(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(status, result)
            return
        if path == "/api/datafiles/update":
            result = self._update_datafile(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(status, result)
            return
        if path == "/api/datafiles/delete":
            result = self._delete_datafile(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(status, result)
            return
        if path == "/api/datafiles/apply":
            result = self._apply_datafiles(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(status, result)
            return
        self._send_text(HTTPStatus.NOT_FOUND, "Not found")

    def _read_json(self) -> Optional[dict[str, object]]:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        try:
            data = self.rfile.read(length)
        except OSError:
            return None
        try:
            value = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if isinstance(value, dict):
            return value
        return None

    def _clone_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        return self.server.datafile_service.clone_datafile(payload)

    def _append_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        return self.server.datafile_service.append_datafile(payload)

    def _update_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        return self.server.datafile_service.update_datafile(payload)

    def _delete_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        return self.server.datafile_service.delete_datafile(payload)

    def _apply_datafiles(self, payload: dict[str, object]) -> dict[str, object]:
        return self.server.datafile_service.apply_datafiles(payload)

    def _resolve_datafile_path(self, value: object) -> Optional[Path]:
        return self.server.datafile_service.resolve_datafile_path(value)

    def _serve_tile(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) < 5:
            self._send_text(HTTPStatus.NOT_FOUND, "Invalid tile path")
            return
        try:
            z = int(parts[2])
            x = int(parts[3])
            y_str, _ext = os.path.splitext(parts[4])
            y = int(y_str)
        except ValueError:
            self._send_text(HTTPStatus.BAD_REQUEST, "Invalid tile coordinates")
            return

        data = self.server.mbtiles.get_tile(z, x, y)
        if data is None:
            self._send_text(HTTPStatus.NOT_FOUND, "Tile not found")
            return

        content_type = _content_type(self.server.mbtiles.info.tile_format)
        encoding = None
        if self.server.mbtiles.info.tile_format == "pbf" and data[:2] == b"\x1f\x8b":
            encoding = "gzip"
        self._send_bytes(
            HTTPStatus.OK,
            data,
            content_type,
            encoding=encoding,
            cache_control="public, max-age=86400",
        )

    def _serve_dem(self, path: str) -> None:
        provider = self.server.dem_provider
        if provider is None:
            self._send_text(HTTPStatus.NOT_FOUND, "DEM unavailable")
            return
        parts = path.split("/")
        if len(parts) < 5:
            self._send_text(HTTPStatus.NOT_FOUND, "Invalid DEM tile path")
            return
        try:
            z = int(parts[2])
            x = int(parts[3])
            y_str, _ext = os.path.splitext(parts[4])
            y = int(y_str)
        except ValueError:
            self._send_text(HTTPStatus.BAD_REQUEST, "Invalid DEM tile coordinates")
            return
        data = provider.get_tile(z, x, y)
        if data is None:
            self._send_text(HTTPStatus.NOT_FOUND, "DEM tile not found")
            return
        self._send_bytes(
            HTTPStatus.OK,
            data,
            "image/png",
            cache_control="public, max-age=86400",
        )

    def _serve_static(self, path: str) -> None:
        file_path = _safe_join(self.server.web_dir, path)
        if file_path is None or not file_path.is_file():
            self._send_text(HTTPStatus.NOT_FOUND, "Not found")
            return
        mime, _ = mimetypes.guess_type(file_path)
        content_type = _ensure_utf8_content_type(mime or "application/octet-stream")
        self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), content_type)

    def _serve_resource(self, path: str) -> None:
        resource_path = path[len("/resources/") :]
        file_path = _safe_join(self.server.resources_dir, resource_path)
        if file_path is None or not file_path.is_file():
            self._send_text(HTTPStatus.NOT_FOUND, "Not found")
            return
        mime, _ = mimetypes.guess_type(file_path)
        content_type = _ensure_utf8_content_type(mime or "application/octet-stream")
        self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), content_type)

    def _serve_data(self, path: str) -> None:
        data_path = path[len("/data/") :]
        file_path = _safe_join(self.server.data_dir, data_path)
        if file_path is None or not file_path.is_file():
            self._send_text(HTTPStatus.NOT_FOUND, "Not found")
            return
        mime, _ = mimetypes.guess_type(file_path)
        content_type = _ensure_utf8_content_type(mime or "application/octet-stream")
        self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), content_type)

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_text(self, status: HTTPStatus, message: str) -> None:
        self._send_bytes(status, message.encode("utf-8"), "text/plain; charset=utf-8")

    def _send_bytes(
        self,
        status: HTTPStatus,
        data: bytes,
        content_type: str,
        encoding: Optional[str] = None,
        cache_control: Optional[str] = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if encoding:
            self.send_header("Content-Encoding", encoding)
        if cache_control:
            self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


def _safe_join(base_dir: Path, request_path: str) -> Optional[Path]:
    safe_path = os.path.normpath(request_path).lstrip("/\\")
    full = (base_dir / safe_path).resolve()
    if base_dir != full and base_dir not in full.parents:
        return None
    return full


def _normalize_format(tile_format: str) -> str:
    fmt = (tile_format or "png").lower()
    if fmt == "jpeg":
        return "jpg"
    return fmt


def _content_type(tile_format: str) -> str:
    fmt = _normalize_format(tile_format)
    if fmt in ("jpg", "jpeg"):
        return "image/jpeg"
    if fmt == "png":
        return "image/png"
    if fmt == "webp":
        return "image/webp"
    if fmt == "pbf":
        return "application/vnd.mapbox-vector-tile"
    return "application/octet-stream"


def _ensure_utf8_content_type(content_type: str) -> str:
    if "charset=" in content_type.lower():
        return content_type
    base = content_type.split(";", 1)[0].strip().lower()
    if base.startswith("text/"):
        return f"{base}; charset=utf-8"
    if base in ("application/javascript", "text/javascript", "application/json", "application/xml", "image/svg+xml"):
        return f"{base}; charset=utf-8"
    if base.endswith("+json") or base.endswith("+xml"):
        return f"{base}; charset=utf-8"
    return content_type


def _format_bounds(bounds: Optional[tuple[float, float, float, float]]) -> str:
    if bounds is None:
        return "null"
    min_lon, min_lat, max_lon, max_lat = bounds
    return json.dumps([[min_lon, min_lat], [max_lon, max_lat]])


def _coerce_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _parse_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ensure_data_dir() -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    bundle_data = BUNDLE_DIR / "data"
    default_dir = DATA_DIR / "default"
    if not default_dir.exists():
        bundle_default = bundle_data / "default"
        if bundle_default.is_dir():
            try:
                shutil.copytree(bundle_default, default_dir)
            except OSError:
                pass

    customed_dir = DATA_DIR / "customed"
    if not customed_dir.exists():
        bundle_customed = bundle_data / "customed"
        if bundle_customed.is_dir():
            try:
                shutil.copytree(bundle_customed, customed_dir)
                return
            except OSError:
                pass
        try:
            customed_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass


def _open_browser(url: str) -> None:
    if not OPEN_BROWSER:
        return

    def _launch() -> None:
        time.sleep(0.5)
        try:
            webbrowser.open_new_tab(url)
        except Exception:
            return

    threading.Thread(target=_launch, daemon=True).start()


class FlightLogger:
    def __init__(
        self,
        root_dir: Path,
        group_size: int = 50,
        max_sessions: int = 10,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.session_path: Path | None = None
        self.group_size = max(1, int(group_size))
        self.max_sessions = max(1, int(max_sessions))
        self._writers: dict[int, dict[str, object]] = {}
        self._flush_interval_s = 1.0
        self._event_file: io.TextIOBase | None = None
        self._event_writer: csv.writer | None = None
        self._event_last_flush = 0.0
        self._metrics_file: io.TextIOBase | None = None
        self._metrics_writer: csv.writer | None = None
        self._metrics_last_flush = 0.0
        self._queue_max_size = 2048
        self._queue: queue.Queue[tuple[str, float, object]] = queue.Queue(
            maxsize=self._queue_max_size
        )
        self._worker_stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._drop_count = 0
        self._drop_last_report = 0.0

    def start_session(self) -> None:
        self.stop()
        try:
            self.root_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.root_dir = Path.cwd() / "log"
            self.root_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        session_path = self.root_dir / timestamp
        session_path.mkdir(parents=True, exist_ok=True)
        self.session_path = session_path
        self._writers = {}
        self._event_file = None
        self._event_writer = None
        self._event_last_flush = 0.0
        self._metrics_file = None
        self._metrics_writer = None
        self._metrics_last_flush = 0.0
        self._reset_queue()
        self._start_worker()
        self._prune_sessions()

    def _is_session_dir(self, name: str) -> bool:
        return (
            len(name) == 15
            and name[8] == "_"
            and name[:8].isdigit()
            and name[9:].isdigit()
        )

    def _prune_sessions(self) -> None:
        if self.max_sessions <= 0:
            return
        try:
            candidates = [
                path
                for path in self.root_dir.iterdir()
                if path.is_dir() and self._is_session_dir(path.name)
            ]
        except OSError:
            return
        if len(candidates) <= self.max_sessions:
            return
        candidates.sort(key=lambda path: path.name)
        to_remove = len(candidates) - self.max_sessions
        for path in candidates:
            if to_remove <= 0:
                break
            if self.session_path and path == self.session_path:
                continue
            try:
                shutil.rmtree(path, ignore_errors=True)
            except OSError:
                pass
            to_remove -= 1

    def stop(self) -> None:
        self.flush(timeout_s=2.0)
        self._worker_stop.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=5.0)
        if worker and worker.is_alive():
            # Best-effort: if the writer is still blocked on I/O, avoid cross-thread close.
            return
        self._worker = None
        self._close_files()
        self._reset_queue()

    def flush(self, timeout_s: float = 1.0) -> bool:
        if not self._queue:
            self._flush_all()
            return True
        deadline = time.time() + max(0.0, float(timeout_s))
        while self._queue.unfinished_tasks > 0:
            if time.time() >= deadline:
                return False
            time.sleep(0.01)
        self._flush_all()
        return True

    def _reset_queue(self) -> None:
        self._queue = queue.Queue(maxsize=self._queue_max_size)
        self._drop_count = 0
        self._drop_last_report = 0.0

    def _start_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._worker_stop.clear()
        self._worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="FlightLoggerWriter",
        )
        self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            if self._worker_stop.is_set() and self._queue.unfinished_tasks <= 0:
                break
            try:
                kind, time_s, payload = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if kind == "event" and isinstance(payload, dict):
                    self._write_event_sync(float(time_s), payload)
                elif kind == "positions" and isinstance(payload, list):
                    self._write_positions_sync(float(time_s), payload)
                elif kind == "metrics" and isinstance(payload, list):
                    self._write_metrics_sync(float(time_s), payload)
            except Exception:
                pass
            finally:
                self._queue.task_done()
        self._flush_all()

    def _report_dropped_if_needed(self) -> None:
        if self._drop_count <= 0:
            return
        now = time.time()
        if now - self._drop_last_report < 5.0:
            return
        print(f"[FlightLogger] queue full, dropped {self._drop_count} log batches.")
        self._drop_last_report = now
        self._drop_count = 0

    def _enqueue(self, kind: str, time_s: float, payload: object) -> None:
        if not self.session_path:
            return
        if not self._worker or not self._worker.is_alive():
            self._start_worker()
        try:
            self._queue.put_nowait((kind, float(time_s), payload))
        except queue.Full:
            self._drop_count += 1
            self._report_dropped_if_needed()

    def append_event(self, time_s: float, event: dict[str, object]) -> None:
        if not self.session_path or not event:
            return
        self._enqueue("event", float(time_s), dict(event))

    def append_positions(self, time_s: float, positions: list[dict[str, object]]) -> None:
        if not self.session_path or not positions:
            return
        self._enqueue("positions", float(time_s), list(positions))

    def append_metrics(self, time_s: float, rows: list[dict[str, object]]) -> None:
        if not self.session_path or not rows:
            return
        self._enqueue("metrics", float(time_s), list(rows))

    def _write_event_sync(self, time_s: float, event: dict[str, object]) -> None:
        if not self.session_path or not event:
            return
        writer = self._ensure_event_writer()
        if not writer:
            return
        try:
            payload = dict(event)
            category = str(payload.get("category") or "").strip()
            kind = str(payload.get("kind") or "").strip()
            action = str(payload.get("action") or "").strip()
            flight_id_raw = payload.get("flight_id")
            flight_id = ""
            if flight_id_raw is not None:
                try:
                    flight_id_value = int(flight_id_raw)
                    if flight_id_value > 0:
                        flight_id = str(flight_id_value)
                    else:
                        flight_id = str(flight_id_raw)
                except (TypeError, ValueError):
                    flight_id = str(flight_id_raw)
            flight_name = str(payload.get("flight_name") or "").strip()
            detail = str(payload.get("detail") or "").strip()
            value = payload.get("value")
            if value is None:
                for key in (
                    "speed_mps",
                    "speed",
                    "target_scale",
                    "scale",
                    "ratio",
                    "duration_s",
                ):
                    if key in payload:
                        value = payload.get(key)
                        break
            if isinstance(value, float):
                value_text = f"{value:.3f}"
            elif value is None:
                value_text = ""
            else:
                value_text = str(value)
            wall_ts = time.time()
            wall_label = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wall_ts))
            wall_label = f"{wall_label}.{int((wall_ts % 1) * 1000):03d}"
            payload_json = json.dumps(payload, ensure_ascii=False)
            writer.writerow(
                [
                    f"{float(time_s):.2f}",
                    wall_label,
                    category,
                    kind,
                    action,
                    flight_id,
                    flight_name,
                    value_text,
                    detail,
                    payload_json,
                ]
            )
            self._flush_event_if_needed()
        except OSError:
            self._close_files()

    def _write_positions_sync(self, time_s: float, positions: list[dict[str, object]]) -> None:
        if not self.session_path:
            return
        try:
            for pos in positions:
                name = str(pos.get("name") or "").strip()
                if not name:
                    continue
                flight_id = self._parse_flight_id(pos.get("id"), name)
                if not flight_id:
                    continue
                lon = _parse_float(pos.get("lon"))
                lat = _parse_float(pos.get("lat"))
                if lon is None or lat is None:
                    continue
                alt_m = _parse_float(pos.get("altitude_m")) or 0.0
                speed = _parse_float(pos.get("speed_mps")) or 0.0
                heading = _parse_float(pos.get("heading_deg")) or 0.0
                mode = str(pos.get("mode") or "").strip()
                origin = str(pos.get("from") or "").strip()
                dest = str(pos.get("to") or "").strip()
                risk = str(pos.get("risk") or "").strip()
                reason = str(pos.get("risk_reason") or "").strip()
                writer = self._ensure_writer(flight_id)
                if not writer:
                    continue
                writer.writerow(
                    [
                        f"{time_s:.2f}",
                        name,
                        str(flight_id),
                        f"{lon:.7f}",
                        f"{lat:.7f}",
                        f"{alt_m:.2f}",
                        f"{speed:.2f}",
                        f"{heading:.2f}",
                        mode,
                        origin,
                        dest,
                        risk,
                        reason,
                    ]
                )
                self._flush_if_needed(flight_id)
        except OSError:
            self._close_files()

    def _write_metrics_sync(self, time_s: float, rows: list[dict[str, object]]) -> None:
        if not self.session_path or not rows:
            return
        writer = self._ensure_metrics_writer()
        if not writer:
            return
        try:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").strip()
                if not name:
                    continue
                flight_id = self._parse_flight_id(row.get("id"), name)
                if not flight_id:
                    continue
                mode = str(row.get("mode") or "").strip()
                origin = str(row.get("from") or "").strip()
                destination = str(row.get("to") or "").strip()
                std_s = _parse_float(row.get("std_s"))
                sta_s = _parse_float(row.get("sta_s"))
                eta_s = _parse_float(row.get("eta_s"))
                ata_s = _parse_float(row.get("ata_s"))
                delay_s = _parse_float(row.get("delay_s"))
                tti = _parse_float(row.get("tti"))
                rem_dist_m = _parse_float(row.get("remaining_dist_m"))
                rem_time_s = _parse_float(row.get("remaining_time_s"))
                writer.writerow(
                    [
                        f"{float(time_s):.2f}",
                        name,
                        str(flight_id),
                        mode,
                        origin,
                        destination,
                        "" if std_s is None else f"{std_s:.2f}",
                        "" if sta_s is None else f"{sta_s:.2f}",
                        "" if eta_s is None else f"{eta_s:.2f}",
                        "" if ata_s is None else f"{ata_s:.2f}",
                        "" if delay_s is None else f"{delay_s:.2f}",
                        "" if tti is None else f"{tti:.4f}",
                        "" if rem_dist_m is None else f"{rem_dist_m:.2f}",
                        "" if rem_time_s is None else f"{rem_time_s:.2f}",
                    ]
                )
            self._flush_metrics_if_needed()
        except OSError:
            self._close_files()

    def read_history(self, name: str) -> list[list[float]]:
        self.flush(timeout_s=1.0)
        target = str(name or "").strip()
        if not target or not self.session_path:
            return []
        flight_id = self._parse_flight_id(None, target)
        if not flight_id:
            return self._read_history_from_all(target)
        file_path = self._file_path_for_id(flight_id)
        if not file_path or not file_path.exists():
            return []
        return self._read_history_file(file_path, target)

    def _parse_flight_id(self, value: object, name: str) -> Optional[int]:
        if value is not None:
            try:
                flight_id = int(value)
                if flight_id > 0:
                    return flight_id
            except (TypeError, ValueError):
                pass
        digits = "".join(ch for ch in name if ch.isdigit())
        if not digits:
            return None
        try:
            flight_id = int(digits)
        except ValueError:
            return None
        return flight_id if flight_id > 0 else None

    def _group_range(self, flight_id: int) -> tuple[int, int, int]:
        group_id = (flight_id - 1) // self.group_size
        start_id = group_id * self.group_size + 1
        end_id = start_id + self.group_size - 1
        return group_id, start_id, end_id

    def _file_path_for_id(self, flight_id: int) -> Optional[Path]:
        if not self.session_path:
            return None
        _group_id, start_id, end_id = self._group_range(flight_id)
        width = max(5, len(str(end_id)))
        filename = f"tracks_{start_id:0{width}d}_{end_id:0{width}d}.csv"
        return self.session_path / filename

    def _ensure_writer(self, flight_id: int) -> Optional[csv.writer]:
        if not self.session_path:
            return None
        group_id, start_id, end_id = self._group_range(flight_id)
        entry = self._writers.get(group_id)
        if entry and entry.get("writer"):
            return entry["writer"]
        file_path = self._file_path_for_id(flight_id)
        if not file_path:
            return None
        file_exists = file_path.exists()
        log_file = file_path.open("a", encoding="utf-8-sig", newline="")
        writer = csv.writer(log_file)
        write_header = not file_exists
        if not write_header:
            try:
                write_header = file_path.stat().st_size == 0
            except OSError:
                write_header = True
        if write_header:
            writer.writerow(
                [
                    "time_s",
                    "name",
                    "id",
                    "lon",
                    "lat",
                    "altitude_m",
                    "speed_mps",
                    "heading_deg",
                    "mode",
                    "from",
                    "to",
                    "risk",
                    "reason",
                ]
            )
        self._writers[group_id] = {
            "file": log_file,
            "writer": writer,
            "last_flush": time.time(),
            "range": (start_id, end_id),
        }
        return writer

    def _ensure_event_writer(self) -> Optional[csv.writer]:
        if not self.session_path:
            return None
        if self._event_writer:
            return self._event_writer
        file_path = self.session_path / "events.csv"
        file_exists = file_path.exists()
        log_file = file_path.open("a", encoding="utf-8-sig", newline="")
        writer = csv.writer(log_file)
        if not file_exists or file_path.stat().st_size == 0:
            writer.writerow(
                [
                    "time_s",
                    "wall_time",
                    "category",
                    "kind",
                    "action",
                    "flight_id",
                    "flight_name",
                    "value",
                    "detail",
                    "payload",
                ]
            )
        self._event_file = log_file
        self._event_writer = writer
        self._event_last_flush = time.time()
        return writer

    def _ensure_metrics_writer(self) -> Optional[csv.writer]:
        if not self.session_path:
            return None
        if self._metrics_writer:
            return self._metrics_writer
        file_path = self.session_path / "flight_metrics.csv"
        file_exists = file_path.exists()
        metrics_file = file_path.open("a", encoding="utf-8-sig", newline="")
        writer = csv.writer(metrics_file)
        if not file_exists or file_path.stat().st_size == 0:
            writer.writerow(
                [
                    "time_s",
                    "name",
                    "id",
                    "mode",
                    "from",
                    "to",
                    "std_s",
                    "sta_s",
                    "eta_s",
                    "ata_s",
                    "delay_s",
                    "tti",
                    "remaining_dist_m",
                    "remaining_time_s",
                ]
            )
        self._metrics_file = metrics_file
        self._metrics_writer = writer
        self._metrics_last_flush = time.time()
        return writer

    def _flush_if_needed(self, flight_id: int) -> None:
        group_id, _start_id, _end_id = self._group_range(flight_id)
        entry = self._writers.get(group_id)
        if not entry:
            return
        log_file = entry.get("file")
        last_flush = entry.get("last_flush", 0.0)
        now = time.time()
        if log_file and now - float(last_flush) >= self._flush_interval_s:
            try:
                log_file.flush()
            except OSError:
                return
            entry["last_flush"] = now

    def _flush_event_if_needed(self) -> None:
        if not self._event_file:
            return
        now = time.time()
        if now - float(self._event_last_flush) >= self._flush_interval_s:
            try:
                self._event_file.flush()
            except OSError:
                return
            self._event_last_flush = now

    def _flush_metrics_if_needed(self) -> None:
        if not self._metrics_file:
            return
        now = time.time()
        if now - float(self._metrics_last_flush) >= self._flush_interval_s:
            try:
                self._metrics_file.flush()
            except OSError:
                return
            self._metrics_last_flush = now

    def _flush_all(self) -> None:
        for entry in self._writers.values():
            log_file = entry.get("file")
            if not log_file:
                continue
            try:
                log_file.flush()
            except OSError:
                pass
            entry["last_flush"] = time.time()
        if self._event_file:
            try:
                self._event_file.flush()
            except OSError:
                pass
            self._event_last_flush = time.time()
        if self._metrics_file:
            try:
                self._metrics_file.flush()
            except OSError:
                pass
            self._metrics_last_flush = time.time()

    def _close_files(self) -> None:
        for entry in self._writers.values():
            log_file = entry.get("file")
            if not log_file:
                continue
            try:
                log_file.flush()
            except OSError:
                pass
            try:
                log_file.close()
            except OSError:
                pass
        self._writers = {}
        if self._event_file:
            try:
                self._event_file.flush()
            except OSError:
                pass
            try:
                self._event_file.close()
            except OSError:
                pass
        if self._metrics_file:
            try:
                self._metrics_file.flush()
            except OSError:
                pass
            try:
                self._metrics_file.close()
            except OSError:
                pass
        self._event_file = None
        self._event_writer = None
        self._event_last_flush = 0.0
        self._metrics_file = None
        self._metrics_writer = None
        self._metrics_last_flush = 0.0

    def _read_history_file(self, file_path: Path, target: str) -> list[list[float]]:
        try:
            with file_path.open("r", encoding="utf-8-sig", newline="") as log_file:
                reader = csv.reader(log_file)
                header = next(reader, None)
                if not header:
                    return []
                index = {value: idx for idx, value in enumerate(header)}
                idx_name = index.get("name")
                idx_time = index.get("time_s")
                idx_lon = index.get("lon")
                idx_lat = index.get("lat")
                idx_alt = index.get("altitude_m")
                if idx_name is None or idx_lon is None or idx_lat is None:
                    return []
                points: list[list[float]] = []
                for row in reader:
                    if idx_name >= len(row) or row[idx_name] != target:
                        continue
                    if idx_lon >= len(row) or idx_lat >= len(row):
                        continue
                    lon = _parse_float(row[idx_lon])
                    lat = _parse_float(row[idx_lat])
                    if lon is None or lat is None:
                        continue
                    time_value = None
                    if idx_time is not None and idx_time < len(row):
                        time_value = _parse_float(row[idx_time])
                    if idx_alt is not None and idx_alt < len(row):
                        alt = _parse_float(row[idx_alt])
                    else:
                        alt = None
                    alt_value = alt if alt is not None else 0.0
                    time_value = time_value if time_value is not None else 0.0
                    points.append([lon, lat, alt_value, time_value])
                return points
        except OSError:
            return []

    def _read_history_from_all(self, target: str) -> list[list[float]]:
        if not self.session_path:
            return []
        points: list[list[float]] = []
        try:
            for file_path in sorted(self.session_path.glob("tracks_*.csv")):
                points.extend(self._read_history_file(file_path, target))
        except OSError:
            return []
        return points

class SimulationApi:
    def __init__(
        self,
        planner: RoutePlanner,
        vertiport_path: Path,
        corridor_path: Path,
        basestation_path: Path,
    ) -> None:
        self._lock = threading.RLock()
        self._rules = replace(DEFAULT_RULES)
        self._traffic_selection: str | None = "Middle"
        self._selected_name = ""
        self._positions: list[dict[str, object]] = []
        self._positions_rev = 0
        self._positions_history_limit = 20
        self._positions_history: dict[int, dict[str, dict[str, object]]] = {}
        self._positions_history_order: deque[int] = deque()
        self._status_messages: list[dict[str, object]] = []
        self._status_hint: str | None = None
        self._human_events: list[dict[str, object]] = []
        self._dashboard_failed: list[list[str]] = []
        self._dashboard_reset = True
        self._dashboard_new: list[list[str]] = []
        self._dashboard_status: list[dict[str, object]] = []
        self._time_s = 0
        self._speed = 1
        self._logger = FlightLogger(LOG_DIR)
        self._vertiport_path = Path(vertiport_path)
        self._corridor_path = Path(corridor_path)
        self._basestation_path = Path(basestation_path)

        self.simulation = Simulation(
            planner=planner,
            rules=self._rules,
            get_traffic_selection=self._get_traffic_selection,
            update_time=self._update_time,
            set_dashboard_data=self._set_dashboard_data,
            add_dashboard_row=self._add_dashboard_row,
            update_dashboard_status=self._update_dashboard_status,
            update_speed=self._update_speed,
            update_map=self._update_map,
            add_human_event=self._add_human_event,
            add_failure_event=self._add_failure_event,
        )

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._store_positions_snapshot([], bump_revision=False)

    def _position_key(self, item: dict[str, object]) -> str:
        flight_id = item.get("id")
        if flight_id is not None:
            text = str(flight_id).strip()
            if text:
                return f"id:{text}"
        name = str(item.get("name") or "").strip()
        if name:
            return f"name:{name}"
        return ""

    def _index_positions(
        self, positions: list[dict[str, object]]
    ) -> dict[str, dict[str, object]] | None:
        indexed: dict[str, dict[str, object]] = {}
        for item in positions:
            key = self._position_key(item)
            if not key:
                return None
            if key in indexed:
                return None
            indexed[key] = item
        return indexed

    def _store_positions_snapshot(
        self, positions: list[dict[str, object]], bump_revision: bool
    ) -> list[dict[str, object]]:
        snapshot = [dict(item) for item in positions]
        self._positions = snapshot
        if bump_revision:
            self._positions_rev += 1
        indexed = self._index_positions(snapshot)
        if indexed is None:
            self._positions_history = {}
            self._positions_history_order.clear()
            return snapshot
        self._positions_history[self._positions_rev] = indexed
        self._positions_history_order.append(self._positions_rev)
        while len(self._positions_history_order) > self._positions_history_limit:
            stale = self._positions_history_order.popleft()
            self._positions_history.pop(stale, None)
        return snapshot

    def _decorate_selected_paths(
        self, positions: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        selected = self._selected_name
        if not selected:
            return positions
        path = self.simulation.build_prediction_path(selected)
        hold_path = self.simulation.build_hold_path(selected)
        if not path and not hold_path:
            return positions
        decorated = [dict(item) for item in positions]
        for item in decorated:
            if item.get("name") != selected:
                continue
            if path:
                item["predict_path"] = path
            if hold_path:
                item["hold_path"] = hold_path
            break
        return decorated

    def _build_position_patch(
        self,
        previous: dict[str, object],
        current: dict[str, object],
        key: str,
    ) -> dict[str, object] | None:
        patch: dict[str, object] = {}
        for field, value in current.items():
            if previous.get(field) != value:
                patch[field] = value
        for field in previous.keys():
            if field not in current:
                patch[field] = None
        if not patch:
            return None
        if "id" not in patch and current.get("id") is not None:
            patch["id"] = current.get("id")
        if "name" not in patch:
            current_name = str(current.get("name") or "").strip()
            if current_name:
                patch["name"] = current_name
            elif key.startswith("name:"):
                patch["name"] = key.split(":", 1)[1]
        return patch

    def _build_positions_payload(self, positions_rev: int | None) -> dict[str, object]:
        current_rev = int(self._positions_rev)
        # Selected-flight prediction/hold paths are computed from live sim state.
        # Keep full mode while selected to avoid stale delta reconstruction.
        if self._selected_name:
            positions = self._decorate_selected_paths(self._positions)
            return {
                "positions_rev": current_rev,
                "positions_mode": "full",
                "positions": positions,
            }

        if positions_rev is None:
            return {
                "positions_rev": current_rev,
                "positions_mode": "full",
                "positions": [dict(item) for item in self._positions],
            }

        base_rev = int(positions_rev)
        if base_rev == current_rev:
            return {
                "positions_rev": current_rev,
                "positions_mode": "none",
            }

        current_index = self._positions_history.get(current_rev)
        base_index = self._positions_history.get(base_rev)
        if current_index is None or base_index is None:
            return {
                "positions_rev": current_rev,
                "positions_mode": "full",
                "positions": [dict(item) for item in self._positions],
            }

        updates: list[dict[str, object]] = []
        removed: list[str] = []

        for key, current in current_index.items():
            previous = base_index.get(key)
            if previous is None:
                updates.append(dict(current))
                continue
            patch = self._build_position_patch(previous, current, key)
            if patch:
                updates.append(patch)

        for key in base_index.keys():
            if key not in current_index:
                removed.append(key)

        return {
            "positions_rev": current_rev,
            "positions_mode": "delta",
            "positions_updates": updates,
            "positions_removed": removed,
        }

    def start_loop(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop_loop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._logger.stop()

    def _run_loop(self) -> None:
        tick_s = SIM_TICK_MS / 1000.0
        last = time.perf_counter()
        while not self._stop_event.is_set():
            now = time.perf_counter()
            delta = now - last
            last = now
            with self._lock:
                self.simulation.step(delta)
            elapsed = time.perf_counter() - now
            sleep_for = max(0.0, tick_s - elapsed)
            if self._stop_event.wait(sleep_for):
                break

    def _get_traffic_selection(self) -> str | None:
        return self._traffic_selection

    def _parse_flightplan_payload(
        self,
        payload: dict[str, object] | None,
    ) -> tuple[list[FlightSchedule], dict[str, object]] | None:
        parsed = parse_flightplan_payload(
            payload,
            default_gate_wait_s=DEFAULT_GATE_WAIT_S,
            default_ground_taxi_s=DEFAULT_GROUND_TAXI_S,
            default_fato_prep_s=DEFAULT_FATO_PREP_S,
            default_turnaround_s=DEFAULT_TURNAROUND_S,
            sim_start_seconds=SIM_START_SECONDS,
            make_schedule=lambda **kwargs: FlightSchedule(**kwargs),
        )
        if parsed is None:
            return None
        schedules, state = parsed
        return schedules, state

    def _update_time(self, value: int) -> None:
        with self._lock:
            self._time_s = int(value)

    def _update_speed(self, value: int) -> None:
        with self._lock:
            self._speed = int(value)

    def _update_map(self, positions: list[dict[str, object]]) -> None:
        with self._lock:
            snapshot = self._store_positions_snapshot(positions, bump_revision=True)
            if self.simulation.running and snapshot:
                self._logger.append_positions(self.simulation.sim_elapsed_s, snapshot)

    def _set_dashboard_data(self, rows: list[list[str]] | None) -> None:
        with self._lock:
            self._dashboard_reset = True
            self._dashboard_new = []
            self._dashboard_status = []
            self._dashboard_failed = []

    def _add_dashboard_row(self, row: list[str]) -> None:
        with self._lock:
            self._dashboard_new.append(list(row))

    def _update_dashboard_status(self, statuses: list[dict[str, object]]) -> None:
        with self._lock:
            self._dashboard_status = list(statuses)
            metric_rows = []
            for status in statuses:
                if not isinstance(status, dict):
                    continue
                if not bool(status.get("ops_metrics_updated")):
                    continue
                metric_rows.append(dict(status))
            if metric_rows:
                self._logger.append_metrics(self.simulation.sim_elapsed_s, metric_rows)

    def _flight_name_by_id(self, flight_id: int) -> str:
        for flight in self.simulation.flights:
            if flight.flight_id == flight_id:
                return str(flight.name)
        return ""

    def _log_event(
        self,
        category: str,
        kind: str = "",
        action: str = "",
        flight_id: int | None = None,
        flight_name: str = "",
        value: object | None = None,
        detail: str = "",
        payload: dict[str, object] | None = None,
    ) -> None:
        if not category:
            return
        event: dict[str, object] = dict(payload or {})
        event["category"] = category
        if kind:
            event["kind"] = kind
        if action:
            event["action"] = action
        if flight_id is not None:
            event["flight_id"] = int(flight_id)
        if flight_name:
            event["flight_name"] = str(flight_name)
        if value is not None:
            event["value"] = value
        if detail:
            event["detail"] = detail
        self._logger.append_event(float(self.simulation.sim_elapsed_s), event)

    def _add_failure_event(self, event: dict[str, object]) -> None:
        if not event:
            return
        time_s = _parse_float(event.get("time_s"))
        time_label = str(int(round(time_s))) if time_s is not None else ""
        flight_id = event.get("flight_id")
        flight_name = str(event.get("flight_name") or "").strip()
        origin = str(event.get("origin") or "").strip()
        destination = str(event.get("destination") or "").strip()
        lon = _parse_float(event.get("lon"))
        lat = _parse_float(event.get("lat"))
        position = (
            f"{lat:.5f}, {lon:.5f}"
            if lat is not None and lon is not None
            else "-"
        )
        battery_pct = _parse_float(event.get("battery_pct"))
        battery_text = f"{battery_pct:.0f}%" if battery_pct is not None else "-"
        reason = str(event.get("reason") or "Battery 0").strip()
        flight_id_text = ""
        if flight_id is not None:
            try:
                flight_id_text = str(int(flight_id))
            except (TypeError, ValueError):
                flight_id_text = str(flight_id)
        row = [
            time_label,
            flight_name or "-",
            flight_id_text or "-",
            origin or "-",
            destination or "-",
            position,
            battery_text,
            reason or "-",
        ]
        flight_id_value = None
        if flight_id is not None:
            try:
                flight_id_value = int(flight_id)
            except (TypeError, ValueError):
                flight_id_value = None
        with self._lock:
            self._dashboard_failed.append(row)
            self._log_event(
                "failure",
                action="Battery Depleted",
                flight_id=flight_id_value,
                flight_name=flight_name,
                value=battery_pct,
                detail=reason,
                payload=event,
            )

    def _emit_human_event(self, event: dict[str, object]) -> None:
        if not event:
            return
        entry = dict(event)
        if "category" not in entry:
            entry["category"] = "human"
        self._human_events.append(entry)
        self._logger.append_event(float(self.simulation.sim_elapsed_s), entry)

    def _add_human_event(self, event: dict[str, object]) -> None:
        if not event:
            return
        with self._lock:
            self._emit_human_event(dict(event))

    def _send_status(self, text: str, level: str = "info", ttl_ms: int = 4000) -> None:
        self._status_messages.append({"text": text, "level": level, "ttlMs": ttl_ms})

    def _set_status_hint(self, text: str | None) -> None:
        self._status_hint = text

    def get_state(self, positions_rev: int | None = None) -> dict[str, object]:
        with self._lock:
            positions_payload = self._build_positions_payload(positions_rev)
            use_flightplan = bool(
                ENABLE_FLIGHTPLAN_MODE and self.simulation.has_flightplan_schedule()
            )
            flightplan_state = (
                self.simulation.get_flightplan_state()
                if ENABLE_FLIGHTPLAN_MODE
                else {"enabled": False, "name": "", "legs": 0, "aircraft": 0}
            )
            status_messages = list(self._status_messages)
            self._status_messages = []
            human_events = list(self._human_events)
            self._human_events = []
            dashboard_new = list(self._dashboard_new)
            self._dashboard_new = []
            dashboard_reset = bool(self._dashboard_reset)
            self._dashboard_reset = False
            dashboard_status = list(self._dashboard_status)
            dashboard_failed = list(self._dashboard_failed)
            self._dashboard_failed = []
            payload = {
                "status_messages": status_messages,
                "status_hint": self._status_hint,
                "running": self.simulation.running,
                "speed": self.simulation.speed_multiplier,
                "time_s": int(self._time_s),
                "traffic_selection": self._traffic_selection,
                "schedule_mode": "flightplan" if use_flightplan else "random",
                "flightplan_mode_enabled": bool(ENABLE_FLIGHTPLAN_MODE),
                "flightplan": flightplan_state,
                "dashboard_reset": dashboard_reset,
                "dashboard_new": dashboard_new,
                "dashboard_status": dashboard_status,
                "dashboard_failed": dashboard_failed,
                "rules": asdict(self._rules),
                "autopilot": asdict(self.simulation.autopilot),
                "human_events": human_events,
            }
            payload.update(positions_payload)
            return payload

    def get_history(self, name: str) -> list[list[float]]:
        return self._logger.read_history(name)

    def get_logs_zip(
        self,
        lang: str = "en",
        vertiport_path: Path | None = None,
        corridor_path: Path | None = None,
        basestation_path: Path | None = None,
    ) -> tuple[bytes, str] | None:
        with self._lock:
            self._logger.flush(timeout_s=2.0)
            session_path = self._logger.session_path
            root_dir = self._logger.root_dir
            active_vertiport = Path(vertiport_path) if vertiport_path else self._vertiport_path
            active_corridor = Path(corridor_path) if corridor_path else self._corridor_path
            active_basestation = (
                Path(basestation_path)
                if basestation_path
                else getattr(self, "_basestation_path", None)
            )
        try:
            data_root = DATA_DIR.resolve()
        except OSError:
            data_root = DATA_DIR
        target = session_path
        if not target:
            try:
                candidates = [path for path in Path(root_dir).iterdir() if path.is_dir()]
            except OSError:
                return None
            if not candidates:
                return None
            candidates.sort(key=lambda path: path.name)
            target = candidates[-1]
        if not target or not target.exists():
            return None

        session_name = target.name
        filename = f"uatm_logs_{session_name}.zip"

        def safe_datafile(path: Path | None) -> Path | None:
            if not path:
                return None
            try:
                resolved = Path(path).resolve()
            except OSError:
                return None
            try:
                resolved.relative_to(data_root)
            except ValueError:
                return None
            return resolved if resolved.is_file() else None

        def build_readme_text(language: str) -> str:
            if language == "ko":
                return (
                    "UATM 로그 안내\n"
                    "\n"
                    "이 압축 파일에는 현재(또는 가장 최근) 시뮬레이션 세션의 로그가 포함됩니다.\n"
                    "\n"
                    "[구성]\n"
                    "1) events.csv\n"
                    "- 시뮬레이션 중 발생한 이벤트/개입 이력이 기록됩니다.\n"
                    "- 주요 필드:\n"
                    "  * time_s: 시뮬레이션 경과 시간(초)\n"
                    "  * wall_time: 실제 시각(ISO 형식)\n"
                    "  * category/kind/action: 이벤트 분류\n"
                    "  * flight_id/flight_name: 대상 비행체\n"
                    "  * value/detail: 요약 값/설명\n"
                    "  * payload: 추가 정보(JSON 문자열)\n"
                    "\n"
                    "2) tracks_XXXXX_YYYYY.csv\n"
                    "- 비행체 항적(트랙) 로그입니다. 비행체 ID 구간별로 파일이 나뉩니다.\n"
                    "- 파일명 예시: tracks_00001_00050.csv (ID 1~50)\n"
                    "- 주요 필드:\n"
                    "  * time_s, name, id\n"
                    "  * lon, lat, altitude_m\n"
                    "  * speed_mps, heading_deg, mode\n"
                    "  * from, to, risk, reason\n"
                    "\n"
                    "3) flight_metrics.csv\n"
                    "- 10초 주기로 저장되는 ETA/STD/STA/ATA/TTI 운영 지표 로그입니다.\n"
                    "- 주요 필드:\n"
                    "  * std_s, sta_s, eta_s, ata_s\n"
                    "  * delay_s, tti\n"
                    "  * remaining_dist_m, remaining_time_s\n"
                    "\n"
                    "4) datafiles/\n"
                    "- 로그 생성 시점의 활성 데이터 파일이 포함됩니다.\n"
                    "- vertiport_active.csv: 현재 버티포트 데이터\n"
                    "- corridor_active.csv: 현재 회랑/항로 데이터\n"
                    "- basestation_active.csv: 현재 기지국 데이터(있는 경우)\n"
                    "- active_paths.json: 위 데이터 파일들의 실제 경로 정보\n"
                    "\n"
                    "[해석 팁]\n"
                    "- events.csv의 action/payload를 보면 자동개입(오토파일럿)과 수동개입을 구분할 수 있습니다.\n"
                    "- tracks_* 파일에서 같은 id를 필터링하면 특정 비행체의 이동 이력을 볼 수 있습니다.\n"
                )
            return (
                "UATM Log Guide\n"
                "\n"
                "This archive contains logs for the current (or most recent) simulation session.\n"
                "\n"
                "[Contents]\n"
                "1) events.csv\n"
                "- Event and intervention history during the simulation.\n"
                "- Key fields:\n"
                "  * time_s: simulation elapsed time in seconds\n"
                "  * wall_time: real clock time (ISO format)\n"
                "  * category/kind/action: event classification\n"
                "  * flight_id/flight_name: target aircraft\n"
                "  * value/detail: summarized value/notes\n"
                "  * payload: extra metadata (JSON string)\n"
                "\n"
                "2) tracks_XXXXX_YYYYY.csv\n"
                "- Flight track logs, split by flight ID ranges.\n"
                "- Example: tracks_00001_00050.csv (IDs 1-50)\n"
                "- Key fields:\n"
                "  * time_s, name, id\n"
                "  * lon, lat, altitude_m\n"
                "  * speed_mps, heading_deg, mode\n"
                "  * from, to, risk, reason\n"
                "\n"
                "3) flight_metrics.csv\n"
                "- Operational KPI log (ETA/STD/STA/ATA/TTI) recorded every 10 simulation seconds.\n"
                "- Key fields:\n"
                "  * std_s, sta_s, eta_s, ata_s\n"
                "  * delay_s, tti\n"
                "  * remaining_dist_m, remaining_time_s\n"
                "\n"
                "4) datafiles/\n"
                "- Active data files at the time of export.\n"
                "- vertiport_active.csv: current vertiport data\n"
                "- corridor_active.csv: current corridor/route data\n"
                "- basestation_active.csv: current base station data (if available)\n"
                "- active_paths.json: resolved source paths for the data files\n"
                "\n"
                "[Tips]\n"
                "- In events.csv, action/payload helps distinguish autopilot vs human interventions.\n"
                "- In tracks_* files, filter by id to trace a specific aircraft over time.\n"
            )

        readme_name = "README_logs_ko.txt" if lang == "ko" else "README_logs_en.txt"
        readme_text = build_readme_text(lang)

        buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                for file_path in sorted(target.glob("*.csv")):
                    try:
                        archive.write(file_path, arcname=file_path.name)
                    except OSError:
                        continue
                datafiles: dict[str, str] = {}
                for key, path, arcname in (
                    ("vertiport", safe_datafile(active_vertiport), "datafiles/vertiport_active.csv"),
                    ("corridor", safe_datafile(active_corridor), "datafiles/corridor_active.csv"),
                    ("basestation", safe_datafile(active_basestation), "datafiles/basestation_active.csv"),
                ):
                    if not path:
                        continue
                    try:
                        archive.write(path, arcname=arcname)
                    except OSError:
                        continue
                    try:
                        datafiles[key] = str(path.relative_to(data_root))
                    except ValueError:
                        datafiles[key] = path.name
                meta = {
                    "session": session_name,
                    "datafiles": datafiles,
                }
                archive.writestr(
                    "datafiles/active_paths.json",
                    json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8-sig"),
                )
                archive.writestr(readme_name, readme_text.encode("utf-8-sig"))
        except OSError:
            return None
        return buffer.getvalue(), filename

    def set_selection(self, payload: dict[str, object]) -> None:
        name = str(payload.get("name") or "").strip()
        with self._lock:
            if self._selected_name == name:
                return
            self._selected_name = name
            # Force clients to resync full positions when selected-path overlays change.
            self._store_positions_snapshot(self._positions, bump_revision=True)

    def set_traffic(self, payload: dict[str, object]) -> None:
        selection = str(payload.get("selection") or "").strip()
        with self._lock:
            if selection in TRAFFIC_LEVELS:
                self._traffic_selection = selection
                self._set_status_hint(None)
                self._log_event(
                    "ops",
                    action="Traffic Selection",
                    value=selection,
                )
            else:
                self._traffic_selection = None
                self._set_status_hint("Please select Daily Traffic in settings.")
                self._log_event(
                    "ops",
                    action="Traffic Selection",
                    value="clear",
                )

    def set_rules(self, payload: dict[str, object]) -> dict[str, object]:
        with self._lock:
            rules = self._rules
            next_rules = SimulationRules(
                speed_mps=_coerce_float(payload.get("speed_mps"), rules.speed_mps),
                accel_mps2=_coerce_float(payload.get("accel_mps2"), rules.accel_mps2),
                climb_rate_fpm=_coerce_float(
                    payload.get("climb_rate_fpm"),
                    rules.climb_rate_fpm,
                ),
                transition_alt_ft=_coerce_float(
                    payload.get("transition_alt_ft"),
                    rules.transition_alt_ft,
                ),
                transition_speed_knot=_coerce_float(
                    payload.get("transition_speed_knot"),
                    rules.transition_speed_knot,
                ),
                holding_s=_coerce_int(payload.get("holding_s"), rules.holding_s),
                takeoff_s=_coerce_int(payload.get("takeoff_s"), rules.takeoff_s),
                landing_s=_coerce_int(payload.get("landing_s"), rules.landing_s),
                battery_capacity_s=_coerce_float(
                    payload.get("battery_capacity_s"),
                    getattr(rules, "battery_capacity_s", 0.0),
                ),
                min_safe_speed_mps=_coerce_float(
                    payload.get("min_safe_speed_mps"),
                    getattr(rules, "min_safe_speed_mps", 0.0),
                ),
                turn_rate_deg_s=_coerce_float(payload.get("turn_rate_deg_s"), rules.turn_rate_deg_s),
                separation_m=_coerce_int(payload.get("separation_m"), rules.separation_m),
                warning_m=_coerce_int(payload.get("warning_m"), rules.warning_m),
                warning_ec_s=_coerce_int(payload.get("warning_ec_s"), rules.warning_ec_s),
                warning_trailing_circles=_coerce_int(
                    payload.get("warning_trailing_circles"),
                    rules.warning_trailing_circles,
                ),
                warning_leading_knot_delta=_coerce_int(
                    payload.get("warning_leading_knot_delta"),
                    rules.warning_leading_knot_delta,
                ),
                caution_m=_coerce_int(payload.get("caution_m"), rules.caution_m),
                caution_ec_s=_coerce_int(payload.get("caution_ec_s"), rules.caution_ec_s),
                caution_trailing_knot_delta=_coerce_int(
                    payload.get("caution_trailing_knot_delta"),
                    rules.caution_trailing_knot_delta,
                ),
                caution_leading_knot_delta=_coerce_int(
                    payload.get("caution_leading_knot_delta"),
                    rules.caution_leading_knot_delta,
                ),
                risk_predict_horizon_s=_coerce_float(
                    payload.get("risk_predict_horizon_s"),
                    rules.risk_predict_horizon_s,
                ),
                risk_lateral_m=_coerce_float(
                    payload.get("risk_lateral_m"),
                    rules.risk_lateral_m,
                ),
                risk_direction_cos=_coerce_float(
                    payload.get("risk_direction_cos"),
                    rules.risk_direction_cos,
                ),
                risk_update_interval_s=_coerce_float(
                    payload.get("risk_update_interval_s"),
                    rules.risk_update_interval_s,
                ),
                risk_proximity_lv1_m=_coerce_float(
                    payload.get("risk_proximity_lv1_m"),
                    rules.risk_proximity_lv1_m,
                ),
                risk_proximity_lv2_m=_coerce_float(
                    payload.get("risk_proximity_lv2_m"),
                    rules.risk_proximity_lv2_m,
                ),
                risk_proximity_lv3_m=_coerce_float(
                    payload.get("risk_proximity_lv3_m"),
                    rules.risk_proximity_lv3_m,
                ),
                risk_battery_lv1_pct=_coerce_float(
                    payload.get("risk_battery_lv1_pct"),
                    rules.risk_battery_lv1_pct,
                ),
                risk_battery_lv2_pct=_coerce_float(
                    payload.get("risk_battery_lv2_pct"),
                    rules.risk_battery_lv2_pct,
                ),
                risk_battery_lv3_pct=_coerce_float(
                    payload.get("risk_battery_lv3_pct"),
                    rules.risk_battery_lv3_pct,
                ),
                rnp_max_lat_m=_coerce_float(
                    payload.get("rnp_max_lat_m"),
                    rules.rnp_max_lat_m,
                ),
                rnp_max_ver_m=_coerce_float(
                    payload.get("rnp_max_ver_m"),
                    rules.rnp_max_ver_m,
                ),
                rnp_r_lv1=_coerce_float(
                    payload.get("rnp_r_lv1"),
                    rules.rnp_r_lv1,
                ),
                rnp_r_lv2=_coerce_float(
                    payload.get("rnp_r_lv2"),
                    rules.rnp_r_lv2,
                ),
                rnp_r_lv3=_coerce_float(
                    payload.get("rnp_r_lv3"),
                    rules.rnp_r_lv3,
                ),
                rnp_ttv_lv1_s=_coerce_float(
                    payload.get("rnp_ttv_lv1_s"),
                    rules.rnp_ttv_lv1_s,
                ),
                rnp_ttv_lv2_s=_coerce_float(
                    payload.get("rnp_ttv_lv2_s"),
                    rules.rnp_ttv_lv2_s,
                ),
                wind_enabled=_coerce_int(
                    payload.get("wind_enabled"),
                    rules.wind_enabled,
                ),
                wind_time_speed=_coerce_float(
                    payload.get("wind_time_speed"),
                    rules.wind_time_speed,
                ),
                wind_smooth_s=_coerce_float(
                    payload.get("wind_smooth_s"),
                    rules.wind_smooth_s,
                ),
                wind_cross_gain=_coerce_float(
                    payload.get("wind_cross_gain"),
                    rules.wind_cross_gain,
                ),
                wind_cross_return_s=_coerce_float(
                    payload.get("wind_cross_return_s"),
                    rules.wind_cross_return_s,
                ),
                wind_cross_max_m=_coerce_float(
                    payload.get("wind_cross_max_m"),
                    rules.wind_cross_max_m,
                ),
                wind_along_gain=_coerce_float(
                    payload.get("wind_along_gain"),
                    rules.wind_along_gain,
                ),
                wind_along_max_mps=_coerce_float(
                    payload.get("wind_along_max_mps"),
                    rules.wind_along_max_mps,
                ),
                wind_crab_max_deg=_coerce_float(
                    payload.get("wind_crab_max_deg"),
                    rules.wind_crab_max_deg,
                ),
                operation_start_min=_coerce_int(
                    payload.get("operation_start_min"),
                    rules.operation_start_min,
                ),
                operation_end_min=_coerce_int(payload.get("operation_end_min"), rules.operation_end_min),
                operation_goal_count=_coerce_int(
                    payload.get("operation_goal_count"),
                    rules.operation_goal_count,
                ),
            )
            self._rules = next_rules
            self.simulation.update_rules(next_rules)
            self._log_event(
                "ops",
                action="Update Rules",
                payload=asdict(next_rules),
            )
            return asdict(next_rules)

    def set_wind(self, payload: dict[str, object]) -> dict[str, object]:
        preset = str(payload.get("preset") or "").strip().lower()
        clear_local = bool(payload.get("clear_local"))
        local = payload.get("local")
        applied: dict[str, object] = {}
        with self._lock:
            if preset in ("good", "fair", "bad", "serious"):
                self.simulation.set_wind_preset(preset)
                applied["preset"] = preset

            if clear_local:
                self.simulation.clear_local_wind()
                applied["cleared"] = True

            if isinstance(local, dict):
                lon = _parse_float(local.get("lon"))
                lat = _parse_float(local.get("lat"))
                radius_m = _parse_float(local.get("radius_m") or local.get("radius"))
                if (
                    lon is not None
                    and lat is not None
                    and radius_m is not None
                    and radius_m > 0
                ):
                    local_preset = str(local.get("preset") or preset or "").strip().lower()
                    if local_preset not in ("good", "fair", "bad", "serious"):
                        local_preset = "good"
                    self.simulation.add_local_wind(lon, lat, radius_m, local_preset)
                    applied["local"] = {
                        "lon": lon,
                        "lat": lat,
                        "radius_m": radius_m,
                        "preset": local_preset,
                    }
            if applied:
                self._log_event("ops", action="Wind Update", payload=applied)
        return applied

    def apply_datafiles(
        self,
        vertiport_path: Path,
        corridor_path: Path,
        basestation_path: Path | None = None,
    ) -> dict[str, object]:
        with self._lock:
            try:
                planner = RoutePlanner.from_csv(vertiport_path, corridor_path)
            except (OSError, ValueError, RuntimeError):
                return {"ok": False, "message": "Failed to load data files."}
            was_running = self.simulation.running
            self.simulation.stop()
            self.simulation.update_planner(planner)
            self._vertiport_path = Path(vertiport_path)
            self._corridor_path = Path(corridor_path)
            if basestation_path and Path(basestation_path).is_file():
                self._basestation_path = Path(basestation_path)
            self._selected_name = ""
            self._send_status("Airspace data updated.", "info", 4000)
            payload = {
                "vertiport": str(self._vertiport_path),
                "corridor": str(self._corridor_path),
            }
            basestation_value = getattr(self, "_basestation_path", None)
            if basestation_value:
                payload["basestation"] = str(basestation_value)
            self._log_event(
                "ops",
                action="Apply Data Files",
                payload=payload,
            )
            if was_running:
                self._send_status("Simulation stopped to apply updated routes.", "warn", 5000)
            result: dict[str, object] = {
                "ok": True,
                "vertiport": str(self._vertiport_path),
                "corridor": str(self._corridor_path),
            }
            if basestation_value:
                result["basestation"] = str(basestation_value)
            return result

    def handle_control(self, payload: dict[str, object]) -> None:
        method = str(payload.get("method") or "").strip()
        args = payload.get("args")
        if not isinstance(args, list):
            args = []
        with self._lock:
            if method == "setFlightSpeed" and len(args) >= 2:
                flight_id = int(args[0])
                speed_mps = float(args[1])
                self.simulation.set_flight_speed(flight_id, speed_mps)
                self._emit_human_event(
                    {
                        "kind": "speed",
                        "action": "Manual Set",
                        "flight_id": flight_id,
                        "flight_name": self._flight_name_by_id(flight_id),
                        "speed_mps": speed_mps,
                    }
                )
            elif method == "clearFlightSpeed" and args:
                flight_id = int(args[0])
                self.simulation.clear_flight_speed(flight_id)
                self._emit_human_event(
                    {
                        "kind": "speed",
                        "action": "Manual Clear",
                        "flight_id": flight_id,
                        "flight_name": self._flight_name_by_id(flight_id),
                    }
                )
            elif method == "startHolding" and len(args) >= 2:
                flight_id = int(args[0])
                loops = int(args[1])
                radius_m = self.simulation.start_holding(flight_id, loops)
                if radius_m:
                    radius_km = radius_m / 1000.0
                    self._send_status(
                        f"Holding radius ~{radius_km:.1f} km (turn rate {self._rules.turn_rate_deg_s:.1f} deg/s)."
                    )
                    self._log_event(
                        "ops",
                        action="Hold Start",
                        flight_id=flight_id,
                        flight_name=self._flight_name_by_id(flight_id),
                        value=radius_m,
                        detail=f"loops={loops}",
                    )
            elif method == "stopHolding" and args:
                flight_id = int(args[0])
                self.simulation.stop_holding(flight_id)
                self._log_event(
                    "ops",
                    action="Hold Stop",
                    flight_id=flight_id,
                    flight_name=self._flight_name_by_id(flight_id),
                )
            elif method == "setEmergencyLanding" and len(args) >= 3:
                flight_id = int(args[0])
                try:
                    lon = float(args[1])
                    lat = float(args[2])
                except (TypeError, ValueError):
                    return
                label = ""
                if len(args) >= 4 and args[3] is not None:
                    label = str(args[3])
                alt_m = None
                if len(args) >= 5 and args[4] is not None:
                    try:
                        alt_m = float(args[4])
                    except (TypeError, ValueError):
                        alt_m = None
                ok = self.simulation.set_emergency_landing(flight_id, lon, lat, label, alt_m)
                if ok:
                    target = label.strip() if label else "point"
                    self._send_status(f"Emergency landing set: {target}.", "warn", 4500)
                    self._emit_human_event(
                        {
                            "kind": "emergency",
                            "action": "Emergency Landing",
                            "flight_id": flight_id,
                            "flight_name": self._flight_name_by_id(flight_id),
                            "target": target,
                            "lon": lon,
                            "lat": lat,
                            "alt_m": alt_m,
                        }
                    )
            elif method == "forceMoveVia" and len(args) >= 2:
                flight_id = int(args[0])
                waypoint = str(args[1] or "").strip()
                if not waypoint or waypoint not in self.simulation.planner.node_xy:
                    self._send_status("Force move failed: invalid waypoint.", "warn", 3500)
                    return
                ok = self.simulation.force_move_via(flight_id, waypoint)
                if ok:
                    self._send_status(f"Force move set: {waypoint}.", "info", 3500)
                    self._emit_human_event(
                        {
                            "kind": "emergency",
                            "action": "Force Move",
                            "flight_id": flight_id,
                            "flight_name": self._flight_name_by_id(flight_id),
                            "target": waypoint,
                        }
                    )
                else:
                    self._send_status(
                        f"Force move failed: no route from {waypoint}.",
                        "warn",
                        4500,
                    )
            elif method == "setWindHold" and len(args) >= 2:
                flight_id = int(args[0])
                target_scale = None
                ramp_s = None
                if len(args) >= 3:
                    try:
                        target_scale = float(args[1])
                        ramp_s = float(args[2])
                    except (TypeError, ValueError):
                        target_scale = None
                else:
                    level = str(args[1]).strip().lower()
                    if level in ("strong", "high", "s"):
                        target_scale = 0.3
                        ramp_s = 7.0
                    else:
                        target_scale = 0.5
                        ramp_s = 12.0
                if target_scale is not None:
                    self.simulation.set_wind_hold(flight_id, float(target_scale), float(ramp_s or 0.0))
                    percent = int(max(0.0, min(100.0, float(target_scale) * 100.0)))
                    self._send_status(
                        f"Route keep: wind effect -> {percent}% ({int(ramp_s or 0)}s ramp).",
                        "info",
                        3500,
                    )
                    self._log_event(
                        "ops",
                        action="Wind Hold",
                        flight_id=flight_id,
                        flight_name=self._flight_name_by_id(flight_id),
                        value=float(target_scale),
                        detail=f"ramp_s={float(ramp_s or 0.0):.1f}",
                    )
            elif method == "setAutopilot":
                current = self.simulation.autopilot
                enabled = current.enabled
                if len(args) >= 1:
                    enabled = bool(args[0])
                duration_s = current.duration_s
                if len(args) >= 2:
                    duration_s = _coerce_float(args[1], duration_s)
                lv1_delta_knot = current.lv1_delta_knot
                if len(args) >= 3:
                    lv1_delta_knot = _coerce_float(args[2], lv1_delta_knot)
                lv2_delta_knot = current.lv2_delta_knot
                if len(args) >= 4:
                    lv2_delta_knot = _coerce_float(args[3], lv2_delta_knot)
                lv3_delta_knot = current.lv3_delta_knot
                if len(args) >= 5:
                    lv3_delta_knot = _coerce_float(args[4], lv3_delta_knot)
                self.simulation.set_autopilot(
                    enabled,
                    duration_s,
                    lv1_delta_knot,
                    lv2_delta_knot,
                    lv3_delta_knot,
                )
                self._log_event(
                    "ops",
                    action="Autopilot",
                    value="on" if enabled else "off",
                    payload={
                        "enabled": bool(enabled),
                        "duration_s": float(duration_s),
                        "lv1_delta_knot": float(lv1_delta_knot),
                        "lv2_delta_knot": float(lv2_delta_knot),
                        "lv3_delta_knot": float(lv3_delta_knot),
                    },
                )
            elif method == "setCorridorClosed" and len(args) >= 3:
                start = str(args[0])
                end = str(args[1])
                closed = bool(args[2])
                changed = self.simulation.set_corridor_closed(start, end, closed)
                if changed:
                    action = "closed" if closed else "reopened"
                    self._send_status(f"Corridor {action}: {start} - {end}")
                    self._emit_human_event(
                        {
                            "kind": "airspace",
                            "action": f"Corridor {action}",
                            "from": start,
                            "to": end,
                            "kind_label": "corridor",
                        }
                    )
            elif method == "setSpareCorridorOpen" and len(args) >= 3:
                start = str(args[0])
                end = str(args[1])
                open_link = bool(args[2])
                changed = self.simulation.set_spare_corridor_open(start, end, open_link)
                if changed:
                    action = "opened" if open_link else "closed"
                    self._send_status(f"Spare link {action}: {start} - {end}")
                    self._emit_human_event(
                        {
                            "kind": "airspace",
                            "action": f"Spare link {action}",
                            "from": start,
                            "to": end,
                            "kind_label": "spare",
                        }
                    )

    def start_simulation(self, payload: dict[str, object] | None = None) -> None:
        with self._lock:
            if self.simulation.running:
                self.simulation.set_speed(1)
                self._send_status("Speed set to 1x.")
                self._log_event("ops", action="Speed Set", value=1)
                return
            parsed_flightplan = self._parse_flightplan_payload(payload)
            if parsed_flightplan is not None:
                if not ENABLE_FLIGHTPLAN_MODE:
                    self.simulation.clear_flightplan_schedule()
                    raw_flightplan = payload.get("flightplan") if isinstance(payload, dict) else None
                    if raw_flightplan is not None:
                        self._send_status(
                            "Flight-plan mode is disabled. Starting in random mode.",
                            "warn",
                            5000,
                        )
                        self._log_event(
                            "ops",
                            action="Flightplan Ignored",
                            payload={"reason": "disabled"},
                        )
                else:
                    schedules, plan_state = parsed_flightplan
                    if schedules:
                        plan_name = str(plan_state.get("name") or "").strip()
                        self.simulation.set_flightplan_schedule(schedules, plan_name)
                        legs = int(plan_state.get("legs") or len(schedules))
                        aircraft = int(plan_state.get("aircraft") or 0)
                        skipped = int(plan_state.get("skipped_rows") or 0)
                        if plan_name:
                            summary = (
                                f"Flight plan loaded: {plan_name} "
                                f"({legs} legs / {aircraft} aircraft)."
                            )
                        else:
                            summary = f"Flight plan loaded ({legs} legs / {aircraft} aircraft)."
                        self._send_status(summary, "success", 5000)
                        if skipped > 0:
                            self._send_status(
                                f"{skipped} plan rows were skipped due to missing data.",
                                "warn",
                                5000,
                            )
                        self._log_event("ops", action="Flightplan Load", payload=plan_state)
                    else:
                        self.simulation.clear_flightplan_schedule()
                        self._log_event("ops", action="Flightplan Clear")

            use_flightplan = bool(
                ENABLE_FLIGHTPLAN_MODE and self.simulation.has_flightplan_schedule()
            )
            if not use_flightplan and not self._traffic_selection:
                fallback = "Middle" if "Middle" in TRAFFIC_LEVELS else next(iter(TRAFFIC_LEVELS), "")
                if fallback:
                    self._traffic_selection = fallback
                    self._send_status(
                        f"Daily Traffic not set; defaulting to {fallback}.",
                        "warn",
                        4500,
                    )
                else:
                    self._set_status_hint("Please select Daily Traffic in settings.")
                    self._send_status("Select Daily Traffic in settings to start.", "warn", 7000)
                    return
            self._set_status_hint(None)
            should_reset = (
                not self.simulation.running
                and (
                    not self.simulation.schedule
                    or self.simulation.sim_elapsed_s >= self.simulation.sim_duration_s
                )
            )
            if should_reset:
                self._logger.start_session()
            self.simulation.start()
            if self.simulation.running:
                if use_flightplan:
                    self._send_status("Simulation started (flight-plan mode).")
                else:
                    self._send_status("Simulation started.")
                self._log_event("ops", action="Simulation Start")
            else:
                if not self.simulation.schedule:
                    if use_flightplan:
                        self._send_status("No valid flight-plan schedule to run.", "warn", 7000)
                    else:
                        self._send_status(
                            "No schedule generated. Check Daily Traffic and data files.",
                            "warn",
                            7000,
                        )
                if should_reset:
                    self._logger.stop()

    def pause_simulation(self) -> None:
        with self._lock:
            if self.simulation.running:
                self.simulation.pause()
                self._send_status("Simulation paused.")
                self._log_event("ops", action="Simulation Pause")

    def stop_simulation(self) -> None:
        with self._lock:
            self.simulation.stop()
            self._send_status("Simulation stopped.")
            self._log_event("ops", action="Simulation Stop")
            self._logger.stop()

    def fast_simulation(self) -> None:
        with self._lock:
            self.simulation.fast()
            self._send_status(f"Speed set to {self.simulation.speed_multiplier}x.")
            self._log_event(
                "ops",
                action="Speed Set",
                value=self.simulation.speed_multiplier,
            )

    def set_simulation_speed(self, payload: dict[str, object]) -> int:
        with self._lock:
            value = _coerce_int(payload.get("speed"), self.simulation.speed_multiplier)
            if value <= 0:
                value = 1
            self.simulation.set_speed(value)
            self._send_status(f"Speed set to {self.simulation.speed_multiplier}x.")
            self._log_event(
                "ops",
                action="Speed Set",
                value=self.simulation.speed_multiplier,
            )
            return int(self.simulation.speed_multiplier)


def main() -> int:
    _ensure_data_dir()
    mbtiles = MBTiles(MBTILES_PATH)
    dem_provider = None
    if DEM_DIR.exists():
        candidate = load_dem_provider(DEM_DIR, tile_size=DEM_TILE_SIZE, max_zoom=DEM_MAX_ZOOM)
        if candidate.available:
            dem_provider = candidate
    planner = RoutePlanner.from_csv(
        DATA_DIR / "default" / "vertiport_default.csv",
        DATA_DIR / "default" / "corridor_default.csv",
    )
    api = SimulationApi(
        planner,
        DATA_DIR / "default" / "vertiport_default.csv",
        DATA_DIR / "default" / "corridor_default.csv",
        DATA_DIR / "default" / "basestation_default.csv",
    )
    server = WebHTTPServer(
        (SERVER_HOST, SERVER_PORT),
        mbtiles=mbtiles,
        web_dir=WEB_DIR,
        resources_dir=RESOURCES_DIR,
        data_dir=DATA_DIR,
        api=api,
        dem_provider=dem_provider,
    )
    api.start_loop()
    url = server.base_url()
    print(f"{APP_TITLE} web server running at {url}")
    _open_browser(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        api.stop_loop()
        server.server_close()
        mbtiles.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
