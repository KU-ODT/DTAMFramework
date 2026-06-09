from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18175


def _prepare_import_path() -> None:
    root_text = str(ROOT)
    framework_text = str(ROOT.parents[1])
    for item in (root_text, framework_text):
        if item not in sys.path:
            sys.path.insert(0, item)
    os.environ["PYTHONPATH"] = root_text + os.pathsep + os.environ.get("PYTHONPATH", "")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DTAM Test Stream plug-in runner")
    parser.add_argument("--host", default=os.environ.get("DTAM_TEST_STREAM_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DTAM_TEST_STREAM_PORT", DEFAULT_PORT)))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    _prepare_import_path()
    os.chdir(ROOT)

    import uvicorn

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser and os.environ.get("DTAM_TEST_STREAM_OPEN_BROWSER", "1") != "0":
        webbrowser.open_new(url)

    uvicorn.run(
        "app.server:app",
        host=args.host,
        port=int(args.port),
        reload=bool(args.reload),
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
