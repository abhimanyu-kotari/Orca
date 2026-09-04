"""
tools/map_tools.py — Folium interactive map generator for ORCA.

─────────────────────────────────────────────────────────────────────────────
STAKEHOLDER PERSONA BEHAVIORS (ISRO SIH 26176):
─────────────────────────────────────────────────────────────────────────────
  1. 🎣 Artisanal Fisherman (default):
     - Interactive anchor marker + safety radius circle.
     - Clickable PFZ hotspots color-coded by productivity.
     - Highlighted dashed navigation line connecting anchor to recommended PFZ.

  2. 🚨 Coastal Authority / Disaster Management:
     - High-Risk Cyclone & Storm Surge Geofence overlay (semi-transparent red Polygon).
     - Coastal Operations / Radar command center marker.
     - Maritime exclusion warnings and emergency recall status.

  3. 🔬 Marine Researcher / Oceanographer:
     - Earth Observation telemetry heat layer (simulated SST / Chlorophyll thermal gradient).
     - Scientific metadata popups (SST, Chlorophyll-a, Thermocline, Salinity).
"""

import folium
from folium import plugins
from folium.plugins import HeatMap

from tools.navigation_tools import calculate_optimal_route, IMBL_BOUNDARIES
from tools.eo_tools import generate_eo_grid, get_eo_legend_html


def _add_imbl_boundaries_to_map(fmap: folium.Map) -> None:
    """
    Render International Maritime Boundary Lines (IMBL) on the Folium map
    with high-visibility dashed red borders and legal restriction warnings.
    """
    imbl_group = folium.FeatureGroup(name="🛑 International Maritime Boundary Line (IMBL)", show=True)
    for name, coords in IMBL_BOUNDARIES.items():
        folium.PolyLine(
            locations=coords,
            color="#dc3545",
            weight=2.5,
            dash_array="8 4",
            tooltip=f"🛑 IMBL: {name} (International Maritime Boundary Line)",
            popup=folium.Popup(
                f"""
                <div style="font-family:Arial; font-size:12px; color:#721c24; min-width:220px;">
                    <b style="color:#dc3545;">🛑 INTERNATIONAL MARITIME BOUNDARY LINE</b><br/>
                    <b>Sector:</b> {name}<br/>
                    <b>Border Enforcement:</b> Strictly Policed<br/>
                    <b>Warning:</b> Navigating within 5 NM risks vessel impoundment and seizure by foreign maritime agencies.<br/>
                    <span style="color:#666;">Source: Bilateral Maritime Boundary Agreements</span>
                </div>
                """,
                max_width=260,
            ),
        ).add_to(imbl_group)
    imbl_group.add_to(fmap)


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
# Geospatial Simulation Helpers (for Authority & Researcher personas)
# ─────────────────────────────────────────────────────────────────────────────

def _generate_coastal_geofence_coords(lat: float, lon: float) -> list[list[float]]:
    """
    Generate polygon coordinates for an offshore disaster geofence
    representing simulated storm surge & gale boundary (~40 km along coast, ~30 km offshore).
    """
    is_west_coast = lon < 79.0
    offshore_offset = -0.32 if is_west_coast else 0.32

    return [
        [lat - 0.22, lon + (offshore_offset * 0.15)],
        [lat - 0.22, lon + offshore_offset],
        [lat + 0.22, lon + offshore_offset],
        [lat + 0.22, lon + (offshore_offset * 0.15)],
    ]


def _generate_sst_heat_points(lat: float, lon: float) -> list[list[float]]:
    """
    Generate simulated SST/Chlorophyll thermal plume points
    representing Oceansat-3/MODIS ocean observation telemetry.
    """
    is_west_coast = lon < 79.0
    sign = -1 if is_west_coast else 1

    points = []
    for d_lat in [-0.28, -0.18, -0.08, 0.0, 0.08, 0.18, 0.28]:
        for step in [1, 2, 3, 4, 5]:
            d_lon = sign * (0.07 * step)
            # High intensity along coastal upwelling axis, gently dispersing offshore
            intensity = round(max(0.20, 1.0 - (step * 0.16) - abs(d_lat) * 0.7), 2)
            points.append([lat + d_lat, lon + d_lon, intensity])
    return points


