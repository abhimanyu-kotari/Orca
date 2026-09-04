"""
tools/weather_tools.py — Pure data-fetching functions for weather and marine conditions.

DESIGN PRINCIPLE:
    These functions are "dumb" data fetchers — they make HTTP requests and return
    raw structured data. They contain NO AI logic, no Gemini calls, and no
    safety judgements. That reasoning happens in the agent layer above.

APIs used (both are free and require NO API key):
    Open-Meteo Forecast : https://open-meteo.com/
    Open-Meteo Marine   : https://open-meteo.com/en/docs/marine-weather-api
    Nominatim Geocoder  : https://nominatim.org/

Functions:
    get_coordinates(location_name)          → Converts city name to lat/lon
    fetch_atmospheric_weather(lat, lon)     → Wind, rain, temperature forecast
    fetch_marine_conditions(lat, lon)       → Wave height, swell, ocean current
    extract_conditions_for_window(data, ..) → Slices hourly data to a time window
"""

import httpx
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

from config import WEATHER_API_BASE, MARINE_API_BASE, DEFAULT_FORECAST_DAYS


# ─────────────────────────────────────────────────────────────────────────────
# Geocoding: location name → (lat, lon)
# ─────────────────────────────────────────────────────────────────────────────

def get_coordinates(location_name: str) -> dict:
    """
    Convert a human-readable place name to GPS coordinates using Nominatim.

    Nominatim is OpenStreetMap's free geocoder — no API key required,
    but it enforces a 1 request/second rate limit.

    Args:
        location_name (str): e.g. "Rameswaram", "Mumbai port", "Visakhapatnam"

    Returns:
        On success:
            {
                "success":  True,
                "location": "Rameswaram, Ramanathapuram, Tamil Nadu, India",
                "lat":      9.2876,
                "lon":      79.3129
            }
        On failure:
            {
                "success": False,
                "error":   "Could not find location: 'XYZ'"
            }
    """
    geocoder = Nominatim(user_agent="orca_marine_platform_v1")

    try:
        result = geocoder.geocode(location_name, timeout=10)

        if result is None:
            return {
                "success": False,
                "error": f"Could not find location: '{location_name}'. "
                         "Try a more specific name (e.g. 'Rameswaram, Tamil Nadu').",
            }

        return {
            "success":  True,
            "location": result.address,
            "lat":      result.latitude,
            "lon":      result.longitude,
        }

    except GeocoderTimedOut:
        return {"success": False, "error": "Geocoder timed out. Check your internet connection."}
    except GeocoderUnavailable:
        return {"success": False, "error": "Nominatim geocoder is currently unavailable."}


# ─────────────────────────────────────────────────────────────────────────────
# Atmospheric weather: wind, rain, temperature
# ─────────────────────────────────────────────────────────────────────────────

