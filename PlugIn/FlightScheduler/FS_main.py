from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18174


def _prepare_import_path() -> None:
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    os.environ["PYTHONPATH"] = root_text + os.pathsep + os.environ.get("PYTHONPATH", "")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UAM Flight Scheduler runner")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Frontend/API port. Default: {DEFAULT_PORT}")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for development.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser after startup.")
    args = parser.parse_args(argv)

    _prepare_import_path()
    os.chdir(ROOT)

    import uvicorn

    if not args.no_browser and os.environ.get("UATM_OPEN_BROWSER", "1") != "0":
        webbrowser.open_new(f"http://{args.host}:{args.port}/")

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=int(args.port),
        reload=bool(args.reload),
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
