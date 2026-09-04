"""
config.py — Central configuration for ORCA.

Loads environment variables from Streamlit secrets (for Streamlit Cloud deployments)
or local .env file (for local development) and exposes them as named constants.

Usage:
    from config import GEMINI_API_KEY, GEMINI_MODEL, WEATHER_API_BASE
"""

import os
from dotenv import load_dotenv

# Load variables from .env into os.environ (does nothing if .env is missing)
load_dotenv()


def get_gemini_api_key() -> str:
    """
    Securely fetch the Gemini API key from Streamlit secrets or os.environ.
    Returns an empty string if not found or invalid.
    """
    key = None
    try:
        import streamlit as st
        # Fetch key from Streamlit's secrets dictionary with an environment fallback
        key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    except Exception:
        # Fall back to os.environ when running outside Streamlit context (e.g. tests)
        key = os.environ.get("GEMINI_API_KEY")

    if key is None:
        key = os.environ.get("GEMINI_API_KEY", "")

    return str(key).strip() if key else ""


# ---------------------------------------------------------------------------
# LLM & API Key Configuration
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = get_gemini_api_key()

if not GEMINI_API_KEY:
    import warnings
    warnings.warn(
        "\n[ORCA] GEMINI_API_KEY is not set in Streamlit secrets or environment. "
        "Agents will operate using robust rule-based fallbacks.\n"
        "  To configure:\n"
        "  - Streamlit Cloud: App settings -> Secrets -> GEMINI_API_KEY = \"...\"\n"
        "  - Local development: Add GEMINI_API_KEY to .env or .streamlit/secrets.toml\n",
        stacklevel=2,
    )

# ---------------------------------------------------------------------------
# Public API base URLs (no keys required)
# ---------------------------------------------------------------------------

# Open-Meteo: atmospheric forecast (wind, rain, temperature)
WEATHER_API_BASE: str = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo Marine: wave height, swell, ocean current
MARINE_API_BASE: str = "https://marine-api.open-meteo.com/v1/marine"

# ---------------------------------------------------------------------------
# Agent defaults
# ---------------------------------------------------------------------------

# Number of forecast days to fetch by default (Open-Meteo supports 1–16)
DEFAULT_FORECAST_DAYS: int = 3

# Gemini model used for all agent reasoning calls
GEMINI_MODEL: str = "gemini-3.6-flash"
