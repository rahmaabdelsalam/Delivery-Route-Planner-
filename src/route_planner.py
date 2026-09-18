#!/usr/bin/env python3
"""Delivery route planner with a recommendation-only consolidation analysis."""

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
SUPPORTED_AREAS = {
    "heliopolis",
    "nasr city",
    "new cairo",
    "maadi",
    "zamalek",
}

# Ordered route links supplied by the business/domain assumption.
# A link means the two areas are considered neighboring for recommendations.
NEIGHBORING_AREAS = {
    frozenset(("heliopolis", "nasr city")),
    frozenset(("heliopolis", "new cairo")),
    frozenset(("nasr city", "new cairo")),
    frozenset(("nasr city", "maadi")),
    frozenset(("maadi", "new cairo")),
}


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

    @property
    def remaining_capacity_kg(self) -> float:
        return round(CAPACITY_KG - self.total_weight_kg, 2)


def normalize_area(area: str) -> str:
    return " ".join(area.casefold().split())


def are_neighboring_areas(area_a: str, area_b: str) -> bool:
    """Return whether two areas are adjacent according to configured links."""
    first = normalize_area(area_a)
    second = normalize_area(area_b)
    return frozenset((first, second)) in NEIGHBORING_AREAS


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
                if normalize_area(delivery.area) not in SUPPORTED_AREAS:
                    raise ValueError(
                        f"OUT OF ZONE: '{delivery.area}' is not one of the supported areas"
                    )
                if delivery.priority < 1:
                    raise ValueError("priority must be at least 1")
                if delivery.weight_kg <= 0:
                    raise ValueError("weight must be greater than 0")
                if delivery.weight_kg > CAPACITY_KG:
                    raise ValueError(f"weight is greater than {CAPACITY_KG:g} kg capacity")
            except (KeyError, TypeError, ValueError) as exc:
                warnings.append(f"Line {line_number} skipped: {exc}")
                continue
            seen_ids.add(delivery.id)
            deliveries.append(delivery)

    return deliveries, warnings


def plan_trips(deliveries: Iterable[Delivery]) -> list[Trip]:
    """Create the required baseline plan: priority first, same-area grouping."""
    ordered = sorted(
        deliveries,
        key=lambda item: (item.priority, normalize_area(item.area), item.id),
    )
    trips: list[Trip] = []

    for delivery in ordered:
        if not trips:
            trips.append(Trip(1, delivery.area, [delivery]))
            continue

        current = trips[-1]
        same_area = normalize_area(current.area) == normalize_area(delivery.area)
        fits = current.total_weight_kg + delivery.weight_kg <= CAPACITY_KG + 1e-9
        if same_area and fits:
            current.deliveries.append(delivery)
        else:
            trips.append(Trip(len(trips) + 1, delivery.area, [delivery]))

    return trips


def _can_add_to_group(group: list[Trip], candidate: Trip) -> bool:
    """Check capacity, priority order, and geographic connection for a group."""
    combined_weight = sum(trip.total_weight_kg for trip in group) + candidate.total_weight_kg
    current_priority = max(item.priority for trip in group for item in trip.deliveries)
    candidate_priority = min(item.priority for item in candidate.deliveries)
    connected = any(are_neighboring_areas(trip.area, candidate.area) for trip in group)
    return (
        connected
        and combined_weight <= CAPACITY_KG + 1e-9
        and candidate_priority >= current_priority
    )


def _find_best_group(trips: list[Trip], start_index: int, available: set[int]) -> list[int]:
    """Find the fullest connected group beginning at one baseline trip."""
    best = [start_index]

    def search(group_indexes: list[int], remaining_indexes: list[int]) -> None:
        nonlocal best
        group = [trips[index] for index in group_indexes]
        group_weight = sum(trip.total_weight_kg for trip in group)
        if len(group_indexes) > 1 and (
            group_weight > sum(trips[index].total_weight_kg for index in best)
            or (group_weight == sum(trips[index].total_weight_kg for index in best)
                and len(group_indexes) > len(best))
        ):
            best = list(group_indexes)

        for position, index in enumerate(remaining_indexes):
            candidate = trips[index]
            if _can_add_to_group(group, candidate):
                search(group_indexes + [index], remaining_indexes[position + 1 :])

    search([start_index], sorted(index for index in available if index > start_index))
    return best


