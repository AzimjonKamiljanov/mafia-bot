#!/usr/bin/env python3
"""Adversarial Stress Harness for Milestone 1 Database Concurrency & Integrity.

Tests:
1. Extreme Concurrency (30-100+ simultaneous tasks) debiting user coins, gold, items, clan coins.
2. Dynamic SQL Column Injection safety on whitelisted fields.
3. Connection Error and Query Failure Rollback Recovery.
4. Transaction Audit Ledger Reconciliation.

Exits with code 0 on complete pass, non-zero on any failure.
"""

import sys
import os
import asyncio
import time
import uuid
from unittest.mock import patch
import aiosqlite

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("BOT_TOKEN", "123456789:MOCK_TEST_BOT_TOKEN")
os.environ.setdefault("ADMIN_IDS", "8048940366,7651553630")
os.environ.setdefault(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "detektiv.db"),
)

from database.db import init_db, get_db, close_db
from database.models import (
    ensure_user, get_user, change_balance,
    add_item, take_item, get_inventory,
    create_clan, get_clan, get_clan_balance, change_clan_balance,
    update_chat_settings, get_chat_settings,
    VALID_CURRENCIES, VALID_INVENTORY_FIELDS
)

class MockUser:
    def __init__(self, uid, full_name, username):
        self.id = uid
        self.full_name = full_name
        self.first_name = full_name
        self.username = username

def random_uid() -> int:
    return int(f"93{int(time.time() * 1000) % 1000000:06d}{uuid.uuid4().int % 10000:04d}")

def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

