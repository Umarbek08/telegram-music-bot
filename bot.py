import os
import asyncio
import logging
import tempfile
from pathlib import Path

import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==========================================
# SOZLAMALAR
# ==========================================

BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
)

AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN")

ITUNES_URL = "https://itunes.apple.com/search"
AUDD_URL = "https://api.audd.io/"

MAX_FILE_SIZE = 10 * 1024 * 1024

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Qidiruv natijalarini vaqtincha saqlash
search_results = {}


# ==========================================
# ITUNES ORQALI MATNLI QIDIRUV
# ==========================================

def search_songs(query: str, limit: int = 7):
    """Qo'shiq nomi yoki ijrochi bo'yicha qidiradi."""

    params = {
        "term": query,
        "entity": "song",
        "limit": limit,
        "country": "UZ",
    }

    response = requests.get(
        ITUNES_URL,
        params=params,
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()

    songs = []

    for item in data.get("results", []):
        if item.get("kind") != "song":
            continue

        songs.append({
            "id": item.get("trackId"),
            "title": item.get("trackName", "Noma'lum qo'shiq"),
            "artist": item.get("artistName", "Noma'lum ijrochi"),
            "album": item.get("collectionName", ""),
            "preview": item.get("previewUrl"),
            "url": item.get("trackViewUrl"),
        })

    return songs


# ==========================================
# AUDD ORQALI OVOZDAN QO'SHIQNI ANIQLASH
# ==========================================

def recognize_song(file_path: str):
    """Audio fayl orqali qo'shiqni aniqlaydi."""

    if not AUDD_API_TOKEN:
        return {
            "error": (
                "AudD API kaliti sozlanmagan. "
                "FadeHost Environment Variables bo'limini tekshiring."
            )
        }

    with open(file_path, "rb") as audio_file:
        response = requests.post(
            AUDD_URL,
            data={
                "api_token": AUDD_API_TOKEN,
                "return": "apple_music,spotify",
            },
            files={
                "file": (
                    Path(file_path).name,
                    audio_file,
                )
            },
            timeout=60,
        )

    response.raise_for_status()
    data = response.json()

    if data.get("status") != "success":
        logger.warning("AudD API muvaffaqiyatsiz javob qaytardi.")
        return {
            "error": (
                "AudD qo'shiqni aniqlay olmadi. "
                "Boshqa, tiniqroq audio yuboring."
            )
        }

    result = data.get("result")

    if not result:
        return None

    return {
        "title": result.get("title", "Noma'lum"),
        "artist": result.get("artist", "Noma'lum"),
        "album": result.get("album", ""),
        "release_date": result.get("release_date", ""),
        "song_link": result.get("song_link", ""),
        "spotify": (
            result.get("spotify", {}).get("external_urls", {}).get("spotify", "")
            if isinstance(result.get("spotify"), dict)
            else ""
        ),
    }


# ==========================================
# /START
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "🎵 Assalomu alaykum!\n\n"
        "Men Musiqa qidiruvchi botman.\n\n"
        "🔎 Qo'shiq nomini yoki ijrochi ismini yozing.\n"
        "🎤 Qo'shiq yozilgan ovozli xabar yuboring.\n"
        "🎧 Audio fayl yuboring.\n\n"
        "Misollar:\n"
        "• Konsta Odamlar\n"
        "• Jaloliddin Ahmadaliyev\n"
        "• Yor-yor\n\n"
        "Qo'shiqni birgalikda topamiz!"
    )

    await update.effective_message.reply_text(text)


# ==========================================
# /HELP
# ==========================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "📌 Botdan foydalanish:\n\n"
        "1. Qo'shiq nomini yozing.\n"
        "2. Ijrochi nomini yozing.\n"
        "3. Qo'shiqdan parcha yozilgan audio yuboring.\n\n"
        "Bot qidiruv natijalarini ko'rsatadi.\n"
        "Audio namunasi mavjud bo'lsa, uni ham yuboradi."
    )


# ==========================================
# MATN ORQALI QIDIRISH
# ==========================================

