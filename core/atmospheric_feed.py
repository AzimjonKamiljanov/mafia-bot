import logging
from typing import Dict, Any, Optional
from telegram.ext import ContextTypes
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.core.atmospheric_feed")

# Group live messages matched to screenshot specifications
ROLE_LIVE_MESSAGES = {
    # 🔵 Shahar
    "Detektiv": f"{tg_emoji('detective', '🕵️‍♂️')} Detektiv izquvarlikka ketdi... 🔎",
    "Sherif": f"{tg_emoji('sheriff', '👮‍♂️')} Sherif gumondorning iziga tushdi... 🔎",
    "Doktor": f"{tg_emoji('doctor', '🩺')} Doktor bemor tomon shoshildi... 🩺",
    "Tansoqchi": f"{tg_emoji('item_shield', '🛡️', 'SHOP')} Tansoqchi nishonini himoya qilish uchun yo‘lga chiqdi... 🛡️",
    "Koldun": f"{tg_emoji('item_shield', '🛡️', 'SHOP')} Tansoqchi nishonini himoya qilish uchun yo‘lga chiqdi... 🛡️",
    "Advokat": f"{tg_emoji('voting', '⚖️')} Advokat mijozining uyiga yo‘l oldi... ⚖️",
    "Sayyoh": f"{tg_emoji('detective', '🚶')} Sayyoh mehmonga borish uchun yo‘lga chiqdi... 🚶",
    "Ruhshunos": f"{tg_emoji('detective', '🔮')} Ruhshunos sirli izlar ortidan ketdi... 🔮",
    "Boy": f"{tg_emoji('coin', '💎', 'SHOP')} Boy yashirin kelishuv uchun yo‘lga chiqdi... 💎",
    "Begona": f"{tg_emoji('detective', '🕴️')} Begona tun qorong‘usida nishon tomon yurdi... 🕴️",
    "Savdogar": f"{tg_emoji('cart', '🛒', 'SHOP')} Savdogar maxfiy yukini yetkazish uchun yo‘lga chiqdi... 🛒",

    # 🔴 Mafiya
    "Boshliq": f"{tg_emoji('don', '👑')} Boshliq maxfiy uchrashuvga yo‘l oldi... 👑",
    "Qotil": f"{tg_emoji('mafia', '🔪')} Qotil nishon tomon yashirincha yurdi... 🔪",
    "Soya": f"{tg_emoji('mafia', '🥷')} Soya tun zulmatida izquvarlar ortidan ketdi... 🥷",
    "Soxtachi": f"{tg_emoji('item_doc', '🎭', 'SHOP')} Soxtachi qora dalilni joylashtirish uchun yo‘lga chiqdi... 🎭",
    "Maftunkor": f"{tg_emoji('detective', '💃')} Maftunkor nishon tomon yo‘l oldi... 💃",
    "Bo‘ri": f"{tg_emoji('mafia', '🐺')} Bo‘ri tun qorong‘usida ovga chiqdi... 🐺",
    "Bo'ri": f"{tg_emoji('mafia', '🐺')} Bo‘ri tun qorong‘usida ovga chiqdi... 🐺",
    "Bori": f"{tg_emoji('mafia', '🐺')} Bo‘ri tun qorong‘usida ovga chiqdi... 🐺",

    # 🟡 Yakkaxon
    "Maniak": f"{tg_emoji('mafia_win', '🩸')} Maniak tun qorong‘usida ovga chiqdi... 🩸",
    "Pirotexnik": f"{tg_emoji('trigger', '🔥')} Pirotexnik nishonlarini belgilash uchun yo‘lga chiqdi... 🔥",
    "Qasoskor": f"{tg_emoji('item_knife', '⚔️', 'SHOP')} Qasoskor dushmani izidan ketdi... ⚔️",
    "Pul o‘g‘risi": f"{tg_emoji('coin', '💰', 'SHOP')} Pul o‘g‘risi boylik izlab tun qorong‘usiga chiqdi... 💰",
    "Pul o'g'risi": f"{tg_emoji('coin', '💰', 'SHOP')} Pul o‘g‘risi boylik izlab tun qorong‘usiga chiqdi... 💰",
    "Firibgar": f"{tg_emoji('detective', '🎪')} Firibgar boshqa qiyofada ko‘chaga chiqdi... 🎭",
    "Buqalamun": f"{tg_emoji('detective', '🎪')} Firibgar boshqa qiyofada ko‘chaga chiqdi... 🎭",
    "Joker": f"{tg_emoji('mafia_win', '🃏')} Shahar ko'chalarida telbaning qahqahasi yangradi...",
}

