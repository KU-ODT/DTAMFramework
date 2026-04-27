"""Run the DTAM Server Emulator.

기본 동작:
 - UDP/TCP 리스너가 17000/17001 에서 모든 ICD 메시지를 수신
 - sequence_diagram.json 규칙에 따라 DB 저장 + 타 모듈로 포워딩
 - 0003 Common Time Info 를 1 Hz 로 vehicle / visual 에 주기 전송
 - FastAPI 기반 GUI 를 ``http://127.0.0.1:{gui_port}`` 로 제공

사용 예::

    python DSE_main.py
    python DSE_main.py --udp-port 17000 --gui-port 8095
    python DSE_main.py --db-root D:/DTAMFramework/DB
    python DSE_main.py --config custom_config.json --no-browser
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
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"

for extra in (str(FRAMEWORK_ROOT), str(DTAM_SDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from dtam_client._ports import find_available_tcp_port, find_available_udp_tcp_pair  # noqa: E402
from DTAM_CoreServer.app.config import (  # noqa: E402
    DEFAULT_CONFIG_FILE,
    DEFAULT_DB_ROOT,
    load_config,
)
from DTAM_CoreServer.app.server import create_app  # noqa: E402


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
    parser = argparse.ArgumentParser(description="DTAM Server Emulator")
    parser.add_argument("--config", default=None, help="config.json 경로 (기본: DTAM_CoreServer/config.json)")
    parser.add_argument("--gui-host", default=None)
    parser.add_argument("--gui-port", type=int, default=None)
    parser.add_argument("--udp-port", type=int, default=None, help="서버 UDP base (TCP = +1)")
    parser.add_argument("--bind-ip", default=None, help="DTAM 수신 bind IP (0.0.0.0 권장)")
    parser.add_argument("--db-root", default=None, help=f"DB 루트 폴더 (기본: {DEFAULT_DB_ROOT})")
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
    if args.udp_port is not None:
        cfg.server.udp_port = int(args.udp_port)
    if args.gui_host:
        cfg.gui_host = args.gui_host
    if args.gui_port is not None:
        cfg.gui_port = int(args.gui_port)
    if args.db_root:
        cfg.db_root = Path(args.db_root)

    cfg.db_root.mkdir(parents=True, exist_ok=True)

    os.chdir(ROOT)

    requested_udp_port = int(cfg.server.udp_port)
    requested_tcp_port = int(cfg.server.tcp_port)
    cfg.server.udp_port, selected_tcp_port = find_available_udp_tcp_pair(
        cfg.server.bind_ip,
        requested_udp_port,
        preferred_tcp_port=requested_tcp_port,
    )
    if cfg.server.udp_port != requested_udp_port or selected_tcp_port != requested_tcp_port:
        print(
            f"[DSE] server ports {requested_udp_port}/{requested_tcp_port} are busy; "
            f"using {cfg.server.udp_port}/{cfg.server.tcp_port}."
        )

    requested_port = int(cfg.gui_port)
    cfg.gui_port = find_available_tcp_port(cfg.gui_host, requested_port)
    if cfg.gui_port != requested_port:
        print(f"[DSE] GUI port {requested_port} is busy; using {cfg.gui_port}.")

    url = f"http://{cfg.gui_host}:{cfg.gui_port}"
    print(f"[DSE] GUI    : {url}")
    print(f"[DSE] Server : {cfg.server.bind_ip}:{cfg.server.udp_port} (TCP {cfg.server.tcp_port})")
    print(f"[DSE] DB root: {cfg.db_root}")
    for m in cfg.modules:
        print(f"[DSE]   [{m.role:<10s}] {m.display_name:<20s}  {m.ip}:{m.udp_port} (TCP {m.resolved_tcp_port})  src='{m.expected_source}'")

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
