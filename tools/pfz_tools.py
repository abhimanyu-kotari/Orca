"""
tools/pfz_tools.py — Potential Fishing Zone (PFZ) data layer.

DESIGN PRINCIPLE:
    Pure data / computation module — no AI calls, no Streamlit.
    Provides the structured PFZ dataset and the spatial query functions
    that the PFZ Agent consumes.

DATA SOURCE (mock):
    Zone coordinates, species, and depth data are modelled after real
    INCOIS (Indian National Centre for Ocean Information Services)
    PFZ advisories. In production, these would be replaced by a live
    INCOIS API call or a daily-downloaded GeoJSON feed.

Functions exported:
    get_all_zones()                            → full PFZ database
    find_nearest_zones(lat, lon, n, max_km)    → n closest zones
    haversine_km(lat1, lon1, lat2, lon2)       → great-circle distance
"""

import math
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Haversine great-circle distance
# ─────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the straight-line distance (great-circle) between two GPS points.

    Formula: Haversine — numerically stable for short and long distances.
    Accuracy: within ~0.5% for distances up to 20,000 km.

    Args:
        lat1, lon1: Starting point (decimal degrees).
        lat2, lon2: Destination point (decimal degrees).

    Returns:
        Distance in kilometres (float).
    """
    R = 6371.0                           # Earth's mean radius (km)
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ     = math.radians(lat2 - lat1)
    Δλ     = math.radians(lon2 - lon1)
    a = (math.sin(Δφ / 2) ** 2
         + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─────────────────────────────────────────────────────────────────────────────
# PFZ Database — modelled after INCOIS advisories
# ─────────────────────────────────────────────────────────────────────────────
# Each entry is a GeoJSON-compatible dict:
#   zone_id              : unique identifier
#   name                 : human-readable zone name
#   lat, lon             : centroid of the PFZ (decimal degrees)
#   depth_m              : sea depth at zone centroid (metres)
#   quality              : "HIGH" | "MEDIUM" | "LOW"
#   species              : list of commercially important target species
#   distance_from_shore_km: approximate distance from nearest coastline
#   advisory             : one-line operational note for fishermen
#   region               : Indian state / territory
#   best_season          : months when productivity peaks

PFZ_DATABASE: list[dict] = [

    # ── Kerala ──────────────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-KL-001",
        "name":                  "Kochi Offshore Upwelling Zone",
        "lat":                   9.72,
        "lon":                   75.82,
        "depth_m":               38,
        "quality":               "HIGH",
        "species":               ["Indian Mackerel", "Oil Sardine", "Skipjack Tuna"],
        "distance_from_shore_km": 18,
        "advisory":              "Strong coastal upwelling. High chlorophyll band detected SW of Kochi.",
        "region":                "Kerala",
        "best_season":           "Jun–Sep (SW Monsoon upwelling)",
    },
    {
        "zone_id":               "PFZ-KL-002",
        "name":                  "Thiruvananthapuram Deep Water Zone",
        "lat":                   8.30,
        "lon":                   76.50,
        "depth_m":               60,
        "quality":               "MEDIUM",
        "species":               ["Seer Fish", "Yellow-fin Tuna", "Barracuda"],
        "distance_from_shore_km": 22,
        "advisory":              "Moderate productivity. Thermocline at 40 m depth.",
        "region":                "Kerala",
        "best_season":           "Nov–Mar (NE Monsoon)",
    },
    {
        "zone_id":               "PFZ-KL-003",
        "name":                  "Kozhikode–Kannur Continental Shelf",
        "lat":                   11.50,
        "lon":                   75.52,
        "depth_m":               45,
        "quality":               "HIGH",
        "species":               ["Oil Sardine", "Indian Mackerel", "Ribbon Fish"],
        "distance_from_shore_km": 15,
        "advisory":              "Dense surface shoals reported. Best trawl window: 0500–1100 hrs.",
        "region":                "Kerala",
        "best_season":           "Jul–Oct",
    },
    {
        "zone_id":               "PFZ-KL-004",
        "name":                  "Lakshadweep Sea Deep-Sea Corridor",
        "lat":                   10.00,
        "lon":                   74.50,
        "depth_m":               1200,
        "quality":               "HIGH",
        "species":               ["Yellow-fin Tuna", "Big-eye Tuna", "Swordfish"],
        "distance_from_shore_km": 120,
        "advisory":              "Deep-sea zone. Requires licensed deep-sea vessel. High tuna density.",
        "region":                "Kerala / Lakshadweep",
        "best_season":           "Jan–May",
    },

    # ── Tamil Nadu ───────────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-TN-001",
        "name":                  "Rameswaram Palk Strait Zone",
        "lat":                   9.15,
        "lon":                   79.65,
        "depth_m":               12,
        "quality":               "HIGH",
        "species":               ["Prawns", "Cuttlefish", "Reef Fish"],
        "distance_from_shore_km": 8,
        "advisory":              "Shallow-water zone. Check tidal windows. Rich reef ecosystem.",
        "region":                "Tamil Nadu",
        "best_season":           "Nov–Mar",
    },
    {
        "zone_id":               "PFZ-TN-002",
        "name":                  "Tuticorin Gulf of Mannar Zone",
        "lat":                   8.75,
        "lon":                   78.40,
        "depth_m":               25,
        "quality":               "MEDIUM",
        "species":               ["Pearl Spot", "Sea Cucumber", "Lobster"],
        "distance_from_shore_km": 14,
        "advisory":              "Marine protected area boundary nearby. Verify coordinates before trawling.",
        "region":                "Tamil Nadu",
        "best_season":           "Oct–Feb",
    },
    {
        "zone_id":               "PFZ-TN-003",
        "name":                  "Nagapattinam Bay of Bengal Shelf",
        "lat":                   11.00,
        "lon":                   80.22,
        "depth_m":               35,
        "quality":               "MEDIUM",
        "species":               ["Catfish", "Shrimp", "Pomfret"],
        "distance_from_shore_km": 20,
        "advisory":              "Moderate chlorophyll. Post-monsoon productivity improving.",
        "region":                "Tamil Nadu",
        "best_season":           "Dec–Feb",
    },
    {
        "zone_id":               "PFZ-TN-004",
        "name":                  "Chennai–Ennore Nearshore Zone",
        "lat":                   13.32,
        "lon":                   80.50,
        "depth_m":               20,
        "quality":               "LOW",
        "species":               ["Mullet", "Anchovy", "Needlefish"],
        "distance_from_shore_km": 10,
        "advisory":              "Low productivity due to port industrial discharge. Exercise caution.",
        "region":                "Tamil Nadu",
        "best_season":           "Jan–Mar only",
    },

    # ── Karnataka ────────────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-KA-001",
        "name":                  "Mangalore Upwelling Hotspot",
        "lat":                   12.68,
        "lon":                   74.48,
        "depth_m":               50,
        "quality":               "HIGH",
        "species":               ["Indian Mackerel", "Squid", "Seer Fish"],
        "distance_from_shore_km": 16,
        "advisory":              "Persistent upwelling cell. Highest CPUE recorded in Jul–Aug.",
        "region":                "Karnataka",
        "best_season":           "Jun–Sep",
    },
    {
        "zone_id":               "PFZ-KA-002",
        "name":                  "Karwar Deep-Water Ridge Zone",
        "lat":                   14.88,
        "lon":                   73.80,
        "depth_m":               80,
        "quality":               "MEDIUM",
        "species":               ["Tuna", "Kingfish", "Prawns"],
        "distance_from_shore_km": 25,
        "advisory":              "Submarine ridge creates fish aggregation. Early morning best.",
        "region":                "Karnataka / Goa border",
        "best_season":           "Oct–Feb",
    },

    # ── Maharashtra ──────────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-MH-001",
        "name":                  "Mumbai Offshore Pomfret Zone",
        "lat":                   18.92,
        "lon":                   72.42,
        "depth_m":               30,
        "quality":               "MEDIUM",
        "species":               ["Silver Pomfret", "Bombay Duck", "Ribbon Fish"],
        "distance_from_shore_km": 20,
        "advisory":              "Active zone but high vessel traffic. Monitor AIS before entry.",
        "region":                "Maharashtra",
        "best_season":           "Nov–Feb",
    },
    {
        "zone_id":               "PFZ-MH-002",
        "name":                  "Ratnagiri Shelf Edge Zone",
        "lat":                   16.82,
        "lon":                   72.78,
        "depth_m":               65,
        "quality":               "HIGH",
        "species":               ["Yellow-fin Tuna", "Seer Fish", "Mackerel"],
        "distance_from_shore_km": 28,
        "advisory":              "Shelf-edge upwelling. Historically highest yield in Konkan region.",
        "region":                "Maharashtra",
        "best_season":           "Oct–Mar",
    },
    {
        "zone_id":               "PFZ-MH-003",
        "name":                  "Malvan Coastal Reef Zone",
        "lat":                   15.70,
        "lon":                   73.42,
        "depth_m":               22,
        "quality":               "MEDIUM",
        "species":               ["Grouper", "Snapper", "Crab"],
        "distance_from_shore_km": 12,
        "advisory":              "Reef area — use line fishing; trawling prohibited.",
        "region":                "Maharashtra",
        "best_season":           "Nov–Mar",
    },

    # ── Gujarat ──────────────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-GJ-001",
        "name":                  "Veraval–Porbandar Productive Corridor",
        "lat":                   21.00,
        "lon":                   69.82,
        "depth_m":               40,
        "quality":               "HIGH",
        "species":               ["Bombay Duck", "Shrimp", "Pomfret"],
        "distance_from_shore_km": 20,
        "advisory":              "One of India's richest zones. High seasonal CPUE.",
        "region":                "Gujarat",
        "best_season":           "Sep–Jan",
    },
    {
        "zone_id":               "PFZ-GJ-002",
        "name":                  "Gulf of Kutch Northern Zone",
        "lat":                   22.50,
        "lon":                   69.02,
        "depth_m":               15,
        "quality":               "MEDIUM",
        "species":               ["Hilsa", "Mullet", "Anchovy"],
        "distance_from_shore_km": 12,
        "advisory":              "Tidal currents strong. Fishing window limited to slack tide.",
        "region":                "Gujarat",
        "best_season":           "Oct–Dec",
    },

    # ── Andhra Pradesh ───────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-AP-001",
        "name":                  "Visakhapatnam Bay of Bengal Upwelling",
        "lat":                   17.52,
        "lon":                   83.72,
        "depth_m":               55,
        "quality":               "HIGH",
        "species":               ["Yellow-fin Tuna", "Seer Fish", "Prawns"],
        "distance_from_shore_km": 22,
        "advisory":              "Consistent upwelling near submarine canyon. Best yields Oct–Jan.",
        "region":                "Andhra Pradesh",
        "best_season":           "Oct–Jan",
    },
    {
        "zone_id":               "PFZ-AP-002",
        "name":                  "Kakinada Offshore Delta Zone",
        "lat":                   16.82,
        "lon":                   82.50,
        "depth_m":               35,
        "quality":               "MEDIUM",
        "species":               ["Prawns", "Catfish", "Mullet"],
        "distance_from_shore_km": 18,
        "advisory":              "River outflow enriches zone post-monsoon. Peak: Nov–Feb.",
        "region":                "Andhra Pradesh",
        "best_season":           "Nov–Feb",
    },

    # ── Odisha ───────────────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-OD-001",
        "name":                  "Paradip Offshore Continental Shelf",
        "lat":                   20.08,
        "lon":                   87.00,
        "depth_m":               45,
        "quality":               "MEDIUM",
        "species":               ["Hilsa", "Prawns", "Pomfret"],
        "distance_from_shore_km": 20,
        "advisory":              "Mahanadi plume creates nutrient-rich patch post-monsoon.",
        "region":                "Odisha",
        "best_season":           "Oct–Feb",
    },
    {
        "zone_id":               "PFZ-OD-002",
        "name":                  "Chilika Lake Outlet Estuarine Zone",
        "lat":                   19.52,
        "lon":                   85.55,
        "depth_m":               8,
        "quality":               "LOW",
        "species":               ["Mullet", "Prawn", "Crab"],
        "distance_from_shore_km": 5,
        "advisory":              "Very shallow. Small traditional craft only. Rich estuarine biodiversity.",
        "region":                "Odisha",
        "best_season":           "Dec–Feb",
    },

    # ── West Bengal ──────────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-WB-001",
        "name":                  "Sundarbans–Haldia Bay of Bengal Zone",
        "lat":                   21.62,
        "lon":                   88.18,
        "depth_m":               18,
        "quality":               "MEDIUM",
        "species":               ["Hilsa", "Tiger Prawn", "Anchovy"],
        "distance_from_shore_km": 15,
        "advisory":              "Ganges outflow creates seasonal nursery ground. Cyclone risk Jun–Nov.",
        "region":                "West Bengal",
        "best_season":           "Feb–May",
    },

    # ── Andaman & Nicobar ────────────────────────────────────────────────────
    {
        "zone_id":               "PFZ-AN-001",
        "name":                  "Andaman Sea Tuna Aggregation Zone",
        "lat":                   11.50,
        "lon":                   93.00,
        "depth_m":               800,
        "quality":               "HIGH",
        "species":               ["Yellow-fin Tuna", "Bigeye Tuna", "Mahi-mahi"],
        "distance_from_shore_km": 35,
        "advisory":              "International-grade tuna fishery. Export-quality catch. Deep-sea vessel required.",
        "region":                "Andaman & Nicobar Islands",
        "best_season":           "Jan–Apr",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_all_zones() -> list[dict]:
    """Return the complete PFZ database (read-only copy)."""
    return list(PFZ_DATABASE)   # shallow copy — safe since dicts are not mutated


def find_nearest_zones(
    user_lat: float,
    user_lon: float,
    max_results: int = 5,
    max_distance_km: float = 400.0,
) -> list[dict]:
    """
    Find the closest PFZ zones to a given GPS position.

    Each returned zone dict has one extra key added:
        "distance_to_user_km" (float): great-circle distance from user to zone centroid.

    Zones beyond max_distance_km are excluded so that a Kochi user does not
    see Andaman zones in their top-5 list.

    Args:
        user_lat         : User / vessel latitude (decimal degrees).
        user_lon         : User / vessel longitude (decimal degrees).
        max_results      : Maximum number of zones to return (default 5).
        max_distance_km  : Hard cutoff — zones further than this are ignored.

    Returns:
        List of zone dicts sorted by ascending distance_to_user_km.
        May be empty if no zones exist within max_distance_km.
    """
    enriched = []
    for zone in PFZ_DATABASE:
        dist = haversine_km(user_lat, user_lon, zone["lat"], zone["lon"])
        if dist <= max_distance_km:
            enriched.append({**zone, "distance_to_user_km": round(dist, 1)})

    enriched.sort(key=lambda z: z["distance_to_user_km"])
    return enriched[:max_results]


def to_geojson(zones: list[dict]) -> dict:
    """
    Convert a list of PFZ zone dicts to a GeoJSON FeatureCollection.

    Useful for future integration with QGIS, Mapbox, or INCOIS data feeds.

    Args:
        zones: List of zone dicts (as returned by find_nearest_zones or get_all_zones).

    Returns:
        GeoJSON FeatureCollection dict.
    """
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type":        "Point",
                "coordinates": [z["lon"], z["lat"]],  # GeoJSON: [lon, lat]
            },
            "properties": {k: v for k, v in z.items() if k not in ("lat", "lon")},
        }
        for z in zones
    ]
    return {"type": "FeatureCollection", "features": features}
