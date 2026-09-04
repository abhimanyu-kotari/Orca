"""
agents/weather_agent.py — Weather & Marine Safety Agent

─────────────────────────────────────────────────────────────────────────────
RESPONSIBILITY
─────────────────────────────────────────────────────────────────────────────
Given a location and a time window, this agent:
    1. Resolves the location to GPS coordinates (via tools/weather_tools.py)
    2. Fetches live atmospheric + marine forecast data (Open-Meteo, no key)
    3. Extracts peak metrics over the requested time window
    4. Applies rule-based thresholds (fast, transparent pre-check)
    5. Sends metrics + rule verdict to Gemini for a human-readable analysis
    6. Returns a single structured dict with verdict, summary, and reasoning

─────────────────────────────────────────────────────────────────────────────
INTERFACE — all agents in ORCA follow this contract:
─────────────────────────────────────────────────────────────────────────────
    run(inputs: dict) -> dict

INPUTS (dict keys):
    "location"     (str,   optional) : Place name, e.g. "Rameswaram"
    "lat"          (float, optional) : Direct latitude  — skips geocoding
    "lon"          (float, optional) : Direct longitude — skips geocoding
    "time_context" (str,   optional) : "today" | "tomorrow" | "3 days"
                                       Default: "today"

    NOTE: Provide either "location" OR ("lat" + "lon"). Not both required.

OUTPUTS (dict keys):
    "success"      (bool)  : True if the agent completed without fatal error
    "location"     (str)   : Human-readable resolved location name
    "lat"          (float) : Latitude used for API calls
    "lon"          (float) : Longitude used for API calls
    "verdict"      (str)   : "SAFE" | "CAUTION" | "DANGER"
    "summary"      (str)   : 2–3 sentence plain-language safety assessment
    "key_metrics"  (dict)  : Peak numeric values used for the assessment
    "reasoning"    (str)   : Bullet-point explanation of why this verdict
    "error"        (str)   : Only present when success=False
"""

import json
import httpx
from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from tools.weather_tools import (
    get_coordinates,
    fetch_atmospheric_weather,
    fetch_marine_conditions,
    extract_conditions_for_window,
)

# ─────────────────────────────────────────────────────────────────────────────
# One-time Gemini client setup (google-genai SDK v2+)
# ─────────────────────────────────────────────────────────────────────────────
# We create the client once at module import time and reuse it for every
# run() call. The new SDK uses google.genai.Client instead of the deprecated
# google.generativeai.GenerativeModel pattern.

# google-genai's HttpOptions.timeout only accepts a plain integer (seconds).
# It maps this to its own internal httpx transport — we cannot pass an
# httpx.Timeout object directly (Pydantic rejects it with a ValidationError).
# 60 s covers both the SSL handshake and the Gemini response read on slow links.
_GEMINI_TIMEOUT_S: int = 60

_gemini = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={"timeout": _GEMINI_TIMEOUT_S},
)


# ─────────────────────────────────────────────────────────────────────────────
# Safety thresholds for small fishing vessels
# Source: IMD / INCOIS marine safety advisories
# ─────────────────────────────────────────────────────────────────────────────
THRESHOLDS = {
    # Wind speed at 10 m above sea level (km/h)
    "wind_danger_kmh":     40,   # Beaufort 8 — Gale: dangerous for all small craft
    "wind_caution_kmh":    25,   # Beaufort 6 — Strong breeze: small vessel caution

    # Significant wave height (m)
    "wave_danger_m":      2.5,   # > 2.5 m: dangerous for most fishing boats
    "wave_caution_m":     1.5,   # > 1.5 m: caution advisory

    # Hourly precipitation (mm)
    "rain_heavy_mm":       20,   # > 20 mm/hr: heavy rain, poor visibility
}

