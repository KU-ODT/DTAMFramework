"""DTAM 4001 송신기 — DTAM_SDK 를 이용해 UDP 로 vehicle status 를 전송."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _ensure_dtam_sdk_on_path() -> None:
    """DTAM_SDK 가 pip install 되어있지 않으면, 프레임워크 내 번들 경로를 sys.path 에 추가."""
    try:
        import dtam_client  # type: ignore  # noqa: F401
        return
    except ImportError:
        pass
    here = Path(__file__).resolve()
    framework_root = here.parents[2]        # d:/DTAM
    candidate = framework_root / "DTAM_SDK"
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


_ensure_dtam_sdk_on_path()


class DtamVehiclePublisher:
    """DTAM_SDK ``DtamClient`` 래퍼 (송수신 양방향).

    - 4001 송신은 ``push()`` 로 수행.
    - 수신은 ``auto_listen=True`` 로 UDP/TCP 리스너가 백그라운드 스레드에서 동작.
      ``on_scheduled_flight_raw`` / ``on_common_time_info_raw`` 에 콜백을 꽂으면
      파싱된 ReceiveResult 객체가 전달된다.
    """

    def __init__(
        self,
        *,
        target_ip: str = "127.0.0.1",
        target_port: int = 17000,
        my_ip: str = "0.0.0.0",
        my_port: int = 17001,
        auto_listen: bool = True,
        async_send: bool = True,
        on_error: Optional[Callable[[Any], None]] = None,
        on_scheduled_flight_raw: Optional[Callable[[Any], None]] = None,
        on_common_time_info_raw: Optional[Callable[[Any], None]] = None,
        on_dtam_execute_raw: Optional[Callable[[Any], None]] = None,
        on_strategic_separation_raw: Optional[Callable[[Any], None]] = None,
        on_tactical_separation_raw: Optional[Callable[[Any], None]] = None,
    ) -> None:
        self.target_ip = str(target_ip)
        self.target_port = int(target_port)
        self.my_ip = str(my_ip)
        self.my_port = int(my_port)
        self.async_send = bool(async_send)
        self.auto_listen = bool(auto_listen)
        self._on_error = on_error
        self.on_scheduled_flight_raw = on_scheduled_flight_raw
        self.on_common_time_info_raw = on_common_time_info_raw
        self.on_dtam_execute_raw = on_dtam_execute_raw
        self.on_strategic_separation_raw = on_strategic_separation_raw
        self.on_tactical_separation_raw = on_tactical_separation_raw
        self._client: Any = None
        self._connect_err: Optional[str] = None
        self._connect()

    def _connect(self) -> None:
        try:
            from dtam_client import DtamClient  # type: ignore

            self._client = DtamClient.module(
                my_ip=self.my_ip,
                my_port=int(self.my_port),
                peer_ip=self.target_ip,
                peer_port=int(self.target_port),
                auto_listen=self.auto_listen,
            )
            if self._on_error is not None:
                self._client.on_send_error = self._on_error
            # 수신 콜백 연결 (사용자가 ``on_*_raw`` 를 지정한 경우)
            if self.on_scheduled_flight_raw is not None:
                self._client.on_scheduled_flight = self.on_scheduled_flight_raw
            if self.on_common_time_info_raw is not None:
                self._client.on_common_time_info = self.on_common_time_info_raw
            if self.on_dtam_execute_raw is not None:
                self._client.on_dtam_execute = self.on_dtam_execute_raw
            if self.on_strategic_separation_raw is not None:
                self._client.on_strategic_separation = self.on_strategic_separation_raw
            if self.on_tactical_separation_raw is not None:
                self._client.on_tactical_separation = self.on_tactical_separation_raw
            self._connect_err = None
        except Exception as exc:
            self._client = None
            self._connect_err = f"{type(exc).__name__}: {exc}"
            logger.warning("DTAM_SDK client init failed: %s", self._connect_err)

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def last_error(self) -> Optional[str]:
        return self._connect_err

    def reconfigure(
        self,
        *,
        target_ip: Optional[str] = None,
        target_port: Optional[int] = None,
        my_ip: Optional[str] = None,
        my_port: Optional[int] = None,
    ) -> None:
        if target_ip is not None:
            self.target_ip = str(target_ip)
        if target_port is not None:
            self.target_port = int(target_port)
        if my_ip is not None:
            self.my_ip = str(my_ip)
        if my_port is not None:
            self.my_port = int(my_port)
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._connect()

    def push_module_status(self, *, source: str = "DTAMAirVehicle", status: int = 1) -> bool:
        if self._client is None:
            return False
        payload = {
            "timestamp": _iso_ts(),
            "source": source,
            "status": int(status),
        }
        try:
            result = self._client.push_module_status(payload)
            return bool(result)
        except Exception as exc:
            logger.debug("DTAM module status push failed: %s", exc)
            return False

    def push(self, message: Dict[str, Any]) -> bool:
        """4001 메시지 전송. 성공 여부 반환."""
        if self._client is None:
            logger.debug("DTAM client offline; dumping payload for %s keys",
                         list(message.keys()))
            return False

        try:
            if self.async_send:
                self._client.push_vehicle_status_async(message)
            else:
                result = self._client.push_vehicle_status(message)
                if not bool(result):
                    if self._on_error:
                        self._on_error(result)
                    return False
            return True
        except Exception as exc:
            logger.warning("DTAM push failed: %s", exc)
            return False

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
