import json
import logging
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger("detektiv.i18n")

_LOCALES: Dict[str, Dict[str, str]] = {}
SUPPORTED_LOCALES = ("uz", "ru", "en")


def load_locale(locale: str) -> Dict[str, str]:
    """Load localization json file for given locale."""
    try:
        base_dir = Path(__file__).resolve().parent.parent
        locale_path = base_dir / "locales" / f"{locale}.json"
        if locale_path.exists():
            with open(locale_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            log.warning("Locale file not found: %s", locale_path)
    except Exception as e:
        log.warning("Could not load locale %s: %s", locale, e)
    return {}


def load_all_locales():
    """Preload all supported locales."""
    global _LOCALES
    for loc in SUPPORTED_LOCALES:
        _LOCALES[loc] = load_locale(loc)


load_all_locales()


def t(key: str, default: str = "", lang: str = "uz", **kwargs: Any) -> str:
    """Translate string by key with optional locale and kwargs formatting.

    Falls back to 'uz' locale if key is missing in requested lang,
    then to default value, and finally to the key itself.
    """
    locale_strings = _LOCALES.get(lang) or _LOCALES.get("uz", {})
    text = locale_strings.get(key)

    if text is None and lang != "uz":
        text = _LOCALES.get("uz", {}).get(key)

    if text is None:
        text = default if default else key

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
