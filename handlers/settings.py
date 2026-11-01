import json
import html
import logging
from typing import Dict, Any, List
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import (
    DEFAULT_LOBBY_SECONDS, DEFAULT_NIGHT_SECONDS, DEFAULT_DAY_SECONDS,
    DEFAULT_VOTE_SECONDS, DEFAULT_VERDICT_SECONDS, ROLES, ROLE_ORDER
)
from database.models import get_chat_settings, update_chat_settings, is_admin
from core.emojis import tg_emoji

log = logging.getLogger("detektiv.handlers.settings")

ROLE_PAGESIZE = 6

def build_settings_menu_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("⏱️ Vaqtlarni sozlash", callback_data=f"sett:times:{chat_id}"),
            InlineKeyboardButton("🎭 Rollarni boshqarish", callback_data=f"sett:roles:{chat_id}:0")
        ],
        [
            InlineKeyboardButton("🔄 Asliga qaytarish (Reset)", callback_data=f"sett:reset:{chat_id}")
        ]
    ]
    if chat_id == 0:
        rows.append([
            InlineKeyboardButton("👑 Master Admin Paneli", callback_data="adm:menu")
        ])
    rows.append([
        InlineKeyboardButton("❌ Yopish", callback_data="sett:close")
    ])
    return InlineKeyboardMarkup(rows)

def build_times_keyboard(chat_id: int, settings: Dict[str, Any]) -> InlineKeyboardMarkup:
    night = int(settings.get("night_seconds", DEFAULT_NIGHT_SECONDS))
    day = int(settings.get("day_seconds", DEFAULT_DAY_SECONDS))
    vote = int(settings.get("vote_seconds", DEFAULT_VOTE_SECONDS))
    verdict = int(settings.get("verdict_seconds", DEFAULT_VERDICT_SECONDS))

    def mark(val, target):
        return f"✓ {val}s" if val == target else f"{val}s"

    rows = [
        [
            InlineKeyboardButton("🌙 Tun:", callback_data="sett:noop"),
            InlineKeyboardButton(mark(30, night), callback_data=f"sett:set_time:{chat_id}:night:30"),
            InlineKeyboardButton(mark(45, night), callback_data=f"sett:set_time:{chat_id}:night:45"),
            InlineKeyboardButton(mark(60, night), callback_data=f"sett:set_time:{chat_id}:night:60"),
        ],
        [
            InlineKeyboardButton("☀️ Kun:", callback_data="sett:noop"),
            InlineKeyboardButton(mark(60, day), callback_data=f"sett:set_time:{chat_id}:day:60"),
            InlineKeyboardButton(mark(90, day), callback_data=f"sett:set_time:{chat_id}:day:90"),
            InlineKeyboardButton(mark(120, day), callback_data=f"sett:set_time:{chat_id}:day:120"),
        ],
        [
            InlineKeyboardButton("🗳 Ovoz:", callback_data="sett:noop"),
            InlineKeyboardButton(mark(30, vote), callback_data=f"sett:set_time:{chat_id}:vote:30"),
            InlineKeyboardButton(mark(45, vote), callback_data=f"sett:set_time:{chat_id}:vote:45"),
            InlineKeyboardButton(mark(60, vote), callback_data=f"sett:set_time:{chat_id}:vote:60"),
        ],
        [
            InlineKeyboardButton("⚖️ Sud:", callback_data="sett:noop"),
            InlineKeyboardButton(mark(20, verdict), callback_data=f"sett:set_time:{chat_id}:verdict:20"),
            InlineKeyboardButton(mark(30, verdict), callback_data=f"sett:set_time:{chat_id}:verdict:30"),
        ],
        [
            InlineKeyboardButton("◀️ Asosiy sozlamalar", callback_data=f"sett:menu:{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(rows)

def build_roles_keyboard(chat_id: int, page: int, disabled: set) -> InlineKeyboardMarkup:
    roles = [r for r in ROLE_ORDER if r not in ("Fuqaro", "Boshliq")] # Fuqaro & Boshliq are essential
    total_pages = (len(roles) + ROLE_PAGESIZE - 1) // ROLE_PAGESIZE
    page = max(0, min(page, total_pages - 1))

    start = page * ROLE_PAGESIZE
    chunk = roles[start:start + ROLE_PAGESIZE]

    rows = []
    # 2 buttons per row
    row = []
    for r in chunk:
        is_disabled = r in disabled
        status = "❌" if is_disabled else "✅"
        btn_text = f"{status} {r}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"sett:toggle_role:{chat_id}:{page}:{r}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # Nav
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"sett:roles:{chat_id}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="sett:noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"sett:roles:{chat_id}:{page+1}"))
    rows.append(nav)

    rows.append([
        InlineKeyboardButton("◀️ Asosiy sozlamalar", callback_data=f"sett:menu:{chat_id}")
    ])
    return InlineKeyboardMarkup(rows)

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.effective_message
    if not chat or not user or not msg:
        return

    # Check admin in group, or global admin
    if chat.type in ("group", "supergroup"):
        if not is_admin(user.id, user.username):
            member = await context.bot.get_chat_member(chat.id, user.id)
            if member.status not in ("administrator", "creator"):
                await msg.reply_text("❌ Faqat guruh adminlari yoki Super Admin sozlamalarni o'zgartira oladi.")
                return
        target_chat_id = chat.id
        title = html.escape(chat.title or "Guruh")
    else:
        # In PM: if admin, check if target chat_id is passed as arg, otherwise show global default settings (chat_id=0)
        if is_admin(user.id, user.username):
            if context.args and len(context.args) > 0 and context.args[0].lstrip("-").isdigit():
                target_chat_id = int(context.args[0])
                title = f"Guruh ({target_chat_id})"
            else:
                target_chat_id = 0
                title = "Asosiy Standart Sozlamalar (Global)"
        else:
            from config import BOT_USERNAME
            pm_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "⚙️ <b>O'yin va Guruh Sozlamalari</b>\n\n"
                "O'yin vaqtlari (tun/kun davomiyligi) va rollarni yoqish/o'chirish faqat <b>Telegram guruhlarida</b> ishlaydi.\n\n"
                "Sozlamalarni o'zgartirish uchun botni guruhingizga qo'shing va o'sha guruhda <code>/settings</code> buyrug'ini yuboring!",
                reply_markup=pm_kb,
                parse_mode="HTML"
            )
            return

    settings = await get_chat_settings(target_chat_id)
    night = settings.get("night_seconds", DEFAULT_NIGHT_SECONDS)
    day = settings.get("day_seconds", DEFAULT_DAY_SECONDS)
    vote = settings.get("vote_seconds", DEFAULT_VOTE_SECONDS)
    verdict = settings.get("verdict_seconds", DEFAULT_VERDICT_SECONDS)
    try:
        disabled = json.loads(settings.get("disabled_roles", "[]"))
    except Exception:
        disabled = []

    dis_text = ", ".join(disabled) if disabled else "<i>Barcha rollar faol</i>"

    text = (
        f"{tg_emoji('settings_gear', '⚙️', 'USER_SETTINGS')} <b>O'YIN VA GURUH SOZLAMALARI</b>\n\n"
        f"👥 Guruh: <b>{title}</b>\n\n"
        f"{tg_emoji('timer', '⏱', 'USER_SETTINGS')} <b>Hozirgi vaqtlar:</b>\n"
        f"• {tg_emoji('night', '🌙')} Tun fazasi: <b>{night}s</b>\n"
        f"• {tg_emoji('day', '☀️')} Kun fazasi: <b>{day}s</b>\n"
        f"• {tg_emoji('voting', '🗳')} Ovoz berish: <b>{vote}s</b>\n"
        f"• {tg_emoji('voting', '⚖️')} Sud (Hukm): <b>{verdict}s</b>\n\n"
        f"• {tg_emoji('settings_roles', '🎭', 'USER_SETTINGS')} <b>O'chirilgan rollar:</b> {dis_text}\n\n"
        "O'zgartirish uchun quyidagi tugmalardan birini tanlang 👇"
    )

    await msg.reply_text(
        text=text,
        reply_markup=build_settings_menu_keyboard(target_chat_id),
        parse_mode="HTML"
    )

