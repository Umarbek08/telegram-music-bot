import os
import logging
import asyncio
import tempfile
import requests

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
AUDD_TOKEN = os.getenv("AUDD_API_TOKEN")

AUDD_URL = "https://api.audd.io/"


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🎵 Assalomu alaykum!\n\n"
        "Men musiqani aniqlovchi botman.\n\n"
        "🎤 Ovozli xabar yuboring.\n"
        "🎶 MP3 yoki audio fayl yuboring.\n"
        "🎬 Musiqa bor video yuboring.\n"
        "🔎 Yoki qo'shiq nomini yozing.\n\n"
        "Qo'shiqni aniqlash uchun /identify buyrug'idan "
        "ham foydalanishingiz mumkin."
    )


async def identify_audio(
    file_url: str = None,
    file_path: str = None,
    query: str = None,
):
    """AudD xizmatiga audio yoki qo'shiq nomini yuboradi."""

    data = {
        "api_token": AUDD_TOKEN,
        "return": "apple_music,spotify",
    }

    files = None

    try:
        if file_path:
            audio_file = open(file_path, "rb")
            files = {"file": audio_file}

            response = await asyncio.to_thread(
                requests.post,
                AUDD_URL,
                data=data,
                files=files,
                timeout=60,
            )

            audio_file.close()

        elif file_url:
            data["url"] = file_url

            response = await asyncio.to_thread(
                requests.post,
                AUDD_URL,
                data=data,
                timeout=60,
            )

        elif query:
            data["q"] = query

            response = await asyncio.to_thread(
                requests.post,
                AUDD_URL,
                data=data,
                timeout=30,
            )

        else:
            return None

        response.raise_for_status()
        result = response.json()

        if result.get("status") != "success":
            logger.warning("AudD javobi: %s", result)
            return None

        return result.get("result")

    finally:
        if files:
            for item in files.values():
                if not item.closed:
                    item.close()


async def handle_identification(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not AUDD_TOKEN:
        await message.reply_text(
            "⚠️ AudD API kaliti sozlanmagan. "
            "FadeHost Environment Variables bo'limida "
            "AUDD_API_TOKEN qiymatini tekshiring."
        )
        return

    audio_file = (
        message.audio
        or message.voice
        or message.video
        or message.document
        or message.video_note
    )

    if not audio_file:
        await message.reply_text(
            "🎵 Ovozli xabar, audio yoki video yuboring."
        )
        return

    status = await message.reply_text(
        "🔍 Musiqa aniqlanmoqda. Biroz kuting..."
    )

    temp_path = None

    try:
        telegram_file = await context.bot.get_file(
            audio_file.file_id
        )

        suffix = ".dat"

        if message.audio and message.audio.file_name:
            suffix = os.path.splitext(
                message.audio.file_name
            )[1] or ".dat"

        elif message.document and message.document.file_name:
            suffix = os.path.splitext(
                message.document.file_name
            )[1] or ".dat"

        elif message.voice:
            suffix = ".ogg"

        elif message.video or message.video_note:
            suffix = ".mp4"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name

        await telegram_file.download_to_drive(
            custom_path=temp_path
        )

        result = await identify_audio(file_path=temp_path)

        if not result:
            await status.edit_text(
                "😕 Qo'shiqni aniqlay olmadim.\n"
                "Musiqa aniq eshitiladigan qismini yuborib ko'ring."
            )
            return

        title = result.get("title", "Noma'lum qo'shiq")
        artist = result.get("artist", "Noma'lum ijrochi")
        album = result.get("album", "Noma'lum albom")
        release_date = result.get("release_date", "")

        text = (
            "✅ Qo'shiq aniqlandi!\n\n"
            f"🎵 Nomi: {title}\n"
            f"👤 Ijrochi: {artist}\n"
            f"💿 Albom: {album}"
        )

        if release_date:
            text += f"\n📅 Chiqqan sana: {release_date}"

        apple_music = result.get("apple_music", {})
        if isinstance(apple_music, dict):
            url = apple_music.get("url")
            if url:
                text += f"\n🔗 Tinglash: {url}"

        spotify = result.get("spotify", {})
        if isinstance(spotify, dict):
            external_urls = spotify.get("external_urls", {})
            url = external_urls.get("spotify")
            if url:
                text += f"\n🎧 Spotify: {url}"

        await status.edit_text(
            text,
            disable_web_page_preview=True,
        )

    except requests.exceptions.Timeout:
        await status.edit_text(
            "⏳ Xizmat javobi kechikdi. Keyinroq urinib ko'ring."
        )

    except requests.exceptions.RequestException:
        logger.exception("AudD API yoki tarmoq xatosi")
        await status.edit_text(
            "🌐 Xizmatga ulanishda xato yuz berdi."
        )

    except Exception:
        logger.exception("Audio aniqlashda xato")
        await status.edit_text(
            "⚠️ Xatolik yuz berdi. FadeHost loglarini tekshiring."
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


async def identify_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🎤 Qo'shiq yozilgan audio yoki videoni yuboring. "
        "Men uni aniqlashga harakat qilaman."
    )


async def text_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    query = message.text.strip()

    if not AUDD_TOKEN:
        await message.reply_text(
            "⚠️ AUDD_API_TOKEN sozlanmagan."
        )
        return

    status = await message.reply_text(
        f"🔎 Qo'shiq qidirilmoqda: {query}"
    )

    try:
        result = await identify_audio(query=query)

        if not result:
            await status.edit_text(
                "😕 Qo'shiq topilmadi yoki matn bo'yicha "
                "qidiruv xizmatda mavjud emas.\n"
                "Musiqaning audio yoki video parchasini yuboring."
            )
            return

        title = result.get("title", "Noma'lum qo'shiq")
        artist = result.get("artist", "Noma'lum ijrochi")

        text = (
            "🎵 Natija:\n\n"
            f"Qo'shiq: {title}\n"
            f"Ijrochi: {artist}"
        )

        apple_music = result.get("apple_music", {})
        if isinstance(apple_music, dict) and apple_music.get("url"):
            text += f"\n🔗 {apple_music['url']}"

        await status.edit_text(
            text,
            disable_web_page_preview=True,
        )

    except requests.exceptions.RequestException:
        logger.exception("Matn qidiruvida tarmoq xatosi")
        await status.edit_text(
            "🌐 Qidiruv xizmatiga ulanishda xato."
        )

    except Exception:
        logger.exception("Matn qidiruvida xato")
        await status.edit_text(
            "⚠️ Qidiruvda xato yuz berdi."
        )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🎵 Botdan foydalanish:\n\n"
        "1. Ovozli xabar yuboring.\n"
        "2. MP3 yoki audio fayl yuboring.\n"
        "3. Musiqa bor video yuboring.\n"
        "4. Qo'shiq nomini yozib ko'ring.\n\n"
        "/start — boshlash\n"
        "/identify — musiqani aniqlash\n"
        "/help — yordam"
    )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Kutilmagan xato",
        exc_info=context.error,
    )


def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN yoki TELEGRAM_BOT_TOKEN topilmadi."
        )

    if not AUDD_TOKEN:
        raise RuntimeError(
            "AUDD_API_TOKEN topilmadi. "
            "FadeHost Environment Variables bo'limini tekshiring."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("identify", identify_command))

    app.add_handler(
        MessageHandler(
            filters.AUDIO
            | filters.VOICE
            | filters.VIDEO
            | filters.VIDEO_NOTE
            | filters.Document.AUDIO
            | filters.Document.VIDEO,
            handle_identification,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_search,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("Musiqa aniqlovchi bot ishga tushdi.")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
