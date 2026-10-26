import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.atmospheric_feed import (
    broadcast_role_action, broadcast_role_sleep,
    ROLE_LIVE_MESSAGES, ROLE_SLEEP_MESSAGES
)
from phases.night import (
    get_role_action_buttons, get_target_selection_keyboard,
    resolve_night, start_night
)
from phases.day import day_phase
from phases.voting import start_voting, start_voting_phase
from core.visuals import send_animated_dice_effect
from handlers.social import para_cmd, bro_cmd, pending_social_proposals
from handlers.callbacks import callback_router
from database.db import init_db, get_db
from database.models import ensure_user

class MockUser:
    def __init__(self, uid: int, name: str, username: str = "testuser"):
        self.id = uid
        self.first_name = name
        self.full_name = name
        self.username = username
        self.is_bot = False

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_atmospheric_action_and_sleep_messages(mock_context):
    """Verify that every specified role has the exact required Uzbek action and sleep text."""
    game = {
        "chat": -10099,
        "night": 1,
        "players": [1, 2, 3, 4],
        "alive": {1: True, 2: True, 3: True, 4: True},
        "roles": {
            1: "Detektiv",
            2: "Doktor",
            3: "Boshliq",
            4: "Maniak"
        }
    }

    # Action broadcasts
    await broadcast_role_action(mock_context, game, actor=1, action="detective")
    assert "Detektiv izquvarlikka ketdi... 🔎" in mock_context.bot.send_message.call_args[1]["text"]

    await broadcast_role_action(mock_context, game, actor=2, action="protect")
    assert "Doktor bemor tomon shoshildi... 🩺" in mock_context.bot.send_message.call_args[1]["text"]

    await broadcast_role_action(mock_context, game, actor=3, action="kill")
    assert "Boshliq maxfiy uchrashuvga yo‘l oldi... 👑" in mock_context.bot.send_message.call_args[1]["text"]

    await broadcast_role_action(mock_context, game, actor=4, action="maniac_kill")
    assert "Maniak tun qorong‘usida ovga chiqdi... 🩸" in mock_context.bot.send_message.call_args[1]["text"]

    # Sleep broadcasts
    game["_notified_night_actions"] = set()
    mock_context.bot.send_message.reset_mock()

    await broadcast_role_sleep(mock_context, game, actor=1)
    assert "Detektiv bu tun dam oldi... 😴" in mock_context.bot.send_message.call_args[1]["text"]

    await broadcast_role_sleep(mock_context, game, actor=2)
    assert "Doktor bu tun dam oldi... 😴" in mock_context.bot.send_message.call_args[1]["text"]

    await broadcast_role_sleep(mock_context, game, actor=3)
    assert "Boshliq bu tun dam oldi... 😴" in mock_context.bot.send_message.call_args[1]["text"]

    await broadcast_role_sleep(mock_context, game, actor=4)
    assert "Maniak bu tun dam oldi... 😴" in mock_context.bot.send_message.call_args[1]["text"]

@pytest.mark.asyncio
async def test_sheriff_promotion_to_detective_role(mock_context):
    """When Detective dies, Sheriff is strictly promoted to Detektiv role with active powers."""
    game = {
        "chat": -2001,
        "players": [10, 20, 30],
        "names": {10: "Detective", 20: "Sheriff", 30: "MafiaBoss"},
        "roles": {10: "Detektiv", 20: "Sherif", 30: "Boshliq"},
        "alive": {10: True, 20: True, 30: True},
        "partners": {10: 20, 20: 10},
        "phase": "night",
        "night": 1,
        "sheriff_promoted": set(),
        "kill_targets": {30: 10}, # Mafia kills detective
        "blocked_roles": {},
        "protected": set(),
        "guarded_by": {},
        "night_done": {30}
    }

    await resolve_night(mock_context, game)

    # Detective died
    assert game["alive"][10] is False
    # Sheriff is now promoted to Detective role
    assert game["roles"][20] == "Detektiv"
    assert 20 in game["sheriff_promoted"]

    # Now Sheriff's keyboard has full Detective investigate & shoot powers
    kb = get_role_action_buttons(game, 20)
    assert kb is not None
    btn_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Shaxsni tekshirish" in t for t in btn_texts)
    assert any("otish" in t for t in btn_texts)

