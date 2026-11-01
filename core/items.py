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
- Items activated manually via command/callback are armed in:
  game.setdefault("armed_items", {}).setdefault(user_id, set()).add(item_id)
  so that passive items (shield, protection, knife, fake doc) are honored when the event triggers.
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
    "shield": {"shield", "ruler_protection", "qatldan_himoya", "qatldan_ximoya", "hukmdan_himoya", "hukmdan_ximoya"},
    "ruler_protection": {"shield", "ruler_protection", "qatldan_himoya", "qatldan_ximoya", "hukmdan_himoya", "hukmdan_ximoya"},
    "qatldan_himoya": {"shield", "ruler_protection", "qatldan_himoya", "qatldan_ximoya", "hukmdan_himoya", "hukmdan_ximoya"},
    "qatldan_ximoya": {"shield", "ruler_protection", "qatldan_himoya", "qatldan_ximoya", "hukmdan_himoya", "hukmdan_ximoya"},
    "hukmdan_himoya": {"shield", "ruler_protection", "qatldan_himoya", "qatldan_ximoya", "hukmdan_himoya", "hukmdan_ximoya"},
    "hukmdan_ximoya": {"shield", "ruler_protection", "qatldan_himoya", "qatldan_ximoya", "hukmdan_himoya", "hukmdan_ximoya"},

    "protection": {"protection", "night_protection", "coin_protect", "tungi_himoya", "tungi_ximoya", "himoya", "ximoya"},
    "coin_protect": {"protection", "night_protection", "coin_protect", "tungi_himoya", "tungi_ximoya", "himoya", "ximoya"},
    "night_protection": {"protection", "night_protection", "coin_protect", "tungi_himoya", "tungi_ximoya", "himoya", "ximoya"},
    "tungi_himoya": {"protection", "night_protection", "coin_protect", "tungi_himoya", "tungi_ximoya", "himoya", "ximoya"},
    "tungi_ximoya": {"protection", "night_protection", "coin_protect", "tungi_himoya", "tungi_ximoya", "himoya", "ximoya"},
    "himoya": {"protection", "night_protection", "coin_protect", "tungi_himoya", "tungi_ximoya", "himoya", "ximoya"},
    "ximoya": {"protection", "night_protection", "coin_protect", "tungi_himoya", "tungi_ximoya", "himoya", "ximoya"},

    "fake_document": {"fake_document", "fake_doc", "soxta_hujjat", "soxta_xujjat", "hujjat", "xujjat"},
    "fake_doc": {"fake_document", "fake_doc", "soxta_hujjat", "soxta_xujjat", "hujjat", "xujjat"},
    "soxta_hujjat": {"fake_document", "fake_doc", "soxta_hujjat", "soxta_xujjat", "hujjat", "xujjat"},
    "soxta_xujjat": {"fake_document", "fake_doc", "soxta_hujjat", "soxta_xujjat", "hujjat", "xujjat"},
    "hujjat": {"fake_document", "fake_doc", "soxta_hujjat", "soxta_xujjat", "hujjat", "xujjat"},
    "xujjat": {"fake_document", "fake_doc", "soxta_hujjat", "soxta_xujjat", "hujjat", "xujjat"},

    "revenge_knife": {"revenge_knife", "knife", "pichoq", "qasos_pichogi", "qasos_pichoq"},
    "knife": {"revenge_knife", "knife", "pichoq", "qasos_pichogi", "qasos_pichoq"},
    "pichoq": {"revenge_knife", "knife", "pichoq", "qasos_pichogi", "qasos_pichoq"},
    "qasos_pichogi": {"revenge_knife", "knife", "pichoq", "qasos_pichogi", "qasos_pichoq"},
    "qasos_pichoq": {"revenge_knife", "knife", "pichoq", "qasos_pichogi", "qasos_pichoq"},

    "extra_vote": {"extra_vote", "extra_votes", "qoshimcha_ovoz", "ovoz"},
    "extra_votes": {"extra_vote", "extra_votes", "qoshimcha_ovoz", "ovoz"},
    "qoshimcha_ovoz": {"extra_vote", "extra_votes", "qoshimcha_ovoz", "ovoz"},
    "ovoz": {"extra_vote", "extra_votes", "qoshimcha_ovoz", "ovoz"},
}

ITEM_DB_FIELDS: Dict[str, str] = {
    "shield": "ruler_protection",
    "ruler_protection": "ruler_protection",
    "qatldan_himoya": "ruler_protection",
    "qatldan_ximoya": "ruler_protection",
    "hukmdan_himoya": "ruler_protection",
    "hukmdan_ximoya": "ruler_protection",

    "protection": "protection",
    "coin_protect": "protection",
    "night_protection": "protection",
    "tungi_himoya": "protection",
    "tungi_ximoya": "protection",
    "himoya": "protection",
    "ximoya": "protection",

    "fake_document": "fake_document",
    "fake_doc": "fake_document",
    "soxta_hujjat": "fake_document",
    "soxta_xujjat": "fake_document",
    "hujjat": "fake_document",
    "xujjat": "fake_document",

    "revenge_knife": "revenge_knife",
    "knife": "revenge_knife",
    "pichoq": "revenge_knife",
    "qasos_pichogi": "revenge_knife",
    "qasos_pichoq": "revenge_knife",

    "extra_vote": "extra_vote",
    "extra_votes": "extra_vote",
    "qoshimcha_ovoz": "extra_vote",
    "ovoz": "extra_vote",
}

