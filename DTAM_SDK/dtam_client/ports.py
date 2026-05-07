"""포트 가용성 헬퍼.

각 모듈의 ``*_main.py`` 가 GUI 용 HTTP 포트(uvicorn) 를 잡을 때 사용.
DTAM ICD 통신 자체는 WebSocket(/ws/dtam) 한 채널이라 별도 포트 검증 불필요.

사용 예::

    from dtam_client.ports import find_available_tcp_port

    port = find_available_tcp_port("127.0.0.1", 8095)
"""
from __future__ import annotations

import socket
from collections.abc import Iterable


def _socket_family(host: str) -> socket.AddressFamily:
    return socket.AF_INET6 if ":" in str(host) else socket.AF_INET


def can_bind_tcp(host: str, port: int) -> bool:
    """주어진 host:port 에 TCP 바인딩 가능한지 확인."""
    family = _socket_family(host)
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.bind((str(host), int(port)))
        return True
    except OSError:
        return False


def find_available_tcp_port(
    host: str,
    preferred_port: int,
    *,
    max_tries: int = 100,
    exclude_ports: Iterable[int] | None = None,
) -> int:
    """``preferred_port`` 또는 그 다음 사용 가능한 TCP 포트를 반환.

    ``max_tries`` 안에 가능한 포트가 없으면 ``RuntimeError``.
    """
    start = int(preferred_port)
    excluded = {int(port) for port in (exclude_ports or ())}
    last_port = min(65535, start + int(max_tries) - 1)
    for port in range(start, last_port + 1):
        if port in excluded:
            continue
        if can_bind_tcp(host, port):
            return port
    raise RuntimeError(
        f"No available TCP port for {host} in range {start}-{last_port}."
    )


__all__ = ["can_bind_tcp", "find_available_tcp_port"]
