"""Start DTAM Operations Console only."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNTIME_DIR = ROOT / ".dtam_runtime"
PID_FILE = RUNTIME_DIR / "start_dtam_operations_console.json"


def tcp_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_tcp_port(host: str, start_port: int) -> int:
    for port in range(start_port, start_port + 100):
        if tcp_port_available(host, port):
            return port
    raise RuntimeError(f"No available TCP port found near {start_port}.")


def launch_console_window(name: str, cwd: Path, command: list[str]) -> subprocess.Popen:
    if os.name == "nt":
        command_line = subprocess.list2cmdline(command)
        return subprocess.Popen(
            ["cmd.exe", "/k", command_line],
            cwd=str(cwd),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    return subprocess.Popen(command, cwd=str(cwd))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start DTAM Operations Console only.")
    parser.add_argument("--python", default=sys.executable or "python", help="Python executable to use.")
    parser.add_argument("--server-ip", default="127.0.0.1", help="Server target IP for Operations Console.")
    parser.add_argument("--server-port", type=int, default=17000, help="DTAM server target UDP port.")
    parser.add_argument("--server-gui-port", type=int, default=8095, help=argparse.SUPPRESS)
    parser.add_argument("--console-port", type=int, default=8000, help="Preferred Operations Console GUI port.")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser windows.")
    parser.add_argument("--log-level", default="info", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    server_port = args.server_port
    console_port = find_tcp_port("127.0.0.1", args.console_port)

    browser_arg = [] if not args.no_browser else ["--no-browser"]
    python_exe = args.python

    console_cmd = [
        python_exe,
        "DOC_main.py",
        "--host",
        "127.0.0.1",
        "--port",
        str(console_port),
        "--target-ip",
        args.server_ip,
        "--target-port",
        str(server_port),
        *browser_arg,
    ]
    console_proc = launch_console_window(
        "DTAM Operations Console",
        ROOT / "DTAMOperationsConsole",
        console_cmd,
    )

    records = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "server": None,
        "operations_console": {
            "pid": console_proc.pid,
            "gui_url": f"http://127.0.0.1:{console_port}",
            "target_ip": args.server_ip,
            "target_udp_port": server_port,
            "command": console_cmd,
        },
    }
    PID_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")

    print("[DTAM] Operations Console started.")
    print("[DTAM] Server Emulator     : not started")
    print(f"[DTAM] Console target UDP  : {args.server_ip}:{server_port}")
    print(f"[DTAM] Operations Console  : http://127.0.0.1:{console_port}")
    print(f"[DTAM] Runtime info        : {PID_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
