"""Run the DTAM Core Server (control plane).

기본 동작:
 - HTTP REST control plane 을 ``http://127.0.0.1:{gui_port}`` 로 호스팅
   (ICD 문서, 시퀀스 다이어그램 메타, 모듈 프로세스 start/stop)
 - 부팅 시 자식 프로세스로 ``DTAM_SimulationState`` (port 8096) 자동 기동
   ─ 데이터 plane (WebSocket ``/ws/dtam``, 트래픽 forwarding, DB, 라이브 모니터)

사용 예::

    python DSE_main.py
    python DSE_main.py --gui-port 8095
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

from dtam_client.ports import find_available_tcp_port  # noqa: E402
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
    parser = argparse.ArgumentParser(description="DTAM Core Server (control plane)")
    parser.add_argument("--config", default=None, help="config.json 경로 (기본: DTAM_CoreServer/config.json)")
    parser.add_argument("--gui-host", default=None)
    parser.add_argument("--gui-port", type=int, default=None, help="HTTP REST/GUI 포트 (기본 8095)")
    parser.add_argument("--bind-ip", default=None, help="HTTP bind IP (0.0.0.0 권장)")
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
    if args.gui_host:
        cfg.gui_host = args.gui_host
    if args.gui_port is not None:
        cfg.gui_port = int(args.gui_port)
    if args.db_root:
        cfg.db_root = Path(args.db_root)

    cfg.db_root.mkdir(parents=True, exist_ok=True)

    os.chdir(ROOT)

    # Core 는 control plane (HTTP REST) 만 호스팅. 데이터 통신은 SimulationState (8096 WS) 가 담당.
    requested_port = int(cfg.gui_port)
    cfg.gui_port = find_available_tcp_port(cfg.gui_host, requested_port)
    if cfg.gui_port != requested_port:
        print(f"[DSE] GUI port {requested_port} is busy; using {cfg.gui_port}.")

    url = f"http://{cfg.gui_host}:{cfg.gui_port}"
    print(f"[DSE] GUI    : {url}")
    print(f"[DSE] DB root: {cfg.db_root}")
    for m in cfg.modules:
        print(f"[DSE]   [{m.role:<10s}] {m.display_name:<20s}  {m.ip}  src='{m.expected_source}'")

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
