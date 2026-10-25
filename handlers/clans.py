import logging
from telegram import Update
from telegram.ext import ContextTypes

from database.models import (
    ensure_user, get_user_clan, create_clan, change_balance
)

log = logging.getLogger("detektiv.handlers.clans")

async def clan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message or update.effective_message
    if not user or not msg:
        return
    await ensure_user(user)

    clan = await get_user_clan(user.id)
    if not clan:
        text = (
            "⚔️ *Mafiya Sindikati (Klanlar)*\n\n"
            "Siz hali hech qanday Mafiya oilasiga a'zo emassiz.\n\n"
            "Yangi sindikat tuzish uchun (narxi 500 Coin):\n"
            "`/newclan <Klan Nomi> <TAG>`\n\n"
            "Misol: `/newclan CosaNostra CN`"
        )
        await msg.reply_text(text, parse_mode="Markdown")
        return

    text = (
        f"⚔️ *Mafiya Oilasi:* *[{clan['tag']}] {clan['name']}*\n\n"
        f"👑 Yetakchi ID: *{clan['leader_id']}*\n"
        f"💰 Oila xazinasi: *{clan['coins']} Coin*\n"
        f"🏆 Mavsumiy ochkolar: *{clan['score']} Ball*\n"
        f"👤 Sizning maqomingiz: *{clan.get('member_role', 'Aʼzo').capitalize()}*"
    )
    await msg.reply_text(text, parse_mode="Markdown")

async def newclan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message or update.effective_message
    if not user or not msg:
        return
    await ensure_user(user)

    existing = await get_user_clan(user.id)
    if existing:
        await msg.reply_text("❌ Siz allaqachon boshqa sindikat a'zosisiz.")
        return

    if not context.args or len(context.args) < 2:
        await msg.reply_text("❗ Foydalanish: `/newclan <Nomi> <TAG>`", parse_mode="Markdown")
        return

    name = context.args[0][:30]
    tag = context.args[1][:5].upper()

    cost = 500
    if not await change_balance(user.id, "coin", -cost, f"Klan ochish: {name}"):
        await msg.reply_text(f"❌ Sindikat tuzish uchun {cost} Coin kerak.")
        return

    clan_id = await create_clan(name, tag, user.id)
    if clan_id:
        await msg.reply_text(
            f"🎉 Tabriklaymiz! *[{tag}] {name}* nomli yangi Mafiya sindikati tuzildi!",
            parse_mode="Markdown"
        )
    else:
        await change_balance(user.id, "coin", cost, "Klan ochish xatosi qaytarildi")
        await msg.reply_text("❌ Bu nomdagi sindikat allaqachon mavjud.")
