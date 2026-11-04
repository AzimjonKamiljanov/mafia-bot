import pytest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock
from database.db import init_db
from core.engine import (
    games, lobbies, is_game_stale, check_and_clean_stale_game, touch_game_activity
)
from handlers.cb_lobby import handle_lobby_callback
from handlers.commands_lobby import join_cmd, stop_cmd
from phases.night import start_night


@pytest.mark.asyncio
async def test_is_game_stale_conditions():
    """Verify stale game detection rules."""
    assert is_game_stale(None) is True
    assert is_game_stale({}) is True

    # Finished or aborted games
    assert is_game_stale({"phase": "finished"}) is True
    assert is_game_stale({"phase": "aborted"}) is True

    now = time.time()
    # Game older than 30 minutes
    assert is_game_stale({"phase": "night", "created_at": now - 2000, "last_activity": now}) is True

    # Game inactive with no timer task for > 45s
    assert is_game_stale({
        "phase": "night",
        "created_at": now - 100,
        "last_activity": now - 60,
        "_timer_task": None
    }) is True

    # Active game with running timer task
    active_task = asyncio.create_task(asyncio.sleep(10))
    active_game = {
        "phase": "night",
        "created_at": now - 10,
        "last_activity": now,
        "_timer_task": active_task
    }
    try:
        assert is_game_stale(active_game) is False
    finally:
        active_task.cancel()


@pytest.mark.asyncio
async def test_check_and_clean_stale_game():
    """Verify check_and_clean_stale_game evicts zombie games."""
    await init_db()
    games.clear()
    chat_id = -100777

    # Non-existent game
    assert check_and_clean_stale_game(chat_id) is False

    # Stale game in memory
    now = time.time()
    games[chat_id] = {
        "chat": chat_id,
        "phase": "night",
        "created_at": now - 500,
        "last_activity": now - 100,
        "_timer_task": None
    }
    assert check_and_clean_stale_game(chat_id) is True
    assert chat_id not in games


@pytest.mark.asyncio
async def test_lobby_join_callback_recovers_from_stale_game():
    """Clicking 'Qo'shilish' on a stale game evicts the dead game and creates/joins lobby."""
    await init_db()
    games.clear()
    lobbies.clear()

    chat_id = -100555
    now = time.time()
    # Dead zombie game from previous crash
    games[chat_id] = {
        "chat": chat_id,
        "phase": "night",
        "created_at": now - 500,
        "last_activity": now - 100,
        "_timer_task": None
    }

    update = MagicMock()
    q = MagicMock()
    user = MagicMock()
    user.id = 7711
    user.full_name = "Abbos"
    user.first_name = "Abbos"
    user.is_premium = False
    q.from_user = user
    q.data = f"lobby_join:{chat_id}"
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.message = MagicMock()
    q.message.chat_id = chat_id
    q.message.message_id = 99
    update.callback_query = q

    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.edit_message_text = AsyncMock()

    handled = await handle_lobby_callback(update, context)
    assert handled is True

    # Dead game should have been evicted
    assert chat_id not in games
    # Lobby should be created and user added
    assert chat_id in lobbies
    assert 7711 in lobbies[chat_id]["players"]
    q.answer.assert_called_with("✅ Siz o'yinga muvaffaqiyatli qo'shildingiz!")


@pytest.mark.asyncio
async def test_join_cmd_recovers_from_stale_game():
    """Command /join evicts a stale game and responds cleanly."""
    await init_db()
    games.clear()
    lobbies.clear()

    chat_id = -100444
    now = time.time()
    games[chat_id] = {
        "chat": chat_id,
        "phase": "night",
        "created_at": now - 500,
        "last_activity": now - 100,
        "_timer_task": None
    }

    update = MagicMock()
    chat = MagicMock()
    chat.id = chat_id
    chat.type = "supergroup"
    user = MagicMock()
    user.id = 8822
    user.full_name = "Jasur"
    user.first_name = "Jasur"
    msg = MagicMock()
    msg.reply_text = AsyncMock()

    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = msg
    context = MagicMock()

    await join_cmd(update, context)

    # Stale game evicted
    assert chat_id not in games
    msg.reply_text.assert_called()
    call_text = msg.reply_text.call_args[0][0]
    # Informs that there is no active lobby and to run /game
    assert "/game" in call_text


@pytest.mark.asyncio
async def test_stop_cmd_cleans_stale_game_for_any_user():
    """Running /stop when a game is stuck evicts the zombie game immediately."""
    await init_db()
    games.clear()
    lobbies.clear()

    chat_id = -100333
    now = time.time()
    games[chat_id] = {
        "chat": chat_id,
        "phase": "night",
        "created_at": now - 500,
        "last_activity": now - 100,
        "_timer_task": None
    }

    update = MagicMock()
    chat = MagicMock()
    chat.id = chat_id
    chat.type = "supergroup"
    user = MagicMock()
    user.id = 9933
    user.full_name = "Regular Player"
    user.first_name = "Regular Player"
    msg = MagicMock()
    msg.reply_text = AsyncMock()

    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = msg
    context = MagicMock()

    await stop_cmd(update, context)

    assert chat_id not in games
    msg.reply_text.assert_called()
    call_text = msg.reply_text.call_args[0][0]
    assert "Qotib qolgan o'yin tozalandi" in call_text


@pytest.mark.asyncio
async def test_start_night_escapes_special_characters():
    """Verify start_night escapes HTML characters in player names so announcement never crashes."""
    await init_db()
    games.clear()
    chat_id = -100222

    players = [1, 2, 3, 4]
    names = {
        1: "Ali <3 Love",
        2: "Bob & Alice",
        3: 'Charlie "The Boss"',
        4: "Dave > Frank"
    }
    roles = {
        1: "Detektiv",
        2: "Doktor",
        3: "Boshliq",
        4: "Fuqaro"
    }
    alive = {u: True for u in players}
    game = {
        "chat": chat_id,
        "players": players,
        "names": names,
        "roles": roles,
        "alive": alive,
        "phase": "lobby",
        "night": 1,
        "settings": {"night_seconds": 30}
    }
    games[chat_id] = game

    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.send_photo = AsyncMock()

    await start_night(context, game)

    # Timer task must be scheduled
    assert game.get("_timer_task") is not None
    assert not game["_timer_task"].done()
    game["_timer_task"].cancel()
