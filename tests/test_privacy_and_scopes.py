import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import (
    BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeChat
)
from database.db import init_db
from config import BOT_USERNAME, ADMIN_IDS
from bot import post_init, create_bot_app
from handlers.commands import (
    profile_cmd, balance_cmd, will_cmd, rating_cmd, guide_cmd, start_cmd, boost_cmd, salom_cmd
)
from handlers.shop import shop_cmd
from handlers.clans import clan_cmd, newclan_cmd
from handlers.admin_panel import admin_cmd, stats_cmd
from core.visuals import anim_emoji, send_animated_dice_effect, TG_ANIMATED_EMOJIS

@pytest.mark.asyncio
async def test_bot_command_scopes_registration():
    """Verify that Telegram set_my_commands enforces strict scope separation."""
    await init_db()
    mock_app = MagicMock()
    mock_app.bot = MagicMock()
    mock_app.bot.set_my_commands = AsyncMock()

    await post_init(mock_app)

    calls = mock_app.bot.set_my_commands.call_args_list
    assert len(calls) >= 2, "set_my_commands must be called for group, private, and admin scopes"

    # 1. Group chats scope verification
    group_call = next(
        (c for c in calls if isinstance(c.kwargs.get("scope"), BotCommandScopeAllGroupChats)),
        None
    )
    assert group_call is not None, "BotCommandScopeAllGroupChats must be registered"
    group_cmd_names = [cmd.command for cmd in group_call.args[0]]

    # MUST contain group game commands
    for expected_cmd in ["game", "startgame", "call", "settings", "salom", "stop", "chiqish", "para", "bro", "send"]:
        assert expected_cmd in group_cmd_names, f"Expected {expected_cmd} in group commands"

    # NEVER show private/admin commands in group chats!
    forbidden_in_groups = ["admin", "profile", "balance", "will", "shop", "guide", "rating", "clan", "stats"]
    for forbidden in forbidden_in_groups:
        assert forbidden not in group_cmd_names, f"{forbidden} must NOT be visible in group commands"

    # 2. Private chats scope verification
    private_call = next(
        (c for c in calls if isinstance(c.kwargs.get("scope"), BotCommandScopeAllPrivateChats)),
        None
    )
    assert private_call is not None, "BotCommandScopeAllPrivateChats must be registered"
    private_cmd_names = [cmd.command for cmd in private_call.args[0]]

    expected_private = ["start", "profile", "balance", "will", "shop", "rating", "guide", "clan", "salom"]
    for expected in expected_private:
        assert expected in private_cmd_names, f"Expected {expected} in private commands"

    assert "admin" not in private_cmd_names, "/admin must not be exposed to all private chats"

    # 3. Admin scope verification
    admin_calls = [
        c for c in calls if isinstance(c.kwargs.get("scope"), BotCommandScopeChat)
    ]
    assert len(admin_calls) > 0, "BotCommandScopeChat must be registered for admins"
    primary_admin_call = next(
        (c for c in admin_calls if c.kwargs["scope"].chat_id == 7651553630),
        None
    )
    assert primary_admin_call is not None, "Primary admin (7651553630) must have dedicated command scope"
    admin_cmd_names = [cmd.command for cmd in primary_admin_call.args[0]]

    expected_admin = ["admin", "settings", "stats", "plan", "start", "profile", "balance", "shop", "guide", "rating", "boost"]
    for expected in expected_admin:
        assert expected in admin_cmd_names, f"Expected {expected} in admin command scope"

