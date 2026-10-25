import html
import logging
from typing import Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import ADMIN_ID, ROLES, BOT_USERNAME
from database.models import (
    ensure_user, get_user, get_balance, change_balance, get_badge,
    get_top_players, is_admin, get_will, set_will, track_group_member
)
from core.engine import (
    games, lobbies, find_game_by_user, find_lobby_by_user, display_name,
    cancel_game_timer, cancel_lobby_timer, save_runtime
)
from phases.lobby import create_lobby, lobby_text, lobby_keyboard
from core.will import save_player_will, format_will_announcement
from core.visuals import anim_emoji

log = logging.getLogger("detektiv.handlers.commands")

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 O'yin ochish", callback_data="menu_game"),
            InlineKeyboardButton("🛒 Do'kon (Shop)", callback_data="menu_shop")
        ],
        [
            InlineKeyboardButton("💰 Balans", callback_data="menu_balance"),
            InlineKeyboardButton("🏆 TOP Reyting", callback_data="menu_rating")
        ],
        [
            InlineKeyboardButton("👤 Profil", callback_data="menu_profile"),
            InlineKeyboardButton("📜 Vasiyatnoma", callback_data="menu_will")
        ],
        [
            InlineKeyboardButton("📖 Rollar qo'llanmasi", callback_data="menu_guide"),
            InlineKeyboardButton("🛡️ Sindikat / Klan", callback_data="menu_clan")
        ]
    ])

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
                        except Exception:
                            pass
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
                                        f"🌙 *Tun #{night_num}*\n"
                                        f"🎭 Sizning rolingiz: *{role}*\n\n"
                                        "✅ Siz bugungi tungi amalingizni allaqachon bajardingiz. Tong otishini kuting!",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="Markdown"
                                    )
                                else:
                                    kb = get_role_action_buttons(active_game, uid)
                                    if kb:
                                        await update.message.reply_text(
                                            f"🌙 *Tun #{night_num} amallari*\n"
                                            f"🎭 Sizning rolingiz: *{role}*\n"
                                            "Quyidagi tugmalardan birini tanlang:",
                                            reply_markup=kb,
                                            parse_mode="Markdown"
                                        )
                                    else:
                                        await update.message.reply_text(
                                            f"🌙 *Tun #{night_num}*\n"
                                            f"🎭 Sizning rolingiz: *{role}*\n\n"
                                            "Bu tunda sizdan maxsus amal talab etilmaydi. Tong otishini kuting!",
                                            reply_markup=return_to_group_keyboard(active_game),
                                            parse_mode="Markdown"
                                        )
                            elif phase == "voting":
                                night_num = active_game.get("night", 1)
                                if uid in active_game.get("votes", {}):
                                    tgt = active_game["votes"][uid]
                                    tgt_name = "🕊️ Hech kimga" if tgt == "none" else display_name(active_game, int(tgt))
                                    await update.message.reply_text(
                                        f"🗳️ *Ovoz berish (#{night_num}-kun)*\n\n"
                                        f"✅ Siz allaqachon ovoz bergansiz (*{tgt_name}*)!",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="Markdown"
                                    )
                                else:
                                    vkb = get_voting_keyboard(active_game, is_pm=True)
                                    await update.message.reply_text(
                                        f"🗳️ *Ovoz berish (#{night_num}-kun)*\n\n"
                                        "Sud minbariga chiqarish uchun gumonlanuvchini tanlang:",
                                        reply_markup=vkb,
                                        parse_mode="Markdown"
                                    )
                            elif phase == "verdict":
                                accused = active_game.get("accused_uid")
                                accused_name = display_name(active_game, accused)
                                if uid == accused:
                                    await update.message.reply_text(
                                        f"⚖️ *Sud minbari*\n\n"
                                        "Siz hozir sud minbaridasiz! Fuqarolar sizning taqdiringizni hal qilmoqda.",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="Markdown"
                                    )
                                elif uid in active_game.get("verdict_votes", {}):
                                    v = active_game["verdict_votes"][uid]
                                    v_str = "⚔️ QATL" if v == "kill" else "🕊️ AFV"
                                    await update.message.reply_text(
                                        f"⚖️ *Sud hukmi ({accused_name})*\n\n"
                                        f"✅ Siz allaqachon ovoz bergansiz (*{v_str}*)!",
                                        reply_markup=return_to_group_keyboard(active_game),
                                        parse_mode="Markdown"
                                    )
                                else:
                                    vkb = verdict_keyboard(target_chat_id, accused, is_pm=True, game_or_link=active_game)
                                    await update.message.reply_text(
                                        f"⚖️ *Sud minbari*\n\n"
                                        f"Ayblanuvchi: *{accused_name}*\n"
                                        "Uning taqdirini hal qiling: qatl etilsinmi yoki afv etilsin?",
                                        reply_markup=vkb,
                                        parse_mode="Markdown"
                                    )
                            else:
                                await update.message.reply_text(
                                    "☀️ *Kunduzgi muhokama fazasi!*\n\n"
                                    "Guruhga qaytib, boshqa o'yinchilar bilan fikr almashing va dalillarni tahlil qiling.",
                                    reply_markup=return_to_group_keyboard(active_game),
                                    parse_mode="Markdown"
                                )
                            return
                        else:
                            await update.message.reply_text(
                                graveyard_status_text(active_game, uid),
                                reply_markup=graveyard_menu_keyboard(active_game.get("_db_id", 0), group_link=group_link),
                                parse_mode="Markdown"
                            )
                            return
                    else:
                        await update.message.reply_text(
                            "👁️ *Siz bu o'yinda tomoshabinsiz.*\n\n"
                            f"Faza: *{active_game.get('phase', '').capitalize()}*\n"
                            f"Tiriklar: *{sum(1 for v in active_game.get('alive', {}).values() if v)}* nafar",
                            reply_markup=return_to_group_keyboard(active_game),
                            parse_mode="Markdown"
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
        elif arg == "profile":
            await profile_cmd(update, context)
            return
        elif arg == "balance":
            await balance_cmd(update, context)
            return
        elif arg == "will":
            await will_cmd(update, context)
            return
        elif arg == "shop":
            from handlers.shop import shop_cmd
            await shop_cmd(update, context)
            return
        elif arg == "guide":
            await guide_cmd(update, context)
            return
        elif arg == "rating":
            await rating_cmd(update, context)
            return
        elif arg == "clan":
            from handlers.clans import clan_cmd
            await clan_cmd(update, context)
            return
        elif arg == "admin":
            from handlers.admin_panel import admin_cmd
            await admin_cmd(update, context)
            return
        elif arg == "stats":
            from handlers.admin_panel import stats_cmd
            await stats_cmd(update, context)
            return

    welcome_text = (
        "🎭 *Detektiv Mafia Botiga Xush Kelibsiz!*\n\n"
        "Shahar va mafiya o'rtasidagi shiddatli psixologik kurash.\n\n"
        "🌟 Imkoniyatlar:\n"
        "• 🕵️ 24+ noyob rollar balansi\n"
        "• 🔍 Kriminalistik ashyoviy dalillar tergovi\n"
        "• 📜 So'nggi Vasiyatnoma tizimi (/will)\n"
        "• 🌫️ Dinamik shahar hodisalari va ob-havo\n"
        "• 👻 Ruhlar olami va o'liklar bashorati\n\n"
        "Quyidagi menyu orqali kerakli bo'limni tanlang:"
    )

    if chat.type == "private":
        await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
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
    if not chat or chat.type not in ("group", "supergroup"):
        if update.message:
            await update.message.reply_text("❌ Ushbu buyruq faqat Telegram guruhlarida ishlaydi.")
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
    if not context.args:
        current_will = await get_will(user.id)
        if current_will:
            await msg.reply_text(
                f"{scroll} <b>Sizning amaldagi Vasiyatnomangiz:</b>\n\n"
                f"<blockquote>{html.escape(current_will)}</blockquote>\n\n"
                f"Yangi vasiyat yozish uchun: <code>/will &lt;matn&gt;</code>",
                parse_mode="HTML"
            )
        else:
            await msg.reply_text(
                f"{scroll} <b>Sizda hali Vasiyatnoma yo'q!</b>\n\n"
                "Tunda yoki kunduzi o'ldirilganingizda butun shaharga sirli ma'lumot qoldirish uchun:\n"
                "<code>/will Mening vasiyatim shu...</code> buyrug'idan foydalaning.",
                parse_mode="HTML"
            )
        return

    text = " ".join(context.args)
    await save_player_will(user.id, text)
    await msg.reply_text(
        "✅ <b>Vasiyatnomangiz muvaffaqiyatli saqlandi!</b>\n"
        "Agar o'yinda halok bo'lsangiz, ushbu xabar shahar ahlisiga e'lon qilinadi.",
        parse_mode="HTML"
    )

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

    badge = await get_badge(user.id) or "Yo'q"
    admin_tag = " (Admin)" if is_admin(user.id, getattr(user, "username", "")) else ""

    text = (
        f"<tg-emoji emoji-id=\"5463134628678688463\">👤</tg-emoji> <b>Profil:</b> <b>{html.escape(u['name'])}</b>{admin_tag}\n\n"
        f"<tg-emoji emoji-id=\"5429462837318049280\">🪙</tg-emoji> Tangalar: <b>{'∞' if is_admin(user.id, getattr(user, 'username', '')) else u['coin']}</b>\n"
        f"<tg-emoji emoji-id=\"5429462837318049280\">🥇</tg-emoji> Oltin: <b>{'∞' if is_admin(user.id, getattr(user, 'username', '')) else u['gold']}</b>\n"
        f"🎮 Jami o'yinlar: <b>{u['games']}</b>\n"
        f"<tg-emoji emoji-id=\"5368324170671202286\">🏆</tg-emoji> G'alabalar: <b>{u['wins']}</b>\n"
        f"❌ Mag'lubiyatlar: <b>{u['losses']}</b>\n"
        f"<tg-emoji emoji-id=\"5370845348392576392\">🎖️</tg-emoji> Faol belgi: <b>{html.escape(badge)}</b>"
    )
    await msg.reply_text(text, parse_mode="HTML")

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
    await msg.reply_text(
        f"<tg-emoji emoji-id=\"5429462837318049280\">💰</tg-emoji> <b>Sizning balansingiz:</b>\n\n"
        f"<tg-emoji emoji-id=\"5429462837318049280\">🪙</tg-emoji> Tangalar: <b>{coins} Coin</b>\n"
        f"<tg-emoji emoji-id=\"5429462837318049280\">🥇</tg-emoji> Oltinlar: <b>{gold} Gold</b>",
        parse_mode="HTML"
    )

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
    await msg.reply_text("\n".join(lines), parse_mode="HTML")

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
    if context.args and len(context.args) > 0:
        query = " ".join(context.args).strip().lower()
        matched = None
        for r_name in ROLE_DOSSIERS:
            if r_name.lower() == query or query in r_name.lower():
                matched = r_name
                break
        if matched:
            card = format_role_dossier(matched)
            await msg.reply_text(card, parse_mode="Markdown")
            return
        else:
            await msg.reply_text(f"❌ *{query}* nomli rol topilmadi. Ro'yxatdan birini tanlang.", parse_mode="Markdown")

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
    await msg.reply_text(text, parse_mode="Markdown")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in ("group", "supergroup"):
        return

    chat_id = chat.id
    if chat_id not in games and chat_id not in lobbies:
        await update.message.reply_text("ℹ️ Hozirda ushbu guruhda faol o'yin yoki lobby yo'q.")
        return

    # Check admin privileges
    if not is_admin(user.id):
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Faqat guruh admini o'yinni to'xtata oladi.")
            return

    lobby = lobbies.pop(chat_id, None)
    if lobby:
        cancel_lobby_timer(lobby)
        pinned_id = lobby.get("pinned_message_id")
        if pinned_id:
            try:
                await context.bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_id)
            except Exception:
                pass
    game = games.pop(chat_id, None)
    if game:
        cancel_game_timer(game)
    await update.message.reply_text("🛑 O'yin yoki lobby ma'mur tomonidan to'xtatildi.")

