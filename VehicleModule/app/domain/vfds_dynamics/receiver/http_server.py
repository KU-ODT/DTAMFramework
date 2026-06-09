"""
VFDS Dynamics Dispatch System — HTTP Server (FastAPI)

POST /api/v1/missions 엔드포인트를 제공하여 Mission JSON을 수신한다.
수신된 데이터는 Dispatcher를 통해 검증 → 분배된다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ..pipeline import MissionPipeline

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path

from ..dispatcher.dispatcher import Dispatcher
from ..dispatcher.models import DispatchResult
from ..dispatcher.sim_time import SimulationClock, SimulationTimeError
from ..compiler.mission_to_ir import mission_to_ir
from ..validator.errors import ValidationReport

from .models import MissionAcceptedResponse, BatchResponse
from .adapter import OperatorPayloadAdapter
from ..status.receiver import dtam_manager, dtam_router, router as status_router, manager, set_dispatcher
from ..status.receiver_mavlink import start_mavlink_receiver, stop_mavlink_receiver

logger = logging.getLogger(__name__)


def _sample_arc_points(block) -> list[dict]:
    """RF_ARC Leg를 위해 원호를 따라 여러 점을 샘플링한다."""
    import math
    points = []
    
    # 필수 데이터 확인 (RF_ARC가 아니거나 정보 부족 시 빈 리스트)
    if not hasattr(block, "leg_type") or block.leg_type.value != "RF_ARC":
        return []
    if not all(hasattr(block, k) for k in ["center_lat", "center_lon", "radius_m", "sweep_rad", "turn_direction"]):
        return []

    # 샘플링 개수
    num_samples = 16
    
    # 시작 각도 계산 (Center -> Start)
    def get_angle(lat, lon, c_lat, c_lon):
        dy = (lat - c_lat) * 111320
        dx = (lon - c_lon) * 111320 * math.cos(math.radians(c_lat))
        return math.atan2(dy, dx)

    start_angle = get_angle(block.start_lat, block.start_lon, block.center_lat, block.center_lon)
    sweep = block.sweep_rad
    direction = 1 if block.turn_direction == "CCW" else -1
    
    # 중간 점 생성 (시작점과 끝점 제외)
    for i in range(1, num_samples):
        ratio = i / num_samples
        angle = start_angle + (sweep * ratio * direction)
        
        # 라디안 -> 위경도 오프셋 변환
        d_lat = (block.radius_m * math.sin(angle)) / 111320
        d_lon = (block.radius_m * math.cos(angle)) / (111320 * math.cos(math.radians(block.center_lat)))
        
        points.append({
            "lat": block.center_lat + d_lat,
            "lon": block.center_lon + d_lon,
            "alt": block.start_alt + (block.end_alt - block.start_alt) * ratio,
            "seq": block.seq,
            "phase": block.phase,
            "kind": "arc_sample"
        })
        
    return points


def _serialize_dispatch_result(result: DispatchResult) -> dict:
    payload = result.to_dict()
    mission = result.mission
    route_points: list[dict] = []

    if mission.enRoute:
        # 1. 시작점 추가
        start = mission.enRoute[0].startLLA
        route_points.append(
            {
                "lat": start.lat,
                "lon": start.lon,
                "alt": start.alt,
                "seq": mission.enRoute[0].seq,
                "phase": mission.enRoute[0].phase.value,
                "kind": "start",
            }
        )

        ir = mission_to_ir(mission, connection_string=result.target.connection_string)
        for block in ir.legs:
            # 2. Leg의 중간 샘플링 (Arc인 경우)
            if hasattr(block, "leg_type") and block.leg_type.value == "RF_ARC":
                samples = _sample_arc_points(block)
                route_points.extend(samples)

            # 3. Leg의 종료점 추가
            route_points.append(
                {
                    "lat": block.end_lat,
                    "lon": block.end_lon,
                    "alt": block.end_alt,
                    "seq": block.seq,
                    "phase": block.phase,
                    "kind": block.leg_type.value,
                }
            )

    payload["spawnPoint"] = route_points[0] if route_points else None
    payload["routePoints"] = route_points
    return payload


def create_app(
    dispatcher: Dispatcher,
    pipeline: "MissionPipeline" = None,
    simulation_clock: SimulationClock | None = None,
) -> FastAPI:
    """
    FastAPI 앱을 생성한다.

    Args:
        dispatcher: 초기화된 Dispatcher 인스턴스
        pipeline: 미션 파이프라인 인스턴스 (종료 시 클린업 용도)
    """

    simulation_clock = simulation_clock or SimulationClock()
    runtime_diag: dict = {
        "missionRxCount": 0,
        "timeRxCount": 0,
        "lastMissionAt": None,
        "lastMissionSource": None,
        "lastMissionPayload": None,
        "lastMissionResponse": None,
        "lastTimeAt": None,
        "lastTimePayload": None,
        "lastTimeSnapshot": None,
    }

    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _payload_preview(payload) -> dict | list | None:
        """Keep the diagnostic payload compact enough for the dashboard."""
        if isinstance(payload, list):
            return [_payload_preview(item) for item in payload[:10]]
        if not isinstance(payload, dict):
            return None

        mission = payload.get("mission") if isinstance(payload.get("mission"), dict) else payload
        return {
            "flightPlanNumber": mission.get("flightPlanNumber")
            or mission.get("flight_plan_number")
            or mission.get("missionId")
            or payload.get("flightPlanNumber"),
            "aircraftId": mission.get("aircraftId")
            or mission.get("aircraft_id")
            or payload.get("aircraftId"),
            "departureVertiportId": mission.get("departureVertiportId")
            or mission.get("departure")
            or payload.get("departureVertiportId"),
            "arrivalVertiportId": mission.get("arrivalVertiportId")
            or mission.get("arrival")
            or payload.get("arrivalVertiportId"),
            "scheduledArmAt": mission.get("scheduledArmAt") or payload.get("scheduledArmAt"),
            "scheduledStartAt": mission.get("scheduledStartAt") or payload.get("scheduledStartAt"),
        }

    def _response_preview(response: JSONResponse) -> dict:
        try:
            body = json.loads(response.body.decode("utf-8"))
        except Exception:
            body = {"raw": response.body.decode("utf-8", errors="replace")}
        if isinstance(body, dict):
            body = dict(body)
            body["httpStatus"] = response.status_code
            return body
        return {"httpStatus": response.status_code, "body": body}

    def _record_mission_rx(source: str, payload, response: JSONResponse) -> None:
        runtime_diag["missionRxCount"] = int(runtime_diag.get("missionRxCount") or 0) + 1
        runtime_diag["lastMissionAt"] = _utc_now_iso()
        runtime_diag["lastMissionSource"] = source
        runtime_diag["lastMissionPayload"] = _payload_preview(payload)
        runtime_diag["lastMissionResponse"] = _response_preview(response)

    def _record_time_rx(payload: dict, snapshot: dict) -> None:
        runtime_diag["timeRxCount"] = int(runtime_diag.get("timeRxCount") or 0) + 1
        runtime_diag["lastTimeAt"] = _utc_now_iso()
        runtime_diag["lastTimePayload"] = dict(payload)
        runtime_diag["lastTimeSnapshot"] = dict(snapshot)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        set_dispatcher(dispatcher)
        logger.info("Mission Dispatch Server starting...")
        await dispatcher.queue.start_worker()

        # MAVLink sysid → aircraftId 매핑 구성
        # 모든 기체는 GCS 포트(14550)로 MAVLink를 전송하며 sysid로 구분된다
        sysid_map = {
            t.mavlink_sysid: t.aircraft_id
            for t in dispatcher.registry.list_all()
            if t.mavlink_sysid > 0
        }
        if sysid_map:
            await start_mavlink_receiver(
                sysid_to_id=sysid_map,
                ws_manager=manager,
                dtam_manager=dtam_manager,
            )
            logger.info("MAVLink receiver started (port 14550) | sysid map: %s", sysid_map)
        else:
            logger.warning("No aircraft with mavlink_sysid configured — MAVLink receiver not started")

        yield
        logger.info("Mission Dispatch Server shutting down...")
        
        # 1. 원격 SITL 클린업 (미션 종료 전 수행)
        if pipeline:
            pipeline.stop_all_active_sitls()
            
        # 2. 워커 종료
        await dispatcher.queue.stop_worker()
        stop_mavlink_receiver()

    app = FastAPI(
        title="VFDS Dynamics Dispatch System",
        description="ICD v1 기반 미션 수신 및 항공기 분배 API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.include_router(status_router)
    app.include_router(dtam_router)
    
    # ────────────── GUI Dashboard ──────────────
    
    # PROJECT_ROOT가 이 파일에 없으므로, 현재 위치에서 상대 경로 구성
    current_dir = Path(__file__).resolve().parent
    static_dir = current_dir / "static"
    
    # static 폴더 마운트
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/")
    async def get_dashboard():
        """HTML 대시보드를 반환한다."""
        return FileResponse(str(static_dir / "index.html"))

    # ────────────── POST /api/v1/missions ──────────────

    @app.post("/api/v1/missions", status_code=202)
    async def receive_missions(request: Request):
        """
        Mission JSON을 수신하여 검증 → 디스패치한다.

        - 단건 (dict) 또는 복수건 (list) 모두 지원
        - 성공: 202 Accepted
        - 검증 실패: 422 Unprocessable Entity
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Invalid JSON payload."},
            )

        # 단건 vs 배치 분기
        if isinstance(body, dict):
            adapted_body = OperatorPayloadAdapter.adapt(body)
            response = _handle_single(dispatcher, adapted_body)
            _record_mission_rx("dashboard-http", body, response)
            return response
        elif isinstance(body, list):
            adapted_body = OperatorPayloadAdapter.adapt_batch(body)
            response = _handle_batch(dispatcher, adapted_body)
            _record_mission_rx("dashboard-http-batch", body, response)
            return response
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Payload must be a JSON object or array.",
                },
            )

    @app.post("/api/v1/time", status_code=202)
    async def update_simulation_time(request: Request):
        """Receive the current simulation clock as HH:MM:SS."""
        try:
            body = await request.json()
            snapshot = await simulation_clock.update(body)
        except SimulationTimeError as e:
            return JSONResponse(
                status_code=422,
                content={"status": "error", "message": str(e)},
            )
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Invalid JSON payload."},
            )
        snapshot_dict = snapshot.to_dict()
        _record_time_rx(body, snapshot_dict)
        return {"status": "ok", **snapshot_dict}

    @app.post("/api/v1/simulation-time", status_code=202)
    async def update_simulation_time_alias(request: Request):
        return await update_simulation_time(request)

    @app.get("/api/v1/time")
    async def get_simulation_time():
        """Return the last received simulation clock."""
        return simulation_clock.snapshot().to_dict()

    @app.get("/api/v1/simulation-time")
    async def get_simulation_time_alias():
        return await get_simulation_time()

    # ────────────── GET /api/v1/missions/status ──────────────

    @app.post("/api/v1/missions/realtime", status_code=202)
    async def receive_realtime_missions(request: Request):
        """External modules can POST live Mission JSON here without using the UI."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Invalid JSON payload."},
            )

        if isinstance(body, dict):
            adapted_body = OperatorPayloadAdapter.adapt(body)
            response = _handle_single(dispatcher, adapted_body)
            _record_mission_rx("realtime-http", body, response)
            return response
        if isinstance(body, list):
            adapted_body = OperatorPayloadAdapter.adapt_batch(body)
            response = _handle_batch(dispatcher, adapted_body)
            _record_mission_rx("realtime-http-batch", body, response)
            return response
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Payload must be a JSON object or array."},
        )

    @app.websocket("/api/v1/missions/ws")
    async def realtime_mission_websocket(websocket: WebSocket):
        """Long-lived realtime Mission JSON ingestion channel for external modules."""
        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {"status": "error", "message": "Invalid JSON payload."}
                    )
                    continue

                if isinstance(body, dict):
                    response = _handle_single(dispatcher, OperatorPayloadAdapter.adapt(body))
                elif isinstance(body, list):
                    response = _handle_batch(dispatcher, OperatorPayloadAdapter.adapt_batch(body))
                else:
                    response = JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "Payload must be a JSON object or array.",
                        },
                    )
                _record_mission_rx("realtime-ws", body, response)
                await websocket.send_json(
                    {
                        "httpStatus": response.status_code,
                        "body": json.loads(response.body.decode("utf-8")),
                    }
                )
        except WebSocketDisconnect:
            logger.info("Realtime mission WebSocket disconnected: %s", websocket.client)

    @app.get("/api/v1/missions/status")
    async def get_all_status():
        """모든 디스패치 결과 상태를 조회한다."""
        results = dispatcher.queue.list_all()
        return {
            "total": len(results),
            "missions": [_serialize_dispatch_result(r) for r in results],
        }

    @app.get("/api/v1/runtime/status")
    async def get_runtime_status():
        """Dashboard-friendly VFDS runtime diagnostics for mission/time ICD flow."""
        results = dispatcher.queue.list_all()
        time_snapshot = simulation_clock.snapshot().to_dict()
        return {
            "status": "ok",
            "registeredAircraft": dispatcher.registry.count,
            "pendingMissions": dispatcher.queue.pending_count,
            "missionStatusTotal": len(results),
            "missions": [_serialize_dispatch_result(r) for r in results[-20:]],
            "time": time_snapshot,
            **runtime_diag,
        }

    @app.delete("/api/v1/missions/{fp_number}")
    async def stop_mission(fp_number: int):
        """특정 미션을 강제로 중단하고 원격 SITL을 종료한다."""
        results = dispatcher.queue.list_all()
        target_result = next((r for r in results if r.flight_plan_number == fp_number), None)
        
        if not target_result:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Mission not found"})
        
        logger.info("Manual stop requested for FP%d", fp_number)
        
        # 1. 원격 SITL 종료 명령 (블로킹 방지를 위해 별도 태스크로 실행 가능하지만 여기선 즉시 실행)
        if pipeline:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, pipeline._uploader.stop_sitl_remote, target_result.target)
            
            # 추적 리스트에서 제거
            if target_result in pipeline._active_results:
                pipeline._active_results.remove(target_result)

        # 2. 상태 변경
        from ..dispatcher.models import DispatchStatus
        target_result.status = DispatchStatus.FAILED
        target_result.error_message = "Stopped by operator"
        
        return {"status": "success", "message": f"Mission FP{fp_number} stopped"}

    # ────────────── GET /api/v1/aircraft ──────────────

    @app.get("/api/v1/aircraft")
    async def list_aircraft():
        """등록된 항공기 목록을 조회한다."""
        targets = dispatcher.registry.list_all()
        return {
            "total": len(targets),
            "aircraft": [
                {
                    "aircraftId": t.aircraft_id,
                    "type": t.type.value,
                    "connectionString": t.connection_string,
                    "mavsdkPort": t.mavsdk_port,
                    "status": t.status.value,
                }
                for t in targets
            ],
        }

    # ────────────── GET /health ──────────────

    @app.get("/health")
    async def health_check():
        time_snapshot = simulation_clock.snapshot().to_dict()
        return {
            "status": "ok",
            "registeredAircraft": dispatcher.registry.count,
            "pendingMissions": dispatcher.queue.pending_count,
            "missionRxCount": runtime_diag.get("missionRxCount", 0),
            "timeRxCount": runtime_diag.get("timeRxCount", 0),
            "lastMissionAt": runtime_diag.get("lastMissionAt"),
            "lastTimeAt": runtime_diag.get("lastTimeAt"),
            "time": time_snapshot.get("time"),
            "seconds": time_snapshot.get("seconds"),
            "timeAvailable": time_snapshot.get("available"),
        }

    @app.get("/api/health")
    async def health_check_api_alias():
        return await health_check()

    @app.get("/api/v1/health")
    async def health_check_api_v1_alias():
        return await health_check()

    return app


def _handle_single(dispatcher: Dispatcher, data: dict) -> JSONResponse:
    """단건 미션 처리"""
    result = dispatcher.process_single(data)

    if isinstance(result, ValidationReport):
        return JSONResponse(
            status_code=422,
            content=result.to_dict(),
        )

    # DispatchResult
    response = MissionAcceptedResponse(
        mission_id=result.mission_id,
        flight_plan_number=result.flight_plan_number,
        aircraft_id=result.aircraft_id,
    )
    return JSONResponse(status_code=202, content=response.to_dict())


def _handle_batch(dispatcher: Dispatcher, data: list) -> JSONResponse:
    """배치 미션 처리"""
    results = dispatcher.process_batch(data)

    batch = BatchResponse(total=len(results))

    for r in results:
        if isinstance(r, ValidationReport):
            batch.rejected += 1
            batch.results.append(r.to_dict())
        elif isinstance(r, DispatchResult):
            batch.accepted += 1
            batch.results.append(r.to_dict())
        else:
            batch.rejected += 1
            batch.results.append({"status": "error", "message": "Unknown error"})

    status_code = 202 if batch.accepted > 0 else 422
    return JSONResponse(status_code=status_code, content=batch.to_dict())
