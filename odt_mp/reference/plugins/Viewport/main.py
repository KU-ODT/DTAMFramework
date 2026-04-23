from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from reference.plugins.Viewport import create_viewport_dashboard
else:
    from . import create_viewport_dashboard


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the ODT Viewport dashboard.")
    parser.add_argument("--settings-path", type=Path, default=None, help="Path to AirSim settings.json")
    parser.add_argument("--host", default=None, help="AirSim host")
    parser.add_argument("--port", type=int, default=None, help="AirSim port")
    parser.add_argument("--plugin-port", type=int, default=None, help="Viewport plugin port")
    parser.add_argument("--plugin-id", type=int, default=None, help="Optional plugin id")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    app = QApplication(sys.argv)
    window = create_viewport_dashboard(
        settings_path=args.settings_path,
        host=args.host,
        port=args.port,
        plugin_port=args.plugin_port,
        plugin_id=args.plugin_id,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
