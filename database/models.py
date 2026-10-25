import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from config import ADMIN_ID, ADMIN_IDS, ADMIN_USERNAMES, BADGE_DAYS
from .db import get_db

log = logging.getLogger("detektiv.models")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def is_admin(user_id: int, username: str = "") -> bool:
    if user_id in ADMIN_IDS:
        return True
    if ADMIN_ID != 0 and user_id == ADMIN_ID:
        return True
    if username and username.lower().lstrip("@") in ADMIN_USERNAMES:
        return True
    return False

async def ensure_user(user) -> Dict[str, Any]:
    """Ensure user exists in users table and inventory is prepared."""
    db = await get_db()
    uid = int(user.id)
    raw_name = getattr(user, "full_name", None) or getattr(user, "first_name", None) or "O'yinchi"
    name = str(raw_name)[:100]
    username = str(getattr(user, "username", "") or "")
    now = now_iso()

    async with db.execute("SELECT * FROM users WHERE user_id = ?", (uid,)) as cursor:
        row = await cursor.fetchone()

    if not row:
        await db.execute("""
            INSERT INTO users (user_id, name, username, coin, gold, games, wins, losses, created_at, updated_at)
            VALUES (?, ?, ?, 100, 0, 0, 0, 0, ?, ?)
        """, (uid, name, username, now, now))
        await db.execute("""
            INSERT OR IGNORE INTO inventory (user_id) VALUES (?)
        """, (uid,))
        await db.commit()
        return await get_user(uid)
    else:
        # Update name/username if changed
        if row["name"] != name or row["username"] != username:
            await db.execute("""
                UPDATE users SET name = ?, username = ?, updated_at = ? WHERE user_id = ?
            """, (name, username, now, uid))
            await db.commit()
        return dict(row)

