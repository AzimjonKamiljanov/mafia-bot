import asyncio
import html
import logging
import time
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import (
    MIN_PLAYERS, MAX_PLAYERS, DEFAULT_LOBBY_SECONDS, DAY_PHOTO_PATH, NIGHT_PHOTO_PATH, ROLES
)
from database.models import (
    ensure_user, get_badge, get_group_settings, is_admin, track_group_member, get_group_members
)
from core.engine import (
    lobbies, games, display_name, save_runtime, cancel_lobby_timer, cancel_game_timer
)
from roles.allocator import choose_roles
from roles.base import get_role_info, get_role_icon
from roles.dossier import format_role_dossier
from core.audio_effects import send_atmospheric_message
from core.navigation import (
    bot_action_button, return_to_group_keyboard, get_bot_deep_link, resolve_and_cache_group_link, escape_md
)

log = logging.getLogger("detektiv.phases.lobby")

def lobby_text(lobby: Dict[str, Any]) -> str:
    players = lobby.get("players", [])
    count = len(players)

    lines = [
        "🎮 <b>O'yinga ro'yxatdan o'tish</b>",
        "",
        f"👥 <b>Ishtirokchilar ({count}/{MAX_PLAYERS}):</b>",
    ]

    if players:
        from core.visuals import format_player_title_html
        for i, uid in enumerate(players, 1):
            name = format_player_title_html(lobby, uid)
            lines.append(f"{i}. 👤 {name}")
    else:
        lines.append("<i>Hozircha hech kim ro'yxatdan o'tmadi.</i>")

    lines.extend([
        "",
        f"⏳ Kamida <b>{MIN_PLAYERS}</b> kishi yig'ilgach start bering.",
        "Qo'shilish uchun pastdagi <b>Qo'shilish</b> tugmasini bosing 👇",
        "",
        "ℹ️ <b>Buyruqlar:</b>",
        "• /start (yoki /startgame) — O'yinni boshlash",
        "• /call — O'yinchilarni chaqirish",
        "• /chiqish — Lobbyni tark etish",
        "• /stop — O'yinni to'xtatish"
    ])
    return "\n".join(lines)


def lobby_keyboard(chat_id: int, include_bot_link: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🎮 Qo'shilish", callback_data=f"lobby_join:{chat_id}")
        ]
    ]
    if include_bot_link:
        rows.append([
            InlineKeyboardButton("💬 Botga o'tish", url=get_bot_deep_link(chat_id, "act"))
        ])
    return InlineKeyboardMarkup(rows)

