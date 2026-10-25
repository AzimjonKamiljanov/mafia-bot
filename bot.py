import logging
import asyncio
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)

from config import BOT_TOKEN
from database.db import init_db, close_db
from database.models import ensure_user, track_group_member
from handlers import (
    start_cmd, startgame_cmd, will_cmd, profile_cmd, balance_cmd, rating_cmd, guide_cmd,
    stop_cmd, chiqish_cmd, reveal_cmd, shop_cmd, clan_cmd, newclan_cmd,
    para_cmd, dpara_cmd, mypara_cmd, bro_cmd, dbro_cmd, mybro_cmd,
    givegul_cmd, send_cmd, coin_cmd, gold_cmd, givecoin_cmd, givegold_cmd,
    call_players_cmd, callback_router, plan_cmd, boost_cmd, settings_cmd, admin_cmd
)
from phases.lobby import create_lobby

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger("detektiv.bot")

async def track_group_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ensure any user sending a message in a group is recorded in DB and counts as active in game."""
    chat = update.effective_chat
    user = update.effective_user
    if user and not user.is_bot:
        try:
            await ensure_user(user)
            if chat and chat.type in ("group", "supergroup"):
                await track_group_member(chat.id, user)
                # Count group chat participation as game activity so active discussants are never marked AFK
                from core.engine import games
                game = games.get(chat.id)
                if game and game.get("phase") in ("day", "voting", "verdict"):
                    if user.id in game.get("players", []) and game.get("alive", {}).get(user.id, False):
                        from core.afk_penalty import record_player_activity
                        record_player_activity(game, user.id)
        except Exception:
            pass

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages sent to bot in private chat (e.g. Dying Words / Last Words)."""
    if not update.message or not update.effective_user or update.effective_user.is_bot:
        return

    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        return

    # 1. Check if user is waiting to deliver Last Words
    from core.engine import games
    for game in list(games.values()):
        if uid in game.get("waiting_last_words", {}):
            from core.last_words import deliver_last_words
            delivered = await deliver_last_words(context, game, uid, text)
            if delivered:
                try:
                    from core.navigation import return_to_group_keyboard
                    await update.message.reply_text(
                        "✅ <b>O'limingizdan oldingi so'nggi so'zingiz shaharga e'lon qilindi!</b>\n"
                        "Endi guruhga qaytib o'yinni kuzatib borishingiz mumkin.",
                        reply_markup=return_to_group_keyboard(game),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return

    # 2. Check if admin sent AI natural language configuration command
    from database.models import is_admin
    if is_admin(uid, getattr(update.effective_user, "username", "")):
        from handlers.admin_ai import process_admin_ai_message
        if await process_admin_ai_message(update, context):
            return

async def post_init(app: Application):
    """Initialize DB and configure Telegram Bot commands list."""
    await init_db()
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Botni ishga tushirish"),
            BotCommand("game", "Guruhda Mafia o'yinini ochish"),
            BotCommand("call", "O'yinchilarni chaqirish"),
            BotCommand("will", "So'nggi Vasiyatnoma yozish"),
            BotCommand("reveal", "Merlikni e'lon qilish (Mer)"),
            BotCommand("shop", "Do'kon (Shop)"),
            BotCommand("profile", "Mening profilim"),
            BotCommand("balance", "Balans"),
            BotCommand("rating", "TOP reyting"),
            BotCommand("guide", "Rollar qo'llanmasi"),
            BotCommand("clan", "Mafiya oilasi / klan"),
            BotCommand("stop", "O'yinni to'xtatish"),
            BotCommand("chiqish", "Lobbyni tark etish"),
            BotCommand("settings", "O'yin sozlamalari"),
            BotCommand("plan", "O'yin mexanikasi va rejasi"),
            BotCommand("boost", "Telegram Premium va Boost"),
            BotCommand("admin", "Master Admin paneli"),
            BotCommand("para", "Juftlik tuzish (Reply)"),
            BotCommand("bro", "Birodarlik rishtasi (Reply)"),
            BotCommand("send", "Guruhga Gold Drop tashlash (/send 10)"),
            BotCommand("coin", "Tangalar o'tkazish (Reply /coin 500)"),
            BotCommand("gold", "Oltin o'tkazish (Reply /gold 5)"),
        ])
        log.info("Bot commands successfully registered with Telegram.")
    except Exception as e:
        log.warning("Could not set bot commands: %s", e)

from telegram.request import HTTPXRequest

def create_bot_app() -> Application:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing or empty. Please verify .env or config.py.")

    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0
    )
    app = Application.builder().token(BOT_TOKEN).request(request).post_init(post_init).build()

    # Core commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler(["startgame", "boshlash", "start_game", "play", "go"], startgame_cmd))
    app.add_handler(CommandHandler(["game", "oyun", "oyin"], create_lobby))
    app.add_handler(CommandHandler(["settings", "sozlama", "sozlamalar"], settings_cmd))
    app.add_handler(CommandHandler(["admin", "panel"], admin_cmd))
    app.add_handler(CommandHandler(["plan", "reja"], plan_cmd))
    app.add_handler(CommandHandler(["boost", "premium"], boost_cmd))
    app.add_handler(CommandHandler(["call", "chaqir", "tagall"], call_players_cmd))
    app.add_handler(CommandHandler("will", will_cmd))
    app.add_handler(CommandHandler("reveal", reveal_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("rating", rating_cmd))
    app.add_handler(CommandHandler("guide", guide_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler(["chiqish", "leave", "tark"], chiqish_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("clan", clan_cmd))
    app.add_handler(CommandHandler("newclan", newclan_cmd))

    # Social commands
    app.add_handler(CommandHandler("para", para_cmd))
    app.add_handler(CommandHandler("dpara", dpara_cmd))
    app.add_handler(CommandHandler("mypara", mypara_cmd))
    app.add_handler(CommandHandler("bro", bro_cmd))
    app.add_handler(CommandHandler("dbro", dbro_cmd))
    app.add_handler(CommandHandler("mybro", mybro_cmd))
    app.add_handler(CommandHandler("givegul", givegul_cmd))
    app.add_handler(CommandHandler(["send", "drop", "golddrop"], send_cmd))
    app.add_handler(CommandHandler(["coin", "givecoin", "sendcoin"], coin_cmd))
    app.add_handler(CommandHandler(["gold", "givegold", "sendgold"], gold_cmd))

    # All callback queries
    app.add_handler(CallbackQueryHandler(callback_router))

    # Private message handler (e.g. Last Words)
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & (~filters.COMMAND), handle_private_message)
    )

    # Group message tracker
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.ALL, track_group_user),
        group=1
    )

    return app

import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "service": "Telegram Mafia Bot", "alive": true}')

    def log_message(self, format, *args):
        pass  # Suppress health check probe logs

def start_health_server(port: int = 8000):
    """Run lightweight HTTP server for Koyeb/Render/Cloud 24/7 health probes."""
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        log.info("Health check HTTP server running on port %d (24/7 Koyeb/Cloud ready)", port)
    except Exception as e:
        log.warning("Could not start health check HTTP server on port %d: %s", port, e)

def main():
    port = int(os.getenv("PORT", "8000") or 8000)
    start_health_server(port)
    log.info("Starting Telegram Mafia Bot...")
    app = create_bot_app()
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=5)

if __name__ == "__main__":
    main()