async def reveal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    # Find active game either by group chat id or by user membership
    game = games.get(chat.id) if chat.type in ("group", "supergroup") else find_game_by_user(user.id)
    if not game:
        await update.message.reply_text("ℹ️ Hozirda siz ishtirok etayotgan faol o'yin topilmadi.")
        return

    chat_id = game["chat"]
    if game.get("roles", {}).get(user.id) != "Mer":
        await update.message.reply_text("❌ Faqat shahar hokimi (Mer) o'zini oshkor qila oladi.")
        return

    if not game.get("alive", {}).get(user.id, False):
        await update.message.reply_text("💀 Halok bo'lganlar o'zini oshkor qila olmaydi.")
        return

    if user.id in game.get("mayor_revealed", set()):
        await update.message.reply_text("ℹ️ Siz allaqachon mer ekanligingizni e'lon qilgansiz.")
        return

    game.setdefault("mayor_revealed", set()).add(user.id)
    m_name = display_name(game, user.id)
    announcement = (
        "👑 *Shahar hokimi (Mer) oshkor bo'ldi!*\n\n"
        f"👤 *{m_name}* rasman o'zining shahar hokimi ekanligini e'lon qildi!\n"
        "Uning har bir ovozi bundan buyon *3 ta ovoz* kuchiga teng bo'ladi."
    )
    await context.bot.send_message(chat_id=chat_id, text=announcement, parse_mode="Markdown")
    if chat.id != chat_id:
        await update.message.reply_text("🎖️ Siz shahar hokimi ekanligingizni guruhda rasman e'lon qildingiz!")
    await save_runtime(game)

