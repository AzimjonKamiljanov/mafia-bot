import asyncio
import logging
from telegram.error import TelegramError
from telegram import Update
from telegram.ext import ContextTypes

from config import DEFAULT_LOBBY_SECONDS, MIN_PLAYERS, MAX_PLAYERS
from database.models import get_group_settings, track_group_member, get_badge, is_admin
from core.engine import games, lobbies, find_game_by_user, cancel_lobby_timer, abort_lobby, abort_game
from phases.lobby import lobby_text, lobby_keyboard, _lobby_timer, call_players_in_chat, start_game
from core.navigation import resolve_and_cache_group_link

log = logging.getLogger("detektiv.handlers.cb_lobby")


async def handle_lobby_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    if not q or not q.data:
        return False
    data = q.data
    user = q.from_user
    uid = user.id

    if data.startswith("lobby_join:"):
        chat_id = int(data.split(":")[1])
        if chat_id in games:
            await q.answer("⚠️ Ushbu guruhda o'yin allaqachon boshlangan!", show_alert=True)
            return True

        lobby = lobbies.get(chat_id)
        if not lobby or not lobby.get("open"):
            settings = await get_group_settings(chat_id)
            group_link = await resolve_and_cache_group_link(context.bot, q.message.chat) if q.message and q.message.chat else None
            lobby = {
                "chat_id": chat_id,
                "players": [],
                "names": {},
                "badges": {},
                "open": True,
                "created_at": asyncio.get_event_loop().time(),
                "settings": settings,
                "message_id": q.message.message_id if q.message else None,
                "group_link": group_link
            }
            lobbies[chat_id] = lobby
            timeout_sec = int(settings.get("lobby_seconds", DEFAULT_LOBBY_SECONDS))
            cancel_lobby_timer(lobby)
            lobby["_timer_task"] = asyncio.create_task(_lobby_timer(context, chat_id, timeout_sec))

        if uid in lobby["players"]:
            await q.answer("ℹ️ Siz allaqachon o'yinga qo'shilgansiz!")
            return True

        existing_game = find_game_by_user(uid)
        if existing_game and existing_game.get("chat") != chat_id and existing_game.get("alive", {}).get(uid, False):
            await q.answer("⚠️ Siz boshqa guruhdagi faol o'yinda tiriksiz! Avval o'sha o'yinni tugating.", show_alert=True)
            return True

        for other_cid, other_lob in lobbies.items():
            if other_cid != chat_id and uid in other_lob.get("players", []):
                await q.answer("⚠️ Siz boshqa guruhdagi ochiq lobbida kutmoqdasiz! Avval u yerdan chiqing.", show_alert=True)
                return True

        if len(lobby["players"]) >= MAX_PLAYERS:
            await q.answer("❌ Lobby to'lgan!", show_alert=True)
            return True

        lobby["players"].append(uid)
        lobby["names"][uid] = (user.full_name or user.first_name)[:40]
        badge = await get_badge(uid)
        if badge:
            lobby["badges"][uid] = badge
        if getattr(user, "is_premium", False):
            lobby.setdefault("premium", {})[uid] = True

        await track_group_member(chat_id, user)
        await q.answer("✅ Siz o'yinga muvaffaqiyatli qo'shildingiz!")

        try:
            await q.edit_message_text(
                text=lobby_text(lobby),
                reply_markup=lobby_keyboard(chat_id, include_bot_link=True),
                parse_mode="HTML"
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                log.warning("Could not edit lobby message on join: %s", e)
        return True

    if data.startswith("lobby_call:"):
        chat_id = int(data.split(":")[1])
        caller_name = (user.full_name or user.first_name)[:40]
        await q.answer("📢 O'yinchilar chaqirilmoqda...")
        await call_players_in_chat(context, chat_id, caller_name)
        return True

    if data.startswith("lobby_leave:"):
        chat_id = int(data.split(":")[1])
        lobby = lobbies.get(chat_id)
        if lobby and uid in lobby["players"]:
            lobby["players"].remove(uid)
            lobby["names"].pop(uid, None)
            lobby["badges"].pop(uid, None)
            await q.answer("🚪 Siz lobbyni tark etdingiz.")
            try:
                await q.edit_message_text(
                    text=lobby_text(lobby),
                    reply_markup=lobby_keyboard(chat_id, include_bot_link=True),
                    parse_mode="HTML"
                )
            except Exception as e:
                if "Message is not modified" not in str(e):
                    log.warning("Could not edit lobby message on leave: %s", e)
        else:
            await q.answer("ℹ️ Siz lobbida emassiz.", show_alert=True)
        return True

    if data.startswith("lobby_start:"):
        chat_id = int(data.split(":")[1])
        lobby = lobbies.get(chat_id)
        if not lobby or not lobby.get("open"):
            await q.answer("❌ Lobby yopilgan.", show_alert=True)
            return True
        if uid not in lobby["players"]:
            await q.answer("❗ Avval o'yinga qo'shiling.", show_alert=True)
            return True
        if len(lobby["players"]) < MIN_PLAYERS:
            await q.answer(f"❗ Kamida {MIN_PLAYERS} kishi kerak. Hozir: {len(lobby['players'])} ta.", show_alert=True)
            return True
        await q.answer("▶️ O'yin boshlanmoqda...")
        await start_game(context, chat_id)
        return True

    if data.startswith("lobby_stop:"):
        chat_id = int(data.split(":")[1])
        if not is_admin(uid):
            try:
                member = await context.bot.get_chat_member(chat_id, uid)
                if member.status not in ("administrator", "creator"):
                    await q.answer("❌ Faqat guruh adminlari to'xtata oladi.", show_alert=True)
                    return True
            except Exception as e:
                log.warning("get_chat_member check failed on lobby_stop for %s in chat %s: %s", uid, chat_id, e)
                await q.answer("❌ Guruh adminlik huquqini tekshirib bo'lmadi. Ruxsat berilmadi.", show_alert=True)
                return True
        abort_lobby(chat_id)
        await abort_game(chat_id)
        await q.answer("🛑 To'xtatildi.")
        try:
            await q.edit_message_text("🛑 <b>Lobby yoki o'yin to'xtatildi.</b>", parse_mode="HTML")
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
        return True

    return False
