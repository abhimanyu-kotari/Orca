"""
tests/test_danger_planning_ui.py — Unit tests verifying UI behavior under DANGER weather conditions.
Verifies that PFZs and fuel-optimal navigation metrics remain visible for planning
with the required safety warning banners and flags.
"""

import unittest
from app import format_orchestrator_response, generate_map_for_result


class TestDangerPlanningUI(unittest.TestCase):

    def setUp(self):
        self.mock_danger_result = {
            "success": True,
            "intent": "pfz_location",
            "persona": "fisherman",
            "navigation_suspended": True,
            "pfz_suppressed": False,
            "pfz_suppression_reason": (
                "⚠️ Navigation Suspended: Sea state / Lightning hazard active. "
                "Showing direct displacement metrics for planning purposes only once weather clears."
            ),
            "synthesis": (
                "🚨 **DANGER Alert for Kochi:** Severe weather or high sea state detected.\n\n"
                "⚠️ **Navigation Suspended: Sea state / Lightning hazard active. "
                "Showing direct displacement metrics for planning purposes only once weather clears.**\n\n"
                "🐟 **Identified Hotspot (Pre-Voyage Planning):** **Kochi Offshore Upwelling Zone**."
            ),
            "weather_result": {
                "success": True,
                "location": "Kochi, Kerala, India",
                "lat": 9.9312,
                "lon": 76.2673,
                "verdict": "DANGER",
                "key_metrics": {
                    "max_wind_speed_kmh": 65.0,
                    "max_wind_gust_kmh": 78.0,
                    "max_wave_height_m": 3.8,
                    "max_swell_height_m": 2.9,
                    "max_wave_period_s": 8.0,
                    "max_precipitation_mm": 15.0,
                    "max_cape_jkg": 1850.0,
                    "thunderstorm_likely": True,
                    "lightning_hazard": True,
                },
                "reasoning": "Sustained winds 65 km/h and wave heights 3.8 m exceed safe thresholds.",
            },
            "pfz_result": {
                "success": True,
                "location": "Kochi, Kerala, India",
                "lat": 9.9312,
                "lon": 76.2673,
                "zones": [
                    {
                        "zone_id": "PFZ-KL-001",
                        "name": "Kochi Offshore Upwelling Zone",
                        "lat": 9.72,
                        "lon": 75.82,
                        "depth_m": 38,
                        "quality": "HIGH",
                        "species": ["Indian Mackerel", "Oil Sardine", "Skipjack Tuna"],
                        "distance_to_user_km": 54.2,
                    }
                ],
                "best_zone": {
                    "zone_id": "PFZ-KL-001",
                    "name": "Kochi Offshore Upwelling Zone",
                    "lat": 9.72,
                    "lon": 75.82,
                },
                "safety_note": "Maintain port mooring during active storm alert.",
            },
            "navigation_result": {
                "success": True,
                "start_label": "Kochi, Kerala, India",
                "end_label": "Kochi Offshore Upwelling Zone",
                "start_coords": [9.9312, 76.2673],
                "end_coords": [9.72, 75.82],
                "total_distance_nm": 29.3,
                "total_distance_km": 54.2,
                "direct_heading_deg": 242.0,
                "direct_heading_str": "242° WSW",
                "fuel_economy": {
                    "unoptimized_distance_nm": 41.0,
                    "optimal_distance_nm": 29.3,
                    "distance_saved_nm": 11.7,
                    "fuel_unoptimized_liters": 73.8,
                    "fuel_optimal_liters": 52.7,
                    "fuel_saved_liters": 21.1,
                    "cost_saved_inr": 2047,
                    "transit_time_hours": 3.3,
                    "transit_time_str": "3h 15m",
                },
                "hazard_avoidance_active": True,
                "geofence_status": "Detour around active hazard geofence",
                "imbl_warning_active": False,
                "waypoints": [
                    {
                        "name": "Departure Mooring",
                        "lat": 9.9312,
                        "lon": 76.2673,
                        "leg_distance_nm": 0.0,
                        "leg_bearing": None,
                        "notes": "Start port",
                    },
                    {
                        "name": "Destination PFZ",
                        "lat": 9.72,
                        "lon": 75.82,
                        "leg_distance_nm": 29.3,
                        "leg_bearing": "242° WSW",
                        "notes": "Target zone",
                    },
                ],
            },
        }

    def test_format_orchestrator_response_retains_pfz_and_nav(self):
        """Verify markdown response retains PFZs and fuel card under DANGER with banners."""
        md = format_orchestrator_response(self.mock_danger_result, persona="fisherman")

        # 1. Warning banner present
        self.assertIn(
            "Navigation Suspended: Sea state / Lightning hazard active",
            md,
        )
        self.assertIn(
            "Showing direct displacement metrics for planning purposes only once weather clears",
            md,
        )

        # 2. PFZ table present with planning note
        self.assertIn("Potential Fishing Zones (INCOIS Data)", md)
        self.assertIn("Pre-Voyage Planning — Navigation Suspended", md)
        self.assertIn("Kochi Offshore Upwelling Zone", md)

        # 3. Fuel-Optimal Navigation card present with suspension planning flag
        self.assertIn("Fuel-Optimal Navigation Summary", md)
        self.assertIn("[TRANSIT SUSPENDED — BENCHMARK PLANNING ONLY]", md)
        self.assertIn("SAFETY WARNING FLAG", md)
        self.assertIn("21.1 Liters Saved", md)
        self.assertIn("₹2,047", md)

    def test_generate_map_for_result_renders_under_danger(self):
        """Verify Folium map is generated with PFZ and route even when verdict is DANGER."""
        fmap = generate_map_for_result(self.mock_danger_result, persona="fisherman")
        self.assertIsNotNone(fmap, "Map should render under DANGER planning mode")
        html = fmap.get_root().render()
        # Verify map includes user anchor and target zone
        self.assertIn("Kochi, Kerala, India", html)
        self.assertIn("Kochi Offshore Upwelling Zone", html)


if __name__ == "__main__":
    unittest.main()