@pytest.mark.asyncio
async def test_self_defense_heal_limit_one_time_per_game(mock_context):
    """Doctor self-heal and Bodyguard self-protect: strictly max 1 time per game."""
    game = {
        "chat": -2002,
        "players": [50, 51],
        "names": {50: "Doc", 51: "Guard"},
        "roles": {50: "Doktor", 51: "Tansoqchi"},
        "alive": {50: True, 51: True},
        "self_protect_used": set(),
        "doctor_self_heal_used": {},
        "phase": "night"
    }

    # First attempt: self is in target selection
    kb_doc1 = get_target_selection_keyboard(game, 50, "protect")
    target_ids = [btn.callback_data.split(":")[-1] for row in kb_doc1.inline_keyboard for btn in row if btn.callback_data and btn.callback_data.startswith("tgt:")]
    assert "50" in target_ids

    # Simulate Doctor using self-heal via callback
    up_cb = MagicMock()
    up_cb.callback_query = MagicMock()
    up_cb.callback_query.data = "tgt:protect:50:50"
    up_cb.callback_query.from_user = MockUser(50, "Doc")
    up_cb.callback_query.answer = AsyncMock()
    up_cb.callback_query.edit_message_text = AsyncMock()
    up_cb.effective_user = up_cb.callback_query.from_user

    from core.engine import games
    games[-2002] = game

    await callback_router(up_cb, mock_context)
    assert 50 in game["self_protect_used"]

    # Second attempt: Doctor cannot select self anymore
    kb_doc2 = get_target_selection_keyboard(game, 50, "protect")
    target_ids2 = [btn.callback_data.split(":")[-1] for row in kb_doc2.inline_keyboard for btn in row if btn.callback_data and btn.callback_data.startswith("tgt:")]
    assert "50" not in target_ids2

    # Second callback attempt gets rejected
    up_cb.callback_query.answer.reset_mock()
    await callback_router(up_cb, mock_context)
    assert up_cb.callback_query.answer.called
    assert "faqat 1 marta" in up_cb.callback_query.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_day_to_voting_15_seconds_transition(mock_context):
    """Day phase default timer is 15 seconds, and transitions automatically to voting."""
    from config import DEFAULT_DAY_SECONDS
    assert DEFAULT_DAY_SECONDS == 15

    game = {
        "chat": -2003,
        "players": [60, 61, 62, 63],
        "names": {60: "P1", 61: "P2", 62: "P3", 63: "P4"},
        "roles": {60: "Fuqaro", 61: "Detektiv", 62: "Doktor", 63: "Boshliq"},
        "alive": {60: True, 61: True, 62: True, 63: True},
        "night": 1,
        "phase": "night",
        "settings": {}
    }
    from core.engine import games
    games[-2003] = game

    await day_phase(mock_context, game)
    assert game["phase"] == "day"
    assert game.get("_timer_task") is not None

    # Verify announcement mentions 15 soniya
    sent_text = mock_context.bot.send_message.call_args[1]["text"]
    assert "15 soniya" in sent_text

@pytest.mark.asyncio
async def test_dice_is_never_sent_to_groups():
    """Verify send_animated_dice_effect returns None and sends nothing when chat_id < 0."""
    mock_bot = MagicMock()
    mock_bot.send_dice = AsyncMock()

    # In groups (negative chat ID)
    res_group = await send_animated_dice_effect(mock_bot, -1001234567, emoji="🎲")
    assert res_group is None
    assert not mock_bot.send_dice.called

    # In PM (positive chat ID)
    res_pm = await send_animated_dice_effect(mock_bot, 1234567, emoji="🎯")
    assert mock_bot.send_dice.called