@pytest.mark.asyncio
async def test_group_to_pm_privacy_redirection_for_personal_commands():
    """Verify that calling personal commands in public groups never leaks private info and redirects to PM."""
    await init_db()

    def make_group_update(uid=55555, first_name="Ali"):
        up = MagicMock()
        up.effective_chat.type = "supergroup"
        up.effective_chat.id = -100123456789
        up.effective_user.id = uid
        up.effective_user.first_name = first_name
        up.effective_user.full_name = f"{first_name} Testov"
        up.effective_user.username = f"{first_name.lower()}_tg"
        up.message = MagicMock()
        up.message.reply_text = AsyncMock()
        up.effective_message = up.message
        return up

    mock_context = MagicMock()
    mock_context.args = []

    # 1. /profile in group
    up1 = make_group_update(uid=1001, first_name="Tohir")
    await profile_cmd(up1, mock_context)
    assert up1.message.reply_text.called
    msg_text1 = up1.message.reply_text.call_args[0][0]
    kb1 = up1.message.reply_text.call_args[1]["reply_markup"]
    assert "Tangalar" not in msg_text1, "Group message must NOT display user coin balances"
    assert "maxfiyligini saqlash" in msg_text1
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=profile" for row in kb1.inline_keyboard for btn in row)

    # 2. /balance in group
    up2 = make_group_update(uid=1002, first_name="Zuhra")
    await balance_cmd(up2, mock_context)
    assert up2.message.reply_text.called
    msg_text2 = up2.message.reply_text.call_args[0][0]
    kb2 = up2.message.reply_text.call_args[1]["reply_markup"]
    assert "Coin" not in msg_text2, "Group message must NOT display coin balances"
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=balance" for row in kb2.inline_keyboard for btn in row)

    # 3. /will in group
    up3 = make_group_update(uid=1003, first_name="Salim")
    mock_context.args = ["Mening", "sirli", "vasiyatim"]
    await will_cmd(up3, mock_context)
    assert up3.message.reply_text.called
    msg_text3 = up3.message.reply_text.call_args[0][0]
    kb3 = up3.message.reply_text.call_args[1]["reply_markup"]
    assert "Mening sirli vasiyatim" not in msg_text3, "Will text must NOT be printed in group"
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=will" for row in kb3.inline_keyboard for btn in row)

    # 4. /shop in group
    up4 = make_group_update(uid=1004, first_name="Malika")
    mock_context.args = []
    await shop_cmd(up4, mock_context)
    assert up4.message.reply_text.called
    msg_text4 = up4.message.reply_text.call_args[0][0]
    kb4 = up4.message.reply_text.call_args[1]["reply_markup"]
    assert "xarid qilish va inventarni boshqarish faqat botning shaxsiy chatida" in msg_text4
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=shop" for row in kb4.inline_keyboard for btn in row)

    # 5. /rating in group
    up5 = make_group_update(uid=1005, first_name="Vali")
    await rating_cmd(up5, mock_context)
    assert up5.message.reply_text.called
    msg_text5 = up5.message.reply_text.call_args[0][0]
    kb5 = up5.message.reply_text.call_args[1]["reply_markup"]
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=rating" for row in kb5.inline_keyboard for btn in row)

    # 6. /guide in group
    up6 = make_group_update(uid=1006, first_name="Karim")
    await guide_cmd(up6, mock_context)
    assert up6.message.reply_text.called
    msg_text6 = up6.message.reply_text.call_args[0][0]
    kb6 = up6.message.reply_text.call_args[1]["reply_markup"]
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=guide" for row in kb6.inline_keyboard for btn in row)

    # 7. /clan in group
    up7 = make_group_update(uid=1007, first_name="Anvar")
    await clan_cmd(up7, mock_context)
    assert up7.message.reply_text.called
    msg_text7 = up7.message.reply_text.call_args[0][0]
    kb7 = up7.message.reply_text.call_args[1]["reply_markup"]
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=clan" for row in kb7.inline_keyboard for btn in row)

@pytest.mark.asyncio
async def test_admin_and_stats_group_privacy():
    """Verify that /admin and /stats in groups protect admin controls and redirect admins to PM."""
    await init_db()

    def make_group_update(uid, username, first_name):
        up = MagicMock()
        up.effective_chat.type = "supergroup"
        up.effective_chat.id = -100987654321
        up.effective_user.id = uid
        up.effective_user.username = username
        up.effective_user.first_name = first_name
        up.effective_user.full_name = f"{first_name} AdminTest"
        up.message = MagicMock()
        up.message.reply_text = AsyncMock()
        up.effective_message = up.message
        return up

    mock_context = MagicMock()

    # 1. Non-admin calls /admin in group -> SILENT NO ACCESS (no leakage)
    non_admin_up = make_group_update(uid=112233, username="random_user", first_name="Random")
    await admin_cmd(non_admin_up, mock_context)
    assert not non_admin_up.message.reply_text.called, "Non-admin in group should receive NO access or response"

    # 2. Admin calls /admin in group -> Redirects to PM with start=admin
    admin_up = make_group_update(uid=7651553630, username="rasuljonovv_a", first_name="Azimjon")
    await admin_cmd(admin_up, mock_context)
    assert admin_up.message.reply_text.called
    admin_reply = admin_up.message.reply_text.call_args[0][0]
    admin_kb = admin_up.message.reply_text.call_args[1]["reply_markup"]
    assert "admin boshqaruv paneli guruhda ochilmaydi" in admin_reply
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=admin" for row in admin_kb.inline_keyboard for btn in row)

    # 3. Non-admin calls /stats in group -> No response
    non_admin_up.message.reply_text.reset_mock()
    await stats_cmd(non_admin_up, mock_context)
    assert not non_admin_up.message.reply_text.called

    # 4. Admin calls /stats in group -> Redirects to PM with start=stats
    admin_up.message.reply_text.reset_mock()
    await stats_cmd(admin_up, mock_context)
    assert admin_up.message.reply_text.called
    stats_reply = admin_up.message.reply_text.call_args[0][0]
    stats_kb = admin_up.message.reply_text.call_args[1]["reply_markup"]
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=stats" for row in stats_kb.inline_keyboard for btn in row)

