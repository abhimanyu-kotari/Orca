"""
tools/eo_tools.py — Earth Observation (EO) Satellite Telemetry Layer for Marine Researchers.

DESIGN PRINCIPLE:
    Pure computational module providing high-resolution simulated satellite telemetry
    modeled after ISRO Oceansat-3 (OCM-3) and Sentinel-3 (SLSTR).
    Simulates realistic oceanographic spatial fields:
      - Sea Surface Temperature (SST): 26.5°C to 30.5°C
      - Chlorophyll-a Concentration: 0.1 to 3.8 mg/m³
      - Coastal upwelling fronts, thermocline shoaling, and thermal anomalies.

ISRO SIH 26176 RELEVANCE:
    Empowers marine scientists and fisheries researchers to analyze satellite
    ocean color, baroclinic upwelling dynamics, and pelagic habitat suitability
    along the Indian coastline.

FUNCTIONS EXPORTED:
    generate_eo_grid(center_lat, center_lon, radius_km, step_km) -> dict
    get_eo_legend_html() -> str
"""

import math
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Physical Constants & Oceanographic Baselines
# ─────────────────────────────────────────────────────────────────────────────

EARTH_RADIUS_KM: float = 6371.0
CLIMATOLOGY_MEAN_SST_C: float = 28.2   # Mean baseline tropical Indian Ocean SST
UPWELLING_TEMP_DEPRESSION_C: float = 1.8


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Fast haversine distance in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lam / 2.0) ** 2)
    return EARTH_RADIUS_KM * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def generate_eo_grid(
    center_lat: float,
    center_lon: float,
    radius_km: float = 120.0,
    step_km: float = 15.0,
) -> dict:
    """
    Generate synthetic Earth Observation telemetry points across coastal and offshore waters.

    Args:
        center_lat: Reference port or centroid latitude
        center_lon: Reference port or centroid longitude
        radius_km: Radius of oceanographic surveillance circle (km)
        step_km: Spatial grid resolution (km)

    Returns:
        dict containing:
            - sst_points: [[lat, lon, normalized_sst], ...] for Folium HeatMap
            - chlorophyll_points: [[lat, lon, normalized_chl], ...] for Folium HeatMap
            - raw_telemetry: list of detailed point dicts
            - mean_sst_c: float
            - min_sst_c: float
            - max_sst_c: float
            - sst_anomaly_c: float
            - mean_chlorophyll_mg_m3: float
            - max_chlorophyll_mg_m3: float
            - upwelling_front_coords: [lat, lon]
            - upwelling_intensity: str
            - thermocline_depth_m: int
            - sensor_metadata: dict
    """
    # 1 degree latitude ~ 111 km
    lat_step = step_km / 111.0
    lon_step = step_km / (111.0 * max(0.2, math.cos(math.radians(center_lat))))

    lat_range = int(math.ceil(radius_km / step_km))
    lon_range = int(math.ceil(radius_km / step_km))

    is_west_coast = center_lon < 79.0  # Arabian Sea vs Bay of Bengal
    offshore_sign = -1.0 if is_west_coast else 1.0

    sst_points = []
    chl_points = []
    raw_points = []

    min_sst = 99.0
    max_sst = -99.0
    sum_sst = 0.0

    max_chl = 0.0
    sum_chl = 0.0

    front_coord = [center_lat, center_lon]
    max_gradient = -1.0

    for i in range(-lat_range, lat_range + 1):
        for j in range(-lon_range, lon_range + 1):
            pt_lat = round(center_lat + (i * lat_step), 4)
            pt_lon = round(center_lon + (j * lon_step), 4)

            dist_km = _haversine_km(center_lat, center_lon, pt_lat, pt_lon)
            if dist_km > radius_km:
                continue

            # Seaward distance factor: positive when moving offshore
            # On west coast, lon < center_lon is offshore. On east coast, lon > center_lon is offshore.
            d_lon = pt_lon - center_lon
            offshore_km = (d_lon * offshore_sign) * 111.0 * math.cos(math.radians(pt_lat))

            # Upwelling zone core is located on the continental shelf edge (~18-35 km offshore)
            upwelling_dist_to_core = abs(offshore_km - 25.0)
            upwelling_factor = math.exp(-(upwelling_dist_to_core ** 2) / (2.0 * (18.0 ** 2)))

            # SST Model:
            # Core drops by up to 2.2°C due to upwelling; ambient offshore water warms to 30.2°C
            # Coastal nearshore waters ~ 28.5°C
            ambient_sst = 28.6 + min(1.4, max(-0.5, (offshore_km - 25.0) * 0.018))
            sst = round(ambient_sst - (UPWELLING_TEMP_DEPRESSION_C * upwelling_factor), 2)
            sst = max(26.5, min(30.5, sst))

            # Chlorophyll-a Model:
            # Phytoplankton blooms in upwelling core (2.2 - 3.8 mg/m³), decaying offshore to ~0.15 mg/m³
            estuary_factor = max(0.0, 1.0 - (dist_km / 35.0)) * 0.8
            chl = round(0.18 + (2.6 * upwelling_factor) + estuary_factor, 2)
            chl = max(0.10, min(3.80, chl))

            # Upwelling front gradient (largest horizontal temperature contrast)
            gradient = upwelling_factor * (30.0 - sst)
            if gradient > max_gradient:
                max_gradient = gradient
                front_coord = [pt_lat, pt_lon]

            min_sst = min(min_sst, sst)
            max_sst = max(max_sst, sst)
            sum_sst += sst

            max_chl = max(max_chl, chl)
            sum_chl += chl

            # Normalized weights for Folium HeatMap (0.0 to 1.0)
            sst_norm = round((sst - 26.5) / (30.5 - 26.5), 3)
            chl_norm = round((chl - 0.10) / (3.80 - 0.10), 3)

            sst_points.append([pt_lat, pt_lon, sst_norm])
            chl_points.append([pt_lat, pt_lon, chl_norm])

            raw_points.append({
                "lat": pt_lat,
                "lon": pt_lon,
                "distance_km": round(dist_km, 1),
                "offshore_km": round(offshore_km, 1),
                "sst_c": sst,
                "chlorophyll_mg_m3": chl,
            })

    total_pts = max(1, len(raw_points))
    mean_sst = round(sum_sst / total_pts, 2)
    mean_chl = round(sum_chl / total_pts, 2)
    sst_anomaly = round(mean_sst - CLIMATOLOGY_MEAN_SST_C, 2)

    # Characterize upwelling intensity
    temp_drop = max_sst - min_sst
    if temp_drop >= 2.0:
        upwelling_intensity = "Strong Coastal Upwelling (Active Baroclinic Front)"
        thermocline_depth = 34
    elif temp_drop >= 1.2:
        upwelling_intensity = "Moderate Upwelling (Developing Thermal Plume)"
        thermocline_depth = 42
    else:
        upwelling_intensity = "Weak / Diffuse Ocean Mixing"
        thermocline_depth = 55

    return {
        "success": True,
        "center_coords": [center_lat, center_lon],
        "radius_km": radius_km,
        "grid_points_count": total_pts,
        "sst_points": sst_points,
        "chlorophyll_points": chl_points,
        "mean_sst_c": mean_sst,
        "min_sst_c": round(min_sst, 2),
        "max_sst_c": round(max_sst, 2),
        "sst_anomaly_c": sst_anomaly,
        "mean_chlorophyll_mg_m3": mean_chl,
        "max_chlorophyll_mg_m3": round(max_chl, 2),
        "upwelling_front_coords": front_coord,
        "upwelling_intensity": upwelling_intensity,
        "thermocline_depth_m": thermocline_depth,
        "sensor_metadata": {
            "sst_sensor": "Copernicus Sentinel-3 SLSTR (Sea and Land Surface Temperature Radiometer)",
            "sst_resolution": "1 km spatial resolution · Daily revisit",
            "ocean_color_sensor": "ISRO Oceansat-3 OCM-3 (Ocean Colour Monitor-3)",
            "chl_resolution": "300 m spatial resolution · 13 spectral bands",
            "climatology_baseline": f"{CLIMATOLOGY_MEAN_SST_C}°C seasonal average",
        },
    }