async def run_harness():
    print("=" * 70)
    print("🚀 STARTING ADVERSARIAL DATABASE STRESS & INTEGRITY HARNESS")
    print("=" * 70)
    await init_db()

    total_assertions = 0
    start_time = time.time()

    # -------------------------------------------------------------
    # Test 1: User Coin Overdraft Concurrency (50 tasks)
    # -------------------------------------------------------------
    print("\n[TEST 1] 50 concurrent coin debits (-25 each) against 100 balance...")
    uid = random_uid()
    await ensure_user(MockUser(uid, "Stress User 1", "stress1"))
    u = await get_user(uid)
    await change_balance(uid, "coin", 100 - u["coin"], "Init 100")

    results = await asyncio.gather(*(change_balance(uid, "coin", -25, f"Debit #{i}") for i in range(50)))
    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)
    u_final = await get_user(uid)

    assert u_final["coin"] == 0, f"Balance went to {u_final['coin']}"
    assert successes == 4, f"Expected 4 successes, got {successes}"
    assert failures == 46, f"Expected 46 failures, got {failures}"
    total_assertions += 3
    print(f"  ✓ Pass: 4 succeeded, 46 rejected, final balance=0")

    # -------------------------------------------------------------
    # Test 2: User Gold Overdraft Concurrency (40 tasks)
    # -------------------------------------------------------------
    print("\n[TEST 2] 40 concurrent gold debits (-7 each) against 50 gold...")
    uid = random_uid()
    await ensure_user(MockUser(uid, "Stress Gold User", "stress_gold"))
    u = await get_user(uid)
    await change_balance(uid, "gold", 50 - u["gold"], "Init 50 gold")

    results = await asyncio.gather(*(change_balance(uid, "gold", -7, f"Gold #{i}") for i in range(40)))
    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)
    u_final = await get_user(uid)

    assert u_final["gold"] == 1, f"Gold went to {u_final['gold']}"
    assert successes == 7, f"Expected 7 successes, got {successes}"
    assert failures == 33, f"Expected 33 failures, got {failures}"
    total_assertions += 3
    print(f"  ✓ Pass: 7 succeeded (49 gold), 33 rejected, final gold=1")

    # -------------------------------------------------------------
    # Test 3: Inventory Item Concurrency Across 4 Fields (170 tasks)
    # -------------------------------------------------------------
    print("\n[TEST 3] 170 concurrent item debits across 4 distinct inventory fields...")
    uid = random_uid()
    await ensure_user(MockUser(uid, "Stress Items User", "stress_items"))
    setup = {"revenge_knife": 15, "protection": 20, "evidence": 8, "extra_vote": 11}
    for item, qty in setup.items():
        await add_item(uid, item, qty)

    tasks = []
    for _ in range(45): tasks.append(("revenge_knife", take_item(uid, "revenge_knife", 1)))
    for _ in range(50): tasks.append(("protection", take_item(uid, "protection", 1)))
    for _ in range(40): tasks.append(("evidence", take_item(uid, "evidence", 1)))
    for _ in range(35): tasks.append(("extra_vote", take_item(uid, "extra_vote", 1)))

    raw_res = await asyncio.gather(*(t[1] for t in tasks))
    inv = await get_inventory(uid)
    for item, expected_successes in setup.items():
        s = sum(1 for (it, _), r in zip(tasks, raw_res) if it == item and r is True)
        assert inv[item] == 0, f"Item {item} count was {inv[item]}"
        assert s == expected_successes, f"Item {item} expected {expected_successes}, got {s}"
        total_assertions += 2
    print(f"  ✓ Pass: All 4 item pools exhausted to exactly 0 with zero negative counts")

    # -------------------------------------------------------------
    # Test 4: Clan Treasury Concurrency (60 tasks)
    # -------------------------------------------------------------
    print("\n[TEST 4] 60 concurrent clan coin debits (-45 each) against 500 balance...")
    uid = random_uid()
    await ensure_user(MockUser(uid, "Clan Leader", "clan_ldr"))
    clan_name = unique_name("Stress_Syndicate")
    cid = await create_clan(clan_name, "SS", uid)
    assert cid is not None

    results = await asyncio.gather(*(change_clan_balance(cid, -45) for _ in range(60)))
    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)
    c_final = await get_clan(cid)

    assert c_final["coins"] == 5, f"Clan coins went to {c_final['coins']}"
    assert successes == 11, f"Expected 11 successes, got {successes}"
    assert failures == 49, f"Expected 49 failures, got {failures}"
    total_assertions += 3
    print(f"  ✓ Pass: 11 succeeded (495 coins), 49 rejected, final balance=5")

    # -------------------------------------------------------------
    # Test 5: Dynamic Column Injection Attacks
    # -------------------------------------------------------------
    print("\n[TEST 5] Dynamic column injection attack payloads on currencies, items, settings...")
    uid = random_uid()
    await ensure_user(MockUser(uid, "SQLi Victim", "sqli_victim"))

    sqli_currencies = [
        "coin; DROP TABLE users; --",
        "gold = 999999 --",
        "coin, gold = 999999",
        "' OR '1'='1",
        "user_id", "games", "wins", "losses", "created_at", "updated_at", "name", "", " "
    ]
    for p in sqli_currencies:
        res = await change_balance(uid, p, 50, "Injection")
        assert res is False, f"Injection permitted: {p}"
        total_assertions += 1

    sqli_items = [
        "user_id", "protection; DROP TABLE inventory; --", "revenge_knife = 999 --",
        "' OR '1'='1", "admin", "coin", "", " "
    ]
    for p in sqli_items:
        assert await add_item(uid, p, 5) is False
        assert await take_item(uid, p, 1) is False
        total_assertions += 2

    chat_id = -random_uid()
    malicious_settings = {
        "updated_at": "2026-01-01",
        "day_seconds; DROP TABLE chat_settings; --": 15,
        "lobby_seconds = 10, day_seconds = 10 --": 20,
        "malicious_col": "hacked_value",
        "day_seconds": 35
    }
    await update_chat_settings(chat_id, **malicious_settings)
    settings = await get_chat_settings(chat_id)
    assert settings["day_seconds"] == 35
    assert "malicious_col" not in settings
    total_assertions += 2
    print(f"  ✓ Pass: All {len(sqli_currencies) + len(sqli_items)*2 + 2} SQLi injection attempts neutralized")

    # -------------------------------------------------------------
    # Test 6: Connection Error Rollback Recovery
    # -------------------------------------------------------------
    print("\n[TEST 6] Transaction rollback recovery on mid-flight database error...")
    uid = random_uid()
    await ensure_user(MockUser(uid, "Rollback Subject", "rollback_sub"))
    u = await get_user(uid)
    init_coins = u["coin"]

    db = await get_db()
    orig_exec = db.execute
    async def flaky_execute(query, *args, **kwargs):
        if "INSERT INTO transactions" in str(query):
            raise aiosqlite.OperationalError("Simulated disk I/O write failure")
        return await orig_exec(query, *args, **kwargs)

    with patch.object(db, "execute", side_effect=flaky_execute):
        res = await change_balance(uid, "coin", -40, "Debit should fail")
        assert res is False

    # Check that balance was preserved by rollback
    u_after_fail = await get_user(uid)
    assert u_after_fail["coin"] == init_coins, f"Balance was not rolled back: {u_after_fail['coin']}"

    # Check connection recovered
    rec_res = await change_balance(uid, "coin", -40, "Legitimate debit")
    assert rec_res is True
    u_rec = await get_user(uid)
    assert u_rec["coin"] == init_coins - 40
    total_assertions += 4
    print("  ✓ Pass: Failed transaction cleanly rolled back; subsequent operations succeed")

    # -------------------------------------------------------------
    # Test 7: Scale 100 Concurrency + Ledger Audit Reconciliation
    # -------------------------------------------------------------
    print("\n[TEST 7] Scale stress: 100 concurrent tasks + exact audit ledger reconciliation...")
    uid = random_uid()
    await ensure_user(MockUser(uid, "Audit User", "audit_user"))
    u = await get_user(uid)
    await change_balance(uid, "coin", 120 - u["coin"], "Init 120")

    # 100 tasks debiting 8 coins (800 attempted, 15 * 8 = 120, exactly 0 remaining)
    results = await asyncio.gather(*(change_balance(uid, "coin", -8, f"Stress Audit #{i}") for i in range(100)))
    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)
    assert successes == 15
    assert failures == 85

    async with db.execute("""
        SELECT COUNT(*) AS cnt, SUM(amount) AS total
        FROM transactions
        WHERE user_id = ? AND note LIKE 'Stress Audit #%'
    """, (uid,)) as cur:
        row = await cur.fetchone()
        assert row["cnt"] == 15
        assert row["total"] == 120

    u_final = await get_user(uid)
    assert u_final["coin"] == 0
    total_assertions += 5
    print(f"  ✓ Pass: 100 concurrent coroutines reconciled with 100% exact audit ledger")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"🎉 ALL ADVERSARIAL STRESS HARNESS TESTS PASSED IN {elapsed:.2f}s")
    print(f"Total assertions verified: {total_assertions}")
    print("Verdict: APPROVE")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(run_harness())
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ADVERSARIAL HARNESS FAILURE: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
