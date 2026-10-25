import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from core.navigation import (
    get_bot_username, get_bot_deep_link, get_group_link,
    bot_action_button, return_to_group_button,
    bot_action_keyboard, return_to_group_keyboard
)
from phases.lobby import lobby_keyboard
from phases.voting import get_voting_keyboard
from phases.verdict import verdict_keyboard

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    return ctx

def test_deep_linking_helpers():
    username = get_bot_username()
    assert username == "Detektivmj_bot"

    # Deep link to bot with action
    link = get_bot_deep_link(-100123456789, "act")
    assert link == f"https://t.me/{username}?start=act_100123456789"

    # Button generation
    btn = bot_action_button(-10055, "💬 Botga o'tish")
    assert btn.text == "💬 Botga o'tish"
    assert btn.url == f"https://t.me/{username}?start=act_10055"

    kb = bot_action_keyboard(-10055)
    assert len(kb.inline_keyboard) == 1
    assert kb.inline_keyboard[0][0].url == f"https://t.me/{username}?start=act_10055"

def test_group_link_resolution():
    # Public group link via string or dict
    game_with_username = {"group_link": "https://t.me/mafia_uzb_test", "chat": -100999}
    assert get_group_link(game_with_username) == "https://t.me/mafia_uzb_test"

    # Supergroup fallback without username
    game_private_supergroup = {"chat": -1001987654321}
    assert get_group_link(game_private_supergroup) == "https://t.me/c/1987654321/999999999"

    # Return button and keyboard
    ret_btn = return_to_group_button(game_with_username)
    assert ret_btn.text == "👥 Guruhga qaytish (Muhokama)"
    assert ret_btn.url == "https://t.me/mafia_uzb_test"

    ret_kb = return_to_group_keyboard(game_with_username)
    assert len(ret_kb.inline_keyboard) == 1
    assert ret_kb.inline_keyboard[0][0].url == "https://t.me/mafia_uzb_test"

def test_lobby_keyboard_bot_link_toggle():
    # Default is clean 1 button (backward-compatibility)
    kb_clean = lobby_keyboard(-5001)
    assert len(kb_clean.inline_keyboard) == 1
    assert kb_clean.inline_keyboard[0][0].text == "🎮 Qo'shilish"

    # With bot link toggle enabled
    kb_with_bridge = lobby_keyboard(-5001, include_bot_link=True)
    assert len(kb_with_bridge.inline_keyboard) == 2
    assert kb_with_bridge.inline_keyboard[0][0].text == "🎮 Qo'shilish"
    assert "Botga o'tish" in kb_with_bridge.inline_keyboard[1][0].text
    assert kb_with_bridge.inline_keyboard[1][0].url == "https://t.me/Detektivmj_bot?start=act_5001"

def test_voting_and_verdict_keyboards_include_bot_bridge():
    game = {
        "chat": -100888,
        "players": [1, 2],
        "names": {1: "Aziz", 2: "Bekzod"},
        "alive": {1: True, 2: True},
        "roles": {1: "Fuqaro", 2: "Boshliq"},
    }
    vkb = get_voting_keyboard(game)
    # The last row must be the bridge button
    last_row = vkb.inline_keyboard[-1]
    assert len(last_row) == 1
    assert "Botga o'tish" in last_row[0].text
    assert last_row[0].url == "https://t.me/Detektivmj_bot?start=act_100888"

    verdict_kb = verdict_keyboard(-100888, 2)
    assert len(verdict_kb.inline_keyboard) == 2
    assert "QATL" in verdict_kb.inline_keyboard[0][0].text
    assert "AVF" in verdict_kb.inline_keyboard[0][1].text
    assert "Botga o'tish" in verdict_kb.inline_keyboard[1][0].text
    assert verdict_kb.inline_keyboard[1][0].url == "https://t.me/Detektivmj_bot?start=act_100888"

