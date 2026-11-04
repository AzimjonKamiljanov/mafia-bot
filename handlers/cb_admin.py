import time
import logging
from telegram.error import TelegramError
from telegram import Update
from telegram.ext import ContextTypes

from database.db import get_db
from database.models import is_admin, change_balance, add_item, set_badge, now_iso

log = logging.getLogger("detektiv.handlers.cb_admin")


async def handle_admin_grant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    if not q or not q.data:
        return False
    data = q.data
    user = q.from_user
    uid = user.id

    if not (data.startswith("adm_grant_confirm:") or data.startswith("adm_grant_cancel:")):
        return False

    token = data.split(":", 1)[1]
    from handlers.admin_ai import pending_admin_grants

    if not is_admin(uid):
        await q.answer("❌ Bu amal faqat Master Admin uchun!", show_alert=True)
        return True

    grant = pending_admin_grants.get(token)
    if not grant or (time.time() - grant.get("created_at", 0) > 300):
        pending_admin_grants.pop(token, None)
        await q.answer("❌ Ushbu so'rov eskirgan yoki topilmadi.", show_alert=True)
        try:
            await q.edit_message_text("⚠️ Ushbu operatsiya bekor qilingan yoki muddati o'tgan.")
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
        return True

    if grant["admin_id"] != uid:
        await q.answer("❌ Bu so'rovni faqat uni yaratgan admin tasdiqlashi mumkin!", show_alert=True)
        return True

    if data.startswith("adm_grant_cancel:"):
        pending_admin_grants.pop(token, None)
        await q.answer("Operatsiya bekor qilindi.")
        await q.edit_message_text("❌ Operatsiya admin tomonidan bekor qilindi.")
        return True

    pending_admin_grants.pop(token, None)
    target_id = grant["target_id"]
    db = await get_db()
    now = now_iso()

    if grant["kind"] == "currency":
        curr = grant["currency"]
        amt = grant["amount"]
        note = f"Super Admin {uid} AI grant"
        await change_balance(target_id, curr, amt, note)
        await db.execute("""
            INSERT INTO transactions (user_id, kind, amount, currency, note, created_at)
            VALUES (?, 'admin_grant', ?, ?, ?, ?)
        """, (target_id, amt, curr, note, now))
        await db.commit()
        curr_title = "Gold 🟡" if curr == "gold" else "Coin 💰"
        await q.answer("✅ Muvaffaqiyatli o'tkazildi!")
        await q.edit_message_text(
            "👑 <b>AI MASTER: MABLAG' O'TKAZMASI</b>\n\n"
            f"👤 <b>Qabul qiluvchi:</b> <code>{target_id}</code>\n"
            f"💎 <b>Miqdor:</b> +{amt} {curr_title}\n\n"
            "<blockquote>Mablag' muvaffaqiyatli to'ldirildi va audit logiga "
            "(admin_grant) kiritildi! ✨</blockquote>",
            parse_mode="HTML"
        )
        return True
    elif grant["kind"] == "item":
        item_key = grant["item_key"]
        count = grant["count"]
        item_title = grant["item_title"]
        note = f"Super Admin {uid} AI item grant"
        await add_item(target_id, item_key, count)
        await db.execute("""
            INSERT INTO transactions (user_id, kind, amount, currency, note, created_at)
            VALUES (?, 'admin_grant', ?, ?, ?, ?)
        """, (target_id, count, f"item:{item_key}", note, now))
        await db.commit()
        await q.answer("✅ Buyum topshirildi!")
        await q.edit_message_text(
            "👑 <b>AI MASTER: BUYUM TAQDIM ETILDI</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> <code>{target_id}</code>\n"
            f"📦 <b>Buyum:</b> {item_title} (x{count})\n\n"
            "<blockquote>Buyum foydalanuvchi inventariga muvaffaqiyatli qo'shildi va "
            "audit logiga (admin_grant) kiritildi! 🎒✨</blockquote>",
            parse_mode="HTML"
        )
        return True
    elif grant["kind"] == "badge":
        badge_key = grant["badge_key"]
        badge_name = grant["badge_name"]
        days = grant.get("days", 365)
        note = f"Super Admin {uid} AI badge grant"
        await set_badge(target_id, badge_key, badge_name, days=days)
        await db.execute("""
            INSERT INTO transactions (user_id, kind, amount, currency, note, created_at)
            VALUES (?, 'admin_grant', 1, ?, ?, ?)
        """, (target_id, f"badge:{badge_key}", note, now))
        await db.commit()
        await q.answer("✅ Nishon topshirildi!")
        await q.edit_message_text(
            "👑 <b>AI MASTER: NISHON TOPSHIRILDI</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> <code>{target_id}</code>\n"
            f"🎖️ <b>Nishon:</b> {badge_name}\n"
            f"⏳ <b>Amal qilish muddati:</b> {days} kun\n\n"
            "<blockquote>VIP nishon muvaffaqiyatli topshirildi va "
            "audit logiga (admin_grant) kiritildi! 👑✨</blockquote>",
            parse_mode="HTML"
        )
        return True

    return True
