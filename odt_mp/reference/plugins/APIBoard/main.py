from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[3]
    reference_root = repo_root / "reference"
    for path in (repo_root, reference_root):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    from reference.plugins.APIBoard import create_api_board_dashboard
else:
    from . import create_api_board_dashboard


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the ODT API Board dashboard.")
    parser.add_argument("--plugin-name", default=None, help="Dashboard title override")
    parser.add_argument("--plugin-port", type=int, default=None, help="Optional plugin port")
    parser.add_argument("--plugin-id", type=int, default=None, help="Optional plugin id")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    app = QApplication(sys.argv)
    window = create_api_board_dashboard(
        plugin_name=args.plugin_name,
        plugin_port=args.plugin_port,
        plugin_id=args.plugin_id,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
