# simpleDynamics

ICD v1 mission plan to flight trajectory data.  
Batch or real-time async streaming at 10 Hz. Zero external dependencies.

```
Mission Plan (JSON)  +  Clock (wall / external / free-run)
        |                        |
        v                        v
  +-----------+          +---------------+
  |  Batch    |    or    |  Async Stream |
  |  Mode     |          |  (10 Hz)      |
  +-----------+          +---------------+
        |                        |
        v                        v
  Full trajectory          Point-by-point
  CSV / JSON               async iterator
```

---

## Quick Start

### Batch Mode (CLI)

```bash
python -m simpleDynamics mission.json \
  --wind good --format both -o output/
```

### Batch Mode (Python)

```python
from simpleDynamics import UAMFlightSimulator, SimulationConfig

sim = UAMFlightSimulator(
    config=SimulationConfig(tick_s=0.1),
    wind_preset="good",
)

results = sim.run_from_file("mission.json")
for r in results:
    print(r.summary())
    r.save_csv("trajectory.csv")
```

### Async Streaming Mode

```python
import asyncio
from simpleDynamics import (
    FlightStreamService,
    WallClockSource,
    SimulationConfig,
)
from simpleDynamics.io import load_from_file

async def main():
    service = FlightStreamService(
        config=SimulationConfig(tick_s=0.1),
        clock_source=WallClockSource(tick_interval=0.1),  # 10 Hz real-time
        wind_preset="good",
    )

    plan = load_from_file("mission.json")[0]
    flight_id = await service.submit_plan(plan)

    async for point in service.subscribe(flight_id):
        print(f"t={point.time_s:.1f}  "
              f"lat={point.lat:.6f}  lon={point.lon:.6f}  "
              f"alt={point.alt_m}m  spd={point.speed_mps}m/s")

    await service.shutdown()

asyncio.run(main())
```

### External Clock (Integration with External Systems)

```python
from simpleDynamics import FlightStreamService, ExternalClockSource

clock = ExternalClockSource(tick_interval=0.1)
service = FlightStreamService(clock_source=clock)

# Your system pushes time updates:
await clock.update(current_time_seconds)
```

---

## Architecture

```
simpleDynamics/
|
|-- core/                    # Pure computation (no I/O, no async)
|   |-- types.py             #   Data models, enums, config
|   |-- geo.py               #   Coordinate projection (LLA <-> XY)
|   |-- wind_model.py        #   3D Perlin noise wind field
|   |-- path_builder.py      #   ICD segments -> densified polylines
|   |-- flight_profile.py    #   Kinematic schedule (speed/accel)
|   |-- flight_dynamics.py   #   Dynamics engine (tick-by-tick stepper)
|
|-- io/                      # Input/Output
|   |-- icd_parser.py        #   ICD v1 JSON parser & validator
|
|-- runtime/                 # Async streaming layer
|   |-- async_runtime.py     #   ClockSource, FlightSession, FlightStreamService
|
|-- simulator.py             # High-level orchestrator (batch + async factory)
|-- __main__.py              # CLI entry point
|-- __init__.py              # Public API surface
```

### Layer Responsibilities

| Layer | Role | Depends on |
|-------|------|------------|
| **core** | Physics, geometry, wind, kinematics. Pure functions and stateful stepper. No I/O. | nothing |
| **io** | Parse ICD v1 JSON mission files. Validate structure. | core (types) |
| **runtime** | Async event loop, clock sources, multi-flight session management, subscriber streams. | core |
| **simulator** | Ties everything together. Batch API + async factory. | core, io, runtime |

---

## Inputs

### 1. Mission Plan (ICD v1 JSON)

```json
[
  {
    "flightPlanNumber": 1201,
    "aircraftId": "UAM0001",
    "departure": {
      "vertiport": "Yeouido",
      "std": "09:00:00",
      "depGateNumber": "G3",
      "eobt": "09:02:00",
      "depFatoNumber": "F2",
      "etot": "09:10:00"
    },
    "enRoute": [
      {
        "seq": 1,
        "phase": "A",
        "startLLA": { "lat": 37.5254, "lon": 126.9214, "alt": 0 },
        "endLLA":   { "lat": 37.5256, "lon": 126.9220, "alt": 0 },
        "targetSpeed": 8
      }
    ],
    "arrival": {
      "vertiport": "Jamsil",
      "sta": "10:00:00",
      "arrGateNumber": "G1",
      "eibt": "09:58:00",
      "arrFatoNumber": "F1",
      "eldt": "09:50:00"
    }
  }
]
```

**ICD Phase Codes:**

| Phase | Description | Phase | Description |
|-------|-------------|-------|-------------|
| A | Gate-out taxi | G | Arrival transition |
| B | Vertical takeoff | H | Arrival turn |
| C | Departure transition | I | Final approach |
| D | Departure turn | J | Vertical landing |
| E | Climb-out | K | Gate-in taxi |
| F | Cruise | | |

Turn phases (D, H) require `turnDirection` ("CW"/"CCW") and `centerLLA`.

