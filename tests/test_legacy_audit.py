import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock

import main

@pytest.mark.asyncio
async def test_legacy_audit_suite():
    # 1. choose_roles (4 to 35 players)
    for n in range(4, 36):
        for trial in range(5):
            roles = main.choose_roles(n)
            assert roles is not None and len(roles) == n, f"choose_roles({n}) failed!"
            if "Qotil" in roles and "Boshliq" not in roles:
                raise AssertionError(f"Qotil appeared without Boshliq for n={n}")
            if "Sherif" in roles and "Detektiv" not in roles:
                raise AssertionError(f"Sherif appeared without Detektiv for n={n}")

    # 2. Detective check
    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    game = {
        "chat": -100123456,
        "players": [101, 102, 103, 104],
        "names": {101: "Detektiv Ali", 102: "Qotil Vali", 103: "Doktor Gani", 104: "Fuqaro Sami"},
        "roles": {101: "Detektiv", 102: "Qotil", 103: "Doktor", 104: "Fuqaro"},
        "alive": {101: True, 102: True, 103: True, 104: True},
        "phase": "night",
        "night": 1,
        "detective_results": {},
        "kill_targets": {},
        "protected": set(),
        "protected_by": {},
        "doctor_self_heal_used": {},
        "boy_stolen_roles": {},
        "sheriff_promoted": set(),
        "night_done": set(),
        "inactive": {101: 0, 102: 0, 103: 0, 104: 0},
        "last_results": [],
    }

    res = await main.execute_action(mock_context, game, 101, "detective", 102)
    assert "Tekshiruv qabul qilindi" in res, f"Detective action failed: {res}"
    assert "101" in game["detective_results"], "Detective result not stored in game"
    assert game["detective_results"]["101"]["role"] == "Qotil"

    # 3. Sheriff check
    game["sheriff_promoted"].add(103)
    game["roles"][103] = "Sherif"
    res_sheriff = await main.execute_action(mock_context, game, 103, "sheriff_check", 102)
    assert 103 not in game["kill_targets"], "Sheriff check improperly added a kill target!"
    assert "Sherif tekshiruvi" in res_sheriff

    # 4. Sayyoh witness resolution
    tourist_game = {
        "chat": -100123456,
        "players": [201, 202, 203, 204],
        "names": {201: "Sayyoh", 202: "Qotil", 203: "Qurbon", 204: "Boshliq"},
        "roles": {201: "Sayyoh", 202: "Qotil", 203: "Fuqaro", 204: "Boshliq"},
        "alive": {201: True, 202: True, 203: True, 204: True},
        "phase": "night",
        "night": 1,
        "blocked_roles": {},
        "kill_targets": {202: 203},
        "tourist_targets": {201: 203},
        "protected": set(),
        "doctor_self_heal_used": {},
        "inactive": {201: 0, 202: 0, 203: 0, 204: 0},
        "night_done": {201, 202, 204},
        "votes": {},
        "last_results": [],
        "detective_results": {},
        "partners": {204: 202, 202: 204},
        "_finish_started": False,
        "_waiting_king": False,
        "_resolving_night": False,
    }
    sent_messages = []
    async def mock_send_message(chat_id, text, **kwargs):
        sent_messages.append((chat_id, text))
    mock_context.bot.send_message = AsyncMock(side_effect=mock_send_message)

    await main.resolve_night(mock_context, tourist_game)
    sayyoh_msgs = [text for cid, text in sent_messages if cid == 201]
    assert any("SAYYOH TASHRIFI GUVOXLIGI" in m for m in sayyoh_msgs), f"Sayyoh did not receive witness message: {sayyoh_msgs}"

    # 5. King attack deadlock fix
    king_game = {
        "chat": -100123456,
        "players": [301, 302, 303, 304],
        "names": {301: "Qirol", 302: "Qotil", 303: "Fuqaro", 304: "Boshliq"},
        "roles": {301: "Qirol", 302: "Qotil", 303: "Fuqaro", 304: "Boshliq"},
        "alive": {301: True, 302: True, 303: True, 304: True},
        "phase": "night",
        "night": 1,
        "blocked_roles": {},
        "kill_targets": {302: 301},
        "tourist_targets": {},
        "protected": set(),
        "inactive": {301: 0, 302: 0, 303: 0, 304: 0},
        "night_done": {301, 302, 304},
        "votes": {},
        "last_results": [],
        "detective_results": {},
        "partners": {304: 302, 302: 304},
        "_finish_started": False,
        "_waiting_king": False,
        "_resolving_night": False,
    }
    await main.resolve_night(mock_context, king_game)
    assert king_game.get("_waiting_king") is True, "King was not put into _waiting_king"
    assert king_game.get("_resolving_night") is False, "King attack left _resolving_night=True (Deadlock!)"

    # 6. Verdict tally and Joker end
    verdict_game = {
        "chat": -100123456,
        "players": [401, 402, 403, 404],
        "names": {401: "Joker Omon", 402: "Ayblovchi 1", 403: "Ayblovchi 2", 404: "Fuqaro"},
        "roles": {401: "Joker", 402: "Fuqaro", 403: "Fuqaro", 404: "Fuqaro"},
        "alive": {401: True, 402: True, 403: True, 404: True},
        "phase": "verdict",
        "accused_uid": 401,
        "verdict_votes": {402: "kill", 403: "kill", 404: "forgive"},
        "votes": {},
        "night": 1,
        "_finish_started": False,
    }
    finished_winners = []
    orig_finish = getattr(main, "finish_game", None)
    async def mock_finish_game(context, game, winners, joker=False, **kwargs):
        finished_winners.append((winners, joker))
    main.finish_game = mock_finish_game

    try:
        await main.resolve_verdict(mock_context, verdict_game)
        assert len(finished_winners) == 1, "finish_game was not called for Joker verdict"
        winners, is_joker = finished_winners[0]
        assert is_joker is True, "Joker flag was not True"
        assert isinstance(winners, (list, set, tuple)), f"Winners must be iterable: {type(winners)}"
        assert 401 in winners, "Joker 401 is not in winners"
    finally:
        if orig_finish is not None:
            main.finish_game = orig_finish
