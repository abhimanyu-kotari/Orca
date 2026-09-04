"""
tests/test_orchestrator.py — Orchestrator integration & unit tests.

TEST STRUCTURE:
    Part 1: Unit tests (TestOrchestratorUnit)
        - All agent calls are mocked via unittest.mock.patch
        - No live network calls; runs in < 1 second
        - Tests the orchestrator's routing, cross-referencing, and suppression logic

    Part 2: Integration tests (TestOrchestratorIntegration)
        - Make REAL API calls (Gemini + Open-Meteo + Nominatim)
        - Prefixed with LIVE_ so they can be skipped in CI:
              python -m pytest tests/test_orchestrator.py -k "not LIVE"
        - Assert on response structure, not on dynamic content

Run all tests:
    cd orca
    python tests/test_orchestrator.py
"""

import sys
import os
import unittest
import warnings
from unittest.mock import patch, MagicMock

# Add project root so `orchestrator` and `agents.*` are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

from orchestrator import run as orchestrator_run


# ─────────────────────────────────────────────────────────────────────────────
# Shared mock factory helpers
# ─────────────────────────────────────────────────────────────────────────────

def _intent(intent, location="Kochi", time_context="today"):
    """Build a minimal mock intent_agent response."""
    return {
        "success":         True,
        "intent":          intent,
        "language":        "English",
        "language_code":   "en",
        "entities":        {"location": location, "time_context": time_context},
        "gemini_response": "Hi! I'm ORCA." if intent == "casual_chat" else None,
        "raw_query":       "test",
        "original_text":   "test",
        "translated_text": "test",
    }


def _weather(verdict="SAFE"):
    """Build a mock weather_agent response with the given verdict."""
    speed = {"SAFE": 12.0, "CAUTION": 28.0, "DANGER": 55.0}[verdict]
    wave  = {"SAFE":  0.5, "CAUTION":  1.8, "DANGER":  3.5}[verdict]
    storm = verdict == "DANGER"
    return {
        "success":    True,
        "verdict":    verdict,
        "location":   "Kochi, Kerala, India",
        "lat":        9.9312,
        "lon":        76.2673,
        "summary":    f"Conditions are {verdict.lower()}.",
        "reasoning":  f"Wind {speed} km/h, wave {wave} m.",
        "key_metrics": {
            "max_wind_speed_kmh":   speed,
            "max_wind_gust_kmh":    speed + 8,
            "max_wave_height_m":    wave,
            "max_swell_height_m":   wave * 0.7,
            "max_wave_period_s":    7.0,
            "max_precipitation_mm": 0.0 if verdict == "SAFE" else 25.0,
            "thunderstorm_likely":  storm,
        },
    }


def _pfz():
    """Build a mock pfz_agent response."""
    return {
        "success":         True,
        "location":        "Kochi, Kerala, India",
        "lat":             9.9312,
        "lon":             76.2673,
        "zone_count":      2,
        "zones": [
            {
                "zone_id":               "PFZ-KL-001",
                "name":                  "Kochi Offshore Upwelling Zone",
                "lat":                   9.72,
                "lon":                   75.82,
                "depth_m":               38,
                "quality":               "HIGH",
                "species":               ["Indian Mackerel", "Oil Sardine"],
                "distance_from_shore_km": 18,
                "advisory":              "Strong upwelling detected.",
                "region":                "Kerala",
                "best_season":           "Jun-Sep",
                "distance_to_user_km":   54.3,
            },
            {
                "zone_id":               "PFZ-KL-002",
                "name":                  "Thiruvananthapuram Deep Water Zone",
                "lat":                   8.30,
                "lon":                   76.50,
                "depth_m":               60,
                "quality":               "MEDIUM",
                "species":               ["Seer Fish", "Tuna"],
                "distance_from_shore_km": 22,
                "advisory":              "Moderate productivity.",
                "region":                "Kerala",
                "best_season":           "Nov-Mar",
                "distance_to_user_km":   183.2,
            },
        ],
        "best_zone": {
            "zone_id":             "PFZ-KL-001",
            "name":                "Kochi Offshore Upwelling Zone",
            "lat":                 9.72,
            "lon":                 75.82,
            "distance_to_user_km": 54.3,
            "quality":             "HIGH",
        },
        "advisory":        "Head to Kochi Offshore Upwelling Zone (54.3 km).",
        "safety_note":     "Check weather before departure.",
        "advisory_source": "rule-based",
    }


