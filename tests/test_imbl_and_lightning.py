"""
tests/test_imbl_and_lightning.py — Unit tests for IMBL Geofencing & Lightning Alerts (ISRO SIH 26176).
"""

import unittest
from tools.navigation_tools import (
    distance_point_to_line_segment_nm,
    check_imbl_proximity,
    calculate_optimal_route,
    IMBL_BOUNDARIES,
)
from agents.weather_agent import (
    _compute_peak_metrics,
    _rule_based_verdict,
)
from agents.hazard_agent import classify_imd_hazard


class TestIMBLGeofencing(unittest.TestCase):
    """Test International Maritime Boundary Line (IMBL) proximity calculations."""

    def test_imbl_boundaries_defined(self):
        """Verify IMBL boundaries are defined for Sri Lanka and Pakistan."""
        self.assertIn("India-Sri Lanka", IMBL_BOUNDARIES)
        self.assertIn("India-Pakistan", IMBL_BOUNDARIES)
        self.assertGreater(len(IMBL_BOUNDARIES["India-Sri Lanka"]), 4)
        self.assertGreater(len(IMBL_BOUNDARIES["India-Pakistan"]), 3)

    def test_distance_point_to_line_segment_nm(self):
        """Test point-to-segment distance calculation."""
        # Point directly on the segment (midpoint of lat 10.0->12.0 at lon 75.0)
        d_on = distance_point_to_line_segment_nm(
            p_lat=11.0, p_lon=75.0,
            a_lat=10.0, a_lon=75.0,
            b_lat=12.0, b_lon=75.0,
        )
        self.assertAlmostEqual(d_on, 0.0, places=1)

        # Point 1 degree east at equator (~60 NM)
        d_off = distance_point_to_line_segment_nm(
            p_lat=0.0, p_lon=1.0,
            a_lat=-1.0, a_lon=0.0,
            b_lat=1.0, b_lon=0.0,
        )
        self.assertAlmostEqual(d_off, 60.0, delta=2.0)

    def test_imbl_proximity_near_rameswaram(self):
        """Route heading towards Sri Lanka border from Rameswaram breaches 5 NM threshold."""
        # Rameswaram (9.2876, 79.3129) towards Kachchatheevu area (9.32, 79.37)
        route_pts = [[9.2876, 79.3129], [9.3200, 79.3700]]
        res = check_imbl_proximity(route_pts, threshold_nm=5.0)

        self.assertTrue(res["imbl_warning_active"])
        self.assertEqual(res["closest_boundary"], "India-Sri Lanka")
        self.assertLess(res["min_distance_nm"], 5.0)
        self.assertIsNotNone(res["warning_message"])
        self.assertIn("Risk of Impoundment", res["warning_message"])

    def test_imbl_proximity_kochi_safe(self):
        """Route off Kochi is hundreds of miles away from IMBL."""
        route_pts = [[9.9312, 76.2673], [9.7200, 75.8200]]
        res = check_imbl_proximity(route_pts, threshold_nm=5.0)

        self.assertFalse(res["imbl_warning_active"])
        self.assertGreater(res["min_distance_nm"], 100.0)
        self.assertIsNone(res["warning_message"])

    def test_calculate_optimal_route_triggers_imbl_warning(self):
        """calculate_optimal_route flags IMBL proximity and styles route in red."""
        route = calculate_optimal_route(
            start_coords=[9.2876, 79.3129],  # Rameswaram
            end_coords=[9.3200, 79.3700],    # Close to Palk Strait IMBL
            hazard_geofences=None,
            start_label="Rameswaram Port",
            end_label="Palk Strait Hotspot",
        )
        self.assertTrue(route["success"])
        self.assertTrue(route["imbl_warning_active"])
        self.assertEqual(route["route_color"], "#dc3545")
        self.assertIn("IMBL WARNING", route["geofence_status"])
        self.assertIn("India-Sri Lanka", route["imbl_closest_boundary"])
        self.assertLess(route["imbl_min_distance_nm"], 5.0)


class TestLightningAndCAPEHazard(unittest.TestCase):
    """Test Convective Available Potential Energy (CAPE) and lightning alert logic."""

    def test_compute_peak_metrics_extracts_cape_and_lightning(self):
        """_compute_peak_metrics correctly parses CAPE and flags lightning hazard when CAPE > 1500."""
        atmo_window = {
            "wind_speed_10m": [12.0, 15.0],
            "wind_gusts_10m": [20.0, 22.0],
            "precipitation": [0.0, 1.5],
            "weather_code": [1, 2],  # No thunderstorm codes
            "cape": [600.0, 1850.0, 1200.0],  # Peak is 1850.0 J/kg (> 1500)
        }
        marine_window = {
            "wave_height": [0.8, 1.1],
            "swell_wave_height": [0.5, 0.6],
            "wave_period": [8.0, 9.0],
        }
        metrics = _compute_peak_metrics(atmo_window, marine_window)

        self.assertEqual(metrics["max_cape_jkg"], 1850.0)
        self.assertTrue(metrics["lightning_hazard"])
        self.assertFalse(metrics["thunderstorm_likely"])

    def test_cape_suppresses_safe_verdict(self):
        """When CAPE > 1500 J/kg, rule verdict MUST NOT be SAFE (suppressed to CAUTION)."""
        benign_metrics = {
            "max_wind_speed_kmh": 15.0,  # Below 25 km/h
            "max_wave_height_m": 0.9,    # Below 1.5 m
            "max_precipitation_mm": 2.0, # Below 20 mm
            "thunderstorm_likely": False,
            "max_cape_jkg": 1750.0,      # Elevated instability
            "lightning_hazard": True,
        }
        verdict = _rule_based_verdict(benign_metrics)
        self.assertEqual(verdict, "CAUTION")

    def test_extreme_cape_triggers_danger(self):
        """Extreme CAPE >= 2500 J/kg triggers DANGER."""
        extreme_metrics = {
            "max_wind_speed_kmh": 20.0,
            "max_wave_height_m": 1.2,
            "max_precipitation_mm": 5.0,
            "thunderstorm_likely": False,
            "max_cape_jkg": 2700.0,
            "lightning_hazard": True,
        }
        verdict = _rule_based_verdict(extreme_metrics)
        self.assertEqual(verdict, "DANGER")

    def test_low_cape_allows_safe(self):
        """Benign conditions with low CAPE allow SAFE verdict."""
        safe_metrics = {
            "max_wind_speed_kmh": 14.0,
            "max_wave_height_m": 0.8,
            "max_precipitation_mm": 0.0,
            "thunderstorm_likely": False,
            "max_cape_jkg": 450.0,
            "lightning_hazard": False,
        }
        verdict = _rule_based_verdict(safe_metrics)
        self.assertEqual(verdict, "SAFE")

    def test_hazard_agent_classifies_lightning_watch(self):
        """classify_imd_hazard elevates benign wind/waves to Level-1 Yellow watch when CAPE > 1500."""
        level, color, category, guidance, advisory = classify_imd_hazard(
            wind_kmh=15.0,
            wave_m=0.8,
            thunderstorm=False,
            cape_jkg=1900.0,
        )
        self.assertEqual(level, "Level-1")
        self.assertEqual(color, "Yellow")
        self.assertIn("Lightning Watch", category)
        self.assertIn("lightning hazard active", guidance.lower())
        self.assertIn("lightning instability", advisory.lower())


if __name__ == "__main__":
    unittest.main()
