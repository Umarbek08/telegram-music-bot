import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎵 Assalomu alaykum!\n\n"
        "Men musiqa botiman.\n"
        "Audio fayl yuborish uchun /audio buyrug'idan foydalaning."
    )


async def audio_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎵 Menga audio fayl yuboring. "
        "Men uni Telegram orqali qaytarib yuboraman."
    )


async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.message

    if message.audio:
        await message.reply_audio(
            audio=message.audio.file_id,
            caption="🎵 Mana audio faylingiz!",
        )
        return

    if message.document:
        mime_type = message.document.mime_type or ""

        if mime_type.startswith("audio/"):
            await message.reply_audio(
                audio=message.document.file_id,
                caption="🎵 Mana audio faylingiz!",
            )
            return

    await message.reply_text(
        "Iltimos, MP3 yoki boshqa audio fayl yuboring."
    )


def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN hosting sozlamalarida kiritilmagan."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("audio", audio_command))

    app.add_handler(
        MessageHandler(
            filters.AUDIO | filters.Document.AUDIO,
            receive_audio,
        )
    )

    logger.info("Bot ishga tushdi.")
    app.run_polling()


if __name__ == "__main__":
    main()
