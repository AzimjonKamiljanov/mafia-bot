import logging
import asyncio
from telegram.error import TelegramError
from telegram import (
    Update, BotCommand, BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats, BotCommandScopeChat, BotCommandScopeDefault,
    BotCommandScopeAllChatAdministrators
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, ChatMemberHandler, filters, ContextTypes
)

from config import BOT_TOKEN, ADMIN_IDS
from database.db import init_db, close_db
from database.models import ensure_user, track_group_member
from handlers import (
    start_cmd, salom_cmd, startgame_cmd, will_cmd, profile_cmd, balance_cmd, rating_cmd, guide_cmd,
    stop_cmd, chiqish_cmd, reveal_cmd, shop_cmd, clan_cmd, newclan_cmd,
    para_cmd, dpara_cmd, mypara_cmd, bro_cmd, dbro_cmd, mybro_cmd,
    givegul_cmd, send_cmd, coin_cmd, gold_cmd, givecoin_cmd, givegold_cmd,
    call_players_cmd, callback_router, plan_cmd, boost_cmd, settings_cmd, admin_cmd, stats_cmd,
    goal_cmd, teamwork_cmd, use_item_cmd
)
from phases.lobby import create_lobby

from core.logging_config import setup_logging

setup_logging()
log = logging.getLogger("detektiv.bot")

# In-memory TTL cache for group user tracking to prevent redundant SQLite queries (Feature 34)
_group_user_ttl_cache: Dict[Tuple[int, int], float] = {}
_GROUP_USER_CACHE_TTL_SECONDS: float = 300.0


async def track_group_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ensure any user sending a message in a group is recorded in DB and counts as active in game."""
    chat = update.effective_chat
    user = update.effective_user
    now = time.time()
    if user and not user.is_bot:
        try:
            cache_key = (chat.id if chat else 0, user.id)
            last_recorded = _group_user_ttl_cache.get(cache_key, 0.0)

            # Skip redundant DB writes if recorded recently within TTL
            if now - last_recorded >= _GROUP_USER_CACHE_TTL_SECONDS:
                await ensure_user(user)
                if chat and chat.type in ("group", "supergroup"):
                    await track_group_member(chat.id, user)
                _group_user_ttl_cache[cache_key] = now

            # Count group chat participation as game activity in memory so active discussants are never marked AFK
            if chat and chat.type in ("group", "supergroup"):
                from core.engine import games
                game = games.get(chat.id)
                if game and game.get("phase") in ("day", "voting", "verdict"):
                    if user.id in game.get("players", []) and game.get("alive", {}).get(user.id, False):
                        from core.afk_penalty import record_player_activity
                        record_player_activity(game, user.id)
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)

    # Track newly added or joined members via message service update
    if update.message and update.message.new_chat_members and chat and chat.type in ("group", "supergroup"):
        for new_user in update.message.new_chat_members:
            if not new_user.is_bot:
                try:
                    await ensure_user(new_user)
                    await track_group_member(chat.id, new_user)
                    log.info("New group member tracked via new_chat_members in %s: %s (%s)", chat.id, new_user.full_name, new_user.id)
                except Exception as e:
                    log.debug("Error tracking new chat member: %s", e)

async def track_chat_member_updated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track when users join, are added, or change status in a group."""
    result = update.chat_member
    if not result:
        return
    chat = result.chat
    if not chat or chat.type not in ("group", "supergroup"):
        return
    new_member = result.new_chat_member
    if new_member and new_member.user and not new_member.user.is_bot:
        if new_member.status in ("member", "administrator", "creator", "restricted"):
            try:
                await ensure_user(new_member.user)
                await track_group_member(chat.id, new_member.user)
                log.info("New group member tracked via ChatMemberHandler in %s: %s (%s)", chat.id, new_member.user.full_name, new_member.user.id)
            except Exception as e:
                log.debug("Error in track_chat_member_updated: %s", e)

PM_DISPATCH_TABLE = {
    ("salom", "assalom", "assalomu alaykum", "assalomualaykum", "salomlar", "hello", "hi"): salom_cmd,
    ("profil", "profile", "profilim", "mening profilim", "shaxsiy", "me"): profile_cmd,
    ("balans", "balance", "hisob", "pul", "pulim", "tangalar", "wallet"): balance_cmd,
    ("dokon", "do'kon", "shop", "magazin", "bozor"): shop_cmd,
    ("reyting", "rating", "top", "top10", "top 10", "top 15", "leaderboard"): rating_cmd,
    ("rollar", "guide", "qo'llanma", "qollanma", "yordam", "help", "qoidalar", "rules"): guide_cmd,
    ("vasiyat", "vasiyatnoma", "will"): will_cmd,
    ("klan", "clan", "sindikat", "oila"): clan_cmd,
    ("newclan", "yangi_klan", "yangiklan"): newclan_cmd,
    ("stats", "statistika", "holat"): stats_cmd,
    ("start", "menu", "menyu", "bosh menyu"): start_cmd,
    ("reja", "plan", "mexanika"): plan_cmd,
    ("boost", "premium", "vip"): boost_cmd,
    ("goal", "maqsad"): goal_cmd,
    ("teamwork", "teamwork-preview", "teamwork_preview", "hamkorlik"): teamwork_cmd,
    ("settings", "sozlama", "sozlamalar"): settings_cmd,
    ("admin", "panel", "boshqaruv"): admin_cmd,
    ("coin", "givecoin", "sendcoin"): coin_cmd,
    ("gold", "givegold", "sendgold"): gold_cmd,
    ("send", "drop", "golddrop"): send_cmd,
    ("givegul",): givegul_cmd,
    ("para",): para_cmd,
    ("dpara",): dpara_cmd,
    ("mypara", "juftlik", "juftim"): mypara_cmd,
    ("bro",): bro_cmd,
    ("dbro",): dbro_cmd,
    ("mybro", "birodar", "broim"): mybro_cmd,
    ("oyin", "o'yin", "game", "play", "boshlash", "oyun"): create_lobby,
    ("startgame", "start_game", "go"): startgame_cmd,
    ("stop", "toxtat"): stop_cmd,
    ("chiqish", "leave", "tark"): chiqish_cmd,
    ("call", "chaqir", "tagall", "chorlov"): call_players_cmd,
    ("reveal", "mer"): reveal_cmd,
    ("use", "ishlat"): use_item_cmd,
}

