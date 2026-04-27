"""Run the DTAM Operations Console web app."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRAMEWORK_ROOT = ROOT.parent
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
APP_IMPORT = "backend.app.main:app"

if str(DTAM_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(DTAM_SDK_ROOT))

from dtam_client.ports import find_available_tcp_port  # noqa: E402


def find_fullscreen_browser() -> Path | None:
    candidate_commands = ("msedge", "chrome", "chromium", "brave")
    for command in candidate_commands:
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)

    candidate_paths = (
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LocalAppData", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    )
    for path in candidate_paths:
        if path.is_file():
            return path

    return None


def open_fullscreen_browser(url: str) -> None:
    browser_path = find_fullscreen_browser()
    if browser_path:
        subprocess.Popen(
            [str(browser_path), "--new-window", "--start-fullscreen", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    print("[DTAMOperationsConsole] fullscreen browser launch unavailable; using default browser.")
    webbrowser.open(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DTAM Operations Console")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    parser.add_argument("--target-ip", default="127.0.0.1", help="DTAM server target IP for ICD sends.")
    parser.add_argument("--target-port", type=int, default=17000, help="DTAM server target UDP port for ICD sends.")
    parser.add_argument("--reload", action="store_true", help="Enable Uvicorn auto-reload.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser window.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    os.environ["DTAM_TARGET_IP"] = str(args.target_ip)
    os.environ["DTAM_TARGET_PORT"] = str(args.target_port)

    requested_port = int(args.port)
    args.port = find_available_tcp_port(args.host, requested_port)
    if args.port != requested_port:
        print(f"[DTAMOperationsConsole] port {requested_port} is busy; using {args.port}.")

    url = f"http://{args.host}:{args.port}"
    print(f"[DTAMOperationsConsole] GUI : {url}")
    print(f"[DTAMOperationsConsole] root: {ROOT}")

    if not args.no_browser:
        threading.Timer(1.0, lambda: open_fullscreen_browser(url)).start()

    import uvicorn

    uvicorn.run(
        APP_IMPORT,
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(ROOT)] if args.reload else None,
    )


if __name__ == "__main__":
    main()
