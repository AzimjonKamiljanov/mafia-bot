import html
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import BOT_USERNAME
from database.models import (
    ensure_user, get_user_clan, create_clan, change_balance
)

log = logging.getLogger("detektiv.handlers.clans")

async def clan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg = update.message or update.effective_message
    if not user or not msg:
        return
    await ensure_user(user)

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=clan"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            "⚔️ <b>Mafiya Sindikati (Klanlar)</b>\n\n"
            "Klaningiz ma'lumotlarini botning shaxsiy chatida ko'ring:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    clan_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Profil", callback_data="menu_profile"),
            InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")
        ]
    ])
    clan = await get_user_clan(user.id)
    if not clan:
        text = (
            "⚔️ <b>Mafiya Sindikati (Klanlar)</b>\n\n"
            "Siz hali hech qanday Mafiya oilasiga a'zo emassiz.\n\n"
            "Yangi sindikat tuzish uchun (narxi 500 Coin):\n"
            "<code>/newclan &lt;Klan Nomi&gt; &lt;TAG&gt;</code>\n\n"
            "Misol: <code>/newclan CosaNostra CN</code>"
        )
        await msg.reply_text(text, reply_markup=clan_kb, parse_mode="HTML")
        return

    c_tag = html.escape(str(clan.get('tag', '')))
    c_name = html.escape(str(clan.get('name', '')))
    m_role = html.escape(str(clan.get('member_role', 'Aʼzo')).capitalize())
    text = (
        f"⚔️ <b>Mafiya Oilasi:</b> <b>[{c_tag}] {c_name}</b>\n\n"
        f"👑 Yetakchi ID: <code>{clan['leader_id']}</code>\n"
        f"💰 Oila xazinasi: <b>{clan['coins']} Coin</b>\n"
        f"🏆 Mavsumiy ochkolar: <b>{clan['score']} Ball</b>\n"
        f"👤 Sizning maqomingiz: <b>{m_role}</b>"
    )
    await msg.reply_text(text, reply_markup=clan_kb, parse_mode="HTML")

async def newclan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg = update.message or update.effective_message
    if not user or not msg:
        return
    await ensure_user(user)

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=clan"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            "⚔️ <b>Mafiya Sindikati (Klanlar)</b>\n\n"
            "Klan tuzish va boshqarish faqat botning shaxsiy chatida amalga oshiriladi.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    clan_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛡️ Sindikat / Klan", callback_data="menu_clan"),
            InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")
        ]
    ])

    existing = await get_user_clan(user.id)
    if existing:
        await msg.reply_text("❌ Siz allaqachon boshqa sindikat a'zosisiz.", reply_markup=clan_kb)
        return

    if not context.args or len(context.args) < 2:
        await msg.reply_text("❗ Foydalanish: <code>/newclan &lt;Nomi&gt; &lt;TAG&gt;</code>", reply_markup=clan_kb, parse_mode="HTML")
        return

    name = context.args[0][:30]
    tag = context.args[1][:5].upper()

    cost = 500
    if not await change_balance(user.id, "coin", -cost, f"Klan ochish: {name}"):
        await msg.reply_text(f"❌ Sindikat tuzish uchun {cost} Coin kerak.", reply_markup=clan_kb)
        return

    clan_id = await create_clan(name, tag, user.id)
    if clan_id:
        await msg.reply_text(
            f"🎉 Tabriklaymiz! <b>[{html.escape(tag)}] {html.escape(name)}</b> nomli yangi Mafiya sindikati tuzildi!",
            reply_markup=clan_kb,
            parse_mode="HTML"
        )
    else:
        await change_balance(user.id, "coin", cost, "Klan ochish xatosi qaytarildi")
        await msg.reply_text("❌ Bu nomdagi sindikat allaqachon mavjud.", reply_markup=clan_kb)
