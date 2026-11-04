import html
import logging
from telegram.error import TelegramError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import MIN_PLAYERS, BOT_USERNAME
from database.models import is_admin, ensure_user, track_group_member
from core.engine import games, lobbies, display_name, abort_lobby, abort_game
from phases.lobby import lobby_text, lobby_keyboard, start_game, call_players_in_chat

log = logging.getLogger("detektiv.handlers.commands_lobby")


async def startgame_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message or update.message
    if not chat or not msg:
        return
    if chat.type not in ("group", "supergroup"):
        add_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🎮 <b>O'yinni boshlash (/startgame)</b>\n\n"
            "Mafia o'yini faqat <b>Telegram guruhlarida</b> o'ynaladi.\n"
            "Botni guruhingizga qo'shing va o'sha yerda <b>/game</b> buyrug'ini yuboring!",
            reply_markup=add_kb,
            parse_mode="HTML"
        )
        return

    if not user:
        return

    chat_id = chat.id
    lobby = lobbies.get(chat_id)
    if not lobby or not lobby.get("open"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="ℹ️ Hozirda faol lobby yo'q. Yangi o'yin ochish uchun <b>/game</b> buyrug'ini yuboring.",
            parse_mode="HTML"
        )
        return

    if user.id not in lobby["players"] and not is_admin(user.id, getattr(user, "username", "")):
        await context.bot.send_message(
            chat_id=chat_id,
            text="❗ O'yinni boshlash uchun avval lobbiga qo'shiling."
        )
        return

    if len(lobby["players"]) < MIN_PLAYERS:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❗ O'yinni boshlash uchun kamida <b>{MIN_PLAYERS}</b> kishi kerak. Hozir: {len(lobby['players'])} ta.",
            parse_mode="HTML"
        )
        return

    await start_game(context, chat_id)


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message or update.message
    if not chat or not msg or not user:
        return
    if chat.type not in ("group", "supergroup"):
        add_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🛑 <b>O'yinni to'xtatish (/stop)</b>\n\n"
            "Ushbu buyruq faqat <b>Telegram guruhlarida ishlaydi</b> (o'yin yoki lobbyni to'xtatish uchun).",
            reply_markup=add_kb,
            parse_mode="HTML"
        )
        return

    chat_id = chat.id
    if chat_id not in games and chat_id not in lobbies:
        await msg.reply_text("ℹ️ Hozirda ushbu guruhda faol o'yin yoki lobby yo'q.")
        return

    # Check admin privileges (Fail closed on error)
    if not is_admin(user.id):
        try:
            member = await context.bot.get_chat_member(chat_id, user.id)
            if member.status not in ("administrator", "creator"):
                await msg.reply_text("❌ Faqat guruh admini o'yinni to'xtata oladi.")
                return
        except Exception as e:
            log.warning("get_chat_member failed on stop_cmd for %s in chat %s: %s", user.id, chat_id, e)
            await msg.reply_text("❌ Guruh adminlik huquqini tekshirib bo'lmadi. Amal bekor qilindi.")
            return

    lobby = abort_lobby(chat_id)
    if lobby:
        pinned_id = lobby.get("pinned_message_id")
        if pinned_id:
            try:
                await context.bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_id)
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

    await abort_game(chat_id)
    await msg.reply_text("🛑 O'yin yoki lobby ma'mur tomonidan to'xtatildi.")


async def chiqish_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or not msg or not user:
        return
    if chat.type not in ("group", "supergroup"):
        add_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
        ])
        await msg.reply_text(
            "🚪 <b>Lobbyni tark etish (/chiqish)</b>\n\n"
            "Ushbu buyruq faqat <b>Telegram guruhlarida</b> ochilgan lobbyni tark etish uchun ishlatiladi.",
            reply_markup=add_kb,
            parse_mode="HTML"
        )
        return
    lobby = lobbies.get(chat.id)
    if lobby and lobby.get("open"):
        if user.id in lobby["players"]:
            lobby["players"].remove(user.id)
            lobby["names"].pop(user.id, None)
            lobby["badges"].pop(user.id, None)
            await msg.reply_text(f"🚪 <b>{html.escape(user.full_name)}</b> lobbyni tark etdi.", parse_mode="HTML")
            try:
                await context.bot.edit_message_text(
                    chat_id=chat.id,
                    message_id=lobby["message_id"],
                    text=lobby_text(lobby),
                    reply_markup=lobby_keyboard(chat.id, include_bot_link=True),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            return

    game = games.get(chat.id)
    if game and user.id in game.get("players", []):
        if not game.get("alive", {}).get(user.id, False):
            await msg.reply_text("💀 Siz allaqachon halok bo'lgansiz.")
            return

        game["alive"][user.id] = False
        p_name = display_name(game, user.id)
        await msg.reply_text(
            f"🚪 <b>{html.escape(p_name)}</b> o'yinni tark etdi (halok bo'ldi deb hisoblanadi).",
            parse_mode="HTML"
        )

        from core.engine import check_winner, save_runtime
        await save_runtime(game)

        won = await check_winner(context, game)
        if won:
            return

        cur_phase = game.get("phase")
        if cur_phase == "verdict" and game.get("accused_uid") == user.id:
            from core.engine import cancel_game_timer
            cancel_game_timer(game)
            await msg.reply_text("⚖️ Ayblanuvchi o'yinni tark etgani sababli sud yakunlandi. Shahar tun quchog'iga kirdi.")
            game["night"] = game.get("night", 1) + 1
            from phases.night import start_night
            await start_night(context, game)
            return
        elif cur_phase == "voting":
            alive_voters = [u for u in game.get("players", []) if game.get("alive", {}).get(u, False)]
            votes = game.get("votes", {})
            if alive_voters and all(u in votes for u in alive_voters):
                from phases.voting import finish_voting
                await finish_voting(context, game)
                return
        return

    await msg.reply_text("ℹ️ Siz hech qanday faol o'yinda yoki lobbida emassiz.")


async def call_players_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or chat.type not in ("group", "supergroup"):
        if msg:
            add_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "📣 <b>O'yinchilarni chaqirish (/call)</b>\n\n"
                "Ushbu buyruq faqat <b>Telegram guruhlarida</b> o'yinchilarni mafia o'yiniga chorlash uchun ishlatiladi.",
                reply_markup=add_kb,
                parse_mode="HTML"
            )
        return

    if user:
        await ensure_user(user)
        await track_group_member(chat.id, user)

    caller_name = (user.full_name or user.first_name)[:40] if user else ""
    await call_players_in_chat(context, chat.id, caller_name)
