import time
import html
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import BOT_USERNAME
from database.models import (
    ensure_user, get_user, change_balance, get_balance, is_admin, add_item, take_item
)
from database.db import get_db
from core.engine import active_drops

log = logging.getLogger("detektiv.handlers.social")

async def para_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    chat = update.effective_chat
    if not msg:
        return
    if chat and chat.type == "private":
        await msg.reply_text("ℹ️ Juftlik (Para) hosil qilish faqat Telegram guruhlarida ikkinchi insonning xabariga 'Reply' qilish orqali amalga oshiriladi.")
        return
    if not msg.reply_to_message:
        await msg.reply_text("💍 /para ishlatish uchun kerakli insonning xabariga Reply qiling.")
        return

    requester = msg.from_user
    target = msg.reply_to_message.from_user
    if not target or target.id == requester.id or target.is_bot:
        await msg.reply_text("❌ O'zingiz yoki bot bilan juftlik hosil qila olmaysiz.")
        return

    await ensure_user(requester)
    await ensure_user(target)

    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'para'", (requester.id,)) as cursor:
        existing = await cursor.fetchone()
    if existing:
        await msg.reply_text("❌ Sizda allaqachon juftlik (Para) mavjud. Yangi tuzishdan oldin /dpara qiling.")
        return

    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'para'", (target.id,)) as cursor:
        target_existing = await cursor.fetchone()
    if target_existing:
        await msg.reply_text("❌ Nishon allaqachon boshqa inson bilan juftlik (Para) tuzgan.")
        return

    # Check or insert request
    await db.execute("""
        INSERT INTO social_links (user_id, other_id, kind, created_at)
        VALUES (?, ?, 'para', datetime('now')), (?, ?, 'para', datetime('now'))
        ON CONFLICT DO NOTHING
    """, (requester.id, target.id, target.id, requester.id))
    await db.commit()

    await msg.reply_text(f"💍 *{requester.full_name}* va *{target.full_name}* muvaffaqiyatli juftlik (Para) bo'ldilar!", parse_mode="Markdown")

async def dpara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'para'", (user.id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        await msg.reply_text("ℹ️ Sizda faol juftlik (Para) yo'q.")
        return
    partner_id = row["other_id"]
    await db.execute("DELETE FROM social_links WHERE user_id IN (?, ?) AND kind = 'para'", (user.id, partner_id))
    await db.commit()
    await msg.reply_text("💔 Juftlik bekor qilindi.")

