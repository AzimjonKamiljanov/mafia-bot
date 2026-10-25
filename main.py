"""Detektiv / Mafia Bot Main Module.

Provides both standalone application execution and backward-compatible module exports
for tests and legacy scripts.
"""

import sys
import asyncio
from config import BOT_TOKEN, ADMIN_ID, DB_PATH, ROLES, ROLE_ORDER, REPEATABLE_ROLES, NIGHT_ACTIVE_ROLES
from database.db import init_db, get_db, close_db
from database.models import (
    ensure_user, get_user, is_admin, get_balance, change_balance,
    get_inventory, add_item, take_item, get_badge, set_badge,
    deactivate_badge, get_owned_badges, save_owned_badge, get_will, set_will
)
from roles.allocator import choose_roles
from roles.base import get_role_info, get_role_icon, get_role_team
from core.engine import (
    games, lobbies, pending_last_words, display_name, save_runtime, check_winner, finish_game
)
from core.storyteller import generate_morning_story, generate_verdict_story
from core.clues import generate_forensic_clue
from core.weather import roll_weather
from core.will import save_player_will, fetch_player_will, format_will_announcement
from phases.lobby import create_lobby, start_game, lobby_text, lobby_keyboard
from phases.night import start_night, resolve_night, get_role_action_buttons, get_target_selection_keyboard
from phases.day import day_phase
from phases.voting import start_voting, finish_voting
from phases.verdict import verdict_phase, resolve_verdict
from bot import create_bot_app, main

# Legacy execute_action compatibility wrapper
async def execute_action(context, game, actor, action, target):
    """Compatibility wrapper for execute_action."""
    role = game.get("roles", {}).get(actor)

    if action == "kill":
        if role == "Boshliq":
            game.setdefault("kill_targets", {})[actor] = target
            return "👑 Nishon tanlandi. 🔪 Qotil shu nishonni amalga oshiradi."
        if role == "Qotil":
            boss_alive = any(
                game.get("alive", {}).get(u, False) and game.get("roles", {}).get(u) == "Boshliq"
                for u in game.get("players", [])
            )
            if boss_alive:
                return "❌ Boshliq tirik. Nishonni faqat Boshliq tanlaydi."
            game.setdefault("kill_targets", {})[actor] = target
            return "🔪 Siz endi Boshliq vazifasidasiz. Nishon belgilandi."
        return "❌ Bu rol o'ldirish qobiliyatiga ega emas."

    if action == "detective":
        target_role = game["roles"].get(target, "Fuqaro")
        game.setdefault("detective_results", {})[str(actor)] = {
            "target": target,
            "role": target_role,
            "night": game.get("night", 1)
        }
        return "🔎 Tekshiruv qabul qilindi. Natija tongda ma'lum bo'ladi."

    if action == "sheriff_check":
        is_red = (ROLES.get(game["roles"].get(target)) == "red")
        team_str = "🔴 QIZIL JAMOA" if is_red else "🔵 QIZIL EMAS"
        return f"👮 Sherif tekshiruvi: {team_str}"

    if action == "protect":
        game.setdefault("protected", set()).add(target)
        game.setdefault("protected_by", {})[target] = actor
        return "🩺 Davolash qabul qilindi."

    return "✅ Qabul qilindi."

if __name__ == "__main__":
    main()
