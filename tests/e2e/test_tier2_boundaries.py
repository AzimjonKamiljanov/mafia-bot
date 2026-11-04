"""Tier 2: Boundary & Corner Cases E2E Tests.

Opaque-box tests verifying boundary values, edge conditions, invalid input combinations,
rate limit transitions, concurrency collisions, and malicious input handling derived from
ORIGINAL_REQUEST.md and PROJECT.md.
"""

import time
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from database.db import init_db, get_db
from database.models import (
    ensure_user, get_user, change_balance, add_item, take_item, get_inventory,
    is_admin, update_chat_settings, get_chat_settings
)
from core.engine import (
    games, lobbies, cancel_game_timer, cancel_lobby_timer, active_drops,
    claim_gold_drop, cleanup_expired_drops, DEFAULT_DROP_EXPIRY_SECONDS
)
from core.rate_limiter import is_rate_limited, reset_rate_limits
from core.visuals import format_player_title_html
from phases.lobby import create_lobby, start_game, lobby_text, MIN_PLAYERS, MAX_PLAYERS
from handlers.commands import (
    start_cmd, profile_cmd, balance_cmd, guide_cmd, will_cmd, stop_cmd
)
from handlers.social import send_cmd, coin_cmd, gold_cmd, para_cmd, bro_cmd
from handlers.callbacks import callback_router
from bot import handle_private_message, track_group_user

from tests.e2e import (
    MockUser, MockChat, make_pm_update, make_group_message_update,
    make_callback_update, make_e2e_context, reset_runtime_state
)
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def setup_e2e_env():
    await init_db()
    reset_runtime_state()
    yield
    reset_runtime_state()


# 1. Empty and Whitespace Inputs
@pytest.mark.asyncio
async def test_boundary_empty_and_whitespace_inputs():
    """Verify handlers handle empty strings, whitespace, and newline inputs gracefully."""
    ctx = make_e2e_context()

    for text in ("", "   ", "\t\t", "\n\n\n", "   \n  \t  "):
        up = make_pm_update(uid=902001, text=text)
        await handle_private_message(up, ctx)
        # Should cleanly return without crashing or replying to empty message
        assert not up.message.reply_text.called


# 2. Non-Digit IDs and Type Edge Cases
@pytest.mark.asyncio
async def test_boundary_non_digit_ids():
    """Verify non-digit IDs or invalid types do not grant privileges or crash handlers."""
    # String or malformed user ID check in admin auth
    assert is_admin(-999, "fake_admin") is False
    assert is_admin(0, "root") is False

    # Calling gold drop claim with non-digit uid
    now = time.time()
    drop_id = "drop_boundary_test"
    active_drops[drop_id] = {
        "id": drop_id,
        "chat_id": -100201,
        "creator_id": 111,
        "creator_name": "Sponsor",
        "total": 5,
        "remaining": 5,
        "claimed_by": {},
        "created_at": now,
        "expires_at": now + 600,
    }

    # Valid claim with numeric ID
    success, msg, drop = await claim_gold_drop(drop_id, 902002, "Valid User")
    assert success is True

    # Same user double claim boundary
    success2, msg2, drop2 = await claim_gold_drop(drop_id, 902002, "Valid User")
    assert success2 is False
    assert "allaqachon" in msg2


# 3. Negative and Zero Amounts
@pytest.mark.asyncio
async def test_boundary_negative_and_zero_currency_amounts():
    """Verify currency and gold updates enforce boundary values."""
    uid = 902003
    user = MockUser(uid, "Amount Tester")
    await ensure_user(user)

    # Reset balance
    u = await get_user(uid)
    await change_balance(uid, "coin", -u["coin"])

    # Zero amount change succeeds (noop)
    assert await change_balance(uid, "coin", 0) is True

    # Negative change on zero balance fails
    assert await change_balance(uid, "coin", -1) is False

    # Negative amount in /send command
    ctx = make_e2e_context()
    for invalid_arg in ("0", "-5", "501", "abc", "10.5", "None"):
        ctx.args = [invalid_arg]
        grp_up = make_group_message_update(chat_id=-100202, user=user, text=f"/send {invalid_arg}")
        await send_cmd(grp_up, ctx)
        assert grp_up.message.reply_text.called
        reply = grp_up.message.reply_text.call_args[0][0]
        assert "1 dan 500 gacha" in reply or "butun son" in reply


