import logging
from typing import Dict, Any, Optional
from telegram.ext import ContextTypes

log = logging.getLogger("detektiv.core.atmospheric_feed")

# Group live messages matched to screenshot specifications
ROLE_LIVE_MESSAGES = {
    "Boshliq": "🤵🏻 Don o'z o'ljasini tanladi.",
    "Qotil": "🤵🏻 Mafia buyruqni qabul qildi.",
    "Doktor": "👨🏼‍⚕ Doktor bemorni davolashga shoshilmoqda.",
    "Detektiv": "🕵🏻 Detektiv izquvarlikni boshladi.",
    "Sherif": "👮🏻 Sherif kuzatuvni boshladi.",
    "Sayyoh": "🧙🏻 Daydi kimnikigadir mehmonga bordi.",
    "Firibgar": "🦎 Buqalamun yangi qiyofaga kirdi.",
    "Buqalamun": "🦎 Buqalamun yangi qiyofaga kirdi.",
    "Tansoqchi": "⚡ Koldun bugun kimnidir osishdan saqlab qoladi!",
    "Koldun": "⚡ Koldun bugun kimnidir osishdan saqlab qoladi!",
    "Maniak": "🩸 Maniak o'z nishonini tanladi.",
    "Pirotexnik": "🔥 Qayerdadir kerosin hidi tarqalmoqda...",
    "Joker": "🃏 Shahar ko'chalarida telbaning qahqahasi yangradi...",
    "Advokat": "⚖️ Advokat o'z mijozi uchun maxfiy himoya tayyorladi.",
    "Soya": "🥷 Soya tun pardasi ortidan kimnidir pinhona kuzatmoqda...",
    "Soxtachi": "🎭 Soxtachi qabih soxta dalil tashlab ketdi...",
    "Maftunkor": "💃 Maftunkor kimnidir sehrlab, harakatini muzlatmoqda...",
    "Begona": "🕴️ Begona kimningdir harakatini blokladi.",
    "Ruhshunos": "🔮 Ruhshunos narigi dunyo bilan bog'lanmoqda...",
    "Qasoskor": "⚔️ Qasoskor o'z qasos nishonini belgiladi.",
    "Pul o'g'risi": "💰 Pul o'g'risi chaqqonlik bilan cho'ntakka qo'l soldi...",
    "Boy": "💎 Boy o'z boyligini ishga solib harakat qildi.",
    "Savdogar": "🛒 Savdogar tunda maxfiy savdo bitimini tuzdi.",
}

ROLE_ACTION_MESSAGES = {
    "kill": "🤵🏻 Don o'z o'ljasini tanladi.",
    "killer_assist": "🤵🏻 Mafia buyruqni qabul qildi.",
    "detective": "🕵🏻 Detektiv izquvarlikni boshladi.",
    "detective_shoot": "💥 Detektiv qurolini ishga soldi!",
    "sheriff_check": "👮🏻 Sherif shubhali shaxsni tekshirmoqda.",
    "protect": "👨🏼‍⚕ Doktor bemorni davolashga shoshilmoqda.",
    "guard": "⚡ Koldun bugun kimnidir osishdan saqlab qoladi!",
    "lawyer": "⚖️ Advokat o'z mijozini himoyaga oldi.",
    "tourist": "🧙🏻 Daydi kimnikigadir mehmonga bordi.",
    "block": "💃 Maftunkor kimnidir sehrlab qo'ydi.",
    "shadow": "🥷 Soya kimnidir pinhona kuzatmoqda.",
    "frame": "🎭 Soxtachi tuhmat qopqonini qo'ydi.",
    "maniac_kill": "🩸 Maniak o'z nishonini tanladi.",
    "douse": "🔥 Qayerdadir kerosin hidi tarqalmoqda...",
    "ignite": "🔥 Pirotexnik butun shaharni olovga burkadi!",
    "coin_thief": "💰 O'g'ri kimningdir cho'ntagiga qo'l soldi.",
    "revenge": "⚔️ Qasoskor qasos o'tida yonib, o'z qasos nishonini belgiladi...",
    "boy": "💎 Boy o'z boyligini ishga solib, kimningdir qobiliyatini ijaraga oldi!",
    "merchant": "🛒 Savdogar tunda maxfiy xaridor bilan savdo bitimini tuzdi...",
    "medium": "🔮 Ruhshunos qabriston uzra marhumlar ruhi bilan sirli muloqot o'tkazmoqda...",
    "firibgar": "🦎 Buqalamun yangi qiyofaga kirdi.",
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
