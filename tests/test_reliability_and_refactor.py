import pytest
from unittest.mock import AsyncMock, MagicMock
from database.db import init_db, get_db
from database.models import get_chat_settings, update_chat_settings
from core.rate_limiter import is_rate_limited, reset_rate_limits
from bot import handle_private_message, PM_DISPATCH_LOOKUP

class MockUser:
    def __init__(self, uid: int, name: str, username: str = ""):
        self.id = uid
        self.first_name = name
        self.full_name = name
        self.username = username
        self.is_bot = False

@pytest.mark.asyncio
async def test_group_and_chat_settings_unified():
    """Verify group_settings view with triggers transparently manages chat_settings table."""
    await init_db()
    db = await get_db()
    chat_id = -999888

    # 1. Clean up
    await db.execute("DELETE FROM chat_settings WHERE chat_id = ?", (chat_id,))
    await db.commit()

    # 2. Insert via group_settings view
    await db.execute("""
        INSERT INTO group_settings (chat_id, lobby_seconds, night_seconds, day_seconds, vote_seconds, verdict_seconds, disabled_roles, updated_at)
        VALUES (?, 250, 45, 10, 30, 20, '["Joker"]', '2026-11-04T12:00:00Z')
    """, (chat_id,))
    await db.commit()

    # Verify presence in chat_settings table
    st = await get_chat_settings(chat_id)
    assert st["lobby_seconds"] == 250
    assert st["night_seconds"] == 45
    assert st["disabled_roles"] == '["Joker"]'

    # 3. Update via update_chat_settings
    await update_chat_settings(chat_id, lobby_seconds=180)
    async with db.execute("SELECT lobby_seconds FROM group_settings WHERE chat_id = ?", (chat_id,)) as cur:
        row = await cur.fetchone()
        assert row["lobby_seconds"] == 180

    # 4. Delete via group_settings view
    await db.execute("DELETE FROM group_settings WHERE chat_id = ?", (chat_id,))
    await db.commit()

    async with db.execute("SELECT COUNT(*) AS c FROM chat_settings WHERE chat_id = ?", (chat_id,)) as cur:
        row = await cur.fetchone()
        assert row["c"] == 0

@pytest.mark.asyncio
async def test_rate_limiter_sliding_window():
    """Verify rate limiter blocks when threshold is exceeded in window."""
    reset_rate_limits()
    uid = 999111

    # First 3 allowed
    for _ in range(3):
        assert is_rate_limited(uid, action="test", max_rate=3, window_seconds=2.0) is False

    # 4th exceeds max_rate=3
    assert is_rate_limited(uid, action="test", max_rate=3, window_seconds=2.0) is True

    # After reset, passes again
    reset_rate_limits()
    assert is_rate_limited(uid, action="test", max_rate=3, window_seconds=2.0) is False

@pytest.mark.asyncio
async def test_pm_dispatcher_routing():
    """Verify PM_DISPATCH_LOOKUP contains expected commands and routes properly."""
    assert "profil" in PM_DISPATCH_LOOKUP
    assert "balans" in PM_DISPATCH_LOOKUP
    assert "dokon" in PM_DISPATCH_LOOKUP
    assert "reyting" in PM_DISPATCH_LOOKUP
    assert "rollar" in PM_DISPATCH_LOOKUP
    assert "start" in PM_DISPATCH_LOOKUP
    assert "chiqish" in PM_DISPATCH_LOOKUP

    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user = MockUser(888123, "TestUser")
    mock_update.message.text = "profil"
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    await handle_private_message(mock_update, mock_context)
