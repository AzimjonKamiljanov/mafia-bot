import pytest
import asyncio
from unittest.mock import MagicMock
from database.db import init_db
from database.models import (
    ensure_user, get_user, change_balance, add_item, take_item, get_inventory,
    update_chat_settings, get_chat_settings
)

class MockUser:
    def __init__(self, uid, full_name, username):
        self.id = uid
        self.full_name = full_name
        self.first_name = full_name
        self.username = username

@pytest.mark.asyncio
async def test_concurrent_purchases_never_negative():
    await init_db()
    uid = 88888801
    user = MockUser(uid, "Concurrency Tester", "concur_test")
    await ensure_user(user)

    # Set exact starting balance of 100 coins
    u = await get_user(uid)
    diff = 100 - u["coin"]
    if diff != 0:
        await change_balance(uid, "coin", diff, "Reset to 100")

    # 10 concurrent tasks each trying to debit 30 coins (Total attempted: 300 coins, only 100 available)
    # At most 3 tasks can succeed (3 x 30 = 90), leaving 10 coins. The 4th+ must fail.
    results = await asyncio.gather(*(change_balance(uid, "coin", -30, f"Debit #{i}") for i in range(10)))

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    u_final = await get_user(uid)
    final_balance = u_final["coin"]

    assert final_balance >= 0, f"Balance went negative! {final_balance}"
    assert successes == 3, f"Expected exactly 3 successes with 100 coin and 30 cost, got {successes}"
    assert failures == 7, f"Expected 7 failures, got {failures}"
    assert final_balance == 10, f"Expected remaining 10 coins, got {final_balance}"

@pytest.mark.asyncio
async def test_concurrent_take_item_never_negative():
    await init_db()
    uid = 88888802
    user = MockUser(uid, "Item Concurrency Tester", "item_test")
    await ensure_user(user)

    # Give exactly 3 protection shields
    await add_item(uid, "protection", 3)

    # 10 concurrent tasks trying to take 1 shield each
    results = await asyncio.gather(*(take_item(uid, "protection", 1) for _ in range(10)))

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    inv = await get_inventory(uid)
    remaining = inv.get("protection", 0)

    assert remaining >= 0, f"Inventory went negative! {remaining}"
    assert successes == 3, f"Expected 3 successes, got {successes}"
    assert failures == 7, f"Expected 7 failures, got {failures}"
    assert remaining == 0

@pytest.mark.asyncio
async def test_column_whitelisting():
    await init_db()
    uid = 88888803
    user = MockUser(uid, "Whitelist Tester", "wl_test")
    await ensure_user(user)

    # Currency whitelist
    assert await change_balance(uid, "invalid_currency; DROP TABLE users;--", 50) is False
    assert await change_balance(uid, "hacked_coin", -50) is False

    # Inventory whitelist
    assert await add_item(uid, "admin; DROP TABLE inventory;--", 5) is False
    assert await take_item(uid, "nonexistent_field", 1) is False

    # Chat settings whitelist
    await update_chat_settings(12345, malicious_col="bad_value", day_seconds=20)
    settings = await get_chat_settings(12345)
    assert settings["day_seconds"] == 20
    assert "malicious_col" not in settings

@pytest.mark.asyncio
async def test_game_finish_awards_exact_reward_no_double_spend():
    await init_db()
    from core.engine import finish_game
    from unittest.mock import AsyncMock

    w_uid = 88888804
    l_uid = 88888805
    await ensure_user(MockUser(w_uid, "Winner User", "winner_user"))
    await ensure_user(MockUser(l_uid, "Loser User", "loser_user"))

    # Set known starting balance (100 coins)
    w_user = await get_user(w_uid)
    await change_balance(w_uid, "coin", 100 - w_user["coin"], "Reset")
    l_user = await get_user(l_uid)
    await change_balance(l_uid, "coin", 100 - l_user["coin"], "Reset")

    chat_id = -888888
    game = {
        "chat": chat_id,
        "players": [w_uid, l_uid],
        "names": {w_uid: "Winner User", l_uid: "Loser User"},
        "roles": {w_uid: "Detektiv", l_uid: "Qotil"},
        "alive": {w_uid: True, l_uid: False},
        "phase": "night",
        "night": 2,
    }

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await finish_game(mock_context, game, winners=[w_uid], winning_team="blue")

    # Winner must get exactly +150 coins (100 + 150 = 250), NOT doubled to 300 or 400
    w_final = await get_user(w_uid)
    assert w_final["coin"] == 250, f"Winner received unexpected balance: {w_final['coin']}"

    # Loser must get exactly +25 consolation coins (100 + 25 = 125)
    l_final = await get_user(l_uid)
    assert l_final["coin"] == 125, f"Loser received unexpected balance: {l_final['coin']}"

@pytest.mark.asyncio
async def test_concurrent_clan_balance_never_negative():
    await init_db()
    from database.models import create_clan, change_clan_balance, get_clan, get_clan_balance
    import random
    uid = random.randint(700000, 799999)
    await ensure_user(MockUser(uid, f"Clan Concurrency Leader {uid}", f"clancur_{uid}"))
    clan_id = await create_clan(f"Concurrency Clan {uid}", "CC", uid)
    assert clan_id is not None

    # Clan starts with 500 coins.
    # 10 concurrent tasks each trying to debit 150 coins (Total attempted: 1500, only 500 available)
    # At most 3 tasks can succeed (3 x 150 = 450), leaving 50 coins. The remaining 7 tasks must fail.
    results = await asyncio.gather(*(change_clan_balance(clan_id, -150) for _ in range(10)))

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    clan = await get_clan(clan_id)
    assert clan["coins"] >= 0, f"Clan balance went negative! {clan['coins']}"
    assert successes == 3, f"Expected 3 successes, got {successes}"
    assert failures == 7, f"Expected 7 failures, got {failures}"
    assert clan["coins"] == 50, f"Expected 50 coins remaining, got {clan['coins']}"
    assert await get_clan_balance(clan_id) == 50

    # Verify credit works correctly
    assert await change_clan_balance(clan_id, 200) is True
    assert await get_clan_balance(clan_id) == 250

    # Verify non-existent clan fails gracefully
    assert await change_clan_balance(999999999, -50) is False
    assert await change_clan_balance(-1, 50) is False
