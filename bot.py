import os
import logging
import asyncio

import requests
from telegram import Update
from telegram.ext import (
Application,
CommandHandler,
ContextTypes,
)

logging.basicConfig(
format="%(asctime)s - %(levelname)s - %(message)s",
level=logging.INFO,
)

logger = logging.getLogger(name)

TOKEN = (
os.getenv("BOT_TOKEN")
or os.getenv("TELEGRAM_BOT_TOKEN")
)

ITUNES_API = "https://itunes.apple.com/search"

def search_music(query: str) -> list:
"""Apple iTunes katalogidan qo‘shiqlarni qidiradi."""

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
):
await update.effective_message.reply_text(
"🎵 Assalomu alaykum!\n"
"Men Music Uz Botman.\n\n"
"🔎 /play qo‘shiq nomi — internetdan qidirish\n"
"🎧 /audio qo‘shiq nomi — musiqa qidirish\n"
"❓ /help — yordam\n\n"
"API kaliti talab qilinmaydi!"
)

async def help_command(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
await update.effective_message.reply_text(
"🎶 MUSIC UZ BOT\n\n"
"/start — boshlash\n"
"/play Adele Hello — qo‘shiq qidirish\n"
"/audio jazz — musiqa qidirish\n"
"/help — yordam\n\n"
"Bot internetdagi musiqa katalogidan "
"natijalarni qidiradi."
)

async def perform_search(
update: Update,
query: str,
):
message = update.effective_message

status = await message.reply_text(
    f"🔎 Internetdan qidiryapman: {query}"
)

try:
    tracks = await asyncio.to_thread(
        search_music,
        query,
    )

    if not tracks:
        await status.edit_text(
            "😕 Qo‘shiq topilmadi.\n"
            "Boshqa nom bilan urinib ko‘ring."
        )
        return

    for index, track in enumerate(tracks, start=1):
        title = track.get("trackName", "Nomsiz")
        artist = track.get("artistName", "Noma’lum")
        album = track.get("collectionName", "")
        store_url = track.get("trackViewUrl", "")
        preview_url = track.get("previewUrl", "")

        text = (
            f"🎵 {index}. {title}\n"
            f"👤 Ijrochi: {artist}\n"
        )

        if album:
            text += f"💿 Albom: {album}\n"

        if store_url:
            text += f"🌐 Tinglash: {store_url}\n"

        if preview_url:
            text += (
                f"🎧 Qisqa audio namuna: "
                f"{preview_url}\n"
            )

        await message.reply_text(
            text,
            disable_web_page_preview=True,
        )

    await status.delete()

except requests.Timeout:
    await status.edit_text(
        "⏳ Musiqa xizmati vaqtida javob bermadi. "
        "Keyinroq urinib ko‘ring."
    )

except requests.RequestException:
    logger.exception("Internetga ulanish xatosi")
    await status.edit_text(
        "🌐 Musiqa xizmatiga ulanib bo‘lmadi. "
        "FadeHost loglarini tekshiring."
    )

except Exception:
    logger.exception("Qidiruvda xatolik")
    await status.edit_text(
        "⚠️ Xatolik yuz berdi. "
        "Keyinroq yana urinib ko‘ring."
    )

async def play(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not context.args:
await update.effective_message.reply_text(
"Misol: /play Adele Hello"
)
return

query = " ".join(context.args)
await perform_search(update, query)

async def audio(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not context.args:
await update.effective_message.reply_text(
"Misol: /audio jazz"
)
return

query = " ".join(context.args)
await perform_search(update, query)

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
"Environment Variables ichida sozlanmagan."
)

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("play", play))
app.add_handler(CommandHandler("audio", audio))

app.add_error_handler(error_handler)

logger.info("Music Uz Bot ishga tushdi.")

app.run_polling(
    allowed_updates=Update.ALL_TYPES
)

if name == "main":
main()
