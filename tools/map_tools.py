"""
tools/map_tools.py — Folium interactive map generator for ORCA.

DESIGN PRINCIPLE:
    Pure rendering module — no AI calls, no data fetching.
    Takes pre-computed data (user location + PFZ zones) and returns a
    folium.Map object ready to be rendered by streamlit-folium.

Functions:
    create_pfz_map(user_lat, user_lon, pfz_zones, ...)  → folium.Map
    create_weather_map(user_lat, user_lon, verdict, ...) → folium.Map
"""

import folium
from folium import plugins


# ─────────────────────────────────────────────────────────────────────────────
# Styling constants
# ─────────────────────────────────────────────────────────────────────────────

# PFZ zone marker colours — green=productive, orange=moderate, red=low
QUALITY_COLOR: dict[str, str] = {
    "HIGH":   "green",
    "MEDIUM": "orange",
    "LOW":    "red",
}

# Safety verdict → circle border colour for weather hazard overlay
VERDICT_COLOR: dict[str, str] = {
    "SAFE":    "#28a745",   # Bootstrap green
    "CAUTION": "#ffc107",   # Bootstrap amber
    "DANGER":  "#dc3545",   # Bootstrap red
}

# Nominal safety radius displayed as a circle around the user's position
_SAFETY_RADIUS_M: int = 15_000   # 15 km in metres


# ─────────────────────────────────────────────────────────────────────────────
# Helper: popup HTML builder
# ─────────────────────────────────────────────────────────────────────────────

