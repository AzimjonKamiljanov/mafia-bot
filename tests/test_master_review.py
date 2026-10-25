import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from config import MIN_PLAYERS, MAX_PLAYERS, ROLES, DEFAULT_NIGHT_SECONDS
from database.db import init_db, get_db
from database.models import (
    is_admin, get_chat_settings, update_chat_settings,
    get_bot_config, set_bot_config, get_user, change_balance
)
from roles.allocator import choose_roles
from phases.lobby import create_lobby, start_game
from phases.night import get_role_action_buttons, resolve_night
from phases.verdict import resolve_verdict
from core.afk_penalty import handle_voting_sleepers, handle_night_sleepers, check_endgame_sleepers, record_player_activity
from core.engine import games, lobbies, cancel_game_timer
from handlers.admin_ai import process_admin_ai_message, resolve_role_name

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.pin_chat_message = AsyncMock()
    ctx.bot.unpin_chat_message = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_sheriff_boundary_and_uniqueness():
    """Verify Sherif strictly never appears below 7, never duplicates, and has Detektiv."""
    for n in range(MIN_PLAYERS, MAX_PLAYERS + 1):
        for _ in range(50):
            roles = choose_roles(n)
            sc = roles.count("Sherif")
            assert sc <= 1, f"Sheriff duplicated ({sc} times) for n={n}"
            if n < 7:
                assert sc == 0, f"Sheriff appeared for n={n} < 7"
            if sc == 1:
                assert "Detektiv" in roles, f"Sheriff without Detective in n={n}"

@pytest.mark.asyncio
async def test_disabled_detective_prevents_sheriff():
    """If Detective is disabled, Sheriff must not appear either, even for n >= 7."""
    for _ in range(50):
        roles = choose_roles(12, disabled={"Detektiv"})
        assert "Detektiv" not in roles
        assert "Sherif" not in roles

@pytest.mark.asyncio
async def test_custom_game_settings_transfer(mock_context):
    """Verify that settings customized in lobby are properly transferred to game."""
    await init_db()
    chat_id = -100445566
    lobbies.pop(chat_id, None)
    games.pop(chat_id, None)

    # Setup chat settings with custom timers
    await update_chat_settings(chat_id, night_seconds=30, day_seconds=60, vote_seconds=30, verdict_seconds=20)
    st = await get_chat_settings(chat_id)
    assert st["night_seconds"] == 30

    mock_update = MagicMock()
    mock_update.effective_chat.type = "supergroup"
    mock_update.effective_chat.id = chat_id
    mock_update.effective_user.id = 1001
    mock_update.effective_user.full_name = "Host"
    mock_update.effective_user.first_name = "Host"
    mock_update.effective_user.username = "host1"

    mock_msg = MagicMock()
    mock_msg.message_id = 888
    mock_context.bot.send_message.return_value = mock_msg

    await create_lobby(mock_update, mock_context)
    lobby = lobbies[chat_id]
    assert lobby["settings"]["night_seconds"] == 30

    # Add 4 players to meet minimum
    for uid in (1002, 1003, 1004):
        lobby["players"].append(uid)
        lobby["names"][uid] = f"Player {uid}"

    await start_game(mock_context, chat_id)
    assert chat_id in games
    game = games[chat_id]
    # Check that game received custom settings!
    assert "settings" in game
    assert game["settings"]["night_seconds"] == 30
    assert game["settings"]["day_seconds"] == 60
    assert game["settings"]["vote_seconds"] == 30
    assert game["settings"]["verdict_seconds"] == 20

    lobbies.pop(chat_id, None)
    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_sheriff_daytime_verdict_promotion(mock_context):
    """When Detective is executed in daytime verdict, Sheriff is immediately promoted."""
    chat_id = -1001122
    game = {
        "chat": chat_id,
        "phase": "verdict",
        "accused_uid": 10, # Detective on the stand
        "players": [10, 20, 30],
        "names": {10: "Detektiv Ali", 20: "Sherif Vali", 30: "Don Sami"},
        "roles": {10: "Detektiv", 20: "Sherif", 30: "Boshliq"},
        "alive": {10: True, 20: True, 30: True},
        "verdict_votes": {20: "kill", 30: "kill"},
        "sheriff_promoted": set(),
    }

    await resolve_verdict(mock_context, game)
    assert game["alive"][10] is False # Detective executed
    assert 20 in game["sheriff_promoted"] # Sheriff promoted!
    assert mock_context.bot.send_message.call_count >= 1

    # Now verify Sheriff's action buttons in night
    kb = get_role_action_buttons(game, 20)
    btn_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "🔎 Shaxsni tekshirish" in btn_texts
    assert "🔫 Shubhali shaxsni otish" in btn_texts

