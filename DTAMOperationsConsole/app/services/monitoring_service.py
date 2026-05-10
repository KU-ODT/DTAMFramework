"""DTAM Operations Console DTAM 통신 service.

``MonitoringModule`` (SDK 베이스) 를 상속한 service 클래스. 다른 클라이언트
모듈들 (``MissionService(MissionModule)``, ``IntegratedAirMobilityService(VehicleModule)``)
과 동일한 ``class XxxService(XxxModule)`` 패턴 — stats + describe + reconfigure
를 모두 제공.

OpsConsole 은 자체 도메인 처리는 하지 않고 (운영 화면이 State Server REST 폴링
으로 데이터 가져옴), forwarding 받는 5개 mid 의 stats 만 추적해서 WS 링크
헬스체크용으로 노출:

  - 0001 ModuleSettingInfo  (다른 모듈의 식별 정보)
  - 0002 ModuleStatus        (다른 모듈의 heartbeat)
  - 2002 DtamExecute         (자기 자신의 명령 echo)
  - 4001 VehicleStatus       (10Hz 차량 상태)
  - 4101 CameraImage         (5Hz 카메라 프레임)
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Any, Dict, Optional

from app.config import settings


def _ensure_sdk_on_path() -> None:
    sdk_root = settings.project_root.parent / "DTAM_SDK"
    if str(sdk_root) not in sys.path:
        sys.path.insert(0, str(sdk_root))


_ensure_sdk_on_path()
from dtam_client import MonitoringModule, on_receive  # type: ignore  # noqa: E402


def _result_raw(result: Any) -> Dict[str, Any]:
    """ICD dataclass / dict / ReceiveResult 어느 형식이 와도 dict 으로 정규화."""
    if isinstance(result, dict):
        return result
    raw = getattr(result, "raw", None)
    if isinstance(raw, dict):
        return raw
    import dataclasses as _dc
    if _dc.is_dataclass(result) and not isinstance(result, type):
        return _dc.asdict(result)
    return {}


class MonitoringService(MonitoringModule):
    """Operations Console DTAM 통신 service — stats + heartbeat."""

    def __init__(self, *, target_ip: Optional[str] = None, ws_port: int = 8096) -> None:
        ip = target_ip or os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"

        # 도메인 상태 (super().__init__ 보다 먼저 — 핸들러가 self._lock 참조)
        self._lock = threading.RLock()
        self._target_ip = str(ip)
        self._ws_port = int(ws_port)

        self._rx_0001_count = 0
        self._rx_0002_count = 0
        self._rx_2002_count = 0
        self._rx_4001_count = 0
        self._rx_4101_count = 0
        self._last_rx_0001 = ""
        self._last_rx_0002 = ""
        self._last_rx_2002 = ""
        self._last_rx_4001 = ""
        self._last_rx_4101 = ""

        super().__init__(
            server_url=f"ws://{self._target_ip}:{self._ws_port}/ws/dtam",
            heartbeat=True,
        )

    # ──────────────────────────────────────────────────────────
    # 수신 핸들러 — base stub override (stats 만 기록, 도메인 처리는 X)
    # 데코레이터는 가독성용 — base 가 이미 mid 매핑 보유.
    # ──────────────────────────────────────────────────────────
    @on_receive("0001")
    def on_module_setting_info(self, msg: Any) -> None:
        raw = _result_raw(msg)
        source = str(raw.get("source") or raw.get("moduleSource") or "")
        with self._lock:
            self._rx_0001_count += 1
            self._last_rx_0001 = source or str(raw)[:80]

    @on_receive("0002")
    def on_module_status(self, msg: Any) -> None:
        raw = _result_raw(msg)
        source = str(raw.get("source") or raw.get("moduleSource") or "")
        with self._lock:
            self._rx_0002_count += 1
            self._last_rx_0002 = source or str(raw)[:80]

    @on_receive("2002")
    def on_dtam_execute(self, msg: Any) -> None:
        raw = _result_raw(msg)
        folder = str(raw.get("flightPlanFolderName") or "")
        with self._lock:
            self._rx_2002_count += 1
            self._last_rx_2002 = folder or str(raw)[:80]

    @on_receive("4001")
    def on_vehicle_status(self, msg: Any) -> None:
        # 4001 은 wire 모양: {timestamp, UAM0001:..., UAM0002:...}
        # dataclass 모양: {timestamp, vehicles:{UAM0001:..., UAM0002:...}}
        # 둘 다 지원해서 차량 수 계산.
        raw = _result_raw(msg)
        n_vehicles = 0
        if isinstance(raw, dict):
            vehicles_field = raw.get("vehicles")
            if isinstance(vehicles_field, dict):
                n_vehicles = len(vehicles_field)
            else:
                n_vehicles = sum(1 for k in raw.keys() if k != "timestamp")
        with self._lock:
            self._rx_4001_count += 1
            self._last_rx_4001 = f"{n_vehicles} vehicles"

    @on_receive("4101")
    def on_camera_image(self, msg: Any) -> None:
        raw = _result_raw(msg)
        vid = str(raw.get("vehicle_id") or raw.get("vehicleId") or "")
        cam = str(raw.get("camera_name") or raw.get("cameraName") or "")
        with self._lock:
            self._rx_4101_count += 1
            self._last_rx_4101 = f"{vid} {cam}".strip() or str(raw)[:80]

    # ──────────────────────────────────────────────────────────
    # 설정 / 상태
    # ──────────────────────────────────────────────────────────
    def reconfigure(  # type: ignore[override]
        self,
        *,
        target_ip: Optional[str] = None,
        ws_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """WebSocket endpoint 재설정 — 핸들러 등록은 보존."""
        with self._lock:
            changed = False
            if target_ip is not None and str(target_ip) != self._target_ip:
                self._target_ip = str(target_ip)
                changed = True
            if ws_port is not None and int(ws_port) != self._ws_port:
                self._ws_port = int(ws_port)
                changed = True
            new_url = f"ws://{self._target_ip}:{self._ws_port}/ws/dtam"
        if changed:
            super().reconfigure(server_url=new_url)
        return self.describe()

    def describe(self) -> Dict[str, Any]:
        """WS 링크 상태 + rx 통계 — ``/api/v1/dtam/status`` 라우트가 사용."""
        with self._lock:
            return {
                "target_ip": self._target_ip,
                "ws_port": self._ws_port,
                "server_url": self.server_url,
                "last_error": self.stats.last_error or "",
                "ready": True,
                "connected": self.connected,
                "registered": self.registered,
                "rx_0001_count": self._rx_0001_count,
                "rx_0002_count": self._rx_0002_count,
                "rx_2002_count": self._rx_2002_count,
                "rx_4001_count": self._rx_4001_count,
                "rx_4101_count": self._rx_4101_count,
                "last_rx_0001": self._last_rx_0001,
                "last_rx_0002": self._last_rx_0002,
                "last_rx_2002": self._last_rx_2002,
                "last_rx_4001": self._last_rx_4001,
                "last_rx_4101": self._last_rx_4101,
                "stats": self.stats.to_dict(),
            }


__all__ = ["MonitoringService"]
