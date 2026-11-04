import pytest
from unittest.mock import AsyncMock, MagicMock
from core.engine import games
from handlers.callbacks import callback_router

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_actor_spoofing_rejected(mock_context):
    chat_id = -100661
    actor = 1111
    imposter = 2222
    game = {
        "chat": chat_id,
        "phase": "night",
        "players": [actor, imposter],
        "alive": {actor: True, imposter: True},
        "roles": {actor: "Detektiv", imposter: "Fuqaro"},
    }
    games[chat_id] = game

    update = MagicMock()
    update.effective_chat.id = imposter
    update.effective_user.id = imposter
    update.callback_query = MagicMock()
    update.callback_query.data = f"act:detective:{actor}"
    update.callback_query.from_user.id = imposter
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "siz uchun emas" in update.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_dead_player_action_rejected(mock_context):
    chat_id = -100662
    dead_actor = 3333
    game = {
        "chat": chat_id,
        "phase": "night",
        "players": [dead_actor, 4444],
        "alive": {dead_actor: False, 4444: True},
        "roles": {dead_actor: "Doktor", 4444: "Fuqaro"},
    }
    games[chat_id] = game

    update = MagicMock()
    update.effective_chat.id = dead_actor
    update.effective_user.id = dead_actor
    update.callback_query = MagicMock()
    update.callback_query.data = f"act:protect:{dead_actor}"
    update.callback_query.from_user.id = dead_actor
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "Halok bo'lganlar" in update.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_role_mismatch_action_rejected(mock_context):
    chat_id = -100663
    actor = 5555
    game = {
        "chat": chat_id,
        "phase": "night",
        "players": [actor, 6666],
        "alive": {actor: True, 6666: True},
        "roles": {actor: "Fuqaro", 6666: "Detektiv"},
    }
    games[chat_id] = game

    update = MagicMock()
    update.effective_chat.id = actor
    update.effective_user.id = actor
    update.callback_query = MagicMock()
    # Civilian trying to kill
    update.callback_query.data = f"act:kill:{actor}"
    update.callback_query.from_user.id = actor
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "bajara olmaydi" in update.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_dead_target_selection_rejected(mock_context):
    chat_id = -100664
    actor = 7777
    dead_target = 8888
    game = {
        "chat": chat_id,
        "phase": "night",
        "players": [actor, dead_target],
        "alive": {actor: True, dead_target: False},
        "roles": {actor: "Boshliq", dead_target: "Fuqaro"},
    }
    games[chat_id] = game

    update = MagicMock()
    update.effective_chat.id = actor
    update.effective_user.id = actor
    update.callback_query = MagicMock()
    update.callback_query.data = f"tgt:kill:{actor}:{dead_target}"
    update.callback_query.from_user.id = actor
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "vafot etgan" in update.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_vote_dead_target_rejected(mock_context):
    chat_id = -100665
    voter = 9991
    dead_target = 9992
    game = {
        "chat": chat_id,
        "phase": "voting",
        "players": [voter, dead_target],
        "alive": {voter: True, dead_target: False},
        "roles": {voter: "Fuqaro", dead_target: "Fuqaro"},
    }
    games[chat_id] = game

    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_user.id = voter
    update.callback_query = MagicMock()
    update.callback_query.data = f"vote:{chat_id}:{dead_target}"
    update.callback_query.from_user.id = voter
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "tirik emas" in update.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_stale_button_rejected(mock_context):
    chat_id = -100666
    actor = 9993
    # No game exists in games or user game
    games.pop(chat_id, None)

    update = MagicMock()
    update.effective_chat.id = actor
    update.effective_user.id = actor
    update.callback_query = MagicMock()
    update.callback_query.data = f"act:detective:{actor}"
    update.callback_query.from_user.id = actor
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "muddati o'tgan" in update.callback_query.answer.call_args[0][0]
