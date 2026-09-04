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
    "pfz_location":    "Where are today's Potential Fishing Zones (PFZ)?",
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
- "safety_check" and "weather_check" are similar; prefer "safety_check" when
  the user explicitly asks if it is "safe" or whether they "can go" somewhere.
- Detect the language from the script and vocabulary, not from the place names.
- For location: extract the most specific geographic entity mentioned.
  If the user says "near Kochi" extract "Kochi". If none, use null.
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

    # --- Keyword intent classification (English keywords only, safe now) ---
    if any(w in q for w in ["cyclone", "surge", "hazard", "alert", "warning", "lightning", "flood", "disaster", "evacuat"]):
        intent = "alert_query"
    elif any(w in q for w in ["safe", "ventur", "danger", "can i go", "should i go"]):
        intent = "safety_check"
    elif any(w in q for w in ["weather", "wave", "wind", "rain", "sea condition", "storm"]):
        intent = "weather_check"
    elif any(w in q for w in ["fishing zone", "pfz", "where to fish", "catch fish"]):
        intent = "pfz_location"
    elif any(w in q for w in ["route", "navigate", "path", "direction", "reach"]):
        intent = "route_planning"
    elif any(w in q for w in ["chlorophyll", "sst", "temperature", "ecosystem", "productivity"]):
        intent = "ecosystem_query"
    elif any(w in q for w in ["hi", "hello", "hey", "thank", "good morning", "good evening"]):
        intent = "casual_chat"
    else:
        intent = "unknown"

    # --- Location extraction — run on the TRANSLATED text ---
    # After translation, place names appear in English (e.g. "Kochi", "Chennai")
    # which the capitalised-word heuristic can detect reliably.
    location = None
    skip = {"what", "where", "when", "safe", "fishing", "sea", "near", "morning",
            "today", "tomorrow", "ocean", "weather", "wave", "condition", "the",
            "is", "it", "will", "tell", "show", "check", "about", "around",
            "does", "like", "how", "conditions", "surge", "storm", "risk", "alert", "level"}
    for word in translated.split():
        clean = word.strip("?,.")
        if clean and clean[0].isupper() and len(clean) > 3 and clean.lower() not in skip:
            location = clean
            break

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

    # Ensure intent is one of our known types
    intent = parsed.get("intent", "unknown")
    if intent not in INTENT_TYPES:
        intent = "unknown"

    # Ensure entities sub-dict is well-formed
    raw_entities   = parsed.get("entities", {})
    location       = raw_entities.get("location")       or None
    raw_time       = raw_entities.get("time_context", "today")
    time_context   = raw_time if raw_time in ("today", "tomorrow", "3 days") else "today"

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
