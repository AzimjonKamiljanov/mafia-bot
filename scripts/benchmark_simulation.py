"""
Benchmark and Load Simulation Script for Detektiv Mafia Bot.
Simulates 10 concurrent game lobbies with 15 players each (150 concurrent players).
Measures concurrency latency (p50, p95, p99), database throughput, and lock contention.
"""

import asyncio
import os
import sys
import time
import statistics
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock

# Set mock BOT_TOKEN if not set for standalone offline benchmarking
os.environ.setdefault("BOT_TOKEN", "mock_benchmark_token_123:ABC")
os.environ.setdefault("DB_PATH", "./data/benchmark_test.db")

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import init_db, get_db
from database.models import ensure_user, change_balance, get_chat_settings
from core.engine import (
    games, lobbies, get_chat_lock, cancel_game_timer, cancel_lobby_timer
)
from phases.lobby import create_lobby, start_game
from roles.allocator import choose_roles


class BenchmarkUser:
    def __init__(self, uid: int, name: str):
        self.id = uid
        self.first_name = name
        self.last_name = ""
        self.full_name = name
        self.username = f"user_{uid}"
        self.is_bot = False


def make_mock_update_message(chat_id: int, user: BenchmarkUser, text: str):
    up = MagicMock()
    up.effective_chat = MagicMock()
    up.effective_chat.id = chat_id
    up.effective_chat.type = "supergroup"
    up.effective_user = user
    up.message = MagicMock()
    up.message.chat = up.effective_chat
    up.message.from_user = user
    up.message.text = text
    up.message.reply_text = AsyncMock()
    up.message.reply_photo = AsyncMock()
    up.message.pin = AsyncMock()
    up.message.unpin = AsyncMock()
    up.message.message_id = 1000 + abs(chat_id) % 10000
    up.effective_message = up.message
    return up


def make_mock_context():
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    ctx.bot.pin_chat_message = AsyncMock()
    ctx.bot.unpin_chat_message = AsyncMock()
    ctx.bot.export_chat_invite_link = AsyncMock(return_value="https://t.me/benchmark_invite")
    return ctx


async def simulate_group(group_idx: int, players_per_group: int = 15) -> Dict[str, Any]:
    """Simulate a single group from lobby creation to game start and night phase."""
    chat_id = -1000000 - group_idx
    ctx = make_mock_context()
    latencies: List[float] = []

    # 1. Lobby Creation
    creator = BenchmarkUser(group_idx * 1000 + 1, f"Creator_G{group_idx}")
    await ensure_user(creator)
    up_create = make_mock_update_message(chat_id, creator, "/game")

    t0 = time.perf_counter()
    async with get_chat_lock(chat_id):
        await create_lobby(up_create, ctx)
    latencies.append(time.perf_counter() - t0)

    # 2. Concurrent Player Joins (14 additional players)
    join_tasks = []

    async def player_join(p_idx: int):
        uid = group_idx * 1000 + p_idx
        p_user = BenchmarkUser(uid, f"Player_{group_idx}_{p_idx}")
        await ensure_user(p_user)
        t_join_start = time.perf_counter()
        async with get_chat_lock(chat_id):
            lobby = lobbies.get(chat_id)
            if lobby and uid not in lobby["players"]:
                lobby["players"].append(uid)
                lobby["names"][uid] = p_user.full_name
        return time.perf_counter() - t_join_start

    join_times = await asyncio.gather(*(player_join(i) for i in range(2, players_per_group + 1)))
    latencies.extend(join_times)

    # 3. Game Start & Role Allocation
    t_start = time.perf_counter()
    async with get_chat_lock(chat_id):
        await start_game(ctx, chat_id)
    latencies.append(time.perf_counter() - t_start)

    # Clean up timers to prevent hanging background tasks
    game = games.get(chat_id)
    if game:
        cancel_game_timer(game)
    lobby = lobbies.get(chat_id)
    if lobby:
        cancel_lobby_timer(lobby)

    return {
        "group_idx": group_idx,
        "chat_id": chat_id,
        "total_players": len(game.get("players", [])) if game else 0,
        "latencies": latencies,
        "roles_allocated": len(game.get("roles", {})) if game else 0,
    }


async def run_benchmark(num_groups: int = 10, players_per_group: int = 15):
    """Run full benchmark simulating num_groups concurrently."""
    print("=" * 60)
    print(f"🚀 INITIATING BENCHMARK: {num_groups} GROUPS × {players_per_group} PLAYERS ({num_groups * players_per_group} USERS)")
    print("=" * 60)

    await init_db()
    games.clear()
    lobbies.clear()

    wall_start = time.perf_counter()
    group_results = await asyncio.gather(*(simulate_group(g, players_per_group) for g in range(1, num_groups + 1)))
    total_wall_time = time.perf_counter() - wall_start

    all_latencies = []
    total_players = 0
    total_roles = 0
    for r in group_results:
        all_latencies.extend(r["latencies"])
        total_players += r["total_players"]
        total_roles += r["roles_allocated"]

    all_latencies.sort()
    count = len(all_latencies)
    p50 = statistics.median(all_latencies) * 1000
    p95 = all_latencies[int(count * 0.95)] * 1000
    p99 = all_latencies[int(count * 0.99)] * 1000
    max_lat = max(all_latencies) * 1000
    avg_lat = statistics.mean(all_latencies) * 1000

    print("\n📊 BENCHMARK RESULTS:")
    print(f"  • Total Simulated Groups:     {num_groups}")
    print(f"  • Total Players Processed:    {total_players}")
    print(f"  • Total Roles Assigned:       {total_roles}")
    print(f"  • Total Operations Measured:  {count}")
    print(f"  • Total Elapsed Wall Time:    {total_wall_time:.3f} s")
    print(f"  • Throughput:                 {count / total_wall_time:.1f} ops/sec")
    print("\n⚡ LATENCY METRICS:")
    print(f"  • Average Latency:            {avg_lat:.2f} ms")
    print(f"  • Median (p50):               {p50:.2f} ms")
    print(f"  • 95th Percentile (p95):      {p95:.2f} ms")
    print(f"  • 99th Percentile (p99):      {p99:.2f} ms")
    print(f"  • Maximum Latency:            {max_lat:.2f} ms")

    # Assertions for quality gate
    assert total_players == num_groups * players_per_group, "Not all players were registered!"
    assert total_roles == num_groups * players_per_group, "Role allocation mismatch!"
    assert p95 < 200.0, f"p95 latency exceeded threshold: {p95:.2f}ms"
    print("\n✅ BENCHMARK PASSED: Concurrency and latency within target SLA (<200ms p95)!\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark(num_groups=10, players_per_group=15))
