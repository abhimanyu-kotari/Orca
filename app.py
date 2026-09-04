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
# ORCA Design System CSS — Full Enterprise Polish
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Global reset ─────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #F8FAFC !important;
    font-family: 'Inter', 'Segoe UI', sans-serif !important;
    color: #1E293B !important;
}
[data-testid="stMain"] { background-color: #F8FAFC !important; }
[data-testid="stSidebar"] {
    background-color: #061826 !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * { color: #CBD5E1 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #F8FAFC !important; }
[data-testid="stSidebar"] .stMarkdown p { color: #94A3B8 !important; font-size: 0.8rem !important; }
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: 1px solid #1E3A52 !important;
    color: #94A3B8 !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    text-align: left !important;
    padding: 8px 12px !important;
    width: 100% !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #0B2638 !important;
    border-color: #0EA5A8 !important;
    color: #F8FAFC !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #0EA5A8 0%, #0891B2 100%) !important;
    border: 1.5px solid #22D3EE !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 12px rgba(14, 165, 168, 0.4) !important;
}

/* ── Typography ───────────────────────────────── */
h1, h2, h3 {
    color: #0B2638 !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}
h1 { font-size: 1.8rem !important; }
h2 { font-size: 1.3rem !important; }
h3 { font-size: 1.05rem !important; font-weight: 600 !important; }
h4 { color: #334155 !important; font-size: 0.9rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.06em !important; }

/* ── Sticky Persona Selector (Horizontal Radio) ───────────── */
div[data-testid="stVerticalBlock"] > div:has(.st-key-sticky_persona_container),
div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stRadio"]),
div.st-key-sticky_persona_container,
div[data-testid="stElementContainer"]:has(> div.st-key-sticky_persona_container),
div[data-testid="stElementContainer"]:has(div[data-testid="stRadio"]),
div[data-testid="stRadio"],
.stRadio {
    position: -webkit-sticky !important;
    position: sticky !important;
    top: 2rem !important;
    z-index: 999 !important;
    background-color: #F8FAFC !important;
    padding-bottom: 10px !important;
    border-bottom: 1px solid #E2E8F0 !important;
}

/* Ensure Leaflet controls and map canvas stay below the sticky widgets */
.leaflet-top, .leaflet-bottom {
    z-index: 400 !important;
}
.leaflet-pane {
    z-index: 200 !important;
}

/* Clean, simple horizontal persona selector buttons */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    gap: 12px !important;
    width: 100% !important;
    align-items: center !important;
}
div[data-testid="stRadio"] [data-baseweb="radio"],
div[data-testid="stRadio"] label {
    flex: 1 1 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #FFFFFF !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
    margin: 0 !important;
    text-align: center !important;
}
div[data-testid="stRadio"] [data-baseweb="radio"]:hover,
div[data-testid="stRadio"] label:hover {
    border-color: #0EA5A8 !important;
    background: #F0FDFA !important;
}
div[data-testid="stRadio"] [data-baseweb="radio"]:has(input:checked),
div[data-testid="stRadio"] label:has(input:checked),
div[data-testid="stRadio"] [data-baseweb="radio"][aria-checked="true"],
div[data-testid="stRadio"] label[aria-checked="true"] {
    background: #F0FDFA !important;
    border-color: #0EA5A8 !important;
    border-width: 2px !important;
    box-shadow: 0 2px 6px rgba(14, 165, 168, 0.15) !important;
}
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #0B2638 !important;
    margin: 0 !important;
}

/* ── Buttons ──────────────────────────────────── */
div.stButton > button[kind="primary"] {
    background-color: #0EA5A8 !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em !important;
    padding: 10px 24px !important;
}
div.stButton > button[kind="primary"]:hover { background-color: #0891B2 !important; }
div.stButton > button {
    border-radius: 8px !important;
    border: 1.5px solid #CBD8E6 !important;
    color: #0B2638 !important;
    font-weight: 500 !important;
}

/* ── Card system ─────────────────────────────── */
.orca-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    margin-bottom: 16px;
    border: 1px solid #F1F5F9;
}
.orca-card-dark {
    background: #0B2638;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    color: #F8FAFC;
}

/* ── Sea Safety status card ──────────────────── */
.safety-card-safe {
    background: linear-gradient(135deg, #052e16 0%, #064e3b 100%);
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 16px;
    border-left: 5px solid #22c55e;
    color: #F0FDF4;
}
.safety-card-caution {
    background: linear-gradient(135deg, #431407 0%, #7c2d12 100%);
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 16px;
    border-left: 5px solid #f97316;
    color: #FFF7ED;
}
.safety-card-danger {
    background: linear-gradient(135deg, #450a0a 0%, #7f1d1d 100%);
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 16px;
    border-left: 5px solid #ef4444;
    color: #FEF2F2;
}
.safety-verdict { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 4px 0; }
.safety-subtitle { font-size: 0.9rem; opacity: 0.8; margin: 0 0 20px 0; }
.safety-metrics { display: flex; gap: 28px; flex-wrap: wrap; margin-top: 4px; }
.safety-metric { text-align: center; }
.safety-metric-val { font-size: 1.1rem; font-weight: 700; display: block; }
.safety-metric-lbl { font-size: 0.7rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.06em; }
.safety-updated { font-size: 0.72rem; opacity: 0.55; margin-top: 16px; }

/* ── Alert severity cards ────────────────────── */
.alert-critical {
    background: #FEF2F2; border-left: 4px solid #DC2626;
    border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;
}
.alert-warning {
    background: #FFF7ED; border-left: 4px solid #EA580C;
    border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;
}
.alert-advisory {
    background: #FEFCE8; border-left: 4px solid #CA8A04;
    border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;
}
.alert-info {
    background: #F0FDFA; border-left: 4px solid #0EA5A8;
    border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;
}
.alert-title { font-weight: 700; font-size: 0.92rem; color: #1E293B; margin: 0 0 4px 0; }
.alert-meta { font-size: 0.78rem; color: #64748B; margin: 0 0 8px 0; }
.alert-severity-pill {
    display: inline-block; font-size: 0.68rem; font-weight: 700;
    letter-spacing: 0.08em; padding: 2px 8px; border-radius: 20px;
    text-transform: uppercase; margin-bottom: 6px;
}
.pill-critical { background: #DC2626; color: white; }
.pill-warning  { background: #EA580C; color: white; }
.pill-advisory { background: #CA8A04; color: white; }
.pill-info     { background: #0EA5A8; color: white; }
.pill-safe     { background: #16A34A; color: white; }

/* ── Zone cards ──────────────────────────────── */
.zone-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 12px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    transition: box-shadow 0.15s;
}
.zone-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.zone-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.zone-name { font-weight: 700; font-size: 0.95rem; color: #0B2638; }
.zone-badge { font-size: 0.68rem; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
.badge-high   { background: #DCFCE7; color: #15803D; }
.badge-medium { background: #FEF9C3; color: #A16207; }
.badge-low    { background: #FEE2E2; color: #DC2626; }
.zone-dist { font-size: 0.78rem; color: #64748B; margin-bottom: 10px; }
.zone-metrics { display: flex; gap: 16px; margin-bottom: 12px; }
.zone-metric { font-size: 0.78rem; }
.zone-metric-lbl { color: #94A3B8; display: block; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.04em; }
.zone-metric-val { color: #0B2638; font-weight: 600; }

/* ── Route card ──────────────────────────────── */
.route-card {
    background: linear-gradient(135deg, #0B2638 0%, #0F3554 100%);
    border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; color: #F8FAFC;
}
.route-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #64B6D0; margin-bottom: 8px; }
.route-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 14px; color: #F8FAFC; }
.route-stats { display: flex; gap: 28px; flex-wrap: wrap; margin-bottom: 16px; }
.route-stat-val { font-size: 1.05rem; font-weight: 700; color: #22D3EE; display: block; }
.route-stat-lbl { font-size: 0.68rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.06em; }
.route-cta {
    display: inline-block; background: #0EA5A8; color: white !important;
    font-weight: 700; font-size: 0.85rem; padding: 10px 24px;
    border-radius: 8px; text-decoration: none; letter-spacing: 0.04em;
    cursor: pointer; border: none;
}

/* ── Hazard/geofence chips ───────────────────── */
.hazard-chip {
    display: flex; align-items: flex-start; gap: 12px;
    background: #FFF7ED; border: 1px solid #FED7AA;
    border-radius: 10px; padding: 12px 16px; margin-bottom: 8px;
}
.hazard-chip.critical { background: #FEF2F2; border-color: #FECACA; }
.hazard-icon { font-size: 1.2rem; flex-shrink: 0; }
.hazard-content { flex: 1; }
.hazard-title { font-weight: 700; font-size: 0.88rem; color: #1E293B; margin: 0 0 2px 0; }
.hazard-detail { font-size: 0.78rem; color: #64748B; margin: 0; }
.hazard-action { font-size: 0.75rem; color: #0EA5A8; font-weight: 600; margin: 4px 0 0 0; }

/* ── Evidence chain ──────────────────────────── */
.evidence-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #F1F5F9; }
.evidence-row:last-child { border-bottom: none; }
.evidence-check { font-size: 1rem; }
.evidence-label { font-size: 0.85rem; color: #334155; font-weight: 500; flex: 1; }
.evidence-source { font-size: 0.72rem; color: #94A3B8; }
.confidence-bar { height: 6px; background: #E2E8F0; border-radius: 3px; overflow: hidden; margin: 8px 0; }
.confidence-fill { height: 100%; background: linear-gradient(90deg, #0EA5A8, #22D3EE); border-radius: 3px; }
.flow-step {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 12px; border-radius: 8px; margin-bottom: 4px;
    background: #F8FAFC; border: 1px solid #E2E8F0; font-size: 0.82rem;
}
.flow-arrow { color: #CBD5E1; font-size: 0.75rem; margin-left: 12px; }

/* ── Agent pipeline viz ──────────────────────── */
.agent-node {
    background: #F0F9FF; border: 1px solid #BAE6FD;
    border-radius: 8px; padding: 8px 14px; display: inline-block;
    font-size: 0.8rem; font-weight: 600; color: #075985; margin: 4px;
}
.agent-node.completed { background: #F0FDF4; border-color: #BBF7D0; color: #14532D; }
.agent-node.blocked   { background: #FEF2F2; border-color: #FECACA; color: #7F1D1D; }

/* ── Data trust badge ────────────────────────── */
.data-trust {
    display: flex; gap: 16px; align-items: center;
    font-size: 0.72rem; color: #94A3B8; margin-top: 12px;
    padding-top: 10px; border-top: 1px solid #F1F5F9; flex-wrap: wrap;
}
.demo-badge {
    display: inline-block; background: #FEF3C7; color: #92400E;
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.06em;
    padding: 2px 8px; border-radius: 4px; text-transform: uppercase;
}

/* ── Language pills ──────────────────────────── */
.lang-pills { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
.lang-pill {
    background: #EFF6FF; border: 1px solid #BFDBFE;
    color: #1E40AF; border-radius: 20px;
    padding: 3px 12px; font-size: 0.78rem; font-weight: 500;
    cursor: pointer; transition: all 0.12s;
}
.lang-pill:hover, .lang-pill.active {
    background: #0B2638; border-color: #0B2638; color: white;
}

/* ── Researcher insight panel ────────────────── */
.insight-panel { background: #FFFFFF; border-radius: 12px; padding: 18px; border: 1px solid #E2E8F0; }
.insight-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #F8FAFC; }
.insight-row:last-child { border-bottom: none; }
.insight-key { font-size: 0.8rem; color: #64748B; }
.insight-val { font-size: 0.88rem; font-weight: 600; color: #0B2638; }
.insight-badge { display: inline-block; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 20px; }
.badge-anomaly { background: #FEE2E2; color: #DC2626; }
.badge-normal  { background: #DCFCE7; color: #15803D; }
.badge-elevated { background: #FEF9C3; color: #A16207; }

/* ── Streamlit native component polish ───────── */
[data-testid="stMetricValue"] { color: #0B2638 !important; font-weight: 700 !important; font-size: 1.3rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.75rem !important; font-weight: 600 !important; color: #64748B !important; }
[data-testid="stAlert"] { border-radius: 10px !important; border-left-width: 4px !important; }
[data-testid="stChatMessage"] { border-radius: 12px !important; margin-bottom: 8px !important; }
details summary { font-weight: 600 !important; color: #0B2638 !important; }
hr { border-color: #E2E8F0 !important; }
.stTabs [data-baseweb="tab"] { font-weight: 600 !important; font-size: 0.85rem !important; }
.stTabs [data-baseweb="tab-list"] { background: #F8FAFC !important; border-radius: 8px !important; }
[data-testid="stDataFrameContainer"] { border-radius: 10px !important; }

/* ── Responsive ──────────────────────────────── */
@media (max-width: 1280px) { .safety-metrics { gap: 16px; } }
@media (max-width: 768px)  { .safety-verdict { font-size: 1.2rem; } .zone-metrics { flex-direction: column; gap: 6px; } }
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
if "orca_lang" not in st.session_state:
    st.session_state.orca_lang = "en"
if "last_orch_result" not in st.session_state:
    st.session_state.last_orch_result = None
if "show_explainer" not in st.session_state:
    st.session_state.show_explainer = False
if "active_layers" not in st.session_state:
    st.session_state.active_layers = ["SST", "Chlorophyll", "PFZ"]
if "active_nav_view" not in st.session_state:
    st.session_state.active_nav_view = "dashboard"


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

# Language display names for the ORCA input panel
LANG_DISPLAY = {
    "en": "English", "hi": "हिन्दी", "ml": "മലയാളം",
    "ta": "தமிழ்",   "te": "తెలుగు", "kn": "ಕನ್ನಡ",
}


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
        "coastal_authority": "🚨 Coastal Authority / Disaster Management",
        "researcher": "🔬 Marine Researcher / Oceanographer",
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
    Fisherman dashboard — enterprise-polished safety-first layout.

    Layout:
      1. Sea Safety Status Card (HTML gradient card with metric row)
      2. Recommended Fishing Zones (2-col zone cards)
      3. Interactive Map (prominent)
      4. Safe Route Card (dark gradient + CTA)
      5. Areas to Avoid (hazard chips)
      6. Ask ORCA language panel
      7. Why ORCA recommends this (evidence drawer expander)
      8. Data trust badge
    """
    import datetime
    ctx = container if container is not None else st

    weather_res   = result.get("weather_result")
    pfz_res       = result.get("pfz_result")
    nav_res       = result.get("navigation_result")
    nav_suspended = result.get("navigation_suspended", False)
    is_danger     = weather_res and weather_res.get("verdict") == "DANGER"
    is_suspended  = nav_suspended or is_danger

    verdict = None
    m_wx    = {}
    if weather_res and weather_res.get("success"):
        verdict = weather_res.get("verdict", "SAFE")
        m_wx    = weather_res.get("key_metrics", {})

    # ── 1. Sea Safety Status Card ─────────────────────────────────────────────
    now_str      = datetime.datetime.now().strftime("%d %b %Y • %H:%M IST")
    location_str = (weather_res.get("location", "N/A") if weather_res
                    else (pfz_res.get("location", "N/A") if pfz_res else "N/A"))

    if verdict == "SAFE" and not is_suspended:
        card_cls    = "safety-card-safe"
        verdict_txt = "🟢  SAFE FOR DEPARTURE"
        subtitle    = "Low marine risk · All conditions within safe limits"
    elif verdict == "CAUTION" or (verdict == "SAFE" and is_suspended):
        card_cls    = "safety-card-caution"
        verdict_txt = "🟡  EXERCISE CAUTION"
        subtitle    = "Elevated sea state · Proceed with life-jacket compliance"
    elif verdict == "DANGER" or is_suspended:
        card_cls    = "safety-card-danger"
        verdict_txt = "🔴  TRANSIT NOT ADVISED"
        subtitle    = "Hazardous conditions active · Stay ashore until all-clear"
    elif pfz_res and pfz_res.get("success"):
        card_cls    = "safety-card-safe"
        verdict_txt = "🟢  FISHING ZONES IDENTIFIED"
        subtitle    = "INCOIS satellite data · No weather alert in effect"
    else:
        card_cls    = "safety-card-safe"
        verdict_txt = "ℹ️  ORCA ANALYSIS READY"
        subtitle    = "Ask a specific query to get a safety verdict"

    wind_val = f"{m_wx.get('max_wind_speed_kmh', 0.0):.0f} km/h" if m_wx else "—"
    wave_h   = m_wx.get("max_wave_height_m", 0.0)
    wave_lo  = max(0.0, wave_h - 0.3)
    wave_val = f"{wave_lo:.1f}–{wave_h:.1f} m" if m_wx else "—"
    lightning = "High ⚡" if m_wx.get("lightning_hazard") else "Low"
    cyclone   = "Active 🌀" if (verdict == "DANGER" and m_wx) else "None"
    wx_label  = "Stormy" if verdict == "DANGER" else ("Unsettled" if verdict == "CAUTION" else "Clear")

    ctx.markdown(f"""
<div class="{card_cls}">
  <p class="safety-verdict">{verdict_txt}</p>
  <p class="safety-subtitle">📍 {location_str} &nbsp;·&nbsp; {subtitle}</p>
  <div class="safety-metrics">
    <div class="safety-metric"><span class="safety-metric-val">{wind_val}</span><span class="safety-metric-lbl">Wind</span></div>
    <div class="safety-metric"><span class="safety-metric-val">{wave_val}</span><span class="safety-metric-lbl">Wave</span></div>
    <div class="safety-metric"><span class="safety-metric-val">{wx_label}</span><span class="safety-metric-lbl">Weather</span></div>
    <div class="safety-metric"><span class="safety-metric-val">{lightning}</span><span class="safety-metric-lbl">Lightning</span></div>
    <div class="safety-metric"><span class="safety-metric-val">{cyclone}</span><span class="safety-metric-lbl">Cyclone</span></div>
  </div>
  <p class="safety-updated">📡 Data updated: {now_str} &nbsp;·&nbsp; <span class="demo-badge">DEMO DATA</span></p>
</div>
""", unsafe_allow_html=True)

    if is_suspended and m_wx.get("lightning_hazard"):
        ctx.error(f"⚡ Lightning Hazard — CAPE {m_wx.get('max_cape_jkg',0):.0f} J/kg. Open sea transit carries acute lightning strike risk.")

    # ── 2. Recommended Fishing Zones ──────────────────────────────────────────
    if pfz_res and pfz_res.get("success"):
        zones = pfz_res.get("zones", [])
        planning_tag = " *(Pre-voyage planning only — navigation suspended)*" if is_suspended else ""
        ctx.markdown(f"#### 🐟 Recommended Fishing Zones{planning_tag}")
        ctx.caption(f"📍 Reference port: **{pfz_res.get('location','N/A')}** · Based on INCOIS satellite telemetry")

        zone_cols = ctx.columns(2)
        for i, z in enumerate(zones[:6]):
            status    = (z.get("quality") or z.get("status", "MEDIUM")).upper()
            badge_cls = {"HIGH":"badge-high","MEDIUM":"badge-medium","LOW":"badge-low"}.get(status,"badge-medium")
            badge_lbl = {"HIGH":"🟢 HIGH POTENTIAL","MEDIUM":"🟡 MODERATE","LOW":"🔴 LOW"}.get(status, status)
            dist      = z.get("distance_to_user_km", "—")
            dist_str  = f"{dist} km away" if dist != "—" else "Distance N/A"
            sp_raw    = z.get("species", "")
            species   = ", ".join(sp_raw) if isinstance(sp_raw, list) else str(sp_raw)
            sst_val   = f"{z.get('sst_c','—')}°C" if z.get("sst_c") else "—"
            chla_val  = f"{z.get('chlorophyll','—')} mg/m³" if z.get("chlorophyll") else "—"
            depth_val = z.get("depth_m") or z.get("depth", "—")
            zone_name = z.get("name", f"Zone {i+1}")
            potential = "high" if status=="HIGH" else ("moderate" if status=="MEDIUM" else "lower")
            fish_plain = f"Marine conditions suggest {potential} fishing potential in this area."

            zone_cols[i % 2].markdown(f"""
<div class="zone-card">
  <div class="zone-header">
    <span class="zone-name">{zone_name}</span>
    <span class="zone-badge {badge_cls}">{badge_lbl}</span>
  </div>
  <p class="zone-dist">📏 {dist_str} · Depth: {depth_val} m</p>
  <div class="zone-metrics">
    <div class="zone-metric"><span class="zone-metric-lbl">SST</span><span class="zone-metric-val">{sst_val}</span></div>
    <div class="zone-metric"><span class="zone-metric-lbl">Chlorophyll</span><span class="zone-metric-val">{chla_val}</span></div>
    <div class="zone-metric"><span class="zone-metric-lbl">Species</span><span class="zone-metric-val" style="font-size:0.7rem;">{species[:30]}</span></div>
  </div>
  <p style="font-size:0.78rem;color:#475569;margin:4px 0 0 0;">{fish_plain}</p>
</div>
""", unsafe_allow_html=True)

    # ── 3. Interactive Map ────────────────────────────────────────────────────
    if fmap is not None:
        ctx.markdown("#### 🗺️ Maritime Zone Map")
        ctx.caption("Click zone markers for details · Green = high potential · Red = hazard zone")
        st_folium(fmap, width=None, height=460, returned_objects=[], use_container_width=True)

    # ── 4. Safe Route Card ────────────────────────────────────────────────────
    if nav_res and nav_res.get("success"):
        imbl_warn  = nav_res.get("imbl_warning_active", False)
        total_nm   = nav_res.get("total_distance_nm", 0.0)
        total_km   = nav_res.get("total_distance_km", 0.0)
        econ       = nav_res.get("fuel_economy", {})
        cost_saved = econ.get("cost_saved_inr", 0)
        transit    = econ.get("transit_time_str", "—")
        start_lbl  = nav_res.get("start_label", "Port")
        end_lbl    = nav_res.get("end_label", "Target Zone")
        detour     = nav_res.get("hazard_avoidance_active", False)
        risk_label = "⚠ Suspended" if is_suspended else ("🔴 Detour Active" if detour else "🟢 Low Risk")
        susp_note  = "<br><small style='color:#94A3B8;'>⚠ Navigation suspended — shown for pre-voyage planning</small>" if is_suspended else ""

        if imbl_warn:
            imbl_dist = nav_res.get("imbl_min_distance_nm", 0.0)
            ctx.markdown(f"""
<div class="hazard-chip critical">
  <span class="hazard-icon">🛑</span>
  <div class="hazard-content">
    <p class="hazard-title">MARITIME BOUNDARY ALERT — RISK OF IMPOUNDMENT</p>
    <p class="hazard-detail">Route approaches within {imbl_dist:.1f} NM of International Maritime Boundary Line</p>
    <p class="hazard-action">→ Recommended action: Maintain 5 NM seaward clearance</p>
  </div>
</div>
""", unsafe_allow_html=True)

        ctx.markdown(f"""
<div class="route-card">
  <p class="route-label">Recommended Route</p>
  <p class="route-title">⛵ {start_lbl} → {end_lbl}</p>
  <div class="route-stats">
    <div><span class="route-stat-val">{total_km:.1f} km</span><span class="route-stat-lbl">Distance</span></div>
    <div><span class="route-stat-val">{total_nm:.1f} NM</span><span class="route-stat-lbl">Nautical Miles</span></div>
    <div><span class="route-stat-val">{transit}</span><span class="route-stat-lbl">Est. Time</span></div>
    <div><span class="route-stat-val">₹{cost_saved:,.0f}</span><span class="route-stat-lbl">Fuel Savings</span></div>
    <div><span class="route-stat-val">{risk_label}</span><span class="route-stat-lbl">Risk Level</span></div>
  </div>
  <span class="route-cta">{"⚠ PLAN VOYAGE (Suspended)" if is_suspended else "▶ START NAVIGATION"}</span>
  {susp_note}
</div>
""", unsafe_allow_html=True)

        waypoints = nav_res.get("waypoints", [])
        if waypoints:
            with ctx.expander(f"📍 Waypoint Route Plan ({len(waypoints)} waypoints)"):
                wp_rows = ""
                for wp in waypoints:
                    leg_dist = f"{wp.get('leg_distance_nm',0.0):.1f} NM" if wp.get("leg_distance_nm") else "Start"
                    bearing  = wp.get("leg_bearing") or "Departure"
                    wp_rows += f"| {wp['name']} | `{wp['lat']:.4f}°N, {wp['lon']:.4f}°E` | {leg_dist} | {bearing} | {wp.get('notes','')} |\n"
                st.markdown("| Waypoint | Coordinates | Leg Distance | Bearing | Advisory |\n|---|---|---|---|---|\n" + wp_rows)

    # ── 5. Areas to Avoid ─────────────────────────────────────────────────────
    hazards = []
    if nav_res and nav_res.get("imbl_warning_active"):
        hazards.append(("🛑","Maritime Boundary",f"{nav_res.get('imbl_min_distance_nm',0):.1f} NM","Maintain 5 NM seaward clearance","critical"))
    if verdict == "DANGER":
        hazards.append(("🌊","High Wave / Storm Region","Active in sector","Do not depart","critical"))
    elif verdict == "CAUTION":
        hazards.append(("⚠","Elevated Wave Region","In forecast window","Exercise caution","warning"))
    if m_wx.get("lightning_hazard"):
        hazards.append(("⚡","Convective Storm Zone","CAPE above threshold","Avoid open sea","critical"))

    if hazards:
        ctx.markdown("#### ⛔ Areas to Avoid")
        for icon, title, dist_h, action, kind in hazards:
            chip_cls = "hazard-chip critical" if kind == "critical" else "hazard-chip"
            ctx.markdown(f"""
<div class="{chip_cls}">
  <span class="hazard-icon">{icon}</span>
  <div class="hazard-content">
    <p class="hazard-title">{title}</p>
    <p class="hazard-detail">{dist_h}</p>
    <p class="hazard-action">→ {action}</p>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── 6. Ask ORCA Language Panel ─────────────────────────────────────────────
    ctx.markdown("---")
    lang_pills_html = "".join(f'<span class="lang-pill">{v}</span>' for v in LANG_DISPLAY.values())
    ctx.markdown(f"""
<div class="orca-card" style="padding:16px 20px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <span style="font-size:0.85rem;font-weight:700;color:#0B2638;">💬 Ask ORCA</span>
    <span style="font-size:0.72rem;color:#94A3B8;">🎙️ Voice <span style="background:#F1F5F9;padding:2px 8px;border-radius:4px;font-size:0.65rem;color:#64748B;">COMING SOON</span></span>
  </div>
  <p style="font-size:0.8rem;color:#64748B;margin:0 0 8px 0;">Ask about: Fishing · Weather · Safety · Routes · Zones</p>
  <div class="lang-pills">{lang_pills_html}</div>
  <p style="font-size:0.72rem;color:#94A3B8;margin:6px 0 0 0;">Type your question in any language above — ORCA auto-detects it.</p>
</div>
""", unsafe_allow_html=True)

    # ── 7. Why ORCA Recommends This ────────────────────────────────────────────
    if weather_res and weather_res.get("success"):
        confidence = {"SAFE": 87, "CAUTION": 72, "DANGER": 94}.get(verdict or "SAFE", 80)
        reasoning  = weather_res.get("reasoning", "Conditions assessed against IMD/INCOIS guidelines.")
        storm_str  = "Yes ⚡" if m_wx.get("thunderstorm_likely") else "No"

        with ctx.expander("🔬 Why ORCA recommends this · Evidence & confidence"):
            has_pfz = pfz_res is not None
            st.markdown(f"""<div class="orca-card">
<p style="font-weight:700;margin:0 0 8px 0;color:#0B2638;">Evidence Chain</p>
<div class="evidence-row"><span class="evidence-check">✅</span><span class="evidence-label">Satellite Observation</span><span class="evidence-source">ISRO Oceansat-3 · Sentinel-3</span></div>
<div class="evidence-row"><span class="evidence-check">✅</span><span class="evidence-label">Weather Forecast</span><span class="evidence-source">Open-Meteo 48H model</span></div>
<div class="evidence-row"><span class="evidence-check">✅</span><span class="evidence-label">Ocean Conditions</span><span class="evidence-source">INCOIS wave & swell</span></div>
<div class="evidence-row"><span class="evidence-check">✅</span><span class="evidence-label">Geospatial Restrictions</span><span class="evidence-source">IMBL boundary database</span></div>
<div class="evidence-row"><span class="evidence-check">{"✅" if has_pfz else "○"}</span><span class="evidence-label">Fishing Zone Analysis</span><span class="evidence-source">{"INCOIS PFZ advisory" if has_pfz else "Not requested"}</span></div>
</div>
<p style="font-weight:600;margin:8px 0 4px 0;">ORCA Confidence: {confidence}%</p>
<div class="confidence-bar"><div class="confidence-fill" style="width:{confidence}%;"></div></div>
<div class="flow-step">📥 <b>DATA</b> — Raw satellite + weather telemetry ingested <span class="flow-arrow">↓</span></div>
<div class="flow-step">🔍 <b>ANALYSIS</b> — {len(result.get("agents_invoked",[]))} agents ran threshold checks <span class="flow-arrow">↓</span></div>
<div class="flow-step">⚖️ <b>SAFETY ASSESSMENT</b> — IMD/INCOIS thresholds applied → verdict: {verdict or "N/A"} <span class="flow-arrow">↓</span></div>
<div class="flow-step">✅ <b>RECOMMENDATION</b> — {verdict_txt}</div>
""", unsafe_allow_html=True)
            st.markdown(f"""
**📊 Peak Marine Conditions**

| Metric | Value | Threshold |
|---|---|---|
| Wind Speed | {m_wx.get('max_wind_speed_kmh',0.0):.1f} km/h | 40 km/h |
| Wave Height | {m_wx.get('max_wave_height_m',0.0):.2f} m | 2.50 m |
| Wind Gust | {m_wx.get('max_wind_gust_kmh',0.0):.1f} km/h | 55 km/h |
| Swell | {m_wx.get('max_swell_height_m',0.0):.2f} m | 2.00 m |
| CAPE | {m_wx.get('max_cape_jkg',0.0):.0f} J/kg | 1500 J/kg |
| Thunderstorm | {storm_str} | Danger |

**🧠 Reasoning:** {reasoning}

**🤖 Agent Pipeline:** {_agents_badge(result)}
""")

    # ── 8. Data Trust Badge ────────────────────────────────────────────────────
    intent_res = result.get("intent_result", {})
    lang_code  = intent_res.get("language_code", "en")
    lang_name  = intent_res.get("language", "English")
    ctx.markdown(f"""
<div class="data-trust">
  <span>📡 Sources: Satellite · IMD Weather · INCOIS Oceanographic</span>
  <span>·</span><span>🌐 {LANG_FLAG.get(lang_code,"🌐")} {lang_name}</span>
  <span>·</span><span><span class="demo-badge">DEMO DATA</span> Simulated for SIH 26176</span>
</div>
""", unsafe_allow_html=True)




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
    Coastal Authority — Marine Operations Center dashboard.

    Layout:
      1. COASTAL OPERATIONS header + alert tier counts
      2. Severity alert cards (CRITICAL / WARNING / ADVISORY)
      3. Map — dominant spatial centrepiece (580px)
      4. 8-metric telemetry row
      5. Geofence cards (styled HTML chips)
      6. Operational synthesis
      7. Collapsed full telemetry + agent pipeline
    """
    import datetime
    ctx = container if container is not None else st

    weather_res = result.get("weather_result")
    nav_res     = result.get("navigation_result")
    pfz_res     = result.get("pfz_result")
    synthesis   = result.get("synthesis", "")
    is_danger   = weather_res and weather_res.get("verdict") == "DANGER"

    verdict = (weather_res.get("verdict", "SAFE")
               if weather_res and weather_res.get("success") else None)
    m = weather_res.get("key_metrics", {}) if weather_res and weather_res.get("success") else {}
    lightning_hazard = m.get("lightning_hazard", False)
    imbl_active = nav_res and nav_res.get("imbl_warning_active", False)

    level_label, level_dot, banner_type = _AUTHORITY_LEVEL_META.get(
        verdict or "SAFE", ("Level-0 / Benign", "🟢", "success")
    )
    location_str = (
        weather_res.get("location", "N/A") if weather_res else
        pfz_res.get("location", "N/A") if pfz_res else "N/A"
    )
    now_str = datetime.datetime.now().strftime("%d %b %Y · %H:%M IST")

    # ── 1. COASTAL OPERATIONS header ──────────────────────────────────────────
    # Count alert tiers
    n_critical = sum([
        verdict == "DANGER",
        lightning_hazard,
        bool(imbl_active),
    ])
    n_warning  = 1 if verdict == "CAUTION" else 0
    n_advisory = 1 if pfz_res and pfz_res.get("success") else 0

    pill_c = f'<span class="alert-severity-pill pill-critical">🔴 CRITICAL ({n_critical})</span>' if n_critical else              f'<span class="alert-severity-pill pill-safe">🟢 CRITICAL (0)</span>'
    pill_w = f'<span class="alert-severity-pill pill-warning">🟠 WARNING ({n_warning})</span>' if n_warning else              f'<span class="alert-severity-pill pill-safe">🟢 WARNING (0)</span>'
    pill_a = f'<span class="alert-severity-pill pill-advisory">🟡 ADVISORY ({n_advisory})</span>' if n_advisory else              f'<span class="alert-severity-pill pill-safe">🟢 ADVISORY (0)</span>'

    ctx.markdown(f"""
<div class="orca-card-dark" style="display:flex;justify-content:space-between;align-items:center;padding:16px 24px;margin-bottom:4px;">
  <div>
    <p style="font-size:0.65rem;font-weight:700;letter-spacing:0.1em;color:#64B6D0;text-transform:uppercase;margin:0 0 4px 0;">ORCA Marine Intelligence</p>
    <p style="font-size:1.2rem;font-weight:800;color:#F8FAFC;margin:0;">COASTAL OPERATIONS CENTER</p>
    <p style="font-size:0.8rem;color:#94A3B8;margin:4px 0 0 0;">📍 Monitored Sector: {location_str} &nbsp;·&nbsp; {now_str}</p>
  </div>
  <div style="text-align:right;">
    <p style="font-size:0.75rem;color:#CBD5E1;margin:0 0 6px 0;">IMD Classification: {level_dot} <b style="color:#F8FAFC;">{level_label}</b></p>
    <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;">{pill_c}{pill_w}{pill_a}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── 2. Alert Severity Cards ───────────────────────────────────────────────
    alerts_rendered = False

    if verdict == "DANGER":
        ctx.markdown(f"""
<div class="alert-critical">
  <span class="alert-severity-pill pill-critical">🔴 CRITICAL</span>
  <p class="alert-title">Severe Maritime Hazard — {level_label}</p>
  <p class="alert-meta">📍 {location_str} &nbsp;·&nbsp; ⏱ {now_str}</p>
  <p style="font-size:0.82rem;color:#374151;margin:0;">SEVERE STATE: Activate Level-2/3 response. Issue vessel exclusion and evacuation protocols. All small-craft launches prohibited.</p>
</div>
""", unsafe_allow_html=True)
        alerts_rendered = True

    if lightning_hazard:
        ctx.markdown(f"""
<div class="alert-critical">
  <span class="alert-severity-pill pill-critical">🔴 CRITICAL</span>
  <p class="alert-title">⚡ Convective Storm Alert — Lightning Hazard</p>
  <p class="alert-meta">CAPE: {m.get("max_cape_jkg",0):.0f} J/kg &nbsp;·&nbsp; Threshold: 1500 J/kg</p>
  <p style="font-size:0.82rem;color:#374151;margin:0;">Prohibit all small-craft launches. Activate port storm-clearance protocol. Expected duration: 18:00–23:00 IST.</p>
</div>
""", unsafe_allow_html=True)
        alerts_rendered = True

    if imbl_active:
        imbl_dist = nav_res.get("imbl_min_distance_nm", 0.0) if nav_res else 0.0
        imbl_bdry = nav_res.get("imbl_closest_boundary", "IMBL") if nav_res else "IMBL"
        ctx.markdown(f"""
<div class="alert-critical">
  <span class="alert-severity-pill pill-critical">🔴 CRITICAL</span>
  <p class="alert-title">🛑 IMBL Proximity Breach — Risk of Impoundment</p>
  <p class="alert-meta">Distance: {imbl_dist:.1f} NM from {imbl_bdry}</p>
  <p style="font-size:0.82rem;color:#374151;margin:0;">Immediate vessel recall recommended. Coordinate with Coast Guard. Risk of foreign maritime apprehension.</p>
</div>
""", unsafe_allow_html=True)
        alerts_rendered = True

    if verdict == "CAUTION":
        ctx.markdown(f"""
<div class="alert-warning">
  <span class="alert-severity-pill pill-warning">🟠 WARNING</span>
  <p class="alert-title">Level-1 Coastal Watch — Elevated Sea State</p>
  <p class="alert-meta">📍 {location_str} &nbsp;·&nbsp; ⏱ {now_str}</p>
  <p style="font-size:0.82rem;color:#374151;margin:0;">Small craft advisory issued. Vessel traffic under Level-1 surveillance. Monitor IMD bulletins for escalation.</p>
</div>
""", unsafe_allow_html=True)
        alerts_rendered = True

    if pfz_res and pfz_res.get("success"):
        zones    = pfz_res.get("zones", [])
        best     = pfz_res.get("best_zone", {})
        best_nm  = best.get("name", "—") if best else "—"
        ctx.markdown(f"""
<div class="alert-info">
  <span class="alert-severity-pill pill-info">ℹ ADVISORY</span>
  <p class="alert-title">📍 Vessel Activity Expected — {len(zones)} Active PFZ Clusters</p>
  <p class="alert-meta">Sector: {pfz_res.get("location","N/A")} · Highest density: {best_nm}</p>
  <p style="font-size:0.82rem;color:#374151;margin:0;">Include active PFZ cluster in coastal surveillance sweep. Small craft vessels operating in this sector.</p>
</div>
""", unsafe_allow_html=True)

    if not alerts_rendered and verdict == "SAFE":
        ctx.markdown(f"""
<div class="alert-info" style="background:#F0FDF4;border-color:#22c55e;">
  <span class="alert-severity-pill pill-safe">🟢 ALL CLEAR</span>
  <p class="alert-title">No Active Alerts — Standard Maritime Advisory in Effect</p>
  <p class="alert-meta">📍 {location_str} &nbsp;·&nbsp; ⏱ {now_str}</p>
  <p style="font-size:0.82rem;color:#374151;margin:0;">All sea-state thresholds within normal limits. Routine monitoring protocol maintained.</p>
</div>
""", unsafe_allow_html=True)

    # ── 3. Map — Dominant spatial centrepiece ─────────────────────────────────
    if fmap is not None:
        ctx.markdown("#### 🗺️ Coastal Surveillance & Hazard Geofence Chart")
        ctx.caption("Red polygon = active storm-surge exclusion zone · Blue track = monitored vessel corridor · Green pins = PFZ clusters")
        st_folium(fmap, width=None, height=560, returned_objects=[], use_container_width=True)
    else:
        ctx.info("📡 No spatial data available. Run a Weather Check or PFZ query to load the geofence chart.")

    ctx.markdown("---")

    # ── 4. Marine & Meteorological Telemetry (8 metrics) ─────────────────────
    if weather_res and weather_res.get("success"):
        ctx.markdown("#### 📊 Marine & Meteorological Disaster Telemetry")
        c1, c2, c3, c4 = ctx.columns(4)
        c1.metric("💨 Peak Wind",    f"{m.get('max_wind_speed_kmh',0.0):.1f} km/h",
                  "⚠ Gale" if m.get("max_wind_speed_kmh",0) > 40 else "Normal", delta_color="inverse")
        c2.metric("🌊 Max Wave",     f"{m.get('max_wave_height_m',0.0):.2f} m",
                  "⚠ Hazard" if m.get("max_wave_height_m",0) > 2.5 else "Normal", delta_color="inverse")
        c3.metric("🌀 Wind Gust",    f"{m.get('max_wind_gust_kmh',0.0):.1f} km/h",
                  "⚠ Severe" if m.get("max_wind_gust_kmh",0) > 55 else "Normal", delta_color="inverse")
        c4.metric("⚡ CAPE Energy",  f"{m.get('max_cape_jkg',0.0):.0f} J/kg",
                  "⚠ Lightning" if m.get("max_cape_jkg",0) > 1500 else "Stable", delta_color="inverse")
        c5, c6, c7, c8 = ctx.columns(4)
        c5.metric("🌊 Swell",        f"{m.get('max_swell_height_m',0.0):.2f} m",
                  "⚠ High" if m.get("max_swell_height_m",0) > 2.0 else "OK", delta_color="inverse")
        c6.metric("🌧️ Precipitation", f"{m.get('max_precipitation_mm',0.0):.1f} mm/hr",
                  "⚠ Heavy" if m.get("max_precipitation_mm",0) > 10 else "Light", delta_color="inverse")
        c7.metric("🕰️ Wave Period",   f"{m.get('max_wave_period_s',0.0):.1f} s")
        c8.metric("⛈️ Thunderstorm",  "Active ⚡" if m.get("thunderstorm_likely") else "None", delta_color="off")

    # ── 5. Geofence & Exclusion Zones (styled HTML chips) ────────────────────
    ctx.markdown("#### 🛡️ Active Geofence & Exclusion Zone Status")

    if nav_res and nav_res.get("imbl_warning_active"):
        imbl_dist = nav_res.get("imbl_min_distance_nm", 0.0)
        imbl_bdry = nav_res.get("imbl_closest_boundary", "IMBL")
        ctx.markdown(f"""
<div class="hazard-chip critical">
  <span class="hazard-icon">🛑</span>
  <div class="hazard-content">
    <p class="hazard-title">INTERNATIONAL MARITIME BOUNDARY LINE BREACH</p>
    <p class="hazard-detail">Restriction: International maritime law · Distance: {imbl_dist:.1f} NM from {imbl_bdry}</p>
    <p class="hazard-action">→ Immediate vessel recall · Coordinate with Indian Coast Guard · Maintain 5 NM clearance</p>
  </div>
</div>
""", unsafe_allow_html=True)

    if verdict == "DANGER":
        ctx.markdown(f"""
<div class="hazard-chip critical">
  <span class="hazard-icon">🚨</span>
  <div class="hazard-content">
    <p class="hazard-title">MARITIME EXCLUSION ZONE ACTIVE — LEVEL-2 PROTOCOL</p>
    <p class="hazard-detail">Restriction: Severe sea state · Sector: {location_str}</p>
    <p class="hazard-action">→ All small-craft return to port · Activate evacuation protocol · Contact IMD for boundary coords</p>
  </div>
</div>
""", unsafe_allow_html=True)
    elif verdict == "CAUTION":
        ctx.markdown(f"""
<div class="hazard-chip">
  <span class="hazard-icon">⚠️</span>
  <div class="hazard-content">
    <p class="hazard-title">LEVEL-1 COASTAL WATCH ZONE</p>
    <p class="hazard-detail">Restriction: Elevated sea conditions · Sector: {location_str}</p>
    <p class="hazard-action">→ Small craft advisory issued · Level-1 surveillance active · Monitor IMD bulletins</p>
  </div>
</div>
""", unsafe_allow_html=True)

    if not imbl_active and verdict == "SAFE":
        ctx.markdown(f"""
<div class="hazard-chip" style="background:#F0FDF4;border-color:#BBF7D0;">
  <span class="hazard-icon">✅</span>
  <div class="hazard-content">
    <p class="hazard-title" style="color:#15803D;">ALL CLEAR — No Active Exclusion Zones</p>
    <p class="hazard-detail">Standard vessel traffic advisory in effect · Routine monitoring protocol</p>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── 6. Operational Synthesis ──────────────────────────────────────────────
    if synthesis:
        ctx.markdown("---\n#### 🧠 ORCA Operational Assessment")
        ctx.markdown(synthesis)

    # ── 7. Full Disaster Telemetry Expander ───────────────────────────────────
    with ctx.expander("📋 Full Disaster Telemetry & Agent Pipeline"):
        if weather_res and weather_res.get("success"):
            storm_str = "Yes ⚡" if m.get("thunderstorm_likely") else "No"
            reasoning = weather_res.get("reasoning", "Assessed against IMD/INCOIS thresholds.")
            st.markdown(
                f"**📊 Complete Peak Conditions**\n\n"
                f"| Metric | Value | IMD Threshold |\n|---|---|---|\n"
                f"| Wind Speed | {m.get('max_wind_speed_kmh',0.0):.1f} km/h | 40.0 km/h |\n"
                f"| Wind Gust | {m.get('max_wind_gust_kmh',0.0):.1f} km/h | 55.0 km/h |\n"
                f"| Wave Height | {m.get('max_wave_height_m',0.0):.2f} m | 2.50 m |\n"
                f"| Swell Height | {m.get('max_swell_height_m',0.0):.2f} m | 2.00 m |\n"
                f"| Wave Period | {m.get('max_wave_period_s',0.0):.1f} s | — |\n"
                f"| Precipitation | {m.get('max_precipitation_mm',0.0):.1f} mm/hr | 10.0 mm/hr |\n"
                f"| CAPE | {m.get('max_cape_jkg',0.0):.0f} J/kg | 1500 J/kg |\n"
                f"| Thunderstorm | {storm_str} | Danger |\n\n"
                f"**🧠 IMD Reasoning:** {reasoning}\n\n"
                f"**🤖 Agent Pipeline:** {_agents_badge(result)}"
            )
        else:
            st.markdown(f"**🤖 Agent Pipeline:** {_agents_badge(result)}")

    # ── 8. Data Trust Badge ────────────────────────────────────────────────────
    ctx.markdown(f"""
<div class="data-trust">
  <span>📡 Sources: IMD · INCOIS · Coast Guard AIS · IMBL Database</span>
  <span>·</span><span>🕐 {now_str}</span>
  <span>·</span><span><span class="demo-badge">DEMO DATA</span> Simulated for SIH 26176</span>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Marine Researcher / Oceanographer — Scientific Analytics Workspace
# ─────────────────────────────────────────────────────────────────────────────

def render_researcher_response(
    result: dict,
    fmap,
    container=None,
) -> None:
    """
    Marine Researcher — Scientific Analytics Workspace.

    Layout:
      1. 4-column KPI metric dashboard
      2. Two-column workspace: map (60%) + insight panel (40%)
      3. EO Diagnostic dataframe
      4. Time-series tabs (24H / 7D / 30D)
      5. Weather/safety context expander
      6. Scientific synthesis
      7. Sensor metadata + agent pipeline expander
      8. Data trust badge
    """
    import datetime, pandas as pd
    try:
        import plotly.graph_objects as go
        _has_plotly = True
    except ImportError:
        _has_plotly = False

    ctx = container if container is not None else st

    eo_res      = result.get("eo_result")
    weather_res = result.get("weather_result")
    synthesis   = result.get("synthesis", "")
    now_str     = datetime.datetime.now().strftime("%d %b %Y · %H:%M IST")

    # ── 1. Oceanographic KPI Metrics ──────────────────────────────────────────
    ctx.markdown("#### 📊 Oceanographic Telemetry — Key Indices")

    if eo_res and eo_res.get("success"):
        sst_mean    = eo_res.get("mean_sst_c", 0.0)
        sst_anom    = eo_res.get("sst_anomaly_c", 0.0)
        chla_mean   = eo_res.get("mean_chlorophyll_mg_m3", 0.0)
        chla_max    = eo_res.get("max_chlorophyll_mg_m3", 0.0)
        thermocline = eo_res.get("thermocline_depth_m", 35)
        meta        = eo_res.get("sensor_metadata", {})
        salinity    = meta.get("mean_salinity_psu", 34.9)

        anom_sign  = "+" if sst_anom > 0 else ""
        anom_label = f"{anom_sign}{sst_anom:.2f}°C vs climatology"
        chla_delta = "Bloom detected" if chla_max > 2.0 else "Baseline productivity"
        tc_delta   = f"Pycnocline at ~{thermocline} m"

        c1, c2, c3, c4 = ctx.columns(4)
        c1.metric("🌡️ Mean SST",          f"{sst_mean:.2f} °C",      anom_label)
        c2.metric("🌿 Mean Chlorophyll-a", f"{chla_mean:.2f} mg/m³",  chla_delta)
        c3.metric("📏 Thermocline Depth",  f"{thermocline} m",         tc_delta)
        c4.metric("🧂 Mean Salinity",      f"{salinity:.1f} PSU")

    elif weather_res and weather_res.get("success"):
        m = weather_res.get("key_metrics", {})
        c1, c2, c3, c4 = ctx.columns(4)
        c1.metric("💨 Wind Speed",   f"{m.get('max_wind_speed_kmh',0.0):.1f} km/h")
        c2.metric("🌊 Wave Height",  f"{m.get('max_wave_height_m',0.0):.2f} m")
        c3.metric("🌊 Swell Height", f"{m.get('max_swell_height_m',0.0):.2f} m")
        c4.metric("⚡ CAPE",          f"{m.get('max_cape_jkg',0.0):.0f} J/kg")
    else:
        ctx.info("📡 Query an ecosystem or SST location to populate the oceanographic telemetry dashboard.")

    # ── 2. Two-column workspace: Map (60%) + Insight Panel (40%) ─────────────
    if eo_res and eo_res.get("success"):
        sst_mean    = eo_res.get("mean_sst_c", 0.0)
        sst_anom    = eo_res.get("sst_anomaly_c", 0.0)
        chla_mean   = eo_res.get("mean_chlorophyll_mg_m3", 0.0)
        chla_max    = eo_res.get("max_chlorophyll_mg_m3", 0.0)
        upwell_int  = eo_res.get("upwelling_intensity", "—")
        thermocline = eo_res.get("thermocline_depth_m", 35)
        front_coords = eo_res.get("upwelling_front_coords", [0.0, 0.0])

        map_col, insight_col = ctx.columns([3, 2])

        with map_col:
            st.markdown("#### 🛰️ ISRO Oceansat-3 / Sentinel-3 Satellite Composite")
            st.caption("Use layer control (top-right) to toggle **SST Thermal Gradient** and **Chlorophyll-a Productivity**")
            if fmap is not None:
                st_folium(fmap, width=None, height=500, returned_objects=[], use_container_width=True)
            else:
                st.info("🗺️ No satellite map loaded. Query an SST/chlorophyll location to render the EO heatmap.")

        with insight_col:
            anom_cls = "badge-anomaly" if abs(sst_anom) > 1.0 else ("badge-elevated" if abs(sst_anom) > 0.3 else "badge-normal")
            bloom_cls = "badge-anomaly" if chla_max > 2.0 else ("badge-elevated" if chla_max > 1.0 else "badge-normal")
            bloom_lbl = "Bloom" if chla_max > 2.0 else ("Elevated" if chla_max > 1.0 else "Normal")
            upwell_cls = "badge-elevated" if "Moderate" in upwell_int or "Strong" in upwell_int else "badge-normal"

            st.markdown(f"""
<div class="insight-panel">
  <p style="font-weight:700;font-size:0.85rem;color:#0B2638;margin:0 0 12px 0;">🔬 Scientific Insights</p>
  <div class="insight-row">
    <span class="insight-key">SST Anomaly</span>
    <span class="insight-val"><span class="insight-badge {anom_cls}">{'+' if sst_anom > 0 else ''}{sst_anom:.2f}°C</span></span>
  </div>
  <div class="insight-row">
    <span class="insight-key">Chlorophyll Status</span>
    <span class="insight-val"><span class="insight-badge {bloom_cls}">{bloom_lbl}</span></span>
  </div>
  <div class="insight-row">
    <span class="insight-key">Upwelling Index</span>
    <span class="insight-val"><span class="insight-badge {upwell_cls}">{upwell_int}</span></span>
  </div>
  <div class="insight-row">
    <span class="insight-key">Thermocline</span>
    <span class="insight-val">~{thermocline} m depth</span>
  </div>
  <div class="insight-row">
    <span class="insight-key">Upwelling Front</span>
    <span class="insight-val" style="font-size:0.78rem;">{front_coords[0]:.3f}°N, {front_coords[1]:.3f}°E</span>
  </div>
  <div class="insight-row">
    <span class="insight-key">Peak Chl-a</span>
    <span class="insight-val">{chla_max:.2f} mg/m³</span>
  </div>
</div>

<div class="insight-panel" style="margin-top:12px;">
  <p style="font-weight:700;font-size:0.85rem;color:#0B2638;margin:0 0 10px 0;">🛰️ Active Sensors</p>
  <div class="insight-row"><span class="insight-key">SST</span><span class="insight-val" style="font-size:0.75rem;">Sentinel-3 SLSTR · 1 km</span></div>
  <div class="insight-row"><span class="insight-key">Chlorophyll</span><span class="insight-val" style="font-size:0.75rem;">Oceansat-3 OCM-3 · 300 m</span></div>
  <div class="insight-row"><span class="insight-key">Coverage</span><span class="insight-val" style="font-size:0.75rem;">120 km radius · 27-day cycle</span></div>
</div>
""", unsafe_allow_html=True)

    elif fmap is not None:
        ctx.markdown("#### 🛰️ ISRO Oceansat-3 / Sentinel-3 Satellite Composite")
        ctx.caption("Use layer control to toggle SST Thermal Gradient and Chlorophyll-a Productivity")
        st_folium(fmap, width=None, height=500, returned_objects=[], use_container_width=True)

    # ── 3. EO Diagnostic Table ─────────────────────────────────────────────────
    ctx.markdown("---")
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
        anom_sign  = "+" if sst_anom > 0 else ""

        ctx.markdown(
            f"#### 🔬 Earth Observation Diagnostic Summary\n"
            f"**🛰️ Sensors:** {sst_sensor} · {chl_sensor} &nbsp;·&nbsp; "
            f"**🌐 Grid:** {grid_pts} stations (120 km radius)"
        )
        eo_df = pd.DataFrame({
            "Oceanographic Parameter": [
                "Mean Sea Surface Temp (SST)", "SST Range", "Thermal Front Anomaly",
                "Mean Chlorophyll-a", "Peak Chlorophyll Bloom",
                "Baroclinic Upwelling Index", "Estimated Thermocline Depth",
                "Primary Upwelling Front",
            ],
            "Satellite-Derived Value": [
                f"{sst_mean:.2f} °C", f"{sst_min:.1f} – {sst_max:.1f} °C",
                f"{anom_sign}{sst_anom:.2f} °C", f"{chla_mean:.2f} mg/m³",
                f"{chla_max:.2f} mg/m³", upwell_int, f"~{thermocline} m",
                f"{front_coords[0]:.4f}°N, {front_coords[1]:.4f}°E",
            ],
            "Sensor Payload & Context": [
                "Sentinel-3 SLSTR infrared (1 km)", "Spatial gradient across grid",
                f"Baseline: {clim_base}", f"Oceansat-3 OCM-3 ({chl_res})",
                "Shelf-edge productivity convergence", "Ekman transport & coastal divergence",
                "Mixed-layer pycnocline", "Maximum horizontal thermal contrast",
            ],
        })
        ctx.dataframe(eo_df, use_container_width=True, hide_index=True)

    # ── 4. Time-series Tabs ────────────────────────────────────────────────────
    if eo_res and eo_res.get("success"):
        sst_mean  = eo_res.get("mean_sst_c", 28.0)
        chla_mean = eo_res.get("mean_chlorophyll_mg_m3", 1.2)
        ctx.markdown("#### 📈 Time-Series Analysis")
        t1, t2, t3, t4 = ctx.tabs(["24H", "7D", "30D", "CUSTOM"])
        if _has_plotly:
            import plotly.graph_objects as go
            import numpy as np, random
            random.seed(42)

            def _make_ts(n_pts, base_sst, base_chl, noise_sst=0.3, noise_chl=0.2):
                sst_  = [round(base_sst + random.gauss(0, noise_sst), 2) for _ in range(n_pts)]
                chl_  = [round(max(0.1, base_chl + random.gauss(0, noise_chl)), 2) for _ in range(n_pts)]
                return sst_, chl_

            for tab, (n, label, noise_s, noise_c) in zip(
                [t1, t2, t3],
                [(24,"24H",0.2,0.15),(7*6,"7D",0.4,0.25),(30*4,"30D",0.8,0.4)]
            ):
                with tab:
                    sst_s, chl_s = _make_ts(n, sst_mean, chla_mean, noise_s, noise_c)
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        y=sst_s, name="SST (°C)", line=dict(color="#0EA5A8", width=2),
                        fill="tozeroy", fillcolor="rgba(14,165,168,0.08)"
                    ))
                    fig.add_trace(go.Scatter(
                        y=chl_s, name="Chl-a (mg/m³)", line=dict(color="#22D3EE", width=2),
                        yaxis="y2"
                    ))
                    fig.update_layout(
                        height=260, margin=dict(l=0,r=0,t=20,b=0),
                        paper_bgcolor="#F8FAFC", plot_bgcolor="#F8FAFC",
                        legend=dict(orientation="h", y=1.1),
                        yaxis=dict(title="SST (°C)", titlefont=dict(color="#0EA5A8")),
                        yaxis2=dict(title="Chl-a (mg/m³)", overlaying="y", side="right",
                                    titlefont=dict(color="#22D3EE")),
                        font=dict(family="Inter", size=11),
                    )
                    tab.plotly_chart(fig, use_container_width=True)
                    tab.caption(f"⚠ Simulated {label} time-series — requires live ISRO API for real data")

            with t4:
                t4.info("📅 Custom date range requires live ISRO Oceansat-3 API connection.")
        else:
            for tab, label in zip([t1,t2,t3,t4],["24H","7D","30D","Custom"]):
                with tab:
                    tab.info(f"📈 {label} time-series requires plotly. Install with: pip install plotly")

    # ── 5. Weather Context Expander ────────────────────────────────────────────
    if weather_res and weather_res.get("success"):
        m       = weather_res.get("key_metrics", {})
        verdict = weather_res.get("verdict", "SAFE")
        emoji_v = VERDICT_EMOJI.get(verdict, "ℹ️")
        color_v = VERDICT_COLOR.get(verdict, "blue")
        with ctx.expander("🌦️ Atmospheric & Sea State Context", expanded=False):
            if m.get("lightning_hazard"):
                st.error(f"⚡ LIGHTNING HAZARD: CAPE {m.get('max_cape_jkg',0):.0f} J/kg — field sampling suspended.")
            st.markdown(
                f"**📍 Station:** {weather_res.get('location','N/A')} · "
                f"**Verdict:** :{color_v}[**{emoji_v} {verdict}**]\n\n"
                f"| Metric | Value | Threshold |\n|---|---|---|\n"
                f"| Wind Speed | {m.get('max_wind_speed_kmh',0.0):.1f} km/h | 40 km/h |\n"
                f"| Wave Height | {m.get('max_wave_height_m',0.0):.2f} m | 2.50 m |\n"
                f"| Swell | {m.get('max_swell_height_m',0.0):.2f} m | 2.00 m |\n"
                f"| Precipitation | {m.get('max_precipitation_mm',0.0):.1f} mm/hr | 10 mm/hr |\n"
                f"| CAPE | {m.get('max_cape_jkg',0.0):.0f} J/kg | 1500 J/kg |\n\n"
                f"**🧠 Reasoning:** {weather_res.get('reasoning','—')}"
            )

    # ── 6. Scientific Synthesis ────────────────────────────────────────────────
    if synthesis:
        ctx.markdown("---\n#### 🧠 Scientific Assessment")
        ctx.markdown(synthesis)

    # ── 7. Sensor Metadata & Agent Pipeline ───────────────────────────────────
    if eo_res and eo_res.get("success"):
        meta = eo_res.get("sensor_metadata", {})
        with ctx.expander("🛰️ Full Sensor Metadata & Agent Pipeline"):
            st.markdown(
                f"**Constellation:** {meta.get('sst_sensor','—')} · {meta.get('ocean_color_sensor','—')}\n\n"
                f"| Parameter | Value |\n|---|---|\n"
                f"| SST Resolution | {meta.get('sst_resolution','1 km')} |\n"
                f"| Chl-a Resolution | {meta.get('chl_resolution','300 m')} |\n"
                f"| Climatology Baseline | {meta.get('climatology_baseline','28.5°C')} |\n"
                f"| Repeat Cycle | {meta.get('repeat_cycle','27 days')} |\n"
                f"| Swath Width | {meta.get('swath_width','1270 km')} |\n\n"
                f"**🤖 Agent Pipeline:** {_agents_badge(result)}"
            )
    else:
        with ctx.expander("🤖 Agent Pipeline"):
            st.markdown(f"**Pipeline:** {_agents_badge(result)}")

    # ── 8. Data Trust Badge ────────────────────────────────────────────────────
    ctx.markdown(f"""
<div class="data-trust">
  <span>📡 Sources: ISRO Oceansat-3 · Copernicus Sentinel-3 · Open-Meteo</span>
  <span>·</span><span>🕐 {now_str}</span>
  <span>·</span><span><span class="demo-badge">DEMO DATA</span> Simulated for SIH 26176</span>
</div>
""", unsafe_allow_html=True)


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
    st.markdown("<p style='font-size:1.1rem;font-weight:800;color:#F8FAFC;margin:4px 0 0 0;'>ORCA OS</p><p style='font-size:0.75rem;color:#64B6D0;margin:0 0 12px 0;'>Marine Decision Intelligence</p>", unsafe_allow_html=True)

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.current_map = None
        st.session_state.active_nav_view = "dashboard"
        st.rerun()

    st.markdown("<hr style='border-color:#1E3A52;margin:12px 0;'>", unsafe_allow_html=True)

    # ── Stakeholder Persona Context Badge ─────────────────────────────────────
    if "stakeholder_persona_radio" in st.session_state and st.session_state.stakeholder_persona_radio:
        st.session_state.current_persona = st.session_state.stakeholder_persona_radio

    _sidebar_persona_label = st.session_state.get("current_persona", "🎣 Artisanal Fisherman")
    if "Fisherman" in _sidebar_persona_label:
        _sidebar_badge_icon = "🎣"
        _sidebar_badge_name = "Artisanal Fisherman"
        _sidebar_badge_scope = "Fishing • Safety • Navigation"
        _sidebar_persona = "fisherman"
    elif "Authority" in _sidebar_persona_label:
        _sidebar_badge_icon = "🚨"
        _sidebar_badge_name = "Coastal Authority"
        _sidebar_badge_scope = "Hazards • Surveillance • Response"
        _sidebar_persona = "coastal_authority"
    else:
        _sidebar_badge_icon = "🔬"
        _sidebar_badge_name = "Marine Researcher"
        _sidebar_badge_scope = "Ocean Science • Analysis • Trends"
        _sidebar_persona = "researcher"

    st.markdown(f"""
    <div style="background:#0B2638; border:1px solid #1E3A52; border-radius:10px; padding:10px 12px; margin-bottom:12px;">
        <div style="font-size:0.65rem; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; color:#0EA5A8;">
            CURRENT MODE
        </div>
        <div style="font-size:0.88rem; font-weight:700; color:#F8FAFC; margin-top:2px;">
            {_sidebar_badge_icon} {_sidebar_badge_name}
        </div>
        <div style="font-size:0.68rem; color:#94A3B8; margin-top:2px;">
            {_sidebar_badge_scope}
        </div>
    </div>
    """, unsafe_allow_html=True)

    show_sst = False
    if "Coastal Authority" in st.session_state.current_persona or "Authority" in st.session_state.current_persona:
        st.markdown("<p style='font-size:0.68rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;'>Coastal Operations</p>", unsafe_allow_html=True)
        if st.button("📢 Broadcast Evacuation Alert", use_container_width=True, type="primary"):
            st.toast("🚨 Emergency Evacuation Alert broadcasted via VHF Ch 16 and NAVTEX.", icon="📢")
            st.session_state.messages.append({
                "role": "system",
                "content": "System: Evacuation broadcast transmitted to all vessels in Sector.",
            })
            st.rerun()
        st.markdown("<hr style='border-color:#1E3A52;margin:12px 0;'>", unsafe_allow_html=True)
    elif "Researcher" in st.session_state.current_persona:
        st.markdown("<p style='font-size:0.68rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;'>EO Telemetry Layers</p>", unsafe_allow_html=True)
        show_sst = st.checkbox(
            "🌡️ Overlay SST / Chl HeatMap",
            value=True,
            key="sst_heatmap_toggle",
            help="Displays simulated Oceansat-3/Sentinel-3 ocean thermal & chlorophyll gradient.",
        )
        st.markdown("<hr style='border-color:#1E3A52;margin:12px 0;'>", unsafe_allow_html=True)

    # ── Contextual Query Tools ────────────────────────────────────────────────
    with st.expander("⚡ Contextual Query Tools", expanded=False):
        st.caption("Trigger multi-agent orchestration for specific locations.")
        manual_location = st.text_input("Weather Location", placeholder="e.g. Kochi, Veraval", key="sb_weather_loc")
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
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": orch_result.get("synthesis", "ORCA scientific analysis complete."),
                        "orch_result": orch_result,
                        "is_researcher_render": True,
                    })
                st.session_state.current_map = fmap
                st.rerun()

        st.markdown("<hr style='border-color:#1E3A52;margin:8px 0;'>", unsafe_allow_html=True)
        pfz_loc = st.text_input("PFZ Location", placeholder="e.g. Malpe, Karwar", key="sb_pfz_loc")
        if st.button("🐟 Find Fishing Zones", use_container_width=True):
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
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": orch_result.get("synthesis", "ORCA scientific analysis complete."),
                        "orch_result": orch_result,
                        "is_researcher_render": True,
                    })
                st.session_state.current_map = fmap
                st.rerun()

    # ── Section 10: ORCA INTELLIGENCE ─────────────────────────────────────────
    with st.expander("🧠 ORCA INTELLIGENCE (Architecture)", expanded=False):
        st.markdown("""
<div style="font-size:0.75rem;line-height:1.6;color:#94A3B8;">
  <p style="font-weight:700;color:#F8FAFC;margin:0 0 6px 0;">Multi-Agent Orchestration Flow</p>
  <div class="flow-step" style="background:#0B2638;border-color:#1E3A52;color:#CBD5E1;">👤 User Query (Multilingual / Voice)</div>
  <div style="text-align:center;color:#64B6D0;font-size:0.7rem;">↓</div>
  <div class="flow-step" style="background:#0B2638;border-color:#1E3A52;color:#CBD5E1;">🎯 Intent Agent &nbsp;<span style="color:#22c55e;font-weight:700;">[Verified]</span></div>
  <div style="text-align:center;color:#64B6D0;font-size:0.7rem;">↓</div>
  <div class="flow-step" style="background:#0B2638;border-color:#0EA5A8;color:#22D3EE;font-weight:700;">⚙️ Master Orchestrator &nbsp;<span style="color:#22c55e;">[Active]</span></div>
  <div style="text-align:center;color:#64B6D0;font-size:0.7rem;">↓ (Concurrent Dispatch)</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:4px 0;">
    <div style="background:#082032;padding:4px 6px;border-radius:6px;border:1px solid #1E3A52;color:#CBD5E1;font-size:0.7rem;">🌦️ Weather Agent<br><span style="color:#22c55e;">● Completed</span></div>
    <div style="background:#082032;padding:4px 6px;border-radius:6px;border:1px solid #1E3A52;color:#CBD5E1;font-size:0.7rem;">🐟 PFZ Agent<br><span style="color:#22c55e;">● Completed</span></div>
    <div style="background:#082032;padding:4px 6px;border-radius:6px;border:1px solid #1E3A52;color:#CBD5E1;font-size:0.7rem;">🧭 Nav & IMBL<br><span style="color:#22c55e;">● Verified</span></div>
    <div style="background:#082032;padding:4px 6px;border-radius:6px;border:1px solid #1E3A52;color:#CBD5E1;font-size:0.7rem;">🛰️ Earth Obs<br><span style="color:#22c55e;">● Completed</span></div>
  </div>
  <div style="text-align:center;color:#64B6D0;font-size:0.7rem;">↓ (Safety Gating)</div>
  <div class="flow-step" style="background:#0B2638;border-color:#1E3A52;color:#CBD5E1;">🛡️ Hazard & Safety Agent &nbsp;<span style="color:#22c55e;font-weight:700;">[Verified]</span></div>
  <div style="text-align:center;color:#64B6D0;font-size:0.7rem;">↓</div>
  <div class="flow-step" style="background:#0B2638;border-color:#22c55e;color:#86EFAC;font-weight:700;">✅ Decision Synthesis Card</div>
</div>
""", unsafe_allow_html=True)


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

# ─────────────────────────────────────────────────────────────────────────────
# Sticky Persona Selector (Horizontal Radio)
# ─────────────────────────────────────────────────────────────────────────────

persona_options = [
    "🎣 Artisanal Fisherman",
    "🚨 Coastal Authority / Disaster Management",
    "🔬 Marine Researcher / Oceanographer",
]

def _on_persona_change():
    """Clear chat, map, synchronize persona state, and force a clean UI refresh."""
    new_persona = st.session_state.get("stakeholder_persona_radio")
    if new_persona:
        st.session_state.current_persona = new_persona
    st.session_state.messages = []
    st.session_state.current_map = None
    st.rerun()

current_stored = st.session_state.get("current_persona", "🎣 Artisanal Fisherman")
default_idx = 0
for idx, opt in enumerate(persona_options):
    if (opt == current_stored
            or (current_stored == "fisherman" and "Fisherman" in opt)
            or (current_stored == "coastal_authority" and "Authority" in opt)
            or (current_stored == "researcher" and "Researcher" in opt)
            or ("Fisherman" in current_stored and "Fisherman" in opt)
            or ("Authority" in current_stored and "Authority" in opt)
            or ("Researcher" in current_stored and "Researcher" in opt)):
        default_idx = idx
        break

# Wrap the st.radio persona selector in its own dedicated st.container()
sticky_persona_container = st.container(key="sticky_persona_container")
with sticky_persona_container:
    st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] > div:has(.st-key-sticky_persona_container),
    div[data-testid="stElementContainer"]:has(> div.st-key-sticky_persona_container),
    div.st-key-sticky_persona_container {
        position: -webkit-sticky !important;
        position: sticky !important;
        top: 2rem !important;
        z-index: 999 !important;
        background-color: #F8FAFC !important;
        padding-bottom: 10px !important;
        border-bottom: 1px solid #E2E8F0 !important;
    }
    div.st-key-sticky_persona_container div[data-testid="stRadio"] {
        border-bottom: none !important;
    }
    /* Fallback directly on .stRadio if container wrapper is not matched */
    div[data-testid="stRadio"]:not(div.st-key-sticky_persona_container div[data-testid="stRadio"]),
    .stRadio:not(div.st-key-sticky_persona_container .stRadio) {
        position: -webkit-sticky !important;
        position: sticky !important;
        top: 2rem !important;
        z-index: 999 !important;
        background-color: #F8FAFC !important;
        padding-bottom: 10px !important;
        border-bottom: 1px solid #E2E8F0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    persona_label = st.radio(
        "Select Role:",
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
if "Fisherman" in persona_label or persona_label == "fisherman":
    persona = "fisherman"
elif "Authority" in persona_label or persona_label == "coastal_authority":
    persona = "coastal_authority"
else:
    persona = "researcher"

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

active_view = st.session_state.get("active_nav_view", "dashboard")

# ── Navigation Views Dispatcher ───────────────────────────────────────────────
if active_view == "map":
    st.markdown("### 🗺️ Interactive Marine GIS & Earth Observation Map")
    st.caption("Real-time coastal surveillance, satellite SST/Chlorophyll thermal gradient layers, and active navigation tracks.")
    
    col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
    sectors = [
        ("📍 Kochi", "Kochi"),
        ("📍 Malpe", "Malpe"),
        ("📍 Mangalore", "Mangalore"),
        ("📍 Mumbai", "Mumbai"),
        ("📍 Chennai", "Chennai"),
        ("📍 Veraval", "Veraval"),
    ]
    for c, (btn_label, port_name) in zip([col_s1, col_s2, col_s3, col_s4, col_s5, col_s6], sectors):
        if c.button(btn_label, use_container_width=True):
            with st.spinner(f"Rendering GIS spatial layers for {port_name}..."):
                res = orchestrator_run({"query": f"Analyze conditions near {port_name}", "location": port_name, "persona": persona})
                st.session_state.current_map = generate_map_for_result(res, persona=persona, show_sst_heatmap=True)
                st.rerun()

    if st.session_state.current_map is not None:
        st_folium(st.session_state.current_map, width=None, height=560, returned_objects=[], use_container_width=True)
    else:
        def_loc = "Chennai" if persona == "coastal_authority" else "Kochi"
        res = orchestrator_run({"query": f"Analyze conditions near {def_loc}", "location": def_loc, "persona": persona})
        st.session_state.current_map = generate_map_for_result(res, persona=persona, show_sst_heatmap=True)
        st_folium(st.session_state.current_map, width=None, height=560, returned_objects=[], use_container_width=True)

    if st.button("← Return to Dashboard", type="primary"):
        st.session_state.active_nav_view = "dashboard"
        st.rerun()

elif active_view == "alerts":
    st.markdown("### 🚨 Coastal Disaster & Hazard Warning Command Center")
    st.caption("Active monitoring across IMD weather alerts, convective lightning hazards, and IMBL sovereign geofences.")
    
    st.markdown("""
<div class="alert-critical">
  <span class="alert-severity-pill pill-critical">🔴 CRITICAL</span>
  <p class="alert-title">🛑 International Maritime Boundary Line (IMBL) Standoff</p>
  <p class="alert-meta">Palk Strait / Sir Creek Corridors · Active 24/7 Geofence</p>
  <p style="font-size:0.85rem;color:#374151;margin:0;">Vessels approaching within 5 NM of the sovereign maritime boundary face apprehension risk. Automated course deviation and VHF radio standoff protocol enforced.</p>
</div>
<div class="alert-critical">
  <span class="alert-severity-pill pill-critical">🔴 CRITICAL</span>
  <p class="alert-title">⚡ Convective Storm & Acute Lightning Hazard</p>
  <p class="alert-meta">CAPE > 1500 J/kg Threshold Active · Southwest Monsoon Front</p>
  <p style="font-size:0.85rem;color:#374151;margin:0;">High convective available potential energy detected. Open water craft face severe risk of direct lightning strikes. Small-craft departures prohibited in active storm cells.</p>
</div>
<div class="alert-warning">
  <span class="alert-severity-pill pill-warning">🟠 WARNING</span>
  <p class="alert-title">🌊 Gale Wind & High Swell Watch (Level-1)</p>
  <p class="alert-meta">Significant Wave Height 2.2m – 2.8m · Beaufort Force 6</p>
  <p style="font-size:0.85rem;color:#374151;margin:0;">Steep, short-period waves detected over continental shelf edge. Artisanal craft advised to operate with mandatory life-jacket compliance and active AIS transponders.</p>
</div>
<div class="alert-info">
  <span class="alert-severity-pill pill-info">ℹ️ ADVISORY</span>
  <p class="alert-title">🐟 Commercial Fleet Density Advisory</p>
  <p class="alert-meta">Gangolli / Kundapura & Kochi Inshore Banks</p>
  <p style="font-size:0.85rem;color:#374151;margin:0;">INCOIS thermal front convergence indicates high pelagic biomass. Expect dense trawler concentration in designated PFZ corridors.</p>
</div>
""", unsafe_allow_html=True)

    c_al1, c_al2 = st.columns([1, 1])
    with c_al1:
        if st.button("🔍 Run Live Sector Safety Scan", type="primary", use_container_width=True):
            with st.spinner("Executing live safety & hazard scan..."):
                scan_res = orchestrator_run({"query": "Check current sea state and hazard warnings near Kochi", "persona": persona})
                st.session_state.messages.append({"role": "user", "content": "🚨 Manual Live Safety & Hazard Scan"})
                if persona == "fisherman":
                    st.session_state.messages.append({"role": "assistant", "content": scan_res.get("synthesis",""), "orch_result": scan_res, "is_fisherman_render": True})
                elif persona == "coastal_authority":
                    st.session_state.messages.append({"role": "assistant", "content": scan_res.get("synthesis",""), "orch_result": scan_res, "is_authority_render": True})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": scan_res.get("synthesis",""), "orch_result": scan_res, "is_researcher_render": True})
                st.session_state.active_nav_view = "dashboard"
                st.rerun()
    with c_al2:
        if st.button("← Return to Dashboard", use_container_width=True):
            st.session_state.active_nav_view = "dashboard"
            st.rerun()

elif active_view == "reports":
    import datetime
    st.markdown("### 📑 Official Marine Intelligence & Voyage Clearance Report")
    st.caption("ORCA Decision Support System · ISRO SIH Problem Statement 26176")
    now_rep = datetime.datetime.now()
    rep_content = f"""================================================================================
ORCA MARINE DECISION INTELLIGENCE ADVISORY REPORT
Reference ID    : ORCA-VOYAGE-{now_rep.strftime('%Y%m%d-%H%M%S')}
Generated Date  : {now_rep.strftime('%d %B %Y, %H:%M:%S IST')}
Operating Role  : {persona_label}
Target Sector   : Coastal Waters of Western / Peninsular India
================================================================================

1. EXECUTIVE VOYAGE CLEARANCE
--------------------------------------------------------------------------------
Operational Verdict : LEVEL-0 BENIGN (Safe For Departure)
Composite Risk Score: 12 / 100 (Low Marine Risk)
Vessel Suitability  : Artisanal Craft, Mechanized Trawlers, Oceanographic Vessels
Advisory Directive  : Sea conditions cleared for standard marine operations.

2. METEOROLOGICAL TELEMETRY (IMD / OPEN-METEO COMPOSITE)
--------------------------------------------------------------------------------
Peak Wind Speed     : 13.8 km/h (Beaufort 3 - Gentle Breeze)
Significant Wave    : 0.92 m (Safe Small-Craft Threshold < 2.50 m)
Swell Height        : 0.78 m (Wave Period: 9.4s)
Convective Energy   : 380 J/kg (CAPE Limit: 1500 J/kg, Lightning Risk: Low)
Precipitation Rate  : 0.0 mm/hr (Clear Maritime Horizon)

3. SATELLITE EARTH OBSERVATION INDICES (ISRO OCEANSAT-3 / SENTINEL-3)
--------------------------------------------------------------------------------
Sea Surface Temp    : 28.40 °C (Climatology Delta: +0.30°C)
Chlorophyll-a Conc  : 2.10 mg/m³ (Coastal Upwelling Thermal Front)
Thermocline Depth   : ~38 m (Mixed Pycnocline Layer)
Marine Productivity : HIGH - Pelagic Shoal Aggregation (Mackerel / Sardine / Tuna)

4. MARITIME GEOFENCING & NAVIGATION SUMMARY
--------------------------------------------------------------------------------
IMBL Standoff       : Fully Compliant (> 28 NM clearance from international boundary)
Exclusion Zones     : No active naval firing zones or storm-surge exclusions.
Fuel Optimization   : Direct displacement route cleared (est. 18-24% fuel saved).

================================================================================
Validated by : ORCA Autonomous Multi-Agent Orchestration Framework
Authorized by: Marine Safety Division (Demonstration Engine)
================================================================================
"""
    st.code(rep_content, language="text")
    c_dl1, c_dl2 = st.columns([1, 1])
    with c_dl1:
        st.download_button(
            "📥 Download Official Advisory Report (.txt)",
            data=rep_content,
            file_name=f"ORCA_Marine_Report_{now_rep.strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )
    with c_dl2:
        if st.button("← Return to Dashboard", use_container_width=True):
            st.session_state.active_nav_view = "dashboard"
            st.rerun()

elif active_view == "ask_orca":
    st.markdown("### 💬 Ask ORCA — Multi-Agent Marine AI Assistant")
    st.caption("Direct natural language interaction in English, हिन्दी, தமிழ், മലയാളം, and తెలుగు.")
    
    st.markdown("#### ⚡ Suggested Queries for Active Role:")
    if persona == "fisherman":
        p_queries = [
            "Where can I fish near Kochi today?",
            "Is it safe to go fishing near Malpe tomorrow morning?",
            "Check IMBL boundary clearance near Rameswaram",
            "What is the sea wave height near Karwar today?",
        ]
    elif persona == "coastal_authority":
        p_queries = [
            "Check storm surge and cyclone risk near Chennai Sector 4",
            "Show active vessel exclusion zones near Mumbai",
            "Is evacuation recommended off Paradip today?",
            "Assess lightning hazard and CAPE index for Kochi port",
        ]
    else:
        p_queries = [
            "Analyze SST anomaly and chlorophyll concentrations off Kochi",
            "What is the thermocline depth and upwelling status near Mangalore?",
            "Compare primary productivity indices off Veraval",
            "Check coastal salinity and wind stress curl near Tuticorin",
        ]
    
    c_q1, c_q2 = st.columns(2)
    for i, q in enumerate(p_queries):
        col_q = c_q1 if i % 2 == 0 else c_q2
        if col_q.button(f"👉 {q}", use_container_width=True):
            with st.spinner("Processing through ORCA multi-agent engine..."):
                q_res = orchestrator_run({"query": q, "persona": persona})
                st.session_state.messages.append({"role": "user", "content": q})
                if persona == "fisherman":
                    st.session_state.messages.append({"role": "assistant", "content": q_res.get("synthesis",""), "orch_result": q_res, "is_fisherman_render": True})
                elif persona == "coastal_authority":
                    st.session_state.messages.append({"role": "assistant", "content": q_res.get("synthesis",""), "orch_result": q_res, "is_authority_render": True})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": q_res.get("synthesis",""), "orch_result": q_res, "is_researcher_render": True})
                st.session_state.current_map = generate_map_for_result(q_res, persona=persona, show_sst_heatmap=True)
                st.session_state.active_nav_view = "dashboard"
                st.rerun()

    if st.button("← Return to Dashboard", use_container_width=True):
        st.session_state.active_nav_view = "dashboard"
        st.rerun()

else:
    # ── Default "dashboard" view ──
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
            clean_mode = persona_label.split("\n")[0].strip()
            if persona == "coastal_authority":
                welcome_text = f"""
👋 **Welcome to ORCA Operations!** Operating in **{clean_mode}** mode.

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
👋 **Welcome to ORCA Research!** Operating in **{clean_mode}** mode.

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
👋 **Welcome to ORCA!** Operating in **{clean_mode}** mode.

**Try asking:**
- *"Where can I fish near Kochi today?"*
- *"Is it safe to go fishing near Rameswaram tomorrow?"*
- *"Show me fishing zones near Mumbai"*
- *"मुंबई के पास मछली कहाँ पकड़ें?"* (Hindi)
- *"ராமேஸ்வரம் அருகே மீன்பிடிக்க எங்கே போவது?"* (Tamil)

Switch between **Fisherman**, **Coastal Authority**, and **Researcher** at the top of the dashboard to inspect role-specific navigation, hazard geofences, and satellite telemetry! 🧭
"""
            st.markdown(welcome_text.strip())


# ── Chat input ────────────────────────────────────────────────────────────────
if user_query := st.chat_input("Ask about sea conditions, fishing zones, or safety..."):
    st.session_state.active_nav_view = "dashboard"

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
