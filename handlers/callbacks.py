import logging
import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import MIN_PLAYERS
from database.models import (
    ensure_user, get_user, change_balance, add_item, get_badge, is_admin, record_afterlife_bet, get_will
)
from core.engine import (
    games, lobbies, find_game_by_user, display_name, save_runtime
)
from core.graveyard import graveyard_menu_keyboard, graveyard_status_text
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

log = logging.getLogger("detektiv.handlers.callbacks")

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    data = q.data
    user = q.from_user
    uid = user.id
    await ensure_user(user)

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

    # 0. Gold Drop Claim Callback
    if data.startswith("claim_gold:"):
        drop_id = data.split(":")[1]
        from core.engine import active_drops
        drop = active_drops.get(drop_id)
        if not drop:
            await q.answer("❌ Ushbu Gold tarqatish yakunlangan yoki mavjud emas.", show_alert=True)
            return

        if uid in drop["claimed_by"]:
            await q.answer("ℹ️ Siz ushbu tarqatishdan allaqachon 1 dona Gold olgansiz!", show_alert=True)
            return

        if drop["remaining"] <= 0:
            await q.answer("😔 Kech qoldingiz! Barcha Goldlar terib olindi.", show_alert=True)
            return

        # Give 1 Gold to user
        user_name = (user.full_name or user.first_name)[:40]
        drop["claimed_by"][uid] = user_name
        drop["remaining"] -= 1
        await change_balance(uid, "gold", 1, f"Gold Drop {drop_id}")
        await q.answer("🎉 Tabriklaymiz! Siz 1 dona Gold oldingiz!", show_alert=True)

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

    # 2. Main Menu Navigation
    if data.startswith("menu_"):
        await q.answer()
        if data == "menu_main":
            await q.edit_message_text(
                "🏙️ *DETEKTIV MAFIA* bosh menyusi:\nKerakli bo'limni tanlang:",
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown"
            )
        elif data == "menu_game":
            await q.message.reply_text("🎮 Guruhda o'yin ochish uchun guruhga /game buyrug'ini yuboring!")
        elif data == "menu_shop":
            await q.edit_message_text("🛒 Do'kon:", reply_markup=shop_main_keyboard())
        elif data == "menu_balance":
            await balance_cmd(update, context)
        elif data == "menu_rating":
            await rating_cmd(update, context)
        elif data == "menu_profile":
            await profile_cmd(update, context)
        elif data == "menu_will":
            await will_cmd(update, context)
        elif data == "menu_guide":
            await guide_cmd(update, context)
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
            except Exception:
                pass
        lobbies.pop(chat_id, None)
        games.pop(chat_id, None)
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
        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Hozir tungi faza emas.", show_alert=True)
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
        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Hozir tungi faza emas.", show_alert=True)
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
        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Hozir tungi faza emas.", show_alert=True)
            return

        tgt_name = display_name(game, target)
        await q.answer(f"✅ Nishon tanlandi: {tgt_name}")

        if action in ("kill", "detective_shoot"):
            game.setdefault("kill_targets", {})[actor] = target
        elif action == "detective":
            game.setdefault("detective_results", {})[str(actor)] = {"target": target}
        elif action == "sheriff_check":
            from config import ROLES
            is_red = (ROLES.get(game["roles"].get(target)) == "red")
            team_str = "🔴 QIZIL JAMOA (MAFIA)" if is_red else "🔵 QIZIL EMAS (TINCH FUQARO)"
            await q.message.reply_text(
                f"👮 *SHERIF TEKSHIRUVI:*\n\n👤 {tgt_name} — {team_str}",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="Markdown"
            )
        elif action == "protect":
            game.setdefault("protected", set()).add(target)
            game.setdefault("protected_by", {})[target] = actor
        elif action == "guard":
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
            active_alive = [
                u for u in game.get("players", [])
                if game.get("alive", {}).get(u, False) and game.get("roles", {}).get(u) in (
                    "Detektiv", "Sherif", "Doktor", "Tansoqchi", "Boshliq", "Maniak", "Pirotexnik", "Begona", "Maftunkor", "Ruhshunos", "Firibgar"
                )
            ]
            if all(u in game.get("night_done", set()) for u in active_alive):
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
        active_alive = [
            u for u in game.get("players", [])
            if game.get("alive", {}).get(u, False) and game.get("roles", {}).get(u) in (
                "Detektiv", "Sherif", "Doktor", "Tansoqchi", "Boshliq", "Maniak", "Pirotexnik", "Begona", "Maftunkor", "Ruhshunos", "Firibgar"
            )
        ]
        if all(u in game.get("night_done", set()) for u in active_alive):
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
            await q.answer("❌ Ovoz berish yakunlangan.", show_alert=True)
            return
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar ovoz bera olmaydi.", show_alert=True)
            return

        # 1 kishi faqat 1 marta ovoz berishi shart!
        if uid in game.get("votes", {}):
            prev_target = game["votes"][uid]
            prev_name = "🕊️ Hech kimga" if prev_target == "none" else display_name(game, int(prev_target))
            await q.answer(f"⚠️ Siz allaqachon ovoz bergansiz ({prev_name})!\nHar bir o'yinchi faqat 1 marta ovoz bera oladi.", show_alert=True)
            return

        # O'ziga ovoz berish taqiqlanadi!
        if target_str != "none" and str(uid) == target_str:
            await q.answer("❌ O'zingizga ovoz bera olmaysiz!", show_alert=True)
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
                text=f"🧊 <b>{html.escape(voter_name)}</b> gumon qildi: <b>{html.escape(target_name)}</b>",
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
            await q.answer("❌ Sud hukmi yakunlangan.", show_alert=True)
            return
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar sud ovozida qatnasha olmaydi.", show_alert=True)
            return

        # 1 kishi faqat 1 marta hukm chiqara oladi!
        if uid in game.get("verdict_votes", {}):
            await q.answer("⚠️ Siz allaqachon sud hukmida ovoz bergansiz!\nHar bir o'yinchi faqat 1 marta ovoz bera oladi.", show_alert=True)
            return

        # Sudlanuvchi o'z hukmida ovoz bera olmaydi!
        if uid == accused:
            await q.answer("❌ Sudlanuvchi o'z hukmida ovoz bera olmaydi!", show_alert=True)
            return

        game.setdefault("verdict_votes", {})[uid] = choice
        record_player_activity(game, uid)
        choice_str = "⚔️ QATL ETISH" if choice == "kill" else "🕊️ AVF ETISH"
        voter_name = display_name(game, uid)
        await q.answer(f"✅ Ovozingiz qayd etildi: {choice_str}", show_alert=True)

        if q.message and q.message.chat.type == "private":
            try:
                await q.edit_message_text(
                    f"✅ Sud hukmingiz qayd etildi: *{choice_str}*.\n\nEndi guruhga qaytib natijani kuting.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚖️ <b>{html.escape(voter_name)}</b> hukm chiqardi: <b>{choice_str}</b>",
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
