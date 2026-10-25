"""
Visual effects and animated elements for Telegram Mafia Bot.
Supports Telegram Custom Animated Emojis (HTML <tg-emoji> format) and native animated dice (🎯, 🎲, 🎰).
"""

import logging
from typing import Optional
from telegram import Bot

log = logging.getLogger("detektiv.visuals")

# Telegram Animated / Custom Emojis (HTML tg-emoji tags with universal fallbacks)
TG_ANIMATED_EMOJIS = {
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
}

def anim_emoji(key: str, fallback: str = "") -> str:
    """Return an animated Telegram custom emoji tag with fallback."""
    return TG_ANIMATED_EMOJIS.get(key, fallback or key)

async def send_animated_dice_effect(bot: Bot, chat_id: int, emoji: str = "🎯"):
    """
    Safely trigger Telegram native interactive 3D physics animation:
    - '🎯': Dart arrow hitting target (execution / shoot)
    - '🎲': 3D rolling dice (luck / gold drop / random event)
    - '🎰': Animated slot jackpot (win / casino)
    - '🎳': Bowling strike
    - '⚽': Football goal
    """
    try:
        if hasattr(bot, "send_dice"):
            return await bot.send_dice(chat_id=chat_id, emoji=emoji)
    except Exception as e:
        log.debug("send_dice (%s) ignored/failed: %s", emoji, e)
    return None
