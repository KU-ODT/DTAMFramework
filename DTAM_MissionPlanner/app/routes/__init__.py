"""DTAM Mission Planner FastAPI 라우트 모듈.

각 파일은 단일 도메인의 APIRouter 를 정의하고, 공유 상태(mbtiles, route_planner,
dem_provider, mission_service, settings) 와 helper 들은 ``..server`` 모듈에서
가져온다 (deferred binding — 실행 시점에 ``server.X`` 로 접근).
"""
