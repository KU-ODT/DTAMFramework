import logging
from typing import List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..dispatcher.dispatcher import Dispatcher

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .cache import status_cache
from .icd4001 import dumps_vehicle_status_4001
from .models import AircraftStatus, MissionEventPayload
from .receiver_mavlink import get_mavlink_debug_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")
dtam_router = APIRouter()

_global_dispatcher: Optional["Dispatcher"] = None


def set_dispatcher(dispatcher):
    global _global_dispatcher
    _global_dispatcher = dispatcher


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error("WebSocket broadcast error: %s", e)
                self.disconnect(connection)


manager = ConnectionManager()


class DtamConnectionManager(ConnectionManager):
    async def broadcast_status(self, status: AircraftStatus):
        await self.broadcast(dumps_vehicle_status_4001([status]))

    async def send_snapshot(self, websocket: WebSocket, statuses: list[AircraftStatus]):
        if not statuses:
            return
        await websocket.send_text(dumps_vehicle_status_4001(statuses))


dtam_manager = DtamConnectionManager()


async def broadcast_status(status: AircraftStatus):
    await manager.broadcast(status.model_dump_json())
    await dtam_manager.broadcast_status(status)


@router.post("/telemetry")
async def receive_telemetry(payload: AircraftStatus):
    """
    미션 스크립트가 로컬 또는 원격에서 전송하는 실시간 텔레메트리 데이터를 수신한다.
    """
    status_cache.update_status(payload.aircraftId, payload)
    await broadcast_status(payload)
    return {"status": "ok"}


@router.get("/telemetry")
async def get_telemetry_snapshot():
    """현재 캐시된 기체별 텔레메트리 스냅샷을 반환한다."""
    aircraft = status_cache.get_all()
    return {
        "total": len(aircraft),
        "aircraft": [status.model_dump() for status in aircraft.values()],
    }


@router.get("/debug/mavlink")
async def get_mavlink_debug():
    """현재 MAVLink 수신기 상태를 반환한다."""
    return get_mavlink_debug_snapshot()


@router.post("/events")
async def receive_event(payload: MissionEventPayload):
    """
    미션 스크립트가 보고하는 진행 상태 이벤트를 수신한다.
    """
    logger.info(
        "[EVENT] %s (FP%s) Phase:%s Seq:%s -> %s",
        payload.aircraftId,
        payload.flightPlanNumber,
        payload.phase,
        payload.seq,
        payload.event,
    )

    status = status_cache.get_status(payload.aircraftId)
    if status is not None:
        status.missionState = payload.event
        status.phase = payload.phase
        status.seq = payload.seq
        status.ts = payload.ts
        status.flightPlanNumber = payload.flightPlanNumber
        status_cache.update_status(payload.aircraftId, status)
        await broadcast_status(status)
    else:
        status = AircraftStatus(aircraftId=payload.aircraftId)
        status.missionState = payload.event
        status.phase = payload.phase
        status.seq = payload.seq
        status.ts = payload.ts
        status.flightPlanNumber = payload.flightPlanNumber
        status_cache.update_status(payload.aircraftId, status)
        await broadcast_status(status)

    if _global_dispatcher:
        from ..dispatcher.models import DispatchStatus

        result = _global_dispatcher.queue.get_status_by_fpn(payload.flightPlanNumber)
        if result:
            try:
                if payload.event in ["EXECUTING", "COMPLETED", "FAILED"]:
                    result.status = DispatchStatus(payload.event)
            except ValueError:
                pass

    return {"status": "ok"}


@router.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    client = getattr(websocket, "client", None)
    await manager.connect(websocket)
    logger.info("WebSocket connected: %s", client)

    try:
        for status in status_cache.get_all().values():
            await websocket.send_text(status.model_dump_json())

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnected: %s", client)


@dtam_router.websocket("/ws/dtam")
async def dtam_websocket_endpoint(websocket: WebSocket):
    client = getattr(websocket, "client", None)
    await dtam_manager.connect(websocket)
    logger.info("DTAM WebSocket connected: %s", client)

    try:
        await dtam_manager.send_snapshot(websocket, list(status_cache.get_all().values()))

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dtam_manager.disconnect(websocket)
        logger.info("DTAM WebSocket disconnected: %s", client)
