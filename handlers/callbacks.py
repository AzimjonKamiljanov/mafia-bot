import logging
import html
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import MIN_PLAYERS
from database.db import get_db
from database.models import (
    ensure_user, get_user, change_balance, add_item, get_badge, is_admin, record_afterlife_bet, get_will, now_iso
)
from core.engine import (
    games, lobbies, find_game_by_user, display_name, save_runtime,
    abort_game, abort_lobby, cancel_game_timer, cancel_lobby_timer
)
from core.graveyard import graveyard_menu_keyboard, graveyard_status_text
from roles.base import is_valid_role_action
from phases.lobby import start_game, lobby_text, lobby_keyboard
from phases.night import (
    get_target_selection_keyboard, resolve_night, complete_night_resolution,
    get_role_action_buttons, handle_king_decision
)
from phases.voting import start_voting, finish_voting
from phases.verdict import resolve_verdict
from handlers.commands import (
    main_menu_keyboard, profile_cmd, balance_cmd, rating_cmd, guide_cmd, will_cmd
)
from handlers.shop import shop_main_keyboard, shop_callback_handler
from core.last_words import LAST_WORD_TEMPLATES, deliver_last_words
from core.atmospheric_feed import broadcast_role_action
from core.afk_penalty import record_player_activity
from core.navigation import return_to_group_keyboard
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.handlers.callbacks")

