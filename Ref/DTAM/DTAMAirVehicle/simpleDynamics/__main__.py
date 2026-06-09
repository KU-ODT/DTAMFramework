"""UAM Flight Simulator — CLI entry point.

Usage:
    python -m simpleDynamics mission.json [options]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .simulator import UAMFlightSimulator
from .core.types import SimulationConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="simpleDynamics",
        description="UAM eVTOL Flight Trajectory Simulator (ICD v1)",
    )
    parser.add_argument(
        "mission",
        help="Path to ICD v1 mission JSON file",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: current directory)",
        default=".",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--tick",
        type=float,
        default=0.1,
        help="Simulation tick interval in seconds (default: 0.1)",
    )
    parser.add_argument(
        "--wind",
        choices=["off", "good", "fair", "bad", "serious"],
        default="good",
        help="Wind preset (default: good)",
    )
    parser.add_argument(
        "--wind-seed",
        type=int,
        default=20260121,
        help="Wind model random seed",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=4,
        choices=range(1, 13),
        help="Calendar month for seasonal wind (default: 4)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary to stdout",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Build config
    config = SimulationConfig(tick_s=args.tick)
    wind_enabled = args.wind != "off"
    wind_preset = args.wind if wind_enabled else "good"
    config.wind_enabled = wind_enabled

    # Create simulator
    sim = UAMFlightSimulator(
        config=config,
        wind_preset=wind_preset,
        wind_seed=args.wind_seed,
        month=args.month,
    )

    # Run
    mission_path = Path(args.mission)
    if not mission_path.exists():
        print(f"Error: file not found: {mission_path}", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"Loading mission: {mission_path}")

    try:
        results = sim.run_from_file(mission_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for result in results:
        tag = f"FP{result.flight_plan_number}_{result.aircraft_id}"

        if not args.quiet:
            print(f"  Simulated {tag}: {result.point_count} points, "
                  f"{result.duration_s:.1f}s flight time")

        if args.summary or not args.quiet:
            summary = result.summary()
            print(f"  Summary: {json.dumps(summary, indent=2, ensure_ascii=False)}")

        if args.format in ("csv", "both"):
            csv_path = output_dir / f"{tag}_trajectory.csv"
            result.save_csv(csv_path)
            if not args.quiet:
                print(f"  Saved: {csv_path}")

        if args.format in ("json", "both"):
            json_path = output_dir / f"{tag}_trajectory.json"
            result.save_json(json_path)
            if not args.quiet:
                print(f"  Saved: {json_path}")

    if not args.quiet:
        print(f"\nDone. {len(results)} flight(s) simulated.")


if __name__ == "__main__":
    main()
