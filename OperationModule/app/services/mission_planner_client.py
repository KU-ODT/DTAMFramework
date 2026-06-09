"""HTTP client for delegating route planning to DTAM Mission Planner."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException

from app.services.module_process_service import ensure_module_backend


class MissionPlannerClientError(RuntimeError):
    """Raised when the Mission Planner route API cannot satisfy a request."""


def compute_route_via_mission_planner(payload: dict[str, Any]) -> dict[str, Any]:
    """Proxy a route request to the Mission Planner module."""

    start = str(payload.get("start") or payload.get("departureName") or "").strip()
    end = str(payload.get("end") or payload.get("arrivalName") or "").strip()
    if not start or not end:
        raise HTTPException(status_code=400, detail="start and end required")
    if start == end:
        raise HTTPException(status_code=400, detail="Departure and arrival must be different.")

    module_url = ensure_module_backend("mission", timeout_s=12.0)
    request_payload = {
        "start": start,
        "end": end,
        "include_arcs": bool(payload.get("include_arcs", True)),
    }
    return _post_json(f"{module_url}/api/route", request_payload, timeout_s=18.0)


def _post_json(url: str, payload: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            data = response.read().decode("utf-8")
            parsed = json.loads(data) if data else {}
            return parsed if isinstance(parsed, dict) else {"data": parsed}
    except urllib.error.HTTPError as exc:
        detail = _read_error_detail(exc)
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Mission Planner route request failed: {exc}") from exc


def _read_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8")
        data = json.loads(raw) if raw else {}
        if isinstance(data, dict):
            return str(data.get("detail") or data.get("error") or raw or exc.reason)
        return str(data)
    except Exception:
        return str(exc.reason or exc)
