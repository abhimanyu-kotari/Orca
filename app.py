"""
app.py — ORCA Streamlit Chat Interface (Stakeholder Persona System)

─────────────────────────────────────────────────────────────────────────────
ISRO SIH PROBLEM STATEMENT 26176 — THREE STAKEHOLDER PERSONAS:
─────────────────────────────────────────────────────────────────────────────
  1. 🎣 Artisanal Fisherman (Default):
     - Conversational plain-language advice with clear SAFE/CAUTION/DANGER badges.
     - Potential Fishing Zone (PFZ) recommendations with species and depths.
     - Highlighted dashed navigation route from reference port to top PFZ hotspot.

  2. 🚨 Coastal Authority / Disaster Management:
     - Disaster Monitoring & Maritime Geofence dashboard header.
     - High-Risk Cyclone & Storm Surge Geofence overlay (semi-transparent red polygon).
     - Simulated Emergency Broadcast dispatch (VHF Ch 16, NAVTEX, SMS gateway).
     - Vessel exclusion alerts when DANGER conditions are detected.

  3. 🔬 Marine Researcher / Oceanographer:
     - Earth Observation Telemetry panel (SST, Chlorophyll-a, Thermocline, Salinity).
     - Toggleable Satellite Thermal Gradient HeatMap on Folium ocean charts.
     - Scientific oceanographic reasoning detailing upwelling fronts and biological productivity.

Run:
    streamlit run app.py
─────────────────────────────────────────────────────────────────────────────
"""

import os
import folium
import streamlit as st
from streamlit_folium import st_folium

from orchestrator import run as orchestrator_run
from tools.map_tools import create_pfz_map, create_weather_map

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "orca_logo.png")
LOGO_EXISTS = os.path.exists(LOGO_PATH)

# ─────────────────────────────────────────────────────────────────────────────
# Page configuration
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ORCA — Satellite Intelligence for Safer Oceans",
    page_icon=LOGO_PATH if LOGO_EXISTS else "🌊",
    layout="wide",
)


# ─────────────────────────────────────────────────────────────────────────────
# Brand Theme — Deep Ocean Navy CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Global body */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #F8FAFC !important;
    font-family: 'Inter', 'Segoe UI', sans-serif !important;
    color: #1E293B !important;
}

/* Main content area */
[data-testid="stMain"] {
    background-color: #F8FAFC !important;
}

/* Sidebar background */
[data-testid="stSidebar"] {
    background-color: #F0F4F8 !important;
    border-right: 1px solid #E2E8F0 !important;
}

/* Page headers */
h1, h2, h3 {
    color: #0B2638 !important;
    font-family: 'Inter', 'Segoe UI', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
}
h1 { font-size: 2rem !important; }
h2 { font-size: 1.4rem !important; }
h3 { font-size: 1.1rem !important; }

/* Top nav persona selector — horizontal radio pills */
div[data-testid="stHorizontalBlock"] .stRadio > div {
    gap: 8px !important;
}
div[data-testid="stHorizontalBlock"] .stRadio > div > label {
    background-color: #E2EBF3 !important;
    border: 1.5px solid #CBD8E6 !important;
    border-radius: 24px !important;
    padding: 6px 18px !important;
    font-weight: 500 !important;
    color: #0B2638 !important;
    cursor: pointer !important;
    transition: all 0.18s ease !important;
}
div[data-testid="stHorizontalBlock"] .stRadio > div > label:hover {
    background-color: #C9DCF0 !important;
    border-color: #0B2638 !important;
}

/* Primary buttons */
div.stButton > button[kind="primary"] {
    background-color: #0B2638 !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #163C55 !important;
}

/* Secondary buttons */
div.stButton > button {
    border-radius: 8px !important;
    border: 1.5px solid #CBD8E6 !important;
    color: #0B2638 !important;
    font-weight: 500 !important;
}

/* Top nav divider */
.orca-nav-divider {
    border: none;
    border-top: 2px solid #E2E8F0;
    margin: 4px 0 16px 0;
}

/* Metric cards */
[data-testid="stMetricValue"] {
    color: #0B2638 !important;
    font-weight: 700 !important;
}

/* Info / warning banners */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-left-width: 4px !important;
}

/* Chat bubbles */
[data-testid="stChatMessage"] {
    border-radius: 12px !important;
    margin-bottom: 8px !important;
}

/* Expander */
details summary {
    font-weight: 600 !important;
    color: #0B2638 !important;
}

/* Divider lines */
hr {
    border-color: #E2E8F0 !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state initialization
# ─────────────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_map" not in st.session_state:
    st.session_state.current_map = None

if "current_persona" not in st.session_state:
    st.session_state.current_persona = "🎣 Artisanal Fisherman"


# ─────────────────────────────────────────────────────────────────────────────
# Display constants & stylings
# ─────────────────────────────────────────────────────────────────────────────
VERDICT_EMOJI = {"SAFE": "✅", "CAUTION": "⚠️", "DANGER": "🚨"}
VERDICT_COLOR = {"SAFE": "green", "CAUTION": "orange", "DANGER": "red"}

LANG_FLAG: dict[str, str] = {
    "en": "🇬🇧", "hi": "🇮🇳", "ta": "🇮🇳", "te": "🇮🇳",
    "ml": "🇮🇳", "kn": "🇮🇳", "bn": "🇮🇳", "mr": "🇮🇳",
    "gu": "🇮🇳", "pa": "🇮🇳", "or": "🇮🇳", "ur": "🇵🇰",
}

INTENT_LABEL: dict[str, str] = {
    "weather_check":   "🌤️ Weather Check",
    "safety_check":    "⚓ Safety Check",
    "pfz_location":    "🐟 Fishing Zone",
    "fishing_zone":    "🐟 Fishing Zone",
    "route_planning":  "🧭 Route Planning",
    "alert_query":     "🚨 Alert Query",
    "ecosystem_query": "🌊 Ecosystem",
    "casual_chat":     "💬 Chat",
    "unknown":         "❓ General / Unknown",
}

QUALITY_EMOJI = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}


# ─────────────────────────────────────────────────────────────────────────────
# Response formatters (Persona-Aware)
# ─────────────────────────────────────────────────────────────────────────────

def _metadata_badge(result: dict, persona: str = None) -> str:
    """Build the metadata footer indicating language, intent, agents, and stakeholder role."""
    active_persona = result.get("persona") or persona or "fisherman"
    intent_res = result.get("intent_result", {})
    lang_code = intent_res.get("language_code", "en")
    lang_name = intent_res.get("language", "English")
    flag = LANG_FLAG.get(lang_code, "🌐")
    intent = result.get("intent", "unknown")
    label = INTENT_LABEL.get(intent, intent)
    agents = " ➔ ".join(result.get("agents_invoked", ["orchestrator"]))
    role_titles = {
        "fisherman": "🎣 Artisanal Fisherman",
        "coastal_authority": "🚨 Coastal Authority",
        "researcher": "🔬 Marine Researcher",
    }
    role_display = role_titles.get(active_persona, active_persona)

    return (
        f"\n\n---\n"
        f"*{flag} Language: **{lang_name}** · Intent: **{label}** · "
        f"Agents: `{agents}` · Stakeholder View: **{role_display}***"
    )


