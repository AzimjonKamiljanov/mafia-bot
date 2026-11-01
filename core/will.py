from typing import Optional
from database.models import get_will, set_will

async def save_player_will(user_id: int, text: str) -> bool:
    clean = text.strip()
    if not clean:
        return False
    await set_will(user_id, clean)
    return True

async def fetch_player_will(user_id: int) -> str:
    return await get_will(user_id)

def format_will_announcement(player_name: str, will_text: Optional[str]) -> str:
    import html
    from core.emojis import tg_emoji
    clean_name = html.escape(str(player_name))
    doc_icon = tg_emoji("item_doc", "📜", "SHOP")
    if not will_text or not will_text.strip():
        return f"{doc_icon} <b>{clean_name}</b> hech qanday vasiyatnoma qoldirmagan."

    clean_will = html.escape(will_text.strip())
    lines = [
        f"{doc_icon} <b>{clean_name}ning So'nggi Vasiyatnomasi:</b>",
        f"<blockquote><i>{clean_will}</i></blockquote>"
    ]
    return "\n".join(lines)

