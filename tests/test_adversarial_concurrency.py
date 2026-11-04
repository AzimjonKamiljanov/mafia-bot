import pytest
import asyncio
from unittest.mock import MagicMock, patch
import aiosqlite

from database.db import init_db, get_db, close_db
from database.models import (
    ensure_user, get_user, change_balance, get_balance,
    add_item, take_item, get_inventory,
    create_clan, get_clan, get_clan_balance, change_clan_balance,
    update_chat_settings, get_chat_settings,
    VALID_CURRENCIES, VALID_INVENTORY_FIELDS, VALID_CHAT_SETTINGS_FIELDS
)

class MockUser:
    def __init__(self, uid, full_name, username):
        self.id = uid
        self.full_name = full_name
        self.first_name = full_name
        self.username = username

import uuid
import time

def random_uid() -> int:
    return int(f"92{int(time.time() * 1000) % 1000000:06d}{uuid.uuid4().int % 10000:04d}")

def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# =========================================================================
# 1. EXTREME CONCURRENCY STRESS TESTS (30+ simultaneous tasks)
# =========================================================================

@pytest.mark.asyncio
async def test_extreme_concurrency_user_coins_debit_overdraft():
    """50 concurrent coroutines attempting to debit 25 coins from 100 available.
    Exactly 4 must succeed, 46 must fail. Balance must end at exactly 0.
    """
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "Coin Overdraft Challenger", "coin_challenger")
    await ensure_user(user)

    # Force exact 100 coin starting balance
    u = await get_user(uid)
    diff = 100 - u["coin"]
    if diff != 0:
        await change_balance(uid, "coin", diff, "Reset to 100")

    # 50 concurrent tasks, each debiting 25 coins
    num_tasks = 50
    results = await asyncio.gather(*(change_balance(uid, "coin", -25, f"Debit #{i}") for i in range(num_tasks)))

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    u_final = await get_user(uid)
    final_balance = u_final["coin"]

    assert final_balance == 0, f"Balance must be exactly 0, got {final_balance}"
    assert successes == 4, f"Expected exactly 4 successes, got {successes}"
    assert failures == 46, f"Expected 46 failures, got {failures}"

    # Verify transactions count
    db = await get_db()
    async with db.execute("SELECT COUNT(*) AS c FROM transactions WHERE user_id = ? AND kind = 'debit'", (uid,)) as cur:
        row = await cur.fetchone()
        assert row["c"] == 4, f"Expected exactly 4 debit transactions in audit log, got {row['c']}"


@pytest.mark.asyncio
async def test_extreme_concurrency_user_coins_partial_remainder():
    """40 concurrent tasks attempting to debit 10 coins from 137 available.
    Exactly 13 must succeed (13 * 10 = 130). Exactly 27 must fail.
    Final balance must be exactly 7.
    """
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "Coin Remainder Challenger", "coin_rem_challenger")
    await ensure_user(user)

    u = await get_user(uid)
    diff = 137 - u["coin"]
    if diff != 0:
        await change_balance(uid, "coin", diff, "Reset to 137")

    num_tasks = 40
    results = await asyncio.gather(*(change_balance(uid, "coin", -10, f"Debit #{i}") for i in range(num_tasks)))

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    u_final = await get_user(uid)
    final_balance = u_final["coin"]

    assert final_balance == 7, f"Balance must be exactly 7, got {final_balance}"
    assert successes == 13, f"Expected 13 successes, got {successes}"
    assert failures == 27, f"Expected 27 failures, got {failures}"


@pytest.mark.asyncio
async def test_extreme_concurrency_user_gold_debit():
    """40 concurrent tasks attempting to debit 7 gold from 50 available.
    Exactly 7 must succeed (7 * 7 = 49). Exactly 33 must fail.
    Final gold must be exactly 1.
    """
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "Gold Challenger", "gold_challenger")
    await ensure_user(user)

    # Set gold to 50
    u = await get_user(uid)
    diff = 50 - u["gold"]
    if diff != 0:
        await change_balance(uid, "gold", diff, "Reset to 50 gold")

    num_tasks = 40
    results = await asyncio.gather(*(change_balance(uid, "gold", -7, f"Gold Debit #{i}") for i in range(num_tasks)))

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    u_final = await get_user(uid)
    final_gold = u_final["gold"]

    assert final_gold == 1, f"Gold must be exactly 1, got {final_gold}"
    assert successes == 7, f"Expected 7 successes, got {successes}"
    assert failures == 33, f"Expected 33 failures, got {failures}"


