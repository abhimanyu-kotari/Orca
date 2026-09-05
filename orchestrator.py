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

from config import GEMINI_API_KEY, GEMINI_MODEL
from agents.intent_agent import run as intent_agent_run, LANG_CODE_TO_NAME
from agents.weather_agent import run as weather_agent_run
from agents.pfz_agent import run as pfz_agent_run
from agents.hazard_agent import run as hazard_agent_run
from tools.navigation_tools import calculate_optimal_route
from tools.map_tools import _generate_coastal_geofence_coords
from tools.eo_tools import generate_eo_grid
from tools.weather_tools import get_coordinates

_GEMINI_TIMEOUT_S = 30
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
            from google import genai
            _gemini = genai.Client(
                api_key=key,
                http_options={"timeout": _GEMINI_TIMEOUT_S},
            )
        except Exception:
            _gemini = None
    return _gemini


_LOCALIZE_CACHE: dict[tuple[str, str], str] = {}

_KNOWN_SYSTEM_TRANSLATIONS: dict[str, dict[str, str]] = {
    "🤔 I am not completely sure what you are asking. You can ask me about sea conditions, weather safety, fishing zones, or navigation routes (e.g., 'Is it safe to fish near Kochi?', 'Show PFZ zones near Rameswaram', or 'Plan route to fishing zone from Kochi').": {
        "kn": "🤔 ನೀವು ಏನು ಕೇಳುತ್ತಿದ್ದೀರಿ ಎಂದು ನನಗೆ ಸಂಪೂರ್ಣವಾಗಿ ಖಚಿತವಾಗಿಲ್ಲ. ಸಮುದ್ರ ಪರಿಸ್ಥಿತಿಗಳು, ಹವಾಮಾನ ಸುರಕ್ಷತೆ, ಮೀನುಗಾರಿಕೆ ವಲಯಗಳು ಅಥವಾ ನ್ಯಾವಿಗೇಷನ್ ಮಾರ್ಗಗಳ ಬಗ್ಗೆ ನೀವು ನನ್ನನ್ನು ಕೇಳಬಹುದು (ಉದಾ., 'ಕೊಚ್ಚಿ ಬಳಿ ಮೀನುಗಾರಿಕೆ ಸುರಕ್ಷಿತವೇ?', 'ರಾಮೇಶ್ವರಂ ಬಳಿ PFZ ವಲಯಗಳನ್ನು ತೋರಿಸಿ' ಅಥವಾ 'ಕೊಚ್ಚಿಯಿಂದ ಮೀನುಗಾರಿಕೆ ವಲಯಕ್ಕೆ ಮಾರ್ಗವನ್ನು ಯೋಜಿಸಿ').",
        "hi": "🤔 मुझे पूरी तरह से यकीन नहीं है कि आप क्या पूछ रहे हैं। आप मुझसे समुद्र की स्थिति, मौसम सुरक्षा, मछली पकड़ने के क्षेत्र या नेविगेशन मार्गों के बारे में पूछ सकते हैं (उदा., 'क्या कोच्चि के पास मछली पकड़ना सुरक्षित है?', 'रामेश्वरम के पास PFZ क्षेत्र दिखाएं', या 'कोच्चि से मछली पकड़ने के क्षेत्र के लिए मार्ग बनाएं')।",
        "ta": "🤔 நீங்கள் என்ன கேட்கிறீர்கள் என்று எனக்கு உறுதியாக தெரியவில்லை. கடல் நிலைமைகள், வானிலை பாதுகாப்பு, மீன்பிடி மண்டலங்கள் அல்லது வழிசெலுத்தல் பாதைகள் பற்றி என்னிடம் கேட்கலாம் (எ.கா., 'கொச்சி அருகே மீன்பிடிப்பது பாதுகாப்பானதா?', 'ராமேஸ்வரம் அருகே PFZ மண்டலங்களைக் காட்டு' அல்லது 'கொச்சியிலிருந்து மீன்பிடி மண்டலத்திற்கு பாதை திட்டமிடு').",
        "te": "🤔 మీరు ఏమి అడుగుతున్నారో నాకు పూర్తిగా స్పష్టంగా లేదు. సముద్ర పరిస్థితులు, వాతావరణ భద్రత, చేపల వేట మండలాలు లేదా నావిగేషన్ మార్గాల గురించి మీరు నన్ను అడగవచ్చు (ఉదా., 'కొచ్చి సమీపంలో చేపల వేట సురక్షితమేనా?', 'రామేశ్వరం సమీపంలో PFZ మండలాలను చూపించు', లేదా 'కొచ్చి నుండి చేపల వేట మండలానికి మార్గాన్ని ప్లాన్ చేయి').",
        "ml": "🤔 നിങ്ങൾ എന്താണ് ചോദിക്കുന്നതെന്ന് എനിക്ക് പൂർണ്ണമായി വ്യക്തമല്ല. സമുദ്രാവസ്ഥ, കാലാവസ്ഥാ സുരക്ഷ, മത്സ്യബന്ധന മേഖലകൾ, അല്ലെങ്കിൽ നാവിഗേഷൻ റൂട്ടുകൾ എന്നിവയെക്കുറിച്ച് നിങ്ങൾക്ക് എന്നോട് ചോദിക്കാം (ഉദാ., 'കൊച്ചിക്ക് സമീപം മത്സ്യബന്ധനം സുരക്ഷിതമാണോ?', 'രാമേശ്വരത്തിന് സമീപമുള്ള PFZ മേഖലകൾ കാണിക്കുക', അല്ലെങ്കിൽ 'കൊച്ചിയിൽ നിന്ന് മത്സ്യബന്ധന മേഖലയിലേക്കുള്ള റൂട്ട് ആസൂത്രണം ചെയ്യുക').",
        "bn": "🤔 আপনি কী জানতে চাইছেন তা আমি পুরোপুরি নিশ্চিত নই। আপনি আমাকে সমুদ্রের অবস্থা, আবহাওয়া সুরক্ষা, মাছ ধরার অঞ্চল বা নেভিগেশন রুট সম্পর্কে জিজ্ঞাসা করতে পারেন (যেমন, 'কোচির কাছে কি মাছ ধরা নিরাপদ?', 'রামেশ্বরমের কাছে PFZ অঞ্চলগুলি দেখান', বা 'কোচি থেকে মাছ ধরার অঞ্চলের রুট পরিকল্পনা করুন')।",
        "mr": "🤔 आपण नक्की काय विचारत आहात याबद्दल मला खात्री नाही. आपण मला समुद्राची स्थिती, हवामान सुरक्षा, मासेमारी क्षेत्रे किंवा नेव्हिगेशन मार्गांबद्दल विचारू शकता (उदा., 'कोचीजवळ मासेमारी करणे सुरक्षित आहे का?', 'रामेश्वरमजवळ PFZ क्षेत्रे दाखवा', किंवा 'कोचीवरून मासेमारी क्षेत्रासाठी मार्ग आखा').",
        "gu": "🤔 તમે શું પૂછી રહ્યા છો તેની મને સંપૂર્ણ ખાતરી નથી. તમે મને દરિયાઈ સ્થિતિ, હવામાન સુરક્ષા, માછીમારી ઝોન અથવા નેવિગેશન રૂટ વિશે પૂછી શકો છો (દા.ત., 'શું કોચી નજીક માછીમારી કરવી સલામત છે?', 'રામેશ્વરમ નજીક PFZ ઝોન બતાવો', અથવા 'કોચીથી માછીમારી ઝોનનો રૂટ પ્લાન કરો').",
    },
    "Please enter a question or coastal location to get started.": {
        "kn": "ಪ್ರಾರಂಭಿಸಲು ದಯವಿಟ್ಟು ಒಂದು ಪ್ರಶ್ನೆ ಅಥವಾ ಕರಾವಳಿ ಸ್ಥಳವನ್ನು ನಮೂದಿಸಿ.",
        "hi": "आरंभ करने के लिए कृपया कोई प्रश्न या तटीय स्थान दर्ज करें।",
        "ta": "தொடங்குவதற்கு ஒரு கேள்வி அல்லது கடலோர இருப்பிடத்தை உள்ளிடவும்.",
        "te": "ప్రారంభించడానికి దయచేసి ఒక ప్రశ్న లేదా తీరప్రాంతాన్ని నమోదు చేయండి.",
        "ml": "ആരംഭിക്കാൻ ദയവായി ഒരു ചോദ്യമോ തീരദേശ ലൊക്കേഷനോ നൽകുക.",
        "bn": "শুরু করতে অনুগ্রহ করে একটি প্রশ্ন বা উপকূলীয় অবস্থান লিখুন।",
        "mr": "सुरू करण्यासाठी कृपया एखादा प्रश्न किंवा किनारपट्टीचे स्थान प्रविष्ट करा.",
        "gu": "શરૂ કરવા માટે કૃપા કરીને કોઈ પ્રશ્ન અથવા દરિયાકાંઠાનું સ્થળ દાખલ કરો.",
    },
    "📍 Which coastal area are you planning to fish near? Please mention a coastal town or port, such as 'Where to fish near Kochi?'.": {
        "kn": "📍 ನೀವು ಯಾವ ಕರಾವಳಿ ಪ್ರದೇಶದ ಬಳಿ ಮೀನುಗಾರಿಕೆ ಮಾಡಲು ಯೋಜಿಸುತ್ತಿದ್ದೀರಿ? ದಯವಿಟ್ಟು ಕೊಚ್ಚಿ ಬಳಿ ಎಲ್ಲಿ ಮೀನುಗಾರಿಕೆ ಮಾಡಬೇಕು ಎಂಬಂತಹ ಕರಾವಳಿ ಪಟ್ಟಣ ಅಥವಾ ಬಂದರನ್ನು ನಮೂದಿಸಿ.",
        "hi": "📍 आप किस तटीय क्षेत्र के पास मछली पकड़ने की योजना बना रहे हैं? कृपया किसी तटीय शहर या बंदरगाह का उल्लेख करें, जैसे 'कोच्चि के पास कहाँ मछली पकड़ें?'।",
        "ta": "📍 எந்த கடலோரப் பகுதியில் மீன்பிடிக்க திட்டமிட்டுள்ளீர்கள்? 'கொச்சி அருகே எங்கே மீன்பிடிப்பது?' என்பது போல கடலோர நகரம் அல்லது துறைமுகத்தைக் குறிப்பிடவும்.",
        "te": "📍 మీరు ఏ తీరప్రాంతంలో చేపల వేటకు వెళ్లాలని ప్లాన్ చేస్తున్నారు? 'కొచ్చి సమీపంలో ఎక్కడ చేపల వేట చేయాలి?' వంటి తీరప్రాంత పట్టణం లేదా ఓడరేవును పేర్కొనండి.",
        "ml": "📍 ഏത് തീരദേശത്തിന് സമീപമാണ് നിങ്ങൾ മത്സ്യബന്ധനത്തിന് പദ്ധതിയിടുന്നത്? 'കൊച്ചിക്ക് സമീപം എവിടെ മത്സ്യബന്ധനം നടത്തണം?' എന്നത് പോലെ ഒരു തീരദേശ നഗരമോ തുറമുഖമോ വ്യക്തമാക്കുക.",
        "bn": "📍 আপনি কোন উপকূলীয় অঞ্চলের কাছে মাছ ধরার পরিকল্পনা করছেন? অনুগ্রহ করে একটি উপকূলীয় শহর বা বন্দরের নাম উল্লেখ করুন, যেমন 'কোচির কাছে কোথায় মাছ ধরবেন?'।",
        "mr": "📍 आपण कोणत्या किनारपट्टी भागात मासेमारी करण्याचे नियोजन करत आहात? कृपया एखाद्या किनारपट्टी शहराचा किंवा बंदराचा उल्लेख करा, जसे की 'कोचीजवळ कुठे मासेमारी करावी?'",
        "gu": "📍 તમે કયા દરિયાકાંઠાના વિસ્તાર નજીક માછીમારી કરવાનું આયોજન કરી રહ્યા છો? કૃપા કરીને કોઈ દરિયાકાંઠાના શહેર અથવા બંદરનો ઉલ્લેખ કરો, જેમ કે 'કોચી નજીક ક્યાં માછીમારી કરવી?'.",
    },
    "📍 I couldn't determine a coastal location from your query. Please specify a port or coastal city (e.g., 'Is it safe near Rameswaram tomorrow?').": {
        "kn": "📍 ನಿಮ್ಮ ಪ್ರಶ್ನೆಯಿಂದ ಕರಾವಳಿ ಸ್ಥಳವನ್ನು ನಿರ್ಧರಿಸಲು ನನಗೆ ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಬಂದರು ಅಥವಾ ಕರಾವಳಿ ನಗರವನ್ನು ನಿರ್ದಿಷ್ಟಪಡಿಸಿ (ಉದಾ., 'ನಾಳೆ ರಾಮೇಶ್ವರಂ ಬಳಿ ಸುರಕ್ಷಿತವೇ?').",
        "hi": "📍 मैं आपके प्रश्न से तटीय स्थान का पता नहीं लगा सका। कृपया किसी बंदरगाह या तटीय शहर का उल्लेख करें (उदा., 'क्या कल रामेश्वरम के पास मौसम सुरक्षित है?')।",
        "ta": "📍 உங்கள் வினவலில் இருந்து கடலோர இருப்பிடத்தைக் கண்டறிய முடியவில்லை. தயவுசெய்து ஒரு துறைமுகம் அல்லது கடலோர நகரத்தைக் குறிப்பிடவும் (எ.கா., 'நாளை ராமேஸ்வரம் அருகே பாதுகாப்பானதா?').",
        "te": "📍 మీ ప్రశ్న నుండి తీరప్రాంతాన్ని గుర్తించలేకపోయాను. దయచేసి ఓడరేవు లేదా తీరప్రాంత నగరాన్ని పేర్కొనండి (ఉదా., 'రేపు రామేశ్వరం సమీపంలో సురక్షితమేనా?').",
        "ml": "📍 നിങ്ങളുടെ ചോദ്യത്തിൽ നിന്ന് തീരദേശ ലൊക്കേഷൻ കണ്ടെത്താനായില്ല. ദയവായി ഒരു തുറമുഖമോ തീരദേശ നഗരമോ വ്യക്തമാക്കുക (ഉദാ., 'നാളെ രാമേശ്വരത്തിന് സമീപം സുരക്ഷിതമാണോ?').",
        "bn": "📍 আপনার অনুসন্ধান থেকে আমি কোনও উপকূলীয় অবস্থান নির্ধারণ করতে পারিনি। অনুগ্রহ করে একটি বন্দর বা উপকূলীয় শহর উল্লেখ করুন (যেমন, 'আগামীকাল রামেশ্বরমের কাছে কি নিরাপদ?')।",
        "mr": "📍 आपल्या प्रश्नावरून मला किनारपट्टीचे स्थान शोधता आले नाही. कृपया एखाद्या बंदराचा किंवा किनारपट्टी शहराचा उल्लेख करा (उदा., 'उद्या रामेश्वरमजवळ सुरक्षित आहे का?').",
        "gu": "📍 હું તમારી પૂછપરછ પરથી દરિયાકાંઠાનું સ્થળ નક્કી કરી શક્યો નથી. કૃપા કરીને કોઈ બંદર અથવા દરિયાકાંઠાના શહેરનો ઉલ્લેખ કરો (દા.ત., 'શું આવતીકાલે રામેશ્વરમ નજીક સલામત છે?').",
    }
}