@pytest.mark.asyncio
async def test_afk_3_nights_rule_with_resets(mock_context, monkeypatch):
    """Test 3-night AFK rule: actions reset count, skipping vote does not kick, 3 inactive nights kicks."""
    mock_change_balance = AsyncMock(return_value=True)
    monkeypatch.setattr("core.afk_penalty.change_balance", mock_change_balance)

    chat_id = -1009988
    game = {
        "chat": chat_id,
        "players": [1, 2],
        "names": {1: "Faol", 2: "Dangasa"},
        "roles": {1: "Fuqaro", 2: "Fuqaro"},
        "alive": {1: True, 2: True},
        "night": 1,
        "votes": {},
    }

    # Day 1: Voting passes with no votes -> handle_voting_sleepers does not kick
    await handle_voting_sleepers(mock_context, game)
    assert game["alive"][2] is True

    # Night 1: Dangasa inactive -> night count is 0 for Fuqaro on night 1 (no daytime preceded)
    await handle_night_sleepers(mock_context, game)
    assert game.get("inactive_nights", {}).get(2, 0) == 0

    # Night 2: Dangasa inactive -> count becomes 1
    game["night"] = 2
    await handle_night_sleepers(mock_context, game)
    assert game["inactive_nights"][2] == 1
    assert game["alive"][2] is True

    # Dangasa talks in group during day 2 -> activity recorded for this round!
    record_player_activity(game, 2)
    assert game["inactive_nights"][2] == 0

    # Night 3: Covered by day 2 activity (round_acted) -> count stays 0, round_acted reset for next cycle
    record_player_activity(game, 1)
    game["night"] = 3
    await handle_night_sleepers(mock_context, game)
    assert game["inactive_nights"][2] == 0
    assert game["alive"][2] is True

    # Night 4: Inactive -> count becomes 1
    record_player_activity(game, 1)
    game["night"] = 4
    await handle_night_sleepers(mock_context, game)
    assert game["inactive_nights"][2] == 1
    assert game["alive"][2] is True

    # Night 5: Inactive -> count becomes 2
    record_player_activity(game, 1)
    game["night"] = 5
    await handle_night_sleepers(mock_context, game)
    assert game["inactive_nights"][2] == 2
    assert game["alive"][2] is True

    # Night 6: Inactive for 3rd consecutive night -> penalized and kicked!
    record_player_activity(game, 1)
    game["night"] = 6
    await handle_night_sleepers(mock_context, game)
    assert game["alive"][2] is False # Kicked!
    assert game["alive"][1] is True # Player 1 is active and alive!
    assert mock_context.bot.send_message.call_count == 1
    call_text = mock_context.bot.send_message.call_args[1]["text"]
    assert "UXLASHGA JAZO" in call_text
    assert "MEN QAYTIB O'YIN PAYTIDA UHLAMAYMAN!" in call_text

@pytest.mark.asyncio
async def test_admin_ai_comprehensive_commands():
    """Verify Master Admin AI interface processes natural language commands for 7651553630."""
    await init_db()
    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = 7651553630
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.effective_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    # Timer test
    mock_update.effective_message.text = "ovozni 30 qil"
    mock_update.effective_message.reply_text.reset_mock()
    h = await process_admin_ai_message(mock_update, mock_context)
    assert h is True
    assert "30 soniya" in mock_update.effective_message.reply_text.call_args[0][0]

    # Role test (Sherifni ochir)
    mock_update.effective_message.text = "sherifni ochir"
    mock_update.effective_message.reply_text.reset_mock()
    h = await process_admin_ai_message(mock_update, mock_context)
    assert h is True
    rep = mock_update.effective_message.reply_text.call_args[0][0]
    assert "Sherif" in rep
    assert "O'CHIRILDI" in rep

    # Item grant test
    mock_update.effective_message.text = "7651553630 ga 3 ta himoya ber"
    mock_update.effective_message.reply_text.reset_mock()
    h = await process_admin_ai_message(mock_update, mock_context)
    assert h is True
    assert "Himoya" in mock_update.effective_message.reply_text.call_args[0][0]

    # Diagnostics test
    mock_update.effective_message.text = "statistika"
    mock_update.effective_message.reply_text.reset_mock()
    h = await process_admin_ai_message(mock_update, mock_context)
    assert h is True
    assert "DIAGNOSTIKA" in mock_update.effective_message.reply_text.call_args[0][0]