# ─────────────────────────────────────────────────────────────────────────────
# Helper: popup HTML builder
# ─────────────────────────────────────────────────────────────────────────────

def _pfz_popup_html(zone: dict, marker_color: str, persona: str = "fisherman") -> str:
    """
    Build HTML content for a PFZ zone popup tailored to the active persona.
    """
    sp_raw = zone.get("species", "")
    species_str = ", ".join(sp_raw) if isinstance(sp_raw, list) else str(sp_raw)
    dist_user   = zone.get("distance_to_user_km", "—")
    dist_shore  = zone.get("distance_from_shore_km", "—")
    quality     = zone.get("quality") or zone.get("status", "MEDIUM")
    depth_val   = zone.get("depth_m") if zone.get("depth_m") is not None else zone.get("depth", "—")
    zone_id     = zone.get("zone_id") or zone.get("id", "PFZ")
    advisory    = zone.get("advisory", "")
    season      = zone.get("best_season", "Year-round")

    badge_bg = {"HIGH": "#28a745", "MEDIUM": "#ffc107", "LOW": "#dc3545"}.get(quality, "#6c757d")

    # Extra section based on persona
    extra_rows = ""
    if persona == "researcher":
        extra_rows = f"""
            <tr style="border-top: 1px dashed #ccc;">
                <td style="padding:3px 0; color:#0d6efd;"><b>SST (Satellite)</b></td>
                <td style="padding:3px 0; color:#0d6efd;">28.4 °C (+0.4°C anom)</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#0d6efd;"><b>Chlorophyll-a</b></td>
                <td style="padding:3px 0; color:#0d6efd;">2.15 mg/m³ (Upwelling)</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#0d6efd;"><b>Salinity</b></td>
                <td style="padding:3px 0; color:#0d6efd;">34.9 PSU</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#0d6efd;"><b>Thermocline</b></td>
                <td style="padding:3px 0; color:#0d6efd;">42 m depth</td>
            </tr>
        """
    elif persona == "coastal_authority":
        extra_rows = f"""
            <tr style="border-top: 1px dashed #dc3545;">
                <td style="padding:3px 0; color:#dc3545;"><b>Geofence Status</b></td>
                <td style="padding:3px 0; color:#dc3545;">Active Sector Watch</td>
            </tr>
            <tr>
                <td style="padding:3px 0; color:#dc3545;"><b>Evacuation Route</b></td>
                <td style="padding:3px 0; color:#dc3545;">Bearing 075° to Port ({dist_shore} km)</td>
            </tr>
        """

    return f"""
    <div style="font-family: Arial, sans-serif; font-size: 12px; min-width: 230px; max-width: 290px;">
        <h4 style="margin:0 0 6px 0; color:{marker_color}; font-size: 14px;">
            &#x1F41F; {zone['name']}
        </h4>
        <span style="background:{badge_bg}; color:white; padding:2px 8px;
                     border-radius:12px; font-size:10px; font-weight:bold;">
            {quality} PRODUCTIVITY
        </span>
        <table style="margin-top:6px; width:100%; border-collapse:collapse; font-size:11px;">
            <tr>
                <td style="padding:2px 0; color:#555;"><b>Zone ID</b></td>
                <td style="padding:2px 0;">{zone_id}</td>
            </tr>
            <tr>
                <td style="padding:2px 0; color:#555;"><b>Target Species</b></td>
                <td style="padding:2px 0;">{species_str}</td>
            </tr>
            <tr>
                <td style="padding:2px 0; color:#555;"><b>Sea Depth</b></td>
                <td style="padding:2px 0;">{depth_val} m</td>
            </tr>
            <tr>
                <td style="padding:2px 0; color:#555;"><b>Distance from Port</b></td>
                <td style="padding:2px 0;"><b>{dist_user} km</b></td>
            </tr>
            {extra_rows}
        </table>
        <p style="margin:6px 0 0 0; font-style:italic; color:#444; font-size:11px;">
            {advisory}
        </p>
        <p style="margin:3px 0 0 0; font-size:9px; color:#888;">
            Source: INCOIS / ISRO Oceansat Advisory
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
    persona: str = "fisherman",
    show_sst_heatmap: bool = False,
    nav_route: dict | None = None,
) -> folium.Map:
    """
    Generate an interactive Folium map for the PFZ Agent response,
    adapted dynamically for the selected Stakeholder Persona and featuring
    fuel-optimal navigation routes.
    """
    # 1. Base Map
    fmap = folium.Map(
        location=[user_lat, user_lon],
        zoom_start=8,
        tiles="OpenStreetMap",
        prefer_canvas=True,
    )

    plugins.MiniMap(toggle_display=True, position="bottomright").add_to(fmap)

    # Render International Maritime Boundary Lines (IMBL Geofence)
    _add_imbl_boundaries_to_map(fmap)

    # 2. Persona: Marine Researcher Multi-Layer HeatMap (SST & Chlorophyll-a)
    if persona == "researcher" or show_sst_heatmap:
        eo_data = generate_eo_grid(user_lat, user_lon)
        sst_points = eo_data["sst_points"]
        chl_points = eo_data["chlorophyll_points"]

        # Layer 1: SST Thermal Gradient (Sentinel-3 SLSTR)
        sst_group = folium.FeatureGroup(name="🌡️ Sea Surface Temp (Sentinel-3 SLSTR)", show=True)
        HeatMap(
            sst_points,
            radius=24,
            blur=15,
            min_opacity=0.30,
            gradient={0.2: '#08306b', 0.4: '#2171b5', 0.6: '#67a9cf', 0.8: '#fc8d59', 1.0: '#d73027'},
        ).add_to(sst_group)
        sst_group.add_to(fmap)

        # Layer 2: Chlorophyll-a Productivity (Oceansat-3 OCM-3)
        chl_group = folium.FeatureGroup(name="🌿 Chlorophyll-a (Oceansat-3 OCM-3)", show=False)
        HeatMap(
            chl_points,
            radius=24,
            blur=15,
            min_opacity=0.30,
            gradient={0.2: '#081d58', 0.4: '#225ea8', 0.6: '#41b6c4', 0.8: '#7fcdbb', 1.0: '#006837'},
        ).add_to(chl_group)
        chl_group.add_to(fmap)

        # Layer Control for toggling between satellite layers
        folium.LayerControl(position="topright", collapsed=False).add_to(fmap)

        # Floating color ramp legend
        fmap.get_root().html.add_child(folium.Element(get_eo_legend_html()))

    # 3. Persona: Coastal Authority High-Risk Geofence Polygon
    if persona == "coastal_authority":
        geofence_coords = _generate_coastal_geofence_coords(user_lat, user_lon)
        folium.Polygon(
            locations=geofence_coords,
            color="#dc3545",
            weight=3,
            fill=True,
            fill_color="#dc3545",
            fill_opacity=0.22,
            dash_array="6 4",
            tooltip="🚨 GEOFENCE: Level-3 Maritime Exclusion & Storm Surge Hazard Zone",
            popup=folium.Popup(
                """
                <div style='font-family:Arial; font-size:12px; color:#721c24;'>
                    <b>🚨 HIGH-RISK CYCLONE / SURGE GEOFENCE</b><br/>
                    <b>Authority:</b> Coastal Disaster Management Cell<br/>
                    <b>Status:</b> Vessel Ingress Prohibited<br/>
                    <b>Protocol:</b> VHF Broadcast Ch 16 / SMS Alert Active
                </div>
                """,
                max_width=250,
            ),
        ).add_to(fmap)

        # Emergency Disaster Radar / Command Marker
        folium.Marker(
            location=[user_lat + 0.05, user_lon],
            popup="<b>🚨 Coastal Emergency Command & Radar</b>",
            tooltip="🚨 Emergency Command Center",
            icon=folium.Icon(color="darkred", icon="shield", prefix="fa"),
        ).add_to(fmap)

    # 4. Standard Coastal Safety Radius Circle
    circle_color = VERDICT_COLOR.get(safety_verdict or "SAFE", "#17a2b8")
    folium.Circle(
        location=[user_lat, user_lon],
        radius=_SAFETY_RADIUS_M,
        color=circle_color,
        weight=2,
        fill=True,
        fill_color=circle_color,
        fill_opacity=0.07,
        tooltip=f"15 km coastal safety radius (Status: {safety_verdict or 'Normal'})",
    ).add_to(fmap)

    # 5. User / Vessel / Port Marker
    port_icon = "anchor" if persona != "coastal_authority" else "building"
    port_color = "blue" if persona != "coastal_authority" else "darkblue"
    folium.Marker(
        location=[user_lat, user_lon],
        popup=folium.Popup(
            f'<div style="font-family:Arial;font-size:12px;">'
            f'<b>⚓ {user_location_name}</b><br/>'
            f'<span>{user_lat:.4f}°N, {user_lon:.4f}°E</span><br/>'
            f'<span>Role View: <b>{persona.replace("_", " ").title()}</b></span>'
            f'</div>',
            max_width=220,
        ),
        tooltip=f"⚓ {user_location_name} (Reference Port)",
        icon=folium.Icon(color=port_color, icon=port_icon, prefix="fa"),
    ).add_to(fmap)

    # 6. Navigation Route & Waypoints Calculation (if not precomputed)
    best_zone = pfz_zones[0] if pfz_zones else None
    if nav_route is None and best_zone is not None:
        geofences = (
            [_generate_coastal_geofence_coords(user_lat, user_lon)]
            if (persona == "coastal_authority" or safety_verdict in ("CAUTION", "DANGER"))
            else None
        )
        nav_route = calculate_optimal_route(
            start_coords=[user_lat, user_lon],
            end_coords=[best_zone["lat"], best_zone["lon"]],
            hazard_geofences=geofences,
            start_label=user_location_name,
            end_label=best_zone.get("name", "Top PFZ Hotspot"),
        )

    # 7. Render Navigation Track to Top Recommended Zone
    if nav_route and nav_route.get("success"):
        route_pts = nav_route.get("route_points", [])
        if len(route_pts) < 2 and best_zone and "lat" in best_zone and "lon" in best_zone:
            route_pts = [[user_lat, user_lon], [best_zone["lat"], best_zone["lon"]]]
        heading_str = nav_route.get("direct_heading_str", "")
        dist_nm = nav_route.get("total_distance_nm", 0.0)
        dist_km = nav_route.get("total_distance_km", 0.0)
        fuel_econ = nav_route.get("fuel_economy", {})
        fuel_saved = fuel_econ.get("fuel_saved_liters", 0.0)
        cost_saved = fuel_econ.get("cost_saved_inr", 0)
        transit_time = fuel_econ.get("transit_time_str", "")
        geofence_status = nav_route.get("geofence_status", "")
        has_detour = nav_route.get("hazard_avoidance_active", False)

        # Check IMBL Warning Status
        imbl_warn = nav_route.get("imbl_warning_active", False)
        imbl_dist = nav_route.get("imbl_min_distance_nm", 0.0)
        imbl_name = nav_route.get("imbl_closest_boundary", "IMBL")

        # High-visibility polyline along optimal route
        if imbl_warn:
            line_color = "#dc3545"  # High-visibility alert red
            dash_style = "6 4"
            route_tooltip = f"🛑 IMBL PROXIMITY WARNING: {imbl_dist:.1f} NM from {imbl_name} border | Impoundment Risk!"
        elif has_detour:
            line_color = "#d9534f"
            dash_style = "8 5"
            route_tooltip = f"🧭 Detour Track | Heading: {heading_str} | {dist_nm} NM ({dist_km} km)"
        else:
            line_color = "#0056b3"
            dash_style = None
            route_tooltip = f"🧭 Optimal Heading: {heading_str} | Safe Transit Corridor | {dist_nm} NM ({dist_km} km)"

        imbl_banner_html = f"""
            <div style="margin-top:6px; background:#f8d7da; border-left:3px solid #dc3545; padding:5px 7px; border-radius:3px; color:#721c24; font-size:11px;">
                <b>🛑 IMBL PROXIMITY WARNING:</b><br/>
                Track passes within <b>{imbl_dist:.1f} NM</b> of <b>{imbl_name}</b> boundary.<br/>
                <b>Action:</b> Maintain 5 NM clearance to prevent impoundment!
            </div>
        """ if imbl_warn else ""

        if len(route_pts) >= 2:
            folium.PolyLine(
                locations=route_pts,
                color=line_color,
                weight=4,
                opacity=0.90,
                dash_array=dash_style,
                tooltip=route_tooltip,
                popup=folium.Popup(
                    f"""
                    <div style="font-family:Arial;font-size:12px;min-width:220px;">
                        <b style="color:{line_color};">🧭 Fuel-Optimal Navigation Track</b><br/>
                        <b>Heading:</b> {heading_str}<br/>
                        <b>Track Distance:</b> {dist_nm} NM ({dist_km} km)<br/>
                        <b>Estimated Transit:</b> {transit_time} (@ 9 knots)<br/>
                        <b>Diesel Savings:</b> <span style="color:#28a745;"><b>{fuel_saved} L (~₹{cost_saved:,.0f})</b></span><br/>
                        <b>Safety Status:</b> {geofence_status}
                        {imbl_banner_html}
                    </div>
                    """,
                    max_width=270,
                ),
            ).add_to(fmap)

        # If hazard detour was synthesized, render intermediate waypoint marker
        if has_detour:
            for wp in nav_route.get("waypoints", []):
                if wp.get("wp_id") == 2:
                    folium.Marker(
                        location=[wp["lat"], wp["lon"]],
                        popup=folium.Popup(
                            f"""
                            <div style="font-family:Arial;font-size:12px;min-width:200px;">
                                <b style="color:#d35400;">⚠️ Seaward Hazard Clearance Waypoint</b><br/>
                                <b>Coordinates:</b> {wp['lat']:.4f}°N, {wp['lon']:.4f}°E<br/>
                                <b>Leg Distance:</b> {wp.get('leg_distance_nm', 0):.1f} NM<br/>
                                <b>Steer Bearing:</b> {wp.get('leg_bearing', 'N/A')}<br/>
                                <span style="color:#555;">Detour skirts active storm surge/cyclone geofence.</span>
                            </div>
                            """,
                            max_width=240,
                        ),
                        tooltip="⚠️ Waypoint 2: Hazard Detour Clearance Point",
                        icon=folium.Icon(color="orange", icon="compass", prefix="fa"),
                    ).add_to(fmap)

    # 8. PFZ Hotspot Markers & Secondary Lines
    best_zone_id = (best_zone.get("zone_id") or best_zone.get("id")) if best_zone else None
    best_zone_name = best_zone.get("name") if best_zone else None

    for i, zone in enumerate(pfz_zones, start=1):
        quality = zone.get("quality") or zone.get("status", "MEDIUM")
        marker_color = QUALITY_COLOR.get(quality, "blue")
        zone_lat = zone["lat"]
        zone_lon = zone["lon"]
        dist_km = zone.get("distance_to_user_km", "?")
        zid = zone.get("zone_id") or zone.get("id")
        is_top = (zid == best_zone_id) or (zone.get("name") == best_zone_name)

        # Secondary zones get faint connector lines
        if not is_top:
            folium.PolyLine(
                locations=[[user_lat, user_lon], [zone_lat, zone_lon]],
                color=marker_color,
                weight=1.5,
                opacity=0.35,
                dash_array="5 5",
                tooltip=f"{dist_km} km to {zone['name']}",
            ).add_to(fmap)

        popup_html = _pfz_popup_html(zone, marker_color, persona=persona)
        folium.Marker(
            location=[zone_lat, zone_lon],
            popup=folium.Popup(popup_html, max_width=310),
            tooltip=f"#{i} 🐟 {zone['name']} — {quality} ({dist_km} km)",
            icon=folium.Icon(color=marker_color, icon="star", prefix="fa"),
        ).add_to(fmap)

    return fmap



def create_weather_map(
    user_lat: float,
    user_lon: float,
    user_location_name: str = "Queried Location",
    safety_verdict: str = "SAFE",
    persona: str = "fisherman",
    show_sst_heatmap: bool = False,
) -> folium.Map:
    """
    Generate a weather-context map with persona-aware geofencing & telemetry overlays.
    """
    fmap = folium.Map(
        location=[user_lat, user_lon],
        zoom_start=9,
        tiles="OpenStreetMap",
        prefer_canvas=True,
    )

    circle_color = VERDICT_COLOR.get(safety_verdict, "#17a2b8")

    # Render International Maritime Boundary Lines (IMBL Geofence)
    _add_imbl_boundaries_to_map(fmap)

    # Persona: Researcher Multi-Layer HeatMap (SST & Chlorophyll-a)
    if persona == "researcher" or show_sst_heatmap:
        eo_data = generate_eo_grid(user_lat, user_lon)
        sst_points = eo_data["sst_points"]
        chl_points = eo_data["chlorophyll_points"]

        sst_group = folium.FeatureGroup(name="🌡️ Sea Surface Temp (Sentinel-3 SLSTR)", show=True)
        HeatMap(
            sst_points,
            radius=24,
            blur=15,
            min_opacity=0.30,
            gradient={0.2: '#08306b', 0.4: '#2171b5', 0.6: '#67a9cf', 0.8: '#fc8d59', 1.0: '#d73027'},
        ).add_to(sst_group)
        sst_group.add_to(fmap)

        chl_group = folium.FeatureGroup(name="🌿 Chlorophyll-a (Oceansat-3 OCM-3)", show=False)
        HeatMap(
            chl_points,
            radius=24,
            blur=15,
            min_opacity=0.30,
            gradient={0.2: '#081d58', 0.4: '#225ea8', 0.6: '#41b6c4', 0.8: '#7fcdbb', 1.0: '#006837'},
        ).add_to(chl_group)
        chl_group.add_to(fmap)

        folium.LayerControl(position="topright", collapsed=False).add_to(fmap)
        fmap.get_root().html.add_child(folium.Element(get_eo_legend_html()))

    # Persona: Coastal Authority Geofence Polygon
    if persona == "coastal_authority" or safety_verdict == "DANGER":
        geofence_coords = _generate_coastal_geofence_coords(user_lat, user_lon)
        folium.Polygon(
            locations=geofence_coords,
            color="#dc3545",
            weight=3,
            fill=True,
            fill_color="#dc3545",
            fill_opacity=0.25,
            dash_array="6 4",
            tooltip="🚨 HIGH-RISK STORM SURGE & CYCLONE GEOFENCE: Level-3 Exclusion Zone",
        ).add_to(fmap)

    # Safety Zone Perimeter
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

    # Location Marker
    folium.Marker(
        location=[user_lat, user_lon],
        popup=folium.Popup(
            f'<b>⚓ {user_location_name}</b><br/>'
            f'Weather status: <b style="color:{circle_color}">{safety_verdict}</b>',
            max_width=200,
        ),
        tooltip=f"⚓ {user_location_name}",
        icon=folium.Icon(color="blue", icon="anchor", prefix="fa"),
    ).add_to(fmap)

    return fmap