ROLE_SLEEP_MESSAGES = {
    # 🔵 Shahar
    "Detektiv": f"{tg_emoji('detective', '🕵️‍♂️')} Detektiv bu tun dam oldi... 😴",
    "Sherif": f"{tg_emoji('sheriff', '👮‍♂️')} Sherif bu tun dam oldi... 😴",
    "Doktor": f"{tg_emoji('doctor', '🩺')} Doktor bu tun dam oldi... 😴",
    "Tansoqchi": f"{tg_emoji('item_shield', '🛡️', 'SHOP')} Tansoqchi bu tun dam oldi... 😴",
    "Koldun": f"{tg_emoji('item_shield', '🛡️', 'SHOP')} Tansoqchi bu tun dam oldi... 😴",
    "Advokat": f"{tg_emoji('voting', '⚖️')} Advokat bu tun dam oldi... 😴",
    "Sayyoh": f"{tg_emoji('detective', '🚶')} Sayyoh bu tun dam oldi... 😴",
    "Ruhshunos": f"{tg_emoji('detective', '🔮')} Ruhshunos bu tun dam oldi... 😴",
    "Boy": f"{tg_emoji('coin', '💎', 'SHOP')} Boy bu tun dam oldi... 😴",
    "Begona": f"{tg_emoji('detective', '🕴️')} Begona bu tun dam oldi... 😴",
    "Savdogar": f"{tg_emoji('cart', '🛒', 'SHOP')} Savdogar bu tun dam oldi... 😴",

    # 🔴 Mafiya
    "Boshliq": f"{tg_emoji('don', '👑')} Boshliq bu tun dam oldi... 😴",
    "Qotil": f"{tg_emoji('mafia', '🔪')} Qotil bu tun dam oldi... 😴",
    "Soya": f"{tg_emoji('mafia', '🥷')} Soya bu tun dam oldi... 😴",
    "Soxtachi": f"{tg_emoji('item_doc', '🎭', 'SHOP')} Soxtachi bu tun dam oldi... 😴",
    "Maftunkor": f"{tg_emoji('detective', '💃')} Maftunkor bu tun dam oldi... 😴",
    "Bo‘ri": f"{tg_emoji('mafia', '🐺')} Bo‘ri bu tun dam oldi... 😴",
    "Bo'ri": f"{tg_emoji('mafia', '🐺')} Bo‘ri bu tun dam oldi... 😴",
    "Bori": f"{tg_emoji('mafia', '🐺')} Bo‘ri bu tun dam oldi... 😴",

    # 🟡 Yakkaxon
    "Maniak": f"{tg_emoji('mafia_win', '🩸')} Maniak bu tun dam oldi... 😴",
    "Pirotexnik": f"{tg_emoji('trigger', '🔥')} Pirotexnik bu tun dam oldi... 😴",
    "Qasoskor": f"{tg_emoji('item_knife', '⚔️', 'SHOP')} Qasoskor bu tun dam oldi... 😴",
    "Pul o‘g‘risi": f"{tg_emoji('coin', '💰', 'SHOP')} Pul o‘g‘risi bu tun dam oldi... 😴",
    "Pul o'g'risi": f"{tg_emoji('coin', '💰', 'SHOP')} Pul o‘g‘risi bu tun dam oldi... 😴",
    "Firibgar": f"{tg_emoji('detective', '🎪')} Firibgar bu tun dam oldi... 😴",
    "Buqalamun": f"{tg_emoji('detective', '🎪')} Firibgar bu tun dam oldi... 😴",
    "Joker": f"{tg_emoji('mafia_win', '🃏')} Joker bu tun dam oldi... 😴",
}

