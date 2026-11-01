"""
Visual effects and animated elements for Telegram Mafia Bot.
Supports Telegram Custom Animated Emojis (HTML <tg-emoji document-id="..."> format),
animated stickers, and native animated 3D physics dice (🎯, 🎲, 🎰).
"""

import re
import logging
from typing import Optional
from telegram import Bot

from core.emojis import (
    EMOJI_CONFIG,
    tg_emoji,
    render_custom_emoji,
    anim_emoji,
    strip_anim_emoji_tags,
    format_badge_with_anim_emoji,
)

log = logging.getLogger("detektiv.visuals")

# Telegram Animated / Custom Emojis (HTML tg-emoji tags with document-id)
TG_ANIMATED_EMOJIS = {
    # Named keys
    "moon": tg_emoji("night", "🌙"),
    "sun": tg_emoji("day", "☀️"),
    "detective": tg_emoji("detective", "🕵️‍♂️"),
    "skull": tg_emoji("dead", "☠️"),
    "knife": tg_emoji("mafia", "🔪"),
    "swords": tg_emoji("item_knife", "⚔️"),
    "scales": tg_emoji("voting", "⚖️"),
    "crown": tg_emoji("don", "👑"),
    "gem": tg_emoji("badge_special", "💎", "USER_SETTINGS"),
    "trophy": tg_emoji("civilian_win", "🏆"),
    "lightning": tg_emoji("badge_lightning", "⚡", "USER_SETTINGS"),
    "fire": tg_emoji("trigger", "🔥"),
    "party": tg_emoji("civilian_win", "🎉"),
    "shield": tg_emoji("item_shield", "🛡️", "SHOP"),
    "target": tg_emoji("badge_target", "🎯", "USER_SETTINGS"),
    "coin": tg_emoji("coin", "🪙", "SHOP"),
    "gold": tg_emoji("gold", "🥇", "SHOP"),
    "rose": tg_emoji("item_rose", "🌹", "SHOP"),
    "scroll": tg_emoji("item_doc", "📜", "SHOP"),
    "rocket": tg_emoji("trigger", "🚀"),
    "lock": tg_emoji("item_shield", "🔒", "SHOP"),
    "sparkles": tg_emoji("trigger", "✨"),

    # Direct emoji character mappings
    "🌙": tg_emoji("night", "🌙"),
    "☀️": tg_emoji("day", "☀️"),
    "🕵️": tg_emoji("detective", "🕵️‍♂️"),
    "🕵️‍♂️": tg_emoji("detective", "🕵️‍♂️"),
    "👑": tg_emoji("don", "👑"),
    "💎": tg_emoji("badge_special", "💎", "USER_SETTINGS"),
    "🏆": tg_emoji("civilian_win", "🏆"),
    "🪙": tg_emoji("coin", "🪙", "SHOP"),
    "🥇": tg_emoji("gold", "🥇", "SHOP"),
    "⚔️": tg_emoji("item_knife", "⚔️"),
    "⚖️": tg_emoji("voting", "⚖️"),
    "🛡️": tg_emoji("item_shield", "🛡️", "SHOP"),
    "🚀": tg_emoji("trigger", "🚀"),
    "🔥": tg_emoji("trigger", "🔥"),
    "⚡": tg_emoji("badge_lightning", "⚡", "USER_SETTINGS"),
    "🎉": tg_emoji("civilian_win", "🎉"),
    "📜": tg_emoji("item_doc", "📜", "SHOP"),
    "🔒": tg_emoji("item_shield", "🔒", "SHOP"),
    "🎯": tg_emoji("badge_target", "🎯", "USER_SETTINGS"),
    "🌹": tg_emoji("item_rose", "🌹", "SHOP"),
    "💀": tg_emoji("dead", "💀"),
    "☠️": tg_emoji("eliminated", "☠️"),
    "🎖️": tg_emoji("badge_target", "🎖️", "USER_SETTINGS"),
    "🕶️": tg_emoji("badge_detective", "🕶️", "USER_SETTINGS"),
    "✦": tg_emoji("badge_special", "💎", "USER_SETTINGS"),
    "✨": tg_emoji("trigger", "✨"),
    "⏳": tg_emoji("timer", "⏳"),
    "⏱️": tg_emoji("countdown", "⏱️"),
    "🗳️": tg_emoji("voting", "🗳️"),
    "🩺": tg_emoji("doctor", "🩺"),
}

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
        return f"{tg_emoji('don', '👑')} {raw_name}"
    if badge in ("👑 Qirol Toji", "Qirol Toji", "badge_crown"):
        return f"{tg_emoji('don', '👑')} {raw_name}"
    if badge in ("✦ Maxsus belgi", "Maxsus belgi", "badge_special", "✦ Maxsus"):
        return f"{tg_emoji('badge_special', '✦', 'USER_SETTINGS')} {raw_name} [Maxsus]"
    if badge in ("⚡ Yashin belgisi", "Yashin belgisi", "badge_lightning"):
        return f"{tg_emoji('badge_lightning', '⚡', 'USER_SETTINGS')} {raw_name}"
    if badge in ("🕶️ Sirli Detektiv", "Sirli Detektiv", "badge_mystery"):
        return f"{tg_emoji('detective', '🕶️')} {raw_name}"
    if badge in ("🎯 Aniqchi", "Aniqchi", "badge_sharpshooter"):
        return f"{tg_emoji('badge_target', '🎯', 'USER_SETTINGS')} {raw_name}"
    if badge:
        return f"{raw_name} [{html.escape(badge)}]"

    return raw_name

async def send_animated_dice_effect(bot: Bot, chat_id: int, emoji: str = "🎯"):
    """
    Safely trigger Telegram native interactive 3D physics animation:
    Note: Suppressed in groups (chat_id < 0) to remove spinning 3D dice from gameplay groups.
    """
    if chat_id < 0:
        return None
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