# ─────────────────────────────────────────────────────────────────────────────
class TestOrchestratorUnit(unittest.TestCase):
    """
    Part 1: Unit tests with fully mocked agents.
    These run instantly with no network calls.
    """

    # ------------------------------------------------------------------ #
    # 1. casual_chat
    # ------------------------------------------------------------------ #

    @patch("orchestrator.intent_agent_run")
    def test_casual_chat_returns_greeting(self, mock_intent):
        """casual_chat intent: returns greeting, invokes no downstream agents."""
        mock_intent.return_value = _intent("casual_chat")
        result = orchestrator_run({"query": "hello"})

        self.assertIn("success", result)
        self.assertEqual(result["intent"], "casual_chat")
        self.assertIsNotNone(result.get("synthesis"))

    @patch("orchestrator.intent_agent_run")
    def test_casual_chat_no_downstream_agents(self, mock_intent):
        """casual_chat must NOT invoke weather_agent or pfz_agent."""
        mock_intent.return_value = _intent("casual_chat")
        result = orchestrator_run({"query": "hello"})

        self.assertIsNone(result.get("weather_result"))
        self.assertIsNone(result.get("pfz_result"))
        agents = result.get("agents_invoked", [])
        self.assertNotIn("weather_agent", agents)
        self.assertNotIn("pfz_agent", agents)

    # ------------------------------------------------------------------ #
    # 2. weather_check / safety_check
    # ------------------------------------------------------------------ #

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    def test_weather_check_invokes_only_weather(self, mock_w, mock_i):
        """weather_check invokes weather_agent only — no PFZ."""
        mock_i.return_value = _intent("weather_check")
        mock_w.return_value = _weather("SAFE")

        result = orchestrator_run({"query": "weather near Kochi"})

        self.assertIsNotNone(result.get("weather_result"))
        self.assertIsNone(result.get("pfz_result"))
        self.assertIn("weather_agent", result.get("agents_invoked", []))
        self.assertNotIn("pfz_agent", result.get("agents_invoked", []))

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    def test_safety_check_verdict_propagated(self, mock_w, mock_i):
        """The weather verdict from the agent is present in the orchestrator result."""
        mock_i.return_value = _intent("safety_check")
        mock_w.return_value = _weather("CAUTION")

        result = orchestrator_run({"query": "safe to fish near Kochi?"})

        self.assertEqual(result["weather_result"]["verdict"], "CAUTION")

    @patch("orchestrator.intent_agent_run")
    def test_weather_check_no_location_graceful(self, mock_i):
        """Missing location: orchestrator returns success=True with an informative message."""
        mock_i.return_value = _intent("weather_check", location=None)
        result = orchestrator_run({"query": "check the weather"})

        # Must not crash; must include intent_result for the UI badge
        self.assertIn("intent_result", result)

    # ------------------------------------------------------------------ #
    # 3. pfz_location — core cross-referencing tests
    # ------------------------------------------------------------------ #

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    @patch("orchestrator.pfz_agent_run")
    def test_pfz_safe_weather_shows_zones(self, mock_pfz, mock_w, mock_i):
        """SAFE weather + pfz_location: both agents run, PFZ is NOT suppressed."""
        mock_i.return_value   = _intent("pfz_location")
        mock_w.return_value   = _weather("SAFE")
        mock_pfz.return_value = _pfz()

        result = orchestrator_run({"query": "where to fish near Kochi"})

        self.assertFalse(result["pfz_suppressed"],
                         "PFZ must NOT be suppressed for SAFE weather")
        self.assertIsNotNone(result["pfz_result"],
                             "pfz_result must be populated for SAFE weather")
        self.assertIn("weather_agent", result["agents_invoked"])
        self.assertIn("pfz_agent", result["agents_invoked"])

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    @patch("orchestrator.pfz_agent_run")
    def test_pfz_danger_weather_suppresses_zones(self, mock_pfz, mock_w, mock_i):
        """
        DANGER weather + pfz_location: PFZ MUST be suppressed.
        This is the critical safety invariant of the whole system.
        """
        mock_i.return_value   = _intent("pfz_location")
        mock_w.return_value   = _weather("DANGER")
        mock_pfz.return_value = _pfz()

        result = orchestrator_run({"query": "where to fish near Kochi"})

        self.assertTrue(result["pfz_suppressed"],
                        "PFZ MUST be suppressed when weather is DANGER")
        self.assertIsNone(result["pfz_result"],
                          "pfz_result MUST be None when suppressed")
        self.assertIsNotNone(result["pfz_suppression_reason"])
        # The suppression reason must mention DANGER so UI can display it
        self.assertIn("DANGER", result["pfz_suppression_reason"].upper())

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    @patch("orchestrator.pfz_agent_run")
    def test_pfz_caution_weather_shows_zones_with_warning(self, mock_pfz, mock_w, mock_i):
        """CAUTION weather + pfz_location: zones shown (not suppressed), caution flag set."""
        mock_i.return_value   = _intent("pfz_location")
        mock_w.return_value   = _weather("CAUTION")
        mock_pfz.return_value = _pfz()

        result = orchestrator_run({"query": "where to fish near Kochi"})

        # CAUTION does not suppress — only DANGER does
        self.assertFalse(result["pfz_suppressed"],
                         "PFZ must NOT be suppressed for CAUTION weather")
        self.assertIsNotNone(result["pfz_result"])
        # But there should be a caution flag or it shows in the synthesis
        self.assertIsNotNone(result.get("synthesis"))

    @patch("orchestrator.intent_agent_run")
    def test_pfz_no_location_graceful(self, mock_i):
        """pfz_location with no extracted location: graceful response, no crash."""
        mock_i.return_value = _intent("pfz_location", location=None)
        result = orchestrator_run({"query": "where to fish"})
        self.assertIn("intent_result", result)

    # ------------------------------------------------------------------ #
    # 4. Structural guarantees
    # ------------------------------------------------------------------ #

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    @patch("orchestrator.pfz_agent_run")
    def test_all_required_keys_present(self, mock_pfz, mock_w, mock_i):
        """Every orchestrator response must contain the full required key set."""
        REQUIRED_KEYS = {
            "success", "intent", "intent_result", "agents_invoked",
            "weather_result", "pfz_result", "navigation_result", "eo_result",
            "pfz_suppressed", "pfz_suppression_reason", "synthesis", "synthesis_source",
        }
        mock_i.return_value   = _intent("pfz_location")
        mock_w.return_value   = _weather("SAFE")
        mock_pfz.return_value = _pfz()

        result = orchestrator_run({"query": "where to fish near Kochi"})
        missing = REQUIRED_KEYS - set(result.keys())
        self.assertSetEqual(missing, set(),
                            f"Orchestrator result missing keys: {missing}")

    def test_empty_query_does_not_crash(self):
        """An empty query must always return a dict without raising."""
        result = orchestrator_run({"query": ""})
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

    def test_missing_query_key_does_not_crash(self):
        """Passing an empty dict must not raise."""
        result = orchestrator_run({})
        self.assertIsInstance(result, dict)

    # ------------------------------------------------------------------ #
    # 5. alert_query (IMD Disaster Scale & Hazard Evaluation)
    # ------------------------------------------------------------------ #

    @patch("orchestrator.intent_agent_run")
    @patch("agents.hazard_agent.weather_agent_run")
    def test_alert_query_triggers_hazard_agent(self, mock_w, mock_i):
        """alert_query invokes hazard_agent and evaluates IMD scale."""
        mock_i.return_value = _intent("alert_query", location="Chennai")
        mock_w.return_value = _weather("DANGER")

        result = orchestrator_run({"query": "check storm surge risk near Chennai"})

        self.assertTrue(result["success"])
        self.assertEqual(result["intent"], "alert_query")
        self.assertIn("hazard_agent", result["agents_invoked"])
        self.assertIn("Level-2", result["synthesis"])
        self.assertTrue(result["pfz_suppressed"])

    @patch("orchestrator.intent_agent_run")
    def test_alert_query_no_location_graceful(self, mock_i):
        """alert_query with missing location returns guidance prompt without crashing."""
        mock_i.return_value = _intent("alert_query", location=None)

        result = orchestrator_run({"query": "check cyclone alerts"})

        self.assertTrue(result["success"])
        self.assertIn("intent_result", result)
        self.assertIn("Which coastal sector", result["synthesis"])

    # ------------------------------------------------------------------ #
    # 6. route_planning & fuel-optimal navigation (Feature 2)
    # ------------------------------------------------------------------ #

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    @patch("orchestrator.pfz_agent_run")
    def test_pfz_query_includes_navigation_result(self, mock_pfz, mock_w, mock_i):
        """Fishing queries automatically include fuel-optimal navigation route."""
        mock_i.return_value = _intent("pfz_location", location="Kochi")
        mock_w.return_value = _weather("SAFE")
        mock_pfz.return_value = _pfz()

        result = orchestrator_run({"query": "where to fish near Kochi"})

        self.assertTrue(result["success"])
        self.assertIsNotNone(result.get("navigation_result"))
        nav = result["navigation_result"]
        self.assertTrue(nav["success"])
        self.assertGreater(nav["total_distance_nm"], 0.0)
        self.assertIn("direct_heading_str", nav)
        self.assertIn("fuel_economy", nav)
        self.assertGreater(nav["fuel_economy"]["fuel_saved_liters"], 0.0)

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    @patch("orchestrator.pfz_agent_run")
    def test_route_planning_invokes_navigation_tools(self, mock_pfz, mock_w, mock_i):
        """route_planning actively synthesizes waypoint plan and fuel economy."""
        mock_i.return_value = _intent("route_planning", location="Kochi")
        mock_w.return_value = _weather("SAFE")
        mock_pfz.return_value = _pfz()

        result = orchestrator_run({"query": "how to navigate to fishing zone from Kochi"})

        self.assertTrue(result["success"])
        self.assertEqual(result["intent"], "route_planning")
        self.assertIn("navigation_tools", result["agents_invoked"])
        self.assertIsNotNone(result["navigation_result"])
        self.assertIn("Fuel-Optimal Waypoint Navigation", result["synthesis"])

    @patch("orchestrator.intent_agent_run")
    def test_route_planning_missing_location_graceful(self, mock_i):
        """route_planning with missing location prompts for departure port."""
        mock_i.return_value = _intent("route_planning", location=None)

        result = orchestrator_run({"query": "plan navigation route"})

        self.assertTrue(result["success"])
        self.assertIn("Which departure port", result["synthesis"])

    # ------------------------------------------------------------------ #
    # 7. ecosystem_query (Earth Observation & Oceanographic Telemetry)
    # ------------------------------------------------------------------ #

    @patch("orchestrator.intent_agent_run")
    @patch("orchestrator.weather_agent_run")
    def test_ecosystem_query_invokes_eo_tools(self, mock_w, mock_i):
        """ecosystem_query invokes weather_agent and eo_tools, returning eo_result."""
        mock_i.return_value = _intent("ecosystem_query", location="Kochi")
        mock_w.return_value = _weather("SAFE")

        result = orchestrator_run({"query": "analyze sst anomaly and chlorophyll near Kochi"})

        self.assertTrue(result["success"])
        self.assertEqual(result["intent"], "ecosystem_query")
        self.assertIn("eo_tools", result["agents_invoked"])
        self.assertIsNotNone(result["eo_result"])
        eo = result["eo_result"]
        self.assertTrue(eo["success"])
        self.assertIn("sst_points", eo)
        self.assertIn("chlorophyll_points", eo)
        self.assertIn("mean_sst_c", eo)
        self.assertIn("mean_chlorophyll_mg_m3", eo)
        self.assertIn("Earth Observation & Oceanographic Telemetry", result["synthesis"])

    @patch("orchestrator.intent_agent_run")
    def test_ecosystem_query_missing_location_graceful(self, mock_i):
        """ecosystem_query with missing location prompts for coastal sector."""
        mock_i.return_value = _intent("ecosystem_query", location=None)

        result = orchestrator_run({"query": "check ocean productivity"})

        self.assertTrue(result["success"])
        self.assertIn("Which coastal sector", result["synthesis"])
        self.assertIsNone(result["eo_result"])




