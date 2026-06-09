"""한 비행체의 ``VehicleSession`` — 엔진 + 컨텍스트 + 상태.

``IntegratedAirMobilityService`` 가 ``Dict[aircraft_id, VehicleSession]`` 으로
세션을 보유하며, 매 tick 마다 ``advance()`` 를 호출해 4001 payload 의
원천이 되는 ``FlightTrajectoryPoint`` 를 얻는다.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..domain.dynamics.core.flight_dynamics import DynamicsEngine
from ..domain.dynamics.core.flight_profile import build_kinematics
from ..domain.dynamics.core.path_builder import build_segment_profiles
from ..domain.dynamics.core.types import (
    FlightPlan,
    FlightTrajectoryPoint,
    SimulationConfig,
)
from ..domain.dynamics.core.wind_model import WindModel
from ..domain.transform.coord_transform import LocalNEDFrame
from .msg4001 import VehiclePublishContext
from .types import VehicleState, VehicleStatus, parse_hhmmss_to_s

logger = logging.getLogger(__name__)


def _departure_origin_frame(plan: FlightPlan) -> LocalNEDFrame:
    """첫 세그먼트의 start_lla 를 NED 원점으로 사용."""
    if plan.en_route:
        start = plan.en_route[0].start_lla
        return LocalNEDFrame(origin_lat=start.lat, origin_lon=start.lon, origin_alt_m=start.alt)
    return LocalNEDFrame(origin_lat=0.0, origin_lon=0.0, origin_alt_m=0.0)


class VehicleSession:
    """한 비행체의 엔진 + 컨텍스트 + 상태."""

    def __init__(
        self,
        plan: FlightPlan,
        *,
        config: SimulationConfig,
        wind_seed: int = 20260121,
        month: int = 4,
    ) -> None:
        self.plan = plan
        self.config = config
        self.wind_seed = int(wind_seed)
        self.month = int(month)

        self.state: VehicleState = VehicleState.WAITING
        self.last_error: str = ""
        self.last_point: Optional[FlightTrajectoryPoint] = None
        self.last_payload: Optional[Dict[str, Any]] = None
        self.elapsed_s: float = 0.0
        self.engine: Optional[DynamicsEngine] = None
        self.origin_frame: LocalNEDFrame = _departure_origin_frame(plan)
        self.context: VehiclePublishContext = VehiclePublishContext(
            vehicle_id=plan.aircraft_id,
            flight_plan_number=int(plan.flight_plan_number),
            origin_frame=self.origin_frame,
            departure_vertiport=str(plan.departure.vertiport),
            departure_gate=str(plan.departure.dep_gate_number),
            arrival_vertiport=str(plan.arrival.vertiport),
            arrival_gate=str(plan.arrival.arr_gate_number),
        )

        try:
            self.etot_s: float = parse_hhmmss_to_s(plan.departure.etot)
        except Exception as exc:
            self.etot_s = 0.0
            self.last_error = f"etot parse failed: {exc}"
            self.state = VehicleState.ERROR

    @property
    def aircraft_id(self) -> str:
        return self.plan.aircraft_id

    @property
    def flight_plan_number(self) -> int:
        return int(self.plan.flight_plan_number)

    def _ensure_engine(self) -> None:
        if self.engine is not None:
            return
        try:
            seg_profiles, proj = build_segment_profiles(self.plan, self.config)
            kinematics = build_kinematics(seg_profiles, self.config)
            wind: Optional[WindModel] = None
            if self.config.wind_enabled:
                parts = self.plan.departure.etot.split(":")
                start_hour = int(parts[0]) + int(parts[1]) / 60.0
                wind = WindModel(
                    seed=self.wind_seed,
                    time_speed=self.config.wind_time_speed,
                    preset=self.config.wind_preset,
                    start_local_hour=start_hour,
                )
            self.engine = DynamicsEngine(
                segments=seg_profiles,
                kinematics=kinematics,
                proj=proj,
                config=self.config,
                wind_model=wind,
                start_clock=self.plan.departure.etot,
                month=self.month,
            )
        except Exception as exc:
            self.state = VehicleState.ERROR
            self.last_error = f"engine init failed: {type(exc).__name__}: {exc}"
            logger.exception("engine init failed for %s", self.aircraft_id)

    def advance(self, sim_time_s: float) -> Optional[FlightTrajectoryPoint]:
        """sim_time_s 가 etot 이상이면 engine.tick() 을 1회 전진시킨다."""
        if self.state == VehicleState.COMPLETED:
            return None
        if self.state == VehicleState.ERROR:
            return None
        if sim_time_s + 1e-6 < self.etot_s:
            return None

        self._ensure_engine()
        if self.engine is None:
            return None

        if self.state == VehicleState.WAITING:
            self.state = VehicleState.ACTIVE

        point = self.engine.tick()
        if point is None:
            self.state = VehicleState.COMPLETED
            return None
        self.last_point = point
        self.elapsed_s = float(getattr(self.engine, "current_time", point.time_s))
        if bool(getattr(self.engine, "is_finished", False)):
            self.state = VehicleState.COMPLETED
        return point

    def status(self) -> VehicleStatus:
        total = 0.0
        if self.engine is not None:
            total = float(getattr(self.engine, "total_time_s", 0.0))
        last_pt_dict: Optional[Dict[str, Any]] = None
        if self.last_payload is not None:
            pos = self.last_payload.get("position") or {}
            gps = self.last_payload.get("gps") or {}
            last_pt_dict = {
                "lat": gps.get("latitude"),
                "lon": gps.get("longitude"),
                "alt_m": gps.get("altitude"),
                "north": pos.get("north"),
                "east": pos.get("east"),
                "down": pos.get("down"),
                "waypoint_id": self.last_payload.get("currentWaypointId"),
            }
        return VehicleStatus(
            vehicle_id=self.aircraft_id,
            flight_plan_number=self.flight_plan_number,
            state=self.state,
            etot_s=float(self.etot_s),
            elapsed_s=float(self.elapsed_s),
            total_duration_s=float(total),
            last_point=last_pt_dict,
            last_error=self.last_error,
        )


__all__ = ["VehicleSession"]
