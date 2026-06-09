"""Port selection helpers shared by DTAM launch scripts."""
from __future__ import annotations

import socket


def _socket_family(host: str) -> socket.AddressFamily:
    return socket.AF_INET6 if ":" in str(host) else socket.AF_INET


def _can_bind(host: str, port: int, socket_type: socket.SocketKind) -> bool:
    family = _socket_family(host)
    try:
        with socket.socket(family, socket_type) as sock:
            sock.bind((str(host), int(port)))
        return True
    except OSError:
        return False


def can_bind_tcp(host: str, port: int) -> bool:
    return _can_bind(host, port, socket.SOCK_STREAM)


def can_bind_udp(host: str, port: int) -> bool:
    return _can_bind(host, port, socket.SOCK_DGRAM)


def find_available_tcp_port(host: str, preferred_port: int, *, max_tries: int = 100) -> int:
    """Return preferred_port, or the next TCP port that can be bound."""
    start = int(preferred_port)
    last_port = min(65535, start + int(max_tries) - 1)
    for port in range(start, last_port + 1):
        if can_bind_tcp(host, port):
            return port
    raise RuntimeError(f"No available TCP port for {host} in range {start}-{last_port}.")


def find_available_udp_tcp_pair(
    host: str,
    preferred_udp_port: int,
    *,
    preferred_tcp_port: int | None = None,
    max_tries: int = 100,
) -> tuple[int, int]:
    """Return an available UDP/TCP pair, preserving TCP = UDP + 1 by default."""
    start_udp = int(preferred_udp_port)
    tcp_delta = int(preferred_tcp_port) - start_udp if preferred_tcp_port is not None else 1

    for offset in range(int(max_tries)):
        udp_port = start_udp + offset * 2
        tcp_port = udp_port + tcp_delta
        if udp_port > 65535 or tcp_port > 65535:
            break
        if can_bind_udp(host, udp_port) and can_bind_tcp(host, tcp_port):
            return udp_port, tcp_port

    last_udp = min(65535, start_udp + (int(max_tries) - 1) * 2)
    raise RuntimeError(f"No available UDP/TCP port pair for {host} starting at {start_udp}-{last_udp}.")
