"""Run the DTAM Visualization Manager.

Responsibilities:
 - Provide the AirSim/Unreal connection window (cosysairsim RPC, default 127.0.0.1:41451).
 - Publish data to other modules (0002 Module Status at 1 Hz, 4101 Camera Image at configured Hz).
 - Receive commands from other modules and translate them to AirSim commands
   (1001/1002/1003 setup, 2002 execute/reset, 4001 simSetVehiclePose, 0003 common time).

Examples:

    python VM_main.py
    python VM_main.py --airsim-host 192.168.0.50 --airsim-port 41451
    python VM_main.py --server-ip 127.0.0.1 --ws-port 8096
    python VM_main.py --config data/configs/vm_custom.json --no-browser
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

ROOT = Path(__file__).resolve().parent                   # DTAMFramework/VisualizationModule/
FRAMEWORK_ROOT = ROOT.parent                              # DTAMFramework/
DTAMSDK_ROOT = FRAMEWORK_ROOT / "DTAMSDK"
AIRSIM_PY_ROOT = ROOT / "runtime" / "PythonClient"

# Put the framework root first and import this module with a fully-qualified
# package name.  This avoids collisions with the other top-level ``app``
# packages used by MissionModule, VehicleModule, and OperationModule.
for extra in (str(AIRSIM_PY_ROOT), str(DTAMSDK_ROOT), str(FRAMEWORK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from dtam_client.ports import find_available_tcp_port  # noqa: E402
from VisualizationModule.app.config import DEFAULT_CONFIG_FILE, load_config  # noqa: E402
from VisualizationModule.app.api.server import create_app  # noqa: E402


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
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return
    webbrowser.open(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DTAM Visualization Manager")
    parser.add_argument("--config", default=None)
    parser.add_argument("--gui-host", default=None)
    parser.add_argument("--gui-port", type=int, default=None)
    parser.add_argument("--server-ip", default=None, help="DTAM SimulationState host")
    parser.add_argument("--ws-port", type=int, default=None, help="DTAM SimulationState HTTP/WebSocket port")
    parser.add_argument("--airsim-host", default=None)
    parser.add_argument("--airsim-port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--log-level", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg_path = Path(args.config) if args.config else DEFAULT_CONFIG_FILE
    cfg = load_config(cfg_path)

    # CLI override
    if args.gui_host: cfg.gui_host = args.gui_host
    if args.gui_port is not None: cfg.gui_port = int(args.gui_port)
    if args.server_ip: cfg.dtam.server_ip = args.server_ip
    if args.ws_port is not None: cfg.dtam.server_port = int(args.ws_port)
    if args.airsim_host: cfg.airsim.host = args.airsim_host
    if args.airsim_port is not None: cfg.airsim.port = int(args.airsim_port)
    if args.log_level: cfg.log_level = args.log_level

    logging.basicConfig(
        level=getattr(logging, str(cfg.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    os.chdir(ROOT)

    req_gui = int(cfg.gui_port)
    cfg.gui_port = find_available_tcp_port(cfg.gui_host, req_gui)
    if cfg.gui_port != req_gui:
        print(f"[DTAM VM] GUI port {req_gui} busy; using {cfg.gui_port}.")

    url = f"http://{cfg.gui_host}:{cfg.gui_port}"
    print(f"[DTAM VM] GUI    : {url}")
    print(f"[DTAM VM] AirSim : {cfg.airsim.host}:{cfg.airsim.port}")
    print(f"[DTAM VM] DTAM WS : ws://{cfg.dtam.server_ip}:{cfg.dtam.server_port}/ws/dtam")

    if not args.no_browser:
        threading.Timer(1.2, lambda: open_browser(url)).start()

    import uvicorn
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.gui_host, port=int(cfg.gui_port), log_level=str(cfg.log_level).lower())


if __name__ == "__main__":
    main()