def format_orchestrator_response(result: dict, persona: str = "fisherman") -> str:
    """
    Format orchestrator output into markdown tailored to the active Stakeholder Persona.
    """
    active_persona = result.get("persona") or persona or "fisherman"
    synthesis = result.get("synthesis", "")
    weather_res = result.get("weather_result")
    pfz_res = result.get("pfz_result")
    pfz_suppressed = result.get("pfz_suppressed", False)
    suppression_reason = result.get("pfz_suppression_reason")
    nav_suspended = result.get("navigation_suspended", False)
    is_danger = (weather_res and weather_res.get("verdict") == "DANGER")
    is_suspended = nav_suspended or is_danger

    sections = []

    # 1. Primary AI / Unified Synthesis
    if synthesis:
        sections.append(synthesis)

    # 2. Critical Safety Suspension Alert / Planning Notice
    suspension_banner = (
        "> ⚠️ **Navigation Suspended: Sea state / Lightning hazard active. "
        "Showing direct displacement metrics for planning purposes only once weather clears.**"
    )
    if is_suspended and "Navigation Suspended: Sea state / Lightning hazard active" not in synthesis:
        sections.append(f"\n{suspension_banner}")
    elif pfz_suppressed and suppression_reason and suppression_reason not in synthesis:
        sections.append(
            f"\n> 🚨 **MARITIME SAFETY OVERRIDE ENFORCED:**\n"
            f"> {suppression_reason}"
        )

    # 3. Persona Specific Banner / Callouts
    if active_persona == "coastal_authority":
        sections.append(
            """
> 🛡️ **DISASTER MANAGEMENT NOTICE:**  
> High-risk coastal geofence is active. All small-craft maritime traffic in this sector is under Level-2/3 surveillance.
"""
        )
    elif active_persona == "researcher":
        sections.append(
            """
> 🛰️ **EARTH OBSERVATION TELEMETRY NOTE:**  
> Upwelling indices derived from Open-Meteo marine baroclinicity and INCOIS thermal models.
"""
        )

    # 4. Weather & Oceanographic Conditions
    if weather_res and weather_res.get("success"):
        verdict = weather_res.get("verdict", "SAFE")
        emoji = VERDICT_EMOJI.get(verdict, "ℹ️")
        color = VERDICT_COLOR.get(verdict, "blue")
        m = weather_res.get("key_metrics", {})
        storm_str = "Yes ⚡" if m.get("thunderstorm_likely") else "No"
        is_lightning = m.get("lightning_hazard", False)

        if is_lightning:
            sections.append(
                f"\n> ⚡ **LIGHTNING HAZARD DETECTED:**\n"
                f"> Elevated convective storm instability (CAPE: **{m.get('max_cape_jkg', 0.0):.0f} J/kg** exceeds 1500 J/kg threshold). "
                f"**SAFE navigational clearance is suppressed.** Open sea transit poses severe lightning strike hazard."
            )

        # Headers tailored to persona
        table_title = "Marine & Atmospheric Telemetry" if persona == "researcher" else "Peak Marine Conditions"

        weather_card = f"""
---
### {emoji} Sea State & Safety Verdict: :{color}[**{verdict}**]
**📍 Reference Location:** {weather_res.get('location', 'N/A')}

**📊 {table_title}**

| Metric | Measured Value | Standard Threshold |
|---|---|---|
| Wind Speed | {m.get('max_wind_speed_kmh', 0.0):.1f} km/h | 40.0 km/h (Gale) |
| Wind Gust | {m.get('max_wind_gust_kmh', 0.0):.1f} km/h | 55.0 km/h (Severe) |
| Wave Height | {m.get('max_wave_height_m', 0.0):.2f} m | 2.50 m (Hazard) |
| Swell Height | {m.get('max_swell_height_m', 0.0):.2f} m | 2.00 m (High Swell) |
| Wave Period | {m.get('max_wave_period_s', 0.0):.1f} s | — |
| Precipitation | {m.get('max_precipitation_mm', 0.0):.1f} mm/hr | 10.0 mm/hr (Heavy Rain) |
| Convective Energy (CAPE) | {m.get('max_cape_jkg', 0.0):.0f} J/kg | 1500 J/kg (Lightning Limit) |
| Thunderstorm | {storm_str} | Immediate Danger |

**🧠 Reasoning & Risk Factors:**  
{weather_res.get('reasoning', 'Conditions assessed against IMD/INCOIS guidelines.')}
"""
        sections.append(weather_card)

    # 5. PFZ Hotspots Table (if available)
    if pfz_res and pfz_res.get("success"):
        zones = pfz_res.get("zones", [])
        best = pfz_res.get("best_zone", {})
        zone_rows = ""
        for i, z in enumerate(zones, start=1):
            quality_dot = QUALITY_EMOJI.get(z.get("quality") or z.get("status", "MEDIUM"), "⚪")
            sp_raw = z.get("species", "")
            species_str = ", ".join(sp_raw) if isinstance(sp_raw, list) else str(sp_raw)
            depth_val = z.get("depth_m") if z.get("depth_m") is not None else z.get("depth", "—")
            zone_rows += (
                f"| {i} | {quality_dot} {z.get('name', 'N/A')} | "
                f"{z.get('distance_to_user_km', '—')} km | "
                f"{depth_val} m | "
                f"{species_str} |\n"
            )

        best_name = best.get("name", "—") if best else "—"
        planning_tag = " ⚠️ *(Pre-Voyage Planning — Navigation Suspended)*" if is_suspended else ""
        pfz_card = f"""
---
### 🐟 Potential Fishing Zones (INCOIS Data){planning_tag}
**📍 Reference Port:** {pfz_res.get('location', 'N/A')}

| # | Zone Name | Distance | Depth | Commercially Viable Species |
|---|---|---|---|---|
{zone_rows}
**🏆 Top Recommended Hotspot:** **{best_name}**  
*Advisory:* {pfz_res.get('safety_note', 'Check local forecasts prior to embarkation.')}
"""
        sections.append(pfz_card)

    # 6. Fuel-Optimal Navigation & Waypoint Summary (if available)
    nav_res = result.get("navigation_result")
    if nav_res and nav_res.get("success"):
        total_nm = nav_res.get("total_distance_nm", 0.0)
        total_km = nav_res.get("total_distance_km", 0.0)
        heading = nav_res.get("direct_heading_str", "—")
        econ = nav_res.get("fuel_economy", {})
        fuel_saved = econ.get("fuel_saved_liters", 0.0)
        cost_saved = econ.get("cost_saved_inr", 0)
        transit_time = econ.get("transit_time_str", "—")
        geofence_status = nav_res.get("geofence_status", "Safe & Clear")
        has_detour = nav_res.get("hazard_avoidance_active", False)
        imbl_warn = nav_res.get("imbl_warning_active", False)
        imbl_dist = nav_res.get("imbl_min_distance_nm", 0.0)
        imbl_boundary = nav_res.get("imbl_closest_boundary", "IMBL")

        if imbl_warn:
            sections.append(
                f"\n> 🛑 **IMBL PROXIMITY WARNING — RISK OF IMPOUNDMENT:**\n"
                f"> Navigation track approaches within **{imbl_dist:.1f} NM** of the **{imbl_boundary}** "
                f"International Maritime Boundary Line. Vessels face immediate risk of apprehension "
                f"by foreign maritime authorities. **Maintain minimum 5 NM seaward safety clearance.**"
            )

        if is_suspended:
            nav_title = "### ⛽ Fuel-Optimal Navigation Summary ⚠️ [TRANSIT SUSPENDED — BENCHMARK PLANNING ONLY]"
            safety_flag_banner = (
                "> ⚠️ **SAFETY WARNING FLAG:** Active marine hazard/convective alert prohibits immediate sailing. "
                "Displacement distance and fuel economics shown below for judging benchmark & pre-voyage planning once weather clears.\n\n"
            )
            detour_badge = (
                f"⚠️ **Transit Suspended:** Active hazard alert. Direct track: {total_nm:.1f} NM ({total_km:.1f} km) plotted for post-clearing transit."
            )
        else:
            nav_title = "### ⛽ Fuel-Optimal Navigation Summary"
            safety_flag_banner = ""
            detour_badge = (
                "🚨 **Detour Engaged:** Course adjusted to steer clear of active coastal hazard geofence."
                if has_detour
                else "✅ Direct track is clear of all active storm surge and hazard geofences."
            )

        imbl_row = (
            f"| **IMBL Border Proximity** | 🛑 **{imbl_dist:.1f} NM to {imbl_boundary}** | **High Impoundment Risk** (< 5 NM limit) |\n"
            if imbl_warn else ""
        )

        wp_rows = ""
        for wp in nav_res.get("waypoints", []):
            leg_dist = f"{wp.get('leg_distance_nm', 0.0):.1f} NM" if wp.get("leg_distance_nm") else "Start"
            bearing = wp.get("leg_bearing") or "Departure"
            wp_rows += f"| {wp['name']} | `{wp['lat']:.4f}°N, {wp['lon']:.4f}°E` | {leg_dist} | {bearing} | {wp.get('notes', '')} |\n"

        nav_card = f"""
---
{nav_title}
{safety_flag_banner}**🎯 Destination Hotspot:** {nav_res.get('end_label', 'Target PFZ')} | **Mooring:** {nav_res.get('start_label', 'Port')}

| Metric | Navigation Telemetry | Benchmark / Savings |
|---|---|---|
| **Direct Track Distance** | **{total_nm:.1f} NM** ({total_km:.1f} km) | Great-circle nautical track |
| **Optimal Compass Heading** | **{heading}** | Forward azimuth |
| **Estimated Transit Time** | **{transit_time}** | Standard 9.0 knots cruising speed |
| **Estimated Fuel Economy** | **{fuel_saved:.1f} Liters Saved** | **~₹{cost_saved:,.0f} net savings** vs blind cruising |
| **Waypoint Safety Check** | **{geofence_status}** | {detour_badge} |
{imbl_row}
<details>
<summary>📍 <b>View Waypoint Route Plan ({len(nav_res.get('waypoints', []))} Waypoints)</b></summary>

| Waypoint | Coordinates | Leg Distance | Steer Bearing | Navigational Advisory |
|---|---|---|---|---|
{wp_rows}
</details>
"""
        sections.append(nav_card)

    # 7. Earth Observation & Satellite Diagnostic Summary (if available)
    eo_res = result.get("eo_result")
    if eo_res and eo_res.get("success"):
        sst_mean = eo_res.get("mean_sst_c", 0.0)
        sst_min = eo_res.get("min_sst_c", 0.0)
        sst_max = eo_res.get("max_sst_c", 0.0)
        sst_anom = eo_res.get("sst_anomaly_c", 0.0)
        anom_sign = "+" if sst_anom > 0 else ""
        chla_mean = eo_res.get("mean_chlorophyll_mg_m3", 0.0)
        chla_max = eo_res.get("max_chlorophyll_mg_m3", 0.0)
        upwell_int = eo_res.get("upwelling_intensity", "Moderate Upwelling")
        thermocline = eo_res.get("thermocline_depth_m", 35)
        front_coords = eo_res.get("upwelling_front_coords", [0.0, 0.0])
        grid_pts = eo_res.get("grid_points_count", 0)

        meta = eo_res.get("sensor_metadata", {})
        sst_sensor = meta.get("sst_sensor", "Copernicus Sentinel-3 SLSTR")
        chl_sensor = meta.get("ocean_color_sensor", "ISRO Oceansat-3 OCM-3")

        eo_card = f"""
---
### 🔬 Earth Observation Diagnostic Summary
**🛰️ Primary Sensors:** {sst_sensor} & {chl_sensor}  
**🌐 Sampling Grid:** {grid_pts} telemetry stations (120 km radius)

| Oceanographic Parameter | Satellite Derived Value | Climatological Context & Sensor Payload |
|---|---|---|
| **Mean Sea Surface Temp (SST)** | **{sst_mean:.2f}°C** (Range: {sst_min:.1f}°C – {sst_max:.1f}°C) | Sentinel-3 SLSTR infrared radiometry (1 km resolution) |
| **Thermal Front Anomaly** | **{anom_sign}{sst_anom:.2f}°C** | Climatology baseline ({meta.get('climatology_baseline', '28.5°C')}) |
| **Mean Chlorophyll-a** | **{chla_mean:.2f} mg/m³** | ISRO Oceansat-3 OCM-3 ({meta.get('chl_resolution', '300 m resolution')}) |
| **Peak Chlorophyll Bloom** | **{chla_max:.2f} mg/m³** | Shelf edge primary productivity convergence |
| **Baroclinic Upwelling Index** | **{upwell_int}** | Ekman transport & coastal divergence |
| **Estimated Thermocline Depth** | **~{thermocline} m** | Subsurface mixed-layer pycnocline |
| **Primary Upwelling Front** | `{front_coords[0]:.4f}°N, {front_coords[1]:.4f}°E` | Maximum horizontal thermal contrast |

*💡 Tip: Use the Folium layer control on the top right of the map to toggle between SST Thermal Gradient and Chlorophyll-a Productivity.*
"""
        sections.append(eo_card)

    # 8. Metadata Badge
    sections.append(_metadata_badge(result, active_persona))

    return "\n".join(sections)


