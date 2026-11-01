import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Chat, Message, CallbackQuery

from config import COIN_SHOP
from database.db import init_db
from database.models import (
    ensure_user, add_item, get_inventory, change_balance
)
from core.items import (
    has_used_item, mark_item_used, consume_game_item,
    ALREADY_USED_MSG, NO_ITEM_MSG
)
from phases.verdict import resolve_verdict
from phases.night import complete_night_resolution
from phases.voting import finish_voting
from handlers.callbacks import callback_router
from handlers.commands import use_item_cmd
from handlers.shop import shop_callback_handler
from core.engine import games

class MockUser:
    def __init__(self, uid: int, first_name: str = "Player", username: str = "player"):
        self.id = uid
        self.first_name = first_name
        self.username = username
        self.full_name = first_name
        self.is_bot = False

class MockChat:
    def __init__(self, cid: int, chat_type: str = "supergroup"):
        self.id = cid
        self.type = chat_type

def make_mock_context():
    ctx = MagicMock()
    ctx.bot = AsyncMock()
    ctx.bot.send_message = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_ruler_protection_strictly_once_per_game():
    """Test that ruler_protection (execution shield) works only 1 time in a single game."""
    await init_db()
    accused_uid = 91001
    voter_uid = 91002
    u1 = MockUser(accused_uid, "Accused")
    u2 = MockUser(voter_uid, "Voter")
    await ensure_user(u1)
    await ensure_user(u2)

    # Give player 10 ruler_protections
    await add_item(accused_uid, "ruler_protection", 10)
    inv = await get_inventory(accused_uid)
    initial_shields = inv.get("ruler_protection", 0)
    assert initial_shields >= 10

    chat_id = -10091001
    game = {
        "chat": chat_id,
        "players": [accused_uid, voter_uid],
        "names": {accused_uid: "Accused", voter_uid: "Voter"},
        "roles": {accused_uid: "Fuqaro", voter_uid: "Detektiv"},
        "alive": {accused_uid: True, voter_uid: True},
        "phase": "verdict",
        "accused_uid": accused_uid,
        "verdict_votes": {voter_uid: "kill"},
        "mayor_revealed": set(),
        "used_items": {},
        "night": 1
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # FIRST VERDICT: Player is saved by ruler_protection
    await resolve_verdict(ctx, game)
    assert game["alive"][accused_uid] is True, "Accused must survive the 1st execution"
    assert has_used_item(game, accused_uid, "ruler_protection") is True
    inv_after_1 = await get_inventory(accused_uid)
    assert inv_after_1["ruler_protection"] == initial_shields - 1, "Exactly 1 item consumed"

    # Reset phase to verdict again in the SAME game for the SAME player
    game["phase"] = "verdict"
    game["accused_uid"] = accused_uid
    game["verdict_votes"] = {voter_uid: "kill"}
    game["weather"] = None

    # SECOND VERDICT: Player has remaining shields, but CANNOT use another in the same game!
    await resolve_verdict(ctx, game)
    assert game["alive"][accused_uid] is False, "Accused must be executed on 2nd attempt in same game"
    inv_after_2 = await get_inventory(accused_uid)
    assert inv_after_2["ruler_protection"] == initial_shields - 1, "No additional item consumed on 2nd attempt"

    # Verify alert message was sent to accused on second attempt
    send_calls = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list]
    assert any("allaqachon foydalangansiz" in t for t in send_calls)

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_night_protection_strictly_once_per_game():
    """Test that night protection (protection) works only 1 time in a single game."""
    await init_db()
    victim_uid = 92001
    attacker_uid = 92002
    u1 = MockUser(victim_uid, "Victim")
    u2 = MockUser(attacker_uid, "Attacker")
    await ensure_user(u1)
    await ensure_user(u2)

    # Give player 5 protections
    await add_item(victim_uid, "protection", 5)
    inv = await get_inventory(victim_uid)
    initial_prot = inv.get("protection", 0)
    assert initial_prot >= 5

    chat_id = -10092001
    game = {
        "chat": chat_id,
        "players": [victim_uid, attacker_uid],
        "names": {victim_uid: "Victim", attacker_uid: "Attacker"},
        "roles": {victim_uid: "Fuqaro", attacker_uid: "Qotil"},
        "alive": {victim_uid: True, attacker_uid: True},
        "phase": "night",
        "used_items": {},
        "night": 1
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # NIGHT 1: Attack lands, protection saves victim
    deaths_1 = {victim_uid}
    causes_1 = {victim_uid: ["Pichoqlandi"]}
    clues_1 = {}
    saved_1 = set()
    attacks_1 = [{"attacker": attacker_uid, "target": victim_uid, "role": "Qotil"}]

    await complete_night_resolution(ctx, game, deaths_1, causes_1, clues_1, saved_1, attacks_1)
    assert victim_uid not in deaths_1, "Victim must be saved on Night 1"
    assert has_used_item(game, victim_uid, "protection") is True
    inv_after_1 = await get_inventory(victim_uid)
    assert inv_after_1["protection"] == initial_prot - 1, "Exactly 1 protection consumed"

    # NIGHT 2: Another attack lands in the SAME game
    deaths_2 = {victim_uid}
    causes_2 = {victim_uid: ["Pichoqlandi"]}
    clues_2 = {}
    saved_2 = set()
    attacks_2 = [{"attacker": attacker_uid, "target": victim_uid, "role": "Qotil"}]

    await complete_night_resolution(ctx, game, deaths_2, causes_2, clues_2, saved_2, attacks_2)
    assert victim_uid in deaths_2, "Victim must NOT be saved on Night 2 (already used in this game)"
    inv_after_2 = await get_inventory(victim_uid)
    assert inv_after_2["protection"] == initial_prot - 1, "No additional protection consumed"

    # Verify alert message sent
    send_calls = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list]
    assert any("allaqachon foydalangansiz" in t for t in send_calls)

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_fake_document_strictly_once_per_game():
    """Test that fake_document disguises a red player only once per game."""
    await init_db()
    mafia_uid = 93001
    det_uid = 93002
    u1 = MockUser(mafia_uid, "MafiaDon")
    u2 = MockUser(det_uid, "Detective")
    await ensure_user(u1)
    await ensure_user(u2)

    await add_item(mafia_uid, "fake_document", 3)
    inv = await get_inventory(mafia_uid)
    initial_docs = inv.get("fake_document", 0)
    assert initial_docs >= 3

    chat_id = -10093001
    game = {
        "chat": chat_id,
        "players": [mafia_uid, det_uid],
        "names": {mafia_uid: "MafiaDon", det_uid: "Detective"},
        "roles": {mafia_uid: "Boshliq", det_uid: "Detektiv"},
        "alive": {mafia_uid: True, det_uid: True},
        "phase": "night",
        "used_items": {},
        "detective_results": {str(det_uid): {"target": mafia_uid}},
        "night": 1
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # NIGHT 1: Detective investigates MafiaDon. Fake document triggers!
    await complete_night_resolution(ctx, game, set(), {}, {}, set(), [])
    assert has_used_item(game, mafia_uid, "fake_document") is True
    inv_after_1 = await get_inventory(mafia_uid)
    assert inv_after_1["fake_document"] == initial_docs - 1

    # Check report sent to detective: should report Fuqaro
    det_reports = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list if c.kwargs.get("chat_id") == det_uid]
    assert any("Fuqaro" in r for r in det_reports)

    # NIGHT 2: Detective investigates same MafiaDon again in the SAME game
    ctx.bot.send_message.reset_mock()
    game["detective_results"] = {str(det_uid): {"target": mafia_uid}}
    await complete_night_resolution(ctx, game, set(), {}, {}, set(), [])
    inv_after_2 = await get_inventory(mafia_uid)
    assert inv_after_2["fake_document"] == initial_docs - 1, "Fake doc cannot be used twice in same game"

    det_reports_2 = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list if c.kwargs.get("chat_id") == det_uid]
    assert any("Boshliq" in r for r in det_reports_2), "Detective must see real role on second check"

    # Verify MafiaDon received alert that fake doc was already used
    mafia_msgs = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list if c.kwargs.get("chat_id") == mafia_uid]
    assert any("allaqachon foydalangansiz" in r for r in mafia_msgs)

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_revenge_knife_strictly_once_per_game_night():
    """Test that revenge knife (revenge_knife) triggers retaliation once per game."""
    await init_db()
    victim_uid = 94001
    killer_uid = 94002
    killer2_uid = 94003
    u1 = MockUser(victim_uid, "VictimWithKnife")
    u2 = MockUser(killer_uid, "Killer")
    u3 = MockUser(killer2_uid, "Killer2")
    await ensure_user(u1)
    await ensure_user(u2)
    await ensure_user(u3)

    await add_item(victim_uid, "revenge_knife", 2)
    inv = await get_inventory(victim_uid)
    initial_knives = inv.get("revenge_knife", 0)
    assert initial_knives >= 2

    chat_id = -10094001
    game = {
        "chat": chat_id,
        "players": [victim_uid, killer_uid, killer2_uid],
        "names": {victim_uid: "VictimWithKnife", killer_uid: "Killer", killer2_uid: "Killer2"},
        "roles": {victim_uid: "Fuqaro", killer_uid: "Qotil", killer2_uid: "Maniak"},
        "alive": {victim_uid: True, killer_uid: True, killer2_uid: True},
        "phase": "night",
        "used_items": {},
        "night": 1
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # NIGHT 1: Killer attacks Victim. Victim retaliates and kills Killer!
    deaths = {victim_uid}
    causes = {victim_uid: ["Pichoqlandi"]}
    attacks = [{"attacker": killer_uid, "target": victim_uid, "role": "Qotil"}]

    await complete_night_resolution(ctx, game, deaths, causes, {}, set(), attacks)

    # Killer must also die due to revenge knife!
    assert killer_uid in deaths, "Killer must die from revenge knife"
    assert has_used_item(game, victim_uid, "revenge_knife") is True
    inv_after = await get_inventory(victim_uid)
    assert inv_after["revenge_knife"] == initial_knives - 1

    # NIGHT 2: Victim attacked again in SAME game. Second knife cannot be used!
    ctx.bot.send_message.reset_mock()
    deaths_2 = {victim_uid}
    causes_2 = {victim_uid: ["Pichoqlandi"]}
    attacks_2 = [{"attacker": killer2_uid, "target": victim_uid, "role": "Maniak"}]

    await complete_night_resolution(ctx, game, deaths_2, causes_2, {}, set(), attacks_2)
    assert killer2_uid not in deaths_2, "Second killer must NOT die on second attack in same game"
    inv_after_2 = await get_inventory(victim_uid)
    assert inv_after_2["revenge_knife"] == initial_knives - 1, "Must NOT consume 2nd knife"

    # Victim must receive alert message
    victim_msgs = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list if c.kwargs.get("chat_id") == victim_uid]
    assert any("allaqachon foydalangansiz" in m for m in victim_msgs)

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_extra_vote_activation_and_restriction():
    """Test that extra_vote is consumed once and adds +1 weight to voting tally."""
    await init_db()
    voter_uid = 95001
    target_uid = 95002
    u1 = MockUser(voter_uid, "ExtraVoter")
    u2 = MockUser(target_uid, "Candidate")
    await ensure_user(u1)
    await ensure_user(u2)

    await add_item(voter_uid, "extra_vote", 3)
    inv = await get_inventory(voter_uid)
    initial_votes = inv.get("extra_vote", 0)
    assert initial_votes >= 3

    chat_id = -10095001
    game = {
        "chat": chat_id,
        "players": [voter_uid, target_uid],
        "names": {voter_uid: "ExtraVoter", target_uid: "Candidate"},
        "roles": {voter_uid: "Fuqaro", target_uid: "Fuqaro"},
        "alive": {voter_uid: True, target_uid: True},
        "phase": "voting",
        "votes": {voter_uid: str(target_uid)},
        "used_items": {},
        "extra_votes": set(),
        "night": 1
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # 1. Activate extra_vote via callback
    q = AsyncMock(spec=CallbackQuery)
    q.data = f"use_item:extra_vote:{chat_id}"
    q.from_user = u1
    q.message = AsyncMock(spec=Message)
    q.message.chat = MockChat(voter_uid, "private")
    q.answer = AsyncMock()
    up = Update(update_id=9501, callback_query=q)

    await callback_router(up, ctx)
    assert voter_uid in game.get("extra_votes", set()), "Voter must be in extra_votes"
    assert has_used_item(game, voter_uid, "extra_vote") is True
    inv_after_1 = await get_inventory(voter_uid)
    assert inv_after_1["extra_vote"] == initial_votes - 1

    # 2. Try to activate extra_vote AGAIN in the same game
    q_repeat = AsyncMock(spec=CallbackQuery)
    q_repeat.data = f"use_item:extra_vote:{chat_id}"
    q_repeat.from_user = u1
    q_repeat.answer = AsyncMock()
    up_repeat = Update(update_id=9502, callback_query=q_repeat)

    await callback_router(up_repeat, ctx)
    q_repeat.answer.assert_called_with(ALREADY_USED_MSG, show_alert=True)
    inv_after_2 = await get_inventory(voter_uid)
    assert inv_after_2["extra_vote"] == initial_votes - 1, "Must NOT consume 2nd item"

    # 3. Check finish_voting weight: standard 1 vote + extra 1 vote = 2 votes
    await finish_voting(ctx, game)
    sent_msgs = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list]
    assert any("2 ovoz" in m for m in sent_msgs), "Candidate must have received 2 votes due to extra_vote"

    # Verify extra_votes was cleared after the voting round finishes
    assert len(game.get("extra_votes", set())) == 0, "extra_votes must be reset after voting round"

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_use_item_cmd_in_game_and_restrictions():
    """Test /use command and in-game item usage restriction."""
    await init_db()
    uid = 96001
    user = MockUser(uid, "CommandUser")
    await ensure_user(user)
    inv0 = await get_inventory(uid)
    init_votes = inv0.get("extra_vote", 0)
    await add_item(uid, "extra_vote", 2)

    chat_id = -10096001
    game = {
        "chat": chat_id,
        "players": [uid],
        "names": {uid: "CommandUser"},
        "alive": {uid: True},
        "phase": "voting",
        "used_items": {},
        "extra_votes": set()
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # 1. Use item via command /use extra_vote
    msg = AsyncMock(spec=Message)
    msg.reply_text = AsyncMock()
    up = Update(update_id=9601, message=msg)
    up._effective_user = user
    up._effective_message = msg
    ctx.args = ["extra_vote"]

    await use_item_cmd(up, ctx)
    assert has_used_item(game, uid, "extra_vote") is True
    inv1 = await get_inventory(uid)
    assert inv1["extra_vote"] == init_votes + 2 - 1

    # 2. Use item AGAIN via command in same game -> Rejected!
    msg.reply_text.reset_mock()
    await use_item_cmd(up, ctx)
    inv2 = await get_inventory(uid)
    assert inv2["extra_vote"] == init_votes + 2 - 1, "Inventory must remain unchanged"
    reply_text = msg.reply_text.call_args[0][0]
    assert "allaqachon foydalangansiz" in reply_text

    # 3. Try to use an item user does not have
    ctx.args = ["knife"]
    msg.reply_text.reset_mock()
    await use_item_cmd(up, ctx)
    reply_text_no_item = msg.reply_text.call_args[0][0]
    assert "mavjud emas" in reply_text_no_item

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_shop_extra_vote_purchase_and_display():
    """Test purchasing extra_vote in shop and verifying inventory display."""
    await init_db()
    uid = 97001
    user = MockUser(uid, "Buyer")
    await ensure_user(user)
    await change_balance(uid, "coin", 500, "Initial balance")

    ctx = make_mock_context()
    q = AsyncMock(spec=CallbackQuery)
    q.from_user = user
    q.effective_chat = MockChat(uid, "private")
    q.message = AsyncMock(spec=Message)
    q.message.chat = MockChat(uid, "private")
    q.edit_message_text = AsyncMock()
    q.answer = AsyncMock()

    # Buy extra_vote from coin shop
    q.data = "buy_item:coin:extra_vote"
    up = Update(update_id=9701, callback_query=q)
    await shop_callback_handler(up, ctx)

    inv = await get_inventory(uid)
    assert inv.get("extra_vote", 0) >= 1

    # View items
    q.data = "shop_items"
    up_view = Update(update_id=9702, callback_query=q)
    await shop_callback_handler(up_view, ctx)

    view_text = q.edit_message_text.call_args[0][0]
    assert "Qo'shimcha ovoz" in view_text
    assert "Har bir o'yinda" in view_text or "O'yinda faqat 1 marta" in view_text

@pytest.mark.asyncio
async def test_pre_armed_ruler_protection_saves_at_verdict_and_blocks_second_attempt():
    """Test that pre-arming ruler_protection via /use shield saves accused at verdict and prevents second use."""
    await init_db()
    accused_uid = 98001
    voter_uid = 98002
    u1 = MockUser(accused_uid, "ArmedAccused")
    u2 = MockUser(voter_uid, "Voter")
    await ensure_user(u1)
    await ensure_user(u2)

    await add_item(accused_uid, "ruler_protection", 3)
    inv0 = await get_inventory(accused_uid)
    init_shields = inv0.get("ruler_protection", 0)

    chat_id = -10098001
    game = {
        "chat": chat_id,
        "players": [accused_uid, voter_uid],
        "names": {accused_uid: "ArmedAccused", voter_uid: "Voter"},
        "roles": {accused_uid: "Fuqaro", voter_uid: "Detektiv"},
        "alive": {accused_uid: True, voter_uid: True},
        "phase": "night",
        "used_items": {},
        "armed_items": {},
        "night": 1
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # 1. Player pre-arms shield via /use shield
    msg = AsyncMock(spec=Message)
    msg.reply_text = AsyncMock()
    up = Update(update_id=9801, message=msg)
    up._effective_user = u1
    up._effective_message = msg
    ctx.args = ["shield"]

    await use_item_cmd(up, ctx)
    assert has_used_item(game, accused_uid, "ruler_protection") is True
    inv1 = await get_inventory(accused_uid)
    assert inv1["ruler_protection"] == init_shields - 1

    # 2. Verdict phase arrives: player is accused and sentenced to death
    game["phase"] = "verdict"
    game["accused_uid"] = accused_uid
    game["verdict_votes"] = {voter_uid: "kill"}
    game["weather"] = None

    await resolve_verdict(ctx, game)
    assert game["alive"][accused_uid] is True, "Pre-armed shield must save accused from execution"
    inv_after_verdict = await get_inventory(accused_uid)
    assert inv_after_verdict["ruler_protection"] == init_shields - 1, "No extra shield should be taken at verdict"

    # 3. Second verdict in SAME game: player is accused again
    ctx.bot.send_message.reset_mock()
    game["phase"] = "verdict"
    game["accused_uid"] = accused_uid
    game["verdict_votes"] = {voter_uid: "kill"}

    await resolve_verdict(ctx, game)
    assert game["alive"][accused_uid] is False, "Accused must die on second verdict in same game"
    inv_after_2 = await get_inventory(accused_uid)
    assert inv_after_2["ruler_protection"] == init_shields - 1, "Inventory must remain unchanged"

    # Accused must receive alert
    accused_msgs = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list if c.kwargs.get("chat_id") == accused_uid]
    assert any("allaqachon foydalangansiz" in m for m in accused_msgs)

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_extra_vote_does_not_persist_across_different_voting_rounds():
    """Test that extra_vote is active ONLY for the single voting round and does not carry over."""
    await init_db()
    voter_uid = 99001
    cand_uid = 99002
    u1 = MockUser(voter_uid, "RoundVoter")
    u2 = MockUser(cand_uid, "Candidate")
    await ensure_user(u1)
    await ensure_user(u2)

    await add_item(voter_uid, "extra_vote", 2)
    chat_id = -10099001
    game = {
        "chat": chat_id,
        "players": [voter_uid, cand_uid],
        "names": {voter_uid: "RoundVoter", cand_uid: "Candidate"},
        "roles": {voter_uid: "Fuqaro", cand_uid: "Fuqaro"},
        "alive": {voter_uid: True, cand_uid: True},
        "phase": "voting",
        "votes": {voter_uid: str(cand_uid)},
        "used_items": {},
        "extra_votes": set(),
        "night": 1
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # ROUND 1: Activate extra_vote
    q = AsyncMock(spec=CallbackQuery)
    q.data = f"use_item:extra_vote:{chat_id}"
    q.from_user = u1
    q.message = AsyncMock(spec=Message)
    q.message.chat = MockChat(voter_uid, "private")
    q.answer = AsyncMock()
    up = Update(update_id=9901, callback_query=q)

    await callback_router(up, ctx)
    assert voter_uid in game.get("extra_votes", set())

    await finish_voting(ctx, game)
    sent_msgs = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list]
    assert any("2 ovoz" in m for m in sent_msgs), "Round 1 must count 2 votes"

    # ROUND 2: Next day voting in SAME game
    ctx.bot.send_message.reset_mock()
    game["phase"] = "voting"
    game["votes"] = {voter_uid: str(cand_uid)}
    game["_finish_started"] = False

    # Check voter has standard 1 vote without extra_vote
    await finish_voting(ctx, game)
    round2_msgs = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list]
    assert any("1 ovoz" in m for m in round2_msgs), "Round 2 must count 1 normal vote"

    # Voter attempts to activate extra_vote again in Round 2 -> Rejected!
    q_round2 = AsyncMock(spec=CallbackQuery)
    q_round2.data = f"use_item:extra_vote:{chat_id}"
    q_round2.from_user = u1
    q_round2.answer = AsyncMock()
    up_r2 = Update(update_id=9902, callback_query=q_round2)

    await callback_router(up_r2, ctx)
    q_round2.answer.assert_called_with(ALREADY_USED_MSG, show_alert=True)

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_extra_vote_cmd_rejected_outside_voting_phase():
    """Test that /use extra_vote is strictly rejected outside the voting phase."""
    await init_db()
    uid = 99101
    user = MockUser(uid, "PhaseUser")
    await ensure_user(user)
    await add_item(uid, "extra_vote", 2)
    inv0 = await get_inventory(uid)

    chat_id = -10099101
    game = {
        "chat": chat_id,
        "players": [uid],
        "names": {uid: "PhaseUser"},
        "alive": {uid: True},
        "phase": "night",  # NOT voting!
        "used_items": {},
        "extra_votes": set()
    }
    games[chat_id] = game
    ctx = make_mock_context()

    msg = AsyncMock(spec=Message)
    msg.reply_text = AsyncMock()
    up = Update(update_id=9911, message=msg)
    up._effective_user = user
    up._effective_message = msg
    ctx.args = ["extra_vote"]

    await use_item_cmd(up, ctx)
    reply_text = msg.reply_text.call_args[0][0]
    assert "faqat ovoz berish paytida" in reply_text

    inv_after = await get_inventory(uid)
    assert inv_after["extra_vote"] == inv0["extra_vote"], "Extra vote must NOT be deducted outside voting"
    assert has_used_item(game, uid, "extra_vote") is False

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_new_game_resets_used_items_allowing_reuse():
    """Test that when a game ends and a new game starts in the same chat, items can be used again."""
    await init_db()
    uid = 99201
    user = MockUser(uid, "MultiGameUser")
    voter = MockUser(99202, "Voter")
    await ensure_user(user)
    await ensure_user(voter)
    await add_item(uid, "ruler_protection", 2)

    chat_id = -10099201

    # GAME 1
    game1 = {
        "chat": chat_id,
        "players": [uid, voter.id],
        "names": {uid: "MultiGameUser", voter.id: "Voter"},
        "roles": {uid: "Fuqaro", voter.id: "Detektiv"},
        "alive": {uid: True, voter.id: True},
        "phase": "verdict",
        "accused_uid": uid,
        "verdict_votes": {voter.id: "kill"},
        "used_items": {},
        "night": 1
    }
    games[chat_id] = game1
    ctx = make_mock_context()

    await resolve_verdict(ctx, game1)
    assert game1["alive"][uid] is True, "Shield works in Game 1"
    assert has_used_item(game1, uid, "ruler_protection") is True

    # GAME 1 Ends cleanly
    games.pop(chat_id, None)

    # GAME 2 in same chat: Fresh game state
    game2 = {
        "chat": chat_id,
        "players": [uid, voter.id],
        "names": {uid: "MultiGameUser", voter.id: "Voter"},
        "roles": {uid: "Fuqaro", voter.id: "Detektiv"},
        "alive": {uid: True, voter.id: True},
        "phase": "verdict",
        "accused_uid": uid,
        "verdict_votes": {voter.id: "kill"},
        "used_items": {},
        "night": 1
    }
    games[chat_id] = game2

    # Shield can be used again in Game 2!
    await resolve_verdict(ctx, game2)
    assert game2["alive"][uid] is True, "Shield must work in fresh Game 2"
    assert has_used_item(game2, uid, "ruler_protection") is True

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_save_runtime_serializes_used_items_and_extra_votes():
    """Test that save_runtime safely persists used_items and extra_votes in database."""
    await init_db()
    from core.engine import save_runtime
    from database.db import get_db
    import json

    chat_id = -10099301
    game = {
        "chat": chat_id,
        "players": [99301],
        "names": {99301: "PersistentUser"},
        "roles": {99301: "Fuqaro"},
        "alive": {99301: True},
        "phase": "voting",
        "night": 2,
        "used_items": {99301: {"shield", "ruler_protection"}},
        "extra_votes": {99301},
        "armed_items": {99301: {"revenge_knife"}}
    }
    games[chat_id] = game

    await save_runtime(game)
    assert game.get("_db_id") is not None

    db = await get_db()
    cur = await db.execute("SELECT data FROM games WHERE game_id = ?", (game["_db_id"],))
    row = await cur.fetchone()
    assert row is not None

    data = json.loads(row[0])
    assert "used_items" in data
    assert "99301" in data["used_items"]
    assert "shield" in data["used_items"]["99301"]
    assert 99301 in data["extra_votes"] or "99301" in str(data["extra_votes"])
    assert "armed_items" in data

    games.pop(chat_id, None)

