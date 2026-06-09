"""Compatibility facade between the existing GUI API and ServerRevision DTAM."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app import comm
from app.schemas.icd import IcdSendResponse
from app.services.simulation_time_service import apply_operation_simulation_setup


def _supported_messages() -> set[str]:
    try:
        comm._ensure_sdk_on_path()  # type: ignore[attr-defined]
        from dtam_client.schema import ICD_REGISTRY  # type: ignore

        return set(ICD_REGISTRY.keys())
    except Exception:
        return {"1001", "1002", "1003", "2001", "2002"}


def start_module_status_heartbeat() -> None:
    """Kept for older startup code.

    Heartbeat is now owned by `MonitoringService`, which registers as the
    monitoring role over SimulationState `/ws/dtam`.
    """


def stop_module_status_heartbeat() -> None:
    """Kept for older shutdown code."""


def send_dtam_message(
    message_id: str,
    payload: dict[str, Any],
    *,
    target_ip: str | None = None,
) -> IcdSendResponse:
    """Send one ICD payload through SimulationState REST."""

    normalized_id = str(message_id).strip()
    if normalized_id not in _supported_messages():
        raise HTTPException(status_code=404, detail=f"Unsupported ICD message: {message_id}")
    if normalized_id == "1002":
        apply_operation_simulation_setup(payload)
    return comm.send_icd_command(normalized_id, payload, target_ip=target_ip)
