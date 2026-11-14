"""
Internationalization (i18n) engine for MingMu (明眸).

Supports 8 languages:
- en: English
- es: Spanish (Español)
- ja: Japanese (日本語)
- ru: Russian (Русский)
- fr: French (Français)
- de: German (Deutsch)
- zh: Chinese (中文)
- tr: Turkish (Türkçe)

Provides configuration loading/saving at ~/.mingmu/config.json,
translation resolution with fallback to English, and runtime switching.
"""

from __future__ import annotations

import json
import locale
import logging
import os
from pathlib import Path
from typing import Any

from mingmu.i18n.translations import TRANSLATIONS

log = logging.getLogger(__name__)

# Code -> (Native Name, English Name)
SUPPORTED_LANGUAGES: dict[str, tuple[str, str]] = {
    "en": ("English", "English"),
    "es": ("Español", "Spanish"),
    "ja": ("日本語", "Japanese"),
    "ru": ("Русский", "Russian"),
    "fr": ("Français", "French"),
    "de": ("Deutsch", "German"),
    "zh": ("中文", "Chinese"),
    "tr": ("Türkçe", "Turkish"),
}

DEFAULT_LANGUAGE = "en"
CONFIG_DIR = Path.home() / ".mingmu"
CONFIG_FILE = CONFIG_DIR / "config.json"

_CURRENT_LANGUAGE: str = DEFAULT_LANGUAGE


def get_config_path() -> Path:
    """Return the configuration file path."""
    return CONFIG_FILE


def load_language_preference() -> str | None:
    """Load persisted language preference from ~/.mingmu/config.json."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lang = data.get("language")
                if isinstance(lang, str) and lang.lower() in SUPPORTED_LANGUAGES:
                    return lang.lower()
    except Exception as exc:
        log.debug("Failed to read language preference from %s: %s", CONFIG_FILE, exc)
    return None


def save_language_preference(code: str) -> bool:
    """Save language preference to ~/.mingmu/config.json."""
    code_norm = code.lower().strip()
    if code_norm not in SUPPORTED_LANGUAGES:
        return False
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config: dict[str, Any] = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                config = {}
        config["language"] = code_norm
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as exc:
        log.warning("Failed to save language preference to %s: %s", CONFIG_FILE, exc)
        return False


def detect_system_language() -> str:
    """Detect system locale and match to a supported language code."""
    # Check environment variables
    for env_var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env_var)
        if val:
            code = val.split(".")[0].split("_")[0].lower()
            if code in SUPPORTED_LANGUAGES:
                return code

    # Check locale.getdefaultlocale
    try:
        loc = locale.getdefaultlocale()[0]
        if loc:
            code = loc.split("_")[0].lower()
            if code in SUPPORTED_LANGUAGES:
                return code
    except Exception:
        pass

    return DEFAULT_LANGUAGE


def get_language() -> str:
    """Return the currently active language code."""
    return _CURRENT_LANGUAGE


def set_language(code: str) -> None:
    """Set the currently active language code."""
    global _CURRENT_LANGUAGE
    code_norm = code.lower().strip()
    if code_norm in SUPPORTED_LANGUAGES:
        _CURRENT_LANGUAGE = code_norm
    else:
        log.warning("Unsupported language code '%s', falling back to '%s'", code, DEFAULT_LANGUAGE)
        _CURRENT_LANGUAGE = DEFAULT_LANGUAGE


def init_language(cli_override: str | None = None) -> str:
    """Initialize active language from CLI flag, saved preference, or system locale."""
    if cli_override and cli_override.lower().strip() in SUPPORTED_LANGUAGES:
        set_language(cli_override)
        return _CURRENT_LANGUAGE

    saved = load_language_preference()
    if saved:
        set_language(saved)
        return _CURRENT_LANGUAGE

    detected = detect_system_language()
    set_language(detected)
    return _CURRENT_LANGUAGE


def t(key: str, default: str | None = None, **kwargs: Any) -> str:
    """Translate a key into the currently active language.

    Falls back to English if the translation is missing,
    or *default* / *key* if missing in English.
    Interpolates any keyword arguments via string formatting.
    """
    lang_dict = TRANSLATIONS.get(_CURRENT_LANGUAGE, TRANSLATIONS.get(DEFAULT_LANGUAGE, {}))
    text = lang_dict.get(key)
    if text is None:
        text = TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key, default if default is not None else key)

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    return text
