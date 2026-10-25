import pytest
from unittest.mock import AsyncMock, MagicMock

from config import ROLES
from roles.dossier import ROLE_DOSSIERS, get_role_dossier, format_role_dossier
from handlers.commands import guide_cmd

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.args = []
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx

def test_all_config_roles_have_tactical_dossiers():
    for role_name in ROLES.keys():
        dossier = get_role_dossier(role_name)
        assert dossier is not None
        assert dossier.role_name == role_name
        assert dossier.team_display
        assert dossier.icon
        assert len(dossier.goal) > 20, f"{role_name} goal too short"
        assert len(dossier.actions_night) > 10, f"{role_name} night action too short"
        assert len(dossier.actions_day) > 10, f"{role_name} day action too short"
        assert len(dossier.tactical_tip) > 20, f"{role_name} tip too short"

def test_format_role_dossier_structure():
    card = format_role_dossier("Detektiv", partner_text="🤝 *Sherigingiz:* Ali (Sherif)")
    # Must have all required structural markers
    assert "Sizning rolingiz: *Detektiv*" in card
    assert "Shahar aholisi 🔵" in card
    assert "🎯 *Bosh Maqsadi:*" in card
    assert "⚡ *Nima qilishingiz kerak?*" in card
    assert "• *Tunda:*" in card
    assert "• *Kunduzi:*" in card
    assert "💡 *Taktik Maslahat:*" in card
    assert "Sherigingiz" in card
    assert "Rolingizni sir saqlang" in card

@pytest.mark.asyncio
async def test_guide_cmd_specific_role_dossier(mock_context):
    up = MagicMock()
    up.message.reply_text = AsyncMock()

    # Query 'Detektiv'
    mock_context.args = ["Detektiv"]
    await guide_cmd(up, mock_context)
    assert up.message.reply_text.call_count == 1
    text = up.message.reply_text.call_args[0][0]
    assert "Sizning rolingiz: *Detektiv*" in text
    assert "🔎 Shaxsni tekshirish" in text

    # Query 'Joker'
    up.message.reply_text.reset_mock()
    mock_context.args = ["joker"]
    await guide_cmd(up, mock_context)
    assert up.message.reply_text.call_count == 1
    text = up.message.reply_text.call_args[0][0]
    assert "Sizning rolingiz: *Joker*" in text
    assert "Yakkaxon neytral 🟡" in text
    assert "MUTLAQ G'ALABA" in text

@pytest.mark.asyncio
async def test_guide_cmd_general_overview(mock_context):
    up = MagicMock()
    up.message.reply_text = AsyncMock()
    mock_context.args = []

    await guide_cmd(up, mock_context)
    assert up.message.reply_text.call_count == 1
    text = up.message.reply_text.call_args[0][0]
    assert "Mukammal Rollar Yo'riqnomasi" in text
    assert "Shahar aholisi:" in text
    assert "Mafiya sindikati:" in text
    assert "Yakkaxon neytrallar:" in text
    assert "/guide <rol>" in text
