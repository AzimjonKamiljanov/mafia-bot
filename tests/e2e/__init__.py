"""E2E Test Suite Package for Telegram Mafia ("Detektiv") Bot.

Provides shared fixtures, protocol mocks, test factories, and state reset utilities
for executing opaque-box 4-tier E2E tests against bot handlers and engine state machines.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Chat, Message, CallbackQuery
from telegram.ext import ContextTypes

from core.engine import games, lobbies, cancel_game_timer, cancel_lobby_timer
from core.rate_limiter import reset_rate_limits
from database.db import init_db, get_db


class MockUser:
    """Mock Telegram User object with spec-conforming attributes."""

    def __init__(
        self,
        uid: int,
        full_name: str,
        username: Optional[str] = None,
        is_premium: bool = False,
        is_bot: bool = False,
    ):
        self.id = uid
        self.full_name = full_name
        self.first_name = full_name.split()[0] if full_name else "User"
        self.last_name = " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""
        self.username = username or f"user_{uid}"
        self.is_premium = is_premium
        self.is_bot = is_bot

    def __repr__(self) -> str:
        return f"<MockUser id={self.id} name={self.full_name}>"


class MockChat:
    """Mock Telegram Chat object supporting private, group, and supergroup types."""

    def __init__(self, chat_id: int, chat_type: str = "group", title: Optional[str] = None):
        self.id = chat_id
        self.type = chat_type
        self.title = title or f"Chat {chat_id}"

    def __repr__(self) -> str:
        return f"<MockChat id={self.id} type={self.type}>"


def make_pm_update(
    uid: int = 12345678,
    username: str = "testuser",
    first_name: str = "Test",
    text: str = "",
    is_premium: bool = False,
) -> Update:
    """Construct an incoming Update simulating a Telegram private chat text message."""
    user = MockUser(uid, f"{first_name} User", username=username, is_premium=is_premium)
    chat = MockChat(uid, chat_type="private")

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user

    msg = MagicMock(spec=Message)
    msg.message_id = 99901
    msg.text = text
    msg.from_user = user
    msg.chat = chat
    msg.reply_to_message = None
    msg.reply_text = AsyncMock()
    msg.reply_html = AsyncMock()

    update.message = msg
    update.effective_message = msg
    update.callback_query = None
    return update


def make_group_message_update(
    chat_id: int = -1001000,
    user: Optional[MockUser] = None,
    text: str = "",
    reply_to: Optional[MockUser] = None,
) -> Update:
    """Construct an incoming Update simulating a message sent to a Telegram group chat."""
    if user is None:
        user = MockUser(998801, "Group Member", "member1")

    chat = MockChat(chat_id, chat_type="supergroup", title="Test Mafia Group")
    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user

    msg = MagicMock(spec=Message)
    msg.message_id = 100200
    msg.text = text
    msg.from_user = user
    msg.chat = chat
    msg.new_chat_members = []
    msg.reply_text = AsyncMock()
    msg.reply_html = AsyncMock()

    if reply_to:
        rep_msg = MagicMock(spec=Message)
        rep_msg.message_id = 100199
        rep_msg.from_user = reply_to
        rep_msg.chat = chat
        rep_msg.text = "Previous message"
        msg.reply_to_message = rep_msg
    else:
        msg.reply_to_message = None

    update.message = msg
    update.effective_message = msg
    update.callback_query = None
    return update


def make_callback_update(
    chat_id: int,
    user: MockUser,
    callback_data: str,
    message_id: int = 100200,
) -> Update:
    """Construct an incoming Update simulating an inline button callback query."""
    chat = MockChat(chat_id, chat_type="supergroup" if chat_id < 0 else "private")
    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user

    query = MagicMock(spec=CallbackQuery)
    query.id = f"cq_{user.id}_{int(time.time())}"
    query.from_user = user
    query.data = callback_data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_caption = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()

    msg = MagicMock(spec=Message)
    msg.message_id = message_id
    msg.chat = chat
    msg.reply_markup = None
    query.message = msg

    update.callback_query = query
    update.message = None
    update.effective_message = msg
    return update


def make_e2e_context() -> ContextTypes.DEFAULT_TYPE:
    """Create a fully-mocked Telegram ContextTypes.DEFAULT_TYPE instance."""
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.args = []
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    ctx.bot.answer_callback_query = AsyncMock()
    ctx.bot.send_photo = AsyncMock()
    ctx.bot.send_dice = AsyncMock()
    ctx.bot.send_animation = AsyncMock()
    ctx.bot.send_sticker = AsyncMock()
    ctx.bot.set_message_reaction = AsyncMock()
    ctx.bot.pin_chat_message = AsyncMock()
    ctx.bot.unpin_chat_message = AsyncMock()
    ctx.bot.get_chat_member = AsyncMock()
    ctx.bot.get_chat_administrators = AsyncMock()
    ctx.bot.set_my_commands = AsyncMock()
    return ctx


def reset_runtime_state():
    """Clear in-memory engine state and rate limiters."""
    for g in list(games.values()):
        cancel_game_timer(g)
    for l in list(lobbies.values()):
        cancel_lobby_timer(l)
    games.clear()
    lobbies.clear()
    reset_rate_limits()
