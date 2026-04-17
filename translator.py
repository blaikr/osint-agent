# ── 1. IMPORTS & SETUP ──────────────────────────────────────
import json
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()


# ── 2. CONFIG ───────────────────────────────────────────────
translator_llm = ChatAnthropic(model="claude-haiku-4-5", temperature=0.0)

TARGET_LANGUAGES = {
    "arabic": "Arabic (Middle East: Saudi Arabia, UAE, Egypt, Syria, Iraq, Lebanon)",
    "persian": "Persian/Farsi (Iran, Afghanistan, Tajikistan)",
    "hebrew": "Hebrew (Israel)",
    "turkish": "Turkish (Turkey)",
    "russian": "Russian (Russia, Belarus, Kazakhstan, Ukraine)",
    "chinese_simplified": "Simplified Chinese (mainland China)",
    "chinese_traditional": "Traditional Chinese (Taiwan, Hong Kong)",
    "japanese": "Japanese (Japan)",
    "korean": "Korean (South Korea, North Korea)",
    "spanish": "Spanish (Spain, Latin America)",
    "french": "French (France, West Africa, parts of Europe)",
    "german": "German (Germany, Austria, Switzerland)",
    "portuguese": "Portuguese (Portugal, Brazil)",
    "italian": "Italian (Italy)",
    "ukrainian": "Ukrainian (Ukraine)",
    "hindi": "Hindi (India)",
}

REGION_MAP = {
    "middle_east": ["arabic", "persian", "hebrew", "turkish"],
    "east_asia": ["chinese_simplified", "chinese_traditional", "japanese", "korean"],
    "europe": ["russian", "french", "german", "spanish", "italian", "portuguese", "ukrainian"],
    "south_asia": ["hindi"],
}


# ── 3. LANGUAGE SELECTION ───────────────────────────────────
def _resolve_languages(regions: list) -> list:
    if not regions or "all" in regions:
        return list(TARGET_LANGUAGES.keys())
    languages = []
    for r in regions:
        languages.extend(REGION_MAP.get(r, []))
    return languages


# ── 4. TRANSLATION ──────────────────────────────────────────
def translate_target(target: str, regions: list = None) -> dict:
    """Translate a target name/topic into multiple languages, returning native-script versions."""
    languages_to_use = _resolve_languages(regions or ["all"])
    language_list = ", ".join(languages_to_use)

    prompt = f"""Translate the target name or topic "{target}" into the following languages. Use the native script for each language (not romanized).

Languages needed: {language_list}

Rules:
1. For person names, transliterate phonetically into the native script of that language.
2. For common names with a known established native form (e.g. Chinese names, Russian politicians), use the established form.
3. For topics/organizations, translate the meaning where possible, otherwise transliterate.
4. If a translation is uncertain, provide your best guess.

Respond ONLY with valid JSON in this exact format:
{{
  "arabic": "...",
  "persian": "...",
  ...
}}

Only include the languages requested. No explanation, no markdown, just JSON."""

    response = translator_llm.invoke(prompt)
    content = response.content.strip()

    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": f"Could not parse translations: {content[:200]}"}


def translate_content_to_english(foreign_text: str, source_language: str = "auto") -> str:
    """Translate foreign-language content to English, preserving names, dates, and facts exactly."""
    if not foreign_text or len(foreign_text.strip()) < 10:
        return foreign_text

    prompt = f"""Translate the following text to English. Preserve all names, dates, numbers, and factual details exactly. Do not add commentary, just provide the English translation.

Source language: {source_language}

Text:
{foreign_text[:4000]}

English translation:"""

    response = translator_llm.invoke(prompt)
    return response.content.strip()
