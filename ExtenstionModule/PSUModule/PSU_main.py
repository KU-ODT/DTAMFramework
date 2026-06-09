"""Run the PSU Monitoring SW web app."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent
EXTENSION_ROOT = ROOT.parent
FRAMEWORK_ROOT = EXTENSION_ROOT.parent
DTAMSDK_ROOT = FRAMEWORK_ROOT / "DTAMSDK"

for extra in (str(FRAMEWORK_ROOT), str(DTAMSDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

try:
    from dtam_client.ports import find_available_tcp_port  # type: ignore
except Exception:  # pragma: no cover - standalone fallback
    import socket

    def find_available_tcp_port(host: str, requested_port: int) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, int(requested_port)))
                return int(requested_port)
            except OSError:
                sock.bind((host, 0))
                return int(sock.getsockname()[1])

from ExtenstionModule.PSUModule.app.server import create_app  # noqa: E402


def find_browser() -> Optional[Path]:
    for command in ("msedge", "chrome", "chromium", "brave"):
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)

    candidates = (
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LocalAppData", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def open_browser(url: str, *, fullscreen: bool = False) -> None:
    browser = find_browser()
    if browser:
        args = [str(browser), "--new-window"]
        if fullscreen:
            args.append("--start-fullscreen")
        args.append(url)
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    webbrowser.open(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DTAM PSU Monitoring SW")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind.")
    parser.add_argument("--port", type=int, default=8120, help="GUI/API port.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser automatically.")
    parser.add_argument("--fullscreen", action="store_true", help="Open browser fullscreen.")
    parser.add_argument("--log-level", default="info", help="Uvicorn log level.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.chdir(ROOT)

    requested_port = int(args.port)
    args.port = find_available_tcp_port(args.host, requested_port)
    if args.port != requested_port:
        print(f"[PSU] port {requested_port} is busy; using {args.port}.")

    url = f"http://{args.host}:{args.port}"
    print(f"[PSU] GUI  : {url}")
    print(f"[PSU] root : {ROOT}")

    if not args.no_browser:
        threading.Timer(1.0, lambda: open_browser(url, fullscreen=args.fullscreen)).start()

    import uvicorn

    app = create_app()
    uvicorn.run(app, host=args.host, port=int(args.port), log_level=str(args.log_level).lower())


if __name__ == "__main__":
    main()
