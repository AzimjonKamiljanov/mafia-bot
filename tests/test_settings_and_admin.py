import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from database.db import init_db
from database.models import get_chat_settings, update_chat_settings, is_admin, change_balance, get_user
from handlers.settings import settings_cmd, handle_settings_callback
from handlers.commands import plan_cmd, boost_cmd
from handlers.admin_panel import admin_cmd, handle_admin_callback
from handlers.admin_ai import process_admin_ai_message
from phases.night import get_role_action_buttons
from phases.lobby import create_lobby, start_game
from core.engine import lobbies, games

@pytest.mark.asyncio
async def test_chat_settings_crud():
    await init_db()
    from database.db import get_db
    db = await get_db()
    chat_id = -100888999
    await db.execute("DELETE FROM chat_settings WHERE chat_id = ?", (chat_id,))
    await db.execute("DELETE FROM group_settings WHERE chat_id = ?", (chat_id,))
    await db.commit()
    settings = await get_chat_settings(chat_id)
    assert settings["night_seconds"] == 60
    assert settings["day_seconds"] == 15
    assert settings["vote_seconds"] == 45
    assert settings["verdict_seconds"] == 25

    await update_chat_settings(chat_id, night_seconds=30, vote_seconds=30, disabled_roles=json.dumps(["Joker"]))
    updated = await get_chat_settings(chat_id)
    assert updated["night_seconds"] == 30
    assert updated["vote_seconds"] == 30
    assert "Joker" in json.loads(updated["disabled_roles"])

@pytest.mark.asyncio
async def test_settings_callback_handling():
    await init_db()
    chat_id = -100777666
    mock_update = MagicMock()
    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_update.effective_user = MagicMock()
    mock_update.effective_user.id = 7651553630 # Super admin
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.callback_query = MagicMock()
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()
    mock_update.callback_query.edit_message_reply_markup = AsyncMock()

    # 1. Test set_time
    mock_update.callback_query.data = f"sett:set_time:{chat_id}:night:45"
    handled = await handle_settings_callback(mock_update, mock_context)
    assert handled is True
    st = await get_chat_settings(chat_id)
    assert st["night_seconds"] == 45

    # 2. Test toggle_role
    mock_update.callback_query.data = f"sett:toggle_role:{chat_id}:0:Sayyoh"
    handled = await handle_settings_callback(mock_update, mock_context)
    assert handled is True
    st = await get_chat_settings(chat_id)
    assert "Sayyoh" in json.loads(st["disabled_roles"])

    # 3. Test reset (2-step confirmation)
    mock_update.callback_query.data = f"sett:reset:{chat_id}"
    handled = await handle_settings_callback(mock_update, mock_context)
    assert handled is True
    # Still unreset before confirmation
    st = await get_chat_settings(chat_id)
    assert st["night_seconds"] == 45

    # 4. Confirm reset
    mock_update.callback_query.data = f"sett:reset_confirm:{chat_id}"
    handled = await handle_settings_callback(mock_update, mock_context)
    assert handled is True
    st = await get_chat_settings(chat_id)
    assert st["night_seconds"] == 60
    assert json.loads(st["disabled_roles"]) == []

@pytest.mark.asyncio
async def test_sheriff_promoted_buttons():
    # When Detektiv is alive, Sherif only checks town/mafia
    game_det_alive = {
        "chat": -10055,
        "players": [10, 20],
        "roles": {10: "Detektiv", 20: "Sherif"},
        "alive": {10: True, 20: True},
        "sheriff_promoted": set()
    }
    kb_alive = get_role_action_buttons(game_det_alive, 20)
    assert kb_alive is not None
    # Check button text: no active ability buttons while Detective is alive
    btn_texts = [btn.text for row in kb_alive.inline_keyboard for btn in row]
    assert "👮 Shahar/Mafiya tekshiruvi" not in btn_texts
    assert "🔎 Shaxsni tekshirish" not in btn_texts
    assert "🔫 Shubhali shaxsni otish" not in btn_texts
    assert any("dam olish" in t.lower() for t in btn_texts)

    # When Detektiv is dead, Sherif gains detective abilities
    game_det_dead = {
        "chat": -10055,
        "players": [10, 20],
        "roles": {10: "Detektiv", 20: "Sherif"},
        "alive": {10: False, 20: True},
        "sheriff_promoted": {20}
    }
    kb_dead = get_role_action_buttons(game_det_dead, 20)
    assert kb_dead is not None
    btn_texts_dead = [btn.text for row in kb_dead.inline_keyboard for btn in row]
    assert "🔎 Shaxsni tekshirish" in btn_texts_dead
    assert "🔫 Shubhali shaxsni otish" in btn_texts_dead

@pytest.mark.asyncio
async def test_plan_and_boost_commands():
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    await plan_cmd(mock_update, mock_context)
    assert mock_update.message.reply_text.call_count == 1
    plan_text = mock_update.message.reply_text.call_args[0][0]
    assert "DETEKTIV MAFIA" in plan_text
    assert "3-Tun AFK Kafolati" in plan_text

    mock_update.message.reply_text.reset_mock()
    await boost_cmd(mock_update, mock_context)
    assert mock_update.message.reply_text.call_count == 1
    boost_text = mock_update.message.reply_text.call_args[0][0]
    assert "TELEGRAM PREMIUM" in boost_text
    assert "Boost Group" in boost_text

