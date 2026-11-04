import html
import logging
from typing import Dict, Any, List
from telegram.error import TelegramError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import ROLES
from database.models import get_user, change_balance, add_item, get_will
from core.engine import (
    games, find_game_by_user, display_name, save_runtime
)
from core.afk_penalty import record_player_activity
from core.navigation import return_to_group_keyboard
from core.atmospheric_feed import broadcast_role_action, broadcast_role_sleep
from core.emojis import tg_emoji
from roles.base import is_valid_role_action
from phases.night import (
    NIGHT_ACTIVE_ROLES,
    get_target_selection_keyboard, get_role_action_buttons,
    resolve_night, handle_king_decision
)

log = logging.getLogger("detektiv.handlers.cb_night")


def check_night_completed(game: Dict[str, Any]) -> bool:
    active_alive = []
    det_alive = False
    for p in game.get("players", []):
        if game.get("roles", {}).get(p) == "Detektiv" and game.get("alive", {}).get(p, False):
            det_alive = True
            break
    for u in game.get("players", []):
        if not game.get("alive", {}).get(u, False):
            continue
        role = game.get("roles", {}).get(u)
        if role == "Sherif" and det_alive and u not in game.get("sheriff_promoted", set()):
            continue
        if role in NIGHT_ACTIVE_ROLES:
            active_alive.append(u)
    return bool(active_alive) and all(u in game.get("night_done", set()) for u in active_alive)


def get_pending_night_actors(game: Dict[str, Any]) -> List[str]:
    active_alive = []
    det_alive = False
    for p in game.get("players", []):
        if game.get("roles", {}).get(p) == "Detektiv" and game.get("alive", {}).get(p, False):
            det_alive = True
            break
    for u in game.get("players", []):
        if not game.get("alive", {}).get(u, False):
            continue
        role = game.get("roles", {}).get(u)
        if role == "Sherif" and det_alive and u not in game.get("sheriff_promoted", set()):
            continue
        if role in NIGHT_ACTIVE_ROLES and u not in game.get("night_done", set()):
            active_alive.append(display_name(game, u))
    return active_alive


