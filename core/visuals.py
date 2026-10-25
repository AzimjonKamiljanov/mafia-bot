"""
Visual effects and animated elements for Telegram Mafia Bot.
Supports Telegram Custom Animated Emojis (HTML <tg-emoji> format),
animated stickers, and native animated 3D physics dice (🎯, 🎲, 🎰).
"""

import re
import logging
from typing import Optional
from telegram import Bot

log = logging.getLogger("detektiv.visuals")

# Telegram Animated / Custom Emojis (HTML tg-emoji tags with universal fallbacks)
TG_ANIMATED_EMOJIS = {
    # Named keys
    "moon": '<tg-emoji emoji-id="5368324170671202286">🌙</tg-emoji>',
    "sun": '<tg-emoji emoji-id="5465465476142387532">☀️</tg-emoji>',
    "detective": '<tg-emoji emoji-id="5463134628678688463">🕵️‍♂️</tg-emoji>',
    "skull": '<tg-emoji emoji-id="5368324170671202286">☠️</tg-emoji>',
    "knife": '<tg-emoji emoji-id="5465465476142387532">🔪</tg-emoji>',
    "swords": '<tg-emoji emoji-id="5370845348392576392">⚔️</tg-emoji>',
    "scales": '<tg-emoji emoji-id="5370845348392576392">⚖️</tg-emoji>',
    "crown": '<tg-emoji emoji-id="5373145953043714207">👑</tg-emoji>',
    "gem": '<tg-emoji emoji-id="5429462837318049280">💎</tg-emoji>',
    "trophy": '<tg-emoji emoji-id="5368324170671202286">🏆</tg-emoji>',
    "lightning": '<tg-emoji emoji-id="5370845348392576392">⚡</tg-emoji>',
    "fire": '<tg-emoji emoji-id="5375253685418820468">🔥</tg-emoji>',
    "party": '<tg-emoji emoji-id="5429462837318049280">🎉</tg-emoji>',
    "shield": '<tg-emoji emoji-id="5370845348392576392">🛡️</tg-emoji>',
    "target": '<tg-emoji emoji-id="5463134628678688463">🎯</tg-emoji>',
    "coin": '<tg-emoji emoji-id="5429462837318049280">🪙</tg-emoji>',
    "gold": '<tg-emoji emoji-id="5429462837318049280">🥇</tg-emoji>',
    "rose": '<tg-emoji emoji-id="5429462837318049280">🌹</tg-emoji>',
    "scroll": '<tg-emoji emoji-id="5463134628678688463">📜</tg-emoji>',
    "rocket": '<tg-emoji emoji-id="5375253685418820468">🚀</tg-emoji>',
    "lock": '<tg-emoji emoji-id="5463134628678688463">🔒</tg-emoji>',
    "sparkles": '<tg-emoji emoji-id="5429462837318049280">✨</tg-emoji>',

    # Direct emoji character mappings
    "🌙": '<tg-emoji emoji-id="5368324170671202286">🌙</tg-emoji>',
    "☀️": '<tg-emoji emoji-id="5465465476142387532">☀️</tg-emoji>',
    "🕵️": '<tg-emoji emoji-id="5463134628678688463">🕵️‍♂️</tg-emoji>',
    "🕵️‍♂️": '<tg-emoji emoji-id="5463134628678688463">🕵️‍♂️</tg-emoji>',
    "👑": '<tg-emoji emoji-id="5373145953043714207">👑</tg-emoji>',
    "💎": '<tg-emoji emoji-id="5429462837318049280">💎</tg-emoji>',
    "🏆": '<tg-emoji emoji-id="5368324170671202286">🏆</tg-emoji>',
    "🪙": '<tg-emoji emoji-id="5429462837318049280">🪙</tg-emoji>',
    "🥇": '<tg-emoji emoji-id="5429462837318049280">🥇</tg-emoji>',
    "⚔️": '<tg-emoji emoji-id="5370845348392576392">⚔️</tg-emoji>',
    "⚖️": '<tg-emoji emoji-id="5370845348392576392">⚖️</tg-emoji>',
    "🛡️": '<tg-emoji emoji-id="5370845348392576392">🛡️</tg-emoji>',
    "🚀": '<tg-emoji emoji-id="5375253685418820468">🚀</tg-emoji>',
    "🔥": '<tg-emoji emoji-id="5375253685418820468">🔥</tg-emoji>',
    "⚡": '<tg-emoji emoji-id="5370845348392576392">⚡</tg-emoji>',
    "🎉": '<tg-emoji emoji-id="5429462837318049280">🎉</tg-emoji>',
    "📜": '<tg-emoji emoji-id="5463134628678688463">📜</tg-emoji>',
    "🔒": '<tg-emoji emoji-id="5463134628678688463">🔒</tg-emoji>',
    "🎯": '<tg-emoji emoji-id="5463134628678688463">🎯</tg-emoji>',
    "🌹": '<tg-emoji emoji-id="5429462837318049280">🌹</tg-emoji>',
    "💀": '<tg-emoji emoji-id="5368324170671202286">💀</tg-emoji>',
    "☠️": '<tg-emoji emoji-id="5368324170671202286">☠️</tg-emoji>',
    "🎖️": '<tg-emoji emoji-id="5370845348392576392">🎖️</tg-emoji>',
    "🕶️": '<tg-emoji emoji-id="5463134628678688463">🕶️</tg-emoji>',
    "✦": '<tg-emoji emoji-id="5429462837318049280">💎</tg-emoji>',
    "✨": '<tg-emoji emoji-id="5429462837318049280">✨</tg-emoji>',
}