@pytest.mark.asyncio
async def test_para_and_bro_group_proposal_flow_and_easter_egg(mock_context):
    """Test full proposal flow in group, acceptance, rejection, and secret repeat auto-accept."""
    await init_db()
    db = await get_db()
    await db.execute("DELETE FROM social_links WHERE user_id IN (9801, 9802, 9803)")
    await db.commit()
    pending_social_proposals.clear()

    u1 = MockUser(9801, "Sardor")
    u2 = MockUser(9802, "Malika")
    u3 = MockUser(9803, "Jasur")

    await ensure_user(u1)
    await ensure_user(u2)
    await ensure_user(u3)

    # 1. Proposal in group from u1 to u2
    up_grp = MagicMock()
    up_grp.message = MagicMock()
    up_grp.message.from_user = u1
    up_grp.message.reply_to_message = MagicMock(from_user=u2)
    up_grp.message.reply_text = AsyncMock()
    up_grp.effective_chat = MagicMock(type="supergroup", id=-1009988)

    await para_cmd(up_grp, mock_context)

    # In group: tells user that request is sent
    reply_group = up_grp.message.reply_text.call_args[0][0]
    assert "so'rovi yubordi" in reply_group
    # In PM: proposal message sent to u2 with accept/reject buttons
    assert mock_context.bot.send_message.called
    pm_call = mock_context.bot.send_message.call_args[1]
    assert pm_call["chat_id"] == 9802
    assert "taklifini yubordi" in pm_call["text"]

    # 2. Secret Easter Egg: If u1 sends /para to u2 again while pending, auto-accepts!
    up_grp.message.reply_text.reset_mock()
    await para_cmd(up_grp, mock_context)
    auto_reply = up_grp.message.reply_text.call_args[0][0]
    assert "muvaffaqiyatli juftlik" in auto_reply

    # Check DB
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = 9801 AND kind = 'para'") as c:
        row = await c.fetchone()
    assert row["other_id"] == 9802

    # 3. Test rejection for bro_cmd
    up_bro = MagicMock()
    up_bro.message = MagicMock()
    up_bro.message.from_user = u1
    up_bro.message.reply_to_message = MagicMock(from_user=u3)
    up_bro.message.reply_text = AsyncMock()
    up_bro.effective_chat = MagicMock(type="supergroup", id=-1009988)

    await bro_cmd(up_bro, mock_context)
    assert (9801, 9803, "bro") in pending_social_proposals

    # Target u3 rejects via callback
    up_rej = MagicMock()
    up_rej.callback_query = MagicMock()
    up_rej.callback_query.data = "soc_rej:9801:9803:bro:-1009988"
    up_rej.callback_query.from_user = u3
    up_rej.callback_query.answer = AsyncMock()
    up_rej.callback_query.edit_message_text = AsyncMock()
    up_rej.effective_user = u3

    await callback_router(up_rej, mock_context)
    assert (9801, 9803, "bro") not in pending_social_proposals
    assert "rad etdingiz" in up_rej.callback_query.edit_message_text.call_args[0][0]

@pytest.mark.asyncio
async def test_sheriff_has_no_active_abilities_while_detective_alive_and_fast_forward(mock_context):
    """While Detektiv is alive, Sherif has NO active abilities, and Sheriff never blocks night fast-forward."""
    from core.engine import games
    from handlers.callbacks import check_night_completed

    chat_id = -2099
    game = {
        "chat": chat_id,
        "players": [8101, 8102, 8103],
        "names": {8101: "Det", 8102: "Sher", 8103: "Boss"},
        "roles": {8101: "Detektiv", 8102: "Sherif", 8103: "Boshliq"},
        "alive": {8101: True, 8102: True, 8103: True},
        "phase": "night",
        "night": 1,
        "night_done": set(),
        "sheriff_promoted": set()
    }
    games[chat_id] = game

    # 1. Verify Sheriff has no active ability buttons
    kb_sher = get_role_action_buttons(game, 8102)
    assert kb_sher is not None
    btn_texts = [b.text for row in kb_sher.inline_keyboard for b in row]
    assert "👮 Shahar/Mafiya tekshiruvi" not in btn_texts
    assert "🔎 Shaxsni tekshirish" not in btn_texts
    assert "🔫 Shubhali shaxsni otish" not in btn_texts
    assert any("dam olish" in t.lower() for t in btn_texts)

    # 2. If Sheriff tries sheriff_check callback while Detective alive, it is rejected
    up_cb = MagicMock()
    up_cb.callback_query = MagicMock()
    up_cb.callback_query.data = "tgt:sheriff_check:8102:8103"
    up_cb.callback_query.from_user = MockUser(8102, "Sher")
    up_cb.callback_query.answer = AsyncMock()
    up_cb.effective_user = up_cb.callback_query.from_user
    await callback_router(up_cb, mock_context)
    assert up_cb.callback_query.answer.called
    assert "qobiliyati faol emas" in up_cb.callback_query.answer.call_args[0][0]

    # 3. Night completion check: only Detective and Boss are required, Sheriff does not block!
    assert not check_night_completed(game)
    game["night_done"].add(8101) # Detective acted
    assert not check_night_completed(game)
    game["night_done"].add(8103) # Boss acted
    # Now night IS completed even though Sheriff never acted!
    assert check_night_completed(game)

