"""역할별 ``DtamModule`` base class.

각 role 이 ``FORWARD_RULES`` 상 받게 돼있는 모든 mid 에 대해 빈 핸들러
stub 을 미리 ``@on_receive`` 로 데코레이트해둔 클래스. 모듈 작성자는
필요한 메서드만 override 하면 됨 — 처리하지 않는 mid 는 베이스의 빈
stub 이 그대로 사용돼 silent drop 으로 동작.

사용 예 (Mission 역할 모듈)::

    from dtam_client import MissionModule

    class MyMission(MissionModule):
        def __init__(self):
            super().__init__(server_url="ws://127.0.0.1:8096/ws/dtam")

        # 2001 만 처리. 2002 는 베이스의 빈 stub 사용.
        def on_flight_plan_request(self, msg):
            ...

검증: 각 base class 가 ``FORWARD_RULES`` 의 변경에 표류하지 않도록,
import 시점에 ``subscriptions_for(role)`` 와 데코레이터 mid 가 일치하는지
확인한다 (불일치 시 ``AssertionError``).
"""
from __future__ import annotations

from typing import Any, Type

from .identity import Role
from .module import DECORATOR_TAG, DtamModule, on_receive
from .policy import subscriptions_for


def _validate_role_base(cls: Type[DtamModule]) -> Type[DtamModule]:
    """``cls.role`` 의 FORWARD_RULES 와 ``@on_receive`` 데코레이터 mid 가 일치하는지 검증."""
    role = cls.role
    if role is None:
        raise AssertionError(f"{cls.__name__}: role 클래스 속성이 없음")
    expected_mids = set(subscriptions_for(role))
    decorated_mids: set = set()
    for name, attr in vars(cls).items():
        mid = getattr(attr, DECORATOR_TAG, None)
        if mid:
            decorated_mids.add(mid)
    missing = expected_mids - decorated_mids
    extra = decorated_mids - expected_mids
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing stubs for {sorted(missing)}")
        if extra:
            parts.append(f"unexpected stubs for {sorted(extra)} (not in FORWARD_RULES)")
        raise AssertionError(
            f"{cls.__name__}: drift between FORWARD_RULES and @on_receive — "
            + "; ".join(parts)
        )
    return cls


# ── 역할별 base class ────────────────────────────────────────

@_validate_role_base
class MissionModule(DtamModule):
    """Mission Planner 역할의 base 클래스.

    FORWARD_RULES: 2001 (Flight Plan Request), 2002 (DTAM Execute),
    3003 (Tactical Separation — PSU 발행분 수신, plan 정합성 추적).
    """
    role = Role.MISSION

    @on_receive("2001")
    def on_flight_plan_request(self, msg: Any) -> None:
        """MSG 2001 — Operations Console 의 비행계획 요청. Override to handle."""

    @on_receive("2002")
    def on_dtam_execute(self, msg: Any) -> None:
        """MSG 2002 — DTAM 실행 명령. Override to handle."""

    @on_receive("3003")
    def on_tactical_separation(self, msg: Any) -> None:
        """MSG 3003 — PSU 발 전술 분리 명령 (수신 전용).

        PSU 가 즉시 개입(directTo/land 등)했음을 Mission 이 인지하여
        보유 plan 의 정합성(superseded 마킹 등)을 유지. Override to handle.
        """


