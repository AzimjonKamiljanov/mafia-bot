import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import User, Chat, Message, Update, ChatMember, ChatMemberUpdated

from handlers.commands import salom_cmd, call_players_cmd
from phases.lobby import call_players_in_chat, lobbies
from bot import track_group_user, track_chat_member_updated
from database.models import track_group_member, get_group_members, ensure_user
from database.db import init_db

@pytest.mark.asyncio
async def test_salom_cmd_greeting_and_mention():
    await init_db()
    user = User(id=777888999, first_name="Ali", last_name="Valiyev", is_bot=False, username="alivali")
    chat = Chat(id=-100999888777, type="supergroup")
    message = MagicMock(spec=Message)
    message.message_id = 42
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    await salom_cmd(update, context)

    # Verify reply_text was called
    message.reply_text.assert_called_once()
    args, kwargs = message.reply_text.call_args
    sent_text = args[0]

    # Verify HTML mention is present
    assert 'href="tg://user?id=777888999"' in sent_text
    assert 'Ali Valiyev' in sent_text
    assert '@alivali' in sent_text
    assert 'Assalomu alaykum' in sent_text
    assert kwargs.get("parse_mode") == "HTML"
    assert kwargs.get("reply_to_message_id") == 42

    # Verify user was saved in group_users
    members = await get_group_members(-100999888777)
    uids = [m["user_id"] for m in members]
    assert 777888999 in uids

@pytest.mark.asyncio
async def test_track_new_chat_members():
    await init_db()
    chat_id = -100555444333
    chat = Chat(id=chat_id, type="supergroup")

    new_user1 = User(id=111001, first_name="Jasur", is_bot=False, username="jasur_dev")
    new_user2 = User(id=111002, first_name="Malika", is_bot=False)

    message = MagicMock(spec=Message)
    message.new_chat_members = [new_user1, new_user2]

    update = MagicMock(spec=Update)
    update.effective_user = new_user1
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    await track_group_user(update, context)

    members = await get_group_members(chat_id)
    uids = [m["user_id"] for m in members]
    assert 111001 in uids
    assert 111002 in uids

@pytest.mark.asyncio
async def test_track_chat_member_updated_join():
    await init_db()
    chat_id = -100666555444
    chat = Chat(id=chat_id, type="supergroup")
    user = User(id=222001, first_name="Temur", is_bot=False, username="temur_99")

    chat_member = MagicMock(spec=ChatMember)
    chat_member.status = "member"
    chat_member.user = user

    cmu = MagicMock(spec=ChatMemberUpdated)
    cmu.chat = chat
    cmu.new_chat_member = chat_member

    update = MagicMock(spec=Update)
    update.chat_member = cmu

    context = MagicMock()

    await track_chat_member_updated(update, context)

    members = await get_group_members(chat_id)
    uids = [m["user_id"] for m in members]
    assert 222001 in uids

@pytest.mark.asyncio
async def test_call_players_in_chat_mentions_all_and_chunks():
    await init_db()
    chat_id = -100777888999

    # Add 12 fake members to group_users
    for i in range(12):
        u = User(id=500000 + i, first_name=f"Player_{i}", is_bot=False, username=f"user_{i}")
        await track_group_member(chat_id, u)

    bot_user = MagicMock()
    bot_user.id = 999999999

    context = MagicMock()
    context.bot.id = bot_user.id
    context.bot.send_message = AsyncMock()
    # Mock get_chat_administrators returning empty list
    context.bot.get_chat_administrators = AsyncMock(return_value=[])

    lobbies[chat_id] = {
        "open": True,
        "players": [500000], # One player already joined
        "names": {500000: "Player_0"},
        "badges": {}
    }

    try:
        await call_players_in_chat(context, chat_id, caller_name="Boss")

        # 12 members - 1 joined = 11 candidates.
        # CHUNK_SIZE is 8, so 2 messages should be sent (8 + 3).
        assert context.bot.send_message.call_count == 2

        # Check first message contains header, caller, mentions
        first_call = context.bot.send_message.call_args_list[0]
        first_text = first_call[1]["text"]
        assert "DIQQAT, MAFIA O'YINIGA CHORLOV" in first_text
        assert "Boss" in first_text
        assert "Chaqirilganlar (1/2)" in first_text
        assert "Player_11" in first_text

        # Check second message contains remaining candidates
        second_call = context.bot.send_message.call_args_list[1]
        second_text = second_call[1]["text"]
        assert "Chaqirilganlar (2/2)" in second_text
        assert "Player_1" in second_text

    finally:
        lobbies.pop(chat_id, None)
