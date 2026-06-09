"""Entry point for the DTAM Simulation State Server.

Hosts the WebSocket data plane, logs ICD traffic to the file DB, drives simulation time, and serves the live monitor UI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add framework and SDK roots to sys.path.
ROOT = Path(__file__).resolve().parent
FRAMEWORK_ROOT = ROOT.parents[1]
DTAMSDK_ROOT = FRAMEWORK_ROOT / "DTAMSDK"
for extra in (str(FRAMEWORK_ROOT), str(DTAMSDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import uvicorn
from IntegrationHub.StateServerModule.app.server import create_app
from IntegrationHub.CoreServerModule.app.model.config import load_config
from IntegrationHub.StateServerModule.app.config import DEFAULT_DB_ROOT


def main():
    parser = argparse.ArgumentParser(description="DTAM Simulation State Server")
    parser.add_argument("--config", default="config.json", help="Core config file (module list)")
    parser.add_argument("--db-root", default=str(DEFAULT_DB_ROOT), help="Database directory")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP/WebSocket bind host")
    parser.add_argument("--port", type=int, default=8096, help="HTTP/WebSocket port (default 8096)")
    args = parser.parse_args()

    config_path = FRAMEWORK_ROOT / "IntegrationHub" / "CoreServerModule" / args.config
    cfg = load_config(config_path)

    app = create_app(cfg, args.db_root)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
