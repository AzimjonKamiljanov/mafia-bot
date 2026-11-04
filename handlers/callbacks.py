import logging
from telegram.error import TelegramError
from telegram import Update
from telegram.ext import ContextTypes

from database.models import ensure_user
from core.rate_limiter import is_rate_limited
from handlers.cb_night import check_night_completed, get_pending_night_actors
from handlers.settings import handle_settings_callback
from handlers.admin_panel import handle_admin_callback
from handlers.cb_admin import handle_admin_grant_callback
from handlers.cb_social import handle_social_callback
from handlers.cb_menu import handle_menu_callback
from handlers.cb_lobby import handle_lobby_callback
from handlers.cb_night import handle_night_callback
from handlers.cb_voting import handle_voting_callback

log = logging.getLogger("detektiv.handlers.callbacks")

__all__ = ["callback_router", "check_night_completed", "get_pending_night_actors"]


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    data = q.data or ""
    user = q.from_user
    uid = user.id
    await ensure_user(user)

    if is_rate_limited(uid, action="cb", max_rate=12, window_seconds=2.0):
        try:
            await q.answer("⏳ Iltimos, tugmalarni juda tez bosmang!", show_alert=False)
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)
        return

    # 1. Settings callbacks (sett:)
    if data.startswith("sett:"):
        if await handle_settings_callback(update, context):
            return

    # 2. Admin panel callbacks (adm:)
    if data.startswith("adm:"):
        if await handle_admin_callback(update, context):
            return

    # 3. Admin AI grant confirmation callbacks (adm_grant_confirm:, adm_grant_cancel:)
    if data.startswith("adm_grant_confirm:") or data.startswith("adm_grant_cancel:"):
        if await handle_admin_grant_callback(update, context):
            return

    # 4. Social callbacks (soc_acc:, soc_rej:)
    if data.startswith("soc_acc:") or data.startswith("soc_rej:"):
        if await handle_social_callback(update, context):
            return

    # 5. Menu, drop, last words, shop, and graveyard callbacks
    if (
        data.startswith("claim_gold:")
        or data == "drop_finished"
        or data.startswith("last_word:")
        or data.startswith("shop_")
        or data.startswith("buy_item:")
        or data.startswith("item:")
        or data.startswith("use_item:")
        or data in ("guide_roles", "menu_guide")
        or data.startswith("menu_")
        or data.startswith("grave_refresh:")
        or data.startswith("grave_bet:")
    ):
        if await handle_menu_callback(update, context):
            return

    # 6. Lobby callbacks (lobby_join:, lobby_call:, lobby_leave:, lobby_start:, lobby_stop:)
    if data.startswith("lobby_"):
        if await handle_lobby_callback(update, context):
            return

    # 7. Night callbacks (act:, disguise:, tgt:, cancel_action, king_kill:, king_forgive:)
    if (
        data.startswith("act:")
        or data.startswith("disguise:")
        or data.startswith("tgt:")
        or data == "cancel_action"
        or data.startswith("king_kill:")
        or data.startswith("king_forgive:")
    ):
        if await handle_night_callback(update, context):
            return

    # 8. Voting & Verdict callbacks (day_to_vote:, vote:, verdict:, mayor_reveal:)
    if (
        data.startswith("day_to_vote:")
        or data.startswith("vote:")
        or data.startswith("verdict:")
        or data.startswith("mayor_reveal:")
    ):
        if await handle_voting_callback(update, context):
            return