PM_DISPATCH_LOOKUP = {k: fn for aliases, fn in PM_DISPATCH_TABLE.items() for k in aliases}

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages sent to bot in private chat (e.g. Dying Words / Last Words, slash-free commands, and fallbacks)."""
    if not update.message or not update.effective_user or update.effective_user.is_bot:
        return

    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        return

    from core.rate_limiter import is_rate_limited
    if is_rate_limited(uid, action="pm_cmd", max_rate=10, window_seconds=3.0):
        try:
            await update.message.reply_text("⏳ Iltimos, xabarlarni juda tez yubormang!")
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
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
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)
            return

    # 2. Tokenize message text and extract command token + arguments
    parts = text.split()
    first_word = parts[0].strip()
    # Strip leading slash and @botusername if present (e.g. /profil, /profil@Detektivmj_bot, profil)
    cmd_token = first_word.lstrip("/").split("@")[0].lower()
    args = parts[1:]
    context.args = args

    full_lower = text.lower().strip()

    # 3. Handle standard commands via fast O(1) dictionary lookup
    handler = PM_DISPATCH_LOOKUP.get(full_lower) or PM_DISPATCH_LOOKUP.get(cmd_token)
    if handler:
        await handler(update, context)
        return

    # 4. Check if admin sent AI natural language configuration command
    from database.models import is_admin
    adm = is_admin(uid, getattr(update.effective_user, "username", ""))
    if adm:
        from handlers.admin_ai import process_admin_ai_message
        if await process_admin_ai_message(update, context):
            return

    # 5. Default fallback for unhandled PM text or unrecognized slash command
    from handlers.commands import main_menu_keyboard
    if first_word.startswith("/"):
        import html
        await update.message.reply_text(
            f"❌ Noma'lum buyruq: <code>{html.escape(first_word)}</code>\n\n"
            "Barcha mavjud bo'limlar bilan quyidagi menyu orqali tanishishingiz mumkin:",
            reply_markup=main_menu_keyboard(adm),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "👋 <b>Detektiv Mafia Bot</b>\n\n"
            "Quyidagi menyu orqali kerakli bo'limni tanlang:",
            reply_markup=main_menu_keyboard(adm),
            parse_mode="HTML"
        )

async def cleanup_orphaned_games(app: Application):
    """Mark any orphaned active game rows as aborted and notify affected group chats."""
    try:
        from database.db import get_db
        from database.models import now_iso
        db = await get_db()
        now = now_iso()
        async with db.execute("SELECT DISTINCT chat_id FROM games WHERE state = 'active'") as cur:
            rows = await cur.fetchall()
            active_chat_ids = [r["chat_id"] for r in rows]

        if active_chat_ids:
            log.info("Found %d orphaned active games on startup; marking aborted...", len(active_chat_ids))
            await db.execute("""
                UPDATE games
                SET state = 'aborted', phase = 'aborted', finished_at = ?, updated_at = ?
                WHERE state = 'active'
            """, (now, now))
            await db.commit()

            for cid in active_chat_ids:
                try:
                    await app.bot.send_message(
                        chat_id=cid,
                        text="🛑 <b>Bot qayta ishga tushirildi.</b>\n"
                             "Avvalgi to'xtatilgan o'yin bekor qilindi. Yangi o'yin boshlash uchun /game yoki /start bosing.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    log.debug("Could not notify chat %s of restart abort: %s", cid, e)
    except Exception as e:
        log.warning("cleanup_orphaned_games failed: %s", e)

async def _periodic_drop_cleanup_task(app: Application):
    """Background task to sweep expired gold drops every 60 seconds."""
    from core.engine import cleanup_expired_drops
    while True:
        try:
            await asyncio.sleep(60)
            purged = cleanup_expired_drops()
            if purged > 0:
                log.info("Purged %d expired gold drops in periodic sweep", purged)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.debug("Error in periodic drop cleanup: %s", e)

async def post_init(app: Application):
    """Initialize DB and configure Telegram Bot commands list with strict scopes."""
    await init_db()
    await cleanup_orphaned_games(app)
    asyncio.create_task(_periodic_drop_cleanup_task(app))
    try:
        # 1. Group commands: Only group game commands
        group_commands = [
            BotCommand("game", "Guruhda Mafia o'yinini ochish"),
            BotCommand("startgame", "O'yinni boshlash"),
            BotCommand("call", "O'yinchilarni chaqirish"),
            BotCommand("settings", "O'yin sozlamalari"),
            BotCommand("salom", "Salomlashish va profil havolasi"),
            BotCommand("stop", "O'yinni to'xtatish"),
            BotCommand("chiqish", "Lobbyni tark etish"),
            BotCommand("para", "Juftlik tuzish (Reply)"),
            BotCommand("bro", "Birodarlik rishtasi (Reply)"),
            BotCommand("send", "Guruhga Gold Drop tashlash"),
        ]
        # 0. Default scope fallback: Safe group commands (NEVER leak admin commands)
        await app.bot.set_my_commands(group_commands, scope=BotCommandScopeDefault())
        await app.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())

        # 2. Private chats scope: Personal commands
        private_commands = [
            BotCommand("start", "Botni ishga tushirish"),
            BotCommand("profile", "Mening profilim"),
            BotCommand("balance", "Balans"),
            BotCommand("will", "So'nggi Vasiyatnoma yozish"),
            BotCommand("shop", "Do'kon (Shop)"),
            BotCommand("rating", "TOP reyting"),
            BotCommand("guide", "Rollar qo'llanmasi"),
            BotCommand("clan", "Mafiya oilasi / klan"),
            BotCommand("salom", "Salomlashish"),
        ]
        await app.bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())

        # 3. Admin scope: Admin command set including /admin, /settings, /stats, /plan and full controls in private chat
        admin_commands = [
            BotCommand("admin", "Master Admin paneli"),
            BotCommand("settings", "O'yin sozlamalari"),
            BotCommand("stats", "Tizim statistikasi"),
            BotCommand("plan", "O'yin mexanikasi va rejasi"),
            BotCommand("start", "Botni ishga tushirish"),
            BotCommand("profile", "Admin profili"),
            BotCommand("balance", "Admin balansi"),
            BotCommand("shop", "Do'kon"),
            BotCommand("guide", "Rollar qo'llanmasi"),
            BotCommand("rating", "TOP reyting"),
            BotCommand("boost", "Telegram Premium va Boost"),
        ]
        for aid in ADMIN_IDS:
            if aid:
                try:
                    await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=aid))
                except Exception as e:
                    log.warning("Could not set admin commands for chat %s: %s", aid, e)

        log.info("Bot commands successfully registered with strict Telegram scopes.")
    except Exception as e:
        log.warning("Could not set bot commands: %s", e)

from telegram.request import HTTPXRequest
from telegram.ext import ExtBot

class SafeExtBot(ExtBot):
    """
    ExtBot subclass that strictly enforces parse_mode='HTML' for <tg-emoji> tags,
    enriches emojis to animated custom emojis, auto-adapts to official Telegram
    custom emoji IDs upon Document_invalid, and gracefully retries on entity parsing failures.
    """
    _needs_real_telegram_ids: bool = False

    async def _do_post(self, endpoint, data=None, *args, **kwargs):
        if data and isinstance(data, dict):
            for k in ("text", "caption"):
                if k in data and isinstance(data[k], str):
                    # 1. Normalize legacy document-id to official emoji-id
                    if "<tg-emoji" in data[k] and "document-id=" in data[k]:
                        import re
                        data[k] = re.sub(r'<tg-emoji\s+document-id="(\d+)"', r'<tg-emoji emoji-id="\1"', data[k])

                    # 2. Strict parse_mode enforcement & universal emoji animation
                    if "<tg-emoji" in data[k]:
                        data["parse_mode"] = "HTML"
                        from core.emojis import enrich_with_animated_emojis
                        data[k] = enrich_with_animated_emojis(data[k])
                    elif data.get("parse_mode") in ("HTML", "html"):
                        from core.emojis import enrich_with_animated_emojis
                        data[k] = enrich_with_animated_emojis(data[k])
                    elif data.get("parse_mode") is None:
                        from core.emojis import _COMBINED_EMOJI_RE, enrich_with_animated_emojis
                        if _COMBINED_EMOJI_RE.search(data[k]):
                            import html
                            escaped = html.escape(data[k])
                            enriched = enrich_with_animated_emojis(escaped)
                            if enriched != escaped:
                                data[k] = enriched
                                data["parse_mode"] = "HTML"

                    # 3. If real Telegram IDs were previously flagged as required, translate proactively
                    if "<tg-emoji" in data[k] and self._needs_real_telegram_ids:
                        from core.emojis import resolve_all_tg_emoji_to_real_telegram
                        data[k] = resolve_all_tg_emoji_to_real_telegram(data[k])

        try:
            return await super()._do_post(endpoint, data, *args, **kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            if any(term in err_msg for term in ("document_invalid", "can't parse entities", "custom_emoji")) and data and isinstance(data, dict):
                log.warning("Telegram BadRequest error (%s). Adapting with verified Telegram Custom Emoji IDs...", e)
                self._needs_real_telegram_ids = True
                self.__class__._needs_real_telegram_ids = True
                retry_data = dict(data)
                for k in ("text", "caption"):
                    if k in retry_data and isinstance(retry_data[k], str) and "<tg-emoji" in retry_data[k]:
                        from core.emojis import resolve_all_tg_emoji_to_real_telegram
                        retry_data[k] = resolve_all_tg_emoji_to_real_telegram(retry_data[k])
                try:
                    return await super()._do_post(endpoint, retry_data, *args, **kwargs)
                except Exception as retry_err:
                    retry_msg = str(retry_err).lower()
                    if any(term in retry_msg for term in ("document_invalid", "can't parse entities", "custom_emoji")):
                        log.warning("Telegram Custom Emoji retry failed (%s). Stripping tags as fallback...", retry_err)
                        strip_data = dict(retry_data)
                        from core.visuals import strip_anim_emoji_tags
                        for k in ("text", "caption"):
                            if k in strip_data and isinstance(strip_data[k], str) and "<tg-emoji" in strip_data[k]:
                                strip_data[k] = strip_anim_emoji_tags(strip_data[k])
                        try:
                            return await super()._do_post(endpoint, strip_data, *args, **kwargs)
                        except Exception as final_err:
                            if "can't parse entities" in str(final_err).lower():
                                strip_data_plain = dict(strip_data)
                                strip_data_plain.pop("parse_mode", None)
                                return await super()._do_post(endpoint, strip_data_plain, *args, **kwargs)
                            raise
                    raise
            raise

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled exception while processing update: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ <i>Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring yoki /start buyrug'ini bering.</i>",
                parse_mode="HTML"
            )
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)

def create_bot_app() -> Application:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing or empty. Please verify .env or config.py.")

    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0
    )
    bot = SafeExtBot(BOT_TOKEN, request=request)
    app = Application.builder().bot(bot).concurrent_updates(True).post_init(post_init).build()
    app.add_error_handler(global_error_handler)

    # Core commands
    app.add_handler(CommandHandler(["start", "menu", "menyu"], start_cmd))
    app.add_handler(CommandHandler(["salom", "assalom", "assalomualaykum", "salomlar", "hello", "hi"], salom_cmd))
    app.add_handler(CommandHandler(["startgame", "boshlash", "start_game", "play", "go"], startgame_cmd))
    app.add_handler(CommandHandler(["game", "oyun", "oyin"], create_lobby))
    app.add_handler(CommandHandler(["settings", "sozlama", "sozlamalar"], settings_cmd))
    app.add_handler(CommandHandler(["admin", "panel", "boshqaruv"], admin_cmd))
    app.add_handler(CommandHandler(["plan", "reja", "mexanika"], plan_cmd))
    app.add_handler(CommandHandler(["boost", "premium", "vip"], boost_cmd))
    app.add_handler(CommandHandler(["goal", "maqsad"], goal_cmd))
    app.add_handler(CommandHandler(["teamwork", "teamwork_preview", "hamkorlik"], teamwork_cmd))
    app.add_handler(CommandHandler(["call", "chaqir", "tagall", "chorlov"], call_players_cmd))
    app.add_handler(CommandHandler(["will", "vasiyat", "vasiyatnoma"], will_cmd))
    app.add_handler(CommandHandler(["reveal", "mer"], reveal_cmd))
    app.add_handler(CommandHandler(["profile", "profil", "me", "shaxsiy"], profile_cmd))
    app.add_handler(CommandHandler(["balance", "balans", "hisob", "pul", "wallet"], balance_cmd))
    app.add_handler(CommandHandler(["rating", "reyting", "top", "top10", "leaderboard"], rating_cmd))
    app.add_handler(CommandHandler(["guide", "qollanma", "yordam", "help", "rules", "rollar", "qoidalar"], guide_cmd))
    app.add_handler(CommandHandler(["stop", "toxtat"], stop_cmd))
    app.add_handler(CommandHandler(["chiqish", "leave", "tark"], chiqish_cmd))
    app.add_handler(CommandHandler(["shop", "dokon", "magazin", "bozor"], shop_cmd))
    app.add_handler(CommandHandler(["clan", "klan", "sindikat", "oila"], clan_cmd))
    app.add_handler(CommandHandler(["newclan", "yangi_klan", "yangiklan"], newclan_cmd))
    app.add_handler(CommandHandler(["stats", "statistika", "holat"], stats_cmd))

    # Social commands
    app.add_handler(CommandHandler("para", para_cmd))
    app.add_handler(CommandHandler("dpara", dpara_cmd))
    app.add_handler(CommandHandler(["mypara", "juftlik", "juftim"], mypara_cmd))
    app.add_handler(CommandHandler("bro", bro_cmd))
    app.add_handler(CommandHandler("dbro", dbro_cmd))
    app.add_handler(CommandHandler(["mybro", "birodar", "broim"], mybro_cmd))
    app.add_handler(CommandHandler("givegul", givegul_cmd))
    app.add_handler(CommandHandler(["send", "drop", "golddrop"], send_cmd))
    app.add_handler(CommandHandler(["coin", "givecoin", "sendcoin"], coin_cmd))
    app.add_handler(CommandHandler(["gold", "givegold", "sendgold"], gold_cmd))
    app.add_handler(CommandHandler(["use", "ishlat"], use_item_cmd))

    # All callback queries
    app.add_handler(CallbackQueryHandler(callback_router))

    # Private message handler (e.g. Last Words, slash-free commands, and fallbacks)
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle_private_message)
    )

    # Group message tracker
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.ALL, track_group_user),
        group=1
    )

    # Chat member status update tracker (joins, leaves, invite link admissions)
    app.add_handler(ChatMemberHandler(track_chat_member_updated, ChatMemberHandler.CHAT_MEMBER))

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
        log.info("Health check HTTP server running on port %d (24/7 Koyeb/Render ready)", port)
    except Exception as e:
        log.warning("Could not start health check HTTP server on port %d: %s", port, e)

import urllib.request
import time

def start_render_keep_alive():
    """If running on Render (RENDER_EXTERNAL_URL is set), ping itself every 10 min to prevent sleep."""
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        return
    def ping_loop():
        log.info("Render auto keep-alive active for %s (anti-sleep)", url)
        time.sleep(60)
        while True:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "RenderAntiSleep/1.0"})
                with urllib.request.urlopen(req, timeout=15):
                    pass
            except Exception as e:
                log.debug("Keep-alive ping to %s: %s", url, e)
            time.sleep(600)  # Ping every 10 minutes (Render free idle sleep is 15 minutes)

    t = threading.Thread(target=ping_loop, daemon=True)
    t.start()

def main():
    port = int(os.getenv("PORT", "8000") or 8000)
    start_health_server(port)
    start_render_keep_alive()
    log.info("Starting Telegram Mafia Bot...")
    app = create_bot_app()
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=5)

if __name__ == "__main__":
    main()