def _localize_synthesis(text: str, language: str, language_code: str) -> str:
    """
    Localize/translate synthesis text into the target language.
    Preserves markdown formatting, numbers, coordinates, and emojis.
    Uses caching and fast-fallback to deep-translator if Gemini is slow or unavailable.
    """
    if not text or not language_code or language_code == "en":
        return text

    cache_key = (text.strip(), language_code.strip().lower())
    if cache_key in _LOCALIZE_CACHE:
        return _LOCALIZE_CACHE[cache_key]

    clean_input = text.replace("Gemini connection timed out (SSL handshake or read >60 s). Showing rule-based result: ", "")
    clean_input = clean_input.replace("Gemini connection timed out (SSL handshake or read >60 s). ", "").strip()

    # Check pre-translated system messages first (0ms instant native translation)
    for en_key, trans_map in _KNOWN_SYSTEM_TRANSLATIONS.items():
        if en_key in clean_input or clean_input in en_key or en_key.strip() == clean_input:
            if language_code in trans_map:
                res_sys = trans_map[language_code]
                _LOCALIZE_CACHE[cache_key] = res_sys
                return res_sys

    # Attempt 1: Fast Gemini translation (max 4s timeout)
    client = _get_gemini_client()
    if client:
        try:
            prompt = (
                f"You are the multilingual translator for ORCA, an Indian marine decision intelligence platform.\n"
                f"Translate the following marine advisory from English to {language} ({language_code}).\n"
                f"CRITICAL REQUIREMENTS:\n"
                f"1. Preserve ALL Markdown formatting (bold **text**, headers #, bullet points -, line breaks).\n"
                f"2. Keep all place names (e.g., Kochi, Chennai, Rameswaram), nautical coordinates, numbers, units (km, NM, m, km/h, knots, °C, mg/m³, J/kg), and emojis intact.\n"
                f"3. Use natural, clear marine phrasing suitable for coastal fishermen and maritime authorities.\n"
                f"4. Output ONLY the translated markdown text without code fences or additional commentary.\n\n"
                f"Text to translate:\n{clean_input}"
            )
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"http_options": {"timeout": 4}},
            )
            if resp and resp.text:
                clean = resp.text.strip().removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
                if clean and len(clean) > 5 and not clean.startswith("<"):
                    _LOCALIZE_CACHE[cache_key] = clean
                    return clean
        except Exception:
            pass  # Fast fall through to deep-translator

    # Attempt 2: deep-translator (fast, dedicated translation endpoint)
    try:
        from deep_translator import GoogleTranslator
        if len(clean_input) < 4500:
            translated = GoogleTranslator(source="auto", target=language_code).translate(clean_input)
            if not translated or "Error" in translated[:30] or "<html" in translated.lower():
                translated = GoogleTranslator(source="en", target=language_code).translate(clean_input)
            if translated and "Error" not in translated[:30] and "<html" not in translated.lower():
                _LOCALIZE_CACHE[cache_key] = translated
                return translated
        else:
            paragraphs = clean_input.split("\n\n")
            translated_paras = []
            for p in paragraphs:
                if p.strip():
                    tp = GoogleTranslator(source="auto", target=language_code).translate(p)
                    if not tp or "<html" in tp.lower():
                        tp = GoogleTranslator(source="en", target=language_code).translate(p)
                    translated_paras.append(tp if tp else p)
                else:
                    translated_paras.append("")
            res_p = "\n\n".join(translated_paras)
            _LOCALIZE_CACHE[cache_key] = res_p
            return res_p
    except Exception:
        pass

    return clean_input


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

