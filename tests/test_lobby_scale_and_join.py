import pytest
from unittest.mock import AsyncMock, MagicMock
from config import MIN_PLAYERS, MAX_PLAYERS, ROLES
from roles.allocator import choose_roles
from core.engine import games, lobbies, get_chat_lock
from phases.lobby import lobby_text, lobby_keyboard
from handlers.cb_lobby import handle_lobby_callback
from handlers.commands_lobby import join_cmd
from bot import track_group_user
from database.db import init_db

def test_allocator_scale_up_to_100():
    """Verify role allocator produces valid roles for all sizes 4 to 100."""
    for n in (4, 10, 25, 35, 50, 75, 100):
        roles = choose_roles(n)
        assert roles is not None
        assert len(roles) == n
        expected_red = max(1, n // 5)
        red_count = sum(1 for r in roles if ROLES.get(r) == "red")
        assert red_count == expected_red
        assert "Boshliq" in roles
        if "Qotil" in roles:
            assert "Boshliq" in roles
        if "Sherif" in roles:
            assert "Detektiv" in roles
            assert n >= 7

def test_lobby_text_truncation_over_25_players():
    """Verify that lobby text with 100 players truncates smoothly under 4096 chars."""
    fake_players = list(range(1001, 1101)) # 100 players
    names = {uid: f"Foydalanuvchi_{uid}" for uid in fake_players}
    lobby = {
        "chat_id": -100999,
        "players": fake_players,
        "names": names,
        "badges": {},
        "open": True,
    }
    text = lobby_text(lobby)
    assert len(text) < 4000, f"Lobby text length ({len(text)}) exceeds safe Telegram limit!"
    assert "Ishtirokchilar (100/100):" in text
    assert "Foydalanuvchi_1001" in text
    assert "va yana <b>75 nafar</b> o'yinchi" in text

@pytest.mark.asyncio
async def test_lobby_join_callback_above_35_players():
    """Verify that callback join works for player 36 up to 100."""
    await init_db()
    games.clear()
    lobbies.clear()

    chat_id = -100888
    existing_players = list(range(1000, 1050)) # 50 players already joined
    names = {uid: f"User_{uid}" for uid in existing_players}
    lobby = {
        "chat_id": chat_id,
        "players": existing_players,
        "names": names,
        "badges": {},
        "open": True,
        "message_id": 999,
    }
    lobbies[chat_id] = lobby

    new_user_id = 9999
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.data = f"lobby_join:{chat_id}"
    update.callback_query.from_user.id = new_user_id
    update.callback_query.from_user.full_name = "Yangi O'yinchi"
    update.callback_query.from_user.first_name = "Yangi"
    update.callback_query.from_user.is_premium = False
    update.callback_query.message.chat_id = chat_id
    update.callback_query.message.message_id = 999
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot.edit_message_text = AsyncMock()

    res = await handle_lobby_callback(update, ctx)
    assert res is True
    assert new_user_id in lobby["players"]
    assert len(lobby["players"]) == 51
    update.callback_query.answer.assert_called_with("✅ Siz o'yinga muvaffaqiyatli qo'shildingiz!")

@pytest.mark.asyncio
async def test_join_cmd_in_group():
    """Verify that /join command in group joins the lobby."""
    await init_db()
    games.clear()
    lobbies.clear()

    chat_id = -100777
    lobby = {
        "chat_id": chat_id,
        "players": [111],
        "names": {111: "Player 1"},
        "badges": {},
        "open": True,
        "message_id": 555,
    }
    lobbies[chat_id] = lobby

    user_id = 222
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_chat.type = "supergroup"
    update.effective_user.id = user_id
    update.effective_user.full_name = "Player 2"
    update.effective_user.first_name = "Player"
    update.effective_user.username = "player2"
    update.effective_user.is_premium = False
    update.effective_message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot.edit_message_text = AsyncMock()

    await join_cmd(update, ctx)
    assert user_id in lobby["players"]
    assert len(lobby["players"]) == 2
    update.effective_message.reply_text.assert_called_once()
    assert "muvaffaqiyatli qo'shildi" in update.effective_message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_auto_switch_between_lobbies():
    """Verify that joining group 2 auto-removes user from group 1 lobby."""
    await init_db()
    games.clear()
    lobbies.clear()

    chat1 = -100111
    chat2 = -100222
    user_id = 777

    lobby1 = {
        "chat_id": chat1,
        "players": [user_id, 888],
        "names": {user_id: "User 777", 888: "User 888"},
        "badges": {},
        "open": True,
        "message_id": 11,
    }
    lobby2 = {
        "chat_id": chat2,
        "players": [999],
        "names": {999: "User 999"},
        "badges": {},
        "open": True,
        "message_id": 22,
    }
    lobbies[chat1] = lobby1
    lobbies[chat2] = lobby2

    update = MagicMock()
    update.effective_chat.id = chat2
    update.effective_chat.type = "supergroup"
    update.effective_user.id = user_id
    update.effective_user.full_name = "User 777"
    update.effective_user.first_name = "User"
    update.effective_user.username = "user777"
    update.effective_user.is_premium = False
    update.effective_message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot.edit_message_text = AsyncMock()

    await join_cmd(update, ctx)

    # Should be removed from lobby1 and present in lobby2
    assert user_id not in lobby1["players"]
    assert user_id in lobby2["players"]

@pytest.mark.asyncio
async def test_finished_game_does_not_block_new_join():
    """Verify that a finished game in games dictionary does not block lobby joining."""
    await init_db()
    games.clear()
    lobbies.clear()

    chat_id = -100333
    games[chat_id] = {
        "chat": chat_id,
        "phase": "finished",
        "players": [123, 456],
        "alive": {123: True, 456: False},
    }
    lobby = {
        "chat_id": chat_id,
        "players": [],
        "names": {},
        "badges": {},
        "open": True,
        "message_id": 33,
    }
    lobbies[chat_id] = lobby

    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_chat.type = "supergroup"
    update.effective_user.id = 123
    update.effective_user.full_name = "Alive Winner"
    update.effective_user.first_name = "Winner"
    update.effective_user.username = "winner"
    update.effective_user.is_premium = False
    update.effective_message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot.edit_message_text = AsyncMock()

    await join_cmd(update, ctx)
    assert 123 in lobby["players"]

@pytest.mark.asyncio
async def test_quick_text_join_in_track_group_user():
    """Verify that sending '+' in a group chat with an open lobby joins the user."""
    await init_db()
    games.clear()
    lobbies.clear()

    chat_id = -100444
    user_id = 555
    lobby = {
        "chat_id": chat_id,
        "players": [111],
        "names": {111: "Host"},
        "badges": {},
        "open": True,
        "message_id": 44,
    }
    lobbies[chat_id] = lobby

    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_chat.type = "supergroup"
    update.effective_user.id = user_id
    update.effective_user.is_bot = False
    update.effective_user.full_name = "Plus Player"
    update.effective_user.first_name = "Plus"
    update.effective_user.username = "plusplayer"
    update.effective_user.is_premium = False
    update.message.text = "+"
    update.message.new_chat_members = None
    update.message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot.edit_message_text = AsyncMock()

    await track_group_user(update, ctx)
    assert user_id in lobby["players"]
    update.message.reply_text.assert_called_once()
    assert "muvaffaqiyatli qo'shildi" in update.message.reply_text.call_args[0][0]