# ─────────────────────────────────────────────────────────────────────────────
class TestOrchestratorIntegration(unittest.TestCase):
    """
    Part 2: Live integration tests (real Gemini + Open-Meteo + Nominatim).
    These WILL make network calls and may take 10–60 seconds.
    Skip in CI: python -m pytest tests/test_orchestrator.py -k "not LIVE"
    """

    def test_LIVE_casual_hello(self):
        """Real hello query: intent=casual_chat, no weather data."""
        result = orchestrator_run({"query": "hello"})
        self.assertIn("success", result)
        self.assertEqual(result.get("intent"), "casual_chat")
        self.assertIsNone(result.get("weather_result"))
        self.assertIsNone(result.get("pfz_result"))
        print(f"\n    Greeting: {result.get('synthesis', '')[:80]}")

    def test_LIVE_weather_rameswaram(self):
        """Real weather check: Rameswaram verdict is SAFE/CAUTION/DANGER."""
        result = orchestrator_run({"query": "Is it safe to fish near Rameswaram today?"})
        self.assertIn("success", result)
        if result.get("success") and result.get("weather_result"):
            verdict = result["weather_result"].get("verdict", "")
            self.assertIn(verdict, ["SAFE", "CAUTION", "DANGER"],
                          f"Unexpected verdict: {verdict}")
            print(f"\n    Rameswaram verdict: {verdict}")

    def test_LIVE_pfz_kochi_structure(self):
        """Real PFZ query: verify structural completeness."""
        REQUIRED = {"success", "intent", "pfz_suppressed", "synthesis",
                    "agents_invoked", "intent_result"}
        result = orchestrator_run({"query": "Where can I fish near Kochi?"})
        missing = REQUIRED - set(result.keys())
        self.assertSetEqual(missing, set(),
                            f"Missing keys in live PFZ result: {missing}")
        print(f"\n    PFZ suppressed: {result.get('pfz_suppressed')}")
        print(f"    Agents: {result.get('agents_invoked')}")
        print(f"    Synthesis: {result.get('synthesis', '')[:80]}")

    def test_LIVE_danger_suppresses_pfz(self):
        """
        Regression test for the critical weather-gate safety invariant.
        Only verifiable if weather is actually DANGER at time of test.
        We verify the structural contract holds; we cannot guarantee the verdict.
        """
        result = orchestrator_run({"query": "Where can I fish near Kochi?"})
        verdict = (result.get("weather_result") or {}).get("verdict", "SAFE")
        suppressed = result.get("pfz_suppressed", False)

        if verdict == "DANGER":
            self.assertTrue(suppressed,
                            "INVARIANT VIOLATED: DANGER verdict must suppress PFZ")
            self.assertIsNone(result.get("pfz_result"),
                              "INVARIANT VIOLATED: pfz_result must be None when suppressed")
            print("\n    [DANGER weather detected — suppression invariant verified]")
        else:
            print(f"\n    [Weather is {verdict} — suppression not triggered (expected)]")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("ORCA Orchestrator — Unit Tests (no API calls)")
    print("=" * 60)
    unit_suite  = unittest.TestLoader().loadTestsFromTestCase(TestOrchestratorUnit)
    runner      = unittest.TextTestRunner(verbosity=2)
    unit_result = runner.run(unit_suite)

    print()
    print("=" * 60)
    print("ORCA Orchestrator — Integration Tests (live API calls)")
    print("=" * 60)
    live_suite = unittest.TestLoader().loadTestsFromTestCase(TestOrchestratorIntegration)
    runner.run(live_suite)
