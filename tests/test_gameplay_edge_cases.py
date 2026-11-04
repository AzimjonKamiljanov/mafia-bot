import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update
from telegram.ext import ContextTypes

from database.db import init_db
from database.models import ensure_user
from core.engine import games, lobbies, check_winner, finish_game
from phases.voting import finish_voting
from phases.night import complete_night_resolution, start_night
from handlers.commands import chiqish_cmd
from handlers.callbacks import callback_router

class MockUser:
    def __init__(self, uid: int, name: str, username: str = ""):
        self.id = uid
        self.first_name = name
        self.full_name = name
        self.username = username

@pytest.fixture(autouse=True)
def clean_state():
    games.clear()
    lobbies.clear()
    yield
    games.clear()
    lobbies.clear()

@pytest.mark.asyncio
async def test_dead_detective_does_not_receive_investigation():
    """If detective dies tonight, they must not receive investigation result."""
    await init_db()
    det_id = 1001
    target_id = 1002
    chat_id = -100123

    game = {
        "chat": chat_id,
        "players": [det_id, target_id],
        "alive": {det_id: True, target_id: True},
        "roles": {det_id: "Detektiv", target_id: "Qotil"},
        "detective_results": {str(det_id): {"target": target_id}},
        "phase": "night",
        "night": 1,
    }
    games[chat_id] = game

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    # Detective is in deaths set (killed by mafia tonight)
    deaths = {det_id}
    death_causes = {det_id: ["Mafiya buyrug'i"]}
    crime_clues = {}
    saved_by_doc = set()

    await complete_night_resolution(mock_context, game, deaths, death_causes, crime_clues, saved_by_doc)

    # Confirm detective is marked dead
    assert game["alive"][det_id] is False

    # Detective must NOT receive any message with "DETEKTIV TEKSHIRUV NATIJASI"
    det_messages = [
        call.kwargs.get("text", "")
        for call in mock_context.bot.send_message.call_args_list
        if call.kwargs.get("chat_id") == det_id
    ]
    assert not any("DETEKTIV TEKSHIRUV NATIJASI" in m for m in det_messages)

@pytest.mark.asyncio
async def test_voting_tie_and_skip_vote():
    """Voting ties and 'none' winning must transition directly to night."""
    chat_id = -100456
    p1, p2, p3 = 2001, 2002, 2003
    game = {
        "chat": chat_id,
        "players": [p1, p2, p3],
        "alive": {p1: True, p2: True, p3: True},
        "roles": {p1: "Fuqaro", p2: "Fuqaro", p3: "Qotil"},
        "votes": {p1: p2, p2: p1},
        "phase": "voting",
        "night": 1,
    }
    games[chat_id] = game

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    # Tie: p1 has 1 vote, p2 has 1 vote
    await finish_voting(mock_context, game)

    # Should announce tie and transition to night
    assert game["phase"] == "night"
    assert any("Ovozlar teng keldi" in call.kwargs.get("text", "") for call in mock_context.bot.send_message.call_args_list)

@pytest.mark.asyncio
async def test_voting_none_skips_trial():
    """When 'none' votes >= top suspect votes, no one goes to trial."""
    chat_id = -100457
    p1, p2, p3 = 3001, 3002, 3003
    game = {
        "chat": chat_id,
        "players": [p1, p2, p3],
        "alive": {p1: True, p2: True, p3: True},
        "roles": {p1: "Fuqaro", p2: "Fuqaro", p3: "Qotil"},
        "votes": {p1: "none", p2: "none", p3: p1},
        "phase": "voting",
        "night": 1,
    }
    games[chat_id] = game

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await finish_voting(mock_context, game)
    assert game["phase"] == "night"
    assert any("hech kimni sud minbariga chiqarmaslikni" in call.kwargs.get("text", "") for call in mock_context.bot.send_message.call_args_list)

@pytest.mark.asyncio
async def test_mid_game_chiqish_cmd():
    """Leaving an active game via /chiqish marks player dead and checks winner."""
    chat_id = -100789
    p1, p2 = 4001, 4002
    u1 = MockUser(p1, "PlayerOne")
    await ensure_user(u1)

    game = {
        "chat": chat_id,
        "players": [p1, p2],
        "alive": {p1: True, p2: True},
        "roles": {p1: "Qotil", p2: "Fuqaro"},
        "phase": "day",
        "night": 1,
    }
    games[chat_id] = game

    mock_update = MagicMock()
    mock_update.effective_chat.id = chat_id
    mock_update.effective_chat.type = "supergroup"
    mock_update.effective_user = u1
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await chiqish_cmd(mock_update, mock_context)

    # p1 is dead
    assert game["alive"][p1] is False
    # With p1 (only killer) leaving, Town (p2) wins and game finishes
    assert game["phase"] == "finished"

@pytest.mark.asyncio
async def test_win_condition_town_vs_non_killing_neutrals():
    """1 Blue + 1 non-killing neutral (Joker, Firibgar, Pul o'g'risi) -> Town wins."""
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    # Case 1: Town vs Joker
    game_joker = {
        "chat": -101,
        "players": [5001, 5002],
        "alive": {5001: True, 5002: True},
        "roles": {5001: "Fuqaro", 5002: "Joker"},
    }
    assert await check_winner(mock_context, game_joker) is True

    # Case 2: Town vs Firibgar
    game_firibgar = {
        "chat": -102,
        "players": [5003, 5004],
        "alive": {5003: True, 5004: True},
        "roles": {5003: "Detektiv", 5004: "Firibgar"},
    }
    assert await check_winner(mock_context, game_firibgar) is True

    # Case 3: Town vs Pul o'g'risi
    game_thief = {
        "chat": -103,
        "players": [5005, 5006],
        "alive": {5005: True, 5006: True},
        "roles": {5005: "Doktor", 5006: "Pul o'g'risi"},
    }
    assert await check_winner(mock_context, game_thief) is True

    # Case 4: Town vs Maniak (Killing solo -> game MUST continue)
    game_maniak = {
        "chat": -104,
        "players": [5007, 5008],
        "alive": {5007: True, 5008: True},
        "roles": {5007: "Fuqaro", 5008: "Maniak"},
    }
    assert await check_winner(mock_context, game_maniak) is False

@pytest.mark.asyncio
async def test_cross_chat_game_state_leak_prevention():
    """Player alive in an active game cannot join a lobby in another chat."""
    active_chat = -100881
    other_chat = -100882
    player_uid = 6001

    games[active_chat] = {
        "chat": active_chat,
        "players": [player_uid, 6002],
        "alive": {player_uid: True, 6002: True},
        "roles": {player_uid: "Fuqaro", 6002: "Qotil"},
        "phase": "night",
    }

    lobbies[other_chat] = {
        "chat_id": other_chat,
        "open": True,
        "players": [7001],
        "names": {7001: "LobbyLeader"},
        "badges": {},
    }

    cb_update = MagicMock()
    cb_update.callback_query.data = f"lobby_join:{other_chat}"
    cb_update.callback_query.from_user = MockUser(player_uid, "BusyPlayer")
    cb_update.callback_query.answer = AsyncMock()

    mock_context = MagicMock()
    await callback_router(cb_update, mock_context)

    # Must be blocked with alert
    assert "boshqa guruhdagi faol o'yinda tiriksiz" in cb_update.callback_query.answer.call_args[0][0]
    assert player_uid not in lobbies[other_chat]["players"]
