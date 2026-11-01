"""
Centralized Telegram Premium Custom Animated Emoji Manager for Detektiv Mafia Bot.
Strictly outputs Telegram HTML custom animated emojis formatted as:
<tg-emoji emoji-id="ID_HERE">fallback_emoji</tg-emoji>
All emojis map to the 11 verified active Telegram animated emoji IDs.
"""

import re
from typing import Dict, Any, Optional

# Verified Active Custom Animated Emoji IDs
ACTIVE_ANIMATED_EMOJI_IDS = {
    "game_start": "3191530815439765550",      # 🎬 🎮 📢 Triggers, titles, announcements, game start
    "mafia": "1269403972611866648",           # 🔪 🗡️ ⚔️ Mafia role, mafia team, knife, attack
    "don": "919985748604617114",              # 👑 🎩 Don / Boss actions, crown, boss reveal, admin
    "detective": "1740555807604342805",       # 🕵️‍♂️ 🔍 🔎 Detective / Commissar / Sheriff investigation, search, profile
    "doctor": "3191530815439765548",          # 🩺 💉 💊 Doctor / Healer save / heal actions / medicine
    "night": "4158409751421517834",           # 🌙 🌌 🌑 Night phase transition / night actions / moon / dark
    "day": "336920350212227127",              # ☀️ 🌅 🗳️ Day phase / morning announcements / voting phase / sun / court
    "dead": "3974262500324540463",            # 💀 ☠️ 🪦 Player eliminated / dead status / skull / graveyard
    "civilian": "1471004892762996745",        # 👥 🏘️ 🏆 Civilian / Villager team / Civilian Victory / town / rewards / coins
    "mafia_win": "1145788388561911824",       # 🩸 😈 Mafia Victory announcement / evil win
    "timer": "3024877442880766280",           # ⏳ ⏱️ ⏰ Timer / countdown / remaining time warning / clock
}

DEFAULT_ANIMATED_EMOJI_ID = "3191530815439765550"

