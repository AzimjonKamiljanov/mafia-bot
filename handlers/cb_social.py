import html
import logging
from telegram.error import TelegramError
from telegram import Update
from telegram.ext import ContextTypes

from database.db import get_db
from database.models import get_user

log = logging.getLogger("detektiv.handlers.cb_social")


async def handle_social_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    if not q or not q.data:
        return False
    data = q.data
    user = q.from_user
    uid = user.id

    if not (data.startswith("soc_acc:") or data.startswith("soc_rej:")):
        return False

    parts = data.split(":")
    if len(parts) < 5 or not parts[1].lstrip("-").isdigit() or not parts[2].lstrip("-").isdigit() or not parts[4].lstrip("-").isdigit():
        await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
        return True
    is_accept = data.startswith("soc_acc:")
    req_id = int(parts[1])
    tgt_id = int(parts[2])
    kind = parts[3]
    orig_chat_id = int(parts[4])

    if uid != tgt_id:
        await q.answer("❌ Bu taklif sizga tegishli emas!", show_alert=True)
        return True

    from handlers.social import pending_social_proposals
    prop_key = (req_id, tgt_id, kind)
    pending_social_proposals.pop(prop_key, None)

    req_user = await get_user(req_id)
    req_name = req_user["name"] if req_user else f"Foydalanuvchi_{req_id}"
    tgt_name = user.full_name or user.first_name
    kind_title = "juftlik (Para)" if kind == "para" else "birodarlik (Bro)"

    if not is_accept:
        db = await get_db()
        await db.execute("DELETE FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = ?", (req_id, tgt_id, kind))
        await db.commit()
        await q.answer("Taklif rad etildi.")
        await q.edit_message_text(f"🔴 Siz <b>{html.escape(req_name)}</b>ning {kind_title} taklifini rad etdingiz.", parse_mode="HTML")
        try:
            await context.bot.send_message(
                chat_id=req_id,
                text=f"💔 <b>{html.escape(tgt_name)}</b> sizning {kind_title} taklifingizni rad etdi.",
                parse_mode="HTML"
            )
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
        return True

    # Check existing partners
    db = await get_db()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = ?", (req_id, kind)) as cursor:
        req_has = await cursor.fetchone()
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = ? AND kind = ?", (tgt_id, kind)) as cursor:
        tgt_has = await cursor.fetchone()

    if req_has or tgt_has:
        await db.execute("DELETE FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = ?", (req_id, tgt_id, kind))
        await db.commit()
        await q.answer("❌ Tomonlardan birida allaqachon bog'lanish mavjud!", show_alert=True)
        await q.edit_message_text("❌ Bog'lanish amalga oshmadi: tomonlardan birida allaqachon faol rishta mavjud.")
        return True

    await db.execute("DELETE FROM social_requests WHERE requester_id = ? AND target_id = ? AND kind = ?", (req_id, tgt_id, kind))
    await db.execute("""
        INSERT INTO social_links (user_id, other_id, kind, created_at)
        VALUES (?, ?, ?, datetime('now')), (?, ?, ?, datetime('now'))
        ON CONFLICT DO NOTHING
    """, (req_id, tgt_id, kind, tgt_id, req_id, kind))
    await db.commit()

    await q.answer("🎉 Taklif qabul qilindi!")
    await q.edit_message_text(f"✅ Siz <b>{html.escape(req_name)}</b> bilan muvaffaqiyatli {kind_title} bo'ldingiz!", parse_mode="HTML")

    # Notify requester in PM
    try:
        await context.bot.send_message(
            chat_id=req_id,
            text=f"💍 <b>{html.escape(tgt_name)}</b> sizning {kind_title} taklifingizni qabul qildi!",
            parse_mode="HTML"
        )
    except (TelegramError, Exception) as e:
        log.debug("Operation suppressed in %s: %s", __name__, e)

    # Announce in group
    try:
        icon = "💍" if kind == "para" else "🤝"
        term = "juftlik (Para)" if kind == "para" else "birodar (Bro)"
        await context.bot.send_message(
            chat_id=orig_chat_id,
            text=f"{icon} <b>{html.escape(req_name)}</b> va <b>{html.escape(tgt_name)}</b> muvaffaqiyatli {term} bo'ldilar!",
            parse_mode="HTML"
        )
    except (TelegramError, Exception) as e:
        log.debug("Operation suppressed in %s: %s", __name__, e)
    return True
