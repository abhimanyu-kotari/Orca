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

import folium
import streamlit as st
from streamlit_folium import st_folium

from orchestrator import run as orchestrator_run
from tools.map_tools import create_pfz_map, create_weather_map


# ─────────────────────────────────────────────────────────────────────────────
# Page configuration
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ORCA — Marine EcoSystem Intelligence",
    page_icon="🌊",
    layout="wide",
)


# ─────────────────────────────────────────────────────────────────────────────
# Session state initialization
# ─────────────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_map" not in st.session_state:
    st.session_state.current_map = None


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

def _metadata_badge(result: dict, persona: str) -> str:
    """Build the metadata footer indicating language, intent, agents, and stakeholder role."""
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
    role_display = role_titles.get(persona, persona)

    return (
        f"\n\n---\n"
        f"*{flag} Language: **{lang_name}** · Intent: **{label}** · "
        f"Agents: `{agents}` · Stakeholder View: **{role_display}***"
    )


def format_orchestrator_response(result: dict, persona: str = "fisherman") -> str:
    """
    Format orchestrator output into markdown tailored to the active Stakeholder Persona.
    """
    synthesis = result.get("synthesis", "")
    weather_res = result.get("weather_result")
    pfz_res = result.get("pfz_result")
    pfz_suppressed = result.get("pfz_suppressed", False)
    suppression_reason = result.get("pfz_suppression_reason")

    sections = []

    # 1. Primary AI / Unified Synthesis
    if synthesis:
        sections.append(synthesis)

    # 2. Critical Safety Suppression Alert
    if pfz_suppressed and suppression_reason:
        sections.append(
            f"\n> 🚨 **MARITIME SAFETY OVERRIDE ENFORCED:**\n"
            f"> {suppression_reason}"
        )

    # 3. Persona Specific Banner / Callouts
    if persona == "coastal_authority":
        sections.append(
            """
> 🛡️ **DISASTER MANAGEMENT NOTICE:**  
> High-risk coastal geofence is active. All small-craft maritime traffic in this sector is under Level-2/3 surveillance.
"""
        )
    elif persona == "researcher":
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
| Thunderstorm | {storm_str} | Immediate Danger |

**🧠 Reasoning & Risk Factors:**  
{weather_res.get('reasoning', 'Conditions assessed against IMD/INCOIS guidelines.')}
"""
        sections.append(weather_card)

    # 5. PFZ Hotspots Table (if available and NOT suppressed)
    if pfz_res and not pfz_suppressed and pfz_res.get("success"):
        zones = pfz_res.get("zones", [])
        best = pfz_res.get("best_zone", {})
        zone_rows = ""
        for i, z in enumerate(zones, start=1):
            quality_dot = QUALITY_EMOJI.get(z.get("quality", "MEDIUM"), "⚪")
            species_str = ", ".join(z.get("species", []))
            zone_rows += (
                f"| {i} | {quality_dot} {z.get('name', 'N/A')} | "
                f"{z.get('distance_to_user_km', '—')} km | "
                f"{z.get('depth_m', '—')} m | "
                f"{species_str} |\n"
            )

        best_name = best.get("name", "—") if best else "—"
        pfz_card = f"""
---
### 🐟 Potential Fishing Zones (INCOIS Data)
**📍 Reference Port:** {pfz_res.get('location', 'N/A')}

| # | Zone Name | Distance | Depth | Commercially Viable Species |
|---|---|---|---|---|
{zone_rows}
**🏆 Top Recommended Hotspot:** **{best_name}**  
*Advisory:* {pfz_res.get('safety_note', 'Check local forecasts prior to embarkation.')}
"""
        sections.append(pfz_card)

    # 6. Metadata Badge
    sections.append(_metadata_badge(result, persona))

    return "\n".join(sections)


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
    pfz_suppressed = orch_result.get("pfz_suppressed", False)
    verdict = weather_res.get("verdict") if weather_res else None

    # Case 1: PFZ Map active
    if pfz_res and not pfz_suppressed and pfz_res.get("success"):
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
                show_sst_heatmap=show_sst_heatmap,
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
                show_sst_heatmap=show_sst_heatmap,
            )

    return None


def render_history():
    """Replay conversation history in chronological order."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Persona Selector & Stakeholder Controls
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("👤 Stakeholder Profile")
    st.caption("Select your role defined in ISRO Problem Statement 26176.")

    persona_label = st.radio(
        "Active Role Perspective:",
        [
            "🎣 Artisanal Fisherman",
            "🚨 Coastal Authority / Disaster Management",
            "🔬 Marine Researcher / Oceanographer",
        ],
        index=0,
        key="stakeholder_persona_radio",
    )

    if "Artisanal Fisherman" in persona_label:
        persona = "fisherman"
    elif "Coastal Authority" in persona_label:
        persona = "coastal_authority"
    else:
        persona = "researcher"

    # Persona-specific action controls
    show_sst = False
    if persona == "coastal_authority":
        st.markdown("---")
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

    elif persona == "researcher":
        st.markdown("---")
        st.subheader("🔬 Earth Observation Telemetry")
        st.caption("Satellite ocean colour and thermal layers.")
        show_sst = st.checkbox(
            "🌡️ Overlay SST / Chlorophyll HeatMap",
            value=True,
            key="sst_heatmap_toggle",
            help="Displays simulated Oceansat-3/Sentinel-3 ocean thermal & chlorophyll gradient.",
        )

    st.markdown("---")
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
                })
            response_md = format_orchestrator_response(orch_result, persona=persona)
            fmap = generate_map_for_result(orch_result, persona=persona, show_sst_heatmap=show_sst)

            st.session_state.messages.append({
                "role": "user",
                "content": f"📍 Weather check for **{manual_location}** ({manual_time})",
            })
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_md,
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
                })
            response_md = format_orchestrator_response(orch_result, persona=persona)
            fmap = generate_map_for_result(orch_result, persona=persona, show_sst_heatmap=show_sst)

            st.session_state.messages.append({
                "role": "user",
                "content": f"🐟 Fishing zone request near **{pfz_loc}**",
            })
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_md,
            })
            st.session_state.current_map = fmap
            st.rerun()
        else:
            st.warning("Please enter a coastal location.")

    st.divider()

    st.markdown("""
**📦 ORCA Architecture (SIH 26176)**
- 🤖 Master Orchestrator (`orchestrator.py`)
- 🛡️ Maritime Safety Gating (`DANGER` suppresses PFZ)
- 👤 3-Stakeholder Persona System
- 🧠 Intent & Multilingual Agent
- 🌦️ Weather & Marine Agent
- 🐟 INCOIS PFZ Fishing Agent
- 🗺️ Interactive Folium Mapping (`OpenStreetMap`)
""")

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.current_map = None
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Main Chat UI
# ─────────────────────────────────────────────────────────────────────────────

st.title("🌊 ORCA")
st.caption("Marine EcoSystem Reasoning with Collaborative Agents · ISRO SIH Problem Statement 26176")

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
            orch_result = orchestrator_run({"query": user_query})
            response_md = format_orchestrator_response(orch_result, persona=persona)
            fmap = generate_map_for_result(orch_result, persona=persona, show_sst_heatmap=show_sst)

        st.markdown(response_md)

        # C. Render map inline
        if fmap is not None:
            st.markdown("**🗺️ Interactive Maritime Map** *(click markers for oceanographic & zone details)*")
            st_folium(fmap, width=850, height=500, returned_objects=[])

    # D. Save to session state
    st.session_state.messages.append({"role": "assistant", "content": response_md})
    st.session_state.current_map = fmap
