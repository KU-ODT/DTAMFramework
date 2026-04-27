"""dtam_client 수신 리스너 — UDP + TCP 동시 대기, 콜백 디스패치.

모듈 개발자는 DtamListener 인스턴스를 만들고 콜백만 연결하면 된다.
소켓/프레이밍/파싱은 내부에서 자동 처리.
"""
from __future__ import annotations

import json
import socket
import struct
import threading
from typing import Any, Callable, Dict, Optional

from ._config import DEFAULT_BASE_PORT
from ._router import route


class DtamListener:
    """에뮬레이터에서 오는 데이터를 수신하는 리스너.

    UDP와 TCP를 동시에 수신하며, 메시지 종류별 콜백을 호출한다.
    TCP는 [u32le header_len][header_json][payload_bytes] 프레이밍을 사용
    (에뮬레이터 pusher와 동일한 포맷).

    Example::

        from dtam_client import DtamListener

        listener = DtamListener(bind_ip="0.0.0.0")

        def on_vehicle(result):
            v = result.vehicles[0]
            print(f"{v.vehicle_id} pos={v.position}")

        def on_execute(result):
            print(f"DTAM Execute: folder={result.raw.get('flightPlanFolderName')}")

        listener.on_vehicle_status = on_vehicle
        listener.on_dtam_execute   = on_execute

        listener.start(block=True)   # Ctrl+C 로 종료
    """

    # mid → 콜백 속성 이름 매핑
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

    def __init__(
        self,
        bind_ip: str = "0.0.0.0",
        udp_port: int = DEFAULT_BASE_PORT,
        tcp_port: Optional[int] = None,
    ) -> None:
        self.bind_ip = bind_ip
        self.udp_port = int(udp_port)
        self.tcp_port = int(tcp_port) if tcp_port is not None else self.udp_port + 1
        self._running = False
        self._threads: list = []

        # ── 메시지별 콜백 ──────────────────────────────────────────
        # 각 콜백은 해당 receiver 의 ReceiveResult 를 인자로 받는다.

        self.on_module_setting_info: Optional[Callable] = None    # MSG 0001 UDP
        """(result: msg_0001.ReceiveResult) ??None"""

        self.on_module_status: Optional[Callable] = None          # MSG 0002 UDP
        """(result: msg_0002.ReceiveResult) → None"""

        self.on_common_time_info: Optional[Callable] = None       # MSG 0003 UDP
        """(result: msg_0003.ReceiveResult) → None"""

        self.on_sim_mode_setup: Optional[Callable] = None         # MSG 1001 UDP
        """(result: msg_1001.ReceiveResult) → None"""

        self.on_simulation_setup: Optional[Callable] = None       # MSG 1002 UDP
        """(result: msg_1002.ReceiveResult) → None"""

        self.on_scenario_setup: Optional[Callable] = None         # MSG 1003 UDP
        """(result: msg_1003.ReceiveResult) → None"""

        self.on_flight_plan_request: Optional[Callable] = None    # MSG 2001 TCP
        """(result: msg_2001.ReceiveResult) → None"""

        self.on_dtam_execute: Optional[Callable] = None           # MSG 2002 TCP
        """(result: msg_2002.ReceiveResult) → None"""

        self.on_scheduled_flight: Optional[Callable] = None       # MSG 3001 TCP
        """(result: msg_3001.ReceiveResult) → None"""

        self.on_strategic_separation: Optional[Callable] = None   # MSG 3002 TCP
        """(result: msg_3002.ReceiveResult) → None"""

        self.on_tactical_separation: Optional[Callable] = None    # MSG 3003 TCP
        """(result: msg_3003.ReceiveResult) → None"""

        self.on_vehicle_status: Optional[Callable] = None         # MSG 4001 UDP
        """(result: msg_4001.ReceiveResult) → None"""

        self.on_camera_image: Optional[Callable] = None           # MSG 4101 TCP
        """(result: msg_4101.ReceiveResult) → None  ※ result.image_bytes 포함"""

        self.on_unknown: Optional[Callable] = None
        """매칭되지 않은 메시지: (raw_dict: dict) → None"""

    # ── 내부: 콜백 디스패치 ────────────────────────────────────────

    def _dispatch(self, obj: Dict[str, Any], image_bytes: bytes = b"") -> None:
        matched = route(obj)
        if matched is None:
            if self.on_unknown:
                try:
                    self.on_unknown(obj)
                except Exception as e:
                    print(f"[dtam_client] on_unknown 예외: {e}")
            return

        mid, result = matched

        # 4101: 이미지 바이너리를 result 에 주입
        if mid == "4101" and image_bytes:
            result.image_bytes = image_bytes

        cb_name = self._CALLBACK_MAP.get(mid)
        if cb_name:
            cb = getattr(self, cb_name, None)
            if cb:
                try:
                    cb(result)
                except Exception as e:
                    import traceback
                    print(f"[dtam_client] {cb_name} 콜백 예외: {type(e).__name__}: {e}")
                    traceback.print_exc()

    # ── 내부: UDP 수신 루프 ────────────────────────────────────────

    def _udp_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)
        try:
            sock.bind((self.bind_ip, self.udp_port))
        except OSError as e:
            print(f"[dtam_client] UDP 바인딩 실패 ({self.bind_ip}:{self.udp_port}): {e}")
            return
        print(f"[dtam_client] UDP 수신 시작 {self.bind_ip}:{self.udp_port}")
        try:
            while self._running:
                try:
                    data, addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                try:
                    obj = json.loads(data.decode("utf-8"))
                    if isinstance(obj, dict):
                        if obj.get("__dtam__") == "__DTAM_PING__":
                            reply = {
                                "__dtam__": "__DTAM_PONG__",
                                "id": obj.get("id"),
                            }
                            sock.sendto(json.dumps(reply).encode("utf-8"), addr)
                            continue
                        self._dispatch(obj)
                except Exception:
                    pass
        finally:
            sock.close()

    # ── 내부: TCP 연결 핸들러 (연결 1개당 스레드) ──────────────────

    def _handle_tcp_conn(self, conn: socket.socket) -> None:
        """TCP 연결에서 binary-framed 메시지를 읽어 _dispatch."""
        buf = bytearray()
        conn.settimeout(30.0)
        try:
            while self._running:
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buf.extend(chunk)

                # 버퍼에서 완성된 프레임 꺼내기
                while len(buf) >= 4:
                    header_len = struct.unpack("<I", buf[:4])[0]
                    if len(buf) < 4 + header_len:
                        break  # 헤더 아직 다 안 옴
                    try:
                        header_json = bytes(buf[4:4 + header_len]).decode("utf-8")
                        obj = json.loads(header_json)
                    except Exception:
                        buf.clear()
                        break
                    payload_size = obj.get("payload_size", 0)
                    total = 4 + header_len + payload_size
                    if len(buf) < total:
                        break  # 페이로드 아직 다 안 옴
                    image_bytes = bytes(buf[4 + header_len:total])
                    del buf[:total]
                    if isinstance(obj, dict):
                        self._dispatch(obj, image_bytes)
        except Exception:
            pass
        finally:
            conn.close()

    # ── 내부: TCP accept 루프 ──────────────────────────────────────

    def _tcp_loop(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.settimeout(1.0)
        try:
            srv.bind((self.bind_ip, self.tcp_port))
        except OSError as e:
            print(f"[dtam_client] TCP 바인딩 실패 ({self.bind_ip}:{self.tcp_port}): {e}")
            return
        srv.listen(32)
        print(f"[dtam_client] TCP 수신 시작 {self.bind_ip}:{self.tcp_port}")
        try:
            while self._running:
                try:
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                t = threading.Thread(
                    target=self._handle_tcp_conn,
                    args=(conn,),
                    daemon=True,
                )
                t.start()
        finally:
            srv.close()

    # ── 공개 API ──────────────────────────────────────────────────

    def start(self, block: bool = True) -> None:
        """UDP + TCP 리스너를 시작한다.

        Args:
            block: True(기본) — 현재 스레드 블로킹. Ctrl+C 로 종료.
                   False        — 백그라운드 스레드로 실행, 즉시 반환.

        Example::

            # 백그라운드로 실행 후 다른 작업 병행
            listener.start(block=False)
            run_my_simulation_loop()
        """
        self._running = True
        for target in (self._udp_loop, self._tcp_loop):
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self._threads.append(t)

        if block:
            try:
                while self._running:
                    threading.Event().wait(1.0)
            except KeyboardInterrupt:
                self.stop()

    def stop(self) -> None:
        """리스너를 중지하고 모든 스레드가 종료될 때까지 대기."""
        self._running = False
        for t in self._threads:
            t.join(timeout=3.0)
        self._threads.clear()
        print("[dtam_client] 리스너 중지")
