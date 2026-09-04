"""
tests/test_navigation.py — Unit tests for tools/navigation_tools.py
"""

import unittest
from tools.navigation_tools import (
    haversine_distance_km,
    haversine_distance_nm,
    calculate_compass_bearing,
    estimate_fuel_consumption,
    check_geofence_intersection,
    calculate_optimal_route,
)


class TestNavigationTools(unittest.TestCase):
    def test_haversine_distance(self):
        # Distance from Kochi (9.9312, 76.2673) to Kochi PFZ (9.72, 75.82)
        km = haversine_distance_km(9.9312, 76.2673, 9.72, 75.82)
        self.assertGreater(km, 40.0)
        self.assertLess(km, 65.0)

        km2, nm = haversine_distance_nm(9.9312, 76.2673, 9.72, 75.82)
        self.assertEqual(km, km2)
        self.assertAlmostEqual(nm, round(km / 1.852, 2), places=1)

    def test_calculate_compass_bearing(self):
        # Directly North
        deg_n, card_n = calculate_compass_bearing(10.0, 76.0, 11.0, 76.0)
        self.assertAlmostEqual(deg_n, 0.0, delta=1.0)
        self.assertIn("N", card_n)

        # Directly East
        deg_e, card_e = calculate_compass_bearing(10.0, 76.0, 10.0, 77.0)
        self.assertAlmostEqual(deg_e, 90.0, delta=1.0)
        self.assertIn("E", card_e)

        # Directly South
        deg_s, card_s = calculate_compass_bearing(10.0, 76.0, 9.0, 76.0)
        self.assertAlmostEqual(deg_s, 180.0, delta=1.0)
        self.assertIn("S", card_s)

        # Directly West
        deg_w, card_w = calculate_compass_bearing(10.0, 76.0, 10.0, 75.0)
        self.assertAlmostEqual(deg_w, 270.0, delta=1.0)
        self.assertIn("W", card_w)

    def test_estimate_fuel_consumption(self):
        dist_nm = 20.0
        fuel = estimate_fuel_consumption(
            distance_nm=dist_nm,
            speed_knots=9.0,
            burn_rate_l_nm=1.8,
            diesel_price_inr=94.0,
            search_factor=1.30,
        )
        self.assertEqual(fuel["optimal_fuel_liters"], 36.0)
        self.assertEqual(fuel["unoptimized_distance_nm"], 26.0)
        self.assertEqual(fuel["unoptimized_fuel_liters"], 46.8)
        self.assertAlmostEqual(fuel["fuel_saved_liters"], 10.8, places=1)
        self.assertAlmostEqual(fuel["cost_saved_inr"], round(10.8 * 94.0), delta=10)
        self.assertIn("2h 13m", fuel["transit_time_str"])

    def test_geofence_intersection_and_detour(self):
        # A rectangular hazard geofence off Kochi
        hazard_poly = [
            [9.70, 76.00],
            [9.70, 75.80],
            [9.90, 75.80],
            [9.90, 76.00],
        ]
        # Track starting at Kochi (9.93, 76.26) and ending offshore (9.72, 75.70)
        # This crosses the polygon boundary
        intersects, detour = check_geofence_intersection(
            start_coords=[9.93, 76.26],
            end_coords=[9.72, 75.70],
            hazard_geofences=[hazard_poly],
        )
        self.assertTrue(intersects)
        self.assertIsNotNone(detour)
        self.assertIsInstance(detour, list)
        self.assertEqual(len(detour), 2)
        # Check that detour waypoint is seaward (further west for Arabian sea)
        self.assertLess(detour[1], 75.80)

    def test_calculate_optimal_route_clean(self):
        # Route without hazards
        route = calculate_optimal_route(
            start_coords=[9.9312, 76.2673],
            end_coords=[9.72, 75.82],
            hazard_geofences=None,
            start_label="Kochi Harbor",
            end_label="Kochi Offshore Upwelling Zone",
        )
        self.assertTrue(route["success"])
        self.assertFalse(route["hazard_avoidance_active"])
        self.assertIn("Safe & Clear", route["geofence_status"])
        self.assertEqual(len(route["waypoints"]), 2)
        self.assertIn("fuel_economy", route)
        self.assertGreater(route["fuel_economy"]["fuel_saved_liters"], 0.0)

    def test_calculate_optimal_route_with_detour(self):
        # Route with hazard geofence
        hazard_poly = [
            [9.70, 76.00],
            [9.70, 75.80],
            [9.90, 75.80],
            [9.90, 76.00],
        ]
        route = calculate_optimal_route(
            start_coords=[9.93, 76.26],
            end_coords=[9.72, 75.70],
            hazard_geofences=[hazard_poly],
            start_label="Kochi Harbor",
            end_label="Deep Sea Hotspot",
        )
        self.assertTrue(route["success"])
        self.assertTrue(route["hazard_avoidance_active"])
        self.assertIn("Detour Active", route["geofence_status"])
        self.assertEqual(len(route["waypoints"]), 3)
        self.assertEqual(route["waypoints"][1]["name"], "WP-2: Hazard Clearance Detour")


if __name__ == "__main__":
    unittest.main()
