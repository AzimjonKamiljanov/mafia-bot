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
    if not will_text or not will_text.strip():
        return f"📜 *{player_name}* hech qanday vasiyatnoma qoldirmagan."

    lines = [
        f"📜 *{player_name}ning So'nggi Vasiyatnomasi:*",
        f"> _{will_text.strip()}_"
    ]
    return "\n".join(lines)