def _execute_orchestration(inputs: dict) -> dict:
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
            "eo_result": None,
            "pfz_suppressed": False,
            "pfz_suppression_reason": None,
            "synthesis": "Please enter a question or coastal location to get started.",
            "synthesis_source": "rule-based",
        }

    # ── Step 1: Intent & Language Analysis ───────────────────────────────────
    forced_lang_code = inputs.get("language_code")
    intent_payload = {"query": query}
    if forced_lang_code and forced_lang_code != "auto":
        intent_payload["language_code"] = forced_lang_code
        intent_payload["language"] = inputs.get("language")

    intent_result = intent_agent_run(intent_payload)
    agents_invoked = ["intent_agent"]

    if forced_lang_code and forced_lang_code != "auto":
        intent_result["language_code"] = forced_lang_code
        intent_result["language"] = inputs.get("language") or LANG_CODE_TO_NAME.get(forced_lang_code, intent_result.get("language", "English"))

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
            "eo_result": None,
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
                "eo_result": None,
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
            "eo_result": None,
            "pfz_suppressed": False,
            "pfz_suppression_reason": None,
            "synthesis": synthesis,
            "synthesis_source": "weather_agent",
        }

    # Case C: Potential Fishing Zone (PFZ) Location with Safety Cross-Referencing
    if intent in ("pfz_location", "fishing_zone"):
        if not location:
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": None,
                "pfz_result": None,
                "navigation_result": None,
                "eo_result": None,
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

        # Check if location resolution failed for both agents (e.g. geocoding failed or not in Indian coastal regions)
        if not weather_res.get("success") and not pfz_res.get("success"):
            err_msg = (
                pfz_res.get("error")
                or weather_res.get("error")
                or f"Location not found in Indian coastal regions. Please check the spelling (e.g., Kundapura)."
            )
            return {
                "success": False,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": pfz_res,
                "navigation_result": None,
                "eo_result": None,
                "navigation_suspended": False,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": f"📍 {err_msg}",
                "synthesis_source": "rule-based",
            }

        verdict = weather_res.get("verdict", "SAFE") if weather_res.get("success") else "SAFE"

        # ── Cross-Reference & Safety Override ────────────────────────────────
        if verdict == "DANGER":
            best_zone = (pfz_res.get("best_zone") or {}) if pfz_res.get("success") else {}
            best_name = best_zone.get("name", "identified zone")

            # Calculate planning route with hazard avoidance geofence
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
                f"🚨 **DANGER Alert for {location}:** Severe weather or high sea state detected.\n\n"
                f"{weather_res.get('summary', '')}\n\n"
                f"⚠️ **Navigation Suspended: Sea state / Lightning hazard active. "
                f"Showing direct displacement metrics for planning purposes only once weather clears.**\n\n"
                f"🐟 **Identified Hotspot (Pre-Voyage Planning):** **{best_name}**.\n\n"
                f"{pfz_res.get('advisory', '') if pfz_res.get('success') else ''}"
            )
            if nav_res and nav_res.get("imbl_warning_active"):
                synthesis += (
                    f"\n\n🛑 **IMBL PROXIMITY WARNING:** Navigation track passes within "
                    f"**{nav_res['imbl_min_distance_nm']:.1f} NM** of **{nav_res['imbl_closest_boundary']}** international border. "
                    f"High risk of impoundment — maintain minimum 5 NM clearance!"
                )

            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": pfz_res if pfz_res.get("success") else None,
                "navigation_result": nav_res,
                "eo_result": None,
                "navigation_suspended": True,
                "pfz_suppressed": False,
                "pfz_suppression_reason": (
                    "⚠️ Navigation Suspended: Sea state / Lightning hazard active. "
                    "Showing direct displacement metrics for planning purposes only once weather clears."
                ),
                "synthesis": synthesis,
                "synthesis_source": "orchestrator_danger_planning",
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
                f"🐟 **PFZ Available with Caution:** Nearest hotspot is **{best_name}**.\n\n"
                f"{pfz_res.get('advisory', '') if pfz_res.get('success') else ''}"
            )
            if nav_res and nav_res.get("imbl_warning_active"):
                synthesis += (
                    f"\n\n🛑 **IMBL PROXIMITY WARNING:** Navigation track passes within "
                    f"**{nav_res['imbl_min_distance_nm']:.1f} NM** of **{nav_res['imbl_closest_boundary']}** international border. "
                    f"High risk of impoundment — maintain minimum 5 NM clearance!"
                )

            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": pfz_res if pfz_res.get("success") else None,
                "navigation_result": nav_res,
                "eo_result": None,
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
                f"🐟 **Top Recommended Fishing Zone:** **{best_name}**.\n\n"
                f"{pfz_res.get('advisory', '') if pfz_res.get('success') else ''}"
            )
            if nav_res and nav_res.get("imbl_warning_active"):
                synthesis += (
                    f"\n\n🛑 **IMBL PROXIMITY WARNING:** Navigation track passes within "
                    f"**{nav_res['imbl_min_distance_nm']:.1f} NM** of **{nav_res['imbl_closest_boundary']}** international border. "
                    f"High risk of impoundment — maintain minimum 5 NM clearance!"
                )
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": pfz_res if pfz_res.get("success") else None,
                "navigation_result": nav_res,
                "eo_result": None,
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
                "eo_result": None,
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
            "eo_result": None,
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
                "eo_result": None,
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
        is_danger = (verdict == "DANGER")

        u_lat = pfz_res.get("lat") if pfz_res.get("success") else None
        u_lon = pfz_res.get("lon") if pfz_res.get("success") else None
        t_lat, t_lon, t_name = _extract_target_coords(pfz_res) if pfz_res.get("success") else (None, None, "Target PFZ")

        if u_lat is None or u_lon is None or t_lat is None or t_lon is None:
            err_msg = (
                (pfz_res.get("error") if pfz_res else None)
                or (weather_res.get("error") if weather_res else None)
                or f"Could not locate destination fishing coordinates near {location}."
            )
            return {
                "success": False,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": pfz_res,
                "navigation_result": None,
                "eo_result": None,
                "navigation_suspended": is_danger,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": f"📍 {err_msg}",
                "synthesis_source": "rule-based",
            }

        geos = [_generate_coastal_geofence_coords(u_lat, u_lon)] if (verdict in ("CAUTION", "DANGER")) else None
        nav_res = calculate_optimal_route(
            start_coords=[u_lat, u_lon],
            end_coords=[t_lat, t_lon],
            hazard_geofences=geos,
            start_label=pfz_res.get("location", location),
            end_label=t_name,
        )

        econ = nav_res["fuel_economy"]
        if is_danger:
            synthesis = (
                f"🚨 **DANGER Alert for {location}:** Severe weather or high sea state detected.\n\n"
                f"{weather_res.get('summary', '')}\n\n"
                f"⚠️ **Navigation Suspended: Sea state / Lightning hazard active. "
                f"Showing direct displacement metrics for planning purposes only once weather clears.**\n\n"
                f"🧭 **Planning Navigation Track:** {location} ➔ **{t_name}**\n\n"
                f"- **Direct Track Distance:** {nav_res['total_distance_nm']:.1f} NM ({nav_res['total_distance_km']:.1f} km)\n"
                f"- **Optimal Compass Heading:** **{nav_res['direct_heading_str']}**\n"
                f"- **Estimated Cruising Duration:** ~{econ['transit_time_str']} (@ 9.0 knots)\n"
                f"- **Marine Fuel Economy:** Saves **{econ['fuel_saved_liters']:.1f} Liters** of diesel "
                f"(~₹{econ['cost_saved_inr']:,.0f}) versus unguided search cruising.\n"
                f"- **Geofence Status:** {nav_res['geofence_status']}"
            )
        else:
            synthesis = (
                f"🧭 **Fuel-Optimal Waypoint Navigation Plan:** {location} ➔ **{t_name}**\n\n"
                f"- **Direct Track Distance:** {nav_res['total_distance_nm']:.1f} NM ({nav_res['total_distance_km']:.1f} km)\n"
                f"- **Optimal Compass Heading:** **{nav_res['direct_heading_str']}**\n"
                f"- **Estimated Cruising Duration:** ~{econ['transit_time_str']} (@ 9.0 knots)\n"
                f"- **Marine Fuel Economy:** Saves **{econ['fuel_saved_liters']:.1f} Liters** of diesel "
                f"(~₹{econ['cost_saved_inr']:,.0f}) versus unguided search cruising.\n"
                f"- **Geofence Clearance Check:** {nav_res['geofence_status']}"
            )
        if nav_res.get("imbl_warning_active"):
            synthesis += (
                f"\n\n🛑 **IMBL PROXIMITY WARNING: Risk of Impoundment!** "
                f"Course approaches within **{nav_res['imbl_min_distance_nm']:.1f} NM** of the "
                f"**{nav_res['imbl_closest_boundary']}** international maritime boundary. "
                f"Crossing risks detention by foreign coast guard. Steer westward to keep safe clearance."
            )

        return {
            "success": True,
            "intent": intent,
            "intent_result": intent_result,
            "agents_invoked": agents_invoked,
            "weather_result": weather_res,
            "pfz_result": pfz_res,
            "navigation_result": nav_res,
            "eo_result": None,
            "navigation_suspended": is_danger,
            "pfz_suppressed": False,
            "pfz_suppression_reason": (
                "⚠️ Navigation Suspended: Sea state / Lightning hazard active. "
                "Showing direct displacement metrics for planning purposes only once weather clears."
            ) if is_danger else None,
            "synthesis": synthesis,
            "synthesis_source": "navigation_synthesis",
        }

    # Case F: Earth Observation & Satellite Oceanography (Feature 3)
    if intent == "ecosystem_query":
        if not location:
            return {
                "success": True,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": None,
                "pfz_result": None,
                "navigation_result": None,
                "eo_result": None,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": (
                    "📍 Which coastal sector or marine water body would you like to analyze for Earth Observation telemetry? "
                    "For example: *'Analyze SST anomaly and chlorophyll concentrations off Kochi'* or *'Check ocean productivity off Veraval'*."
                ),
                "synthesis_source": "rule-based",
            }

        # Resolve explicit coordinates for the target location
        input_lat = inputs.get("lat")
        input_lon = inputs.get("lon")

        target_lat = None
        target_lon = None
        resolved_loc_name = location

        if input_lat is not None and input_lon is not None:
            target_lat = float(input_lat)
            target_lon = float(input_lon)
        else:
            # Explicitly geocode the extracted location name
            geo = get_coordinates(location)
            if geo.get("success"):
                target_lat = float(geo["lat"])
                target_lon = float(geo["lon"])
                resolved_loc_name = geo.get("location", location)

        weather_inputs = {
            "location": resolved_loc_name,
            "time_context": time_context,
        }
        if target_lat is not None and target_lon is not None:
            weather_inputs["lat"] = target_lat
            weather_inputs["lon"] = target_lon

        weather_res = weather_agent_run(weather_inputs)
        agents_invoked.append("weather_agent")

        lat = target_lat if target_lat is not None else weather_res.get("lat")
        lon = target_lon if target_lon is not None else weather_res.get("lon")

        if lat is None or lon is None or not weather_res.get("success"):
            err_msg = (weather_res.get("error") if weather_res else None) or f"Could not retrieve oceanographic coordinates for {location}."
            return {
                "success": False,
                "intent": intent,
                "intent_result": intent_result,
                "agents_invoked": agents_invoked,
                "weather_result": weather_res,
                "pfz_result": None,
                "navigation_result": None,
                "eo_result": None,
                "pfz_suppressed": False,
                "pfz_suppression_reason": None,
                "synthesis": f"📍 {err_msg}",
                "synthesis_source": "rule-based",
            }

        # Explicitly pass the resolved geocoded coordinates into eo_tools.generate_eo_grid
        eo_data = generate_eo_grid(center_lat=float(lat), center_lon=float(lon), radius_km=120.0)
        agents_invoked.append("eo_tools")

        synthesis = (
            f"🛰️ **Earth Observation & Oceanographic Telemetry: {weather_res.get('location', location)}**\n\n"
            f"**📊 Key Satellite Ocean Colour & Thermal Indices:**\n"
            f"- **Mean Sea Surface Temp (SST):** {eo_data['mean_sst_c']:.1f}°C *(Anomaly: {eo_data['sst_anomaly_c']:+.2f}°C vs climatology)*\n"
            f"- **SST Dynamic Range:** {eo_data['min_sst_c']:.1f}°C to {eo_data['max_sst_c']:.1f}°C\n"
            f"- **Chlorophyll-a Concentration:** {eo_data['mean_chlorophyll_mg_m3']:.2f} mg/m³ *(Peak Bloom: {eo_data['max_chlorophyll_mg_m3']:.2f} mg/m³)*\n"
            f"- **Baroclinic Upwelling Status:** **{eo_data['upwelling_intensity']}**\n"
            f"- **Estimated Thermocline Depth:** ~{eo_data['thermocline_depth_m']} m\n"
            f"- **Detected Upwelling Front:** `{eo_data['upwelling_front_coords'][0]:.4f}°N, {eo_data['upwelling_front_coords'][1]:.4f}°E`\n\n"
            f"**🔬 Scientific Assessment:**\n"
            f"Combined Copernicus Sentinel-3 SLSTR infrared radiometry and ISRO Oceansat-3 OCM-3 spectral telemetry show active coastal upwelling with elevated primary productivity and shoaling thermocline."
        )

        return {
            "success": True,
            "intent": intent,
            "intent_result": intent_result,
            "agents_invoked": agents_invoked,
            "weather_result": weather_res,
            "pfz_result": None,
            "navigation_result": None,
            "eo_result": eo_data,
            "pfz_suppressed": False,
            "pfz_suppression_reason": None,
            "synthesis": synthesis,
            "synthesis_source": "eo_synthesis",
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
        "eo_result": None,
        "pfz_suppressed": False,
        "pfz_suppression_reason": None,
        "synthesis": (
            "🤔 I am not completely sure what you are asking. "
            "You can ask me about sea conditions, weather safety, fishing zones, or navigation routes "
            "(e.g., 'Is it safe to fish near Kochi?', 'Show PFZ zones near Rameswaram', or 'Plan route to fishing zone from Kochi')."
        ),
        "synthesis_source": "rule-based",
    }


