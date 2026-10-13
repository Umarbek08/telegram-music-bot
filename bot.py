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

# ==============================
# SOZLAMALAR
# ==============================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
)

JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "")

JAMENDO_API = "https://api.jamendo.com/v3.0/tracks/"


# ==============================
# INTERNETDAN MUSIQA QIDIRISH
# ==============================

def search_jamendo(query: str) -> list:
    """Jamendo katalogidan musiqa qidiradi."""

    if not JAMENDO_CLIENT_ID:
        raise RuntimeError(
            "JAMENDO_CLIENT_ID sozlanmagan."
        )

    params = {
        "client_id": JAMENDO_CLIENT_ID,
        "format": "json",
        "limit": 5,
        "namesearch": query,
        "audioformat": "mp31",
    }

    response = requests.get(
        JAMENDO_API,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("headers", {}).get("status") != "success":
        logger.error("Jamendo API javobi: %s", data)
        raise RuntimeError("Musiqa xizmati xatolik qaytardi.")

    return data.get("results", [])


# ==============================
# /START
# ==============================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🎵 Assalomu alaykum!\n"
        "Men Music Uz Botman.\n\n"
        "🌐 Internetdan musiqa qidirish:\n"
        "/play jazz\n"
        "/audio piano\n\n"
        "📋 /help — yordam\n\n"
        "Men Jamendo katalogidan "
        "musiqalarni qidirib topaman."
    )


# ==============================
# /HELP
# ==============================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🎶 MUSIC UZ BOT — YORDAM\n\n"
        "/start — botni boshlash\n"
        "/play jazz — internetdan musiqa qidirish\n"
        "/audio piano — musiqa qidirish\n"
        "/help — yordam\n\n"
        "Masalan:\n"
        "/play relaxing music\n"
        "/audio classical piano\n\n"
        "Eslatma: katalogda barcha mashhur "
        "qo‘shiqlar mavjud bo‘lmasligi mumkin."
    )


# ==============================
# QIDIRUV NATIJALARINI CHIQARISH
# ==============================

async def perform_search(
    update: Update,
    query: str,
):
    message = update.effective_message

    status_message = await message.reply_text(
        f"🔎 Internetdan qidiryapman: {query}"
    )

    try:
        tracks = await asyncio.to_thread(
            search_jamendo,
            query,
        )

        if not tracks:
            await status_message.edit_text(
                "😕 Bu nom bilan musiqa topilmadi.\n"
                "Boshqa nom bilan urinib ko‘ring."
            )
            return

        results = []

        for index, track in enumerate(tracks, start=1):
            title = track.get("name") or "Nomsiz"
            artist = track.get("artist_name") or "Noma’lum"
            audio_url = track.get("audio")
            page_url = track.get("shareurl")

            text = (
                f"🎵 {index}. {title}\n"
                f"👤 Ijrochi: {artist}\n"
            )

            if audio_url:
                text += f"🎧 Tinglash: {audio_url}\n"

            if page_url:
                text += f"🌐 Musiqa sahifasi: {page_url}\n"

            results.append(text)

        await status_message.edit_text(
            "\n\n".join(results),
            disable_web_page_preview=True,
        )

    except requests.Timeout:
        await status_message.edit_text(
            "⏳ Musiqa xizmati javob bermadi. "
            "Keyinroq qayta urinib ko‘ring."
        )

    except requests.RequestException:
        logger.exception("Jamendo tarmoq xatosi")

        await status_message.edit_text(
            "🌐 Internetdagi musiqa xizmatiga "
            "ulanib bo‘lmadi. Keyinroq urinib ko‘ring."
        )

    except Exception:
        logger.exception("Musiqa qidirish xatosi")

        await status_message.edit_text(
            "⚠️ Qidiruvda xatolik yuz berdi. "
            "FadeHost loglarini tekshiring."
        )


# ==============================
# /PLAY
# ==============================

async def play(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.effective_message.reply_text(
            "🎵 Qo‘shiq nomini yozing.\n"
            "Misol: /play jazz"
        )
        return

    query = " ".join(context.args)
    await perform_search(update, query)


# ==============================
# /AUDIO
# ==============================

async def audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.effective_message.reply_text(
            "🎧 Audio nomini yozing.\n"
            "Misol: /audio piano"
        )
        return

    query = " ".join(context.args)
    await perform_search(update, query)


# ==============================
# AUDIO FAYL QABUL QILISH
# ==============================

async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    audio_file = message.audio

    if not audio_file:
        return

    title = (
        audio_file.title
        or audio_file.file_name
        or message.caption
        or "Nomsiz audio"
    )

    await message.reply_text(
        f"🎵 Audio qabul qilindi!\n"
        f"📀 Nomi: {title}\n\n"
        "Internet katalogidan qidirish uchun:\n"
        f"/play {title}"
    )


# ==============================
# XATOLIKLARNI QAYD ETISH
# ==============================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Telegram botda xatolik yuz berdi",
        exc_info=context.error,
    )


# ==============================
# BOTNI ISHGA TUSHIRISH
# ==============================

def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN yoki TELEGRAM_BOT_TOKEN "
            "FadeHost Environment Variables "
            "bo‘limida sozlanmagan."
        )

    if not JAMENDO_CLIENT_ID:
        raise RuntimeError(
            "JAMENDO_CLIENT_ID FadeHost Environment "
            "Variables bo‘limida sozlanmagan."
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("audio", audio))

    app.add_handler(
        MessageHandler(filters.AUDIO, receive_audio)
    )

    app.add_error_handler(error_handler)

    logger.info("Music Uz Bot ishga tushdi.")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
