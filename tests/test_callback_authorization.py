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

@pytest.mark.asyncio
async def test_king_decision_actor_spoofing_rejected(mock_context):
    chat_id = -100667
    king_uid = 11111
    attacker_uid = 22222
    imposter_uid = 33333

    game = {
        "chat": chat_id,
        "phase": "night",
        "players": [king_uid, attacker_uid, imposter_uid],
        "alive": {king_uid: True, attacker_uid: True, imposter_uid: True},
        "roles": {king_uid: "Qirol", attacker_uid: "Qotil", imposter_uid: "Fuqaro"},
        "_waiting_king": True,
    }
    games[chat_id] = game

    update = MagicMock()
    update.effective_chat.id = imposter_uid
    update.effective_user.id = imposter_uid
    update.callback_query = MagicMock()
    update.callback_query.data = f"king_kill:{king_uid}:{attacker_uid}"
    update.callback_query.from_user.id = imposter_uid
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "Faqat Qirol hukm chiqara oladi" in update.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_king_decision_dead_king_rejected(mock_context):
    chat_id = -100668
    king_uid = 11112
    attacker_uid = 22223

    game = {
        "chat": chat_id,
        "phase": "night",
        "players": [king_uid, attacker_uid],
        "alive": {king_uid: False, attacker_uid: True},
        "roles": {king_uid: "Qirol", attacker_uid: "Qotil"},
        "_waiting_king": True,
    }
    games[chat_id] = game

    update = MagicMock()
    update.effective_chat.id = king_uid
    update.effective_user.id = king_uid
    update.callback_query = MagicMock()
    update.callback_query.data = f"king_forgive:{king_uid}:{attacker_uid}"
    update.callback_query.from_user.id = king_uid
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "Halok bo'lgan Qirol" in update.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_king_decision_dead_or_missing_attacker_rejected(mock_context):
    chat_id = -100669
    king_uid = 11113
    attacker_uid = 22224

    game = {
        "chat": chat_id,
        "phase": "night",
        "players": [king_uid, attacker_uid],
        "alive": {king_uid: True, attacker_uid: False},
        "roles": {king_uid: "Qirol", attacker_uid: "Qotil"},
        "_waiting_king": True,
    }
    games[chat_id] = game

    update = MagicMock()
    update.effective_chat.id = king_uid
    update.effective_user.id = king_uid
    update.callback_query = MagicMock()
    update.callback_query.data = f"king_kill:{king_uid}:{attacker_uid}"
    update.callback_query.from_user.id = king_uid
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    assert "Hujumchi allaqachon o'yinda yo'q yoki vafot etgan" in update.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_day_to_vote_spectator_and_dead_rejected(mock_context):
    chat_id = -100670
    player_uid = 44441
    dead_player_uid = 44442
    spectator_uid = 44443

    game = {
        "chat": chat_id,
        "phase": "day",
        "players": [player_uid, dead_player_uid],
        "alive": {player_uid: True, dead_player_uid: False},
    }
    games[chat_id] = game

    # Spectator test
    update_spec = MagicMock()
    update_spec.effective_chat.id = chat_id
    update_spec.effective_user.id = spectator_uid
    update_spec.callback_query = MagicMock()
    update_spec.callback_query.data = f"day_to_vote:{chat_id}"
    update_spec.callback_query.from_user.id = spectator_uid
    update_spec.callback_query.answer = AsyncMock()

    await callback_router(update_spec, mock_context)
    update_spec.callback_query.answer.assert_called_once()
    assert "qatnashmayapsiz" in update_spec.callback_query.answer.call_args[0][0]

    # Dead player test
    update_dead = MagicMock()
    update_dead.effective_chat.id = chat_id
    update_dead.effective_user.id = dead_player_uid
    update_dead.callback_query = MagicMock()
    update_dead.callback_query.data = f"day_to_vote:{chat_id}"
    update_dead.callback_query.from_user.id = dead_player_uid
    update_dead.callback_query.answer = AsyncMock()

    await callback_router(update_dead, mock_context)
    update_dead.callback_query.answer.assert_called_once()
    assert "Halok bo'lganlar" in update_dead.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_callback_router_unrecognized_fallback(mock_context):
    update = MagicMock()
    update.effective_chat.id = 12345
    update.effective_user.id = 12345
    update.callback_query = MagicMock()
    update.callback_query.data = "unrecognized_legacy_payload_xyz"
    update.callback_query.from_user.id = 12345
    update.callback_query.answer = AsyncMock()

    await callback_router(update, mock_context)

    update.callback_query.answer.assert_called_once()
    args, kwargs = update.callback_query.answer.call_args
    assert "muddati o'tgan yoki faol emas" in args[0]
    assert kwargs.get("show_alert") is True