def _metadata_badge_fisherman(result: dict) -> str:
    """
    Compact badge for Fisherman view — language + intent only.
    Agent pipeline is hidden (moved to technical expander).
    """
    intent_res = result.get("intent_result", {})
    lang_code = intent_res.get("language_code", "en")
    lang_name = intent_res.get("language", "English")
    flag = LANG_FLAG.get(lang_code, "🌐")
    intent = result.get("intent", "unknown")
    label = INTENT_LABEL.get(intent, intent)
    return f"\n\n---\n*{flag} **{lang_name}** · {label} · 🎣 Artisanal Fisherman View*"


def _agents_badge(result: dict) -> str:
    """Agent pipeline string for the technical evidence expander."""
    agents = " ➔ ".join(result.get("agents_invoked", ["orchestrator"]))
    return f"`{agents}`"


def render_fisherman_response(
    result: dict,
    fmap,
    container=None,
) -> None:
    """
    Render a progressive, safety-first Streamlit UI for the Fisherman persona.

    Layout (top-to-bottom priority):
      1. 🟢/⚠️/🚨 Large verdict banner (st.success / st.warning / st.error)
      2. Synthesis text (plain-language ORCA advice)
      3. PFZ Hotspots table  ← actionable destination info
      4. Fuel-Optimal Navigation summary ← right below zones
      5. 🗺️ Folium map (prominent)
      6. Collapsed expander: technical meteorological evidence + agent pipeline
    """
    ctx = container if container is not None else st

    weather_res = result.get("weather_result")
    pfz_res = result.get("pfz_result")
    nav_res = result.get("navigation_result")
    nav_suspended = result.get("navigation_suspended", False)
    is_danger = weather_res and weather_res.get("verdict") == "DANGER"
    is_suspended = nav_suspended or is_danger
    synthesis = result.get("synthesis", "")

    # ── 1. Prominent Verdict Banner ──────────────────────────────────────────
    verdict = None
    if weather_res and weather_res.get("success"):
        verdict = weather_res.get("verdict", "SAFE")

    if verdict == "SAFE" and not is_suspended:
        ctx.success("## 🟢 SAFE FOR DEPARTURE\nConditions are within safe limits for small craft operations.")
    elif verdict == "CAUTION" or (verdict == "SAFE" and is_suspended):
        ctx.warning("## ⚠️ EXERCISE CAUTION\nElevated sea state detected. Proceed with heightened vigilance and life-jacket compliance.")
    elif verdict == "DANGER" or is_suspended:
        ctx.error("## 🚨 TRANSIT NOT ADVISED\nHazardous marine conditions active. Stay ashore until the all-clear is issued.")
    elif not weather_res and pfz_res and pfz_res.get("success"):
        # PFZ-only query with no explicit weather check
        ctx.success("## 🟢 FISHING ZONES IDENTIFIED\nPotential Fishing Zones computed from INCOIS satellite data.")

    # Navigation suspension banner
    if is_suspended and weather_res:
        m = weather_res.get("key_metrics", {})
        is_lightning = m.get("lightning_hazard", False)
        if is_lightning:
            ctx.error(
                f"⚡ **LIGHTNING HAZARD:** CAPE {m.get('max_cape_jkg', 0):.0f} J/kg — "
                "severe convective instability. Open sea transit carries acute lightning strike risk."
            )
        ctx.warning(
            "> ⚠️ **Navigation Suspended:** Sea state / Lightning hazard active. "
            "Showing direct displacement metrics for planning purposes only once weather clears."
        )

    # ── 2. Plain-Language Synthesis ─────────────────────────────────────────
    if synthesis:
        ctx.markdown(synthesis)

    # ── 3. PFZ Hotspots ─────────────────────────────────────────────────────
    if pfz_res and pfz_res.get("success"):
        zones = pfz_res.get("zones", [])
        best = pfz_res.get("best_zone", {})
        planning_tag = " ⚠️ *(Pre-Voyage Planning — Navigation Suspended)*" if is_suspended else ""
        ctx.markdown(f"---\n### 🐟 Potential Fishing Zones (INCOIS Data){planning_tag}")
        ctx.caption(f"📍 Reference Port: **{pfz_res.get('location', 'N/A')}**")

        zone_rows = ""
        for i, z in enumerate(zones, start=1):
            quality_dot = QUALITY_EMOJI.get(z.get("quality") or z.get("status", "MEDIUM"), "⚪")
            sp_raw = z.get("species", "")
            species_str = ", ".join(sp_raw) if isinstance(sp_raw, list) else str(sp_raw)
            depth_val = z.get("depth_m") if z.get("depth_m") is not None else z.get("depth", "—")
            zone_rows += (
                f"| {i} | {quality_dot} {z.get('name', 'N/A')} | "
                f"{z.get('distance_to_user_km', '—')} km | "
                f"{depth_val} m | "
                f"{species_str} |\n"
            )

        ctx.markdown(
            f"| # | Zone Name | Distance | Depth | Commercially Viable Species |\n"
            f"|---|---|---|---|---|\n"
            f"{zone_rows}"
        )

        best_name = best.get("name", "—") if best else "—"
        ctx.markdown(
            f"🏆 **Top Recommended Hotspot:** **{best_name}**  \n"
            f"*Advisory:* {pfz_res.get('safety_note', 'Check local forecasts prior to embarkation.')}"
        )

    # ── 4. Fuel-Optimal Navigation ───────────────────────────────────────────
    if nav_res and nav_res.get("success"):
        imbl_warn = nav_res.get("imbl_warning_active", False)
        imbl_dist = nav_res.get("imbl_min_distance_nm", 0.0)
        imbl_boundary = nav_res.get("imbl_closest_boundary", "IMBL")

        if imbl_warn:
            ctx.error(
                f"🛑 **IMBL PROXIMITY WARNING — RISK OF IMPOUNDMENT:**  \n"
                f"Navigation track approaches within **{imbl_dist:.1f} NM** of the **{imbl_boundary}** "
                "International Maritime Boundary Line. **Maintain 5 NM seaward clearance.**"
            )

        total_nm = nav_res.get("total_distance_nm", 0.0)
        total_km = nav_res.get("total_distance_km", 0.0)
        heading = nav_res.get("direct_heading_str", "—")
        econ = nav_res.get("fuel_economy", {})
        fuel_saved = econ.get("fuel_saved_liters", 0.0)
        cost_saved = econ.get("cost_saved_inr", 0)
        transit_time = econ.get("transit_time_str", "—")
        geofence_status = nav_res.get("geofence_status", "Safe & Clear")
        has_detour = nav_res.get("hazard_avoidance_active", False)

        if is_suspended:
            ctx.markdown(
                "---\n### ⛽ Fuel-Optimal Navigation ⚠️ *[Benchmark — Transit Suspended]*"
            )
            ctx.warning(
                "Active marine hazard prohibits immediate sailing. "
                "Fuel economics shown for pre-voyage planning once weather clears."
            )
        else:
            ctx.markdown("---\n### ⛽ Fuel-Optimal Navigation")

        col_a, col_b, col_c, col_d = ctx.columns(4)
        col_a.metric("📏 Track Distance", f"{total_nm:.1f} NM", f"{total_km:.1f} km")
        col_b.metric("🧭 Heading", heading)
        col_c.metric("⏱️ Transit Time", transit_time)
        col_d.metric(
            "⛽ Fuel Saved",
            f"{fuel_saved:.1f} L",
            f"₹{cost_saved:,.0f} saved",
            delta_color="normal" if not is_suspended else "off",
        )

        ctx.caption(
            f"🎯 **{nav_res.get('start_label', 'Port')}** → **{nav_res.get('end_label', 'Target PFZ')}**  "
            + (
                f"🚨 **Detour engaged** — course avoids active hazard geofence."
                if has_detour else
                f"✅ **{geofence_status}**"
            )
        )

        # Waypoints in compact expander
        waypoints = nav_res.get("waypoints", [])
        if waypoints:
            with ctx.expander(f"📍 View Waypoint Route Plan ({len(waypoints)} waypoints)"):
                wp_rows = ""
                for wp in waypoints:
                    leg_dist = f"{wp.get('leg_distance_nm', 0.0):.1f} NM" if wp.get("leg_distance_nm") else "Start"
                    bearing = wp.get("leg_bearing") or "Departure"
                    wp_rows += f"| {wp['name']} | `{wp['lat']:.4f}°N, {wp['lon']:.4f}°E` | {leg_dist} | {bearing} | {wp.get('notes', '')} |\n"
                ctx.markdown(
                    "| Waypoint | Coordinates | Leg Distance | Steer Bearing | Advisory |\n"
                    "|---|---|---|---|---|\n"
                    + wp_rows
                )

    # ── 5. Folium Map ────────────────────────────────────────────────────────
    if fmap is not None:
        ctx.markdown("---\n**🗺️ Interactive Maritime Map** *(click markers for zone details)*")
        st_folium(fmap, width=None, height=480, returned_objects=[], use_container_width=True)

    # ── 6. Technical Evidence Expander (progressive disclosure) ──────────────
    if weather_res and weather_res.get("success"):
        m = weather_res.get("key_metrics", {})
        storm_str = "Yes ⚡" if m.get("thunderstorm_likely") else "No"
        reasoning = weather_res.get("reasoning", "Conditions assessed against IMD/INCOIS guidelines.")
        location = weather_res.get("location", "N/A")
        verdict_v = weather_res.get("verdict", "SAFE")
        emoji_v = VERDICT_EMOJI.get(verdict_v, "ℹ️")
        color_v = VERDICT_COLOR.get(verdict_v, "blue")

        with ctx.expander("🔬 Why ORCA recommends this (Technical Evidence)"):
            st.markdown(
                f"**📍 Observation Point:** {location}  \n"
                f"**Verdict:** :{color_v}[**{emoji_v} {verdict_v}**]\n\n"
                "**📊 Peak Marine Conditions (48-hour forecast window)**\n\n"
                f"| Metric | Measured Value | Threshold |\n"
                f"|---|---|---|\n"
                f"| Wind Speed | {m.get('max_wind_speed_kmh', 0.0):.1f} km/h | 40.0 km/h (Gale) |\n"
                f"| Wind Gust | {m.get('max_wind_gust_kmh', 0.0):.1f} km/h | 55.0 km/h (Severe) |\n"
                f"| Wave Height | {m.get('max_wave_height_m', 0.0):.2f} m | 2.50 m (Hazard) |\n"
                f"| Swell Height | {m.get('max_swell_height_m', 0.0):.2f} m | 2.00 m (High Swell) |\n"
                f"| Wave Period | {m.get('max_wave_period_s', 0.0):.1f} s | — |\n"
                f"| Precipitation | {m.get('max_precipitation_mm', 0.0):.1f} mm/hr | 10.0 mm/hr (Heavy Rain) |\n"
                f"| Convective Energy (CAPE) | {m.get('max_cape_jkg', 0.0):.0f} J/kg | 1500 J/kg (Lightning Limit) |\n"
                f"| Thunderstorm | {storm_str} | Immediate Danger |\n\n"
                f"**🧠 Reasoning & Risk Factors:**  \n{reasoning}\n\n"
                f"**🤖 Agent Pipeline:** {_agents_badge(result)}"
            )

    # ── 7. Compact metadata footer ───────────────────────────────────────────
    ctx.markdown(_metadata_badge_fisherman(result))