@_validate_role_base
class VehicleModule(DtamModule):
    """Air Mobility 역할의 base 클래스.

    FORWARD_RULES: 0003, 1002, 2002, 3001, 3002, 3003, 4103, 5001, 5004.
    """
    role = Role.VEHICLE

    @on_receive("0003")
    def on_common_time_info(self, msg: Any) -> None:
        """MSG 0003 — 공통 시간 정보 (1Hz). Override to handle."""

    @on_receive("1002")
    def on_simulation_setup(self, msg: Any) -> None:
        """MSG 1002 — 시뮬레이션 통제 (play/pause/reset). Override to handle."""

    @on_receive("2002")
    def on_dtam_execute(self, msg: Any) -> None:
        """MSG 2002 — DTAM 실행 명령. Override to handle."""

    @on_receive("3001")
    def on_scheduled_flight(self, msg: Any) -> None:
        """MSG 3001 — 비행계획 등록/갱신. Override to handle."""

    @on_receive("3002")
    def on_strategic_separation(self, msg: Any) -> None:
        """MSG 3002 — 전략적 분리 명령. Override to handle."""

    @on_receive("3003")
    def on_tactical_separation(self, msg: Any) -> None:
        """MSG 3003 — 전술적 분리 명령. Override to handle."""

    @on_receive("4103")
    def on_vehicle_collision_event(self, msg: Any) -> None:
        """MSG 4103 — 비행체 충돌 이벤트. Override to handle."""

    @on_receive("5001")
    def on_operator_control_input(self, msg: Any) -> None:
        """MSG 5001 — 수동 조종 입력. Override to handle."""

    @on_receive("5004")
    def on_wind_effect_data(self, msg: Any) -> None:
        """MSG 5004 — 데모 날씨 기체별 바람 영향 (dynamics 보정). Override to handle."""


@_validate_role_base
class MonitoringModule(DtamModule):
    """Operations Console 역할의 base 클래스.

    FORWARD_RULES: 0001, 0002, 2002, 4001, 4002, 4101, 4102, 4103.
    """
    role = Role.MONITORING

    @on_receive("0001")
    def on_module_setting_info(self, msg: Any) -> None:
        """MSG 0001 — 다른 모듈의 식별 정보 보고. Override to handle."""

    @on_receive("0002")
    def on_module_status(self, msg: Any) -> None:
        """MSG 0002 — 다른 모듈의 heartbeat. Override to handle."""

    @on_receive("2002")
    def on_dtam_execute(self, msg: Any) -> None:
        """MSG 2002 — DTAM 실행 명령 (자기 자신이 보낸 것의 echo). Override to handle."""

    @on_receive("4001")
    def on_vehicle_status(self, msg: Any) -> None:
        """MSG 4001 — 비행체 10Hz 상태. Override to handle."""

    @on_receive("4002")
    def on_vehicle_warning_event(self, msg: Any) -> None:
        """MSG 4002 — 비행체 경고 이벤트 (이상 감지). Override to handle."""

    @on_receive("4101")
    def on_camera_image(self, msg: Any) -> None:
        """MSG 4101 — 카메라 이미지 프레임. Override to handle."""
    @on_receive("4102")
    def on_camera_stream_descriptor(self, msg: Any) -> None:
        """MSG 4102 ? Camera Stream Descriptor. Override to handle."""

    @on_receive("4103")
    def on_vehicle_collision_event(self, msg: Any) -> None:
        """MSG 4103 — 비행체 충돌 이벤트. Override to handle."""



@_validate_role_base
class VisualModule(DtamModule):
    """Visualization (Unreal) 역할의 base 클래스.

    FORWARD_RULES: 0003, 1002, 1003, 2002, 3001, 4001, 5002, 5003, 5004.
    현재 Visual 은 외부 Unreal Engine 바이너리이고 Python SDK 사용처가
    없지만, 향후 Python 시각화기를 만들 때를 위해 준비.
    """
    role = Role.VISUAL

    @on_receive("0003")
    def on_common_time_info(self, msg: Any) -> None:
        """MSG 0003 — 공통 시간 정보. Override to handle."""

    @on_receive("1002")
    def on_simulation_setup(self, msg: Any) -> None:
        """MSG 1002 — 시뮬레이션 통제. Override to handle."""

    @on_receive("1003")
    def on_scenario_setup(self, msg: Any) -> None:
        """MSG 1003 scenario setup. Override to handle."""

    @on_receive("2002")
    def on_dtam_execute(self, msg: Any) -> None:
        """MSG 2002 — DTAM 실행 명령. Override to handle."""

    @on_receive("3001")
    def on_scheduled_flight(self, msg: Any) -> None:
        """MSG 3001 scheduled flight guide. Override to handle."""

    @on_receive("4001")
    def on_vehicle_status(self, msg: Any) -> None:
        """MSG 4001 — 비행체 10Hz 상태. Override to handle."""

    @on_receive("5002")
    def on_camera_control_command(self, msg: Any) -> None:
        """MSG 5002 — 카메라 제어 명령. Override to handle."""

    @on_receive("5003")
    def on_abnormal_situation_command(self, msg: Any) -> None:
        """MSG 5003 — 비정상 상황/장애물 생성 명령. Override to handle."""

    @on_receive("5004")
    def on_wind_effect_data(self, msg: Any) -> None:
        """MSG 5004 — 데모 날씨 기체별 바람 영향 (시각화). Override to handle."""


