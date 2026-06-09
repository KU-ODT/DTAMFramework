"""Small stdlib HTTP client for the VFDS/KP2A mission dispatch server.

The VehicleModule should be able to run even when the high-fidelity VFDS server
is offline. Therefore every method returns a structured result instead of
raising network exceptions to callers.

The embedded VFDS Dynamics server exposes the same HTTP paths
(``/api/v1/missions/realtime``, ``/api/v1/time``, ``/api/v1/telemetry``).  This
module standardizes DTAM-side naming to VFDS.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


DEFAULT_VFDS_BASE_URL = "http://127.0.0.1:8098"
VFDS_BASE_URL_ENV = "DTAM_VFDS_BASE_URL"
VFDS_TIMEOUT_ENV = "DTAM_VFDS_TIMEOUT_S"
VFDS_AUTOSTART_ENV = "DTAM_VFDS_AUTOSTART"
VFDS_AUTOSTART_TIMEOUT_ENV = "DTAM_VFDS_AUTOSTART_TIMEOUT_S"
VFDS_AUTOSTART_LOG_ENV = "DTAM_VFDS_AUTOSTART_LOG"
_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "password",
    "secret",
    "token",
}
_URL_RE = re.compile(r"(?P<url>(?:https?|wss?)://[^\s]+)")
_AUTOSTART_LOCK = threading.RLock()
_AUTOSTART_PROCESS: Optional[subprocess.Popen[Any]] = None


@dataclass(frozen=True)
class VfdsHttpResult:
    ok: bool
    method: str
    url: str
    status_code: int = 0
    body: Any = None
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "method": self.method,
            "url": _redact_url(self.url),
            "status_code": int(self.status_code or 0),
            "body": _redact_value(self.body),
            "error": _redact_value(self.error),
        }


class VfdsMissionClient:
    """HTTP wrapper for VFDS mission/time APIs.

    Environment:
    - ``DTAM_VFDS_BASE_URL``: defaults to ``http://127.0.0.1:8098``
    - ``DTAM_VFDS_TIMEOUT_S``: defaults to ``0.75``
    """

    def __init__(self, base_url: Optional[str] = None, *, timeout_s: Optional[float] = None) -> None:
        raw_base = str(
            base_url
            or os.environ.get(VFDS_BASE_URL_ENV)
            or DEFAULT_VFDS_BASE_URL
        ).strip()
        self.base_url = raw_base.rstrip("/") or DEFAULT_VFDS_BASE_URL
        if timeout_s is None:
            try:
                timeout_s = float(
                    os.environ.get(VFDS_TIMEOUT_ENV)
                    or 0.75
                )
            except (TypeError, ValueError):
                timeout_s = 0.75
        self.timeout_s = max(0.05, float(timeout_s))

    def health(self) -> VfdsHttpResult:
        last = self._request("GET", "/health", accepted=(200,))
        if last.ok:
            return last
        # Embedded VFDS and some older/ref-packaged builds used different health
        # aliases.  Keep all aliases here so Operation/Vehicle can simply ask
        # "is VFDS ready?" without caring which runtime is active.
        for path in ("/api/health", "/api/v1/health"):
            result = self._request("GET", path, accepted=(200,))
            if result.ok:
                return result
            last = result
        return last

    def ensure_ready(self, *, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        """Ensure the embedded VFDS/KP2A dispatch server is reachable.

        The normal DTAM flow is now:
        OperationModule chooses ``highFidelity/VFDS-KP2A`` → VehicleModule owns
        the local embedded VFDS dispatch server → missions are delivered via
        ``POST /api/v1/missions/realtime``.  This method starts the local server
        on demand when the configured URL is local, then polls health until it is
        ready.  Remote URLs are never auto-started.
        """

        deadline_s = _coerce_timeout(
            timeout_s,
            os.environ.get(VFDS_AUTOSTART_TIMEOUT_ENV),
            default=20.0,
        )
        first_health = self.health()
        if first_health.ok:
            return {
                "ok": True,
                "already_running": True,
                "started": False,
                "base_url": _redact_url(self.base_url),
                "health": first_health.to_dict(),
            }

        if not _truthy_env(os.environ.get(VFDS_AUTOSTART_ENV), default=True):
            return {
                "ok": False,
                "started": False,
                "base_url": _redact_url(self.base_url),
                "health": first_health.to_dict(),
                "error": f"VFDS server is not reachable and {VFDS_AUTOSTART_ENV}=false",
            }
        if not _is_local_http_url(self.base_url):
            return {
                "ok": False,
                "started": False,
                "base_url": _redact_url(self.base_url),
                "health": first_health.to_dict(),
                "error": "VFDS auto-start is allowed only for localhost URLs",
            }

        with _AUTOSTART_LOCK:
            global _AUTOSTART_PROCESS
            if _AUTOSTART_PROCESS is None or _AUTOSTART_PROCESS.poll() is not None:
                _AUTOSTART_PROCESS, log_path = _start_embedded_vfds_process(self.base_url)
            else:
                log_path = _vfds_autostart_log_path()
            pid = int(getattr(_AUTOSTART_PROCESS, "pid", 0) or 0)

        deadline = time.monotonic() + max(0.25, deadline_s)
        last_health = first_health
        while time.monotonic() < deadline:
            time.sleep(0.25)
            last_health = self.health()
            if last_health.ok:
                return {
                    "ok": True,
                    "already_running": False,
                    "started": True,
                    "pid": pid,
                    "base_url": _redact_url(self.base_url),
                    "log_path": str(log_path),
                    "health": last_health.to_dict(),
                }

        return {
            "ok": False,
            "already_running": False,
            "started": True,
            "pid": pid,
            "base_url": _redact_url(self.base_url),
            "log_path": str(log_path),
            "health": last_health.to_dict(),
            "error": f"VFDS server did not become healthy within {deadline_s:.1f}s",
        }

    def submit_mission(self, payload: Dict[str, Any]) -> VfdsHttpResult:
        return self._request("POST", "/api/v1/missions/realtime", payload=payload, accepted=(200, 202))

    def delete_mission(self, flight_plan_number: int) -> VfdsHttpResult:
        return self._request("DELETE", f"/api/v1/missions/{int(flight_plan_number)}", accepted=(200, 202, 204, 404))

    def post_time_hhmmss(self, hhmmss: str, *, source: str = "VehicleModule") -> VfdsHttpResult:
        return self._request(
            "POST",
            "/api/v1/time",
            payload={"time": str(hhmmss), "source": str(source or "VehicleModule")},
            accepted=(200, 202),
        )

    def get_telemetry_snapshot(self) -> VfdsHttpResult:
        return self._request("GET", "/api/v1/telemetry", accepted=(200,))

    def websocket_url(self, path: str = "/api/v1/ws/live") -> str:
        parsed = urllib.parse.urlparse(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        netloc = parsed.netloc or parsed.path
        normalized_path = path if str(path).startswith("/") else f"/{path}"
        return urllib.parse.urlunparse((scheme, netloc, normalized_path, "", "", ""))

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Any] = None,
        accepted: Tuple[int, ...] = (200,),
    ) -> VfdsHttpResult:
        method = str(method or "GET").upper()
        url = f"{self.base_url}{path if str(path).startswith('/') else '/' + str(path)}"
        data: Optional[bytes] = None
        headers: Dict[str, str] = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                status_code = int(getattr(response, "status", 0) or 0)
                raw = response.read()
                body = self._decode_body(raw)
                return VfdsHttpResult(
                    ok=status_code in accepted,
                    method=method,
                    url=url,
                    status_code=status_code,
                    body=body,
                    error="" if status_code in accepted else f"unexpected status {status_code}",
                )
        except urllib.error.HTTPError as exc:
            raw = exc.read() if hasattr(exc, "read") else b""
            body = self._decode_body(raw)
            status_code = int(getattr(exc, "code", 0) or 0)
            return VfdsHttpResult(
                ok=status_code in accepted,
                method=method,
                url=url,
                status_code=status_code,
                body=body,
                error="" if status_code in accepted else str(exc),
            )
        except Exception as exc:
            return VfdsHttpResult(
                ok=False,
                method=method,
                url=url,
                status_code=0,
                body=None,
                error=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _decode_body(raw: bytes) -> Any:
        if not raw:
            return None
        text = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except Exception:
            return text


def _redact_url(url: str) -> str:
    """Remove userinfo and sensitive query values before exposing status."""
    text = str(url or "")
    try:
        parsed = urllib.parse.urlsplit(text)
    except Exception:
        return text
    hostname = parsed.hostname or ""
    if not hostname:
        return text
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    query_items = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        redacted = "***" if key.lower() in _SENSITIVE_KEYS else value
        query_items.append((key, redacted))
    query = urllib.parse.urlencode(query_items)
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): ("***" if str(key).lower() in _SENSITIVE_KEYS else _redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _redact_string(value: str) -> str:
    text = str(value)
    if "://" not in text:
        return text
    return _URL_RE.sub(lambda match: _redact_url(match.group("url")), text)


def _truthy_env(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if not text:
        return bool(default)
    return text not in {"0", "false", "no", "off", "disabled"}


def _coerce_timeout(*values: Any, default: float) -> float:
    for value in values:
        if value is None:
            continue
        try:
            return max(0.25, float(value))
        except (TypeError, ValueError):
            continue
    return max(0.25, float(default))


def _is_local_http_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").strip().lower()
    return host in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def _framework_root() -> Path:
    # .../VehicleModule/app/services/vfds_client.py -> .../DTAMFramework
    return Path(__file__).resolve().parents[3]


def _vfds_autostart_log_path() -> Path:
    configured = str(os.environ.get(VFDS_AUTOSTART_LOG_ENV) or "").strip()
    if configured:
        return Path(configured).expanduser()
    return _framework_root() / "VehicleModule" / "logs" / "vfds_dynamics_autostart.log"


def _start_embedded_vfds_process(base_url: str = DEFAULT_VFDS_BASE_URL) -> Tuple[subprocess.Popen[Any], Path]:
    root = _framework_root()
    log_path = _vfds_autostart_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    pythonpath_parts = [
        str(root),
        str(root / "VehicleModule"),
        str(root / "DTAMSDK"),
    ]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    parsed = urllib.parse.urlparse(str(base_url or DEFAULT_VFDS_BASE_URL))
    if parsed.hostname:
        env["DTAM_VFDS_HOST"] = "0.0.0.0" if parsed.hostname in {"0.0.0.0", "127.0.0.1", "localhost", "::1"} else parsed.hostname
    if parsed.port:
        env["DTAM_VFDS_PORT"] = str(parsed.port)
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    log_file = log_path.open("a", encoding="utf-8")
    log_file.write("\n=== DTAM VFDS Dynamics autostart ===\n")
    log_file.flush()
    process = subprocess.Popen(
        [sys.executable, "-m", "VehicleModule.app.domain.vfds_dynamics"],
        cwd=str(root),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=creationflags,
    )
    # The child owns the inherited handle; keep the parent from leaking it.
    try:
        log_file.close()
    except Exception:
        pass
    return process, log_path


