from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def _int_env(name: str, fallback: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


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
    return subprocess.Popen([sys.executable, str(APP), service], env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run API, tiles, and frontend together.")
    parser.add_argument(
        "--host",
        default=os.getenv("UATM_SERVER_HOST", "203.252.161.192"),
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
    args = parser.parse_args()

    env = _build_env(args.host, args.api_port, args.tile_port, args.frontend_port)
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
