"""
tests/test_geocoding_lock.py — Tests for Indian Coastal Geocoding Lock & Fallback Handling.

Covers:
1. Geocoder Country Restriction: geocode() called with country_codes='in'.
2. Query Appending: ", coastal India" automatically appended to prioritize coastal ports.
3. Fallback Logic: When location is not found in India, returns:
   "Location not found in Indian coastal regions. Please check the spelling (e.g., Kundapura)."
4. Intent Agent Typo Tolerance: "Kundpura" resolves to "Kundapura".
5. Orchestrator Graceful Handling: Unresolvable locations return graceful error message.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.weather_tools import get_coordinates
from agents.intent_agent import _extract_location_from_text, _resolve_location_candidate
from orchestrator import run as orchestrator_run


class TestGeocodingLock(unittest.TestCase):

    @patch("tools.weather_tools.Nominatim")
    def test_country_restriction_and_query_appending(self, mock_nominatim_cls):
        """Verify country_codes='in' and ', coastal India' appending."""
        mock_geocoder = MagicMock()
        mock_nominatim_cls.return_value = mock_geocoder

        mock_result = MagicMock()
        mock_result.address = "Kundapura, Udupi, Karnataka, India"
        mock_result.latitude = 13.6288
        mock_result.longitude = 74.6931
        mock_geocoder.geocode.return_value = mock_result

        res = get_coordinates("Kundapura")

        self.assertTrue(res["success"])
        self.assertEqual(res["lat"], 13.6288)
        self.assertEqual(res["lon"], 74.6931)

        called_args, called_kwargs = mock_geocoder.geocode.call_args_list[0]
        self.assertEqual(called_args[0], "Kundapura, coastal India")
        self.assertEqual(called_kwargs.get("country_codes"), "in")

    @patch("tools.weather_tools.Nominatim")
    def test_query_already_containing_coastal_india(self, mock_nominatim_cls):
        """Verify query is not double-appended if it already ends with coastal India."""
        mock_geocoder = MagicMock()
        mock_nominatim_cls.return_value = mock_geocoder

        mock_result = MagicMock()
        mock_result.address = "Kochi, Kerala, India"
        mock_result.latitude = 9.9679
        mock_result.longitude = 76.2444
        mock_geocoder.geocode.return_value = mock_result

        res = get_coordinates("Kochi, coastal India")
        self.assertTrue(res["success"])

        called_args, called_kwargs = mock_geocoder.geocode.call_args_list[0]
        self.assertEqual(called_args[0], "Kochi, coastal India")
        self.assertEqual(called_kwargs.get("country_codes"), "in")

    @patch("tools.weather_tools.Nominatim")
    def test_fallback_when_not_found_in_india(self, mock_nominatim_cls):
        """When Nominatim returns None for all attempts, return graceful coastal error."""
        mock_geocoder = MagicMock()
        mock_nominatim_cls.return_value = mock_geocoder
        mock_geocoder.geocode.return_value = None

        res = get_coordinates("NonExistentPlaceXYZ")

        self.assertFalse(res["success"])
        self.assertIn("Location not found in Indian coastal regions", res["error"])
        self.assertIn("Please check the spelling (e.g., Kundapura)", res["error"])

    @patch("tools.weather_tools.Nominatim")
    def test_empty_location_returns_graceful_error(self, mock_nominatim_cls):
        """Empty or whitespace-only location returns graceful error."""
        res = get_coordinates("   ")
        self.assertFalse(res["success"])
        self.assertIn("Location not found in Indian coastal regions", res["error"])

    @patch("tools.weather_tools.Nominatim")
    def test_fallback_cascade_if_coastal_query_none(self, mock_nominatim_cls):
        """If ', coastal India' returns None, geocoder falls back to ', India' and raw query with country_codes='in'."""
        mock_geocoder = MagicMock()
        mock_nominatim_cls.return_value = mock_geocoder

        mock_result = MagicMock()
        mock_result.address = "Kundapura, Udupi, Karnataka, India"
        mock_result.latitude = 13.6288
        mock_result.longitude = 74.6931

        mock_geocoder.geocode.side_effect = [None, mock_result]

        res = get_coordinates("Kundapura")
        self.assertTrue(res["success"])
        self.assertEqual(res["location"], "Kundapura, Udupi, Karnataka, India")

        self.assertEqual(mock_geocoder.geocode.call_count, 2)
        call1_args, call1_kwargs = mock_geocoder.geocode.call_args_list[0]
        call2_args, call2_kwargs = mock_geocoder.geocode.call_args_list[1]
        self.assertEqual(call1_args[0], "Kundapura, coastal India")
        self.assertEqual(call1_kwargs.get("country_codes"), "in")
        self.assertEqual(call2_args[0], "Kundapura, India")
        self.assertEqual(call2_kwargs.get("country_codes"), "in")

    def test_intent_agent_typo_tolerance_for_kundpura(self):
        """Verify intent agent resolves 'Kundpura' typo to 'Kundapura'."""
        resolved = _resolve_location_candidate("kundpura")
        self.assertEqual(resolved, "Kundapura")

        extracted = _extract_location_from_text("where can I fish near Kundpura today?")
        self.assertEqual(extracted, "Kundapura")

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    @patch("orchestrator.pfz_agent_run")
    def test_orchestrator_unresolvable_location_error(self, mock_pfz, mock_w, mock_i):
        """Orchestrator returns graceful error when location geocoding fails."""
        mock_i.return_value = {
            "success": True,
            "intent": "pfz_location",
            "confidence": 0.9,
            "entities": {"location": "InvalidOceanPlace123", "time_context": "today"},
            "reasoning": "Fishing query",
            "language": "en",
        }
        err_msg = "Location not found in Indian coastal regions. Please check the spelling (e.g., Kundapura)."
        mock_w.return_value = {"success": False, "error": err_msg}
        mock_pfz.return_value = {"success": False, "error": err_msg}

        res = orchestrator_run({"query": "where to fish in InvalidOceanPlace123"})
        self.assertFalse(res["success"])
        self.assertIn("Location not found in Indian coastal regions", res["synthesis"])
        self.assertIn("Please check the spelling (e.g., Kundapura)", res["synthesis"])


if __name__ == "__main__":
    unittest.main()