def check_night_completed(game: Dict[str, Any]) -> bool:
    from config import NIGHT_ACTIVE_ROLES
    det_alive = any(
        game.get("alive", {}).get(u, False) and game.get("roles", {}).get(u) == "Detektiv"
        for u in game.get("players", [])
    )
    active_alive = []
    for u in game.get("players", []):
        if not game.get("alive", {}).get(u, False):
            continue
        role = game.get("roles", {}).get(u)
        # While Detective is alive, Sheriff has no active abilities and cannot act
        if role == "Sherif" and det_alive and u not in game.get("sheriff_promoted", set()):
            continue
        if role in NIGHT_ACTIVE_ROLES:
            active_alive.append(u)
    return bool(active_alive) and all(u in game.get("night_done", set()) for u in active_alive)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    data = q.data
    user = q.from_user
    uid = user.id
    await ensure_user(user)

    from core.rate_limiter import is_rate_limited
    if is_rate_limited(uid, action="cb", max_rate=12, window_seconds=2.0):
        try:
            await q.answer("⏳ Iltimos, tugmalarni juda tez bosmang!", show_alert=False)
        except Exception:
            pass
        return

    # Settings callbacks
    if data.startswith("sett:"):
        from handlers.settings import handle_settings_callback
        if await handle_settings_callback(update, context):
            return

    # Admin callbacks
    if data.startswith("adm:"):
        from handlers.admin_panel import handle_admin_callback
        if await handle_admin_callback(update, context):
            return

    # Admin AI grant confirmation callbacks
    if data.startswith("adm_grant_confirm:") or data.startswith("adm_grant_cancel:"):
        token = data.split(":", 1)[1]
        from handlers.admin_ai import pending_admin_grants

        if not is_admin(uid):
            await q.answer("❌ Bu amal faqat Master Admin uchun!", show_alert=True)
            return

        grant = pending_admin_grants.get(token)
        if not grant or (time.time() - grant.get("created_at", 0) > 300):
            pending_admin_grants.pop(token, None)
            await q.answer("❌ Ushbu so'rov eskirgan yoki topilmadi.", show_alert=True)
            try:
                await q.edit_message_text("⚠️ Ushbu operatsiya bekor qilingan yoki muddati o'tgan.")
            except Exception:
                pass
            return

        if grant["admin_id"] != uid:
            await q.answer("❌ Bu so'rovni faqat uni yaratgan admin tasdiqlashi mumkin!", show_alert=True)
            return

        if data.startswith("adm_grant_cancel:"):
            pending_admin_grants.pop(token, None)
            await q.answer("Operatsiya bekor qilindi.")
            await q.edit_message_text("❌ Operatsiya admin tomonidan bekor qilindi.")
            return

        pending_admin_grants.pop(token, None)
        target_id = grant["target_id"]
        db = await get_db()
        now = now_iso()

        if grant["kind"] == "currency":
            curr = grant["currency"]
            amt = grant["amount"]
            note = f"Super Admin {uid} AI grant"
            await change_balance(target_id, curr, amt, note)
            await db.execute("""
                INSERT INTO transactions (user_id, kind, amount, currency, note, created_at)
                VALUES (?, 'admin_grant', ?, ?, ?, ?)
            """, (target_id, amt, curr, note, now))
            await db.commit()
            curr_title = "Gold 🟡" if curr == "gold" else "Coin 💰"
            await q.answer("✅ Muvaffaqiyatli o'tkazildi!")
            await q.edit_message_text(
                "👑 <b>AI MASTER: MABLAG' O'TKAZMASI</b>\n\n"
                f"👤 <b>Qabul qiluvchi:</b> <code>{target_id}</code>\n"
                f"💎 <b>Miqdor:</b> +{amt} {curr_title}\n\n"
                "<blockquote>Mablag' muvaffaqiyatli to'ldirildi va audit logiga "
                "(admin_grant) kiritildi! ✨</blockquote>",
                parse_mode="HTML"
            )
            return
        elif grant["kind"] == "item":
            item_key = grant["item_key"]
            count = grant["count"]
            item_title = grant["item_title"]
            note = f"Super Admin {uid} AI item grant"
            await add_item(target_id, item_key, count)
            await db.execute("""
                INSERT INTO transactions (user_id, kind, amount, currency, note, created_at)
                VALUES (?, 'admin_grant', ?, ?, ?, ?)
            """, (target_id, count, f"item:{item_key}", note, now))
            await db.commit()
            await q.answer("✅ Buyum topshirildi!")
            await q.edit_message_text(
                "👑 <b>AI MASTER: BUYUM TAQDIM ETILDI</b>\n\n"
                f"👤 <b>Foydalanuvchi:</b> <code>{target_id}</code>\n"
                f"📦 <b>Buyum:</b> {item_title} (x{count})\n\n"
                "<blockquote>Buyum foydalanuvchi inventariga muvaffaqiyatli qo'shildi va "
                "audit logiga (admin_grant) kiritildi! 🎒✨</blockquote>",
                parse_mode="HTML"
            )
            return

    # Social callbacks (Para / Bro accept or reject)
    if data.startswith("soc_acc:") or data.startswith("soc_rej:"):
        parts = data.split(":")
        is_accept = data.startswith("soc_acc:")
        req_id = int(parts[1])
        tgt_id = int(parts[2])
        kind = parts[3]
        orig_chat_id = int(parts[4])

        if uid != tgt_id:
            await q.answer("❌ Bu taklif sizga tegishli emas!", show_alert=True)
            return

        from handlers.social import pending_social_proposals
        prop_key = (req_id, tgt_id, kind)
        prop = pending_social_proposals.pop(prop_key, None)

        req_user = await get_user(req_id)
        req_name = req_user["name"] if req_user else f"Foydalanuvchi_{req_id}"
        tgt_name = user.full_name or user.first_name
        kind_title = "juftlik (Para)" if kind == "para" else "birodarlik (Bro)"

        if not is_accept:
            db = await get_db()
            await db.execute("DELETE FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = ?", (req_id, tgt_id, kind))
            await db.commit()
            await q.answer("Taklif rad etildi.")
            await q.edit_message_text(f"🔴 Siz <b>{html.escape(req_name)}</b>ning {kind_title} taklifini rad etdingiz.", parse_mode="HTML")
            try:
                await context.bot.send_message(
                    chat_id=req_id,
                    text=f"💔 <b>{html.escape(tgt_name)}</b> sizning {kind_title} taklifingizni rad etdi.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return

        # Check existing partners
        db = await get_db()
        async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = ?", (req_id, kind)) as cursor:
            req_has = await cursor.fetchone()
        async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = ?", (tgt_id, kind)) as cursor:
            tgt_has = await cursor.fetchone()

        if req_has or tgt_has:
            await db.execute("DELETE FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = ?", (req_id, tgt_id, kind))
            await db.commit()
            await q.answer("❌ Tomonlardan birida allaqachon bog'lanish mavjud!", show_alert=True)
            await q.edit_message_text("❌ Bog'lanish amalga oshmadi: tomonlardan birida allaqachon faol rishta mavjud.")
            return

        await db.execute("DELETE FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = ?", (req_id, tgt_id, kind))
        await db.execute("""
            INSERT INTO social_links (user_id, other_id, kind, created_at)
            VALUES (?, ?, ?, datetime('now')), (?, ?, ?, datetime('now'))
            ON CONFLICT DO NOTHING
        """, (req_id, tgt_id, kind, tgt_id, req_id, kind))
        await db.commit()

        await q.answer("🎉 Taklif qabul qilindi!")
        await q.edit_message_text(f"✅ Siz <b>{html.escape(req_name)}</b> bilan muvaffaqiyatli {kind_title} bo'ldingiz!", parse_mode="HTML")

        # Notify requester in PM
        try:
            await context.bot.send_message(
                chat_id=req_id,
                text=f"💍 <b>{html.escape(tgt_name)}</b> sizning {kind_title} taklifingizni qabul qildi!",
                parse_mode="HTML"
            )
        except Exception:
            pass

        # Announce in group
        try:
            icon = "💍" if kind == "para" else "🤝"
            term = "juftlik (Para)" if kind == "para" else "birodar (Bro)"
            await context.bot.send_message(
                chat_id=orig_chat_id,
                text=f"{icon} <b>{html.escape(req_name)}</b> va <b>{html.escape(tgt_name)}</b> muvaffaqiyatli {term} bo'ldilar!",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    # 0. Gold Drop Claim Callback
    if data.startswith("claim_gold:"):
        drop_id = data.split(":")[1]
        user_name = (user.full_name or user.first_name or "O'yinchi")[:40]
        from core.engine import claim_gold_drop
        ok, msg_text, drop = await claim_gold_drop(drop_id, uid, user_name)
        await q.answer(msg_text, show_alert=True)
        if not ok or not drop:
            return

        rem = drop["remaining"]
        tot = drop["total"]
        claimed_names = list(drop["claimed_by"].values())
        c_name = html.escape(drop["creator_name"])

        if rem > 0:
            recent_str = ", ".join(html.escape(n) for n in claimed_names[-5:])
            new_text = (
                f"🎁 <b>OLTIN SOVRIN (GOLD DROP)!</b>\n\n"
                f"👤 <b>{c_name}</b> guruhga <b>{tot} dona Gold</b> tashladi!\n"
                f"⚡️ Har bir ishtirokchi <b>1 donadan Gold</b> olishi mumkin.\n"
                f"Kim birinchi ulgursa, o'shaniki! Shoshiling!\n\n"
                f"💰 Qoldi: <b>{rem}/{tot} ta Gold</b>\n"
                f"🏃 So'nggi olganlar: {recent_str}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🎁 Gold olish (Qoldi: {rem})", callback_data=f"claim_gold:{drop_id}")]
            ])
        else:
            new_text = (
                f"🎉 <b>BARCHA GOLDLAR TERIB OLINDI!</b>\n\n"
                f"👤 <b>{c_name}</b> tashlagan <b>{tot} dona Gold</b> to'liq o'z egalarini topdi!\n\n"
                f"👥 Omadli ishtirokchilar ({len(claimed_names)} nafar):\n"
                + "\n".join(f"• 👤 {html.escape(n)}" for n in claimed_names[:15])
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Barcha Goldlar olindi", callback_data="drop_finished")]
            ])

        try:
            await q.edit_message_text(text=new_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        return

    if data == "drop_finished":
        await q.answer("✅ Ushbu tarqatishdagi barcha Goldlar olingan.", show_alert=True)
        return

    # 0.5. Last Words Callback (last_word:<key>:<uid>)
    if data.startswith("last_word:"):
        parts = data.split(":")
        word_key = parts[1]
        target_uid = int(parts[2])
        if uid != target_uid:
            await q.answer("❌ Bu sizning xabaringiz emas.", show_alert=True)
            return

        text = LAST_WORD_TEMPLATES.get(word_key, "Meni nohaq o'ldirdingiz!")
        game = find_game_by_user(uid)
        if game:
            await deliver_last_words(context, game, uid, text)
            await q.answer("✅ So'nggi so'zingiz shaharga yetkazildi!")
            try:
                await q.edit_message_text(
                    f"✅ <b>So'nggi so'zingiz butun shaharga yetkazildi:</b>\n«<i>{html.escape(text)}</i>»\n\nEndi guruhga qaytib o'yinni kuzatishingiz mumkin.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await q.answer("ℹ️ Faol o'yin topilmadi.")
        return

    # 1. Shop & Inventory callbacks
    if data.startswith("shop_") or data.startswith("buy_item:") or data.startswith("item:"):
        await shop_callback_handler(update, context)
        return

    # 1.1. In-game item activation callback (use_item:<item_id>:<chat_id>)
    if data.startswith("use_item:"):
        parts = data.split(":")
        item_id = parts[1]
        chat_id = int(parts[2])
        game = games.get(chat_id)
        if not game:
            await q.answer("❌ Faol o'yin topilmadi.", show_alert=True)
            return
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar buyum ishlata olmaydi.", show_alert=True)
            return

        from core.items import has_used_item, consume_game_item, ALREADY_USED_MSG
        if has_used_item(game, uid, item_id):
            await q.answer(ALREADY_USED_MSG, show_alert=True)
            return

        if item_id == "extra_vote":
            if game.get("phase") != "voting":
                await q.answer("❌ Qo'shimcha ovozni faqat ovoz berish paytida ishlatish mumkin!", show_alert=True)
                return
            success, msg = await consume_game_item(game, uid, "extra_vote")
            if not success:
                await q.answer(msg, show_alert=True)
                return
            game.setdefault("extra_votes", set()).add(uid)
            await q.answer("🗳️ Qo'shimcha ovoz faollashtirildi! Sizning ovozingiz 2 barobar hisoblanadi (O'yinda 1 marta).", show_alert=True)
            try:
                await q.message.reply_text(
                    "🗳️ <b>Qo'shimcha ovoz faollashtirildi!</b>\nUshbu ovoz berishda sizning ovozingiz 2 barobar hisoblanadi.\n⚠️ <i>Eslatma: Har bir o'yinda faqat 1 marta ishlatish mumkin.</i>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return

        success, msg = await consume_game_item(game, uid, item_id)
        await q.answer(msg, show_alert=True)
        return

    # 2. Main Menu Navigation
    if data in ("guide_roles", "menu_guide"):
        await q.answer()
        context.args = None
        await guide_cmd(update, context)
        return

    if data.startswith("menu_"):
        await q.answer()
        if data == "menu_main":
            adm = is_admin(uid, getattr(user, "username", ""))
            try:
                await q.edit_message_text(
                    "🏙️ <b>DETEKTIV MAFIA</b> bosh menyusi:\nKerakli bo'limni tanlang:",
                    reply_markup=main_menu_keyboard(adm),
                    parse_mode="HTML"
                )
            except Exception:
                await q.message.reply_text(
                    "🏙️ <b>DETEKTIV MAFIA</b> bosh menyusi:\nKerakli bo'limni tanlang:",
                    reply_markup=main_menu_keyboard(adm),
                    parse_mode="HTML"
                )
        elif data == "menu_game":
            from config import BOT_USERNAME
            add_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
            ])
            await q.message.reply_text(
                "🎮 <b>Mafia O'yini</b>\n\n"
                "Mafia o'yini faqat <b>Telegram guruhlarida</b> o'ynaladi.\n"
                "O'yin boshlash uchun botni guruhingizga qo'shing va guruhda <b>/game</b> buyrug'ini yuboring!",
                reply_markup=add_kb,
                parse_mode="HTML"
            )
        elif data == "menu_shop":
            try:
                await q.edit_message_text("🛒 Do'kon:", reply_markup=shop_main_keyboard())
            except Exception:
                await q.message.reply_text("🛒 Do'kon:", reply_markup=shop_main_keyboard())
        elif data == "menu_balance":
            await balance_cmd(update, context)
        elif data == "menu_rating":
            await rating_cmd(update, context)
        elif data == "menu_profile":
            await profile_cmd(update, context)
        elif data == "menu_will":
            await will_cmd(update, context)
        elif data == "menu_clan":
            from handlers.clans import clan_cmd
            await clan_cmd(update, context)
        return

    # 3. Lobby Callbacks
    if data.startswith("lobby_join:"):
        chat_id = int(data.split(":")[1])
        if chat_id in games:
            await q.answer("⚠️ Ushbu guruhda o'yin allaqachon boshlangan!", show_alert=True)
            return

        lobby = lobbies.get(chat_id)
        if not lobby or not lobby.get("open"):
            # Auto-restore lobby on this message if game not active
            import asyncio
            from config import DEFAULT_LOBBY_SECONDS
            from database.models import get_group_settings
            from core.engine import cancel_lobby_timer
            from phases.lobby import _lobby_timer
            from core.navigation import resolve_and_cache_group_link

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
            return

        existing_game = find_game_by_user(uid)
        if existing_game and existing_game.get("chat") != chat_id and existing_game.get("alive", {}).get(uid, False):
            await q.answer("⚠️ Siz boshqa guruhdagi faol o'yinda tiriksiz! Avval o'sha o'yinni tugating.", show_alert=True)
            return

        for other_cid, other_lob in lobbies.items():
            if other_cid != chat_id and uid in other_lob.get("players", []):
                await q.answer("⚠️ Siz boshqa guruhdagi ochiq lobbida kutmoqdasiz! Avval u yerdan chiqing.", show_alert=True)
                return

        from config import MAX_PLAYERS
        if len(lobby["players"]) >= MAX_PLAYERS:
            await q.answer("❌ Lobby to'lgan!", show_alert=True)
            return

        from database.models import track_group_member
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
        return

    if data.startswith("lobby_call:"):
        chat_id = int(data.split(":")[1])
        caller_name = (user.full_name or user.first_name)[:40]
        await q.answer("📢 O'yinchilar chaqirilmoqda...")
        from phases.lobby import call_players_in_chat
        await call_players_in_chat(context, chat_id, caller_name)
        return

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
        return

    if data.startswith("lobby_start:"):
        chat_id = int(data.split(":")[1])
        lobby = lobbies.get(chat_id)
        if not lobby or not lobby.get("open"):
            await q.answer("❌ Lobby yopilgan.", show_alert=True)
            return
        if uid not in lobby["players"]:
            await q.answer("❗ Avval o'yinga qo'shiling.", show_alert=True)
            return
        if len(lobby["players"]) < MIN_PLAYERS:
            await q.answer(f"❗ Kamida {MIN_PLAYERS} kishi kerak. Hozir: {len(lobby['players'])} ta.", show_alert=True)
            return
        await q.answer("▶️ O'yin boshlanmoqda...")
        await start_game(context, chat_id)
        return

    if data.startswith("lobby_stop:"):
        chat_id = int(data.split(":")[1])
        if not is_admin(uid):
            try:
                member = await context.bot.get_chat_member(chat_id, uid)
                if member.status not in ("administrator", "creator"):
                    await q.answer("❌ Faqat guruh adminlari to'xtata oladi.", show_alert=True)
                    return
            except Exception as e:
                log.warning("get_chat_member check failed on lobby_stop for %s in chat %s: %s", uid, chat_id, e)
                await q.answer("❌ Guruh adminlik huquqini tekshirib bo'lmadi. Ruxsat berilmadi.", show_alert=True)
                return
        abort_lobby(chat_id)
        await abort_game(chat_id)
        await q.answer("🛑 To'xtatildi.")
        try:
            await q.edit_message_text("🛑 <b>Lobby yoki o'yin to'xtatildi.</b>", parse_mode="HTML")
        except Exception:
            pass
        return

    # 4. Role Action in PM (act:<action>:<actor>)
    if data.startswith("act:"):
        parts = data.split(":")
        action = parts[1]
        actor = int(parts[2])

        # Strict identity check
        if q.from_user.id != actor:
            await q.answer("❌ Bu tugma siz uchun emas!", show_alert=True)
            return

        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Ushbu tugma muddati o'tgan yoki hozir tungi faza emas.", show_alert=True)
            return

        if not game.get("alive", {}).get(actor, False):
            await q.answer("💀 Halok bo'lganlar tunda harakat qila olmaydi.", show_alert=True)
            return

        actor_role = game.get("roles", {}).get(actor)
        if not is_valid_role_action(actor_role, action, game, actor):
            await q.answer("❌ Sizning rolingiz ushbu harakatni bajara olmaydi.", show_alert=True)
            return

        if action == "sleep":
            await q.answer("😴 Siz bu tun dam olishga qaror qildingiz.", show_alert=True)
            game.setdefault("night_done", set()).add(actor)
            record_player_activity(game, actor)
            from core.atmospheric_feed import broadcast_role_sleep
            await broadcast_role_sleep(context, game, actor)
            try:
                await q.edit_message_text(
                    "😴 *Bu tun hech kimni tanlamadingiz — dam oldingiz.*\nTong otishini kuting!",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            if check_night_completed(game):
                await resolve_night(context, game)
            return

        if action == "will_help":
            await q.answer()
            await q.message.reply_text(
                "📜 *Vasiyatnoma yozish:* Shaxsiy chatda `/will Mening vasiyatim...` buyrug'ini yuboring.\n"
                "U o'limingizdan so'ng guruhda e'lon qilinadi.",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="Markdown"
            )
            return

        if action == "ignite":
            await q.answer()
            game.setdefault("arsonist_action", {})["ignite"] = actor
            game.setdefault("night_done", set()).add(actor)
            record_player_activity(game, actor)
            await broadcast_role_action(context, game, actor, "ignite")
            await q.edit_message_text(
                "🔥 *BARCHASINI YOQISH BUYRUG'I BERILDI!* Tongda kerosin sepilgan barcha uylar yonadi.",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="Markdown"
            )
            return

        if action == "killer_assist":
            await q.answer("🔪 Boshliq nishon tanlamoqda, siz unga ko'maklashasiz.", show_alert=True)
            game.setdefault("night_done", set()).add(actor)
            record_player_activity(game, actor)
            await broadcast_role_action(context, game, actor, "killer_assist")
            try:
                await q.edit_message_text(
                    "🔪 *Boshliq nishon tanlamoqda.* Siz unga ko'maklashasiz.\nTong otishini kuting!",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return

        if action == "joker_laugh":
            await q.answer("🃏 Qahqahangiz butun shaharga tarqaldi!", show_alert=True)
            game.setdefault("night_done", set()).add(actor)
            record_player_activity(game, actor)
            await broadcast_role_action(context, game, actor, "joker_laugh")
            try:
                await q.edit_message_text(
                    "🃏 *Qahqahangiz butun shaharni larzaga keltirdi!*\nTong otishini kuting!",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return

        if action == "medium":
            await q.answer()
            dead_players = [u for u in game.get("players", []) if not game.get("alive", {}).get(u, False)]
            if not dead_players:
                await q.edit_message_text(
                    "🔮 *RUHLAR OLAMI BILAN BOG'LANISH*\n\n"
                    "Bu kecha qabriston sokin... Ruhlar olamida hali hech kim yo'q.\n"
                    "Shahar ahli hozircha to'liq tirik.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
                game.setdefault("night_done", set()).add(actor)
                record_player_activity(game, actor)
                await broadcast_role_action(context, game, actor, "medium")
                return

            dead_info = []
            for duid in dead_players:
                dname = display_name(game, duid)
                drole = game.get("roles", {}).get(duid, "Noma'lum")
                dwill = await get_will(duid)
                will_str = f' — "{dwill}"' if dwill else " (vasiyat qoldirmagan)"
                dead_info.append(f"• 👻 *{dname}* ({drole}){will_str}")

            info_text = (
                "🔮 *Ruhlar olami bilan bog'landingiz!*\n\n"
                "Qabristondagi marhumlar sizga o'z sirlarini shivirlashdi:\n"
                + "\n".join(dead_info) + "\n\n"
                "Ruhlar sizga yo'l ko'rsatdi. Shahar foydasiga to'g'ri xulosa chiqaring!"
            )
            await q.edit_message_text(
                info_text,
                reply_markup=return_to_group_keyboard(game),
                parse_mode="Markdown"
            )
            game.setdefault("night_done", set()).add(actor)
            record_player_activity(game, actor)
            await broadcast_role_action(context, game, actor, "medium")
            await save_runtime(game)
            return

        if action == "firibgar":
            await q.answer()
            from core.navigation import return_to_group_button
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🎭 Fuqaro", callback_data=f"disguise:{actor}:Fuqaro"),
                    InlineKeyboardButton("🎭 Detektiv", callback_data=f"disguise:{actor}:Detektiv")
                ],
                [
                    InlineKeyboardButton("🎭 Doktor", callback_data=f"disguise:{actor}:Doktor"),
                    InlineKeyboardButton("🎭 Boshliq", callback_data=f"disguise:{actor}:Boshliq")
                ],
                [
                    return_to_group_button(game)
                ]
            ])
            await q.edit_message_text("🎪 Tekshiruvchilarni chalg'itish uchun soxta qiyofani tanlang:", reply_markup=kb)
            return

        await q.answer()
        kb = get_target_selection_keyboard(game, actor, action)
        await q.edit_message_text(
            f"🎯 *{action.upper()}* uchun nishonni tanlang:",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return

    # 4.5. Disguise selection for Firibgar
    if data.startswith("disguise:"):
        parts = data.split(":")
        actor = int(parts[1])
        chosen_role = parts[2]

        if q.from_user.id != actor:
            await q.answer("❌ Bu tugma siz uchun emas!", show_alert=True)
            return

        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Ushbu tugma muddati o'tgan yoki hozir tungi faza emas.", show_alert=True)
            return

        if not game.get("alive", {}).get(actor, False):
            await q.answer("💀 Halok bo'lganlar harakat qila olmaydi.", show_alert=True)
            return

        if game.get("roles", {}).get(actor) != "Firibgar":
            await q.answer("❌ Faqat Firibgar soxta qiyofa tanlay oladi.", show_alert=True)
            return

        from config import ROLES
        if chosen_role not in ROLES:
            await q.answer("❌ Noto'g'ri rol tanlandi.", show_alert=True)
            return

        game.setdefault("firibgar_disguises", {})[actor] = chosen_role
        game.setdefault("night_done", set()).add(actor)
        record_player_activity(game, actor)
        await broadcast_role_action(context, game, actor, "firibgar")
        await q.answer("🎭 Soxta qiyofa tanlandi!")
        await q.edit_message_text(
            f"✅ Siz bu kecha *{chosen_role}* qiyofasidasiz!\nDetektiv yoki Sherif sizni tekshirganda aynan shu rolni ko'radi.",
            reply_markup=return_to_group_keyboard(game),
            parse_mode="Markdown"
        )
        await save_runtime(game)
        return

    # 5. Target Selection in PM (tgt:<action>:<actor>:<target>)
    if data.startswith("tgt:"):
        parts = data.split(":")
        action = parts[1]
        actor = int(parts[2])
        target = int(parts[3])

        if q.from_user.id != actor:
            await q.answer("❌ Bu tugma siz uchun emas!", show_alert=True)
            return

        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Ushbu tugma muddati o'tgan yoki hozir tungi faza emas.", show_alert=True)
            return

        if not game.get("alive", {}).get(actor, False):
            await q.answer("💀 Halok bo'lganlar tunda harakat qila olmaydi.", show_alert=True)
            return

        actor_role = game.get("roles", {}).get(actor)
        if not is_valid_role_action(actor_role, action, game, actor):
            await q.answer("❌ Sizning rolingiz ushbu harakatni bajara olmaydi.", show_alert=True)
            return

        # Target validation
        if target not in game.get("players", []):
            await q.answer("❌ Tanlangan o'yinchi bu o'yinda qatnashmayapti.", show_alert=True)
            return

        if not game.get("alive", {}).get(target, False):
            await q.answer("❌ Tanlangan o'yinchi allaqachon vafot etgan!", show_alert=True)
            return

        if target == actor:
            if action in ("protect", "guard"):
                if actor in game.get("self_protect_used", set()) or game.get("doctor_self_heal_used", {}).get(actor, False):
                    await q.answer("❌ O'zingizni himoya qilishdan faqat 1 marta foydalana olasiz!", show_alert=True)
                    return
            elif action != "will_help":
                await q.answer("❌ O'zingizni tanlay olmaysiz!", show_alert=True)
                return

        from config import ROLES
        if action == "kill" and ROLES.get(game.get("roles", {}).get(target)) == "red":
            await q.answer("❌ Mafiya a'zosi o'z sherigiga hujum qila olmaydi!", show_alert=True)
            return

        tgt_name = display_name(game, target)
        await q.answer(f"✅ Nishon tanlandi: {tgt_name}")

        if action in ("kill", "detective_shoot"):
            game.setdefault("kill_targets", {})[actor] = target
        elif action == "detective":
            game.setdefault("detective_results", {})[str(actor)] = {"target": target}
        elif action == "sheriff_check":
            det_alive = any(
                game.get("alive", {}).get(u, False) and game.get("roles", {}).get(u) == "Detektiv"
                for u in game.get("players", [])
            )
            if det_alive and actor not in game.get("sheriff_promoted", set()):
                await q.answer("❌ Detektiv tirik bo'lgan paytda Sherif qobiliyati faol emas!", show_alert=True)
                return
            from config import ROLES
            from core.items import has_used_item, mark_item_used, is_item_armed, disarm_item
            is_red = (ROLES.get(game["roles"].get(target)) == "red")
            if is_red:
                fake_doc_used = False
                if is_item_armed(game, target, "fake_document"):
                    disarm_item(game, target, "fake_document")
                    fake_doc_used = True
                elif not has_used_item(game, target, "fake_document"):
                    from database.models import take_item
                    if await take_item(target, "fake_document", 1):
                        mark_item_used(game, target, "fake_document")
                        fake_doc_used = True
                else:
                    from database.models import get_inventory
                    inv = await get_inventory(target)
                    if inv.get("fake_document", 0) > 0:
                        try:
                            await context.bot.send_message(
                                chat_id=target,
                                text="⚠️ Siz ushbu o'yinda bu buyumdan (Soxta hujjat) allaqachon foydalangansiz! Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                                reply_markup=return_to_group_keyboard(game),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

                if fake_doc_used:
                    is_red = False
                    try:
                        await context.bot.send_message(
                            chat_id=target,
                            text=f"{tg_emoji('item_doc', '📄', 'SHOP')} <b>SOXTA HUJJAT ISHLADI!</b> Sherif sizni tekshirdi, ammo soxta hujjatingiz tufayli sizni oddiy fuqaro deb bildi (1 ta hujjat sarflandi).\n⚠️ <b>Eslatma:</b> Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                            reply_markup=return_to_group_keyboard(game),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
            team_str = f"{tg_emoji('mafia_team', '🔴')} <b>QIZIL JAMOA (MAFIA)</b>" if is_red else f"{tg_emoji('civilian_team', '🔵')} <b>QIZIL EMAS (TINCH FUQARO)</b>"
            await q.message.reply_text(
                f"{tg_emoji('sheriff', '👮‍♂️')} <b>SHERIF TEKSHIRUVI:</b>\n\n👤 {html.escape(tgt_name)} — {team_str}",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="HTML"
            )
        elif action == "protect":
            if target == actor:
                if actor in game.setdefault("self_protect_used", set()) or game.get("doctor_self_heal_used", {}).get(actor, False):
                    await q.answer("❌ O'zingizni davolashdan har o'yinda faqat 1 marta foydalana olasiz!", show_alert=True)
                    return
                game["self_protect_used"].add(actor)
                game.setdefault("doctor_self_heal_used", {})[actor] = True
            else:
                game.setdefault("self_protect_used", set()).discard(actor)
                if actor in game.get("doctor_self_heal_used", {}):
                    game["doctor_self_heal_used"][actor] = False
            game.setdefault("protected", set()).add(target)
            game.setdefault("protected_by", {})[target] = actor
        elif action == "guard":
            if target == actor:
                if actor in game.setdefault("self_protect_used", set()):
                    await q.answer("❌ O'zingizni himoya qilishdan har o'yinda faqat 1 marta foydalana olasiz!", show_alert=True)
                    return
                game["self_protect_used"].add(actor)
            else:
                game.setdefault("self_protect_used", set()).discard(actor)
            game.setdefault("guarded_by", {})[target] = actor
        elif action == "lawyer":
            game.setdefault("lawyer_clients", {})[actor] = target
        elif action == "tourist":
            game.setdefault("tourist_targets", {})[actor] = target
        elif action == "block":
            game.setdefault("blocked_roles", {})[target] = actor
        elif action == "shadow":
            game.setdefault("shadow_targets", {})[actor] = target
        elif action == "frame":
            game.setdefault("framer_targets", {})[actor] = target
        elif action == "maniac_kill":
            game.setdefault("maniac_targets", {})[actor] = target
        elif action == "douse":
            game.setdefault("arsonist_doused", set()).add(target)
        elif action == "coin_thief":
            game.setdefault("coin_thief_targets", {})[actor] = target
        elif action == "revenge":
            game.setdefault("revenge_targets", {})[actor] = target
        elif action == "boy":
            u = await get_user(actor)
            coins = int(u.get("coin", 0)) if u else 0
            if coins < 50:
                await q.message.reply_text("❌ Rolni ijaraga olish uchun kamida 50 Coin kerak.")
                return
            await change_balance(actor, "coin", -50, "Boy rolni ijaraga oldi")
            await change_balance(target, "coin", 50, "Boydan 50 Coin ijara haqi")
            tgt_role = game["roles"].get(target, "Fuqaro")
            game.setdefault("boy_stolen_roles", {})[actor] = {
                "role": tgt_role,
                "night": game.get("night", 1),
                "accepted": True
            }
            await q.edit_message_text(
                f"💎 *{tgt_name}*ning qobiliyati (*{tgt_role}*) 50 Coin evaziga 1 tunga ijaraga olindi!\n"
                "Endi uning qobiliyatidan foydalanishingiz mumkin.",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="Markdown"
            )
            kb = get_role_action_buttons(game, actor)
            if kb:
                try:
                    await context.bot.send_message(
                        chat_id=actor,
                        text=f"🎭 *Ijaraga olingan rol:* {tgt_role}\nAmalni tanlang:",
                        reply_markup=kb
                    )
                except Exception:
                    pass
            try:
                await context.bot.send_message(
                    chat_id=target,
                    text="💰 *Boy sizning rolingizni 1 tunga ijaraga oldi va sizga 50 Coin to'ladi!*",
                    reply_markup=return_to_group_keyboard(game)
                )
            except Exception:
                pass
            record_player_activity(game, actor)
            await broadcast_role_action(context, game, actor, "boy")
            return
        elif action == "merchant":
            await add_item(target, "protection", 1)
            record_player_activity(game, actor)
            await broadcast_role_action(context, game, actor, "merchant")
            game.setdefault("night_done", set()).add(actor)
            try:
                await context.bot.send_message(
                    chat_id=target,
                    text="🛒 *Savdogar sizga bepul tungi himoya qalqonini (Protection) sovg'a qildi!*",
                    reply_markup=return_to_group_keyboard(game)
                )
            except Exception:
                pass
            await q.edit_message_text(
                f"🛒 *{tgt_name}*ga bepul tungi himoya qalqoni (Protection) taqdim etildi!\n\nEndi guruhga qaytib muhokamani davom ettirishingiz mumkin.",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="Markdown"
            )
            await save_runtime(game)
            if check_night_completed(game):
                await resolve_night(context, game)
            return

        game.setdefault("night_done", set()).add(actor)
        record_player_activity(game, actor)
        await broadcast_role_action(context, game, actor, action)
        await q.edit_message_text(
            f"✅ Amal qabul qilindi! Nishon: *{tgt_name}*.\n\nEndi guruhga qaytib muhokamani davom ettirishingiz mumkin.",
            reply_markup=return_to_group_keyboard(game),
            parse_mode="Markdown"
        )
        await save_runtime(game)

        # Fast forward if all active alive have acted
        if check_night_completed(game):
            await resolve_night(context, game)
        return

    # 6. Cancel Action
    if data == "cancel_action":
        await q.answer("❌ Bekor qilindi.")
        game_cur = find_game_by_user(uid)
        await q.edit_message_text(
            "Amal bekor qilindi.",
            reply_markup=return_to_group_keyboard(game_cur) if game_cur else None
        )
        return

    # 7. Day to Vote early transition
    if data.startswith("day_to_vote:"):
        chat_id = int(data.split(":")[1])
        game = games.get(chat_id)
        if game and game.get("phase") == "day":
            await q.answer("🗳️ Ovoz berishga o'tilmoqda...")
            await start_voting(context, game)
        else:
            await q.answer("ℹ️ Hozir muhokama vaqti emas.", show_alert=True)
        return

    # 8. Voting Callback (vote:<chat_id>:<target>)
    if data.startswith("vote:"):
        parts = data.split(":")
        chat_id = int(parts[1])
        target_str = parts[2]
        game = games.get(chat_id)
        if not game or game.get("phase") != "voting":
            await q.answer("❌ Ovoz berish muddati o'tgan yoki yakunlangan.", show_alert=True)
            return
        if uid not in game.get("players", []):
            await q.answer("❌ Siz bu o'yinda qatnashmayapsiz.", show_alert=True)
            return
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar ovoz bera olmaydi.", show_alert=True)
            return

        # Target validation
        if target_str != "none":
            try:
                target_id = int(target_str)
            except ValueError:
                await q.answer("❌ Noto'g'ri nishon tanlandi.", show_alert=True)
                return
            if target_id == uid:
                await q.answer("❌ O'zingizga ovoz bera olmaysiz!", show_alert=True)
                return
            if target_id not in game.get("players", []) or not game.get("alive", {}).get(target_id, False):
                await q.answer("❌ Tanlangan o'yinchi tirik emas yoki o'yinda yo'q!", show_alert=True)
                return

        # 1 kishi faqat 1 marta ovoz berishi shart!
        if uid in game.get("votes", {}):
            prev_target = game["votes"][uid]
            prev_name = "🕊️ Hech kimga" if prev_target == "none" else display_name(game, int(prev_target))
            await q.answer(f"⚠️ Siz allaqachon ovoz bergansiz ({prev_name})!\nHar bir o'yinchi faqat 1 marta ovoz bera oladi.", show_alert=True)
            return

        game.setdefault("votes", {})[uid] = target_str
        record_player_activity(game, uid)
        target_name = "🕊️ Hech kimga" if target_str == "none" else display_name(game, int(target_str))
        voter_name = display_name(game, uid)
        await q.answer(f"✅ Ovozingiz qabul qilindi: {target_name}", show_alert=True)

        if q.message and q.message.chat.type == "private":
            try:
                await q.edit_message_text(
                    f"✅ Ovozingiz qabul qilindi: *{target_name}*.\n\nEndi guruhga qaytib muhokamani davom ettirishingiz mumkin.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{tg_emoji('voting', '🧊')} <b>{html.escape(voter_name)}</b> gumon qildi: <b>{html.escape(target_name)}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

        alive_count = sum(1 for v in game["alive"].values() if v)
        if len(game.get("votes", {})) >= alive_count:
            await finish_voting(context, game)
        return

    # 9. Verdict Callback (verdict:<chat_id>:<accused>:<kill/forgive>)
    if data.startswith("verdict:"):
        parts = data.split(":")
        chat_id = int(parts[1])
        accused = int(parts[2])
        choice = parts[3]
        game = games.get(chat_id)
        if not game or game.get("phase") != "verdict":
            await q.answer("❌ Sud hukmi muddati o'tgan yoki yakunlangan.", show_alert=True)
            return
        if uid not in game.get("players", []):
            await q.answer("❌ Siz bu o'yinda qatnashmayapsiz.", show_alert=True)
            return
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar sud ovozida qatnasha olmaydi.", show_alert=True)
            return
        if uid == accused:
            await q.answer("❌ Sudlanuvchi o'z hukmida ovoz bera olmaydi!", show_alert=True)
            return
        if choice not in ("kill", "forgive"):
            await q.answer("❌ Noto'g'ri hukm tanlovi.", show_alert=True)
            return
        if not game.get("alive", {}).get(accused, False) or accused != game.get("accused_uid"):
            await q.answer("❌ Sudlanuvchi tirik emas yoki sud jarayoni yakunlangan.", show_alert=True)
            return

        game.setdefault("verdict_votes", {})[uid] = choice
        record_player_activity(game, uid)
        choice_str = "⚔️ QATL ETISH" if choice == "kill" else "🕊️ AVF ETISH"
        voter_name = display_name(game, uid)
        await q.answer(f"✅ Ovozingiz qayd etildi: {choice_str}", show_alert=True)

        if q.message and q.message.chat.type == "private":
            try:
                await q.edit_message_text(
                    f"✅ Sud hukmingiz qayd etildi: <b>{choice_str}</b>.\n\nEndi guruhga qaytib natijani kuting.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="HTML"
                )
            except Exception:
                pass

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{tg_emoji('voting', '⚖️')} <b>{html.escape(voter_name)}</b> hukm chiqardi: <b>{choice_str}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

        # Accused doesn't vote, so required count is alive_count - 1
        alive_count = sum(1 for v in game["alive"].values() if v)
        req_count = alive_count - 1 if game.get("alive", {}).get(accused, False) else alive_count
        if len(game.get("verdict_votes", {})) >= max(1, req_count):
            await resolve_verdict(context, game)
        return

    # 10. King Decision Callback (king_kill / king_forgive)
    if data.startswith("king_kill:") or data.startswith("king_forgive:"):
        parts = data.split(":")
        king_uid = int(parts[1])
        attacker_uid = int(parts[2])
        game = find_game_by_user(king_uid)
        if not game:
            await q.answer("❌ O'yin topilmadi.")
            return

        if not game.get("_waiting_king"):
            await q.answer("ℹ️ Qaror qabul qilish vaqti o'tib ketgan.", show_alert=True)
            return

        is_kill = data.startswith("king_kill:")
        if is_kill:
            try:
                await q.edit_message_text(
                    f"⚔️ *QIROLNING QAT'IY HUKMI:* Hujumchi *{display_name(game, attacker_uid)}* qatl etildi!\n\nEndi guruhga qaytib natijani kuting.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            try:
                await q.edit_message_text(
                    f"🕊️ *QIROLNING MARHAMATI:* Hujumchi *{display_name(game, attacker_uid)}* avf etildi.\n\nEndi guruhga qaytib natijani kuting.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        await handle_king_decision(context, game, king_uid, attacker_uid, is_kill=is_kill, is_timeout=False)
        return

    # 11. Mayor Reveal Callback (mayor_reveal:<chat_id>)
    if data.startswith("mayor_reveal:"):
        chat_id = int(data.split(":")[1])
        game = games.get(chat_id)
        if not game:
            await q.answer("❌ O'yin topilmadi.", show_alert=True)
            return
        if game.get("roles", {}).get(uid) != "Mer":
            await q.answer("❌ Siz shahar meri emassiz!", show_alert=True)
            return
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar o'zini oshkor qila olmaydi.", show_alert=True)
            return
        if uid in game.get("mayor_revealed", set()):
            await q.answer("ℹ️ Siz allaqachon mer ekanligingizni e'lon qilgansiz.", show_alert=True)
            return

        game.setdefault("mayor_revealed", set()).add(uid)
        await q.answer("🎖️ Siz shahar hokimi sifatida o'zingizni oshkor qildingiz!", show_alert=True)
        m_name = display_name(game, uid)
        announcement = (
            "👑 *Shahar hokimi (Mer) oshkor bo'ldi!*\n\n"
            f"👤 *{m_name}* rasman shahar hokimi ekanligini e'lon qildi!\n"
            "Uning har bir ovozi bundan buyon *3 ta ovoz* kuchiga teng bo'ladi."
        )
        await context.bot.send_message(chat_id=chat_id, text=announcement)
        await save_runtime(game)
        return

    # 12. Graveyard Refresh Callback (grave_refresh:<game_id>)
    if data.startswith("grave_refresh:"):
        parts = data.split(":")
        game_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        game = find_game_by_user(uid)
        if not game and game_id:
            for g in games.values():
                if g.get("_db_id") == game_id:
                    game = g
                    break
        if not game and games:
            game = list(games.values())[0]

        if game:
            await q.answer("🔄 Yangilandi.")
            try:
                await q.edit_message_text(
                    text=graveyard_status_text(game, uid),
                    reply_markup=graveyard_menu_keyboard(game.get("_db_id", 0), group_link=game.get("group_link"))
                )
            except Exception:
                pass
        else:
            await q.answer("ℹ️ Faol o'yin topilmadi.", show_alert=True)
        return

    # 13. Graveyard Afterlife Bet (grave_bet:<game_id>:<team>:<amount>)
    if data.startswith("grave_bet:"):
        parts = data.split(":")
        game_id = int(parts[1])
        team = parts[2]
        amount = int(parts[3])
        if await record_afterlife_bet(game_id, uid, team, amount):
            await q.answer(f"✅ 50 Coin {team.upper()} g'alabasiga tikildi (2x yutuq)!", show_alert=True)
        else:
            await q.answer("❌ Balansingizda Coin yetarli emas.", show_alert=True)
        return
