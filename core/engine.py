import time
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from config import ROLES
from database.models import (
    now_iso, get_badge, change_balance, record_game_finish, resolve_afterlife_bets
)
from database.db import get_db
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.engine")

# Global runtime state
lobbies: Dict[int, Dict[str, Any]] = {}
games: Dict[int, Dict[str, Any]] = {}
pending_last_words: Dict[int, Dict[str, Any]] = {}
active_drops: Dict[str, Dict[str, Any]] = {}

DEFAULT_DROP_EXPIRY_SECONDS = 600
_drop_claim_lock = asyncio.Lock()

def cleanup_expired_drops(expiry_seconds: int = DEFAULT_DROP_EXPIRY_SECONDS) -> int:
    """Purge expired gold drops from memory (older than expiry_seconds)."""
    now = time.time()
    expired = []
    for drop_id, d in list(active_drops.items()):
        exp = d.get("expires_at")
        if exp is not None:
            if now > exp:
                expired.append(drop_id)
        else:
            cat = d.get("created_at", now)
            if cat > 1000000000 and (now - cat > expiry_seconds):
                expired.append(drop_id)
    for drop_id in expired:
        active_drops.pop(drop_id, None)
    return len(expired)

async def claim_gold_drop(drop_id: str, uid: int, user_name: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Atomically claim 1 gold from an active drop, preventing double-claims and race conditions."""
    now = time.time()
    async with _drop_claim_lock:
        drop = active_drops.get(drop_id)
        if not drop:
            return False, "❌ Ushbu Gold tarqatish yakunlangan yoki mavjud emas.", None

        exp = drop.get("expires_at")
        if exp is not None and now > exp:
            return False, "❌ Ushbu Gold tarqatish muddati (10 daqiqa) tugagan.", drop
        elif exp is None:
            cat = drop.get("created_at", now)
            if cat > 1000000000 and (now - cat > DEFAULT_DROP_EXPIRY_SECONDS):
                return False, "❌ Ushbu Gold tarqatish muddati (10 daqiqa) tugagan.", drop

        if uid in drop.get("claimed_by", {}):
            return False, "ℹ️ Siz ushbu tarqatishdan allaqachon 1 dona Gold olgansiz!", drop

        if drop.get("remaining", 0) <= 0:
            return False, "😔 Kech qoldingiz! Barcha Goldlar terib olindi.", drop

        drop["remaining"] -= 1
        drop.setdefault("claimed_by", {})[uid] = user_name

    await change_balance(uid, "gold", 1, f"Gold Drop {drop_id}")
    return True, "🎉 Tabriklaymiz! Siz 1 dona Gold oldingiz!", drop

def get_game(chat_id: int) -> Optional[Dict[str, Any]]:
    return games.get(chat_id)

def get_lobby(chat_id: int) -> Optional[Dict[str, Any]]:
    return lobbies.get(chat_id)

def find_game_by_user(user_id: int) -> Optional[Dict[str, Any]]:
    for g in games.values():
        if user_id in g.get("players", []):
            return g
    return None

def find_lobby_by_user(user_id: int) -> Optional[Dict[str, Any]]:
    for l in lobbies.values():
        if user_id in l.get("players", []):
            return l
    return None

def cancel_game_timer(game: Optional[Dict[str, Any]]):
    """Safely cancel any pending background timer task attached to game."""
    if not game:
        return
    curr = None
    try:
        curr = asyncio.current_task()
    except (TelegramError, Exception) as e:
        log.debug("Operation suppressed in %s: %s", __name__, e)
    task = game.pop("_timer_task", None)
    if task and task is not curr and not task.done():
        task.cancel()
    king_task = game.pop("_king_timer_task", None)
    if king_task and king_task is not curr and not king_task.done():
        king_task.cancel()

def cancel_lobby_timer(lobby: Optional[Dict[str, Any]]):
    """Safely cancel any pending background timer task attached to lobby."""
    if not lobby:
        return
    task = lobby.pop("_timer_task", None)
    if task and not task.done():
        task.cancel()

async def abort_game(
    chat_id: int,
    reason: str = "O'yin to'xtatildi.",
    context: Optional[Any] = None,
    notify_chat: bool = False
) -> bool:
    """Safely abort and clean up an active game, cancelling timers and persisting aborted status to DB."""
    game = games.pop(chat_id, None)
    now = now_iso()
    db = await get_db()
    if game:
        cancel_game_timer(game)
        game["phase"] = "aborted"
        db_id = game.get("_db_id")
        if db_id:
            await db.execute("""
                UPDATE games SET state = 'aborted', phase = 'aborted', finished_at = ?, updated_at = ?
                WHERE game_id = ?
            """, (now, now, db_id))
        else:
            await db.execute("""
                UPDATE games SET state = 'aborted', phase = 'aborted', finished_at = ?, updated_at = ?
                WHERE chat_id = ? AND state = 'active'
            """, (now, now, chat_id))
        await db.commit()
    else:
        # Also ensure any dangling active rows in DB for this chat are aborted
        await db.execute("""
            UPDATE games SET state = 'aborted', phase = 'aborted', finished_at = ?, updated_at = ?
            WHERE chat_id = ? AND state = 'active'
        """, (now, now, chat_id))
        await db.commit()

    if notify_chat and context:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🛑 <b>{reason}</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            log.warning("Could not send abort notification to chat %s: %s", chat_id, e)
    return game is not None

def abort_lobby(chat_id: int) -> Optional[Dict[str, Any]]:
    """Safely cancel lobby timer and remove from lobbies."""
    lobby = lobbies.pop(chat_id, None)
    if lobby:
        cancel_lobby_timer(lobby)
    return lobby

def display_name(game: Dict[str, Any], uid: int) -> str:
    """Format player name with Telegram Premium, Admin Crown, and shop badges."""
    if not isinstance(game, dict):
        return f"O'yinchi_{uid}"
    names = game.get("names", {})
    raw_name = str(names.get(uid, names.get(str(uid), f"O'yinchi_{uid}")))

    badges = game.get("badges", {})
    badge = str(badges.get(uid, badges.get(str(uid), "")))

    from config import ADMIN_IDS, ADMIN_ID
    is_adm = (uid in ADMIN_IDS) or (ADMIN_ID != 0 and uid == ADMIN_ID)

    if is_adm or badge in ("👑 Bosh Admin", "Bosh Admin"):
        return f"👑 {raw_name}"

    if badge in ("👑 Qirol Toji", "Qirol Toji", "badge_crown"):
        return f"👑 {raw_name}"
    elif badge in ("✦ Maxsus belgi", "Maxsus belgi", "badge_special", "✦ Maxsus"):
        return f"✦ {raw_name} [Maxsus]"
    elif badge in ("⚡ Yashin belgisi", "Yashin belgisi", "badge_lightning"):
        return f"⚡ {raw_name}"
    elif badge in ("🕶️ Sirli Detektiv", "Sirli Detektiv", "badge_mystery"):
        return f"🕶️ {raw_name}"
    elif badge in ("🎯 Aniqchi", "Aniqchi", "badge_sharpshooter"):
        return f"🎯 {raw_name}"
    elif badge:
        return f"{raw_name} [{badge}]"

    if game.get("premium", {}).get(uid):
        return f"⭐ {raw_name}"

    return raw_name

async def save_runtime(game: Dict[str, Any]):
    """Persist active game state asynchronously."""
    db_id = game.get("_db_id")
    chat_id = game.get("chat")
    if not chat_id:
        return
    try:
        db = await get_db()
        data_json = json.dumps({
            "players": game.get("players", []),
            "names": {str(k): v for k, v in game.get("names", {}).items()},
            "roles": {str(k): v for k, v in game.get("roles", {}).items()},
            "alive": {str(k): v for k, v in game.get("alive", {}).items()},
            "phase": game.get("phase", "lobby"),
            "night": game.get("night", 1),
            "group_link": game.get("group_link"),
            "used_items": {str(k): list(v) for k, v in game.get("used_items", {}).items()},
            "extra_votes": list(game.get("extra_votes", set())),
            "armed_items": {str(k): list(v) for k, v in game.get("armed_items", {}).items()},
        })
        now = now_iso()
        if db_id:
            await db.execute("""
                UPDATE games SET state = 'active', phase = ?, night = ?, data = ?, updated_at = ?
                WHERE game_id = ?
            """, (game.get("phase", "night"), game.get("night", 1), data_json, now, db_id))
        else:
            cur = await db.execute("""
                INSERT INTO games (chat_id, state, phase, night, data, created_at, updated_at)
                VALUES (?, 'active', ?, ?, ?, ?, ?)
            """, (chat_id, game.get("phase", "night"), game.get("night", 1), data_json, now, now))
            game["_db_id"] = cur.lastrowid
        await db.commit()
    except Exception as e:
        log.warning("save_runtime failed for chat %s: %s", chat_id, e)

async def check_winner(context, game: Dict[str, Any]) -> bool:
    """Check win conditions for Town, Mafia, or Neutral factions."""
    alive = [u for u in game.get("players", []) if game.get("alive", {}).get(u, False)]
    if not alive:
        await finish_game(context, game, [], winning_team="draw")
        return True

    red = [u for u in alive if ROLES.get(game["roles"].get(u), "blue") == "red"]
    blue = [u for u in alive if ROLES.get(game["roles"].get(u), "blue") == "blue"]
    solo = [u for u in alive if ROLES.get(game["roles"].get(u), "blue") == "solo"]

    # 1. Maniak yoki Arsonist yolg'iz qolsa
    solo_killers = [u for u in solo if game["roles"].get(u) in ("Maniak", "Pirotexnik")]
    if len(alive) == 1 and solo_killers:
        await finish_game(context, game, solo_killers, winning_team="solo")
        return True

    # 2. Shahar g'alabasi: barcha Mafia va qotil Neytrallar (Maniak, Pirotexnik) yo'q qilinsa
    if not red and not solo_killers and blue:
        await finish_game(context, game, blue, winning_team="blue")
        return True

    # 3. Mafia g'alabasi: barcha Shahar yo'q qilinsa, yoki Mafia soni shahardan oshsa va Neytrallar bo'lmasa
    if not blue and not solo:
        await finish_game(context, game, red, winning_team="red")
        return True
    if len(red) >= len(blue) and not solo and len(red) > 0:
        await finish_game(context, game, red, winning_team="red")
        return True

    # 4. Yagona tirik neytral
    if len(alive) == 1 and solo:
        await finish_game(context, game, solo, winning_team="solo")
        return True

    return False

async def finish_game(
    context,
    game: Dict[str, Any],
    winners: List[int],
    joker: bool = False,
    winning_team: str = "blue"
):
    """Cleanly finalize game, broadcast results, award coins, and update database."""
    import sys
    from telegram.error import TelegramError
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from config import BOT_USERNAME
    from roles.base import format_role_display

    if game.get("_finish_started"):
        return
    game["_finish_started"] = True
    cancel_game_timer(game)
    game["phase"] = "finished"
    game["_finish_time"] = time.time()

    winner_set = set(winners)
    chat_id = game.get("chat")

    # DB update for stats and bets
    db_id = game.get("_db_id", 0)
    await record_game_finish(chat_id, winning_team if not joker else "joker", list(winners), game.get("players", []))
    if db_id:
        await resolve_afterlife_bets(db_id, winning_team if not joker else "solo")

    # Persist game state as finished in games table
    try:
        db = await get_db()
        now = now_iso()
        if db_id:
            await db.execute("""
                UPDATE games SET state = 'finished', phase = 'finished', finished_at = ?, updated_at = ?
                WHERE game_id = ?
            """, (now, now, db_id))
        else:
            await db.execute("""
                UPDATE games SET state = 'finished', phase = 'finished', finished_at = ?, updated_at = ?
                WHERE chat_id = ? AND state = 'active'
            """, (now, now, chat_id))
        await db.commit()
    except Exception as e:
        log.warning("Could not set game to finished in DB for chat %s: %s", chat_id, e)

    # Award coins to winners and consolation to other participants
    for uid in winners:
        await change_balance(uid, "coin", 150, "O'yin g'olibi")
    for uid in game.get("players", []):
        if uid not in winner_set:
            await change_balance(uid, "coin", 25, "O'yin ishtirokchisi (tasalli)")

    # 1. Tunda o'ldirilganlar
    killed_lines = []
    last_deaths = game.get("last_night_deaths", [])
    causes = game.get("last_night_causes", {})
    if last_deaths:
        for d_uid in last_deaths:
            d_name = display_name(game, d_uid)
            d_role = game.get("roles", {}).get(d_uid, "Fuqaro")
            role_title = format_role_display(d_role)
            d_cause = causes.get(d_uid, ["vaxshiylarcha o'ldirildi"])[0]
            if "Mafiya" in d_cause or "Boshliq" in d_cause:
                extra = f" Aytishlaricha, unikiga {tg_emoji('don', '👑')} Don kelgan."
            elif "Maniak" in d_cause:
                extra = f" Aytishlaricha, unikiga {tg_emoji('mafia_win', '🩸')} Maniak kelgan."
            elif "Pirotexnik" in d_cause:
                extra = f" Aytishlaricha, uning uyiga {tg_emoji('trigger', '🔥')} o't qo'yilgan."
            elif "Detektiv" in d_cause or "Sherif" in d_cause:
                extra = f" {tg_emoji('detective', '⚖️')} Qonun himoyachilarining adolat o'qi unga yetdi."
            else:
                extra = ""
            killed_lines.append(f"Tunda {role_title} {d_name}... {d_cause}.{extra}")
    else:
        killed_lines.append("Bu tunda hech kim o'ldirilmadi.")

    # 2. G'oliblar
    winner_lines = []
    if winners:
        for i, uid in enumerate(winners, 1):
            role = game.get("roles", {}).get(uid, "Fuqaro")
            role_title = format_role_display(role)
            name = display_name(game, uid)
            if i == 1:
                winner_lines.append(f"🌟 1. {name} - {role_title}")
            else:
                winner_lines.append(f"{i}. {name} - {role_title}")
    else:
        winner_lines.append("• Hech kim")

    # 3. Qolgan o'yinchilar
    other_lines = []
    other_players = [u for u in game.get("players", []) if u not in winner_set]
    start_idx = len(winners) + 1 if winners else 1
    for idx, uid in enumerate(other_players, start_idx):
        role = game.get("roles", {}).get(uid, "Fuqaro")
        role_title = format_role_display(role)
        name = display_name(game, uid)
        other_lines.append(f"{idx}. {name} - {role_title}")

    # 4. Duration
    created_at = game.get("created_at")
    if created_at:
        duration_min = max(1, round((time.time() - created_at) / 60))
    else:
        duration_min = max(1, round(game.get("night", 1) * 2))

    # Assemble announcement
    victory_header = ""
    if winning_team == "red":
        victory_header = f"{tg_emoji('mafia_win', '🩸')} <b>MAFIYA G'ALABA QOZONDI!</b>\n\n"
    elif winning_team == "blue":
        victory_header = f"{tg_emoji('civilian_win', '🏆')} <b>SHAHAR FUQAROLARI G'ALABA QOZONDI!</b>\n\n"
    elif joker:
        victory_header = f"{tg_emoji('mafia_win', '🃏')} <b>JOKER G'ALABA QOZONDI!</b>\n\n"

    winners_emoji = tg_emoji('mafia_win', '🩸') if winning_team == "red" else (tg_emoji('civilian_win', '🏆') if winning_team == "blue" else tg_emoji('mafia_win', '🃏'))
    lines = [
        f"{tg_emoji('dead', '💀')} <b>Tunda o'ldirilganlar:</b>",
        *killed_lines,
        "",
        f"{victory_header}{tg_emoji('game_start', '🎬')} <b>O'yin tugadi!</b>",
        "",
        f"{winners_emoji} <b>G'oliblar:</b>",
        *winner_lines,
    ]
    if other_lines:
        lines.extend([
            "",
            "<b>Qolgan o'yinchilar:</b>",
            *other_lines
        ])
    lines.extend([
        "",
        f"{tg_emoji('timer', '⏳')} O'yin davomiyligi: {duration_min} minut",
        "",
        "🎉 🪩"
    ])

    text = "\n".join(lines)
    stats_url = f"https://t.me/{BOT_USERNAME}?start=stats"
    reply_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟣 📊 Statistika ↗", url=stats_url)]
    ])

    try:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_kb, parse_mode="HTML")
    except Exception as e:
        log.warning("Could not send finish game text: %s", e)

    # Announce endgame sleepers if any
    try:
        from core.afk_penalty import check_endgame_sleepers
        await check_endgame_sleepers(context, game)
    except Exception as e:
        log.warning("Could not check endgame sleepers: %s", e)

    # Clean up from active games
    games.pop(chat_id, None)
