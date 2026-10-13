import os
import json
import logging
from pathlib import Path

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

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CATALOG_FILE = DATA_DIR / "music_catalog.json"


def load_catalog():
    if not CATALOG_FILE.exists():
        return []

    try:
        with CATALOG_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        logger.exception("Musiqa katalogini o‘qib bo‘lmadi")
        return []


def save_catalog(catalog):
    temporary_file = CATALOG_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(catalog, file, ensure_ascii=False, indent=2)

    temporary_file.replace(CATALOG_FILE)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "🎵 Assalomu alaykum!\n"
        "Men Music Uz Botman.\n\n"
        "🎧 /audio nom — katalogdan qo‘shiq qidirish\n"
        "📋 /list — katalogdagi qo‘shiqlar\n"
        "❓ /help — yordam\n\n"
        "➕ Katalogga qo‘shish uchun menga audio fayl yuboring.\n"
        "Audio nomini fayl nomidan yoki izohidan olaman."
    )

    await update.effective_message.reply_text(text)


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🎵 Buyruqlar:\n\n"
        "/start — boshlash\n"
        "/audio qo‘shiq nomi — qidirish\n"
        "/list — mavjud audiolar ro‘yxati\n"
        "/help — yordam\n\n"
        "Yangi audio qo‘shish uchun botga audio yuboring."
    )


async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    audio = message.audio

    if not audio:
        await message.reply_text(
            "Iltimos, audio fayl yuboring."
        )
        return

    title = (
        audio.title
        or message.caption
        or audio.file_name
        or "Nomsiz audio"
    ).strip()

    catalog = load_catalog()

    entry = {
        "file_id": audio.file_id,
        "title": title,
        "artist": audio.performer or "",
        "user_id": message.from_user.id if message.from_user else None,
    }

    catalog.append(entry)
    save_catalog(catalog)

    await message.reply_text(
        f"✅ Audio katalogga qo‘shildi!\n"
        f"🎵 Nomi: {title}\n\n"
        f"Qidirish uchun: /audio {title}"
    )


async def search_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not context.args:
        await message.reply_text(
            "🔎 Masalan: /audio Munisa Rizayeva"
        )
        return

    query = " ".join(context.args).casefold()
    catalog = load_catalog()

    matches = [
        item for item in catalog
        if query in item.get("title", "").casefold()
        or query in item.get("artist", "").casefold()
    ]

    if not matches:
        await message.reply_text(
            "😕 Katalogdan topilmadi.\n\n"
            "Avval kerakli audio faylni botga yuboring "
            "yoki boshqa nom bilan qidirib ko‘ring."
        )
        return

    for item in matches[:5]:
        try:
            await message.reply_audio(
                audio=item["file_id"],
                title=item.get("title", "Nomsiz audio"),
                performer=item.get("artist") or None,
            )
        except Exception:
            logger.exception("Audio yuborishda xatolik")
            await message.reply_text(
                f"⚠️ «{item.get('title', 'Audio')}» yuborilmadi."
            )


async def list_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    catalog = load_catalog()

    if not catalog:
        await update.effective_message.reply_text(
            "📭 Katalog hozircha bo‘sh.\n"
            "Menga audio yuborib, katalogni to‘ldiring."
        )
        return

    lines = ["🎵 Katalogdagi audiolar:"]

    for number, item in enumerate(catalog[-30:], start=1):
        title = item.get("title", "Nomsiz audio")
        artist = item.get("artist", "")
        label = f"{number}. {title}"

        if artist:
            label += f" — {artist}"

        lines.append(label)

    await update.effective_message.reply_text("\n".join(lines))


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Botda xatolik yuz berdi",
        exc_info=context.error,
    )


def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN yoki TELEGRAM_BOT_TOKEN sozlanmagan!"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("audio", search_audio))
    app.add_handler(CommandHandler("list", list_audio))
    app.add_handler(
        MessageHandler(filters.AUDIO, receive_audio)
    )
    app.add_error_handler(error_handler)

    logger.info("Music Uz Bot ishga tushmoqda...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
