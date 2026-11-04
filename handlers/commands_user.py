import html
import logging
from typing import Optional
from telegram.error import TelegramError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import BOT_USERNAME, ROLES
from database.models import (
    ensure_user, get_top_players, is_admin, get_badge, get_will, track_group_member
)
from core.engine import (
    games, lobbies, find_game_by_user, find_lobby_by_user, display_name, save_runtime
)
from phases.lobby import lobby_text, lobby_keyboard
from core.will import save_player_will
from core.visuals import anim_emoji, format_badge_with_anim_emoji
from core.emojis import tg_emoji
from handlers.commands_meta import plan_cmd, boost_cmd
from handlers.commands_lobby import startgame_cmd

log = logging.getLogger("detektiv.handlers.commands_user")


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

    # Check deep linking (e.g. /start join_-100123456, /start act_-100123, /start profile)
    if context.args and len(context.args) > 0:
        from handlers.deep_link import handle_deep_link
        if await handle_deep_link(update, context, context.args[0]):
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


async def reveal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or not user or not msg:
        return

    game = games.get(chat.id) if chat.type in ("group", "supergroup") else find_game_by_user(user.id)
    if not game:
        if chat.type == "private":
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


async def salom_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
