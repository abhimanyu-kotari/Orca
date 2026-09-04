"""
agents/pfz_agent.py — Potential Fishing Zone (PFZ) Agent.

─────────────────────────────────────────────────────────────────────────────
RESPONSIBILITY
─────────────────────────────────────────────────────────────────────────────
Given a coastal location (name or coordinates), this agent:
    1. Resolves the location to GPS coordinates (Nominatim geocoder)
    2. Queries the PFZ database for the 5 nearest productive zones
    3. Calls Gemini to produce a plain-language fishing advisory
    4. Returns a structured dict for the Streamlit UI to render
       (text card + Folium map)

─────────────────────────────────────────────────────────────────────────────
INTERFACE
─────────────────────────────────────────────────────────────────────────────
    run(inputs: dict) -> dict

INPUTS:
    "location"  (str, required): coastal city / region name
    "lat"       (float, optional): pre-resolved latitude  (skip geocoding)
    "lon"       (float, optional): pre-resolved longitude (skip geocoding)
    "max_zones" (int,   optional): max PFZ zones to return (default 5)

OUTPUTS (success=True):
    "success"          (bool): True
    "location"         (str):  resolved full location name
    "lat"              (float): resolved latitude
    "lon"              (float): resolved longitude
    "zones"            (list): list of zone dicts with distance_to_user_km
    "zone_count"       (int):  number of zones found
    "best_zone"        (dict | None): highest-quality nearest zone
    "advisory"         (str):  Gemini-generated plain-language advisory
    "advisory_source"  (str):  "gemini" | "rule-based"

OUTPUTS (success=False):
    "success" (bool): False
    "error"   (str):  description of what failed
"""

import json
import httpx
from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from tools.weather_tools import get_coordinates
from tools.pfz_tools import find_nearest_zones


# ─────────────────────────────────────────────────────────────────────────────
# Gemini client — same pattern as all other ORCA agents
# ─────────────────────────────────────────────────────────────────────────────
_GEMINI_TIMEOUT_S: int = 60

_gemini = None


def _get_gemini_client():
    """Lazily and safely instantiate or return the genai.Client."""
    global _gemini
    if _gemini is not None:
        return _gemini
    from config import get_gemini_api_key
    key = get_gemini_api_key()
    if key:
        try:
            _gemini = genai.Client(
                api_key=key,
                http_options={"timeout": _GEMINI_TIMEOUT_S},
            )
        except Exception:
            _gemini = None
    return _gemini


# Initialise on load if key is already available in secrets or env
if GEMINI_API_KEY:
    _get_gemini_client()



# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_advisory_prompt(location: str, zones: list[dict]) -> str:
    """
    Construct the Gemini prompt that generates the fishing advisory.

    We inject the full zone list as a structured summary so Gemini
    reasons over real data — it never fabricates zone coordinates.
    """
    zone_summary = ""
    for i, z in enumerate(zones, start=1):
        sp_raw = z.get("species", "")
        species = ", ".join(sp_raw) if isinstance(sp_raw, list) else str(sp_raw)
        q_val = z.get("quality") or z.get("status", "MEDIUM")
        d_val = z.get("depth_m") if z.get("depth_m") is not None else z.get("depth", "—")
        z_id = z.get("zone_id") or z.get("id", f"PFZ-{i}")
        zone_summary += (
            f"  Zone {i}: {z['name']} ({z_id})\n"
            f"    Quality       : {q_val}\n"
            f"    Distance      : {z['distance_to_user_km']} km from {location}\n"
            f"    Depth         : {d_val} m\n"
            f"    Target species: {species}\n"
            f"    Advisory note : {z.get('advisory', '')}\n"
            f"    Best season   : {z.get('best_season', 'Year-round')}\n\n"
        )

    return f"""
You are ORCA, a trusted fishing advisor for Indian coastal fishermen.
A fisherman near {location} is asking where to fish today.

Here are the {len(zones)} nearest Potential Fishing Zones (PFZ) from the
INCOIS advisory database:

{zone_summary}
Your task:
1. Write a "summary" — a 2–3 sentence practical advisory in plain language
   that a fisherman with no technical background can immediately act on.
   Name the best zone and say why.
2. Write "top_zone" — just the zone name of the single best recommendation.
3. Write "safety_note" — one sentence about any important safety consideration
   (vessel size, season, tidal/weather dependency, depth risk).

Respond ONLY with valid JSON — no markdown fences:
{{
  "summary":     "...",
  "top_zone":    "...",
  "safety_note": "..."
}}
"""