def build_recommendations(deliveries: list[Delivery], trips: list[Trip]) -> list[str]:
    """Find and print explicit recommendations for safe multi-trip groups."""
    del deliveries  # The baseline trips already contain the validated deliveries.
    recommendations: list[str] = []
    available = set(range(len(trips)))
    groups: list[list[int]] = []
    while available:
        start = min(available)
        group = _find_best_group(trips, start, available)
        if len(group) > 1:
            groups.append(group)
            available.difference_update(group)
        else:
            available.remove(start)

    for group_indexes in groups:
        group = [trips[index] for index in group_indexes]
        combined_weight = sum(trip.total_weight_kg for trip in group)
        trip_names = ", ".join(
            f"Trip {trip.trip_number} ({trip.area}, {trip.total_weight_kg:.2f} kg)"
            for trip in group
        )
        trip_numbers = ", ".join(str(trip.trip_number) for trip in group)
        recommendations.append(
            f"RECOMMENDATION: Consider merging trips [{trip_numbers}]: {trip_names}. "
            f"The areas form a connected nearby group and the combined weight would be "
            f"{combined_weight:.2f}/{CAPACITY_KG:.2f} kg, so one vehicle trip could serve "
            "all of them. This is optional and is not applied automatically."
        )

    if not groups:
        recommendations.append(
            "No safe neighboring-trip group was found in the current valid data. "
            "Check that IDs are unique, areas use the configured names, and the pair "
            "weight does not exceed 10 kg."
        )

    recommendations.append(
        "Recommendation policy: groups may contain two or more trips. Every added area "
        "must be connected to the current group, and the total must stay within 10 kg. "
        "Configured links are Heliopolis-Nasr City, Heliopolis-New Cairo, "
        "Nasr City-New Cairo, and Nasr City-Maadi."
    )
    return recommendations


def build_recommended_plan(trips: list[Trip]) -> tuple[list[Trip], list[str]]:
    """Build a complete alternative plan using best non-overlapping groups."""
    alternative: list[Trip] = []
    merge_notes: list[str] = []
    available = set(range(len(trips)))
    groups: list[list[int]] = []
    while available:
        start = min(available)
        group = _find_best_group(trips, start, available)
        if len(group) > 1:
            groups.append(group)
            available.difference_update(group)
        else:
            available.remove(start)

    used_indexes: set[int] = set()
    for group_indexes in groups:
        group = [trips[index] for index in group_indexes]
        used_indexes.update(group_indexes)
        combined_weight = sum(trip.total_weight_kg for trip in group)
        areas = " + ".join(trip.area for trip in group)
        deliveries = [item for trip in group for item in trip.deliveries]
        alternative.append(Trip(0, areas, deliveries))
        trip_numbers = ", ".join(str(trip.trip_number) for trip in group)
        merge_notes.append(
            f"Merged baseline trips [{trip_numbers}]: "
            f"{combined_weight:.2f}/{CAPACITY_KG:.2f} kg."
        )

    for index, trip in enumerate(trips):
        if index not in used_indexes:
            alternative.append(Trip(0, trip.area, list(trip.deliveries)))
    for number, trip in enumerate(alternative, start=1):
        trip.trip_number = number
    return alternative, merge_notes


def print_trip_lines(trips: list[Trip], detailed: bool = True) -> None:
    """Print each trip. When detailed, break down every delivery inside it."""
    for trip in trips:
        bar = "-" * 60
        print(f"\n  Trip {trip.trip_number}  |  Area: {trip.area}")
        print(f"  {bar}")
        if detailed:
            for item in sorted(trip.deliveries, key=lambda d: d.priority):
                print(
                    f"    - ID {item.id:<4} priority={item.priority:<3} "
                    f"weight={item.weight_kg:>5.2f} kg"
                )
        else:
            ids = ", ".join(str(item.id) for item in trip.deliveries)
            print(f"    deliveries=[{ids}]")
        print(f"  {bar}")
        print(
            f"    Load: {trip.total_weight_kg:.2f}/{CAPACITY_KG:.2f} kg   "
            f"Remaining capacity: {trip.remaining_capacity_kg:.2f} kg"
        )


