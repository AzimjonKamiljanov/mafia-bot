"""
Centralized Telegram Premium Custom Emoji Manager for Detektiv Mafia Bot.
Supports scalable emoji mapping with Telegram HTML <tg-emoji document-id="..."> fallback </tg-emoji> format.
"""

import re
from typing import Dict, Any, Optional

# Scalable Centralized Configuration grouped by category
EMOJI_CONFIG: Dict[str, Dict[str, Dict[str, str]]] = {
    "GAMEPLAY": {
        # Core active emoji IDs provided by task
        "game_start": {"id": "3191530815439765550", "fallback": "🎬"},
        "trigger": {"id": "3191530815439765550", "fallback": "📢"},
        "announcement": {"id": "3191530815439765550", "fallback": "📢"},
        "start": {"id": "3191530815439765550", "fallback": "🎮"},
        "mafia": {"id": "1269403972611866648", "fallback": "🔪"},
        "mafia_role": {"id": "1269403972611866648", "fallback": "🔪"},
        "mafia_team": {"id": "1269403972611866648", "fallback": "🔪"},
        "mafia_action": {"id": "1269403972611866648", "fallback": "🕶️"},
        "don": {"id": "919985748604617114", "fallback": "🎩"},
        "boss": {"id": "919985748604617114", "fallback": "👑"},
        "detective": {"id": "1740555807604342805", "fallback": "🕵️‍♂️"},
        "investigation": {"id": "1740555807604342805", "fallback": "🔍"},
        "sheriff": {"id": "1740555807604342805", "fallback": "👮‍♂️"},
        "doctor": {"id": "3191530815439765548", "fallback": "🩺"},
        "heal": {"id": "3191530815439765548", "fallback": "💉"},
        "doctor_save": {"id": "3191530815439765548", "fallback": "💊"},
        "night": {"id": "4158409751421517834", "fallback": "🌙"},
        "night_phase": {"id": "4158409751421517834", "fallback": "🌌"},
        "day": {"id": "336920350212227127", "fallback": "☀️"},
        "day_phase": {"id": "336920350212227127", "fallback": "☀️"},
        "morning": {"id": "336920350212227127", "fallback": "🌅"},
        "voting": {"id": "336920350212227127", "fallback": "🗳️"},
        "dead": {"id": "3974262500324540463", "fallback": "💀"},
        "eliminated": {"id": "3974262500324540463", "fallback": "☠️"},
        "graveyard": {"id": "3974262500324540463", "fallback": "🪦"},
        "civilian": {"id": "1471004892762996745", "fallback": "👥"},
        "civilian_team": {"id": "1471004892762996745", "fallback": "🏘️"},
        "civilian_win": {"id": "1471004892762996745", "fallback": "🏆"},
        "mafia_win": {"id": "1145788388561911824", "fallback": "🩸"},
        "mafia_victory": {"id": "1145788388561911824", "fallback": "😈"},
        "timer": {"id": "3024877442880766280", "fallback": "⏳"},
        "countdown": {"id": "3024877442880766280", "fallback": "⏱️"},
        "warning": {"id": "3024877442880766280", "fallback": "⏰"},
    },
    "SHOP": {
        "coin": {"id": "5429462837318049280", "fallback": "🪙"},
        "gold": {"id": "5429462837318049280", "fallback": "🥇"},
        "gem": {"id": "5429462837318049280", "fallback": "💎"},
        "cart": {"id": "5429462837318049280", "fallback": "🛒"},
        "bag": {"id": "5463134628678688463", "fallback": "🎒"},
        "item_knife": {"id": "1269403972611866648", "fallback": "🔪"},
        "item_shield": {"id": "5370845348392576392", "fallback": "🛡️"},
        "item_crown": {"id": "919985748604617114", "fallback": "👑"},
        "item_doc": {"id": "5463134628678688463", "fallback": "📄"},
        "item_vote": {"id": "336920350212227127", "fallback": "🗳️"},
        "item_rose": {"id": "5429462837318049280", "fallback": "🌹"},
        "shop_header": {"id": "5429462837318049280", "fallback": "🛍️"},
    },
    "USER_SETTINGS": {
        "profile": {"id": "1740555807604342805", "fallback": "👤"},
        "badge_admin": {"id": "919985748604617114", "fallback": "👑"},
        "badge_special": {"id": "5429462837318049280", "fallback": "💎"},
        "badge_lightning": {"id": "5370845348392576392", "fallback": "⚡"},
        "badge_detective": {"id": "1740555807604342805", "fallback": "🕶️"},
        "badge_target": {"id": "5463134628678688463", "fallback": "🎯"},
        "stats_games": {"id": "3191530815439765550", "fallback": "🎮"},
        "stats_wins": {"id": "1471004892762996745", "fallback": "🏆"},
        "stats_losses": {"id": "3974262500324540463", "fallback": "❌"},
        "balance_coins": {"id": "5429462837318049280", "fallback": "🪙"},
        "balance_gold": {"id": "5429462837318049280", "fallback": "🥇"},
        "settings_gear": {"id": "5463134628678688463", "fallback": "⚙️"},
        "settings_time": {"id": "3024877442880766280", "fallback": "⏱️"},
        "settings_roles": {"id": "3191530815439765550", "fallback": "🎭"},
    }
}

