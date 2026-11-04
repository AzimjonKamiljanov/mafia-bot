import re
import os
import html
import json
import uuid
import time
import logging
from typing import Optional, Dict, Any, Tuple
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import ADMIN_IDS, ROLES, ROLE_ORDER, GOLD_SHOP
from database.db import get_db
from database.models import (
    is_admin, get_user, change_balance, set_badge, add_item,
    set_bot_config, get_bot_config, get_all_bot_configs,
    update_chat_settings, now_iso
)
from core.engine import (
    games, lobbies, cancel_game_timer,
    abort_game, abort_lobby
)

log = logging.getLogger("detektiv.handlers.admin_ai")

MAX_ITEM_COUNT = 50
MAX_CURRENCY_COUNT = 100_000
GRANT_VERBS = ("grant", "ber", "qo'sh", "qosh", "tashla")
pending_admin_grants: Dict[str, Dict[str, Any]] = {}

# Universal role alias mapping for intuitive Uzbek role recognition
ROLE_ALIASES = {
    "don": "Boshliq",
    "boshliq": "Boshliq",
    "mafiya": "Qotil",
    "qotil": "Qotil",
    "sherif": "Sherif",
    "detektiv": "Detektiv",
    "komissar": "Detektiv",
    "kamisar": "Detektiv",
    "doktor": "Doktor",
    "shifokor": "Doktor",
    "tansoqchi": "Tansoqchi",
    "sayyoh": "Sayyoh",
    "daydi": "Sayyoh",
    "advokat": "Advokat",
    "ruhshunos": "Ruhshunos",
    "mer": "Mer",
    "hokim": "Mer",
    "boy": "Boy",
    "qirol": "Qirol",
    "begona": "Begona",
    "savdogar": "Savdogar",
    "fuqaro": "Fuqaro",
    "tinch": "Fuqaro",
    "soxtachi": "Soxtachi",
    "maftunkor": "Maftunkor",
    "kamikadze": "Kamikadze",
    "bori": "Bo'ri",
    "bo'ri": "Bo'ri",
    "joker": "Joker",
    "maniak": "Maniak",
    "pirotexnik": "Pirotexnik",
    "qasoskor": "Qasoskor",
    "firibgar": "Firibgar",
    "buqalamun": "Firibgar",
    "ogri": "Pul o'g'risi",
    "o'g'ri": "Pul o'g'risi",
    "pul o'g'risi": "Pul o'g'risi",
    "pul": "Pul o'g'risi",
}

def resolve_role_name(name_str: str) -> Optional[str]:
    """Resolve role name accounting for Uzbek accusative case suffixes (-ni, -i, -lar)."""
    raw = name_str.strip().lower()
    # Strip common suffixes: -rolini, -roli, -ni, -i, -lar, -lari
    clean = re.sub(r'(?:rolini|roli|lari|lar|ni|i)$', '', raw).strip()
    clean_no_apos = clean.replace("'", "").replace("`", "").replace("ʻ", "").replace("’", "").strip()

    if clean_no_apos in ROLE_ALIASES:
        return ROLE_ALIASES[clean_no_apos]

    for alias, canonical in ROLE_ALIASES.items():
        alias_clean = alias.replace("'", "")
        if clean_no_apos == alias_clean or (len(clean_no_apos) >= 3 and alias_clean.startswith(clean_no_apos[:4])):
            return canonical

    for r in ROLE_ORDER:
        r_clean = r.lower().replace("'", "").replace("`", "")
        if clean_no_apos == r_clean or (len(clean_no_apos) >= 3 and r_clean.startswith(clean_no_apos[:4])):
            return r

    return None

async def query_gemini_ai(prompt: str) -> Optional[str]:
    """Calls Gemini API if GEMINI_API_KEY is configured in environment."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Siz Telegramdagi «Detektiv Mafia» o'yin botining AI Boshqaruv Assistentisiz. "
                                "Foydalanuvchi — Bot Super Admini (ID: 7651553630). "
                                "Unga qisqa, do'stona, o'zbek tilida professional javob bering va zarur bot sozlamalari buyruqlarini eslatib o'ting.\n\n"
                                f"Admin so'rovi: {prompt}"
                            )
                        }
                    ]
                }
            ]
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
    except Exception as e:
        log.warning("Gemini AI API request error: %s", e)
    return None

async def process_admin_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Processes natural language requests sent by Master Admin in bot's private chat.
    Returns True if handled, False if not an admin or in a group chat.
    """
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not msg.text or not user or not chat:
        return False

    # Only process in private chat for Master Admins
    if chat.type != "private":
        return False

    if not is_admin(user.id, user.username):
        return False

    raw_text = msg.text.strip()
    text = raw_text.lower()

    # 1. Broadcaster (Broadcast message to all groups)
    if text.startswith(("broadcast:", "hammaga xabar:", "barchaga xabar:", "elon:", "e'lon:", "habar:")):
        clean_msg = raw_text.split(":", 1)[1].strip()
        if not clean_msg:
            await msg.reply_text("⚠️ Xabar matni bo'sh bo'lishi mumkin emas.")
            return True

        db = await get_db()
        async with db.execute("SELECT DISTINCT chat_id FROM group_users") as cur:
            rows = await cur.fetchall()

        sent_count = 0
        broadcast_text = (
            "📢 <b>ADMINISTRATSIYA E'LONI:</b>\n\n"
            f"<blockquote>{html.escape(clean_msg)}</blockquote>\n\n"
            "✨ <i>Detektiv Mafia jamoasi</i>"
        )
        for r in rows:
            cid = r["chat_id"]
            try:
                await context.bot.send_message(chat_id=cid, text=broadcast_text, parse_mode="HTML")
                sent_count += 1
            except Exception:
                pass

        resp = (
            "👑 <b>AI MASTER: GLOBAL XABAR YUBORILDI</b>\n\n"
            f"<blockquote>{html.escape(clean_msg)}</blockquote>\n\n"
            f"🚀 <b>Natija:</b> Xabar <b>{sent_count} ta</b> guruhga muvaffaqiyatli yetkazildi! ✨"
        )
        await msg.reply_text(resp, parse_mode="HTML")
        return True

    # 2. Timer Adjustment Intent (Tun, Kun, Ovoz, Sud, Lobby)
    # Supports: "tunni 30 qil", "tun 30", "30 tun", "tun vaqti 30", "sudni 20 qil", etc.
    time_match = re.search(r'(tun|kun|ovoz|sud|hukm|lobby|lobbi)(?:ni)?\s*(?:vaqti|vaqtini)?\s*(?:qil|bolsin|bo\'lsin|ornat|o\'rnat)?\s*[:=]?\s*(\d+)', text)
    if not time_match:
        time_match = re.search(r'(\d+)\s*(?:sekund|soniya|s)?\s*(tun|kun|ovoz|sud|hukm|lobby|lobbi)(?:ni)?', text)
        if time_match:
            sec_val, phase_word = int(time_match.group(1)), time_match.group(2)
        else:
            sec_val, phase_word = None, None
    else:
        phase_word, sec_val = time_match.group(1), int(time_match.group(2))

    if phase_word and sec_val:
        field_map = {
            "tun": ("default_night_seconds", "night_seconds", "Tun 🌙"),
            "kun": ("default_day_seconds", "day_seconds", "Kun ☀️"),
            "ovoz": ("default_vote_seconds", "vote_seconds", "Ovoz berish 🗳"),
            "sud": ("default_verdict_seconds", "verdict_seconds", "Sud (Hukm) ⚖️"),
            "hukm": ("default_verdict_seconds", "verdict_seconds", "Sud (Hukm) ⚖️"),
            "lobby": ("default_lobby_seconds", "lobby_seconds", "Lobby 🎮"),
            "lobbi": ("default_lobby_seconds", "lobby_seconds", "Lobby 🎮"),
        }
        cfg_key, sett_col, display_title = field_map[phase_word]
        await set_bot_config(cfg_key, str(sec_val))

        # Also update running games' settings
        for g in games.values():
            g.setdefault("settings", {})[sett_col] = sec_val

        resp = (
            "👑 <b>AI MASTER: VAQT SOZLAMASI YANGILANDI</b>\n\n"
            f"⏱ <b>Faza:</b> {display_title}\n"
            f"⚡ <b>Yangi vaqt:</b> <code>{sec_val} soniya</code>\n\n"
            "<blockquote>Ushbu yangi vaqt global konfiguratsiyaga saqlandi va "
            "barcha yangi hamda faol o'yinlarga darhol tatbiq etildi! ✨</blockquote>"
        )
        await msg.reply_text(resp, parse_mode="HTML")
        return True

    # 3. Role Toggle Intent (Yoqish / O'chirish / Reset)
    # Check for "barcha rollarni yoq" / "rollarni reset qil"
    if any(k in text for k in ("rollarni yoq", "barcha rollar", "rollarni tikla", "rollarni reset")):
        await set_bot_config("disabled_roles", "[]")
        resp = (
            "👑 <b>AI MASTER: ROLLIK TIZIM TIKLANDI</b>\n\n"
            "✅ <b>Barcha rollar to'liq faollashtirildi!</b>\n\n"
            "<blockquote>Hech bir rol o'chirilmagan holatga qaytarildi. ✨</blockquote>"
        )
        await msg.reply_text(resp, parse_mode="HTML")
        return True

    cand_role, cand_action = None, None
    m_role1 = re.search(r'([a-zA-Z\'`ʻ]+)\s*(?:rolini|roli)?\s*(o\'chir|ochir|yoq|qosh|qo\'sh|och|ishlat)', text)
    if m_role1 and resolve_role_name(m_role1.group(1)):
        cand_role, cand_action = m_role1.group(1), m_role1.group(2)
    else:
        m_role2 = re.search(r'(o\'chir|ochir|yoq|qosh|qo\'sh|och|ishlat)\s*(?:roli|rolini)?\s*([a-zA-Z\'`ʻ]+)', text)
        if m_role2 and resolve_role_name(m_role2.group(2)):
            cand_role, cand_action = m_role2.group(2), m_role2.group(1)

    if cand_role and cand_action:
        resolved_role = resolve_role_name(cand_role)
        if resolved_role:
            turn_on = cand_action in ("yoq", "qosh", "qo'sh", "och", "ishlat")
            cur_dis = await get_bot_config("disabled_roles", "[]")
            try:
                dis_list = set(json.loads(cur_dis))
            except Exception:
                dis_list = set()

            if turn_on:
                dis_list.discard(resolved_role)
                status_str = "YOQILDI (Faol)"
                emoji = "✅"
            else:
                dis_list.add(resolved_role)
                status_str = "O'CHIRILDI (O'yindan olib tashlandi)"
                emoji = "❌"

            await set_bot_config("disabled_roles", json.dumps(list(dis_list)))

            resp = (
                "👑 <b>AI MASTER: ROL NAZORATI</b>\n\n"
                f"{emoji} <b>Rol:</b> 🎭 <b>{resolved_role}</b>\n"
                f"⚡ <b>Holat:</b> <b>{status_str}</b>\n\n"
                f"<blockquote>Ushbu o'zgarish bot bazasida saqlandi. Yangi boshlanadigan "
                f"barcha o'yinlarda inobatga olinadi. 🪐</blockquote>"
            )
            await msg.reply_text(resp, parse_mode="HTML")
            return True

    # Clean up expired pending admin grants (older than 10 minutes)
    now_t = time.time()
    expired_grants = [t for t, g in pending_admin_grants.items() if now_t - g.get("created_at", 0) > 600]
    for exp_tok in expired_grants:
        pending_admin_grants.pop(exp_tok, None)

    has_grant_verb = any(v in text for v in GRANT_VERBS)

    # 4. Currency Grant Intent (Coin or Gold) - requires explicit grant verb
    if has_grant_verb and any(c in text for c in ("coin", "gold", "tanga", "oltin")):
        target_id, amount_val, curr_str = None, None, None
        give_match = re.search(r'(\d{7,15})\s*(?:ga)?\s*(\d+)\s*(coin|gold|tanga|oltin)', text)
        if not give_match:
            give_match = re.search(r'(\d+)\s*(coin|gold|tanga|oltin)\s*(?:ber|qo\'sh|qosh|tashla|grant)\s*(\d{7,15})', text)
            if give_match:
                amount_val = int(give_match.group(1))
                curr_str = give_match.group(2)
                target_id = int(give_match.group(3))
            else:
                give_match = re.search(r'(?:grant|ber|qo\'sh|qosh|tashla)\s*(\d{7,15})\s*(?:ga)?\s*(\d+)\s*(coin|gold|tanga|oltin)', text)
                if give_match:
                    target_id = int(give_match.group(1))
                    amount_val = int(give_match.group(2))
                    curr_str = give_match.group(3)
                else:
                    give_match = re.search(r'(?:grant|ber|qo\'sh|qosh|tashla)\s*(\d+)\s*(coin|gold|tanga|oltin)\s*(?:ga)?\s*(\d{7,15})', text)
                    if give_match:
                        amount_val = int(give_match.group(1))
                        curr_str = give_match.group(2)
                        target_id = int(give_match.group(3))
                    else:
                        give_match = re.search(r'(?:menga|mening hisobimga|hisobimga|o\'zimga)\s*(\d+)\s*(coin|gold|tanga|oltin)', text)
                        if not give_match:
                            give_match = re.search(r'(\d+)\s*(coin|gold|tanga|oltin)', text)
                        if give_match:
                            amount_val = int(give_match.group(1))
                            curr_str = give_match.group(2)
                            uid_m = re.search(r'(\d{7,15})', text)
                            target_id = int(uid_m.group(1)) if uid_m else user.id
        else:
            target_id = int(give_match.group(1))
            amount_val = int(give_match.group(2))
            curr_str = give_match.group(3)

        if target_id and amount_val and curr_str:
            if amount_val > MAX_CURRENCY_COUNT:
                await msg.reply_text(f"⚠️ Xatolik: Valyuta miqdori {MAX_CURRENCY_COUNT:,} dan oshmasligi kerak!")
                return True
            if amount_val <= 0:
                await msg.reply_text("⚠️ Xatolik: Miqdor musbat bo'lishi kerak!")
                return True

            currency = "gold" if curr_str in ("gold", "oltin") else "coin"
            token = uuid.uuid4().hex[:12]
            pending_admin_grants[token] = {
                "admin_id": user.id,
                "target_id": target_id,
                "kind": "currency",
                "currency": currency,
                "amount": amount_val,
                "created_at": time.time(),
            }

            curr_title = "Gold 🟡" if currency == "gold" else "Coin 💰"
            confirm_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_grant_confirm:{token}"),
                    InlineKeyboardButton("❌ Bekor qilish", callback_data=f"adm_grant_cancel:{token}")
                ]
            ])
            resp = (
                "👑 <b>AI MASTER: TASDIQLASH SO'ROVI</b>\n\n"
                f"👤 <b>Qabul qiluvchi:</b> <code>{target_id}</code>\n"
                f"💎 <b>Mablag':</b> +{amount_val} {curr_title}\n\n"
                "<blockquote>Haqiqatan ham ushbu mablag'ni o'tkazishni tasdiqlaysizmi? "
                "Amalni yakunlash uchun quyidagi tugmani bosing. ✨</blockquote>"
            )
            await msg.reply_text(resp, reply_markup=confirm_kb, parse_mode="HTML")
            return True

    # 5. Item / Inventory Grant Intent - requires explicit grant verb
    if has_grant_verb and any(k in text for k in ("himoya", "pichoq", "hujjat", "ruler_protection", "rose", "gul", "ruler")):
        item_key = None
        item_title = None
        if "himoya" in text:
            item_key, item_title = "protection", "🛡️ Tungi Himoya Qalqoni"
        elif "pichoq" in text:
            item_key, item_title = "revenge_knife", "🔪 Qasos Pichog'i"
        elif "hujjat" in text:
            item_key, item_title = "fake_document", "📄 Soxta Hujjat"
        elif "gul" in text or "rose" in text:
            item_key, item_title = "rose", "🌹 Sevgi Guli"
        elif "ruler" in text:
            item_key, item_title = "ruler_protection", "👑 Hukmdan Himoya"

        if item_key:
            uid_match = re.search(r'(\d{7,15})', text)
            tgt_uid = int(uid_match.group(1)) if uid_match else user.id

            count_val = 1
            explicit_ta = re.search(r'(\d+)\s*(?:ta|dona)', text)
            if explicit_ta:
                count_val = int(explicit_ta.group(1))
            else:
                nums = [int(n) for n in re.findall(r'\b\d+\b', text) if int(n) != tgt_uid]
                if nums:
                    count_val = nums[0]

            if count_val > MAX_ITEM_COUNT:
                await msg.reply_text(f"⚠️ Xatolik: Buyumlar soni {MAX_ITEM_COUNT} tadan oshmasligi kerak!")
                return True
            if count_val <= 0:
                await msg.reply_text("⚠️ Xatolik: Buyumlar soni musbat bo'lishi kerak!")
                return True

            token = uuid.uuid4().hex[:12]
            pending_admin_grants[token] = {
                "admin_id": user.id,
                "target_id": tgt_uid,
                "kind": "item",
                "item_key": item_key,
                "item_title": item_title,
                "count": count_val,
                "created_at": time.time(),
            }

            confirm_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_grant_confirm:{token}"),
                    InlineKeyboardButton("❌ Bekor qilish", callback_data=f"adm_grant_cancel:{token}")
                ]
            ])
            resp = (
                "👑 <b>AI MASTER: TASDIQLASH SO'ROVI</b>\n\n"
                f"👤 <b>Foydalanuvchi:</b> <code>{tgt_uid}</code>\n"
                f"📦 <b>Buyum:</b> {item_title} (x{count_val})\n\n"
                "<blockquote>Haqiqatan ham ushbu buyumni topshirishni tasdiqlaysizmi? "
                "Amalni yakunlash uchun quyidagi tugmani bosing. 🎒✨</blockquote>"
            )
            await msg.reply_text(resp, reply_markup=confirm_kb, parse_mode="HTML")
            return True

    # 6. Badge Grant Intent - requires explicit grant verb
    if ("badge" in text or "belgi" in text or "toji" in text or "nishon" in text) and has_grant_verb:
        badge_key = None
        badge_name = None
        if "toji" in text or "qirol" in text:
            badge_key, badge_name = "badge_crown", "👑 Qirol Toji"
        elif "yashin" in text:
            badge_key, badge_name = "badge_lightning", "⚡ Yashin belgisi"
        elif "detektiv" in text:
            badge_key, badge_name = "badge_mystery", "🕶️ Sirli Detektiv"
        elif "aniqchi" in text or "mergan" in text:
            badge_key, badge_name = "badge_sharpshooter", "🎯 Aniqchi"
        else:
            badge_key, badge_name = "badge_special", "✦ Maxsus belgi"

        uid_match = re.search(r'(\d{7,12})', text)
        tgt_uid = int(uid_match.group(1)) if uid_match else user.id

        await set_badge(tgt_uid, badge_key, badge_name, days=365)
        resp = (
            "👑 <b>AI MASTER: NISHON TOPSHIRILDI</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> <code>{tgt_uid}</code>\n"
            f"🎖️ <b>Nishon:</b> {badge_name}\n"
            "⏳ <b>Amal qilish muddati:</b> 365 kun (1 yil)\n\n"
            "<blockquote>Foydalanuvchining ismiga maxsus VIP nishon biriktirildi! 👑✨</blockquote>"
        )
        await msg.reply_text(resp, parse_mode="HTML")
        return True

    # 7. Direct Dynamic Config Key/Value Intent (set <key> <val> / get <key> / config)
    if text.startswith(("set ", "sozla ")):
        parts = raw_text.split(maxsplit=2)
        if len(parts) >= 3:
            c_key, c_val = parts[1].strip(), parts[2].strip()
            await set_bot_config(c_key, c_val)
            resp = (
                "👑 <b>AI MASTER: KONFIGURATSIYA SAQLANDI</b>\n\n"
                f"🔑 <b>Kalit:</b> <code>{html.escape(c_key)}</code>\n"
                f"📝 <b>Qiymat:</b> <code>{html.escape(c_val)}</code>\n\n"
                "<blockquote>Ushbu parametr bot bazasiga muvaffaqiyatli yozildi! 🚀</blockquote>"
            )
            await msg.reply_text(resp, parse_mode="HTML")
            return True

    if text.startswith(("get ", "kor ", "ko'r ")):
        parts = raw_text.split(maxsplit=1)
        if len(parts) >= 2:
            c_key = parts[1].strip()
            val = await get_bot_config(c_key, "")
            val_str = html.escape(val) if val else "<i>Mavjud emas</i>"
            resp = (
                "👑 <b>AI MASTER: KONFIGURATSIYA MA'LUMOTI</b>\n\n"
                f"🔑 <b>Kalit:</b> <code>{html.escape(c_key)}</code>\n"
                f"📝 <b>Hozirgi qiymat:</b> {val_str}"
            )
            await msg.reply_text(resp, parse_mode="HTML")
            return True

    if text in ("config", "konfiguratsiya", "sozlamalar royxati", "bot sozlamalari"):
        all_cfgs = await get_all_bot_configs()
        if not all_cfgs:
            await msg.reply_text("ℹ️ Hozirda maxsus bot konfiguratsiyalari saqlanmagan.")
            return True
        lines = ["⚙️ <b>BOT KONFIGURATSIYALARI RO'YXATI:</b>\n"]
        for k, v in all_cfgs.items():
            lines.append(f"• <code>{html.escape(k)}</code>: <code>{html.escape(str(v)[:100])}</code>")
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
        return True

    # 8. Active Games / Stop Intent
    if text in ("faol o'yinlar", "o'yinlar", "o'yinlar ro'yxati", "active games", "games", "lobbylar"):
        if not games and not lobbies:
            await msg.reply_text("ℹ️ Hozirda faol o'yinlar yoki ochiq lobbylar mavjud emas.")
            return True
        lines = ["🎮 <b>FAOL O'YINLAR VA LOBBYLAR:</b>\n"]
        for cid, g in games.items():
            alive = sum(1 for a in g.get("alive", {}).values() if a)
            lines.append(f"• O'yin: <code>{cid}</code> | Faza: <b>{g.get('phase')}</b> | Tiriklar: <b>{alive} ta</b>")
        for cid, lob in lobbies.items():
            lines.append(f"• Lobby: <code>{cid}</code> | Ishtirokchilar: <b>{len(lob.get('players', []))} ta</b>")
        lines.append("\nTo'xtatish uchun: <code>to'xtat &lt;chat_id&gt;</code> deb yozing.")
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
        return True

    if text.startswith(("to'xtat", "toxtat", "stop")):
        if "barcha" in text or "hammasi" in text or "all" in text:
            stopped = 0
            for cid in list(games.keys()):
                await abort_game(cid)
                stopped += 1
            for cid in list(lobbies.keys()):
                abort_lobby(cid)
                stopped += 1
            await msg.reply_text(f"🛑 Barcha ({stopped} ta) faol o'yinlar va lobbylar to'xtatildi.")
            return True

        cid_match = re.search(r'(-?\d{7,15})', text)
        if cid_match:
            target_chat = int(cid_match.group(1))
            lob = abort_lobby(target_chat)
            was_active = await abort_game(
                target_chat,
                reason="O'yin Master Admin tomonidan to'xtatildi.",
                context=context,
                notify_chat=True
            )
            if was_active:
                await msg.reply_text(f"✅ O'yin ({target_chat}) to'xtatildi.")
            elif lob:
                await msg.reply_text(f"✅ Lobby ({target_chat}) to'xtatildi.")
            else:
                await msg.reply_text(f"❌ Guruhda ({target_chat}) faol o'yin topilmadi.")
            return True

    # 9. System Diagnostics / Server Status Intent
    if any(k in text for k in ("holat", "statistika", "status", "server", "diagnostika", "ping")):
        db = await get_db()
        async with db.execute("SELECT COUNT(*) AS c FROM users") as cur:
            users_count = (await cur.fetchone())["c"]
        async with db.execute("SELECT COUNT(*) AS c FROM game_history") as cur:
            games_count = (await cur.fetchone())["c"]

        resp = (
            "👑 <b>AI MASTER: TIZIM DIAGNOSTIKASI</b>\n\n"
            "🟢 <b>Bot Holati:</b> <i>Online & Barqaror</i>\n"
            f"👥 <b>Foydalanuvchilar:</b> <code>{users_count} ta</code>\n"
            f"🏆 <b>O'ynalgan o'yinlar:</b> <code>{games_count} ta</code>\n"
            f"🎮 <b>Ayni paytdagi o'yinlar:</b> <code>{len(games)} ta</code>\n"
            f"🚪 <b>Ochiq lobbylar:</b> <code>{len(lobbies)} ta</code>\n\n"
            "<blockquote>Barcha tizimlar normal tartibda ishlamoqda. AI intellektual "
            "monitoring moduli faol. 🚀✨</blockquote>"
        )
        await msg.reply_text(resp, parse_mode="HTML")
        return True

    # 10. Generative Gemini AI query fallback if API key configured
    ai_gen = await query_gemini_ai(raw_text)
    if ai_gen:
        resp = (
            "🤖 <b>AI MASTER ASSISTENT:</b>\n\n"
            f"{html.escape(ai_gen)}\n\n"
            "<blockquote>Admin boshqaruv paneli: <b>/admin</b> | Sozlamalar: <b>/settings</b> 🪐</blockquote>"
        )
        await msg.reply_text(resp, parse_mode="HTML")
        return True

    # 11. General AI Help Fallback Menu
    resp = (
        "🤖 <b>AI MASTER ASSISTENT QABUL QILDI</b>\n\n"
        f"Buyrug'ingiz: <i>«{html.escape(raw_text)}»</i>\n\n"
        "✨ <b>Siz quyidagi amallarni bir zumda bajara olasiz:</b>\n"
        "• ⏱ <code>tunni 30 qil</code> / <code>kunni 60 qil</code> / <code>ovozni 30 qil</code>\n"
        "• 🎭 <code>Sherif rolini o'chir</code> / <code>donni yoq</code> / <code>rollarni reset</code>\n"
        "• 💰 <code>7651553630 ga 500 coin ber</code> / <code>10 gold ber</code>\n"
        "• 🛡️ <code>7651553630 ga 3 ta himoya ber</code> / <code>pichoq ber</code>\n"
        "• 👑 <code>7651553630 ga qirol toji ber</code> — Nishon topshirish\n"
        "• 📢 <code>broadcast: Sizning xabaringiz</code> — Barcha guruhlarga e'lon\n"
        "• ⚙️ <code>set welcome_text Salom!</code> / <code>get welcome_text</code>\n"
        "• 📊 <code>statistika</code> / <code>faol o'yinlar</code> / <code>to'xtat &lt;chat_id&gt;</code>\n\n"
        "<blockquote>Boshqaruv paneli uchun <b>/admin</b> yoki sozlamalar uchun <b>/settings</b> buyrug'ini yuboring. 🪐</blockquote>"
    )
    admin_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 Master Admin Paneli (/admin)", callback_data="adm:menu"),
            InlineKeyboardButton("⚙️ Sozlamalar (/settings)", callback_data="adm:config")
        ]
    ])
    await msg.reply_text(resp, reply_markup=admin_kb, parse_mode="HTML")
    return True
