"""Tier 3: Cross-Feature Combinations E2E Tests.

Opaque-box tests verifying pairwise interactions, phase transitions, role collisions,
and economy-to-gameplay state integrations derived from ORIGINAL_REQUEST.md and PROJECT.md.
"""

import time
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from database.db import init_db, get_db
from database.models import (
    ensure_user, get_user, change_balance, add_item, take_item, get_inventory,
    create_clan, get_user_clan, record_afterlife_bet, resolve_afterlife_bets
)
from core.engine import (
    games, lobbies, cancel_game_timer, cancel_lobby_timer, abort_game, abort_lobby,
    finish_game
)
from core.afk_penalty import handle_voting_sleepers, record_player_activity
from phases.lobby import create_lobby, start_game
from phases.night import resolve_night
from phases.voting import start_voting, finish_voting
from phases.verdict import verdict_phase, resolve_verdict
from handlers.commands import stop_cmd, reveal_cmd
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


# 1. Lobby Join + Admin Stop
@pytest.mark.asyncio
async def test_comb_lobby_join_and_admin_stop():
    """Verify lobby join flow followed by admin stop aborts lobby and cancels timers."""
    chat_id = -100301
    creator = MockUser(903001, "Lobby Creator")
    p2 = MockUser(903002, "Player Two")
    p3 = MockUser(903003, "Player Three")
    for u in (creator, p2, p3):
        await ensure_user(u)

    ctx = make_e2e_context()
    # Mock admin status in group for creator
    creator_member = MagicMock()
    creator_member.status = "administrator"
    ctx.bot.get_chat_member.return_value = creator_member

    # 1. Create lobby
    up_create = make_group_message_update(chat_id=chat_id, user=creator, text="/game")
    await create_lobby(up_create, ctx)
    assert chat_id in lobbies

    # 2. Players join
    for u in (p2, p3):
        up_join = make_callback_update(chat_id, u, f"lobby_join:{chat_id}")
        await callback_router(up_join, ctx)

    assert len(lobbies[chat_id]["players"]) == 3

    # 3. Creator issues /stop
    up_stop = make_group_message_update(chat_id=chat_id, user=creator, text="/stop")
    await stop_cmd(up_stop, ctx)

    # Lobby must be cancelled and removed
    assert chat_id not in lobbies


