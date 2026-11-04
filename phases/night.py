import asyncio
import random
import logging
import html
from typing import Dict, Any, List, Optional, Set
from telegram.error import TelegramError
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import (
    DEFAULT_NIGHT_SECONDS, DEFAULT_KING_TIMEOUT_SECONDS, NIGHT_ACTIVE_ROLES, NIGHT_PHOTO_PATH, ROLES, ROLE_ORDER
)
from database.models import (
    get_user, change_balance, get_inventory, take_item
)
from core.engine import (
    display_name, save_runtime, check_winner, finish_game, cancel_game_timer
)
from core.clues import generate_forensic_clue
from core.weather import roll_weather
from core.will import fetch_player_will
from core.audio_effects import send_atmospheric_message
from core.navigation import bot_action_keyboard, return_to_group_keyboard, get_bot_deep_link
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.phases.night")


def get_role_action_buttons(game: Dict[str, Any], uid: int) -> Optional[InlineKeyboardMarkup]:
    role = game.get("roles", {}).get(uid)
    if not role or not game.get("alive", {}).get(uid, False):
        return None

    # Boy borrowed role check
    if role == "Boy":
        stolen = game.get("boy_stolen_roles", {}).get(uid)
        if stolen and stolen.get("accepted") and stolen.get("night") == game.get("night", 1):
            role = stolen.get("role", role)

    buttons = []
    if role == "Detektiv":
        buttons.append([
            InlineKeyboardButton("🔎 Shaxsni tekshirish", callback_data=f"act:detective:{uid}"),
            InlineKeyboardButton("🔫 Shubhali shaxsni otish", callback_data=f"act:detective_shoot:{uid}")
        ])
    elif role == "Sherif":
        det_alive = any(
            game["alive"].get(u, False) and game["roles"].get(u) == "Detektiv"
            for u in game.get("players", [])
        )
        if (uid in game.get("sheriff_promoted", set())) or (not det_alive):
            buttons.append([
                InlineKeyboardButton("🔎 Shaxsni tekshirish", callback_data=f"act:detective:{uid}"),
                InlineKeyboardButton("🔫 Shubhali shaxsni otish", callback_data=f"act:detective_shoot:{uid}")
            ])
        # Note: While Detektiv is alive, Sherif has NO active abilities
    elif role in ("Bo'ri", "Bori"):
        boss_alive = any(
            game["alive"].get(u, False) and game["roles"].get(u) == "Boshliq"
            for u in game.get("players", [])
        )
        killer_alive = any(
            game["alive"].get(u, False) and game["roles"].get(u) == "Qotil"
            for u in game.get("players", [])
        )
        if not boss_alive and not killer_alive:
            buttons.append([
                InlineKeyboardButton("🐺 Ovga chiqish (Boshliqsiz)", callback_data=f"act:kill:{uid}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("🐺 Boshliq bilan ovga chiqish", callback_data=f"act:killer_assist:{uid}")
            ])
    elif role == "Doktor":
        buttons.append([
            InlineKeyboardButton("🩺 Bir kishini davolash / himoya", callback_data=f"act:protect:{uid}")
        ])
    elif role == "Tansoqchi":
        buttons.append([
            InlineKeyboardButton("🛡️ Jon fido qilib himoyalash", callback_data=f"act:guard:{uid}")
        ])
    elif role == "Advokat":
        buttons.append([
            InlineKeyboardButton("⚖️ Himoyaga mijoz tanlash", callback_data=f"act:lawyer:{uid}")
        ])
    elif role == "Sayyoh":
        buttons.append([
            InlineKeyboardButton("🚶 Mehmonga borish", callback_data=f"act:tourist:{uid}")
        ])
    elif role == "Ruhshunos":
        buttons.append([
            InlineKeyboardButton("🔮 Ruhlar olami bilan bog'lanish", callback_data=f"act:medium:{uid}")
        ])
    elif role == "Boshliq":
        buttons.append([
            InlineKeyboardButton("👑 Qotillik nishonini tanlash", callback_data=f"act:kill:{uid}")
        ])
    elif role == "Qotil":
        boss_alive = any(
            game["alive"].get(u, False) and game["roles"].get(u) == "Boshliq"
            for u in game.get("players", [])
        )
        if not boss_alive:
            buttons.append([
                InlineKeyboardButton("🔪 Qotillik nishonini tanlash (Boshliqsiz)", callback_data=f"act:kill:{uid}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("🔪 Boshliq buyrug'ini kutish", callback_data=f"act:killer_assist:{uid}")
            ])
    elif role == "Soya":
        buttons.append([
            InlineKeyboardButton("🥷 Chalg'itish / Kuzatuv", callback_data=f"act:shadow:{uid}")
        ])
    elif role == "Soxtachi":
        buttons.append([
            InlineKeyboardButton("🎭 Soxta dalil tashlash (Frame)", callback_data=f"act:frame:{uid}")
        ])
    elif role in ("Maftunkor", "Begona"):
        buttons.append([
            InlineKeyboardButton("🕴️ Harakatni bloklash", callback_data=f"act:block:{uid}")
        ])
    elif role == "Maniak":
        buttons.append([
            InlineKeyboardButton("🩸 Shafqatsiz qotillik", callback_data=f"act:maniac_kill:{uid}")
        ])
    elif role == "Pirotexnik":
        buttons.append([
            InlineKeyboardButton("⛽ Kerosin quyish", callback_data=f"act:douse:{uid}"),
            InlineKeyboardButton("🔥 BARCHASINI YOQISH!", callback_data=f"act:ignite:{uid}")
        ])
    elif role == "Qasoskor":
        buttons.append([
            InlineKeyboardButton("⚔️ Qasos nishonini belgilash", callback_data=f"act:revenge:{uid}")
        ])
    elif role == "Pul o'g'risi":
        buttons.append([
            InlineKeyboardButton("💰 Tangalarni o'g'irlash", callback_data=f"act:coin_thief:{uid}")
        ])
    elif role == "Boy":
        buttons.append([
            InlineKeyboardButton("💎 Qobiliyat sotib olish", callback_data=f"act:boy:{uid}")
        ])
    elif role == "Savdogar":
        buttons.append([
            InlineKeyboardButton("🛒 Buyum sotish", callback_data=f"act:merchant:{uid}")
        ])
    elif role == "Firibgar":
        buttons.append([
            InlineKeyboardButton("🎪 Soxta qiyofa tanlash", callback_data=f"act:firibgar:{uid}")
        ])
    elif role == "Joker":
        buttons.append([
            InlineKeyboardButton("🃏 Telba qahqahasini yangratish", callback_data=f"act:joker_laugh:{uid}")
        ])

    from core.navigation import return_to_group_button
    buttons.append([
        InlineKeyboardButton("😴 Bu tun dam olish", callback_data=f"act:sleep:{uid}"),
        InlineKeyboardButton("📜 Vasiyatnoma yozish (/will)", callback_data=f"act:will_help:{uid}")
    ])
    buttons.append([
        return_to_group_button(game)
    ])
    return InlineKeyboardMarkup(buttons)

def get_target_selection_keyboard(game: Dict[str, Any], actor: int, action: str) -> InlineKeyboardMarkup:
    from core.navigation import return_to_group_button
    alive_players = [
        u for u in game.get("players", [])
        if game.get("alive", {}).get(u, False)
    ]
    role = game.get("roles", {}).get(actor)
    rows = []

    for target in alive_players:
        # Rules on self-target: Doctor self-heal and Bodyguard self-protect strictly max 1 time per game
        if target == actor:
            if action in ("protect", "guard"):
                if actor in game.get("self_protect_used", set()) or game.get("doctor_self_heal_used", {}).get(actor, False):
                    continue
            elif action != "will_help":
                continue
        # Mafia members cannot kill teammates
        if action == "kill" and ROLES.get(game["roles"].get(target)) == "red":
            continue

        name = display_name(game, target)
        rows.append([
            InlineKeyboardButton(f"👤 {name}", callback_data=f"tgt:{action}:{actor}:{target}")
        ])

    rows.append([
        InlineKeyboardButton("😴 Dam olish (Hech kimni tanlamaslik)", callback_data=f"act:sleep:{actor}")
    ])
    rows.append([
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_action"),
        return_to_group_button(game)
    ])
    return InlineKeyboardMarkup(rows)

async def start_night(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    chat_id = game["chat"]
    night_num = game.get("night", 1)
    game["phase"] = "night"
    game["_resolving_night"] = False
    game["_waiting_king"] = False

    # Roll weather
    weather = roll_weather()
    game["weather"] = weather

    # Reset night action stores
    game["night_done"] = set()
    game["kill_targets"] = {}
    game["protected"] = set()
    game["protected_by"] = {}
    game["guarded_by"] = {}
    game["lawyer_clients"] = {}
    game["blocked_roles"] = {}
    game["tourist_targets"] = {}
    game["shadow_targets"] = {}
    game["framer_targets"] = {}
    game["maniac_targets"] = {}
    game["arsonist_action"] = {}
    game["coin_thief_targets"] = {}
    game["detective_results"] = {}
    game["firibgar_disguises"] = {}

    await save_runtime(game)

    alive_uids = [u for u in game.get("players", []) if game.get("alive", {}).get(u, False)]
    player_lines = [f"{i}. {display_name(game, uid)}" for i, uid in enumerate(alive_uids, 1)]

    from roles.base import format_role_display
    blue_roles = []
    red_roles = []
    solo_roles = []

    for uid in alive_uids:
        r = game.get("roles", {}).get(uid, "Fuqaro")
        team = ROLES.get(r, "blue")
        r_display = format_role_display(r)
        if team == "blue":
            blue_roles.append(r_display)
        elif team == "red":
            red_roles.append(r_display)
        else:
            solo_roles.append(r_display)

    announcement_lines = [
        f"{tg_emoji('night', '🌙')} <b>Tun #{night_num}</b>",
        "",
        "<b>Tirik o'yinchilar:</b>",
        *player_lines,
        "",
        f"{tg_emoji('civilian_team', '👥')} <b>Tinchlar - {len(blue_roles)}:</b>",
        ", ".join(blue_roles),
        "",
        f"{tg_emoji('mafia_team', '🔪')} <b>Mafiyalar - {len(red_roles)}:</b>",
        ", ".join(red_roles),
    ]
    if solo_roles:
        announcement_lines.extend([
            "",
            f"<b>Yakkalar - {len(solo_roles)}:</b>",
            ", ".join(solo_roles),
        ])
    night_seconds = int(game.get("settings", {}).get("night_seconds", DEFAULT_NIGHT_SECONDS))
    announcement_lines.extend([
        "",
        f"<b>Jami: {len(alive_uids)} ta</b>",
        "",
        f"Tonggacha {tg_emoji('timer', '⏳')} <b>{night_seconds} sekund</b> qoldi"
    ])

    night_announcement = "\n".join(announcement_lines)
    night_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Botga o'tish ↗", url=get_bot_deep_link(chat_id, "act"))]
    ])

    await send_atmospheric_message(
        bot=context.bot,
        chat_id=chat_id,
        text=night_announcement,
        sound_type="night",
        photo_path=NIGHT_PHOTO_PATH,
        reply_markup=night_kb,
        parse_mode="HTML"
    )

    # Deliver action menus to players in PM
    for uid in game.get("players", []):
        if not game["alive"].get(uid, False):
            continue
        role = game["roles"].get(uid)
        det_alive = any(
            game["alive"].get(u, False) and game["roles"].get(u) == "Detektiv"
            for u in game.get("players", [])
        )
        if role == "Sherif" and det_alive and uid not in game.get("sheriff_promoted", set()):
            pm_prompt = (
                f"{tg_emoji('night', '🌙')} <b>Tun #{night_num} amallari</b>\n"
                f"🎭 Sizning rolingiz: <b>Sherif</b>\n\n"
                f"{tg_emoji('sheriff', '👮‍♂️')} <b>Detektiv hozirda tirik!</b> Shahar xavfsizligini Detektiv ta'minlamoqda.\n"
                "Siz uning o'rnini faqat Detektiv halok bo'lgandagina egallaysiz.\n"
                "Quyidagi tugmalardan birini tanlang:"
            )
        else:
            pm_prompt = (
                f"{tg_emoji('night', '🌙')} <b>Tun #{night_num} amallari</b>\n"
                f"🎭 Sizning rolingiz: <b>{role}</b>\n"
                "Quyidagi tugmalardan birini tanlang:"
            )
        kb = get_role_action_buttons(game, uid)
        if kb:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=pm_prompt,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

    # Start timer
    cancel_game_timer(game)
    game["_timer_task"] = asyncio.create_task(_night_timer(context, chat_id, night_num, night_seconds))

async def _night_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, night_num: int, seconds: int):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    from core.engine import games
    game = games.get(chat_id)
    if game and game.get("phase") == "night" and game.get("night") == night_num and not game.get("_finish_started"):
        await resolve_night(context, game)

