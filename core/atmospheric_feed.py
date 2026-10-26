import logging
from typing import Dict, Any, Optional
from telegram.ext import ContextTypes

log = logging.getLogger("detektiv.core.atmospheric_feed")

# Group live messages matched to screenshot specifications
ROLE_LIVE_MESSAGES = {
    # 🔵 Shahar
    "Detektiv": "🕵️‍♂️ Detektiv izquvarlikka ketdi... 🔎",
    "Sherif": "👮‍♂️ Sherif gumondorning iziga tushdi... 🔎",
    "Doktor": "🩺 Doktor bemor tomon shoshildi... 🩺",
    "Tansoqchi": "🛡️ Tansoqchi nishonini himoya qilish uchun yo‘lga chiqdi... 🛡️",
    "Koldun": "🛡️ Tansoqchi nishonini himoya qilish uchun yo‘lga chiqdi... 🛡️",
    "Advokat": "⚖️ Advokat mijozining uyiga yo‘l oldi... ⚖️",
    "Sayyoh": "🚶 Sayyoh mehmonga borish uchun yo‘lga chiqdi... 🚶",
    "Ruhshunos": "🔮 Ruhshunos sirli izlar ortidan ketdi... 🔮",
    "Boy": "💎 Boy yashirin kelishuv uchun yo‘lga chiqdi... 💎",
    "Begona": "🕴️ Begona tun qorong‘usida nishon tomon yurdi... 🕴️",
    "Savdogar": "🛒 Savdogar maxfiy yukini yetkazish uchun yo‘lga chiqdi... 🛒",

    # 🔴 Mafiya
    "Boshliq": "👑 Boshliq maxfiy uchrashuvga yo‘l oldi... 👑",
    "Qotil": "🔪 Qotil nishon tomon yashirincha yurdi... 🔪",
    "Soya": "🥷 Soya tun zulmatida izquvarlar ortidan ketdi... 🥷",
    "Soxtachi": "🎭 Soxtachi qora dalilni joylashtirish uchun yo‘lga chiqdi... 🎭",
    "Maftunkor": "💃 Maftunkor nishon tomon yo‘l oldi... 💃",
    "Bo‘ri": "🐺 Bo‘ri tun qorong‘usida ovga chiqdi... 🐺",
    "Bo'ri": "🐺 Bo‘ri tun qorong‘usida ovga chiqdi... 🐺",
    "Bori": "🐺 Bo‘ri tun qorong‘usida ovga chiqdi... 🐺",

    # 🟡 Yakkaxon
    "Maniak": "🩸 Maniak tun qorong‘usida ovga chiqdi... 🩸",
    "Pirotexnik": "🔥 Pirotexnik nishonlarini belgilash uchun yo‘lga chiqdi... 🔥",
    "Qasoskor": "⚔️ Qasoskor dushmani izidan ketdi... ⚔️",
    "Pul o‘g‘risi": "💰 Pul o‘g‘risi boylik izlab tun qorong‘usiga chiqdi... 💰",
    "Pul o'g'risi": "💰 Pul o‘g‘risi boylik izlab tun qorong‘usiga chiqdi... 💰",
    "Firibgar": "🎪 Firibgar boshqa qiyofada ko‘chaga chiqdi... 🎭",
    "Buqalamun": "🎪 Firibgar boshqa qiyofada ko‘chaga chiqdi... 🎭",
    "Joker": "🃏 Shahar ko'chalarida telbaning qahqahasi yangradi...",
}

