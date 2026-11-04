import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from database.db import init_db, get_db
from core.engine import games, lobbies, abort_game, abort_lobby, finish_game
from handlers.callbacks import callback_router
from bot import cleanup_orphaned_games

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.get_chat_member = AsyncMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_lobby_stop_fails_closed_on_error(mock_context):
    chat_id = -1005551
    user_id = 998877

    # Setup an active lobby and game
    lobby_timer = asyncio.create_task(asyncio.sleep(100))
    game_timer = asyncio.create_task(asyncio.sleep(100))
    lobbies[chat_id] = {"open": True, "_timer_task": lobby_timer, "players": [user_id]}
    games[chat_id] = {"chat": chat_id, "phase": "lobby", "_timer_task": game_timer, "players": [user_id]}

    # Mock get_chat_member raising an exception (e.g. Telegram network error)
    mock_context.bot.get_chat_member.side_effect = Exception("Telegram API network timeout")

    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_user.id = user_id
    update.effective_user.username = "intruder"
    update.callback_query = MagicMock()
    update.callback_query.data = f"lobby_stop:{chat_id}"
    update.callback_query.from_user.id = user_id
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    # Must FAIL CLOSED: lobby and game must NOT be stopped
    assert chat_id in lobbies, "Lobby was stopped despite error (failed open)!"
    assert chat_id in games, "Game was stopped despite error (failed open)!"
    assert not lobby_timer.cancelled(), "Lobby timer was cancelled despite error!"
    assert not game_timer.cancelled(), "Game timer was cancelled despite error!"

    # Clean up tasks
    lobby_timer.cancel()
    game_timer.cancel()
    lobbies.pop(chat_id, None)
    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_abort_game_cancels_timer_and_persists_aborted():
    await init_db()
    chat_id = -1005552

    # Insert a dummy active game
    db = await get_db()
    cur = await db.execute("""
        INSERT INTO games (chat_id, state, phase, data, created_at, updated_at)
        VALUES (?, 'active', 'night', '{}', '2026-01-01', '2026-01-01')
    """, (chat_id,))
    db_id = cur.lastrowid
    await db.commit()

    timer_task = asyncio.create_task(asyncio.sleep(100))
    games[chat_id] = {
        "chat": chat_id,
        "phase": "night",
        "_db_id": db_id,
        "_timer_task": timer_task
    }

    assert not timer_task.cancelled()
    was_active = await abort_game(chat_id)

    assert was_active is True
    assert timer_task.cancelled()
    assert chat_id not in games

    # Verify DB state is now 'aborted'
    async with db.execute("SELECT state, finished_at FROM games WHERE game_id = ?", (db_id,)) as c:
        row = await c.fetchone()
        assert row["state"] == "aborted"
        assert row["finished_at"] is not None

@pytest.mark.asyncio
async def test_finish_game_persists_finished():
    await init_db()
    chat_id = -1005553

    db = await get_db()
    cur = await db.execute("""
        INSERT INTO games (chat_id, state, phase, data, created_at, updated_at)
        VALUES (?, 'active', 'night', '{}', '2026-01-01', '2026-01-01')
    """, (chat_id,))
    db_id = cur.lastrowid
    await db.commit()

    game = {
        "chat": chat_id,
        "phase": "night",
        "_db_id": db_id,
        "players": [101, 102],
        "alive": {101: True, 102: True},
        "names": {101: "P1", 102: "P2"},
        "roles": {101: "Detektiv", 102: "Fuqaro"},
        "_finish_started": False,
    }
    games[chat_id] = game

    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()

    await finish_game(ctx, game, winners=[101, 102], winning_team="blue")

    # Verify DB state is now 'finished'
    async with db.execute("SELECT state, finished_at FROM games WHERE game_id = ?", (db_id,)) as c:
        row = await c.fetchone()
        assert row["state"] == "finished"
        assert row["finished_at"] is not None

@pytest.mark.asyncio
async def test_startup_cleanup_orphaned_games():
    await init_db()
    chat_id = -1005554

    db = await get_db()
    await db.execute("UPDATE games SET state = 'aborted' WHERE state = 'active'")
    await db.commit()

    cur = await db.execute("""
        INSERT INTO games (chat_id, state, phase, data, created_at, updated_at)
        VALUES (?, 'active', 'voting', '{}', '2026-01-01', '2026-01-01')
    """, (chat_id,))
    db_id = cur.lastrowid
    await db.commit()

    mock_app = MagicMock()
    mock_app.bot = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    await cleanup_orphaned_games(mock_app)

    async with db.execute("SELECT state, finished_at FROM games WHERE game_id = ?", (db_id,)) as c:
        row = await c.fetchone()
        assert row["state"] == "aborted"
        assert row["finished_at"] is not None

    mock_app.bot.send_message.assert_called_once()
