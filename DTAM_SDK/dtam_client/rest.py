"""DtamRest — 단발 REST 호출용 작은 헬퍼.

장기 구독·forwarding 이 필요 없는 운영자 스크립트나 테스트에서 사용.
모듈끼리 (vehicle/mission/etc.) 가 메시지를 주고받는 데이터 경로는
``DtamModule`` (WS) 를 사용하세요.

REST는 다음 두 가지에 적합:
  1. 외부 트리거 / Swagger UI 호출 (예: 운영자가 GUI에서 "1002 play" 누르기)
  2. 단발성 조회 (서버 스냅샷, ICD 문서 메타 등)

사용 예::

    from dtam_client import DtamRest

    state = DtamRest("http://127.0.0.1:8096")
    state.push("simulation_setup", {"playState": "play"}, role="vehicle")
    snap = state.snapshot()                       # GET /api/state
    state.heartbeat("DTAMOperationsConsole")     # POST /api/heartbeat

    core = DtamRest("http://127.0.0.1:8095")
    core.process_start("vehicle")                  # POST /api/v1/process/vehicle/start

표준 라이브러리(urllib)만 사용 — requests 같은 추가 의존성 없음.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .catalog import resolve


class DtamRestError(RuntimeError):
    """REST 호출 실패. ``status`` / ``response`` 가 있을 수 있음."""

    def __init__(self, msg: str, *, status: Optional[int] = None, response: Any = None) -> None:
        super().__init__(msg)
        self.status = status
        self.response = response


class DtamRest:
    """SimulationState(8096) 또는 CoreServer(8095) 의 REST API 헬퍼."""

    def __init__(self, base_url: str, *, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)

    # ── SimulationState (8096) ────────────────────────────────
    def push(
        self,
        message: str | int,
        payload: Dict[str, Any],
        *,
        role: str = "",
    ) -> Dict[str, Any]:
        """``POST /api/msg/{mid}`` — 메시지 송신.

        ``role`` 을 비우면 서버가 ``FORWARD_RULES`` 에 따라 브로드캐스트.
        """
        spec = resolve(message)
        body = {"role": role or "", "payload": payload}
        return self._post(f"/api/msg/{spec.mid}", body)

    def snapshot(self) -> Dict[str, Any]:
        """``GET /api/state`` — 서버/모듈/트래픽 스냅샷."""
        return self._get("/api/state")

    def modules(self) -> Dict[str, Any]:
        """``GET /api/modules`` — 모듈 레지스트리."""
        return self._get("/api/modules")

    def heartbeat(self, source: str) -> Dict[str, Any]:
        """``POST /api/heartbeat`` — 강제 heartbeat 주입."""
        return self._post("/api/heartbeat", {"source": source})

    def db_stats(self) -> Dict[str, Any]:
        """``GET /api/db/stats`` — file DB 통계 (있으면)."""
        return self._get("/api/db/stats")

    # ── CoreServer (8095) ─────────────────────────────────────
    def icd_list(self) -> Any:
        return self._get("/api/icd")

    def icd_doc(self, mid: str, *, lang: str = "ko") -> str:
        return self._get_text(f"/api/icd/{mid}?lang={lang}")

    def process_start(self, role: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/process/{role}/start", None)

    def process_stop(self, role: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/process/{role}/stop", None)

    # ── 내부 ──────────────────────────────────────────────────
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
