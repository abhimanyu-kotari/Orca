"""
tools/navigation_tools.py — Fuel-Optimal Navigation & Waypoint Routing Module.

DESIGN PRINCIPLE:
    Pure computational module (no external APIs, no Streamlit dependencies).
    Calculates great-circle distance in Nautical Miles (NM), initial compass
    bearings (forward azimuth), marine diesel fuel economy, and dynamic
    hazard avoidance waypoints for Indian artisanal fishing operations.

ISRO SIH 26176 RELEVANCE:
    Empowers artisanal fishermen to eliminate blind cruising (which consumes
    ~30-35% more diesel while searching for fish), reducing both fuel expenditure
    and operational carbon footprint while steering clear of coastal hazard geofences.

FUNCTIONS EXPORTED:
    haversine_distance_km(lat1, lon1, lat2, lon2) -> float
    haversine_distance_nm(lat1, lon1, lat2, lon2) -> tuple[float, float]
    calculate_compass_bearing(lat1, lon1, lat2, lon2) -> tuple[float, str]
    estimate_fuel_consumption(distance_nm, ...) -> dict
    check_geofence_intersection(start_coords, end_coords, geofences) -> tuple[bool, Optional[list[float]]]
    calculate_optimal_route(start_coords, end_coords, hazard_geofences=None, ...) -> dict
"""

import math
from typing import Optional, Union


# ─────────────────────────────────────────────────────────────────────────────
# Nautical & Marine Constants
# ─────────────────────────────────────────────────────────────────────────────

KM_PER_NAUTICAL_MILE: float = 1.852       # Exact international nautical mile in km
DEFAULT_VESSEL_SPEED_KNOTS: float = 9.0   # Standard artisanal mechanized craft cruising speed
DEFAULT_BURN_RATE_L_NM: float = 1.8       # Marine diesel burn rate: 1.8 Liters per Nautical Mile
UNOPTIMIZED_SEARCH_FACTOR: float = 1.30   # +30% wandering/search penalty without PFZ coordinates
DEFAULT_DIESEL_PRICE_INR: float = 94.0    # Baseline coastal retail diesel price per Liter

COMPASS_POINTS_16: list[str] = [
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
]

# ─────────────────────────────────────────────────────────────────────────────
# International Maritime Boundary Lines (IMBL) — ISRO SIH 26176 Geofences
# ─────────────────────────────────────────────────────────────────────────────
# Coordinates of bilateral international maritime boundary lines for Indian waters:
#   1. India - Sri Lanka (1974 & 1976 bilateral agreements):
#      Runs from Palk Strait across Palk Bay, Adam's Bridge, and into the Gulf of Mannar.
#   2. India - Pakistan (Sir Creek & offshore maritime boundary):
#      Extends from the mouth of Sir Creek southwest into the Arabian Sea.