@pytest.mark.asyncio
async def test_start_cmd_act_deep_link_night(mock_context):
    from handlers.commands import start_cmd
    from core.engine import games

    game = {
        "chat": -100333,
        "players": [101, 102],
        "names": {101: "Detektiv Ali", 102: "Don Karim"},
        "roles": {101: "Detektiv", 102: "Boshliq"},
        "alive": {101: True, 102: True},
        "phase": "night",
        "night": 1,
        "night_done": set(),
        "group_link": "https://t.me/test_group_mafia"
    }
    games[-100333] = game

    up = MagicMock()
    up.effective_user.id = 101
    up.effective_user.full_name = "Detektiv Ali"
    up.effective_user.username = "det_ali"
    up.effective_chat.type = "private"
    up.message.reply_text = AsyncMock()

    mock_context.args = ["act_100333"]

    await start_cmd(up, mock_context)
    assert up.message.reply_text.call_count == 1
    reply_args = up.message.reply_text.call_args
    # Message should prompt night action
    assert "Tun #1 amallari" in reply_args[0][0]
    assert "Detektiv" in reply_args[0][0]
    assert reply_args[1]["reply_markup"] is not None

@pytest.mark.asyncio
async def test_start_cmd_act_deep_link_dead_player(mock_context):
    from handlers.commands import start_cmd
    from core.engine import games

    game = {
        "chat": -100444,
        "players": [201, 202],
        "names": {201: "Marhum Fuqaro", 202: "Don Karim"},
        "roles": {201: "Fuqaro", 202: "Boshliq"},
        "alive": {201: False, 202: True},
        "phase": "night",
        "night": 2,
        "group_link": "https://t.me/test_group_mafia"
    }
    games[-100444] = game

    up = MagicMock()
    up.effective_user.id = 201
    up.effective_user.full_name = "Marhum Fuqaro"
    up.effective_user.username = "marhum"
    up.effective_chat.type = "private"
    up.message.reply_text = AsyncMock()

    mock_context.args = ["act_100444"]

    await start_cmd(up, mock_context)
    assert up.message.reply_text.call_count == 1
    reply_args = up.message.reply_text.call_args
    assert "Ruhlar Olami" in reply_args[0][0]
    kb = reply_args[1]["reply_markup"]
    assert any("Guruhga qaytish" in btn.text for row in kb.inline_keyboard for btn in row)

