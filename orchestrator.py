"""
orchestrator.py — Master Orchestrator & Multi-Agent Synthesis (Phase 4)

─────────────────────────────────────────────────────────────────────────────
RESPONSIBILITY
─────────────────────────────────────────────────────────────────────────────
Acts as the central coordination engine for ORCA:
  1. Calls Intent & Language Agent to classify query and extract entities.
  2. Routes to appropriate domain agents.
  3. Executes Weather Agent and PFZ Agent in parallel via ThreadPoolExecutor
     when fishing or coastal activity is evaluated.
  4. Enforces Safety Gating:
     - DANGER weather verdict: Suppresses PFZ recommendations completely
       (small craft safety invariant).
     - CAUTION weather verdict: Displays PFZ recommendations with high-risk
       warning banners.
     - SAFE weather verdict: Synthesizes optimal fishing zones and benign sea conditions.
  5. Produces a unified multi-agent response dictionary that UI layers (app.py)
     can render seamlessly.

─────────────────────────────────────────────────────────────────────────────
INTERFACE — Uniform across all ORCA agents
─────────────────────────────────────────────────────────────────────────────
    run(inputs: dict) -> dict

INPUTS:
    "query"        (str, required): Raw text query from the user.
    "location"     (str, optional): Explicit override for location name.
    "time_context" (str, optional): Explicit override for time window.

OUTPUTS (Schema):
    "success"                (bool): True if orchestration completed
    "intent"                 (str):  Detected intent category
    "intent_result"          (dict): Raw output from intent_agent
    "agents_invoked"         (list): Names of agents called during execution
    "weather_result"         (dict | None): Output from weather_agent
    "pfz_result"             (dict | None): Output from pfz_agent (None if suppressed)
    "pfz_suppressed"         (bool): True if PFZ was withheld for safety
    "pfz_suppression_reason" (str | None): Explanation for safety suppression
    "synthesis"              (str):  Unified natural language summary/explanation
    "synthesis_source"       (str):  Source of the synthesis
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from agents.intent_agent import run as intent_agent_run
from agents.weather_agent import run as weather_agent_run
from agents.pfz_agent import run as pfz_agent_run
from agents.hazard_agent import run as hazard_agent_run
from tools.navigation_tools import calculate_optimal_route
from tools.map_tools import _generate_coastal_geofence_coords


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Coming soon placeholders for future phases
# ─────────────────────────────────────────────────────────────────────────────

def _format_coming_soon_text(intent: str) -> str:
    messages = {
        "alert_query": (
            "🚨 Alert & Hazard Agent is planned for Phase 5. "
            "It will stream live IMD/NDMA cyclone, storm surge, and coastal warnings."
        ),
        "route_planning": (
            "🧭 Navigation & Routing Agent is planned for Phase 5. "
            "It will compute optimal vessel paths avoiding hazardous sea corridors."
        ),
        "ecosystem_query": (
            "🌊 Ocean Analytics Agent is planned for Phase 5. "
            "It will analyze chlorophyll and SST trends from satellite Earth Observation feeds."
        ),
    }
    return messages.get(
        intent,
        "This capability is planned for a future release. "
        "Ask me about weather, sea conditions, or where to fish!"
    )


def _extract_target_coords(pfz_res: dict) -> tuple[Optional[float], Optional[float], str]:
    """Safely extract destination lat, lon, and name from a pfz_agent response."""
    best = pfz_res.get("best_zone") or {}
    name = best.get("name") or "Target PFZ Hotspot"
    lat = best.get("lat")
    lon = best.get("lon")
    if lat is None or lon is None:
        for z in pfz_res.get("zones", []):
            if (best.get("zone_id") and z.get("zone_id") == best.get("zone_id")) or (best.get("name") and z.get("name") == best.get("name")):
                lat = z.get("lat")
                lon = z.get("lon")
                name = z.get("name") or name
                break
    # Fallback to first zone in list if best_zone lacked coords
    if (lat is None or lon is None) and pfz_res.get("zones"):
        first_z = pfz_res["zones"][0]
        lat = first_z.get("lat")
        lon = first_z.get("lon")
        name = first_z.get("name") or name
    return lat, lon, name


# ─────────────────────────────────────────────────────────────────────────────
# Master Orchestrator entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def run(inputs: dict) -> dict:
    """
    Execute the Master Orchestration pipeline.

    Args:
        inputs (dict): Must contain "query" (str), with optional "location"
                       and "time_context" overrides.

    Returns:
        dict: Standardized orchestration result dictionary.
    """
    if not isinstance(inputs, dict):
        inputs = {}

    raw_query = inputs.get("query", "")
    query = raw_query.strip() if isinstance(raw_query, str) else ""

    # ── Guard: Empty query ───────────────────────────────────────────────────
    if not query and not inputs.get("location"):
        return {
            "success": True,
            "intent": "unknown",
            "intent_result": {
                "success": False,
                "intent": "unknown",
                "language": "English",
                "language_code": "en",
                "entities": {"location": None, "time_context": "today"},
                "gemini_response": None,
                "raw_query": query,
                "original_text": query,
                "translated_text": query,
            },
            "agents_invoked": [],
            "weather_result": None,
            "pfz_result": None,
            "navigation_result": None,
            "pfz_suppressed": False,
            "pfz_suppression_reason": None,
            "synthesis": "Please enter a question or coastal location to get started.",
            "synthesis_source": "rule-based",
        }

    # ── Step 1: Intent & Language Analysis ───────────────────────────────────
    intent_result = intent_agent_run({"query": query})
    agents_invoked = ["intent_agent"]

    intent = intent_result.get("intent", "unknown")
    entities = intent_result.get("entities", {})

    # Allow caller overrides (e.g. sidebar parameters), falling back to intent extraction
    location = inputs.get("location") or entities.get("location")
    time_context = inputs.get("time_context") or entities.get("time_context", "today")

    # ── Step 2: Route by Intent ──────────────────────────────────────────────

    # Case A: Casual conversation
    if intent == "casual_chat":
        greeting = (
            intent_result.get("gemini_response")
            or "👋 Hello! I'm ORCA, your marine intelligence assistant. "
               "Ask me about sea safety, wave conditions, or where to fish!"
        )
        return {
            "success": True,
            "intent": intent,
            "intent_result": intent_result,
            "agents_invoked": agents_invoked,
            "weather_result": None,
            "pfz_result": None,
            "navigation_result": None,
            "pfz_suppressed": False,
            "pfz_suppression_reason": None,
            "synthesis": greeting,
            "synthesis_source": "intent_agent" if intent_result.get("gemini_response") else "rule-based",
        }

    # Case B: Weather & Sea Safety Check
    if intent in ("weather_check", "safety_check"):
        if not location:
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": None,
                "pfz_result": None,
                "navigation_result": None,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": (
                    "📍 I couldn't determine a coastal location from your query. "
                    "Please specify a port or coastal city (e.g., 'Is it safe near Rameswaram tomorrow?')."
                ),
                "synthesis_source": "rule-based",
            }

        weather_res = weather_agent_run({
            "location": location,
            "time_context": time_context,
        })
        agents_invoked.append("weather_agent")

        synthesis = weather_res.get("summary", "") if weather_res.get("success") else weather_res.get("error", "Weather data unavailable.")
        return {
            "success": bool(weather_res.get("success", True)),
            "intent": intent,
            "intent_result": intent_result,
            "agents_invoked": agents_invoked,
            "weather_result": weather_res,
            "pfz_result": None,
            "navigation_result": None,
            "pfz_suppressed": False,
            "pfz_suppression_reason": None,
            "synthesis": synthesis,
            "synthesis_source": "weather_agent",
        }

    # Case C: Potential Fishing Zone (PFZ) Location with Safety Cross-Referencing
    if intent == "pfz_location":
        if not location:
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": None,
                "pfz_result": None,
                "navigation_result": None,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": (
                    "📍 Which coastal area are you planning to fish near? "
                    "Please mention a coastal town or port, such as 'Where to fish near Kochi?'."
                ),
                "synthesis_source": "rule-based",
            }

        # Parallel Execution: Run Weather Agent and PFZ Agent simultaneously
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_weather = executor.submit(
                weather_agent_run,
                {"location": location, "time_context": time_context}
            )
            future_pfz = executor.submit(
                pfz_agent_run,
                {"location": location}
            )
            weather_res = future_weather.result()
            pfz_res = future_pfz.result()

        agents_invoked.extend(["weather_agent", "pfz_agent"])

        verdict = weather_res.get("verdict", "SAFE") if weather_res.get("success") else "SAFE"

        # ── Cross-Reference & Safety Override ────────────────────────────────
        if verdict == "DANGER":
            pfz_suppressed = True
            suppression_reason = (
                f"DANGER weather conditions detected near {location}. "
                f"Peak wind/waves exceed maritime safety thresholds. "
                f"PFZ recommendations are suppressed to protect life and vessels at sea."
            )
            synthesis = (
                f"🚨 **DANGER Alert for {location}:** Severe weather or high sea state detected.\n\n"
                f"{weather_res.get('summary', '')}\n\n"
                f"⚠️ **FISHING ADVISORY SUPPRESSED:** Navigating to Potential Fishing Zones is strictly "
                f"discouraged under DANGER conditions. Small craft should not venture into the sea."
            )
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": None,  # Strictly withheld for safety
                "navigation_result": None,
                "pfz_suppressed": pfz_suppressed,
                "pfz_suppression_reason": suppression_reason,
                "synthesis": synthesis,
                "synthesis_source": "orchestrator_safety_override",
            }

        elif verdict == "CAUTION":
            pfz_suppressed = False
            best_zone = (pfz_res.get("best_zone") or {}) if pfz_res.get("success") else {}
            best_name = best_zone.get("name", "identified zone")

            # Calculate fuel-optimal route with hazard avoidance geofence
            nav_res = None
            if pfz_res.get("success"):
                u_lat = pfz_res.get("lat")
                u_lon = pfz_res.get("lon")
                t_lat, t_lon, t_name = _extract_target_coords(pfz_res)
                if u_lat is not None and u_lon is not None and t_lat is not None and t_lon is not None:
                    geos = [_generate_coastal_geofence_coords(u_lat, u_lon)]
                    nav_res = calculate_optimal_route(
                        start_coords=[u_lat, u_lon],
                        end_coords=[t_lat, t_lon],
                        hazard_geofences=geos,
                        start_label=pfz_res.get("location", location),
                        end_label=t_name,
                    )
                    agents_invoked.append("navigation_tools")

            synthesis = (
                f"⚠️ **CAUTION Advisory for {location}:** Sea conditions require heightened care.\n\n"
                f"{weather_res.get('summary', '')}\n\n"
                f"🐟 **PFZ Available with Caution:** Nearest hotspot is **{best_name}**. "
                f"{pfz_res.get('advisory', '') if pfz_res.get('success') else ''}"
            )
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": pfz_res if pfz_res.get("success") else None,
                "navigation_result": nav_res,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": synthesis,
                "synthesis_source": "orchestrator_synthesis",
            }

        else:  # SAFE
            pfz_suppressed = False
            best_zone = (pfz_res.get("best_zone") or {}) if pfz_res.get("success") else {}
            best_name = best_zone.get("name", "identified zone")

            # Calculate direct fuel-optimal route
            nav_res = None
            if pfz_res.get("success"):
                u_lat = pfz_res.get("lat")
                u_lon = pfz_res.get("lon")
                t_lat, t_lon, t_name = _extract_target_coords(pfz_res)
                if u_lat is not None and u_lon is not None and t_lat is not None and t_lon is not None:
                    nav_res = calculate_optimal_route(
                        start_coords=[u_lat, u_lon],
                        end_coords=[t_lat, t_lon],
                        hazard_geofences=None,
                        start_label=pfz_res.get("location", location),
                        end_label=t_name,
                    )
                    agents_invoked.append("navigation_tools")

            synthesis = (
                f"✅ **Favorable Conditions for {location}:** Weather and sea conditions are SAFE for operations.\n\n"
                f"{weather_res.get('summary', '')}\n\n"
                f"🐟 **Top Recommended Fishing Zone:** **{best_name}**.\n"
                f"{pfz_res.get('advisory', '') if pfz_res.get('success') else ''}"
            )
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": pfz_res if pfz_res.get("success") else None,
                "navigation_result": nav_res,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": synthesis,
                "synthesis_source": "orchestrator_synthesis",
            }

    # Case D: Active Alert & Maritime Disaster Evaluation (IMD Scales)
    if intent == "alert_query":
        if not location:
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": None,
                "pfz_result": None,
                "navigation_result": None,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": (
                    "📍 Which coastal sector or port would you like to evaluate for disaster/cyclone alerts? "
                    "For example: *'Check storm surge risk near Chennai'* or *'Cyclone alert for Visakhapatnam'*."
                ),
                "synthesis_source": "rule-based",
            }

        hazard_res = hazard_agent_run({
            "location": location,
            "time_context": time_context,
        })
        agents_invoked.append("hazard_agent")
        weather_res = hazard_res.get("weather_result")

        # Suppress PFZ if severe disaster state
        is_danger = (
            hazard_res.get("level") == "Level-2"
            or (weather_res and weather_res.get("verdict") == "DANGER")
        )
        pfz_suppressed = is_danger
        suppression_reason = (
            f"Level-2 Maritime Cyclone / Storm Hazard active near {location}. "
            f"Active geofence enforced — fishing advisories are strictly suppressed."
        ) if is_danger else None

        return {
            "success": bool(hazard_res.get("success", True)),
            "intent": intent,
            "intent_result": intent_result,
            "agents_invoked": agents_invoked,
            "weather_result": weather_res,
            "pfz_result": None,
            "navigation_result": None,
            "pfz_suppressed": pfz_suppressed,
            "pfz_suppression_reason": suppression_reason,
            "synthesis": hazard_res.get("summary", ""),
            "synthesis_source": "hazard_agent",
        }

    # Case E: Fuel-Optimal Navigation & Route Planning (Feature 2)
    if intent == "route_planning":
        if not location:
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": None,
                "pfz_result": None,
                "navigation_result": None,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": (
                    "📍 Which departure port or coastal area are you planning to navigate from? "
                    "For example: *'Plan route to fishing zone from Kochi'* or *'How to navigate from Rameswaram?'*."
                ),
                "synthesis_source": "rule-based",
            }

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_weather = executor.submit(
                weather_agent_run,
                {"location": location, "time_context": time_context}
            )
            future_pfz = executor.submit(
                pfz_agent_run,
                {"location": location}
            )
            weather_res = future_weather.result()
            pfz_res = future_pfz.result()

        agents_invoked.extend(["weather_agent", "pfz_agent", "navigation_tools"])
        verdict = weather_res.get("verdict", "SAFE") if weather_res.get("success") else "SAFE"

        if verdict == "DANGER":
            suppression_reason = (
                f"DANGER weather conditions active near {location}. "
                f"Navigation corridors and fishing routes are suspended for vessel survivability."
            )
            synthesis = (
                f"🚨 **Navigation Suspended for {location}:** Severe weather or high sea state detected.\n\n"
                f"{weather_res.get('summary', '')}\n\n"
                f"⛔ **TRANSIT NOT ADVISED:** Fuel-optimal waypoint routing is suspended under DANGER status."
            )
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": None,
                "navigation_result": None,
                "pfz_suppressed": True,
                "pfz_suppression_reason": suppression_reason,
                "synthesis": synthesis,
                "synthesis_source": "orchestrator_safety_override",
            }

        u_lat = pfz_res.get("lat") if pfz_res.get("success") else None
        u_lon = pfz_res.get("lon") if pfz_res.get("success") else None
        t_lat, t_lon, t_name = _extract_target_coords(pfz_res) if pfz_res.get("success") else (None, None, "Target PFZ")

        if u_lat is None or u_lon is None or t_lat is None or t_lon is None:
            return {
                "success": False,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": pfz_res,
                "navigation_result": None,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": f"Could not locate destination fishing coordinates near {location}.",
                "synthesis_source": "rule-based",
            }

        geos = [_generate_coastal_geofence_coords(u_lat, u_lon)] if verdict == "CAUTION" else None
        nav_res = calculate_optimal_route(
            start_coords=[u_lat, u_lon],
            end_coords=[t_lat, t_lon],
            hazard_geofences=geos,
            start_label=pfz_res.get("location", location),
            end_label=t_name,
        )

        econ = nav_res["fuel_economy"]
        synthesis = (
            f"🧭 **Fuel-Optimal Waypoint Navigation Plan:** {location} ➔ **{t_name}**\n\n"
            f"- **Direct Track Distance:** {nav_res['total_distance_nm']:.1f} NM ({nav_res['total_distance_km']:.1f} km)\n"
            f"- **Optimal Compass Heading:** **{nav_res['direct_heading_str']}**\n"
            f"- **Estimated Cruising Duration:** ~{econ['transit_time_str']} (@ 9.0 knots)\n"
            f"- **Marine Fuel Economy:** Saves **{econ['fuel_saved_liters']:.1f} Liters** of diesel "
            f"(~₹{econ['cost_saved_inr']:,.0f}) versus unguided search cruising.\n"
            f"- **Geofence Clearance Check:** {nav_res['geofence_status']}"
        )

        return {
            "success": True,
            "intent": intent,
            "intent_result": intent_result,
            "agents_invoked": agents_invoked,
            "weather_result": weather_res,
            "pfz_result": pfz_res,
            "navigation_result": nav_res,
            "pfz_suppressed": False,
            "pfz_suppression_reason": None,
            "synthesis": synthesis,
            "synthesis_source": "navigation_synthesis",
        }

    # Case F: Future Capabilities Stubs (Satellite Oceanography)
    if intent == "ecosystem_query":
        return {
            "success": True,
            "intent": intent,
            "intent_result": intent_result,
            "agents_invoked": agents_invoked,
            "weather_result": None,
            "pfz_result": None,
            "navigation_result": None,
            "pfz_suppressed": False,
            "pfz_suppression_reason": None,
            "synthesis": _format_coming_soon_text(intent),
            "synthesis_source": "rule-based",
        }

    # Case G: Unknown / Unhandled queries
    return {
        "success": True,
        "intent": intent,
        "intent_result": intent_result,
        "agents_invoked": agents_invoked,
        "weather_result": None,
        "pfz_result": None,
        "navigation_result": None,
        "pfz_suppressed": False,
        "pfz_suppression_reason": None,
        "synthesis": (
            "🤔 I am not completely sure what you are asking. "
            "You can ask me about sea conditions, weather safety, fishing zones, or navigation routes "
            "(e.g., 'Is it safe to fish near Kochi?', 'Show PFZ zones near Rameswaram', or 'Plan route to fishing zone from Kochi')."
        ),
        "synthesis_source": "rule-based",
    }