ROLE_ACTION_MESSAGES = {
    "kill": f"{tg_emoji('don', '👑')} Boshliq: Don o'z o'ljasini tanladi.",
    "killer_assist": f"{tg_emoji('mafia', '🔪')} Qotil nishon tomon yashirincha yurdi... 🔪",
    "detective": f"{tg_emoji('detective', '🕵️‍♂️')} Detektiv izquvarlikka ketdi... 🔎",
    "detective_shoot": f"{tg_emoji('detective', '💥')} Detektiv qurolini ishga soldi!",
    "sheriff_check": f"{tg_emoji('sheriff', '👮‍♂️')} Sherif gumondorning iziga tushdi... 🔎",
    "protect": f"{tg_emoji('doctor', '🩺')} Doktor bemor tomon shoshildi... 🩺",
    "guard": f"{tg_emoji('item_shield', '🛡️', 'SHOP')} Tansoqchi nishonini himoya qilish uchun yo‘lga chiqdi... 🛡️",
    "lawyer": f"{tg_emoji('voting', '⚖️')} Advokat mijozining uyiga yo‘l oldi... ⚖️",
    "tourist": "🚶 Sayyoh mehmonga borish uchun yo‘lga chiqdi... 🚶",
    "block": "💃 Maftunkor nishon tomon yo‘l oldi... 💃",
    "shadow": "🥷 Soya tun zulmatida izquvarlar ortidan ketdi... 🥷",
    "frame": f"{tg_emoji('item_doc', '🎭', 'SHOP')} Soxtachi qora dalilni joylashtirish uchun yo‘lga chiqdi... 🎭",
    "maniac_kill": "🩸 Maniak tun qorong‘usida ovga chiqdi... 🩸",
    "douse": "🔥 Qayerdadir kerosin hidi tarqalmoqda...",
    "ignite": "🔥 Pirotexnik butun shaharni olovga burkadi!",
    "coin_thief": f"{tg_emoji('coin', '💰', 'SHOP')} Pul o‘g‘risi boylik izlab tun qorong‘usiga chiqdi... 💰",
    "revenge": f"{tg_emoji('item_knife', '⚔️', 'SHOP')} Qasoskor dushmani izidan ketdi... ⚔️",
    "boy": f"{tg_emoji('coin', '💎', 'SHOP')} Boy yashirin kelishuv uchun yo‘lga chiqdi... 💎",
    "merchant": f"{tg_emoji('cart', '🛒', 'SHOP')} Savdogar maxfiy yukini yetkazish uchun yo‘lga chiqdi... 🛒",
    "medium": "🔮 Ruhshunos sirli izlar ortidan ketdi... 🔮",
    "firibgar": "🎪 Firibgar boshqa qiyofada ko‘chaga chiqdi... 🎭",
    "joker_laugh": "🃏 Shahar ko'chalarida telbaning qahqahasi yangradi...",
}

async def broadcast_role_action(
    context: ContextTypes.DEFAULT_TYPE,
    game: Dict[str, Any],
    actor: int,
    action: str
):
    """Send an atmospheric update to the group when a role takes night action."""
    chat_id = game.get("chat")
    if not chat_id:
        return

    night = game.get("night", 1)
    notified = game.setdefault("_notified_night_actions", set())
    act_key = f"{actor}_{action}_{night}"

    if act_key in notified:
        return

    notified.add(act_key)
    notified.add(f"{actor}_acted_{night}")

    # Determine message from role first, then action fallback
    role = game.get("roles", {}).get(actor)
    msg = None
    if role and role in ROLE_LIVE_MESSAGES:
        msg = ROLE_LIVE_MESSAGES[role]
    else:
        msg = ROLE_ACTION_MESSAGES.get(action)
        if not msg:
            msg = "⚡ <i>Shahar tunda yana bir sirli harakatga guvoh bo'ldi...</i>"

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="HTML"
        )
    except Exception as e:
        log.warning("Could not broadcast role action to chat %s: %s", chat_id, e)

async def broadcast_role_sleep(
    context: ContextTypes.DEFAULT_TYPE,
    game: Dict[str, Any],
    actor: int
):
    """Send an atmospheric update to the group when a role sleeps / skips."""
    chat_id = game.get("chat")
    if not chat_id:
        return

    night = game.get("night", 1)
    notified = game.setdefault("_notified_night_actions", set())
    act_key = f"{actor}_slept_{night}"
    acted_key = f"{actor}_acted_{night}"

    if act_key in notified or acted_key in notified:
        return

    notified.add(act_key)

    role = game.get("roles", {}).get(actor)
    msg = ROLE_SLEEP_MESSAGES.get(role) if role else None
    if not msg:
        msg = "Bu tun hech kimni tanlamadi — dam oldi... 😴"

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="HTML"
        )
    except Exception as e:
        log.warning("Could not broadcast role sleep to chat %s: %s", chat_id, e)
