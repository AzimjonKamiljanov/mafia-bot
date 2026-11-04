"""
Core Presentation & UI System for Detektiv Mafia Bot.
Provides throttled in-place game board updates, HTML card templates,
image asset caching, custom emoji capability probing, and animation helpers.
"""

import asyncio
import html
import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from telegram import Bot, InlineKeyboardMarkup
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from core.emojis import tg_emoji, anim_emoji, strip_anim_emoji_tags
from core.i18n import t

log = logging.getLogger("detektiv.ui")

# In-memory throttler for in-place game board updates per chat (3.0s minimum throttle)
_BOARD_THROTTLE_SECONDS: float = 3.0
_board_last_updated: Dict[int, float] = {}

# Cached Telegram file IDs for static image assets
PHOTO_FILE_IDS: Dict[str, str] = {}

# Custom emoji feature availability probe flag
_CUSTOM_EMOJI_SUPPORTED: Optional[bool] = None


async def probe_custom_emoji_capability(bot: Bot) -> bool:
    """
    Proactively checks whether Telegram Bot API allows querying/rendering custom emojis.
    Stores the result in _CUSTOM_EMOJI_SUPPORTED.
    """
    global _CUSTOM_EMOJI_SUPPORTED
    if _CUSTOM_EMOJI_SUPPORTED is not None:
        return _CUSTOM_EMOJI_SUPPORTED

    try:
        if hasattr(bot, "get_custom_emoji_stickers"):
            # Probe with the first active custom emoji ID
            test_id = "3191530815439765550"
            stickers = await bot.get_custom_emoji_stickers([test_id])
            _CUSTOM_EMOJI_SUPPORTED = bool(stickers)
            log.info("Custom emoji capability probe succeeded. Custom emojis supported: %s", _CUSTOM_EMOJI_SUPPORTED)
            return _CUSTOM_EMOJI_SUPPORTED
    except Exception as e:
        log.warning("Custom emoji probe encountered an error (using fallback): %s", e)

    _CUSTOM_EMOJI_SUPPORTED = False
    return False


def is_custom_emoji_supported() -> bool:
    """Returns whether custom emojis were confirmed supported by the probe."""
    return _CUSTOM_EMOJI_SUPPORTED is True


def render_divider() -> str:
    """Returns a clean HTML decorative divider."""
    return "────────────────────"


def render_card(title: str, body: str, meta: Optional[str] = None, footer: Optional[str] = None) -> str:
    """
    Renders a structured, clean HTML card with concise typography (group-friendly ≤ 8 lines).
    """
    lines = [f"<b>{title}</b>"]
    if meta:
        lines.append(f"<i>{meta}</i>")
    lines.append(render_divider())
    if body:
        lines.append(body)
    if footer:
        lines.append(render_divider())
        lines.append(f"<i>{footer}</i>")
    return "\n".join(lines)


def render_player_roster(game: dict, show_roles: bool = False, alive_only: bool = False) -> str:
    """
    Renders formatted player list with status indicators and titles.
    """
    from core.visuals import format_player_title_html
    players = game.get("players", [])
    alive_dict = game.get("alive", {})
    roles_dict = game.get("roles", {})

    lines: List[str] = []
    idx = 1
    for uid in players:
        is_alive = alive_dict.get(uid, False)
        if alive_only and not is_alive:
            continue
        p_name = format_player_title_html(game, uid)
        status_ico = tg_emoji("detective", "👤") if is_alive else tg_emoji("dead", "💀")

        if show_roles and uid in roles_dict:
            r_name = roles_dict[uid]
            lines.append(f"{idx}. {status_ico} {p_name} — <i>{html.escape(r_name)}</i>")
        else:
            lines.append(f"{idx}. {status_ico} {p_name}")
        idx += 1

    return "\n".join(lines)


def format_html(template_key: str, lang: str = "uz", **kwargs: Any) -> str:
    """
    Returns escaped HTML formatted string based on centralized locale keys.
    """
    raw_template = t(template_key, lang=lang)
    safe_kwargs = {k: html.escape(str(v)) for k, v in kwargs.items()}
    try:
        return raw_template.format(**safe_kwargs)
    except Exception:
        return raw_template


async def update_game_board(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    photo_key: Optional[str] = None,
    force_new: bool = False,
) -> Optional[int]:
    """
    Updates the in-place game board message with 3-5s throttle debounce.
    If no existing board message ID in game["board_msg_id"], sends message and stores ID.
    If editing fails due to message deletion or age, transparently posts a new board message.
    """
    from core.engine import games
    game = games.get(chat_id)

    now = time.time()
    last_update = _board_last_updated.get(chat_id, 0.0)
    elapsed = now - last_update

    # Apply throttle sleep if called within throttle window
    if elapsed < _BOARD_THROTTLE_SECONDS:
        sleep_needed = _BOARD_THROTTLE_SECONDS - elapsed
        log.debug("Throttling game board update for chat %s (waiting %.2fs)", chat_id, sleep_needed)
        await asyncio.sleep(sleep_needed)

    board_msg_id = None if force_new or not game else game.get("board_msg_id")

    if board_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=board_msg_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            _board_last_updated[chat_id] = time.time()
            return board_msg_id
        except BadRequest as e:
            err_str = str(e).lower()
            if "message is not modified" in err_str:
                _board_last_updated[chat_id] = time.time()
                return board_msg_id
            log.warning("Could not edit existing game board (%s) in chat %s: %s. Sending new board.", board_msg_id, chat_id, e)
        except Exception as e:
            log.warning("Unexpected error editing board message in chat %s: %s", chat_id, e)

    # Post a new board message
    try:
        new_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        _board_last_updated[chat_id] = time.time()
        if game:
            game["board_msg_id"] = new_msg.message_id
        return new_msg.message_id
    except Exception as e:
        log.error("Failed to post game board message to chat %s: %s", chat_id, e)
        return None