# ─────────────────────────────────────────────────────────────────────────────
# Coastal Authority / Disaster Management — Native Widget Renderer
# ─────────────────────────────────────────────────────────────────────────────

# IMD Maritime Disaster Classification thresholds (Beaufort / wave height)
_AUTHORITY_LEVEL_META = {
    "SAFE":    ("Level-0 / Benign",    "🟢", "success"),
    "CAUTION": ("Level-1 / Moderate",  "🟡", "warning"),
    "DANGER":  ("Level-2 / Severe",    "🔴", "error"),
}


def render_authority_response(
    result: dict,
    fmap,
    container=None,
) -> None:
    """
    Render a Marine Operations Center dashboard for the Coastal Authority persona.

    Layout:
      1. 🚨 Disaster Classification Alert Banner (success / warning / error)
      2. 🗺️ Folium map — spatial centrepiece (dominant visual)
      3. 📊 Marine & Meteorological Telemetry (metric columns)
      4. 🛡️ Active Geofence & Exclusion Zone Notices (st.info / st.warning / st.error)
      5. 🧠 Operational Synthesis (plain-language summary)
      6. Collapsed technical expander (full metrics table + agent pipeline)
    """
    ctx = container if container is not None else st

    weather_res = result.get("weather_result")
    nav_res     = result.get("navigation_result")
    pfz_res     = result.get("pfz_result")
    synthesis   = result.get("synthesis", "")
    is_danger   = weather_res and weather_res.get("verdict") == "DANGER"

    # ── 1. Disaster Classification Alert Banner ───────────────────────────────
    verdict = (weather_res.get("verdict", "SAFE") if weather_res and weather_res.get("success") else None)
    level_label, level_dot, banner_type = _AUTHORITY_LEVEL_META.get(
        verdict or "SAFE", ("Level-0 / Benign", "🟢", "success")
    )
    location_str = (
        weather_res.get("location", "N/A") if weather_res else
        pfz_res.get("location", "N/A") if pfz_res else "N/A"
    )

    banner_body = (
        f"**IMD Maritime Classification: {level_dot} {level_label}**  \n"
        f"**Monitored Sector:** {location_str}  \n"
        f"**Sea State Verdict:** {verdict or 'UNKNOWN'} — "
        + (
            "All-clear: standard maritime traffic advisory in effect."
            if (verdict == "SAFE" and not is_danger) else
            "Elevated conditions: heightened coastal surveillance recommended."
            if verdict == "CAUTION" else
            "SEVERE STATE: Activate Level-2/3 response. Issue vessel exclusion and evacuation protocols."
        )
    )
    getattr(ctx, banner_type)(banner_body)

    # Lightning supplement
    if weather_res and weather_res.get("success"):
        m = weather_res.get("key_metrics", {})
        if m.get("lightning_hazard"):
            ctx.error(
                f"⚡ **CONVECTIVE STORM ALERT — LIGHTNING HAZARD:**  \n"
                f"CAPE: **{m.get('max_cape_jkg', 0):.0f} J/kg** (threshold: 1500 J/kg). "
                "Prohibit all small-craft launches. Activate port storm-clearance protocol."
            )

    # ── 2. Folium Map — Spatial Centrepiece ───────────────────────────────────
    if fmap is not None:
        ctx.markdown("---\n#### 🗺️ Coastal Surveillance & Hazard Geofence Chart")
        ctx.caption("Red polygon = active storm-surge exclusion zone · Blue track = monitored vessel corridor")
        st_folium(fmap, width=None, height=520, returned_objects=[], use_container_width=True)
    else:
        ctx.info("📡 No spatial data available for this query. Run a Weather Check or PFZ query to load the geofence chart.")

    ctx.markdown("---")

    # ── 3. Marine & Meteorological Telemetry (metric columns) ─────────────────
    if weather_res and weather_res.get("success"):
        m = weather_res.get("key_metrics", {})
        ctx.markdown("#### 📊 Marine & Meteorological Disaster Telemetry")
        c1, c2, c3, c4 = ctx.columns(4)
        c1.metric("💨 Peak Wind Speed",  f"{m.get('max_wind_speed_kmh', 0.0):.1f} km/h",
                  "⚠ Gale" if m.get("max_wind_speed_kmh", 0) > 40 else "Normal",
                  delta_color="inverse")
        c2.metric("🌊 Max Wave Height",  f"{m.get('max_wave_height_m', 0.0):.2f} m",
                  "⚠ Hazard" if m.get("max_wave_height_m", 0) > 2.5 else "Normal",
                  delta_color="inverse")
        c3.metric("🌀 Wind Gust Peak",   f"{m.get('max_wind_gust_kmh', 0.0):.1f} km/h",
                  "⚠ Severe" if m.get("max_wind_gust_kmh", 0) > 55 else "Normal",
                  delta_color="inverse")
        c4.metric("⚡ CAPE Energy",       f"{m.get('max_cape_jkg', 0.0):.0f} J/kg",
                  "⚠ Lightning Risk" if m.get("max_cape_jkg", 0) > 1500 else "Stable",
                  delta_color="inverse")

        c5, c6, c7, c8 = ctx.columns(4)
        c5.metric("🌊 Swell Height",     f"{m.get('max_swell_height_m', 0.0):.2f} m",
                  "⚠ High Swell" if m.get("max_swell_height_m", 0) > 2.0 else "Manageable",
                  delta_color="inverse")
        c6.metric("🌧️ Precipitation",    f"{m.get('max_precipitation_mm', 0.0):.1f} mm/hr",
                  "⚠ Heavy Rain" if m.get("max_precipitation_mm", 0) > 10 else "Light",
                  delta_color="inverse")
        c7.metric("🕰️ Wave Period",       f"{m.get('max_wave_period_s', 0.0):.1f} s")
        c8.metric("⛈️ Thunderstorm",
                  "Active ⚡" if m.get("thunderstorm_likely") else "None",
                  delta_color="off")

    # ── 4. Active Geofence & Exclusion Zone Notices ───────────────────────────
    ctx.markdown("#### 🛡️ Active Geofence & Surveillance Status")

    geofence_notices = []

    # IMBL proximity
    if nav_res and nav_res.get("imbl_warning_active"):
        imbl_dist = nav_res.get("imbl_min_distance_nm", 0.0)
        imbl_bdry = nav_res.get("imbl_closest_boundary", "IMBL")
        ctx.error(
            f"🛑 **IMBL PROXIMITY BREACH — INTERNATIONAL MARITIME BOUNDARY LINE:**  \n"
            f"Vessel track within **{imbl_dist:.1f} NM** of **{imbl_bdry}**. "
            "Immediate vessel recall recommended. Risk of foreign maritime apprehension."
        )
        geofence_notices.append("IMBL")

    # Disaster verdict-based geofence
    if verdict == "DANGER":
        ctx.error(
            "🚨 **MARITIME EXCLUSION ZONE ACTIVE:**  \n"
            "Severe sea state breach triggers automatic Level-2 geofence protocol. "
            "All small-craft vessels in coastal zone advised to return to port immediately. "
            "Coordinate with IMD/Coast Guard for zone boundary coordinates."
        )
        geofence_notices.append("Storm-surge")
    elif verdict == "CAUTION":
        ctx.warning(
            "⚠️ **LEVEL-1 COASTAL WATCH ZONE:**  \n"
            "Elevated sea conditions — small craft advisory issued. Vessel traffic in affected "
            "sector under Level-1 surveillance. Monitor IMD bulletins for escalation."
        )
        geofence_notices.append("Level-1 Watch")

    if not geofence_notices and verdict == "SAFE":
        ctx.success(
            "✅ **All Clear — No Active Exclusion Zones:**  \n"
            "No maritime geofence triggers active. Standard vessel traffic advisory in effect. "
            "Routine monitoring protocol maintained."
        )

    # PFZ vessel activity notice
    if pfz_res and pfz_res.get("success"):
        zones = pfz_res.get("zones", [])
        best = pfz_res.get("best_zone", {})
        best_name = best.get("name", "—") if best else "—"
        ctx.info(
            f"📍 **Vessel Activity Expected:**  \n"
            f"**{len(zones)} active PFZ clusters** computed near {pfz_res.get('location', 'N/A')}. "
            f"Highest-density zone: **{best_name}**. "
            "Vessels expected in this sector — include in surveillance sweep."
        )

    # ── 5. Operational Synthesis ───────────────────────────────────────────────
    if synthesis:
        ctx.markdown("---\n#### 🧠 ORCA Operational Assessment")
        ctx.markdown(synthesis)

    # ── 6. Technical Evidence Expander ────────────────────────────────────────
    with ctx.expander("📋 Full Disaster Telemetry & Agent Pipeline"):
        if weather_res and weather_res.get("success"):
            m = weather_res.get("key_metrics", {})
            storm_str = "Yes ⚡" if m.get("thunderstorm_likely") else "No"
            reasoning = weather_res.get("reasoning", "Assessed against IMD/INCOIS thresholds.")
            st.markdown(
                "**📊 Complete Peak Conditions Table**\n\n"
                "| Metric | Value | IMD Threshold |\n"
                "|---|---|---|\n"
                f"| Wind Speed | {m.get('max_wind_speed_kmh', 0.0):.1f} km/h | 40.0 km/h (Gale) |\n"
                f"| Wind Gust | {m.get('max_wind_gust_kmh', 0.0):.1f} km/h | 55.0 km/h (Severe) |\n"
                f"| Wave Height | {m.get('max_wave_height_m', 0.0):.2f} m | 2.50 m (Hazard) |\n"
                f"| Swell Height | {m.get('max_swell_height_m', 0.0):.2f} m | 2.00 m (High Swell) |\n"
                f"| Wave Period | {m.get('max_wave_period_s', 0.0):.1f} s | — |\n"
                f"| Precipitation | {m.get('max_precipitation_mm', 0.0):.1f} mm/hr | 10.0 mm/hr |\n"
                f"| CAPE | {m.get('max_cape_jkg', 0.0):.0f} J/kg | 1500 J/kg (Lightning Limit) |\n"
                f"| Thunderstorm | {storm_str} | Immediate Danger |\n\n"
                f"**🧠 IMD Reasoning:** {reasoning}\n\n"
                f"**🤖 Agent Pipeline:** {_agents_badge(result)}"
            )
        else:
            st.markdown(f"**🤖 Agent Pipeline:** {_agents_badge(result)}")

    # ── 7. Full metadata badge ────────────────────────────────────────────────
    ctx.markdown(_metadata_badge(result, "coastal_authority"))


