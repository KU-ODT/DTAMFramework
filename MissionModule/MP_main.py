"""Run the DTAM Mission Planner web app.

Default behavior:
 - Start FastAPI at ``http://127.0.0.1:{PORT}``.
 - Open a browser window unless ``--no-browser`` is specified.
 - Connect to the DTAM SimulationState WebSocket ``/ws/dtam`` using
   ``--target-ip`` and ``--ws-port``.
 - Send ICD 3001/3002/3003 messages over the shared DTAM channel.

Examples:

    python MP_main.py
    python MP_main.py --target-ip 127.0.0.1 --ws-port 8096 --port 8090
    python MP_main.py --host 0.0.0.0 --port 8090 --no-browser

The server forwards 3001 messages to VehicleModule to create flight data.
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
FRAMEWORK_ROOT = ROOT.parent                   # d:/DTAMFramework
DTAMSDK_ROOT = FRAMEWORK_ROOT / "DTAMSDK"    # dtam_client location

# MissionModule package import + bundled DTAMSDK import path.
for extra in (str(FRAMEWORK_ROOT), str(DTAMSDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from dtam_client.ports import find_available_tcp_port  # noqa: E402
from MissionModule.app.server import create_app, settings  # noqa: E402


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

    # DTAM communication (WebSocket /ws/dtam)
    parser.add_argument("--target-ip", default=None,
                        help="DTAM SimulationState server host (default from env or 127.0.0.1)")
    parser.add_argument("--ws-port", type=int, default=None,
                        help="DTAM SimulationState WebSocket/HTTP port (default 8096)")
    parser.add_argument("--server-http-host", default=None,
                        help="DTAM CoreServer HTTP host for central DB lookup.")
    parser.add_argument("--server-http-port", type=int, default=None,
                        help="DTAM CoreServer HTTP port for central DB lookup.")
    return parser.parse_args()


def _apply_dtam_overrides(args: argparse.Namespace) -> None:
    """Apply DTAM endpoint overrides from CLI options."""
    if args.target_ip:
        settings["dtam_target_ip"] = str(args.target_ip)
    if args.ws_port is not None:
        settings["dtam_ws_port"] = int(args.ws_port)
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
    ws_port = settings.get("dtam_ws_port", 8096)
    print(f"[DTAM MP] GUI    : {url}")
    print(f"[DTAM MP] root   : {ROOT}")
    print(f"[DTAM MP] CoreServer DB API: http://{settings['server_http_host']}:{settings['server_http_port']}")
    print(f"[DTAM MP] DTAM   : ws://{settings['dtam_target_ip']}:{ws_port}/ws/dtam")

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