async def chiqish_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat:
        return
    lobby = lobbies.get(chat.id)
    if lobby and lobby.get("open"):
        if user.id in lobby["players"]:
            lobby["players"].remove(user.id)
            lobby["names"].pop(user.id, None)
            lobby["badges"].pop(user.id, None)
            await update.message.reply_text(f"🚪 *{user.full_name}* lobbyni tark etdi.", parse_mode="Markdown")
            try:
                await context.bot.edit_message_text(
                    chat_id=chat.id,
                    message_id=lobby["message_id"],
                    text=lobby_text(lobby),
                    reply_markup=lobby_keyboard(chat.id, include_bot_link=True),
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return
    await update.message.reply_text("ℹ️ Siz hech qanday faol lobbida emassiz.")

async def salom_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchiga 'Assalomu alaykum' deb uni metka (mention) qilib javob beradi."""
    user = update.effective_user
    chat = update.effective_chat
    if not user:
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

    if update.message:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id
        )

async def call_players_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in ("group", "supergroup"):
        if update.message:
            await update.message.reply_text("❌ Ushbu buyruq faqat Telegram guruhlarida ishlaydi.")
        return

    if user:
        await ensure_user(user)
        await track_group_member(chat.id, user)

    caller_name = (user.full_name or user.first_name)[:40] if user else ""
    from phases.lobby import call_players_in_chat
    await call_players_in_chat(context, chat.id, caller_name)

async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_text = (
        "🗺️ <b>DETEKTIV MAFIA — TO'LIQ O'YIN REJASI VA MEXANIKASI</b>\n\n"
        "✨ <b>1. O'yin Bosqichlari:</b>\n"
        "• 🌙 <b>Tun:</b> Yashirin harakatlar — Mafia suiqasdi, Shifokor davosi, Detektiv tekshiruvi.\n"
        "• ☀️ <b>Kun:</b> Shahar uyg'onadi, qurbonlar va tungi xabarlar e'lon qilinadi.\n"
        "• 🗳 <b>Ovoz berish:</b> Shahar gumonlanuvchini sudga tortish uchun ovoz beradi.\n"
        "• ⚖️ <b>Sud (Hukm):</b> Gumondor sud minbariga chiqadi. Shahar: ⚔️ Qatl yoki 🕊️ Afv!\n\n"
        "🎭 <b>2. Rollar va Taqsimot Balansi:</b>\n"
        "• 🔵 <b>Shahar (Town):</b> Detektiv, Sherif (faqat 7+ kishida), Doktor, Tansoqchi, Advokat, Sayyoh, Ruhshunos, Mer, Boy, Qirol, Savdogar, Fuqaro.\n"
        "• 🔴 <b>Mafiya (Red):</b> Boshliq (Don), Qotil, Soya, Soxtachi, Maftunkor, Kamikadze, Bo'ri.\n"
        "• 🟡 <b>Yakkaxonlar (Solo):</b> Joker, Maniak, Pirotexnik, Qasoskor, Pul o'g'risi, Firibgar.\n\n"
        "🛡️ <b>3. 3-Tun AFK Kafolati:</b>\n"
        "Bir martalik ovoz bermaslikka jazo yo'q! Faqat ketma-ket 3 tun harakatsiz qolgandagina uxlash jarimasi beriladi.\n\n"
        "⚙️ <b>Sozlamalar:</b> <code>/settings</code> orqali vaqtlar va rollarni moslashtiring! 🚀"
    )
    chat_id = update.effective_chat.id if update.effective_chat else 0
    plan_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Sozlamalar (/settings)", callback_data=f"sett:menu:{chat_id}"),
            InlineKeyboardButton("📖 Rollar Qo'llanmasi", callback_data="guide_roles")
        ]
    ])
    await update.message.reply_text(plan_text, reply_markup=plan_kb, parse_mode="HTML")

async def boost_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    boost_text = (
        f"{anim_emoji('rocket', '🚀')} <b>TELEGRAM PREMIUM & GURUHNI BOOST QILISH</b>\n\n"
        f"{anim_emoji('gem', '💎')} <b>Detektiv Mafia loyihasini qo'llab-quvvatlang!</b>\n\n"
        "Guruhimiz yoki botimizni Telegram Premium orqali <b>Boost</b> qilgan o'yinchilarga maxsus imtiyozlar beriladi:\n\n"
        "✨ <b>Premium & Booster Imtiyozlari:</b>\n"
        f"• {anim_emoji('crown', '👑')} <b>Eksklyuziv VIP Nishonlar:</b> Ismingiz yonida porlab turuvchi animatsiyali emojilar!\n"
        f"• {anim_emoji('coin', '💰')} <b>2x Bonus:</b> O'yinlarda g'alaba uchun 2 barobar ko'proq Coin va Gold yutuqlari.\n"
        f"• {anim_emoji('detective', '🎭')} <b>Yangi Rollarga Erta Kirish:</b> Sinovdagi yangi rollar birinchi sizga beriladi.\n"
        f"• {anim_emoji('shield', '🛡️')} <b>Sindikat Imtiyozi:</b> Klan ochish va rivojlantirishda 50% chegirma.\n\n"
        "Guruhga boost berish uchun guruh profiliga kiring va <b>«Boost Group»</b> tugmasini bosing! 🔥✨"
    )
    adm = is_admin(user.id, getattr(user, "username", "")) if user else False
    is_pm = bool(chat and getattr(chat, "type", "") == "private")

    buttons = [[InlineKeyboardButton("💎 VIP Do'kon", callback_data="shop:category:badges")]]
    if adm and is_pm:
        buttons[0].append(InlineKeyboardButton("👑 Master Admin Paneli", callback_data="adm:menu"))

    boost_kb = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(boost_text, reply_markup=boost_kb, parse_mode="HTML")


