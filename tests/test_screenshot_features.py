import pytest
from unittest.mock import AsyncMock, MagicMock
from core.engine import display_name, finish_game
from phases.night import start_night
from config import MIN_PLAYERS, MAX_PLAYERS, ROLES, DEFAULT_NIGHT_SECONDS

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.send_photo = AsyncMock()
    return ctx

def test_display_name_badges_and_crowns():
    # Admin gets crown
    game = {"names": {8048940366: "Saidazim"}, "badges": {}}
    assert display_name(game, 8048940366) == "👑 Saidazim"

    # Shop Crown badge
    game2 = {"names": {1234: "Farrux"}, "badges": {1234: "👑 Qirol Toji"}}
    assert display_name(game2, 1234) == "👑 Farrux"

    # Special badge
    game3 = {"names": {5678: "Malika"}, "badges": {5678: "✦ Maxsus belgi"}}
    assert display_name(game3, 5678) == "✦ Malika [Maxsus]"

    # Lightning badge
    game4 = {"names": {9999: "Javohir"}, "badges": {9999: "⚡ Yashin belgisi"}}
    assert display_name(game4, 9999) == "⚡ Javohir"

    # Normal player
    game5 = {"names": {1111: "Akmal"}, "badges": {}}
    assert display_name(game5, 1111) == "Akmal"

@pytest.mark.asyncio
async def test_night_announcement_screenshot_format(mock_context):
    game = {
        "chat": -10012345,
        "night": 1,
        "players": [1, 2, 3, 4, 5],
        "names": {1: "DonPlayer", 2: "DocPlayer", 3: "DetPlayer", 4: "Citizen1", 5: "Citizen2"},
        "roles": {1: "Boshliq", 2: "Doktor", 3: "Detektiv", 4: "Fuqaro", 5: "Fuqaro"},
        "alive": {1: True, 2: True, 3: True, 4: True, 5: True},
        "badges": {},
    }

    await start_night(mock_context, game)

    # Check call to send message
    assert mock_context.bot.send_photo.call_count == 1 or mock_context.bot.send_message.call_count >= 1
    # Check night announcement text content
    if mock_context.bot.send_photo.called:
        kwargs = mock_context.bot.send_photo.call_args[1]
        text = kwargs.get("caption", "")
    else:
        kwargs = mock_context.bot.send_message.call_args[1]
        text = kwargs.get("text", "")

    assert "Tirik o'yinchilar:" in text
    assert "Tinchlar - 4:" in text
    assert "Mafiyalar - 1:" in text
    assert "Jami: 5 ta" in text
    assert f"Tonggacha ⏳ {DEFAULT_NIGHT_SECONDS} sekund qoldi" in text

@pytest.mark.asyncio
async def test_finish_game_screenshot_format(mock_context):
    game = {
        "chat": -10099999,
        "night": 2,
        "players": [1, 2, 3],
        "names": {1: "WinnerBoss", 2: "VictimDoc", 3: "VictimDet"},
        "roles": {1: "Boshliq", 2: "Doktor", 3: "Detektiv"},
        "alive": {1: True, 2: False, 3: False},
        "badges": {},
        "last_night_deaths": [2],
        "last_night_causes": {2: ["vaxshiylarcha o'ldirildi"]},
    }

    await finish_game(mock_context, game, winners=[1], winning_team="red")

    assert mock_context.bot.send_message.call_count >= 1
    # First message sent is the game-end announcement
    msg_call = mock_context.bot.send_message.call_args_list[0][1]
    text = msg_call["text"]

    assert "Tunda o'ldirilganlar:" in text
    assert "O'yin tugadi!" in text
    assert "G'oliblar:" in text
    assert "🌟 1. WinnerBoss - 🤵🏻 Don" in text
    assert "Qolgan o'yinchilar:" in text
    assert "O'yin davomiyligi:" in text
    assert "🎉 🪩" in text
    # Check button URL
    kb = msg_call.get("reply_markup")
    assert kb is not None
    assert "Statistika" in kb.inline_keyboard[0][0].text
