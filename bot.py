import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Loglar
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# FadeHost sozlamasidan olinadi
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "🎵 Assalomu alaykum!\n"
        "Men Music Uz Botman.\n\n"
        "🎧 Qo‘shiq qidirish: /play qo‘shiq nomi\n"
        "📁 Audio qidirish: /audio qo‘shiq nomi\n"
        "⏸ Pauza: /pause\n"
        "▶️ Davom ettirish: /resume\n"
        "⏭ Keyingi qo‘shiq: /skip\n"
        "📋 Navbat: /queue\n\n"
        "Hozircha musiqa qidirish va ijro etish "
        "funksiyalari ulanmagan."
    )

    await update.effective_message.reply_text(text)


async def play(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.effective_message.reply_text(
            "🎵 Foydalanish: /play qo‘shiq nomi"
        )
        return

    query = " ".join(context.args)

    await update.effective_message.reply_text(
        f"🔎 Qidiruv: {query}\n\n"
        "Musiqa qidirish tizimi hali ulanmagan."
    )


async def audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.effective_message.reply_text(
            "🎧 Foydalanish: /audio qo‘shiq nomi"
        )
        return

    query = " ".join(context.args)

    await update.effective_message.reply_text(
        f"🔎 Audio qidiruvi: {query}\n\n"
        "Audio qidirish tizimi hali ulanmagan."
    )


async def pause(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "⏸ Pauza funksiyasi hali ulanmagan."
    )


async def resume(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "▶️ Davom ettirish funksiyasi hali ulanmagan."
    )


async def skip(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "⏭ Keyingi qo‘shiq funksiyasi hali ulanmagan."
    )


async def queue(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "📋 Hozircha navbat bo‘sh."
    )


async def error_handler(
    update:
