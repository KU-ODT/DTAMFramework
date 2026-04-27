"""DTAM Simulation State Server 진입점.

새로운 아키텍처에서 이 서버는 시뮬레이션 세션을 전담하는 "인게임 서버"입니다.
- UDP/TCP 리스너 및 WebSocket 통신 허브 가동
- 1002 명령 수신 시 자체 엔진 기동 (0003 주기적 송신)
- 모든 통신 트래픽을 로컬 SQLite DB에 기록
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프레임워크 최상위 및 SDK 경로를 path에 추가
ROOT = Path(__file__).resolve().parent
FRAMEWORK_ROOT = ROOT.parent
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
for extra in (str(FRAMEWORK_ROOT), str(DTAM_SDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import uvicorn
from DTAM_SimulationState.app.server import create_app
from DTAM_CoreServer.app.model.config import load_config
from DTAM_SimulationState.app.config import DEFAULT_DB_ROOT

def main():
    parser = argparse.ArgumentParser(description="DTAM Simulation State Engine")
    parser.add_argument("--config", default="config.json", help="Core config file (for module list)")
    parser.add_argument("--db-root", default=str(DEFAULT_DB_ROOT), help="Database directory")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP Server Host")
    parser.add_argument("--port", type=int, default=8096, help="HTTP Server Port")
    parser.add_argument("--udp-port", type=int, default=17000, help="DTAM logical UDP port")
    args = parser.parse_args()

    # Load configuration from DTAM_CoreServer/config.json
    # We reuse the core config for module definitions, but we could split it later
    config_path = FRAMEWORK_ROOT / "DTAM_CoreServer" / args.config
    cfg = load_config(config_path)
    
    # Override server port to ensure it captures module traffic
    cfg.server.udp_port = args.udp_port

    app = create_app(cfg, args.db_root)
    
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
