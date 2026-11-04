import html
import logging
from typing import Optional
from telegram.error import TelegramError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import ADMIN_ID, ROLES, BOT_USERNAME
from database.models import (
    ensure_user, get_user, get_balance, change_balance, get_badge,
    get_top_players, is_admin, get_will, set_will, track_group_member
)
from core.engine import (
    games, lobbies, find_game_by_user, find_lobby_by_user, display_name,
    cancel_game_timer, cancel_lobby_timer, save_runtime, abort_game, abort_lobby
)
from phases.lobby import create_lobby, lobby_text, lobby_keyboard
from core.will import save_player_will, format_will_announcement
from core.visuals import anim_emoji, format_badge_with_anim_emoji, strip_anim_emoji_tags
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.handlers.commands")

def main_menu_keyboard(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🟢 🎮 O'yin ochish", callback_data="menu_game"),
            InlineKeyboardButton("🟣 🛒 Do'kon (Shop)", callback_data="menu_shop")
        ],
        [
            InlineKeyboardButton("🟡 💰 Balans", callback_data="menu_balance"),
            InlineKeyboardButton("🏆 🥇 TOP Reyting", callback_data="menu_rating")
        ],
        [
            InlineKeyboardButton("🔵 👤 Profil", callback_data="menu_profile"),
            InlineKeyboardButton("📜 ✍️ Vasiyatnoma", callback_data="menu_will")
        ],
        [
            InlineKeyboardButton("📖 🎭 Rollar qo'llanmasi", callback_data="menu_guide"),
            InlineKeyboardButton("🛡️ ⚔️ Sindikat / Klan", callback_data="menu_clan")
        ]
    ]
    if is_admin_user:
        rows.append([InlineKeyboardButton("👑 Master Admin Paneli", callback_data="adm:menu")])
    return InlineKeyboardMarkup(rows)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user:
        return

    await ensure_user(user)

    # Check deep linking (e.g. /start join_-100123456)
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("join_"):
            try:
                target_chat_id = int(arg.replace("join_", ""))
                lobby = lobbies.get(target_chat_id)
                if lobby and lobby.get("open"):
                    existing_game = find_game_by_user(user.id)
                    if existing_game and existing_game.get("chat") != target_chat_id and existing_game.get("alive", {}).get(user.id, False):
                        await update.message.reply_text("⚠️ Siz boshqa guruhdagi faol o'yinda tiriksiz! Avval o'sha o'yinni tugating.")
                        return
                    existing_lobby = find_lobby_by_user(user.id)
                    if existing_lobby and existing_lobby.get("chat_id") != target_chat_id:
                        await update.message.reply_text("⚠️ Siz boshqa guruhdagi ochiq lobbida kutmoqdasiz! Avval u yerdan chiqing.")
                        return

                    if user.id not in lobby["players"]:
                        lobby["players"].append(user.id)
                        lobby["names"][user.id] = (user.full_name or user.first_name)[:40]
                        badge = await get_badge(user.id)
                        if badge:
                            lobby["badges"][user.id] = badge
                        await update.message.reply_text(
                            "✅ Siz o'yin lobbiesiga muvaffaqiyatli qo'shildingiz!\n"
                            "Guruhga qaytib o'yin boshlanishini kuting."
                        )
                        # Refresh lobby in group
                        try:
                            await context.bot.edit_message_text(
                                chat_id=target_chat_id,
                                message_id=lobby["message_id"],
                                text=lobby_text(lobby),
                                reply_markup=lobby_keyboard(target_chat_id, include_bot_link=True)
                            )
                        except (TelegramError, Exception) as e:
                            log.debug("Operation suppressed in %s: %s", __name__, e)
                        return
                    else:
                        await update.message.reply_text("ℹ️ Siz allaqachon ushbu lobbiga qo'shilgansiz.")
                        return
            except Exception as e:
                log.warning("Deep link join error: %s", e)
        elif arg.startswith("act_"):
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
                                    await update.message.reply_text(
                                        f"{tg_emoji('night', '🌙')} <b>Tun #{night_num}</b>\n"
                                        f"🎭 Sizning rolingiz: <b>{html.escape(role)}</b>\n\n"
                                        "✅ Siz bugungi tungi amalingizni allaqachon bajardingiz. Tong otishini kuting!",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="HTML"
                                    )
                                else:
                                    kb = get_role_action_buttons(active_game, uid)
                                    if kb:
                                        await update.message.reply_text(
                                            f"{tg_emoji('night', '🌙')} <b>Tun #{night_num} amallari</b>\n"
                                            f"🎭 Sizning rolingiz: <b>{html.escape(role)}</b>\n"
                                            "Quyidagi tugmalardan birini tanlang:",
                                            reply_markup=kb,
                                            parse_mode="HTML"
                                        )
                                    else:
                                        await update.message.reply_text(
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
                                    await update.message.reply_text(
                                        f"{tg_emoji('voting', '🗳️')} <b>Ovoz berish (#{night_num}-kun)</b>\n\n"
                                        f"✅ Siz allaqachon ovoz bergansiz (<b>{html.escape(tgt_name)}</b>)!",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="HTML"
                                    )
                                else:
                                    vkb = get_voting_keyboard(active_game, is_pm=True)
                                    await update.message.reply_text(
                                        f"{tg_emoji('voting', '🗳️')} <b>Ovoz berish (#{night_num}-kun)</b>\n\n"
                                        "Sud minbariga chiqarish uchun gumonlanuvchini tanlang:",
                                        reply_markup=vkb,
                                        parse_mode="HTML"
                                    )
                            elif phase == "verdict":
                                accused = active_game.get("accused_uid")
                                accused_name = display_name(active_game, accused)
                                if uid == accused:
                                    await update.message.reply_text(
                                        f"{tg_emoji('voting', '⚖️')} <b>Sud minbari</b>\n\n"
                                        "Siz hozir sud minbaridasiz! Fuqarolar sizning taqdiringizni hal qilmoqda.",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="HTML"
                                    )
                                elif uid in active_game.get("verdict_votes", {}):
                                    v = active_game["verdict_votes"][uid]
                                    v_str = "⚔️ QATL" if v == "kill" else "🕊️ AFV"
                                    await update.message.reply_text(
                                        f"{tg_emoji('voting', '⚖️')} <b>Sud hukmi ({html.escape(accused_name)})</b>\n\n"
                                        f"✅ Siz allaqachon ovoz bergansiz (<b>{v_str}</b>)!",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="HTML"
                                    )
                                else:
                                    vkb = verdict_keyboard(target_chat_id, accused, is_pm=True, game_or_link=active_game)
                                    await update.message.reply_text(
                                        f"{tg_emoji('voting', '⚖️')} <b>Sud minbari</b>\n\n"
                                        f"Ayblanuvchi: <b>{html.escape(accused_name)}</b>\n"
                                        "Uning taqdirini hal qiling: qatl etilsinmi yoki afv etilsin?",
                                        reply_markup=vkb,
                                        parse_mode="HTML"
                                    )
                            else:
                                await update.message.reply_text(
                                    f"{tg_emoji('day', '☀️')} <b>Kunduzgi muhokama fazasi!</b>\n\n"
                                    "Guruhga qaytib, boshqa o'yinchilar bilan fikr almashing va dalillarni tahlil qiling.",
                                    reply_markup=return_to_group_keyboard(active_game),
                                    parse_mode="HTML"
                                )
                            return
                        else:
                            await update.message.reply_text(
                                graveyard_status_text(active_game, uid),
                                reply_markup=graveyard_menu_keyboard(active_game.get("_db_id", 0), group_link=group_link),
                                parse_mode="HTML"
                            )
                            return
                    else:
                        await update.message.reply_text(
                            f"👁️ <b>Siz bu o'yinda tomoshabinsiz.</b>\n\n"
                            f"Faza: <b>{active_game.get('phase', '').capitalize()}</b>\n"
                            f"Tiriklar: <b>{sum(1 for v in active_game.get('alive', {}).values() if v)}</b> nafar",
                            reply_markup=return_to_group_keyboard(active_game),
                            parse_mode="HTML"
                        )
                        return

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
                        await update.message.reply_text(
                            "🎮 *Siz o'yin lobbiesidasiz!*\n\n"
                            f"👥 Ishtirokchilar: {len(active_lobby['players'])} nafar.\n"
                            "Guruhga qaytib o'yin boshlanishini kuting.",
                            reply_markup=return_to_group_keyboard(g_link),
                            parse_mode="Markdown"
                        )
                    else:
                        await update.message.reply_text(
                            "🎮 *Guruhda yangi o'yin ochilgan!*\n\n"
                            "Qo'shilish uchun guruhga qayting yoki pastdagi tugmani bosing:",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🎮 Qo'shilish", callback_data=f"lobby_join:{target_chat_id}")],
                                [InlineKeyboardButton("👥 Guruhga qaytish", url=g_link)]
                            ]),
                            parse_mode="Markdown"
                        )
                    return
                else:
                    cid_str = str(target_chat_raw)
                    g_link = f"https://t.me/c/{cid_str[3:]}/999999999" if cid_str.startswith("100") else "https://t.me"
                    await update.message.reply_text(
                        "ℹ️ Bu guruhda hozirda faol o'yin topilmadi.",
                        reply_markup=return_to_group_keyboard(g_link)
                    )
                    return
            except Exception as e:
                log.warning("Act deep link error: %s", e)
        arg_lower = arg.lower().strip()
        if arg_lower in ("profile", "profil", "me", "shaxsiy"):
            await profile_cmd(update, context)
            return
        elif arg_lower in ("balance", "balans", "hisob", "pul", "wallet"):
            await balance_cmd(update, context)
            return
        elif arg_lower in ("will", "vasiyat", "vasiyatnoma"):
            await will_cmd(update, context)
            return
        elif arg_lower in ("shop", "dokon", "do'kon", "magazin", "bozor"):
            from handlers.shop import shop_cmd
            await shop_cmd(update, context)
            return
        elif arg_lower in ("guide", "rules", "help", "qollanma", "qo'llanma", "yordam", "rollar", "qoidalar"):
            await guide_cmd(update, context)
            return
        elif arg_lower in ("rating", "top", "reyting", "leaderboard", "top10"):
            await rating_cmd(update, context)
            return
        elif arg_lower in ("clan", "clans", "klan", "sindikat", "oila"):
            from handlers.clans import clan_cmd
            await clan_cmd(update, context)
            return
        elif arg_lower in ("admin", "panel", "boshqaruv"):
            from handlers.admin_panel import admin_cmd
            await admin_cmd(update, context)
            return
        elif arg_lower in ("stats", "statistika", "holat"):
            from handlers.admin_panel import stats_cmd
            await stats_cmd(update, context)
            return
        elif arg_lower in ("plan", "reja", "mexanika"):
            await plan_cmd(update, context)
            return
        elif arg_lower in ("boost", "premium", "vip"):
            await boost_cmd(update, context)
            return
        elif arg_lower in ("mypara", "juftlik", "juftim"):
            from handlers.social import mypara_cmd
            await mypara_cmd(update, context)
            return
        elif arg_lower in ("mybro", "birodar", "broim"):
            from handlers.social import mybro_cmd
            await mybro_cmd(update, context)
            return
        elif arg_lower in ("settings", "sozlama", "sozlamalar"):
            from handlers.settings import settings_cmd
            await settings_cmd(update, context)
            return
        elif arg_lower in ("salom", "hello", "assalom", "assalomualaykum"):
            await salom_cmd(update, context)
            return
        elif arg_lower in ("game", "oyin", "o'yin", "play"):
            from config import BOT_USERNAME
            add_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
            ])
            await update.message.reply_text(
                "🎮 <b>Mafia O'yini</b>\n\n"
                "Mafia o'yini faqat <b>Telegram guruhlarida</b> o'ynaladi.\n"
                "O'yin boshlash uchun botni guruhingizga qo'shing va guruhda <b>/game</b> buyrug'ini yuboring!",
                reply_markup=add_kb,
                parse_mode="HTML"
            )
            return

    welcome_text = (
        f"{anim_emoji('detective', '🎭')} <b>Detektiv Mafia Botiga Xush Kelibsiz!</b>\n\n"
        "Shahar va mafiya o'rtasidagi shiddatli psixologik kurash.\n\n"
        f"{anim_emoji('sparkles', '🌟')} <b>Imkoniyatlar:</b>\n"
        f"• {anim_emoji('detective', '🕵️')} <b>24+ noyob rollar balansi</b>\n"
        f"• {anim_emoji('target', '🔍')} <b>Kriminalistik ashyoviy dalillar tergovi</b>\n"
        f"• {anim_emoji('scroll', '📜')} <b>So'nggi Vasiyatnoma tizimi (/will)</b>\n"
        f"• {anim_emoji('moon', '🌫️')} <b>Dinamik shahar hodisalari va ob-havo</b>\n"
        f"• {anim_emoji('skull', '👻')} <b>Ruhlar olami va o'liklar bashorati</b>\n\n"
        "Quyidagi menyu orqali kerakli bo'limni tanlang:"
    )

    adm = is_admin(user.id, getattr(user, "username", ""))
    msg = update.message or update.effective_message
    if chat.type == "private":
        if msg:
            await msg.reply_text(welcome_text, reply_markup=main_menu_keyboard(adm), parse_mode="HTML")
    else:
        if chat.id in lobbies and lobbies[chat.id].get("open"):
            await startgame_cmd(update, context)
        else:
            await context.bot.send_message(
                chat_id=chat.id,
                text="🎮 Guruhda yangi Mafia o'yini ochish uchun <b>/game</b> buyrug'ini yuboring.",
                parse_mode="HTML"
            )

