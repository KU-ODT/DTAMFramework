"""Start the odt_Integration GUI backed by the sibling DTAM_SDK."""
from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SDK_ROOT = ROOT.parent / "DTAM_SDK"

if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from dtam_client._ports import find_available_tcp_port  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="odt_Integration GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    os.environ["DTAM_CONFIG"] = str(cfg_path)

    if not SDK_ROOT.is_dir():
        raise RuntimeError(f"DTAM_SDK folder not found: {SDK_ROOT}")

    requested_port = int(args.port)
    args.port = find_available_tcp_port(args.host, requested_port)
    if args.port != requested_port:
        print(f"[odt_Integration] port {requested_port} is busy; using {args.port}.")

    url = f"http://{args.host}:{args.port}"
    print(f"[odt_Integration] GUI : {url}")
    print(f"[odt_Integration] SDK : {SDK_ROOT}")
    print(f"[odt_Integration] config: {cfg_path}")

    if not args.no_browser and not args.reload:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
