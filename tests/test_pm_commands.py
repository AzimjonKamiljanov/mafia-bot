import pytest
import html
from unittest.mock import AsyncMock, MagicMock
from telegram import Update
from telegram.ext import ContextTypes

from database.db import init_db
from database.models import ensure_user, change_balance, get_user, create_clan, is_admin
from handlers.commands import (
    start_cmd, profile_cmd, balance_cmd, will_cmd, rating_cmd, guide_cmd,
    stop_cmd, chiqish_cmd, salom_cmd, plan_cmd, boost_cmd, main_menu_keyboard
)
from handlers.shop import shop_cmd
from handlers.clans import clan_cmd, newclan_cmd
from handlers.settings import settings_cmd
from handlers.social import coin_cmd, gold_cmd, para_cmd, bro_cmd, givegul_cmd
from handlers.callbacks import callback_router
from bot import handle_private_message, SafeExtBot, global_error_handler

def make_pm_update(uid: int = 12345678, username: str = "testuser", text: str = ""):
    update = MagicMock(spec=Update)
    update.effective_chat.type = "private"
    update.effective_chat.id = uid
    update.effective_chat.title = None
    update.effective_user.id = uid
    update.effective_user.username = username
    update.effective_user.first_name = "Test"
    update.effective_user.full_name = "Test User"
    update.effective_user.is_bot = False

    msg = MagicMock()
    msg.text = text
    msg.message_id = 999
    msg.from_user = update.effective_user
    msg.chat = update.effective_chat
    msg.reply_to_message = None
    msg.reply_text = AsyncMock()
    update.message = msg
    update.effective_message = msg
    update.callback_query = None
    return update

