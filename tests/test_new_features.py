import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from core.atmospheric_feed import broadcast_role_action, ROLE_ACTION_MESSAGES
from core.last_words import prompt_last_words, deliver_last_words, last_words_keyboard, LAST_WORD_TEMPLATES
from core.afk_penalty import handle_voting_sleepers, handle_night_sleepers, check_endgame_sleepers, record_player_activity

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_broadcast_role_action(mock_context):
    game = {
        "chat": -10055,
        "night": 1,
        "players": [1, 2, 3],
        "alive": {1: True, 2: True, 3: True},
    }

    # Broadcast mafia kill
    await broadcast_role_action(mock_context, game, actor=1, action="kill")
    assert mock_context.bot.send_message.call_count == 1
    call_args = mock_context.bot.send_message.call_args[1]
    assert call_args["chat_id"] == -10055
    assert "Don o'z o'ljasini tanladi" in call_args["text"]

    # Same action by same actor on same night should not duplicate
    await broadcast_role_action(mock_context, game, actor=1, action="kill")
    assert mock_context.bot.send_message.call_count == 1

    # Detective check
    await broadcast_role_action(mock_context, game, actor=2, action="detective")
    assert mock_context.bot.send_message.call_count == 2
    call_args2 = mock_context.bot.send_message.call_args[1]
    assert "Detektiv" in call_args2["text"]

@pytest.mark.asyncio
async def test_last_words_system(mock_context):
    game = {
        "chat": -10077,
        "players": [10, 20],
        "names": {10: "Akmal", 20: "Botir"},
        "roles": {10: "Fuqaro", 20: "Boshliq"},
        "alive": {10: False, 20: True},
    }

    # Prompt dead player
    await prompt_last_words(mock_context, game, 10)
    assert 10 in game["waiting_last_words"]
    assert mock_context.bot.send_message.call_count == 1
    pm_args = mock_context.bot.send_message.call_args[1]
    assert pm_args["chat_id"] == 10
    assert "so'nggi so'zingizni" in pm_args["text"]

    # Deliver custom dying words
    custom_msg = "Meni nohaq osdingiz, shahar baribir yutadi!"
    res = await deliver_last_words(mock_context, game, 10, custom_msg)
    assert res is True
    assert 10 not in game["waiting_last_words"]

    # Check broadcast to group
    broadcast_call = mock_context.bot.send_message.call_args[1]
    assert broadcast_call["chat_id"] == -10077
    assert "O'limidan oldingi so'nggi gapi" in broadcast_call["text"]
    assert "Akmal" in broadcast_call["text"]
    assert "Fuqaro" in broadcast_call["text"]
    assert custom_msg in broadcast_call["text"]

@pytest.mark.asyncio
async def test_afk_sleepers_and_shout(mock_context, monkeypatch):
    # Mock change_balance to avoid DB call in unit test
    mock_change_balance = AsyncMock(return_value=True)
    monkeypatch.setattr("core.afk_penalty.change_balance", mock_change_balance)

    game = {
        "chat": -10099,
        "players": [1, 2, 3],
        "names": {1: "Olim", 2: "Sardor", 3: "Jasur"},
        "roles": {1: "Fuqaro", 2: "Detektiv", 3: "Boshliq"},
        "alive": {1: True, 2: True, 3: True},
        "night": 1,
        "votes": {1: "2"}, # 2 and 3 did NOT vote!
    }

    # Voting phase does NOT penalize or kick just for not voting!
    await handle_voting_sleepers(mock_context, game)
    assert mock_context.bot.send_message.call_count == 0
    assert game["alive"][2] is True
    assert game["alive"][3] is True

    # Night 1: Sardor (2) and Jasur (3) did not act, Olim (1) acted
    record_player_activity(game, 1)
    await handle_night_sleepers(mock_context, game)
    assert game["inactive_nights"][2] == 1
    assert game["inactive_nights"][3] == 1
    assert game["inactive_nights"][1] == 0
    assert mock_context.bot.send_message.call_count == 0

    # Night 2: Jasur acts, Sardor inactive again
    game["night"] = 2
    record_player_activity(game, 3)
    await handle_night_sleepers(mock_context, game)
    assert game["inactive_nights"][2] == 2
    assert game["inactive_nights"][3] == 0
    assert mock_context.bot.send_message.call_count == 0
    assert game["alive"][2] is True

    # Night 3: Sardor inactive for 3rd consecutive night -> penalized and kicked!
    game["night"] = 3
    await handle_night_sleepers(mock_context, game)
    assert mock_context.bot.send_message.call_count == 1
    call_text = mock_context.bot.send_message.call_args[1]["text"]
    assert "UXLASHGA JAZO" in call_text
    assert "MEN QAYTIB O'YIN PAYTIDA UHLAMAYMAN!" in call_text
    assert "Sardor" in call_text
    assert game["alive"][2] is False # Kicked from game!
    assert game["alive"][3] is True # Jasur still alive

@pytest.mark.asyncio
async def test_endgame_sleepers(mock_context):
    game = {
        "chat": -10088,
        "players": [100, 200],
        "names": {100: "Faol", 200: "Uyquchi"},
        "player_actions": {100: 5}, # 200 has 0 actions
    }

    await check_endgame_sleepers(mock_context, game)
    assert mock_context.bot.send_message.call_count == 1
    call_text = mock_context.bot.send_message.call_args[1]["text"]
    assert "Uyquchi" in call_text
    assert "MEN QAYTIB O'YIN PAYTIDA UHLAMAYMAN!" in call_text

@pytest.mark.asyncio
async def test_daytime_chat_prevents_afk(mock_context):
    from bot import track_group_user
    from core.engine import games

    chat_id = -1006677
    game = {
        "chat": chat_id,
        "phase": "day",
        "players": [555],
        "alive": {555: True},
        "inactive_nights": {555: 2},
        "round_acted": set(),
    }
    games[chat_id] = game

    mock_update = MagicMock()
    mock_update.effective_chat.type = "supergroup"
    mock_update.effective_chat.id = chat_id
    mock_update.effective_user.id = 555
    mock_update.effective_user.is_bot = False
    mock_update.effective_user.full_name = "Faol Suhbatdosh"
    mock_update.effective_user.first_name = "Faol"
    mock_update.effective_user.username = "faol555"

    await track_group_user(mock_update, mock_context)
    # Verifying that chatting during day phase reset inactive_nights to 0 and added to round_acted
    assert game["inactive_nights"][555] == 0
    assert 555 in game["round_acted"]
    games.pop(chat_id, None)