async def startgame_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or chat.type not in ("group", "supergroup"):
        if msg:
            from config import BOT_USERNAME
            add_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "🎮 <b>O'yinni boshlash (/startgame)</b>\n\n"
                "Mafia o'yini faqat <b>Telegram guruhlarida</b> o'ynaladi.\n"
                "Botni guruhingizga qo'shing va o'sha yerda <b>/game</b> buyrug'ini yuboring!",
                reply_markup=add_kb,
                parse_mode="HTML"
            )
        return

    chat_id = chat.id
    lobby = lobbies.get(chat_id)
    if not lobby or not lobby.get("open"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="ℹ️ Hozirda faol lobby yo'q. Yangi o'yin ochish uchun <b>/game</b> buyrug'ini yuboring.",
            parse_mode="HTML"
        )
        return

    from database.models import is_admin
    if user.id not in lobby["players"] and not is_admin(user.id, user.username):
        await context.bot.send_message(
            chat_id=chat_id,
            text="❗ O'yinni boshlash uchun avval lobbiga qo'shiling."
        )
        return

    from config import MIN_PLAYERS
    if len(lobby["players"]) < MIN_PLAYERS:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❗ O'yinni boshlash uchun kamida <b>{MIN_PLAYERS}</b> kishi kerak. Hozir: {len(lobby['players'])} ta.",
            parse_mode="HTML"
        )
        return

    from phases.lobby import start_game
    await start_game(context, chat_id)

