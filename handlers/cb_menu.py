import html
import logging
from telegram.error import TelegramError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from database.models import is_admin, record_afterlife_bet
from core.engine import games, find_game_by_user, claim_gold_drop
from core.navigation import return_to_group_keyboard
from core.last_words import deliver_last_words, LAST_WORD_TEMPLATES
from core.graveyard import graveyard_status_text, graveyard_menu_keyboard
from handlers.shop import shop_callback_handler, shop_main_keyboard
from handlers.commands_user import (
    guide_cmd, balance_cmd, rating_cmd, profile_cmd, will_cmd, main_menu_keyboard
)

log = logging.getLogger("detektiv.handlers.cb_menu")


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    if not q or not q.data:
        return False
    data = q.data
    user = q.from_user
    uid = user.id

    # Gold Drop Claim Callback
    if data.startswith("claim_gold:"):
        parts = data.split(":")
        if len(parts) < 2:
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        drop_id = parts[1]
        user_name = (user.full_name or user.first_name or "O'yinchi")[:40]
        ok, msg_text, drop = await claim_gold_drop(drop_id, uid, user_name)
        await q.answer(msg_text, show_alert=True)
        if not ok or not drop:
            return True

        rem = drop["remaining"]
        tot = drop["total"]
        claimed_names = list(drop["claimed_by"].values())
        c_name = html.escape(drop["creator_name"])

        if rem > 0:
            recent_str = ", ".join(html.escape(n) for n in claimed_names[-5:])
            new_text = (
                f"🎁 <b>OLTIN SOVRIN (GOLD DROP)!</b>\n\n"
                f"👤 <b>{c_name}</b> guruhga <b>{tot} dona Gold</b> tashladi!\n"
                f"⚡️ Har bir ishtirokchi <b>1 donadan Gold</b> olishi mumkin.\n"
                f"Kim birinchi ulgursa, o'shaniki! Shoshiling!\n\n"
                f"💰 Qoldi: <b>{rem}/{tot} ta Gold</b>\n"
                f"🏃 So'nggi olganlar: {recent_str}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🎁 Gold olish (Qoldi: {rem})", callback_data=f"claim_gold:{drop_id}")]
            ])
        else:
            new_text = (
                f"🎉 <b>BARCHA GOLDLAR TERIB OLINDI!</b>\n\n"
                f"👤 <b>{c_name}</b> tashlagan <b>{tot} dona Gold</b> to'liq o'z egalarini topdi!\n\n"
                f"👥 Omadli ishtirokchilar ({len(claimed_names)} nafar):\n"
                + "\n".join(f"• 👤 {html.escape(n)}" for n in claimed_names[:15])
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Barcha Goldlar olindi", callback_data="drop_finished")]
            ])

        try:
            await q.edit_message_text(text=new_text, reply_markup=kb, parse_mode="HTML")
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
        return True

    if data == "drop_finished":
        await q.answer("✅ Ushbu tarqatishdagi barcha Goldlar olingan.", show_alert=True)
        return True

    # Last Words Callback (last_word:<key>:<uid>)
    if data.startswith("last_word:"):
        parts = data.split(":")
        if len(parts) < 3 or not parts[2].isdigit():
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        word_key = parts[1]
        target_uid = int(parts[2])
        if uid != target_uid:
            await q.answer("❌ Bu sizning xabaringiz emas.", show_alert=True)
            return True

        text = LAST_WORD_TEMPLATES.get(word_key, "Meni nohaq o'ldirdingiz!")
        game = find_game_by_user(uid)
        if game:
            await deliver_last_words(context, game, uid, text)
            await q.answer("✅ So'nggi so'zingiz shaharga yetkazildi!")
            try:
                await q.edit_message_text(
                    f"✅ <b>So'nggi so'zingiz butun shaharga yetkazildi:</b>\n«<i>{html.escape(text)}</i>»\n\nEndi guruhga qaytib o'yinni kuzatishingiz mumkin.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
        else:
            await q.answer("ℹ️ Faol o'yin topilmadi.")
        return True

    # Shop & Inventory callbacks
    if data.startswith("shop_") or data.startswith("buy_item:") or data.startswith("item:"):
        await shop_callback_handler(update, context)
        return True

    # In-game item activation callback (use_item:<item_id>:<chat_id>)
    if data.startswith("use_item:"):
        parts = data.split(":")
        if len(parts) < 3 or not parts[2].lstrip("-").isdigit():
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        item_id = parts[1]
        chat_id = int(parts[2])
        game = games.get(chat_id)
        if not game:
            await q.answer("❌ Faol o'yin topilmadi.", show_alert=True)
            return True
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar buyum ishlata olmaydi.", show_alert=True)
            return True

        from core.items import has_used_item, consume_game_item, ALREADY_USED_MSG
        if has_used_item(game, uid, item_id):
            await q.answer(ALREADY_USED_MSG, show_alert=True)
            return True

        if item_id == "extra_vote":
            if game.get("phase") != "voting":
                await q.answer("❌ Qo'shimcha ovozni faqat ovoz berish paytida ishlatish mumkin!", show_alert=True)
                return True
            success, msg = await consume_game_item(game, uid, "extra_vote")
            if not success:
                await q.answer(msg, show_alert=True)
                return True
            game.setdefault("extra_votes", set()).add(uid)
            await q.answer("🗳️ Qo'shimcha ovoz faollashtirildi! Sizning ovozingiz 2 barobar hisoblanadi (O'yinda 1 marta).", show_alert=True)
            try:
                await q.message.reply_text(
                    "🗳️ <b>Qo'shimcha ovoz faollashtirildi!</b>\nUshbu ovoz berishda sizning ovozingiz 2 barobar hisoblanadi.\n⚠️ <i>Eslatma: Har bir o'yinda faqat 1 marta ishlatish mumkin.</i>",
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            return True

        success, msg = await consume_game_item(game, uid, item_id)
        await q.answer(msg, show_alert=True)
        return True

    # Main Menu Navigation
    if data in ("guide_roles", "menu_guide"):
        await q.answer()
        context.args = None
        await guide_cmd(update, context)
        return True

    if data.startswith("menu_"):
        await q.answer()
        if data == "menu_main":
            adm = is_admin(uid, getattr(user, "username", ""))
            try:
                await q.edit_message_text(
                    "🏙️ <b>DETEKTIV MAFIA</b> bosh menyusi:\nKerakli bo'limni tanlang:",
                    reply_markup=main_menu_keyboard(adm),
                    parse_mode="HTML"
                )
            except Exception:
                await q.message.reply_text(
                    "🏙️ <b>DETEKTIV MAFIA</b> bosh menyusi:\nKerakli bo'limni tanlang:",
                    reply_markup=main_menu_keyboard(adm),
                    parse_mode="HTML"
                )
        elif data == "menu_game":
            from config import BOT_USERNAME
            add_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
            ])
            await q.message.reply_text(
                "🎮 <b>Mafia O'yini</b>\n\n"
                "Mafia o'yini faqat <b>Telegram guruhlarida</b> o'ynaladi.\n"
                "O'yin boshlash uchun botni guruhingizga qo'shing va guruhda <b>/game</b> buyrug'ini yuboring!",
                reply_markup=add_kb,
                parse_mode="HTML"
            )
        elif data == "menu_shop":
            try:
                await q.edit_message_text("🛒 Do'kon:", reply_markup=shop_main_keyboard())
            except Exception:
                await q.message.reply_text("🛒 Do'kon:", reply_markup=shop_main_keyboard())
        elif data == "menu_balance":
            await balance_cmd(update, context)
        elif data == "menu_rating":
            await rating_cmd(update, context)
        elif data == "menu_profile":
            await profile_cmd(update, context)
        elif data == "menu_will":
            await will_cmd(update, context)
        elif data == "menu_clan":
            from handlers.clans import clan_cmd
            await clan_cmd(update, context)
        return True

    # Graveyard Refresh Callback (grave_refresh:<game_id>)
    if data.startswith("grave_refresh:"):
        parts = data.split(":")
        game_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        game = find_game_by_user(uid)
        if not game and game_id:
            for g in games.values():
                if g.get("_db_id") == game_id:
                    game = g
                    break
        if not game and games:
            game = list(games.values())[0]

        if game:
            await q.answer("🔄 Yangilandi.")
            try:
                await q.edit_message_text(
                    text=graveyard_status_text(game, uid),
                    reply_markup=graveyard_menu_keyboard(game.get("_db_id", 0), group_link=game.get("group_link"))
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
        else:
            await q.answer("ℹ️ Faol o'yin topilmadi.", show_alert=True)
        return True

    # Graveyard Afterlife Bet (grave_bet:<game_id>:<team>:<amount>)
    if data.startswith("grave_bet:"):
        parts = data.split(":")
        if len(parts) < 4 or not parts[1].isdigit() or not parts[3].isdigit():
            await q.answer("❌ Noto'g'ri so'rov formati.", show_alert=True)
            return True
        game_id = int(parts[1])
        team = parts[2]
        amount = int(parts[3])
        if await record_afterlife_bet(game_id, uid, team, amount):
            await q.answer(f"✅ 50 Coin {team.upper()} g'alabasiga tikildi (2x yutuq)!", show_alert=True)
        else:
            await q.answer("❌ Balansingizda Coin yetarli emas.", show_alert=True)
        return True

    return False