# Flat lookup cache for rapid direct key searches
_FLAT_EMOJI_CACHE: Dict[str, Dict[str, str]] = {}
for _cat, _items in EMOJI_CONFIG.items():
    for _key, _val in _items.items():
        if _key not in _FLAT_EMOJI_CACHE:
            _FLAT_EMOJI_CACHE[_key] = _val

_KEY_ALIASES: Dict[str, str] = {
    "moon": "night",
    "sun": "day",
    "crown": "boss",
    "gem": "badge_special",
    "skull": "dead",
    "knife": "mafia",
    "swords": "item_knife",
    "scales": "voting",
    "trophy": "stats_wins",
    "lightning": "badge_lightning",
    "fire": "trigger",
    "party": "civilian_win",
    "shield": "item_shield",
    "target": "badge_target",
    "rose": "item_rose",
    "scroll": "item_doc",
    "rocket": "trigger",
    "lock": "item_shield",
    "sparkles": "trigger",
}
for _alias, _target in _KEY_ALIASES.items():
    if _alias not in _FLAT_EMOJI_CACHE and _target in _FLAT_EMOJI_CACHE:
        _FLAT_EMOJI_CACHE[_alias] = _FLAT_EMOJI_CACHE[_target]

# Character mappings for legacy compatibility
_CHAR_TO_KEY = {
    "🌙": "night",
    "☀️": "day",
    "🕵️": "detective",
    "🕵️‍♂️": "detective",
    "👑": "boss",
    "💎": "gem",
    "🏆": "stats_wins",
    "🪙": "coin",
    "🥇": "gold",
    "⚔️": "item_knife",
    "🔪": "mafia",
    "⚖️": "voting",
    "🛡️": "item_shield",
    "🚀": "trigger",
    "🔥": "trigger",
    "⚡": "badge_lightning",
    "🎉": "civilian_win",
    "📜": "item_doc",
    "🔒": "item_shield",
    "🎯": "badge_target",
    "🌹": "item_rose",
    "💀": "dead",
    "☠️": "eliminated",
    "🪦": "graveyard",
    "🎖️": "badge_target",
    "🕶️": "badge_detective",
    "✦": "gem",
    "✨": "trigger",
    "⏳": "timer",
    "⏱️": "countdown",
    "🗳️": "voting",
    "🗳": "voting",
    "🩺": "doctor",
    "💉": "heal",
    "💊": "doctor_save",
}

def render_custom_emoji(category: str, name: str, fallback: str = "") -> str:
    """
    Render a custom emoji tag formatted as:
    <tg-emoji document-id="ID_HERE">fallback_emoji</tg-emoji>
    """
    cat_dict = EMOJI_CONFIG.get(category.upper(), {})
    item = cat_dict.get(name.lower())
    if item:
        doc_id = item["id"]
        fb = fallback or item.get("fallback", "")
        return f'<tg-emoji document-id="{doc_id}">{fb}</tg-emoji>'
    return fallback or name

