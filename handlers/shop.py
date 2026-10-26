import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import COIN_SHOP, GOLD_SHOP, BOT_USERNAME
from database.models import (
    ensure_user, get_user, change_balance, get_inventory, add_item,
    get_badge, set_badge, deactivate_badge, get_owned_badges, save_owned_badge, is_admin
)

log = logging.getLogger("detektiv.handlers.shop")

def shop_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 💰 Coin Do'kon", callback_data="shop_coin")],
        [InlineKeyboardButton("🥇 👑 Gold VIP Do'kon", callback_data="shop_gold")],
        [InlineKeyboardButton("🎒 📦 Mening buyumlarim", callback_data="shop_items")],
        [InlineKeyboardButton("⬅️ 🏠 Bosh menyu", callback_data="menu_main")]
    ])

async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg = update.message or update.effective_message
    if not user or not msg:
        return
    await ensure_user(user)

    is_group = bool(chat and getattr(chat, "type", "") in ("group", "supergroup"))
    if is_group:
        pm_link = f"https://t.me/{BOT_USERNAME}?start=shop"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Botda ko'rish (Shaxsiy)", url=pm_link)
        ]])
        await msg.reply_text(
            "🛍️ <b>Detektiv Do'koni</b>\n\n"
            "Buyumlar xarid qilish va inventarni boshqarish faqat botning shaxsiy chatida amalga oshiriladi.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    text = (
        "🛍️ *Detektiv Do'koni (Shop)*\n\n"
        "O'yinda ustunlik beruvchi maxsus buyumlar, himoyalar va nufuzli unvonlar (Badges).\n\n"
        "Kerakli bo'limni tanlang:"
    )
    await msg.reply_text(text, reply_markup=shop_main_keyboard(), parse_mode="Markdown")

async def shop_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    chat = update.effective_chat
    if chat and getattr(chat, "type", "") in ("group", "supergroup"):
        await q.answer("🛍️ Do'kon va inventar faqat botning shaxsiy chatida ishlaydi.", show_alert=True)
        return

    user = q.from_user
    uid = user.id
    await ensure_user(user)
    data = q.data

    if data in ("shop:category:badges", "shop_gold"):
        data = "shop_gold"

    if data == "menu_shop" or data == "shop_main":
        await q.answer()
        await q.edit_message_text(
            "🛒 *Detektiv Do'koni*\nKerakli bo'limni tanlang:",
            reply_markup=shop_main_keyboard(),
            parse_mode="Markdown"
        )
        return

    if data == "shop_coin":
        await q.answer()
        rows = []
        for k, (name, price) in COIN_SHOP.items():
            rows.append([InlineKeyboardButton(f"{name} — {price} 🪙", callback_data=f"buy_item:coin:{k}")])
        rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="shop_main")])
        await q.edit_message_text(
            "🪙 *Coin Shop*\nTangalaringiz evaziga buyumlar xarid qiling:",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="Markdown"
        )
        return

    if data == "shop_gold":
        await q.answer()
        rows = []
        for k, (name, price) in GOLD_SHOP.items():
            rows.append([InlineKeyboardButton(f"{name} — {price} 🥇", callback_data=f"buy_item:gold:{k}")])
        rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="shop_main")])
        await q.edit_message_text(
            "🥇 *Gold Shop*\nOltin evaziga nufuzli belgilar (Badge) va noyob qasos qurollari:",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="Markdown"
        )
        return

    if data == "shop_items" or data == "item:list":
        await q.answer()
        inv = await get_inventory(uid)
        badges = await get_owned_badges(uid)
        active_badge = await get_badge(uid) or "Yo'q"

        knife = inv.get("revenge_knife", 0)
        fake_doc = inv.get("fake_document", 0)
        ruler_prot = inv.get("ruler_protection", 0)
        prot = inv.get("protection", 0)
        rose = inv.get("rose", 0)

        lines = [
            "📦 *Mening Buyumlarim va Belgilarim*",
            "",
            f"🏷️ Faol belgi: *{active_badge}*",
            "",
            "🎒 Buyumlar:",
            f"• 🔪 Qasos pichog'i: *{knife}*",
            f"• 📄 Soxta hujjat: *{fake_doc}*",
            f"• 👑 Hukmdan himoya: *{ruler_prot}*",
            f"• 🛡️ Tungi himoya: *{prot}*",
            f"• 🌹 Gul: *{rose}*"
        ]

        rows = []
        if badges:
            for b in badges:
                k = b["badge_key"]
                n = b["badge_name"]
                is_act = (n == active_badge)
                txt = f"🟢 {n} (Faol)" if is_act else f"⚪ {n} (Aktivlashtirish)"
                rows.append([InlineKeyboardButton(txt, callback_data=f"item:badge:{k}")])

        rows.append([InlineKeyboardButton("❌ Belgini o'chirish", callback_data="item:off")])
        rows.append([InlineKeyboardButton("⬅️ Do'konga qaytish", callback_data="shop_main")])

        await q.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="Markdown"
        )
        return

    if data.startswith("buy_item:"):
        parts = data.split(":")
        currency = parts[1]
        key = parts[2]

        if currency == "coin" and key in COIN_SHOP:
            name, price = COIN_SHOP[key]
            field_map = {
                "fake_document": "fake_document",
                "ruler_protection": "ruler_protection",
                "coin_protect": "protection",
                "rose": "rose"
            }
            field = field_map.get(key, "protection")
            if not await change_balance(uid, "coin", -price, f"Shop: {name}"):
                await q.answer("❌ Tangalaringiz (Coin) yetarli emas!", show_alert=True)
                return
            await add_item(uid, field, 1)
            await q.answer(f"✅ {name} xarid qilindi!", show_alert=True)
            return

        if currency == "gold" and key in GOLD_SHOP:
            name, price = GOLD_SHOP[key]
            if not await change_balance(uid, "gold", -price, f"Shop: {name}"):
                await q.answer("❌ Oltinlaringiz (Gold) yetarli emas!", show_alert=True)
                return
            if key == "revenge_knife":
                await add_item(uid, "revenge_knife", 1)
            else:
                await save_owned_badge(uid, key, name)
                await set_badge(uid, key, name)
            await q.answer(f"✅ {name} muvaffaqiyatli xarid qilindi!", show_alert=True)
            return

    if data.startswith("item:badge:"):
        key = data.split(":")[2]
        badges = await get_owned_badges(uid)
        target_badge = next((b for b in badges if b["badge_key"] == key), None)
        if target_badge:
            await set_badge(uid, key, target_badge["badge_name"])
            await q.answer(f"🟢 {target_badge['badge_name']} faollashtirildi!", show_alert=True)
            try:
                await shop_items(update, context)
            except Exception:
                pass
        return

    if data == "item:off":
        await deactivate_badge(uid)
        await q.answer("⚪ Faol belgi olib tashlandi.", show_alert=True)
        try:
            await shop_items(update, context)
        except Exception:
            pass
        return
