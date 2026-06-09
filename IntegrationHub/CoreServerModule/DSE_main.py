"""Run the DTAM Core Server control plane.

Starts the HTTP REST/GUI service and launches StateServerModule as the data plane.
SimulationState owns the DB under StateServerModule/data/DB; Core only manages control-plane APIs.
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
FRAMEWORK_ROOT = ROOT.parents[1]               # d:/DTAMFramework
DTAMSDK_ROOT = FRAMEWORK_ROOT / "DTAMSDK"

for extra in (str(FRAMEWORK_ROOT), str(DTAMSDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from dtam_client.ports import find_available_tcp_port  # noqa: E402
from IntegrationHub.CoreServerModule.app.config import (  # noqa: E402
    DEFAULT_CONFIG_FILE,
    load_config,
)
from IntegrationHub.CoreServerModule.app.server import create_app  # noqa: E402

RESERVED_DTAM_PORTS = {
    8090,  # Mission Planner GUI
    8096,  # SimulationState HTTP/WS
    8097,  # Visualization GUI
    8100,  # Air Mobility GUI
}


def find_browser() -> Optional[Path]:
    for command in ("msedge", "chrome", "chromium", "brave"):
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)
    for candidate in (
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LocalAppData", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ):
        if candidate.is_file():
            return candidate
    return None


def open_browser(url: str) -> None:
    browser = find_browser()
    if browser:
        subprocess.Popen(
            [str(browser), "--new-window", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    webbrowser.open(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DTAM Core Server (control plane)")
    parser.add_argument("--config", default=None, help="config.json path (default: CoreServerModule/config.json)")
    parser.add_argument("--gui-host", default=None)
    parser.add_argument("--gui-port", type=int, default=None, help="HTTP REST/GUI port (default: 8095)")
    parser.add_argument("--bind-ip", default=None, help="HTTP bind IP (default: 0.0.0.0)")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--log-level", default="info")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg_path = Path(args.config) if args.config else DEFAULT_CONFIG_FILE
    cfg = load_config(cfg_path)

    # CLI override
    if args.bind_ip:
        cfg.server.bind_ip = args.bind_ip
    if args.gui_host:
        cfg.gui_host = args.gui_host
    if args.gui_port is not None:
        cfg.gui_port = int(args.gui_port)

    os.chdir(ROOT)

    # Registration handling
    requested_port = int(cfg.gui_port)
    cfg.gui_port = find_available_tcp_port(
        cfg.gui_host,
        requested_port,
        exclude_ports=RESERVED_DTAM_PORTS,
    )
    if cfg.gui_port != requested_port:
        print(
            f"[DSE] GUI port {requested_port} is busy; using {cfg.gui_port}. "
            "Reserved DTAM ports such as 8096 were skipped."
        )

    url = f"http://{cfg.gui_host}:{cfg.gui_port}"
    print(f"[DSE] GUI    : {url}")
    for m in cfg.modules:
        print(f"[DSE]   [{m.role:<10s}] {m.display_name:<20s}  src='{m.expected_source}'")

    if not args.no_browser:
        threading.Timer(1.2, lambda: open_browser(url)).start()

    import uvicorn

    app = create_app(cfg)
    uvicorn.run(
        app,
        host=cfg.gui_host,
        port=int(cfg.gui_port),
        log_level=str(args.log_level).lower(),
    )


if __name__ == "__main__":
    main()
