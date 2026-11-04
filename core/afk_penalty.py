from telegram.error import TelegramError
import html
import logging
from typing import Dict, Any, List
from telegram.ext import ContextTypes

from config import NIGHT_ACTIVE_ROLES
from core.engine import display_name, save_runtime
from database.models import change_balance

log = logging.getLogger("detektiv.core.afk_penalty")

def record_player_activity(game: Dict[str, Any], uid: int):
    """Mark that player performed a legitimate action in game."""
    act_map = game.setdefault("player_actions", {})
    act_map[uid] = act_map.get(uid, 0) + 1
    # Reset inactivity tracking for this round
    game.setdefault("inactive_nights", {})[uid] = 0
    game.setdefault("round_acted", set()).add(uid)

def reset_player_inactivity(game: Dict[str, Any], uid: int):
    """Explicitly reset consecutive inactive nights counter for player."""
    game.setdefault("inactive_nights", {})[uid] = 0
    game.setdefault("round_acted", set()).add(uid)

async def handle_voting_sleepers(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    """Compatibility handler: records voter activity.
    Does NOT mark or kick players as sleepers just for skipping a vote.
    """
    votes = game.get("votes", {})
    for voter in votes.keys():
        record_player_activity(game, voter)

async def handle_night_sleepers(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    """Enforces 3-night AFK rule:
    Only players who have been completely inactive for 3 consecutive nights
    are penalized with 20 coin deduction and kicked from the game.
    """
    chat_id = game.get("chat")
    if not chat_id:
        return

    alive_players = [
        u for u in game.get("players", [])
        if game.get("alive", {}).get(u, False)
    ]
    if not alive_players:
        return

    round_acted = game.get("round_acted", set())
    inactive_nights = game.setdefault("inactive_nights", {})
    night_num = game.get("night", 1)

    sleepers_to_penalize = []

    for u in alive_players:
        if u in round_acted:
            inactive_nights[u] = 0
            continue

        role = game.get("roles", {}).get(u, "Fuqaro")
        # Non-night active role on night 1 had no night action and no previous daytime
        if night_num == 1 and role not in NIGHT_ACTIVE_ROLES:
            continue

        count = inactive_nights.get(u, 0) + 1
        inactive_nights[u] = count

        if count >= 3:
            sleepers_to_penalize.append(u)

    for u in sleepers_to_penalize:
        name = display_name(game, u)
        try:
            await change_balance(u, "coin", -20, "Ketma-ket 3 tun uxlab qolish jarimasi")
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)

        shout_msg = (
            "💤 <b>UXLASHGA JAZO!</b>\n\n"
            f"👤 <b>{html.escape(name)}</b> ketma-ket <b>3 tun</b> mobaynida hech qanday harakat qilmay, butunlay uxlab qoldi!\n\n"
            "Shahar maydonida uning baland ovozda:\n"
            "🗣 <b>«MEN QAYTIB O'YIN PAYTIDA UHLAMAYMAN!»</b> deb baqirgani eshitildi! 😂🤦‍♂️\n\n"
            "💸 <i>Jarima: 20 Coin hisobingizdan yechildi.</i>\n\n"
            f"🚪 <b>{html.escape(name)}</b> o'yindan chetlatildi!"
        )

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=shout_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            log.warning("Could not send sleeper alert for %s: %s", u, e)

        game["alive"][u] = False
        inactive_nights[u] = 0

    # Reset round_acted for upcoming cycle
    game["round_acted"] = set()
    await save_runtime(game)

async def check_endgame_sleepers(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    """Announce players who never took a single action during the whole match."""
    chat_id = game.get("chat")
    if not chat_id:
        return

    actions = game.get("player_actions", {})
    all_players = game.get("players", [])

    last_night_deaths = set(game.get("last_night_deaths", []))
    night_num = game.get("night", 1)
    roles = game.get("roles", {})
    total_sleepers = [
        u for u in all_players
        if actions.get(u, 0) == 0 and not (
            night_num <= 1 and u in last_night_deaths and roles.get(u) not in NIGHT_ACTIVE_ROLES
        )
    ]
    if not total_sleepers:
        return

    lines = [
        "💤 <b>O'YINNING ASOSIY UYQUCHILARI:</b>",
        ""
    ]
    for u in total_sleepers[:5]:
        name = display_name(game, u)
        lines.append(f"• 👤 <b>{html.escape(name)}</b> — biror marta ham harakat qilmadi!")

    lines.extend([
        "",
        "Ular birgalikda:",
        "🗣 <b>«MEN QAYTIB O'YIN PAYTIDA UHLAMAYMAN!»</b> deb qasamyod qildilar! 😂💤"
    ])

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="\n".join(lines),
            parse_mode="HTML"
        )
    except Exception as e:
        log.warning("Could not send endgame sleepers to chat %s: %s", chat_id, e)