ITEM_TITLES: Dict[str, str] = {
    "ruler_protection": "👑 Hukmdan himoya (Qatldan himoya)",
    "shield": "👑 Hukmdan himoya (Qatldan himoya)",
    "qatldan_himoya": "👑 Hukmdan himoya (Qatldan himoya)",
    "qatldan_ximoya": "👑 Hukmdan himoya (Qatldan himoya)",
    "protection": "🛡️ Tungi himoya",
    "coin_protect": "🛡️ Tungi himoya",
    "night_protection": "🛡️ Tungi himoya",
    "tungi_himoya": "🛡️ Tungi himoya",
    "tungi_ximoya": "🛡️ Tungi himoya",
    "himoya": "🛡️ Tungi himoya",
    "ximoya": "🛡️ Tungi himoya",
    "fake_document": "📄 Soxta hujjat",
    "fake_doc": "📄 Soxta hujjat",
    "soxta_hujjat": "📄 Soxta hujjat",
    "revenge_knife": "🔪 Qasos pichog'i",
    "knife": "🔪 Qasos pichog'i",
    "pichoq": "🔪 Qasos pichog'i",
    "extra_vote": "🗳️ Qo'shimcha ovoz",
    "extra_votes": "🗳️ Qo'shimcha ovoz",
    "qoshimcha_ovoz": "🗳️ Qo'shimcha ovoz",
}

def normalize_item_id(item_id: str) -> str:
    """Normalize item input strings (strip whitespace, replace spaces with underscores)."""
    raw = item_id.lower().strip().replace(" ", "_").replace("-", "_")
    return ITEM_DB_FIELDS.get(raw, raw)

def get_used_items(game: Dict[str, Any], user_id: int) -> Set[str]:
    """Retrieve the set of items already used by a player in the given game."""
    return game.setdefault("used_items", {}).setdefault(user_id, set())

def has_used_item(game: Dict[str, Any], user_id: int, item_id: str) -> bool:
    """Check if the player has already used this item (or any of its aliases) in this game."""
    used = get_used_items(game, user_id)
    canonical = item_id.lower().strip().replace(" ", "_")
    aliases = ITEM_ALIASES.get(canonical, {canonical})
    return bool(used.intersection(aliases))

def mark_item_used(game: Dict[str, Any], user_id: int, item_id: str):
    """Mark an item and all its aliases as used for this player in the active game."""
    used = get_used_items(game, user_id)
    canonical = item_id.lower().strip().replace(" ", "_")
    aliases = ITEM_ALIASES.get(canonical, {canonical})
    used.update(aliases)

def get_armed_items(game: Dict[str, Any], user_id: int) -> Set[str]:
    """Retrieve items manually armed/activated by a player in this game."""
    return game.setdefault("armed_items", {}).setdefault(user_id, set())

def is_item_armed(game: Dict[str, Any], user_id: int, item_id: str) -> bool:
    """Check if an item is armed for this player in this game."""
    armed = get_armed_items(game, user_id)
    canonical = item_id.lower().strip().replace(" ", "_")
    aliases = ITEM_ALIASES.get(canonical, {canonical})
    return bool(armed.intersection(aliases))

def arm_item(game: Dict[str, Any], user_id: int, item_id: str):
    """Arm an item so that its passive effect will trigger upon next event."""
    armed = get_armed_items(game, user_id)
    canonical = item_id.lower().strip().replace(" ", "_")
    aliases = ITEM_ALIASES.get(canonical, {canonical})
    armed.update(aliases)

def disarm_item(game: Dict[str, Any], user_id: int, item_id: str) -> bool:
    """Disarm an item after its effect triggers."""
    armed = get_armed_items(game, user_id)
    canonical = item_id.lower().strip().replace(" ", "_")
    aliases = ITEM_ALIASES.get(canonical, {canonical})
    had = bool(armed.intersection(aliases))
    armed.difference_update(aliases)
    return had

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

    Deducts 1 from the player's inventory if allowed, records the usage in the game state,
    and arms the item for in-game resolution.
    Returns (success: bool, message: str).
    """
    allowed, err_msg = can_use_item_in_game(game, user_id, item_id)
    if not allowed:
        return False, err_msg

    canonical = item_id.lower().strip().replace(" ", "_")
    field = db_field or ITEM_DB_FIELDS.get(canonical, canonical)

    if not await take_item(user_id, field, 1):
        return False, NO_ITEM_MSG

    mark_item_used(game, user_id, item_id)
    arm_item(game, user_id, item_id)
    if canonical in ("extra_vote", "extra_votes", "qoshimcha_ovoz", "ovoz"):
        game.setdefault("extra_votes", set()).add(user_id)

    title = ITEM_TITLES.get(canonical, f"Buyum ({item_id})")
    log.info("Player %s used shop item %s (%s) in game %s", user_id, item_id, field, game.get("chat"))
    return True, f"✅ {title} muvaffaqiyatli ishlatildi (Har bir o'yinda faqat 1 marta ishlatish mumkin)!"
