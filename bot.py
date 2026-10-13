import os
import re
import json
import sqlite3
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

# FadeHost doimiy diskni qo'llasa, shu papkani
# doimiy disk joylashuviga o'zgartirish mumkin.
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "music.db"

ITUNES_URL = "https://itunes.apple.com/search"
AUDD_URL = "https://api.audd.io/"

MAX_FILE_SIZE = 10 * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# MA'LUMOTLAR BAZASI
# ==========================================

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT DEFAULT '',
                filename TEXT NOT NULL,
                uploader_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()


def normalize(text):
    text = (text or "").casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def save_song(title, artist, filename, uploader_id):
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute(
            """
            INSERT INTO songs
                (title, artist, filename, uploader_id)
            VALUES (?, ?, ?, ?)
            """,
            (title, artist, filename, uploader_id),
        )
        db.commit()
        return cursor.lastrowid


def find_local_songs(query, limit=10):
    """O'z audio bazamizdan qo'shiq qidirish."""

    query_norm = normalize(query)

    if not query_norm:
        return []

    words = query_norm.split()

    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row

        rows = db.execute(
            """
            SELECT id, title, artist, filename
            FROM songs
            ORDER BY id DESC
            LIMIT 2000
            """
        ).fetchall()

    results = []

    for row in rows:
        haystack = normalize(
            f"{row['title']} {row['artist']}"
        )

        if all(word in haystack for word in words):
            results.append(dict(row))

            if len(results) >= limit:
                break

    return results


# ==========================================
# INTERNETDAN QO'SHIQ QIDIRISH
# ==========================================

