import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from database.db import init_db
from database.models import ensure_user
from core.engine import games
from phases.night import resolve_night
from phases.verdict import resolve_verdict
from phases.voting import finish_voting
from handlers.commands import reveal_cmd
from handlers.social import para_cmd, bro_cmd, dpara_cmd, dbro_cmd
from handlers.callbacks import callback_router

class MockUser:
    def __init__(self, uid, full_name, username=""):
        self.id = uid
        self.full_name = full_name
        self.first_name = full_name
        self.username = username
        self.is_bot = False

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.send_photo = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_king_forgive_callback(mock_context):
    game = {
        "chat": -2001,
        "players": [40, 41, 42, 43],
        "names": {40: "King", 41: "Killer", 42: "Citizen", 43: "Doc"},
        "roles": {40: "Qirol", 41: "Boshliq", 42: "Fuqaro", 43: "Doktor"},
        "alive": {40: True, 41: True, 42: True, 43: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {41: 40},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-2001] = game

    # Night resolves and pauses for King
    await resolve_night(mock_context, game)
    assert game["_waiting_king"] is True
    assert 41 not in game.get("kill_targets", {})

    # King chooses to forgive
    mock_update = MagicMock()
    mock_q = MagicMock()
    mock_q.from_user = MockUser(40, "King")
    mock_q.data = "king_forgive:40:41"
    mock_q.answer = AsyncMock()
    mock_q.edit_message_text = AsyncMock()
    mock_update.callback_query = mock_q

    await callback_router(mock_update, mock_context)

    # Attacker 41 is spared, King 40 survived, phase transitioned to day
    assert game["_waiting_king"] is False
    assert game["alive"][41] is True, "Attacker should be alive after King forgiveness"
    assert game["alive"][40] is True, "King should be alive"
    assert game["phase"] == "day"

@pytest.mark.asyncio
async def test_king_kill_callback(mock_context):
    game = {
        "chat": -2002,
        "players": [50, 51, 52, 53, 54],
        "names": {50: "King", 51: "Boss", 52: "Citizen", 53: "Doc", 54: "Killer"},
        "roles": {50: "Qirol", 51: "Boshliq", 52: "Fuqaro", 53: "Doktor", 54: "Qotil"},
        "alive": {50: True, 51: True, 52: True, 53: True, 54: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {51: 50},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-2002] = game

    await resolve_night(mock_context, game)
    assert game["_waiting_king"] is True

    # King chooses to execute
    mock_update = MagicMock()
    mock_q = MagicMock()
    mock_q.from_user = MockUser(50, "King")
    mock_q.data = "king_kill:50:51"
    mock_q.answer = AsyncMock()
    mock_q.edit_message_text = AsyncMock()
    mock_update.callback_query = mock_q

    await callback_router(mock_update, mock_context)

    assert game["_waiting_king"] is False
    assert game["alive"][51] is False, "Attacker should be executed by King"
    assert game["alive"][50] is True, "King should be alive"
    assert 51 in game.get("last_night_deaths", [])
    assert game["phase"] == "day"

@pytest.mark.asyncio
async def test_king_attack_preserves_other_night_attacks(mock_context):
    # Boss attacks King, Maniak attacks Citizen
    game = {
        "chat": -2003,
        "players": [60, 61, 62, 63],
        "names": {60: "King", 61: "Boss", 62: "Maniak", 63: "Citizen"},
        "roles": {60: "Qirol", 61: "Boshliq", 62: "Maniak", 63: "Fuqaro"},
        "alive": {60: True, 61: True, 62: True, 63: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {61: 60},
        "maniac_targets": {62: 63},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-2003] = game

    await resolve_night(mock_context, game)
    assert game["_waiting_king"] is True

    # King forgives Boss
    mock_update = MagicMock()
    mock_q = MagicMock()
    mock_q.from_user = MockUser(60, "King")
    mock_q.data = "king_forgive:60:61"
    mock_q.answer = AsyncMock()
    mock_q.edit_message_text = AsyncMock()
    mock_update.callback_query = mock_q

    await callback_router(mock_update, mock_context)

    # Citizen 63 should still have died from Maniak 62!
    assert game["alive"][63] is False, "Citizen attacked by Maniak must die even if King paused resolution"
    assert 63 in game.get("last_night_deaths", [])
    assert game["alive"][60] is True, "King should be alive"
    assert game["alive"][61] is True, "Boss should be alive since King forgave"

@pytest.mark.asyncio
async def test_sud_amnistiyasi_pardons_accused(mock_context):
    game = {
        "chat": -2004,
        "players": [70, 71, 72],
        "names": {70: "Accused", 71: "Voter1", 72: "Voter2"},
        "roles": {70: "Fuqaro", 71: "Fuqaro", 72: "Fuqaro"},
        "alive": {70: True, 71: True, 72: True},
        "phase": "verdict",
        "accused_uid": 70,
        "verdict_votes": {71: "kill", 72: "kill"},
        "weather": {"id": "amnesty", "name": "Sud Amnistiyasi"},
        "_finish_started": False,
    }
    games[-2004] = game

    await resolve_verdict(mock_context, game)

    # Accused 70 must survive despite 2 kill votes
    assert game["alive"][70] is True, "Accused must survive under amnesty weather"
    assert game["phase"] == "night"

@pytest.mark.asyncio
async def test_mayor_reveal_and_weighted_voting(mock_context):
    game = {
        "chat": -2005,
        "players": [80, 81, 82, 83],
        "names": {80: "Mayor", 81: "Townie1", 82: "Townie2", 83: "Suspect"},
        "roles": {80: "Mer", 81: "Fuqaro", 82: "Fuqaro", 83: "Fuqaro"},
        "alive": {80: True, 81: True, 82: True, 83: True},
        "phase": "voting",
        "night": 1,
        "mayor_revealed": set(),
        "_finish_started": False,
    }
    games[-2005] = game

    # Reveal Mayor
    mock_update = MagicMock()
    mock_update.effective_chat = MagicMock(id=-2005, type="supergroup")
    mock_update.effective_user = MockUser(80, "Mayor")
    mock_update.message = MagicMock()
    mock_update.message.reply_text = AsyncMock()

    await reveal_cmd(mock_update, mock_context)
    assert 80 in game["mayor_revealed"], "Mayor must be recorded in mayor_revealed set"

    # Mayor votes for Suspect (83). Townie1 and Townie2 vote for None.
    # Without Mayor 3x weight, none would win 2 to 1.
    # With Mayor 3x weight, Suspect has 3 votes vs none has 2 votes.
    game["votes"] = {80: 83, 81: "none", 82: "none"}
    await finish_voting(mock_context, game)

    # Suspect should be brought to verdict because Mayor has 3 votes!
    assert game["phase"] == "verdict"
    assert game.get("accused_uid") == 83, "Accused should be 83 due to Mayor's 3x voting weight"

@pytest.mark.asyncio
async def test_roleblock_cancels_doctor_and_bodyguard(mock_context):
    game = {
        "chat": -2006,
        "players": [90, 91, 92, 93],
        "names": {90: "Hooker", 91: "Doc", 92: "Boss", 93: "Victim"},
        "roles": {90: "Maftunkor", 91: "Doktor", 92: "Boshliq", 93: "Fuqaro"},
        "alive": {90: True, 91: True, 92: True, 93: True},
        "phase": "night",
        "night": 1,
        "blocked_roles": {91: 90},  # Doctor 91 is blocked by Maftunkor 90
        "protected": {93},
        "protected_by": {93: 91},
        "kill_targets": {92: 93},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-2006] = game

    await resolve_night(mock_context, game)

    # Doctor was blocked, so Victim 93 dies!
    assert game["alive"][93] is False, "Victim must die because Doctor was roleblocked"
    assert 93 not in game.get("last_night_saved", [])

@pytest.mark.asyncio
async def test_social_para_and_bro_target_concurrency(mock_context):
    await init_db()

    uA = MockUser(9101, "Alice")
    uB = MockUser(9102, "Bob")
    uC = MockUser(9103, "Charlie")

    await ensure_user(uA)
    await ensure_user(uB)
    await ensure_user(uC)

    # Clear any previous links
    from database.db import get_db
    db = await get_db()
    await db.execute("DELETE FROM social_links WHERE user_id IN (9101, 9102, 9103)")
    await db.commit()

    # 1. A and B become Para
    up_ab = MagicMock()
    up_ab.message = MagicMock()
    up_ab.message.from_user = uA
    up_ab.message.reply_to_message = MagicMock(from_user=uB)
    up_ab.message.reply_text = AsyncMock()

    await para_cmd(up_ab, mock_context)
    reply_ab = up_ab.message.reply_text.call_args[0][0]
    assert "muvaffaqiyatli juftlik" in reply_ab

    # 2. C tries to become Para with B (who is already taken)
    up_cb = MagicMock()
    up_cb.message = MagicMock()
    up_cb.message.from_user = uC
    up_cb.message.reply_to_message = MagicMock(from_user=uB)
    up_cb.message.reply_text = AsyncMock()

    await para_cmd(up_cb, mock_context)
    reply_cb = up_cb.message.reply_text.call_args[0][0]
    assert "Nishon allaqachon boshqa inson bilan juftlik" in reply_cb

    # 3. A and B become Bro
    up_bro_ab = MagicMock()
    up_bro_ab.message = MagicMock()
    up_bro_ab.message.from_user = uA
    up_bro_ab.message.reply_to_message = MagicMock(from_user=uB)
    up_bro_ab.message.reply_text = AsyncMock()

    await bro_cmd(up_bro_ab, mock_context)
    reply_bro_ab = up_bro_ab.message.reply_text.call_args[0][0]
    assert "birodar (Bro) bo'ldilar" in reply_bro_ab

    # 4. C tries to become Bro with B (who is already Bro with A)
    up_bro_cb = MagicMock()
    up_bro_cb.message = MagicMock()
    up_bro_cb.message.from_user = uC
    up_bro_cb.message.reply_to_message = MagicMock(from_user=uB)
    up_bro_cb.message.reply_text = AsyncMock()

    await bro_cmd(up_bro_cb, mock_context)
    reply_bro_cb = up_bro_cb.message.reply_text.call_args[0][0]
    assert "Nishon allaqachon boshqa inson bilan birodarlik" in reply_bro_cb

@pytest.mark.asyncio
async def test_king_afk_timeout_resolution(mock_context):
    """Verify that if King is AFK, the 30-sec timeout automatically forgives attacker and resumes Day."""
    game = {
        "chat": -2008,
        "players": [70, 71, 72, 73],
        "names": {70: "King", 71: "Attacker", 72: "Citizen", 73: "Doctor"},
        "roles": {70: "Qirol", 71: "Boshliq", 72: "Fuqaro", 73: "Doktor"},
        "alive": {70: True, 71: True, 72: True, 73: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {71: 70},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
        "king_timeout_seconds": 0.05,
    }
    games[-2008] = game

    await resolve_night(mock_context, game)

    # Initial state: waiting for king, timer task is active
    assert game["_waiting_king"] is True
    assert "_king_timer_task" in game
    assert not game["_king_timer_task"].done()

    # Wait for the timeout task to complete
    await game["_king_timer_task"]

    # Post-timeout state: auto-forgiveness applied, phase transitioned to day
    assert game["_waiting_king"] is False
    assert game["alive"][71] is True, "Attacker should be auto-forgiven on King timeout"
    assert game["alive"][70] is True, "King should be alive"
    assert game["phase"] == "day", "Game should transition to day phase after timeout"

    # Notification sent about AFK
    calls = [c.kwargs.get("text", "") for c in mock_context.bot.send_message.call_args_list]
    assert any("AFK" in t for t in calls), "AFK timeout notification should be sent to chat"

@pytest.mark.asyncio
async def test_king_blocked_pm_auto_recovery(mock_context):
    """Verify that if King blocked bot in PM, resolution auto-forgives immediately and never deadlocks."""
    game = {
        "chat": -2009,
        "players": [80, 81, 82, 83],
        "names": {80: "KingBlocked", 81: "Attacker", 82: "Citizen", 83: "Doctor"},
        "roles": {80: "Qirol", 81: "Boshliq", 82: "Fuqaro", 83: "Doktor"},
        "alive": {80: True, 81: True, 82: True, 83: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {81: 80},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-2009] = game

    # Mock send_message to raise Exception when targeting King (80)
    orig_send = mock_context.bot.send_message
    async def mock_send_with_block(*args, **kwargs):
        if kwargs.get("chat_id") == 80:
            raise Exception("Forbidden: bot was blocked by the user")
        return await orig_send(*args, **kwargs)

    mock_context.bot.send_message = AsyncMock(side_effect=mock_send_with_block)

    await resolve_night(mock_context, game)

    # Must immediately recover without staying in _waiting_king
    assert game["_waiting_king"] is False, "Blocked PM should immediately unblock _waiting_king"
    assert game["alive"][81] is True, "Attacker should be alive after auto-forgive"
    assert game["phase"] == "day", "Game should advance to day phase without hanging"

@pytest.mark.asyncio
async def test_king_decision_cancels_timeout_task(mock_context):
    """Verify that when King clicks in time, the background timer is safely cancelled."""
    game = {
        "chat": -2010,
        "players": [90, 91, 92, 93, 94],
        "names": {90: "KingFast", 91: "Killer", 92: "Citizen", 93: "Doc", 94: "Partner"},
        "roles": {90: "Qirol", 91: "Boshliq", 92: "Fuqaro", 93: "Doktor", 94: "Qotil"},
        "alive": {90: True, 91: True, 92: True, 93: True, 94: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {91: 90},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
        "king_timeout_seconds": 60.0,
    }
    games[-2010] = game

    await resolve_night(mock_context, game)
    assert "_king_timer_task" in game
    task = game["_king_timer_task"]

    # King sends decision
    mock_update = MagicMock()
    mock_q = MagicMock()
    mock_q.from_user = MockUser(90, "KingFast")
    mock_q.data = "king_kill:90:91"
    mock_q.answer = AsyncMock()
    mock_q.edit_message_text = AsyncMock()
    mock_update.callback_query = mock_q

    await callback_router(mock_update, mock_context)

    # Task should now be cancelled or done
    assert task.cancelled() or task.done()
    assert "_king_timer_task" not in game
    assert game["alive"][91] is False, "Attacker should be killed"
    assert game["phase"] == "day"

@pytest.mark.asyncio
async def test_send_atmospheric_message_safety_and_guarantees(mock_context, tmp_path):
    """Verify that full text is ALWAYS delivered, never truncated, and voice notes dispatch safely."""
    from core.audio_effects import send_atmospheric_message, SOUND_ICONS
    bot = mock_context.bot
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_voice = AsyncMock()

    # 1. Standard text message with sound cue
    await send_atmospheric_message(bot, 12345, "Oddiy e'lon", sound_type="night")
    assert bot.send_message.called
    sent_text = bot.send_message.call_args[1]["text"]
    assert SOUND_ICONS["night"] in sent_text
    assert "Oddiy e'lon" in sent_text

    # 2. Long text exceeding 1024 characters with photo:
    # Telegram captions are capped at 1024 chars. Ensure full text is delivered via send_message
    long_narrative = "A" * 1200
    dummy_photo = tmp_path / "test.jpg"
    dummy_photo.write_bytes(b"dummy")

    bot.send_message.reset_mock()
    bot.send_photo.reset_mock()
    await send_atmospheric_message(bot, 12345, long_narrative, sound_type="morning", photo_path=str(dummy_photo))

    # Photo sent with sound cue header
    assert bot.send_photo.called
    # Full untruncated message sent via send_message
    assert bot.send_message.called
    sent_long_text = bot.send_message.call_args[1]["text"]
    assert len(sent_long_text) >= 1200
    assert long_narrative in sent_long_text

    # 3. Audio/Voice note dispatched safely while delivering text
    dummy_voice = tmp_path / "voice.ogg"
    dummy_voice.write_bytes(b"voice")

    bot.send_voice.reset_mock()
    bot.send_message.reset_mock()
    await send_atmospheric_message(bot, 12345, "Ovozli xabar matni", sound_type="murder", voice_path=str(dummy_voice))
    assert bot.send_voice.called
    assert bot.send_message.called
    assert "Ovozli xabar matni" in bot.send_message.call_args[1]["text"]

@pytest.mark.asyncio
async def test_cancel_game_timer_self_cancellation_guard():
    """Verify that a running timer task calling cancel_game_timer does not cancel itself."""
    from core.engine import cancel_game_timer
    game = {}

    task_completed = False

    async def running_timer():
        nonlocal task_completed
        # Simulate timer calling cancel_game_timer
        cancel_game_timer(game)
        # Yield to event loop to prove CancelledError is NOT raised
        await asyncio.sleep(0.01)
        task_completed = True

    task = asyncio.create_task(running_timer())
    game["_timer_task"] = task
    game["_king_timer_task"] = task

    await task
    assert task_completed is True, "Running task should not cancel itself via cancel_game_timer"

@pytest.mark.asyncio
async def test_multi_attack_with_king_and_doctor_and_qasoskor(mock_context):
    """Verify that when King is attacked, concurrent attacks with Doctor and Qasoskor retain all events and PMs."""
    game = {
        "chat": -2011,
        "players": [101, 102, 103, 104, 105, 106, 107],
        "names": {
            101: "King", 102: "Boss", 103: "Doctor", 104: "DocPatient",
            105: "Maniak", 106: "Qasoskor", 107: "RevengeTarget"
        },
        "roles": {
            101: "Qirol", 102: "Boshliq", 103: "Doktor", 104: "Fuqaro",
            105: "Maniak", 106: "Qasoskor", 107: "Fuqaro"
        },
        "alive": {
            101: True, 102: True, 103: True, 104: True,
            105: True, 106: True, 107: True
        },
        "phase": "night",
        "night": 1,
        # Boss attacks King
        "kill_targets": {102: 101},
        # Maniak attacks DocPatient, who is protected by Doctor
        "maniac_targets": {105: 104},
        "protected": {104},
        "protected_by": {104: 103},
        # Qasoskor was targeted (e.g. by Arsonist or secondary kill)
        "arsonist_action": {"ignite": 105},
        "arsonist_doused": {106},
        "revenge_targets": {106: 107},
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
    }
    games[-2011] = game

    sent_pms = []
    async def track_send_message(*args, **kwargs):
        sent_pms.append((kwargs.get("chat_id"), kwargs.get("text", "")))
    mock_context.bot.send_message = AsyncMock(side_effect=track_send_message)

    await resolve_night(mock_context, game)

    # 1. King is waiting for decision
    assert game["_waiting_king"] is True
    # 2. Doctor PMs were sent!
    doc_msgs = [t for cid, t in sent_pms if cid == 103]
    patient_msgs = [t for cid, t in sent_pms if cid == 104]
    assert any("HIMOYA ISHLADI" in m for m in doc_msgs), "Doctor must receive save confirmation"
    assert any("DOKTOR SIZNI DAVOLADI" in m for m in patient_msgs), "Patient must receive doctor healed confirmation"

    # 3. King executes Boss
    from handlers.callbacks import callback_router
    mock_update = MagicMock()
    mock_q = MagicMock()
    mock_q.from_user = MockUser(101, "King")
    mock_q.data = "king_kill:101:102"
    mock_q.answer = AsyncMock()
    mock_q.edit_message_text = AsyncMock()
    mock_update.callback_query = mock_q

    await callback_router(mock_update, mock_context)

    # 4. Final state check:
    # King (101) is alive
    assert game["alive"][101] is True
    # Boss (102) was executed by King
    assert game["alive"][102] is False
    # DocPatient (104) was saved by Doctor
    assert game["alive"][104] is True
    # Qasoskor (106) died from ignite, and their revenge target (107) died from revenge!
    assert game["alive"][106] is False
    assert game["alive"][107] is False

@pytest.mark.asyncio
async def test_send_atmospheric_message_markdown_fallback(mock_context):
    """Verify that send_atmospheric_message falls back to plain text if Markdown parsing fails."""
    from core.audio_effects import send_atmospheric_message
    bot = mock_context.bot

    # First call with parse_mode raises TelegramError/BadRequest
    call_count = 0
    async def mock_send_with_markdown_error(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if kwargs.get("parse_mode") == "Markdown":
            raise Exception("Can't parse entities: unmatched *")
        return MagicMock()

    bot.send_message = AsyncMock(side_effect=mock_send_with_markdown_error)

    # Text with problematic unclosed markdown
    malformed_text = "Salom *dunyo bu yerda yopilmagan yulduzcha"
    await send_atmospheric_message(bot, 99999, malformed_text, sound_type="night")

    # Should have tried with Markdown, caught exception, and retried without parse_mode
    assert call_count == 2
    assert bot.send_message.call_args[1]["parse_mode"] is None
    assert malformed_text in bot.send_message.call_args[1]["text"]

@pytest.mark.asyncio
async def test_concurrent_multi_game_king_resolution(mock_context):
    """Stress-test concurrent games where multiple Kings in different chats are attacked simultaneously."""
    game1 = {
        "chat": -2012,
        "players": [201, 202, 203],
        "names": {201: "King1", 202: "Boss1", 203: "Doc1"},
        "roles": {201: "Qirol", 202: "Boshliq", 203: "Doktor"},
        "alive": {201: True, 202: True, 203: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {202: 201},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
        "king_timeout_seconds": 0.05,
    }
    game2 = {
        "chat": -2013,
        "players": [301, 302, 303, 304],
        "names": {301: "King2", 302: "Boss2", 303: "Doc2", 304: "Killer2"},
        "roles": {301: "Qirol", 302: "Boshliq", 303: "Doktor", 304: "Qotil"},
        "alive": {301: True, 302: True, 303: True, 304: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {302: 301},
        "protected": set(),
        "blocked_roles": {},
        "tourist_targets": {},
        "detective_results": {},
        "_finish_started": False,
        "_resolving_night": False,
        "_waiting_king": False,
        "king_timeout_seconds": 1.0,
    }
    games[-2012] = game1
    games[-2013] = game2

    # Resolve night on both games simultaneously
    await asyncio.gather(
        resolve_night(mock_context, game1),
        resolve_night(mock_context, game2)
    )

    assert game1["_waiting_king"] is True
    assert game2["_waiting_king"] is True

    # Game 2: King manually executes Boss2
    from handlers.callbacks import callback_router
    up2 = MagicMock()
    q2 = MagicMock()
    q2.from_user = MockUser(301, "King2")
    q2.data = "king_kill:301:302"
    q2.answer = AsyncMock()
    q2.edit_message_text = AsyncMock()
    up2.callback_query = q2
    await callback_router(up2, mock_context)

    # Game 1: King1 times out after 0.05s
    await game1["_king_timer_task"]

    # Verify Game 1 state: Boss1 auto-forgiven, Day phase
    assert game1["_waiting_king"] is False
    assert game1["alive"][202] is True
    assert game1["phase"] == "day"

    # Verify Game 2 state: Boss2 executed, Day phase
    assert game2["_waiting_king"] is False
    assert game2["alive"][302] is False
    assert game2["phase"] == "day"

@pytest.mark.asyncio
async def test_voting_single_vote_limit(mock_context):
    game = {
        "chat": -3001,
        "players": [101, 102, 103, 104],
        "names": {101: "P1", 102: "P2", 103: "P3", 104: "P4"},
        "roles": {101: "Fuqaro", 102: "Qotil", 103: "Doktor", 104: "Detektiv"},
        "alive": {101: True, 102: True, 103: True, 104: True},
        "phase": "voting",
        "night": 1,
        "votes": {},
    }
    games[-3001] = game

    # 1. P1 votes for P2
    up1 = MagicMock()
    q1 = MagicMock()
    q1.from_user = MockUser(101, "P1")
    q1.data = "vote:-3001:102"
    q1.answer = AsyncMock()
    up1.callback_query = q1
    await callback_router(up1, mock_context)
    assert game["votes"][101] == "102"

    # 2. P1 attempts to vote again for P3 -> Denied!
    up1_dup = MagicMock()
    q1_dup = MagicMock()
    q1_dup.from_user = MockUser(101, "P1")
    q1_dup.data = "vote:-3001:103"
    q1_dup.answer = AsyncMock()
    up1_dup.callback_query = q1_dup
    await callback_router(up1_dup, mock_context)
    assert game["votes"][101] == "102"  # Remains unchanged!
    q1_dup.answer.assert_called()
    assert "allaqachon" in q1_dup.answer.call_args[0][0].lower()

    # 3. P4 attempts to vote for themselves -> Denied!
    up4_self = MagicMock()
    q4_self = MagicMock()
    q4_self.from_user = MockUser(104, "P4")
    q4_self.data = "vote:-3001:104"
    q4_self.answer = AsyncMock()
    up4_self.callback_query = q4_self
    await callback_router(up4_self, mock_context)
    assert 104 not in game["votes"]
    assert "o'zingizga" in q4_self.answer.call_args[0][0].lower()

@pytest.mark.asyncio
async def test_admin_privileges_and_badge():
    from database.models import is_admin, get_balance, get_badge, change_balance
    await init_db()

    # Admin IDs check
    assert is_admin(8048940366) is True
    assert is_admin(7651553630) is True
    assert is_admin(999999999, "rasuljonovv_a") is True
    assert is_admin(12345, "other_user") is False

    # Infinite balances & badge
    assert await get_balance(8048940366, "coin") == 999999999
    assert await get_balance(7651553630, "gold") == 999999999
    assert await get_badge(7651553630) == "👑 Bosh Admin"
    assert await get_badge(8048940366) == "👑 Bosh Admin"

    # Admin bypass deductions
    ok = await change_balance(8048940366, "gold", -500, "Admin test")
    assert ok is True

@pytest.mark.asyncio
async def test_gold_drop_and_claim(mock_context):
    from core.engine import active_drops
    from database.models import get_balance, get_user
    await init_db()

    # Setup a drop
    drop_id = "drop_test_123"
    active_drops[drop_id] = {
        "id": drop_id,
        "chat_id": -999,
        "creator_id": 8048940366,
        "creator_name": "Azimjon",
        "total": 2,
        "remaining": 2,
        "claimed_by": {},
        "created_at": 1000.0,
        "message_id": 12
    }

    # User 701 claims
    u701 = MockUser(701, "Claimer1")
    await ensure_user(u701)
    up1 = MagicMock()
    q1 = MagicMock()
    q1.from_user = u701
    q1.data = f"claim_gold:{drop_id}"
    q1.answer = AsyncMock()
    q1.edit_message_text = AsyncMock()
    up1.callback_query = q1
    await callback_router(up1, mock_context)

    assert active_drops[drop_id]["remaining"] == 1
    assert 701 in active_drops[drop_id]["claimed_by"]
    u701_row = await get_user(701)
    assert u701_row["gold"] >= 1

    # User 701 tries again -> Denied!
    await callback_router(up1, mock_context)
    assert active_drops[drop_id]["remaining"] == 1
    assert "allaqachon" in q1.answer.call_args[0][0].lower()

    # User 702 claims -> remaining becomes 0
    u702 = MockUser(702, "Claimer2")
    await ensure_user(u702)
    up2 = MagicMock()
    q2 = MagicMock()
    q2.from_user = u702
    q2.data = f"claim_gold:{drop_id}"
    q2.answer = AsyncMock()
    q2.edit_message_text = AsyncMock()
    up2.callback_query = q2
    await callback_router(up2, mock_context)
    assert active_drops[drop_id]["remaining"] == 0

    # User 703 claims -> Denied because finished!
    u703 = MockUser(703, "Claimer3")
    await ensure_user(u703)
    up3 = MagicMock()
    q3 = MagicMock()
    q3.from_user = u703
    q3.data = f"claim_gold:{drop_id}"
    q3.answer = AsyncMock()
    q3.edit_message_text = AsyncMock()
    up3.callback_query = q3
    await callback_router(up3, mock_context)
    assert "kech qoldingiz" in q3.answer.call_args[0][0].lower()

@pytest.mark.asyncio
async def test_coin_and_gold_transfer_commands():
    from handlers.social import coin_cmd, gold_cmd
    from database.models import get_user
    await init_db()

    sender = MockUser(8048940366, "Boss") # Admin
    target = MockUser(88811, "Recipient")
    await ensure_user(sender)
    await ensure_user(target)

    # 1. /coin 250
    up = MagicMock()
    msg = MagicMock()
    msg.from_user = sender
    msg.reply_to_message = MagicMock()
    msg.reply_to_message.from_user = target
    msg.reply_text = AsyncMock()
    up.message = msg

    ctx = MagicMock()
    ctx.args = ["250"]
    await coin_cmd(up, ctx)
    t_row = await get_user(88811)
    assert t_row["coin"] >= 350 # initial 100 + 250

    # 2. /gold 7
    ctx.args = ["7"]
    await gold_cmd(up, ctx)
    t_row = await get_user(88811)
    assert t_row["gold"] >= 7

@pytest.mark.asyncio
async def test_single_button_lobby_and_startgame_cmd(mock_context):
    from phases.lobby import lobby_keyboard, lobby_text
    from handlers.commands import startgame_cmd
    from core.engine import lobbies, games

    # Verify keyboard has exactly 1 button: '🎮 Qo'shilish'
    kb = lobby_keyboard(-5001)
    assert len(kb.inline_keyboard) == 1
    assert len(kb.inline_keyboard[0]) == 1
    assert kb.inline_keyboard[0][0].text == "🎮 Qo'shilish"
    assert kb.inline_keyboard[0][0].callback_data == "lobby_join:-5001"

    # Setup lobby with 4 players
    lobby = {
        "chat_id": -5001,
        "players": [1, 2, 3, 4],
        "names": {1: "A", 2: "B", 3: "C", 4: "D"},
        "badges": {},
        "open": True,
        "settings": {}
    }
    lobbies[-5001] = lobby

    # Test /startgame by player 1 in group
    up = MagicMock()
    up.effective_chat.type = "supergroup"
    up.effective_chat.id = -5001
    up.effective_user = MockUser(1, "A")
    ctx = MagicMock()
    ctx.bot = mock_context.bot

    await startgame_cmd(up, ctx)
    assert -5001 in games
    assert games[-5001]["phase"] == "night"


