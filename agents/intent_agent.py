"""
agents/intent_agent.py — Intent Classification & Language Detection Agent

─────────────────────────────────────────────────────────────────────────────
RESPONSIBILITY
─────────────────────────────────────────────────────────────────────────────
This is the FIRST agent called for every user query. It answers two questions:
    1. WHAT does the user want?  → intent classification
    2. WHAT language are they using? → language detection

Both answers are derived in a single Gemini call, keeping latency low.

After this agent runs, the result is handed to the Orchestrator (Phase 4),
which decides which downstream agent(s) to invoke. For now (Phase 2),
app.py does the routing directly using the intent field.

─────────────────────────────────────────────────────────────────────────────
INTERFACE — uniform across all ORCA agents
─────────────────────────────────────────────────────────────────────────────
    run(inputs: dict) -> dict

INPUTS:
    "query"  (str, required): Raw user query exactly as typed

OUTPUTS (success=True):
    "success"         (bool): True
    "intent"          (str):  One of the INTENT_TYPES keys below
    "language"        (str):  Human-readable name, e.g. "Tamil", "Hindi"
    "language_code"   (str):  ISO 639-1 code, e.g. "ta", "hi", "en"
    "entities"        (dict): {
                                  "location":     str | None,
                                  "time_context": "today" | "tomorrow" | "3 days"
                              }
    "gemini_response" (str | None): Pre-written reply for casual_chat; None otherwise
    "raw_query"       (str):  The original query, unchanged

OUTPUTS (success=False):
    "success" (bool): False
    "error"   (str):  What went wrong
    + fallback values for all other keys so the caller never KeyErrors
"""

import json
import re
import difflib
import httpx
from langdetect import detect as langdetect_detect, LangDetectException

from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL

# ─────────────────────────────────────────────────────────────────────────────
# Gemini client — same pattern as weather_agent.py
# ─────────────────────────────────────────────────────────────────────────────
_GEMINI_TIMEOUT_S: int = 60

_gemini = None


def _get_gemini_client():
    """Lazily and safely instantiate or return the genai.Client."""
    global _gemini
    if _gemini is not None:
        return _gemini
    from config import get_gemini_api_key
    key = get_gemini_api_key()
    if key:
        try:
            _gemini = genai.Client(
                api_key=key,
                http_options={"timeout": _GEMINI_TIMEOUT_S},
            )
        except Exception:
            _gemini = None
    return _gemini


# Initialise on load if key is already available in secrets or env
if GEMINI_API_KEY:
    _get_gemini_client()



# ─────────────────────────────────────────────────────────────────────────────
# Intent taxonomy
# ─────────────────────────────────────────────────────────────────────────────
# Each key maps to a downstream agent (column "Agent" shows which Phase adds it).
# This dict is injected verbatim into the Gemini prompt so it understands
# the full vocabulary before classifying.

INTENT_TYPES: dict[str, str] = {
    "weather_check":   "General weather / sea / wave conditions for a location",
    "safety_check":    "Is it safe to go fishing or venture into the sea?",
    "pfz_location":    "Potential Fishing Zones (PFZ), fishing spots, where to find or catch fish, fishing grounds",
    "route_planning":  "Safe navigation route from one point to another",
    "alert_query":     "Cyclone, lightning, storm surge, or hazard warnings",
    "ecosystem_query": "Chlorophyll, SST, fish productivity, ecosystem health",
    "casual_chat":     "Greeting, thanks, general chitchat unrelated to marine data",
    "unknown":         "Intent cannot be determined from the query",
}

# ─────────────────────────────────────────────────────────────────────────────
# Language code → human-readable name mapping
# (Used in the fallback path when Gemini is unavailable)
# ─────────────────────────────────────────────────────────────────────────────
LANG_CODE_TO_NAME: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "or": "Odia",
    "ur": "Urdu",
}