@pytest.mark.asyncio
async def test_extreme_concurrency_inventory_multiple_items():
    """Stress test item debits across 4 different inventory fields with 30-50 concurrent tasks each.
    Confirm no negative counts and exact exhaustion.
    """
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "Item Multi Challenger", "item_multi_challenger")
    await ensure_user(user)

    # Setup initial inventory counts
    initial_setup = {
        "revenge_knife": 15,
        "protection": 20,
        "evidence": 8,
        "extra_vote": 11,
    }
    for item, qty in initial_setup.items():
        await add_item(uid, item, qty)

    # Concurrently launch tasks for all 4 items simultaneously (Total: 45 + 50 + 40 + 35 = 170 tasks)
    tasks = []
    # 45 tasks taking 1 revenge_knife (15 available -> 15 succeed, 30 fail)
    for _ in range(45):
        tasks.append(("revenge_knife", take_item(uid, "revenge_knife", 1)))
    # 50 tasks taking 1 protection (20 available -> 20 succeed, 30 fail)
    for _ in range(50):
        tasks.append(("protection", take_item(uid, "protection", 1)))
    # 40 tasks taking 1 evidence (8 available -> 8 succeed, 32 fail)
    for _ in range(40):
        tasks.append(("evidence", take_item(uid, "evidence", 1)))
    # 35 tasks taking 1 extra_vote (11 available -> 11 succeed, 24 fail)
    for _ in range(35):
        tasks.append(("extra_vote", take_item(uid, "extra_vote", 1)))

    raw_results = await asyncio.gather(*(t[1] for t in tasks))

    results_by_item = {"revenge_knife": [], "protection": [], "evidence": [], "extra_vote": []}
    for (item, _), res in zip(tasks, raw_results):
        results_by_item[item].append(res)

    inv = await get_inventory(uid)

    for item, expected_successes in initial_setup.items():
        successes = sum(1 for r in results_by_item[item] if r is True)
        remaining = inv.get(item, 0)
        assert remaining == 0, f"Item {item} remaining must be 0, got {remaining}"
        assert successes == expected_successes, f"Item {item} expected {expected_successes} successes, got {successes}"


@pytest.mark.asyncio
async def test_extreme_concurrency_clan_balance():
    """60 concurrent tasks attempting to debit 45 coins from clan with 500 coins.
    Exactly 11 must succeed (11 * 45 = 495), leaving 5 coins.
    49 tasks must fail.
    """
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "Clan Challenger", "clan_challenger")
    await ensure_user(user)

    clan_name = unique_name("Extreme_Clan")
    clan_id = await create_clan(clan_name, "ECC", uid)
    assert clan_id is not None
    assert await get_clan_balance(clan_id) == 500

    num_tasks = 60
    results = await asyncio.gather(*(change_clan_balance(clan_id, -45) for _ in range(num_tasks)))

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    clan = await get_clan(clan_id)
    final_balance = clan["coins"]

    assert final_balance == 5, f"Clan coins must be exactly 5, got {final_balance}"
    assert successes == 11, f"Expected 11 clan successes, got {successes}"
    assert failures == 49, f"Expected 49 clan failures, got {failures}"
    assert await get_clan_balance(clan_id) == 5


