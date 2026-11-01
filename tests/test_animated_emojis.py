import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update
from telegram.ext import ContextTypes, ExtBot

from core.emojis import (
    ACTIVE_ANIMATED_EMOJI_IDS,
    EMOJI_CONFIG,
    tg_emoji,
    anim_emoji,
    render_custom_emoji,
    strip_anim_emoji_tags,
    enrich_with_animated_emojis,
    format_badge_with_anim_emoji,
    _CHAR_TO_KEY,
)
from bot import SafeExtBot
from handlers.commands import boost_cmd, goal_cmd, plan_cmd, teamwork_cmd


def test_all_emoji_config_entries_use_active_ids():
    """Verify that every emoji configured in EMOJI_CONFIG maps strictly to one of the 11 verified active IDs."""
    valid_ids = set(ACTIVE_ANIMATED_EMOJI_IDS.values())
    for cat_name, cat_items in EMOJI_CONFIG.items():
        for key, conf in cat_items.items():
            assert "id" in conf, f"Missing id in {cat_name}.{key}"
            assert conf["id"] in valid_ids, f"Invalid emoji ID '{conf['id']}' for {cat_name}.{key}. Must be in verified active IDs."
            assert "fallback" in conf, f"Missing fallback in {cat_name}.{key}"


def test_tg_emoji_official_html_format():
    """Verify that tg_emoji strictly outputs the official Telegram Bot API format <tg-emoji emoji-id="...">."""
    res = tg_emoji("detective")
    assert res.startswith('<tg-emoji emoji-id="1740555807604342805">')
    assert res.endswith("</tg-emoji>")
    assert "document-id=" not in res


def test_enrich_with_animated_emojis_converts_raw_unicode():
    """Verify raw unicode emojis are converted to official animated custom emoji tags."""
    raw = "Salom 🌙 Tun keldi va 🔪 Mafia chiqdi. 👑 Don buyrug'i!"
    enriched = enrich_with_animated_emojis(raw)
    assert '<tg-emoji emoji-id="4158409751421517834">🌙</tg-emoji>' in enriched
    assert '<tg-emoji emoji-id="1269403972611866648">🔪</tg-emoji>' in enriched
    assert '<tg-emoji emoji-id="919985748604617114">👑</tg-emoji>' in enriched
    assert "Salom " in enriched
    assert " Tun keldi va " in enriched


def test_enrich_does_not_double_wrap_existing_tg_emoji():
    """Verify existing <tg-emoji> tags are preserved without nested or duplicate tags."""
    already_tagged = '<tg-emoji emoji-id="3191530815439765550">🎮</tg-emoji> Boshlash'
    enriched = enrich_with_animated_emojis(already_tagged)
    assert enriched == already_tagged
    assert enriched.count("<tg-emoji") == 1


def test_enrich_normalizes_legacy_document_id():
    """Verify legacy document-id attributes are automatically normalized to emoji-id."""
    legacy = '<tg-emoji document-id="3191530815439765550">🎮</tg-emoji>'
    enriched = enrich_with_animated_emojis(legacy)
    assert enriched == '<tg-emoji emoji-id="3191530815439765550">🎮</tg-emoji>'
    assert "document-id" not in enriched


def test_enrich_inside_html_structures():
    """Verify that emojis inside <a> and other HTML tags are properly enriched without corrupting tags."""
    text = '<a href="https://t.me/test">Guruhga qo\'shiling 🚀</a> va <b>bahra oling ✨</b>'
    enriched = enrich_with_animated_emojis(text)
    assert '<a href="https://t.me/test">Guruhga qo\'shiling <tg-emoji emoji-id="3191530815439765550">🚀</tg-emoji></a>' in enriched
    assert '<b>bahra oling <tg-emoji emoji-id="3191530815439765550">✨</tg-emoji></b>' in enriched


@pytest.mark.asyncio
async def test_safe_ext_bot_enriches_outgoing_html():
    """Verify SafeExtBot._do_post enriches unicode emojis into animated custom emojis on outgoing requests."""
    SafeExtBot._needs_real_telegram_ids = False
    bot = SafeExtBot("123456:TEST_TOKEN")
    captured = []

    async def mock_do_post(self, endpoint, data=None, *args, **kwargs):
        captured.append(dict(data) if data else {})
        return {"ok": True, "result": {"message_id": 999}}

    with pytest.MonkeyPatch.context() as m:
        m.setattr(ExtBot, "_do_post", mock_do_post)

        await bot._do_post("sendMessage", {
            "chat_id": 111,
            "text": "Bugun ☀️ Kun fazasi va 🗳️ Ovoz berish!",
            "parse_mode": "HTML"
        })

        assert len(captured) == 1
        out = captured[0]
        assert out["parse_mode"] == "HTML"
        assert '<tg-emoji emoji-id="336920350212227127">☀️</tg-emoji>' in out["text"]
        assert '<tg-emoji emoji-id="336920350212227127">🗳️</tg-emoji>' in out["text"]