# ─────────────────────────────────────────────────────────────────────────────
# Coastal location dictionary & stop-words for accurate entity extraction
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_COASTAL_LOCATIONS = [
    "kochi", "cochin", "chennai", "madras", "mumbai", "bombay", "visakhapatnam", "vizag",
    "rameswaram", "rameshwaram", "mangalore", "mangaluru", "goa", "panaji", "karwar",
    "veraval", "porbandar", "paradip", "paradeep", "puri", "digha", "haldia",
    "kannur", "kozhikode", "calicut", "alappuzha", "alleppey", "thiruvananthapuram", "trivandrum",
    "tuticorin", "thoothukudi", "kanyakumari", "nagapattinam", "cuddalore", "pondicherry", "puducherry",
    "machilipatnam", "kakinada", "bhavnagar", "surat", "ratnagiri", "malvan", "port blair",
    "andaman", "nicobar", "lakshadweep", "kavaratti", "ennore", "chilika", "sundarbans",
    "daman", "diu", "dwarka", "okha", "mandvi", "kandla", "mundra", "jafrabad", "alibag",
    "dapoli", "devgad", "bhatkal", "udupi", "malpe", "kasaragod", "kollam", "quilon",
    "vizhinjam", "varkala", "munambam", "ponnani", "beypore", "thalassery", "mahe",
    "karaikal", "pamban", "mandapam", "colachel", "nellore", "ongole", "bapatla",
    "narsapur", "bheemunipatnam", "gopalpur", "chandipur", "balasore", "bakkhali", "sagar island"
]

CANONICAL_LOCATION_NAMES = {
    "cochin": "Kochi",
    "madras": "Chennai",
    "bombay": "Mumbai",
    "vizag": "Visakhapatnam",
    "rameshwaram": "Rameswaram",
    "mangaluru": "Mangalore",
    "panaji": "Goa",
    "calicut": "Kozhikode",
    "alleppey": "Alappuzha",
    "trivandrum": "Thiruvananthapuram",
    "thoothukudi": "Tuticorin",
    "paradeep": "Paradip",
    "quilon": "Kollam",
}

NON_LOCATION_WORDS = {
    "what", "where", "when", "which", "how", "safe", "fishing", "sea", "near", "morning",
    "today", "tomorrow", "ocean", "weather", "wave", "condition", "the", "is", "it",
    "will", "tell", "show", "check", "about", "around", "does", "like", "conditions",
    "surge", "storm", "risk", "alert", "level", "analyze", "analysis", "sst",
    "chlorophyll", "anomaly", "concentration", "concentrations", "temperature",
    "temperatures", "ecosystem", "productivity", "marine", "satellite", "telemetry",
    "forecast", "data", "report", "status", "overview", "zone", "zones", "route",
    "planning", "transit", "navigation", "water", "waters", "assess", "examine",
    "evaluate", "monitor", "detect", "inspect", "explore", "view", "give", "find",
    "help", "please", "could", "would", "should", "off", "into", "onto", "from",
    "with", "have", "some", "good", "best", "very", "high", "much", "many",
    "indian", "india", "bay", "coast", "coastal", "waters", "port", "harbour", "harbor",
    "catch", "fish", "spot", "spots", "place", "places", "ground", "grounds", "area", "areas",
    "shoal", "shoals", "boat", "trawler", "vessel", "trip", "go", "going", "gone", "can",
    "may", "want", "neare", "ner", "neer", "naer", "clos", "close", "arround", "arund"
}

PREPOSITION_TYPO_PATTERN = re.compile(
    r'\b(?:neare?|ner|neer|naer|nre|near\s+to|close\s+to|clos\s+to|offf?|of|ar+ound|arund|round|inn?|att?|fro[m]?|frm|for|towards?|to)\s+([A-Za-z\-]+)\b',
    re.IGNORECASE
)


def _resolve_location_candidate(cand: str) -> str | None:
    """
    Resolve a candidate token to a known coastal location, handling canonical mapping
    and typo tolerance via difflib fuzzy matching.
    """
    if not cand:
        return None
    cand_clean = cand.strip("?,.!:;\"'").lower()
    if cand_clean in NON_LOCATION_WORDS or len(cand_clean) < 3:
        return None
    if cand_clean in KNOWN_COASTAL_LOCATIONS:
        return CANONICAL_LOCATION_NAMES.get(cand_clean, cand_clean.title())
    if cand_clean in CANONICAL_LOCATION_NAMES:
        return CANONICAL_LOCATION_NAMES[cand_clean]
    matches = difflib.get_close_matches(cand_clean, KNOWN_COASTAL_LOCATIONS, n=1, cutoff=0.70)
    if matches:
        matched = matches[0]
        return CANONICAL_LOCATION_NAMES.get(matched, matched.title())
    return None