# ─────────────────────────────────────────────────────────────────────────────
# Marine Researcher / Oceanographer — Scientific Analytics Workspace
# ─────────────────────────────────────────────────────────────────────────────

def render_researcher_response(
    result: dict,
    fmap,
    container=None,
) -> None:
    """
    Render a scientific analytics workspace for the Marine Researcher persona.

    Layout:
      1. 📊 Oceanographic KPI Metrics — 4-column st.metric dashboard
      2. 🗺️ EO Satellite Map — SST / Chlorophyll heatmap centrepiece
      3. 🔬 EO Diagnostic Table — full telemetry grid as st.dataframe
      4. 🌊 Weather & Safety Context (if available)
      5. 🧠 Scientific Synthesis
      6. Collapsed expander — raw sensor metadata + agent pipeline
    """
    import pandas as pd
    ctx = container if container is not None else st

    eo_res      = result.get("eo_result")
    weather_res = result.get("weather_result")
    synthesis   = result.get("synthesis", "")

    # ── 1. Oceanographic KPI Metrics ─────────────────────────────────────────
    ctx.markdown("#### 📊 Oceanographic Telemetry — Key Indices")

    if eo_res and eo_res.get("success"):
        sst_mean   = eo_res.get("mean_sst_c", 0.0)
        sst_anom   = eo_res.get("sst_anomaly_c", 0.0)
        chla_mean  = eo_res.get("mean_chlorophyll_mg_m3", 0.0)
        chla_max   = eo_res.get("max_chlorophyll_mg_m3", 0.0)
        thermocline = eo_res.get("thermocline_depth_m", 35)
        upwell_int  = eo_res.get("upwelling_intensity", "—")
        meta        = eo_res.get("sensor_metadata", {})
        salinity    = meta.get("mean_salinity_psu", 34.9)

        anom_sign  = "+" if sst_anom > 0 else ""
        anom_label = f"{anom_sign}{sst_anom:.2f}°C vs climatology"

        chla_delta = "Bloom detected" if chla_max > 2.0 else "Baseline productivity"
        tc_delta   = f"Pycnocline at ~{thermocline} m"

        c1, c2, c3, c4 = ctx.columns(4)
        c1.metric("🌡️ Mean SST",        f"{sst_mean:.2f} °C",   anom_label)
        c2.metric("🌿 Mean Chlorophyll-a", f"{chla_mean:.2f} mg/m³", chla_delta)
        c3.metric("📏 Thermocline Depth",  f"{thermocline} m",     tc_delta)
        c4.metric("🧂 Mean Salinity",      f"{salinity:.1f} PSU")

    elif weather_res and weather_res.get("success"):
        # Fallback when no EO result — show available marine metrics
        m = weather_res.get("key_metrics", {})
        c1, c2, c3, c4 = ctx.columns(4)
        c1.metric("💨 Wind Speed",   f"{m.get('max_wind_speed_kmh', 0.0):.1f} km/h")
        c2.metric("🌊 Wave Height",  f"{m.get('max_wave_height_m', 0.0):.2f} m")
        c3.metric("🌊 Swell Height", f"{m.get('max_swell_height_m', 0.0):.2f} m")
        c4.metric("⚡ CAPE",          f"{m.get('max_cape_jkg', 0.0):.0f} J/kg")
    else:
        ctx.info("📡 Query an ecosystem or SST location to populate the oceanographic telemetry dashboard.")

    # ── 2. EO Satellite Map — Centrepiece ─────────────────────────────────────
    if fmap is not None:
        ctx.markdown("---\n#### 🛰️ ISRO Oceansat-3 / Sentinel-3 Satellite Composite")
        ctx.caption(
            "🛰️ Tip: Use the layer control (top-right of map) to toggle between "
            "**SST Thermal Gradient** and **Chlorophyll-a Productivity** overlays."
        )
        st_folium(fmap, width=None, height=520, returned_objects=[], use_container_width=True)
    else:
        ctx.info(
            "🗺️ No satellite map loaded. Ask about SST / chlorophyll near a coastal location "
            "(e.g. *\"Analyze ocean conditions off Kochi\"*) to render the EO heatmap."
        )

    ctx.markdown("---")

    # ── 3. EO Diagnostic Table ────────────────────────────────────────────────
    if eo_res and eo_res.get("success"):
        sst_min    = eo_res.get("min_sst_c", 0.0)
        sst_max    = eo_res.get("max_sst_c", 0.0)
        sst_mean   = eo_res.get("mean_sst_c", 0.0)
        sst_anom   = eo_res.get("sst_anomaly_c", 0.0)
        chla_mean  = eo_res.get("mean_chlorophyll_mg_m3", 0.0)
        chla_max   = eo_res.get("max_chlorophyll_mg_m3", 0.0)
        upwell_int = eo_res.get("upwelling_intensity", "—")
        thermocline = eo_res.get("thermocline_depth_m", 35)
        front_coords = eo_res.get("upwelling_front_coords", [0.0, 0.0])
        grid_pts   = eo_res.get("grid_points_count", 0)
        meta       = eo_res.get("sensor_metadata", {})
        sst_sensor = meta.get("sst_sensor", "Copernicus Sentinel-3 SLSTR")
        chl_sensor = meta.get("ocean_color_sensor", "ISRO Oceansat-3 OCM-3")
        clim_base  = meta.get("climatology_baseline", "28.5°C")
        chl_res    = meta.get("chl_resolution", "300 m resolution")

        ctx.markdown(
            f"#### 🔬 Earth Observation Diagnostic Summary\n"
            f"**🛰️ Primary Sensors:** {sst_sensor} · {chl_sensor}  \n"
            f"**🌐 Sampling Grid:** {grid_pts} telemetry stations (120 km radius)"
        )

        anom_sign = "+" if sst_anom > 0 else ""
        eo_df = pd.DataFrame({
            "Oceanographic Parameter": [
                "Mean Sea Surface Temp (SST)",
                "SST Range",
                "Thermal Front Anomaly",
                "Mean Chlorophyll-a",
                "Peak Chlorophyll Bloom",
                "Baroclinic Upwelling Index",
                "Estimated Thermocline Depth",
                "Primary Upwelling Front Coords",
            ],
            "Satellite-Derived Value": [
                f"{sst_mean:.2f} °C",
                f"{sst_min:.1f} °C – {sst_max:.1f} °C",
                f"{anom_sign}{sst_anom:.2f} °C",
                f"{chla_mean:.2f} mg/m³",
                f"{chla_max:.2f} mg/m³",
                upwell_int,
                f"~{thermocline} m",
                f"{front_coords[0]:.4f}°N, {front_coords[1]:.4f}°E",
            ],
            "Sensor Payload & Context": [
                f"Sentinel-3 SLSTR infrared radiometry (1 km resolution)",
                f"Spatial gradient across 120 km grid",
                f"Baseline: {clim_base} (climatological mean)",
                f"ISRO Oceansat-3 OCM-3 ({chl_res})",
                f"Shelf-edge primary productivity convergence",
                f"Ekman transport & coastal divergence index",
                f"Subsurface mixed-layer pycnocline",
                f"Maximum horizontal thermal contrast point",
            ],
        })
        ctx.dataframe(eo_df, use_container_width=True, hide_index=True)

    # ── 4. Weather / Safety Context ───────────────────────────────────────────
    if weather_res and weather_res.get("success"):
        m       = weather_res.get("key_metrics", {})
        verdict = weather_res.get("verdict", "SAFE")
        emoji_v = VERDICT_EMOJI.get(verdict, "ℹ️")
        color_v = VERDICT_COLOR.get(verdict, "blue")
        is_lightning = m.get("lightning_hazard", False)

        with ctx.expander("🌦️ Atmospheric & Sea State Context (Weather Agent)", expanded=False):
            if is_lightning:
                st.error(
                    f"⚡ **LIGHTNING HAZARD:** CAPE {m.get('max_cape_jkg', 0):.0f} J/kg — "
                    "convective instability above threshold. Field sampling operations suspended."
                )
            st.markdown(
                f"**📍 Reference Station:** {weather_res.get('location', 'N/A')}  \n"
                f"**Safety Verdict:** :{color_v}[**{emoji_v} {verdict}**]\n\n"
                f"| Metric | Value | Threshold |\n"
                f"|---|---|---|\n"
                f"| Wind Speed | {m.get('max_wind_speed_kmh', 0.0):.1f} km/h | 40.0 km/h |\n"
                f"| Wave Height | {m.get('max_wave_height_m', 0.0):.2f} m | 2.50 m |\n"
                f"| Swell Height | {m.get('max_swell_height_m', 0.0):.2f} m | 2.00 m |\n"
                f"| Precipitation | {m.get('max_precipitation_mm', 0.0):.1f} mm/hr | 10.0 mm/hr |\n"
                f"| CAPE | {m.get('max_cape_jkg', 0.0):.0f} J/kg | 1500 J/kg |\n\n"
                f"**🧠 Reasoning:** {weather_res.get('reasoning', '—')}"
            )

    # ── 5. Scientific Synthesis ───────────────────────────────────────────────
    if synthesis:
        ctx.markdown("---\n#### 🧠 Scientific Assessment")
        ctx.markdown(synthesis)

    # ── 6. Sensor Metadata Expander ───────────────────────────────────────────
    if eo_res and eo_res.get("success"):
        meta = eo_res.get("sensor_metadata", {})
        with ctx.expander("🛰️ Full Sensor Metadata & Agent Pipeline"):
            st.markdown(
                f"**Satellite Constellation:** {meta.get('sst_sensor', '—')} · "
                f"{meta.get('ocean_color_sensor', '—')}\n\n"
                f"| Sensor Parameter | Value |\n"
                f"|---|---|\n"
                f"| SST Resolution | {meta.get('sst_resolution', '1 km')} |\n"
                f"| Chl-a Resolution | {meta.get('chl_resolution', '300 m')} |\n"
                f"| Climatology Baseline | {meta.get('climatology_baseline', '28.5°C')} |\n"
                f"| Repeat Cycle | {meta.get('repeat_cycle', '27 days')} |\n"
                f"| Swath Width | {meta.get('swath_width', '1270 km')} |\n\n"
                f"**🤖 Agent Pipeline:** {_agents_badge(result)}"
            )
    else:
        with ctx.expander("🤖 Agent Pipeline"):
            st.markdown(f"**Pipeline:** {_agents_badge(result)}")

    # ── 7. Metadata footer ────────────────────────────────────────────────────
    ctx.markdown(_metadata_badge(result, "researcher"))