async def call_players_in_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, caller_name: str = ""):
    """Mention all known members of the group and invite them to play."""
    # 1. Dynamically sync all chat administrators into group_users
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        for adm in admins:
            if adm.user and not adm.user.is_bot:
                await track_group_member(chat_id, adm.user)
    except Exception as e:
        log.debug("Could not fetch chat admins in call_players_in_chat: %s", e)

    # 2. Get all tracked group members
    members = await get_group_members(chat_id, limit=150)
    lobby = lobbies.get(chat_id)
    joined = set(lobby.get("players", [])) if lobby else set()
    bot_id = context.bot.id

    # 3. Filter candidates (not bot, not already in lobby)
    candidates = [m for m in members if m["user_id"] != bot_id and m["user_id"] not in joined]

    caller_str = f"📣 <b>{html.escape(caller_name)}</b> barchani o'yinga chorlamoqda!\n\n" if caller_name else ""
    reply_markup = lobby_keyboard(chat_id, include_bot_link=True) if (lobby and lobby.get("open")) else None

    if candidates:
        def make_mention(m):
            name = html.escape((m.get("name") or "O'yinchi")[:25])
            uid = m["user_id"]
            username = m.get("username")
            if username:
                return f'👤 <a href="tg://user?id={uid}">{name}</a> (@{username})'
            return f'👤 <a href="tg://user?id={uid}">{name}</a>'

        CHUNK_SIZE = 8
        chunks = [candidates[i:i + CHUNK_SIZE] for i in range(0, len(candidates), CHUNK_SIZE)]

        action_hint = "🎮 Safimizga qo'shilish uchun yuqoridagi <b>Qo'shilish</b> tugmasini bosing!" if (lobby and lobby.get("open")) else "💡 O'yinni boshlash uchun guruhda <b>/game</b> buyrug'ini bering!"

        # First batch includes full banner
        first_mentions = "\n".join(f"• {make_mention(m)}" for m in chunks[0])
        batch_label = f" (1/{len(chunks)})" if len(chunks) > 1 else ""
        header_text = (
            f"📢 <b>DIQQAT, MAFIA O'YINIGA CHORLOV!</b> 🕵️‍♂️🔥\n\n"
            f"{caller_str}"
            f"Qotillar shahar ko'chalarida kezib yuribdi! Haqiqiy detektiv kim, ayyor mafiya kim — o'yinda aniqlaymiz! 🎭\n\n"
            f"👥 <b>Chaqirilganlar{batch_label}:</b>\n"
            f"{first_mentions}\n\n"
            f"{action_hint}"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=header_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

        # Remaining batches if more than CHUNK_SIZE members
        for idx, chunk in enumerate(chunks[1:], start=2):
            await asyncio.sleep(0.4)
            b_mentions = "\n".join(f"• {make_mention(m)}" for m in chunk)
            b_text = (
                f"👥 <b>Chaqirilganlar ({idx}/{len(chunks)}):</b>\n"
                f"{b_mentions}"
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=b_text,
                parse_mode="HTML"
            )
    else:
        if lobby and lobby.get("open") and lobby.get("players"):
            text = (
                f"📢 <b>DIQQAT!</b>\n\n"
                f"{caller_str}"
                f"🎉 Barcha ma'lum o'yinchilar allaqachon lobbiyda!\n"
                f"O'yinni boshlash uchun <b>/startgame</b> buyrug'ini bering."
            )
        else:
            text = (
                f"📢 <b>Diqqat, barcha shahar ahli!</b>\n\n"
                f"{caller_str}"
                f"Yangi Mafia o'yini boshlanmoqda! Haqiqiy detektiv kim, ayyor qotil kim — sinab ko'ring!\n\n"
                f"🎮 O'yin ochish uchun <b>/game</b> buyrug'ini yuboring!"
            )
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def create_lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in ("group", "supergroup"):
        if update.effective_user:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text="❌ Ushbu buyruq faqat Telegram guruhlarida ishlaydi."
                )
            except Exception:
                pass
        return

    chat_id = chat.id
    if chat_id in games:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Ushbu guruhda ayni paytda o'yin davom etmoqda!"
        )
        return

    if chat_id in lobbies:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=lobby_text(lobbies[chat_id]),
            reply_markup=lobby_keyboard(chat_id, include_bot_link=True),
            parse_mode="HTML"
        )
        lobbies[chat_id]["message_id"] = msg.message_id
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
            lobbies[chat_id]["pinned_message_id"] = msg.message_id
        except Exception as e:
            log.warning("Could not pin lobby message in chat %s: %s", chat_id, e)
        return

    await ensure_user(user)
    await track_group_member(chat_id, user)
    settings = await get_group_settings(chat_id)
    group_link = await resolve_and_cache_group_link(context.bot, chat)
    lobby = {
        "chat_id": chat_id,
        "players": [],
        "names": {},
        "badges": {},
        "premium": {},
        "open": True,
        "created_at": asyncio.get_event_loop().time(),
        "settings": settings,
        "message_id": None,
        "pinned_message_id": None,
        "group_link": group_link
    }
    lobbies[chat_id] = lobby

    # Add creator automatically
    lobby["players"].append(user.id)
    lobby["names"][user.id] = (user.full_name or user.first_name)[:40]
    badge = await get_badge(user.id)
    if badge:
        lobby["badges"][user.id] = badge
    if getattr(user, "is_premium", False):
        lobby.setdefault("premium", {})[user.id] = True

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=lobby_text(lobby),
        reply_markup=lobby_keyboard(chat_id, include_bot_link=True),
        parse_mode="HTML"
    )
    lobby["message_id"] = msg.message_id
    try:
        await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
        lobby["pinned_message_id"] = msg.message_id
    except Exception as e:
        log.warning("Could not pin lobby message in chat %s: %s", chat_id, e)

    # Auto timeout task
    timeout_sec = int(settings.get("lobby_seconds", DEFAULT_LOBBY_SECONDS))
    cancel_lobby_timer(lobby)
    lobby["_timer_task"] = asyncio.create_task(_lobby_timer(context, chat_id, timeout_sec))

async def _lobby_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, seconds: int):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    lobby = lobbies.get(chat_id)
    if lobby and lobby.get("open") and chat_id not in games:
        lobbies.pop(chat_id, None)
        pinned_id = lobby.get("pinned_message_id")
        if pinned_id:
            try:
                await context.bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_id)
            except Exception:
                pass
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏳ Lobby vaqti tugadi va o'yin bekor qilindi."
            )
        except Exception:
            pass

