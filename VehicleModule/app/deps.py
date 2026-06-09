"""FastAPI dependency providers.

라우트가 ``Depends(get_X)`` 로 의존성을 주입받기 위한 getters. 런타임
상태는 ``app.state`` 에 저장되어 있고, 여기 함수들이 그걸 읽어서
검증된 형태로 라우트에 넘긴다.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from .services.integrated_service import IntegratedAirMobilityService


def get_service(request: Request) -> IntegratedAirMobilityService:
    """``app.state.service`` (``IntegratedAirMobilityService``) 를 반환."""
    svc = getattr(request.app.state, "service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="IntegratedAirMobilityService not ready")
    return svc


__all__ = ["get_service"]