def _extract_location_from_text(text: str) -> str | None:
    """
    Extract a valid coastal location from text using a 4-tier strategy with typo tolerance:
    1. Direct match against known Indian coastal ports and maritime regions.
    2. Preposition match with typo tolerance ('off Kochi', 'neare Kochi', 'ner Chennai', etc.).
    3. Fuzzy token scan resolving typos (e.g. 'kochii', 'chenai', 'rameswarm').
    4. Capitalized token scan excluding all non-location stop words.
    """
    if not text:
        return None

    lower_text = text.lower()

    # Tier 1: Exact match against known coastal ports/cities
    for loc in KNOWN_COASTAL_LOCATIONS:
        pattern = r'\b' + re.escape(loc) + r'\b'
        if re.search(pattern, lower_text):
            return CANONICAL_LOCATION_NAMES.get(loc, loc.title())

    # Tier 2: Preposition match with typo tolerance
    prep_match = PREPOSITION_TYPO_PATTERN.search(text)
    if prep_match:
        cand = prep_match.group(1).strip("?,.!:;\"'")
        resolved = _resolve_location_candidate(cand)
        if resolved:
            return resolved
        if cand.lower() not in NON_LOCATION_WORDS and len(cand) >= 3:
            return CANONICAL_LOCATION_NAMES.get(cand.lower(), cand.title())

    # Tier 3: Fuzzy token scan across all candidate words
    for word in text.split():
        clean = word.strip("?,.!:;\"'")
        resolved = _resolve_location_candidate(clean)
        if resolved:
            return resolved

    # Tier 4: Capitalized word search excluding stop words
    for word in text.split():
        clean = word.strip("?,.!:;\"'")
        if clean and clean[0].isupper() and len(clean) >= 3 and clean.lower() not in NON_LOCATION_WORDS:
            return CANONICAL_LOCATION_NAMES.get(clean.lower(), clean.title())

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(query: str) -> str:
    """
    Construct the Gemini prompt for intent + language + entity extraction.

    Design goals:
    - One API call covers all three tasks (language, intent, entities).
    - The intent vocabulary is injected so Gemini matches exactly our keys.
    - Gemini is asked to reply in the user's own language for casual_chat,
      making the platform feel native to non-English speakers.
    - Strict JSON-only output makes parsing reliable.
    """
    intent_descriptions = "\n".join(
        f'  "{k}": {v}' for k, v in INTENT_TYPES.items()
    )

    return f"""
You are the intent parser for ORCA, an AI marine intelligence platform
used by Indian fishermen and coastal authorities.

Analyze the user query below and return a single JSON object with these fields:

  "intent"          — one of the exact keys listed below
  "language"        — full language name (e.g. "Tamil", "Hindi", "English")
  "language_code"   — ISO 639-1 two-letter code (e.g. "ta", "hi", "en")
  "entities"        — object with:
      "location"    — place name extracted from the query, or null if none
      "time_context"— one of: "today", "tomorrow", "3 days"
                      (default to "today" if not mentioned)
  "gemini_response" — if intent is "casual_chat": write a warm, helpful
                      1–2 sentence reply IN THE SAME LANGUAGE as the query,
                      introducing yourself as ORCA, a marine assistant.
                      For all other intents: set this to null.

Intent options:
{intent_descriptions}

Rules:
- STRICT INTENT RULE: Queries containing "where can I fish", "fish near", "fishing zones", "where to fish", "find fish", or "catch fish" (e.g. "Where can I fish near Kochi today?") MUST ALWAYS be classified as "pfz_location". They must NEVER be classified as "casual_chat" or "chat".
- "casual_chat" is ONLY for greetings (hello, hi, good morning), thanks, or small talk completely unrelated to the sea, weather, fish, or marine navigation.
- "safety_check" and "weather_check" are similar; prefer "safety_check" when
  the user explicitly asks if it is "safe" or whether they "can go" somewhere (e.g. "is it safe to fish", "can I go out to sea"). If safety or danger is questioned, prefer "safety_check" even if fishing or weather is mentioned.
- "pfz_location": Potential Fishing Zones (PFZ), fishing spots, finding fish, catching fish, where to fish, best fishing grounds, or locating fish shoals (e.g. "find fish", "catch fish", "fishing spot", "where to fish", "good place to fish", "best fishing grounds").
- "ecosystem_query": questions about chlorophyll, SST (sea surface temperature), thermal anomalies, upwelling, primary productivity, satellite oceanography, or marine ecological health.
- Detect the language from the script and vocabulary, not from the place names.
- For location: extract the actual coastal town, port, city, island, or region (e.g. "Kochi", "Chennai", "Visakhapatnam", "Rameswaram", "Mumbai", "Veraval", "Mangalore").
  Pay special attention to phrasing like "off Kochi", "near Chennai", "neare Kochi", "ner Chennai", "off Veraval".
  Gracefully resolve common spelling typos in coastal locations (e.g. "kochii" -> "Kochi", "chenai" -> "Chennai", "rameswarm" -> "Rameswaram").
  CRITICAL: NEVER extract action verbs, inquiry terms, or oceanographic parameters as the location. Specifically, NEVER return "Analyze", "Analysis", "Check", "Assess", "Examine", "SST", "Chlorophyll", "Anomaly", "Productivity", "Temperature", "Ocean", "Sea", "Satellite", "Weather", "Conditions" as a location. If no coastal place name is mentioned, set "location" to null.
- Respond ONLY with valid JSON — no markdown fences, no extra text.

User query: "{query}"
"""


