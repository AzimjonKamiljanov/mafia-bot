import html
import logging
from telegram.error import TelegramError
from telegram import Update
from telegram.ext import ContextTypes

from core.engine import (
    games, display_name, save_runtime
)
from core.afk_penalty import record_player_activity
from core.navigation import return_to_group_keyboard
from core.emojis import tg_emoji
from phases.voting import start_voting, finish_voting
from phases.verdict import resolve_verdict

log = logging.getLogger("detektiv.handlers.cb_voting")


async def handle_voting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    if not q or not q.data:
        return False
    data = q.data
    user = q.from_user
    uid = user.id

    # 1. Day to Vote early transition
    if data.startswith("day_to_vote:"):
        chat_id = int(data.split(":")[1])
        game = games.get(chat_id)
        if game and game.get("phase") == "day":
            await q.answer("🗳️ Ovoz berishga o'tilmoqda...")
            await start_voting(context, game)
        else:
            await q.answer("ℹ️ Hozir muhokama vaqti emas.", show_alert=True)
        return True

    # 2. Voting Callback (vote:<chat_id>:<target>)
    if data.startswith("vote:"):
        parts = data.split(":")
        chat_id = int(parts[1])
        target_str = parts[2]
        game = games.get(chat_id)
        if not game or game.get("phase") != "voting":
            await q.answer("❌ Ovoz berish muddati o'tgan yoki yakunlangan.", show_alert=True)
            return True
        if uid not in game.get("players", []):
            await q.answer("❌ Siz bu o'yinda qatnashmayapsiz.", show_alert=True)
            return True
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar ovoz bera olmaydi.", show_alert=True)
            return True

        # Target validation
        if target_str != "none":
            try:
                target_id = int(target_str)
            except ValueError:
                await q.answer("❌ Noto'g'ri nishon tanlandi.", show_alert=True)
                return True
            if target_id == uid:
                await q.answer("❌ O'zingizga ovoz bera olmaysiz!", show_alert=True)
                return True
            if target_id not in game.get("players", []) or not game.get("alive", {}).get(target_id, False):
                await q.answer("❌ Tanlangan o'yinchi tirik emas yoki o'yinda yo'q!", show_alert=True)
                return True

        if uid in game.get("votes", {}):
            prev_target = game["votes"][uid]
            prev_name = "🕊️ Hech kimga" if prev_target == "none" else display_name(game, int(prev_target))
            await q.answer(f"⚠️ Siz allaqachon ovoz bergansiz ({prev_name})!\nHar bir o'yinchi faqat 1 marta ovoz bera oladi.", show_alert=True)
            return True

        game.setdefault("votes", {})[uid] = target_str
        record_player_activity(game, uid)
        target_name = "🕊️ Hech kimga" if target_str == "none" else display_name(game, int(target_str))
        voter_name = display_name(game, uid)
        await q.answer(f"✅ Ovozingiz qabul qilindi: {target_name}", show_alert=True)

        if q.message and q.message.chat.type == "private":
            try:
                await q.edit_message_text(
                    f"✅ Ovozingiz qabul qilindi: *{target_name}*.\n\nEndi guruhga qaytib muhokamani davom ettirishingiz mumkin.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="Markdown"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

        alive_voters = [u for u in game.get("players", []) if game.get("alive", {}).get(u, False)]
        unacted_voters = [display_name(game, u) for u in alive_voters if u not in game.get("votes", {})]
        remaining = len(unacted_voters)

        pending_str = f"\n<i>Kutilayotgan ovozlar ({remaining}): {html.escape(', '.join(unacted_voters))}</i>" if unacted_voters else ""

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{tg_emoji('voting', '🧊')} <b>{html.escape(voter_name)}</b> gumon qildi: <b>{html.escape(target_name)}</b>{pending_str}",
                parse_mode="HTML"
            )
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)

        alive_count = sum(1 for v in game["alive"].values() if v)
        if len(game.get("votes", {})) >= alive_count:
            await finish_voting(context, game)
        return True

    # 3. Verdict Callback (verdict:<chat_id>:<accused>:<kill/forgive>)
    if data.startswith("verdict:"):
        parts = data.split(":")
        chat_id = int(parts[1])
        accused = int(parts[2])
        choice = parts[3]
        game = games.get(chat_id)
        if not game or game.get("phase") != "verdict":
            await q.answer("❌ Sud hukmi muddati o'tgan yoki yakunlangan.", show_alert=True)
            return True
        if uid not in game.get("players", []):
            await q.answer("❌ Siz bu o'yinda qatnashmayapsiz.", show_alert=True)
            return True
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar sud ovozida qatnasha olmaydi.", show_alert=True)
            return True
        if uid == accused:
            await q.answer("❌ Sudlanuvchi o'z hukmida ovoz bera olmaydi!", show_alert=True)
            return True
        if choice not in ("kill", "forgive"):
            await q.answer("❌ Noto'g'ri hukm tanlovi.", show_alert=True)
            return True
        if not game.get("alive", {}).get(accused, False) or accused != game.get("accused_uid"):
            await q.answer("❌ Sudlanuvchi tirik emas yoki sud jarayoni yakunlangan.", show_alert=True)
            return True

        game.setdefault("verdict_votes", {})[uid] = choice
        record_player_activity(game, uid)
        choice_str = "⚔️ QATL ETISH" if choice == "kill" else "🕊️ AVF ETISH"
        voter_name = display_name(game, uid)
        await q.answer(f"✅ Ovozingiz qayd etildi: {choice_str}", show_alert=True)

        if q.message and q.message.chat.type == "private":
            try:
                await q.edit_message_text(
                    f"✅ Sud hukmingiz qayd etildi: <b>{choice_str}</b>.\n\nEndi guruhga qaytib natijani kuting.",
                    reply_markup=return_to_group_keyboard(game),
                    parse_mode="HTML"
                )
            except (TelegramError, Exception) as e:
                log.debug("Operation suppressed in %s: %s", __name__, e)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{tg_emoji('voting', '⚖️')} <b>{html.escape(voter_name)}</b> hukm chiqardi: <b>{choice_str}</b>",
                parse_mode="HTML"
            )
        except (TelegramError, Exception) as e:
            log.debug("Operation suppressed in %s: %s", __name__, e)

        alive_count = sum(1 for v in game["alive"].values() if v)
        req_count = alive_count - 1 if game.get("alive", {}).get(accused, False) else alive_count
        if len(game.get("verdict_votes", {})) >= max(1, req_count):
            await resolve_verdict(context, game)
        return True

    # 4. Mayor Reveal Callback (mayor_reveal:<chat_id>)
    if data.startswith("mayor_reveal:"):
        chat_id = int(data.split(":")[1])
        game = games.get(chat_id)
        if not game:
            await q.answer("❌ O'yin topilmadi.", show_alert=True)
            return True
        if game.get("roles", {}).get(uid) != "Mer":
            await q.answer("❌ Siz shahar meri emassiz!", show_alert=True)
            return True
        if not game.get("alive", {}).get(uid, False):
            await q.answer("💀 Halok bo'lganlar o'zini oshkor qila olmaydi.", show_alert=True)
            return True
        if uid in game.get("mayor_revealed", set()):
            await q.answer("ℹ️ Siz allaqachon mer ekanligingizni e'lon qilgansiz.", show_alert=True)
            return True

        game.setdefault("mayor_revealed", set()).add(uid)
        await q.answer("🎖️ Siz shahar hokimi sifatida o'zingizni oshkor qildingiz!", show_alert=True)
        m_name = display_name(game, uid)
        announcement = (
            "👑 *Shahar hokimi (Mer) oshkor bo'ldi!*\n\n"
            f"👤 *{m_name}* rasman shahar hokimi ekanligini e'lon qildi!\n"
            "Uning har bir ovozi bundan buyon *3 ta ovoz* kuchiga teng bo'ladi."
        )
        await context.bot.send_message(chat_id=chat_id, text=announcement)
        await save_runtime(game)
        return True

    return False
