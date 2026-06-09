"""
VFDS Dynamics Dispatch System — Dispatcher 데이터 모델

Dispatcher가 사용하는 AircraftTarget, DispatchResult 등을 정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import uuid

from ..validator.models import MissionPlan


class AircraftType(str, Enum):
    """항공기 접속 유형"""
    SITL = "SITL"
    HARDWARE = "hardware"


class AircraftStatus(str, Enum):
    """항공기 가용 상태"""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class DispatchStatus(str, Enum):
    """미션 디스패치 진행 상태"""
    QUEUED = "QUEUED"
    SCHEDULED = "SCHEDULED"
    COMPILING = "COMPILING"
    COMPILED = "COMPILED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class SITLLaunchConfig:
    """
    미션 업로드 시 PX4 SITL을 자동 기동하기 위한 옵션 설정.

    기본값은 모두 비활성이며, registry YAML에 명시한 항공기만
    launch template 기반 자동 기동을 수행한다.
    """
    enabled: bool = False
    distro: str = ""
    workdir: str = ""
    prelaunch_template: str = ""
    vfds_command_template: str = ""
    command_template: str = ""
    stop_pattern: str = ""
    process_pattern: str = ""
    ready_command: str = ""
    log_path: str = ""
    startup_delay_sec: float = 5.0
    ready_timeout_sec: int = 20


@dataclass
class AircraftTarget:
    """
    항공기 레지스트리에서 조회된 타겟 정보.

    aircraft_registry.yaml의 개별 항공기 항목에 대응한다.
    """
    aircraft_id: str
    type: AircraftType
    connection_string: str
    mavsdk_port: int
    send_protocol: str
    send_host: str
    send_port: int
    execution_mode: str
    script_deploy_path: str
    status: AircraftStatus
    python_executable: str = "python3"
    ssh_password: str = ""          # SSH 비밀번호 (레지스트리에서 설정)
    # NED→LLA 변환용 HOME 좌표
    home_lat: float = 37.525680
    home_lon: float = 126.922050
    home_alt: float = 0.0
    # 인스턴스 ID (0~4)
    instance_id: int = 0
    # MAVLink system ID — PX4 SITL 인스턴스 번호+1 (0=미사용)
    mavlink_sysid: int = 0
    # Optional PX4 SITL auto-launch settings.
    sitl: SITLLaunchConfig = field(default_factory=SITLLaunchConfig)


@dataclass
class DispatchResult:
    """
    디스패치 결과를 추적하는 객체.

    미션 1건이 특정 항공기에 배정→컴파일→업로드되는 전체 과정을 추적한다.
    """
    aircraft_id: str
    mission: MissionPlan
    target: AircraftTarget
    mission_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: DispatchStatus = DispatchStatus.QUEUED
    compiled_script_path: Optional[Path] = None
    error_message: Optional[str] = None
    scheduled_start_at: Optional[str] = None
    scheduled_arm_at: Optional[str] = None
    schedule_field: Optional[str] = None
    schedule_lead_sec: Optional[float] = None

    @property
    def flight_plan_number(self) -> int:
        return self.mission.flightPlanNumber

    def to_dict(self) -> dict:
        """상태 조회용 직렬화"""
        return {
            "missionId": self.mission_id,
            "flightPlanNumber": self.flight_plan_number,
            "aircraftId": self.aircraft_id,
            "status": self.status.value,
            "compiledScript": str(self.compiled_script_path) if self.compiled_script_path else None,
            "error": self.error_message,
            "scheduledStartAt": self.scheduled_start_at,
            "scheduledArmAt": self.scheduled_arm_at,
            "scheduleField": self.schedule_field,
            "scheduleLeadSec": self.schedule_lead_sec,
        }