def generate_map_for_result(
    orch_result: dict,
    persona: str = "fisherman",
    show_sst_heatmap: bool = False,
) -> folium.Map | None:
    """
    Generate the appropriate Folium map tailored to the active Stakeholder Persona.
    """
    weather_res = orch_result.get("weather_result")
    pfz_res = orch_result.get("pfz_result")
    nav_res = orch_result.get("navigation_result")
    eo_res = orch_result.get("eo_result")
    pfz_suppressed = orch_result.get("pfz_suppressed", False)
    verdict = weather_res.get("verdict") if weather_res else None

    effective_sst = show_sst_heatmap or bool(eo_res) or (persona == "researcher")

    # Case 1: PFZ Map active (with fuel-optimal navigation track)
    if pfz_res and pfz_res.get("success"):
        lat = pfz_res.get("lat")
        lon = pfz_res.get("lon")
        zones = pfz_res.get("zones", [])
        loc_name = pfz_res.get("location", "Port")
        if lat is not None and lon is not None:
            return create_pfz_map(
                user_lat=lat,
                user_lon=lon,
                pfz_zones=zones,
                user_location_name=loc_name,
                safety_verdict=verdict,
                persona=persona,
                show_sst_heatmap=effective_sst,
                nav_route=nav_res,
            )

    # Case 2: Pure Weather or DANGER suppression hazard map
    if weather_res and weather_res.get("success"):
        lat = weather_res.get("lat")
        lon = weather_res.get("lon")
        loc_name = weather_res.get("location", "Port")
        v = weather_res.get("verdict", "SAFE")
        if lat is not None and lon is not None:
            return create_weather_map(
                user_lat=lat,
                user_lon=lon,
                user_location_name=loc_name,
                safety_verdict=v,
                persona=persona,
                show_sst_heatmap=effective_sst,
            )

    # Case 3: Direct EO result without weather agent
    if eo_res and eo_res.get("success"):
        coords = eo_res.get("center_coords", [0.0, 0.0])
        return create_weather_map(
            user_lat=coords[0],
            user_lon=coords[1],
            user_location_name="Oceanographic Sector",
            safety_verdict="SAFE",
            persona=persona,
            show_sst_heatmap=True,
        )

    return None