# Scalable Centralized Configuration grouped by category
EMOJI_CONFIG: Dict[str, Dict[str, Dict[str, str]]] = {
    "GAMEPLAY": {
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
        "coin": {"id": "1471004892762996745", "fallback": "🪙"},
        "gold": {"id": "1471004892762996745", "fallback": "🥇"},
        "gem": {"id": "1471004892762996745", "fallback": "💎"},
        "cart": {"id": "3191530815439765550", "fallback": "🛒"},
        "bag": {"id": "3191530815439765550", "fallback": "🎒"},
        "item_knife": {"id": "1269403972611866648", "fallback": "🔪"},
        "item_shield": {"id": "3191530815439765550", "fallback": "🛡️"},
        "item_crown": {"id": "919985748604617114", "fallback": "👑"},
        "item_doc": {"id": "1740555807604342805", "fallback": "📄"},
        "item_vote": {"id": "336920350212227127", "fallback": "🗳️"},
        "item_rose": {"id": "1471004892762996745", "fallback": "🌹"},
        "shop_header": {"id": "1471004892762996745", "fallback": "🛍️"},
    },
    "USER_SETTINGS": {
        "profile": {"id": "1740555807604342805", "fallback": "👤"},
        "badge_admin": {"id": "919985748604617114", "fallback": "👑"},
        "badge_special": {"id": "1471004892762996745", "fallback": "💎"},
        "badge_lightning": {"id": "3191530815439765550", "fallback": "⚡"},
        "badge_detective": {"id": "1740555807604342805", "fallback": "🕶️"},
        "badge_target": {"id": "3191530815439765550", "fallback": "🎯"},
        "stats_games": {"id": "3191530815439765550", "fallback": "🎮"},
        "stats_wins": {"id": "1471004892762996745", "fallback": "🏆"},
        "stats_losses": {"id": "3974262500324540463", "fallback": "❌"},
        "balance_coins": {"id": "1471004892762996745", "fallback": "🪙"},
        "balance_gold": {"id": "1471004892762996745", "fallback": "🥇"},
        "settings_gear": {"id": "3191530815439765550", "fallback": "⚙️"},
        "settings_time": {"id": "3024877442880766280", "fallback": "⏱️"},
        "settings_roles": {"id": "3191530815439765550", "fallback": "🎭"},
    },
    "SOCIAL": {
        "para": {"id": "1471004892762996745", "fallback": "💍"},
        "bro": {"id": "1471004892762996745", "fallback": "🤝"},
        "clan": {"id": "1471004892762996745", "fallback": "🛡️"},
        "gift": {"id": "1471004892762996745", "fallback": "🎁"},
        "wave": {"id": "3191530815439765550", "fallback": "👋"},
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
    "coin": "coin",
    "gold": "gold",
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
    "boost": "trigger",
    "plan": "game_start",
    "goal": "badge_target",
    "teamwork": "civilian_team",
    "bag": "bag",
    "cart": "cart",
    "clock": "timer",
    "hourglass": "timer",
    "ring": "para",
    "handshake": "bro",
}
for _alias, _target in _KEY_ALIASES.items():
    if _alias not in _FLAT_EMOJI_CACHE and _target in _FLAT_EMOJI_CACHE:
        _FLAT_EMOJI_CACHE[_alias] = _FLAT_EMOJI_CACHE[_target]

# Comprehensive Unicode character mappings covering all symbols used across the bot
_CHAR_TO_KEY: Dict[str, str] = {
    # 3191530815439765550
    "🎬": "game_start",
    "🎮": "game_start",
    "🎲": "game_start",
    "🎰": "game_start",
    "📢": "trigger",
    "📣": "trigger",
    "🚀": "trigger",
    "🔥": "trigger",
    "✨": "trigger",
    "🌟": "trigger",
    "💡": "trigger",
    "⚙️": "settings_gear",
    "⚙": "settings_gear",
    "🎭": "settings_roles",
    "ℹ️": "trigger",
    "ℹ": "trigger",
    "📌": "trigger",
    "🎯": "badge_target",
    "🛡️": "item_shield",
    "🛡": "item_shield",
    "🔒": "item_shield",
    "🔑": "item_shield",
    "🎒": "bag",
    "🛒": "cart",
    "🛍️": "shop_header",
    "🛍": "shop_header",
    "⚡": "badge_lightning",
    "🏷️": "trigger",
    "🏷": "trigger",
    "📖": "trigger",
    "💬": "trigger",
    "🏠": "trigger",
    "📦": "trigger",
    "🚪": "trigger",
    "🤖": "trigger",
    "📊": "trigger",
    "➕": "trigger",
    "⬅️": "trigger",
    "➡️": "trigger",
    "◀️": "trigger",
    "▶️": "trigger",
    "↗️": "trigger",
    "↗": "trigger",
    "👇": "trigger",
    "👋": "trigger",
    "🔄": "trigger",
    "🔁": "trigger",
    "🗣️": "trigger",
    "🗣": "trigger",
    "🔔": "trigger",
    "⛽": "trigger",
    "😂": "trigger",

    # 1269403972611866648
    "🔪": "mafia",
    "🗡️": "item_knife",
    "🗡": "item_knife",
    "⚔️": "item_knife",
    "⚔": "item_knife",
    "🔫": "mafia",
    "🥷": "mafia",
    "🐺": "mafia",
    "💣": "mafia",
    "💥": "mafia",
    "🦎": "mafia",

    # 919985748604617114
    "👑": "boss",
    "🎩": "don",
    "🤵🏻": "don",
    "🤵": "don",
    "🤴": "don",
    "🟡": "don",

    # 1740555807604342805
    "🕵️‍♂️": "detective",
    "🕵️": "detective",
    "🕵": "detective",
    "👮‍♂️": "sheriff",
    "👮": "sheriff",
    "🔍": "investigation",
    "🔎": "investigation",
    "❓": "investigation",
    "❔": "investigation",
    "📜": "item_doc",
    "📄": "item_doc",
    "📝": "item_doc",
    "✍️": "item_doc",
    "✍": "item_doc",
    "👤": "profile",
    "🆔": "profile",
    "🕶️": "badge_detective",
    "🕶": "badge_detective",
    "🚶": "detective",
    "🎪": "detective",
    "🔮": "detective",
    "🕴️": "detective",
    "🕴": "detective",
    "💃": "detective",
    "🗺️": "investigation",
    "🗺": "investigation",
    "👁️": "investigation",
    "👁": "investigation",
    "🧙🏻": "detective",
    "🧙": "detective",

    # 3191530815439765548
    "🩺": "doctor",
    "💉": "heal",
    "💊": "doctor_save",
    "🩹": "heal",
    "🏥": "doctor",
    "👨🏼‍⚕": "doctor",
    "👨‍⚕️": "doctor",
    "👨‍⚕": "doctor",

    # 4158409751421517834
    "🌙": "night",
    "🌌": "night_phase",
    "🌑": "night",
    "🌚": "night",
    "😴": "night",
    "💤": "night",
    "🌫️": "night",
    "🌫": "night",
    "👻": "graveyard",
    "🤫": "night",
    "⚫": "night",

    # 336920350212227127
    "☀️": "day",
    "🌅": "morning",
    "🌄": "morning",
    "🗳️": "voting",
    "🗳": "voting",
    "⚖️": "voting",
    "⚖": "voting",
    "🕊️": "day",
    "🕊": "day",
    "🏛️": "voting",
    "🏛": "voting",
    "🔨": "voting",
    "⚪": "day",
    "🧊": "voting",

    # 3974262500324540463
    "💀": "dead",
    "☠️": "eliminated",
    "☠": "eliminated",
    "🪦": "graveyard",
    "⚰️": "graveyard",
    "⚰": "graveyard",
    "❌": "stats_losses",
    "✖️": "stats_losses",
    "🛑": "dead",
    "⛔": "dead",
    "🏃": "dead",
    "💔": "dead",
    "😔": "stats_losses",
    "👎": "stats_losses",

    # 1471004892762996745
    "👥": "civilian",
    "🏘️": "civilian_team",
    "🏘": "civilian_team",
    "🏙️": "civilian_team",
    "🏙": "civilian_team",
    "🏆": "stats_wins",
    "🥇": "gold",
    "🥈": "stats_wins",
    "🥉": "stats_wins",
    "🪙": "coin",
    "💰": "coin",
    "💎": "gem",
    "✦": "gem",
    "🌹": "item_rose",
    "🎁": "gift",
    "🎉": "civilian_win",
    "🎊": "civilian_win",
    "💍": "para",
    "🤝": "bro",
    "🔵": "civilian_team",
    "🟢": "civilian_win",
    "🟣": "civilian_team",
    "💵": "coin",
    "💳": "coin",
    "💸": "coin",
    "🎖️": "badge_target",
    "🎖": "badge_target",
    "✅": "civilian_win",
    "✓": "civilian_win",
    "☑️": "civilian_win",
    "☑": "civilian_win",
    "⭐": "gold",
    "💌": "gift",
    "📩": "gift",
    "🪐": "gem",
    "🪩": "gem",
    "👍": "civilian_win",
    "👏": "civilian_win",
    "💪": "civilian_win",

    # 1145788388561911824
    "🩸": "mafia_win",
    "😈": "mafia_victory",
    "👿": "mafia_victory",
    "🔴": "mafia_win",
    "🃏": "mafia_victory",

    # 3024877442880766280
    "⏳": "timer",
    "⏱️": "countdown",
    "⏱": "countdown",
    "⏰": "warning",
    "⌛": "timer",
    "🕐": "timer",
    "🕑": "timer",
    "🕒": "timer",
    "🕓": "timer",
    "🕔": "timer",
    "⚠️": "warning",
    "❗": "warning",
    "❗️": "warning",
    "‼️": "warning",
    "🚨": "warning",
}

# Verified official Telegram Custom Animated Emoji IDs (MTProto tested & validated)
REAL_TELEGRAM_EMOJI_MAP: Dict[str, str] = {
    "3191530815439765550": "5361741454685256344",  # Game / announcement (GameEmoji)
    "1269403972611866648": "5373239082136650704",  # Knife / mafia (GameEmoji)
    "919985748604617114":  "5229011542011299168",  # Crown / don (GameEmoji)
    "1740555807604342805": "5231012545799666522",  # Detective search (NewsEmoji)
    "3191530815439765548": "5463081281048818043",  # Doctor medicine (GameEmoji)
    "4158409751421517834": "5226662903569989373",  # Night moon (GameEmoji)
    "336920350212227127":  "5373021138316186413",  # Day sun (GameEmoji)
    "3974262500324540463": "5463250708918711044",  # Dead skull (GameEmoji)
    "1471004892762996745": "5453957997418004470",  # Civilian / Town (GameEmoji)
    "1145788388561911824": "5228962845672096235",  # Evil win (GameEmoji)
    "3024877442880766280": "5373236586760651455",  # Timer / Clock (GameEmoji)
}

def resolve_all_tg_emoji_to_real_telegram(text: str) -> str:
    """
    Map configured IDs (such as Discord snowflakes) to verified official Telegram Custom Emoji IDs.
    Preserves fallback characters and ensures Telegram MTProto and Bot API render true moving animated emojis.
    """
    if not text or not isinstance(text, str) or "<tg-emoji" not in text:
        return text

    def _sub(m):
        eid = m.group(2)
        real = REAL_TELEGRAM_EMOJI_MAP.get(eid, eid)
        return f'<tg-emoji emoji-id="{real}">'

    return re.sub(r'<tg-emoji\s+(emoji-id|document-id)="(\d+)">', _sub, text)

# Precompile regex for known characters sorted longest first
_KNOWN_KEYS_SORTED = sorted(_CHAR_TO_KEY.keys(), key=len, reverse=True)
_KNOWN_PATTERN_STR = "|".join(re.escape(k) for k in _KNOWN_KEYS_SORTED)

# General regex for any other astral / technical unicode emojis
_GEN_PATTERN_STR = r"(?:(?:\u200d|\ufe0e|\ufe0f|[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u203c-\u2049]|[\u25aa-\u25fe]|[\u3030-\u303d]|[\u3297-\u3299])+)"

_COMBINED_EMOJI_RE = re.compile(f"({_KNOWN_PATTERN_STR})|({_GEN_PATTERN_STR})")
_HTML_TOKEN_RE = re.compile(r"(<tg-emoji[^>]*>.*?</tg-emoji>|<[^>]+>|[^<]+)", re.DOTALL)


def render_custom_emoji(category: str, name: str, fallback: str = "") -> str:
    """
    Render an official Telegram Bot API custom emoji tag formatted as:
    <tg-emoji emoji-id="ID_HERE">fallback_emoji</tg-emoji>
    """
    cat_dict = EMOJI_CONFIG.get(category.upper(), {})
    item = cat_dict.get(name.lower())
    if item:
        emoji_id = item["id"]
        fb = fallback or item.get("fallback", "")
        return f'<tg-emoji emoji-id="{emoji_id}">{fb}</tg-emoji>'
    return fallback or name


def tg_emoji(key: str, fallback: str = "", category: Optional[str] = None) -> str:
    """
    Lookup and render an official Telegram HTML custom animated emoji tag.
    Strictly outputs <tg-emoji emoji-id="ID_HERE">fallback_emoji</tg-emoji>.
    """
    key_clean = key.strip()

    if category:
        cat_dict = EMOJI_CONFIG.get(category.upper(), {})
        if key_clean.lower() in cat_dict:
            item = cat_dict[key_clean.lower()]
            fb = fallback or item.get("fallback", "")
            return f'<tg-emoji emoji-id="{item["id"]}">{fb}</tg-emoji>'

    # 1. Direct flat cache
    if key_clean.lower() in _FLAT_EMOJI_CACHE:
        item = _FLAT_EMOJI_CACHE[key_clean.lower()]
        fb = fallback or item.get("fallback", "")
        return f'<tg-emoji emoji-id="{item["id"]}">{fb}</tg-emoji>'

    # 2. Check if key is a unicode emoji character
    if key_clean in _CHAR_TO_KEY:
        mapped_key = _CHAR_TO_KEY[key_clean]
        if mapped_key in _FLAT_EMOJI_CACHE:
            item = _FLAT_EMOJI_CACHE[mapped_key]
            fb = fallback or key_clean
            return f'<tg-emoji emoji-id="{item["id"]}">{fb}</tg-emoji>'

    # 3. Check if key is already an ID
    if key_clean.isdigit():
        fb = fallback or "✨"
        return f'<tg-emoji emoji-id="{key_clean}">{fb}</tg-emoji>'

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


def enrich_with_animated_emojis(text: str) -> str:
    """
    Universal enhancer: transforms raw unicode emojis in HTML text outside tags into
    animated custom emoji tags <tg-emoji emoji-id="...">char</tg-emoji>.
    Preserves existing <tg-emoji> tags and normalizes legacy document-id attributes.
    """
    if not text or not isinstance(text, str):
        return text

    # Normalize legacy document-id to official Bot API emoji-id
    if "<tg-emoji" in text and "document-id=" in text:
        text = re.sub(r'<tg-emoji\s+document-id="(\d+)"', r'<tg-emoji emoji-id="\1"', text)

    def _replace_emojis(chunk: str) -> str:
        def _match_repl(m):
            matched = m.group(0)
            if matched in _CHAR_TO_KEY:
                mapped = _CHAR_TO_KEY[matched]
                eid = _FLAT_EMOJI_CACHE.get(mapped, {}).get("id", DEFAULT_ANIMATED_EMOJI_ID)
            else:
                eid = DEFAULT_ANIMATED_EMOJI_ID
            return f'<tg-emoji emoji-id="{eid}">{matched}</tg-emoji>'

        return _COMBINED_EMOJI_RE.sub(_match_repl, chunk)

    tokens = _HTML_TOKEN_RE.findall(text)
    out = []
    for token in tokens:
        if token.startswith("<"):
            out.append(token)
        else:
            out.append(_replace_emojis(token))

    return "".join(out)


def format_badge_with_anim_emoji(badge: str) -> str:
    """
    Format a player badge with animated custom emoji tags for HTML mode.
    Example:
      '👑 Bosh Admin' -> '<tg-emoji emoji-id="919985748604617114">👑</tg-emoji> Bosh Admin'
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
