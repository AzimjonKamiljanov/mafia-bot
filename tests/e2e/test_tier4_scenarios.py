"""Tier 4: Real-World Scenarios E2E Tests.

Opaque-box tests verifying complete, multi-turn game simulations from lobby registration,
night actions, morning reports, day debates, voting rounds, verdict executions, through to
endgame win conditions and database reward persistence.
"""

import time
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from database.db import init_db, get_db
from database.models import (
    ensure_user, get_user, change_balance, get_badge, is_admin
)
from core.engine import (
    games, lobbies, cancel_game_timer, cancel_lobby_timer, abort_game, finish_game,
    check_winner
)
from phases.lobby import create_lobby, start_game
from phases.night import start_night, resolve_night
from phases.day import day_phase
from phases.voting import start_voting, finish_voting
from phases.verdict import verdict_phase, resolve_verdict
from handlers.commands import stop_cmd
from handlers.callbacks import callback_router

from tests.e2e import (
    MockUser, MockChat, make_pm_update, make_group_message_update,
    make_callback_update, make_e2e_context, reset_runtime_state
)


@pytest_asyncio.fixture(autouse=True)
async def setup_e2e_env():
    await init_db()
    reset_runtime_state()
    yield
    reset_runtime_state()


# Scenario 1: Complete 5-Player Town (Civilian) Victory
@pytest.mark.asyncio
async def test_scenario_01_complete_town_victory():
    """Full Simulation: 5 Players -> Lobby -> Night 1 (Doc save) -> Day 1 -> Vote -> Verdict -> Town Wins."""
    chat_id = -100401

    # 1. Initialize 5 player accounts
    p_det = MockUser(904001, "Detective Holmes", username="holmes")
    p_doc = MockUser(904002, "Dr Watson", username="watson")
    p_cit1 = MockUser(904003, "Citizen Arthur", username="arthur")
    p_cit2 = MockUser(904004, "Citizen Mary", username="mary")
    p_boss = MockUser(904005, "Don Corleone", username="corleone")
    all_players = [p_det, p_doc, p_cit1, p_cit2, p_boss]

    for p in all_players:
        await ensure_user(p)
        u = await get_user(p.id)
        await change_balance(p.id, "coin", 100 - u["coin"]) # Reset to 100 coins

    ctx = make_e2e_context()

    # Step 1: Open Lobby
    up_lobby = make_group_message_update(chat_id=chat_id, user=p_det, text="/game")
    await create_lobby(up_lobby, ctx)
    assert chat_id in lobbies
    assert p_det.id in lobbies[chat_id]["players"]

    # Step 2: Other 4 players join lobby
    for p in (p_doc, p_cit1, p_cit2, p_boss):
        up_join = make_callback_update(chat_id, p, f"lobby_join:{chat_id}")
        await callback_router(up_join, ctx)

    assert len(lobbies[chat_id]["players"]) == 5

    # Step 3: Setup explicit game with known role assignments
    lobbies.pop(chat_id, None)
    game = {
        "chat": chat_id,
        "players": [p.id for p in all_players],
        "names": {p.id: p.full_name for p in all_players},
        "badges": {},
        "premium": {},
        "settings": {"day_seconds": 10, "vote_seconds": 10, "verdict_seconds": 10},
        "created_at": time.time(),
        "roles": {
            p_det.id: "Detektiv",
            p_doc.id: "Doktor",
            p_cit1.id: "Fuqaro",
            p_cit2.id: "Fuqaro",
            p_boss.id: "Boshliq",
        },
        "alive": {p.id: True for p in all_players},
        "phase": "night",
        "night": 1,
        "partners": {},
        "inactive": {p.id: 0 for p in all_players},
        "night_done": set(),
        "kill_targets": {},
        "protected": set(),
        "protected_by": {},
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "votes": {},
        "_finish_started": False,
        "_waiting_king": False,
        "_resolving_night": False,
        "_db_id": None,
    }
    games[chat_id] = game

    # Step 4: Night 1 Actions
    # - Boss targets Citizen 1 (p_cit1)
    game["kill_targets"][p_boss.id] = p_cit1.id
    # - Doctor protects Citizen 1 (p_cit1)
    game["protected"].add(p_cit1.id)
    game["protected_by"][p_cit1.id] = p_doc.id
    # - Detective investigates Boss (p_boss)
    game["detective_results"][p_det.id] = {"target": p_boss.id}

    # Resolve Night 1
    await resolve_night(ctx, game)

    # Doctor successfully saves Citizen 1!
    assert game["alive"][p_cit1.id] is True
    assert p_cit1.id in game.get("last_night_saved", [])
    assert len(game.get("last_night_deaths", [])) == 0

    # Step 5: Day 1 Phase
    await day_phase(ctx, game)
    assert game["phase"] == "day"

    # Step 6: Voting Phase
    await start_voting(ctx, game)
    assert game["phase"] == "voting"

    # Citizens unite and vote for Boss (p_boss)
    game["votes"] = {
        p_det.id: p_boss.id,
        p_doc.id: p_boss.id,
        p_cit1.id: p_boss.id,
        p_cit2.id: p_boss.id,
        p_boss.id: p_cit1.id, # Boss futilely votes for Cit1
    }

    # Resolve Voting
    await finish_voting(ctx, game)

    # Boss is put on verdict stand!
    assert game["phase"] == "verdict"
    assert game.get("accused_uid") == p_boss.id

    # Step 7: Verdict Phase
    # Citizens vote QATL (kill), Boss votes AFV (forgive)
    game["verdict_votes"] = {
        p_det.id: "kill",
        p_doc.id: "kill",
        p_cit1.id: "kill",
        p_cit2.id: "kill",
        p_boss.id: "forgive",
    }

    # Resolve Verdict
    await resolve_verdict(ctx, game)

    # Boss is executed!
    assert game["alive"][p_boss.id] is False

    # Step 8: Endgame Check & Finish
    is_ended = await check_winner(ctx, game)
    assert is_ended is True

    # Validate economic payouts: Citizens won (+150 coins), Boss lost (+25 coins)
    for p in (p_det, p_doc, p_cit1, p_cit2):
        u = await get_user(p.id)
        assert u["coin"] == 250, f"Winning citizen {p.full_name} has incorrect coins: {u['coin']}"

    boss_user = await get_user(p_boss.id)
    assert boss_user["coin"] == 125, f"Losing boss has incorrect coins: {boss_user['coin']}"


# Scenario 2: Complete 5-Player Mafia Victory
@pytest.mark.asyncio
async def test_scenario_02_complete_mafia_victory():
    """Full Simulation: 2 Mafia + 3 Citizens -> Mafia eliminates citizens to reach parity."""
    chat_id = -100402

    p_boss = MockUser(904010, "Mafia Boss", username="boss")
    p_killer = MockUser(904011, "Mafia Killer", username="killer")
    p_cit1 = MockUser(904012, "Citizen One", username="cit1")
    p_cit2 = MockUser(904013, "Citizen Two", username="cit2")
    p_cit3 = MockUser(904014, "Citizen Three", username="cit3")
    p_cit4 = MockUser(904015, "Citizen Four", username="cit4")
    all_players = [p_boss, p_killer, p_cit1, p_cit2, p_cit3, p_cit4]

    for p in all_players:
        await ensure_user(p)
        u = await get_user(p.id)
        await change_balance(p.id, "coin", 100 - u["coin"])

    ctx = make_e2e_context()

    game = {
        "chat": chat_id,
        "players": [p.id for p in all_players],
        "names": {p.id: p.full_name for p in all_players},
        "badges": {},
        "premium": {},
        "settings": {},
        "created_at": time.time(),
        "roles": {
            p_boss.id: "Boshliq",
            p_killer.id: "Qotil",
            p_cit1.id: "Fuqaro",
            p_cit2.id: "Fuqaro",
            p_cit3.id: "Fuqaro",
            p_cit4.id: "Fuqaro",
        },
        "alive": {p.id: True for p in all_players},
        "phase": "night",
        "night": 1,
        "partners": {p_boss.id: p_killer.id, p_killer.id: p_boss.id},
        "kill_targets": {},
        "protected": set(),
        "protected_by": {},
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "votes": {},
        "_finish_started": False,
        "_resolving_night": False,
    }
    games[chat_id] = game

    # Night 1: Boss kills Citizen 1
    game["kill_targets"][p_boss.id] = p_cit1.id
    await resolve_night(ctx, game)

    # Citizen 1 is dead. Remaining: 2 Mafia vs 3 Citizens (Game continues)
    assert game["alive"][p_cit1.id] is False
    assert not game.get("_finish_started")

    # Day 1 & Voting 1: Split votes, resulting in tie
    game["phase"] = "voting"
    game["votes"] = {
        p_boss.id: p_cit2.id,
        p_killer.id: p_cit2.id,
        p_cit2.id: p_boss.id,
        p_cit3.id: p_boss.id,
        p_cit4.id: p_cit3.id,
    }
    # Voting ties (2 vs 2), returns to night without execution
    await finish_voting(ctx, game)

    # Night 2: Killer attacks Citizen 2
    game["phase"] = "night"
    game["night"] = 2
    game["kill_targets"] = {p_killer.id: p_cit2.id}
    await resolve_night(ctx, game)

    # Citizen 2 is dead
    assert game["alive"][p_cit2.id] is False

    # Check Win Condition:
    # Alive: 2 Mafia (Boss, Killer) vs 2 Citizens (Cit 3, Cit 4)
    # Mafia parity reached (2 >= 2) -> Mafia Victory!
    ended = await check_winner(ctx, game)
    assert ended is True

    # Payout check: Mafia winners get +150 coins
    for p in (p_boss, p_killer):
        u = await get_user(p.id)
        assert u["coin"] == 250