def get_eo_legend_html() -> str:
    """
    Generate an HTML snippet with dual color ramp legends for SST and Chlorophyll-a
    suitable for injection into a Folium map.
    """
    return """
    <style>
    .eo-legend-box {
        position: fixed;
        bottom: 15px;
        left: 12px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.90);
        padding: 6px 10px;
        border-radius: 6px;
        border: 1px solid #CBD5E1;
        box-shadow: 0 2px 6px rgba(0,0,0,0.14);
        font-family: Arial, sans-serif;
        font-size: 10px;
        line-height: 1.3;
        max-width: 205px;
    }
    @media (max-width: 600px) {
        .eo-legend-box {
            max-width: 155px !important;
            padding: 4px 6px !important;
            font-size: 8.5px !important;
            bottom: 6px !important;
            left: 6px !important;
        }
        .eo-legend-title { font-size: 9px !important; }
        .eo-legend-box span { font-size: 7.5px !important; }
    }
    </style>
    <div class="eo-legend-box">
        <b class="eo-legend-title" style="font-size:12px; color:#0b5ed7;">🛰️ Earth Observation Color Scales</b><br/>

        <!-- SST Scale -->
        <div style="margin-top:6px;">
            <b>🌡️ Sea Surface Temp (°C)</b>
            <div style="
                height: 10px;
                border-radius: 4px;
                background: linear-gradient(to right, #08306b, #2171b5, #67a9cf, #fc8d59, #d73027);
                margin: 3px 0;
            "></div>
            <div style="display:flex; justify-content:space-between; font-size:10px; color:#555;">
                <span>26.5°C (Upwelling)</span>
                <span>28.5°C</span>
                <span>30.5°C (Warm)</span>
            </div>
        </div>

        <!-- Chlorophyll-a Scale -->
        <div style="margin-top:8px;">
            <b>🌿 Chlorophyll-a (mg/m³)</b>
            <div style="
                height: 10px;
                border-radius: 4px;
                background: linear-gradient(to right, #081d58, #225ea8, #41b6c4, #7fcdbb, #006837);
                margin: 3px 0;
            "></div>
            <div style="display:flex; justify-content:space-between; font-size:10px; color:#555;">
                <span>0.1 (Oligotrophic)</span>
                <span>1.8</span>
                <span>3.8 (Bloom)</span>
            </div>
        </div>

        <div style="margin-top:6px; font-size:9px; color:#777; border-top:1px dashed #ddd; padding-top:4px;">
            Sensors: ISRO Oceansat-3 (OCM-3) & Sentinel-3 SLSTR
        </div>
    </div>
    """