# 2. Night Attack + Doctor Heal (Victim Survives)
@pytest.mark.asyncio
async def test_comb_night_attack_and_doctor_heal():
    """Verify Doctor healing negates Mafia Boss kill target during resolve_night."""
    chat_id = -100302
    boss = 903010
    doctor = 903011
    victim = 903012
    citizen = 903013

    game = {
        "chat": chat_id,
        "players": [boss, doctor, victim, citizen],
        "names": {boss: "Boss", doctor: "Doctor", victim: "Victim", citizen: "Citizen"},
        "roles": {boss: "Boshliq", doctor: "Doktor", victim: "Fuqaro", citizen: "Fuqaro"},
        "alive": {boss: True, doctor: True, victim: True, citizen: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {boss: victim},
        "protected": {victim},
        "protected_by": {victim: doctor},
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    await resolve_night(ctx, game)

    assert game["alive"][victim] is True, "Doctor failed to save victim!"
    assert victim in game.get("last_night_saved", [])
    assert victim not in game.get("last_night_deaths", [])


# 3. Night Attack + Bodyguard Duel Sacrifice
@pytest.mark.asyncio
async def test_comb_night_attack_and_bodyguard_duel():
    """Verify Bodyguard duel sacrifice saves victim while eliminating Bodyguard."""
    chat_id = -100303
    killer = 903020
    bodyguard = 903021
    mayor = 903022
    citizen = 903023

    game = {
        "chat": chat_id,
        "players": [killer, bodyguard, mayor, citizen],
        "names": {killer: "Killer", bodyguard: "Bodyguard", mayor: "Mayor", citizen: "Citizen"},
        "roles": {killer: "Qotil", bodyguard: "Tansoqchi", mayor: "Mer", citizen: "Fuqaro"},
        "alive": {killer: True, bodyguard: True, mayor: True, citizen: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {killer: mayor},
        "guarded_by": {mayor: bodyguard},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    await resolve_night(ctx, game)

    # Mayor survives, Bodyguard dies defending
    assert game["alive"][mayor] is True, "Mayor should survive behind Bodyguard"
    assert game["alive"][bodyguard] is False, "Bodyguard must die in duel sacrifice"
    assert bodyguard in game.get("last_night_deaths", [])


# 4. Detective Inspection on Killer vs Boss
@pytest.mark.asyncio
async def test_comb_detective_investigate_killer_and_boss():
    """Verify Detective finds Killer guilty (red) but Boss appears innocent (blue)."""
    chat_id = -100304
    det = 903030
    boss = 903031
    killer = 903032
    cit = 903033

    # Case A: Inspect Killer
    game_a = {
        "chat": chat_id,
        "players": [det, boss, killer, cit],
        "names": {det: "Det", boss: "Boss", killer: "Killer", cit: "Cit"},
        "roles": {det: "Detektiv", boss: "Boshliq", killer: "Qotil", cit: "Fuqaro"},
        "alive": {det: True, boss: True, killer: True, cit: True},
        "phase": "night",
        "night": 1,
        "detective_results": {det: {"target": killer}},
        "blocked_roles": {},
        "tourist_targets": {},
        "_finish_started": False,
        "_resolving_night": False,
    }
    games[chat_id] = game_a
    ctx = make_e2e_context()

    await resolve_night(ctx, game_a)

    # Detektiv received result message indicating Killer
    det_msgs = [
        (c[1].get("text") or c[0][1])
        for c in ctx.bot.send_message.call_args_list
        if c[1].get("chat_id") == det or (len(c[0]) > 0 and c[0][0] == det)
    ]
    assert any("Qotil" in m for m in det_msgs)

    # Case B: Inspect Boss
    game_b = {
        "chat": chat_id,
        "players": [det, boss, killer, cit],
        "names": {det: "Det", boss: "Boss", killer: "Killer", cit: "Cit"},
        "roles": {det: "Detektiv", boss: "Boshliq", killer: "Qotil", cit: "Fuqaro"},
        "alive": {det: True, boss: True, killer: True, cit: True},
        "phase": "night",
        "night": 1,
        "detective_results": {det: {"target": boss}},
        "blocked_roles": {},
        "tourist_targets": {},
        "_finish_started": False,
        "_resolving_night": False,
    }
    games[chat_id] = game_b
    ctx_b = make_e2e_context()
    await resolve_night(ctx_b, game_b)

    det_msgs_b = [
        (c[1].get("text") or c[0][1])
        for c in ctx_b.bot.send_message.call_args_list
        if c[1].get("chat_id") == det or (len(c[0]) > 0 and c[0][0] == det)
    ]
    # Boss role is Boshliq
    assert any("Boshliq" in m for m in det_msgs_b)


# 5. Day Transition + Mayor Reveal
@pytest.mark.asyncio
async def test_comb_day_transition_and_mayor_reveal():
    """Verify Mayor can reveal role via callback and get registered in mayor_revealed."""
    chat_id = -100305
    mayor_uid = 903040
    user = MockUser(mayor_uid, "His Honor The Mayor")
    await ensure_user(user)

    game = {
        "chat": chat_id,
        "players": [mayor_uid, 903041, 903042, 903043],
        "names": {mayor_uid: "Mayor", 903041: "C1", 903042: "C2", 903043: "C3"},
        "roles": {mayor_uid: "Mer", 903041: "Fuqaro", 903042: "Fuqaro", 903043: "Fuqaro"},
        "alive": {mayor_uid: True, 903041: True, 903042: True, 903043: True},
        "phase": "day",
        "mayor_revealed": set(),
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    up = make_callback_update(chat_id, user, f"mayor_reveal:{chat_id}")
    await callback_router(up, ctx)

    assert mayor_uid in game.get("mayor_revealed", set())
    assert ctx.bot.send_message.called


# 6. Voting Weight: Mayor (3x) + Extra Vote Item
@pytest.mark.asyncio
async def test_comb_voting_with_mayor_weight_and_extra_vote():
    """Verify revealed Mayor has 3x vote weight and extra_vote item adds +1."""
    chat_id = -100306
    mayor_uid = 903050
    citizen_uid = 903051
    suspect_uid = 903052
    other_uid = 903053

    game = {
        "chat": chat_id,
        "players": [mayor_uid, citizen_uid, suspect_uid, other_uid],
        "names": {mayor_uid: "Mayor", citizen_uid: "Citizen", suspect_uid: "Suspect", other_uid: "Other"},
        "roles": {mayor_uid: "Mer", citizen_uid: "Fuqaro", suspect_uid: "Qotil", other_uid: "Fuqaro"},
        "alive": {mayor_uid: True, citizen_uid: True, suspect_uid: True, other_uid: True},
        "phase": "voting",
        "night": 1,
        "mayor_revealed": {mayor_uid}, # 3x weight
        "extra_votes": {citizen_uid},   # 1 + 1 = 2x weight
        "votes": {
            mayor_uid: suspect_uid,     # 3 votes for suspect
            citizen_uid: suspect_uid,   # 2 votes for suspect
            suspect_uid: other_uid,     # 1 vote for other
            other_uid: suspect_uid,     # 1 vote for suspect
        },
        "_finish_started": False,
        "_resolving_voting": False,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    await finish_voting(ctx, game)

    # Suspect must be accused with top votes and transitioned to verdict
    assert game.get("phase") == "verdict"
    assert game.get("accused_uid") == suspect_uid
    # Extra votes cleared after voting
    assert len(game.get("extra_votes", set())) == 0


# 7. Verdict Phase + Lawyer Intervention
@pytest.mark.asyncio
async def test_comb_verdict_and_lawyer_intervention():
    """Verify Lawyer defense prevents execution even if QATL votes outnumber AFV."""
    chat_id = -100307
    lawyer_uid = 903060
    accused_uid = 903061
    voter_uid = 903062

    game = {
        "chat": chat_id,
        "players": [lawyer_uid, accused_uid, voter_uid],
        "names": {lawyer_uid: "Lawyer", accused_uid: "Client", voter_uid: "Executioner"},
        "roles": {lawyer_uid: "Advokat", accused_uid: "Fuqaro", voter_uid: "Fuqaro"},
        "alive": {lawyer_uid: True, accused_uid: True, voter_uid: True},
        "phase": "verdict",
        "accused_uid": accused_uid,
        "lawyer_clients": {lawyer_uid: accused_uid}, # Lawyer protected accused
        "verdict_votes": {voter_uid: "kill"},         # 1 kill vs 0 forgive
        "_finish_started": False,
        "_resolving_verdict": False,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    await resolve_verdict(ctx, game)

    # Accused must survive due to lawyer intervention
    assert game["alive"][accused_uid] is True
    assert ctx.bot.send_message.called
    all_messages = [
        (c[1].get("text") or (c[0][1] if len(c[0]) > 1 else ""))
        for c in ctx.bot.send_message.call_args_list
    ]
    assert any("ADVOKAT ARALASHUVI" in m for m in all_messages)


# 8. Verdict Phase + Ruler Shield Item Consumption
@pytest.mark.asyncio
async def test_comb_verdict_and_ruler_protection_item():
    """Verify ruler_protection item spares suspect from hanging and is consumed."""
    chat_id = -100308
    accused_uid = 903070
    voter_uid = 903071
    await ensure_user(MockUser(accused_uid, "Protected Lord"))
    await add_item(accused_uid, "ruler_protection", 1)

    game = {
        "chat": chat_id,
        "players": [accused_uid, voter_uid],
        "names": {accused_uid: "Protected Lord", voter_uid: "Judge"},
        "roles": {accused_uid: "Fuqaro", voter_uid: "Fuqaro"},
        "alive": {accused_uid: True, voter_uid: True},
        "phase": "verdict",
        "accused_uid": accused_uid,
        "verdict_votes": {voter_uid: "kill"},
        "_finish_started": False,
        "_resolving_verdict": False,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    await resolve_verdict(ctx, game)

    # Accused spared
    assert game["alive"][accused_uid] is True
    # Item consumed
    inv = await get_inventory(accused_uid)
    assert inv.get("ruler_protection", 0) == 0


# 9. Economy + Item Consumption State Integration
@pytest.mark.asyncio
async def test_comb_economy_and_item_consumption():
    """Verify purchasing an item debits currency and adds item to inventory."""
    uid = 903080
    user = MockUser(uid, "Economy Player")
    await ensure_user(user)

    # Reset balance to 200 coins
    u = await get_user(uid)
    await change_balance(uid, "coin", 200 - u["coin"])

    # Buy protection for 50 coins
    cost = 50
    assert await change_balance(uid, "coin", -cost, "Buy Protection Shield") is True
    assert await add_item(uid, "protection", 1) is True

    # Validate balances
    u_after = await get_user(uid)
    assert u_after["coin"] == 150

    inv = await get_inventory(uid)
    assert inv.get("protection", 0) >= 1

    # Take item when used in game
    assert await take_item(uid, "protection", 1) is True
    inv_after = await get_inventory(uid)
    assert inv_after.get("protection", 0) == inv.get("protection", 0) - 1


# 10. AFK Sleepers Penalty + Game Finish Rewards
@pytest.mark.asyncio
async def test_comb_afk_sleepers_and_game_finish_rewards():
    """Verify AFK players get penalty and finish_game accurately rewards active winners."""
    chat_id = -100309
    winner_uid = 903090
    loser_uid = 903091
    w_user = MockUser(winner_uid, "Active Winner")
    l_user = MockUser(loser_uid, "Active Loser")
    await ensure_user(w_user)
    await ensure_user(l_user)

    # Reset starting balances to 100 coins
    for uid in (winner_uid, loser_uid):
        u = await get_user(uid)
        await change_balance(uid, "coin", 100 - u["coin"])

    game = {
        "chat": chat_id,
        "players": [winner_uid, loser_uid],
        "names": {winner_uid: "Active Winner", loser_uid: "Active Loser"},
        "roles": {winner_uid: "Detektiv", loser_uid: "Qotil"},
        "alive": {winner_uid: True, loser_uid: False},
        "phase": "day",
        "night": 2,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    # Finish game with Town win
    await finish_game(ctx, game, winners=[winner_uid], winning_team="blue")

    # Winner gets +150 coins (100 + 150 = 250)
    w_final = await get_user(winner_uid)
    assert w_final["coin"] == 250

    # Loser gets +25 coins (100 + 25 = 125)
    l_final = await get_user(loser_uid)
    assert l_final["coin"] == 125


# 11. Afterlife Bets Integration
@pytest.mark.asyncio
async def test_comb_afterlife_bets_and_resolution():
    """Verify afterlife bet deducts coins and pays 2x on winning prediction."""
    uid = 903100
    user = MockUser(uid, "Spectator Gambler")
    await ensure_user(user)

    # Set balance to 100 coins
    u = await get_user(uid)
    await change_balance(uid, "coin", 100 - u["coin"])

    game_id = 999901
    bet_amount = 40
    # Bet on blue team
    assert await record_afterlife_bet(game_id, uid, "blue", bet_amount) is True

    # Balance debited
    u_debited = await get_user(uid)
    assert u_debited["coin"] == 60

    # Blue team wins -> resolves bet with 2x payout (40 * 2 = 80)
    await resolve_afterlife_bets(game_id, "blue")

    u_payout = await get_user(uid)
    assert u_payout["coin"] == 60 + 80 # 140 coins


# 12. Clan Creation and Membership Check
@pytest.mark.asyncio
async def test_comb_clan_creation_and_membership():
    """Verify clan creation assigns leadership and links user in clan_members."""
    leader_uid = int(time.time() * 1000) % 1000000000
    leader = MockUser(leader_uid, "Syndicate Boss")
    await ensure_user(leader)

    clan_name = f"E2E Syn {leader_uid}"
    clan_id = await create_clan(clan_name, "SYN", leader_uid)
    assert clan_id is not None

    membership = await get_user_clan(leader_uid)
    assert membership is not None
    assert membership["name"] == clan_name
    assert membership["member_role"] == "leader"
