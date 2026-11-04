import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from database.db import init_db, get_db
from database.models import ensure_user, get_balance, get_inventory
from handlers.admin_ai import process_admin_ai_message, pending_admin_grants, MAX_ITEM_COUNT, MAX_CURRENCY_COUNT
from handlers.callbacks import callback_router

@pytest.mark.asyncio
async def test_bare_words_rejected_without_grant_verb():
    await init_db()
    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = 7651553630
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.effective_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    pending_admin_grants.clear()

    # Bare item word "himoya"
    mock_update.effective_message.text = "himoya"
    await process_admin_ai_message(mock_update, mock_context)
    assert len(pending_admin_grants) == 0

    # Bare item word "gul"
    mock_update.effective_message.text = "gul"
    await process_admin_ai_message(mock_update, mock_context)
    assert len(pending_admin_grants) == 0

    # Bare currency without verb "500 coin"
    mock_update.effective_message.text = "500 coin"
    await process_admin_ai_message(mock_update, mock_context)
    assert len(pending_admin_grants) == 0

@pytest.mark.asyncio
async def test_caps_enforced_for_currency_and_items():
    await init_db()
    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = 7651553630
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.effective_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    pending_admin_grants.clear()

    # Over currency cap: 150_000 coin
    mock_update.effective_message.text = "7651553630 ga 150000 coin ber"
    await process_admin_ai_message(mock_update, mock_context)
    assert len(pending_admin_grants) == 0
    assert "oshmasligi kerak" in mock_update.effective_message.reply_text.call_args[0][0]

    # Over item cap: 100 ta himoya
    mock_update.effective_message.reply_text.reset_mock()
    mock_update.effective_message.text = "7651553630 ga 100 ta himoya ber"
    await process_admin_ai_message(mock_update, mock_context)
    assert len(pending_admin_grants) == 0
    assert "oshmasligi kerak" in mock_update.effective_message.reply_text.call_args[0][0]

class MockUser:
    def __init__(self, uid: int, name: str, username: str = ""):
        self.id = uid
        self.first_name = name
        self.full_name = name
        self.username = username

@pytest.mark.asyncio
async def test_currency_grant_confirmation_flow_and_audit():
    await init_db()
    target_uid = 444111222
    await ensure_user(MockUser(target_uid, "TargetPlayer"))
    initial_coin = await get_balance(target_uid, "coin")

    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = 7651553630
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.effective_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    pending_admin_grants.clear()

    mock_update.effective_message.text = f"{target_uid} ga 2500 coin ber"
    await process_admin_ai_message(mock_update, mock_context)

    # Check pending grant created with confirmation buttons
    assert len(pending_admin_grants) == 1
    token = list(pending_admin_grants.keys())[0]
    grant = pending_admin_grants[token]
    assert grant["target_id"] == target_uid
    assert grant["amount"] == 2500
    assert grant["currency"] == "coin"

    # Verify balance has NOT changed yet (waiting for confirmation)
    assert await get_balance(target_uid, "coin") == initial_coin

    # 1. Non-admin cannot confirm
    cb_update = MagicMock()
    cb_update.effective_chat.type = "private"
    cb_update.callback_query.data = f"adm_grant_confirm:{token}"
    cb_update.callback_query.from_user.id = 999999999
    cb_update.callback_query.from_user.username = "random_user"
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.edit_message_text = AsyncMock()

    await callback_router(cb_update, mock_context)
    assert "faqat Master Admin" in cb_update.callback_query.answer.call_args[0][0]
    assert token in pending_admin_grants

    # 2. Proper admin confirms
    cb_update.callback_query.from_user.id = 7651553630
    cb_update.callback_query.from_user.username = "rasuljonovv_a"
    await callback_router(cb_update, mock_context)

    # Token consumed
    assert token not in pending_admin_grants

    # Balance updated
    new_coin = await get_balance(target_uid, "coin")
    assert new_coin == initial_coin + 2500

    # Audit log in transactions table
    db = await get_db()
    async with db.execute(
        "SELECT * FROM transactions WHERE user_id = ? AND kind = 'admin_grant' ORDER BY id DESC LIMIT 1",
        (target_uid,)
    ) as cur:
        tx = await cur.fetchone()
        assert tx is not None
        assert tx["amount"] == 2500
        assert tx["currency"] == "coin"

@pytest.mark.asyncio
async def test_item_grant_cancellation_flow():
    await init_db()
    target_uid = 555222333
    await ensure_user(MockUser(target_uid, "TargetPlayer2"))

    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = 7651553630
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.effective_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    pending_admin_grants.clear()

    mock_update.effective_message.text = f"{target_uid} ga 5 ta pichoq ber"
    await process_admin_ai_message(mock_update, mock_context)

    assert len(pending_admin_grants) == 1
    token = list(pending_admin_grants.keys())[0]

    # Admin cancels
    cb_update = MagicMock()
    cb_update.effective_chat.type = "private"
    cb_update.callback_query.data = f"adm_grant_cancel:{token}"
    cb_update.callback_query.from_user.id = 7651553630
    cb_update.callback_query.from_user.username = "rasuljonovv_a"
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.edit_message_text = AsyncMock()

    await callback_router(cb_update, mock_context)
    assert token not in pending_admin_grants

    # Inventory must remain empty
    inv = await get_inventory(target_uid)
    assert inv.get("revenge_knife", 0) == 0

@pytest.mark.asyncio
async def test_badge_grant_confirmation_flow_and_audit():
    await init_db()
    target_uid = 9988776655
    await ensure_user(MockUser(target_uid, "BadgeUser"))
    db = await get_db()

    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = 7651553630
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.effective_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    pending_admin_grants.clear()

    mock_update.effective_message.text = f"{target_uid} ga qirol toji nishon ber"
    await process_admin_ai_message(mock_update, mock_context)

    assert len(pending_admin_grants) == 1
    token = list(pending_admin_grants.keys())[0]
    grant = pending_admin_grants[token]
    assert grant["kind"] == "badge"
    assert grant["badge_key"] == "badge_crown"
    assert grant["target_id"] == target_uid

    # Confirm grant
    cb_update = MagicMock()
    cb_update.effective_chat.type = "private"
    cb_update.callback_query.data = f"adm_grant_confirm:{token}"
    cb_update.callback_query.from_user.id = 7651553630
    cb_update.callback_query.from_user.username = "rasuljonovv_a"
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.edit_message_text = AsyncMock()

    await callback_router(cb_update, mock_context)
    assert token not in pending_admin_grants

    from database.models import get_badge
    assigned_badge = await get_badge(target_uid)
    assert assigned_badge == "👑 Qirol Toji"

    # Verify audit transaction
    async with db.execute(
        "SELECT kind, currency, note FROM transactions WHERE user_id = ? AND kind = 'admin_grant'",
        (target_uid,)
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "admin_grant"
        assert row[1] == "badge:badge_crown"
        assert "Super Admin 7651553630" in row[2]