@pytest.mark.asyncio
async def test_night_resolves_immediately_on_sleep(mock_context):
    """When the last active player sleeps, night resolves immediately."""
    from core.engine import games
    chat_id = -2098
    game = {
        "chat": chat_id,
        "players": [8201, 8202],
        "names": {8201: "Det", 8202: "Boss"},
        "roles": {8201: "Detektiv", 8202: "Boshliq"},
        "alive": {8201: True, 8202: True},
        "phase": "night",
        "night": 1,
        "night_done": {8201}, # Detective already acted
        "sheriff_promoted": set()
    }
    games[chat_id] = game

    # Boss chooses sleep
    up_cb = MagicMock()
    up_cb.callback_query = MagicMock()
    up_cb.callback_query.data = "act:sleep:8202"
    up_cb.callback_query.from_user = MockUser(8202, "Boss")
    up_cb.callback_query.answer = AsyncMock()
    up_cb.callback_query.edit_message_text = AsyncMock()
    up_cb.effective_user = up_cb.callback_query.from_user

    await callback_router(up_cb, mock_context)
    # Boss is marked done and resolution was initiated
    assert 8202 in game["night_done"]
    assert game.get("phase") in ("day", "finished")

@pytest.mark.asyncio
async def test_doctor_target_switch_preserves_self_heal(mock_context):
    """Doctor selecting another player after selecting self restores their 1-time self-heal."""
    from core.engine import games
    chat_id = -2097
    game = {
        "chat": chat_id,
        "players": [8301, 8302, 8303],
        "names": {8301: "Doc", 8302: "Patient", 8303: "Boss"},
        "roles": {8301: "Doktor", 8302: "Fuqaro", 8303: "Boshliq"},
        "alive": {8301: True, 8302: True, 8303: True},
        "phase": "night",
        "night": 1,
        "night_done": set(),
        "self_protect_used": set(),
        "doctor_self_heal_used": {}
    }
    games[chat_id] = game

    # 1. Doctor selects self
    up_self = MagicMock()
    up_self.callback_query = MagicMock()
    up_self.callback_query.data = "tgt:protect:8301:8301"
    up_self.callback_query.from_user = MockUser(8301, "Doc")
    up_self.callback_query.answer = AsyncMock()
    up_self.callback_query.edit_message_text = AsyncMock()
    up_self.effective_user = up_self.callback_query.from_user

    await callback_router(up_self, mock_context)
    assert 8301 in game["self_protect_used"]

    # 2. Doctor switches to Patient before night resolution
    up_other = MagicMock()
    up_other.callback_query = MagicMock()
    up_other.callback_query.data = "tgt:protect:8301:8302"
    up_other.callback_query.from_user = MockUser(8301, "Doc")
    up_other.callback_query.answer = AsyncMock()
    up_other.callback_query.edit_message_text = AsyncMock()
    up_other.effective_user = up_other.callback_query.from_user

    await callback_router(up_other, mock_context)
    # Self protect is freed!
    assert 8301 not in game["self_protect_used"]
    assert game["doctor_self_heal_used"][8301] is False

