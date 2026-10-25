import os
import logging
from typing import Optional
from telegram import Bot

log = logging.getLogger("detektiv.audio")

# Tovushli signallar (ortiqcha chiziqlar va sun'iy belgilarsiz)
SOUND_ICONS = {
    "night": "",
    "murder": "",
    "verdict": "",
    "morning": "",
    "saved": "",
    "voting": "",
    "execution": "",
}

async def _safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup=None,
    parse_mode: Optional[str] = "Markdown"
):
    """Safely deliver message with Markdown formatting, falling back to plain text if syntax fails."""
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        if parse_mode:
            log.warning("send_message with parse_mode=%s failed (%s), falling back to plain text", parse_mode, e)
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=None
            )
        raise e

async def send_atmospheric_message(
    bot: Bot,
    chat_id: int,
    text: str,
    sound_type: Optional[str] = None,
    photo_path: Optional[str] = None,
    voice_path: Optional[str] = None,
    audio_path: Optional[str] = None,
    reply_markup = None,
    parse_mode: Optional[str] = "Markdown"
):
    """Send game announcements accompanied by sound tags and optional cinematic imagery.

    Guarantees:
      - Always ensures full, complete, easily readable text is delivered.
      - If user has audio disabled or cannot hear voice clips, the full text is 100% visible and clear.
      - Dispatches voice or audio notes safely without blocking or dropping text announcements.
      - If photo caption exceeds Telegram's 1024-char limit, delivers full announcement text via send_message
        so no game narrative or forensic clues are ever truncated.
      - Applies clean aesthetic Markdown formatting with automatic error-recovery fallback.
    """
    if voice_path and os.path.exists(voice_path):
        try:
            with open(voice_path, "rb") as vf:
                await bot.send_voice(chat_id=chat_id, voice=vf)
        except Exception as e:
            log.warning("Could not dispatch voice note %s: %s", voice_path, e)
    elif audio_path and os.path.exists(audio_path):
        try:
            with open(audio_path, "rb") as af:
                await bot.send_audio(chat_id=chat_id, audio=af)
        except Exception as e:
            log.warning("Could not dispatch audio file %s: %s", audio_path, e)

    full_text = text
    cue = SOUND_ICONS.get(sound_type, "") if sound_type else ""
    if cue:
        full_text = f"{cue}\n\n{text}"

    if photo_path and os.path.exists(photo_path):
        try:
            with open(photo_path, "rb") as photo:
                if len(full_text) <= 1024:
                    try:
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=full_text,
                            reply_markup=reply_markup,
                            parse_mode=parse_mode
                        )
                        return
                    except Exception as pe:
                        log.warning("send_photo with parse_mode failed (%s), retrying without parse_mode", pe)
                        photo.seek(0)
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=full_text,
                            reply_markup=reply_markup,
                            parse_mode=None
                        )
                        return
                else:
                    sound_cue = SOUND_ICONS.get(sound_type, "🎬 *O'YIN YANGILANISHI*")
                    try:
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=sound_cue,
                            parse_mode=parse_mode
                        )
                    except Exception:
                        photo.seek(0)
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=sound_cue,
                            parse_mode=None
                        )
                    await _safe_send_message(
                        bot=bot,
                        chat_id=chat_id,
                        text=full_text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
                    return
        except Exception as e:
            log.warning("Could not send photo %s: %s. Falling back to plain text.", photo_path, e)

    await _safe_send_message(
        bot=bot,
        chat_id=chat_id,
        text=full_text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )
