"""Mission Planner 런타임 상태 컨테이너.

``server.create_app().lifespan`` 이 ``state.X = ...`` 으로 채우고,
서버의 module-level helpers (route 빌딩, DEM 샘플링 등) 와
``app.deps`` 의 ``Depends`` getters 가 동일 ``state`` 를 읽는다.
attribute 변이만 사용하므로 ``global`` 키워드는 어디에서도 필요 없다.

테스트에서 격리가 필요하면 ``state.reset()`` 으로 초기화 가능.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .config import DTAM_TARGET_IP, DTAM_WS_PORT


@dataclass
class ServerState:
    mbtiles: Any = None              # MBTiles | None
    route_planner: Any = None        # RoutePlanner | None
    dem_provider: Any = None         # DemProvider | None
    mission_service: Any = None      # MissionService | None
    settings: Dict[str, Any] = field(default_factory=dict)

    def reset(self) -> None:
        self.mbtiles = None
        self.route_planner = None
        self.dem_provider = None
        self.mission_service = None
        self.settings = _default_settings()


def _default_settings() -> Dict[str, Any]:
    import os
    return {
        "dtam_target_ip": DTAM_TARGET_IP,
        "dtam_ws_port": DTAM_WS_PORT,
        "server_http_host": os.getenv("DTAM_MP_SERVER_HTTP_HOST", DTAM_TARGET_IP),
        "server_http_port": int(os.getenv("DTAM_MP_SERVER_HTTP_PORT", "8095")),
        "default_speed_mps": 30.0,
        "default_altitude_m": 300.0,
        "auto_plan_max_aircraft": int(os.getenv("DTAM_MP_AUTO_PLAN_MAX_AIRCRAFT", "8")),
    }


# 모듈 레벨 싱글턴 — attribute mutation 만 사용 (global 키워드 불필요).
state = ServerState(settings=_default_settings())


__all__ = ["ServerState", "state"]
