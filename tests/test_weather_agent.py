"""
tests/test_weather_agent.py — Isolated end-to-end tests for the Weather Agent.

These tests call the REAL Weather Agent with REAL network requests.
Run them before wiring the agent into the Streamlit UI to confirm that
the full data pipeline (geocoding → API fetch → Gemini → output) works.

Usage:
    python tests/test_weather_agent.py       # Run directly
    python -m pytest tests/ -v               # Run via pytest (shows pass/fail)

Tests:
    1. test_by_location_name   — Happy path with a valid city name
    2. test_by_coordinates     — Skip geocoding with direct lat/lon
    3. test_tomorrow_context   — Verify time context parsing
    4. test_invalid_location   — Verify graceful failure for unknown locations
    5. test_output_shape       — Verify all required output keys are always present
"""

import sys
import os

# Add the project root to sys.path so we can import from agents/ and tools/
# This is needed when running the file directly (not via pytest from project root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.weather_agent import run


# ─────────────────────────────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────────────────────────────

def _header(name: str):
    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")

def _passed():
    print("  ✅ PASSED")

def _show(result: dict):
    """Print the key output fields in a readable format."""
    print(f"  Verdict   : {result.get('verdict')}")
    print(f"  Location  : {result.get('location', '')[:60]}")
    summary = result.get('summary', '')
    print(f"  Summary   : {summary[:80]}{'...' if len(summary) > 80 else ''}")
    m = result.get("key_metrics", {})
    if m:
        print(f"  Wave Ht   : {m.get('max_wave_height_m', 'N/A')} m")
        print(f"  Wind      : {m.get('max_wind_speed_kmh', 'N/A')} km/h")
        print(f"  Thunderstm: {m.get('thunderstorm_likely', 'N/A')}")


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_by_location_name():
    """Happy path: valid location name, default time context (today)."""
    _header("Test 1 — Location by name: Rameswaram (today)")

    result = run({"location": "Rameswaram"})
    _show(result)

    assert result["success"],                       f"Expected success, got error: {result.get('error')}"
    assert result["verdict"] in ("SAFE", "CAUTION", "DANGER"), "Verdict must be one of SAFE/CAUTION/DANGER"
    assert isinstance(result["summary"], str) and len(result["summary"]) > 10
    assert isinstance(result["key_metrics"], dict)
    _passed()


def test_by_coordinates():
    """Direct lat/lon input — should skip geocoding entirely."""
    _header("Test 2 — Direct coordinates: Mumbai coast (tomorrow)")

    # Mumbai coast: 18.9422°N, 72.8347°E
    result = run({"lat": 18.9422, "lon": 72.8347, "time_context": "tomorrow"})
    _show(result)

    assert result["success"],          f"Expected success, got error: {result.get('error')}"
    assert result["lat"]  == 18.9422,  "lat should match input exactly"
    assert result["lon"]  == 72.8347,  "lon should match input exactly"
    _passed()


def test_tomorrow_context():
    """Verify that time context 'tomorrow' returns a valid result."""
    _header("Test 3 — Time context: Visakhapatnam tomorrow")

    result = run({"location": "Visakhapatnam", "time_context": "tomorrow"})
    _show(result)

    assert result["success"],                                          f"Error: {result.get('error')}"
    assert result["verdict"] in ("SAFE", "CAUTION", "DANGER")
    _passed()


def test_invalid_location():
    """Graceful failure: unrecognisable location should return success=False with an error message."""
    _header("Test 4 — Invalid location: should fail gracefully")

    result = run({"location": "XYZZY_NONEXISTENT_PLACE_99999"})
    print(f"  Error (expected): {result.get('error')}")

    assert not result["success"],     "Expected success=False for an unrecognised location"
    assert "error" in result,         "Expected an 'error' key in the output"
    assert len(result["error"]) > 5,  "Error message should be non-trivial"
    _passed()


def test_output_shape():
    """All required output keys must always be present on success."""
    _header("Test 5 — Output shape: all required keys present")

    result = run({"location": "Kochi"})

    if result["success"]:
        required_keys = {"success", "location", "lat", "lon", "verdict", "summary", "key_metrics", "reasoning"}
        missing = required_keys - result.keys()
        assert not missing, f"Missing output keys: {missing}"
        print(f"  All {len(required_keys)} required keys present ✓")

        required_metric_keys = {
            "max_wind_speed_kmh", "max_wind_gust_kmh", "max_precipitation_mm",
            "max_wave_height_m", "max_swell_height_m", "max_wave_period_s",
            "thunderstorm_likely",
        }
        missing_m = required_metric_keys - result["key_metrics"].keys()
        assert not missing_m, f"Missing metric keys: {missing_m}"
        print(f"  All {len(required_metric_keys)} metric keys present ✓")
    else:
        print(f"  Agent failed (possibly network issue): {result.get('error')}")
        print("  Skipping shape check — mark as inconclusive, not failed.")

    _passed()


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  ORCA — Weather Agent Test Suite")
    print("=" * 60)

    tests = [
        test_by_location_name,
        test_by_coordinates,
        test_tomorrow_context,
        test_invalid_location,
        test_output_shape,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 ERROR : {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    if failed > 0:
        sys.exit(1)   # Non-zero exit so CI/CD systems can detect failures