def print_plan(
    trips: list[Trip],
    warnings: list[str],
    recommendations: list[str],
    recommended_plan: list[Trip],
    merge_notes: list[str],
) -> None:
    print("=" * 72)
    print("DELIVERY ROUTE PLANNER")
    print("=" * 72)

    # -----------------------------------------------------------------
    # STEP 1 — Baseline plan: this is the core, REQUIRED rule set.
    # Deliveries are grouped by their own area first (same-area trips
    # filled up to the 10 kg capacity), ordered by priority. Nothing
    # here crosses area boundaries — that only happens in the optional
    # recommendation step below.
    # -----------------------------------------------------------------
    print("\n" + "#" * 72)
    print("STEP 1: BASELINE PLAN  (required rules — same area, priority order)")
    print("#" * 72)
    if not trips:
        print("\n  No valid deliveries found. No trips planned.")
    else:
        print_trip_lines(trips, detailed=True)
        print(
            f"\n  Summary: {len(trips)} trip(s), "
            f"{sum(len(t.deliveries) for t in trips)} delivery(ies) — "
            f"each trip stays within a single area and under {CAPACITY_KG:g} kg."
        )

    if warnings:
        print("\n" + "-" * 72)
        print("WARNINGS (rows skipped during validation)")
        print("-" * 72)
        for warning in warnings:
            print(f"  - {warning}")

    # -----------------------------------------------------------------
    # STEP 2 — Optional recommendation: only shown AFTER the baseline
    # plan above. This suggests merging trips from different, but
    # geographically neighboring, areas to save vehicle trips. It is
    # advisory only and never changes the baseline plan itself.
    # -----------------------------------------------------------------
    print("\n" + "#" * 72)
    print("STEP 2: RECOMMENDATION  (optional — merging nearby areas)")
    print("#" * 72)
    for recommendation in recommendations:
        print(f"  - {recommendation}")

    if merge_notes:
        saved = len(trips) - len(recommended_plan)
        print("\n" + "-" * 72)
        print("RECOMMENDED ALTERNATIVE PLAN (only applied if you accept it)")
        print("-" * 72)
        print_trip_lines(recommended_plan, detailed=True)
        print(
            f"\n  Alternative summary: {len(recommended_plan)} trip(s), "
            f"{saved} trip(s) saved compared with the baseline."
        )
        print("  Merge decisions:")
        for note in merge_notes:
            print(f"    - {note}")
    else:
        print("\n  No complete alternative plan was found that satisfies all rules.")
    print("\n" + "=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan delivery trips from a CSV file.")
    parser.add_argument("input", help="Path to a CSV file")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args()

    try:
        deliveries, warnings = read_deliveries(args.input)
        trips = plan_trips(deliveries)
        recommendations = build_recommendations(deliveries, trips)
        recommended_plan, merge_notes = build_recommended_plan(trips)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "capacity_kg": CAPACITY_KG,
                    "trips": [
                        {
                            "trip_number": trip.trip_number,
                            "area": trip.area,
                            "total_weight_kg": trip.total_weight_kg,
                            "remaining_capacity_kg": trip.remaining_capacity_kg,
                            "deliveries": [asdict(item) for item in trip.deliveries],
                        }
                        for trip in trips
                    ],
                    "warnings": warnings,
                    "recommendations": recommendations,
                    "recommended_plan": [
                        {
                            "trip_number": trip.trip_number,
                            "area": trip.area,
                            "total_weight_kg": trip.total_weight_kg,
                            "deliveries": [asdict(item) for item in trip.deliveries],
                        }
                        for trip in recommended_plan
                    ],
                    "merge_notes": merge_notes,
                },
                indent=2,
            )
        )
    else:
        print_plan(
            trips,
            warnings,
            recommendations,
            recommended_plan,
            merge_notes,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())