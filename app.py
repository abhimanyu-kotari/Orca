"""
app.py — ORCA Streamlit Chat Interface (Phase 4)

─────────────────────────────────────────────────────────────────────────────
WHAT CHANGED FROM PHASE 3
─────────────────────────────────────────────────────────────────────────────
  ✅ Full Orchestration: app.py is now a pure rendering layer.
     All queries route through orchestrator.py via run(inputs: dict) -> dict.
  ✅ Multi-Agent Synthesis: Displays synchronized responses combining:
     - Intent & Language recognition
     - Multi-agent AI synthesis
     - Safety Override banners (DANGER suppresses PFZ recommendations)
     - Full weather condition tables & reasoning
     - Potential Fishing Zone tables & top recommendations
     - Interactive Folium maps with safety circles & hotspot markers
  ✅ Parallel Execution: UI shows agents invoked sequentially/concurrently.

ROUTING FLOW (Phase 4)
─────────────────────────────────────────────────────────────────────────────
    User query ──► orchestrator.run()
                         │
                         ├─ Intent & Language Agent
                         │
                         ├─ Parallel Dispatch (ThreadPoolExecutor)
                         │    ├─ Weather & Marine Agent
                         │    └─ PFZ Fishing Zone Agent
                         │
                         ├─ Safety Gating & Cross-Referencing
                         │    (DANGER ──► Suppress PFZ)
                         │    (CAUTION ──► Warning Banner)
                         │
                         └─ Unified Synthesis Dict ──► app.py renders UI + Map

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
# Page configuration — must be the very first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ORCA — Marine Intelligence",
    page_icon="🌊",
    layout="centered",
)


# ─────────────────────────────────────────────────────────────────────────────
# Session state
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
# Rendering & formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

def _metadata_badge(result: dict) -> str:
    """Build the metadata footer indicating language, intent, agents, and source."""
    intent_res = result.get("intent_result", {})
    lang_code = intent_res.get("language_code", "en")
    lang_name = intent_res.get("language", "English")
    flag = LANG_FLAG.get(lang_code, "🌐")
    intent = result.get("intent", "unknown")
    label = INTENT_LABEL.get(intent, intent)
    agents = " ➔ ".join(result.get("agents_invoked", ["orchestrator"]))
    source = result.get("synthesis_source", "orchestrator")

    return (
        f"\n\n---\n"
        f"*{flag} Language: **{lang_name}** · Intent: **{label}** · "
        f"Agents: `{agents}` · Source: `{source}`*"
    )


def format_orchestrator_response(result: dict) -> str:
    """
    Format the complete orchestrator output into markdown.
    Seamlessly integrates synthesis, safety overrides, weather metrics, and PFZ zones.
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

    # 2. Critical Safety Suppression Alert (if triggered)
    if pfz_suppressed and suppression_reason:
        sections.append(
            f"\n> 🚨 **MARITIME SAFETY OVERRIDE ACTIVE:**\n"
            f"> {suppression_reason}"
        )

    # 3. Weather Conditions Details (if available)
    if weather_res and weather_res.get("success"):
        verdict = weather_res.get("verdict", "SAFE")
        emoji = VERDICT_EMOJI.get(verdict, "ℹ️")
        color = VERDICT_COLOR.get(verdict, "blue")
        m = weather_res.get("key_metrics", {})
        storm_str = "Yes ⚡" if m.get("thunderstorm_likely") else "No"

        weather_card = f"""
---
### {emoji} Live Sea Safety Assessment: :{color}[**{verdict}**]
**📍 Monitored Region:** {weather_res.get('location', 'N/A')}

**📊 Peak Marine & Atmospheric Metrics**

| Metric | Measured Value |
|---|---|
| Wind Speed | {m.get('max_wind_speed_kmh', 0.0):.1f} km/h |
| Wind Gust | {m.get('max_wind_gust_kmh', 0.0):.1f} km/h |
| Wave Height | {m.get('max_wave_height_m', 0.0):.2f} m |
| Swell Height | {m.get('max_swell_height_m', 0.0):.2f} m |
| Wave Period | {m.get('max_wave_period_s', 0.0):.1f} s |
| Precipitation | {m.get('max_precipitation_mm', 0.0):.1f} mm/hr |
| Thunderstorm | {storm_str} |

**🧠 Reasoning Trail:**  
{weather_res.get('reasoning', 'Conditions assessed against IMD/INCOIS criteria.')}
"""
        sections.append(weather_card)

    # 4. PFZ Hotspots Table (if available and NOT suppressed)
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
**🏆 Top Recommended Zone:** **{best_name}**  
*Safety Advisory:* {pfz_res.get('safety_note', 'Check local forecasts prior to embarkation.')}
"""
        sections.append(pfz_card)

    # 5. Metadata Badge
    sections.append(_metadata_badge(result))

    return "\n".join(sections)


def generate_map_for_result(orch_result: dict) -> folium.Map | None:
    """
    Generate the appropriate Folium map from the orchestrator's unified result.
    - If PFZ is active and safe/caution: renders interactive PFZ map with safety boundary.
    - If weather is available or PFZ is suppressed: renders weather hazard map.
    """
    weather_res = orch_result.get("weather_result")
    pfz_res = orch_result.get("pfz_result")
    pfz_suppressed = orch_result.get("pfz_suppressed", False)
    verdict = weather_res.get("verdict") if weather_res else None

    # Option 1: PFZ Map with zone hotspots and weather-coloured safety radius
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
            )

    # Option 2: Weather Hazard Map (e.g. for pure weather or DANGER suppression)
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
            )

    return None


def render_history():
    """Replay conversation history in chronological order."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Direct Controls & Demonstrations
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Direct Controls")
    st.caption("Trigger multi-agent orchestration directly with specific parameters.")

    # Section 1: Weather & Safety Check
    st.subheader("🌦️ Weather Check")
    manual_location = st.text_input("Location", placeholder="e.g. Rameswaram, Kochi", key="sb_weather_loc")
    manual_time = st.selectbox("Time Window", ["today", "tomorrow", "3 days"], key="sb_weather_time")

    if st.button("🔍 Run Weather Check", use_container_width=True):
        if manual_location.strip():
            with st.spinner(f"Orchestrator querying weather for **{manual_location}**..."):
                orch_result = orchestrator_run({
                    "query": f"What is the weather and sea safety near {manual_location} {manual_time}?",
                    "location": manual_location.strip(),
                    "time_context": manual_time,
                })
            response_md = format_orchestrator_response(orch_result)
            fmap = generate_map_for_result(orch_result)

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
            with st.spinner(f"Orchestrator evaluating PFZ & safety for **{pfz_loc}**..."):
                orch_result = orchestrator_run({
                    "query": f"Where can I fish near {pfz_loc} today?",
                    "location": pfz_loc.strip(),
                })
            response_md = format_orchestrator_response(orch_result)
            fmap = generate_map_for_result(orch_result)

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
**📦 Phase 4** — Full Orchestration & Multi-Agent Synthesis

