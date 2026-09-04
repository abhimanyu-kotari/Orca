"""
tests/test_expanded_pfz.py — Comprehensive tests for the expanded PFZ database (70 zones).
Validates schema compliance, geographical coverage, and local harbor resolution
with special focus on Karnataka regional hubs (Kundapura, Malpe, Karwar, etc.).
"""

import unittest
from tools.pfz_tools import get_all_zones, find_nearest_zones, haversine_km


class TestExpandedPFZDatabase(unittest.TestCase):

    def setUp(self):
        self.all_zones = get_all_zones()

    def test_database_size_exceeds_50_zones(self):
        """Verify the mock database contains well over 50 comprehensive coastal harbors."""
        self.assertGreaterEqual(
            len(self.all_zones),
            50,
            f"Expected at least 50 zones, got {len(self.all_zones)}"
        )

    def test_schema_conformance(self):
        """
        Verify each record has the requested schema:
        id, name, lat, lon, depth, species, status,
        along with backward-compatible fields: zone_id, depth_m, quality, region.
        """
        required_keys = {"id", "name", "lat", "lon", "depth", "species", "status"}
        compat_keys = {"zone_id", "depth_m", "quality", "region"}

        for z in self.all_zones:
            for k in required_keys:
                self.assertIn(k, z, f"Missing required key '{k}' in zone {z.get('id', z.get('name'))}")
            for k in compat_keys:
                self.assertIn(k, z, f"Missing compat key '{k}' in zone {z.get('id', z.get('name'))}")

            # Types and value validity
            self.assertIsInstance(z["id"], str)
            self.assertIsInstance(z["name"], str)
            self.assertIsInstance(z["lat"], (int, float))
            self.assertIsInstance(z["lon"], (int, float))
            self.assertIsInstance(z["depth"], (int, float))
            self.assertIn(z["status"], {"HIGH", "MEDIUM", "LOW"})
            self.assertEqual(z["id"], z["zone_id"])
            self.assertEqual(z["depth"], z["depth_m"])
            self.assertEqual(z["status"], z["quality"])

    def test_kundapura_resolves_to_local_gangolli_harbor(self):
        """
        Typing local coastal towns like Kundapura must instantly map to local harbors
        (Gangolli / Kundapura Inshore Bank) rather than defaulting to distant hubs like Mangalore.
        """
        # Kundapura town center GPS coordinates (~13.6268° N, 74.6908° E)
        kundapura_lat = 13.6268
        kundapura_lon = 74.6908

        nearest = find_nearest_zones(kundapura_lat, kundapura_lon, max_results=3)
        self.assertTrue(len(nearest) > 0, "Should find zones near Kundapura")

        top_zone = nearest[0]
        # Should be Gangolli / Kundapura Inshore Bank (PFZ-KA-002)
        self.assertEqual(top_zone["id"], "PFZ-KA-002")
        self.assertIn("Kundapura", top_zone["name"])
        # Should be within 15 km of Kundapura town
        self.assertLess(top_zone["distance_to_user_km"], 15.0)

    def test_malpe_and_udupi_local_resolution(self):
        """Udupi / Malpe (~13.35° N, 74.70° E) resolves to Malpe harbor grounds."""
        nearest = find_nearest_zones(13.3500, 74.7000, max_results=2)
        self.assertTrue(any("Malpe" in z["name"] or "Udupi" in z["name"] for z in nearest))
        self.assertLess(nearest[0]["distance_to_user_km"], 20.0)

    def test_karwar_local_resolution(self):
        """Karwar (~14.81° N, 74.13° E) resolves to Karwar Baithkol / Ridge."""
        nearest = find_nearest_zones(14.8100, 74.1300, max_results=2)
        self.assertTrue(any("Karwar" in z["name"] for z in nearest))
        self.assertLess(nearest[0]["distance_to_user_km"], 15.0)

    def test_honnavar_local_resolution(self):
        """Honnavar (~14.28° N, 74.44° E) resolves to Honnavar Sharavathi bank."""
        nearest = find_nearest_zones(14.2800, 74.4400, max_results=2)
        self.assertTrue(any("Honnavar" in z["name"] for z in nearest))
        self.assertLess(nearest[0]["distance_to_user_km"], 15.0)

    def test_bhatkal_local_resolution(self):
        """Bhatkal (~13.98° N, 74.55° E) resolves to Bhatkal harbor grounds."""
        nearest = find_nearest_zones(13.9800, 74.5500, max_results=2)
        self.assertTrue(any("Bhatkal" in z["name"] for z in nearest))
        self.assertLess(nearest[0]["distance_to_user_km"], 15.0)

    def test_kumta_local_resolution(self):
        """Kumta (~14.42° N, 74.41° E) resolves to Kumta Aghanashini grounds."""
        nearest = find_nearest_zones(14.4200, 74.4100, max_results=2)
        self.assertTrue(any("Kumta" in z["name"] for z in nearest))
        self.assertLess(nearest[0]["distance_to_user_km"], 15.0)

    def test_regional_coverage_across_india(self):
        """Verify presence of zones for all major requested coastal regions."""
        regions = {z.get("region") for z in self.all_zones}
        expected_regions = {
            "Karnataka",
            "Kerala",
            "Goa",
            "Maharashtra",
            "Gujarat",
            "Tamil Nadu",
            "Andhra Pradesh",
            "Odisha",
            "West Bengal",
            "Andaman & Nicobar Islands",
        }
        for reg in expected_regions:
            self.assertIn(reg, regions, f"Missing zones for region {reg}")


if __name__ == "__main__":
    unittest.main()
