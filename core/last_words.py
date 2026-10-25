import html
import logging
from typing import Dict, Any, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from core.engine import find_game_by_user, display_name, save_runtime

log = logging.getLogger("detektiv.core.last_words")

LAST_WORD_TEMPLATES = {
    "nohaq": "Meni nohaq o'ldirdingiz, shahar baribir g'alaba qozonadi!",
    "mafia": "Haqiqiy mafiya hali ham oramizda, ehtiyot bo'ling!",
    "fuqaro": "Tinch fuqarolar, aslo taslim bo'lmang, oxirigacha kurashing!",
    "ruh": "Ruhim shahar uzra aylanib yuradi, sizlarni tinch qo'ymayman...",
    "qasos": "Mening o'limim uchun qonli xun to'laysizlar!",
}

def last_words_keyboard(uid: Any = 0, group_link: Optional[str] = None) -> InlineKeyboardMarkup:
    from core.navigation import return_to_group_button
    if isinstance(uid, str) and not group_link:
        group_link = uid
        uid = 0
    elif isinstance(uid, dict):
        if not group_link:
            group_link = uid.get("group_link")
        uid = 0

    rows = [
        [InlineKeyboardButton("💬 «Meni nohaq o'ldirdingiz!»", callback_data=f"last_word:nohaq:{uid}")],
        [InlineKeyboardButton("💬 «Haqiqiy mafiya oramizda!»", callback_data=f"last_word:mafia:{uid}")],
        [InlineKeyboardButton("💬 «Tinch aholi, taslim bo'lmang!»", callback_data=f"last_word:fuqaro:{uid}")],
        [InlineKeyboardButton("💬 «Mening o'limim uchun xun to'laysizlar!»", callback_data=f"last_word:qasos:{uid}")],
        [return_to_group_button(group_link)]
    ]
    return InlineKeyboardMarkup(rows)

async def prompt_last_words(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any], uid: int):
    """Notify dead player in PM that they have a chance to leave their dying words to the group."""
    chat_id = game["chat"]
    name = display_name(game, uid)
    role = game.get("roles", {}).get(uid, "Fuqaro")
    group_link = game.get("group_link")

    game.setdefault("waiting_last_words", {})[uid] = {
        "chat_id": chat_id,
        "name": name,
        "role": role,
    }
    await save_runtime(game)

    try:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                "💀 <b>Siz o'yinda halok bo'ldingiz!</b>\n\n"
                "Shaharga o'limingizdan oldingi <b>so'nggi so'zingizni</b> e'lon qilishingiz mumkin.\n\n"
                "Quyidagi tayyor tugmalardan birini bosing yoki to'g'ridan-to'g'ri <b>shu yerga o'z gapingizni yozib yuboring</b> "
                "(xabaringiz darhol butun guruhga chiqadi):"
            ),
            reply_markup=last_words_keyboard(uid, group_link=group_link),
            parse_mode="HTML"
        )
    except Exception as e:
        log.warning("Could not send last words prompt to %s: %s", uid, e)

async def deliver_last_words(
    context: ContextTypes.DEFAULT_TYPE,
    game: Dict[str, Any],
    uid: int,
    text: str
) -> bool:
    """Broadcast the dead player's dying words to the group chat."""
    info = game.get("waiting_last_words", {}).pop(uid, None)
    if not info:
        # Fallback if not tracked yet
        name = display_name(game, uid)
        role = game.get("roles", {}).get(uid, "Fuqaro")
        chat_id = game["chat"]
    else:
        name = info["name"]
        role = info["role"]
        chat_id = info["chat_id"]

    clean_text = text.strip()[:300]
    if not clean_text:
        return False

    broadcast_msg = (
        "🗣 <b>O'limidan oldingi so'nggi gapi:</b>\n"
        f"👤 <b>{html.escape(name)}</b> ({role}):\n"
        f"«<i>{html.escape(clean_text)}</i>»"
    )

    try:
        from core.navigation import bot_action_keyboard
        await context.bot.send_message(
            chat_id=chat_id,
            text=broadcast_msg,
            reply_markup=bot_action_keyboard(chat_id, "💬 Botga o'tish (Amallar/Ovoz)"),
            parse_mode="HTML"
        )
    except Exception as e:
        log.warning("Could not broadcast last words to chat %s: %s", chat_id, e)

    await save_runtime(game)
    return True