def tg_emoji(key: str, fallback: str = "", category: Optional[str] = None) -> str:
    """
    Lookup and render a custom emoji tag using category or automatic resolution.
    Strictly outputs <tg-emoji document-id="ID_HERE">fallback_emoji</tg-emoji>.
    """
    key_clean = key.strip()

    if category:
        cat_dict = EMOJI_CONFIG.get(category.upper(), {})
        if key_clean.lower() in cat_dict:
            item = cat_dict[key_clean.lower()]
            fb = fallback or item.get("fallback", "")
            return f'<tg-emoji document-id="{item["id"]}">{fb}</tg-emoji>'

    # 1. Direct flat cache
    if key_clean.lower() in _FLAT_EMOJI_CACHE:
        item = _FLAT_EMOJI_CACHE[key_clean.lower()]
        fb = fallback or item.get("fallback", "")
        return f'<tg-emoji document-id="{item["id"]}">{fb}</tg-emoji>'

    # 2. Check if key is a unicode emoji character
    if key_clean in _CHAR_TO_KEY:
        mapped_key = _CHAR_TO_KEY[key_clean]
        if mapped_key in _FLAT_EMOJI_CACHE:
            item = _FLAT_EMOJI_CACHE[mapped_key]
            fb = fallback or key_clean
            return f'<tg-emoji document-id="{item["id"]}">{fb}</tg-emoji>'

    # 3. Check if key is already an ID
    if key_clean.isdigit():
        fb = fallback or "✨"
        return f'<tg-emoji document-id="{key_clean}">{fb}</tg-emoji>'

    return fallback or key

def anim_emoji(key: str, fallback: str = "") -> str:
    """Universal animated/custom emoji helper with fallback (backward compatible)."""
    return tg_emoji(key, fallback=fallback)

def strip_anim_emoji_tags(text: str) -> str:
    """Strip <tg-emoji> tags leaving only fallback characters for plain/Markdown/safe HTML text."""
    if not text or "<tg-emoji" not in text:
        return text
    # Replace <tg-emoji document-id="..." or emoji-id="...">FALLBACK</tg-emoji> with FALLBACK
    cleaned = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text, flags=re.DOTALL)
    # Strip any dangling or self-closing tg-emoji tags
    return re.sub(r'</?tg-emoji[^>]*>', '', cleaned)

def format_badge_with_anim_emoji(badge: str) -> str:
    """
    Format a player badge with animated custom emoji tags for HTML mode.
    Example:
      '👑 Bosh Admin' -> '<tg-emoji document-id="919985748604617114">👑</tg-emoji> Bosh Admin'
    """
    if not badge or badge == "Yo'q":
        return badge or "Yo'q"
    badge_str = str(badge).strip()

    # Admin / Crown
    if badge_str.startswith("👑"):
        rem = badge_str[1:].strip()
        return f"{tg_emoji('don', '👑')} {rem}"
    # Lightning
    if badge_str.startswith("⚡"):
        rem = badge_str[1:].strip()
        return f"{tg_emoji('badge_lightning', '⚡', 'USER_SETTINGS')} {rem}"
    # Gem / Special
    if badge_str.startswith("✦") or badge_str.startswith("💎"):
        rem = badge_str[1:].strip()
        return f"{tg_emoji('badge_special', '💎', 'USER_SETTINGS')} {rem}"
    # Detective / Shades
    if badge_str.startswith("🕶️") or badge_str.startswith("🕶"):
        rem = badge_str[2:].strip() if badge_str.startswith("🕶️") else badge_str[1:].strip()
        return f"{tg_emoji('detective', '🕶️')} {rem}"
    # Target
    if badge_str.startswith("🎯"):
        rem = badge_str[1:].strip()
        return f"{tg_emoji('badge_target', '🎯', 'USER_SETTINGS')} {rem}"

    return f"{tg_emoji('item_shield', '🎖️', 'SHOP')} {badge_str}"