def run(inputs: dict) -> dict:
    """
    Public entry point for Master Orchestrator.
    Handles stakeholder persona normalization, multilingual synthesis localization,
    and ensures persona is returned.
    """
    if not isinstance(inputs, dict):
        inputs = {}

    raw_persona = inputs.get("persona")
    persona = "fisherman"
    if raw_persona:
        rp = str(raw_persona).lower()
        if "authority" in rp or "disaster" in rp:
            persona = "coastal_authority"
        elif "research" in rp or "oceanographer" in rp:
            persona = "researcher"
        else:
            persona = "fisherman"

    result = _execute_orchestration(inputs)
    result["persona"] = persona

    # ── Multilingual Localization ────────────────────────────────────────────
    intent_res = result.get("intent_result") or {}
    target_code = inputs.get("language_code")
    if not target_code or target_code == "auto":
        target_code = intent_res.get("language_code", "en")
    target_name = inputs.get("language") or intent_res.get("language") or LANG_CODE_TO_NAME.get(target_code, "English")

    if target_code and target_code != "en" and result.get("synthesis"):
        orig_synth = result["synthesis"]
        result["synthesis"] = _localize_synthesis(orig_synth, target_name, target_code)
        result["language"] = target_name
        result["language_code"] = target_code
        if "intent_result" in result and isinstance(result["intent_result"], dict):
            result["intent_result"]["language"] = target_name
            result["intent_result"]["language_code"] = target_code

    return result