def search_itunes(term, limit=7):
    response = requests.get(
        ITUNES_URL,
        params={
            "term": term,
            "entity": "song",
            "limit": limit,
            "country": "UZ",
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()
    results = []

    for item in data.get("results", []):
        if item.get("kind") != "song":
            continue

        results.append({
            "title": item.get(
                "trackName", "Noma'lum qo'shiq"
            ),
            "artist": item.get(
                "artistName", "Noma'lum ijrochi"
            ),
            "album": item.get("collectionName", ""),
            "preview": item.get("previewUrl"),
            "url": item.get("trackViewUrl"),
        })

    return results


# ==========================================
# AUDD: OVOZDAN ANIQLASH
# ==========================================

def recognize_audio(path):
    if not AUDD_API_TOKEN:
        return {
            "error": (
                "AUDD_API_TOKEN sozlanmagan. "
                "FadeHost Environment Variables bo'limini tekshiring."
            )
        }

    with open(path, "rb") as audio:
        response = requests.post(
            AUDD_URL,
            data={
                "api_token": AUDD_API_TOKEN,
            },
            files={
                "file": (
                    Path(path).name,
                    audio,
                )
            },
            timeout=60,
        )

    response.raise_for_status()
    data = response.json()

    if data.get("status") != "success":
        logger.warning("AudD API status: %s", data.get("status"))
        return {"error": "AudD audio faylni aniqlay olmadi."}

    result = data.get("result")

    if not result:
        return None

    return {
        "title": result.get("title", "Noma'lum"),
        "artist": result.get("artist", "Noma'lum"),
        "album": result.get("album", ""),
        "url": result.get("song_link", ""),
    }


# ==========================================
# START
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🎵 Assalomu alaykum!\n\n"
        "Men musiqa qidiruvchi botman.\n\n"
        "✍️ Qo'shiq nomi yoki ijrochisini yozing.\n"
        "🎤 Qo'shiq yozilgan audio yuboring.\n"
        "📁 O'z audio faylingizni bazaga qo'shing:\n"
        "/add nomi | ijrochi\n\n"
        "Buyruqlar:\n"
        "/start — boshlash\n"
        "/help — yordam\n"
        "/mycount — bazadagi qo'shiqlar soni"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🔎 Qidirish:\n"
        "Qo'shiq nomini yoki ijrochini yozing.\n\n"
        "📁 Audio bazaga qo'shish:\n"
        "Avval /add Qo'shiq nomi | Ijrochi deb yozing,\n"
        "keyin o'zingizga tegishli yoki tarqatishga "
        "ruxsatingiz bor audio faylni yuboring.\n\n"
        "🎤 Aniqlash:\n"
        "Qo'shiqdan qisqa audio parcha yuboring."
    )


# ==========================================
# AUDIO BAZAGA QO'SHISH
# ==========================================

async def add_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    raw = " ".join(context.args).strip()

    if not raw or "|" not in raw:
        await update.effective_message.reply_text(
            "Format:\n/add Qo'shiq nomi | Ijrochi\n\n"
            "Masalan:\n/add Odamlar | Konsta"
        )
        return

    title, artist = [
        part.strip() for part in raw.split("|", 1)
    ]

    if not title:
        await update.effective_message.reply_text(
            "Qo'shiq nomini kiriting."
        )
        return

    context.user_data["pending_song"] = {
        "title": title,
        "artist": artist,
    }

    await update.effective_message.reply_text(
        f"🎵 Nomi: {title}\n"
        f"🎤 Ijrochi: {artist or 'Ko‘rsatilmagan'}\n\n"
        "Endi shu qo'shiqning audio faylini yuboring."
    )


async def receive_song_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    pending = context.user_data.get("pending_song")

    if not pending:
        await message.reply_text(
            "Audio faylni bazaga qo'shish uchun avval:\n"
            "/add Qo'shiq nomi | Ijrochi\n"
            "deb yozing."
        )
        return

    media = message.audio or message.document

    if not media:
        await message.reply_text(
            "Iltimos, audio fayl yuboring."
        )
        return

    mime = getattr(media, "mime_type", "") or ""

    if message.document and not (
        mime.startswith("audio/")
        or (media.file_name or "").lower().endswith(
            (".mp3", ".m4a", ".ogg", ".wav", ".flac")
        )
    ):
        await message.reply_text(
            "Bu audio faylga o'xshamaydi. "
            "MP3, M4A, OGG yoki WAV yuboring."
        )
        return

    size = getattr(media, "file_size", 0) or 0

    if size > MAX_FILE_SIZE:
        await message.reply_text(
            "Fayl 10 MB dan katta. Kichikroq audio yuboring."
        )
        return

    status = await message.reply_text(
        "⏳ Audio fayl saqlanmoqda..."
    )

    path = None

    try:
        tg_file = await context.bot.get_file(media.file_id)

        suffix = Path(
            getattr(media, "file_name", "") or "song.mp3"
        ).suffix

        if not suffix:
            suffix = ".audio"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            dir=AUDIO_DIR,
            delete=False,
        ) as temp:
            path = Path(temp.name)

        await tg_file.download_to_drive(
            custom_path=str(path)
        )

        if path.stat().st_size > MAX_FILE_SIZE:
            path.unlink(missing_ok=True)
            await status.edit_text(
                "Fayl 10 MB limitidan oshdi."
            )
            return

        save_song(
            title=pending["title"],
            artist=pending["artist"],
            filename=path.name,
            uploader_id=message.from_user.id,
        )

        context.user_data.pop("pending_song", None)

        await status.edit_text(
            "✅ Audio bazaga qo'shildi!\n\n"
            f"🎵 {pending['title']}\n"
            f"🎤 {pending['artist'] or 'Noma’lum'}\n\n"
            "Endi qo'shiq nomini yozib qidirishingiz mumkin."
        )

    except Exception:
        logger.exception("Audio saqlashda xatolik")

        if path and path.exists():
            path.unlink(missing_ok=True)

        await status.edit_text(
            "⚠️ Audio saqlanmadi. FadeHost Logs bo'limini tekshiring."
        )


# ==========================================
# QO'SHIQLAR SONI
# ==========================================

async def mycount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    with sqlite3.connect(DB_PATH) as db:
        count = db.execute(
            "SELECT COUNT(*) FROM songs"
        ).fetchone()[0]

    await update.effective_message.reply_text(
        f"📚 Audio bazada {count} ta qo'shiq bor."
    )


