import os
import logging
import asyncio
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

ARCHIVE_SEARCH_API = "https://archive.org/advancedsearch.php"
ARCHIVE_METADATA_API = "https://archive.org/metadata/"


def search_music(query: str) -> list:
    """Internet Archive katalogidan audio qidiradi."""

    params = {
        "q": f'({query}) AND mediatype:audio',
        "fl[]": ["identifier", "title", "creator"],
        "rows": 10,
        "page": 1,
        "output": "json",
    }

    response = requests.get(
        ARCHIVE_SEARCH_API,
        params=params,
        timeout=25,
    )
    response.raise_for_status()

    data = response.json()

    return data.get("response", {}).get("docs", [])


def get_audio_file(identifier: str) -> dict | None:
    """Audio fayllarini va foydalanish shartlarini tekshiradi."""

    response = requests.get(
        ARCHIVE_METADATA_API + identifier,
        timeout=25,
    )
    response.raise_for_status()

    data = response.json()
    files = data.get("files", [])

    for file_info in files:
        name = file_info.get("name", "")
        lower_name = name.lower()

        if not lower_name.endswith((".mp3", ".ogg", ".m4a", ".flac")):
            continue

        # Faqat oddiy, yuklab olinadigan fayllarni ko'rib chiqamiz.
        if file_info.get("private") == "true":
            continue

        if file_info.get("source") == "metadata":
            continue

        return {
            "name": name,
            "size": file_info.get("size"),
            "url": (
                f"https://archive.org/download/"
                f"{identifier}/{requests.utils.quote(name, safe='/')}"
            ),
        }

    return None


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "Assalomu alaykum! 🎵\n\n"
        "Men bepul audio katalogidan musiqa qidiraman.\n\n"
        "Qidirish uchun:\n"
        "/play qo'shiq nomi\n\n"
        "Masalan:\n"
        "/play classical piano"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🎵 Musiqa qidirish:\n\n"
        "/play qo'shiq nomi\n\n"
        "Yoki qo'shiq nomini oddiy xabar qilib yuboring.\n\n"
        "Eslatma: katalogda barcha qo'shiqlar mavjud emas."
    )


async def send_audio(
    update: Update,
    query: str,
):
    message = update.effective_message

    if not query.strip():
        await message.reply_text(
            "Qo'shiq nomini yozing.\n"
            "Masalan: /play classical piano"
        )
        return

    status = await message.reply_text(
        f"🔎 Qidirilmoqda: {query}\n"
        "Iltimos, kuting..."
    )

    try:
        results = await asyncio.to_thread(search_music, query)

        if not results:
            await status.edit_text(
                "😕 Audio topilmadi. Boshqa nom bilan urinib ko'ring."
            )
            return

        for item in results:
            identifier = item.get("identifier")

            if not identifier:
                continue

            audio = await asyncio.to_thread(
                get_audio_file,
                identifier,
            )

            if not audio:
                continue

            size = audio.get("size")

            # Juda katta fayllarni yuklashga urinmaymiz.
            if size and int(size) > 45 * 1024 * 1024:
                continue

            await status.edit_text(
                f"⬇️ Audio tayyorlanmoqda:\n"
                f"{item.get('title', 'Noma’lum audio')}"
            )

            file_response = await asyncio.to_thread(
                requests.get,
                audio["url"],
                timeout=60,
                stream=True,
            )

            file_response.raise_for_status()

            content_type = file_response.headers.get(
                "Content-Type", ""
            ).lower()

            if "text/html" in content_type:
                file_response.close()
                continue

            temp_path = "/tmp/music_bot_audio"

            try:
                with open(temp_path, "wb") as file:
                    for chunk in file_response.iter_content(
                        chunk_size=64 * 1024
                    ):
                        if chunk:
                            file.write(chunk)

                file_response.close()

                if os.path.getsize(temp_path) == 0:
                    continue

                title = item.get("title", "Audio")
                creator = item.get("creator", "Noma'lum ijrochi")

                with open(temp_path, "rb") as audio_file:
                    await message.reply_audio(
                        audio=audio_file,
                        title=str(title)[:64],
                        performer=str(creator)[:64],
                        caption="🎵 Internet Archive audio katalogi",
                    )

                await status.delete()
                return

            finally:
                file_response.close()

                if os.path.exists(temp_path):
                    os.remove(temp_path)

        await status.edit_text(
            "😕 Yuborish mumkin bo'lgan audio topilmadi.\n"
            "Boshqa so'zlar bilan qidirib ko'ring."
        )

    except requests.exceptions.RequestException:
        logger.exception("Audio qidirish yoki yuklash xatosi")

        await status.edit_text(
            "🌐 Audio xizmatiga ulanishda xato yuz berdi. "
            "Keyinroq qayta urinib ko'ring."
        )

    except Exception:
        logger.exception("Kutilmagan xato")

        await status.edit_text(
            "⚠️ Xatolik yuz berdi. Hosting loglarini tekshiring."
        )


async def play_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = " ".join(context.args).strip()
    await send_audio(update, query)


async def text_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.effective_message.text.strip()
    await send_audio(update, query)


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Telegram bot xatosi",
        exc_info=context.error,
    )


def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN yoki TELEGRAM_BOT_TOKEN "
            "hosting sozlamalarida topilmadi."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("play", play_command))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_search,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("Musiqa bot ishga tushdi.")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