@pytest.mark.asyncio
async def test_extreme_concurrency_interleaved_multi_user_and_clan():
    """Massive stress test: 5 users and 1 clan simultaneously executing mixed debits and credits
    across 250+ concurrent tasks.
    Every account's final balance must equal initial + sum(successful_credits) - sum(successful_debits).
    """
    await init_db()
    users = []
    for i in range(5):
        uid = random_uid()
        u = MockUser(uid, f"Interleaved User {i}", f"interleaved_{i}")
        await ensure_user(u)
        # reset coin to 200
        cur = await get_user(uid)
        await change_balance(uid, "coin", 200 - cur["coin"], "Init 200")
        users.append(uid)

    leader_uid = users[0]
    clan_name = unique_name("Interleaved_Clan")
    clan_id = await create_clan(clan_name, "ISS", leader_uid)
    assert clan_id is not None

    async def user_op(uid: int, amount: int):
        ok = await change_balance(uid, "coin", amount, f"Interleaved {amount}")
        return (uid, amount, ok)

    async def clan_op(cid: int, amount: int):
        ok = await change_clan_balance(cid, amount)
        return ("clan", amount, ok)

    tasks = []
    # For each of the 5 users: 30 debits of -15, 10 credits of +25
    for uid in users:
        for _ in range(30):
            tasks.append(user_op(uid, -15))
        for _ in range(10):
            tasks.append(user_op(uid, 25))

    # For clan: 30 debits of -35, 10 credits of +50 (starts at 500)
    for _ in range(30):
        tasks.append(clan_op(clan_id, -35))
    for _ in range(10):
        tasks.append(clan_op(clan_id, 50))

    # Total tasks: 5 * 40 + 40 = 240 tasks
    results = await asyncio.gather(*tasks)

    # Calculate expected final balances from success logs
    expected_user_balances = {uid: 200 for uid in users}
    expected_clan_balance = 500

    for target, amount, ok in results:
        if ok:
            if target == "clan":
                expected_clan_balance += amount
            else:
                expected_user_balances[target] += amount

    # Verify all users
    for uid in users:
        u = await get_user(uid)
        assert u["coin"] >= 0, f"User {uid} went negative: {u['coin']}"
        assert u["coin"] == expected_user_balances[uid], f"User {uid} mismatch! Expected {expected_user_balances[uid]}, got {u['coin']}"

    # Verify clan
    clan = await get_clan(clan_id)
    assert clan["coins"] >= 0, f"Clan went negative: {clan['coins']}"
    assert clan["coins"] == expected_clan_balance, f"Clan mismatch! Expected {expected_clan_balance}, got {clan['coins']}"


# =========================================================================
# 2. COLUMN INJECTION ATTEMPTS ON DYNAMIC FIELD INTERPOLATIONS
# =========================================================================

@pytest.mark.asyncio
async def test_column_injection_change_balance_currency():
    """Test SQL injection and non-whitelisted columns in change_balance currency parameter."""
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "SQLi Tester Currency", "sqli_cur")
    await ensure_user(user)

    string_injection_payloads = [
        "coin; DROP TABLE users; --",
        "coin = 999999 --",
        "gold; UPDATE users SET gold = 999999; --",
        "coin, gold = 999999",
        "' OR '1'='1",
        "coin' OR '1'='1",
        "1; SELECT 1; --",
        "user_id",       # Existing column in users table, but NOT a currency
        "games",         # Existing column in users table, but NOT a currency
        "wins",          # Existing column in users table, but NOT a currency
        "losses",        # Existing column in users table, but NOT a currency
        "created_at",    # Existing column in users table, but NOT a currency
        "updated_at",    # Existing column in users table, but NOT a currency
        "name",          # Existing column in users table, but NOT a currency
        "",
        " ",
    ]

    for payload in string_injection_payloads:
        # Should return False safely without raising unhandled exception
        result = await change_balance(uid, payload, 50, "Injection attempt")
        assert result is False, f"Payload {payload!r} should have been rejected!"

    # Verify table integrity and balance untouched
    u = await get_user(uid)
    assert u is not None, "Users table was dropped or corrupted!"
    assert u["coin"] == 100, f"Coin modified by injection! {u['coin']}"
    assert u["gold"] == 0, f"Gold modified by injection! {u['gold']}"


@pytest.mark.asyncio
async def test_column_injection_add_and_take_item():
    """Test SQL injection and non-whitelisted columns in add_item and take_item field parameter."""
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "SQLi Tester Items", "sqli_items")
    await ensure_user(user)

    string_item_payloads = [
        "user_id",       # Existing column in inventory, but NOT an inventory item
        "protection; DROP TABLE inventory; --",
        "revenge_knife = 999 --",
        "evidence, revenge_knife = 999",
        "' OR '1'='1",
        "hint; UPDATE inventory SET hint = 999; --",
        "admin",
        "coin",
        "gold",
        "",
        " ",
    ]

    for payload in string_item_payloads:
        assert await add_item(uid, payload, 5) is False, f"add_item allowed injection: {payload!r}"
        assert await take_item(uid, payload, 1) is False, f"take_item allowed injection: {payload!r}"

    # Verify inventory table integrity
    inv = await get_inventory(uid)
    assert inv is not None, "Inventory table was dropped or corrupted!"
    for field in VALID_INVENTORY_FIELDS:
        assert inv.get(field, 0) == 0, f"Field {field} was unexpectedly altered to {inv.get(field)}"


