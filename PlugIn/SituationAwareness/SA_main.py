from __future__ import annotations

import argparse
import os
import webbrowser
from typing import Sequence

import uvicorn


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Situation Awareness plug-in runner")
    parser.add_argument("--host", default=os.environ.get("DTAM_SA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DTAM_SA_PORT", "18210")))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--input-mode",
        choices=("icd", "airsim"),
        default=os.environ.get("DTAM_SA_INPUT_MODE", "icd"),
        help="icd: consume DTAM 4001/4101 via /ws/dtam, airsim: use legacy direct AirSim capture.",
    )
    args = parser.parse_args(argv)

    os.environ["DTAM_SA_INPUT_MODE"] = args.input_mode
    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser and os.environ.get("DTAM_SA_OPEN_BROWSER", "1") != "0":
        webbrowser.open_new(url)

    uvicorn.run("app.server:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

