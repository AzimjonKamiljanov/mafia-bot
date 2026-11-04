import os
import aiosqlite
import logging
from config import DB_PATH

log = logging.getLogger("detektiv.db")

_db_connection = None

async def get_db() -> aiosqlite.Connection:
    """Return a shared or new aiosqlite connection with Row factory configured."""
    global _db_connection
    if _db_connection is None:
        if DB_PATH != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(DB_PATH))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        _db_connection = await aiosqlite.connect(DB_PATH, timeout=30.0)
        _db_connection.row_factory = aiosqlite.Row
        await _db_connection.execute("PRAGMA journal_mode=WAL")
        await _db_connection.execute("PRAGMA foreign_keys=ON")
        await _db_connection.execute("PRAGMA busy_timeout=30000")
    return _db_connection

async def close_db():
    global _db_connection
    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None

async def init_db():
    """Ensure all required tables, columns, and indexes are initialized asynchronously."""
    db = await get_db()

    # Pre-migration: If group_settings is an existing physical table, merge into chat_settings and drop it
    try:
        async with db.execute("SELECT type FROM sqlite_master WHERE name = 'group_settings'") as cur:
            tbl_info = await cur.fetchone()
            if tbl_info and tbl_info["type"] == "table":
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS chat_settings (
                        chat_id INTEGER PRIMARY KEY,
                        lobby_seconds INTEGER NOT NULL DEFAULT 300,
                        night_seconds INTEGER NOT NULL DEFAULT 60,
                        day_seconds INTEGER NOT NULL DEFAULT 15,
                        vote_seconds INTEGER NOT NULL DEFAULT 45,
                        verdict_seconds INTEGER NOT NULL DEFAULT 25,
                        disabled_roles TEXT NOT NULL DEFAULT '[]',
                        updated_at TEXT NOT NULL
                    )
                """)
                await db.execute("""
                    INSERT OR IGNORE INTO chat_settings (chat_id, lobby_seconds, night_seconds, day_seconds, vote_seconds, verdict_seconds, disabled_roles, updated_at)
                    SELECT chat_id, lobby_seconds, night_seconds, day_seconds, vote_seconds, verdict_seconds, disabled_roles, updated_at FROM group_settings
                """)
                await db.execute("DROP TABLE group_settings")
                await db.commit()
    except Exception as e:
        log.debug("group_settings pre-migration notice: %s", e)

    # 1. Asosiy jadvallar
    await db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        username TEXT DEFAULT '',
        coin INTEGER NOT NULL DEFAULT 0,
        gold INTEGER NOT NULL DEFAULT 0,
        games INTEGER NOT NULL DEFAULT 0,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS badges (
        user_id INTEGER PRIMARY KEY,
        badge_key TEXT NOT NULL,
        badge_name TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS inventory (
        user_id INTEGER PRIMARY KEY,
        revenge_knife INTEGER NOT NULL DEFAULT 0,
        evidence INTEGER NOT NULL DEFAULT 0,
        protection INTEGER NOT NULL DEFAULT 0,
        hint INTEGER NOT NULL DEFAULT 0,
        special_detective INTEGER NOT NULL DEFAULT 0,
        rose INTEGER NOT NULL DEFAULT 0,
        fake_document INTEGER NOT NULL DEFAULT 0,
        ruler_protection INTEGER NOT NULL DEFAULT 0,
        extra_vote INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS games (
        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        state TEXT NOT NULL,
        phase TEXT NOT NULL,
        night INTEGER NOT NULL DEFAULT 0,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        finished_at TEXT
    );

    CREATE TABLE IF NOT EXISTS game_players (
        game_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        role TEXT DEFAULT '',
        alive INTEGER NOT NULL DEFAULT 1,
        joined_at TEXT NOT NULL,
        PRIMARY KEY(game_id, user_id),
        FOREIGN KEY(game_id) REFERENCES games(game_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        amount INTEGER NOT NULL,
        currency TEXT NOT NULL,
        note TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS game_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        winners TEXT NOT NULL,
        ended_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS group_users (
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        username TEXT DEFAULT '',
        updated_at TEXT NOT NULL,
        PRIMARY KEY(chat_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id INTEGER PRIMARY KEY,
        lobby_seconds INTEGER NOT NULL DEFAULT 300,
        night_seconds INTEGER NOT NULL DEFAULT 60,
        day_seconds INTEGER NOT NULL DEFAULT 15,
        vote_seconds INTEGER NOT NULL DEFAULT 45,
        verdict_seconds INTEGER NOT NULL DEFAULT 25,
        disabled_roles TEXT NOT NULL DEFAULT '[]',
        updated_at TEXT NOT NULL
    );

    CREATE VIEW IF NOT EXISTS group_settings AS SELECT * FROM chat_settings;

    CREATE TRIGGER IF NOT EXISTS trg_group_settings_insert
    INSTEAD OF INSERT ON group_settings
    BEGIN
        INSERT OR REPLACE INTO chat_settings (chat_id, lobby_seconds, night_seconds, day_seconds, vote_seconds, verdict_seconds, disabled_roles, updated_at)
        VALUES (NEW.chat_id, NEW.lobby_seconds, NEW.night_seconds, NEW.day_seconds, NEW.vote_seconds, NEW.verdict_seconds, NEW.disabled_roles, NEW.updated_at);
    END;

    CREATE TRIGGER IF NOT EXISTS trg_group_settings_update
    INSTEAD OF UPDATE ON group_settings
    BEGIN
        UPDATE chat_settings
        SET lobby_seconds = NEW.lobby_seconds,
            night_seconds = NEW.night_seconds,
            day_seconds = NEW.day_seconds,
            vote_seconds = NEW.vote_seconds,
            verdict_seconds = NEW.verdict_seconds,
            disabled_roles = NEW.disabled_roles,
            updated_at = NEW.updated_at
        WHERE chat_id = OLD.chat_id;
    END;

    CREATE TRIGGER IF NOT EXISTS trg_group_settings_delete
    INSTEAD OF DELETE ON group_settings
    BEGIN
        DELETE FROM chat_settings WHERE chat_id = OLD.chat_id;
    END;

    CREATE TABLE IF NOT EXISTS bot_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS social_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_id INTEGER NOT NULL,
        target_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS social_links (
        user_id INTEGER NOT NULL,
        other_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(user_id, kind)
    );

    CREATE TABLE IF NOT EXISTS owned_badges (
        user_id INTEGER NOT NULL,
        badge_key TEXT NOT NULL,
        badge_name TEXT NOT NULL,
        bought_at TEXT NOT NULL,
        PRIMARY KEY(user_id, badge_key)
    );

    -- 📜 Vasiyatnoma (The Last Will)
    CREATE TABLE IF NOT EXISTS wills (
        user_id INTEGER PRIMARY KEY,
        will_text TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    -- ⚔️ Klanlar (Mafia Syndicates / Families)
    CREATE TABLE IF NOT EXISTS clans (
        clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        tag TEXT NOT NULL,
        leader_id INTEGER NOT NULL,
        coins INTEGER NOT NULL DEFAULT 0,
        score INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS clan_members (
        clan_id INTEGER NOT NULL,
        user_id INTEGER PRIMARY KEY,
        role TEXT NOT NULL DEFAULT 'member',
        joined_at TEXT NOT NULL,
        FOREIGN KEY(clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    -- 👻 Ruhlar Olami Tikishlari (Afterlife Predictions)
    CREATE TABLE IF NOT EXISTS afterlife_bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        predicted_team TEXT NOT NULL,
        amount INTEGER NOT NULL DEFAULT 0,
        resolved INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_games_chat_state ON games(chat_id, state);
    CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
    CREATE INDEX IF NOT EXISTS idx_afterlife_game ON afterlife_bets(game_id);
    """)

    # Qo'shimcha ustunlarni tekshirish (migratsiyalar)
    for col, col_def in [
        ("rose", "INTEGER NOT NULL DEFAULT 0"),
        ("fake_document", "INTEGER NOT NULL DEFAULT 0"),
        ("ruler_protection", "INTEGER NOT NULL DEFAULT 0"),
        ("extra_vote", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            await db.execute(f"ALTER TABLE inventory ADD COLUMN {col} {col_def}")
            await db.commit()
        except aiosqlite.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                log.exception("Unexpected error while adding %s column to inventory: %s", col, e)
                raise

    # Versioned migration using PRAGMA user_version
    async with db.execute("PRAGMA user_version") as cur:
        row = await cur.fetchone()
        user_ver = row[0] if row else 0

    if user_ver < 1:
        async with db.execute("SELECT type FROM sqlite_master WHERE name = 'group_settings'") as cur:
            tbl_info = await cur.fetchone()
            if tbl_info and tbl_info["type"] == "table":
                try:
                    await db.execute("""
                        INSERT OR IGNORE INTO chat_settings (chat_id, lobby_seconds, night_seconds, day_seconds, vote_seconds, verdict_seconds, disabled_roles, updated_at)
                        SELECT chat_id, lobby_seconds, night_seconds, day_seconds, vote_seconds, verdict_seconds, disabled_roles, updated_at FROM group_settings
                    """)
                    await db.execute("DROP TABLE group_settings")
                except Exception as e:
                    log.debug("group_settings merge note: %s", e)

        await db.execute("CREATE VIEW IF NOT EXISTS group_settings AS SELECT * FROM chat_settings")
        await db.execute("PRAGMA user_version = 1")
        await db.commit()

    # One-time migration to close historical stale rows stuck in state='active' (Migration v2)
    if user_ver < 2:
        try:
            await db.execute("""
                UPDATE games
                SET state = 'aborted', finished_at = COALESCE(updated_at, created_at)
                WHERE state = 'active'
            """)
            await db.execute("PRAGMA user_version = 2")
            await db.commit()
            log.info("Migration v2: Historical stale games marked as aborted.")
        except Exception as e:
            log.warning("Could not migrate historical stale games: %s", e)

    log.info("Database schema verification and initialization completed.")
