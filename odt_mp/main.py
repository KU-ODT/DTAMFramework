from __future__ import annotations

import sys
import socket
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
DTAM_SDK_ROOT = ROOT.parent / "DTAM_SDK"

if str(DTAM_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(DTAM_SDK_ROOT))

from app.config import SERVER_HOST, SERVER_PORT
from app.server import create_app
from dtam_client._ports import find_available_tcp_port

app = create_app()


def _discover_access_ips() -> list[str]:
    candidates: list[str] = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            candidates.append(sock.getsockname()[0])
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                candidates.append(ip)
    except OSError:
        pass

    seen = set()
    unique = []
    for ip in candidates:
        if ip in seen:
            continue
        seen.add(ip)
        unique.append(ip)

    preferred = [ip for ip in unique if ip.startswith("203.252.")]
    remainder = [ip for ip in unique if not ip.startswith("203.252.")]
    return preferred + remainder

if __name__ == "__main__":
    selected_port = find_available_tcp_port(SERVER_HOST, SERVER_PORT)
    if selected_port != SERVER_PORT:
        print(f"[ODT Mission Planner] port {SERVER_PORT} is busy; using {selected_port}.")

    print(f"[ODT Mission Planner] Listening on http://{SERVER_HOST}:{selected_port}")
    if SERVER_HOST in {"0.0.0.0", "::"}:
        access_ips = _discover_access_ips()
        if access_ips:
            for ip in access_ips:
                print(f"[ODT Mission Planner] Network URL: http://{ip}:{selected_port}")
    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=selected_port,
        reload=False,
        log_level="info",
    )
