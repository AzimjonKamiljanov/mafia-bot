import asyncio
import random
import logging
from typing import Dict, Any, List
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import DEFAULT_VERDICT_SECONDS
from database.models import take_item
from core.engine import (
    display_name, save_runtime, check_winner, finish_game, cancel_game_timer
)
from core.storyteller import generate_verdict_story
from core.will import fetch_player_will, format_will_announcement
from core.graveyard import graveyard_menu_keyboard, graveyard_status_text
from core.audio_effects import send_atmospheric_message
from core.navigation import bot_action_button
from core.visuals import send_animated_dice_effect
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.phases.verdict")

def verdict_keyboard(chat_id: int, accused_uid: int, is_pm: bool = False, game_or_link: Any = None) -> InlineKeyboardMarkup:
    from core.navigation import bot_action_button, return_to_group_button
    bottom_btn = return_to_group_button(game_or_link or chat_id) if is_pm else bot_action_button(chat_id, "🔵 💬 Botga o'tish (Hukm/Ovoz)")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 ⚔️ QATL ETISH", callback_data=f"verdict:{chat_id}:{accused_uid}:kill"),
            InlineKeyboardButton("🟢 🕊️ AFV (AVF) ETISH", callback_data=f"verdict:{chat_id}:{accused_uid}:forgive")
        ],
        [
            bottom_btn
        ]
    ])

async def verdict_phase(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any], accused_uid: int):
    chat_id = game["chat"]
    game["phase"] = "verdict"
    game["accused_uid"] = accused_uid
    game["verdict_votes"] = {}
    await save_runtime(game)

    accused_name = display_name(game, accused_uid)

    verdict_seconds = int(game.get("settings", {}).get("verdict_seconds", DEFAULT_VERDICT_SECONDS))
    text = (
        f"{tg_emoji('voting', '⚖️')} <b>Sud minbari</b>\n\n"
        f"Ayblanuvchi: <b>{accused_name}</b>\n\n"
        "Shahar fuqarolari, uning taqdirini hal qiling: qatl etilsinmi yoki afv etilsin?\n\n"
        f"{tg_emoji('timer', '⏳')} Vaqt: <b>{verdict_seconds} soniya</b>"
    )

    kb = verdict_keyboard(chat_id, accused_uid)
    await send_atmospheric_message(
        bot=context.bot,
        chat_id=chat_id,
        text=text,
        sound_type="verdict",
        reply_markup=kb,
        parse_mode="HTML"
    )

    night_num = game.get("night", 1)
    cancel_game_timer(game)
    game["_timer_task"] = asyncio.create_task(_verdict_timer(context, chat_id, night_num, accused_uid, verdict_seconds))

async def _verdict_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, night_num: int, accused_uid: int, seconds: int):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    from core.engine import games
    game = games.get(chat_id)
    if game and game.get("phase") == "verdict" and game.get("accused_uid") == accused_uid and not game.get("_finish_started"):
        await resolve_verdict(context, game)

