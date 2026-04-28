"""DTAM Operations Console DTAM 통신 service.

``MonitoringModule`` (SDK 베이스) 를 상속한 service 클래스. 다른 클라이언트
모듈들과 동일한 ``class XxxService(XxxModule)`` 패턴 통일을 위해 클래스를
유지한다 — 현재는 heartbeat 만 필요해서 override 가 없지만, 향후 운영자
화면이 4001/4101 같은 forwarding 메시지를 처리하게 되면 ``on_*`` 메서드를
override 하면 된다.

베이스가 제공하는 핸들러 stub (silent drop):
  - on_module_setting_info  (0001)
  - on_module_status        (0002)
  - on_dtam_execute         (2002)
  - on_vehicle_status       (4001)
  - on_camera_image         (4101)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from app.config import settings


def _ensure_sdk_on_path() -> None:
    sdk_root = settings.project_root.parent / "DTAM_SDK"
    if str(sdk_root) not in sys.path:
        sys.path.insert(0, str(sdk_root))


_ensure_sdk_on_path()
from dtam_client import MonitoringModule  # type: ignore  # noqa: E402


class MonitoringService(MonitoringModule):
    """Operations Console DTAM 통신 service — 현재는 heartbeat 전용."""

    def __init__(self, *, target_ip: Optional[str] = None, ws_port: int = 8096) -> None:
        ip = target_ip or os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
        super().__init__(
            server_url=f"ws://{ip}:{ws_port}/ws/dtam",
            heartbeat=True,
        )


__all__ = ["MonitoringService"]
