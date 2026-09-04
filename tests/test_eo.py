"""
tests/test_eo.py — Unit tests for tools/eo_tools.py
"""

import unittest
from tools.eo_tools import generate_eo_grid, get_eo_legend_html


class TestEarthObservationTools(unittest.TestCase):
    def test_generate_eo_grid_kochi(self):
        """Test EO grid generation for Kochi (West Coast / Arabian Sea)."""
        res = generate_eo_grid(center_lat=9.9312, center_lon=76.2673, radius_km=100.0, step_km=15.0)

        self.assertTrue(res["success"])
        self.assertGreater(res["grid_points_count"], 10)
        self.assertEqual(len(res["sst_points"]), res["grid_points_count"])
        self.assertEqual(len(res["chlorophyll_points"]), res["grid_points_count"])

        # Check SST bounds
        self.assertGreaterEqual(res["min_sst_c"], 26.5)
        self.assertLessEqual(res["max_sst_c"], 30.5)
        self.assertGreaterEqual(res["mean_sst_c"], 26.5)
        self.assertLessEqual(res["mean_sst_c"], 30.5)

        # Check Chlorophyll-a bounds
        self.assertGreaterEqual(res["mean_chlorophyll_mg_m3"], 0.10)
        self.assertLessEqual(res["max_chlorophyll_mg_m3"], 3.80)

        # Check normalized heatmap values are strictly [0.0, 1.0]
        for pt in res["sst_points"]:
            self.assertEqual(len(pt), 3)
            self.assertGreaterEqual(pt[2], 0.0)
            self.assertLessEqual(pt[2], 1.0)

        for pt in res["chlorophyll_points"]:
            self.assertEqual(len(pt), 3)
            self.assertGreaterEqual(pt[2], 0.0)
            self.assertLessEqual(pt[2], 1.0)

        # Check upwelling front coords
        front = res["upwelling_front_coords"]
        self.assertEqual(len(front), 2)
        self.assertAlmostEqual(front[0], 9.9312, delta=2.0)

        # Check sensor metadata
        self.assertIn("Oceansat-3", res["sensor_metadata"]["ocean_color_sensor"])
        self.assertIn("Sentinel-3", res["sensor_metadata"]["sst_sensor"])

    def test_generate_eo_grid_chennai(self):
        """Test EO grid generation for Chennai (East Coast / Bay of Bengal)."""
        res = generate_eo_grid(center_lat=13.0827, center_lon=80.2707, radius_km=80.0, step_km=20.0)

        self.assertTrue(res["success"])
        self.assertGreater(res["grid_points_count"], 5)
        self.assertIn("thermocline_depth_m", res)
        self.assertIn("upwelling_intensity", res)

    def test_get_eo_legend_html(self):
        """Test floating legend HTML generation."""
        legend_html = get_eo_legend_html()
        self.assertIsInstance(legend_html, str)
        self.assertIn("Earth Observation Color Scales", legend_html)
        self.assertIn("Sea Surface Temp", legend_html)
        self.assertIn("Chlorophyll-a", legend_html)
        self.assertIn("Oceansat-3", legend_html)


if __name__ == "__main__":
    unittest.main()
