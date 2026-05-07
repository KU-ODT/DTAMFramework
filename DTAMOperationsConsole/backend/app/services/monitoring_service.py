"""Operations Console WebSocket service for SimulationState forwarding."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from backend.app.core.settings import settings


def _ensure_sdk_on_path() -> None:
    sdk_root = settings.project_root.parent / "DTAM_SDK"
    sdk_path = str(sdk_root)
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)


_ensure_sdk_on_path()
from dtam_client import MonitoringModule  # type: ignore  # noqa: E402


class MonitoringService(MonitoringModule):
    """Register the Operations Console as the monitoring role over `/ws/dtam`."""

    def __init__(self, *, target_ip: Optional[str] = None, ws_port: int | None = None) -> None:
        ip = target_ip or os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
        port = int(ws_port or os.environ.get("DTAM_WS_PORT") or 8096)
        super().__init__(
            server_url=f"ws://{ip}:{port}/ws/dtam",
            heartbeat=True,
        )

    def on_vehicle_status(self, msg) -> None:
        from backend.app.services.vehicle_status_service import record_vehicle_status

        record_vehicle_status(msg)


__all__ = ["MonitoringService"]