async def will_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg = update.effective_message or update.message
    if not user or not msg:
        return
    await ensure_user(user)

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=will"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            f"📜 <b>Maxfiy Vasiyatnoma</b>\n\n"
            f"Hurmatli {html.escape(user.first_name)}, vasiyatingiz sir tutilishi uchun "
            f"uni faqat botning shaxsiy chatida yozing va ko'ring.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    scroll = anim_emoji("scroll", "📜")
    will_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Profil", callback_data="menu_profile"),
            InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")
        ]
    ])
    if not context.args:
        current_will = await get_will(user.id)
        if current_will:
            reply_content = (
                f"{scroll} <b>Sizning amaldagi Vasiyatnomangiz:</b>\n\n"
                f"<blockquote>{html.escape(current_will)}</blockquote>\n\n"
                f"Yangi vasiyat yozish uchun: <code>/will &lt;matn&gt;</code>"
            )
        else:
            reply_content = (
                f"{scroll} <b>Sizda hali Vasiyatnoma yo'q!</b>\n\n"
                "Tunda yoki kunduzi o'ldirilganingizda butun shaharga sirli ma'lumot qoldirish uchun:\n"
                "<code>/will Mening vasiyatim shu...</code> buyrug'idan foydalaning."
            )
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(reply_content, reply_markup=will_kb, parse_mode="HTML")
                return
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
        await msg.reply_text(reply_content, reply_markup=will_kb, parse_mode="HTML")
        return

    text = " ".join(context.args)
    await save_player_will(user.id, text)
    saved_text = (
        "✅ <b>Vasiyatnomangiz muvaffaqiyatli saqlandi!</b>\n"
        "Agar o'yinda halok bo'lsangiz, ushbu xabar shahar ahlisiga e'lon qilinadi."
    )
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(saved_text, reply_markup=will_kb, parse_mode="HTML")
            return
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
    await msg.reply_text(saved_text, reply_markup=will_kb, parse_mode="HTML")

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg = update.message or update.effective_message
    if not user or not msg:
        return
    u = await ensure_user(user)

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=profile"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            f"🔒 <b>Hurmatli {html.escape(user.first_name)}!</b>\n\n"
            f"Shaxsiy profilingiz, balansingiz va yutuqlaringiz maxfiyligini saqlash uchun "
            f"profil ma'lumotlari faqat botning shaxsiy chatida ko'rsatiladi.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    badge_raw = await get_badge(user.id) or "Yo'q"
    badge_display = format_badge_with_anim_emoji(badge_raw) if badge_raw and badge_raw != "Yo'q" else "Yo'q"
    admin_tag = " (Admin)" if is_admin(user.id, getattr(user, "username", "")) else ""

    text = (
        f"{tg_emoji('profile', '👤', 'USER_SETTINGS')} <b>Profil:</b> <b>{html.escape(u['name'])}</b>{admin_tag}\n\n"
        f"{tg_emoji('balance_coins', '🪙', 'USER_SETTINGS')} Tangalar: <b>{'∞' if is_admin(user.id, getattr(user, 'username', '')) else u['coin']}</b>\n"
        f"{tg_emoji('balance_gold', '🥇', 'USER_SETTINGS')} Oltin: <b>{'∞' if is_admin(user.id, getattr(user, 'username', '')) else u['gold']}</b>\n"
        f"{tg_emoji('stats_games', '🎮', 'USER_SETTINGS')} Jami o'yinlar: <b>{u['games']}</b>\n"
        f"{tg_emoji('stats_wins', '🏆', 'USER_SETTINGS')} G'alabalar: <b>{u['wins']}</b>\n"
        f"{tg_emoji('stats_losses', '❌', 'USER_SETTINGS')} Mag'lubiyatlar: <b>{u['losses']}</b>\n"
        f"{tg_emoji('badge_target', '🎖️', 'USER_SETTINGS')} Faol belgi: <b>{badge_display}</b>"
    )
    profile_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Balans", callback_data="menu_balance"),
            InlineKeyboardButton("🛒 Do'kon", callback_data="menu_shop")
        ],
        [
            InlineKeyboardButton("📜 Vasiyatnoma", callback_data="menu_will"),
            InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")
        ]
    ])
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=profile_kb, parse_mode="HTML")
            return
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
    await msg.reply_text(text, reply_markup=profile_kb, parse_mode="HTML")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg = update.message or update.effective_message
    if not user or not msg:
        return
    u = await ensure_user(user)

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=balance"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            f"🔒 <b>Hurmatli {html.escape(user.first_name)}!</b>\n\n"
            f"Mablag'laringiz xavfsizligi va maxfiyligi uchun balansingiz "
            f"faqat botning o'zida shaxsiy ko'rsatiladi.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    coins = "Cheksiz ∞" if is_admin(user.id, getattr(user, "username", "")) else str(u['coin'])
    gold = "Cheksiz ∞" if is_admin(user.id, getattr(user, "username", "")) else str(u['gold'])
    balance_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛒 Do'kon (Shop)", callback_data="shop_main"),
            InlineKeyboardButton("👤 Profil", callback_data="menu_profile")
        ],
        [
            InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")
        ]
    ])
    b_text = (
        f"{tg_emoji('cart', '💰', 'SHOP')} <b>Sizning balansingiz:</b>\n\n"
        f"{tg_emoji('balance_coins', '🪙', 'USER_SETTINGS')} Tangalar: <b>{coins} Coin</b>\n"
        f"{tg_emoji('balance_gold', '🥇', 'USER_SETTINGS')} Oltinlar: <b>{gold} Gold</b>"
    )
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(b_text, reply_markup=balance_kb, parse_mode="HTML")
            return
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
    await msg.reply_text(b_text, reply_markup=balance_kb, parse_mode="HTML")