@pytest.mark.asyncio
async def test_start_cmd_act_deep_link_voting_phase(mock_context):
    from handlers.commands import start_cmd
    from core.engine import games

    game = {
        "chat": -100555,
        "players": [301, 302],
        "names": {301: "Olim", 302: "Salim"},
        "roles": {301: "Fuqaro", 302: "Boshliq"},
        "alive": {301: True, 302: True},
        "phase": "voting",
        "night": 2,
        "votes": {},
        "group_link": "https://t.me/test_group_mafia"
    }
    games[-100555] = game

    up = MagicMock()
    up.effective_user.id = 301
    up.effective_user.full_name = "Olim"
    up.effective_user.username = "olim"
    up.effective_chat.type = "private"
    up.message.reply_text = AsyncMock()

    mock_context.args = ["act_100555"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.call_count == 1
    reply_args = up.message.reply_text.call_args
    assert "Ovoz berish" in reply_args[0][0]
    assert reply_args[1]["reply_markup"] is not None

@pytest.mark.asyncio
async def test_start_cmd_act_deep_link_verdict_accused(mock_context):
    from handlers.commands import start_cmd
    from core.engine import games

    game = {
        "chat": -100666,
        "players": [401, 402],
        "names": {401: "Sudlanuvchi", 402: "Don Karim"},
        "roles": {401: "Fuqaro", 402: "Boshliq"},
        "alive": {401: True, 402: True},
        "phase": "verdict",
        "accused_uid": 401,
        "verdict_votes": {},
        "group_link": "https://t.me/test_group_mafia"
    }
    games[-100666] = game

    up = MagicMock()
    up.effective_user.id = 401
    up.effective_user.full_name = "Sudlanuvchi"
    up.effective_user.username = "sudlanuvchi"
    up.effective_chat.type = "private"
    up.message.reply_text = AsyncMock()

    mock_context.args = ["act_100666"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.call_count == 1
    reply_args = up.message.reply_text.call_args
    assert "sud minbaridasiz" in reply_args[0][0]
    kb = reply_args[1]["reply_markup"]
    assert any("Guruhga qaytish" in btn.text for row in kb.inline_keyboard for btn in row)

@pytest.mark.asyncio
async def test_start_game_sends_full_dossier_with_return_bridge(mock_context):
    from phases.lobby import start_game
    from core.engine import lobbies, games

    lobby = {
        "chat_id": -100777,
        "players": [501, 502, 503, 504],
        "names": {501: "Ali", 502: "Vali", 503: "Gani", 504: "Salim"},
        "badges": {},
        "open": True,
        "group_link": "https://t.me/super_mafia_group"
    }
    lobbies[-100777] = lobby

    await start_game(mock_context, -100777)

    # 1 message to group + 4 PMs to players = at least 5 messages
    assert mock_context.bot.send_message.call_count >= 5

    # Check group message has bot bridge button
    group_call = mock_context.bot.send_message.call_args_list[0]
    assert group_call[1]["chat_id"] == -100777
    assert "O'yin boshlandi" in group_call[1]["text"]
    g_kb = group_call[1]["reply_markup"]
    assert any("Botga o'tish" in btn.text for row in g_kb.inline_keyboard for btn in row)

    # Check PM calls have format_role_dossier and return_to_group_keyboard
    for call in mock_context.bot.send_message.call_args_list[1:5]:
        pm_text = call[1]["text"]
        assert "Sizning rolingiz:" in pm_text
        assert "🎯 *Bosh Maqsadi:*" in pm_text
        assert "⚡ *Nima qilishingiz kerak?*" in pm_text
        assert "💡 *Taktik Maslahat:*" in pm_text
        pm_kb = call[1]["reply_markup"]
        assert pm_kb is not None
        assert any("Guruhga qaytish" in btn.text for row in pm_kb.inline_keyboard for btn in row)

def test_voting_and_verdict_pm_keyboards():
    game = {
        "chat": -100888,
        "players": [1, 2],
        "names": {1: "Aziz", 2: "Bekzod"},
        "alive": {1: True, 2: True},
        "roles": {1: "Fuqaro", 2: "Boshliq"},
        "group_link": "https://t.me/test_group_link"
    }
    vkb_pm = get_voting_keyboard(game, is_pm=True)
    last_row = vkb_pm.inline_keyboard[-1]
    assert len(last_row) == 1
    assert "Guruhga qaytish" in last_row[0].text
    assert last_row[0].url == "https://t.me/test_group_link"

    verdict_kb_pm = verdict_keyboard(-100888, 2, is_pm=True, game_or_link=game)
    assert len(verdict_kb_pm.inline_keyboard) == 2
    assert "QATL" in verdict_kb_pm.inline_keyboard[0][0].text
    assert "AVF" in verdict_kb_pm.inline_keyboard[0][1].text
    assert "Guruhga qaytish" in verdict_kb_pm.inline_keyboard[1][0].text
    assert verdict_kb_pm.inline_keyboard[1][0].url == "https://t.me/test_group_link"

def test_graveyard_and_last_words_keyboards():
    from core.graveyard import graveyard_menu_keyboard
    from core.last_words import last_words_keyboard

    g_kb = graveyard_menu_keyboard("https://t.me/test_group")
    assert any("Guruhga qaytish" in btn.text for row in g_kb.inline_keyboard for btn in row)
    assert any(btn.url == "https://t.me/test_group" for row in g_kb.inline_keyboard for btn in row)

    lw_kb = last_words_keyboard("https://t.me/test_group")
    assert any("Guruhga qaytish" in btn.text for row in lw_kb.inline_keyboard for btn in row)
    assert any(btn.url == "https://t.me/test_group" for row in lw_kb.inline_keyboard for btn in row)

@pytest.mark.asyncio
async def test_menu_callbacks_when_update_message_is_none(mock_context):
    from handlers.commands import balance_cmd, profile_cmd, rating_cmd, guide_cmd
    from handlers.clans import clan_cmd

    up = MagicMock()
    up.message = None  # simulate inline callback query update where message is None
    up.effective_message = MagicMock()
    up.effective_message.reply_text = AsyncMock()
    up.effective_user.id = 99999
    up.effective_user.full_name = "Callback User"
    up.effective_user.username = "cb_user"
    mock_context.args = []

    await balance_cmd(up, mock_context)
    assert up.effective_message.reply_text.call_count >= 1

    up.effective_message.reply_text.reset_mock()
    await profile_cmd(up, mock_context)
    assert up.effective_message.reply_text.call_count >= 1

    up.effective_message.reply_text.reset_mock()
    await rating_cmd(up, mock_context)
    assert up.effective_message.reply_text.call_count >= 1

    up.effective_message.reply_text.reset_mock()
    await guide_cmd(up, mock_context)
    assert up.effective_message.reply_text.call_count >= 1

    up.effective_message.reply_text.reset_mock()
    await clan_cmd(up, mock_context)
    assert up.effective_message.reply_text.call_count >= 1

