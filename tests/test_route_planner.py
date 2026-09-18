import csv
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from route_planner import (
    Delivery,
    are_neighboring_areas,
    build_recommendations,
    build_recommended_plan,
    plan_trips,
    read_deliveries,
)


class RoutePlannerTests(unittest.TestCase):
    def test_baseline_groups_same_area_and_respects_capacity(self):
        deliveries = [
            Delivery(1, "Nasr City", 2, 4.5),
            Delivery(2, "Maadi", 1, 2.0),
            Delivery(3, "Nasr City", 3, 1.2),
        ]
        trips = plan_trips(deliveries)
        self.assertEqual([trip.deliveries[0].id for trip in trips], [2, 1])
        self.assertEqual(trips[1].total_weight_kg, 5.7)
        self.assertTrue(all(trip.total_weight_kg <= 10 for trip in trips))

    def test_empty_input(self):
        self.assertEqual(plan_trips([]), [])

    def test_same_area_splits_when_capacity_is_exceeded(self):
        deliveries = [
            Delivery(1, "Heliopolis", 1, 7.0),
            Delivery(2, "Heliopolis", 2, 4.0),
        ]
        trips = plan_trips(deliveries)
        self.assertEqual(len(trips), 2)

    def test_neighbor_links_are_symmetric_and_distant_areas_are_not_neighbors(self):
        self.assertTrue(are_neighboring_areas("Heliopolis", "Nasr City"))
        self.assertTrue(are_neighboring_areas("Nasr City", "Heliopolis"))
        self.assertFalse(are_neighboring_areas("Heliopolis", "Zamalek"))

    def test_recommendation_finds_later_neighbor_that_fits(self):
        deliveries = [
            Delivery(1, "Heliopolis", 1, 7.0),
            Delivery(2, "Nasr City", 2, 3.0),
        ]
        trips = plan_trips(deliveries)
        recommendations = build_recommendations(deliveries, trips)
        self.assertTrue(any("Trip 1" in item and "Trip 2" in item for item in recommendations))
        self.assertTrue(any("10.00 kg" in item for item in recommendations))

    def test_recommended_plan_contains_merged_trip_and_saves_one_trip(self):
        deliveries = [
            Delivery(1, "Heliopolis", 1, 5.0),
            Delivery(2, "New Cairo", 1, 2.0),
        ]
        trips = plan_trips(deliveries)
        recommended_plan, merge_notes = build_recommended_plan(trips)
        self.assertEqual(len(trips), 2)
        self.assertEqual(len(recommended_plan), 1)
        self.assertEqual(recommended_plan[0].total_weight_kg, 7.0)
        self.assertEqual(len(merge_notes), 1)

    def test_recommendation_does_not_break_priority(self):
        deliveries = [
            Delivery(1, "Heliopolis", 2, 7.0),
            Delivery(2, "Zamalek", 1, 3.0),
        ]
        trips = plan_trips(deliveries)
        recommendations = build_recommendations(deliveries, trips)
        self.assertTrue(any("No safe neighboring-trip group" in item for item in recommendations))

    def test_invalid_rows_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["id", "area", "priority", "weight_kg"])
                writer.writerow([1, "Maadi", 1, 11])
                writer.writerow([2, "Maadi", 1, 2])
            deliveries, warnings = read_deliveries(path)
            self.assertEqual([item.id for item in deliveries], [2])
            self.assertEqual(len(warnings), 1)

    def test_out_of_zone_area_is_rejected_with_clear_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["id", "area", "priority", "weight_kg"])
                writer.writerow([1, "October", 1, 2.0])
            deliveries, warnings = read_deliveries(path)
            self.assertEqual(deliveries, [])
            self.assertTrue(any("OUT OF ZONE" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