def anim_emoji(key: str, fallback: str = "") -> str:
    """Return an animated Telegram custom emoji tag with fallback."""
    return TG_ANIMATED_EMOJIS.get(key, fallback or key)

def format_badge_with_anim_emoji(badge: str) -> str:
    """
    Format a player badge with animated custom emoji tags for HTML mode.
    Example:
      '👑 Bosh Admin' -> '<tg-emoji ...>👑</tg-emoji> Bosh Admin'
      '⚡ Yashin belgisi' -> '<tg-emoji ...>⚡</tg-emoji> Yashin belgisi'
    """
    if not badge or badge == "Yo'q":
        return badge or "Yo'q"
    badge_str = str(badge).strip()
    for char, tag in TG_ANIMATED_EMOJIS.items():
        if len(char) <= 4 and badge_str.startswith(char):
            remaining = badge_str[len(char):].strip()
            return f"{tag} {remaining}"
    return f"{anim_emoji('shield', '🎖️')} {badge_str}"

def format_player_title_html(game_or_lobby: dict, uid: int) -> str:
    """Format player name with Telegram Premium animated custom emoji badge for HTML mode."""
    import html
    if not isinstance(game_or_lobby, dict):
        return f"O'yinchi_{uid}"
    names = game_or_lobby.get("names", {})
    raw_name = html.escape(str(names.get(uid, names.get(str(uid), f"O'yinchi_{uid}"))))

    badges = game_or_lobby.get("badges", {})
    badge = str(badges.get(uid, badges.get(str(uid), "")))

    from config import ADMIN_IDS, ADMIN_ID
    is_adm = (uid in ADMIN_IDS) or (ADMIN_ID != 0 and uid == ADMIN_ID)

    if is_adm or badge in ("👑 Bosh Admin", "Bosh Admin"):
        return f"{anim_emoji('crown', '👑')} {raw_name}"
    if badge in ("👑 Qirol Toji", "Qirol Toji", "badge_crown"):
        return f"{anim_emoji('crown', '👑')} {raw_name}"
    if badge in ("✦ Maxsus belgi", "Maxsus belgi", "badge_special", "✦ Maxsus"):
        return f"{anim_emoji('gem', '✦')} {raw_name} [Maxsus]"
    if badge in ("⚡ Yashin belgisi", "Yashin belgisi", "badge_lightning"):
        return f"{anim_emoji('lightning', '⚡')} {raw_name}"
    if badge in ("🕶️ Sirli Detektiv", "Sirli Detektiv", "badge_mystery"):
        return f"{anim_emoji('detective', '🕶️')} {raw_name}"
    if badge in ("🎯 Aniqchi", "Aniqchi", "badge_sharpshooter"):
        return f"{anim_emoji('target', '🎯')} {raw_name}"
    if badge:
        return f"{raw_name} [{html.escape(badge)}]"

    return raw_name

def strip_anim_emoji_tags(text: str) -> str:
    """Strip <tg-emoji> tags leaving only fallback characters for plain/Markdown/safe HTML text."""
    if not text or "<tg-emoji" not in text:
        return text
    # Replace <tg-emoji emoji-id="...">FALLBACK</tg-emoji> with FALLBACK
    cleaned = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text, flags=re.DOTALL)
    # Strip any dangling or self-closing tg-emoji tags
    return re.sub(r'</?tg-emoji[^>]*>', '', cleaned)

async def send_animated_dice_effect(bot: Bot, chat_id: int, emoji: str = "🎯"):
    """
    Safely trigger Telegram native interactive 3D physics animation:
    - '🎯': Dart arrow hitting target (execution / shoot)
    - '🎲': 3D rolling dice (luck / gold drop / random event / mystery)
    - '🎰': Animated slot jackpot (win / casino celebration)
    - '🎳': Bowling strike
    - '⚽': Football goal
    """
    try:
        if hasattr(bot, "send_dice"):
            return await bot.send_dice(chat_id=chat_id, emoji=emoji)
    except Exception as e:
        log.debug("send_dice (%s) ignored/failed: %s", emoji, e)
    return None

async def send_animated_sticker(bot: Bot, chat_id: int, sticker: str):
    """
    Safely dispatch an animated Telegram sticker (tgs/webm/file_id/url).
    Gracefully catches and logs errors so game progress is never blocked.
    """
    try:
        if hasattr(bot, "send_sticker"):
            return await bot.send_sticker(chat_id=chat_id, sticker=sticker)
    except Exception as e:
        log.debug("send_sticker (%s) ignored/failed: %s", sticker, e)
    return None