async def resolve_night(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    """Execute all night actions according to strict priority chain."""
    if game.get("phase") != "night" or game.get("_finish_started"):
        return
    if game.get("_waiting_king") or game.get("_resolving_night"):
        return
    game["_resolving_night"] = True
    cancel_game_timer(game)

    deaths: Set[int] = set()
    death_causes: Dict[int, List[str]] = {}
    crime_clues: Dict[int, Dict[str, str]] = {}
    saved_by_doc: Set[int] = set()

    # 0. Broadcast sleep message for active roles who took no action
    from core.atmospheric_feed import broadcast_role_sleep
    for uid in game.get("players", []):
        if not game["alive"].get(uid, False):
            continue
        role = game.get("roles", {}).get(uid)
        if role in NIGHT_ACTIVE_ROLES and uid not in game.get("night_done", set()):
            det_alive = any(
                game["alive"].get(u, False) and game["roles"].get(u) == "Detektiv"
                for u in game.get("players", [])
            )
            if role == "Sherif" and det_alive and uid not in game.get("sheriff_promoted", set()):
                continue
            await broadcast_role_sleep(context, game, uid)

    # 1. PRIORITY 1: ROLEBLOCKS (Begona, Maftunkor)
    blocked = game.get("blocked_roles", {})
    for target in list(blocked.keys()):
        if not game["alive"].get(target, False):
            continue
        # Cancel actions of target
        game.get("kill_targets", {}).pop(target, None)
        game.get("maniac_targets", {}).pop(target, None)
        game.get("detective_results", {}).pop(str(target), None)
        game.get("detective_results", {}).pop(target, None)
        # Cancel Doctor heal on patient
        for p, doc in list(game.get("protected_by", {}).items()):
            if doc == target:
                game.get("protected", set()).discard(p)
                game.get("protected_by", {}).pop(p, None)
        # Cancel Bodyguard guard on ward
        for w, g in list(game.get("guarded_by", {}).items()):
            if g == target:
                game.get("guarded_by", {}).pop(w, None)
        game.get("tourist_targets", {}).pop(target, None)
        game.get("shadow_targets", {}).pop(target, None)
        game.get("framer_targets", {}).pop(target, None)
        game.get("lawyer_clients", {}).pop(target, None)
        game.get("revenge_targets", {}).pop(target, None)
        game.get("boy_stolen_roles", {}).pop(target, None)
        game.get("coin_thief_targets", {}).pop(target, None)
        if game.get("arsonist_action", {}).get("ignite") == target:
            game.get("arsonist_action", {}).pop("ignite", None)

        try:
            await context.bot.send_message(
                chat_id=target,
                text="🕴️ *SIZ BLOKLANDINGIZ!*\nBu kecha harakatingiz muzlatildi va qobiliyatingiz ishlamadi."
            )
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)

    # 2. PRIORITY 2: THEFT (Pul o'g'risi)
    for thief, victim in list(game.get("coin_thief_targets", {}).items()):
        if game["alive"].get(thief, False) and game["alive"].get(victim, False):
            u = await get_user(victim)
            available = int(u.get("coin", 0)) if u else 0
            stolen = min(50, max(0, available))
            if stolen > 0:
                await change_balance(victim, "coin", -stolen, "Pul o'g'risi o'g'irladi")
                await change_balance(thief, "coin", stolen, "Pul o'g'risi o'ljasi")
                try:
                    await context.bot.send_message(
                        chat_id=thief,
                        text=f"💰 *O'g'rilik muvaffaqiyatli!* Siz *{display_name(game, victim)}*dan {stolen} Coin o'g'irladingiz."
                    )
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)

    # 3. PRIORITY 3: ATTACKS (Mafia, Maniak, Detektiv Shoot, Pirotexnik)
    attacks: List[Dict[str, Any]] = []
    king_attacks: List[Dict[str, Any]] = []

    # Attacks (Mafia Kill, Detective / Sheriff Shoot)
    for boss, tgt in list(game.get("kill_targets", {}).items()):
        if game["alive"].get(boss, False) and game["alive"].get(tgt, False):
            actor_role = game.get("roles", {}).get(boss, "Boshliq")
            if actor_role in ("Detektiv", "Sherif"):
                attacks.append({
                    "attacker": boss,
                    "target": tgt,
                    "role": actor_role,
                    "cause": f"{actor_role} qurolidan otildi"
                })
            else:
                attacks.append({
                    "attacker": boss,
                    "target": tgt,
                    "role": "Boshliq",
                    "cause": "Mafiya buyrug'i"
                })

    # Maniak Kill
    for maniac, tgt in list(game.get("maniac_targets", {}).items()):
        if game["alive"].get(maniac, False) and game["alive"].get(tgt, False):
            attacks.append({"attacker": maniac, "target": tgt, "role": "Maniak", "cause": "Maniak hujumi"})

    # Arsonist Ignite
    arsonist_ignite = game.get("arsonist_action", {}).get("ignite")
    if arsonist_ignite:
        for doused_uid in list(game.get("arsonist_doused", set())):
            if game["alive"].get(doused_uid, False):
                attacks.append({
                    "attacker": arsonist_ignite,
                    "target": doused_uid,
                    "role": "Pirotexnik",
                    "cause": "Pirotexnik alangasida yonish"
                })

    # Process Attacks
    for atk in attacks:
        attacker = atk["attacker"]
        target = atk["target"]
        atk_role = atk["role"]
        cause = atk["cause"]

        if not game["alive"].get(target, False):
            continue

        tgt_role = game["roles"].get(target)

        # Werewolf (Bori / Bo'ri) special check: survives and recruits partner
        if tgt_role in ("Bori", "Bo'ri") and atk_role in ("Boshliq", "Qotil"):
            try:
                await context.bot.send_message(
                    chat_id=target,
                    text="🐺 *BO'RI!*\nSizga tunda hujum qilindi, ammo siz tirik qoldingiz! Hujumchi endi sizning yashirin ittifoqdoshingiz."
                )
                await context.bot.send_message(
                    chat_id=attacker,
                    text="🌑 *G'alati tun:* Bo'ri o'lmadi va sizga zarar yetkazmadi."
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            continue

        # Maniak 1st night attack immunity check
        if tgt_role == "Maniak" and not game.get("maniac_immunity_used", {}).get(target, False):
            game.setdefault("maniac_immunity_used", {})[target] = True
            try:
                await context.bot.send_message(
                    chat_id=target,
                    text="🩸 *MANIAK IMMUNITETI!* Tunda sizga suiqasd qilindi, ammo siz omon qoldingiz (1 martalik immunitet sarflandi)!"
                )
                await context.bot.send_message(
                    chat_id=attacker,
                    text="🌑 *G'alati holat:* Qurboningiz o'lmadi, u shafqatsiz qarshilik ko'rsatib tirik qoldi!"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            continue

        # King (Qirol) check - King intercepts attack and does not die
        if tgt_role == "Qirol":
            king_attacks.append({
                "king_uid": target,
                "attacker_uid": attacker,
                "atk_role": atk_role
            })
            continue

        # Bodyguard (Tansoqchi) protection duel check
        guard_uid = game.get("guarded_by", {}).get(target)
        if guard_uid and game["alive"].get(guard_uid, False):
            if guard_uid == target:
                # Bodyguard self-protect: target survives
                try:
                    await context.bot.send_message(
                        chat_id=target,
                        text="🛡️ *O'ZINGIZNI HIMOYA QILDINGIZ!* Sizga qilingan tungi hujumni qaytardingiz va omon qoldingiz."
                    )
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)
                continue
            else:
                # Target is saved, Guard and Attacker duel to death
                deaths.add(guard_uid)
                deaths.add(attacker)
                death_causes.setdefault(guard_uid, []).append("Tansoqchi mudofaasida qahramonlarcha halok bo'ldi")
                death_causes.setdefault(attacker, []).append("Tansoqchining qarshi zarbasidan yiqildi")
                try:
                    await context.bot.send_message(
                        chat_id=target,
                        text="🛡️ *Tansoqchi sizni qutqardi!* U o'z joni evaziga qotilni yo'q qildi."
                    )
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)
                continue

        # Doctor Protection check
        if target in game.get("protected", set()):
            saved_by_doc.add(target)
            doc_uid = game.get("protected_by", {}).get(target)
            if doc_uid:
                try:
                    await context.bot.send_message(
                        chat_id=doc_uid,
                        text=f"{tg_emoji('doctor_save', '🩺')} <b>HIMOYA ISHLADI!</b> Siz <b>{display_name(game, target)}</b>ni o'limdan asrab qoldingiz.",
                        parse_mode="HTML"
                    )
                    await context.bot.send_message(
                        chat_id=target,
                        text=f"{tg_emoji('doctor_save', '🩺')} <b>DOKTOR SIZNI DAVOLADI!</b> Tunda sizga suiqasd qilingan edi, ammo shifokor sizni qutqarib qoldi.",
                        parse_mode="HTML"
                    )
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)
            continue

        # Avenger (Qasoskor) counter-strike check
        if tgt_role == "Qasoskor":
            deaths.add(target)
            death_causes.setdefault(target, []).append(cause)
            if game["alive"].get(attacker, False):
                deaths.add(attacker)
                death_causes.setdefault(attacker, []).append("Qasoskorning halokatli javob zarbasi")
            rev_target = game.get("revenge_targets", {}).get(target)
            if rev_target and game["alive"].get(rev_target, False) and rev_target != target and rev_target != attacker:
                deaths.add(rev_target)
                death_causes.setdefault(rev_target, []).append("Qasoskorning qasos nishoni bo'lgani sababli halok bo'ldi")
            continue

        # Target dies
        deaths.add(target)
        death_causes.setdefault(target, []).append(cause)
        crime_clues[target] = generate_forensic_clue(atk_role, display_name(game, target))

    # If King was attacked, pause resolution for King's verdict
    if king_attacks:
        primary_king_atk = king_attacks[0]
        k_target = primary_king_atk["king_uid"]
        k_attacker = primary_king_atk["attacker_uid"]
        k_atk_role = primary_king_atk["atk_role"]

        game["_waiting_king"] = True
        game["king_attacker"] = k_attacker
        game.get("kill_targets", {}).pop(k_attacker, None)

        game["_pending_night_resolution"] = {
            "deaths": list(deaths),
            "death_causes": {k: list(v) for k, v in death_causes.items()},
            "crime_clues": dict(crime_clues),
            "saved_by_doc": list(saved_by_doc),
            "attacks": attacks,
        }
        game["_resolving_night"] = False

        # Cancel any previous king timer task
        prev_king_task = game.pop("_king_timer_task", None)
        if prev_king_task and not prev_king_task.done():
            prev_king_task.cancel()

        msg_sent = False
        from core.navigation import return_to_group_button
        king_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ Qatl etish", callback_data=f"king_kill:{k_target}:{k_attacker}")],
            [InlineKeyboardButton("🕊️ Avf etish", callback_data=f"king_forgive:{k_target}:{k_attacker}")],
            [return_to_group_button(game)]
        ])
        king_text = (
            f"{tg_emoji('boss', '👑')} <b>QIROLGA HUJUM BO'LDI!</b>\n\n"
            f"👤 Hujumchi: <b>{html.escape(display_name(game, k_attacker))}</b>\n"
            f"🎭 Roli: <b>{k_atk_role}</b>\n\n"
            f"{tg_emoji('voting', '⚖️')} Qatl qilish yoki avf etishni tanlang ({DEFAULT_KING_TIMEOUT_SECONDS} soniya):"
        )
        try:
            await context.bot.send_message(
                chat_id=k_target,
                text=king_text,
                reply_markup=king_kb,
                parse_mode="HTML"
            )
            msg_sent = True
        except Exception as e:
            log.warning("Could not send King prompt to user %s with HTML (%s), retrying plain text", k_target, e)
            try:
                await context.bot.send_message(
                    chat_id=k_target,
                    text=king_text.replace("<b>", "").replace("</b>", ""),
                    reply_markup=king_kb,
                    parse_mode=None
                )
                msg_sent = True
            except Exception as e2:
                log.warning("Could not send King prompt to user %s: %s", k_target, e2)
                msg_sent = False

        if not msg_sent:
            # Bot blocked in PM or network error - auto-forgive immediately so game never stalls
            await handle_king_decision(
                context=context,
                game=game,
                king_uid=k_target,
                attacker_uid=k_attacker,
                is_kill=False,
                is_timeout=True
            )
            return

        timeout_sec = float(game.get("king_timeout_seconds", DEFAULT_KING_TIMEOUT_SECONDS))
        game["_king_timer_task"] = asyncio.create_task(
            _king_timeout(context, game["chat"], k_target, k_attacker, timeout_sec)
        )
        await save_runtime(game)
        return

    await complete_night_resolution(context, game, deaths, death_causes, crime_clues, saved_by_doc, attacks)