async def rating_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.message or update.effective_message
    user = update.effective_user
    if not msg:
        return

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=rating"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        fname = html.escape(user.first_name) if user else "Foydalanuvchi"
        await msg.reply_text(
            f"🏆 <b>Top Detektivlar Reytingi</b>\n\n"
            f"Hurmatli {fname}, yetakchi detektivlar ro'yxatini botning shaxsiy chatida ko'ring:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    top = await get_top_players(15)
    lines = [
        f"{anim_emoji('trophy', '🏆')} <b>Top 15 Detektivlar:</b>",
        ""
    ]
    for i, p in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} <b>{html.escape(p['name'])}</b> — {p['wins']} g'alaba ({p['coin']} 🪙)")
    rating_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Profil", callback_data="menu_profile"),
            InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")
        ]
    ])
    r_text = "\n".join(lines)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(r_text, reply_markup=rating_kb, parse_mode="HTML")
            return
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
    await msg.reply_text(r_text, reply_markup=rating_kb, parse_mode="HTML")

async def guide_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.message or update.effective_message
    user = update.effective_user
    if not msg:
        return

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=guide"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        fname = html.escape(user.first_name) if user else "Foydalanuvchi"
        await msg.reply_text(
            f"📖 <b>Rollar va Qoidalar Qo'llanmasi</b>\n\n"
            f"Hurmatli {fname}, barcha 24+ rollar, taktikalar va yo'riqnomalar bilan "
            f"botning shaxsiy chatida batafsil tanishing:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    from roles.dossier import format_role_dossier, ROLE_DOSSIERS
    guide_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Profil", callback_data="menu_profile"),
            InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")
        ]
    ])
    if context.args and len(context.args) > 0:
        query = " ".join(context.args).strip().lower()
        matched = None
        for r_name in ROLE_DOSSIERS:
            if r_name.lower() == query or query in r_name.lower():
                matched = r_name
                break
        if matched:
            card = format_role_dossier(matched)
            if update.callback_query:
                try:
                    await update.callback_query.edit_message_text(card, reply_markup=guide_kb, parse_mode="Markdown")
                    return
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)
            await msg.reply_text(card, reply_markup=guide_kb, parse_mode="Markdown")
            return
        else:
            safe_query = html.escape(query)
            if update.callback_query:
                try:
                    await update.callback_query.edit_message_text(f"❌ <b>{safe_query}</b> nomli rol topilmadi. Ro'yxatdan birini tanlang.", reply_markup=guide_kb, parse_mode="HTML")
                    return
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)
            await msg.reply_text(f"❌ <b>{safe_query}</b> nomli rol topilmadi. Ro'yxatdan birini tanlang.", reply_markup=guide_kb, parse_mode="HTML")
            return

    text = (
        "📖 *Mukammal Rollar Yo'riqnomasi (24+ Rollar)*\n\n"
        "🔵 *Shahar aholisi:*\n"
        "• *Detektiv (🕵️‍♂️):* Har tun shaxsni tekshiradi yoki shubhalini otadi.\n"
        "• *Sherif (👮‍♂️):* Detektiv sherigi, shahar/qizillikni tekshiradi. Detektiv o'lsa o'rnini egallaydi.\n"
        "• *Doktor (🩺):* Har tun 1 kishini davolaydi.\n"
        "• *Tansoqchi (🛡️):* Nishonni joni evaziga himoyalaydi, qotil bilan birga halok bo'ladi.\n"
        "• *Advokat (⚖️):* Tunda mijoz tanlaydi, kunduzgi qatldan asraydi.\n"
        "• *Sayyoh (🚶):* Mehmonga boradi, mezbon o'lsa qotilga bevosita guvoh bo'ladi.\n"
        "• *Ruhshunos (🔮):* O'liklar olami (Graveyard) bilan bog'lanib sirlarni biladi.\n"
        "• *Mer (🎖️):* O'zini oshkor qilsa, ovozi 3 ta ovoz kuchiga aylanadi.\n"
        "• *Boy (💎):* Tunda tangalari evaziga birovning rolni 1 tunga ijaraga oladi.\n"
        "• *Qirol (👑):* Unga hujum bo'lsa o'lmaydi, hujumchini qatl yoki afv etadi.\n"
        "• *Begona (🕴️):* Tanlangan o'yinchining tungi harakatini bloklaydi.\n"
        "• *Savdogar (🛒):* Tunda himoya qalqoni va do'kon buyumlarini sovg'a qiladi.\n"
        "• *Fuqaro (👤):* Mantiq va ovozi bilan shaharni qutqaradi.\n\n"
        "🔴 *Mafiya sindikati:*\n"
        "• *Boshliq (👑 Don):* Qotillik nishonini belgilaydi. Tekshiruvda tinch fuqaro ko'rinadi.\n"
        "• *Qotil (🔪):* Boshliq buyurgan qurbonni yo'q qiladi. Boshliq o'lsa lider bo'ladi.\n"
        "• *Soya (🥷):* Tekshiruvlarni chalg'itadi, tergov natijalarini ag'daradi.\n"
        "• *Soxtachi (🎭):* Fuqaroning uyiga qora dalil tashlab, mafiya qilib ko'rsatadi.\n"
        "• *Maftunkor (💃):* Tunda o'yinchini jalb qilib harakatini muzlatadi (Roleblock).\n"
        "• *Kamikadze (💣):* Kunduzi dorda osilsa, ayblovchilardan birini portlatib ketadi.\n"
        "• *Bo'ri (🐺):* Tungi hujumlardan omon qolib, mafiyaning yirtqich quroli bo'ladi.\n\n"
        "🟡 *Yakkaxon neytrallar:*\n"
        "• *Joker (🃏):* Kunduzi o'zini osishlariga erishsa, YOLG'IZ O'ZI YUTADI!\n"
        "• *Maniak (🩸):* Har kecha 1 kishini o'ldiradi. Birinchi hujumga immunitetga ega.\n"
        "• *Pirotexnik (🔥):* Kerosin sepadi va istalgan tunda barchasini birdaniga yoqadi!\n"
        "• *Qasoskor (⚔️):* O'ldirilsa qotilni, osilsa ayblovchilardan birini o'zi bilan olib ketadi.\n"
        "• *Pul o'g'risi (💰):* Tunda boylardan 50 tangagacha o'g'irlaydi.\n"
        "• *Firibgar (🎪):* O'zini istalgan boshqa rol qilib niqoblaydi.\n\n"
        "💡 *Har bir rolning to'liq taktik yo'riqnomasi uchun:* `/guide <rol>`\n"
        "_Masalan:_ `/guide Detektiv` yoki `/guide Joker`"
    )
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=guide_kb, parse_mode="Markdown")
            return
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
    await msg.reply_text(text, reply_markup=guide_kb, parse_mode="Markdown")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or not msg:
        return
    if chat.type not in ("group", "supergroup"):
        from config import BOT_USERNAME
        add_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🛑 <b>O'yinni to'xtatish (/stop)</b>\n\n"
            "Ushbu buyruq faqat <b>Telegram guruhlarida ishlaydi</b> (o'yin yoki lobbyni to'xtatish uchun).",
            reply_markup=add_kb,
            parse_mode="HTML"
        )
        return

    chat_id = chat.id
    if chat_id not in games and chat_id not in lobbies:
        await msg.reply_text("ℹ️ Hozirda ushbu guruhda faol o'yin yoki lobby yo'q.")
        return

    # Check admin privileges (Fail closed on error)
    if not is_admin(user.id):
        try:
            member = await context.bot.get_chat_member(chat_id, user.id)
            if member.status not in ("administrator", "creator"):
                await msg.reply_text("❌ Faqat guruh admini o'yinni to'xtata oladi.")
                return
        except Exception as e:
            log.warning("get_chat_member failed on stop_cmd for %s in chat %s: %s", user.id, chat_id, e)
            await msg.reply_text("❌ Guruh adminlik huquqini tekshirib bo'lmadi. Amal bekor qilindi.")
            return

    lobby = abort_lobby(chat_id)
    if lobby:
        pinned_id = lobby.get("pinned_message_id")
        if pinned_id:
            try:
                await context.bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_id)
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

    await abort_game(chat_id)
    await msg.reply_text("🛑 O'yin yoki lobby ma'mur tomonidan to'xtatildi.")

