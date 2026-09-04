"""
config.py — Central configuration for ORCA.

Loads environment variables from the .env file and exposes them as named
constants. Import this module anywhere you need an API key or base URL.

Usage:
    from config import GEMINI_API_KEY, WEATHER_API_BASE
"""

import os
from dotenv import load_dotenv

# Load variables from .env into os.environ (does nothing if .env is missing)
load_dotenv()

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    import warnings
    warnings.warn(
        "\n[ORCA] GEMINI_API_KEY is not set. "
        "The Weather Agent's Gemini analysis step will fail.\n"
        "  1. Copy .env.example → .env\n"
        "  2. Paste your key from https://aistudio.google.com/app/apikey\n",
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

# Gemini model used for all agent reasoning calls.
# Updated to gemini-3.6-flash (gemini-2.0-flash was deprecated by Google).
GEMINI_MODEL: str = "gemini-3.6-flash"