async def mypara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not user:
        return

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=mypara"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            f"💍 <b>Juftlik (Para) ma'lumotlari</b>\n\n"
            f"Hurmatli {html.escape(user.first_name)}, juftlik ma'lumotlaringiz maxfiyligi uchun "
            f"faqat botning shaxsiy chatida ko'rsatiladi.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'para'", (user.id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        await msg.reply_text("ℹ️ Sizda hali juftlik (Para) yo'q.")
        return
    partner = await get_user(row["other_id"])
    name = partner["name"] if partner else "Noma'lum"
    await msg.reply_text(f"💍 Sizning juftingiz: <b>{html.escape(name)}</b>", parse_mode="HTML")

async def bro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    chat = update.effective_chat
    if not msg:
        return
    if chat and chat.type == "private":
        await msg.reply_text("ℹ️ Birodarlik (Bro) rishtasini bog'lash faqat Telegram guruhlarida ikkinchi insonning xabariga 'Reply' qilish orqali amalga oshiriladi.")
        return
    if not msg.reply_to_message:
        await msg.reply_text("🤝 /bro ishlatish uchun birodaringizning xabariga Reply qiling.")
        return
    requester = msg.from_user
    target = msg.reply_to_message.from_user
    if not target or target.id == requester.id or target.is_bot:
        await msg.reply_text("❌ Noto'g'ri nishon.")
        return

    await ensure_user(requester)
    await ensure_user(target)

    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'bro'", (requester.id,)) as cursor:
        req_existing = await cursor.fetchone()
    if req_existing:
        await msg.reply_text("❌ Sizda allaqachon birodar (Bro) mavjud. Yangi tuzishdan oldin /dbro qiling.")
        return

    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'bro'", (target.id,)) as cursor:
        tgt_existing = await cursor.fetchone()
    if tgt_existing:
        await msg.reply_text("❌ Nishon allaqachon boshqa inson bilan birodarlik rishtasini bog'lagan.")
        return

    await db.execute("""
        INSERT INTO social_links (user_id, other_id, kind, created_at)
        VALUES (?, ?, 'bro', datetime('now')), (?, ?, 'bro', datetime('now'))
        ON CONFLICT DO NOTHING
    """, (requester.id, target.id, target.id, requester.id))
    await db.commit()
    await msg.reply_text(f"🤝 *{requester.full_name}* va *{target.full_name}* birodar (Bro) bo'ldilar!", parse_mode="Markdown")

async def dbro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'bro'", (user.id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        await msg.reply_text("ℹ️ Sizda faol birodar (Bro) yo'q.")
        return
    bro_id = row["other_id"]
    await db.execute("DELETE FROM social_links WHERE user_id IN (?, ?) AND kind = 'bro'", (user.id, bro_id))
    await db.commit()
    await msg.reply_text("🤝 Birodarlik rishtasi uzildi.")

async def mybro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not user:
        return

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=mybro"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            f"🤝 <b>Birodarlik (Bro) ma'lumotlari</b>\n\n"
            f"Hurmatli {html.escape(user.first_name)}, birodarlik ma'lumotlaringiz maxfiyligi uchun "
            f"faqat botning shaxsiy chatida ko'rsatiladi.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'bro'", (user.id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        await msg.reply_text("ℹ️ Sizda hali birodar (Bro) yo'q.")
        return
    bro = await get_user(row["other_id"])
    name = bro["name"] if bro else "Noma'lum"
    await msg.reply_text(f"🤝 Sizning birodaringiz: <b>{html.escape(name)}</b>", parse_mode="HTML")

async def givegul_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    chat = update.effective_chat
    if not msg:
        return
    if chat and chat.type == "private":
        await msg.reply_text("ℹ️ Gul sovg'a qilish faqat Telegram guruhlarida ikkinchi insonning xabariga 'Reply' qilish orqali amalga oshiriladi.")
        return
    if not msg.reply_to_message:
        await msg.reply_text("🌹 Gul sovg'a qilish uchun kerakli odam xabariga Reply qiling.")
        return
    sender = msg.from_user
    target = msg.reply_to_message.from_user
    if not await take_item(sender.id, "rose", 1):
        await msg.reply_text("❌ Sizda gul (Rose) yo'q. Avval /shop dan xarid qiling.")
        return
    await add_item(target.id, "rose", 1)
    await msg.reply_text(f"🌹 <b>{html.escape(sender.full_name)}</b> <b>{html.escape(target.full_name)}</b>ga gul sovg'a qildi!", parse_mode="HTML")

async def send_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /send <soni> - Guruhga Gold Drop tashlaydi!
    Har bir odam 1 donadan Gold olishi mumkin.
    """
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    sender = msg.from_user

    if not chat or chat.type not in ("group", "supergroup"):
        await msg.reply_text("❌ Ushbu buyruq faqat guruhlarda ishlaydi.")
        return

    if not context.args:
        await msg.reply_text(
            "🎁 <b>Guruhga Oltin tashlash (Gold Drop) uchun:</b>\n"
            "<code>/send &lt;soni&gt;</code> deb yozing.\n"
            "Masalan: <code>/send 10</code> — 10 kishiga 1 donadan Gold ulashadi!",
            parse_mode="HTML"
        )
        return

    try:
        amount = int(context.args[0])
        if amount <= 0 or amount > 500:
            raise ValueError()
    except Exception:
        await msg.reply_text("❌ Miqdor 1 dan 500 gacha bo'lgan butun son bo'lishi kerak.")
        return

    await ensure_user(sender)

    # Check sender's balance (Admins bypass deduction)
    if not is_admin(sender.id, sender.username):
        user_gold = await get_balance(sender.id, "gold")
        if user_gold < amount:
            await msg.reply_text(
                f"❌ Balansingizda yetarli Gold yo'q!\nSizda: <b>{user_gold} ta Gold</b> mavjud.",
                parse_mode="HTML"
            )
            return
        await change_balance(sender.id, "gold", -amount, f"Guruhga Gold Drop: {amount}")

    sender_name = sender.full_name or sender.first_name or "Saxiy o'yinchi"
    drop_id = f"drop_{int(time.time())}_{sender.id % 10000}"
    active_drops[drop_id] = {
        "id": drop_id,
        "chat_id": chat.id,
        "creator_id": sender.id,
        "creator_name": sender_name[:40],
        "total": amount,
        "remaining": amount,
        "claimed_by": {},
        "created_at": time.time()
    }

    text = (
        f"🎁 <b>OLTIN SOVRIN (GOLD DROP)!</b>\n\n"
        f"👤 <b>{html.escape(sender_name)}</b> guruhga <b>{amount} dona Gold</b> tashladi!\n"
        f"⚡️ Har bir ishtirokchi <b>1 donadan Gold</b> olishi mumkin.\n"
        f"Kim birinchi ulgursa, o'shaniki! Shoshiling!\n\n"
        f"💰 Qoldi: <b>{amount}/{amount} ta Gold</b>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Gold olish (1 dona)", callback_data=f"claim_gold:{drop_id}")]
    ])

    try:
        from core.visuals import send_animated_dice_effect
        await send_animated_dice_effect(context.bot, chat.id, emoji="🎲")
    except Exception as e:
        log.debug("Gold drop dice error: %s", e)

    sent_msg = await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML"
    )
    active_drops[drop_id]["message_id"] = sent_msg.message_id


async def coin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /coin <miqdor> - Reply qilingan foydalanuvchiga Coin o'tkazadi.
    /coin <user_id> <miqdor> - Berilgan ID ga ega foydalanuvchiga Coin o'tkazadi.
    """
    msg = update.message or update.effective_message
    if not msg:
        return
    sender = msg.from_user
    if not sender:
        return

    target_user_id = None
    target_name = None
    amount = 0

    if msg.reply_to_message and context.args:
        try:
            amount = int(context.args[0])
            if amount <= 0:
                raise ValueError()
        except Exception:
            await msg.reply_text("❌ Miqdor musbat butun son bo'lishi kerak.")
            return
        target = msg.reply_to_message.from_user
        if not target or target.id == sender.id or target.is_bot:
            await msg.reply_text("❌ O'zingizga yoki botga tanga o'tkaza olmaysiz.")
            return
        await ensure_user(target)
        target_user_id = target.id
        target_name = target.full_name or target.first_name
    elif context.args and len(context.args) >= 2:
        try:
            target_user_id = int(context.args[0])
            amount = int(context.args[1])
            if amount <= 0 or target_user_id <= 0:
                raise ValueError()
        except Exception:
            await msg.reply_text("❌ Foydalanish: <code>/coin &lt;foydalanuvchi_id&gt; &lt;miqdor&gt;</code> yoki Reply qilib <code>/coin &lt;miqdor&gt;</code>", parse_mode="HTML")
            return
        if target_user_id == sender.id:
            await msg.reply_text("❌ O'zingizga tanga o'tkaza olmaysiz.")
            return
        target_user = await get_user(target_user_id)
        if not target_user:
            await msg.reply_text(f"❌ <code>{target_user_id}</code> ID li foydalanuvchi bot tizimidan topilmadi.", parse_mode="HTML")
            return
        target_name = target_user.get("name", f"ID: {target_user_id}")
    else:
        await msg.reply_text(
            "🪙 <b>Tangalar o'tkazish uchun:</b>\n\n"
            "1. Guruhda: Kerakli inson xabariga Reply qilib <code>/coin &lt;miqdor&gt;</code> deb yozing.\n"
            "2. Shaxsiy chatda: <code>/coin &lt;foydalanuvchi_id&gt; &lt;miqdor&gt;</code> deb yozing.\n\n"
            "Masalan: <code>/coin 123456789 500</code>",
            parse_mode="HTML"
        )
        return

    await ensure_user(sender)

    if not is_admin(sender.id, sender.username):
        if not await change_balance(sender.id, "coin", -amount, f"O'tkazma: {target_user_id}"):
            await msg.reply_text("❌ Balansingizda yetarli Coin yo'q.")
            return

    await change_balance(target_user_id, "coin", amount, f"O'tkazma: {sender.id} dan")
    s_name = html.escape(sender.full_name or sender.first_name)
    t_name = html.escape(target_name or str(target_user_id))
    await msg.reply_text(
        f"🪙 <b>{s_name}</b> foydalanuvchi <b>{t_name}</b>ga <b>{amount:,} Coin</b> o'tkazdi!",
        parse_mode="HTML"
    )


async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /gold <miqdor> - Reply qilingan foydalanuvchiga Gold o'tkazadi.
    /gold <user_id> <miqdor> - Berilgan ID ga ega foydalanuvchiga Gold o'tkazadi.
    """
    msg = update.message or update.effective_message
    if not msg:
        return
    sender = msg.from_user
    if not sender:
        return

    target_user_id = None
    target_name = None
    amount = 0

    if msg.reply_to_message and context.args:
        try:
            amount = int(context.args[0])
            if amount <= 0:
                raise ValueError()
        except Exception:
            await msg.reply_text("❌ Miqdor musbat butun son bo'lishi kerak.")
            return
        target = msg.reply_to_message.from_user
        if not target or target.id == sender.id or target.is_bot:
            await msg.reply_text("❌ O'zingizga yoki botga oltin o'tkaza olmaysiz.")
            return
        await ensure_user(target)
        target_user_id = target.id
        target_name = target.full_name or target.first_name
    elif context.args and len(context.args) >= 2:
        try:
            target_user_id = int(context.args[0])
            amount = int(context.args[1])
            if amount <= 0 or target_user_id <= 0:
                raise ValueError()
        except Exception:
            await msg.reply_text("❌ Foydalanish: <code>/gold &lt;foydalanuvchi_id&gt; &lt;miqdor&gt;</code> yoki Reply qilib <code>/gold &lt;miqdor&gt;</code>", parse_mode="HTML")
            return
        if target_user_id == sender.id:
            await msg.reply_text("❌ O'zingizga oltin o'tkaza olmaysiz.")
            return
        target_user = await get_user(target_user_id)
        if not target_user:
            await msg.reply_text(f"❌ <code>{target_user_id}</code> ID li foydalanuvchi bot tizimidan topilmadi.", parse_mode="HTML")
            return
        target_name = target_user.get("name", f"ID: {target_user_id}")
    else:
        await msg.reply_text(
            "🥇 <b>Oltin o'tkazish uchun:</b>\n\n"
            "1. Guruhda: Kerakli inson xabariga Reply qilib <code>/gold &lt;miqdor&gt;</code> deb yozing.\n"
            "2. Shaxsiy chatda: <code>/gold &lt;foydalanuvchi_id&gt; &lt;miqdor&gt;</code> deb yozing.\n\n"
            "Masalan: <code>/gold 123456789 5</code>",
            parse_mode="HTML"
        )
        return

    await ensure_user(sender)

    if not is_admin(sender.id, sender.username):
        if not await change_balance(sender.id, "gold", -amount, f"Gold o'tkazma: {target_user_id}"):
            await msg.reply_text("❌ Balansingizda yetarli Gold yo'q.")
            return

    await change_balance(target_user_id, "gold", amount, f"Gold o'tkazma: {sender.id} dan")
    s_name = html.escape(sender.full_name or sender.first_name)
    t_name = html.escape(target_name or str(target_user_id))
    await msg.reply_text(
        f"🥇 <b>{s_name}</b> foydalanuvchi <b>{t_name}</b>ga <b>{amount:,} Gold</b> o'tkazdi!",
        parse_mode="HTML"
    )


# Alias functions for backward compatibility
givecoin_cmd = coin_cmd
givegold_cmd = gold_cmd
