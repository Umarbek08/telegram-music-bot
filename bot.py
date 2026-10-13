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

# Loglarni sozlash
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Telegram tokeni hostingdagi Environment Variables orqali olinadi
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

# Apple iTunes qidiruv API manzili
ITUNES_API = "https://itunes.apple.com/search"


def search_music(query: str) -> list:
    """Apple iTunes katalogidan qo'shiqlarni qidiradi."""

    params = {
        "term": query,
        "entity": "song",
        "media": "music",
        "limit": 5,
        "country": "US",
    }

    response = requests.get(
        ITUNES_API,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return data.get("results", [])


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Botning boshlang'ich xabari."""

    message = (
        "Assalomu alaykum! 🎵\n\n"
        "Men musiqa qidiruvchi botman.\n\n"
        "🔎 Qo'shiqni qidirish uchun:\n"
        "/play Adele Hello\n\n"
        "Yoki shunchaki qo'shiq nomini yozing.\n\n"
        "📌 /help — yordam"
    )

    await update.effective_message.reply_text(message)


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Yordam xabari."""

    message = (
        "🎵 MUSIQA BOTI — YORDAM\n\n"
        "Qo'shiq qidirish:\n"
        "/play Adele Hello\n\n"
        "Yoki qo'shiq nomi va ijrochisini oddiy xabar "
        "sifatida yuboring.\n\n"
        "Bot qo'shiq nomini, ijrochisini va mavjud "
        "havolalarini ko'rsatadi.\n\n"
        "Eslatma: ayrim qo'shiqlarda audio namuna "
        "bo'lmasligi mumkin."
    )

    await update.effective_message.reply_text(message)


async def send_music_results(
    update: Update,
    query: str,
) -> None:
    """Qidiruv natijalarini foydalanuvchiga yuboradi."""

    message = update.effective_message

    if not query.strip():
        await message.reply_text(
            "Qo'shiq nomini yozing.\n"
            "Masalan: /play Adele Hello"
        )
        return

    await message.reply_text(
        f"🔎 Qidirilmoqda: {query}\n"
        "Iltimos, biroz kuting..."
    )

    try:
        # Sinxron HTTP so'rovni alohida oqimda bajarish
        results = await asyncio.to_thread(search_music, query)

    except requests.exceptions.Timeout:
        logger.warning("Musiqa qidiruvi vaqti tugadi.")

        await message.reply_text(
            "⏳ Qidiruv vaqti tugadi. "
            "Iltimos, yana urinib ko'ring."
        )
        return

    except requests.exceptions.RequestException:
        logger.exception("iTunes API bilan bog'lanishda xato.")

        await message.reply_text(
            "🌐 Musiqa xizmatiga ulanib bo'lmadi. "
            "Birozdan keyin qayta urinib ko'ring."
        )
        return

    except (ValueError, TypeError):
        logger.exception("Qidiruv javobini o'qishda xato.")

        await message.reply_text(
            "Javobni o'qishda xato yuz berdi. "
            "Qayta urinib ko'ring."
        )
        return

    if not results:
        await message.reply_text(
            "😕 Bu qo'shiq topilmadi.\n"
            "Boshqa nom yoki ijrochi nomini yozib ko'ring."
        )
        return

    for index, track in enumerate(results, start=1):
        title = track.get("trackName", "Noma'lum qo'shiq")
        artist = track.get("artistName", "Noma'lum ijrochi")
        album = track.get("collectionName", "Noma'lum albom")
        track_url = track.get("trackViewUrl")
        preview_url = track.get("previewUrl")

        text = (
            f"🎵 Natija {index}\n\n"
            f"🎶 Qo'shiq: {title}\n"
            f"👤 Ijrochi: {artist}\n"
            f"💿 Albom: {album}"
        )

        if track_url:
            text += f"\n🔗 Tinglash sahifasi: {track_url}"

        if preview_url:
            text += f"\n▶️ Qisqa audio namuna: {preview_url}"

        await message.reply_text(
            text,
            disable_web_page_preview=True,
        )


async def play_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """ /play buyrug'i orqali qidirish."""

    query = " ".join(context.args).strip()

    await send_music_results(update, query)


async def text_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Oddiy matn yuborilganda qidirish."""

    query = update.effective_message.text.strip()

    await send_music_results(update, query)


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Kutilmagan xatolarni logga yozadi."""

    logger.error(
        "Kutilmagan xato yuz berdi.",
        exc_info=context.error,
    )


def main() -> None:
    """Botni ishga tushiradi."""

    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. Hosting sozlamalarida "
            "BOT_TOKEN yoki TELEGRAM_BOT_TOKEN ni kiriting."
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

    logger.info("Musiqa bot ishga tushmoqda...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