async def reveal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or not user or not msg:
        return

    # Find active game either by group chat id or by user membership
    game = games.get(chat.id) if chat.type in ("group", "supergroup") else find_game_by_user(user.id)
    if not game:
        if chat.type == "private":
            from config import BOT_USERNAME
            pm_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "🎖️ <b>Shahar hokimi (Mer) oshkor bo'lishi (/reveal)</b>\n\n"
                "Hozirda siz ishtirok etayotgan faol o'yin topilmadi.\n"
                "Agar siz o'yinda <b>Mer</b> roliga ega bo'lsangiz, ushbu buyruq orqali o'zingizni shahar ahliga oshkor qilishingiz mumkin.",
                reply_markup=pm_kb,
                parse_mode="HTML"
            )
        else:
            await msg.reply_text("ℹ️ Hozirda siz ishtirok etayotgan faol o'yin topilmadi.")
        return

    chat_id = game["chat"]
    if game.get("roles", {}).get(user.id) != "Mer":
        await msg.reply_text("❌ Faqat shahar hokimi (Mer) o'zini oshkor qila oladi.")
        return

    if not game.get("alive", {}).get(user.id, False):
        await msg.reply_text("💀 Halok bo'lganlar o'zini oshkor qila olmaydi.")
        return

    if user.id in game.get("mayor_revealed", set()):
        await msg.reply_text("ℹ️ Siz allaqachon mer ekanligingizni e'lon qilgansiz.")
        return

    game.setdefault("mayor_revealed", set()).add(user.id)
    m_name = html.escape(display_name(game, user.id))
    announcement = (
        "👑 <b>Shahar hokimi (Mer) oshkor bo'ldi!</b>\n\n"
        f"👤 <b>{m_name}</b> rasman o'zining shahar hokimi ekanligini e'lon qildi!\n"
        "Uning har bir ovozi bundan buyon <b>3 ta ovoz</b> kuchiga teng bo'ladi."
    )
    await context.bot.send_message(chat_id=chat_id, text=announcement, parse_mode="HTML")
    if chat.id != chat_id:
        await msg.reply_text("🎖️ Siz shahar hokimi ekanligingizni guruhda rasman e'lon qildingiz!")
    await save_runtime(game)