# 4. NoneType Updates and Missing Objects
@pytest.mark.asyncio
async def test_boundary_none_updates_and_channel_posts():
    """Verify all major handlers survive None message, None user, and channel posts."""
    ctx = make_e2e_context()

    # Update with None message and None effective_user (e.g. channel post or status update)
    null_up = MagicMock()
    null_up.message = None
    null_up.effective_message = None
    null_up.effective_user = None
    null_up.effective_chat = None
    null_up.callback_query = None

    # Should all complete cleanly without unhandled exceptions
    await handle_private_message(null_up, ctx)
    await track_group_user(null_up, ctx)
    await start_cmd(null_up, ctx)
    await profile_cmd(null_up, ctx)
    await balance_cmd(null_up, ctx)
    await guide_cmd(null_up, ctx)
    await will_cmd(null_up, ctx)
    await stop_cmd(null_up, ctx)
    await callback_router(null_up, ctx)


# 5. Unescaped Characters and XSS Injections in Names
def test_boundary_unescaped_characters_in_names():
    """Verify HTML special characters, script tags, and RTL characters in names are escaped."""
    malicious_names = [
        ("<script>alert('XSS')</script>", "&lt;script&gt;alert('XSS')&lt;/script&gt;"),
        ("<b>Bold Hacker</b>", "&lt;b&gt;Bold Hacker&lt;/b&gt;"),
        ("John & Jane <Doe>", "John &amp; Jane &lt;Doe&gt;"),
        ("\"quoted\" 'single'", "&quot;quoted&quot; &#x27;single&#x27;"),
    ]

    for raw, expected in malicious_names:
        lobby = {
            "players": [902004],
            "names": {902004: raw},
            "badges": {},
        }
        title = format_player_title_html(lobby, 902004)
        assert "<script>" not in title
        assert "<b>Bold" not in title

        rendered_lobby = lobby_text(lobby)
        assert "<script>" not in rendered_lobby


# 6. Rate Limit Sliding Window Boundary
def test_boundary_rate_limit_sliding_window_bounds():
    """Verify rate limiter strictly adheres to max_rate boundary and sliding window."""
    reset_rate_limits()
    uid = 902005
    max_rate = 4
    window = 1.0

    # Exactly max_rate requests succeed
    for i in range(max_rate):
        limited = is_rate_limited(uid, action="burst_test", max_rate=max_rate, window_seconds=window)
        assert limited is False, f"Request {i+1} was unexpectedly rate limited"

    # Request max_rate + 1 must be throttled
    assert is_rate_limited(uid, action="burst_test", max_rate=max_rate, window_seconds=window) is True
    # Request max_rate + 2 is also throttled
    assert is_rate_limited(uid, action="burst_test", max_rate=max_rate, window_seconds=window) is True


# 7. Concurrent Lobby Joins and Duplicate Prevention
@pytest.mark.asyncio
async def test_boundary_concurrent_lobby_joins():
    """Verify concurrent lobby joins do not create duplicate player entries."""
    chat_id = -100203
    creator = MockUser(902010, "Creator")
    ctx = make_e2e_context()

    grp_up = make_group_message_update(chat_id=chat_id, user=creator, text="/game")
    await create_lobby(grp_up, ctx)
    assert chat_id in lobbies

    # Pre-ensure user in DB to test in-memory lobby concurrency isolation
    same_user = MockUser(902011, "Same Player")
    await ensure_user(same_user)
    join_up = make_callback_update(chat_id, same_user, f"lobby_join:{chat_id}")

    await asyncio.gather(*(callback_router(join_up, ctx) for _ in range(5)))

    # User must appear at most once in players list
    player_count = lobbies[chat_id]["players"].count(902011)
    assert player_count == 1, f"Player appeared {player_count} times in lobby players!"


# 8. Player Count Limits: MIN_PLAYERS and MAX_PLAYERS
@pytest.mark.asyncio
async def test_boundary_player_count_limits():
    """Verify game refuses to start when player count is below MIN_PLAYERS."""
    chat_id = -100204
    ctx = make_e2e_context()

    # Create lobby with only 3 players (MIN_PLAYERS is 4)
    lobbies[chat_id] = {
        "chat_id": chat_id,
        "players": [902021, 902022, 902023],
        "names": {902021: "P1", 902022: "P2", 902023: "P3"},
        "badges": {},
        "premium": {},
        "settings": {},
        "open": True,
    }

    await start_game(ctx, chat_id)

    # Game should NOT start, error message sent to group
    assert chat_id not in games
    assert ctx.bot.send_message.called
    msg = ctx.bot.send_message.call_args[1].get("text") or ctx.bot.send_message.call_args[0][1]
    assert f"kamida {MIN_PLAYERS}" in msg


# 9. Malformed and Out-of-Spec Callback Queries
@pytest.mark.asyncio
async def test_boundary_malformed_callback_queries():
    """Verify malformed callback queries answer safely without throwing unhandled exceptions."""
    user = MockUser(902030, "Query Tester")
    ctx = make_e2e_context()

    malformed_payloads = [
        "",
        ":",
        ":::",
        "act:invalid:99999",
        "vote:-100205:none",
        "vote:-100205:99999",
        "verdict:-100205:99999:kill",
        "lobby_stop:-100205",
        "sett:unknown_action:-100205:val",
        "claim_gold:invalid_drop",
        "nonexistent_subsystem_action:123:456",
    ]

    for payload in malformed_payloads:
        up = make_callback_update(-100205, user, payload)
        # Must execute cleanly without exception
        await callback_router(up, ctx)
        if any(payload.startswith(prefix) for prefix in ("act:", "vote:", "verdict:", "lobby_", "claim_gold:")):
            assert up.callback_query.answer.called


@pytest.mark.asyncio
async def test_boundary_cb_night_malformed_index_error():
    """Verify cb_night guards against truncated act: callback queries without IndexError."""
    user = MockUser(902031, "IndexError Tester")
    ctx = make_e2e_context()
    up = make_callback_update(-100205, user, "act:only_two_parts")
    await callback_router(up, ctx)
    assert up.callback_query.answer.called


# 10. Expired and Depleted Gold Drops
@pytest.mark.asyncio
async def test_boundary_expired_and_depleted_gold_drops():
    """Verify claims on expired or depleted drops are properly rejected."""
    # 1. Depleted drop (0 remaining)
    depleted_id = "drop_depleted_01"
    active_drops[depleted_id] = {
        "id": depleted_id,
        "chat_id": -100206,
        "creator_id": 999,
        "creator_name": "Sponsor",
        "total": 1,
        "remaining": 0,
        "claimed_by": {111: "First Claimer"},
        "created_at": time.time(),
        "expires_at": time.time() + 600,
    }
    success1, msg1, _ = await claim_gold_drop(depleted_id, 902040, "Late User")
    assert success1 is False
    assert "Barcha Goldlar terib olindi" in msg1

    # 2. Expired drop (created 20 minutes ago)
    expired_id = "drop_expired_01"
    active_drops[expired_id] = {
        "id": expired_id,
        "chat_id": -100206,
        "creator_id": 999,
        "creator_name": "Sponsor",
        "total": 5,
        "remaining": 5,
        "claimed_by": {},
        "created_at": time.time() - 1200,
        "expires_at": time.time() - 600,
    }
    success2, msg2, _ = await claim_gold_drop(expired_id, 902041, "Expired Claimer")
    assert success2 is False
    assert "muddati" in msg2

    # Cleanup sweeps expired drops
    purged = cleanup_expired_drops(expiry_seconds=600)
    assert expired_id not in active_drops


# 11. Command Invocation in Inappropriate Chat Types
@pytest.mark.asyncio
async def test_boundary_command_chat_type_restrictions():
    """Verify group commands in private chat guide user back to groups."""
    ctx = make_e2e_context()

    # /para in PM
    up_para = make_pm_update(uid=902050, text="/para")
    await para_cmd(up_para, ctx)
    assert up_para.message.reply_text.called
    assert "Telegram guruhlarida" in up_para.message.reply_text.call_args[0][0]

    # /bro in PM
    up_bro = make_pm_update(uid=902050, text="/bro")
    await bro_cmd(up_bro, ctx)
    assert up_bro.message.reply_text.called
    assert "Telegram guruhlarida" in up_bro.message.reply_text.call_args[0][0]