async def resolve_verdict(context: ContextTypes.DEFAULT_TYPE, game: Dict[str, Any]):
    if game.get("phase") != "verdict" or game.get("_finish_started"):
        return
    cancel_game_timer(game)

    chat_id = game["chat"]
    accused_uid = game.get("accused_uid")
    if not accused_uid or not game["alive"].get(accused_uid, False):
        return

    accused_name = display_name(game, accused_uid)
    accused_role = game.get("roles", {}).get(accused_uid, "Fuqaro")
    votes = game.get("verdict_votes", {})

    mayor_revealed = game.get("mayor_revealed", set())
    kill_votes = [u for u, v in votes.items() if v == "kill" and game["alive"].get(u, False)]
    forgive_votes = [u for u, v in votes.items() if v == "forgive" and game["alive"].get(u, False)]

    kill_weight = sum(3 if u in mayor_revealed else 1 for u in kill_votes)
    forgive_weight = sum(3 if u in mayor_revealed else 1 for u in forgive_votes)

    import html
    escaped_accused = html.escape(accused_name)

    lines = [
        f"{tg_emoji('voting', '⚖️')} <b>Hukm natijasi ({escaped_accused}):</b>",
        "",
        f"⚔️ Qatl: <b>{kill_weight} ta ovoz ({len(kill_votes)} kishi)</b>",
        f"🕊️ Afv: <b>{forgive_weight} ta ovoz ({len(forgive_votes)} kishi)</b>",
        ""
    ]

    weather = game.get("weather", {})
    is_amnesty = bool(weather and weather.get("id") == "amnesty")

    from core.navigation import bot_action_keyboard
    verdict_res_kb = bot_action_keyboard(chat_id, "💬 Botga o'tish (Amallar/Ovoz)")

    if is_amnesty:
        lines.append(f"\n{tg_emoji('voting', '⚖️')} <b>SUD AMNISTIYASI ISHLADI!</b>")
        lines.append("Shaharda e'lon qilingan sud amnistiyasi farmoniga binoan, bugungi barcha qatl hukmlari bekor qilindi!")
        lines.append(f"<b>{escaped_accused}</b> dor ostidan ozod qilindi va omon qoldi.")
        try:
            await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=verdict_res_kb, parse_mode="HTML")
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=verdict_res_kb)
        game["night"] = game.get("night", 1) + 1
        from phases.night import start_night
        await start_night(context, game)
        return

    if kill_weight > forgive_weight:
        # 1. ADVOKAT HIMOYA CHECK
        lawyer_clients = game.get("lawyer_clients", {})
        saved_by_lawyer = any(client == accused_uid for client in lawyer_clients.values())
        if saved_by_lawyer:
            lines.append(f"\n{tg_emoji('voting', '⚖️')} <b>ADVOKAT ARALASHUVI!</b>")
            lines.append(f"Advokat o'z vakolatidan foydalanib, <b>{escaped_accused}</b>ni dorga osilishdan saqlab qoldi!")
            try:
                await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=verdict_res_kb, parse_mode="HTML")
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=verdict_res_kb)
            game["night"] = game.get("night", 1) + 1
            from phases.night import start_night
            await start_night(context, game)
            return

        # 2. SHOP ITEM RULER PROTECTION CHECK (Strictly 1 use per game per player)
        from core.items import has_used_item, mark_item_used, is_item_armed, disarm_item, ALREADY_USED_MSG
        saved_by_shield = False
        if is_item_armed(game, accused_uid, "ruler_protection"):
            disarm_item(game, accused_uid, "ruler_protection")
            saved_by_shield = True
        elif not has_used_item(game, accused_uid, "ruler_protection"):
            if await take_item(accused_uid, "ruler_protection", 1):
                mark_item_used(game, accused_uid, "ruler_protection")
                saved_by_shield = True
        else:
            from database.models import get_inventory
            inv = await get_inventory(accused_uid)
            if inv.get("ruler_protection", 0) > 0:
                try:
                    await context.bot.send_message(
                        chat_id=accused_uid,
                        text="⚠️ Siz ushbu o'yinda bu buyumdan (Qatldan himoya) allaqachon foydalangansiz! Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                        reply_markup=verdict_res_kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        if saved_by_shield:
            lines.append(f"\n{tg_emoji('don', '👑')} <b>HUKMDAN HIMOYA ISHLADI!</b>")
            lines.append(f"<b>{escaped_accused}</b> maxsus do'kon himoyasini ishlatdi va qatldan qutuldi (Har bir o'yinda faqat 1 marta ishlatish mumkin).")
            try:
                await context.bot.send_message(
                    chat_id=accused_uid,
                    text=f"{tg_emoji('don', '👑')} <b>QATLDAN HIMOYA ISHLADI!</b> Siz maxsus do'kon himoyasini ishlatib qatldan omon qoldingiz (1 ta buyum sarflandi).\n⚠️ <b>Eslatma:</b> Ushbu buyumdan har bir o'yinda faqat 1 marta foydalanish mumkin.",
                    reply_markup=verdict_res_kb,
                    parse_mode="HTML"
                )
            except Exception:
                pass
            try:
                await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=verdict_res_kb, parse_mode="HTML")
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=verdict_res_kb)
            game["night"] = game.get("night", 1) + 1
            from phases.night import start_night
            await start_night(context, game)
            return

        # 3. JOKER WIN CHECK
        if accused_role == "Joker":
            lines.append("\n🃏 <b>JOKER MAQSADIGA YETDI!</b>")
            lines.append(f"Telba Joker <b>{escaped_accused}</b> butun shaharni aldab, o'zini osishlariga erishdi!")
            try:
                await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=verdict_res_kb, parse_mode="HTML")
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=verdict_res_kb)
            await finish_game(context, game, [accused_uid], joker=True)
            return

        # 4. KAMIKADZE BLAST CHECK
        kamikadze_victim = None
        if accused_role == "Kamikadze" and kill_votes:
            kamikadze_victim = random.choice(kill_votes)

        # 5. QASOSKOR RETALIATION CHECK
        qasoskor_victim = None
        if accused_role == "Qasoskor":
            rev_tgt = game.get("revenge_targets", {}).get(accused_uid)
            if rev_tgt and game["alive"].get(rev_tgt, False) and rev_tgt != accused_uid:
                qasoskor_victim = rev_tgt
            elif kill_votes:
                qasoskor_victim = random.choice(kill_votes)

        # 5.1. SHOP ITEM REVENGE KNIFE CHECK (Strictly 1 use per game)
        knife_victim = None
        if not qasoskor_victim and kill_votes:
            if is_item_armed(game, accused_uid, "revenge_knife"):
                disarm_item(game, accused_uid, "revenge_knife")
                knife_victim = random.choice(kill_votes)
            elif not has_used_item(game, accused_uid, "revenge_knife"):
                if await take_item(accused_uid, "revenge_knife", 1):
                    mark_item_used(game, accused_uid, "revenge_knife")
                    knife_victim = random.choice(kill_votes)
            else:
                from database.models import get_inventory
                inv = await get_inventory(accused_uid)
                if inv.get("revenge_knife", 0) > 0:
                    try:
                        await context.bot.send_message(
                            chat_id=accused_uid,
                            text="⚠️ Siz ushbu o'yinda bu buyumdan (Qasos pichog'i) allaqachon foydalangansiz! Har bir o'yinda faqat 1 marta ishlatish mumkin.",
                            reply_markup=verdict_res_kb,
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

        # Execute accused
        game["alive"][accused_uid] = False
        verdict_story = generate_verdict_story(accused_name, accused_role)
        lines.append(f"\n{tg_emoji('eliminated', '☠️')} <b>QATL IJRO ETILDI:</b>\n{verdict_story}")

        # Broadcast Last Will
        will = await fetch_player_will(accused_uid)
        lines.append("\n" + format_will_announcement(accused_name, will))

        # Deliver Kamikadze explosion if triggered
        if kamikadze_victim and game["alive"].get(kamikadze_victim, False):
            game["alive"][kamikadze_victim] = False
            kv_name = display_name(game, kamikadze_victim)
            lines.append(f"\n💣 <b>KAMIKADZE PORTLASHI!</b>\n<b>{escaped_accused}</b> o'zi bilan birga ayblovchi <b>{html.escape(kv_name)}</b>ni ham portlatib ketdi!")

        # Deliver Qasoskor retaliation if triggered
        if qasoskor_victim and game["alive"].get(qasoskor_victim, False):
            game["alive"][qasoskor_victim] = False
            qv_name = display_name(game, qasoskor_victim)
            lines.append(f"\n⚔️ <b>QASOSKORNING SO'NGGI ZARBASI!</b>\n<b>{escaped_accused}</b> o'zi bilan birga <b>{html.escape(qv_name)}</b>ni ham narigi dunyoga tortib ketdi!")

        # Deliver Revenge Knife strike if triggered
        if knife_victim and game["alive"].get(knife_victim, False):
            game["alive"][knife_victim] = False
            rkv_name = display_name(game, knife_victim)
            lines.append(f"\n{tg_emoji('mafia', '🔪')} <b>QASOS PICHOG'I ISHLADI!</b>\n<b>{escaped_accused}</b> o'limi oldidan yashirin qasos pichog'ini ishlatib, qatl tarafdori <b>{html.escape(rkv_name)}</b>ni o'ldirdi (Har bir o'yinda faqat 1 marta ishlatish mumkin)!")
            try:
                await context.bot.send_message(
                    chat_id=accused_uid,
                    text=f"{tg_emoji('mafia', '🔪')} <b>QASOS PICHOG'I ISHLADI!</b> Siz o'limingiz oldidan qasos oldingiz (1 ta pichoq sarflandi).\n⚠️ <b>Eslatma:</b> Har bir o'yinda faqat 1 marta foydalanish mumkin.",
                    reply_markup=verdict_res_kb,
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # Check promotions if Detective or Boss died
        day_deaths = [u for u in [accused_uid, kamikadze_victim, qasoskor_victim, knife_victim] if u and not game["alive"].get(u, True)]
        for d_uid in day_deaths:
            if game["roles"].get(d_uid) == "Detektiv":
                for p_uid, p_role in game.get("roles", {}).items():
                    if p_role == "Sherif" and game["alive"].get(p_uid, False):
                        game.setdefault("sheriff_promoted", set()).add(p_uid)
                        game["roles"][p_uid] = "Detektiv"
                        try:
                            await context.bot.send_message(
                                chat_id=p_uid,
                                text=f"{tg_emoji('detective', '🕵️‍♂️')} <b>DETEKTIV VAFOT ETDI!</b>\nSiz Sherif sifatida barcha detektivlik vakolatlarini qabul qildingiz va Detektivga aylandingiz.",
                                reply_markup=return_to_group_keyboard(game),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
            elif game["roles"].get(d_uid) == "Boshliq":
                for p_uid, p_role in game.get("roles", {}).items():
                    if p_role == "Qotil" and game["alive"].get(p_uid, False):
                        game["roles"][p_uid] = "Boshliq"
                        try:
                            await context.bot.send_message(
                                chat_id=p_uid,
                                text=f"{tg_emoji('don', '👑')} <b>BOSHLIQ HALOK BO'LDI!</b>\nEndi mafiya boshqaruvi sizning qo'lingizda. Nishonni o'zingiz tanlaysiz.",
                                reply_markup=return_to_group_keyboard(game),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

        # Send Graveyard card to executed player
        try:
            await context.bot.send_message(
                chat_id=accused_uid,
                text=graveyard_status_text(game, accused_uid),
                reply_markup=graveyard_menu_keyboard(game.get("_db_id", 0), group_link=game.get("group_link")),
                parse_mode="HTML"
            )
        except Exception:
            pass

        # Prompt Last Words (O'limidan oldingi so'nggi gapi)
        try:
            from core.last_words import prompt_last_words
            await prompt_last_words(context, game, accused_uid)
            if kamikadze_victim:
                await prompt_last_words(context, game, kamikadze_victim)
            if qasoskor_victim:
                await prompt_last_words(context, game, qasoskor_victim)
        except Exception as e:
            log.warning("Could not prompt last words: %s", e)

    else:
        lines.append(f"\n🕊️ <b>SHAHAR AVF ETDI:</b> <b>{escaped_accused}</b> omon qoldi va o'yin davom etadi.")

    sound_marker = "execution" if (kill_weight > forgive_weight) else "saved"
    await send_atmospheric_message(
        bot=context.bot,
        chat_id=chat_id,
        text="\n".join(lines),
        sound_type=sound_marker,
        reply_markup=verdict_res_kb,
        parse_mode="HTML"
    )
    await save_runtime(game)

    # Check winner
    if await check_winner(context, game):
        return

    # Advance to next night
    game["night"] = game.get("night", 1) + 1
    from phases.night import start_night
    await start_night(context, game)