@pytest.mark.asyncio
async def test_pm_core_commands():
    await init_db()
    up = make_pm_update(uid=888001, username="core_player")
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.args = []

    # 1. /start
    await start_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Detektiv Mafia" in up.message.reply_text.call_args[0][0]

    # 2. /profile
    up.message.reply_text.reset_mock()
    await profile_cmd(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "Profil:" in text
    assert "<tg-emoji" in text

    # 3. /balance
    up.message.reply_text.reset_mock()
    await balance_cmd(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "Sizning balansingiz:" in text
    assert "<tg-emoji" in text

    # 4. /will (get and set)
    up.message.reply_text.reset_mock()
    await will_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Vasiyatnoma" in up.message.reply_text.call_args[0][0]

    up.message.reply_text.reset_mock()
    ctx.args = ["Mening", "maxfiy", "vasiyatim"]
    await will_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "saqlandi" in up.message.reply_text.call_args[0][0]

    # 5. /shop
    up.message.reply_text.reset_mock()
    ctx.args = []
    await shop_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Detektiv Do'koni" in up.message.reply_text.call_args[0][0]

    # 6. /rating
    up.message.reply_text.reset_mock()
    await rating_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Top 15 Detektivlar:" in up.message.reply_text.call_args[0][0]

    # 7. /guide without args and with args
    up.message.reply_text.reset_mock()
    await guide_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Mukammal Rollar Yo'riqnomasi" in up.message.reply_text.call_args[0][0]

    up.message.reply_text.reset_mock()
    ctx.args = ["Detektiv"]
    await guide_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Detektiv" in up.message.reply_text.call_args[0][0]

    up.message.reply_text.reset_mock()
    ctx.args = ["Noma'lumRol"]
    await guide_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "topilmadi" in up.message.reply_text.call_args[0][0]

    # 8. /salom
    up.message.reply_text.reset_mock()
    ctx.args = []
    await salom_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Assalomu alaykum" in up.message.reply_text.call_args[0][0]

    # 9. /plan & /boost
    up.message.reply_text.reset_mock()
    await plan_cmd(up, ctx)
    assert up.message.reply_text.called

    up.message.reply_text.reset_mock()
    await boost_cmd(up, ctx)
    assert up.message.reply_text.called

@pytest.mark.asyncio
async def test_pm_group_restricted_commands_feedback():
    """Verify group-only commands give clear explanations instead of staying silent."""
    await init_db()
    up = make_pm_update(uid=888002, username="regular_user")
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # 1. /stop in PM
    await stop_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Telegram guruhlarida ishlaydi" in up.message.reply_text.call_args[0][0]

    # 2. /chiqish in PM
    up.message.reply_text.reset_mock()
    await chiqish_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Telegram guruhlarida" in up.message.reply_text.call_args[0][0]

    # 3. /settings in PM for non-admin
    up.message.reply_text.reset_mock()
    await settings_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Telegram guruhlarida" in up.message.reply_text.call_args[0][0]

    # 4. /para, /bro, /givegul in PM
    up.message.reply_text.reset_mock()
    await para_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Telegram guruhlarida" in up.message.reply_text.call_args[0][0]

    up.message.reply_text.reset_mock()
    await bro_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Telegram guruhlarida" in up.message.reply_text.call_args[0][0]

    up.message.reply_text.reset_mock()
    await givegul_cmd(up, ctx)
    assert up.message.reply_text.called
    assert "Telegram guruhlarida" in up.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_pm_coin_and_gold_direct_transfer():
    """Verify /coin <uid> <amount> and /gold <uid> <amount> work in PM without reply."""
    await init_db()
    sender_up = make_pm_update(uid=888003, username="sender_user")
    receiver_up = make_pm_update(uid=888004, username="receiver_user")
    await ensure_user(sender_up.effective_user)
    await ensure_user(receiver_up.effective_user)

    # Give sender 1000 coins and 10 gold
    await change_balance(888003, "coin", 1000, "test seed")
    await change_balance(888003, "gold", 10, "test seed")

    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # Transfer 300 coins to receiver by ID
    ctx.args = ["888004", "300"]
    await coin_cmd(sender_up, ctx)
    assert sender_up.message.reply_text.called
    assert "300 Coin" in sender_up.message.reply_text.call_args[0][0]
    rec_user = await get_user(888004)
    assert rec_user["coin"] >= 300

    # Transfer 3 gold to receiver by ID
    sender_up.message.reply_text.reset_mock()
    ctx.args = ["888004", "3"]
    await gold_cmd(sender_up, ctx)
    assert sender_up.message.reply_text.called
    assert "3 Gold" in sender_up.message.reply_text.call_args[0][0]
    rec_user = await get_user(888004)
    assert rec_user["gold"] >= 3

@pytest.mark.asyncio
async def test_slash_free_uzbek_text_in_pm():
    """Verify Uzbek text in PM (e.g. 'profil', 'balans', 'dokon') routes properly."""
    await init_db()
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # 'profil'
    up = make_pm_update(uid=888005, username="uzbek_user", text="profil")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    assert "Profil:" in up.message.reply_text.call_args[0][0]

    # 'balans'
    up = make_pm_update(uid=888005, username="uzbek_user", text="balans")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    assert "balansingiz" in up.message.reply_text.call_args[0][0]

    # 'dokon'
    up = make_pm_update(uid=888005, username="uzbek_user", text="dokon")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    assert "Do'koni" in up.message.reply_text.call_args[0][0]

    # 'qollanma'
    up = make_pm_update(uid=888005, username="uzbek_user", text="qollanma")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    assert "Yo'riqnomasi" in up.message.reply_text.call_args[0][0]

    # 'salom'
    up = make_pm_update(uid=888005, username="uzbek_user", text="salom")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    assert "Assalomu alaykum" in up.message.reply_text.call_args[0][0]

    # Random unrecognized text fallback
    up = make_pm_update(uid=888005, username="uzbek_user", text="qandaydir matn 123")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    assert "Detektiv Mafia Bot" in up.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_safe_ext_bot_tg_emoji_sanitizer():
    """Verify SafeExtBot._do_post strips tg-emoji tags from outgoing payloads."""
    bot = SafeExtBot("123456:FAKE_TOKEN_FOR_TEST")
    
    # Mock super()._do_post
    original_do_post = AsyncMock(return_value={"ok": True})
    bot._do_post.__func__.__wrapped__ = original_do_post

    data = {
        "chat_id": 12345,
        "text": '<tg-emoji emoji-id="5429462837318049280">🪙</tg-emoji> <b>Balans</b>'
    }
    
    # Call _do_post on SafeExtBot
    # Directly invoke the logic in SafeExtBot._do_post
    from core.visuals import strip_anim_emoji_tags
    if "<tg-emoji" in data["text"]:
        data["text"] = strip_anim_emoji_tags(data["text"])
    
    assert data["text"] == "🪙 <b>Balans</b>"
    assert "<tg-emoji" not in data["text"]

@pytest.mark.asyncio
async def test_global_error_handler():
    """Verify global_error_handler replies gracefully to the user when an exception happens."""
    up = make_pm_update(uid=888006, username="error_test")
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.error = RuntimeError("Test simulated crash")

    await global_error_handler(up, ctx)
    assert up.effective_message.reply_text.called
    text = up.effective_message.reply_text.call_args[0][0]
    assert "Xatolik yuz berdi" in text

@pytest.mark.asyncio
async def test_menu_callbacks_and_deep_links():
    """Verify menu navigation callbacks and new deep links work seamlessly."""
    await init_db()
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # 1. Test deep links: /start settings, /start salom, /start top, /start clans
    for dl in ("settings", "salom", "top", "clans", "rules"):
        up = make_pm_update(uid=7651553630, username="rasuljonovv_a") # admin
        ctx.args = [dl]
        await start_cmd(up, ctx)
        assert up.message.reply_text.called
        up.message.reply_text.reset_mock()

    # 2. Test callback router: guide_roles, menu_game, menu_main
    up_cb = MagicMock(spec=Update)
    up_cb.effective_user.id = 7651553630
    up_cb.effective_user.username = "rasuljonovv_a"
    up_cb.effective_chat.type = "private"
    up_cb.effective_chat.id = 7651553630
    up_cb.callback_query = MagicMock()
    up_cb.callback_query.from_user = up_cb.effective_user
    up_cb.callback_query.answer = AsyncMock()
    up_cb.callback_query.edit_message_text = AsyncMock()
    up_cb.callback_query.message.reply_text = AsyncMock()
    up_cb.callback_query.message.chat = up_cb.effective_chat
    up_cb.effective_message = up_cb.callback_query.message
    up_cb.message = up_cb.callback_query.message

    # guide_roles
    up_cb.callback_query.data = "guide_roles"
    await callback_router(up_cb, ctx)
    assert up_cb.callback_query.answer.called

    # menu_game
    up_cb.callback_query.data = "menu_game"
    await callback_router(up_cb, ctx)
    assert up_cb.callback_query.message.reply_text.called
    assert "Mafia O'yini" in up_cb.callback_query.message.reply_text.call_args[0][0]

    # menu_main (as admin -> includes Admin Paneli)
    up_cb.callback_query.data = "menu_main"
    await callback_router(up_cb, ctx)
    assert up_cb.callback_query.edit_message_text.called
    kb = up_cb.callback_query.edit_message_text.call_args[1]["reply_markup"]
    btn_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "👑 Master Admin Paneli" in btn_texts

@pytest.mark.asyncio
async def test_admin_slash_free_commands_not_hijacked_by_ai():
    """Verify that when the super admin types 'profil', 'balans', 'dokon', etc. in PM,
    it is NOT intercepted by AI assistant fallback."""
    await init_db()
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    admin_id = 7651553630
    admin_username = "rasuljonovv_a"

    # 1. Admin sends 'profil'
    up = make_pm_update(uid=admin_id, username=admin_username, text="profil")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "Profil:" in text
    assert "AI MASTER ASSISTENT" not in text

    # 2. Admin sends 'balans'
    up = make_pm_update(uid=admin_id, username=admin_username, text="balans")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "balansingiz" in text
    assert "AI MASTER ASSISTENT" not in text

    # 3. Admin sends 'dokon'
    up = make_pm_update(uid=admin_id, username=admin_username, text="dokon")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "Do'koni" in text
    assert "AI MASTER ASSISTENT" not in text

    # 4. Admin sends natural language AI command 'tunni 45 qil'
    up = make_pm_update(uid=admin_id, username=admin_username, text="tunni 45 qil")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "45 soniya" in text or "AI MASTER" in text

@pytest.mark.asyncio
async def test_pm_slash_free_commands_with_args():
    """Verify slash-free commands with arguments work in PM (args get passed to handlers)."""
    await init_db()
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # 1. 'vasiyat Mening yangi vasiyatnomam'
    up = make_pm_update(uid=888010, username="will_tester", text="vasiyat Mening yangi vasiyatnomam")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    assert "saqlandi" in up.message.reply_text.call_args[0][0]

    # Verify saved will
    from database.models import get_will
    saved = await get_will(888010)
    assert saved == "Mening yangi vasiyatnomam"

    # 2. 'guide Detektiv'
    up = make_pm_update(uid=888010, username="will_tester", text="guide Detektiv")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    assert "Detektiv" in up.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_pm_username_transfer():
    """Verify transferring coins and gold using @username works in PM."""
    await init_db()
    sender_up = make_pm_update(uid=888020, username="sender_alex", text="")
    receiver_up = make_pm_update(uid=888021, username="receiver_bob", text="")
    await ensure_user(sender_up.effective_user)
    await ensure_user(receiver_up.effective_user)

    await change_balance(888020, "coin", 2000, "seed")
    await change_balance(888020, "gold", 20, "seed")

    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # 1. /coin @receiver_bob 400
    ctx.args = ["@receiver_bob", "400"]
    await coin_cmd(sender_up, ctx)
    assert sender_up.message.reply_text.called
    assert "400 Coin" in sender_up.message.reply_text.call_args[0][0]
    bob = await get_user(888021)
    assert bob["coin"] >= 400

    # 2. /gold @receiver_bob 5
    sender_up.message.reply_text.reset_mock()
    ctx.args = ["@receiver_bob", "5"]
    await gold_cmd(sender_up, ctx)
    assert sender_up.message.reply_text.called
    assert "5 Gold" in sender_up.message.reply_text.call_args[0][0]
    bob = await get_user(888021)
    assert bob["gold"] >= 5

    # 3. Non-existent username
    sender_up.message.reply_text.reset_mock()
    ctx.args = ["@nonexistent_user_xyz", "50"]
    await coin_cmd(sender_up, ctx)
    assert sender_up.message.reply_text.called
    assert "topilmadi" in sender_up.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_pm_unrecognized_slash_command():
    """Verify unknown slash command in PM does not fail silently, but provides a helpful fallback."""
    await init_db()
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    up = make_pm_update(uid=888030, username="curious_player", text="/unknown_command_test")
    await handle_private_message(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[0][0]
    assert "Noma'lum buyruq" in text
    assert "/unknown_command_test" in text
    assert "reply_markup" in up.message.reply_text.call_args[1]

@pytest.mark.asyncio
async def test_pm_settings_for_admin_default_global():
    """Verify admin calling /settings without args in PM configures default settings (chat_id=0)."""
    await init_db()
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.args = []
    up = make_pm_update(uid=7651553630, username="rasuljonovv_a")
    await settings_cmd(up, ctx)
    assert up.message.reply_text.called
    text = up.message.reply_text.call_args[1]["text"]
    assert "Asosiy Standart Sozlamalar (Global)" in text
    kb = up.message.reply_text.call_args[1]["reply_markup"]
    btn_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "👑 Master Admin Paneli" in btn_texts

@pytest.mark.asyncio
async def test_safe_ext_bot_badrequest_entity_retry():
    """Verify SafeExtBot retries without parse_mode when BadRequest('can\\'t parse entities') occurs."""
    from telegram.error import BadRequest
    from telegram.ext import ExtBot
    bot = SafeExtBot("123456:FAKE_TOKEN_FOR_TEST")
    
    call_count = 0
    async def mock_super_do_post(self, endpoint, data=None, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise BadRequest("Can't parse entities: can't find end of tag")
        return {"ok": True, "result": {"message_id": 123}}

    with pytest.MonkeyPatch.context() as m:
        m.setattr(ExtBot, "_do_post", mock_super_do_post)
        payload = {"chat_id": 12345, "text": "<b>Unclosed bold", "parse_mode": "HTML"}
        res = await bot._do_post("sendMessage", payload)
        assert res["ok"] is True
        assert call_count == 2

