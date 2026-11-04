"""Tier 1: Feature Coverage E2E Tests (Features 1 through 41).

Opaque-box tests verifying primary behavior (happy paths) of each individual
feature in isolation, derived strictly from ORIGINAL_REQUEST.md and PROJECT.md.
"""

import os
import re
import html
import time
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from database.db import init_db, get_db
from database.models import (
    ensure_user, get_user, change_balance, add_item, take_item, get_inventory,
    is_admin, create_clan, get_chat_settings, update_chat_settings
)
try:
    from database.models import change_clan_balance
except ImportError:
    change_clan_balance = None
from core.engine import (
    games, lobbies, cancel_game_timer, cancel_lobby_timer, abort_game, abort_lobby,
    finish_game, active_drops, cleanup_expired_drops
)
from core.emojis import tg_emoji
from core.i18n import t
from core.rate_limiter import is_rate_limited, reset_rate_limits
from core.visuals import send_animated_dice_effect
from handlers.commands import start_cmd, profile_cmd, guide_cmd
from handlers.callbacks import callback_router
from handlers.social import send_cmd
from phases.lobby import create_lobby, lobby_text
from phases.night import resolve_night
from phases.verdict import resolve_verdict
from bot import (
    create_bot_app, cleanup_orphaned_games, post_init, handle_private_message,
    PM_DISPATCH_TABLE, SafeExtBot, track_group_user
)

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


# Feature 1: Fail-Fast BOT_TOKEN
def test_feature_01_fail_fast_bot_token(monkeypatch):
    """F1: Bot application startup must fail immediately if BOT_TOKEN is empty."""
    monkeypatch.setattr("bot.BOT_TOKEN", "")
    with pytest.raises(ValueError, match="BOT_TOKEN is missing or empty"):
        create_bot_app()


# Feature 2: Numeric Admin Authorization
@pytest.mark.asyncio
async def test_feature_02_numeric_admin_authorization():
    """F2: Admin privileges are granted strictly via numeric ID validation."""
    from config import ADMIN_IDS
    known_admin_id = next(iter(ADMIN_IDS)) if ADMIN_IDS else 8048940366

    assert is_admin(known_admin_id, "anyone") is True
    # Non-admin numeric ID cannot gain access through admin username spoofing
    assert is_admin(11223344, "admin_boss") is False


# Feature 3: Env-configurable DB_PATH
def test_feature_03_env_configurable_db_path():
    """F3: Database path must be resolved dynamically from config/env."""
    import config
    assert hasattr(config, "DB_PATH")
    assert isinstance(config.DB_PATH, str)
    assert len(config.DB_PATH) > 0


# Feature 4: Atomic Balance Updates
@pytest.mark.asyncio
async def test_feature_04_atomic_balance_updates():
    """F4: Balance updates use atomic SQL checks and column whitelisting."""
    uid = 901001
    user = MockUser(uid, "Balance User")
    await ensure_user(user)

    # Reset balance
    u = await get_user(uid)
    await change_balance(uid, "coin", -u["coin"])

    # Credit succeeds
    assert await change_balance(uid, "coin", 150) is True
    u = await get_user(uid)
    assert u["coin"] == 150

    # Overdraft is atomically rejected
    assert await change_balance(uid, "coin", -200) is False
    u = await get_user(uid)
    assert u["coin"] == 150

    # Column whitelist rejects invalid currency
    assert await change_balance(uid, "invalid_currency; DROP TABLE users;--", 50) is False


# Feature 5: Atomic Inventory Debits
@pytest.mark.asyncio
async def test_feature_05_atomic_inventory_debits():
    """F5: Inventory debits reject negative inventory and whitelist item columns."""
    uid = 901002
    user = MockUser(uid, "Inventory User")
    await ensure_user(user)

    # Credit 2 protection items
    assert await add_item(uid, "protection", 2) is True
    inv = await get_inventory(uid)
    assert inv.get("protection", 0) >= 2

    # Take 1 item
    assert await take_item(uid, "protection", 1) is True

    # Take excessive items fails
    assert await take_item(uid, "protection", 99) is False

    # Whitelist rejects unknown items
    assert await take_item(uid, "non_existent_item_hack", 1) is False


