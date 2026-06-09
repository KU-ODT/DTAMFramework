from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field


class PositionData(BaseModel):
    """LLA 좌표 (NED에서 변환된 결과)"""
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    # NED 원본값도 보존 (디버깅용)
    north: Optional[float] = 0.0
    east: Optional[float] = 0.0
    down: Optional[float] = 0.0


class AttitudeData(BaseModel):
    """자세 데이터 (ICD: radians)"""
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


class ActuatorData(BaseModel):
    """액추에이터 데이터 (ICD §2.3)"""
    tilt_left: float = 0.0
    tilt_right: float = 0.0
    aileron: float = 0.0
    rudder_left: float = 0.0
    rudder_right: float = 0.0


class AircraftStatus(BaseModel):
    """
    비행체 실시간 상태 — WebSocket 브로드캐스트 및 캐시용.

    ICD MSG 4001 기반. NED→LLA 변환 후 이 모델로 정규화된다.
    """
    aircraftId: str
    flightPlanNumber: int = 0
    ts: str = ""
    missionState: str = "WAITING"
    phase: str = "N/A"
    seq: int = 0

    position: PositionData = Field(default_factory=PositionData)
    attitude: AttitudeData = Field(default_factory=AttitudeData)
    actuator: ActuatorData = Field(default_factory=ActuatorData)
    motorRpm: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


class MissionEventPayload(BaseModel):
    """미션 스크립트가 보고하는 이벤트"""
    type: str = "MISSION_EVENT"
    aircraftId: str
    flightPlanNumber: int
    seq: int
    phase: str
    event: str
    ts: str
