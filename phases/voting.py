import asyncio
import logging
from collections import Counter
from typing import Dict, Any, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import DEFAULT_VOTE_SECONDS
from core.engine import (
    display_name, save_runtime, check_winner, cancel_game_timer
)
from core.audio_effects import send_atmospheric_message
from core.navigation import bot_action_button
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.phases.voting")

def get_voting_keyboard(game: Dict[str, Any], is_pm: bool = False) -> InlineKeyboardMarkup:
    from core.navigation import return_to_group_button
    chat_id = game["chat"]
    alive_players = [
        u for u in game.get("players", [])
        if game.get("alive", {}).get(u, False)
    ]
    rows = []
    for uid in alive_players:
        name = display_name(game, uid)
        rows.append([
            InlineKeyboardButton(f"👤 {name}", callback_data=f"vote:{chat_id}:{uid}")
        ])
    rows.append([
        InlineKeyboardButton("🟢 🕊️ Hech kimga ovoz bermaslik", callback_data=f"vote:{chat_id}:none")
    ])
    has_unrevealed_mayor = any(
        game.get("roles", {}).get(u) == "Mer" and game.get("alive", {}).get(u, False) and u not in game.get("mayor_revealed", set())
        for u in game.get("players", [])
    )
    if has_unrevealed_mayor:
        rows.append([
            InlineKeyboardButton("🎖️ 👑 Merlikni e'lon qilish (/reveal)", callback_data=f"mayor_reveal:{chat_id}")
        ])
    if is_pm:
        rows.append([
            InlineKeyboardButton("🗳️ Qo'shimcha ovoz ishlatish", callback_data=f"use_item:extra_vote:{chat_id}")
        ])
        rows.append([
            return_to_group_button(game)
        ])
    else:
        rows.append([
            bot_action_button(chat_id, "🔵 💬 Botga o'tish ↗")
        ])
    return InlineKeyboardMarkup(rows)

async def start_voting(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    chat_id = game["chat"]
    night_num = game.get("night", 1)
    game["phase"] = "voting"
    game["votes"] = {}
    await save_runtime(game)

    vote_seconds = int(game.get("settings", {}).get("vote_seconds", DEFAULT_VOTE_SECONDS))
    text = (
        f"{tg_emoji('voting', '🗳️')} <b>Aybdorlarni aniqlash va jazolash vaqti keldi.</b>\n"
        f"Ovoz berish uchun {tg_emoji('timer', '⏳')} <b>{vote_seconds} sekund</b>"
    )

    kb = get_voting_keyboard(game)
    await send_atmospheric_message(
        bot=context.bot,
        chat_id=chat_id,
        text=text,
        sound_type="voting",
        reply_markup=kb,
        parse_mode="HTML"
    )

    cancel_game_timer(game)
    game["_timer_task"] = asyncio.create_task(_vote_timer(context, chat_id, night_num, vote_seconds))

async def _vote_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, night_num: int, seconds: int):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    from core.engine import games
    game = games.get(chat_id)
    if game and game.get("phase") == "voting" and game.get("night") == night_num and not game.get("_finish_started"):
        await finish_voting(context, game)

async def finish_voting(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    if game.get("phase") != "voting" or game.get("_finish_started"):
        return
    cancel_game_timer(game)

    chat_id = game["chat"]
    votes: Dict[int, Any] = game.get("votes", {})
    tally: Dict[Any, int] = {}

    # Weight votes (Mayor counts 3 votes if revealed, Extra Vote adds +1)
    mayor_revealed = game.get("mayor_revealed", set())
    extra_votes = game.get("extra_votes", set())
    for voter_uid, target in votes.items():
        if not game["alive"].get(voter_uid, False):
            continue
        weight = 3 if voter_uid in mayor_revealed else 1
        if voter_uid in extra_votes:
            weight += 1
        tally[target] = tally.get(target, 0) + weight

    # Clear active round extra votes so they do not leak into subsequent voting rounds
    game.setdefault("extra_votes", set()).clear()

    # Check results
    lines = [
        f"{tg_emoji('voting', '🧊')} <b>Ovoz berish natijalari:</b>",
        ""
    ]

    for target, count in tally.items():
        if target == "none":
            lines.append(f"• 🕊️ Hech kimga: <b>{count} ovoz</b>")
        else:
            try:
                t_uid = int(target)
                lines.append(f"• 👤 <b>{display_name(game, t_uid)}</b>: <b>{count} ovoz</b>")
            except Exception:
                pass

    if not tally:
        lines.append("<i>Hech kim ovoz bermadi.</i>")

    from core.navigation import bot_action_keyboard
    action_kb = bot_action_keyboard(chat_id, "💬 Botga o'tish (Amallar/Ovoz)")

    try:
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=action_kb, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=action_kb)

    # AFK sleepers check and humorous shout
    try:
        from core.afk_penalty import handle_voting_sleepers
        await handle_voting_sleepers(context, game)
    except Exception as e:
        log.warning("Could not handle voting sleepers: %s", e)

    # Determine highest voted candidate
    valid_tally = {k: v for k, v in tally.items() if k != "none"}
    if not valid_tally:
        # No suspect chosen, proceed to night
        await context.bot.send_message(
            chat_id=chat_id,
            text="🕊️ Hech kim sud minbariga chiqarilmadi. Shahar yana tun quchog'iga kirdi.",
            reply_markup=action_kb
        )
        game["night"] = game.get("night", 1) + 1
        from phases.night import start_night
        await start_night(context, game)
        return

    sorted_targets = sorted(valid_tally.items(), key=lambda x: x[1], reverse=True)
    top_target, top_votes = sorted_targets[0]

    # Check for tie
    if len(sorted_targets) > 1 and sorted_targets[1][1] == top_votes:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚖️ Ovozlar teng keldi! Shahar ikkilanib qoldi va hech kim sud minbariga chiqarilmadi.",
            reply_markup=action_kb
        )
        game["night"] = game.get("night", 1) + 1
        from phases.night import start_night
        await start_night(context, game)
        return

    accused_uid = int(top_target)
    from phases.verdict import verdict_phase
    await verdict_phase(context, game, accused_uid)

start_voting_phase = start_voting