def _pfz_popup_html(zone: dict, marker_color: str) -> str:
    """
    Build the HTML content for a PFZ zone popup.

    Uses an inline-styled table so it renders correctly inside Folium's
    IFrame popup regardless of external CSS.
    """
    species_str = ", ".join(zone.get("species", []))
    dist_user   = zone.get("distance_to_user_km", "—")
    dist_shore  = zone.get("distance_from_shore_km", "—")
    quality     = zone.get("quality", "MEDIUM")
    advisory    = zone.get("advisory", "")
    season      = zone.get("best_season", "Year-round")

    # Colour badge for quality
    badge_bg = {"HIGH": "#28a745", "MEDIUM": "#ffc107", "LOW": "#dc3545"}.get(quality, "#6c757d")

    return f"""
    <div style="font-family: Arial, sans-serif; font-size: 13px; min-width: 220px; max-width: 280px;">
        <h4 style="margin:0 0 6px 0; color:{marker_color};">
            &#x1F41F; {zone['name']}
        </h4>
        <span style="background:{badge_bg}; color:white; padding:2px 8px;
                     border-radius:12px; font-size:11px; font-weight:bold;">
            {quality} PRODUCTIVITY
        </span>
        <table style="margin-top:8px; width:100%; border-collapse:collapse;">
            <tr>
                <td style="padding:3px 0; color:#555;"><b>Zone ID</b></td>
                <td style="padding:3px 0;">{zone['zone_id']}</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#555;"><b>Region</b></td>
                <td style="padding:3px 0;">{zone['region']}</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#555;"><b>Target species</b></td>
                <td style="padding:3px 0;">{species_str}</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#555;"><b>Sea depth</b></td>
                <td style="padding:3px 0;">{zone['depth_m']} m</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#555;"><b>From shore</b></td>
                <td style="padding:3px 0;">{dist_shore} km</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#555;"><b>From your location</b></td>
                <td style="padding:3px 0;"><b>{dist_user} km</b></td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#555;"><b>Best season</b></td>
                <td style="padding:3px 0;">{season}</td>
            </tr>
        </table>
        <p style="margin:8px 0 0 0; font-style:italic; color:#444; font-size:12px;">
            {advisory}
        </p>
        <p style="margin:4px 0 0 0; font-size:10px; color:#999;">
            Source: INCOIS PFZ Advisory (mock data)
        </p>
    </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
# Main map functions
# ─────────────────────────────────────────────────────────────────────────────

def create_pfz_map(
    user_lat: float,
    user_lon: float,
    pfz_zones: list[dict],
    user_location_name: str = "Your Location",
    safety_verdict: str | None = None,
) -> folium.Map:
    """
    Generate an interactive Folium map for the PFZ Agent response.

    Layers rendered:
      1. CartoDB Positron base tile (clean, minimal ocean background)
      2. Blue anchor marker at the user's resolved position
      3. Safety-radius circle (15 km) coloured by weather verdict
      4. PFZ hotspot markers, colour-coded by zone quality:
             GREEN  = HIGH productivity
             ORANGE = MEDIUM productivity
             RED    = LOW productivity
      5. Dashed connector lines from user to each PFZ zone
      6. Clickable popups on each PFZ marker with full zone metadata
      7. Minimap plugin (bottom-right corner)

    Args:
        user_lat           : Latitude of the user's coastal location.
        user_lon           : Longitude of the user's coastal location.
        pfz_zones          : List of zone dicts from pfz_tools.find_nearest_zones().
                             Each must have 'lat', 'lon', 'quality', 'name', etc.
        user_location_name : Human-readable label for the anchor marker popup.
        safety_verdict     : "SAFE" | "CAUTION" | "DANGER" | None.
                             Controls the safety circle border colour.

    Returns:
        folium.Map object ready for st_folium() in Streamlit.
    """
    # —— Base map —————————————————————————————————————————————————
    # Zoom level 8 shows ~300km radius — appropriate for "find nearby PFZ"
    fmap = folium.Map(
        location=[user_lat, user_lon],
        zoom_start=8,
        tiles="OpenStreetMap",  # Free, no API key required (CartoDB requires a key)
        prefer_canvas=True,     # Canvas renderer is faster for many markers
    )

    # —— Minimap plugin (context map in corner) ———————————————————
    plugins.MiniMap(toggle_display=True, position="bottomright").add_to(fmap)

    # —— Safety radius circle ———————————————————————————————
    circle_color = VERDICT_COLOR.get(safety_verdict or "SAFE", "#17a2b8")
    folium.Circle(
        location=[user_lat, user_lon],
        radius=_SAFETY_RADIUS_M,
        color=circle_color,
        weight=2,
        fill=True,
        fill_color=circle_color,
        fill_opacity=0.06,
        tooltip=f"15 km coastal safety radius ({safety_verdict or 'check weather'})",
    ).add_to(fmap)

    # —— User / boat anchor marker ———————————————————————————
    folium.Marker(
        location=[user_lat, user_lon],
        popup=folium.Popup(
            f'<div style="font-family:Arial;font-size:13px;">'  
            f'<b>&#x2693; {user_location_name}</b><br/>'
            f'<span style="color:#666;">{user_lat:.4f}°N, {user_lon:.4f}°E</span>'
            f'</div>',
            max_width=220,
        ),
        tooltip=f"\u2693 {user_location_name} (your location)",
        icon=folium.Icon(color="blue", icon="anchor", prefix="fa"),
    ).add_to(fmap)

    # —— PFZ zone markers ————————————————————————————————
    for i, zone in enumerate(pfz_zones, start=1):
        quality      = zone.get("quality", "MEDIUM")
        marker_color = QUALITY_COLOR.get(quality, "blue")
        zone_lat     = zone["lat"]
        zone_lon     = zone["lon"]
        dist_km      = zone.get("distance_to_user_km", "?")

        # Dashed connector line: user → zone
        folium.PolyLine(
            locations=[[user_lat, user_lon], [zone_lat, zone_lon]],
            color=marker_color,
            weight=1.5,
            opacity=0.45,
            dash_array="6 4",
            tooltip=f"{dist_km} km to {zone['name']}",
        ).add_to(fmap)

        # Zone marker with rich popup
        popup_html = _pfz_popup_html(zone, marker_color)
        folium.Marker(
            location=[zone_lat, zone_lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=(
                f"#{i} \u1f41f {zone['name']} — "
                f"{quality} ({dist_km} km)"
            ),
            icon=folium.Icon(
                color=marker_color,
                icon="star",
                prefix="fa",
            ),
        ).add_to(fmap)

    return fmap


def create_weather_map(
    user_lat: float,
    user_lon: float,
    user_location_name: str = "Queried Location",
    safety_verdict: str = "SAFE",
) -> folium.Map:
    """
    Generate a minimal weather-context map (no PFZ zones).

    Shows the queried location with a safety-verdict-coloured circle.
    Used by the Weather Agent response view to give spatial context.

    Args:
        user_lat           : Latitude.
        user_lon           : Longitude.
        user_location_name : Label for the anchor popup.
        safety_verdict     : "SAFE" | "CAUTION" | "DANGER".

    Returns:
        folium.Map
    """
    fmap = folium.Map(
        location=[user_lat, user_lon],
        zoom_start=9,
        tiles="OpenStreetMap",  # Free, no API key required (CartoDB requires a key)
        prefer_canvas=True,
    )

    circle_color = VERDICT_COLOR.get(safety_verdict, "#17a2b8")

    folium.Circle(
        location=[user_lat, user_lon],
        radius=_SAFETY_RADIUS_M,
        color=circle_color,
        weight=2,
        fill=True,
        fill_color=circle_color,
        fill_opacity=0.10,
        tooltip=f"Safety zone — verdict: {safety_verdict}",
    ).add_to(fmap)

    folium.Marker(
        location=[user_lat, user_lon],
        popup=folium.Popup(
            f'<b>\u2693 {user_location_name}</b><br/>'
            f'Weather verdict: <b style="color:{circle_color}">{safety_verdict}</b>',
            max_width=200,
        ),
        tooltip=f"\u2693 {user_location_name}",
        icon=folium.Icon(color="blue", icon="anchor", prefix="fa"),
    ).add_to(fmap)

    return fmap