def fetch_atmospheric_weather(lat: float, lon: float, days: int = DEFAULT_FORECAST_DAYS) -> dict:
    """
    Fetch hourly atmospheric forecast from Open-Meteo.

    Covers the conditions most relevant for vessel safety:
        - Wind speed & gusts: primary capsize/navigation hazard
        - Precipitation:      reduces visibility and increases wave chop
        - Visibility:         critical for navigation
        - Weather code:       WMO standard codes (thunderstorm = 95/96/99)

    Args:
        lat  (float): Latitude  (e.g. 9.2876)
        lon  (float): Longitude (e.g. 79.3129)
        days (int):   Forecast horizon in days (1–7). Default: 3.

    Returns:
        Raw Open-Meteo JSON as a Python dict, e.g.:
            {
                "latitude":  9.25,
                "longitude": 79.25,
                "timezone":  "Asia/Kolkata",
                "hourly": {
                    "time":             ["2024-01-01T00:00", ...],
                    "temperature_2m":   [28.1, 28.4, ...],
                    "wind_speed_10m":   [12.3, 14.1, ...],
                    ...
                }
            }
        Or {"error": "..."} if the request fails.
    """
    params = {
        "latitude":     lat,
        "longitude":    lon,
        "forecast_days": days,
        "timezone":     "auto",   # Detect timezone from coordinates (e.g. "Asia/Kolkata")
        "hourly": ",".join([
            "temperature_2m",       # Air temperature at 2 m height (°C)
            "wind_speed_10m",       # Wind speed at 10 m height (km/h)
            "wind_gusts_10m",       # Peak wind gust at 10 m height (km/h)
            "wind_direction_10m",   # Wind direction (0–360°, 0 = North)
            "precipitation",        # Hourly precipitation sum (mm)
            "visibility",           # Horizontal visibility (metres)
            "weather_code",         # WMO weather interpretation code
        ]),
    }

    try:
        response = httpx.get(WEATHER_API_BASE, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        return {"error": f"Weather API returned HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except httpx.TimeoutException:
        return {"error": "Weather API request timed out."}
    except httpx.RequestError as e:
        return {"error": f"Could not reach Open-Meteo: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Marine conditions: waves, swell, ocean current
# ─────────────────────────────────────────────────────────────────────────────

def fetch_marine_conditions(lat: float, lon: float, days: int = DEFAULT_FORECAST_DAYS) -> dict:
    """
    Fetch hourly marine (wave/swell) forecast from Open-Meteo Marine API.

    Wave height is the single most important metric for small vessel safety.
    IMD/INCOIS advisories generally use:
        < 1.5 m  → relatively safe for most fishing vessels
        1.5–2.5 m → caution, depending on vessel size
        > 2.5 m  → dangerous for small craft

    Args:
        lat  (float): Latitude
        lon  (float): Longitude
        days (int):   Forecast horizon in days (1–7). Default: 3.

    Returns:
        Raw Open-Meteo Marine JSON as a Python dict, with "hourly" containing:
            wave_height, wave_direction, wave_period, wind_wave_height,
            swell_wave_height, swell_wave_period, swell_wave_direction,
            ocean_current_velocity

        Or {"error": "..."} if the request fails.

    Note:
        This API only has data for ocean/sea grid cells. For inland lat/lon
        points it returns an error — callers should handle this gracefully.
    """
    params = {
        "latitude":     lat,
        "longitude":    lon,
        "forecast_days": days,
        "timezone":     "auto",
        "hourly": ",".join([
            "wave_height",           # Significant wave height (m)
            "wave_direction",        # Mean wave direction (degrees from North)
            "wave_period",           # Mean wave period (seconds)
            "wind_wave_height",      # Wind-generated component of wave height (m)
            "swell_wave_height",     # Swell component of wave height (m)
            "swell_wave_period",     # Swell period (seconds)
            "swell_wave_direction",  # Swell propagation direction (degrees)
            "ocean_current_velocity", # Surface current speed (m/s)
        ]),
    }

    try:
        response = httpx.get(MARINE_API_BASE, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        return {"error": f"Marine API returned HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except httpx.TimeoutException:
        return {"error": "Marine API request timed out."}
    except httpx.RequestError as e:
        return {"error": f"Could not reach Open-Meteo Marine: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Time-window helper
# ─────────────────────────────────────────────────────────────────────────────

def extract_conditions_for_window(hourly_data: dict, start_hour: int = 0, window_hours: int = 24) -> dict:
    """
    Slice hourly time-series data to a specific time window.

    Open-Meteo returns data as parallel lists (e.g. hourly["time"][i] corresponds
    to hourly["wind_speed_10m"][i]). This function slices all lists to the same
    [start_hour, start_hour + window_hours) range.

    Args:
        hourly_data  (dict): The "hourly" dict from a fetch_* function.
        start_hour   (int):  Index of the first hour to include.
                             0  = current hour (now)
                             24 = same time tomorrow
                             48 = same time day after tomorrow
        window_hours (int):  How many consecutive hours to include.

    Returns:
        Dict with the same keys as hourly_data but with lists sliced to the window.

    Example:
        # Get tomorrow's 24-hour window
        tomorrow = extract_conditions_for_window(atmo_hourly, start_hour=24, window_hours=24)
    """
    end_hour = start_hour + window_hours
    sliced = {}

    for key, value in hourly_data.items():
        if isinstance(value, list):
            sliced[key] = value[start_hour:end_hour]
        else:
            # Non-list values (e.g. unit strings) pass through unchanged
            sliced[key] = value

    return sliced
