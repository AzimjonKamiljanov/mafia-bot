import asyncio
import logging
from telegram.error import TelegramError
from telegram import Update
from telegram.ext import ContextTypes

from config import DEFAULT_LOBBY_SECONDS, MIN_PLAYERS, MAX_PLAYERS
from database.models import get_group_settings, track_group_member, get_badge, is_admin
from core.engine import games, lobbies, find_game_by_user, cancel_lobby_timer, abort_lobby, abort_game, get_chat_lock
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
        parts = data.split(":")
        if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        chat_id = int(parts[1])

        async with get_chat_lock(chat_id):
            if chat_id in games:
                game = games[chat_id]
                if game.get("phase") in ("finished", "aborted"):
                    games.pop(chat_id, None)
                else:
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
            if existing_game and existing_game.get("chat") != chat_id and existing_game.get("phase") not in ("finished", "aborted") and existing_game.get("alive", {}).get(uid, False):
                await q.answer("⚠️ Siz boshqa guruhdagi faol o'yinda tiriksiz! Avval o'sha o'yinni tugating.", show_alert=True)
                return True

            # Auto-switch from any other lobby smoothly without blocking
            for other_cid, other_lob in list(lobbies.items()):
                if other_cid != chat_id and uid in other_lob.get("players", []):
                    other_lob["players"].remove(uid)
                    other_lob.get("names", {}).pop(uid, None)
                    other_lob.get("badges", {}).pop(uid, None)
                    other_lob.get("premium", {}).pop(uid, None)

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
                if q.message and q.message.chat_id == chat_id:
                    await q.edit_message_text(
                        text=lobby_text(lobby),
                        reply_markup=lobby_keyboard(chat_id, include_bot_link=True),
                        parse_mode="HTML"
                    )
                elif lobby.get("message_id"):
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=lobby["message_id"],
                        text=lobby_text(lobby),
                        reply_markup=lobby_keyboard(chat_id, include_bot_link=True),
                        parse_mode="HTML"
                    )
            except Exception as e:
                if "Message is not modified" not in str(e):
                    log.warning("Could not edit lobby message on join: %s", e)
            return True

    if data.startswith("lobby_call:"):
        parts = data.split(":")
        if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        chat_id = int(parts[1])
        caller_name = (user.full_name or user.first_name)[:40]
        await q.answer("📢 O'yinchilar chaqirilmoqda...")
        await call_players_in_chat(context, chat_id, caller_name)
        return True

    if data.startswith("lobby_leave:"):
        parts = data.split(":")
        if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        chat_id = int(parts[1])
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
        parts = data.split(":")
        if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        chat_id = int(parts[1])
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
        parts = data.split(":")
        if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        chat_id = int(parts[1])
        if chat_id not in games and chat_id not in lobbies:
            await q.answer("ℹ️ Hozirda ushbu guruhda faol o'yin yoki lobby yo'q.", show_alert=True)
            return True
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
        lobby = abort_lobby(chat_id)
        if lobby:
            pinned_id = lobby.get("pinned_message_id")
            if pinned_id:
                try:
                    await context.bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_id)
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)
        await abort_game(chat_id)
        await q.answer("🛑 To'xtatildi.")
        try:
            await q.edit_message_text("🛑 <b>Lobby yoki o'yin to'xtatildi.</b>", parse_mode="HTML")
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
        return True

    return False