@pytest.mark.asyncio
async def test_column_injection_chat_settings():
    """Test SQL injection in update_chat_settings via kwargs."""
    await init_db()
    chat_id = -random_uid()

    malicious_kwargs = {
        "updated_at": "2026-01-01",                         # Existing column, not in VALID_CHAT_SETTINGS_FIELDS
        "day_seconds; DROP TABLE chat_settings; --": 15,
        "lobby_seconds = 10, day_seconds = 10 --": 20,
        "malicious_col": "hacked_value",
        "' OR '1'='1": 99,
        "day_seconds": 25,                                  # Valid field
    }

    # Should execute safely without error
    await update_chat_settings(chat_id, **malicious_kwargs)

    settings = await get_chat_settings(chat_id)
    assert settings is not None, "chat_settings table was dropped or corrupted!"
    assert settings["day_seconds"] == 25, f"Valid field day_seconds was not updated: {settings['day_seconds']}"
    assert settings["chat_id"] == chat_id, f"chat_id primary key was illegally modified: {settings['chat_id']}"
    assert "malicious_col" not in settings


# =========================================================================
# 3. CONNECTION ERROR & QUERY FAILURE ROLLBACK RECOVERY
# =========================================================================

@pytest.mark.asyncio
async def test_rollback_on_transaction_insert_failure():
    """Verify that if INSERT INTO transactions fails during change_balance,
    the preceding UPDATE users is cleanly rolled back and balance remains unchanged.
    """
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "Rollback Tester", "rollback_user")
    await ensure_user(user)

    u_before = await get_user(uid)
    initial_balance = u_before["coin"]

    db = await get_db()
    original_execute = db.execute

    # Intercept execute: fail when executing INSERT INTO transactions
    async def flaky_execute(query, *args, **kwargs):
        if "INSERT INTO transactions" in str(query):
            raise aiosqlite.OperationalError("Simulated disk I/O failure on transactions insert")
        return await original_execute(query, *args, **kwargs)

    with patch.object(db, "execute", side_effect=flaky_execute):
        success = await change_balance(uid, "coin", -40, "Debit that must fail mid-flight")
        assert success is False, "change_balance should have failed due to disk error"

    # CRITICAL: Verify balance was NOT debited because rollback occurred!
    u_after = await get_user(uid)
    assert u_after["coin"] == initial_balance, f"Balance was not rolled back! Expected {initial_balance}, got {u_after['coin']}"

    # Verify recovery: next normal change_balance MUST succeed cleanly on the same connection
    recovery_success = await change_balance(uid, "coin", -40, "Legitimate debit after recovery")
    assert recovery_success is True, "Database connection failed to recover after rollback!"
    u_recovered = await get_user(uid)
    assert u_recovered["coin"] == initial_balance - 40, f"Expected {initial_balance - 40}, got {u_recovered['coin']}"


@pytest.mark.asyncio
async def test_rollback_on_take_item_commit_failure():
    """Verify that if db.commit() fails during take_item,
    inventory decrement is rolled back and item count is preserved.
    """
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "Item Rollback Tester", "item_rollback")
    await ensure_user(user)

    await add_item(uid, "protection", 5)
    inv_before = await get_inventory(uid)
    assert inv_before["protection"] == 5

    db = await get_db()

    async def failing_commit():
        raise aiosqlite.OperationalError("Simulated commit deadlock")

    with patch.object(db, "commit", side_effect=failing_commit):
        success = await take_item(uid, "protection", 2)
        assert success is False, "take_item should return False on commit failure"

    # Verify item count was NOT decremented
    inv_after = await get_inventory(uid)
    assert inv_after["protection"] == 5, f"Item count was decremented despite failure! Got {inv_after['protection']}"

    # Verify connection recovers for subsequent operations
    legit_take = await take_item(uid, "protection", 2)
    assert legit_take is True, "take_item failed to work after rollback recovery"
    inv_final = await get_inventory(uid)
    assert inv_final["protection"] == 3