async def handle_night_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    if not q or not q.data:
        return False
    data = q.data
    user = q.from_user
    uid = user.id

    # 1. Role Action in PM (act:<action>:<actor>)
    if data.startswith("act:"):
        parts = data.split(":")
        action = parts[1]
        actor = int(parts[2])

        if q.from_user.id != actor:
            await q.answer("❌ Bu tugma siz uchun emas!", show_alert=True)
            return True

        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Ushbu tugma muddati o'tgan yoki hozir tungi faza emas.", show_alert=True)
            return True

        if not game.get("alive", {}).get(actor, False):
            await q.answer("💀 Halok bo'lganlar tunda harakat qila olmaydi.", show_alert=True)
            return True

        actor_role = game.get("roles", {}).get(actor)
        if not is_valid_role_action(actor_role, action, game, actor):
            await q.answer("❌ Sizning rolingiz ushbu harakatni bajara olmaydi.", show_alert=True)
            return True

        if action == "sleep":
            await q.answer("😴 Siz bu tun dam olishga qaror qildingiz.", show_alert=True)
            game.setdefault("night_done", set()).add(actor)
            record_player_activity(game, actor)
            await broadcast_role_sleep(context, game, actor)
            try:
                await q.edit_message_text(
                    "😴 *Bu tun hech kimni tanlamadingiz — dam oldingiz.*\nTong otishini kuting!",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            if check_night_completed(game):
                await resolve_night(context, game)
            return True

        if action == "will_help":
            await q.answer()
            await q.message.reply_text(
                "📜 *Vasiyatnoma yozish:* Shaxsiy chatda `/will Mening vasiyatim...` buyrug'ini yuboring.\n"
                "U o'limingizdan so'ng guruhda e'lon qilinadi.",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="Markdown"
            )
            return True

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
            return True

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
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            return True

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
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            return True

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
                return True

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
            return True

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
            return True

        await q.answer()
        kb = get_target_selection_keyboard(game, actor, action)
        await q.edit_message_text(
            f"🎯 *{action.upper()}* uchun nishonni tanlang:",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return True

    # 2. Disguise selection for Firibgar
    if data.startswith("disguise:"):
        parts = data.split(":")
        actor = int(parts[1])
        chosen_role = parts[2]

        if q.from_user.id != actor:
            await q.answer("❌ Bu tugma siz uchun emas!", show_alert=True)
            return True

        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Ushbu tugma muddati o'tgan yoki hozir tungi faza emas.", show_alert=True)
            return True

        if not game.get("alive", {}).get(actor, False):
            await q.answer("💀 Halok bo'lganlar harakat qila olmaydi.", show_alert=True)
            return True

        if game.get("roles", {}).get(actor) != "Firibgar":
            await q.answer("❌ Faqat Firibgar soxta qiyofa tanlay oladi.", show_alert=True)
            return True

        if chosen_role not in ROLES:
            await q.answer("❌ Noto'g'ri rol tanlandi.", show_alert=True)
            return True

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
        return True

    # 3. Target Selection in PM (tgt:<action>:<actor>:<target>)
    if data.startswith("tgt:"):
        parts = data.split(":")
        action = parts[1]
        actor = int(parts[2])
        target = int(parts[3])

        if q.from_user.id != actor:
            await q.answer("❌ Bu tugma siz uchun emas!", show_alert=True)
            return True

        game = find_game_by_user(actor)
        if not game or game.get("phase") != "night":
            await q.answer("❌ Ushbu tugma muddati o'tgan yoki hozir tungi faza emas.", show_alert=True)
            return True

        if not game.get("alive", {}).get(actor, False):
            await q.answer("💀 Halok bo'lganlar tunda harakat qila olmaydi.", show_alert=True)
            return True

        actor_role = game.get("roles", {}).get(actor)
        if not is_valid_role_action(actor_role, action, game, actor):
            await q.answer("❌ Sizning rolingiz ushbu harakatni bajara olmaydi.", show_alert=True)
            return True

        if target not in game.get("players", []):
            await q.answer("❌ Tanlangan o'yinchi bu o'yinda qatnashmayapti.", show_alert=True)
            return True

        if not game.get("alive", {}).get(target, False):
            await q.answer("❌ Tanlangan o'yinchi allaqachon vafot etgan!", show_alert=True)
            return True

        if target == actor:
            if action in ("protect", "guard"):
                if actor in game.get("self_protect_used", set()) or game.get("doctor_self_heal_used", {}).get(actor, False):
                    await q.answer("❌ O'zingizni himoya qilishdan faqat 1 marta foydalana olasiz!", show_alert=True)
                    return True
            elif action != "will_help":
                await q.answer("❌ O'zingizni tanlay olmaysiz!", show_alert=True)
                return True

        if action == "kill" and ROLES.get(game.get("roles", {}).get(target)) == "red":
            await q.answer("❌ Mafiya a'zosi o'z sherigiga hujum qila olmaydi!", show_alert=True)
            return True

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
                return True
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
                        except (TelegramError, Exception) as e:
                            log.debug("Operation suppressed in %s: %s", __name__, e)

                if fake_doc_used:
                    is_red = False
                    try:
                        await context.bot.send_message(
                            chat_id=target,
                            text=f"{tg_emoji('item_doc', '📄', 'SHOP')} <b>SOXTA HUJJAT ISHLADI!</b> Sherif sizni tekshirdi, ammo soxta hujjatingiz tufayli sizni oddiy fuqaro deb bildi (1 ta hujjat sarflandi).\n⚠️ <b>Eslatma:</b> Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                            reply_markup=return_to_group_keyboard(game),
                            parse_mode="HTML"
                        )
                    except (TelegramError, Exception) as e:
                        log.debug("Operation suppressed in %s: %s", __name__, e)
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
                    return True
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
                    return True
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
                return True
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
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)
            try:
                await context.bot.send_message(
                    chat_id=target,
                    text="💰 *Boy sizning rolingizni 1 tunga ijaraga oldi va sizga 50 Coin to'ladi!*",
                    reply_markup=return_to_group_keyboard(game)
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            record_player_activity(game, actor)
            await broadcast_role_action(context, game, actor, "boy")
            return True
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
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            await q.edit_message_text(
                f"🛒 *{tgt_name}*ga bepul tungi himoya qalqoni (Protection) taqdim etildi!\n\nEndi guruhga qaytib muhokamani davom ettirishingiz mumkin.",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="Markdown"
            )
            await save_runtime(game)
            if check_night_completed(game):
                await resolve_night(context, game)
            return True

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
        return True

    # 4. Cancel Action
    if data == "cancel_action":
        await q.answer("❌ Bekor qilindi.")
        game_cur = find_game_by_user(uid)
        await q.edit_message_text(
            "Amal bekor qilindi.",
            reply_markup=return_to_group_keyboard(game_cur) if game_cur else None
        )
        return True

    # 5. King Decision Callback (king_kill / king_forgive)
    if data.startswith("king_kill:") or data.startswith("king_forgive:"):
        parts = data.split(":")
        king_uid = int(parts[1])
        attacker_uid = int(parts[2])
        game = find_game_by_user(king_uid)
        if not game:
            await q.answer("❌ O'yin topilmadi.")
            return True

        if not game.get("_waiting_king"):
            await q.answer("ℹ️ Qaror qabul qilish vaqti o'tib ketgan.", show_alert=True)
            return True

        is_kill = data.startswith("king_kill:")
        if is_kill:
            try:
                await q.edit_message_text(
                    f"⚔️ *QIROLNING QAT'IY HUKMI:* Hujumchi *{display_name(game, attacker_uid)}* qatl etildi!\n\nEndi guruhga qaytib natijani kuting.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
        else:
            try:
                await q.edit_message_text(
                    f"🕊️ *QIROLNING MARHAMATI:* Hujumchi *{display_name(game, attacker_uid)}* avf etildi.\n\nEndi guruhga qaytib natijani kuting.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

        await handle_king_decision(context, game, king_uid, attacker_uid, is_kill=is_kill, is_timeout=False)
        return True

    return False