# Scenario 3: Mid-Game Admin Abort and Clean Recovery
@pytest.mark.asyncio
async def test_scenario_03_mid_game_admin_abort_and_recovery():
    """Verify mid-game /stop cleanly aborts active game, cancels timers, and clears state."""
    chat_id = -100403
    p1 = MockUser(904020, "Player 1")
    p2 = MockUser(904021, "Player 2")
    p3 = MockUser(904022, "Player 3")
    p4 = MockUser(904023, "Player 4")
    admin_user = MockUser(8048940366, "Master Admin") # Known admin ID

    ctx = make_e2e_context()
    timer = asyncio.create_task(asyncio.sleep(100))

    game = {
        "chat": chat_id,
        "players": [p1.id, p2.id, p3.id, p4.id],
        "names": {p1.id: "P1", p2.id: "P2", p3.id: "P3", p4.id: "P4"},
        "roles": {p1.id: "Detektiv", p2.id: "Doktor", p3.id: "Fuqaro", p4.id: "Boshliq"},
        "alive": {p1.id: True, p2.id: True, p3.id: True, p4.id: True},
        "phase": "night",
        "night": 1,
        "_timer_task": timer,
    }
    games[chat_id] = game

    # Admin issues /stop
    up_stop = make_group_message_update(chat_id=chat_id, user=admin_user, text="/stop")
    await stop_cmd(up_stop, ctx)

    # Game must be removed from runtime
    assert chat_id not in games
    await asyncio.sleep(0)
    assert timer.cancelled() or (hasattr(timer, "cancelling") and timer.cancelling() > 0)


# Scenario 4: Tie Voting and Peaceful Night Transition
@pytest.mark.asyncio
async def test_scenario_04_tie_voting_and_peaceful_transition():
    """Verify tie votes during voting do not execute anyone and transition cleanly to night."""
    chat_id = -100404
    p1, p2, p3, p4 = 904031, 904032, 904033, 904034

    game = {
        "chat": chat_id,
        "players": [p1, p2, p3, p4],
        "names": {p1: "P1", p2: "P2", p3: "P3", p4: "P4"},
        "roles": {p1: "Fuqaro", p2: "Fuqaro", p3: "Fuqaro", p4: "Fuqaro"},
        "alive": {p1: True, p2: True, p3: True, p4: True},
        "phase": "voting",
        "night": 1,
        "votes": {
            p1: p3, # 1 vote for p3
            p2: p3, # 1 vote for p3 (total 2)
            p3: p4, # 1 vote for p4
            p4: p4, # 1 vote for p4 (total 2)
        },
        "_finish_started": False,
        "_resolving_voting": False,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    await finish_voting(ctx, game)

    # Because votes were tied (2 vs 2), no suspect was put on verdict stand
    assert game.get("phase") != "verdict"
    assert game.get("accused_uid") is None
    # All players remain alive
    assert all(game["alive"].values())
