"""In-game shop items handling and restrictions.

Rules:
- Shop items used during gameplay (shield / qatldan himoya, protection / tungi himoya,
  extra_vote / qo'shimcha ovoz, revenge_knife / pichoq, fake_document / soxta hujjat):
  Strictly 1 use per game per player.
- If a player attempts to use an item already used in the active game, the action is rejected
  with an alert:
  "⚠️ Siz ushbu o'yinda bu buyumdan allaqachon foydalangansiz! Har bir o'yinda faqat 1 marta ishlatish mumkin."
- In-game item usage per player is tracked inside active game state:
  game.setdefault("used_items", {}).setdefault(user_id, set()).add(item_id)
"""

import logging
from typing import Dict, Any, Set, Tuple, Optional
from database.models import take_item

log = logging.getLogger("detektiv.core.items")

ALREADY_USED_MSG = "⚠️ Siz ushbu o'yinda bu buyumdan allaqachon foydalangansiz! Har bir o'yinda faqat 1 marta ishlatish mumkin."
NO_ITEM_MSG = "❌ Sizda ushbu buyum mavjud emas! Avval do'kondan xarid qiling."
NOT_IN_GAME_MSG = "❌ Siz hozirda faol o'yinda emassiz."
ALREADY_DEAD_MSG = "💀 Halok bo'lganlar buyum ishlata olmaydi."

# Comprehensive item alias sets mapping to canonical names
ITEM_ALIASES: Dict[str, Set[str]] = {
    "shield": {"shield", "ruler_protection", "qatldan_himoya"},
    "ruler_protection": {"shield", "ruler_protection", "qatldan_himoya"},
    "qatldan_himoya": {"shield", "ruler_protection", "qatldan_himoya"},

    "protection": {"protection", "night_protection", "coin_protect", "tungi_himoya"},
    "coin_protect": {"protection", "night_protection", "coin_protect", "tungi_himoya"},
    "night_protection": {"protection", "night_protection", "coin_protect", "tungi_himoya"},
    "tungi_himoya": {"protection", "night_protection", "coin_protect", "tungi_himoya"},

    "fake_document": {"fake_document", "fake_doc", "soxta_hujjat"},
    "fake_doc": {"fake_document", "fake_doc", "soxta_hujjat"},
    "soxta_hujjat": {"fake_document", "fake_doc", "soxta_hujjat"},

    "revenge_knife": {"revenge_knife", "knife", "pichoq"},
    "knife": {"revenge_knife", "knife", "pichoq"},
    "pichoq": {"revenge_knife", "knife", "pichoq"},

    "extra_vote": {"extra_vote", "extra_votes", "qoshimcha_ovoz"},
    "extra_votes": {"extra_vote", "extra_votes", "qoshimcha_ovoz"},
    "qoshimcha_ovoz": {"extra_vote", "extra_votes", "qoshimcha_ovoz"},
}

ITEM_DB_FIELDS: Dict[str, str] = {
    "shield": "ruler_protection",
    "ruler_protection": "ruler_protection",
    "qatldan_himoya": "ruler_protection",

    "protection": "protection",
    "coin_protect": "protection",
    "night_protection": "protection",
    "tungi_himoya": "protection",

    "fake_document": "fake_document",
    "fake_doc": "fake_document",
    "soxta_hujjat": "fake_document",

    "revenge_knife": "revenge_knife",
    "knife": "revenge_knife",
    "pichoq": "revenge_knife",

    "extra_vote": "extra_vote",
    "extra_votes": "extra_vote",
    "qoshimcha_ovoz": "extra_vote",
}

ITEM_TITLES: Dict[str, str] = {
    "ruler_protection": "👑 Hukmdan himoya (Qatldan himoya)",
    "shield": "👑 Hukmdan himoya (Qatldan himoya)",
    "protection": "🛡️ Tungi himoya",
    "coin_protect": "🛡️ Tungi himoya",
    "fake_document": "📄 Soxta hujjat",
    "revenge_knife": "🔪 Qasos pichog'i",
    "extra_vote": "🗳️ Qo'shimcha ovoz",
}

def get_used_items(game: Dict[str, Any], user_id: int) -> Set[str]:
    """Retrieve the set of items already used by a player in the given game."""
    return game.setdefault("used_items", {}).setdefault(user_id, set())

def has_used_item(game: Dict[str, Any], user_id: int, item_id: str) -> bool:
    """Check if the player has already used this item (or any of its aliases) in this game."""
    used = get_used_items(game, user_id)
    canonical = item_id.lower().strip()
    aliases = ITEM_ALIASES.get(canonical, {canonical})
    return bool(used.intersection(aliases))

def mark_item_used(game: Dict[str, Any], user_id: int, item_id: str):
    """Mark an item and all its aliases as used for this player in the active game."""
    used = get_used_items(game, user_id)
    canonical = item_id.lower().strip()
    aliases = ITEM_ALIASES.get(canonical, {canonical})
    used.update(aliases)

def can_use_item_in_game(game: Dict[str, Any], user_id: int, item_id: str) -> Tuple[bool, str]:
    """Check whether a player is allowed to use the item in the active game."""
    if not game:
        return False, NOT_IN_GAME_MSG
    if not game.get("alive", {}).get(user_id, False):
        return False, ALREADY_DEAD_MSG
    if has_used_item(game, user_id, item_id):
        return False, ALREADY_USED_MSG
    return True, ""

async def consume_game_item(
    game: Dict[str, Any],
    user_id: int,
    item_id: str,
    db_field: Optional[str] = None
) -> Tuple[bool, str]:
    """Attempt to consume 1 item in-game with strict 1-use-per-game restriction.

    Deducts 1 from the player's inventory if allowed and records the usage in the game state.
    Returns (success: bool, message: str).
    """
    allowed, err_msg = can_use_item_in_game(game, user_id, item_id)
    if not allowed:
        return False, err_msg

    canonical = item_id.lower().strip()
    field = db_field or ITEM_DB_FIELDS.get(canonical, canonical)

    if not await take_item(user_id, field, 1):
        return False, NO_ITEM_MSG

    mark_item_used(game, user_id, item_id)
    title = ITEM_TITLES.get(canonical, f"Buyum ({item_id})")
    log.info("Player %s used shop item %s (%s) in game %s", user_id, item_id, field, game.get("chat"))
    return True, f"✅ {title} muvaffaqiyatli ishlatildi (Har bir o'yinda faqat 1 marta ishlatish mumkin)!"