async def start_game(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    lobby = lobbies.pop(chat_id, None)
    if not lobby:
        return
    cancel_lobby_timer(lobby)
    pinned_id = lobby.get("pinned_message_id")
    if pinned_id:
        try:
            await context.bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_id)
        except Exception:
            pass
    players = lobby.get("players", [])
    n = len(players)
    if n < MIN_PLAYERS:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ O'yin boshlash uchun kamida {MIN_PLAYERS} o'yinchi kerak!"
        )
        return

    # Taqsimot
    disabled = set()
    try:
        import json
        disabled = set(json.loads(lobby.get("settings", {}).get("disabled_roles", "[]")))
    except Exception:
        pass
    try:
        from database.models import get_bot_config
        global_dis = await get_bot_config("disabled_roles", "[]")
        if global_dis:
            disabled.update(json.loads(global_dis))
    except Exception:
        pass

    roles_list = choose_roles(n, disabled=disabled)
    if not roles_list or len(roles_list) != n:
        # Emergency fallback
        roles_list = ["Detektiv", "Doktor", "Boshliq", "Fuqaro"] * 10
        roles_list = roles_list[:n]

    player_roles = dict(zip(players, roles_list))

    # Partners mapping: Detective <-> Sheriff, Boss <-> Killer
    partners = {}
    det_uids = [u for u, r in player_roles.items() if r == "Detektiv"]
    sher_uids = [u for u, r in player_roles.items() if r == "Sherif"]
    boss_uids = [u for u, r in player_roles.items() if r == "Boshliq"]
    killer_uids = [u for u, r in player_roles.items() if r == "Qotil"]

    if det_uids and sher_uids:
        partners[det_uids[0]] = sher_uids[0]
        partners[sher_uids[0]] = det_uids[0]

    if boss_uids and killer_uids:
        partners[boss_uids[0]] = killer_uids[0]
        partners[killer_uids[0]] = boss_uids[0]

    game = {
        "chat": chat_id,
        "players": players,
        "names": lobby.get("names", {}),
        "badges": dict(lobby.get("badges", {})),
        "premium": dict(lobby.get("premium", {})),
        "settings": dict(lobby.get("settings", {})),
        "created_at": time.time(),
        "roles": player_roles,
        "alive": {u: True for u in players},
        "phase": "night",
        "night": 1,
        "partners": partners,
        "group_link": lobby.get("group_link"),
        "inactive": {u: 0 for u in players},
        "night_done": set(),
        "kill_targets": {},
        "protected": set(),
        "protected_by": {},
        "doctor_self_heal_used": {},
        "blocked_roles": {},
        "tourist_targets": {},
        "shadow_targets": {},
        "framer_targets": {},
        "joker_targets": {},
        "revenge_targets": {},
        "boy_offers": {},
        "boy_stolen_roles": {},
        "merchant_sales": {},
        "maniac_targets": {},
        "arsonist_doused": set(),
        "arsonist_action": {},
        "lawyer_clients": {},
        "mayor_revealed": set(),
        "detective_results": {},
        "votes": {},
        "weather": None,
        "_finish_started": False,
        "_waiting_king": False,
        "_resolving_night": False,
        "_db_id": None
    }
    games[chat_id] = game
    await save_runtime(game)

    # Guruhga start e'loni
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "✨ *O'yin boshlandi!*\n\n"
            f"👥 Ishtirokchilar: {n} nafar\n"
            "📩 Barcha o'yinchilarga shaxsiy xabarda (PM) rollar yuborildi.\n\n"
            "🌙 Shahar uyquga ketmoqda... Tungi harakatlar boshlandi!"
        ),
        reply_markup=InlineKeyboardMarkup([
            [bot_action_button(chat_id, "💬 Botga o'tish (Amallar/Ovoz)")]
        ]),
        parse_mode="Markdown"
    )

    # Shaxsiy xabarda har bir o'yinchiga to'liq taktik rol yo'riqnomasini yuborish
    from phases.night import start_night
    return_kb = return_to_group_keyboard(game)
    for uid in players:
        role_name = player_roles[uid]
        partner_id = partners.get(uid)
        partner_text = ""
        if ROLES.get(role_name) == "red":
            other_mafia = [
                f"{escape_md(lobby['names'].get(u, f'Oʻyinchi_{u}'))} ({player_roles.get(u)})"
                for u in players if u != uid and ROLES.get(player_roles.get(u)) == "red"
            ]
            if other_mafia:
                partner_text = "\n🤝 *Mafiya a'zolari:*\n• " + "\n• ".join(other_mafia)
        elif partner_id:
            p_name = escape_md(lobby["names"].get(partner_id, "Sherigingiz"))
            p_role = player_roles.get(partner_id, "")
            partner_text = f"\n🤝 *Sherigingiz:* {p_name} ({p_role})"

        dossier_text = format_role_dossier(role_name, partner_text=partner_text)
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=dossier_text,
                reply_markup=return_kb,
                parse_mode="Markdown"
            )
        except Exception as e:
            log.warning("Could not send dossier with Markdown to %s (%s), retrying plain text", uid, e)
            try:
                plain_dossier = dossier_text.replace("*", "").replace("_", "")
                await context.bot.send_message(
                    chat_id=uid,
                    text=plain_dossier,
                    reply_markup=return_kb,
                    parse_mode=None
                )
            except Exception as e2:
                log.warning("Could not send dossier to %s: %s", uid, e2)

    # Tunni boshlash
    await start_night(context, game)
