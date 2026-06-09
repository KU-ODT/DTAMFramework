"""Run the DTAM Mission Planner web app.

기본 동작:
 - FastAPI 앱을 ``http://127.0.0.1:{PORT}`` 로 기동
 - 브라우저를 새 창으로 띄움 (--no-browser 로 생략)
 - DTAM 3001 (Scheduled Flight) 송신 대상을 ``--target-ip/--target-port`` 로 지정
 - ``--my-port`` 로 본 모듈이 사용할 UDP 베이스 포트 지정 (TCP = +1)

사용 예::

    python MP_main.py
    python MP_main.py --target-ip 127.0.0.1 --target-port 17000 --port 8090
    python MP_main.py --host 0.0.0.0 --port 8090 --no-browser

DTAM Mission Planner 가 3001 을 TCP 로 송출하면 DTAMAirVehicle
(AM_main.py) 가 이를 수신해 비행 데이터를 생성한다.
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
FRAMEWORK_ROOT = ROOT.parent                   # d:/DTAM
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"    # dtam_client 위치

# DTAM_MissionManagement 패키지 import 용 + DTAM_SDK 번들 import 용
for extra in (str(FRAMEWORK_ROOT), str(DTAM_SDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from dtam_client._ports import find_available_tcp_port  # noqa: E402
from DTAM_MissionManagement.app.server import create_app, settings  # noqa: E402


def find_fullscreen_browser() -> Optional[Path]:
    candidate_commands = ("msedge", "chrome", "chromium", "brave")
    for command in candidate_commands:
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)

    candidate_paths = (
        Path(os.environ.get("ProgramFiles", ""))
        / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", ""))
        / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LocalAppData", ""))
        / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", ""))
        / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", ""))
        / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LocalAppData", ""))
        / "Google" / "Chrome" / "Application" / "chrome.exe",
    )
    for path in candidate_paths:
        if path.is_file():
            return path
    return None


def open_browser(url: str, fullscreen: bool = False) -> None:
    browser_path = find_fullscreen_browser()
    if browser_path and fullscreen:
        subprocess.Popen(
            [str(browser_path), "--new-window", "--start-fullscreen", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    if browser_path:
        subprocess.Popen(
            [str(browser_path), "--new-window", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    print("[DTAM MP] dedicated browser not found; using default webbrowser.open")
    webbrowser.open(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DTAM Mission Planner web app")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind.")
    parser.add_argument("--port", type=int, default=8090, help="Port to listen on.")
    parser.add_argument("--no-browser", action="store_true", help="Skip opening a browser window.")
    parser.add_argument("--fullscreen", action="store_true", help="Open browser fullscreen.")
    parser.add_argument("--log-level", default="info")

    # DTAM 3001 송신 대상
    parser.add_argument("--target-ip", default=None,
                        help="DTAM target IP for 3001 (default from env or 127.0.0.1)")
    parser.add_argument("--target-port", type=int, default=None,
                        help="DTAM target UDP base port (TCP = +1). Default 17000.")
    parser.add_argument("--my-ip", default=None,
                        help="Local bind IP (default 0.0.0.0)")
    parser.add_argument("--my-port", type=int, default=None,
                        help="Local UDP base port (TCP = +1). Default 17010.")
    parser.add_argument("--server-http-host", default=None,
                        help="DTAM Server Emulator HTTP host for central Database lookup.")
    parser.add_argument("--server-http-port", type=int, default=None,
                        help="DTAM Server Emulator HTTP port for central Database lookup.")
    return parser.parse_args()


def _apply_dtam_overrides(args: argparse.Namespace) -> None:
    """CLI 옵션으로 DTAM 기본 target/my endpoint 를 덮어쓴다."""
    if args.target_ip:
        settings["dtam_target_ip"] = str(args.target_ip)
    if args.target_port is not None:
        settings["dtam_target_port"] = int(args.target_port)
    if args.my_ip:
        settings["dtam_my_ip"] = str(args.my_ip)
    if args.my_port is not None:
        settings["dtam_my_port"] = int(args.my_port)
    if args.server_http_host:
        settings["server_http_host"] = str(args.server_http_host)
    if args.server_http_port is not None:
        settings["server_http_port"] = int(args.server_http_port)


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    os.chdir(ROOT)
    _apply_dtam_overrides(args)

    requested_port = int(args.port)
    args.port = find_available_tcp_port(args.host, requested_port)
    if args.port != requested_port:
        print(f"[DTAM MP] port {requested_port} is busy; using {args.port}.")

    url = f"http://{args.host}:{args.port}"
    print(f"[DTAM MP] GUI    : {url}")
    print(f"[DTAM MP] root   : {ROOT}")
    print(f"[DTAM MP] server Database API: http://{settings['server_http_host']}:{settings['server_http_port']}")
    print(f"[DTAM MP] DTAM → {settings['dtam_target_ip']}:{settings['dtam_target_port']} "
          f"(TCP {int(settings['dtam_target_port']) + 1})")
    print(f"[DTAM MP] my     : {settings['dtam_my_ip']}:{settings['dtam_my_port']} "
          f"(TCP {int(settings['dtam_my_port']) + 1})")

    if not args.no_browser:
        threading.Timer(
            1.0,
            lambda: open_browser(url, fullscreen=args.fullscreen),
        ).start()

    import uvicorn

    app = create_app()
    uvicorn.run(
        app,
        host=args.host,
        port=int(args.port),
        log_level=str(args.log_level).lower(),
    )


if __name__ == "__main__":
    main()