# ==========================================
# MATN ORQALI QIDIRISH
# ==========================================

async def text_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    term = (message.text or "").strip()

    if not term or term.startswith("/"):
        return

    if len(term) > 200:
        await message.reply_text(
            "Qidiruv so'zini qisqaroq yozing."
        )
        return

    status = await message.reply_text(
        "🔎 Avval o'z bazamdan, keyin internetdan qidiraman..."
    )

    try:
        # 1. O'z bazamizdan qidiramiz
        local_songs = find_local_songs(term)

        if local_songs:
            keyboard = []

            for song in local_songs:
                keyboard.append([
                    InlineKeyboardButton(
                        text=(
                            f"📁 {song['title']} — "
                            f"{song['artist'] or 'Noma’lum'}"
                        ),
                        callback_data=f"local:{song['id']}",
                    )
                ])

            await status.edit_text(
                "✅ O'z audio bazamdan topdim!\n"
                "Kerakli qo'shiqni tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # 2. Internet katalogidan qidiramiz
        results = await asyncio.to_thread(
            search_itunes,
            term,
        )

        if not results:
            await status.edit_text(
                "😕 Qo'shiq topilmadi.\n\n"
                "Boshqa nom bilan qidirib ko'ring yoki "
                "audio faylni bazaga qo'shing."
            )
            return

        keyboard = []

        for index, song in enumerate(results):
            context.user_data.setdefault(
                "itunes_results", {}
            )[str(index)] = song

            keyboard.append([
                InlineKeyboardButton(
                    text=f"🎵 {song['title']} — {song['artist']}",
                    callback_data=f"itunes:{index}",
                )
            ])

        await status.edit_text(
            "🎶 Internet katalogidan topilgan qo'shiqlar:\n"
            "Tanlash uchun tugmani bosing.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except requests.RequestException:
        logger.exception("Internet qidiruvida xatolik")

        await status.edit_text(
            "⚠️ Internet qidiruvi vaqtincha ishlamayapti. "
            "Keyinroq urinib ko'ring."
        )

    except Exception:
        logger.exception("Matnli qidiruv xatosi")

        await status.edit_text(
            "⚠️ Qidiruvda xatolik yuz berdi."
        )


# ==========================================
# NATIJANI TANLASH
# ==========================================

async def select_song(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if not query.message:
        return

    try:
        kind, value = query.data.split(":", 1)

        if kind == "local":
            with sqlite3.connect(DB_PATH) as db:
                db.row_factory = sqlite3.Row

                song = db.execute(
                    """
                    SELECT id, title, artist, filename
                    FROM songs
                    WHERE id = ?
                    """,
                    (int(value),),
                ).fetchone()

            if not song:
                await query.message.reply_text(
                    "Bu audio bazadan topilmadi."
                )
                return

            path = AUDIO_DIR / song["filename"]

            if not path.is_file():
                await query.message.reply_text(
                    "Audio fayl serverda topilmadi. "
                    "FadeHost doimiy disk sozlamasini tekshiring."
                )
                return

            await context.bot.send_chat_action(
                chat_id=query.message.chat_id,
                action=ChatAction.UPLOAD_AUDIO,
            )

            with path.open("rb") as audio:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=audio,
                    title=song["title"],
                    performer=song["artist"] or None,
                    filename=path.name,
                )

            return

        if kind == "itunes":
            song = context.user_data.get(
                "itunes_results", {}
            ).get(value)

            if not song:
                await query.message.reply_text(
                    "Natija eskirgan. Qaytadan qidiring."
                )
                return

            title = song["title"]
            artist = song["artist"]
            preview = song.get("preview")
            url = song.get("url")

            text = (
                f"🎵 {title}\n"
                f"🎤 {artist}\n"
            )

            if url:
                text += f"\n🔗 Tinglash: {url}"

            await query.message.reply_text(text)

            if not preview:
                await query.message.reply_text(
                    "Bu qo'shiq uchun audio namunasi yo'q. "
                    "To'liq audio fayl o'z bazangizda bo'lsa, "
                    "uni /add orqali qo'shing."
                )
                return

            await query.message.reply_text(
                "⏳ Audio namunasi yuklanmoqda..."
            )

            def download_preview():
                response = requests.get(
                    preview,
                    timeout=30,
                )
                response.raise_for_status()

                with tempfile.NamedTemporaryFile(
                    suffix=".m4a",
                    dir=AUDIO_DIR,
                    delete=False,
                ) as temp:
                    temp.write(response.content)
                    return temp.name

            path = await asyncio.to_thread(download_preview)

            try:
                with open(path, "rb") as audio:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=audio,
                        title=title,
                        performer=artist,
                        filename=f"{title[:60]}.m4a",
                        caption="🎧 Qisqa audio namuna",
                    )
            finally:
                Path(path).unlink(missing_ok=True)

    except Exception:
        logger.exception("Natijani yuborishda xatolik")

        await query.message.reply_text(
            "⚠️ Natijani yuborishda xatolik yuz berdi."
        )


# ==========================================
# AUDIO ANIQLASH
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

    size = getattr(media, "file_size", 0) or 0

    if size > MAX_FILE_SIZE:
        await message.reply_text(
            "Audio 10 MB dan katta. Qisqaroq fayl yuboring."
        )
        return

    status = await message.reply_text(
        "🎧 Qo'shiq aniqlanmoqda..."
    )

    path = None

    try:
        tg_file = await context.bot.get_file(media.file_id)

        with tempfile.NamedTemporaryFile(
            suffix=".audio",
            delete=False,
        ) as temp:
            path = temp.name

        await tg_file.download_to_drive(
            custom_path=path
        )

        result = await asyncio.to_thread(
            recognize_audio,
            path,
        )

        if not result:
            await status.edit_text(
                "😕 Qo'shiqni aniqlay olmadim. "
                "Tiniqroq audio yuboring."
            )
            return

        if result.get("error"):
            await status.edit_text(
                "⚠️ " + result["error"]
            )
            return

        title = result["title"]
        artist = result["artist"]

        # Aniqlangan qo'shiqni avval o'z bazamizdan qidiramiz.
        local = find_local_songs(f"{title} {artist}", limit=1)

        if local:
            song = local[0]
            audio_path = AUDIO_DIR / song["filename"]

            if audio_path.is_file():
                await status.edit_text(
                    f"✅ {title} — {artist}\n"
                    "O'z bazamdan audio faylni yuboryapman..."
                )

                with audio_path.open("rb") as audio:
                    await context.bot.send_audio(
                        chat_id=message.chat_id,
                        audio=audio,
                        title=title,
                        performer=artist,
                    )
                return

        text = f"✅ Qo'shiq aniqlandi!\n\n🎵 {title}\n🎤 {artist}"

        if result.get("album"):
            text += f"\n💿 {result['album']}"

        if result.get("url"):
            text += f"\n\n🔗 {result['url']}"

        text += (
            "\n\nTo'liq audio bazamda mavjud emas. "
            "Qo'shiq faylini /add orqali bazaga qo'shish mumkin."
        )

        await status.edit_text(text)

    except Exception:
        logger.exception("Audioni aniqlashda xatolik")

        await status.edit_text(
            "⚠️ Audio tahlilida xatolik. "
            "FadeHost Logs bo'limini tekshiring."
        )

    finally:
        if path:
            Path(path).unlink(missing_ok=True)


# ==========================================
# XATOLARNI LOGGA YOZISH
# ==========================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Bot xatosi",
        exc_info=context.error,
    )


# ==========================================
# MAIN
# ==========================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN yoki TELEGRAM_BOT_TOKEN topilmadi!"
        )

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("mycount", mycount))

    app.add_handler(
        CallbackQueryHandler(
            select_song,
            pattern=r"^(local|itunes):",
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

    logger.info("Musiqa boti ishga tushmoqda...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
