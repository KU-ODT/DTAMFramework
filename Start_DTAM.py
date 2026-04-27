"""Start DTAM 2-Tier Architecture: Core Server + Operations Console."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

def launch_console_window(name: str, cwd: Path, command: list[str]) -> subprocess.Popen:
    if os.name == "nt":
        command_line = subprocess.list2cmdline(command)
        return subprocess.Popen(
            ["cmd.exe", "/c", f"title {name} & {command_line}"],
            cwd=str(cwd),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    return subprocess.Popen(command, cwd=str(cwd))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start DTAM Core Server and Operations Console.")
    parser.add_argument("--python", default=sys.executable or "python", help="Python executable to use.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python_exe = args.python

    print("[DTAM] Starting 2-Tier Architecture...")

    # 1. Start Core Server (which auto-starts Simulation State)
    server_cmd = [
        python_exe,
        "DSE_main.py",
        "--udp-port", "16000"
    ]
    launch_console_window(
        "DTAM Core Server (Lobby)",
        ROOT / "DTAM_CoreServer",
        server_cmd,
    )

    # 2. Start Operations Console
    console_cmd = [
        python_exe,
        "DOC_main.py",
    ]
    launch_console_window(
        "DTAM Operations Console",
        ROOT / "DTAMOperationsConsole",
        console_cmd,
    )

    print("[DTAM] Successfully launched Core Server and Operations Console in new windows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
