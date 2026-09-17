#!/usr/bin/env python3
"""Plan delivery trips from a CSV file."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

CAPACITY_KG = 10.0
REQUIRED_COLUMNS = {"id", "area", "priority", "weight_kg"}


@dataclass(frozen=True)
class Delivery:
    id: int
    area: str
    priority: int
    weight_kg: float


@dataclass
class Trip:
    trip_number: int
    area: str
    deliveries: list[Delivery]

    @property
    def total_weight_kg(self) -> float:
        return round(sum(item.weight_kg for item in self.deliveries), 2)


def read_deliveries(path: str | Path) -> tuple[list[Delivery], list[str]]:
    """Read valid deliveries and return validation warnings for rejected rows."""
    deliveries: list[Delivery] = []
    warnings: list[str] = []
    seen_ids: set[int] = set()

    with Path(path).open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(
                "Input CSV is missing required columns: " + ", ".join(sorted(missing))
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                delivery = Delivery(
                    id=int(row["id"]),
                    area=row["area"].strip(),
                    priority=int(row["priority"]),
                    weight_kg=float(row["weight_kg"]),
                )
                if delivery.id in seen_ids:
                    raise ValueError("duplicate id")
                if not delivery.area:
                    raise ValueError("area is empty")
                if delivery.priority < 1:
                    raise ValueError("priority must be at least 1")
                if delivery.weight_kg <= 0:
                    raise ValueError("weight must be greater than 0")
                if delivery.weight_kg > CAPACITY_KG:
                    raise ValueError(f"weight is greater than {CAPACITY_KG:g} kg capacity")
            except (TypeError, ValueError) as exc:
                warnings.append(f"Line {line_number} skipped: {exc}")
                continue
            seen_ids.add(delivery.id)
            deliveries.append(delivery)

    return deliveries, warnings


def plan_trips(deliveries: Iterable[Delivery]) -> list[Trip]:
    """Create trips in priority order, grouping consecutive deliveries by area.

    Within equal priority, area and ID make the result deterministic. A delivery
    joins the current trip only when it has the same area and still fits.
    """
    ordered = sorted(deliveries, key=lambda item: (item.priority, item.area.lower(), item.id))
    trips: list[Trip] = []

    for delivery in ordered:
        if not trips:
            trips.append(Trip(1, delivery.area, [delivery]))
            continue

        current = trips[-1]
        same_area = current.area.casefold() == delivery.area.casefold()
        fits = current.total_weight_kg + delivery.weight_kg <= CAPACITY_KG + 1e-9
        if same_area and fits:
            current.deliveries.append(delivery)
        else:
            trips.append(Trip(len(trips) + 1, delivery.area, [delivery]))

    return trips


def print_plan(trips: list[Trip], warnings: list[str]) -> None:
    if not trips:
        print("No valid deliveries found. No trips planned.")
        return

    for trip in trips:
        ids = ", ".join(str(item.id) for item in trip.deliveries)
        print(
            f"Trip {trip.trip_number}: area={trip.area} | "
            f"deliveries=[{ids}] | weight={trip.total_weight_kg:.2f}/{CAPACITY_KG:.2f} kg"
        )

    print(f"\nSummary: {len(trips)} trip(s), {sum(len(t.deliveries) for t in trips)} delivery(ies)")
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan delivery trips from a CSV file.")
    parser.add_argument("input", help="Path to a CSV file")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args()

    try:
        deliveries, warnings = read_deliveries(args.input)
        trips = plan_trips(deliveries)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "capacity_kg": CAPACITY_KG,
            "trips": [
                {
                    "trip_number": trip.trip_number,
                    "area": trip.area,
                    "total_weight_kg": trip.total_weight_kg,
                    "deliveries": [asdict(item) for item in trip.deliveries],
                }
                for trip in trips
            ],
            "warnings": warnings,
        }
        print(json.dumps(payload, indent=2))
    else:
        print_plan(trips, warnings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
