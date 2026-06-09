from __future__ import annotations

import argparse

from .io import run_analysis_from_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="vp_sim",
        description="Run a vertiport ground simulation as a JSON-in/JSON-out analysis module.",
    )
    parser.add_argument("--layout", required=True, help="Path to layout JSON.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the analysis result JSON.",
    )
    parser.add_argument(
        "--sim-config",
        default=None,
        help="Optional path to a separate simulation parameter JSON.",
    )
    parser.add_argument("--start", default="06:00", help="Operating start time in HH:MM.")
    parser.add_argument("--end", default="22:00", help="Operating end time in HH:MM.")
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=None,
        help="Override operating duration in minutes. If set, --start/--end are still recorded as labels.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Omit the full simulationResult from the output JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_analysis_from_files(
        layout_path=args.layout,
        output_path=args.output,
        sim_config_path=args.sim_config,
        start=args.start,
        end=args.end,
        duration_minutes=args.duration_minutes,
        include_simulation_result=not args.compact,
    )
    summary = payload["analysis"]["summary"]
    print("VP_Sim analysis complete")
    print(f"Output: {args.output}")
    print(
        "Throughput: "
        f"{summary['totalThroughput']} total, "
        f"{summary['takeoffSuccess']} takeoff, "
        f"{summary['landingComplete']} landing"
    )
    print(
        "Wait: "
        f"{summary['averageWaitMinutes']:.1f} min avg, "
        f"{summary['adjustedAverageWaitMinutes']:.1f} min after recommended slots"
    )


if __name__ == "__main__":
    main()
