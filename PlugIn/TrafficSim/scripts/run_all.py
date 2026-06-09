from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "TS_main.py"


def _int_env(name: str, fallback: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def _find_available_tcp_port(preferred: int, host: str = "127.0.0.1", used: set[int] | None = None) -> int:
    """Return preferred when free, otherwise ask OS for an available local port."""
    used = used or set()
    bind_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    if preferred not in used:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((bind_host, preferred))
                return preferred
            except OSError:
                pass

    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((bind_host, 0))
            port = int(sock.getsockname()[1])
        if port not in used:
            return port


def _build_env(host: str, api_port: int, tile_port: int, frontend_port: int) -> dict:
    env = os.environ.copy()
    env["UATM_SERVER_HOST"] = host
    env["UATM_SERVER_PORT"] = str(api_port)
    env["UATM_TILE_HOST"] = host
    env["UATM_TILE_PORT"] = str(tile_port)
    env["UATM_FRONTEND_HOST"] = host
    env["UATM_FRONTEND_PORT"] = str(frontend_port)
    return env


def _start(service: str, env: dict) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(APP), service], env=env, cwd=str(ROOT))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run API, tiles, and frontend together.")
    parser.add_argument(
        "--host",
        default=os.getenv("UATM_SERVER_HOST", "127.0.0.1"),
        help="Bind host for all services.",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=_int_env("UATM_SERVER_PORT", 8002),
        help="Port for API server.",
    )
    parser.add_argument(
        "--tile-port",
        type=int,
        default=_int_env("UATM_TILE_PORT", 8001),
        help="Port for tile/DEM server.",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=_int_env("UATM_FRONTEND_PORT", 5173),
        help="Port for frontend proxy server.",
    )
    args = parser.parse_args(argv)

    used_ports: set[int] = set()
    api_port = _find_available_tcp_port(args.api_port, args.host, used_ports)
    used_ports.add(api_port)
    tile_port = _find_available_tcp_port(args.tile_port, args.host, used_ports)
    used_ports.add(tile_port)
    frontend_port = _find_available_tcp_port(args.frontend_port, args.host, used_ports)
    if (api_port, tile_port, frontend_port) != (args.api_port, args.tile_port, args.frontend_port):
        print(
            "[TrafficSim] requested port busy; using "
            f"api={api_port}, tiles={tile_port}, frontend={frontend_port}"
        )

    env = _build_env(args.host, api_port, tile_port, frontend_port)
    print(f"[TrafficSim] frontend: http://{args.host}:{frontend_port}/")
    procs = []
    try:
        procs.append(_start("api", env))
        procs.append(_start("tiles", env))
        procs.append(_start("frontend", env))

        while True:
            time.sleep(0.5)
            exited = [p for p in procs if p.poll() is not None]
            if exited:
                for p in exited:
                    code = p.poll()
                    print(f"[run_all] {p.args[-1]} exited with code {code}.")
                break
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        time.sleep(0.5)
        for p in procs:
            if p.poll() is None:
                p.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