@pytest.mark.asyncio
async def test_boost_cmd_and_goal_cmd_animated_emoji_coverage():
    """Verify /boost and /goal produce complete animated custom emoji tags."""
    up = MagicMock(spec=Update)
    up.effective_user.id = 7651553630
    up.effective_user.username = "test_user"
    up.effective_user.first_name = "User"
    up.effective_chat.type = "private"
    up.effective_chat.id = 7651553630
    up.message.reply_text = AsyncMock()
    up.effective_message = up.message
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # 1. /boost
    await boost_cmd(up, ctx)
    boost_text = up.message.reply_text.call_args[0][0]
    assert "<tg-emoji emoji-id=" in boost_text
    assert "document-id=" not in boost_text
    # Check key active IDs in boost
    assert 'emoji-id="3191530815439765550"' in boost_text  # rocket / sparkles
    assert 'emoji-id="919985748604617114"' in boost_text   # crown

    # 2. /goal
    up.message.reply_text.reset_mock()
    await goal_cmd(up, ctx)
    goal_text = up.message.reply_text.call_args[0][0]
    assert "<tg-emoji emoji-id=" in goal_text
    assert "document-id=" not in goal_text
    # Check key active IDs in goal
    assert 'emoji-id="1471004892762996745"' in goal_text  # civilian
    assert 'emoji-id="1269403972611866648"' in goal_text  # mafia


def test_common_symbols_mapped_and_enriched():
    """Verify common emojis (checkmark, warning, question, bomb, dice, etc.) are recognized and enriched."""
    from core.emojis import _CHAR_TO_KEY, enrich_with_animated_emojis, REAL_TELEGRAM_EMOJI_MAP, resolve_all_tg_emoji_to_real_telegram

    symbols = ["✅", "⚠️", "❓", "❗", "🚨", "💣", "🎲", "🧊", "🟣", "💸", "📝"]
    for s in symbols:
        assert s in _CHAR_TO_KEY, f"Symbol {s} must be in _CHAR_TO_KEY"

    res = enrich_with_animated_emojis("✅ Muvaffaqiyatli! ⚠️ Diqqat! 💣 Portlash! 🎲 O'yin!")
    assert '<tg-emoji emoji-id="1471004892762996745">✅</tg-emoji>' in res
    assert '<tg-emoji emoji-id="3024877442880766280">⚠️</tg-emoji>' in res
    assert '<tg-emoji emoji-id="1269403972611866648">💣</tg-emoji>' in res
    assert '<tg-emoji emoji-id="3191530815439765550">🎲</tg-emoji>' in res

    # Test resolution to official Telegram Custom Emoji IDs
    real_resolved = resolve_all_tg_emoji_to_real_telegram(res)
    assert '<tg-emoji emoji-id="5453957997418004470">✅</tg-emoji>' in real_resolved
    assert '<tg-emoji emoji-id="5373236586760651455">⚠️</tg-emoji>' in real_resolved
    assert '<tg-emoji emoji-id="5373239082136650704">💣</tg-emoji>' in real_resolved
    assert '<tg-emoji emoji-id="5361741454685256344">🎲</tg-emoji>' in real_resolved


@pytest.mark.asyncio
async def test_safe_ext_bot_enriches_none_parse_mode_with_generic_emojis():
    """Verify SafeExtBot._do_post detects unicode emojis when parse_mode is None and converts to HTML."""
    SafeExtBot._needs_real_telegram_ids = False
    bot = SafeExtBot("123456:TEST_TOKEN")
    captured = []

    async def mock_do_post(self, endpoint, data=None, *args, **kwargs):
        captured.append(dict(data) if data else {})
        return {"ok": True, "result": {"message_id": 999}}

    with pytest.MonkeyPatch.context() as m:
        m.setattr(ExtBot, "_do_post", mock_do_post)

        # Message with parse_mode=None and checkmark emoji
        await bot._do_post("sendMessage", {
            "chat_id": 111,
            "text": "✅ Siz lobbiga qo'shildingiz!",
            "parse_mode": None
        })

        assert len(captured) == 1
        out = captured[0]
        assert out["parse_mode"] == "HTML"
        assert '<tg-emoji emoji-id="1471004892762996745">✅</tg-emoji>' in out["text"]


@pytest.mark.asyncio
async def test_safe_ext_bot_adapts_to_real_ids_on_document_invalid():
    """Verify that when Telegram API raises Document_invalid, SafeExtBot auto-adapts to official Telegram IDs and retries."""
    from telegram.error import BadRequest
    bot = SafeExtBot("123456:TEST_TOKEN")
    bot._needs_real_telegram_ids = False
    attempts = []

    async def mock_do_post(self, endpoint, data=None, *args, **kwargs):
        attempts.append(dict(data) if data else {})
        if len(attempts) == 1:
            # Simulate real Telegram rejecting unknown Discord snowflake ID
            raise BadRequest("Document_invalid")
        return {"ok": True, "result": {"message_id": 1001}}

    with pytest.MonkeyPatch.context() as m:
        m.setattr(ExtBot, "_do_post", mock_do_post)

        res = await bot._do_post("sendMessage", {
            "chat_id": 111,
            "text": '<tg-emoji emoji-id="3191530815439765550">🎮</tg-emoji> Boshlash',
            "parse_mode": "HTML"
        })

        assert res["ok"] is True
        assert len(attempts) == 2
        # Attempt 1 sent configured ID
        assert 'emoji-id="3191530815439765550"' in attempts[0]["text"]
        # Attempt 2 adapted to real Telegram Custom Emoji ID
        assert 'emoji-id="5361741454685256344"' in attempts[1]["text"]
        assert bot._needs_real_telegram_ids is True

        # Subsequent call should adapt proactively
        await bot._do_post("sendMessage", {
            "chat_id": 111,
            "text": '<tg-emoji emoji-id="1269403972611866648">🔪</tg-emoji> Mafia',
            "parse_mode": "HTML"
        })
        assert len(attempts) == 3
        assert 'emoji-id="5373239082136650704"' in attempts[2]["text"]

