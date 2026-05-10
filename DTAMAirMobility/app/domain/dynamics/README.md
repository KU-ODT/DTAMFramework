# dynamics — UAM Flight Dynamics Core

DTAMAirMobility 의 비행 물리 / ICD 파싱 코어. ICD v1 비행계획을 받아
``DynamicsEngine`` 이 tick-by-tick 으로 trajectory point 를 산출.

## 위치 (이전 ``simpleDynamics`` 패키지가 여기로 이동)

```
DTAMAirMobility/app/domain/dynamics/
├── core/
│   ├── types.py            # FlightPlan, FlightTrajectoryPoint, SimulationConfig, ...
│   ├── flight_dynamics.py  # DynamicsEngine ★ tick 단위 진행
│   ├── flight_profile.py   # build_kinematics
│   ├── path_builder.py     # build_segment_profiles
│   ├── wind_model.py       # WindModel
│   └── geo.py              # 좌표 변환 보조
├── io/
│   └── icd_parser.py       # load_from_file, parse_flight_plans, ICDValidationError
└── __init__.py             # 공개 API re-export
```

## 사용 — ``IntegratedAirMobilityService`` 안에서 자동

[`services/vehicle_session.py`](../../services/vehicle_session.py) 의
``VehicleSession.advance(sim_time_s)`` 가 매 tick 마다 ``DynamicsEngine.tick()``
을 호출:

```python
from ..domain.dynamics.core.flight_dynamics import DynamicsEngine
from ..domain.dynamics.core.flight_profile import build_kinematics
from ..domain.dynamics.core.path_builder import build_segment_profiles
from ..domain.dynamics.core.types import FlightPlan, SimulationConfig
from ..domain.dynamics.core.wind_model import WindModel

seg_profiles, proj = build_segment_profiles(plan, config)
kinematics = build_kinematics(seg_profiles, config)
wind = WindModel(seed=..., preset=..., start_local_hour=...)
engine = DynamicsEngine(
    segments=seg_profiles, kinematics=kinematics, proj=proj,
    config=config, wind_model=wind,
    start_clock=plan.departure.etot, month=4,
)
point = engine.tick()           # FlightTrajectoryPoint 한 개
```

10 Hz 호출은 ``IntegratedAirMobilityService._loop`` (services/integrated_service.py)
가 시계 모드(EXTERNAL / WALL / MANUAL) 에 맞춰 수행.

## ICD 파싱

```python
from ..domain.dynamics.io.icd_parser import parse_flight_plans, parse_flight_plan

plans = parse_flight_plans(json_data)            # list 또는 fleet payload
plan = parse_flight_plan(record_dict)            # 단일 record
```

## 의존성

순수 표준 라이브러리만 사용 (외부 의존성 없음).

## 마이그레이션 메모

이전 standalone 패키지 ``simpleDynamics`` 의 batch CLI (``python -m
simpleDynamics``), ``UAMFlightSimulator``, async streaming runtime
(``FlightStreamService``, ``ClockSource``, …) 은 ``IntegratedAirMobilityService``
가 동등한 역할을 직접 수행하므로 제거됨.