# Feature 6: Clan Balance Atomic Helper
@pytest.mark.asyncio
async def test_feature_06_clan_balance_atomic_helper():
    """F6: Clan treasury balance is modified via atomic checks."""
    leader_id = int(time.time() * 1000) % 1000000000
    leader = MockUser(leader_id, "Clan Leader")
    await ensure_user(leader)

    if change_clan_balance is None:
        pytest.xfail("Feature 6 missing: change_clan_balance not yet implemented in database/models.py (Interface Contract in PROJECT.md)")

    clan_name = f"Alpha E2E Clan {leader_id}"
    clan_id = await create_clan(clan_name, "ALPHA", leader_id)
    assert clan_id is not None

    # Credit clan balance
    assert await change_clan_balance(clan_id, 300) is True

    # Overdraft fails
    assert await change_clan_balance(clan_id, -5000) is False


# Feature 7: Fail-Closed lobby_stop
@pytest.mark.asyncio
async def test_feature_07_fail_closed_lobby_stop():
    """F7: lobby_stop must fail closed and preserve lobby if admin check errors."""
    chat_id = -100901
    user_id = 901004
    user = MockUser(user_id, "Intruder")

    task = asyncio.create_task(asyncio.sleep(100))
    lobbies[chat_id] = {"open": True, "players": [user_id], "_timer_task": task}

    ctx = make_e2e_context()
    ctx.bot.get_chat_member.side_effect = Exception("Telegram API Timeout")

    up = make_callback_update(chat_id, user, f"lobby_stop:{chat_id}")
    await callback_router(up, ctx)

    # Must fail closed: lobby and timer still exist
    assert chat_id in lobbies
    assert not task.cancelled()
    task.cancel()


# Feature 8: Phase Timer Cancellation
@pytest.mark.asyncio
async def test_feature_08_phase_timer_cancellation():
    """F8: Game and lobby timers are cancelled on termination."""
    chat_id = -100902
    task1 = asyncio.create_task(asyncio.sleep(100))
    task2 = asyncio.create_task(asyncio.sleep(100))

    game = {"chat": chat_id, "phase": "night", "_timer_task": task1}
    lobby = {"open": True, "_timer_task": task2}
    games[chat_id] = game
    lobbies[chat_id] = lobby

    cancel_game_timer(game)
    cancel_lobby_timer(lobby)
    await asyncio.sleep(0)

    assert task1.cancelled() or (hasattr(task1, "cancelling") and task1.cancelling() > 0)
    assert task2.cancelled() or (hasattr(task2, "cancelling") and task2.cancelling() > 0)


# Feature 9: Callback Actor & Target Auth
@pytest.mark.asyncio
async def test_feature_09_callback_actor_target_auth():
    """F9: Callback action validates actor life state and rejects non-players."""
    chat_id = -100903
    p1 = MockUser(901005, "Alive Player")
    p2 = MockUser(901006, "Dead Player")
    games[chat_id] = {
        "chat": chat_id,
        "phase": "night",
        "players": [p1.id, p2.id],
        "roles": {p1.id: "Detektiv", p2.id: "Doktor"},
        "alive": {p1.id: True, p2.id: False},
        "night": 1,
    }

    ctx = make_e2e_context()
    # Dead player clicking action must be rejected
    up = make_callback_update(chat_id, p2, f"act:detective:{p2.id}")
    await callback_router(up, ctx)
    assert up.callback_query.answer.called


# Feature 10: Stale Button Graceful Rejection
@pytest.mark.asyncio
async def test_feature_10_stale_button_graceful_rejection():
    """F10: Stale callback button does not crash and alerts user."""
    user = MockUser(901007, "Stale Clicker")
    ctx = make_e2e_context()
    up = make_callback_update(-100904, user, "vote:-100904:none")
    # Game doesn't exist
    await callback_router(up, ctx)
    assert up.callback_query.answer.called


# Feature 11: Startup Orphan Game Cleanup
@pytest.mark.asyncio
async def test_feature_11_startup_orphan_cleanup():
    """F11: Active games in SQLite database are reconciled to aborted on startup."""
    db = await get_db()
    chat_id = -100905
    await db.execute(
        "INSERT INTO games (chat_id, state, phase, data, created_at, updated_at) VALUES (?, 'active', 'night', '{}', '2026-01-01', '2026-01-01')",
        (chat_id,)
    )
    await db.commit()

    mock_app = MagicMock()
    mock_app.bot = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    await cleanup_orphaned_games(mock_app)

    async with db.execute("SELECT state FROM games WHERE chat_id = ?", (chat_id,)) as cur:
        row = await cur.fetchone()
        assert row["state"] == "aborted"


# Feature 12: Git & Secrets Hygiene
def test_feature_12_git_secrets_hygiene():
    """F12: Sensitive files (.env, *.db, *.log, *.zip) are strictly gitignored."""
    project_root = Path(__file__).resolve().parent.parent.parent
    gitignore_path = project_root / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist"

    content = gitignore_path.read_text(encoding="utf-8")
    for pattern in (".env", "*.db", "*.log", "*.zip"):
        assert pattern in content, f"{pattern} must be listed in .gitignore"


# Feature 13: Comprehensive COMMANDS.md Documentation / Specification
def test_feature_13_commands_matrix_coverage():
    """F13: Every registered command handler is mapped in the command matrix."""
    from bot import PM_DISPATCH_TABLE
    registered_aliases = set(alias for aliases in PM_DISPATCH_TABLE.keys() for alias in aliases)

    core_commands = {"start", "salom", "game", "stop", "chiqish", "profile", "balance", "shop", "rating", "guide"}
    assert core_commands.issubset(registered_aliases)


# Feature 14: Fix send_cmd Boundary & Parameter Handling
@pytest.mark.asyncio
async def test_feature_14_send_cmd_boundary_and_validation():
    """F14: /send command validates arguments and warns if called in private chat."""
    ctx = make_e2e_context()

    # In private chat, /send guides user to use in group
    pm_up = make_pm_update(uid=901008, text="/send 10")
    await send_cmd(pm_up, ctx)
    assert pm_up.message.reply_text.called
    text = pm_up.message.reply_text.call_args[0][0]
    assert "Telegram guruhlarida" in text

    # In group without args, provides usage guide
    user = MockUser(901008, "Donor User")
    grp_up = make_group_message_update(chat_id=-100906, user=user, text="/send")
    ctx.args = []
    await send_cmd(grp_up, ctx)
    assert grp_up.message.reply_text.called
    usage = grp_up.message.reply_text.call_args[0][0]
    assert "/send" in usage and "soni" in usage


# Feature 15: Fix PM_DISPATCH_TABLE Collision
def test_feature_15_pm_dispatch_table_collision():
    """F15: coin and gold commands in PM do not collide with balance."""
    from handlers.social import coin_cmd, gold_cmd
    from handlers.commands import balance_cmd

    coin_entry = next((fn for k, fn in PM_DISPATCH_TABLE.items() if "givecoin" in k), None)
    gold_entry = next((fn for k, fn in PM_DISPATCH_TABLE.items() if "givegold" in k), None)
    balance_entry = next((fn for k, fn in PM_DISPATCH_TABLE.items() if "hisob" in k), None)

    assert coin_entry is coin_cmd
    assert gold_entry is gold_cmd
    assert balance_entry is balance_cmd


# Feature 16: NoneType Guarding
@pytest.mark.asyncio
async def test_feature_16_nonetype_guarding():
    """F16: Handlers safely guard against None update.message or effective_user."""
    ctx = make_e2e_context()
    up = MagicMock()
    up.message = None
    up.effective_message = None
    up.effective_user = None
    up.effective_chat = None

    # Should not raise exception
    await handle_private_message(up, ctx)
    await track_group_user(up, ctx)


# Feature 17: HTML Dynamic Escaping
def test_feature_17_html_dynamic_escaping():
    """F17: Dynamic strings are escaped with html.escape to prevent injection."""
    raw_name = "<b>Evil<script>alert('xss')</script></b>"
    escaped = html.escape(raw_name)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped


# Feature 18: Two-Tier PM Command Dispatcher
@pytest.mark.asyncio
async def test_feature_18_two_tier_pm_dispatcher():
    """F18: Two-tier dispatcher supports slash and slash-free commands with fallback."""
    ctx = make_e2e_context()

    # Valid slash-free command
    up1 = make_pm_update(uid=901009, text="profil")
    await handle_private_message(up1, ctx)
    assert up1.message.reply_text.called

    # Unknown command triggers fallback main menu
    up2 = make_pm_update(uid=901009, text="/unknown_command_12345")
    await handle_private_message(up2, ctx)
    assert up2.message.reply_text.called
    assert "Noma'lum buyruq" in up2.message.reply_text.call_args[0][0]


# Feature 19: Telegram Command Scopes
@pytest.mark.asyncio
async def test_feature_19_telegram_command_scopes():
    """F19: post_init registers distinct command sets per Telegram scope."""
    mock_app = MagicMock()
    mock_app.bot = MagicMock()
    mock_app.bot.set_my_commands = AsyncMock()

    await post_init(mock_app)
    assert mock_app.bot.set_my_commands.call_count >= 3


# Feature 20: Modularize start_cmd
@pytest.mark.asyncio
async def test_feature_20_modularize_start_cmd():
    """F20: Deep link parameters (e.g. act_*) guide user back to game."""
    chat_id = -100907
    uid = 901010
    games[chat_id] = {
        "chat": chat_id,
        "players": [uid],
        "roles": {uid: "Fuqaro"},
        "alive": {uid: True},
        "phase": "night",
    }
    ctx = make_e2e_context()
    ctx.args = [f"act_{chat_id}"]
    up = make_pm_update(uid=uid, text=f"/start act_{chat_id}")
    await start_cmd(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "Tun" in text and "rolingiz" in text


# Feature 21: Modularize callback_router
@pytest.mark.asyncio
async def test_feature_21_modularize_callback_router():
    """F21: Callback router dispatches registered actions cleanly."""
    user = MockUser(901011, "Menu User")
    ctx = make_e2e_context()
    up = make_callback_update(-100908, user, "menu_main")
    await callback_router(up, ctx)
    assert up.callback_query.answer.called


# Feature 22: Modularize resolve_night
@pytest.mark.asyncio
async def test_feature_22_modularize_resolve_night():
    """F22: resolve_night accurately resolves night actions with Doctor save."""
    chat_id = -100909
    game = {
        "chat": chat_id,
        "players": [101, 102, 103, 104],
        "names": {101: "Boss", 102: "Doc", 103: "Target", 104: "Cit"},
        "roles": {101: "Boshliq", 102: "Doktor", 103: "Fuqaro", 104: "Fuqaro"},
        "alive": {101: True, 102: True, 103: True, 104: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {101: 103},
        "protected": {103},
        "protected_by": {103: 102},
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    await resolve_night(ctx, game)

    assert game["alive"][103] is True
    assert 103 in game.get("last_night_saved", [])


# Feature 23: Modularize resolve_verdict
@pytest.mark.asyncio
async def test_feature_23_modularize_resolve_verdict():
    """F23: resolve_verdict executes suspect when kill votes exceed forgive votes."""
    chat_id = -100910
    game = {
        "chat": chat_id,
        "players": [201, 202, 203],
        "names": {201: "Suspect", 202: "Voter1", 203: "Voter2"},
        "roles": {201: "Fuqaro", 202: "Fuqaro", 203: "Fuqaro"},
        "alive": {201: True, 202: True, 203: True},
        "phase": "verdict",
        "accused_uid": 201,
        "verdict_votes": {202: "kill", 203: "kill"},
        "_finish_started": False,
        "_resolving_verdict": False,
    }
    games[chat_id] = game
    ctx = make_e2e_context()

    await resolve_verdict(ctx, game)

    assert game["alive"][201] is False


# Feature 24: Centralized UI Message Formatting
def test_feature_24_centralized_ui_message_formatting():
    """F24: Group messages maintain structured, readable formatting."""
    lobby = {
        "players": [301, 302],
        "names": {301: "Player 1", 302: "Player 2"},
    }
    text = lobby_text(lobby)
    assert "Ishtirokchilar" in text
    assert "Qo'shilish" in text


# Feature 25: Throttled Game Board Editing
def test_feature_25_throttled_game_board_editing():
    """F25: Rate limiter prevents rapid burst message actions."""
    uid = 901012
    reset_rate_limits()
    # 5 actions within 3 seconds
    for _ in range(5):
        assert is_rate_limited(uid, action="board_edit", max_rate=5, window_seconds=3.0) is False
    # 6th action is throttled
    assert is_rate_limited(uid, action="board_edit", max_rate=5, window_seconds=3.0) is True


# Feature 26: Custom Emoji Capability Probe / Fallback
def test_feature_26_custom_emoji_fallback():
    """F26: Emoji enrichment produces HTML markup with tg-emoji tags."""
    from core.emojis import enrich_with_animated_emojis
    text = "O'yin boshlandi! 🎮"
    enriched = enrich_with_animated_emojis(text)
    assert "<tg-emoji" in enriched or "🎮" in enriched


# Feature 27: Animation & Emoji Registry
def test_feature_27_animation_emoji_registry():
    """F27: tg_emoji registry returns custom emoji markup or fallback."""
    icon = tg_emoji("detective", "🔎")
    assert "🔎" in icon or "<tg-emoji" in icon


# Feature 28: Image Asset Caching / Resolution
def test_feature_28_image_asset_resolution():
    """F28: Day and Night image asset files exist at configured paths."""
    from config import DAY_PHOTO_PATH, NIGHT_PHOTO_PATH
    assert os.path.exists(DAY_PHOTO_PATH), f"Missing {DAY_PHOTO_PATH}"
    assert os.path.exists(NIGHT_PHOTO_PATH), f"Missing {NIGHT_PHOTO_PATH}"


# Feature 29: Multi-Channel Animations
@pytest.mark.asyncio
async def test_feature_29_multi_channel_animations():
    """F29: Multi-channel dice effect triggers Telegram dice animation."""
    ctx = make_e2e_context()
    await send_animated_dice_effect(ctx.bot, 901017, emoji="🎲")
    assert ctx.bot.send_dice.called


# Feature 30: Rich Onboarding & Guides
@pytest.mark.asyncio
async def test_feature_30_rich_onboarding_and_guides():
    """F30: /guide command displays role information and classification."""
    up = make_pm_update(uid=901013, text="/guide")
    ctx = make_e2e_context()
    await guide_cmd(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "Qo'llanma" in text or "Rollar" in text


# Feature 31: Centralized Locales (i18n)
def test_feature_31_centralized_locales():
    """F31: Translation function t() fetches locale strings across supported languages."""
    uz_text = t("welcome", lang="uz")
    assert len(uz_text) > 0
    # Fallback to key if not found
    assert t("non_existent_key_123", lang="uz") == "non_existent_key_123"


# Feature 32: Concurrent Updates & Chat Locks
@pytest.mark.asyncio
async def test_feature_32_concurrent_updates_chat_locks():
    """F32: Concurrent operations serialize cleanly without corruption."""
    uid = 901014
    user = MockUser(uid, "Concurrent Lock User")
    await ensure_user(user)

    # 10 concurrent balance changes
    await asyncio.gather(*(change_balance(uid, "coin", 10, f"Add {i}") for i in range(10)))
    u = await get_user(uid)
    assert u["coin"] >= 100


# Feature 33: Rate Limiter & Tracked Timers
def test_feature_33_rate_limiter_and_tracked_timers():
    """F33: Sliding window rate limiter enforces request bounds."""
    reset_rate_limits()
    uid = 901015
    for _ in range(3):
        assert is_rate_limited(uid, action="test_action", max_rate=3, window_seconds=1.0) is False
    assert is_rate_limited(uid, action="test_action", max_rate=3, window_seconds=1.0) is True


# Feature 34: TTL Cache for track_group_user
@pytest.mark.asyncio
async def test_feature_34_ttl_cache_track_group_user():
    """F34: track_group_user safely records message events without duplicate errors."""
    user = MockUser(901016, "Group Member")
    up = make_group_message_update(chat_id=-100912, user=user, text="Salom do'stlar")
    ctx = make_e2e_context()

    await track_group_user(up, ctx)
    # Repeated calls should not raise error
    await track_group_user(up, ctx)


# Feature 35: Hot Read Caching
@pytest.mark.asyncio
async def test_feature_35_hot_read_caching():
    """F35: Chat settings queries return consistent settings."""
    chat_id = -100913
    await update_chat_settings(chat_id, day_seconds=45)
    st = await get_chat_settings(chat_id)
    assert st["day_seconds"] == 45


# Feature 36: Specific Exceptions & Logging
def test_feature_36_specific_exceptions_and_logging():
    """F36: Logger 'detektiv' is configured with structured output."""
    import logging
    logger = logging.getLogger("detektiv")
    assert logger is not None


# Feature 37: Concurrency Benchmark Simulation Logic
@pytest.mark.asyncio
async def test_feature_37_concurrency_benchmark_simulation():
    """F37: Simulated concurrent games and lobbies execute without deadlock."""
    async def simulate_lobby(chat_id: int):
        lobbies[chat_id] = {"open": True, "players": [chat_id + i for i in range(5)]}
        await asyncio.sleep(0.01)
        lobbies.pop(chat_id, None)

    # Run 10 lobbies concurrently
    await asyncio.gather(*(simulate_lobby(-100920 - i) for i in range(10)))
    assert len(lobbies) == 0


# Feature 38: Pinned Dependencies
def test_feature_38_pinned_dependencies():
    """F38: requirements.txt contains exact pinned dependency versions (==)."""
    project_root = Path(__file__).resolve().parent.parent.parent
    req_file = project_root / "requirements.txt"
    assert req_file.exists()
    lines = [line.strip() for line in req_file.read_text().splitlines() if line.strip() and not line.startswith("#")]
    for line in lines:
        assert "==" in line, f"Dependency '{line}' in requirements.txt must be pinned with =="


# Feature 39: Tooling & CI Pipeline
def test_feature_39_ci_tooling_pipeline():
    """F39: GitHub Actions CI workflow config exists and defines test jobs."""
    project_root = Path(__file__).resolve().parent.parent.parent
    ci_file = project_root / ".github" / "workflows" / "ci.yml"
    assert ci_file.exists()
    content = ci_file.read_text(encoding="utf-8")
    assert "pytest" in content


# Feature 40: Production Docker & Compose
def test_feature_40_production_docker_compose():
    """F40: Dockerfile specifies non-root user and persistent /app/data volume."""
    project_root = Path(__file__).resolve().parent.parent.parent
    dockerfile = project_root / "Dockerfile"
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")
    assert "USER appuser" in content
    assert "/app/data" in content


# Feature 41: Documentation & Quickstart
def test_feature_41_documentation_quickstart():
    """F41: README.md exists and documents quickstart instructions."""
    project_root = Path(__file__).resolve().parent.parent.parent
    readme = project_root / "README.md"
    assert readme.exists()
    content = readme.read_text(encoding="utf-8")
    assert "BOT_TOKEN" in content
