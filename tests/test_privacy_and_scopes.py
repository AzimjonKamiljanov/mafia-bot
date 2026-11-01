import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import (
    BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats,
    BotCommandScopeChat, BotCommandScopeDefault
)
from database.db import init_db
from config import BOT_USERNAME, ADMIN_IDS
from bot import post_init, create_bot_app
from handlers.commands import (
    profile_cmd, balance_cmd, will_cmd, rating_cmd, guide_cmd, start_cmd,
    boost_cmd, salom_cmd, plan_cmd
)
from handlers.shop import shop_cmd, shop_callback_handler
from handlers.clans import clan_cmd, newclan_cmd
from handlers.social import mypara_cmd, mybro_cmd
from handlers.admin_panel import admin_cmd, stats_cmd, handle_admin_callback
from core.visuals import (
    anim_emoji, send_animated_dice_effect, send_animated_sticker,
    format_badge_with_anim_emoji, format_player_title_html,
    strip_anim_emoji_tags, TG_ANIMATED_EMOJIS
)
from core.audio_effects import send_atmospheric_message

@pytest.mark.asyncio
async def test_bot_command_scopes_registration():
    """Verify that Telegram set_my_commands enforces strict scope separation and default fallback safety."""
    await init_db()
    mock_app = MagicMock()
    mock_app.bot = MagicMock()
    mock_app.bot.set_my_commands = AsyncMock()

    await post_init(mock_app)

    calls = mock_app.bot.set_my_commands.call_args_list
    assert len(calls) >= 3, "set_my_commands must be called for default, group, private, and admin scopes"

    forbidden_in_groups = ["admin", "profile", "balance", "will", "shop", "guide", "rating", "clan", "stats", "plan"]

    # 0. Default scope fallback verification (MUST NOT leak admin commands)
    default_call = next(
        (c for c in calls if isinstance(c.kwargs.get("scope"), BotCommandScopeDefault)),
        None
    )
    assert default_call is not None, "BotCommandScopeDefault must be registered to sanitize fallback commands"
    default_cmd_names = [cmd.command for cmd in default_call.args[0]]
    for forbidden in forbidden_in_groups:
        assert forbidden not in default_cmd_names, f"{forbidden} must NOT be in default commands"

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

    # 8. /mypara in group
    up8 = make_group_update(uid=1008, first_name="Farrux")
    await mypara_cmd(up8, mock_context)
    assert up8.message.reply_text.called
    msg_text8 = up8.message.reply_text.call_args[0][0]
    kb8 = up8.message.reply_text.call_args[1]["reply_markup"]
    assert "Juftlik (Para) ma'lumotlari" in msg_text8
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=mypara" for row in kb8.inline_keyboard for btn in row)

    # 9. /mybro in group
    up9 = make_group_update(uid=1009, first_name="Jasur")
    await mybro_cmd(up9, mock_context)
    assert up9.message.reply_text.called
    msg_text9 = up9.message.reply_text.call_args[0][0]
    kb9 = up9.message.reply_text.call_args[1]["reply_markup"]
    assert "Birodarlik (Bro) ma'lumotlari" in msg_text9
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=mybro" for row in kb9.inline_keyboard for btn in row)

@pytest.mark.asyncio
async def test_admin_and_stats_group_privacy():
    """Verify that /admin, /stats, and /plan in groups protect admin controls and redirect admins to PM."""
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

    # 5. Non-admin calls /plan in group -> No response
    non_admin_up.message.reply_text.reset_mock()
    await plan_cmd(non_admin_up, mock_context)
    assert not non_admin_up.message.reply_text.called

    # 6. Admin calls /plan in group -> Redirects to PM with start=plan
    admin_up.message.reply_text.reset_mock()
    await plan_cmd(admin_up, mock_context)
    assert admin_up.message.reply_text.called
    plan_reply = admin_up.message.reply_text.call_args[0][0]
    plan_kb = admin_up.message.reply_text.call_args[1]["reply_markup"]
    assert "Admin boshqaruv rejasi faqat botning shaxsiy chatida ochiladi" in plan_reply
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=plan" for row in plan_kb.inline_keyboard for btn in row)

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

    # 6. /start plan in PM
    up.message.reply_text.reset_mock()
    mock_context.args = ["plan"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert "TO'LIQ O'YIN REJASI" in up.message.reply_text.call_args[0][0]

    # 7. /start boost in PM
    up.message.reply_text.reset_mock()
    mock_context.args = ["boost"]
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert "TELEGRAM PREMIUM" in up.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_boost_command_group_vs_pm():
    """Verify that /boost provides URL redirect in groups and callback buttons in PM."""
    mock_context = MagicMock()

    # 1. Group /boost
    group_up = MagicMock()
    group_up.effective_chat.type = "supergroup"
    group_up.effective_chat.id = -100555
    group_up.effective_user.id = 112233
    group_up.effective_user.username = "player"
    group_up.message = MagicMock()
    group_up.message.reply_text = AsyncMock()
    group_up.effective_message = group_up.message

    await boost_cmd(group_up, mock_context)
    assert group_up.message.reply_text.called
    g_kb = group_up.message.reply_text.call_args[1]["reply_markup"]
    # Group must have a safe URL button, NEVER a broken callback
    assert any(btn.url == f"https://t.me/{BOT_USERNAME}?start=shop" for row in g_kb.inline_keyboard for btn in row)

    # 2. PM /boost by Admin
    pm_up = MagicMock()
    pm_up.effective_chat.type = "private"
    pm_up.effective_chat.id = 7651553630
    pm_up.effective_user.id = 7651553630
    pm_up.effective_user.username = "rasuljonovv_a"
    pm_up.message = MagicMock()
    pm_up.message.reply_text = AsyncMock()
    pm_up.effective_message = pm_up.message

    await boost_cmd(pm_up, mock_context)
    assert pm_up.message.reply_text.called
    pm_kb = pm_up.message.reply_text.call_args[1]["reply_markup"]
    assert any(btn.callback_data == "shop_gold" for row in pm_kb.inline_keyboard for btn in row)
    assert any(btn.callback_data == "adm:menu" for row in pm_kb.inline_keyboard for btn in row)

@pytest.mark.asyncio
async def test_group_callbacks_privacy_protection():
    """Verify that shop and admin callbacks are strictly rejected if executed inside groups."""
    mock_context = MagicMock()

    # 1. Shop callback inside a group
    shop_q_up = MagicMock()
    shop_q_up.effective_chat.type = "supergroup"
    shop_q_up.effective_chat.id = -100444
    shop_q_up.callback_query = MagicMock()
    shop_q_up.callback_query.data = "shop_items"
    shop_q_up.callback_query.answer = AsyncMock()
    shop_q_up.callback_query.edit_message_text = AsyncMock()

    await shop_callback_handler(shop_q_up, mock_context)
    assert shop_q_up.callback_query.answer.called
    assert "shaxsiy chatida ishlaydi" in shop_q_up.callback_query.answer.call_args[0][0]
    assert not shop_q_up.callback_query.edit_message_text.called, "Must NOT leak inventory in group"

    # 2. Admin callback inside a group
    adm_q_up = MagicMock()
    adm_q_up.effective_chat.type = "supergroup"
    adm_q_up.effective_chat.id = -100444
    adm_q_up.callback_query = MagicMock()
    adm_q_up.callback_query.data = "adm:menu"
    adm_q_up.callback_query.answer = AsyncMock()
    adm_q_up.callback_query.edit_message_text = AsyncMock()
    adm_q_up.effective_user.id = 7651553630
    adm_q_up.effective_user.username = "rasuljonovv_a"

    res = await handle_admin_callback(adm_q_up, mock_context)
    assert res is True
    assert adm_q_up.callback_query.answer.called
    assert "shaxsiy chatida amalga oshiriladi" in adm_q_up.callback_query.answer.call_args[0][0]
    assert not adm_q_up.callback_query.edit_message_text.called, "Must NOT leak admin panel in group"

@pytest.mark.asyncio
async def test_visual_elements_and_animated_dice():
    """Verify custom animated emojis and safe dispatching of 3D animated dice."""
    assert "moon" in TG_ANIMATED_EMOJIS
    assert "<tg-emoji" in anim_emoji("moon")
    assert "<tg-emoji" in anim_emoji("crown")
    assert "<tg-emoji" in anim_emoji("gem")
    assert "<tg-emoji" in anim_emoji("🌙")
    assert "<tg-emoji" in anim_emoji("👑")

    mock_bot = MagicMock()
    mock_bot.send_dice = AsyncMock()
    mock_bot.send_sticker = AsyncMock()

    res = await send_animated_dice_effect(mock_bot, 123456, emoji="🎯")
    assert mock_bot.send_dice.called
    assert mock_bot.send_dice.call_args[1]["emoji"] == "🎯"

    # Safe error recovery check
    failing_bot = MagicMock()
    failing_bot.send_dice = AsyncMock(side_effect=Exception("API Network Error"))
    res_err = await send_animated_dice_effect(failing_bot, 123456, emoji="🎲")
    assert res_err is None, "Function should catch exception gracefully"

    # Animated sticker dispatcher check
    res_stk = await send_animated_sticker(mock_bot, 123456, sticker="test_sticker_id")
    assert mock_bot.send_sticker.called

    # Badge animated formatting check
    adm_badge = format_badge_with_anim_emoji("👑 Bosh Admin")
    assert "<tg-emoji" in adm_badge
    assert "👑" in adm_badge
    assert "Bosh Admin" in adm_badge

    lightning_badge = format_badge_with_anim_emoji("⚡ Yashin belgisi")
    assert "<tg-emoji" in lightning_badge

    # Player title formatting in HTML lobby check
    title = format_player_title_html({"names": {1: "PlayerOne"}, "badges": {1: "👑 Qirol Toji"}}, 1)
    assert "<tg-emoji" in title
    assert "PlayerOne" in title

    # Strip tags check
    raw_text = "<tg-emoji emoji-id=\"123\">🌙</tg-emoji> Kechasi"
    clean = strip_anim_emoji_tags(raw_text)
    assert clean == "🌙 Kechasi"

@pytest.mark.asyncio
async def test_atmospheric_message_animated_dice_trigger():
    """Verify send_atmospheric_message triggers 3D physics dice for night and execution."""
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_dice = AsyncMock()

    # Night trigger
    await send_atmospheric_message(mock_bot, 123456, "Tun kirdi", sound_type="night")
    assert mock_bot.send_dice.called
    assert mock_bot.send_dice.call_args[1]["emoji"] == "🎲"

    # Execution trigger
    mock_bot.send_dice.reset_mock()
    await send_atmospheric_message(mock_bot, 123456, "Qatl bo'ldi", sound_type="execution")
    assert mock_bot.send_dice.called
    assert mock_bot.send_dice.call_args[1]["emoji"] == "🎯"

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
    await plan_cmd(none_user_up, mock_context)
    await boost_cmd(none_user_up, mock_context)
    await mypara_cmd(none_user_up, mock_context)
    await mybro_cmd(none_user_up, mock_context)
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

def test_custom_emojis_full_suite():
    """Exhaustive test for Telegram Premium Custom Emojis integration."""
    from core.emojis import tg_emoji, render_custom_emoji, strip_anim_emoji_tags, EMOJI_CONFIG
    from bot import SafeExtBot
    import pytest

    # 1. Verify all 11 required active emoji IDs
    active_ids = {
        "game_start": "3191530815439765550",
        "mafia": "1269403972611866648",
        "don": "919985748604617114",
        "detective": "1740555807604342805",
        "doctor": "3191530815439765548",
        "night": "4158409751421517834",
        "day": "336920350212227127",
        "dead": "3974262500324540463",
        "civilian": "1471004892762996745",
        "mafia_win": "1145788388561911824",
        "timer": "3024877442880766280",
    }
    for key, doc_id in active_ids.items():
        tag = tg_emoji(key)
        assert f'<tg-emoji emoji-id="{doc_id}">' in tag
        assert tag.endswith("</tg-emoji>")

    # 2. render_custom_emoji category checks
    res_game = render_custom_emoji("GAMEPLAY", "doctor")
    assert '<tg-emoji emoji-id="3191530815439765548">🩺</tg-emoji>' == res_game

    res_shop = render_custom_emoji("SHOP", "coin")
    assert '<tg-emoji emoji-id="1471004892762996745">🪙</tg-emoji>' == res_shop

    res_unknown = render_custom_emoji("UNKNOWN", "nonexistent", fallback="❓")
    assert res_unknown == "❓"

    # 3. Direct numeric ID rendering
    res_direct_id = tg_emoji("3191530815439765550", fallback="🎮")
    assert res_direct_id == '<tg-emoji emoji-id="3191530815439765550">🎮</tg-emoji>'

    # 4. Unknown key fallback
    assert tg_emoji("random_unknown_key_xyz", fallback="⭐") == "⭐"

    # 5. strip_anim_emoji_tags edge cases
    assert strip_anim_emoji_tags("") == ""
    assert strip_anim_emoji_tags(None) is None
    assert strip_anim_emoji_tags("Plain text with no tags") == "Plain text with no tags"
    multi_tag = '<tg-emoji document-id="123">🔪</tg-emoji> Killer vs <tg-emoji document-id="456">🩺</tg-emoji> Doctor'
    assert strip_anim_emoji_tags(multi_tag) == "🔪 Killer vs 🩺 Doctor"
    legacy_tag = '<tg-emoji emoji-id="789">🌙</tg-emoji> Tun'
    assert strip_anim_emoji_tags(legacy_tag) == "🌙 Tun"


@pytest.mark.asyncio
async def test_safe_ext_bot_overrides_markdown_for_tg_emoji():
    """Verify SafeExtBot overrides parse_mode='Markdown' to 'HTML' when <tg-emoji> is present."""
    from telegram.ext import ExtBot
    from bot import SafeExtBot
    from core.emojis import tg_emoji

    bot = SafeExtBot("123456:FAKE_TOKEN_FOR_TEST")
    
    captured_data = []
    async def mock_super_do_post(self, endpoint, data=None, *args, **kwargs):
        captured_data.append(dict(data) if data else {})
        return {"ok": True, "result": {"message_id": 123}}

    with pytest.MonkeyPatch.context() as m:
        m.setattr(ExtBot, "_do_post", mock_super_do_post)

        # 1. Text with tg-emoji and parse_mode="Markdown" -> overridden to "HTML"
        text_with_emoji = f"{tg_emoji('mafia')} Killer"
        await bot._do_post("sendMessage", {"chat_id": 123, "text": text_with_emoji, "parse_mode": "Markdown"})
        assert len(captured_data) == 1
        assert captured_data[-1]["parse_mode"] == "HTML"

        # 2. Caption with tg-emoji and parse_mode="Markdown" -> overridden to "HTML"
        cap_with_emoji = f"{tg_emoji('night')} Night time"
        await bot._do_post("sendPhoto", {"chat_id": 123, "caption": cap_with_emoji, "parse_mode": "Markdown"})
        assert len(captured_data) == 2
        assert captured_data[-1]["parse_mode"] == "HTML"

        # 3. Text without tg-emoji and parse_mode="Markdown" -> untouched
        plain_md = "*Bold* text"
        await bot._do_post("sendMessage", {"chat_id": 123, "text": plain_md, "parse_mode": "Markdown"})
        assert len(captured_data) == 3
        assert captured_data[-1]["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_shop_inventory_render_and_badge_activation():
    """Verify render_shop_inventory and shop_items alias function without NameError."""
    from handlers.shop import render_shop_inventory, shop_items, shop_callback_handler
    from database.models import ensure_user, save_owned_badge

    await init_db()
    uid = 88001
    mock_user = MagicMock()
    mock_user.id = uid
    mock_user.first_name = "ShopUser"
    mock_user.username = "shop_user"
    mock_user.full_name = "ShopUser"
    await ensure_user(mock_user)
    await save_owned_badge(uid, "crown", "👑 Toj")

    # Verify alias exists and is callable
    assert shop_items == render_shop_inventory

    # Test badge activation callback
    q = AsyncMock()
    q.data = "item:badge:crown"
    q.from_user = mock_user
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    up = MagicMock()
    up.callback_query = q
    ctx = MagicMock()

    await shop_callback_handler(up, ctx)
    assert q.answer.called
    assert "faollashtirildi" in q.answer.call_args[0][0]
    assert q.edit_message_text.called

    # Test badge deactivation callback
    q.reset_mock()
    q.data = "item:off"
    await shop_callback_handler(up, ctx)
    assert q.answer.called
    assert "olib tashlandi" in q.answer.call_args[0][0]
    assert q.edit_message_text.called


@pytest.mark.asyncio
async def test_will_formatting_html_with_custom_emoji():
    """Verify format_will_announcement produces valid HTML with tg_emoji."""
    from core.will import format_will_announcement

    out = format_will_announcement("Ali <Sher>", "Haqiqat egiladi, bukilmaydi!")
    assert "<tg-emoji" in out
    assert "<b>Ali &lt;Sher&gt;ning So'nggi Vasiyatnomasi:</b>" in out
    assert "<blockquote><i>Haqiqat egiladi, bukilmaydi!</i></blockquote>" in out


@pytest.mark.asyncio
async def test_start_act_deep_link_html_parse_mode():
    """Verify that /start act_<chat_id> uses HTML parse mode for all phases."""
    from handlers.commands import start_cmd
    from core.engine import games

    chat_id = -1008899
    game = {
        "chat": chat_id,
        "players": [99901],
        "names": {99901: "Tester"},
        "roles": {99901: "Fuqaro"},
        "alive": {99901: True},
        "phase": "night",
        "night": 1,
        "night_done": set(),
        "group_link": "https://t.me/test_group"
    }
    games[chat_id] = game

    mock_context = MagicMock()
    up = MagicMock()
    up.effective_user.id = 99901
    up.effective_user.full_name = "Tester"
    up.effective_user.username = "tester"
    up.effective_chat.type = "private"
    up.message.reply_text = AsyncMock()

    mock_context.args = [f"act_{chat_id}"]

    # 1. Night phase
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert up.message.reply_text.call_args[1].get("parse_mode") == "HTML"

    # 2. Voting phase
    game["phase"] = "voting"
    up.message.reply_text.reset_mock()
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert up.message.reply_text.call_args[1].get("parse_mode") == "HTML"

    # 3. Verdict phase
    game["phase"] = "verdict"
    game["accused_uid"] = 99901
    up.message.reply_text.reset_mock()
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert up.message.reply_text.call_args[1].get("parse_mode") == "HTML"

    # 4. Graveyard (dead player)
    game["alive"][99901] = False
    up.message.reply_text.reset_mock()
    await start_cmd(up, mock_context)
    assert up.message.reply_text.called
    assert up.message.reply_text.call_args[1].get("parse_mode") == "HTML"

    games.pop(chat_id, None)


@pytest.mark.asyncio
async def test_commands_custom_emoji_rich_output():
    """Verify plan, boost, goal, and teamwork commands output custom emoji tags."""
    from handlers.commands import plan_cmd, boost_cmd, goal_cmd, teamwork_cmd

    up = MagicMock()
    up.effective_user.id = 7651553630
    up.effective_user.username = "rasuljonovv_a"
    up.effective_user.first_name = "Admin"
    up.effective_chat.type = "private"
    up.effective_chat.id = 7651553630
    up.message.reply_text = AsyncMock()
    up.effective_message = up.message
    ctx = MagicMock()

    # /plan
    await plan_cmd(up, ctx)
    plan_out = up.message.reply_text.call_args[0][0]
    assert "<tg-emoji emoji-id=" in plan_out

    # /boost
    up.message.reply_text.reset_mock()
    await boost_cmd(up, ctx)
    boost_out = up.message.reply_text.call_args[0][0]
    assert "<tg-emoji emoji-id=" in boost_out

    # /goal
    up.message.reply_text.reset_mock()
    await goal_cmd(up, ctx)
    goal_out = up.message.reply_text.call_args[0][0]
    assert "<tg-emoji emoji-id=" in goal_out

    # /teamwork
    up.message.reply_text.reset_mock()
    await teamwork_cmd(up, ctx)
    tw_out = up.message.reply_text.call_args[0][0]
    assert "<tg-emoji emoji-id=" in tw_out