@pytest.mark.asyncio
async def test_sheriff_investigation_fake_document_once_per_game():
    """Test Sheriff checking a red role with fake document: 1st check disguised, 2nd check exposed."""
    await init_db()
    sh_uid = 99401
    target_uid = 99402
    u_sh = MockUser(sh_uid, "Sheriff")
    u_tgt = MockUser(target_uid, "MafiaTgt")
    await ensure_user(u_sh)
    await ensure_user(u_tgt)

    await add_item(target_uid, "fake_document", 2)
    inv0 = await get_inventory(target_uid)
    init_docs = inv0.get("fake_document", 0)
    assert init_docs >= 2

    chat_id = -10099401
    game = {
        "chat": chat_id,
        "players": [sh_uid, target_uid],
        "names": {sh_uid: "Sheriff", target_uid: "MafiaTgt"},
        "roles": {sh_uid: "Sherif", target_uid: "Boshliq"},
        "alive": {sh_uid: True, target_uid: True},
        "phase": "night",
        "used_items": {},
        "sheriff_promoted": {sh_uid},  # promoted so sheriff can investigate
        "night": 1
    }
    games[chat_id] = game
    ctx = make_mock_context()

    # 1. First Sheriff check on target_uid
    q1 = AsyncMock(spec=CallbackQuery)
    q1.data = f"tgt:sheriff_check:{sh_uid}:{target_uid}"
    q1.from_user = u_sh
    q1.message = AsyncMock(spec=Message)
    q1.message.reply_text = AsyncMock()
    q1.answer = AsyncMock()
    up1 = Update(update_id=9941, callback_query=q1)

    await callback_router(up1, ctx)
    reply1 = q1.message.reply_text.call_args[0][0]
    assert "TINCH FUQARO" in reply1, "1st check must show fake doc disguise (Fuqaro)"
    assert has_used_item(game, target_uid, "fake_document") is True
    inv1 = await get_inventory(target_uid)
    assert inv1["fake_document"] == init_docs - 1

    # 2. Second Sheriff check on same target_uid in same game
    q2 = AsyncMock(spec=CallbackQuery)
    q2.data = f"tgt:sheriff_check:{sh_uid}:{target_uid}"
    q2.from_user = u_sh
    q2.message = AsyncMock(spec=Message)
    q2.message.reply_text = AsyncMock()
    q2.answer = AsyncMock()
    up2 = Update(update_id=9942, callback_query=q2)

    await callback_router(up2, ctx)
    reply2 = q2.message.reply_text.call_args[0][0]
    assert "QIZIL JAMOA (MAFIA)" in reply2, "2nd check must reveal true role (Mafia)"
    inv2 = await get_inventory(target_uid)
    assert inv2["fake_document"] == init_docs - 1, "Must NOT consume second fake document"

    # Target must receive alert that fake document was already used
    tgt_msgs = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list if c.kwargs.get("chat_id") == target_uid]
    assert any("allaqachon foydalangansiz" in m for m in tgt_msgs)

    games.pop(chat_id, None)