async def complete_night_resolution(
    context: ContextTypes.DEFAULT_TYPE,
    game: Dict[str, Any],
    deaths: Set[int],
    death_causes: Dict[int, List[str]],
    crime_clues: Dict[int, Dict[str, str]],
    saved_by_doc: Set[int],
    attacks: Optional[List[Dict[str, Any]]] = None
):
    """Finalize deaths, deliver clue reports, process investigations, and transition to Day."""
    if attacks is None:
        attacks = []

    # 4. SHOP PROTECTION (Inventory item - Strictly 1 use per game per player)
    from core.items import has_used_item, mark_item_used, is_item_armed, disarm_item
    for uid in list(deaths):
        saved = False
        if is_item_armed(game, uid, "protection"):
            disarm_item(game, uid, "protection")
            saved = True
        elif not has_used_item(game, uid, "protection"):
            if await take_item(uid, "protection", 1):
                mark_item_used(game, uid, "protection")
                saved = True
        else:
            inv = await get_inventory(uid)
            if inv.get("protection", 0) > 0:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text="⚠️ Siz ushbu o'yinda bu buyumdan (Tungi himoya) allaqachon foydalangansiz! Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                        reply_markup=return_to_group_keyboard(game),
                        parse_mode="HTML"
                    )
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)

        if saved:
            deaths.discard(uid)
            crime_clues.pop(uid, None)
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"{tg_emoji('item_shield', '🛡️', 'SHOP')} <b>SHOP HIMOYASI ISHLADI!</b> Sizga qilingan tungi hujum qaytarildi (1 ta himoya sarflandi).\n⚠️ <b>Eslatma:</b> Ushbu buyumdan har bir o'yinda faqat 1 marta foydalanish mumkin.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

    # 4.1. SHOP REVENGE KNIFE (Inventory item - Strictly 1 use per game per player)
    for victim_uid in list(deaths):
        victim_attackers = [
            atk["attacker"] for atk in attacks
            if atk.get("target") == victim_uid and atk.get("attacker") != victim_uid and game["alive"].get(atk.get("attacker"), False)
        ]
        if not victim_attackers:
            continue
        target_attacker = victim_attackers[0]

        knife_used = False
        if is_item_armed(game, victim_uid, "revenge_knife"):
            disarm_item(game, victim_uid, "revenge_knife")
            knife_used = True
        elif not has_used_item(game, victim_uid, "revenge_knife"):
            if await take_item(victim_uid, "revenge_knife", 1):
                mark_item_used(game, victim_uid, "revenge_knife")
                knife_used = True
        else:
            inv = await get_inventory(victim_uid)
            if inv.get("revenge_knife", 0) > 0:
                try:
                    await context.bot.send_message(
                        chat_id=victim_uid,
                        text="⚠️ Siz ushbu o'yinda bu buyumdan (Qasos pichog'i) allaqachon foydalangansiz! Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                        reply_markup=return_to_group_keyboard(game),
                        parse_mode="HTML"
                    )
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)

        if knife_used:
            deaths.add(target_attacker)
            death_causes.setdefault(target_attacker, []).append("Qurbonning qasos pichog'i zarbasi tufayli halok bo'ldi")
            try:
                await context.bot.send_message(
                    chat_id=victim_uid,
                    text=f"{tg_emoji('item_knife', '🔪', 'SHOP')} <b>QASOS PICHOG'I ISHLADI!</b> Siz o'limingiz oldidan hujumchi ustidan qasos oldingiz (1 ta pichoq sarflandi).\n⚠️ <b>Eslatma:</b> Har bir o'yinda faqat 1 marta foydalanish mumkin.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

    # 5. WITNESS (Sayyoh / Tourist)
    for tourist_uid, visited_uid in game.get("tourist_targets", {}).items():
        if game["alive"].get(tourist_uid, False):
            attackers_here = [
                atk for atk in attacks
                if atk["target"] == visited_uid and atk["attacker"] != tourist_uid
            ]
            if attackers_here:
                killer_name = display_name(game, attackers_here[0]["attacker"])
                killer_role = attackers_here[0]["role"]
                try:
                    await context.bot.send_message(
                        chat_id=tourist_uid,
                        text=(
                            f"🚶 <b>SAYYOH TASHRIFI GUVOXLIGI</b>\n\n"
                            f"Siz <b>{html.escape(display_name(game, visited_uid))}</b>ning uyida edingiz.\n"
                            f"Ko'zingiz oldida <b>{html.escape(killer_name)}</b> ({killer_role}) hujum qildi!"
                        ),
                        reply_markup=return_to_group_keyboard(game),
                        parse_mode="HTML"
                    )
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)

    # 6. INVESTIGATIONS (Detektiv & Sherif)
    for det_uid, info in game.get("detective_results", {}).items():
        try:
            det_id = int(det_uid)
        except Exception:
            continue
        if not game["alive"].get(det_id, False) or det_id in deaths:
            continue
        tgt = info["target"]
        real_role = game["roles"].get(tgt, "Fuqaro")
        tgt_name = display_name(game, tgt)

        # Weather Fog interference (25% chance)
        if game.get("weather", {}).get("id") == "fog" and random.random() < 0.25:
            try:
                await context.bot.send_message(
                    chat_id=det_id,
                    text=f"🌫️ *Qora tuman sababli* ko'rish masofasi yomonlashdi. {tgt_name}ning kimligini aniqlab bo'lmadi.",
                    reply_markup=return_to_group_keyboard(game)
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)
            continue

        # Firibgar deception
        if tgt in game.get("firibgar_disguises", {}):
            real_role = game["firibgar_disguises"][tgt]

        # Framer (Soxtachi) deception
        if tgt in game.get("framer_targets", {}).values():
            real_role = "Qotil"

        # Shadow (Soya) deception
        if tgt in game.get("shadow_targets", {}).values():
            real_role = "Fuqaro" if ROLES.get(real_role) == "red" else "Qotil"

        # Shop Item: Fake Document (Soxta hujjat - Strictly 1 use per game)
        from core.items import has_used_item, mark_item_used, is_item_armed, disarm_item
        if ROLES.get(real_role) == "red":
            fake_doc_used = False
            if is_item_armed(game, tgt, "fake_document"):
                disarm_item(game, tgt, "fake_document")
                fake_doc_used = True
            elif not has_used_item(game, tgt, "fake_document"):
                if await take_item(tgt, "fake_document", 1):
                    mark_item_used(game, tgt, "fake_document")
                    fake_doc_used = True
            else:
                inv = await get_inventory(tgt)
                if inv.get("fake_document", 0) > 0:
                    try:
                        await context.bot.send_message(
                            chat_id=tgt,
                            text="⚠️ Siz ushbu o'yinda bu buyumdan (Soxta hujjat) allaqachon foydalangansiz! Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                            reply_markup=return_to_group_keyboard(game),
                            parse_mode="HTML"
                        )
                    except (TelegramError, Exception) as e:
                        log.debug("Operation suppressed in %s: %s", __name__, e)

            if fake_doc_used:
                real_role = "Fuqaro"
                try:
                    await context.bot.send_message(
                        chat_id=tgt,
                        text=f"{tg_emoji('item_doc', '📄', 'SHOP')} <b>SOXTA HUJJAT ISHLADI!</b> Detektiv sizni tekshirdi, ammo soxta hujjatingiz tufayli sizni 'Fuqaro' deb bildi (1 ta hujjat sarflandi).\n⚠️ <b>Eslatma:</b> Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                        reply_markup=return_to_group_keyboard(game),
                        parse_mode="HTML"
                    )
                except (TelegramError, Exception) as e:
                    log.debug("Operation suppressed in %s: %s", __name__, e)

        try:
            await context.bot.send_message(
                chat_id=det_id,
                text=f"{tg_emoji('investigation', '🔎')} <b>DETEKTIV TEKSHIRUV NATIJASI:</b>\n\n👤 {tgt_name} — 🎭 <b>{real_role}</b>",
                reply_markup=return_to_group_keyboard(game),
                parse_mode="HTML"
            )
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)

    # 7. COMMIT DEATHS
    final_deaths = [u for u in deaths if game["alive"].get(u, False)]
    for u in final_deaths:
        game["alive"][u] = False

    # Check promotions: Detective dead -> Sheriff becomes Detective
    dead_detectives = [u for u in final_deaths if game["roles"].get(u) == "Detektiv"]
    for dead_det in dead_detectives:
        sheriffs_to_promote = set()
        partner = game.get("partners", {}).get(dead_det)
        if partner and game["alive"].get(partner, False) and game["roles"].get(partner) == "Sherif":
            sheriffs_to_promote.add(partner)
        for p_uid, p_role in game.get("roles", {}).items():
            if p_role == "Sherif" and game["alive"].get(p_uid, False):
                sheriffs_to_promote.add(p_uid)
        for sh_id in sheriffs_to_promote:
            game.setdefault("sheriff_promoted", set()).add(sh_id)
            game["roles"][sh_id] = "Detektiv"
            try:
                await context.bot.send_message(
                    chat_id=sh_id,
                    text=f"{tg_emoji('detective', '🕵️‍♂️')} <b>DETEKTIV VAFOT ETDI!</b>\nSiz Sherif sifatida barcha detektivlik vakolatlarini qabul qildingiz va Detektivga aylandingiz.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

    # Boss dead -> Killer becomes Boss
    dead_bosses = [u for u in final_deaths if game["roles"].get(u) == "Boshliq"]
    for dead_boss in dead_bosses:
        partner = game.get("partners", {}).get(dead_boss)
        if partner and game["alive"].get(partner, False) and game["roles"].get(partner) == "Qotil":
            game["roles"][partner] = "Boshliq"
            try:
                await context.bot.send_message(
                    chat_id=partner,
                    text=f"{tg_emoji('don', '👑')} <b>BOSHLIQ HALOK BO'LDI!</b>\nEndi mafiya boshqaruvi sizning qo'lingizda. Nishonni o'zingiz tanlaysiz.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

    # Store morning data
    game["last_night_deaths"] = final_deaths
    game["last_night_causes"] = death_causes
    game["last_night_clues"] = crime_clues
    game["last_night_saved"] = list(saved_by_doc)

    # Prompt Last Words (O'limidan oldingi so'nggi gapi) for night victims
    if final_deaths:
        try:
            from core.last_words import prompt_last_words
            for d_uid in final_deaths:
                await prompt_last_words(context, game, d_uid)
        except Exception as e:
            log.warning("Could not prompt last words: %s", e)

    await save_runtime(game)

    # Check AFK sleepers (3 consecutive inactive nights)
    try:
        from core.afk_penalty import handle_night_sleepers
        await handle_night_sleepers(context, game)
    except Exception as e:
        log.warning("Could not handle night sleepers: %s", e)

    # Check winner
    if await check_winner(context, game):
        game["_resolving_night"] = False
        return

    game["_resolving_night"] = False

    from phases.day import day_phase
    await day_phase(context, game)

async def _king_timeout(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    king_uid: int,
    attacker_uid: int,
    seconds: float
):
    """Background timer task that executes when King is AFK/unresponsive."""
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    from core.engine import games
    game = games.get(chat_id)
    if game and game.get("_waiting_king") and not game.get("_finish_started") and game.get("phase") == "night":
        log.info("King %s timed out against attacker %s in chat %s. Auto-forgiving.", king_uid, attacker_uid, chat_id)
        await handle_king_decision(
            context=context,
            game=game,
            king_uid=king_uid,
            attacker_uid=attacker_uid,
            is_kill=False,
            is_timeout=True
        )

async def handle_king_decision(
    context: ContextTypes.DEFAULT_TYPE,
    game: Dict[str, Any],
    king_uid: int,
    attacker_uid: int,
    is_kill: bool,
    is_timeout: bool = False
):
    """Process King's choice (kill or forgive), or auto-forgive on AFK timeout / delivery error."""
    king_task = game.pop("_king_timer_task", None)
    curr = None
    try:
        curr = asyncio.current_task()
    except (TelegramError, Exception) as e:
        log.debug("Operation suppressed in %s: %s", __name__, e)
    if king_task and king_task is not curr and not king_task.done():
        king_task.cancel()

    if not game.get("_waiting_king"):
        return

    game["_waiting_king"] = False
    game.get("kill_targets", {}).pop(attacker_uid, None)

    pending = game.pop("_pending_night_resolution", None)
    deaths = set(pending["deaths"]) if pending else set()
    death_causes = pending["death_causes"] if pending else {}
    crime_clues = pending["crime_clues"] if pending else {}
    saved_by_doc = set(pending["saved_by_doc"]) if pending else set()
    attacks = pending.get("attacks", []) if pending else []

    if is_kill:
        deaths.add(attacker_uid)
        death_causes.setdefault(attacker_uid, []).append("Qirolning oliy hukmi bilan qatl etildi")
        crime_clues[attacker_uid] = generate_forensic_clue("Qirol", display_name(game, attacker_uid))
    else:
        # Default / forgive
        if is_timeout:
            try:
                await context.bot.send_message(
                    chat_id=game.get("chat"),
                    text=(
                        f"{tg_emoji('boss', '👑')} {tg_emoji('timer', '⏱️')} <b>Qirol javob bermadi (AFK).</b>\n"
                        f"Hujumchi <b>{html.escape(display_name(game, attacker_uid))}</b> avtomatik afv etildi va o'yin davom etmoqda."
                    ),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

    await save_runtime(game)
    await complete_night_resolution(context, game, deaths, death_causes, crime_clues, saved_by_doc, attacks)