def _translate_to_english(text: str, lang_code: str) -> str:
    """
    Translate *text* to English using deep-translator's GoogleTranslator.

    Returns the original text unchanged if:
      - The language is already English ("en")
      - Translation fails for any reason (network error, quota, etc.)

    We deliberately swallow all errors here — the fallback parser is a
    last-resort path, so we prefer a degraded-but-working result over a crash.

    Args:
        text      (str): The raw user query.
        lang_code (str): ISO 639-1 code detected by langdetect, e.g. "hi".

    Returns:
        str: English translation, or the original text on failure.
    """
    if lang_code == "en":
        return text          # Nothing to do

    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="auto", target="en").translate(text)

        # Guard: Google Translate's free endpoint occasionally returns an HTML
        # error page (e.g. "Error 500") instead of translated text. Detect
        # these by checking for telltale substrings and fall back gracefully.
        if not translated or "Error" in translated[:30] or "<html" in translated.lower():
            return text

        return translated
    except Exception:
        return text          # Silent fallback to original


def _classify_intent_from_text(text: str) -> str:
    """
    Robust rule-based intent classification handling natural language phrasing and keywords.
    Used in fallback paths and when Gemini classification needs reinforcement.
    """
    if not text:
        return "unknown"
    q = text.lower()

    # 1. Alert / Disaster
    if any(w in q for w in ["cyclone", "surge", "hazard", "alert", "warning", "lightning", "flood", "disaster", "evacuat", "tsunami", "gale"]):
        return "alert_query"

    # 2. Safety Check (takes precedence over fishing if safety is mentioned)
    if any(w in q for w in ["safe", "ventur", "danger", "can i go", "should i go", "is it safe", "safety"]):
        return "safety_check"

    # 3. Route Planning
    if any(w in q for w in ["route", "navigate", "path", "direction", "reach", "transit", "waypoint", "bearing", "optimal route"]):
        return "route_planning"

    # 4. Ecosystem Query (SST, chlorophyll, etc.)
    if any(w in q for w in ["chlorophyll", "sst", "temperature anomaly", "ecosystem", "productivity", "upwelling", "ocm-3", "ocean colour", "ocean color"]):
        return "ecosystem_query"

    # 5. Potential Fishing Zone (PFZ) / Natural language fishing queries
    pfz_phrases = [
        "where can i fish", "where can we fish", "where to fish", "where do i fish", "where should i fish",
        "fish near", "fishing near", "fishing zone", "fishing zones", "fishing ground", "fishing grounds",
        "fishing spot", "fishing spots", "pfz", "find fish", "catch fish", "good place to fish",
        "best place to fish", "fish shoal", "fish shoals", "fish aggregation",
        "catch tuna", "find tuna", "catch sardine", "look for fish", "looking for fish"
    ]
    if any(p in q for p in pfz_phrases):
        return "pfz_location"
    if re.search(r'\bfish\s+(?:near|neare|ner|around|off|in|at)\b', q):
        return "pfz_location"
    if re.search(r'\b(?:find|catch|locate|hunt)\s+fish\b', q):
        return "pfz_location"
    if re.search(r'\bwhere\s+(?:can\s+i|to|do\s+we|should\s+i)\s+fish\b', q):
        return "pfz_location"
    if re.search(r'\bfishing\s+(?:spot|spots|zone|zones|ground|grounds|area|areas|place|places)\b', q):
        return "pfz_location"

    # 6. Weather Check
    if any(w in q for w in ["weather", "wave", "wind", "rain", "sea condition", "storm", "swell", "tide"]):
        return "weather_check"

    # 7. Casual Chat
    if any(w in q for w in ["hi", "hello", "hey", "thank", "good morning", "good evening", "who are you"]):
        return "casual_chat"

    return "unknown"