def _rule_based_advisory(location: str, zones: list[dict]) -> dict:
    """
    Fallback advisory when Gemini is unavailable.
    Picks the closest HIGH-quality zone or the closest zone overall.
    """
    if not zones:
        return {
            "summary":     f"No PFZ zones found within range of {location}.",
            "top_zone":    None,
            "safety_note": "Try a coastal city closer to the sea.",
        }

    # Prefer HIGH quality, otherwise take nearest
    high_zones = [z for z in zones if (z.get("quality") or z.get("status")) == "HIGH"]
    best = high_zones[0] if high_zones else zones[0]
    sp_raw = best.get("species", "")
    species = ", ".join(sp_raw) if isinstance(sp_raw, list) else str(sp_raw)
    depth_val = best.get("depth_m") if best.get("depth_m") is not None else best.get("depth", "—")

    return {
        "summary": (
            f"The nearest productive PFZ near {location} is "
            f"{best['name']} ({best['distance_to_user_km']} km away). "
            f"Depth: {depth_val} m. Target species: {species}."
        ),
        "top_zone":    best["name"],
        "safety_note": best.get("advisory", "Check local weather before departure."),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(inputs: dict) -> dict:
    """
    Execute the PFZ Agent.

    Internal pipeline:
        1. Resolve location name → (lat, lon) via Nominatim geocoder
           (Skip if lat/lon already provided in inputs)
        2. Query PFZ database for nearest zones
        3. Call Gemini for a plain-language fishing advisory
        4. Return structured result dict

    Args:
        inputs (dict): See module docstring for schema.

    Returns:
        dict: See module docstring for schema.
    """

    location_name = inputs.get("location", "").strip()
    max_zones     = int(inputs.get("max_zones", 5))

    # ─ Step 1: Resolve coordinates ─────────────────────────────────────────
    # Caller may pass pre-resolved lat/lon to skip geocoding
    lat = inputs.get("lat")
    lon = inputs.get("lon")

    if lat is None or lon is None:
        if not location_name:
            return {
                "success": False,
                "error":   "Provide either 'location' (name) or 'lat'/'lon' coordinates.",
            }
        geo = get_coordinates(location_name)
        if not geo.get("success"):
            return {"success": False, "error": geo.get("error", "Geocoding failed.")}
        lat           = geo["lat"]
        lon           = geo["lon"]
        resolved_name = geo["location"]          # Full resolved address
    else:
        lat           = float(lat)
        lon           = float(lon)
        resolved_name = location_name or f"{lat:.4f}°N, {lon:.4f}°E"

    # ─ Step 2: Find nearest PFZ zones ────────────────────────────────────
    zones = find_nearest_zones(lat, lon, max_results=max_zones)

    if not zones:
        return {
            "success":    False,
            "error":      (
                f"No PFZ zones found within 400 km of {resolved_name}. "
                "Try a coastal city (e.g. Kochi, Rameswaram, Visakhapatnam)."
            ),
            "lat":        lat,
            "lon":        lon,
            "location":   resolved_name,
        }

    # ─ Step 3: Gemini advisory ──────────────────────────────────────────
    prompt          = _build_advisory_prompt(location_name or resolved_name, zones)
    advisory_source = "gemini"

    client = _get_gemini_client()
    if not client:
        advice          = _rule_based_advisory(location_name or resolved_name, zones)
        advisory_source = "rule-based (GEMINI_API_KEY not configured)"
    else:
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"http_options": {"timeout": _GEMINI_TIMEOUT_S}},
            )
            raw_text   = response.text.strip()
            clean_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            advice     = json.loads(clean_text)

            # Validate keys
            if not all(k in advice for k in ("summary", "top_zone", "safety_note")):
                raise ValueError("Missing keys in Gemini advisory response.")

        except (TimeoutError, httpx.TimeoutException):
            advice          = _rule_based_advisory(location_name or resolved_name, zones)
            advisory_source = "rule-based (Gemini timed out)"
        except (json.JSONDecodeError, ValueError, Exception):
            advice          = _rule_based_advisory(location_name or resolved_name, zones)
            advisory_source = "rule-based (Gemini failed)"

    # ─ Step 4: Build best_zone reference ──────────────────────────────
    top_zone_name = advice.get("top_zone")
    best_zone     = next(
        (z for z in zones if z["name"] == top_zone_name),
        zones[0],   # fallback to closest zone
    )

    return {
        "success":         True,
        "location":        resolved_name,
        "lat":             lat,
        "lon":             lon,
        "zones":           zones,
        "zone_count":      len(zones),
        "best_zone":       best_zone,
        "advisory":        advice.get("summary", ""),
        "safety_note":     advice.get("safety_note", ""),
        "advisory_source": advisory_source,
    }
