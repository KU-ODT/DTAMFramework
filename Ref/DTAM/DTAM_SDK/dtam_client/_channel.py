"""DtamChannel — 에뮬레이터와 단일 TCP 연결로 양방향 통신.

포트 설정 없이 에뮬레이터 IP 하나만 알면 됨.
연결이 끊기면 자동 재연결.

Usage::

    from dtam_client import DtamChannel

    ch = DtamChannel()

    ch.on_vehicle_status = lambda r: print(r.vehicles)
    ch.on_dtam_execute   = lambda r: print(r.flight_plan_folder_name)

    ch.connect("192.168.1.10", block=False)   # 백그라운드 연결

    # 에뮬레이터로 데이터 전송 (연결만 되어있으면 프로토콜 신경 X)
    ch.push_vehicle_status({...})
    ch.push_dtam_execute({...})
"""
from __future__ import annotations

import json
import socket
import struct
import threading
import time
from typing import Any, Callable, Dict, Optional

from ._config import DEFAULT_TCP_PORT, get_config
from ._result import PushResult
from ._router import route
from ._transport import _format_send_error

_DEFAULT_PORT = DEFAULT_TCP_PORT


class DtamChannel:
    """에뮬레이터 단일 연결 채널.

    DtamListener와 달리 직접 에뮬레이터에 접속하므로
    포트 바인딩·방화벽 설정이 필요 없다.
    """

    _CALLBACK_MAP: Dict[str, str] = {
        "0001": "on_module_setting_info",
        "0002": "on_module_status",
        "0003": "on_common_time_info",
        "1001": "on_sim_mode_setup",
        "1002": "on_simulation_setup",
        "1003": "on_scenario_setup",
        "2001": "on_flight_plan_request",
        "2002": "on_dtam_execute",
        "3001": "on_scheduled_flight",
        "3002": "on_strategic_separation",
        "3003": "on_tactical_separation",
        "4001": "on_vehicle_status",
        "4101": "on_camera_image",
    }

    def __init__(self) -> None:
        self._ip = "127.0.0.1"
        self._port = _DEFAULT_PORT
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._running = False

        # ── 수신 콜백 ─────────────────────────────────────────────
        self.on_module_setting_info:Optional[Callable] = None
        self.on_module_status:      Optional[Callable] = None
        self.on_common_time_info:   Optional[Callable] = None
        self.on_sim_mode_setup:     Optional[Callable] = None
        self.on_simulation_setup:   Optional[Callable] = None
        self.on_scenario_setup:     Optional[Callable] = None
        self.on_flight_plan_request:Optional[Callable] = None
        self.on_dtam_execute:       Optional[Callable] = None
        self.on_scheduled_flight:   Optional[Callable] = None
        self.on_strategic_separation:Optional[Callable] = None
        self.on_tactical_separation:Optional[Callable] = None
        self.on_vehicle_status:     Optional[Callable] = None
        self.on_camera_image:       Optional[Callable] = None
        self.on_unknown:            Optional[Callable] = None

    # ── 공개 API ──────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._sock is not None

    def connect(
        self,
        ip: Optional[str] = None,
        port: Optional[int] = None,
        block: bool = True,
        retry: bool = True,
        retry_interval: float = 3.0,
    ) -> None:
        """에뮬레이터에 연결한다.

        Args:
            ip:             에뮬레이터 IP
            port:           에뮬레이터 채널 포트 (기본 17000)
            block:          True — 현재 스레드 블로킹. False — 백그라운드 실행.
            retry:          True — 연결 끊기면 자동 재연결.
            retry_interval: 재연결 대기 시간 (초).
        """
        cfg = get_config()
        self._ip = ip or cfg.server_ip
        self._port = int(port) if port is not None else cfg.tcp_port
        self._retry = retry
        self._retry_interval = retry_interval
        self._running = True
        t = threading.Thread(target=self._connect_loop, daemon=True)
        t.start()
        if block:
            try:
                while self._running:
                    threading.Event().wait(1.0)
            except KeyboardInterrupt:
                self.disconnect()

    def disconnect(self) -> None:
        """연결을 끊고 재연결 루프를 중단한다."""
        self._running = False
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
        print("[DtamChannel] 연결 종료")

    # ── 송신 메서드 ───────────────────────────────────────────────

    def push_module_status(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_0002 import validate_message
        return self._push(data, validate_message)

    def push_module_setting_info(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_0001 import validate_message
        return self._push(data, validate_message)

    def push_common_time_info(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_0003 import validate_message
        return self._push(data, validate_message)

    def push_sim_mode_setup(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_1001 import validate_message
        return self._push(data, validate_message)

    def push_simulation_setup(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_1002 import validate_message
        return self._push(data, validate_message)

    def push_scenario_setup(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_1003 import validate_message
        return self._push(data, validate_message)

    def push_flight_plan_request(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_2001 import validate_message
        return self._push(data, validate_message)

    def push_dtam_execute(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_2002 import validate_message
        return self._push(data, validate_message)

    def push_scheduled_flight(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_3001 import validate_message
        return self._push(data, validate_message)

    def push_strategic_separation(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_3002 import validate_message
        return self._push(data, validate_message)

    def push_tactical_separation(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_3003 import validate_message
        return self._push(data, validate_message)

    def push_vehicle_status(self, data: Dict[str, Any]) -> PushResult:
        from .schema.msg_4001 import validate_message
        return self._push(data, validate_message)

    def push_camera_image(
        self,
        header: Dict[str, Any],
        image_bytes: bytes = b"",
    ) -> PushResult:
        from .schema.msg_4101 import validate_header
        return self._push(header, validate_header, image_bytes)

    # ── 내부: 연결 루프 ───────────────────────────────────────────

    def _connect_loop(self) -> None:
        while self._running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((self._ip, self._port))
                sock.settimeout(None)
                print(f"[DtamChannel] 연결됨 → {self._ip}:{self._port}")
                with self._lock:
                    self._sock = sock
                self._recv_loop(sock)
                print("[DtamChannel] 연결 끊김")
            except OSError as e:
                print(f"[DtamChannel] {_format_send_error('TCP', self._ip, self._port, e)}")
            except Exception as e:
                print(f"[DtamChannel] connection failed ({self._ip}:{self._port}): {e}")
            with self._lock:
                self._sock = None
            if self._running and self._retry:
                time.sleep(self._retry_interval)
            else:
                break

    # ── 내부: 수신 루프 ───────────────────────────────────────────

    def _recv_loop(self, sock: socket.socket) -> None:
        buf = bytearray()
        sock.settimeout(1.0)
        try:
            while self._running:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf.extend(chunk)
                while len(buf) >= 4:
                    header_len = struct.unpack("<I", buf[:4])[0]
                    if len(buf) < 4 + header_len:
                        break
                    try:
                        header_json = bytes(buf[4:4 + header_len]).decode("utf-8")
                        obj = json.loads(header_json)
                    except Exception:
                        buf.clear()
                        break
                    payload_size = obj.get("payload_size", 0)
                    total = 4 + header_len + payload_size
                    if len(buf) < total:
                        break
                    image_bytes = bytes(buf[4 + header_len:total])
                    del buf[:total]
                    if isinstance(obj, dict):
                        self._dispatch(obj, image_bytes)
        except Exception:
            pass
        finally:
            with self._lock:
                if self._sock is sock:
                    self._sock = None
            try:
                sock.close()
            except Exception:
                pass

    # ── 내부: 프레임 전송 ─────────────────────────────────────────

    def _send_frame(
        self,
        data: Dict[str, Any],
        payload_bytes: bytes = b"",
    ) -> tuple:
        wire = {k: v for k, v in data.items() if not k.startswith("_")}
        try:
            header = json.dumps(wire, ensure_ascii=False).encode("utf-8")
        except Exception as e:
            return False, f"JSON serialization failed: {e}"
        frame = struct.pack("<I", len(header)) + header + payload_bytes
        with self._lock:
            if self._sock is None:
                return False, "channel is not connected. Call connect() first or use DtamClient.push_*()."
            try:
                self._sock.sendall(frame)
                return True, len(frame)
            except OSError as e:
                self._sock = None
                return False, _format_send_error("TCP", self._ip, self._port, e)
            except Exception as e:
                self._sock = None
                return False, str(e)

    def _push(
        self,
        data: Dict[str, Any],
        validator=None,
        payload_bytes: bytes = b"",
    ) -> PushResult:
        result = PushResult(target=f"{self._ip}:{self._port}", payload=data)
        if validator:
            ok, errors, _ = validator(data)
            if not ok:
                result.errors.extend(errors)
                return result
        sent, val = self._send_frame(data, payload_bytes)
        if sent:
            result.ok = True
            result.bytes_sent = val
        else:
            result.errors.append(f"channel send failed: {val}")
        return result

    # ── 내부: 수신 디스패치 ───────────────────────────────────────

    def _dispatch(self, obj: Dict[str, Any], image_bytes: bytes = b"") -> None:
        matched = route(obj)
        if matched is None:
            if self.on_unknown:
                try:
                    self.on_unknown(obj)
                except Exception as e:
                    print(f"[DtamChannel] on_unknown 예외: {e}")
            return
        mid, result = matched
        if mid == "4101" and image_bytes:
            result.image_bytes = image_bytes
        cb_name = self._CALLBACK_MAP.get(mid)
        if cb_name:
            cb = getattr(self, cb_name, None)
            if cb:
                try:
                    cb(result)
                except Exception as e:
                    print(f"[DtamChannel] {cb_name} 예외: {type(e).__name__}: {e}")