@pytest.mark.asyncio
async def test_start_command_deep_link_dispatch():
    """Verify that start deep links route directly to personal and admin views in PM."""
    await init_db()

    def make_pm_update(uid=7651553630, username="rasuljonovv_a"):
        up = MagicMock()
        up.effective_chat.type = "private"
        up.effective_chat.id = uid
        up.effective_user.id = uid
        up.effective_user.username = username
        up.effective_user.first_name = "Admin"
        up.effective_user.full_name = "Admin User"
        up.message = MagicMock()
        up.message.reply_text = AsyncMock()
        up.effective_message = up.message
        return up

    # 1. /start profile in PM
    up = make_pm_update()
    mock_context = MagicMock()
    mock_context.args = ["profile"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert "Profil:" in up.message.reply_text.call_args[0][0]

    # 2. /start balance in PM
    up.message.reply_text.reset_mock()
    mock_context.args = ["balance"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert "Sizning balansingiz:" in up.message.reply_text.call_args[0][0]

    # 3. /start will in PM
    up.message.reply_text.reset_mock()
    mock_context.args = ["will"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert "Vasiyatnoma" in up.message.reply_text.call_args[0][0]

    # 4. /start admin in PM by admin
    up.message.reply_text.reset_mock()
    mock_context.args = ["admin"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert "MASTER ADMIN BOSHQARUV PANELI" in up.message.reply_text.call_args[0][0]

    # 5. /start stats in PM
    up.message.reply_text.reset_mock()
    mock_context.args = ["stats"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert "STATISTIKASI" in up.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_visual_elements_and_animated_dice():
    """Verify custom animated emojis and safe dispatching of 3D animated dice."""
    assert "moon" in TG_ANIMATED_EMOJIS
    assert "<tg-emoji" in anim_emoji("moon")
    assert "<tg-emoji" in anim_emoji("crown")
    assert "<tg-emoji" in anim_emoji("gem")

    mock_bot = MagicMock()
    mock_bot.send_dice = AsyncMock()

    res = await send_animated_dice_effect(mock_bot, 123456, emoji="🎯")
    assert mock_bot.send_dice.called
    assert mock_bot.send_dice.call_args[1]["emoji"] == "🎯"

    # Safe error recovery check
    failing_bot = MagicMock()
    failing_bot.send_dice = AsyncMock(side_effect=Exception("API Network Error"))
    res_err = await send_animated_dice_effect(failing_bot, 123456, emoji="🎲")
    assert res_err is None, "Function should catch exception gracefully"

@pytest.mark.asyncio
async def test_edge_cases_and_none_handling():
    """Verify handlers handle None objects, missing users, and non-admin access gracefully."""
    await init_db()
    mock_context = MagicMock()
    mock_context.args = []

    # 1. Update with None user
    none_user_up = MagicMock()
    none_user_up.effective_user = None
    none_user_up.effective_chat = MagicMock()
    none_user_up.message = MagicMock()
    none_user_up.message.reply_text = AsyncMock()

    await profile_cmd(none_user_up, mock_context)
    await balance_cmd(none_user_up, mock_context)
    await will_cmd(none_user_up, mock_context)
    await shop_cmd(none_user_up, mock_context)
    await clan_cmd(none_user_up, mock_context)
    await admin_cmd(none_user_up, mock_context)
    await stats_cmd(none_user_up, mock_context)
    assert not none_user_up.message.reply_text.called

    # 2. Non-admin accessing /start admin in PM
    regular_up = MagicMock()
    regular_up.effective_chat.type = "private"
    regular_up.effective_chat.id = 998877
    regular_up.effective_user.id = 998877
    regular_up.effective_user.username = "ordinary_player"
    regular_up.effective_user.first_name = "Ordinary"
    regular_up.effective_user.full_name = "Ordinary User"
    regular_up.message = MagicMock()
    regular_up.message.reply_text = AsyncMock()
    regular_up.effective_message = regular_up.message

    mock_context.args = ["admin"]
    await start_cmd(regular_up, mock_context)
    assert regular_up.message.reply_text.called
    assert "Super Adminlari" in regular_up.message.reply_text.call_args[0][0]

    # 3. newclan_cmd in group
    group_up = MagicMock()
    group_up.effective_chat.type = "group"
    group_up.effective_chat.id = -100445566
    group_up.effective_user.id = 1234
    group_up.effective_user.username = "clan_tester"
    group_up.effective_user.first_name = "ClanTester"
    group_up.message = MagicMock()
    group_up.message.reply_text = AsyncMock()
    group_up.effective_message = group_up.message

    await newclan_cmd(group_up, mock_context)
    assert group_up.message.reply_text.called
    assert "Klan tuzish va boshqarish faqat botning shaxsiy chatida" in group_up.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_create_bot_app_registers_all_handlers():
    """Verify application builds and registers handlers properly."""
    app = create_bot_app()
    assert app is not None
    # Inspect registered command handlers
    registered_cmds = set()
    for h_list in app.handlers.values():
        for h in h_list:
            if hasattr(h, "commands"):
                registered_cmds.update(h.commands)

    expected = {"start", "game", "admin", "stats", "profile", "balance", "will", "shop", "guide", "rating", "clan", "boost"}
    for cmd in expected:
        assert cmd in registered_cmds, f"Handler for /{cmd} must be registered in bot app"

