"""UAM Flight Dynamics — DTAMAirMobility 의 비행 물리 / ICD 파싱 코어.

DTAMAirMobility 의 ``IntegratedAirMobilityService`` (=``VehicleSession``) 가
이 패키지의 ``DynamicsEngine`` 을 tick-by-tick 으로 호출해 4001 trajectory 를
생성한다.

공개 API (``services/`` 에서 사용 중):
  - ``core.types``         FlightPlan, FlightTrajectoryPoint, SimulationConfig 등
  - ``core.flight_dynamics`` DynamicsEngine
  - ``core.flight_profile`` build_kinematics
  - ``core.path_builder``  build_segment_profiles
  - ``core.wind_model``    WindModel
  - ``io.icd_parser``      load_from_file, parse_flight_plans

이전 standalone ``simpleDynamics`` 패키지의 batch CLI / async streaming runtime
(``UAMFlightSimulator``, ``FlightStreamService``, ``ClockSource``…) 은 통합
서비스 ``IntegratedAirMobilityService`` 가 같은 역할을 직접 수행하므로 제거됨.
"""

from .core.types import (
    LLA,
    Phase,
    FlightMode,
    FlightPlan,
    FlightTrajectoryPoint,
    FlightState,
    FlightStatus,
    SimulationConfig,
)
from .core.wind_model import WindModel
from .io.icd_parser import load_from_file, parse_flight_plans, ICDValidationError

__version__ = "2.1.0"
__all__ = [
    "LLA",
    "Phase",
    "FlightMode",
    "FlightPlan",
    "FlightTrajectoryPoint",
    "FlightState",
    "FlightStatus",
    "SimulationConfig",
    "WindModel",
    "load_from_file",
    "parse_flight_plans",
    "ICDValidationError",
]
