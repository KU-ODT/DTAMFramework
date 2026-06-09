from __future__ import annotations

from datetime import date

from demand_gen import DemandGenerator, DemandRequest


def main() -> None:
    generator = DemandGenerator()

    request = DemandRequest(
        base_traffic=200_000,
        transfer_ratio_percent=2.5,
        scenario_date=date(2026, 5, 15),
        operation_start="07:00",
        operation_end="22:00",
        random_seed=42,
    )

    preview = generator.preview(request)
    print("=== preview ===")
    print(f"window-adjusted passengers: {preview['demand']['windowAdjustedPassengers']}")

    summary = generator.create_scenario(request)
    print("\n=== scenario ===")
    print(f"scenarioId: {summary['scenarioId']}")
    print(f"generated passengers: {summary['demand']['generatedPassengers']}")
    print(f"active OD pairs: {summary['allocation']['activePairs']}")

    print("\n=== per-vertiport totals ===")
    for entry in summary["allocation"]["originTotals"]:
        print(f"  {entry['origin']:<12} dep={entry['passengers']}")

    print("\n=== first 5 passengers ===")
    for record in summary["passengers"]["sample"][:5]:
        print(f"  {record['id']}  {record['origin']} -> {record['destination']}  @ {record['arrivalTimeLabel']}")


if __name__ == "__main__":
    main()
