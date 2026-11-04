"""
Deep Link Dispatcher for Detektiv Mafia Bot.
Handles incoming Telegram deep-linking parameters in /start <param>:
- join_<chat_id>: Direct lobby join from invite link or inline buttons.
- act_<chat_id>: Direct action/voting menu opening in private chat.
- Keyword links: profile, balance, will, shop, guide, rating, clan, admin, stats, plan, boost.
"""

import html
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from database.models import get_badge
from core.engine import (
    games, lobbies, find_game_by_user, find_lobby_by_user, display_name
)
from core.emojis import tg_emoji
from phases.lobby import lobby_text, lobby_keyboard

log = logging.getLogger("detektiv.handlers.deep_link")


async def handle_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE, arg: str) -> bool:
    """
    Evaluates and processes /start <arg> deep-linking payload.
    Returns True if handled, False otherwise.
    """
    user = update.effective_user
    msg = update.message or update.effective_message
    if not user or not msg or not arg:
        return False

    # 1. Direct Lobby Join (join_<chat_id>)
    if arg.startswith("join_"):
        try:
            target_chat_id = int(arg.replace("join_", ""))
            lobby = lobbies.get(target_chat_id)
            if lobby and lobby.get("open"):
                existing_game = find_game_by_user(user.id)
                if existing_game and existing_game.get("chat") != target_chat_id and existing_game.get("alive", {}).get(user.id, False):
                    await msg.reply_text("⚠️ Siz boshqa guruhdagi faol o'yinda tiriksiz! Avval o'sha o'yinni tugating.")
                    return True
                existing_lobby = find_lobby_by_user(user.id)
                if existing_lobby and existing_lobby.get("chat_id") != target_chat_id:
                    await msg.reply_text("⚠️ Siz boshqa guruhdagi ochiq lobbida kutmoqdasiz! Avval u yerdan chiqing.")
                    return True

                if user.id not in lobby["players"]:
                    lobby["players"].append(user.id)
                    lobby["names"][user.id] = (user.full_name or user.first_name)[:40]
                    badge = await get_badge(user.id)
                    if badge:
                        lobby["badges"][user.id] = badge
                    await msg.reply_text(
                        "✅ Siz o'yin lobbiesiga muvaffaqiyatli qo'shildingiz!\n"
                        "Guruhga qaytib o'yin boshlanishini kuting."
                    )
                    # Refresh lobby in group
                    try:
                        await context.bot.edit_message_text(
                            chat_id=target_chat_id,
                            message_id=lobby["message_id"],
                            text=lobby_text(lobby),
                            reply_markup=lobby_keyboard(target_chat_id, include_bot_link=True),
                            parse_mode="HTML"
                        )
                    except (TelegramError, Exception) as e:
                        log.debug("Operation suppressed in %s: %s", __name__, e)
                    return True
                else:
                    await msg.reply_text("ℹ️ Siz allaqachon ushbu lobbiga qo'shilgansiz.")
                    return True
        except Exception as e:
            log.warning("Deep link join error: %s", e)
            return False

    # 2. In-Game Role Action / Voting Bridge (act_<chat_id>)
    if arg.startswith("act_"):
        try:
            target_chat_raw = int(arg.replace("act_", ""))
            from core.navigation import get_group_link, return_to_group_keyboard
            from phases.night import get_role_action_buttons
            from phases.voting import get_voting_keyboard
            from phases.verdict import verdict_keyboard
            from core.graveyard import graveyard_status_text, graveyard_menu_keyboard

            chat_candidates = [-target_chat_raw, target_chat_raw]
            active_game = None
            target_chat_id = None
            for c_id in chat_candidates:
                if c_id in games:
                    active_game = games[c_id]
                    target_chat_id = c_id
                    break

            if active_game:
                group_link = get_group_link(active_game)
                uid = user.id
                if uid in active_game.get("players", []):
                    if active_game.get("alive", {}).get(uid, False):
                        phase = active_game.get("phase", "night")
                        role = active_game.get("roles", {}).get(uid, "Fuqaro")
                        if phase == "night":
                            night_num = active_game.get("night", 1)
                            if uid in active_game.get("night_done", set()):
                                await msg.reply_text(
                                    f"{tg_emoji('night', '🌙')} <b>Tun #{night_num}</b>\n"
                                    f"🎭 Sizning rolingiz: <b>{html.escape(role)}</b>\n\n"
                                    "✅ Siz bugungi tungi amalingizni allaqachon bajardingiz. Tong otishini kuting!",
                                    reply_markup=return_to_group_keyboard(active_game),
                                    parse_mode="HTML"
                                )
                            else:
                                kb = get_role_action_buttons(active_game, uid)
                                if kb:
                                    await msg.reply_text(
                                        f"{tg_emoji('night', '🌙')} <b>Tun #{night_num} amallari</b>\n"
                                        f"🎭 Sizning rolingiz: <b>{html.escape(role)}</b>\n"
                                        "Quyidagi tugmalardan birini tanlang:",
                                        reply_markup=kb,
                                        parse_mode="HTML"
                                    )
                                else:
                                    await msg.reply_text(
                                        f"{tg_emoji('night', '🌙')} <b>Tun #{night_num}</b>\n"
                                        f"🎭 Sizning rolingiz: <b>{html.escape(role)}</b>\n\n"
                                        "Bu tunda sizdan maxsus amal talab etilmaydi. Tong otishini kuting!",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="HTML"
                                    )
                        elif phase == "voting":
                            night_num = active_game.get("night", 1)
                            if uid in active_game.get("votes", {}):
                                tgt = active_game["votes"][uid]
                                tgt_name = "🕊️ Hech kimga" if tgt == "none" else display_name(active_game, int(tgt))
                                await msg.reply_text(
                                    f"{tg_emoji('voting', '🗳️')} <b>Ovoz berish (#{night_num}-kun)</b>\n\n"
                                    f"✅ Siz allaqachon ovoz bergansiz (<b>{html.escape(tgt_name)}</b>)!",
                                    reply_markup=return_to_group_keyboard(active_game),
                                    parse_mode="HTML"
                                )
                            else:
                                vkb = get_voting_keyboard(active_game, is_pm=True)
                                await msg.reply_text(
                                    f"{tg_emoji('voting', '🗳️')} <b>Ovoz berish (#{night_num}-kun)</b>\n\n"
                                    "Sud minbariga chiqarish uchun gumonlanuvchini tanlang:",
                                    reply_markup=vkb,
                                    parse_mode="HTML"
                                )
                        elif phase == "verdict":
                            accused = active_game.get("accused_uid")
                            accused_name = display_name(active_game, accused)
                            if uid == accused:
                                await msg.reply_text(
                                    f"{tg_emoji('voting', '⚖️')} <b>Sud minbari</b>\n\n"
                                    "Siz hozir sud minbaridasiz! Fuqarolar sizning taqdiringizni hal qilmoqda.",
                                    reply_markup=return_to_group_keyboard(active_game),
                                    parse_mode="HTML"
                                )
                            elif uid in active_game.get("verdict_votes", {}):
                                v = active_game["verdict_votes"][uid]
                                v_str = "⚔️ QATL" if v == "kill" else "🕊️ AFV"
                                await msg.reply_text(
                                    f"{tg_emoji('voting', '⚖️')} <b>Sud hukmi ({html.escape(accused_name)})</b>\n\n"
                                    f"✅ Siz allaqachon ovoz bergansiz (<b>{v_str}</b>)!",
                                    reply_markup=return_to_group_keyboard(active_game),
                                    parse_mode="HTML"
                                )
                            else:
                                vkb = verdict_keyboard(target_chat_id, accused, is_pm=True, game_or_link=active_game)
                                await msg.reply_text(
                                    f"{tg_emoji('voting', '⚖️')} <b>Sud minbari</b>\n\n"
                                    f"Ayblanuvchi: <b>{html.escape(accused_name)}</b>\n"
                                    "Uning taqdirini hal qiling: qatl etilsinmi yoki afv etilsin?",
                                    reply_markup=vkb,
                                    parse_mode="HTML"
                                )
                        else:
                            await msg.reply_text(
                                f"{tg_emoji('day', '☀️')} <b>Kunduzgi muhokama fazasi!</b>\n\n"
                                "Guruhga qaytib, boshqa o'yinchilar bilan fikr almashing va dalillarni tahlil qiling.",
                                reply_markup=return_to_group_keyboard(active_game),
                                parse_mode="HTML"
                            )
                        return True
                    else:
                        await msg.reply_text(
                            graveyard_status_text(active_game, uid),
                            reply_markup=graveyard_menu_keyboard(active_game.get("_db_id", 0), group_link=group_link),
                            parse_mode="HTML"
                        )
                        return True
                else:
                    await msg.reply_text(
                        f"👁️ <b>Siz bu o'yinda tomoshabinsiz.</b>\n\n"
                        f"Faza: <b>{active_game.get('phase', '').capitalize()}</b>\n"
                        f"Tiriklar: <b>{sum(1 for v in active_game.get('alive', {}).values() if v)}</b> nafar",
                        reply_markup=return_to_group_keyboard(active_game),
                        parse_mode="HTML"
                    )
                    return True

            # Check lobbies
            active_lobby = None
            for c_id in chat_candidates:
                if c_id in lobbies:
                    active_lobby = lobbies[c_id]
                    target_chat_id = c_id
                    break

            if active_lobby and active_lobby.get("open"):
                g_link = active_lobby.get("group_link") or get_group_link({"chat": target_chat_id})
                if user.id in active_lobby.get("players", []):
                    await msg.reply_text(
                        "🎮 <b>Siz o'yin lobbiesidasiz!</b>\n\n"
                        f"👥 Ishtirokchilar: <b>{len(active_lobby['players'])} nafar</b>.\n"
                        "Guruhga qaytib o'yin boshlanishini kuting.",
                        reply_markup=return_to_group_keyboard(g_link),
                        parse_mode="HTML"
                    )
                else:
                    await msg.reply_text(
                        "🎮 <b>Guruhda yangi o'yin ochilgan!</b>\n\n"
                        "Qo'shilish uchun guruhga qayting yoki pastdagi tugmani bosing:",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🎮 Qo'shilish", callback_data=f"lobby_join:{target_chat_id}")],
                            [InlineKeyboardButton("👥 Guruhga qaytish", url=g_link)]
                        ]),
                        parse_mode="HTML"
                    )
                return True
            else:
                cid_str = str(target_chat_raw)
                g_link = f"https://t.me/c/{cid_str[3:]}/999999999" if cid_str.startswith("100") else "https://t.me"
                await msg.reply_text(
                    "ℹ️ Bu guruhda hozirda faol o'yin topilmadi.",
                    reply_markup=return_to_group_keyboard(g_link)
                )
                return True
        except Exception as e:
            log.warning("Act deep link error: %s", e)
            return False

    # 3. Keyword Redirections
    from handlers.commands_user import profile_cmd, balance_cmd, will_cmd, guide_cmd, rating_cmd
    from handlers.commands_meta import plan_cmd, boost_cmd

    arg_lower = arg.lower().strip()
    if arg_lower in ("profile", "profil", "me", "shaxsiy"):
        await profile_cmd(update, context)
        return True
    elif arg_lower in ("balance", "balans", "hisob", "pul", "wallet"):
        await balance_cmd(update, context)
        return True
    elif arg_lower in ("will", "vasiyat", "vasiyatnoma"):
        await will_cmd(update, context)
        return True
    elif arg_lower in ("shop", "dokon", "do'kon", "magazin", "bozor"):
        from handlers.shop import shop_cmd
        await shop_cmd(update, context)
        return True
    elif arg_lower in ("guide", "rules", "help", "qollanma", "qo'llanma", "yordam", "rollar", "qoidalar"):
        await guide_cmd(update, context)
        return True
    elif arg_lower in ("rating", "top", "reyting", "leaderboard", "top10"):
        await rating_cmd(update, context)
        return True
    elif arg_lower in ("clan", "clans", "klan", "sindikat", "oila"):
        from handlers.clans import clan_cmd
        await clan_cmd(update, context)
        return True
    elif arg_lower in ("admin", "panel", "boshqaruv"):
        from handlers.admin_panel import admin_cmd
        await admin_cmd(update, context)
        return True
    elif arg_lower in ("stats", "statistika", "holat"):
        from handlers.admin_panel import stats_cmd
        await stats_cmd(update, context)
        return True
    elif arg_lower in ("plan", "reja", "mexanika"):
        await plan_cmd(update, context)
        return True
    elif arg_lower in ("boost", "premium", "vip"):
        await boost_cmd(update, context)
        return True
    elif arg_lower in ("mypara", "juftlik", "juftim"):
        from handlers.social import mypara_cmd
        await mypara_cmd(update, context)
        return True
    elif arg_lower in ("mybro", "birodar", "broim"):
        from handlers.social import mybro_cmd
        await mybro_cmd(update, context)
        return True
    elif arg_lower in ("settings", "sozlama", "sozlamalar"):
        from handlers.settings import settings_cmd
        await settings_cmd(update, context)
        return True
    elif arg_lower in ("salom", "hello", "assalom", "assalomualaykum"):
        from handlers.commands_user import salom_cmd
        await salom_cmd(update, context)
        return True
    elif arg_lower in ("game", "oyin", "o'yin", "play"):
        from config import BOT_USERNAME
        add_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🎮 <b>Mafia O'yini</b>\n\n"
            "Mafia o'yini faqat <b>Telegram guruhlarida</b> o'ynaladi.\n"
            "O'yin boshlash uchun botni guruhingizga qo'shing va guruhda <b>/game</b> buyrug'ini yuboring!",
            reply_markup=add_kb,
            parse_mode="HTML"
        )
        return True

    return False
