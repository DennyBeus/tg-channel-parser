#!/usr/bin/env python3
import os
import sys
import re
import asyncio
import logging
import json
import argparse
from datetime import datetime, timedelta

# --- Совместимость с Python 3.10+ ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Загрузить переменные из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pyrogram import Client

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------- Configuration ----------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE_NUMBER", "")
DATA_DIR = os.getenv("DATA_DIR", "./data")
SESSION_PATH = os.path.join(DATA_DIR, "user")
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

# ---------------- Text processing ----------------
def normalize_whitespace(text: str) -> str:
    """Очистка лишних пробелов и пустых строк (всегда при парсинге)."""
    if not text:
        return ""
    text = re.sub(r'[ \t]+', ' ', text)
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def remove_links(text: str) -> str:
    """Удаляет ссылки из текста (URL и t.me)."""
    if not text:
        return ""
    text = re.sub(r'https?://[^\s\n\)]+', '', text)
    text = re.sub(r'[^\s\n]*t\.me/[^\s\n\)]+', '', text)
    return text


def remove_emoji(text: str) -> str:
    """Удаляет эмодзи из текста."""
    if not text:
        return ""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def _safe_attr_text(obj, attr_name: str) -> str:
    """Безопасно читает строковый атрибут у объекта."""
    try:
        value = getattr(obj, attr_name, None)
        return str(value) if value else ""
    except Exception:
        return ""


def _extract_text_from_raw_message(message) -> str:
    """
    Fallback для случаев, когда high-level message.text/caption пусты
    из-за новых entity (например, Quote/Blockquote).
    """
    raw = getattr(message, "_raw", None)
    if raw is None:
        return ""

    text = _safe_attr_text(raw, "message")
    if text:
        return text

    media = getattr(raw, "media", None)
    if media is not None:
        text = _safe_attr_text(media, "caption")
        if text:
            return text

    return ""


def get_message_text_plain(message) -> str:
    """Возвращает текст/подпись сообщения без markdown-конвертации."""
    text = _safe_attr_text(message, "text") or _safe_attr_text(message, "caption")
    if text:
        return text
    return _extract_text_from_raw_message(message)


def get_message_views(message) -> int:
    """Возвращает количество просмотров поста."""
    try:
        views = getattr(message, "views", None)
        return int(views) if views is not None else 0
    except (TypeError, ValueError):
        return 0


def get_message_reactions_count(message) -> int:
    """Возвращает суммарное количество реакций по посту."""
    reactions = getattr(message, "reactions", None)
    if not reactions:
        return 0

    reaction_items = getattr(reactions, "reactions", None)
    if reaction_items is None and isinstance(reactions, list):
        reaction_items = reactions

    if reaction_items:
        total = 0
        for item in reaction_items:
            count = getattr(item, "count", 0)
            try:
                total += int(count or 0)
            except (TypeError, ValueError):
                continue
        return total

    total_count = getattr(reactions, "count", None)
    try:
        return int(total_count) if total_count is not None else 0
    except (TypeError, ValueError):
        return 0

# ---------------- Core Parsing Logic ----------------
async def parse_channel(
    app: Client,
    channel_id: int,
    start_date: datetime,
    end_date: datetime,
    limit: int,
    no_links: bool,
    no_emoji: bool,
    post_id: int | None = None,
):
    messages_data = []
    count = 0

    logger.info(f"Parsing channel {channel_id} (Limit: {limit or 'None'}, No-Links: {no_links}, No-Emoji: {no_emoji})")

    if post_id:
        target_message = await app.get_messages(channel_id, post_id)
        message_iterable = [target_message] if target_message else []
    else:
        message_iterable = app.get_chat_history(channel_id)

    async def _iterate_messages():
        if post_id:
            for msg in message_iterable:
                yield msg
        else:
            async for msg in message_iterable:
                yield msg

    async for message in _iterate_messages():
        if not message:
            continue
        if limit and count >= limit:
            break

        msg_date = message.date
        if msg_date < start_date:
            break
        if msg_date > end_date:
            continue

        text = get_message_text_plain(message)
        views = get_message_views(message)
        reactions_count = get_message_reactions_count(message)

        if no_links:
            text = remove_links(text)
        text = normalize_whitespace(text)
        if no_emoji:
            text = remove_emoji(text)

        if text.strip():
            messages_data.append({
                'post_id': getattr(message, "id", 0),
                'text': text.strip(),
                'date': msg_date.strftime("%d.%m.%Y %H:%M:%S"),
                'views': views,
                'reactions_count': reactions_count
            })
            count += 1
            if count % 50 == 0:
                logger.info(f"Parsed {count} messages...")

    return messages_data

