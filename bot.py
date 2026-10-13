import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Log sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Bot tokenini hosting sozlamalaridan olish
TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = (
        "🎵 Assalomu alaykum!\n"
        "Men Music Uz Botman.\n\n"
        "🎶 Qo‘shiq qidirish: /play qo‘shiq nomi\n"
        "🎧 Audio qidirish: /audio qo‘shiq nomi\n"
        "⏸ Pauza: /pause\n"
        "▶️ Davom ettirish: /resume\n"
        "⏭ Keyingi qo‘shiq: /skip\n"
        "📋 Navbat: /queue\n\n"
        "Bot ishga tushdi! Musiqa funksiyalari "
        "hali ulanmagan."
    )

    await update.effective_message.reply_text(message)


async def play(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not context.args:
        await update.effective_message.reply_text(
            "🎵 Misol: /play Munisa Rizayeva"
        )
        return

    query = " ".join(context.args)

    await update.effective_message.reply_text(
        f"🔎 Qidiruv: {query}\n\n"
        "Musiqa qidirish funksiyasi hali ulanmagan."
    )


async def audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not context.args:
        await update.effective_message.reply_text(
            "🎧 Misol: /audio qo‘shiq nomi"
        )
        return

    query = " ".join(context.args)

    await update.effective_message.reply_text(
        f"🔎 Audio qidiruvi: {query}\n\n"
        "Audio qidirish funksiyasi hali ulanmagan."
    )


async def pause(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.effective_message.reply_text(
        "⏸ Pauza funksiyasi hali ulanmagan."
    )


async def resume(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.effective_message.reply_text(
        "▶️ Davom ettirish funksiyasi hali ulanmagan."
    )


async def skip(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.effective_message.reply_text(
        "⏭ Keyingi qo‘shiq funksiyasi hali ulanmagan."
    )


async def queue(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.effective_message.reply_text(
        "📋 Hozircha navbat bo‘sh."
    )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Telegram botda xatolik yuz berdi",
        exc_info=context.error,
    )


def main() -> None:
    if not TOKEN:
        raise RuntimeError(
            "Bot tokeni topilmadi! "
            "Hosting sozlamalarida BOT_TOKEN "
            "nomli environment variable yarating."
        )

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )
    application.add_handler(
        CommandHandler("play", play)
    )
    application.add_handler(
        CommandHandler("audio", audio)
    )
    application.add_handler(
        CommandHandler("pause", pause)
    )
    application.add_handler(
        CommandHandler("resume", resume)
    )
    application.add_handler(
        CommandHandler("skip", skip)
    )
    application.add_handler(
        CommandHandler("queue", queue)
    )

    application.add_error_handler(error_handler)

    logger.info("Music Uz Bot ishga tushmoqda...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
