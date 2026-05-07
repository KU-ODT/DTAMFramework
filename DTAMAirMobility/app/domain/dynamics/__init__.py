"""UAM Flight Simulator — Async-capable eVTOL trajectory generator.

A modular UAM (Urban Air Mobility) flight trajectory simulator that accepts
ICD v1 mission plans and generates realistic flight data, either in batch
mode or as a real-time async stream at configurable tick rates (default 30 Hz).

Batch usage:
    from simpleDynamics import UAMFlightSimulator
    results = sim.run_from_file("mission.json")

Async streaming usage:
    from simpleDynamics import FlightStreamService, WallClockSource
    service = FlightStreamService(clock_source=WallClockSource())
    fid = await service.submit_plan(plan)
    async for point in service.subscribe(fid):
        ...
"""

from .core.types import (
    DEFAULT_SIMULATION_HZ,
    DEFAULT_SIMULATION_TICK_S,
    LLA,
    Phase,
    FlightMode,
    FlightPlan,
    FlightTrajectoryPoint,
    FlightState,
    FlightStatus,
    SimulationConfig,
)
from .simulator import UAMFlightSimulator, SimulationResult
from .io.icd_parser import load_from_file, parse_flight_plans, ICDValidationError
from .core.wind_model import WindModel
from .runtime.async_runtime import (
    FlightStreamService,
    FlightSession,
    ClockSource,
    WallClockSource,
    ExternalClockSource,
    FreeRunClockSource,
)

__version__ = "2.0.0"
__all__ = [
    # Batch API
    "DEFAULT_SIMULATION_HZ",
    "DEFAULT_SIMULATION_TICK_S",
    "UAMFlightSimulator",
    "SimulationResult",
    "SimulationConfig",
    "FlightPlan",
    "FlightTrajectoryPoint",
    "FlightMode",
    "Phase",
    "LLA",
    "WindModel",
    "load_from_file",
    "parse_flight_plans",
    "ICDValidationError",
    # Async streaming API
    "FlightStreamService",
    "FlightSession",
    "FlightState",
    "FlightStatus",
    "ClockSource",
    "WallClockSource",
    "ExternalClockSource",
    "FreeRunClockSource",
]