### 2. Clock Source

| Clock | Use case |
|-------|----------|
| `WallClockSource(tick_interval)` | Real-time simulation at wall-clock speed |
| `ExternalClockSource(tick_interval)` | Driven by external system via `await clock.update(t)` |
| `FreeRunClockSource()` | Maximum speed, no pacing (batch / test) |

---

## Output

Each tick produces a `FlightTrajectoryPoint`:

| Field | Unit | Description |
|-------|------|-------------|
| `time_s` | s | Elapsed simulation time |
| `clock` | HH:MM:SS | Wall-clock time |
| `phase` | A-K | ICD mission phase code |
| `mode` | string | Flight mode (gate_taxi, vertical_climb, cruise, ...) |
| `lat` | deg | Latitude |
| `lon` | deg | Longitude |
| `alt_m` | m | Altitude |
| `speed_mps` | m/s | Ground speed |
| `heading_deg` | deg | Aircraft heading (nose direction) |
| `track_heading_deg` | deg | Track heading (actual flight path) |
| `wind_e_mps` | m/s | Eastward wind component |
| `wind_n_mps` | m/s | Northward wind component |
| `lateral_dev_m` | m | Cross-track deviation from planned path |
| `battery_pct` | % | Remaining battery |

---

## API Reference

### `FlightStreamService`

The primary async interface.

```python
service = FlightStreamService(
    config=SimulationConfig(),       # simulation parameters
    clock_source=WallClockSource(),  # pacing strategy
    wind_preset="good",              # good / fair / bad / serious
    wind_seed=20260121,              # deterministic wind seed
    month=4,                         # seasonal wind (1-12)
)

# Submit a mission plan (returns immediately)
flight_id = await service.submit_plan(plan)

# Subscribe to one flight's stream
async for point in service.subscribe(flight_id):
    ...

# Subscribe to ALL active flights
async for flight_id, point in service.subscribe_all():
    ...

# Flight management
service.get_status(flight_id)   # -> FlightStatus
service.list_flights()          # -> List[FlightStatus]
service.active_flights()        # -> List[str]
await service.cancel_flight(flight_id)
await service.shutdown()
```

### `UAMFlightSimulator` (Batch)

```python
sim = UAMFlightSimulator(config, wind_preset, wind_seed, month)

results = sim.run_from_file("mission.json")
results = sim.run_from_json(parsed_dict)
results = sim.run_from_string(json_string)
result  = sim.simulate_plan(flight_plan)

# Each SimulationResult:
result.summary()          # -> dict
result.trajectory         # -> List[FlightTrajectoryPoint]
result.save_csv(path)
result.save_json(path)

# Bridge to async:
service = sim.create_stream_service(clock_source)
```

### `SimulationConfig`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tick_s` | 0.1 | Time step (seconds) |
| `accel_mps2` | 1.5 | Longitudinal acceleration |
| `vertical_climb_rate_mps` | 2.54 | Vertical climb rate (~500 fpm) |
| `vertical_descent_rate_mps` | 2.54 | Vertical descent rate |
| `battery_capacity_s` | 1800 | Battery capacity (30 min) |
| `taxi_speed_mps` | 5.0 | Ground taxi speed |
| `wind_enabled` | True | Enable wind perturbation |
| `wind_preset` | "good" | Wind severity preset |
| `densify_step_m` | 20.0 | Path densification step |
| `arc_step_deg` | 1.0 | Arc sampling step for turn phases |
| `trajectory_smoothing_enabled` | True | Apply post-process trajectory smoothing |
| `trajectory_smoothing_tau_s` | 0.45 | Smoothing time constant |
| `trajectory_smoothing_passes` | 2 | Forward/backward smoothing passes |
| `trajectory_turn_smoothing_radius_m` | 400.0 | Spatial XY smoothing radius for turns |
| `trajectory_heading_lookahead_m` | 400.0 | Heading lookahead distance after path smoothing |

---

## Wind Model

3D Perlin noise spatiotemporal wind field:

- **Presets**: good (1-3 m/s), fair (1-5), bad (3-10), serious (5-12)
- **Temporal**: seasonal modulation (month), diurnal cycle (hour), layered noise (slow drift + gusts)
- **Spatial**: curl-noise at multiple scales, local weather zones, terrain effects (Han river enhancement)
- **Deterministic**: seeded PRNG for reproducible results across runs

---

## Requirements

- **Python >= 3.9**
- **No external dependencies** (stdlib only)
- `asyncio` (stdlib) for streaming mode

---

## CLI Options

```
python -m simpleDynamics <mission.json> [options]
```

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output` | Output directory | `.` |
| `--format` | csv / json / both | both |
| `--tick` | Tick interval (seconds) | 0.1 |
| `--wind` | off / good / fair / bad / serious | good |
| `--wind-seed` | Wind model random seed | 20260121 |
| `--month` | Calendar month (1-12) | 4 |
| `--summary` | Print summary to stdout | |
| `--quiet` | Suppress progress output | |

---

## License

Internal use.
