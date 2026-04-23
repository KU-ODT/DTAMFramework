import argparse

from app.fastapi_server import main as api_main
from app.frontend_server import main as frontend_main
from app.tile_fastapi_server import main as tile_main
from scripts.run_all import main as run_all_main


def main() -> int:
    parser = argparse.ArgumentParser(description="TrafficS service runner")
    parser.add_argument(
        "service",
        nargs="?",
        choices=("api", "tiles", "frontend", "all"),
        default="all",
        help="Service to run (api, tiles, frontend, all).",
    )
    args = parser.parse_args()
    if args.service == "all":
        return run_all_main()
    if args.service == "tiles":
        return tile_main()
    if args.service == "frontend":
        return frontend_main()
    return api_main()


if __name__ == "__main__":
    raise SystemExit(main())
