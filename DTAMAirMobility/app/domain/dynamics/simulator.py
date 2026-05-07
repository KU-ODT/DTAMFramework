"""UAM Flight Simulator — Main orchestrator.

High-level API that ties together ICD parsing, path building, kinematic
profiling, dynamics simulation, and output generation.
"""

from __future__ import annotations

import csv
import json
import io
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Union

from .core.types import FlightPlan, FlightTrajectoryPoint, SimulationConfig
from .io.icd_parser import load_from_file, parse_flight_plans
from .core.path_builder import build_segment_profiles
from .core.flight_profile import build_kinematics
from .core.flight_dynamics import DynamicsEngine
from .core.wind_model import WindModel
from .runtime.async_runtime import FlightStreamService, ClockSource


class SimulationResult:
    """Result of a single flight simulation."""

    def __init__(
        self,
        flight_plan: FlightPlan,
        trajectory: List[FlightTrajectoryPoint],
        config: SimulationConfig,
    ) -> None:
        self.flight_plan = flight_plan
        self.trajectory = trajectory
        self.config = config

    @property
    def aircraft_id(self) -> str:
        return self.flight_plan.aircraft_id

    @property
    def flight_plan_number(self) -> int:
        return self.flight_plan.flight_plan_number

    @property
    def duration_s(self) -> float:
        if not self.trajectory:
            return 0.0
        return self.trajectory[-1].time_s

    @property
    def point_count(self) -> int:
        return len(self.trajectory)

    def summary(self) -> Dict:
        """Return a summary dict of the simulation result."""
        if not self.trajectory:
            return {"error": "no trajectory data"}
        first = self.trajectory[0]
        last = self.trajectory[-1]
        speeds = [p.speed_mps for p in self.trajectory if p.speed_mps > 0]
        alts = [p.alt_m for p in self.trajectory]
        return {
            "flight_plan_number": self.flight_plan_number,
            "aircraft_id": self.aircraft_id,
            "departure": self.flight_plan.departure.vertiport,
            "arrival": self.flight_plan.arrival.vertiport,
            "start_clock": first.clock,
            "end_clock": last.clock,
            "duration_s": round(self.duration_s, 1),
            "total_points": self.point_count,
            "max_speed_mps": round(max(speeds), 2) if speeds else 0,
            "max_altitude_m": round(max(alts), 2),
            "min_battery_pct": round(min(p.battery_pct for p in self.trajectory), 2),
        }

    def to_json(self, indent: int = 2) -> str:
        """Export trajectory as JSON string."""
        records = [asdict(p) for p in self.trajectory]
        return json.dumps(records, indent=indent, ensure_ascii=False)

    def to_csv(self) -> str:
        """Export trajectory as CSV string."""
        if not self.trajectory:
            return ""
        fields = list(asdict(self.trajectory[0]).keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for p in self.trajectory:
            writer.writerow(asdict(p))
        return output.getvalue()

    def save_json(self, path: Union[str, Path]) -> None:
        """Save trajectory to a JSON file."""
        Path(path).write_text(self.to_json(), encoding="utf-8")

    def save_csv(self, path: Union[str, Path]) -> None:
        """Save trajectory to a CSV file."""
        Path(path).write_text(self.to_csv(), encoding="utf-8")


class UAMFlightSimulator:
    """Main simulator class.

    Usage:
        sim = UAMFlightSimulator()
        results = sim.run_from_file("mission.json")
        for result in results:
            print(result.summary())
            result.save_csv("output.csv")
    """

    def __init__(
        self,
        config: Optional[SimulationConfig] = None,
        wind_preset: str = "good",
        wind_seed: int = 20260121,
        month: int = 4,
    ) -> None:
        self.config = config or SimulationConfig()
        self.config.wind_preset = wind_preset
        self.wind_seed = wind_seed
        self.month = month

    def _create_wind_model(self, start_hour: float) -> Optional[WindModel]:
        if not self.config.wind_enabled:
            return None
        return WindModel(
            seed=self.wind_seed,
            time_speed=self.config.wind_time_speed,
            preset=self.config.wind_preset,
            start_local_hour=start_hour,
        )

    def simulate_plan(self, plan: FlightPlan) -> SimulationResult:
        """Simulate a single flight plan and return the result."""
        # Build path from ICD segments
        seg_profiles, proj = build_segment_profiles(plan, self.config)

        # Build kinematic schedule
        kinematics = build_kinematics(seg_profiles, self.config)

        # Parse departure time for wind model
        parts = plan.departure.etot.split(":")
        start_hour = int(parts[0]) + int(parts[1]) / 60.0

        # Create wind model
        wind = self._create_wind_model(start_hour)

        # Run dynamics
        engine = DynamicsEngine(
            segments=seg_profiles,
            kinematics=kinematics,
            proj=proj,
            config=self.config,
            wind_model=wind,
            start_clock=plan.departure.etot,
            month=self.month,
        )
        trajectory = engine.generate_trajectory()

        return SimulationResult(
            flight_plan=plan,
            trajectory=trajectory,
            config=self.config,
        )

    def run_from_file(self, path: Union[str, Path]) -> List[SimulationResult]:
        """Load flight plans from a JSON file and simulate all of them."""
        plans = load_from_file(path)
        return [self.simulate_plan(p) for p in plans]

    def run_from_json(self, data: Union[dict, list]) -> List[SimulationResult]:
        """Simulate flight plans from parsed JSON data."""
        plans = parse_flight_plans(data)
        return [self.simulate_plan(p) for p in plans]

    def run_from_string(self, json_str: str) -> List[SimulationResult]:
        """Simulate flight plans from a JSON string."""
        data = json.loads(json_str)
        return self.run_from_json(data)

    # ── Async service factory ──────────────────────────────────

    def create_stream_service(
        self, clock_source: Optional[ClockSource] = None
    ) -> FlightStreamService:
        """Create an async ``FlightStreamService`` with this simulator's settings.

        The returned service can accept plans dynamically and stream
        trajectory points at the configured tick rate.
        """
        return FlightStreamService(
            config=self.config,
            clock_source=clock_source,
            wind_preset=self.config.wind_preset,
            wind_seed=self.wind_seed,
            month=self.month,
        )
