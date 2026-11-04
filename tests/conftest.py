import os

os.environ.setdefault("BOT_TOKEN", "123456789:MOCK_TEST_BOT_TOKEN")
os.environ.setdefault("ADMIN_IDS", "8048940366,7651553630")
os.environ.setdefault(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "detektiv.db"),
)

import pytest_asyncio
import asyncio
from database.db import close_db
from core.engine import games, lobbies, cancel_game_timer, cancel_lobby_timer

@pytest_asyncio.fixture(autouse=True)
async def cleanup_database_and_tasks():
    yield
    for game in list(games.values()):
        cancel_game_timer(game)
    for lobby in list(lobbies.values()):
        cancel_lobby_timer(lobby)
    await close_db()