async def text_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = (update.effective_message.text or "").strip()

    if not query:
        return

    if query.startswith("/"):
        return

    if len(query) > 200:
        await update.effective_message.reply_text(
            "Iltimos, qidiruv so'zini qisqaroq yozing."
        )
        return

    status = await update.effective_message.reply_text(
        "🔎 Qo'shiq qidirilmoqda..."
    )

    try:
        songs = await asyncio.to_thread(search_songs, query)

        if not songs:
            await status.edit_text(
                "😕 Bu nom bilan qo'shiq topilmadi.\n\n"
                "Qo'shiq nomini yoki ijrochi ismini boshqacha yozib ko'ring."
            )
            return

        chat_id = update.effective_chat.id

        keyboard = []

        for song in songs:
            track_id = song.get("id")

            if not track_id:
                continue

            search_results[(chat_id, str(track_id))] = song

            keyboard.append([
                InlineKeyboardButton(
                    text=f"🎵 {song['title']} — {song['artist']}",
                    callback_data=f"song:{track_id}",
                )
            ])

        message = (
            f"🎶 Qidiruv natijalari: {query}\n\n"
            "Kerakli qo'shiqni tanlang:"
        )

        await status.edit_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except requests.Timeout:
        await status.edit_text(
            "⏳ Qidiruv vaqti tugadi. Birozdan keyin qayta urinib ko'ring."
        )

    except requests.RequestException:
        logger.exception("iTunes qidiruvida tarmoq xatosi")

        await status.edit_text(
            "⚠️ Qidiruv xizmatiga ulanishda xatolik yuz berdi."
        )

    except Exception:
        logger.exception("Matnli qidiruvda xatolik")

        await status.edit_text(
            "⚠️ Kutilmagan xatolik yuz berdi. Keyinroq urinib ko'ring."
        )


# ==========================================
# TANLANGAN QO'SHIQNI YUBORISH
# ==========================================

async def selected_song(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    if not query.message:
        return

    try:
        track_id = query.data.split(":", 1)[1]

        chat_id = query.message.chat_id

        song = search_results.get((chat_id, track_id))

        if not song:
            await query.message.reply_text(
                "Bu natija eskirgan. Qo'shiq nomini qaytadan qidiring."
            )
            return

        title = song["title"]
        artist = song["artist"]
        album = song.get("album", "")
        preview = song.get("preview")
        song_url = song.get("url")

        details = (
            f"🎵 Qo'shiq: {title}\n"
            f"🎤 Ijrochi: {artist}\n"
        )

        if album:
            details += f"💿 Albom: {album}\n"

        if song_url:
            details += f"\n🔗 Tinglash: {song_url}"

        await query.message.reply_text(details)

        if not preview:
            await query.message.reply_text(
                "Bu qo'shiq uchun audio namunasi mavjud emas.\n"
                "Tinglash havolasidan foydalanishingiz mumkin."
                if song_url
                else "Bu qo'shiq uchun audio namunasi yoki havola topilmadi."
            )
            return

        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.UPLOAD_AUDIO,
        )

        await query.message.reply_text(
            "⏳ Qo'shiqning mavjud audio namunasi olinmoqda..."
        )

        def download_preview():
            response = requests.get(
                preview,
                timeout=30,
                stream=True,
            )

            response.raise_for_status()

            with tempfile.NamedTemporaryFile(
                suffix=".m4a",
                delete=False,
            ) as temp:
                for chunk in response.iter_content(64 * 1024):
                    if chunk:
                        temp.write(chunk)

                return temp.name

        temp_path = await asyncio.to_thread(download_preview)

        try:
            with open(temp_path, "rb") as audio:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    title=title,
                    performer=artist,
                    filename=f"{title[:60]}.m4a",
                    caption=(
                        "🎧 Audio namuna\n"
                        "To'liq qo'shiq uchun rasmiy tinglash "
                        "havolasidan foydalaning."
                    ),
                )
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    except Exception:
        logger.exception("Tanlangan qo'shiqni yuborishda xatolik")

        await query.message.reply_text(
            "⚠️ Audio namunani yuborib bo'lmadi. "
            "Qo'shiqning tinglash havolasidan foydalaning."
        )


