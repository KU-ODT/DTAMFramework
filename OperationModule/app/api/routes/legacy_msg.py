"""Compatibility routes for older Operations Console ICD POST URLs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.dtam_sdk_service import send_dtam_message

router = APIRouter(prefix="/api/msg")


@router.post("/{message_id}")
async def send_legacy_msg(message_id: str, request: Request) -> JSONResponse:
    """Accept legacy ``/api/msg/{mid}`` posts and forward through ServerRevision."""

    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body if isinstance(body, dict) else {}

    payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
    target_ip = body.get("target_ip") or body.get("targetIp")
    result = send_dtam_message(str(message_id), dict(payload or {}), target_ip=target_ip)
    response: dict[str, Any] = (
        result.model_dump() if hasattr(result, "model_dump") else result.dict()
    )
    response["ok"] = bool(result.sent)
    return JSONResponse(response, status_code=200 if result.sent else 502)
