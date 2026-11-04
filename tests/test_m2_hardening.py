import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from database.db import init_db
from database.models import ensure_user, change_balance, get_balance, is_admin
from core.engine import active_drops, lobbies, games
from bot import (
    create_bot_app, PM_DISPATCH_TABLE, PM_DISPATCH_LOOKUP,
    post_init, handle_private_message
)
from handlers.social import send_cmd, coin_cmd, gold_cmd, para_cmd, bro_cmd, givegul_cmd
from handlers.commands_lobby import startgame_cmd, stop_cmd, chiqish_cmd, call_players_cmd
from handlers.commands_user import (
    start_cmd, profile_cmd, balance_cmd, will_cmd, rating_cmd,
    guide_cmd, reveal_cmd, salom_cmd, use_item_cmd
)
from phases.lobby import create_lobby

@pytest.mark.asyncio
async def test_command_matrix_coverage_and_collision_free():
    """Verify all 34 commands are registered, PM_DISPATCH_TABLE has zero collisions, and aliases route accurately."""
    app = create_bot_app()
    cmd_handlers = [h for h in app.handlers[0] if isinstance(h, CommandHandler)]
    
    # 1. Verify 34 registered command handlers in app
    assert len(cmd_handlers) >= 34, f"Expected at least 34 command handlers, got {len(cmd_handlers)}"

    # 2. Verify PM_DISPATCH_TABLE has zero key collisions
    all_pm_aliases = [alias for aliases in PM_DISPATCH_TABLE.keys() for alias in aliases]
    unique_pm_aliases = set(all_pm_aliases)
    assert len(all_pm_aliases) == len(unique_pm_aliases), (
        f"PM_DISPATCH_TABLE has duplicate aliases: {len(all_pm_aliases) - len(unique_pm_aliases)} collisions found!"
    )

    # 3. Verify collision fix: 'coin' and 'gold' route to coin_cmd and gold_cmd, NOT balance_cmd
    assert PM_DISPATCH_LOOKUP["coin"] == coin_cmd
    assert PM_DISPATCH_LOOKUP["gold"] == gold_cmd
    assert PM_DISPATCH_LOOKUP["balans"] == balance_cmd
    assert PM_DISPATCH_LOOKUP["balance"] == balance_cmd
    assert PM_DISPATCH_LOOKUP["hisob"] == balance_cmd
    assert PM_DISPATCH_LOOKUP["tangalar"] == balance_cmd
    assert PM_DISPATCH_LOOKUP["wallet"] == balance_cmd

@pytest.mark.asyncio
async def test_send_cmd_runtime_and_sender_name_fix():
    """Verify /send does not crash with UnboundLocalError and properly stores creator_name."""
    await init_db()
    
    # Mock user and update
    uid = 999101
    user = MagicMock()
    user.id = uid
    user.full_name = "Don Sponsor"
    user.first_name = "Don"
    user.username = "sponsor_don"
    user.is_bot = False

    chat = MagicMock()
    chat.type = "supergroup"
    chat.id = -10099901

    msg = MagicMock()
    msg.from_user = user
    msg.chat = chat
    msg.reply_text = AsyncMock()
    
    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = msg
    update.message = msg

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = ["10"]
    context.bot = MagicMock()
    sent_msg = MagicMock()
    sent_msg.message_id = 8881
    context.bot.send_message = AsyncMock(return_value=sent_msg)

    # Give user 100 Gold
    await ensure_user(user)
    await change_balance(uid, "gold", 100, "Initial test deposit")
    initial_gold = await get_balance(uid, "gold")
    assert initial_gold >= 10

    # Call send_cmd
    await send_cmd(update, context)

    # Verify context.bot.send_message was called with HTML format
    assert context.bot.send_message.called
    kwargs = context.bot.send_message.call_args[1]
    assert kwargs["parse_mode"] == "HTML"
    assert "Don Sponsor" in kwargs["text"]

    # Verify drop was registered in active_drops with valid creator_name
    drop = next((d for d in active_drops.values() if d.get("creator_id") == uid), None)
    assert drop is not None
    assert drop["creator_name"] == "Don Sponsor"
    assert drop["total"] == 10
    assert drop["remaining"] == 10

    # Verify 10 Gold deducted
    final_gold = await get_balance(uid, "gold")
    assert final_gold == initial_gold - 10

@pytest.mark.asyncio
async def test_handlers_none_user_and_none_message_safety():
    """Verify all major handlers gracefully handle None effective_user and None message without crashing."""
    await init_db()
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.args = []
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()

    # Handlers that must survive update.effective_user = None (e.g. channel post)
    handlers = [
        startgame_cmd, stop_cmd, chiqish_cmd, call_players_cmd,
        start_cmd, profile_cmd, balance_cmd, will_cmd, rating_cmd,
        guide_cmd, reveal_cmd, salom_cmd, use_item_cmd,
        para_cmd, bro_cmd, givegul_cmd, send_cmd, coin_cmd, gold_cmd,
        create_lobby
    ]

    for handler in handlers:
        up = MagicMock(spec=Update)
        up.effective_user = None
        up.effective_chat = MagicMock()
        up.effective_chat.type = "group"
        up.effective_chat.id = -100777
        
        msg = MagicMock()
        msg.from_user = None
        msg.reply_to_message = None
        msg.reply_text = AsyncMock()
        up.effective_message = msg
        up.message = msg
        up.callback_query = None

        # Execute handler - must NOT raise AttributeError or UnboundLocalError
        try:
            await handler(up, ctx)
        except Exception as e:
            pytest.fail(f"Handler {handler.__name__} crashed with {type(e).__name__}: {e} when effective_user was None")

    # Handlers that must survive update.message = None (e.g. edited message or callback transition)
    for handler in [start_cmd, salom_cmd, profile_cmd, balance_cmd, will_cmd]:
        up = MagicMock(spec=Update)
        up.effective_user = MagicMock()
        up.effective_user.id = 999202
        up.effective_user.first_name = "User202"
        up.effective_user.full_name = "User 202"
        up.effective_chat = MagicMock()
        up.effective_chat.type = "private"
        up.effective_chat.id = 999202
        
        eff_msg = MagicMock()
        eff_msg.reply_text = AsyncMock()
        up.effective_message = eff_msg
        up.message = None  # update.message is None!
        up.callback_query = None

        try:
            await handler(up, ctx)
        except AttributeError as e:
            pytest.fail(f"Handler {handler.__name__} crashed with AttributeError: {e} when update.message was None")

@pytest.mark.asyncio
async def test_social_reply_missing_target_safety():
    """Verify /para, /bro, /givegul gracefully handle missing reply target or bot target."""
    await init_db()
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.args = []

    user = MagicMock()
    user.id = 999303
    user.full_name = "Applicant"

    chat = MagicMock()
    chat.type = "group"
    chat.id = -100555

    for handler in [para_cmd, bro_cmd, givegul_cmd]:
        # Case A: No reply_to_message
        up = MagicMock(spec=Update)
        up.effective_user = user
        up.effective_chat = chat
        msg = MagicMock()
        msg.from_user = user
        msg.reply_to_message = None
        msg.reply_text = AsyncMock()
        up.effective_message = msg
        up.message = msg

        await handler(up, ctx)
        assert msg.reply_text.called
        assert "Reply" in msg.reply_text.call_args[0][0]

        # Case B: reply_to_message has no from_user (anonymous post)
        msg.reply_text.reset_mock()
        reply_msg = MagicMock()
        reply_msg.from_user = None
        msg.reply_to_message = reply_msg

        await handler(up, ctx)
        assert msg.reply_text.called
