"""Small REST helper for DTAM operational scripts and tests.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .catalog import resolve


class DtamRestError(RuntimeError):
    """Internal helper."""

    def __init__(self, msg: str, *, status: Optional[int] = None, response: Any = None) -> None:
        super().__init__(msg)
        self.status = status
        self.response = response


class DtamRest:
    """Internal helper."""

    def __init__(self, base_url: str, *, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)

    # Registration handling
    def push(
        self,
        message: str | int,
        payload: Dict[str, Any],
        *,
        role: str = "",
    ) -> Dict[str, Any]:
        """Internal DTAM helper."""
        spec = resolve(message)
        body = {"role": role or "", "payload": payload}
        return self._post(f"/api/msg/{spec.mid}", body)

    def snapshot(self) -> Dict[str, Any]:
        """Internal helper."""
        return self._get("/api/state")

    def modules(self) -> Dict[str, Any]:
        """Internal helper."""
        return self._get("/api/modules")

    def heartbeat(self, source: str) -> Dict[str, Any]:
        """Internal helper."""
        return self._post("/api/heartbeat", {"source": source})

    def db_stats(self) -> Dict[str, Any]:
        """Internal helper."""
        return self._get("/api/db/stats")

    # Registration handling
    def icd_list(self) -> Any:
        return self._get("/api/icd")

    def icd_doc(self, mid: str, *, lang: str = "ko") -> str:
        return self._get_text(f"/api/icd/{mid}?lang={lang}")

    def process_start(self, role: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/process/{role}/start", None)

    def process_stop(self, role: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/process/{role}/stop", None)

    # Registration handling
    def _get(self, path: str) -> Any:
        return self._request("GET", path, None)

    def _get_text(self, path: str) -> str:
        url = self.base_url + path
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise DtamRestError(f"GET {path} failed: {exc.code} {exc.reason}",
                                status=exc.code, response=exc.read()) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise DtamRestError(f"GET {path} unreachable: {exc}") from exc

    def _post(self, path: str, body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return self._request("POST", path, body)

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]]) -> Any:
        url = self.base_url + path
        data: Optional[bytes] = None
        headers: Dict[str, str] = {}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                if not raw:
                    return {}
                ctype = resp.headers.get("Content-Type", "")
                if "json" in ctype.lower():
                    return json.loads(raw)
                return {"_raw": raw}
        except urllib.error.HTTPError as exc:
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
                err_json = json.loads(err_body) if err_body else None
            except Exception:
                err_json = None
            raise DtamRestError(
                f"{method} {path} failed: {exc.code} {exc.reason}",
                status=exc.code,
                response=err_json,
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise DtamRestError(f"{method} {path} unreachable: {exc}") from exc


__all__ = ["DtamRest", "DtamRestError"]
