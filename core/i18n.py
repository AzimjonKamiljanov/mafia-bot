import json
import logging
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger("detektiv.i18n")

_STRINGS: Dict[str, str] = {}

def load_locales(locale: str = "uz"):
    """Load localization json file from locales/ directory."""
    global _STRINGS
    try:
        base_dir = Path(__file__).resolve().parent.parent
        locale_path = base_dir / "locales" / f"{locale}.json"
        if locale_path.exists():
            with open(locale_path, "r", encoding="utf-8") as f:
                _STRINGS = json.load(f)
        else:
            log.warning("Locale file not found: %s", locale_path)
    except Exception as e:
        log.warning("Could not load locale %s: %s", locale, e)

# Initial load
load_locales("uz")

def t(key: str, default: str = "", **kwargs: Any) -> str:
    """Translate string by key with optional kwargs formatting."""
    text = _STRINGS.get(key, default or key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