@pytest.mark.asyncio
async def test_rollback_on_clan_balance_commit_failure():
    """Verify that if commit fails during change_clan_balance,
    clan treasury modification is rolled back and balance preserved.
    """
    await init_db()
    uid = random_uid()
    user = MockUser(uid, "Clan Rollback Leader", "clan_rollback")
    await ensure_user(user)

    clan_name = unique_name("Rollback_Clan")
    clan_id = await create_clan(clan_name, "RC", uid)
    assert clan_id is not None
    initial_clan_coins = await get_clan_balance(clan_id)
    assert initial_clan_coins == 500

    db = await get_db()

    async def failing_commit():
        raise aiosqlite.OperationalError("Simulated clan commit error")

    with patch.object(db, "commit", side_effect=failing_commit):
        success = await change_clan_balance(clan_id, -100)
        assert success is False, "change_clan_balance should fail on commit error"

    # Verify clan coins preserved
    assert await get_clan_balance(clan_id) == 500, "Clan coins altered despite commit error!"

    # Verify recovery
    assert await change_clan_balance(clan_id, -100) is True, "Recovery failed for clan balance"
    assert await get_clan_balance(clan_id) == 400


@pytest.mark.asyncio
async def test_connection_reopen_after_close():
    """Verify close_db() cleanly terminates connection and get_db() re-establishes a working connection."""
    await init_db()
    uid = random_uid()
    await ensure_user(MockUser(uid, "Reconnect User", "reconnect_u"))

    # Explicitly close the database connection
    await close_db()

    # Next call to get_db / models must automatically reconnect
    db = await get_db()
    assert db is not None

    # Perform read and write
    assert await change_balance(uid, "coin", 50, "After reconnect") is True
    u = await get_user(uid)
    assert u["coin"] == 150


# =========================================================================
# 4. DEEP ADVERSARIAL SCALE, LEDGER RECONCILIATION & CROSS-CURRENCY
# =========================================================================

@pytest.mark.asyncio
async def test_scale_100_concurrent_debits():
    """Stress test with 100 concurrent tasks attempting to debit 5 coins each
    from an account with 85 coins.
    Expected: exactly 17 successes (17 * 5 = 85), 83 failures, remaining = 0.
    """
    await init_db()
    uid = random_uid()
    await ensure_user(MockUser(uid, "Scale 100 User", "scale100"))

    # Set balance to 85
    u = await get_user(uid)
    await change_balance(uid, "coin", 85 - u["coin"], "Set 85")

    num_tasks = 100
    results = await asyncio.gather(*(change_balance(uid, "coin", -5, f"Scale #{i}") for i in range(num_tasks)))

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    u_final = await get_user(uid)
    assert successes == 17, f"Expected 17 successes, got {successes}"
    assert failures == 83, f"Expected 83 failures, got {failures}"
    assert u_final["coin"] == 0, f"Expected 0 remaining coins, got {u_final['coin']}"


@pytest.mark.asyncio
async def test_cross_currency_simultaneous_debits():
    """Verify that concurrent debits to 'coin' and 'gold' on the SAME user
    do not overwrite or interfere with each other's state.
    """
    await init_db()
    uid = random_uid()
    await ensure_user(MockUser(uid, "Cross Currency User", "cross_cur"))

    # Set 200 coins and 100 gold
    u = await get_user(uid)
    await change_balance(uid, "coin", 200 - u["coin"], "Set 200")
    await change_balance(uid, "gold", 100 - u["gold"], "Set 100")

    # 40 tasks debiting 10 coins each (400 attempted -> exactly 20 succeed, 20 fail, 0 remaining)
    # 40 tasks debiting 5 gold each (200 attempted -> exactly 20 succeed, 20 fail, 0 remaining)
    tasks = []
    for _ in range(40):
        tasks.append(("coin", change_balance(uid, "coin", -10, "Coin debit")))
    for _ in range(40):
        tasks.append(("gold", change_balance(uid, "gold", -5, "Gold debit")))

    raw_results = await asyncio.gather(*(t[1] for t in tasks))

    coin_results = [res for (curr, _), res in zip(tasks, raw_results) if curr == "coin"]
    gold_results = [res for (curr, _), res in zip(tasks, raw_results) if curr == "gold"]

    assert sum(1 for r in coin_results if r is True) == 20
    assert sum(1 for r in coin_results if r is False) == 20
    assert sum(1 for r in gold_results if r is True) == 20
    assert sum(1 for r in gold_results if r is False) == 20

    u_final = await get_user(uid)
    assert u_final["coin"] == 0, f"Coin corrupted: {u_final['coin']}"
    assert u_final["gold"] == 0, f"Gold corrupted: {u_final['gold']}"