async def chiqish_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or not msg or not user:
        return
    if chat.type not in ("group", "supergroup"):
        from config import BOT_USERNAME
        add_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🚪 <b>Lobbyni tark etish (/chiqish)</b>\n\n"
            "Ushbu buyruq faqat <b>Telegram guruhlarida</b> ochilgan lobbyni tark etish uchun ishlatiladi.",
            reply_markup=add_kb,
            parse_mode="HTML"
        )
        return
    lobby = lobbies.get(chat.id)
    if lobby and lobby.get("open"):
        if user.id in lobby["players"]:
            lobby["players"].remove(user.id)
            lobby["names"].pop(user.id, None)
            lobby["badges"].pop(user.id, None)
            await msg.reply_text(f"🚪 *{user.full_name}* lobbyni tark etdi.", parse_mode="Markdown")
            try:
                await context.bot.edit_message_text(
                    chat_id=chat.id,
                    message_id=lobby["message_id"],
                    text=lobby_text(lobby),
                    reply_markup=lobby_keyboard(chat.id, include_bot_link=True),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            return

    game = games.get(chat.id)
    if game and user.id in game.get("players", []):
        if not game.get("alive", {}).get(user.id, False):
            await msg.reply_text("💀 Siz allaqachon halok bo'lgansiz.")
            return

        game["alive"][user.id] = False
        p_name = display_name(game, user.id)
        await msg.reply_text(
            f"🚪 <b>{html.escape(p_name)}</b> o'yinni tark etdi (halok bo'ldi deb hisoblanadi).",
            parse_mode="HTML"
        )

        from core.engine import check_winner, save_runtime
        await save_runtime(game)

        won = await check_winner(context, game)
        if won:
            return

        cur_phase = game.get("phase")
        if cur_phase == "verdict" and game.get("accused_uid") == user.id:
            from core.engine import cancel_game_timer
            cancel_game_timer(game)
            await msg.reply_text("⚖️ Ayblanuvchi o'yinni tark etgani sababli sud yakunlandi. Shahar tun quchog'iga kirdi.")
            game["night"] = game.get("night", 1) + 1
            from phases.night import start_night
            await start_night(context, game)
            return
        elif cur_phase == "voting":
            alive_voters = [u for u in game.get("players", []) if game.get("alive", {}).get(u, False)]
            votes = game.get("votes", {})
            if alive_voters and all(u in votes for u in alive_voters):
                from phases.voting import finish_voting
                await finish_voting(context, game)
                return
        return

    await msg.reply_text("ℹ️ Siz hech qanday faol o'yinda yoki lobbida emassiz.")

async def salom_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchiga 'Assalomu alaykum' deb uni metka (mention) qilib javob beradi."""
    user = update.effective_user
    chat = update.effective_chat
    msg = update.message or update.effective_message
    if not user or not msg:
        return

    await ensure_user(user)
    if chat and chat.type in ("group", "supergroup"):
        await track_group_member(chat.id, user)

    name = (user.full_name or user.first_name or "Do'stim")[:40]
    mention = f'<a href="tg://user?id={user.id}">{html.escape(name)}</a>'
    username_tag = f" (@{user.username})" if user.username else ""

    text = (
        f"👋 <b>Assalomu alaykum, {mention}{username_tag}!</b> 🕵️‍♂️✨\n\n"
        f"Detektiv Mafia olamiga xush kelibsiz! Shahar ko'chalarida adolat o'rnatishga tayyormisiz? 🎭\n\n"
        f"🎮 <b>Asosiy buyruqlar:</b>\n"
        f"• <code>/game</code> — Guruhda yangi Mafia o'yinini ochish\n"
        f"• <code>/call</code> — Barcha o'yinchilarni o'yinga chaqirish\n"
        f"• <code>/settings</code> — Guruh sozlamalari (vaqt va rollar)"
    )

    adm = is_admin(user.id, getattr(user, "username", ""))
    kb = main_menu_keyboard(adm) if chat and chat.type == "private" else None
    reply_to = update.message.message_id if update.message else None
    await msg.reply_text(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        reply_to_message_id=reply_to
    )

async def call_players_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or chat.type not in ("group", "supergroup"):
        if msg:
            from config import BOT_USERNAME
            add_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "📣 <b>O'yinchilarni chaqirish (/call)</b>\n\n"
                "Ushbu buyruq faqat <b>Telegram guruhlarida</b> o'yinchilarni mafia o'yiniga chorlash uchun ishlatiladi.",
                reply_markup=add_kb,
                parse_mode="HTML"
            )
        return

    if user:
        await ensure_user(user)
        await track_group_member(chat.id, user)

    caller_name = (user.full_name or user.first_name)[:40] if user else ""
    from phases.lobby import call_players_in_chat
    await call_players_in_chat(context, chat.id, caller_name)

async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not user or not msg:
        return

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    adm = is_admin(user.id, getattr(user, "username", "")) if user else False

    if is_group:
        if not adm:
            return
        pm_link = f"https://t.me/{BOT_USERNAME}?start=plan"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            "🗺️ <b>O'yin Rejasi va Mexanikasi</b>\n\n"
            "Admin boshqaruv rejasi faqat botning shaxsiy chatida ochiladi:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    plan_text = (
        f"{tg_emoji('game_start', '🎮')} <b>DETEKTIV MAFIA — TO'LIQ O'YIN REJASI VA MEXANIKASI</b>\n\n"
        f"{tg_emoji('trigger', '✨')} <b>1. O'yin Bosqichlari:</b>\n"
        f"• {tg_emoji('night', '🌙')} <b>Tun:</b> Yashirin harakatlar — {tg_emoji('mafia', '🔪')} Mafia suiqasdi, {tg_emoji('doctor', '🩺')} Shifokor davosi, {tg_emoji('detective', '🕵️‍♂️')} Detektiv tekshiruvi.\n"
        f"• {tg_emoji('day', '☀️')} <b>Kun:</b> Shahar uyg'onadi, {tg_emoji('dead', '💀')} qurbonlar va tungi xabarlar e'lon qilinadi.\n"
        f"• {tg_emoji('voting', '🗳️')} <b>Ovoz berish:</b> Shahar gumonlanuvchini sudga tortish uchun ovoz beradi.\n"
        f"• {tg_emoji('voting', '⚖️')} <b>Sud (Hukm):</b> Gumondor sud minbariga chiqadi. Shahar: {tg_emoji('mafia', '⚔️')} Qatl yoki {tg_emoji('civilian_win', '🕊️')} Afv!\n\n"
        f"{tg_emoji('settings_roles', '🎭')} <b>2. Rollar va Taqsimot Balansi:</b>\n"
        f"• {tg_emoji('civilian_team', '🔵')} <b>Shahar (Town):</b> {tg_emoji('detective', '🕵️‍♂️')} Detektiv, {tg_emoji('sheriff', '👮‍♂️')} Sherif (faqat 7+ kishida), {tg_emoji('doctor', '🩺')} Doktor, Tansoqchi, Advokat, Sayyoh, Ruhshunos, Mer, Boy, Qirol, Savdogar, Fuqaro.\n"
        f"• {tg_emoji('mafia_team', '🔴')} <b>Mafiya (Red):</b> {tg_emoji('don', '👑')} Boshliq (Don), {tg_emoji('mafia', '🔪')} Qotil, Soya, Soxtachi, Maftunkor, Kamikadze, Bo'ri.\n"
        f"• {tg_emoji('don', '🟡')} <b>Yakkaxonlar (Solo):</b> Joker, Maniak, Pirotexnik, Qasoskor, Pul o'g'risi, Firibgar.\n\n"
        f"• {tg_emoji('item_shield', '🛡️', 'SHOP')} <b>3. 3-Tun AFK Kafolati:</b>\n"
        f"Bir martalik ovoz bermaslikka jazo yo'q! {tg_emoji('timer', '⏱️')} Faqat ketma-ket 3 tun harakatsiz qolgandagina uxlash jarimasi beriladi.\n\n"
        f"{tg_emoji('settings_gear', '⚙️')} <b>Sozlamalar:</b> <code>/settings</code> orqali vaqtlar va rollarni moslashtiring! {tg_emoji('trigger', '🚀')}"
    )
    chat_id = chat.id if chat else 0
    buttons = []
    if adm:
        buttons.append([InlineKeyboardButton("⚙️ Sozlamalar (/settings)", callback_data=f"sett:menu:{chat_id}")])
    buttons.append([InlineKeyboardButton("📖 Rollar Qo'llanmasi", callback_data="guide_roles")])
    plan_kb = InlineKeyboardMarkup(buttons)
    await msg.reply_text(plan_text, reply_markup=plan_kb, parse_mode="HTML")

async def boost_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg = update.message or update.effective_message
    if not user or not msg:
        return

    boost_text = (
        f"{tg_emoji('trigger', '🚀')} <b>TELEGRAM PREMIUM & GURUHNI BOOST QILISH</b>\n\n"
        f"{tg_emoji('badge_special', '💎', 'USER_SETTINGS')} <b>Detektiv Mafia loyihasini qo'llab-quvvatlang!</b>\n\n"
        "Guruhimiz yoki botimizni Telegram Premium orqali <b>Boost</b> qilgan o'yinchilarga maxsus imtiyozlar beriladi:\n\n"
        f"{tg_emoji('trigger', '✨')} <b>Premium & Booster Imtiyozlari:</b>\n"
        f"• {tg_emoji('don', '👑')} <b>Eksklyuziv VIP Nishonlar:</b> Ismingiz yonida porlab turuvchi animatsiyali emojilar!\n"
        f"• {tg_emoji('coin', '💰', 'SHOP')} <b>2x Bonus:</b> O'yinlarda g'alaba uchun 2 barobar ko'proq Coin va Gold yutuqlari.\n"
        f"• {tg_emoji('detective', '🎭')} <b>Yangi Rollarga Erta Kirish:</b> Sinovdagi yangi rollar birinchi sizga beriladi.\n"
        f"• {tg_emoji('item_shield', '🛡️', 'SHOP')} <b>Sindikat Imtiyozi:</b> Klan ochish va rivojlantirishda 50% chegirma.\n\n"
        f"Guruhga boost berish uchun guruh profiliga kiring va <b>«Boost Group»</b> tugmasini bosing! {tg_emoji('trigger', '🔥')}{tg_emoji('trigger', '✨')}"
    )
    adm = is_admin(user.id, getattr(user, "username", "")) if user else False
    is_pm = bool(chat and getattr(chat, "type", "") == "private")

    buttons = []
    if is_pm:
        buttons.append([InlineKeyboardButton("💎 VIP Do'kon", callback_data="shop_gold")])
        if adm:
            buttons[0].append(InlineKeyboardButton("👑 Master Admin Paneli", callback_data="adm:menu"))
    else:
        buttons.append([InlineKeyboardButton("💬 VIP Do'kon (Shaxsiy)", url=f"https://t.me/{BOT_USERNAME}?start=shop")])

    boost_kb = InlineKeyboardMarkup(buttons)
    await msg.reply_text(boost_text, reply_markup=boost_kb, parse_mode="HTML")

async def goal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    await ensure_user(user)

    from core.engine import find_game_by_user
    game = find_game_by_user(user.id)
    if game and game.get("alive", {}).get(user.id, False):
        role = game.get("roles", {}).get(user.id)
        from roles.dossier import get_role_dossier
        dossier = get_role_dossier(role)
        role_emoji = tg_emoji('don', '👑') if role == 'Boshliq' else (
            tg_emoji('mafia', '🔪') if ROLES.get(role) == 'red' else (
                tg_emoji('detective', '🕵️‍♂️') if role in ('Detektiv', 'Sherif') else (
                    tg_emoji('doctor', '🩺') if role == 'Doktor' else tg_emoji(dossier.icon, dossier.icon)
                )
            )
        )
        team_emoji = tg_emoji('mafia_win', '🔴') if ROLES.get(role) == 'red' else tg_emoji('civilian_win', '🔵')
        text = (
            f"{tg_emoji('badge_target', '🎯', 'USER_SETTINGS')} <b>SIZNING O'YIN MAQSADINGIZ</b>\n\n"
            f"{tg_emoji('settings_roles', '🎭')} <b>Rolingiz:</b> {role_emoji} <b>{dossier.role_name}</b>\n"
            f"{tg_emoji('trigger', '🏷️')} <b>Jamoangiz:</b> {team_emoji} <b>{dossier.team_display}</b>\n\n"
            f"{tg_emoji('trigger', '⚡')} <b>Bosh Maqsad:</b>\n{dossier.goal}\n\n"
            f"{tg_emoji('trigger', '💡')} <i>Taktik maslahat:</i> {dossier.tactical_tip}"
        )
    else:
        text = (
            f"{tg_emoji('badge_target', '🎯', 'USER_SETTINGS')} <b>DETEKTIV MAFIA — JAMOAVIY MAQSADLAR</b>\n\n"
            f"{tg_emoji('civilian_team', '🔵', 'GAMEPLAY')} <b>Shahar (Town) Maqsadi:</b>\n"
            f"Barcha {tg_emoji('mafia_team', '🔴')} Mafiya a'zolari va {tg_emoji('dead', '💀')} shafqatsiz qotillarni fosh qilish, {tg_emoji('detective', '🕵️‍♂️')} tergov va {tg_emoji('voting', '⚖️')} sud orqali shaharni tozalash!\n\n"
            f"{tg_emoji('mafia_team', '🔴', 'GAMEPLAY')} <b>Mafiya (Mafia) Maqsadi:</b>\n"
            f"Shahar aholisini {tg_emoji('night', '🌙')} tunda va {tg_emoji('voting', '⚖️')} sudda yo'q qilib, ko'pchilikni egallash va shahar ustidan nazorat o'rnatish!\n\n"
            f"{tg_emoji('don', '🟡')} <b>Yakkaxonlar (Solo) Maqsadi:</b>\n"
            f"• {tg_emoji('mafia_win', '🃏')} <b>Joker:</b> Shaharni aldab o'zini dorda ostirish!\n"
            f"• {tg_emoji('mafia_win', '🩸')} <b>Maniak:</b> Shahar va mafiyaning barchasini yo'q qilib, yolg'iz tirik qolish!\n"
            f"• {tg_emoji('trigger', '🔥')} <b>Pirotexnik:</b> Uylarga kerosin quyib, barchasini olovda yoqish!\n"
            f"• {tg_emoji('item_knife', '⚔️')} <b>Qasoskor:</b> O'z dushmanidan qasos olish!\n"
            f"• {tg_emoji('coin', '💰')} <b>Pul o'g'risi:</b> Eng boy o'yinchiga aylanish!\n"
            f"• {tg_emoji('detective', '🎪')} <b>Firibgar:</b> Soxta qiyofaga kirib omon qolish!"
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Barcha Rollar Qo'llanmasi", callback_data="guide_roles")],
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
    ])
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def teamwork_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    await ensure_user(user)

    text = (
        f"{tg_emoji('bro', '🤝')} <b>DETEKTIV MAFIA — JAMOAVIY HAMKORLIK VA ITTIFOQLAR PREVIEW</b>\n\n"
        f"{tg_emoji('trigger', '✨')} <b>1. {tg_emoji('detective', '🕵️‍♂️')}{tg_emoji('sheriff', '👮‍♂️')} Detektiv va Sherif Hamkorligi:</b>\n"
        f"• Detektiv tirik ekan, shahar xavfsizligini ta'minlab, faol tergov olib boradi.\n"
        f"• Sherif esa Detektiv tirik paytda passiv turadi va uning o'rnini kutadi.\n"
        f"• <b>Detektiv {tg_emoji('dead', '💀')} halok bo'lgach:</b> Sherif darhol barcha detektivlik vakolatlariga ega bo'lib Detektivga aylanadi!\n\n"
        f"{tg_emoji('trigger', '✨')} <b>2. {tg_emoji('mafia_team', '🔪')} Mafiya Sindikati:</b>\n"
        f"• {tg_emoji('don', '👑')} <b>Boshliq (Don)</b> tungi qotillik nishonini belgilaydi.\n"
        f"• <b>Qotil</b> va <b>Bo'ri</b> Boshliq bilan birga harakatlanadi. Agar Boshliq {tg_emoji('dead', '💀')} halok bo'lsa, mustaqil ovga chiqadi!\n"
        f"• <b>Soya</b> va <b>Soxtachi</b> tergovchilarni chalg'itib, soxta dalillar orqali mafiyani himoyalaydi.\n\n"
        f"{tg_emoji('trigger', '✨')} <b>3. {tg_emoji('doctor', '🩺')}{tg_emoji('doctor_save', '💊')} Shifokor va Tansoqchi Himoyasi:</b>\n"
        f"• Doktor har kecha bir fuqaroni {tg_emoji('doctor_save', '💊')} davolaydi yoki o'zini qutqaradi (har o'yinda 1 marta o'zini davolash).\n"
        f"• Tansoqchi esa o'z jonini fido qilib bo'lsa ham nishonni qutqarib qoladi!\n\n"
        f"{tg_emoji('trigger', '✨')} <b>4. Ijtimoiy Ittifoqlar (Social Bonds):</b>\n"
        f"• {tg_emoji('para', '💍')} <code>/para</code> — Juftlik: do'stingiz bilan maxsus sevgi rishtasi.\n"
        f"• {tg_emoji('bro', '🤝')} <code>/bro</code> — Birodarlik: do'stingiz bilan ishonchli do'stlik rishtasi.\n"
        f"• Guruhda kimningdir xabariga 'Reply' qilib buyruqni yuboring va so'rov yuboriladi!"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💍 Juftlik (/mypara)", callback_data="my_para_info"), InlineKeyboardButton("🤝 Birodar (/mybro)", callback_data="my_bro_info")],
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
    ])
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def use_item_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    await ensure_user(user)

    from core.engine import find_game_by_user
    game = find_game_by_user(user.id)
    if not game:
        await msg.reply_text("ℹ️ Buyumlarni faqat faol o'yin davomida ishlatish mumkin.")
        return

    args = context.args or []
    if not args:
        await msg.reply_text(
            "🎒 <b>O'yinda buyum ishlatish:</b>\n"
            "Foydalanish: <code>/use extra_vote</code> yoki <code>/use shield</code>\n\n"
            "⚠️ <i>Har bir buyumdan bitta o'yinda faqat 1 marta foydalanish mumkin!</i>",
            parse_mode="HTML"
        )
        return

    item_id = "_".join(args).lower().strip()
    from core.items import normalize_item_id, consume_game_item
    canonical = normalize_item_id(item_id)
    if canonical == "extra_vote" and game.get("phase") != "voting":
        await msg.reply_text("❌ Qo'shimcha ovozni faqat ovoz berish paytida ishlatish mumkin!")
        return

    success, reply = await consume_game_item(game, user.id, item_id)
    await msg.reply_text(reply, parse_mode="HTML")