# ==========================================
# AUDIO YOKI OVOZLI XABARNI ANIQLASH
# ==========================================

async def identify_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    media = (
        message.audio
        or message.voice
        or message.video
        or message.video_note
        or message.document
    )

    if not media:
        return

    mime_type = getattr(media, "mime_type", None) or ""

    if (
        message.document
        and not mime_type.startswith("audio/")
        and not mime_type.startswith("video/")
    ):
        await message.reply_text(
            "Iltimos, audio yoki video fayl yuboring."
        )
        return

    file_size = getattr(media, "file_size", None)

    if file_size and file_size > MAX_FILE_SIZE:
        await message.reply_text(
            "⚠️ Fayl 10 MB dan katta. "
            "Qisqaroq audio yuborib ko'ring."
        )
        return

    if not AUDD_API_TOKEN:
        await message.reply_text(
            "⚠️ Ovozdan qo'shiqni aniqlash xizmati sozlanmagan.\n"
            "FadeHost'dagi AUDD_API_TOKEN qiymatini tekshiring."
        )
        return

    status = await message.reply_text(
        "🎧 Audioni tekshiryapman..."
    )

    temp_path = None

    try:
        telegram_file = await context.bot.get_file(media.file_id)

        with tempfile.NamedTemporaryFile(
            suffix=".audio",
            delete=False,
        ) as temp:
            temp_path = temp.name

        await telegram_file.download_to_drive(custom_path=temp_path)

        if os.path.getsize(temp_path) > MAX_FILE_SIZE:
            await status.edit_text(
                "⚠️ Fayl 10 MB dan katta. Kichikroq audio yuboring."
            )
            return

        result = await asyncio.to_thread(
            recognize_song,
            temp_path,
        )

        if not result:
            await status.edit_text(
                "😕 Qo'shiqni aniqlay olmadim.\n\n"
                "Tiniqroq, shovqinsiz 10–20 soniyalik parcha yuboring."
            )
            return

        if result.get("error"):
            await status.edit_text(
                "⚠️ " + result["error"]
            )
            return

        title = result.get("title", "Noma'lum")
        artist = result.get("artist", "Noma'lum")
        album = result.get("album", "")
        song_link = result.get("song_link")
        spotify = result.get("spotify")

        text = (
            "✅ Qo'shiq aniqlandi!\n\n"
            f"🎵 Nomi: {title}\n"
            f"🎤 Ijrochi: {artist}\n"
        )

        if album:
            text += f"💿 Albom: {album}\n"

        if song_link:
            text += f"\n🔗 Tinglash: {song_link}"

        if spotify:
            text += f"\n🎧 Spotify: {spotify}"

        await status.edit_text(text)

    except requests.Timeout:
        await status.edit_text(
            "⏳ Aniqlash xizmati javob bermadi. Qayta urinib ko'ring."
        )

    except requests.RequestException:
        logger.exception("AudD tarmoq xatosi")

        await status.edit_text(
            "⚠️ Qo'shiqni aniqlash xizmatiga ulanishda xatolik."
        )

    except Exception:
        logger.exception("Audio tahlilida xatolik")

        await status.edit_text(
            "⚠️ Audio faylni tekshirishda xatolik yuz berdi."
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# ==========================================
# XATOLARNI LOGGA YOZISH
# ==========================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Botda xatolik yuz berdi",
        exc_info=context.error,
    )


# ==========================================
# BOTNI ISHGA TUSHIRISH
# ==========================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN yoki TELEGRAM_BOT_TOKEN sozlanmagan!"
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        CallbackQueryHandler(
            selected_song,
            pattern=r"^song:\d+$",
        )
    )

    app.add_handler(
        MessageHandler(
            filters.AUDIO
            | filters.VOICE
            | filters.VIDEO
            | filters.VIDEO_NOTE
            | filters.Document.AUDIO
            | filters.Document.VIDEO,
            identify_audio,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_search,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("Musiqa qidiruvchi bot ishga tushmoqda...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