# WMO weather codes that indicate thunderstorm activity.
# See: https://open-meteo.com/en/docs (search "WMO Weather interpretation codes")
THUNDERSTORM_CODES = {95, 96, 99}


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_time_context(time_context: str) -> tuple[int, int]:
    """
    Map a natural language time string to a (start_hour, window_hours) tuple.

    This tells extract_conditions_for_window() which slice of the 72-hour
    hourly forecast array to analyse.

    Args:
        time_context (str): "today" | "tomorrow" | "3 days" (case-insensitive)

    Returns:
        (start_hour, window_hours)
            start_hour   — index into the hourly array (0 = now)
            window_hours — number of hours to analyse

    Examples:
        "today"    → (0,  24)   # next 24 hours
        "tomorrow" → (24, 24)   # hours 24 to 48
        "3 days"   → (0,  72)   # full 3-day horizon
    """
    ctx = (time_context or "today").lower().strip()

    if "tomorrow" in ctx:
        return 24, 24
    elif any(k in ctx for k in ["2 day", "two day"]):
        return 48, 24
    elif any(k in ctx for k in ["3 day", "three day", "week"]):
        return 0, 72
    else:
        return 0, 24   # Default: today


def _compute_peak_metrics(atmo_window: dict, marine_window: dict) -> dict:
    """
    Extract the worst-case (peak) value for each key metric over a time window.

    We pass these peaks to Gemini so it reasons over concrete numbers, not raw
    time-series arrays (which would consume too many tokens and be harder to reason over).

    Args:
        atmo_window   (dict): Sliced atmospheric hourly data.
        marine_window (dict): Sliced marine hourly data.

    Returns:
        A flat dict of peak metric values, e.g.:
            {
                "max_wind_speed_kmh":  32.5,
                "max_wind_gust_kmh":   41.0,
                "max_precipitation_mm": 5.2,
                "max_wave_height_m":    1.8,
                "max_swell_height_m":   1.2,
                "max_wave_period_s":   10.0,
                "thunderstorm_likely": False,
            }
    """
    def safe_max(data: dict, key: str, default: float = 0.0) -> float:
        """Return the max of a list, safely ignoring None values."""
        values = data.get(key, [])
        valid  = [v for v in values if v is not None]
        return max(valid) if valid else default

    def any_thunderstorm(data: dict) -> bool:
        """Return True if any hourly weather code indicates a thunderstorm."""
        codes = data.get("weather_code", [])
        return any(int(c) in THUNDERSTORM_CODES for c in codes if c is not None)

    return {
        "max_wind_speed_kmh":   safe_max(atmo_window,   "wind_speed_10m"),
        "max_wind_gust_kmh":    safe_max(atmo_window,   "wind_gusts_10m"),
        "max_precipitation_mm": safe_max(atmo_window,   "precipitation"),
        "max_wave_height_m":    safe_max(marine_window, "wave_height"),
        "max_swell_height_m":   safe_max(marine_window, "swell_wave_height"),
        "max_wave_period_s":    safe_max(marine_window, "wave_period"),
        "thunderstorm_likely":  any_thunderstorm(atmo_window),
    }


def _rule_based_verdict(metrics: dict) -> str:
    """
    Fast, transparent rule-based safety verdict — runs before Gemini.

    WHY: Rules are auditable and fast. We inject this verdict into the Gemini
    prompt as a "starting point" so Gemini focuses on explanation, not
    re-deriving the classification from scratch.

    DANGER conditions (any one is sufficient):
        - Thunderstorm forecast
        - Wind speed ≥ 40 km/h  (Beaufort 8, Gale-force)
        - Wave height ≥ 2.5 m

    CAUTION conditions (any one, if no DANGER):
        - Wind speed ≥ 25 km/h  (Beaufort 6)
        - Wave height ≥ 1.5 m
        - Precipitation ≥ 20 mm/hr

    Returns:
        "SAFE" | "CAUTION" | "DANGER"
    """
    if (
        metrics["thunderstorm_likely"]
        or metrics["max_wind_speed_kmh"]  >= THRESHOLDS["wind_danger_kmh"]
        or metrics["max_wave_height_m"]   >= THRESHOLDS["wave_danger_m"]
    ):
        return "DANGER"

    if (
        metrics["max_wind_speed_kmh"]     >= THRESHOLDS["wind_caution_kmh"]
        or metrics["max_wave_height_m"]   >= THRESHOLDS["wave_caution_m"]
        or metrics["max_precipitation_mm"] >= THRESHOLDS["rain_heavy_mm"]
    ):
        return "CAUTION"

    return "SAFE"


