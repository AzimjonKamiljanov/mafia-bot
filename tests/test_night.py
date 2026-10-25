import pytest
from unittest.mock import AsyncMock, MagicMock
from phases.night import resolve_night
from core.engine import games

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.send_photo = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_doctor_protects_victim(mock_context):
    game = {
        "chat": -1001,
        "players": [1, 2, 3, 4],
        "names": {1: "Doc", 2: "Boss", 3: "Victim", 4: "Citizen"},
        "roles": {1: "Doktor", 2: "Boshliq", 3: "Fuqaro", 4: "Fuqaro"},
        "alive": {1: True, 2: True, 3: True, 4: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {2: 3},
        "protected": {3},
        "protected_by": {3: 1},
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-1001] = game

    await resolve_night(mock_context, game)

    assert game["alive"][3] is True, "Victim should have been saved by Doctor"
    assert 3 in game.get("last_night_saved", []), "Victim should be recorded in last_night_saved"

@pytest.mark.asyncio
async def test_bodyguard_duel_sacrifice(mock_context):
    game = {
        "chat": -1002,
        "players": [10, 11, 12, 13],
        "names": {10: "Bodyguard", 11: "Killer", 12: "Mayor", 13: "Citizen"},
        "roles": {10: "Tansoqchi", 11: "Boshliq", 12: "Mer", 13: "Fuqaro"},
        "alive": {10: True, 11: True, 12: True, 13: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {11: 12},
        "guarded_by": {12: 10},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-1002] = game

    await resolve_night(mock_context, game)

    # Target 12 survives, Bodyguard 10 and Attacker 11 both die!
    assert game["alive"][12] is True, "Protected target should survive"
    assert game["alive"][10] is False, "Bodyguard should die sacrificing themselves"
    assert game["alive"][11] is False, "Attacker should die in duel with Bodyguard"

@pytest.mark.asyncio
async def test_tourist_witnesses_murder(mock_context):
    game = {
        "chat": -1003,
        "players": [20, 21, 22, 23],
        "names": {20: "Tourist", 21: "Boss", 22: "Victim", 23: "Doc"},
        "roles": {20: "Sayyoh", 21: "Boshliq", 22: "Fuqaro", 23: "Doktor"},
        "alive": {20: True, 21: True, 22: True, 23: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {21: 22},
        "tourist_targets": {20: 22},
        "protected": set(),
        "blocked_roles": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-1003] = game

    sent_pm = []
    async def mock_pm(chat_id, text, **kwargs):
        sent_pm.append((chat_id, text))
    mock_context.bot.send_message = AsyncMock(side_effect=mock_pm)

    await resolve_night(mock_context, game)

    tourist_msgs = [txt for cid, txt in sent_pm if cid == 20]
    assert any("SAYYOH TASHRIFI GUVOXLIGI" in m for m in tourist_msgs), "Tourist did not receive witness message"

@pytest.mark.asyncio
async def test_king_attack_intercepts_deadlock(mock_context):
    game = {
        "chat": -1004,
        "players": [30, 31, 32, 33],
        "names": {30: "King", 31: "Killer", 32: "Citizen", 33: "Doctor"},
        "roles": {30: "Qirol", 31: "Boshliq", 32: "Fuqaro", 33: "Doktor"},
        "alive": {30: True, 31: True, 32: True, 33: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {31: 30},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-1004] = game

    await resolve_night(mock_context, game)

    assert game["_waiting_king"] is True, "King attack should set _waiting_king to True"
    assert game["_resolving_night"] is False, "Night resolving flag should reset to False"
