"""Start DTAM step 1: Server Emulator + Operations Console."""

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
PID_FILE = RUNTIME_DIR / "start_dtam_step1.json"


def tcp_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def udp_tcp_pair_available(port: int) -> bool:
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        udp.bind(("0.0.0.0", port))
        tcp.bind(("0.0.0.0", port + 1))
        return True
    except OSError:
        return False
    finally:
        udp.close()
        tcp.close()


def find_udp_tcp_pair(start_port: int) -> int:
    for port in range(start_port, start_port + 300, 2):
        if udp_tcp_pair_available(port):
            return port
    raise RuntimeError(f"No available UDP/TCP pair found near {start_port}.")


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
    parser = argparse.ArgumentParser(description="Start DTAM Server Emulator and Operations Console.")
    parser.add_argument("--python", default=sys.executable or "python", help="Python executable to use.")
    parser.add_argument("--server-ip", default="127.0.0.1", help="Server target IP for Operations Console.")
    parser.add_argument("--server-port", type=int, default=17000, help="Preferred DTAM server UDP port.")
    parser.add_argument("--server-gui-port", type=int, default=8095, help="Preferred Server Emulator GUI port.")
    parser.add_argument("--console-port", type=int, default=8000, help="Preferred Operations Console GUI port.")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser windows.")
    parser.add_argument("--log-level", default="info", help="Server Emulator log level.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    server_port = find_udp_tcp_pair(args.server_port)
    server_gui_port = find_tcp_port("127.0.0.1", args.server_gui_port)
    console_port = find_tcp_port("127.0.0.1", args.console_port)

    browser_arg = [] if not args.no_browser else ["--no-browser"]
    python_exe = args.python

    server_cmd = [
        python_exe,
        "DSE_main.py",
        "--bind-ip",
        "0.0.0.0",
        "--udp-port",
        str(server_port),
        "--gui-host",
        "127.0.0.1",
        "--gui-port",
        str(server_gui_port),
        "--db-root",
        str(ROOT / "DB"),
        "--log-level",
        args.log_level,
        *browser_arg,
    ]
    server_proc = launch_console_window(
        "DTAM Server Emulator",
        ROOT / "DTAM_ServerEmulator",
        server_cmd,
    )

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
        "server": {
            "pid": server_proc.pid,
            "dtam_udp_port": server_port,
            "dtam_tcp_port": server_port + 1,
            "gui_url": f"http://127.0.0.1:{server_gui_port}",
            "command": server_cmd,
        },
        "operations_console": {
            "pid": console_proc.pid,
            "gui_url": f"http://127.0.0.1:{console_port}",
            "target_ip": args.server_ip,
            "target_udp_port": server_port,
            "command": console_cmd,
        },
    }
    PID_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")

    print("[DTAM] Step 1 started.")
    print(f"[DTAM] Server Emulator     : http://127.0.0.1:{server_gui_port}")
    print(f"[DTAM] Server DTAM UDP/TCP : {args.server_ip}:{server_port} / {server_port + 1}")
    print(f"[DTAM] Operations Console  : http://127.0.0.1:{console_port}")
    print(f"[DTAM] Runtime info        : {PID_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