@pytest.mark.asyncio
async def test_admin_ai_processor():
    await init_db()
    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = 7651553630
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.effective_message.text = "tun vaqtini 30 qil"
    mock_update.effective_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    handled = await process_admin_ai_message(mock_update, mock_context)
    assert handled is True
    assert mock_update.effective_message.reply_text.call_count == 1
    rep = mock_update.effective_message.reply_text.call_args[0][0]
    assert "30 soniya" in rep

    # Test currency intent
    mock_update.effective_message.text = "7651553630 ga 500 coin ber"
    mock_update.effective_message.reply_text.reset_mock()
    handled2 = await process_admin_ai_message(mock_update, mock_context)
    assert handled2 is True
    rep2 = mock_update.effective_message.reply_text.call_args[0][0]
    assert "+500 Coin" in rep2

@pytest.mark.asyncio
async def test_lobby_pinning_and_unpinning():
    await init_db()
    chat_id = -100999888
    lobbies.pop(chat_id, None)
    games.pop(chat_id, None)

    mock_update = MagicMock()
    mock_update.effective_chat.type = "supergroup"
    mock_update.effective_chat.id = chat_id
    mock_update.effective_user.id = 111
    mock_update.effective_user.full_name = "Player One"
    mock_update.effective_user.first_name = "Player One"
    mock_update.effective_user.username = "player1"

    mock_msg = MagicMock()
    mock_msg.message_id = 456
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=mock_msg)
    mock_context.bot.pin_chat_message = AsyncMock()
    mock_context.bot.unpin_chat_message = AsyncMock()

    # Create lobby -> must pin
    await create_lobby(mock_update, mock_context)
    assert chat_id in lobbies
    assert mock_context.bot.pin_chat_message.call_count == 1
    assert mock_context.bot.pin_chat_message.call_args[1]["message_id"] == 456

    # Add enough players to start game
    lobby = lobbies[chat_id]
    for uid in (222, 333, 444):
        lobby["players"].append(uid)
        lobby["names"][uid] = f"Player {uid}"

    # Start game -> must unpin and pass settings into game
    await start_game(mock_context, chat_id)
    assert mock_context.bot.unpin_chat_message.call_count == 1
    assert mock_context.bot.unpin_chat_message.call_args[1]["message_id"] == 456
    assert chat_id in games
    assert "settings" in games[chat_id]
    lobbies.pop(chat_id, None)
    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_admin_ai_accusative_and_aliases():
    await init_db()
    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = 7651553630
    mock_update.effective_user.username = "rasuljonovv_a"
    mock_update.effective_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    # 1. "tunni 30 qil"
    mock_update.effective_message.text = "tunni 30 qil"
    mock_update.effective_message.reply_text.reset_mock()
    handled = await process_admin_ai_message(mock_update, mock_context)
    assert handled is True
    assert "30 soniya" in mock_update.effective_message.reply_text.call_args[0][0]

    # 2. "kunni 60 qil"
    mock_update.effective_message.text = "kunni 60 qil"
    mock_update.effective_message.reply_text.reset_mock()
    handled = await process_admin_ai_message(mock_update, mock_context)
    assert handled is True
    assert "60 soniya" in mock_update.effective_message.reply_text.call_args[0][0]

    # 3. "donni ochir" -> resolves Don alias to Boshliq
    mock_update.effective_message.text = "donni ochir"
    mock_update.effective_message.reply_text.reset_mock()
    handled = await process_admin_ai_message(mock_update, mock_context)
    assert handled is True
    rep = mock_update.effective_message.reply_text.call_args[0][0]
    assert "Boshliq" in rep
    assert "O'CHIRILDI" in rep

    # 4. "barcha rollarni yoq"
    mock_update.effective_message.text = "barcha rollarni yoq"
    mock_update.effective_message.reply_text.reset_mock()
    handled = await process_admin_ai_message(mock_update, mock_context)
    assert handled is True
    assert "Barcha rollar" in mock_update.effective_message.reply_text.call_args[0][0]

    # 5. "set test_key hello_world" and "get test_key"
    mock_update.effective_message.text = "set test_key hello_world"
    mock_update.effective_message.reply_text.reset_mock()
    handled = await process_admin_ai_message(mock_update, mock_context)
    assert handled is True
    assert "hello_world" in mock_update.effective_message.reply_text.call_args[0][0]

    mock_update.effective_message.text = "get test_key"
    mock_update.effective_message.reply_text.reset_mock()
    handled = await process_admin_ai_message(mock_update, mock_context)
    assert handled is True
    assert "hello_world" in mock_update.effective_message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_detective_shoot_cause_and_role():
    from phases.night import resolve_night
    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    game = {
        "chat": -10044,
        "players": [10, 20],
        "names": {10: "Detektiv Ali", 20: "Qotil Bobur"},
        "roles": {10: "Detektiv", 20: "Qotil"},
        "alive": {10: True, 20: True},
        "phase": "night",
        "night": 1,
        "kill_targets": {10: 20}, # Detective shoots suspect!
        "night_done": {10, 20},
    }

    await resolve_night(mock_context, game)
    assert game["alive"][20] is False # Suspect died
    causes = game["last_night_causes"].get(20, [])
    assert any("Detektiv qurolidan otildi" in c for c in causes)

