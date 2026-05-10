"""Communication manager backed by the sibling DTAM_SDK package."""
from __future__ import annotations

import asyncio
import json
import socket
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from .sdk_import import ensure_sdk_path
from .state import STATE, Target

ensure_sdk_path()
from dtam_client import DtamClient, PushResult  # noqa: E402
from dtam_client._client import MESSAGE_SPECS  # noqa: E402


PING_MAGIC = "__DTAM_PING__"
PONG_MAGIC = "__DTAM_PONG__"


class CommManager:
    """GUI communication bridge.

    DTAM messages are sent and received through ``DTAM_SDK.dtam_client``.
    The small ping packet is GUI-only diagnostics and is intentionally kept
    outside the ICD message flow.
    """

    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.client: Optional[DtamClient] = None
        self.channel_clients: set = set()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def start_rx(self) -> Tuple[bool, str]:
        await self.stop_rx()
        sr = STATE.self_rx
        ok, msg = self._check_bind_available(sr.bind_ip, sr.bind_port)
        if not ok:
            sr.enabled = False
            return False, msg

        client = DtamClient.module(
            my_ip=sr.bind_ip,
            my_port=sr.bind_port,
            peer_ip="127.0.0.1",
            peer_port=sr.bind_port,
            auto_listen=False,
        )
        self._attach_callbacks(client)
        client.listen(block=False)
        self.client = client
        sr.enabled = True
        return True, f"DTAM_SDK listener UDP {sr.bind_ip}:{sr.bind_port} / TCP {sr.bind_ip}:{sr.bind_port + 1}"

    async def stop_rx(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
        STATE.self_rx.enabled = False

    def send_message(
        self,
        mid: str,
        data: Dict[str, Any],
        target: Target,
        *,
        image_bytes: bytes = b"",
    ) -> PushResult:
        """Send one DTAM message through the SDK."""
        client = self.client
        close_after = False
        if client is None:
            client = DtamClient.module(
                my_ip=STATE.self_rx.bind_ip,
                my_port=STATE.self_rx.bind_port,
                peer_ip=target.ip,
                peer_port=target.port,
                peer_tcp_port=target.tcp_port,
                auto_listen=False,
            )
            close_after = True
        try:
            return client.send(
                mid,
                data,
                image_bytes=image_bytes,
                target_ip=target.ip,
                udp_port=target.port,
                tcp_port=target.tcp_port,
            )
        finally:
            if close_after:
                client.close()

    def send_to_channels(self, data: Dict[str, Any], payload_bytes: bytes = b"") -> int:
        """Compatibility hook for the old GUI channel mode.

        Persistent channel clients are no longer hosted by odt_Integration.
        The GUI now exercises the real SDK's normal UDP/TCP send path.
        """
        return 0

    async def ping_target(self, target_name: str, timeout: float = 1.0) -> Tuple[bool, str]:
        t = STATE.get_target(target_name)
        if not t:
            return False, "target not found"

        ok, msg, rtt = await asyncio.to_thread(self._ping_sync, t.ip, t.port, timeout)
        t.last_ping_ok = ok
        t.last_ping_rtt_ms = rtt
        t.last_ping_msg = msg
        return ok, msg

    def _attach_callbacks(self, client: DtamClient) -> None:
        for mid in MESSAGE_SPECS:
            client.on(mid, self._make_receive_handler(mid))

    def _make_receive_handler(self, mid: str):
        def handle(result: Any) -> None:
            now = time.time()
            sr = STATE.self_rx
            sr.rx_count += 1
            sr.rx_last_ts = now
            payload = result.to_dict() if hasattr(result, "to_dict") else result
            if isinstance(payload, dict):
                sr.rx_last_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            else:
                sr.rx_last_payload = b""

            msg = STATE.get_message(mid)
            if msg:
                msg.rx_count += 1
                msg.rx_last_ts = now
                msg.rx_last_payload = payload if isinstance(payload, dict) else {"value": str(payload)}

        return handle

    @staticmethod
    def _check_bind_available(bind_ip: str, udp_port: int) -> Tuple[bool, str]:
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.bind((bind_ip, int(udp_port)))
            tcp.bind((bind_ip, int(udp_port) + 1))
            return True, "ok"
        except OSError as exc:
            return False, f"bind failed ({bind_ip}:{udp_port}/{int(udp_port) + 1}) - {exc}"
        finally:
            udp.close()
            tcp.close()

    @staticmethod
    def _ping_sync(ip: str, port: int, timeout: float) -> Tuple[bool, str, Optional[float]]:
        pid = str(uuid.uuid4())
        payload = json.dumps({"__dtam__": PING_MAGIC, "id": pid}).encode("utf-8")
        start = time.time()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(float(timeout))
                sock.sendto(payload, (ip, int(port)))
                while True:
                    data, _addr = sock.recvfrom(4096)
                    obj = json.loads(data.decode("utf-8"))
                    if obj.get("__dtam__") == PONG_MAGIC and obj.get("id") == pid:
                        rtt = (time.time() - start) * 1000
                        return True, f"OK ({rtt:.1f} ms)", rtt
        except socket.timeout:
            return False, f"no response ({timeout * 1000:.0f} ms)", None
        except OSError as exc:
            return False, f"send failed - {exc}", None
        except Exception as exc:
            return False, f"ping failed - {type(exc).__name__}: {exc}", None


COMM = CommManager()
