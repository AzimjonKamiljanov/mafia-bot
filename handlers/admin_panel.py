import html
import logging
from typing import Dict, Any, List
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import ADMIN_IDS, ROLES
from database.db import get_db
from database.models import (
    is_admin, get_user, change_balance, get_badge, set_badge,
    get_all_bot_configs, set_bot_config
)
from core.engine import games, lobbies, cancel_game_timer, cancel_lobby_timer

log = logging.getLogger("detektiv.handlers.admin_panel")

def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Tizim Statistikasi", callback_data="adm:stats"),
            InlineKeyboardButton("🎮 Faol O'yinlar", callback_data="adm:games")
        ],
        [
            InlineKeyboardButton("💰 Balans Boshqaruvi", callback_data="adm:balance_info"),
            InlineKeyboardButton("⚙️ Bot Konfiguratsiyasi", callback_data="adm:config")
        ],
        [
            InlineKeyboardButton("📢 Global Xabar (Broadcast)", callback_data="adm:broadcast_info"),
            InlineKeyboardButton("🤖 AI Boshqaruv Qo'llanmasi", callback_data="adm:ai_info")
        ],
        [
            InlineKeyboardButton("❌ Yopish", callback_data="adm:close")
        ]
    ])

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id, user.username):
        if update.message:
            await update.message.reply_text("⛔ Ushbu buyruq faqat Bot Super Adminlari uchun ruxsat etilgan.")
        return

    db = await get_db()
    async with db.execute("SELECT COUNT(*) AS c FROM users") as cur:
        total_users = (await cur.fetchone())["c"]
    async with db.execute("SELECT COUNT(*) AS c FROM game_history") as cur:
        total_games = (await cur.fetchone())["c"]

    text = (
        "👑 <b>MASTER ADMIN BOSHQARUV PANELI</b>\n\n"
        f"🌟 <b>Hurmatli Bosh Administrator:</b> {html.escape(user.full_name or user.first_name)}\n"
        f"🆔 Sizning ID: <code>{user.id}</code>\n\n"
        "📊 <b>Umumiy ko'rsatkichlar:</b>\n"
        f"• 👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
        f"• 🏆 O'ynalgan o'yinlar: <b>{total_games} ta</b>\n"
        f"• 🎮 Faol o'yinlar: <b>{len(games)} ta</b>\n"
        f"• 🚪 Ochiq lobbylar: <b>{len(lobbies)} ta</b>\n\n"
        "🤖 <b>AI Boshqaruv Rejimi:</b> <i>FAOL</i>\n"
        "💡 <i>Siz botga shaxsiy xabarda istalgan buyruqni tabiiy tilda yozishingiz mumkin. "
        "Masalan: «tun vaqtini 30 qil», «7651553630 ga 1000 coin ber», «Sherif rolini o'chir» va hokazo.</i>"
    )

    await update.message.reply_text(
        text=text,
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML"
    )

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data or ""
    if not data.startswith("adm:"):
        return False

    user = update.effective_user
    if not user or not is_admin(user.id, user.username):
        await q.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return True

    parts = data.split(":")
    action = parts[1]

    if action == "close":
        await q.answer("Panel yopildi.")
        try:
            await q.message.delete()
        except Exception:
            pass
        return True

    if action == "menu":
        db = await get_db()
        async with db.execute("SELECT COUNT(*) AS c FROM users") as cur:
            total_users = (await cur.fetchone())["c"]
        async with db.execute("SELECT COUNT(*) AS c FROM game_history") as cur:
            total_games = (await cur.fetchone())["c"]

        text = (
            "👑 <b>MASTER ADMIN BOSHQARUV PANELI</b>\n\n"
            f"🌟 <b>Hurmatli Administrator:</b> {html.escape(user.full_name or user.first_name)}\n"
            f"🆔 ID: <code>{user.id}</code>\n\n"
            "📊 <b>Umumiy ko'rsatkichlar:</b>\n"
            f"• 👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
            f"• 🏆 O'ynalgan o'yinlar: <b>{total_games} ta</b>\n"
            f"• 🎮 Faol o'yinlar: <b>{len(games)} ta</b>\n"
            f"• 🚪 Ochiq lobbylar: <b>{len(lobbies)} ta</b>\n\n"
            "Kerakli bo'limni tanlang 👇"
        )
        await q.edit_message_text(text, reply_markup=admin_main_keyboard(), parse_mode="HTML")
        await q.answer()
        return True

    if action == "stats":
        db = await get_db()
        async with db.execute("SELECT COUNT(*) AS c FROM users") as cur:
            users_count = (await cur.fetchone())["c"]
        async with db.execute("SELECT COUNT(*) AS c FROM clans") as cur:
            clans_count = (await cur.fetchone())["c"]
        async with db.execute("SELECT COUNT(*) AS c FROM group_users") as cur:
            tracked_members = (await cur.fetchone())["c"]

        text = (
            "📊 <b>BATAFSIL TIZIM STATISTIKASI</b>\n\n"
            f"• 👤 Ro'yxatdan o'tganlar: <b>{users_count} ta</b>\n"
            f"• 👥 Guruh a'zolari bazasi: <b>{tracked_members} ta</b>\n"
            f"• 🛡️ Mafiya klanlari: <b>{clans_count} ta</b>\n"
            f"• 🎮 Hozir o'ynalayotgan o'yinlar: <b>{len(games)} ta</b>\n"
            f"• 🚪 Ochiq o'yin lobbilari: <b>{len(lobbies)} ta</b>\n\n"
            "⚡ <b>Server holati:</b> Barqaror (Online)\n"
            "🟢 <b>Ma'lumotlar bazasi:</b> WAL rejimida aiosqlite"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")]])
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        await q.answer()
        return True

    if action == "games":
        if not games:
            text = "🎮 <b>FAOL O'YINLAR</b>\n\nHozirda hech bir guruhda faol o'yin ketmayapti."
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")]])
            await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            await q.answer()
            return True

        rows = []
        lines = ["🎮 <b>HOZIRGI FAOL O'YINLAR:</b>\n"]
        for cid, g in list(games.items())[:10]:
            alive = sum(1 for a in g.get("alive", {}).values() if a)
            phase = g.get("phase", "night")
            night = g.get("night", 1)
            lines.append(f"• Chat <code>{cid}</code>: #{night}-tun, faza: <b>{phase}</b>, tiriklar: <b>{alive} ta</b>")
            rows.append([
                InlineKeyboardButton(f"🛑 To'xtatish ({cid})", callback_data=f"adm:kill:{cid}")
            ])
        rows.append([InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")])
        await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        await q.answer()
        return True

    if action == "kill":
        target_chat = int(parts[2])
        g = games.pop(target_chat, None)
        if g:
            cancel_game_timer(g)
            try:
                await context.bot.send_message(
                    chat_id=target_chat,
                    text="🛑 <b>O'yin Super Admin tomonidan majburiy to'xtatildi.</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            await q.answer(f"O'yin ({target_chat}) to'xtatildi!", show_alert=True)
        else:
            await q.answer("O'yin allaqachon tugagan.", show_alert=True)
        # Refresh games list
        return await handle_admin_callback(update, context)

    if action == "balance_info":
        text = (
            "💰 <b>BALANS VA MABLAG' BOSHQARUVI</b>\n\n"
            "Foydalanuvchilarga Coin yoki Gold berish uchun botga tabiiy tilda xabar yozishingiz mumkin:\n\n"
            "📝 <b>Misollar:</b>\n"
            "• <code>7651553630 ga 1000 coin ber</code>\n"
            "• <code>7651553630 ga 50 gold ber</code>\n"
            "• <code>12345678 ga qirol toji ber</code>\n\n"
            "Yoki buyruq orqali: <code>/coin 500</code> yoki <code>/gold 10</code> (reply qilib)."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")]])
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        await q.answer()
        return True

    if action == "config":
        configs = await get_all_bot_configs()
        lines = ["⚙️ <b>BOT KONFIGURATSIYASI (DINAMIK)</b>\n"]
        if configs:
            for k, v in configs.items():
                lines.append(f"• <b>{k}</b>: <code>{v}</code>")
        else:
            lines.append("<i>Hozircha maxsus dinamik parametrlar kiritilmagan. Standart konfiguratsiya faol.</i>")

        lines.extend([
            "",
            "💡 Yangi parametr o'rnatish uchun botga quyidagicha yozing:",
            "<code>set_config: kalit = qiymat</code> yoki tabiiy tilda: «tun vaqtini 30 qil»"
        ])
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")]])
        await q.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        await q.answer()
        return True

    if action == "broadcast_info":
        text = (
            "📢 <b>GLOBAL XABAR (BROADCAST) YUBORISH</b>\n\n"
            "Barcha guruhlarga yoki o'yinchilarga e'lon yuborish uchun botga shaxsiyda quyidagicha yozing:\n\n"
            "<code>broadcast: Hurmatli o'yinchilar, bot yangilandi!</code>\n"
            "yoki\n"
            "<code>hammaga xabar: Bugun soat 20:00 da turnir bo'ladi!</code>\n\n"
            "Bot barcha ma'lum guruhlarga xabarni yetkazadi."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")]])
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        await q.answer()
        return True

    if action == "ai_info":
        text = (
            "🤖 <b>AI MASTER BOSHQARUV TIZIMI</b>\n\n"
            "Siz super admin sifatida botga shaxsiy chatda xohlagan matnli buyruqlaringizni yozishingiz mumkin. "
            "Botning intellektual boshqaruv qatlami buyruqni tushunadi va avtomatik bajaradi:\n\n"
            "✨ <b>Qo'llab-quvvatlanadigan so'rovlar:</b>\n"
            "• ⏱ <b>Vaqtlar:</b> «tun vaqtini 30 qil», «kun vaqti 60 bo'lsin», «ovoz berish 30 soniya»\n"
            "• 🎭 <b>Rollar:</b> «Sherif rolini o'chir», «Jokerni yoq», «barcha rollarni yoq»\n"
            "• 💰 <b>Tangalar:</b> «7651553630 ga 500 coin ber», «falonchiga 50 gold qo'sh»\n"
            "• 👑 <b>Nishonlar:</b> «7651553630 ga qirol toji nishonini ber»\n"
            "• 🎮 <b>O'yinlar:</b> «faol o'yinlar ro'yxatini ber», «o'yinni to'xtat -100123»\n"
            "• 📢 <b>E'lon:</b> «barcha guruhlarga xabar yubor: ...»\n"
            "• 📊 <b>Statistika:</b> «bot holati qanaqa», «server holati»\n\n"
            "Har qanday vaqtda shaxsiy chatga yozing!"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")]])
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        await q.answer()
        return True

    return True
