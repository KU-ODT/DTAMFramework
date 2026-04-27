"""Run the DTAMAirMobility web app.

기본 동작:
 - FastAPI 앱을 ``http://127.0.0.1:{PORT}`` 로 기동
 - 브라우저를 새 창(가능하면 전체화면)으로 띄움
 - ``--target-ip/--target-port/--my-port`` 로 DTAM 4001 송신 대상 지정
 - ``--plan`` 으로 비행계획 JSON 을 즉시 등록

사용 예::

    python AM_main.py
    python AM_main.py --target-ip 203.252.1.10 --target-port 17000 --port 8100
    python AM_main.py --plan ./mission1.json --plan ./mission2.json --clock wall
    python AM_main.py --no-browser
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent
FRAMEWORK_ROOT = ROOT.parent                   # d:/DTAMFramework
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"    # dtam_client 위치

# DTAMAirMobility 패키지 import 용 + DTAM_SDK 번들 import 용
for extra in (str(FRAMEWORK_ROOT), str(DTAM_SDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from dtam_client.ports import find_available_tcp_port  # noqa: E402
from DTAMAirMobility.backend.app import create_app  # noqa: E402
from DTAMAirMobility.service.integrated_service import (  # noqa: E402
    ClockMode,
    IntegratedAirMobilityService,
)


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


def open_browser(url: str, fullscreen: bool = True) -> None:
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
    print("[DTAMAirMobility] dedicated browser not found; using default webbrowser.open")
    webbrowser.open(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DTAM AirMobility web app")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind.")
    parser.add_argument("--port", type=int, default=8100, help="Port to listen on.")
    parser.add_argument("--no-browser", action="store_true", help="Skip opening a browser window.")
    parser.add_argument("--windowed", action="store_true", help="Open non-fullscreen window.")
    parser.add_argument("--log-level", default="info")

    # DTAM 송신 설정
    parser.add_argument("--target-ip", default="127.0.0.1", help="DTAM 4001 target IP")
    parser.add_argument("--target-port", type=int, default=17000, help="DTAM 4001 target UDP port")
    parser.add_argument("--my-port", type=int, default=17030, help="Local UDP port")

    # 즉시 등록할 비행계획
    parser.add_argument("--plan", action="append", default=[],
                        help="Flight-plan JSON path (repeatable)")
    parser.add_argument("--clock", choices=[m.value for m in ClockMode],
                        default=ClockMode.EXTERNAL.value)
    parser.add_argument("--autostart", action="store_true",
                        help="Immediately start the service after boot")
    return parser.parse_args()


def _load_plans(service: IntegratedAirMobilityService, paths: List[str]) -> None:
    for path in paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            logging.error("failed to read %s: %s", path, exc)
            continue
        try:
            ids = service.add_plans_from_json(data)
            logging.info("loaded %s → %s", path, ids)
        except Exception as exc:
            logging.error("invalid plan %s: %s", path, exc)


def build_app(args: argparse.Namespace):
    service = IntegratedAirMobilityService(
        target_ip=args.target_ip,
        target_port=int(args.target_port),
        my_port=int(args.my_port),
    )
    _load_plans(service, args.plan)
    service.set_clock_mode(ClockMode(args.clock))
    if args.autostart:
        service.start()
    return create_app(service=service)


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    os.chdir(ROOT)
    requested_port = int(args.port)
    args.port = find_available_tcp_port(args.host, requested_port)
    if args.port != requested_port:
        print(f"[DTAMAirMobility] port {requested_port} is busy; using {args.port}.")

    url = f"http://{args.host}:{args.port}"
    print(f"[DTAMAirMobility] GUI : {url}")
    print(f"[DTAMAirMobility] root: {ROOT}")
    print(f"[DTAMAirMobility] DTAM target: {args.target_ip}:{args.target_port}  my_port={args.my_port}")

    if not args.no_browser:
        threading.Timer(
            1.0,
            lambda: open_browser(url, fullscreen=not args.windowed),
        ).start()

    import uvicorn

    app = build_app(args)
    uvicorn.run(
        app,
        host=args.host,
        port=int(args.port),
        log_level=str(args.log_level).lower(),
    )


if __name__ == "__main__":
    main()
