import html
import logging
from typing import Dict, Any, Optional, Union
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_USERNAME

log = logging.getLogger("detektiv.core.navigation")

def get_bot_username() -> str:
    return BOT_USERNAME or "Detektivmj_bot"

def get_bot_deep_link(chat_id: int, action: str = "act") -> str:
    username = get_bot_username()
    return f"https://t.me/{username}?start={action}_{abs(chat_id)}"

def escape_md(text: Any) -> str:
    s = str(text) if text is not None else ""
    for ch in ("_", "*", "`", "["):
        s = s.replace(ch, f"\\{ch}")
    return s

def get_group_link(game_or_link: Any) -> str:
    if isinstance(game_or_link, dict):
        link = game_or_link.get("group_link")
        if link:
            return link
        chat_id = game_or_link.get("chat", 0)
        cid_str = str(abs(chat_id))
        if cid_str.startswith("100"):
            return f"https://t.me/c/{cid_str[3:]}/999999999"
        elif chat_id != 0:
            return f"https://t.me/c/{cid_str}/999999999"
        return "https://t.me"
    elif isinstance(game_or_link, int):
        cid_str = str(abs(game_or_link))
        if cid_str.startswith("100"):
            return f"https://t.me/c/{cid_str[3:]}/999999999"
        elif game_or_link != 0:
            return f"https://t.me/c/{cid_str}/999999999"
        return "https://t.me"
    elif isinstance(game_or_link, str) and game_or_link:
        return game_or_link
    return "https://t.me"

def bot_action_button(chat_id: int, label: str = "💬 Botga o'tish (Amallar/Ovoz)") -> InlineKeyboardButton:
    return InlineKeyboardButton(label, url=get_bot_deep_link(chat_id, "act"))

def return_to_group_button(game_or_link: Any, label: str = "👥 Guruhga qaytish (Muhokama)") -> InlineKeyboardButton:
    return InlineKeyboardButton(label, url=get_group_link(game_or_link))

def bot_action_keyboard(chat_id: int, label: str = "💬 Botga o'tish (Amallar/Ovoz)") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[bot_action_button(chat_id, label)]])

def return_to_group_keyboard(game_or_link: Any, label: str = "👥 Guruhga qaytish (Muhokama)") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[return_to_group_button(game_or_link, label)]])

async def resolve_and_cache_group_link(bot, chat) -> str:
    if not chat:
        return "https://t.me"
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}"
    try:
        link = await bot.export_chat_invite_link(chat.id)
        if link:
            return link
    except Exception as e:
        log.debug("Could not export chat invite link for %s: %s", chat.id, e)
    cid_str = str(abs(chat.id))
    if cid_str.startswith("100"):
        return f"https://t.me/c/{cid_str[3:]}/999999999"
    return f"https://t.me/c/{cid_str}/999999999"