async def get_user(uid: int) -> Optional[Dict[str, Any]]:
    db = await get_db()
    async with db.execute("SELECT * FROM users WHERE user_id = ?", (uid,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    if not username:
        return None
    clean = username.lstrip("@").strip().lower()
    if not clean:
        return None
    db = await get_db()
    async with db.execute("SELECT * FROM users WHERE LOWER(username) = ?", (clean,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_balance(uid: int, currency: str = "coin") -> int:
    if is_admin(uid):
        return 999999999
    u = await get_user(uid)
    if not u:
        return 0
    return int(u.get(currency, 0))

async def change_balance(uid: int, currency: str, amount: int, note: str = "") -> bool:
    """Safely adjust coin or gold balance. Admins bypass balance checks."""
    if currency not in ("coin", "gold"):
        return False
    if is_admin(uid):
        return True

    db = await get_db()
    async with db.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (uid,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        return False

    current = int(row[currency] or 0)
    if current + amount < 0:
        return False

    await db.execute(
        f"UPDATE users SET {currency} = {currency} + ?, updated_at = ? WHERE user_id = ?",
        (amount, now_iso(), uid)
    )
    await db.execute("""
        INSERT INTO transactions (user_id, kind, amount, currency, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (uid, "credit" if amount >= 0 else "debit", abs(amount), currency, note, now_iso()))
    await db.commit()
    return True

async def get_inventory(uid: int) -> Dict[str, int]:
    db = await get_db()
    async with db.execute("SELECT * FROM inventory WHERE user_id = ?", (uid,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT OR IGNORE INTO inventory (user_id) VALUES (?)", (uid,))
            await db.commit()
            return {}
        return dict(row)

async def add_item(uid: int, field: str, amount: int = 1) -> bool:
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE inventory SET {field} = {field} + ? WHERE user_id = ?",
            (amount, uid)
        )
        await db.commit()
        return True
    except Exception as e:
        log.error("Failed to add item %s for %s: %s", field, uid, e)
        return False

async def take_item(uid: int, field: str, amount: int = 1) -> bool:
    db = await get_db()
    try:
        async with db.execute(f"SELECT {field} FROM inventory WHERE user_id = ?", (uid,)) as cursor:
            row = await cursor.fetchone()
        if not row or (row[field] or 0) < amount:
            return False
        await db.execute(
            f"UPDATE inventory SET {field} = {field} - ? WHERE user_id = ?",
            (amount, uid)
        )
        await db.commit()
        return True
    except Exception as e:
        log.error("Failed to take item %s from %s: %s", field, uid, e)
        return False

async def get_badge(uid: int) -> str:
    if is_admin(uid):
        return "👑 Bosh Admin"
    db = await get_db()
    now = now_iso()
    async with db.execute("""
        SELECT badge_name, expires_at FROM badges WHERE user_id = ?
    """, (uid,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        return ""
    if row["expires_at"] < now:
        await db.execute("DELETE FROM badges WHERE user_id = ?", (uid,))
        await db.commit()
        return ""
    return str(row["badge_name"])

async def set_badge(uid: int, key: str, name: str, days: int = BADGE_DAYS):
    db = await get_db()
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    await db.execute("""
        INSERT INTO badges (user_id, badge_key, badge_name, expires_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            badge_key = excluded.badge_key,
            badge_name = excluded.badge_name,
            expires_at = excluded.expires_at
    """, (uid, key, name, expires))
    await db.commit()

async def deactivate_badge(uid: int):
    db = await get_db()
    await db.execute("DELETE FROM badges WHERE user_id = ?", (uid,))
    await db.commit()

async def get_owned_badges(uid: int) -> List[Dict[str, Any]]:
    db = await get_db()
    async with db.execute("SELECT * FROM owned_badges WHERE user_id = ?", (uid,)) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def save_owned_badge(uid: int, key: str, name: str):
    db = await get_db()
    now = now_iso()
    await db.execute("""
        INSERT OR IGNORE INTO owned_badges (user_id, badge_key, badge_name, bought_at)
        VALUES (?, ?, ?, ?)
    """, (uid, key, name, now))
    await db.commit()

# ============================================================
# 📜 VASIYATNOMA (THE LAST WILL)
# ============================================================

async def get_will(uid: int) -> str:
    db = await get_db()
    async with db.execute("SELECT will_text FROM wills WHERE user_id = ?", (uid,)) as cursor:
        row = await cursor.fetchone()
        return str(row["will_text"]) if row else ""

async def set_will(uid: int, text: str):
    db = await get_db()
    now = now_iso()
    clean_text = text.strip()[:1000]
    await db.execute("""
        INSERT INTO wills (user_id, will_text, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            will_text = excluded.will_text,
            updated_at = excluded.updated_at
    """, (uid, clean_text, now))
    await db.commit()

# ============================================================
# ⚙️ GURUH VA CHAT SOZLAMALARI (CHAT_SETTINGS & BOT_CONFIG)
# ============================================================

async def get_chat_settings(chat_id: int) -> Dict[str, Any]:
    db = await get_db()
    async with db.execute("SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        now = now_iso()
        await db.execute("""
            INSERT OR IGNORE INTO chat_settings (chat_id, lobby_seconds, night_seconds, day_seconds, vote_seconds, verdict_seconds, disabled_roles, updated_at)
            VALUES (?, 300, 60, 120, 45, 25, '[]', ?)
        """, (chat_id, now))
        await db.execute("""
            INSERT OR IGNORE INTO group_settings (chat_id, lobby_seconds, night_seconds, day_seconds, vote_seconds, verdict_seconds, disabled_roles, updated_at)
            VALUES (?, 300, 60, 120, 45, 25, '[]', ?)
        """, (chat_id, now))
        await db.commit()
        return {
            "chat_id": chat_id,
            "lobby_seconds": 300,
            "night_seconds": 60,
            "day_seconds": 120,
            "vote_seconds": 45,
            "verdict_seconds": 25,
            "disabled_roles": "[]"
        }
    res = dict(row)
    if "vote_seconds" not in res:
        res["vote_seconds"] = 45
    if "verdict_seconds" not in res:
        res["verdict_seconds"] = 25
    return res

async def update_chat_settings(chat_id: int, **kwargs):
    await get_chat_settings(chat_id)
    db = await get_db()
    fields = []
    params = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        params.append(v)
    fields.append("updated_at = ?")
    params.append(now_iso())
    params.append(chat_id)
    await db.execute(f"UPDATE chat_settings SET {', '.join(fields)} WHERE chat_id = ?", params)
    try:
        await db.execute(f"UPDATE group_settings SET {', '.join(fields)} WHERE chat_id = ?", params)
    except Exception:
        pass
    await db.commit()

get_group_settings = get_chat_settings
update_group_settings = update_chat_settings

async def get_bot_config(key: str, default: str = "") -> str:
    db = await get_db()
    async with db.execute("SELECT value FROM bot_config WHERE key = ?", (key,)) as cursor:
        row = await cursor.fetchone()
        return str(row["value"]) if row else default

async def set_bot_config(key: str, value: str):
    db = await get_db()
    now = now_iso()
    await db.execute("""
        INSERT INTO bot_config (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (key, str(value), now))
    await db.commit()

async def get_all_bot_configs() -> Dict[str, str]:
    db = await get_db()
    async with db.execute("SELECT key, value FROM bot_config") as cursor:
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}

# ============================================================
# 🏆 REYTING VA O'YIN HISOBI
# ============================================================

async def get_top_players(limit: int = 30) -> List[Dict[str, Any]]:
    db = await get_db()
    async with db.execute("""
        SELECT name, username, coin, gold, games, wins, losses
        FROM users
        ORDER BY wins DESC, coin DESC
        LIMIT ?
    """, (limit,)) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def record_game_finish(chat_id: int, winners_team: str, winning_uids: List[int], all_players: List[int]):
    db = await get_db()
    now = now_iso()
    
    # 1. Game history
    await db.execute("""
        INSERT INTO game_history (game_id, chat_id, winners, ended_at)
        VALUES (0, ?, ?, ?)
    """, (chat_id, f"{winners_team}: {','.join(str(u) for u in winning_uids)}", now))

    # 2. Wins and losses stats + rewards
    for uid in all_players:
        if uid in winning_uids:
            reward = 150
            await db.execute("""
                UPDATE users SET games = games + 1, wins = wins + 1, coin = coin + ?, updated_at = ?
                WHERE user_id = ?
            """, (reward, now, uid))
        else:
            loss_reward = 25
            await db.execute("""
                UPDATE users SET games = games + 1, losses = losses + 1, coin = coin + ?, updated_at = ?
                WHERE user_id = ?
            """, (loss_reward, now, uid))
    await db.commit()

# ============================================================
# 🛡️ KLANLAR (SYNDICATES)
# ============================================================

async def create_clan(name: str, tag: str, leader_id: int) -> Optional[int]:
    db = await get_db()
    now = now_iso()
    try:
        cursor = await db.execute("""
            INSERT INTO clans (name, tag, leader_id, coins, score, created_at)
            VALUES (?, ?, ?, 500, 0, ?)
        """, (name, tag, leader_id, now))
        clan_id = cursor.lastrowid
        await db.execute("""
            INSERT INTO clan_members (clan_id, user_id, role, joined_at)
            VALUES (?, ?, 'leader', ?)
        """, (clan_id, leader_id, now))
        await db.commit()
        return clan_id
    except Exception as e:
        log.warning("Clan creation error: %s", e)
        return None

async def get_user_clan(user_id: int) -> Optional[Dict[str, Any]]:
    db = await get_db()
    async with db.execute("""
        SELECT c.*, cm.role AS member_role
        FROM clans c
        JOIN clan_members cm ON c.clan_id = cm.clan_id
        WHERE cm.user_id = ?
    """, (user_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None

# ============================================================
# 👻 RUHLAR OLAMI TIKISHLARI (AFTERLIFE BETS)
# ============================================================

async def record_afterlife_bet(game_id: int, user_id: int, predicted_team: str, amount: int) -> bool:
    if amount <= 0:
        return False
    if not await change_balance(user_id, "coin", -amount, "Ruhlar olami tikishi"):
        return False
    db = await get_db()
    now = now_iso()
    await db.execute("""
        INSERT INTO afterlife_bets (game_id, user_id, predicted_team, amount, resolved, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
    """, (game_id, user_id, predicted_team, amount, now))
    await db.commit()
    return True

async def resolve_afterlife_bets(game_id: int, winning_team: str):
    db = await get_db()
    async with db.execute("""
        SELECT * FROM afterlife_bets WHERE game_id = ? AND resolved = 0
    """, (game_id,)) as cursor:
        bets = await cursor.fetchall()

    for bet in bets:
        uid = bet["user_id"]
        pred = bet["predicted_team"]
        amount = bet["amount"]
        if pred == winning_team:
            win_amount = amount * 2
            await change_balance(uid, "coin", win_amount, f"Ruhlar olami yutug'i: {pred}")
        await db.execute("UPDATE afterlife_bets SET resolved = 1 WHERE id = ?", (bet["id"],))
    await db.commit()


# ============================================================
# 👥 GURUH FOYDALANUVCHILARI (GROUP USERS)
# ============================================================

async def track_group_member(chat_id: int, user) -> None:
    """Record or update group member in group_users table."""
    if not user or getattr(user, "is_bot", False):
        return
    db = await get_db()
    name = (getattr(user, "full_name", None) or getattr(user, "first_name", None) or "O'yinchi")[:100]
    username = getattr(user, "username", None) or ""
    now = now_iso()
    try:
        await db.execute("""
            INSERT INTO group_users (chat_id, user_id, name, username, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                name = excluded.name,
                username = excluded.username,
                updated_at = excluded.updated_at
        """, (chat_id, user.id, name, username, now))
        await db.commit()
    except Exception as e:
        log.warning("Could not track group member: %s", e)

async def get_group_members(chat_id: int, limit: int = 150) -> List[Dict[str, Any]]:
    """Retrieve known members of this group."""
    db = await get_db()
    try:
        async with db.execute("""
            SELECT user_id, name, username FROM group_users
            WHERE chat_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (chat_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        log.warning("Could not get group members: %s", e)
        return []