@pytest.mark.asyncio
async def test_transaction_ledger_exact_audit_reconciliation():
    """Reconcile the transactions audit table with the user's actual balance change.
    Assert that SUM(amount) for debit transactions exactly equals the balance deducted.
    """
    await init_db()
    uid = random_uid()
    await ensure_user(MockUser(uid, "Ledger Audit User", "ledger_user"))

    # Initial balance 150 coins
    u = await get_user(uid)
    await change_balance(uid, "coin", 150 - u["coin"], "Init 150")

    # Run 50 concurrent debits of 12 coins (600 attempted, 12 * 12 = 144, 6 left)
    results = await asyncio.gather(*(change_balance(uid, "coin", -12, f"Audit Debit #{i}") for i in range(50)))
    successes = sum(1 for r in results if r is True)
    assert successes == 12

    db = await get_db()
    async with db.execute("""
        SELECT SUM(amount) AS total_debited, COUNT(*) AS debit_count
        FROM transactions
        WHERE user_id = ? AND kind = 'debit' AND note LIKE 'Audit Debit #%'
    """, (uid,)) as cur:
        row = await cur.fetchone()
        assert row["debit_count"] == 12, f"Expected 12 debit log rows, got {row['debit_count']}"
        assert row["total_debited"] == 144, f"Expected 144 total debited in log, got {row['total_debited']}"

    u_final = await get_user(uid)
    assert u_final["coin"] == 6, f"Expected 6 remaining coins, got {u_final['coin']}"
    assert 150 - u_final["coin"] == row["total_debited"]


@pytest.mark.asyncio
async def test_zero_balance_concurrent_debit_rejection():
    """Verify that when an account balance is exactly 0, 50 concurrent debit tasks
    are all cleanly rejected with 0 successes, 50 failures, and balance remains 0.
    """
    await init_db()
    uid = random_uid()
    await ensure_user(MockUser(uid, "Zero Balance User", "zero_user"))

    # Set balance to 0
    u = await get_user(uid)
    await change_balance(uid, "coin", -u["coin"], "Zero out")
    assert (await get_user(uid))["coin"] == 0

    results = await asyncio.gather(*(change_balance(uid, "coin", -10, f"Zero Debit #{i}") for i in range(50)))
    assert all(r is False for r in results)
    assert (await get_user(uid))["coin"] == 0


@pytest.mark.asyncio
async def test_multi_clan_extreme_concurrency():
    """Verify concurrent debits across 5 different clans simultaneously (150 total tasks).
    No clan balance should go negative, and all final balances must match expected remainders.
    """
    await init_db()
    clans = []
    for i in range(5):
        uid = random_uid()
        await ensure_user(MockUser(uid, f"Multi Clan Leader {i}", f"mclan_ldr_{i}"))
        c_name = unique_name(f"Multi_Clan_{i}")
        cid = await create_clan(c_name, f"MC{i}", uid)
        assert cid is not None
        clans.append(cid)

    # Each clan starts with 500 coins.
    # 30 concurrent tasks per clan, debiting 30 coins each (900 attempted per clan).
    # Exactly 16 tasks per clan can succeed (16 * 30 = 480), leaving 20 coins.
    clan_tasks = []
    for cid in clans:
        for i in range(30):
            clan_tasks.append((cid, change_clan_balance(cid, -30)))

    raw_results = await asyncio.gather(*(t[1] for t in clan_tasks))

    results_by_clan = {cid: [] for cid in clans}
    for (cid, _), res in zip(clan_tasks, raw_results):
        results_by_clan[cid].append(res)

    for cid in clans:
        successes = sum(1 for r in results_by_clan[cid] if r is True)
        failures = sum(1 for r in results_by_clan[cid] if r is False)
        assert successes == 16, f"Clan {cid}: expected 16 successes, got {successes}"
        assert failures == 14, f"Clan {cid}: expected 14 failures, got {failures}"
        c = await get_clan(cid)
        assert c["coins"] == 20, f"Clan {cid}: expected 20 coins, got {c['coins']}"