@_validate_role_base
class SituationAwarenessModule(DtamModule):
    """Situation Awareness 플러그인 역할의 base 클래스.

    FORWARD_RULES: 2002, 4001, 4002, 4101, 4102, 4103.
    """
    role = Role.SITUATION_AWARENESS

    @on_receive("2002")
    def on_dtam_execute(self, msg: Any) -> None:
        """MSG 2002 — DTAM 실행 명령. Override to handle."""

    @on_receive("4001")
    def on_vehicle_status(self, msg: Any) -> None:
        """MSG 4001 — 비행체 10Hz 상태. Override to handle."""

    @on_receive("4002")
    def on_vehicle_warning_event(self, msg: Any) -> None:
        """MSG 4002 — 비행체 경고 이벤트 (이상 감지). Override to handle."""

    @on_receive("4101")
    def on_camera_image(self, msg: Any) -> None:
        """MSG 4101 — 카메라 이미지 프레임. Override to handle."""
    @on_receive("4102")
    def on_camera_stream_descriptor(self, msg: Any) -> None:
        """MSG 4102 ? Camera Stream Descriptor. Override to handle."""

    @on_receive("4103")
    def on_vehicle_collision_event(self, msg: Any) -> None:
        """MSG 4103 — 비행체 충돌 이벤트. Override to handle."""


@_validate_role_base
class PSUModule(DtamModule):
    """Provider of Services for UAM (PSU) 외부 이해관계자 역할의 base 클래스.

    ExtenstionModule/PSUModule 이 사용. UAM 교통관리 서비스로서
    Vehicle 발 상태/경고 이벤트를 받아 지속 궤적 예측·충돌 감지를 수행하고,
    충돌 위험 또는 긴급 상황(배터리 부족 등) 시 3003 Tactical Separation
    을 직접 발행하여 즉시 개입.

    FORWARD_RULES (수신): 4001 (Vehicle Status 10Hz), 4002 (Warning),
    5004 (Wind Effect — 궤적 예측에 바람 반영).
    발행: 3003 (Tactical Separation), 2001 (전략 재계획 트리거 — 보조 경로).
    """
    role = Role.PSU

    @on_receive("4001")
    def on_vehicle_status(self, msg: Any) -> None:
        """MSG 4001 — 비행체 10Hz 상태 (궤적 예측·트래픽 분석용). Override to handle."""

    @on_receive("4002")
    def on_vehicle_warning_event(self, msg: Any) -> None:
        """MSG 4002 — 비행체 경고 이벤트 (이상 감지). Override to handle."""

    @on_receive("5004")
    def on_wind_effect_data(self, msg: Any) -> None:
        """MSG 5004 — 데모 날씨 기체별 바람 영향 (궤적 예측 보정). Override to handle."""


__all__ = [
    "MissionModule",
    "VehicleModule",
    "MonitoringModule",
    "VisualModule",
    "SituationAwarenessModule",
    "PSUModule",
]