def render_history():
    """
    Replay conversation history in chronological order.
    Each persona's assistant messages are re-rendered via their dedicated
    widget renderer. All other messages use plain markdown.
    """
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            orch_result = msg.get("orch_result")
            if orch_result and msg.get("is_fisherman_render"):
                render_fisherman_response(orch_result, fmap=None)   # map shown live only
            elif orch_result and msg.get("is_authority_render"):
                render_authority_response(orch_result, fmap=None)   # map shown live only
            elif orch_result and msg.get("is_researcher_render"):
                render_researcher_response(orch_result, fmap=None)  # map shown live only
            else:
                st.markdown(msg["content"])


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Secondary Controls Only (persona selector moved to top nav)
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    if LOGO_EXISTS:
        st.image(LOGO_PATH, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Persona-specific action controls (persona resolved from top nav below)
    # We read from session_state so sidebar responds to top-nav changes
    _sidebar_persona_label = st.session_state.get("current_persona", "🎣 Artisanal Fisherman")
    if "Artisanal Fisherman" in _sidebar_persona_label:
        _sidebar_persona = "fisherman"
    elif "Coastal Authority" in _sidebar_persona_label:
        _sidebar_persona = "coastal_authority"
    else:
        _sidebar_persona = "researcher"

    show_sst = False
    if _sidebar_persona == "coastal_authority":
        st.subheader("🚨 Disaster Management Panel")
        st.caption("Sector surveillance & emergency broadcast tools.")
        if st.button("📢 Broadcast Emergency Evacuation Alert", use_container_width=True, type="primary"):
            st.success(
                "✅ **Emergency Alert Transmitted!**\n\n"
                "• **VHF Marine:** Channel 16 Broadcast Active\n"
                "• **NAVTEX:** Urgent Warning (518 kHz)\n"
                "• **SMS Gateway:** Dispatched to 142 registered craft\n"
                "• **Geofence:** Maritime Exclusion Zone active"
            )
        st.markdown("---")

    elif _sidebar_persona == "researcher":
        st.subheader("🔬 Earth Observation Telemetry")
        st.caption("Satellite ocean colour and thermal layers.")
        show_sst = st.checkbox(
            "🌡️ Overlay SST / Chlorophyll HeatMap",
            value=True,
            key="sst_heatmap_toggle",
            help="Displays simulated Oceansat-3/Sentinel-3 ocean thermal & chlorophyll gradient.",
        )
        st.markdown("---")

    # Direct Query Controls
    st.header("⚙️ Direct Query Controls")
    st.caption("Trigger multi-agent orchestration for specific locations.")

    # Section 1: Weather Check
    st.subheader("🌦️ Weather Check")
    manual_location = st.text_input("Location", placeholder="e.g. Rameswaram, Kochi", key="sb_weather_loc")
    manual_time = st.selectbox("Time Window", ["today", "tomorrow", "3 days"], key="sb_weather_time")

    if st.button("🔍 Run Weather Check", use_container_width=True):
        if manual_location.strip():
            with st.spinner(f"Querying weather for **{manual_location}**..."):
                orch_result = orchestrator_run({
                    "query": f"What is the weather and sea safety near {manual_location} {manual_time}?",
                    "location": manual_location.strip(),
                    "time_context": manual_time,
                    "persona": _sidebar_persona,
                })
            fmap = generate_map_for_result(orch_result, persona=_sidebar_persona, show_sst_heatmap=show_sst)
            st.session_state.messages.append({
                "role": "user",
                "content": f"📍 Weather check for **{manual_location}** ({manual_time})",
            })
            if _sidebar_persona == "fisherman":
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": orch_result.get("synthesis", "ORCA weather analysis complete."),
                    "orch_result": orch_result,
                    "is_fisherman_render": True,
                })
            elif _sidebar_persona == "coastal_authority":
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": orch_result.get("synthesis", "ORCA operational assessment complete."),
                    "orch_result": orch_result,
                    "is_authority_render": True,
                })
            else:
                # ── Marine Researcher: Scientific Analytics Workspace ──
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": orch_result.get("synthesis", "ORCA scientific analysis complete."),
                    "orch_result": orch_result,
                    "is_researcher_render": True,
                })
            st.session_state.current_map = fmap
            st.rerun()
        else:
            st.warning("Please enter a coastal location.")

    st.divider()

    # Section 2: PFZ Fishing Zones Finder
    st.subheader("🐟 PFZ Zone Finder")
    st.caption("Queries both PFZ and Weather agents concurrently.")
    pfz_loc = st.text_input("Coastal Location", placeholder="e.g. Kochi, Mumbai", key="sb_pfz_loc")

    if st.button("🗺️ Find PFZ Zones", use_container_width=True):
        if pfz_loc.strip():
            with st.spinner(f"Evaluating PFZ & safety for **{pfz_loc}**..."):
                orch_result = orchestrator_run({
                    "query": f"Where can I fish near {pfz_loc} today?",
                    "location": pfz_loc.strip(),
                    "persona": _sidebar_persona,
                })
            fmap = generate_map_for_result(orch_result, persona=_sidebar_persona, show_sst_heatmap=show_sst)
            st.session_state.messages.append({
                "role": "user",
                "content": f"🐟 Fishing zone request near **{pfz_loc}**",
            })
            if _sidebar_persona == "fisherman":
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": orch_result.get("synthesis", "ORCA PFZ analysis complete."),
                    "orch_result": orch_result,
                    "is_fisherman_render": True,
                })
            elif _sidebar_persona == "coastal_authority":
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": orch_result.get("synthesis", "ORCA operational assessment complete."),
                    "orch_result": orch_result,
                    "is_authority_render": True,
                })
            else:
                # ── Marine Researcher: Scientific Analytics Workspace ──
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": orch_result.get("synthesis", "ORCA scientific analysis complete."),
                    "orch_result": orch_result,
                    "is_researcher_render": True,
                })
            st.session_state.current_map = fmap
            st.rerun()
        else:
            st.warning("Please enter a coastal location.")




    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.current_map = None
        st.rerun()

    # ORCA Architecture collapsed into expander — hide complexity from primary user
    with st.expander("⚙️ ORCA Intelligence Architecture"):
        st.markdown("""
**📦 ORCA Architecture (SIH 26176)**
- 🤖 Master Orchestrator (`orchestrator.py`)
- 🛡️ Maritime Safety Gating (`DANGER` suppresses PFZ)
- 👤 3-Stakeholder Persona System
- 🧠 Intent & Multilingual Agent
- 🌦️ Weather & Marine Agent
- 🐟 INCOIS PFZ Fishing Agent
- 🗺️ Interactive Folium Mapping (`OpenStreetMap`)
- 🛰️ Earth Observation (Oceansat-3 / Sentinel-3)
- ⚡ IMD Hazard & Lightning Classification
- 🧭 Fuel-Optimal Navigation & IMBL Geofencing
""")


# ─────────────────────────────────────────────────────────────────────────────
# Global Top Navigation — Horizontal Persona Selector
# ─────────────────────────────────────────────────────────────────────────────