async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data or ""
    if not data.startswith("sett:"):
        return False

    user = update.effective_user
    if not user:
        return True

    parts = data.split(":")
    action = parts[1]

    if action == "close":
        await q.answer("Sozlamalar yopildi.")
        try:
            await q.message.delete()
        except Exception:
            pass
        return True

    if action == "noop":
        await q.answer()
        return True

    chat_id = int(parts[2])

    # Check permission
    if not is_admin(user.id, user.username):
        try:
            member = await context.bot.get_chat_member(chat_id, user.id)
            if member.status not in ("administrator", "creator"):
                await q.answer("❌ Faqat guruh admini o'zgartira oladi!", show_alert=True)
                return True
        except Exception:
            pass

    if action == "menu":
        settings = await get_chat_settings(chat_id)
        night = settings.get("night_seconds", DEFAULT_NIGHT_SECONDS)
        day = settings.get("day_seconds", DEFAULT_DAY_SECONDS)
        vote = settings.get("vote_seconds", DEFAULT_VOTE_SECONDS)
        verdict = settings.get("verdict_seconds", DEFAULT_VERDICT_SECONDS)
        try:
            disabled = json.loads(settings.get("disabled_roles", "[]"))
        except Exception:
            disabled = []

        dis_text = ", ".join(disabled) if disabled else "<i>Barcha rollar faol</i>"
        text = (
            f"{tg_emoji('settings_gear', '⚙️', 'USER_SETTINGS')} <b>O'YIN VA GURUH SOZLAMALARI</b>\n\n"
            f"{tg_emoji('timer', '⏱', 'USER_SETTINGS')} <b>Hozirgi vaqtlar:</b>\n"
            f"• {tg_emoji('night', '🌙')} Tun fazasi: <b>{night}s</b>\n"
            f"• {tg_emoji('day', '☀️')} Kun fazasi: <b>{day}s</b>\n"
            f"• {tg_emoji('voting', '🗳')} Ovoz berish: <b>{vote}s</b>\n"
            f"• {tg_emoji('voting', '⚖️')} Sud (Hukm): <b>{verdict}s</b>\n\n"
            f"• {tg_emoji('settings_roles', '🎭', 'USER_SETTINGS')} <b>O'chirilgan rollar:</b> {dis_text}\n\n"
            "O'zgartirish uchun quyidagi tugmalardan birini tanlang 👇"
        )
        await q.edit_message_text(text, reply_markup=build_settings_menu_keyboard(chat_id), parse_mode="HTML")
        await q.answer()
        return True

    if action == "times":
        settings = await get_chat_settings(chat_id)
        text = (
            "⏱ <b>FAZALAR VAQTLARINI SOZLASH</b>\n\n"
            "Har bir faza uchun kerakli soniyani tanlang.\n"
            "Faol qiymatlar <b>✓</b> belgisi bilan ko'rsatiladi:"
        )
        await q.edit_message_text(text, reply_markup=build_times_keyboard(chat_id, settings), parse_mode="HTML")
        await q.answer()
        return True

    if action == "set_time":
        phase_name = parts[3]
        seconds_val = int(parts[4])
        field_map = {
            "night": "night_seconds",
            "day": "day_seconds",
            "vote": "vote_seconds",
            "verdict": "verdict_seconds",
        }
        field = field_map.get(phase_name)
        if field:
            await update_chat_settings(chat_id, **{field: seconds_val})
        settings = await get_chat_settings(chat_id)
        await q.edit_message_reply_markup(reply_markup=build_times_keyboard(chat_id, settings))
        await q.answer(f"✅ {phase_name.capitalize()} vaqti {seconds_val}s ga o'rnatildi!")
        return True

    if action == "roles":
        page = int(parts[3])
        settings = await get_chat_settings(chat_id)
        try:
            disabled = set(json.loads(settings.get("disabled_roles", "[]")))
        except Exception:
            disabled = set()

        text = (
            "🎭 <b>ROLLARNI BOSHQARISH</b>\n\n"
            "Kerakli rolni o'chirish yoki yoqish uchun uning ustiga bosing:\n"
            "• ✅ — Rol o'yinda ishtirok etadi\n"
            "• ❌ — Rol o'yindan chiqarilgan"
        )
        await q.edit_message_text(text, reply_markup=build_roles_keyboard(chat_id, page, disabled), parse_mode="HTML")
        await q.answer()
        return True

    if action == "toggle_role":
        page = int(parts[3])
        role_to_toggle = parts[4]

        settings = await get_chat_settings(chat_id)
        try:
            disabled = set(json.loads(settings.get("disabled_roles", "[]")))
        except Exception:
            disabled = set()

        if role_to_toggle in disabled:
            disabled.remove(role_to_toggle)
            msg_status = f"✅ {role_to_toggle} yoqildi"
        else:
            disabled.add(role_to_toggle)
            msg_status = f"❌ {role_to_toggle} o'chirildi"

        await update_chat_settings(chat_id, disabled_roles=json.dumps(list(disabled)))
        await q.edit_message_reply_markup(reply_markup=build_roles_keyboard(chat_id, page, disabled))
        await q.answer(msg_status)
        return True

    if action == "reset":
        await update_chat_settings(
            chat_id,
            night_seconds=DEFAULT_NIGHT_SECONDS,
            day_seconds=DEFAULT_DAY_SECONDS,
            vote_seconds=DEFAULT_VOTE_SECONDS,
            verdict_seconds=DEFAULT_VERDICT_SECONDS,
            disabled_roles="[]"
        )
        await q.answer("🔄 Barcha sozlamalar asliga qaytarildi!", show_alert=True)
        settings = await get_chat_settings(chat_id)
        text = (
            "⚙️ <b>O'YIN VA GURUH SOZLAMALARI</b>\n\n"
            "⏱ <b>Hozirgi vaqtlar:</b>\n"
            f"• 🌙 Tun fazasi: <b>{DEFAULT_NIGHT_SECONDS}s</b>\n"
            f"• ☀️ Kun fazasi: <b>{DEFAULT_DAY_SECONDS}s</b>\n"
            f"• 🗳 Ovoz berish: <b>{DEFAULT_VOTE_SECONDS}s</b>\n"
            f"• ⚖️ Sud (Hukm): <b>{DEFAULT_VERDICT_SECONDS}s</b>\n\n"
            "🎭 <b>O'chirilgan rollar:</b> <i>Barcha rollar faol</i>\n\n"
            "O'zgartirish uchun quyidagi tugmalardan birini tanlang 👇"
        )
        await q.edit_message_text(text, reply_markup=build_settings_menu_keyboard(chat_id), parse_mode="HTML")
        return True

    return True