**Active Architecture:**
- 🤖 Master Orchestrator (`orchestrator.py`)
- ⚡ Concurrent Parallel Execution (`ThreadPoolExecutor`)
- 🛡️ Maritime Safety Gating (`DANGER` suppresses PFZ)
- 🧠 Intent & Language Agent
- 🌦️ Weather & Marine Agent
- 🐟 PFZ Fishing Zone Agent
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
st.caption("Marine EcoSystem Reasoning with Collaborative Agents · SIH 26176 · Phase 4")
st.divider()

# 1. Render message history
render_history()

# 2. Render latest interactive Folium map if available
if st.session_state.current_map is not None:
    st.markdown("**🗺️ Interactive Maritime Map** *(click markers for oceanographic & zone details)*")
    st_folium(
        st.session_state.current_map,
        width=700,
        height=480,
        returned_objects=[],
    )

# 3. Welcome banner when chat is fresh
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown("""
👋 **Hello! I'm ORCA**, your autonomous collaborative marine intelligence assistant.

In **Phase 4**, all requests are orchestrated across multiple specialized agents in real time:

**Try asking:**
- *"Where can I fish near Kochi today?"* (Executes Weather + PFZ agents in parallel)
- *"Is it safe to go fishing near Rameswaram tomorrow?"*
- *"Show me fishing zones near Mumbai"*
- *"मुंबई के पास मछली कहाँ पकड़ें?"* (Hindi)
- *"ராமேஸ்வரம் அருகே மீன்பிடிக்க எங்கே போவது?"* (Tamil)

If high winds, heavy waves, or thunderstorms cause a **DANGER** state, ORCA will automatically enforce a **safety override** and withhold fishing zones to protect vessels at sea. 🛡️
        """)

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
            response_md = format_orchestrator_response(orch_result)
            fmap = generate_map_for_result(orch_result)

        st.markdown(response_md)

        # C. Render map inline
        if fmap is not None:
            st.markdown("**🗺️ Interactive Maritime Map** *(click markers for oceanographic & zone details)*")
            st_folium(fmap, width=700, height=480, returned_objects=[])

    # D. Save to session state
    st.session_state.messages.append({"role": "assistant", "content": response_md})
    st.session_state.current_map = fmap