# Brand header
if LOGO_EXISTS:
    col_logo, col_title = st.columns([1, 7], vertical_alignment="center")
    with col_logo:
        st.image(LOGO_PATH, width=90)
    with col_title:
        st.title("ORCA")
        st.caption("Satellite Intelligence for Safer Oceans · ISRO SIH Problem Statement 26176")
else:
    st.title("🌊 ORCA")
    st.caption("Satellite Intelligence for Safer Oceans · ISRO SIH Problem Statement 26176")

st.markdown("<hr class='orca-nav-divider'>", unsafe_allow_html=True)

# Horizontal top-nav persona radio — stays at top of main content
persona_options = [
    "🎣 Artisanal Fisherman",
    "🚨 Coastal Authority / Disaster Management",
    "🔬 Marine Researcher / Oceanographer",
]

def _on_persona_change():
    """Clear chat and map when persona is switched via top nav."""
    st.session_state.messages = []
    st.session_state.current_map = None

current_stored = st.session_state.get("current_persona", "🎣 Artisanal Fisherman")
default_idx = 0
for idx, opt in enumerate(persona_options):
    if (opt == current_stored
            or (current_stored == "fisherman" and "Fisherman" in opt)
            or (current_stored == "coastal_authority" and "Authority" in opt)
            or (current_stored == "researcher" and "Researcher" in opt)):
        default_idx = idx
        break

persona_label = st.radio(
    "**Select Role:**",
    persona_options,
    index=default_idx,
    key="stakeholder_persona_radio",
    horizontal=True,
    on_change=_on_persona_change,
    label_visibility="collapsed",
)

# Sync session_state and clear chat if persona changed
if st.session_state.get("current_persona") != persona_label:
    st.session_state.current_persona = persona_label
    st.session_state.messages = []
    st.session_state.current_map = None

# Resolve internal persona key
if "Artisanal Fisherman" in persona_label or persona_label == "fisherman":
    persona = "fisherman"
elif "Coastal Authority" in persona_label or persona_label == "coastal_authority":
    persona = "coastal_authority"
else:
    persona = "researcher"

st.markdown("<hr class='orca-nav-divider'>", unsafe_allow_html=True)



# Dynamic Persona Header Banner
if persona == "coastal_authority":
    st.warning("""
    🚨 **COASTAL DISASTER MONITORING & MARITIME GEOFENCE ACTIVE**  
    **Surveillance Status:** Level-2 Marine Gale Watch | **Monitored Sector:** Coastal Warning Zone 4  
    *High-risk storm surge & cyclone geofences are actively rendered on charts. Use the sidebar to broadcast evacuation warnings.*
    """)
elif persona == "researcher":
    st.info("""
    🔬 **EARTH OBSERVATION & OCEANOGRAPHIC TELEMETRY (ISRO Oceansat-3 / Sentinel-3 SLSTR)**  
    **Spectral Sensors:** Ocean Colour Monitor (OCM-3) & Sea Surface Temperature (SST) Radiometer  
    *HeatMap overlay visualizes thermal plumes and coastal upwelling fronts driving marine productivity.*
    """)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sea Surface Temp (SST)", "28.4 °C", "+0.4°C anom")
    col2.metric("Chlorophyll-a", "2.15 mg/m³", "Upwelling front")
    col3.metric("Thermocline Depth", "42 m", "-3 m")
    col4.metric("Mean Salinity", "34.9 PSU", "Normal")

st.divider()

# 1. Render message history
render_history()

# 2. Render latest interactive Folium map if available, or default authority map on initial load
if st.session_state.current_map is not None:
    st.markdown("**🗺️ Interactive Maritime Map** *(click markers for oceanographic & zone details)*")
    st_folium(
        st.session_state.current_map,
        width=850,
        height=500,
        returned_objects=[],
    )
elif persona == "coastal_authority" and not st.session_state.messages:
    st.markdown("**🗺️ Hazard Surveillance Overview: Coastal Warning Zone 4 (Chennai–Ennore Sector)**")
    default_auth_map = create_weather_map(
        user_lat=13.0827,
        user_lon=80.2707,
        user_location_name="Coastal Warning Zone 4 (Chennai Sector)",
        safety_verdict="CAUTION",
        persona="coastal_authority",
    )
    st_folium(
        default_auth_map,
        width=850,
        height=480,
        returned_objects=[],
    )
    with st.expander("📋 Zone 4 Maritime Hazard & Surveillance Baseline", expanded=True):
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Active Vessels in Geofence", "142 Small Craft", "Evacuation Ready")
        col_b.metric("Significant Wave Height", "2.10 m", "Elevated Swell")
        col_c.metric("Gale Inundation Risk", "Level 2 (Moderate)", "Surge Watch")
        st.caption("Active surveillance baseline for Coastal Warning Zone 4. Ask a query below or use direct controls to query any port.")

# 3. Welcome banner when chat is fresh (tailored to active Persona)
if not st.session_state.messages:
    with st.chat_message("assistant"):
        if persona == "coastal_authority":
            welcome_text = f"""
👋 **Welcome to ORCA Operations!** Operating in **{persona_label}** mode.

**Try asking:**
- *"Check storm surge risk near Chennai"*
- *"What is the cyclone alert level for Visakhapatnam?"*
- *"Is vessel evacuation recommended off Paradip today?"*
- *"Show active high-wave hazard geofence near Mumbai"*
- *"तूफान और भारी लहरों का अलर्ट चेक करें"* (Hindi)

Use the sidebar to broadcast emergency evacuation notices via VHF Ch 16, NAVTEX, and coastal SMS! 📢
"""
        elif persona == "researcher":
            welcome_text = f"""
👋 **Welcome to ORCA Research!** Operating in **{persona_label}** mode.

**Try asking:**
- *"Analyze SST anomaly and chlorophyll concentrations off Kochi"*
- *"What is the thermocline depth and upwelling status near Mangalore?"*
- *"Compare marine primary productivity indices off Veraval"*
- *"Check coastal salinity and wind stress curl near Tuticorin"*
- *"कोच्चि के पास समुद्री सतह का तापमान और क्लोरोफिल विश्लेषण"* (Hindi)

Toggle the thermal gradient HeatMap in the sidebar to visualize Oceansat-3 & Sentinel-3 telemetry! 🛰️
"""
        else:
            welcome_text = f"""
👋 **Welcome to ORCA!** Operating in **{persona_label}** mode.

**Try asking:**
- *"Where can I fish near Kochi today?"*
- *"Is it safe to go fishing near Rameswaram tomorrow?"*
- *"Show me fishing zones near Mumbai"*
- *"मुंबई के पास मछली कहाँ पकड़ें?"* (Hindi)
- *"ராமேஸ்வரம் அருகே மீன்பிடிக்க எங்கே போவது?"* (Tamil)

Switch between **Fisherman**, **Coastal Authority**, and **Researcher** in the sidebar to inspect role-specific navigation, hazard geofences, and satellite telemetry! 🧭
"""
        st.markdown(welcome_text)

# ── Chat input ────────────────────────────────────────────────────────────────
if user_query := st.chat_input("Ask about sea conditions, fishing zones, or safety..."):

    # A. Display user query
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # B. Route through Orchestrator
    with st.chat_message("assistant"):
        with st.spinner("ORCA agents collaborating & synthesizing..."):
            orch_result = orchestrator_run({"query": user_query, "persona": persona})
            fmap = generate_map_for_result(orch_result, persona=persona, show_sst_heatmap=show_sst)

        if persona == "fisherman":
            # ── Fisherman: progressive disclosure with native Streamlit widgets ──
            render_fisherman_response(orch_result, fmap=fmap)
            # Store orch_result for history replay (synthesis string as fallback text)
            synthesis_text = orch_result.get("synthesis", "ORCA analysis complete.")
            st.session_state.messages.append({
                "role": "assistant",
                "content": synthesis_text,      # plain-text fallback
                "orch_result": orch_result,      # rich result for widget replay
                "is_fisherman_render": True,
            })
        elif persona == "coastal_authority":
            # ── Coastal Authority: Marine Operations Center dashboard ──
            render_authority_response(orch_result, fmap=fmap)
            synthesis_text = orch_result.get("synthesis", "ORCA operational assessment complete.")
            st.session_state.messages.append({
                "role": "assistant",
                "content": synthesis_text,
                "orch_result": orch_result,
                "is_authority_render": True,
            })
        else:
            # ── Marine Researcher: Scientific Analytics Workspace ──
            render_researcher_response(orch_result, fmap=fmap)
            synthesis_text = orch_result.get("synthesis", "ORCA scientific analysis complete.")
            st.session_state.messages.append({
                "role": "assistant",
                "content": synthesis_text,
                "orch_result": orch_result,
                "is_researcher_render": True,
            })

    # D. Save latest map to session state (for the persistent map panel above history)
    st.session_state.current_map = fmap