@pytest.mark.asyncio
async def test_social_proposal_persistence_across_process_reboot(mock_context):
    """Pending proposal stored in SQLite allows secret easter egg to trigger even after in-memory state is lost."""
    await init_db()
    db = await get_db()
    await db.execute("DELETE FROM social_links WHERE user_id IN (9901, 9902)")
    await db.execute("DELETE FROM social_requests WHERE requester_id IN (9901, 9902) OR target_id IN (9901, 9902)")
    await db.commit()
    pending_social_proposals.clear()

    u1 = MockUser(9901, "Alisher")
    u2 = MockUser(9902, "Nargiza")

    await ensure_user(u1)
    await ensure_user(u2)

    up_grp = MagicMock()
    up_grp.message = MagicMock()
    up_grp.message.from_user = u1
    up_grp.message.reply_to_message = MagicMock(from_user=u2)
    up_grp.message.reply_text = AsyncMock()
    up_grp.effective_chat = MagicMock(type="supergroup", id=-1007788)

    # 1. First send
    await para_cmd(up_grp, mock_context)

    # Verify persisted in SQLite
    async with db.execute("SELECT * FROM social_requests WHERE requester_id = 9901 AND target_id = 9902") as c:
        row = await c.fetchone()
    assert row is not None

    # Simulate process reboot: memory wiped!
    pending_social_proposals.clear()
    assert (9901, 9902, "para") not in pending_social_proposals

    # 2. Second send after reboot -> Secret Easter Egg auto-accepts from DB!
    up_grp.message.reply_text.reset_mock()
    await para_cmd(up_grp, mock_context)
    auto_reply = up_grp.message.reply_text.call_args[0][0]
    assert "muvaffaqiyatli juftlik" in auto_reply

    # Verified linked in social_links
    async with db.execute("SELECT other_id FROM social_links WHERE user_id = 9901 AND kind = 'para'") as c:
        link_row = await c.fetchone()
    assert link_row["other_id"] == 9902

@pytest.mark.asyncio
async def test_goal_and_teamwork_commands(mock_context):
    """Test /goal and /teamwork command handlers."""
    from handlers.commands import goal_cmd, teamwork_cmd
    u = MockUser(7701, "Botir")
    await ensure_user(u)

    up = MagicMock()
    up.message = MagicMock()
    up.message.from_user = u
    up.message.reply_text = AsyncMock()
    up.effective_user = u

    # /goal outside of active game
    await goal_cmd(up, mock_context)
    goal_out = up.message.reply_text.call_args[0][0]
    assert "Shahar (Town) Maqsadi" in goal_out
    assert "Mafiya (Mafia) Maqsadi" in goal_out

    # /teamwork
    up.message.reply_text.reset_mock()
    await teamwork_cmd(up, mock_context)
    tw_out = up.message.reply_text.call_args[0][0]
    assert "Detektiv va Sherif Hamkorligi" in tw_out
    assert "/para" in tw_out

@pytest.mark.asyncio
async def test_bori_night_action_and_sleep(mock_context):
    """Test Bo'ri actions and sleep messages."""
    game = {
        "chat": -2096,
        "players": [401, 402, 403],
        "names": {401: "Wolf", 402: "Boss", 403: "Doc"},
        "roles": {401: "Bo'ri", 402: "Boshliq", 403: "Doktor"},
        "alive": {401: True, 402: True, 403: True},
        "phase": "night",
        "night": 1
    }
    # When boss is alive, Bo'ri assists
    kb_alive = get_role_action_buttons(game, 401)
    btn_texts = [b.text for row in kb_alive.inline_keyboard for b in row]
    assert any("Boshliq bilan ovga chiqish" in t for t in btn_texts)

    # When boss dies, Bo'ri hunts independently
    game["alive"][402] = False
    kb_solo = get_role_action_buttons(game, 401)
    btn_texts_solo = [b.text for row in kb_solo.inline_keyboard for b in row]
    assert any("Ovga chiqish (Boshliqsiz)" in t for t in btn_texts_solo)

    # Test Bo'ri sleep broadcast
    await broadcast_role_sleep(mock_context, game, actor=401)
    assert "Bo‘ri bu tun dam oldi... 😴" in mock_context.bot.send_message.call_args[1]["text"]

