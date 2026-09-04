"""
agents/hazard_agent.py — Alert & Maritime Hazard Agent (IMD Disaster Scales)

─────────────────────────────────────────────────────────────────────────────
RESPONSIBILITY
─────────────────────────────────────────────────────────────────────────────
Evaluates maritime disaster and cyclone hazard levels for Indian coastal zones
using official IMD (India Meteorological Department) & INCOIS disaster criteria:

  - 🟢 Green / Level-0 (Normal):
      Wind < 40 km/h, Waves < 2.0 m
      Standard navigational protocols. No active geofences.

  - 🟡 Yellow / Level-1 (Gale & Swell Watch):
      Wind 40–61 km/h OR Waves 2.0–3.5 m
      Cautionary coastal geofence. Small traditional craft stay close to shore.

  - 🔴 Red / Level-2 (Cyclone Alert / Severe Sea State):
      Wind >= 62 km/h OR Waves > 3.5 m
      Active Maritime Exclusion Geofence. Complete fishing ban & vessel recall.

─────────────────────────────────────────────────────────────────────────────
INTERFACE — Uniform across all ORCA agents
─────────────────────────────────────────────────────────────────────────────
    run(inputs: dict) -> dict

INPUTS:
    "location"       (str, required): Coastal city or sector name
    "time_context"   (str, optional): Default "today"
    "weather_result" (dict, optional): Pre-fetched weather_agent dict

OUTPUTS:
    "success":           bool
    "location":          str
    "lat":               float
    "lon":               float
    "level":             "Level-0" | "Level-1" | "Level-2"
    "color":             "Green" | "Yellow" | "Red"
    "category":          "Normal" | "Gale/Swell Watch" | "Cyclone Alert"
    "imd_scale":         str
    "metrics":           dict
    "geofence_guidance": str
    "advisory":          str
    "weather_result":    dict
    "summary":           str (markdown)
"""

from typing import Optional
from agents.weather_agent import run as weather_agent_run


def classify_imd_hazard(wind_kmh: float, wave_m: float, thunderstorm: bool = False) -> tuple[str, str, str, str, str]:
    """
    Classify marine conditions against IMD maritime disaster scales.

    Returns:
        (level, color, category, geofence_guidance, advisory)
    """
    # Red / Level-2: Cyclone Alert / Severe Storm State
    if wind_kmh >= 62.0 or wave_m > 3.5 or (wind_kmh >= 50.0 and thunderstorm):
        level = "Level-2"
        color = "Red"
        category = "Cyclone Alert / Severe Hazard"
        geofence_guidance = (
            "🚨 **ACTIVE MARITIME EXCLUSION GEOFENCE:** Mandatory harbor recall. "
            "Ingress/egress prohibited for all motorized trawlers and artisanal craft. "
            "Emergency VHF Ch 16 and NAVTEX warnings broadcast."
        )
        advisory = (
            "DANGER: Severe gale-force winds and violent wave heights exceed maritime survivability limits. "
            "Total suspension of fishing operations and coastal navigation."
        )
    # Yellow / Level-1: Gale / Swell Watch
    elif (40.0 <= wind_kmh <= 61.0) or (2.0 <= wave_m <= 3.5):
        level = "Level-1"
        color = "Yellow"
        category = "Gale / Swell Watch"
        geofence_guidance = (
            "⚠️ **CAUTIONARY GEOFENCE (Zone 4 Perimeter):** High-wave inundation watch. "
            "Small artisanal craft advised not to navigate into open deep-water corridors. "
            "Maintain continuous radio watch on VHF Ch 16."
        )
        advisory = (
            "CAUTION: Elevated swell and squally winds present hazardous conditions for small craft. "
            "Remain within sheltered waters and keep away from breaker zones."
        )
    # Green / Level-0: Normal / Benign
    else:
        level = "Level-0"
        color = "Green"
        category = "Normal / Benign"
        geofence_guidance = (
            "✅ **STANDARD NAVIGATIONAL BUFFER:** No active hazard geofences. "
            "Normal port clearance protocols in effect."
        )
        advisory = (
            "SAFE: Benign sea state and wind conditions. Safe for all routine artisanal "
            "and commercial marine operations."
        )

    return level, color, category, geofence_guidance, advisory


def run(inputs: dict) -> dict:
    """Execute IMD alert & hazard evaluation."""
    if not isinstance(inputs, dict):
        inputs = {}

    location = inputs.get("location", "").strip()
    time_context = inputs.get("time_context", "today")
    weather_res = inputs.get("weather_result")

    if not location and not (weather_res and weather_res.get("location")):
        return {
            "success": False,
            "error": "No coastal location provided for hazard evaluation.",
            "level": "Level-0",
            "color": "Green",
            "category": "Unknown",
            "imd_scale": "Green / Level-0 (Unknown)",
            "summary": "Please specify a coastal city or port to evaluate IMD hazard status.",
        }

    # 1. Fetch weather if not already pre-fetched
    if not weather_res or not weather_res.get("success"):
        weather_res = weather_agent_run({
            "location": location,
            "time_context": time_context,
        })

    if not weather_res.get("success"):
        return {
            "success": False,
            "error": weather_res.get("error", "Failed to retrieve marine telemetry."),
            "location": location,
            "level": "Level-0",
            "color": "Green",
            "category": "Unknown",
            "imd_scale": "Unknown",
            "summary": f"Could not retrieve live oceanographic telemetry for {location}.",
        }

    loc_name = weather_res.get("location", location)
    lat = weather_res.get("lat")
    lon = weather_res.get("lon")
    metrics = weather_res.get("key_metrics", {})

    wind_speed = metrics.get("max_wind_speed_kmh", 0.0)
    wind_gust = metrics.get("max_wind_gust_kmh", 0.0)
    wave_height = metrics.get("max_wave_height_m", 0.0)
    swell_height = metrics.get("max_swell_height_m", 0.0)
    thunderstorm = metrics.get("thunderstorm_likely", False)

    # 2. Classify according to IMD Disaster Scales
    level, color, category, geofence_guidance, advisory = classify_imd_hazard(
        wind_speed, wave_height, thunderstorm
    )
    imd_scale = f"{color} / {level} ({category})"

    # Color emoji
    color_emoji = {"Green": "🟢", "Yellow": "🟡", "Red": "🔴"}.get(color, "ℹ️")

    # 3. Format structured bulletin
    storm_text = "Yes ⚡" if thunderstorm else "No"
    summary_md = f"""
### {color_emoji} IMD Maritime Disaster Classification: **{color} / {level}**
**Category:** **{category}**  
**Monitored Sector:** {loc_name}

---

**📊 Marine & Meteorological Disaster Telemetry**
- **Sustained Wind:** {wind_speed:.1f} km/h *(Gusts: {wind_gust:.1f} km/h)*
- **Significant Wave Height:** {wave_height:.2f} m *(Swell: {swell_height:.2f} m)*
- **Convective Storm Activity:** {storm_text}

---

**🛡️ Active Geofence & Surveillance Guidance**  
{geofence_guidance}

---

**📢 Official Maritime Safety Advisory**  
{advisory}
"""

    return {
        "success": True,
        "location": loc_name,
        "lat": lat,
        "lon": lon,
        "level": level,
        "color": color,
        "category": category,
        "imd_scale": imd_scale,
        "metrics": metrics,
        "geofence_guidance": geofence_guidance,
        "advisory": advisory,
        "weather_result": weather_res,
        "summary": summary_md.strip(),
    }
