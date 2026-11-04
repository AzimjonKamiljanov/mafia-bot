import time
import html
import logging
from telegram.error import TelegramError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import BOT_USERNAME
from database.models import (
    ensure_user, get_user, change_balance, get_balance, is_admin, add_item, take_item
)
from database.db import get_db
from core.engine import active_drops
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.handlers.social")

pending_social_proposals: dict = {}

async def para_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    chat = update.effective_chat
    if not msg:
        return
    if chat and chat.type == "private":
        from config import BOT_USERNAME
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "💍 <b>Juftlik (Para)</b>\n\n"
            "Juftlik hosil qilish faqat <b>Telegram guruhlarida</b> ikkinchi insonning xabariga 'Reply' qilib <code>/para</code> deb yozish orqali amalga oshiriladi.\n\n"
            "Mavjud juftingizni tekshirish uchun: <code>/mypara</code>",
            reply_markup=kb,
            parse_mode="HTML"
        )
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

    cid = getattr(chat, "id", None)
    is_group = bool(
        chat and (
            getattr(chat, "type", "") in ("group", "supergroup")
            or (isinstance(cid, int) and cid < 0)
        )
    )
    if is_group:
        prop_key = (requester.id, target.id, "para")
        # Check SQLite and memory for existing pending proposal
        async with db.execute("SELECT id FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = 'para'", (requester.id, target.id)) as c:
            db_req = await c.fetchone()

        # Secret Easter Egg: If repeat proposal sent without target rejecting, auto-accept!
        if prop_key in pending_social_proposals or db_req:
            pending_social_proposals.pop(prop_key, None)
            await db.execute("DELETE FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = 'para'", (requester.id, target.id))
            await db.execute("""
                INSERT INTO social_links (user_id, other_id, kind, created_at)
                VALUES (?, ?, 'para', datetime('now')), (?, ?, 'para', datetime('now'))
                ON CONFLICT DO NOTHING
            """, (requester.id, target.id, target.id, requester.id))
            await db.commit()

            # Announce both in group and in PM
            await msg.reply_text(f"💍 <b>{html.escape(requester.full_name)}</b> va <b>{html.escape(target.full_name)}</b> muvaffaqiyatli juftlik (Para) bo'ldilar!", parse_mode="HTML")
            try:
                await context.bot.send_message(
                    chat_id=requester.id,
                    text=f"💍 <b>{html.escape(target.full_name)}</b> bilan juftlik (Para) muvaffaqiyatli bog'landi!",
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            try:
                await context.bot.send_message(
                    chat_id=target.id,
                    text=f"💍 <b>{html.escape(requester.full_name)}</b> bilan juftlik (Para) tasdiqlandi!",
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            return

        # 1st time: register pending proposal in memory and database, then send PM to target
        await db.execute("""
            INSERT INTO social_requests (requester_id, target_id, kind, created_at)
            VALUES (?, ?, 'para', datetime('now'))
        """, (requester.id, target.id))
        await db.commit()

        pending_social_proposals[prop_key] = {
            "requester_id": requester.id,
            "requester_name": requester.full_name,
            "target_id": target.id,
            "target_name": target.full_name,
            "chat_id": chat.id,
            "kind": "para",
            "time": time.time()
        }

        # Reply in group
        await msg.reply_text(
            f"👤 <b>{html.escape(requester.full_name)}</b> <b>{html.escape(target.full_name)}</b> ga juftlik (/para) so'rovi yubordi. Qabul qilsa, xabar beraman!",
            parse_mode="HTML"
        )

        # Dispatch proposal to target in PM
        pm_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Qabul qilish", callback_data=f"soc_acc:{requester.id}:{target.id}:para:{chat.id}"),
                InlineKeyboardButton("🔴 Rad etish", callback_data=f"soc_rej:{requester.id}:{target.id}:para:{chat.id}")
            ]
        ])
        pm_text = (
            f"💌 <b>{html.escape(requester.full_name)}</b> sizga juftlik (/para) taklifini yubordi! Qabul qilasizmi?"
        )
        try:
            await context.bot.send_message(
                chat_id=target.id,
                text=pm_text,
                reply_markup=pm_kb,
                parse_mode="HTML"
            )
        except Exception:
            from config import BOT_USERNAME
            warn_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔵 💬 Botga o'tish ↗", url=f"https://t.me/{BOT_USERNAME}?start=para")]
            ])
            await msg.reply_text(
                f"⚠️ <b>{html.escape(target.full_name)}</b> botga start bosmagan! Taklifni qabul qilish uchun avval botimizga kiring: @{BOT_USERNAME}",
                reply_markup=warn_kb,
                parse_mode="HTML"
            )
        return

    # Non-group fallback (e.g. test environments)
    await db.execute("""
        INSERT INTO social_links (user_id, other_id, kind, created_at)
        VALUES (?, ?, 'para', datetime('now')), (?, ?, 'para', datetime('now'))
        ON CONFLICT DO NOTHING
    """, (requester.id, target.id, target.id, requester.id))
    await db.commit()

    await msg.reply_text(f"💍 <b>{html.escape(requester.full_name)}</b> va <b>{html.escape(target.full_name)}</b> muvaffaqiyatli juftlik (Para) bo'ldilar!", parse_mode="HTML")

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
        from config import BOT_USERNAME
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🤝 <b>Birodarlik (Bro)</b>\n\n"
            "Birodarlik rishtasini bog'lash faqat <b>Telegram guruhlarida</b> ikkinchi insonning xabariga 'Reply' qilib <code>/bro</code> deb yozish orqali amalga oshiriladi.\n\n"
            "Mavjud birodaringizni tekshirish uchun: <code>/mybro</code>",
            reply_markup=kb,
            parse_mode="HTML"
        )
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

    cid = getattr(chat, "id", None)
    is_group = bool(
        chat and (
            getattr(chat, "type", "") in ("group", "supergroup")
            or (isinstance(cid, int) and cid < 0)
        )
    )
    if is_group:
        prop_key = (requester.id, target.id, "bro")
        # Check SQLite and memory for existing pending proposal
        async with db.execute("SELECT id FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = 'bro'", (requester.id, target.id)) as c:
            db_req = await c.fetchone()

        # Secret Easter Egg: If repeat proposal sent without target rejecting, auto-accept!
        if prop_key in pending_social_proposals or db_req:
            pending_social_proposals.pop(prop_key, None)
            await db.execute("DELETE FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = 'bro'", (requester.id, target.id))
            await db.execute("""
                INSERT INTO social_links (user_id, other_id, kind, created_at)
                VALUES (?, ?, 'bro', datetime('now')), (?, ?, 'bro', datetime('now'))
                ON CONFLICT DO NOTHING
            """, (requester.id, target.id, target.id, requester.id))
            await db.commit()

            # Announce both in group and in PM
            await msg.reply_text(f"🤝 <b>{html.escape(requester.full_name)}</b> va <b>{html.escape(target.full_name)}</b> birodar (Bro) bo'ldilar!", parse_mode="HTML")
            try:
                await context.bot.send_message(
                    chat_id=requester.id,
                    text=f"🤝 <b>{html.escape(target.full_name)}</b> bilan birodarlik (Bro) rishtasi muvaffaqiyatli bog'landi!",
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            try:
                await context.bot.send_message(
                    chat_id=target.id,
                    text=f"🤝 <b>{html.escape(requester.full_name)}</b> bilan birodarlik (Bro) tasdiqlandi!",
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            return

        # 1st time: register pending proposal in memory and database, then send PM to target
        await db.execute("""
            INSERT INTO social_requests (requester_id, target_id, kind, created_at)
            VALUES (?, ?, 'bro', datetime('now'))
        """, (requester.id, target.id))
        await db.commit()

        pending_social_proposals[prop_key] = {
            "requester_id": requester.id,
            "requester_name": requester.full_name,
            "target_id": target.id,
            "target_name": target.full_name,
            "chat_id": chat.id,
            "kind": "bro",
            "time": time.time()
        }

        # Reply in group
        await msg.reply_text(
            f"👤 <b>{html.escape(requester.full_name)}</b> <b>{html.escape(target.full_name)}</b> ga birodarlik (/bro) so'rovi yubordi. Qabul qilsa, xabar beraman!",
            parse_mode="HTML"
        )

        # Dispatch proposal to target in PM
        pm_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Qabul qilish", callback_data=f"soc_acc:{requester.id}:{target.id}:bro:{chat.id}"),
                InlineKeyboardButton("🔴 Rad etish", callback_data=f"soc_rej:{requester.id}:{target.id}:bro:{chat.id}")
            ]
        ])
        pm_text = (
            f"💌 <b>{html.escape(requester.full_name)}</b> sizga birodarlik (/bro) taklifini yubordi! Qabul qilasizmi?"
        )
        try:
            await context.bot.send_message(
                chat_id=target.id,
                text=pm_text,
                reply_markup=pm_kb,
                parse_mode="HTML"
            )
        except Exception:
            from config import BOT_USERNAME
            warn_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔵 💬 Botga o'tish ↗", url=f"https://t.me/{BOT_USERNAME}?start=bro")]
            ])
            await msg.reply_text(
                f"⚠️ <b>{html.escape(target.full_name)}</b> botga start bosmagan! Taklifni qabul qilish uchun avval botimizga kiring: @{BOT_USERNAME}",
                reply_markup=warn_kb,
                parse_mode="HTML"
            )
        return

    # Non-group fallback
    await db.execute("""
        INSERT INTO social_links (user_id, other_id, kind, created_at)
        VALUES (?, ?, 'bro', datetime('now')), (?, ?, 'bro', datetime('now'))
        ON CONFLICT DO NOTHING
    """, (requester.id, target.id, target.id, requester.id))
    await db.commit()
    await msg.reply_text(f"🤝 <b>{html.escape(requester.full_name)}</b> va <b>{html.escape(target.full_name)}</b> birodar (Bro) bo'ldilar!", parse_mode="HTML")

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
        from config import BOT_USERNAME
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("🛒 Do'kon (/shop)", callback_data="menu_shop")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🌹 <b>Gul sovg'a qilish (/givegul)</b>\n\n"
            "Gul sovg'a qilish faqat <b>Telegram guruhlarida</b> ikkinchi insonning xabariga 'Reply' qilib <code>/givegul</code> deb yozish orqali amalga oshiriladi.\n\n"
            "Gulingiz tugagan bo'lsa, /shop do'konidan xarid qilishingiz mumkin.",
            reply_markup=kb,
            parse_mode="HTML"
        )
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
    msg = update.message or update.effective_message
    if not msg:
        return
    chat = update.effective_chat
    sender = msg.from_user

    if not chat or chat.type not in ("group", "supergroup"):
        from config import BOT_USERNAME
        send_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🪙 Balans", callback_data="menu_balance")],
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🎁 <b>Oltin Sovrin (Gold Drop) (/send)</b>\n\n"
            "Guruhga oltin tashlash faqat <b>Telegram guruhlarida</b> ishlaydi.\n"
            "Shaxsiy chatda foydalanuvchiga oltin o'tkazish uchun: <code>/gold &lt;user_id yoki @username&gt; &lt;miqdor&gt;</code> buyrug'idan foydalaning.",
            reply_markup=send_kb,
            parse_mode="HTML"
        )
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

    import uuid
    from core.engine import DEFAULT_DROP_EXPIRY_SECONDS
    drop_id = f"drop_{uuid.uuid4().hex[:12]}"
    now_ts = time.time()
    active_drops[drop_id] = {
        "id": drop_id,
        "chat_id": chat.id,
        "creator_id": sender.id,
        "creator_name": sender_name[:40],
        "total": amount,
        "remaining": amount,
        "claimed_by": {},
        "created_at": now_ts,
        "expires_at": now_ts + DEFAULT_DROP_EXPIRY_SECONDS
    }

    text = (
        f"🎁 <b>OLTIN SOVRIN (GOLD DROP)!</b>\n\n"
        f"👤 <b>{html.escape(sender_name)}</b> guruhga <b>{amount} dona Gold</b> tashladi!\n"
        f"⚡️ Har bir ishtirokchi <b>1 donadan Gold</b> olishi mumkin.\n"
        f"Kim birinchi ulgursa, o'shaniki! Shoshiling!\n\n"
        f"💰 Qoldi: <b>{amount}/{amount} ta Gold</b>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟡 🎁 Gold olish (1 dona)", callback_data=f"claim_gold:{drop_id}")]
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
        raw_target = context.args[0].strip()
        try:
            amount = int(context.args[1])
            if amount <= 0:
                raise ValueError()
        except Exception:
            await msg.reply_text("❌ Miqdor musbat butun son bo'lishi kerak.")
            return

        target_user = None
        if raw_target.isdigit():
            target_user_id = int(raw_target)
            target_user = await get_user(target_user_id)
        else:
            from database.models import get_user_by_username
            target_user = await get_user_by_username(raw_target)
            if target_user:
                target_user_id = target_user["user_id"]

        if not target_user:
            clean_tgt = html.escape(raw_target)
            await msg.reply_text(f"❌ <code>{clean_tgt}</code> foydalanuvchisi bot tizimidan topilmadi.", parse_mode="HTML")
            return

        if target_user_id == sender.id:
            await msg.reply_text("❌ O'zingizga tanga o'tkaza olmaysiz.")
            return

        target_name = target_user.get("name", f"ID: {target_user_id}")
    else:
        coin_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🪙 Balans", callback_data="menu_balance"), InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ]) if update.effective_chat and update.effective_chat.type == "private" else None
        await msg.reply_text(
            "🪙 <b>Tangalar o'tkazish uchun:</b>\n\n"
            "1. Guruhda: Kerakli inson xabariga Reply qilib <code>/coin &lt;miqdor&gt;</code> deb yozing.\n"
            "2. Shaxsiy chatda: <code>/coin &lt;foydalanuvchi_id yoki @username&gt; &lt;miqdor&gt;</code> deb yozing.\n\n"
            "Masalan: <code>/coin 123456789 500</code> yoki <code>/coin @rasuljonovv_a 500</code>",
            reply_markup=coin_kb,
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
    /gold <user_id|username> <miqdor> - Berilgan foydalanuvchiga Gold o'tkazadi.
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
        raw_target = context.args[0].strip()
        try:
            amount = int(context.args[1])
            if amount <= 0:
                raise ValueError()
        except Exception:
            await msg.reply_text("❌ Miqdor musbat butun son bo'lishi kerak.")
            return

        target_user = None
        if raw_target.isdigit():
            target_user_id = int(raw_target)
            target_user = await get_user(target_user_id)
        else:
            from database.models import get_user_by_username
            target_user = await get_user_by_username(raw_target)
            if target_user:
                target_user_id = target_user["user_id"]

        if not target_user:
            clean_tgt = html.escape(raw_target)
            await msg.reply_text(f"❌ <code>{clean_tgt}</code> foydalanuvchisi bot tizimidan topilmadi.", parse_mode="HTML")
            return

        if target_user_id == sender.id:
            await msg.reply_text("❌ O'zingizga oltin o'tkaza olmaysiz.")
            return

        target_name = target_user.get("name", f"ID: {target_user_id}")
    else:
        gold_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Balans", callback_data="menu_balance"), InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ]) if update.effective_chat and update.effective_chat.type == "private" else None
        await msg.reply_text(
            "🥇 <b>Oltin o'tkazish uchun:</b>\n\n"
            "1. Guruhda: Kerakli inson xabariga Reply qilib <code>/gold &lt;miqdor&gt;</code> deb yozing.\n"
            "2. Shaxsiy chatda: <code>/gold &lt;foydalanuvchi_id yoki @username&gt; &lt;miqdor&gt;</code> deb yozing.\n\n"
            "Masalan: <code>/gold 123456789 5</code> yoki <code>/gold @rasuljonovv_a 5</code>",
            reply_markup=gold_kb,
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
