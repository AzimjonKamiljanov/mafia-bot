import pytest
from unittest.mock import MagicMock
from database.db import init_db
from database.models import (
    ensure_user, get_user, change_balance, get_inventory, add_item,
    take_item, set_badge, get_badge, set_will, get_will, create_clan,
    get_user_clan, record_afterlife_bet, resolve_afterlife_bets
)

class MockUser:
    def __init__(self, uid, full_name, username):
        self.id = uid
        self.full_name = full_name
        self.first_name = full_name
        self.username = username

@pytest.mark.asyncio
async def test_db_user_and_balance():
    await init_db()
    u = MockUser(99901, "Test User", "testuser")
    user_row = await ensure_user(u)
    assert user_row["user_id"] == 99901
    assert user_row["coin"] >= 100

    # Balance transaction test
    ok = await change_balance(99901, "coin", 50, "Test Bonus")
    assert ok is True
    u_updated = await get_user(99901)
    assert u_updated["coin"] == user_row["coin"] + 50

    # Overdraft protection
    fail = await change_balance(99901, "coin", -999999, "Overdraft test")
    assert fail is False

@pytest.mark.asyncio
async def test_inventory_and_items():
    await init_db()
    u = MockUser(99902, "Inv User", "invuser")
    await ensure_user(u)

    await add_item(99902, "protection", 2)
    inv = await get_inventory(99902)
    assert inv.get("protection", 0) >= 2

    # Take item
    taken = await take_item(99902, "protection", 1)
    assert taken is True

    # Take more than available
    failed_take = await take_item(99902, "protection", 999)
    assert failed_take is False

@pytest.mark.asyncio
async def test_will_storage():
    await init_db()
    uid = 99903
    u = MockUser(uid, "Will Tester", "willtest")
    await ensure_user(u)

    await set_will(uid, "Mening sirim: 104-raqamli Mafiya!")
    fetched = await get_will(uid)
    assert "Mening sirim: 104-raqamli Mafiya!" in fetched

@pytest.mark.asyncio
async def test_clan_and_afterlife_bets():
    import random
    await init_db()
    uid = random.randint(300000, 999999)
    u = MockUser(uid, f"Clan Leader {uid}", f"clanleader{uid}")
    await ensure_user(u)

    clan_name = f"Peaky Blinders {uid}"
    clan_id = await create_clan(clan_name, "PB", uid)
    assert clan_id is not None

    clan_info = await get_user_clan(uid)
    assert clan_info is not None
    assert clan_info["name"] == clan_name
    assert clan_info["tag"] == "PB"

    # Afterlife bet test
    await change_balance(uid, "coin", 200, "Seed for betting")
    bet_ok = await record_afterlife_bet(12345, uid, "blue", 50)
    assert bet_ok is True

    # Resolve win
    before = (await get_user(uid))["coin"]
    await resolve_afterlife_bets(12345, "blue")
    after = (await get_user(uid))["coin"]
    assert after == before + 100  # 50 * 2 = 100 reward

@pytest.mark.asyncio
async def test_group_member_tracking():
    from database.models import track_group_member, get_group_members
    await init_db()
    chat_id = -100999888
    u1 = MockUser(88801, "Guruh O'yinchisi 1", "player1")
    u2 = MockUser(88802, "Guruh O'yinchisi 2", "player2")
    await track_group_member(chat_id, u1)
    await track_group_member(chat_id, u2)

    members = await get_group_members(chat_id)
    uids = [m["user_id"] for m in members]
    assert 88801 in uids
    assert 88802 in uids

@pytest.mark.asyncio
async def test_clan_balance_operations():
    await init_db()
    from database.models import create_clan, change_clan_balance, get_clan, get_clan_balance
    import random
    uid = random.randint(800000, 899999)
    await ensure_user(MockUser(uid, f"Clan Tester {uid}", f"clantester{uid}"))
    clan_id = await create_clan(f"Test Clan Treasury {uid}", "TCT", uid)
    assert clan_id is not None

    # Clan starts with 500 coins
    assert await get_clan_balance(clan_id) == 500

    # Credit +100
    assert await change_clan_balance(clan_id, 100) is True
    assert await get_clan_balance(clan_id) == 600

    # Debit -200
    assert await change_clan_balance(clan_id, -200) is True
    assert await get_clan_balance(clan_id) == 400

    # Overdraft attempt (-1000 when balance is 400)
    assert await change_clan_balance(clan_id, -1000) is False
    assert await get_clan_balance(clan_id) == 400

    # Zero amount no-op
    assert await change_clan_balance(clan_id, 0) is True
    assert await get_clan_balance(clan_id) == 400

    # Non-existent clan
    assert await change_clan_balance(9999999, 100) is False
    assert await get_clan(9999999) is None
    assert await get_clan_balance(9999999) == 0
    assert await change_clan_balance(-1, 50) is False

