import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import BOT_USERNAME, ROLES
from database.models import is_admin, ensure_user
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.handlers.commands_meta")

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
