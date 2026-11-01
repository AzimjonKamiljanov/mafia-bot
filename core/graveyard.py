import logging
from typing import Dict, Any, List, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import record_afterlife_bet, resolve_afterlife_bets, get_balance
from core.navigation import return_to_group_button

log = logging.getLogger("detektiv.graveyard")

def graveyard_menu_keyboard(game_id: Any = 0, group_link: Optional[str] = None) -> InlineKeyboardMarkup:
    if isinstance(game_id, dict):
        if not group_link:
            group_link = game_id.get("group_link")
        game_id = game_id.get("_db_id", 0)
    elif isinstance(game_id, str) and not group_link:
        group_link = game_id
        game_id = 0

    rows = [
        [
            InlineKeyboardButton("🔵 Shahar g'alabasiga (x2)", callback_data=f"grave_bet:{game_id}:blue:50"),
            InlineKeyboardButton("🔴 Mafia g'alabasiga (x2)", callback_data=f"grave_bet:{game_id}:red:50")
        ],
        [
            InlineKeyboardButton("🟡 Neytral g'alabasiga (x2)", callback_data=f"grave_bet:{game_id}:solo:50")
        ],
        [
            InlineKeyboardButton("🔄 O'yin holatini yangilash", callback_data=f"grave_refresh:{game_id}")
        ],
        [
            return_to_group_button(group_link)
        ]
    ]
    return InlineKeyboardMarkup(rows)

from core.emojis import tg_emoji

def graveyard_status_text(game: Dict[str, Any], viewer_id: int) -> str:
    alive_count = sum(1 for v in game.get("alive", {}).values() if v)
    dead_count = len(game.get("players", [])) - alive_count
    night_num = game.get("night", 1)

    lines = [
        f"{tg_emoji('graveyard', '👻')} <b>Ruhlar Olami (Graveyard)</b>",
        "",
        f"🌌 Faza: <b>{game.get('phase', 'Nomaʼlum').capitalize()}</b> | #{night_num}",
        f"{tg_emoji('civilian', '👥')} Tiriklar: <b>{alive_count}</b> | {tg_emoji('dead', '💀')} Ruhlar: <b>{dead_count}</b>",
        "",
        "O'yinni tomosha qiling va qaysi jamoa g'alaba qozonishiga tanga tiking (50 coin, x2 yutuq):"
    ]
    return "\n".join(lines)