def _ask_gemini(location: str, time_context: str, metrics: dict, rule_verdict: str) -> dict:
    """
    Call Gemini to produce a plain-language safety analysis.

    WHAT GEMINI DOES HERE:
        - Confirms or refines the rule-based verdict (rarely overrides it)
        - Writes a friendly 2–3 sentence summary a fisherman can act on
        - Produces a concise bullet-point reasoning trail

    WHAT GEMINI DOES NOT DO:
        - It does NOT fetch live data (the tools layer already did that)
        - It does NOT invent numbers (all metrics are injected as facts)

    The prompt asks for strict JSON output to make parsing reliable.

    Args:
        location     (str):  Resolved location name
        time_context (str):  "today" | "tomorrow" | "3 days"
        metrics      (dict): Peak metric values from _compute_peak_metrics()
        rule_verdict (str):  Pre-computed verdict from _rule_based_verdict()

    Returns:
        {
            "verdict":   "SAFE" | "CAUTION" | "DANGER",
            "summary":   "...",
            "reasoning": "..."
        }
        Falls back to rule-based values if Gemini fails or returns invalid JSON.
    """
    prompt = f"""
You are ORCA, a friendly and reliable marine safety advisor for Indian fishermen.
Analyze the following forecast data and provide a safety assessment.

Location    : {location}
Time Window : {time_context}

--- Forecast Peak Metrics ---
Max Wind Speed       : {metrics['max_wind_speed_kmh']:.1f} km/h
Max Wind Gust        : {metrics['max_wind_gust_kmh']:.1f} km/h
Max Wave Height      : {metrics['max_wave_height_m']:.2f} m
Max Swell Height     : {metrics['max_swell_height_m']:.2f} m
Max Wave Period      : {metrics['max_wave_period_s']:.1f} s
Max Precipitation    : {metrics['max_precipitation_mm']:.1f} mm/hr
Thunderstorm Likely  : {metrics['thunderstorm_likely']}

--- Rule-Based Starting Verdict ---
{rule_verdict}

--- Your Task ---
1. Review the metrics above and confirm or refine the verdict.
2. Write a 2–3 sentence "summary" in plain language that a fisherman with
   no technical background can immediately understand and act upon.
   Mention the most important hazard if conditions are not SAFE.
3. Write "reasoning" as 3–5 bullet points explaining the key factors
   behind this verdict.

Respond ONLY with a valid JSON object — no markdown fences, no extra text:
{{
  "verdict":   "SAFE" | "CAUTION" | "DANGER",
  "summary":   "...",
  "reasoning": "..."
}}
"""

    try:
        # Per-request timeout reuses the same _GEMINI_TIMEOUT object defined at
        # module level, so both the Client transport and this call share identical
        # ceiling values — no accidental mismatch.
        response   = _gemini.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"http_options": {"timeout": _GEMINI_TIMEOUT_S}},
        )
        # Strip any markdown code fences Gemini sometimes adds despite instructions
        clean_text = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed     = json.loads(clean_text)

        # Validate that required keys are present
        if not all(k in parsed for k in ("verdict", "summary", "reasoning")):
            raise ValueError("Gemini response missing required keys.")

        return parsed

    except (TimeoutError, httpx.TimeoutException):
        # BUG FIX: httpx raises httpx.ConnectTimeout (a subclass of
        # httpx.TimeoutException), NOT Python's built-in TimeoutError.
        # The previous bare `except TimeoutError` never matched, so the SSL
        # timeout fell through to the generic Exception handler below and
        # dumped the raw "_ssl.c:1059" traceback string into the UI.
        return {
            "verdict":   rule_verdict,
            "summary":   (
                f"Gemini connection timed out (SSL handshake or read >60 s). "
                f"Showing rule-based result: {rule_verdict}. "
                f"Peak wave: {metrics['max_wave_height_m']:.2f} m, "
                f"peak wind: {metrics['max_wind_speed_kmh']:.1f} km/h."
            ),
            "reasoning": (
                f"• Gemini API timed out during SSL/TLS handshake or response read.\n"
                f"• Rule-based verdict ({rule_verdict}) applied using IMD/INCOIS thresholds.\n"
                f"• Peak wind {metrics['max_wind_speed_kmh']:.1f} km/h "
                f"(danger threshold: {THRESHOLDS['wind_danger_kmh']} km/h)\n"
                f"• Peak wave {metrics['max_wave_height_m']:.2f} m "
                f"(danger threshold: {THRESHOLDS['wave_danger_m']} m)"
            ),
        }

    except (json.JSONDecodeError, ValueError, Exception) as e:
        # Catch-all for bad JSON, missing keys, unexpected API errors, etc.
        return {
            "verdict":   rule_verdict,
            "summary":   (
                f"Conditions for {location} assessed from live forecast data. "
                f"Peak wave height: {metrics['max_wave_height_m']:.2f} m, "
                f"peak wind: {metrics['max_wind_speed_kmh']:.1f} km/h."
            ),
            "reasoning": (
                f"• AI explanation unavailable ({type(e).__name__}: {e})\n"
                f"• Rule-based verdict applied using IMD/INCOIS thresholds.\n"
                f"• Peak wind {metrics['max_wind_speed_kmh']:.1f} km/h "
                f"(danger threshold: {THRESHOLDS['wind_danger_kmh']} km/h)\n"
                f"• Peak wave {metrics['max_wave_height_m']:.2f} m "
                f"(danger threshold: {THRESHOLDS['wave_danger_m']} m)"
            ),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(inputs: dict) -> dict:
    """
    Execute the Weather & Marine Safety Agent.

    This is the only public function. The Orchestrator (Phase 4) and the
    Streamlit UI both call this function exclusively.

    Args:
        inputs (dict): See module docstring for full key descriptions.

    Returns:
        dict: See module docstring for full output key descriptions.

    Step-by-step execution:
        1. Resolve location → (lat, lon)
        2. Parse time context → (start_hour, window_hours)
        3. Fetch atmospheric & marine data from Open-Meteo
        4. Slice data to the relevant time window
        5. Compute peak metrics
        6. Apply rule-based thresholds → preliminary verdict
        7. Ask Gemini to explain in plain language
        8. Assemble and return final structured output
    """

    # ── Step 1: Resolve location ─────────────────────────────────────────────
    lat = inputs.get("lat")
    lon = inputs.get("lon")
    resolved_location = inputs.get("location", "Unknown location")

    if lat is None or lon is None:
        location_name = inputs.get("location")
        if not location_name:
            return {
                "success": False,
                "error": "Missing input: provide 'location' (name) or 'lat' + 'lon' (coordinates).",
            }
        geo = get_coordinates(location_name)
        if not geo["success"]:
            return {"success": False, "error": geo["error"]}

        lat               = geo["lat"]
        lon               = geo["lon"]
        resolved_location = geo["location"]

    # ── Step 2: Parse time context ───────────────────────────────────────────
    time_context            = inputs.get("time_context", "today")
    start_hour, window_hours = _parse_time_context(time_context)

    # ── Step 3: Fetch data ───────────────────────────────────────────────────
    atmo_raw   = fetch_atmospheric_weather(lat, lon)
    marine_raw = fetch_marine_conditions(lat, lon)

    if "error" in atmo_raw:
        return {"success": False, "error": f"Atmospheric data unavailable: {atmo_raw['error']}"}

    # Marine data may legitimately fail for inland points — treat gracefully
    marine_hourly = marine_raw.get("hourly", {}) if "error" not in marine_raw else {}
    atmo_hourly   = atmo_raw.get("hourly", {})

    # ── Step 4: Slice to time window ─────────────────────────────────────────
    atmo_window   = extract_conditions_for_window(atmo_hourly,   start_hour, window_hours)
    marine_window = extract_conditions_for_window(marine_hourly, start_hour, window_hours)

    # ── Step 5: Compute peak metrics ─────────────────────────────────────────
    metrics = _compute_peak_metrics(atmo_window, marine_window)

    # ── Step 6: Rule-based pre-assessment ───────────────────────────────────
    rule_verdict = _rule_based_verdict(metrics)

    # ── Step 7: Gemini analysis ──────────────────────────────────────────────
    gemini_result = _ask_gemini(resolved_location, time_context, metrics, rule_verdict)

    # ── Step 8: Assemble output ──────────────────────────────────────────────
    return {
        "success":     True,
        "location":    resolved_location,
        "lat":         lat,
        "lon":         lon,
        "verdict":     gemini_result["verdict"],
        "summary":     gemini_result["summary"],
        "key_metrics": metrics,
        "reasoning":   gemini_result["reasoning"],
    }