ROLE_SLEEP_MESSAGES = {
    # 🔵 Shahar
    "Detektiv": "🕵️‍♂️ Detektiv bu tun dam oldi... 😴",
    "Sherif": "👮‍♂️ Sherif bu tun dam oldi... 😴",
    "Doktor": "🩺 Doktor bu tun dam oldi... 😴",
    "Tansoqchi": "🛡️ Tansoqchi bu tun dam oldi... 😴",
    "Koldun": "🛡️ Tansoqchi bu tun dam oldi... 😴",
    "Advokat": "⚖️ Advokat bu tun dam oldi... 😴",
    "Sayyoh": "🚶 Sayyoh bu tun dam oldi... 😴",
    "Ruhshunos": "🔮 Ruhshunos bu tun dam oldi... 😴",
    "Boy": "💎 Boy bu tun dam oldi... 😴",
    "Begona": "🕴️ Begona bu tun dam oldi... 😴",
    "Savdogar": "🛒 Savdogar bu tun dam oldi... 😴",

    # 🔴 Mafiya
    "Boshliq": "👑 Boshliq bu tun dam oldi... 😴",
    "Qotil": "🔪 Qotil bu tun dam oldi... 😴",
    "Soya": "🥷 Soya bu tun dam oldi... 😴",
    "Soxtachi": "🎭 Soxtachi bu tun dam oldi... 😴",
    "Maftunkor": "💃 Maftunkor bu tun dam oldi... 😴",
    "Bo‘ri": "🐺 Bo‘ri bu tun dam oldi... 😴",
    "Bo'ri": "🐺 Bo‘ri bu tun dam oldi... 😴",
    "Bori": "🐺 Bo‘ri bu tun dam oldi... 😴",

    # 🟡 Yakkaxon
    "Maniak": "🩸 Maniak bu tun dam oldi... 😴",
    "Pirotexnik": "🔥 Pirotexnik bu tun dam oldi... 😴",
    "Qasoskor": "⚔️ Qasoskor bu tun dam oldi... 😴",
    "Pul o‘g‘risi": "💰 Pul o‘g‘risi bu tun dam oldi... 😴",
    "Pul o'g'risi": "💰 Pul o‘g‘risi bu tun dam oldi... 😴",
    "Firibgar": "🎪 Firibgar bu tun dam oldi... 😴",
    "Buqalamun": "🎪 Firibgar bu tun dam oldi... 😴",
    "Joker": "🃏 Joker bu tun dam oldi... 😴",
}

ROLE_ACTION_MESSAGES = {
    "kill": "👑 Boshliq: Don o'z o'ljasini tanladi.",
    "killer_assist": "🔪 Qotil nishon tomon yashirincha yurdi... 🔪",
    "detective": "🕵️‍♂️ Detektiv izquvarlikka ketdi... 🔎",
    "detective_shoot": "💥 Detektiv qurolini ishga soldi!",
    "sheriff_check": "👮‍♂️ Sherif gumondorning iziga tushdi... 🔎",
    "protect": "🩺 Doktor bemor tomon shoshildi... 🩺",
    "guard": "🛡️ Tansoqchi nishonini himoya qilish uchun yo‘lga chiqdi... 🛡️",
    "lawyer": "⚖️ Advokat mijozining uyiga yo‘l oldi... ⚖️",
    "tourist": "🚶 Sayyoh mehmonga borish uchun yo‘lga chiqdi... 🚶",
    "block": "💃 Maftunkor nishon tomon yo‘l oldi... 💃",
    "shadow": "🥷 Soya tun zulmatida izquvarlar ortidan ketdi... 🥷",
    "frame": "🎭 Soxtachi qora dalilni joylashtirish uchun yo‘lga chiqdi... 🎭",
    "maniac_kill": "🩸 Maniak tun qorong‘usida ovga chiqdi... 🩸",
    "douse": "🔥 Qayerdadir kerosin hidi tarqalmoqda...",
    "ignite": "🔥 Pirotexnik butun shaharni olovga burkadi!",
    "coin_thief": "💰 Pul o‘g‘risi boylik izlab tun qorong‘usiga chiqdi... 💰",
    "revenge": "⚔️ Qasoskor dushmani izidan ketdi... ⚔️",
    "boy": "💎 Boy yashirin kelishuv uchun yo‘lga chiqdi... 💎",
    "merchant": "🛒 Savdogar maxfiy yukini yetkazish uchun yo‘lga chiqdi... 🛒",
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
