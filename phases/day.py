import asyncio
import logging
import html
from typing import Dict, Any, List
from telegram.error import TelegramError
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import DEFAULT_DAY_SECONDS, DAY_PHOTO_PATH
from core.engine import (
    display_name, save_runtime, check_winner, cancel_game_timer, touch_game_activity
)
from core.storyteller import generate_morning_story
from core.will import fetch_player_will, format_will_announcement
from core.graveyard import graveyard_menu_keyboard, graveyard_status_text
from core.audio_effects import send_atmospheric_message
from core.navigation import bot_action_button, return_to_group_keyboard

from core.emojis import tg_emoji

log = logging.getLogger("detektiv.phases.day")

async def day_phase(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    chat_id = game["chat"]
    night_num = game.get("night", 1)
    game["phase"] = "day"
    touch_game_activity(game)

    deaths: List[int] = game.get("last_night_deaths", [])
    causes: Dict[int, List[str]] = game.get("last_night_causes", {})
    clues: Dict[int, Dict[str, str]] = game.get("last_night_clues", {})
    saved: List[int] = game.get("last_night_saved", [])
    weather = game.get("weather", {})

    # Generate Cinematic Noir Story
    story = ""
    if saved and not deaths:
        saved_name = display_name(game, saved[0])
        story = generate_morning_story(None, None, doctor_saved_name=saved_name, weather_info=weather)
    elif deaths:
        if len(deaths) > 1:
            victims = [display_name(game, u) for u in deaths]
            story = generate_morning_story(None, None, multi_victims=victims, weather_info=weather)
        else:
            vic_uid = deaths[0]
            vic_name = display_name(game, vic_uid)
            vic_cause = causes.get(vic_uid, ["Noma'lum"])[0]
            vic_clue = clues.get(vic_uid)
            story = generate_morning_story(vic_name, vic_cause, clue=vic_clue, weather_info=weather)
    else:
        story = generate_morning_story(None, None, weather_info=weather)

    lines = [
        f"{tg_emoji('day', '☀️')} <b>Tong #{night_num}</b>",
        "",
        f"<i>{story}</i>",
    ]

    # Death reports, Clues, and Last Wills
    if deaths:
        lines.append("")
        lines.append(f"{tg_emoji('dead', '💀')} <b>Qurbonlar:</b>")
        for uid in deaths:
            name = display_name(game, uid)
            escaped_name = html.escape(name)
            role = game.get("roles", {}).get(uid, "Fuqaro")
            cause_list = causes.get(uid, ["Noma'lum sabab"])
            cause_str = ", ".join(cause_list)
            clue = clues.get(uid)

            lines.append(f"• <b>{escaped_name}</b> — {role} ({cause_str})")
            if clue:
                lines.append(f"  {tg_emoji('investigation', '🔎')} <b>Ashyoviy dalil:</b> {html.escape(clue['summary'])}")

            # Fetch and broadcast Last Will
            will = await fetch_player_will(uid)
            will_text = format_will_announcement(name, will)
            if will_text:
                lines.append(f"  {will_text}")

            # Send Graveyard spectator card to dead player
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=graveyard_status_text(game, uid),
                    reply_markup=graveyard_menu_keyboard(game.get("_db_id", 0), group_link=game.get("group_link")),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
    else:
        lines.append("")
        lines.append(f"🕊️ {tg_emoji('civilian_win', '🕊️')} Bu kecha hech kim halok bo'lmadi. Shaharda osoyishtalik!")

    day_seconds = int(game.get("settings", {}).get("day_seconds", 15))
    lines.extend([
        "",
        f"💬 Shahar uyg'ondi. Muhokama boshlandi! ({tg_emoji('timer', '⏱️')} <b>{day_seconds} soniya</b>)",
        "Gumonlaringizni muhokama qiling va dalillarni tahlil qiling."
    ])

    buttons = [
        [InlineKeyboardButton("🟡 🗳️ Ovoz berishga o'tish", callback_data=f"day_to_vote:{chat_id}")],
        [bot_action_button(chat_id, "🔵 💬 Botga o'tish (Amallar/Ovoz)")]
    ]
    has_unrevealed_mayor = any(
        game.get("roles", {}).get(u) == "Mer" and game.get("alive", {}).get(u, False) and u not in game.get("mayor_revealed", set())
        for u in game.get("players", [])
    )
    if has_unrevealed_mayor:
        buttons.append([
            InlineKeyboardButton("🎖️ 👑 Merlikni e'lon qilish (/reveal)", callback_data=f"mayor_reveal:{chat_id}")
        ])
    day_keyboard = InlineKeyboardMarkup(buttons)

    try:
        await send_atmospheric_message(
            bot=context.bot,
            chat_id=chat_id,
            text="\n".join(lines),
            sound_type="morning",
            photo_path=DAY_PHOTO_PATH,
            reply_markup=day_keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        log.error("Error sending day atmospheric message in chat %s: %s", chat_id, e)

    await save_runtime(game)

    # Check winner
    if await check_winner(context, game):
        return

    # Auto timer to transition to voting
    cancel_game_timer(game)
    game["_timer_task"] = asyncio.create_task(_day_timer(context, chat_id, night_num, day_seconds))

async def _day_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, night_num: int, seconds: int):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    from core.engine import games
    game = games.get(chat_id)
    if game and game.get("phase") == "day" and game.get("night") == night_num and not game.get("_finish_started"):
        try:
            from phases.voting import start_voting
            await start_voting(context, game)
        except Exception as e:
            log.exception("Exception in start_voting from _day_timer for chat %s: %s", chat_id, e)
