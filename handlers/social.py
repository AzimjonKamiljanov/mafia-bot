import time
import html
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from database.models import (
    ensure_user, get_user, change_balance, get_balance, is_admin, add_item, take_item
)
from database.db import get_db
from core.engine import active_drops

log = logging.getLogger("detektiv.handlers.social")

async def para_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
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
    msg = update.message
    user = msg.from_user
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
    msg = update.message
    user = msg.from_user
    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'para'", (user.id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        await msg.reply_text("ℹ️ Sizda hali juftlik (Para) yo'q.")
        return
    partner = await get_user(row["other_id"])
    name = partner["name"] if partner else "Noma'lum"
    await msg.reply_text(f"💍 Sizning juftingiz: *{name}*", parse_mode="Markdown")

async def bro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
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
    msg = update.message
    user = msg.from_user
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
    msg = update.message
    user = msg.from_user
    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = 'bro'", (user.id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        await msg.reply_text("ℹ️ Sizda hali birodar (Bro) yo'q.")
        return
    bro = await get_user(row["other_id"])
    name = bro["name"] if bro else "Noma'lum"
    await msg.reply_text(f"🤝 Sizning birodaringiz: *{name}*", parse_mode="Markdown")

async def givegul_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        await msg.reply_text("🌹 Gul sovg'a qilish uchun kerakli odam xabariga Reply qiling.")
        return
    sender = msg.from_user
    target = msg.reply_to_message.from_user
    if not await take_item(sender.id, "rose", 1):
        await msg.reply_text("❌ Sizda gul (Rose) yo'q. Avval /shop dan xarid qiling.")
        return
    await add_item(target.id, "rose", 1)
    await msg.reply_text(f"🌹 *{sender.full_name}* *{target.full_name}*ga gul sovg'a qildi!", parse_mode="Markdown")

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
    """
    msg = update.message
    if not msg:
        return
    sender = msg.from_user

    if not msg.reply_to_message or not context.args:
        await msg.reply_text(
            "🪙 <b>Tangalar o'tkazish uchun:</b>\n"
            "Kerakli inson xabariga Reply qilib <code>/coin &lt;miqdor&gt;</code> deb yozing.\n"
            "Masalan: <code>/coin 500</code>",
            parse_mode="HTML"
        )
        return

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

    await ensure_user(sender)
    await ensure_user(target)

    if not is_admin(sender.id, sender.username):
        if not await change_balance(sender.id, "coin", -amount, f"O'tkazma: {target.id}"):
            await msg.reply_text("❌ Balansingizda yetarli Coin yo'q.")
            return

    await change_balance(target.id, "coin", amount, f"O'tkazma: {sender.id} dan")
    s_name = html.escape(sender.full_name or sender.first_name)
    t_name = html.escape(target.full_name or target.first_name)
    await msg.reply_text(
        f"🪙 <b>{s_name}</b> foydalanuvchi <b>{t_name}</b>ga <b>{amount:,} Coin</b> o'tkazdi!",
        parse_mode="HTML"
    )


async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /gold <miqdor> - Reply qilingan foydalanuvchiga Gold o'tkazadi.
    """
    msg = update.message
    if not msg:
        return
    sender = msg.from_user

    if not msg.reply_to_message or not context.args:
        await msg.reply_text(
            "🥇 <b>Oltin o'tkazish uchun:</b>\n"
            "Kerakli inson xabariga Reply qilib <code>/gold &lt;miqdor&gt;</code> deb yozing.\n"
            "Masalan: <code>/gold 5</code>",
            parse_mode="HTML"
        )
        return

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

    await ensure_user(sender)
    await ensure_user(target)

    if not is_admin(sender.id, sender.username):
        if not await change_balance(sender.id, "gold", -amount, f"Gold o'tkazma: {target.id}"):
            await msg.reply_text("❌ Balansingizda yetarli Gold yo'q.")
            return

    await change_balance(target.id, "gold", amount, f"Gold o'tkazma: {sender.id} dan")
    s_name = html.escape(sender.full_name or sender.first_name)
    t_name = html.escape(target.full_name or target.first_name)
    await msg.reply_text(
        f"🥇 <b>{s_name}</b> foydalanuvchi <b>{t_name}</b>ga <b>{amount:,} Gold</b> o'tkazdi!",
        parse_mode="HTML"
    )


# Alias functions for backward compatibility
givecoin_cmd = coin_cmd
givegold_cmd = gold_cmd
