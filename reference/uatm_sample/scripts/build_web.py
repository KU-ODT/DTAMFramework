from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

IGNORE_PATTERNS = ("__pycache__", "*.pyc", "*.pyo", ".DS_Store")


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Missing source: {src}")
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))


def write_text(path: Path, text: str, newline: str = "\n") -> None:
    with path.open("w", encoding="utf-8", newline=newline) as handle:
        handle.write(text)


def create_run_scripts(out_dir: Path, host: str, port: int) -> None:
    bat_lines = [
        "@echo off",
        "setlocal",
        "cd /d %~dp0",
        f"set UATM_SERVER_HOST={host}",
        f"set UATM_SERVER_PORT={port}",
        "python app.py",
        "endlocal",
        "",
    ]
    write_text(out_dir / "run_web.bat", "\n".join(bat_lines), newline="\r\n")

    sh_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'cd "$SCRIPT_DIR"',
        f'export UATM_SERVER_HOST="{host}"',
        f"export UATM_SERVER_PORT={port}",
        "python3 app.py",
        "",
    ]
    write_text(out_dir / "run_web.sh", "\n".join(sh_lines))


def create_readme(out_dir: Path, host: str, port: int) -> None:
    content = f"""UATM Web Deployment
====================

1) Run the server
   - Windows: run `run_web.bat`
   - macOS/Linux: run `./run_web.sh`

2) Open the browser
   http://{host}:{port}

Notes
-----
- This package runs a local web server. Opening index.html directly will not start the simulation.
- If you need a different host or port, edit run_web.bat/run_web.sh or set
  UATM_SERVER_HOST and UATM_SERVER_PORT before running.
"""
    write_text(out_dir / "README_WEB.txt", content)


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build a local web deployment bundle.")
    parser.add_argument(
        "--out",
        default=str(root_dir / "dist_web"),
        help="Output directory (default: dist_web in repo root)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Server host for run scripts.")
    parser.add_argument("--port", type=int, default=8000, help="Server port for run scripts.")
    args = parser.parse_args()

    out_dir = Path(args.out).resolve()
    if out_dir.exists():
        suffix = time.strftime("%Y%m%d_%H%M%S")
        out_dir = out_dir.with_name(f"{out_dir.name}_{suffix}")

    out_dir.mkdir(parents=True, exist_ok=False)

    copy_tree(root_dir / "app", out_dir / "app")
    copy_tree(root_dir / "resources", out_dir / "resources")
    copy_tree(root_dir / "data", out_dir / "data")
    shutil.copy2(root_dir / "app.py", out_dir / "app.py")

    create_run_scripts(out_dir, args.host, args.port)
    create_readme(out_dir, args.host, args.port)

    print(f"Web bundle created at: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