IMBL_BOUNDARIES: dict[str, list[list[float]]] = {
    "India-Sri Lanka": [
        [10.0833, 80.0500],
        [9.9833, 79.9167],
        [9.7000, 79.5333],
        [9.3667, 79.3833],
        [9.1000, 79.4333],
        [8.8667, 79.1667],
        [8.4000, 78.9167],
        [7.9833, 78.7500],
    ],
    "India-Pakistan": [
        [23.6333, 68.1000],
        [23.5000, 67.8000],
        [23.2500, 67.4000],
        [22.8000, 66.8000],
        [22.3000, 66.0000],
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Distance & Great-Circle Calculations
# ─────────────────────────────────────────────────────────────────────────────

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers using the Haversine formula."""
    R = 6371.0  # Earth's mean radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2
         + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def haversine_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """
    Compute distance in both kilometers and Nautical Miles.
    Returns: (distance_km, distance_nm)
    """
    km = haversine_distance_km(lat1, lon1, lat2, lon2)
    nm = round(km / KM_PER_NAUTICAL_MILE, 2)
    return km, nm


# ─────────────────────────────────────────────────────────────────────────────
# Bearing & Heading Calculations
# ─────────────────────────────────────────────────────────────────────────────

def calculate_compass_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, str]:
    """
    Calculate the initial forward azimuth (compass bearing) from Point 1 to Point 2.

    Returns:
        (bearing_degrees, formatted_heading_str)
        e.g. (245.2, "245° WSW")
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = (math.cos(phi1) * math.sin(phi2)
         - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda))

    initial_bearing = math.atan2(y, x)
    # Normalize from [-pi, pi] to [0, 360)
    compass_bearing = (math.degrees(initial_bearing) + 360.0) % 360.0

    # Map to 16-point cardinal compass rose
    # Each sector spans 22.5 degrees (360 / 16)
    idx = int(round(compass_bearing / 22.5)) % 16
    cardinal = COMPASS_POINTS_16[idx]

    heading_str = f"{round(compass_bearing)}° {cardinal}"
    return round(compass_bearing, 1), heading_str


# ─────────────────────────────────────────────────────────────────────────────
# Fuel Economy & Emission Calculations
# ─────────────────────────────────────────────────────────────────────────────

def estimate_fuel_consumption(
    distance_nm: float,
    speed_knots: float = DEFAULT_VESSEL_SPEED_KNOTS,
    burn_rate_l_nm: float = DEFAULT_BURN_RATE_L_NM,
    diesel_price_inr: float = DEFAULT_DIESEL_PRICE_INR,
    search_factor: float = UNOPTIMIZED_SEARCH_FACTOR,
) -> dict:
    """
    Estimate fuel consumption for optimal waypoint transit versus blind cruising.

    Returns dict containing:
        - optimal_fuel_liters: fuel required for direct optimal track
        - unoptimized_fuel_liters: fuel consumed during unguided search cruising
        - fuel_saved_liters: net fuel savings
        - cost_saved_inr: monetary savings in Indian Rupees (₹)
        - transit_time_hours: float
        - transit_time_str: human-readable duration e.g. "1h 45m"
    """
    optimal_liters = round(distance_nm * burn_rate_l_nm, 1)

    unoptimized_distance_nm = round(distance_nm * search_factor, 1)
    unoptimized_liters = round(unoptimized_distance_nm * burn_rate_l_nm, 1)

    saved_liters = round(max(0.0, unoptimized_liters - optimal_liters), 1)
    cost_saved = round(saved_liters * diesel_price_inr, 0)

    hours_float = distance_nm / max(0.1, speed_knots)
    total_mins = int(round(hours_float * 60))
    hrs = total_mins // 60
    mins = total_mins % 60

    if hrs > 0:
        time_str = f"{hrs}h {mins}m" if mins > 0 else f"{hrs} hr"
    else:
        time_str = f"{mins} mins"

    return {
        "speed_knots": speed_knots,
        "burn_rate_l_nm": burn_rate_l_nm,
        "optimal_distance_nm": distance_nm,
        "optimal_fuel_liters": optimal_liters,
        "unoptimized_distance_nm": unoptimized_distance_nm,
        "unoptimized_fuel_liters": unoptimized_liters,
        "fuel_saved_liters": saved_liters,
        "cost_saved_inr": cost_saved,
        "transit_time_hours": round(hours_float, 2),
        "transit_time_str": time_str,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Geospatial Line & Polygon Collision (Hazard Avoidance)
# ─────────────────────────────────────────────────────────────────────────────

def _ccw(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]) -> bool:
    """Return True if points p1, p2, p3 are listed in counter-clockwise order."""
    return (p3[1] - p1[1]) * (p2[0] - p1[0]) > (p2[1] - p1[1]) * (p3[0] - p1[0])


def _segments_intersect(
    seg1_a: tuple[float, float],
    seg1_b: tuple[float, float],
    seg2_a: tuple[float, float],
    seg2_b: tuple[float, float],
) -> bool:
    """
    Check if line segment (seg1_a -> seg1_b) intersects line segment (seg2_a -> seg2_b).
    Points formatted as (lat, lon).
    """
    if (max(seg1_a[0], seg1_b[0]) < min(seg2_a[0], seg2_b[0]) or
        min(seg1_a[0], seg1_b[0]) > max(seg2_a[0], seg2_b[0]) or
        max(seg1_a[1], seg1_b[1]) < min(seg2_a[1], seg2_b[1]) or
        min(seg1_a[1], seg1_b[1]) > max(seg2_a[1], seg2_b[1])):
        return False

    return (_ccw(seg1_a, seg2_a, seg2_b) != _ccw(seg1_b, seg2_a, seg2_b) and
            _ccw(seg1_a, seg1_b, seg2_a) != _ccw(seg1_a, seg1_b, seg2_b))


def _point_inside_polygon(lat: float, lon: float, poly: list[list[float]]) -> bool:
    """Ray casting algorithm to determine if (lat, lon) is inside polygon."""
    inside = False
    n = len(poly)
    if n < 3:
        return False

    p1x, p1y = poly[0][0], poly[0][1]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n][0], poly[i % n][1]
        if min(p1y, p2y) < lon <= max(p1y, p2y):
            if lat <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (lon - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or lat <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def check_geofence_intersection(
    start_coords: list[float] | tuple[float, float],
    end_coords: list[float] | tuple[float, float],
    hazard_geofences: Optional[list] = None,
) -> tuple[bool, Optional[list[float]]]:
    """
    Check if the direct transit segment between start_coords and end_coords traverses
    any active hazard geofence polygon.

    If intersection or intrusion occurs, compute a safe seaward clearance detour waypoint.

    Args:
        start_coords: [lat, lon] of departure point
        end_coords:   [lat, lon] of destination (PFZ hotspot)
        hazard_geofences: list of polygon coordinate lists `[[ [lat, lon], ... ], ...]`

    Returns:
        (is_intersecting: bool, detour_waypoint: Optional[[lat, lon]])
    """
    if not hazard_geofences:
        return False, None

    s = (float(start_coords[0]), float(start_coords[1]))
    e = (float(end_coords[0]), float(end_coords[1]))

    mid_lat = (s[0] + e[0]) / 2.0
    mid_lon = (s[1] + e[1]) / 2.0

    hit_poly = None

    for poly in hazard_geofences:
        if not poly or len(poly) < 3:
            continue

        intersected = False
        n = len(poly)
        for i in range(n):
            poly_a = (float(poly[i][0]), float(poly[i][1]))
            poly_b = (float(poly[(i + 1) % n][0]), float(poly[(i + 1) % n][1]))
            if _segments_intersect(s, e, poly_a, poly_b):
                intersected = True
                break

        if intersected or _point_inside_polygon(mid_lat, mid_lon, poly):
            hit_poly = poly
            break

    if not hit_poly:
        return False, None

    # Determine seaward buffer direction
    is_west_coast = mid_lon < 79.0

    if is_west_coast:
        furthest_seaward_lon = min(float(p[1]) for p in hit_poly)
        detour_lon = round(furthest_seaward_lon - 0.08, 4)
    else:
        furthest_seaward_lon = max(float(p[1]) for p in hit_poly)
        detour_lon = round(furthest_seaward_lon + 0.08, 4)

    detour_lat = round(mid_lat, 4)
    detour_point = [detour_lat, detour_lon]

    return True, detour_point


# ─────────────────────────────────────────────────────────────────────────────
# IMBL Geofencing & Proximity Calculations (ISRO SIH 26176)
# ─────────────────────────────────────────────────────────────────────────────

def distance_point_to_line_segment_nm(
    p_lat: float, p_lon: float,
    a_lat: float, a_lon: float,
    b_lat: float, b_lon: float,
) -> float:
    """
    Calculate minimum distance from GPS point P to geodesic line segment AB in Nautical Miles.
    Uses equirectangular planar projection for local spherical geometry.
    """
    mid_lat = math.radians((p_lat + a_lat + b_lat) / 3.0)
    cos_lat = math.cos(mid_lat)

    # Convert coordinates to local NM coordinates relative to P(0, 0)
    # 1 degree of latitude = 60.0 Nautical Miles
    xa = (a_lon - p_lon) * cos_lat * 60.0
    ya = (a_lat - p_lat) * 60.0
    xb = (b_lon - p_lon) * cos_lat * 60.0
    yb = (b_lat - p_lat) * 60.0

    vx = xb - xa
    vy = yb - ya
    seg_len_sq = vx * vx + vy * vy

    if seg_len_sq < 1e-9:
        # Segment collapsed to a single point
        return round(math.sqrt(xa * xa + ya * ya), 2)

    # Project point P(0,0) onto segment AB: t = - (xa*vx + ya*vy) / seg_len_sq
    t = -(xa * vx + ya * vy) / seg_len_sq
    t_clamped = max(0.0, min(1.0, t))

    closest_x = xa + t_clamped * vx
    closest_y = ya + t_clamped * vy

    return round(math.sqrt(closest_x * closest_x + closest_y * closest_y), 2)


def check_imbl_proximity(
    route_points: list[list[float]],
    threshold_nm: float = 5.0,
    boundaries: Optional[dict[str, list[list[float]]]] = None,
) -> dict:
    """
    Evaluate whether any point along the navigation route breaches the
    IMBL (International Maritime Boundary Line) safety clearance corridor (default 5 NM).

    Checks all route waypoints and interpolated route segments against
    all IMBL line segments.

    Returns:
        {
            "imbl_warning_active": bool,
            "closest_boundary": Optional[str],
            "min_distance_nm": float,
            "warning_message": Optional[str],
        }
    """
    target_boundaries = boundaries or IMBL_BOUNDARIES
    min_dist = float("inf")
    closest_b_name = None

    if not route_points:
        return {
            "imbl_warning_active": False,
            "closest_boundary": None,
            "min_distance_nm": 999.0,
            "warning_message": None,
        }

    # Interpolate intermediate sampling points along route legs (every ~1 NM)
    sampled_points: list[tuple[float, float]] = []
    for i in range(len(route_points) - 1):
        p1 = route_points[i]
        p2 = route_points[i + 1]
        sampled_points.append((p1[0], p1[1]))

        leg_km, leg_nm = haversine_distance_nm(p1[0], p1[1], p2[0], p2[1])
        num_steps = max(1, int(math.ceil(leg_nm)))
        for s in range(1, num_steps):
            frac = s / num_steps
            interp_lat = p1[0] + frac * (p2[0] - p1[0])
            interp_lon = p1[1] + frac * (p2[1] - p1[1])
            sampled_points.append((interp_lat, interp_lon))

    sampled_points.append((route_points[-1][0], route_points[-1][1]))

    # Test all sampled points against all IMBL segments
    for b_name, coords in target_boundaries.items():
        for j in range(len(coords) - 1):
            a_lat, a_lon = coords[j]
            b_lat, b_lon = coords[j + 1]
            for p_lat, p_lon in sampled_points:
                d_nm = distance_point_to_line_segment_nm(
                    p_lat, p_lon, a_lat, a_lon, b_lat, b_lon
                )
                if d_nm < min_dist:
                    min_dist = d_nm
                    closest_b_name = b_name

    warning_active = min_dist < threshold_nm
    warning_msg = None
    if warning_active and closest_b_name:
        warning_msg = (
            f"🛑 IMBL PROXIMITY WARNING: Risk of Impoundment! "
            f"Vessel track is {min_dist:.1f} NM from {closest_b_name} international boundary "
            f"(threshold: {threshold_nm:.1f} NM). High seizure risk by foreign maritime enforcement."
        )

    return {
        "imbl_warning_active": warning_active,
        "closest_boundary": closest_b_name if min_dist < float("inf") else None,
        "min_distance_nm": round(min_dist, 2) if min_dist < float("inf") else 999.0,
        "warning_message": warning_msg,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Master Route Generator
# ─────────────────────────────────────────────────────────────────────────────

def calculate_optimal_route(
    start_coords: list[float] | tuple[float, float],
    end_coords: list[float] | tuple[float, float],
    hazard_geofences: Optional[list] = None,
    start_label: str = "Departure Port",
    end_label: str = "PFZ Hotspot",
    vessel_speed_knots: float = DEFAULT_VESSEL_SPEED_KNOTS,
    burn_rate_l_nm: float = DEFAULT_BURN_RATE_L_NM,
    diesel_price_inr: float = DEFAULT_DIESEL_PRICE_INR,
    imbl_threshold_nm: float = 5.0,
) -> dict:
    """
    Generate complete fuel-optimal waypoint navigation plan with IMBL proximity screening.
    """
    s_lat, s_lon = float(start_coords[0]), float(start_coords[1])
    e_lat, e_lon = float(end_coords[0]), float(end_coords[1])

    direct_bearing, direct_heading = calculate_compass_bearing(s_lat, s_lon, e_lat, e_lon)

    has_hazard, detour_coords = check_geofence_intersection(
        (s_lat, s_lon), (e_lat, e_lon), hazard_geofences=hazard_geofences
    )

    if has_hazard and detour_coords is not None:
        d_lat, d_lon = detour_coords[0], detour_coords[1]

        km_1, nm_1 = haversine_distance_nm(s_lat, s_lon, d_lat, d_lon)
        _, bearing_1 = calculate_compass_bearing(s_lat, s_lon, d_lat, d_lon)

        km_2, nm_2 = haversine_distance_nm(d_lat, d_lon, e_lat, e_lon)
        _, bearing_2 = calculate_compass_bearing(d_lat, d_lon, e_lat, e_lon)

        total_km = round(km_1 + km_2, 2)
        total_nm = round(nm_1 + nm_2, 2)

        waypoints = [
            {
                "wp_id": 1,
                "name": f"WP-1: {start_label}",
                "lat": s_lat,
                "lon": s_lon,
                "leg_distance_nm": 0.0,
                "leg_bearing": None,
                "notes": "Departure mooring / port anchorage",
            },
            {
                "wp_id": 2,
                "name": "WP-2: Hazard Clearance Detour",
                "lat": d_lat,
                "lon": d_lon,
                "leg_distance_nm": nm_1,
                "leg_bearing": bearing_1,
                "notes": "Seaward detour waypoint: safely skirts active hazard geofence",
            },
            {
                "wp_id": 3,
                "name": f"WP-3: {end_label}",
                "lat": e_lat,
                "lon": e_lon,
                "leg_distance_nm": nm_2,
                "leg_bearing": bearing_2,
                "notes": "Target PFZ coordinates: commence fishing operations",
            },
        ]
        route_points = [[s_lat, s_lon], [d_lat, d_lon], [e_lat, e_lon]]
        geofence_status = "⚠️ Detour Active (Hazard Avoidance Engaged)"
        hazard_avoidance_active = True
    else:
        total_km, total_nm = haversine_distance_nm(s_lat, s_lon, e_lat, e_lon)

        waypoints = [
            {
                "wp_id": 1,
                "name": f"WP-1: {start_label}",
                "lat": s_lat,
                "lon": s_lon,
                "leg_distance_nm": 0.0,
                "leg_bearing": None,
                "notes": "Departure mooring / harbor exit",
            },
            {
                "wp_id": 2,
                "name": f"WP-2: {end_label}",
                "lat": e_lat,
                "lon": e_lon,
                "leg_distance_nm": total_nm,
                "leg_bearing": direct_heading,
                "notes": "Target PFZ coordinates: commence fishing operations",
            },
        ]
        route_points = [[s_lat, s_lon], [e_lat, e_lon]]
        geofence_status = "✅ Safe & Clear of Hazard Geofences"
        hazard_avoidance_active = False

    fuel_metrics = estimate_fuel_consumption(
        distance_nm=total_nm,
        speed_knots=vessel_speed_knots,
        burn_rate_l_nm=burn_rate_l_nm,
        diesel_price_inr=diesel_price_inr,
    )

    # ── IMBL Proximity Screening (ISRO SIH 26176) ─────────────────────────────
    imbl_check = check_imbl_proximity(route_points, threshold_nm=imbl_threshold_nm)
    imbl_warning_active = imbl_check["imbl_warning_active"]
    imbl_min_distance_nm = imbl_check["min_distance_nm"]
    imbl_closest_boundary = imbl_check["closest_boundary"]
    imbl_warning_message = imbl_check["warning_message"]

    if imbl_warning_active:
        route_color = "#dc3545"  # Alert Red
        geofence_status = (
            f"{geofence_status} | 🛑 IMBL WARNING: Within {imbl_min_distance_nm:.1f} NM "
            f"of {imbl_closest_boundary}"
        )
    elif hazard_avoidance_active:
        route_color = "#d9534f"  # Warning Amber/Red
    else:
        route_color = "#0056b3"  # Navigational Blue

    return {
        "success": True,
        "start_coords": [s_lat, s_lon],
        "end_coords": [e_lat, e_lon],
        "start_label": start_label,
        "end_label": end_label,
        "total_distance_km": total_km,
        "total_distance_nm": total_nm,
        "direct_bearing_deg": direct_bearing,
        "direct_heading_str": direct_heading,
        "hazard_avoidance_active": hazard_avoidance_active,
        "geofence_status": geofence_status,
        "waypoints": waypoints,
        "route_points": route_points,
        "fuel_economy": fuel_metrics,
        "imbl_warning_active": imbl_warning_active,
        "imbl_min_distance_nm": imbl_min_distance_nm,
        "imbl_closest_boundary": imbl_closest_boundary,
        "imbl_warning_message": imbl_warning_message,
        "route_color": route_color,
    }
