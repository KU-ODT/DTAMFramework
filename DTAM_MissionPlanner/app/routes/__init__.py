"""DTAM Mission Planner FastAPI 라우트 모듈.

각 파일은 단일 도메인의 APIRouter 를 정의한다. 런타임 의존성
(mission_service, route_planner, dem_provider, mbtiles, settings) 은
``app.deps`` 의 ``Depends(get_X)`` 로 주입받는다 — 라우트 시그니처에
무엇을 의존하는지 명시되고, ``app.state`` 컨테이너 (``app.state``
모듈) 가 단일 소스. ``global`` 키워드 사용 없음.

도메인 파이프라인이 필요한 helpers (``_route_payload_response``,
``_sample_ground_m``, ``_server_get_json`` 등) 는 ``app.server`` 모듈
함수로 남아 있고, 그쪽에서도 동일한 ``state`` 컨테이너를 읽는다.
"""