def save_results(messages: list, filename: str, fmt: str):
    """Сохраняет результат в Downloads или по указанному пути"""
    if not os.path.isabs(filename) and os.sep not in filename:
        full_path = os.path.join(DOWNLOADS_DIR, f"{filename}.{fmt}")
    else:
        full_path = filename if filename.endswith(f".{fmt}") else f"{filename}.{fmt}"

    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    if fmt == 'json':
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=4)
    else:
        with open(full_path, 'w', encoding='utf-8') as f:
            for m in messages:
                f.write(
                    f"[{m['date']}] "
                    f"(views: {m.get('views', 0)}, reactions: {m.get('reactions_count', 0)})\n"
                    f"{m['text']}\n\n---\n\n"
                )
    
    logger.info(f"Successfully saved {len(messages)} items to {full_path}")

# ---------------- Execution ----------------
async def main():
    parser = argparse.ArgumentParser(description="Telegram Channel Parser CLI")
    
    parser.add_argument("channel", nargs='?', help="Channel URL (https://t.me/***)")
    parser.add_argument("-s", "--start", help="Start date DD.MM.YYYY", default="01.01.1970")
    parser.add_argument("-e", "--end", help="End date DD.MM.YYYY", default=None)
    parser.add_argument("-o", "--output", help="Output filename (in Downloads)", default="result")
    parser.add_argument("-f", "--format", choices=['txt', 'json'], default='txt', help="Output format")
    parser.add_argument("-l", "--limit", type=int, help="Max messages to parse")
    parser.add_argument("--post-id", type=int, help="Parse only one post by Telegram message id")
    parser.add_argument("-r", "--reverse", action="store_true", help="Write output from oldest to newest (default: newest to oldest)")
    parser.add_argument("--no-links", action="store_true", help="Remove links from text (default: keep links)")
    parser.add_argument("--no-emoji", action="store_true", help="Remove all emoji from text (default: keep emoji)")
    parser.add_argument("--auth", action="store_true", help="Run authorization mode")

    args = parser.parse_args()

    if args.auth:
        async with Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE) as auth_app:
            print("\n--- Authorization Successful! ---\n")
        return

    if not args.channel:
        parser.print_help()
        return

    try:
        start_dt = datetime.strptime(args.start, "%d.%m.%Y")
        end_dt = datetime.strptime(args.end, "%d.%m.%Y") if args.end else datetime.now()
        if args.end:
            end_dt = end_dt + timedelta(days=1) - timedelta(microseconds=1)
    except ValueError as e:
        logger.error(f"Date format error: {e}. Use DD.MM.YYYY")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    
    app = Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE)
    
    async with app:
        clean_channel = args.channel.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "").strip()
        try:
            chat = await app.get_chat(clean_channel)
            channel_id = chat.id
        except Exception as e:
            logger.error(f"Could not find channel '{args.channel}': {e}")
            return

        results = await parse_channel(
            app,
            channel_id,
            start_dt,
            end_dt,
            args.limit,
            args.no_links,
            args.no_emoji,
            args.post_id,
        )

        if args.reverse:
            results = list(reversed(results))

        if results:
            save_results(results, args.output, args.format)
        else:
            logger.warning("No messages found for the given criteria.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass