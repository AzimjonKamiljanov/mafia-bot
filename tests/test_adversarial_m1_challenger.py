import asyncio
import os
import subprocess
import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram.error import TelegramError

from core.engine import (
    games,
    lobbies,
    cancel_game_timer,
    cancel_lobby_timer,
    abort_lobby,
    abort_game,
)
from handlers.callbacks import callback_router
from database.models import is_admin


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    ctx.bot.unpin_chat_message = AsyncMock()
    ctx.bot.get_chat_member = AsyncMock()
    return ctx


# ============================================================================
# 1. Adversarial Tests: Self-Cancellation Guards on Timers
# ============================================================================

class TestTimerSelfCancellationGuards:
    @pytest.mark.asyncio
    async def test_lobby_timer_self_cancellation_guard(self):
        """A running lobby timer task calling cancel_lobby_timer must NOT cancel itself."""
        executed = False
        lobby = {}

        async def fake_lobby_timer(lobby_ref):
            nonlocal executed
            # Simulate timer invoking cancellation during normal execution/timeout
            cancel_lobby_timer(lobby_ref)
            await asyncio.sleep(0.01)
            executed = True

        task = asyncio.create_task(fake_lobby_timer(lobby))
        lobby["_timer_task"] = task
        await task

        assert executed is True, "cancel_lobby_timer must not cancel the currently running task"
        assert not task.cancelled(), "Task should complete cleanly without being cancelled"
        assert "_timer_task" not in lobby, "Timer task reference should be removed from lobby"

    @pytest.mark.asyncio
    async def test_game_timer_self_cancellation_guard(self):
        """A running phase timer task calling cancel_game_timer must NOT cancel itself."""
        executed = False
        game = {"chat": -100100}

        async def fake_game_timer(game_ref):
            nonlocal executed
            cancel_game_timer(game_ref)
            await asyncio.sleep(0.01)
            executed = True

        task = asyncio.create_task(fake_game_timer(game))
        game["_timer_task"] = task
        await task

        assert executed is True, "cancel_game_timer must not cancel the currently running phase timer"
        assert not task.cancelled()
        assert "_timer_task" not in game

    @pytest.mark.asyncio
    async def test_king_timer_self_cancellation_guard(self):
        """A running king timer task calling cancel_game_timer must NOT cancel itself."""
        executed = False
        game = {"chat": -100101}

        async def fake_king_timer(game_ref):
            nonlocal executed
            cancel_game_timer(game_ref)
            await asyncio.sleep(0.01)
            executed = True

        task = asyncio.create_task(fake_king_timer(game))
        game["_king_timer_task"] = task
        await task

        assert executed is True, "cancel_game_timer must not cancel the currently running king timer"
        assert not task.cancelled()
        assert "_king_timer_task" not in game

    @pytest.mark.asyncio
    async def test_dual_timer_cross_cancellation_behavior(self):
        """When king timer runs and cancels game timer, phase timer is cancelled but king timer survives."""
        phase_timer_cancelled = False
        king_timer_completed = False
        game = {"chat": -100102}

        async def fake_phase_timer():
            nonlocal phase_timer_cancelled
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                phase_timer_cancelled = True
                raise

        async def fake_king_timer(game_ref):
            nonlocal king_timer_completed
            cancel_game_timer(game_ref)
            await asyncio.sleep(0.01)
            king_timer_completed = True

        phase_task = asyncio.create_task(fake_phase_timer())
        game["_timer_task"] = phase_task

        king_task = asyncio.create_task(fake_king_timer(game))
        game["_king_timer_task"] = king_task

        await king_task
        with pytest.raises(asyncio.CancelledError):
            await phase_task

        assert king_timer_completed is True
        assert phase_timer_cancelled is True

    @pytest.mark.asyncio
    async def test_external_caller_cancels_all_timers(self):
        """An external caller calling cancel_game_timer cancels both attached tasks."""
        game = {"chat": -100103}
        task1 = asyncio.create_task(asyncio.sleep(10))
        task2 = asyncio.create_task(asyncio.sleep(10))
        game["_timer_task"] = task1
        game["_king_timer_task"] = task2

        cancel_game_timer(game)

        # Cancellation is delivered on next event loop tick
        with pytest.raises(asyncio.CancelledError):
            await task1
        with pytest.raises(asyncio.CancelledError):
            await task2

        assert task1.cancelled()
        assert task2.cancelled()
        assert "_timer_task" not in game
        assert "_king_timer_task" not in game

    @pytest.mark.asyncio
    async def test_timer_cancellation_with_none_and_empty_inputs(self):
        """Timer cancellation functions must fail safe when called with None or empty dict."""
        cancel_game_timer(None)
        cancel_lobby_timer(None)
        cancel_game_timer({})
        cancel_lobby_timer({})
        # Should complete without error


# ============================================================================
# 2. Adversarial Tests: Spoofed Callback Queries
# ============================================================================

class TestSpoofedCallbackQueries:
    @pytest.mark.asyncio
    async def test_spoofed_non_king_cannot_invoke_king_kill(self, mock_context):
        chat_id = -100201
        king_uid = 10001
        attacker_uid = 10002
        imposter_uid = 99999

        game = {
            "chat": chat_id,
            "phase": "night",
            "players": [king_uid, attacker_uid, imposter_uid],
            "alive": {king_uid: True, attacker_uid: True, imposter_uid: True},
            "roles": {king_uid: "Qirol", attacker_uid: "Qotil", imposter_uid: "Fuqaro"},
            "_waiting_king": True,
        }
        games[chat_id] = game

        update = MagicMock()
        update.effective_chat.id = imposter_uid
        update.effective_user.id = imposter_uid
        update.callback_query = MagicMock()
        update.callback_query.data = f"king_kill:{king_uid}:{attacker_uid}"
        update.callback_query.from_user.id = imposter_uid
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Bu tugma siz uchun emas! Faqat Qirol hukm chiqara oladi" in args[0]
        assert kwargs.get("show_alert") is True
        # Ensure game state not altered
        assert game.get("_waiting_king") is True

    @pytest.mark.asyncio
    async def test_spoofed_non_king_cannot_invoke_king_forgive(self, mock_context):
        chat_id = -100202
        king_uid = 10003
        attacker_uid = 10004
        imposter_uid = 99998

        game = {
            "chat": chat_id,
            "phase": "night",
            "players": [king_uid, attacker_uid, imposter_uid],
            "alive": {king_uid: True, attacker_uid: True, imposter_uid: True},
            "roles": {king_uid: "Qirol", attacker_uid: "Qotil", imposter_uid: "Fuqaro"},
            "_waiting_king": True,
        }
        games[chat_id] = game

        update = MagicMock()
        update.effective_chat.id = imposter_uid
        update.effective_user.id = imposter_uid
        update.callback_query = MagicMock()
        update.callback_query.data = f"king_forgive:{king_uid}:{attacker_uid}"
        update.callback_query.from_user.id = imposter_uid
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Bu tugma siz uchun emas! Faqat Qirol hukm chiqara oladi" in args[0]
        assert kwargs.get("show_alert") is True
        assert game.get("_waiting_king") is True

    @pytest.mark.asyncio
    async def test_dead_king_cannot_invoke_decision(self, mock_context):
        chat_id = -100203
        king_uid = 10005
        attacker_uid = 10006

        game = {
            "chat": chat_id,
            "phase": "night",
            "players": [king_uid, attacker_uid],
            "alive": {king_uid: False, attacker_uid: True},
            "roles": {king_uid: "Qirol", attacker_uid: "Qotil"},
            "_waiting_king": True,
        }
        games[chat_id] = game

        update = MagicMock()
        update.effective_chat.id = king_uid
        update.effective_user.id = king_uid
        update.callback_query = MagicMock()
        update.callback_query.data = f"king_kill:{king_uid}:{attacker_uid}"
        update.callback_query.from_user.id = king_uid
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Halok bo'lgan Qirol qaror qabul qila olmaydi" in args[0]
        assert kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_dead_attacker_cannot_be_targeted(self, mock_context):
        chat_id = -100204
        king_uid = 10007
        attacker_uid = 10008

        game = {
            "chat": chat_id,
            "phase": "night",
            "players": [king_uid, attacker_uid],
            "alive": {king_uid: True, attacker_uid: False},
            "roles": {king_uid: "Qirol", attacker_uid: "Qotil"},
            "_waiting_king": True,
        }
        games[chat_id] = game

        update = MagicMock()
        update.effective_chat.id = king_uid
        update.effective_user.id = king_uid
        update.callback_query = MagicMock()
        update.callback_query.data = f"king_forgive:{king_uid}:{attacker_uid}"
        update.callback_query.from_user.id = king_uid
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Hujumchi allaqachon o'yinda yo'q yoki vafot etgan" in args[0]
        assert kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_missing_attacker_cannot_be_targeted(self, mock_context):
        chat_id = -100205
        king_uid = 10009
        attacker_uid = 10010  # Not in game["players"]

        game = {
            "chat": chat_id,
            "phase": "night",
            "players": [king_uid],
            "alive": {king_uid: True},
            "roles": {king_uid: "Qirol"},
            "_waiting_king": True,
        }
        games[chat_id] = game

        update = MagicMock()
        update.effective_chat.id = king_uid
        update.effective_user.id = king_uid
        update.callback_query = MagicMock()
        update.callback_query.data = f"king_kill:{king_uid}:{attacker_uid}"
        update.callback_query.from_user.id = king_uid
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Hujumchi allaqachon o'yinda yo'q yoki vafot etgan" in args[0]
        assert kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_spectator_cannot_invoke_day_to_vote(self, mock_context):
        chat_id = -100206
        player1 = 20001
        spectator = 90001

        game = {
            "chat": chat_id,
            "phase": "day",
            "players": [player1],
            "alive": {player1: True},
        }
        games[chat_id] = game

        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.id = spectator
        update.callback_query = MagicMock()
        update.callback_query.data = f"day_to_vote:{chat_id}"
        update.callback_query.from_user.id = spectator
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Siz bu o'yinda qatnashmayapsiz" in args[0]
        assert kwargs.get("show_alert") is True
        assert game["phase"] == "day"

    @pytest.mark.asyncio
    async def test_dead_player_cannot_invoke_day_to_vote(self, mock_context):
        chat_id = -100207
        living_player = 20002
        dead_player = 20003

        game = {
            "chat": chat_id,
            "phase": "day",
            "players": [living_player, dead_player],
            "alive": {living_player: True, dead_player: False},
        }
        games[chat_id] = game

        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.id = dead_player
        update.callback_query = MagicMock()
        update.callback_query.data = f"day_to_vote:{chat_id}"
        update.callback_query.from_user.id = dead_player
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Halok bo'lganlar ovoz berishga o'tkaza olmaydi" in args[0]
        assert kwargs.get("show_alert") is True
        assert game["phase"] == "day"

    @pytest.mark.asyncio
    async def test_unauthorized_member_cannot_invoke_lobby_stop(self, mock_context):
        chat_id = -100208
        regular_user = 30001

        lobbies[chat_id] = {"open": True, "players": [regular_user]}

        mock_member = MagicMock()
        mock_member.status = "member"
        mock_context.bot.get_chat_member.return_value = mock_member

        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.id = regular_user
        update.callback_query = MagicMock()
        update.callback_query.data = f"lobby_stop:{chat_id}"
        update.callback_query.from_user.id = regular_user
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Faqat guruh adminlari to'xtata oladi" in args[0]
        assert kwargs.get("show_alert") is True
        assert chat_id in lobbies, "Lobby must NOT be terminated by regular member"

    @pytest.mark.asyncio
    async def test_lobby_stop_fails_closed_when_admin_check_raises_error(self, mock_context):
        chat_id = -100209
        user_id = 30002

        lobbies[chat_id] = {"open": True, "players": [user_id]}
        mock_context.bot.get_chat_member.side_effect = TelegramError("Chat not found")

        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.id = user_id
        update.callback_query = MagicMock()
        update.callback_query.data = f"lobby_stop:{chat_id}"
        update.callback_query.from_user.id = user_id
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Guruh adminlik huquqini tekshirib bo'lmadi. Ruxsat berilmadi" in args[0]
        assert kwargs.get("show_alert") is True
        assert chat_id in lobbies, "Lobby must NOT be terminated when admin check fails"

    @pytest.mark.asyncio
    async def test_lobby_stop_by_authorized_admin_unpins_and_stops(self, mock_context):
        chat_id = -100210
        admin_id = 30003
        pinned_msg_id = 8877

        lobbies[chat_id] = {
            "open": True,
            "players": [admin_id],
            "pinned_message_id": pinned_msg_id,
        }

        mock_member = MagicMock()
        mock_member.status = "administrator"
        mock_context.bot.get_chat_member.return_value = mock_member

        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.id = admin_id
        update.callback_query = MagicMock()
        update.callback_query.data = f"lobby_stop:{chat_id}"
        update.callback_query.from_user.id = admin_id
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        await callback_router(update, mock_context)

        assert chat_id not in lobbies
        mock_context.bot.unpin_chat_message.assert_called_once_with(
            chat_id=chat_id, message_id=pinned_msg_id
        )
        update.callback_query.answer.assert_called_once_with("🛑 To'xtatildi.")


# ============================================================================
# 3. Adversarial Tests: Callback Fallback and Payload Robustness
# ============================================================================

class TestCallbackPayloadFallbacks:
    @pytest.mark.asyncio
    async def test_unrecognized_payload_fallback(self, mock_context):
        update = MagicMock()
        update.effective_chat.id = 50001
        update.effective_user.id = 50001
        update.callback_query = MagicMock()
        update.callback_query.data = "unknown_callback_payload_xyz"
        update.callback_query.from_user.id = 50001
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Ushbu tugma muddati o'tgan yoki faol emas" in args[0]
        assert kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_empty_callback_payload_fallback(self, mock_context):
        update = MagicMock()
        update.effective_chat.id = 50002
        update.effective_user.id = 50002
        update.callback_query = MagicMock()
        update.callback_query.data = ""
        update.callback_query.from_user.id = 50002
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Ushbu tugma muddati o'tgan yoki faol emas" in args[0]
        assert kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_unrecognized_lobby_subaction_fallback(self, mock_context):
        """When data starts with lobby_ but action is unrecognized, it falls back gracefully."""
        update = MagicMock()
        update.effective_chat.id = 50003
        update.effective_user.id = 50003
        update.callback_query = MagicMock()
        update.callback_query.data = "lobby_unknown_bogus_action:12345"
        update.callback_query.from_user.id = 50003
        update.callback_query.answer = AsyncMock()

        await callback_router(update, mock_context)

        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        assert "Ushbu tugma muddati o'tgan yoki faol emas" in args[0]
        assert kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_corrupted_payload_causes_parsing_exception(self, mock_context):
        """M2 Hardening: Corrupted payloads with valid prefixes (e.g. non-integer arguments
        or truncated parts) must be handled gracefully without unhandled ValueError or IndexError.
        """
        corrupted_cases = [
            "lobby_stop:not_a_number",
            "lobby_stop:",
            "king_kill:notanumber:999",
            "king_kill:999",
            "king_forgive:notanumber:999",
            "king_forgive:999",
            "day_to_vote:not_a_number",
            "day_to_vote:",
            "vote:notanumber:target",
            "vote:123",
            "act:kill:notanumber",
            "act:kill",
            "act:",
        ]

        for idx, payload in enumerate(corrupted_cases):
            uid = 60000 + idx
            update = MagicMock()
            update.effective_chat.id = uid
            update.effective_user.id = uid
            update.callback_query = MagicMock()
            update.callback_query.data = payload
            update.callback_query.from_user.id = uid
            update.callback_query.answer = AsyncMock()

            # Must execute without raising exception
            await callback_router(update, mock_context)
            assert update.callback_query.answer.called


# ============================================================================
# 4. Adversarial Tests: Non-Numeric ADMIN_ID Resilience
# ============================================================================

class TestNonNumericAdminIdResilience:
    @pytest.mark.parametrize("invalid_id", [
        "@admin",
        "superadmin",
        "   ",
        "",
        "-12345",
        "0xABC",
        "123abc456",
        "None",
        "null",
        "false",
    ])
    def test_subprocess_with_invalid_admin_id(self, invalid_id):
        """Verify python runtime boots cleanly and parses ADMIN_ID as 0 when non-numeric."""
        env = os.environ.copy()
        env["BOT_TOKEN"] = "12345:TEST_TOKEN"
        env["ADMIN_ID"] = invalid_id

        cmd = [
            "python3",
            "-c",
            "import config; assert config.ADMIN_ID == 0, f'Expected 0, got {config.ADMIN_ID}'"
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert res.returncode == 0, f"Failed for ADMIN_ID='{invalid_id}': {res.stderr}"

    def test_subprocess_with_valid_admin_id(self):
        """Verify positive digit ADMIN_ID parses correctly."""
        env = os.environ.copy()
        env["BOT_TOKEN"] = "12345:TEST_TOKEN"
        env["ADMIN_ID"] = "76543210"

        cmd = [
            "python3",
            "-c",
            "import config; assert config.ADMIN_ID == 76543210; assert 76543210 in config.ADMIN_IDS"
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert res.returncode == 0, f"Valid ADMIN_ID parsing failed: {res.stderr}"

    def test_admin_ids_list_filtering(self):
        """Verify non-numeric entries in ADMIN_IDS are filtered out while valid numeric entries survive."""
        env = os.environ.copy()
        env["BOT_TOKEN"] = "12345:TEST_TOKEN"
        env["ADMIN_IDS"] = "@admin, 112233, invalid_string, -4455, 667788, ,   "
        env["ADMIN_ID"] = "999999"

        cmd = [
            "python3",
            "-c",
            "import config; assert config.ADMIN_IDS == {112233, 667788, 999999}, f'Got {config.ADMIN_IDS}'"
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert res.returncode == 0, f"ADMIN_IDS filtering failed: {res.stderr}"

    def test_is_admin_safe_evaluation(self):
        """Verify is_admin never grants privileges to 0, negative, or invalid types."""
        assert is_admin(0) is False
        assert is_admin(-1) is False
        assert is_admin(-999999) is False
        assert is_admin("0") is False
        assert is_admin("invalid_string") is False
        assert is_admin(None) is False
