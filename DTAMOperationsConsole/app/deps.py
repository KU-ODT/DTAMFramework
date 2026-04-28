"""FastAPI dependency providers.

라우트가 ``Depends(get_X)`` 으로 의존성을 주입받기 위한 getters.
런타임 상태는 ``app.state`` 에 저장되어 있고, 여기 함수들이 그걸
읽어서 검증된 형태로 라우트에 넘긴다.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request


def get_monitoring_service(request: Request) -> Any:
    """``app.state.monitoring_service`` (``MonitoringService``) 를 반환.

    lifespan 안에서 시작/종료되며, 시작 전에 호출되면 503 으로 응답.
    """
    svc = getattr(request.app.state, "monitoring_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="MonitoringService not ready")
    return svc


__all__ = ["get_monitoring_service"]