def _fallback_parse(query: str, error: str) -> dict:
    """
    Rule-based fallback used when Gemini is unavailable or returns bad JSON.

    Uses langdetect for language detection and simple keyword matching for
    intent. This ensures the app stays functional even without the LLM.
    """
    # --- Language detection via langdetect ---
    try:
        lang_code = langdetect_detect(query)
    except LangDetectException:
        lang_code = "en"

    lang_name = LANG_CODE_TO_NAME.get(lang_code, "English")

    # --- Translate to English if needed ---
    # All keyword matching and location extraction below runs on English text.
    # This is the fix for queries like "कोची के पास मौसम कैसा है?" returning
    # intent=unknown because the keywords ("weather", "near", etc.) only exist
    # in the translated version, not in the original Devanagari/Tamil/etc. text.
    translated = _translate_to_english(query, lang_code)

    # Work on the translated (or original if already English) lowercased text
    q = translated.lower()

    # --- Rule-based intent classification ---
    intent = _classify_intent_from_text(translated)
    if intent == "unknown":
        intent = _classify_intent_from_text(query)

    # --- Location extraction — run on the TRANSLATED text (and original query) ---
    location = _extract_location_from_text(translated) or _extract_location_from_text(query)

    # --- Time context — also from translated text ---
    if "tomorrow" in q:
        time_ctx = "tomorrow"
    elif any(p in q for p in ["3 day", "three day", "next few"]):
        time_ctx = "3 days"
    else:
        time_ctx = "today"

    greeting = None
    if intent == "casual_chat":
        greeting = ("Hello! I'm ORCA, your marine intelligence assistant. "
                    "Ask me about sea conditions, fishing zones, or weather safety.")

    return {
        "success":         False,   # Marks that this is the fallback path
        "error":           f"Gemini unavailable ({error}), using rule-based fallback.",
        "intent":          intent,
        "language":        lang_name,
        "language_code":   lang_code,
        "entities":        {"location": location, "time_context": time_ctx},
        "gemini_response": greeting,
        "raw_query":       query,
        "original_text":   query,       # Preserved for output rendering
        "translated_text": translated,  # English version used by downstream agents
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(inputs: dict) -> dict:
    """
    Execute the Intent & Language Detection Agent.

    Step-by-step:
        1. Validate that "query" is present in inputs
        2. Build a structured Gemini prompt
        3. Call Gemini — one call covers language + intent + entities + greeting
        4. Parse and validate the JSON response
        5. Return a clean, typed output dict
        6. On any failure, fall back to rule-based parsing so the app never crashes

    Args:
        inputs (dict): Must contain "query" (str).

    Returns:
        dict: See module docstring for full schema.
    """

    query = inputs.get("query", "").strip()
    if not query:
        return {
            "success":         False,
            "error":           "No query provided.",
            "intent":          "unknown",
            "language":        "English",
            "language_code":   "en",
            "entities":        {"location": None, "time_context": "today"},
            "gemini_response": None,
            "raw_query":       query,
            "original_text":   query,
            "translated_text": query,
        }

    # ── Step 1: Ask Gemini ────────────────────────────────────────────────────
    prompt = _build_prompt(query)

    client = _get_gemini_client()
    if not client:
        return _fallback_parse(query, "GEMINI_API_KEY not configured or client unavailable")

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"http_options": {"timeout": _GEMINI_TIMEOUT_S}},
        )

        # Strip any accidental markdown fences before parsing
        raw_text   = response.text.strip()
        clean_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed     = json.loads(clean_text)

    except (TimeoutError, httpx.TimeoutException):
        return _fallback_parse(query, "Gemini timed out")
    except (json.JSONDecodeError, ValueError) as e:
        return _fallback_parse(query, f"Bad JSON from Gemini: {e}")
    except Exception as e:
        return _fallback_parse(query, str(e))

    # ── Step 2: Validate and normalise the parsed response ────────────────────

    INTENT_ALIASES = {
        "fishing_zone": "pfz_location",
        "fishing_zones": "pfz_location",
        "pfz": "pfz_location",
        "chat": "casual_chat",
        "greeting": "casual_chat",
        "weather": "weather_check",
        "safety": "safety_check",
        "alert": "alert_query",
        "hazard": "alert_query",
        "ecosystem": "ecosystem_query",
        "route": "route_planning",
        "navigation": "route_planning",
    }

    raw_intent = parsed.get("intent", "unknown")
    intent = INTENT_ALIASES.get(raw_intent, raw_intent)
    if intent not in INTENT_TYPES:
        intent = "unknown"

    # ── Strict Enforcement for Fishing & Marine Queries ──────────────────────
    # Queries containing "where can I fish", "fish near", or "fishing zones" must strictly
    # route to pfz_location (unless safety/danger is explicitly questioned).
    q_lower = query.lower()
    is_safety_or_hazard = any(w in q_lower for w in ["safe", "danger", "cyclone", "surge", "hazard", "warning", "can i go", "should i go"])

    strict_pfz_triggers = [
        "where can i fish", "where can we fish", "where to fish", "where do i fish", "where should i fish",
        "fish near", "fishing near", "fishing zone", "fishing zones", "fishing ground", "fishing grounds",
        "fishing spot", "fishing spots", "find fish", "catch fish", "good place to fish",
    ]
    if not is_safety_or_hazard and (
        any(t in q_lower for t in strict_pfz_triggers)
        or re.search(r'\bfish\s+(?:near|neare|ner|around|off|in|at)\b', q_lower)
    ):
        intent = "pfz_location"

    # If Gemini returned unknown or casual_chat for a query containing marine data, reinforce with rule-based classifier
    if intent in ("unknown", "casual_chat"):
        rule_intent = _classify_intent_from_text(query)
        if rule_intent != "unknown" and rule_intent != "casual_chat":
            intent = rule_intent

    # Ensure entities sub-dict is well-formed
    raw_entities   = parsed.get("entities", {})
    raw_location   = raw_entities.get("location")
    raw_time       = raw_entities.get("time_context", "today")
    time_context   = raw_time if raw_time in ("today", "tomorrow", "3 days") else "today"

    location = None
    if raw_location and isinstance(raw_location, str):
        # Resolve extracted candidate directly (handles typos and canonical mapping)
        resolved_direct = _resolve_location_candidate(raw_location)
        if resolved_direct:
            location = resolved_direct
        else:
            clean_cand = re.sub(r'^(?:off|near|around|in|at|from|to|for)\s+', '', raw_location.strip(), flags=re.IGNORECASE)
            resolved_clean = _resolve_location_candidate(clean_cand)
            if resolved_clean:
                location = resolved_clean
            elif clean_cand.lower() not in NON_LOCATION_WORDS and clean_cand.lower() not in ("none", "null", "n/a", "unknown"):
                location = CANONICAL_LOCATION_NAMES.get(clean_cand.lower(), clean_cand.title())

    # Fallback/refinement: If Gemini failed to extract a valid location or extracted an invalid word,
    # use our rule-based coastal extractor to recover it directly from the query.
    if not location:
        location = _extract_location_from_text(query)

    # Ensure language fields are present
    language       = parsed.get("language", "English")
    language_code  = parsed.get("language_code", "en")

    # gemini_response is only meaningful for casual_chat
    gemini_response = parsed.get("gemini_response") if intent == "casual_chat" else None

    # ── Step 3: Return structured output ──────────────────────────────────────
    # For the Gemini path: Gemini understands the source language natively, so
    # the location it extracts is already in English (e.g. "Kochi" not "കൊച്ചി").
    # We still include original_text / translated_text for schema consistency —
    # downstream agents and app.py can rely on both keys existing in all paths.
    return {
        "success":         True,
        "intent":          intent,
        "language":        language,
        "language_code":   language_code,
        "entities":        {"location": location, "time_context": time_context},
        "gemini_response": gemini_response,
        "raw_query":       query,
        "original_text":   query,   # User's original text in their language
        "translated_text": query,   # Gemini handles NLP natively; no translation needed
    }
