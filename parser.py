#!/usr/bin/env python3
import os
import re
import asyncio
import logging
import json
import argparse
from datetime import datetime, timedelta

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

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

PROXY = None
if os.getenv("PROXY_HOSTNAME"):
    PROXY = {
        "scheme": os.getenv("PROXY_SCHEME", "http"),
        "hostname": os.getenv("PROXY_HOSTNAME"),
        "port": int(os.getenv("PROXY_PORT", "8080")),
    }
    if os.getenv("PROXY_USERNAME"):
        PROXY["username"] = os.getenv("PROXY_USERNAME")
        PROXY["password"] = os.getenv("PROXY_PASSWORD", "")

# ---------------- Text processing ----------------
def normalize_whitespace(text: str) -> str:
    """Очистка лишних пробелов и пустых строк (всегда при парсинге)."""
    if not text:
        return ""
    text = re.sub(r'[ \t]+', ' ', text)
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


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


def _utf16_to_python_index(text: str, utf16_offset: int) -> int:
    """Telegram entity offsets are in UTF-16 code units; Python strings use code points."""
    pos = 0
    for i, ch in enumerate(text):
        if pos >= utf16_offset:
            return i
        pos += 2 if ord(ch) > 0xFFFF else 1
    return len(text)


def get_message_text_with_urls(message) -> str:
    """Возвращает текст сообщения с inline URL, вставленными после якорного текста."""
    text = _safe_attr_text(message, "text")
    entities = getattr(message, "entities", None)

    if not text:
        text = _safe_attr_text(message, "caption")
        entities = getattr(message, "caption_entities", None)

    if not text:
        return _extract_text_from_raw_message(message)

    if not entities:
        return text

    inserts = []
    for entity in entities:
        entity_type = getattr(entity, "type", None)
        if entity_type is None:
            continue
        type_str = str(entity_type).lower()
        if "text_link" in type_str:
            url = getattr(entity, "url", "")
            if url:
                raw_offset = getattr(entity, "offset", 0)
                raw_length = getattr(entity, "length", 0)
                py_end = _utf16_to_python_index(text, raw_offset + raw_length)
                while py_end < len(text) and not text[py_end].isspace() and text[py_end] not in '.,;:!?)]}':
                    py_end += 1
                inserts.append((py_end, url))

    if not inserts:
        return text

    inserts.sort(key=lambda x: x[0], reverse=True)
    for pos, url in inserts:
        text = text[:pos] + f" ({url})" + text[pos:]

    return text


def get_message_views(message) -> int:
    """Возвращает количество просмотров поста."""
    try:
        views = getattr(message, "views", None)
        return int(views) if views is not None else 0
    except (TypeError, ValueError):
        return 0


def filter_by_keywords(messages: list, keywords: list) -> list:
    """Фильтрует сообщения, оставляя только те, где есть хотя бы одно ключевое слово."""
    if not keywords:
        return messages
    lower_keywords = [kw.lower() for kw in keywords]
    filtered = [m for m in messages if any(kw in m['text'].lower() for kw in lower_keywords)]
    logger.info(f"Keyword filter {keywords}: {len(messages)} → {len(filtered)} messages")
    return filtered


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
    channel_username: str,
    start_date: datetime,
    end_date: datetime,
    limit: int,
    no_emoji: bool,
    keywords: list | None = None,
):
    messages_data = []
    count = 0
    lower_keywords = [kw.lower() for kw in keywords] if keywords else None

    logger.info(f"Parsing channel {channel_username} (Limit: {limit or 'None'}, No-Emoji: {no_emoji}, Keywords: {keywords or 'None'})")

    async for message in app.get_chat_history(channel_id):
        if not message:
            continue
        if limit and count >= limit:
            break

        msg_date = message.date
        if msg_date < start_date:
            break
        if msg_date > end_date:
            continue

        text = get_message_text_with_urls(message)
        views = get_message_views(message)
        reactions_count = get_message_reactions_count(message)

        text = normalize_whitespace(text)
        if no_emoji:
            text = remove_emoji(text)

        if not text:
            continue

        if lower_keywords and not any(kw in text.lower() for kw in lower_keywords):
            continue

        messages_data.append({
            'text': text,
            'date': msg_date.strftime("%Y-%m-%d %H:%M:%S"),
            'views': views,
            'reactions_count': reactions_count,
            'link': f"https://t.me/{channel_username}/{message.id}",
            'source_channel': channel_username,
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
    parser = argparse.ArgumentParser(
        description="Telegram Channel Parser CLI",
        usage="userbot.py [-h] [-a] [-s START] [-e END] [-o OUTPUT] [-f {txt,json}] [-l LIMIT] [-r] [-j] [-k WORD [WORD ...]] [--stdout] [channel ...]",
        add_help=False,
    )
    
    parser.add_argument("-h", "--help", action="help", help="Show this help message and exit")
    parser.add_argument("channel", nargs='*', help="Channel URLs (https://t.me/***)")
    parser.add_argument("-a", "--auth", action="store_true", help="Run authorization mode")
    parser.add_argument("-s", metavar="START", help="Start date in DD.MM.YYYY format", default="01.01.1970")
    parser.add_argument("-e", metavar="END", help="End date in DD.MM.YYYY format", default=None)
    parser.add_argument("-o", metavar="OUTPUT", help="Output file name (saved to Downloads by default)", default="result")
    parser.add_argument("-f", choices=['txt', 'json'], default='txt', help="Output format: txt or json")
    parser.add_argument("-l", metavar="LIMIT", type=int, help="Maximum number of messages to parse")
    parser.add_argument("-r", "--reverse", action="store_true", help="Write output from oldest to newest (default: newest to oldest)")
    parser.add_argument("-j", "--no-emoji", action="store_true", help="Remove all emoji from text (default: keep emoji)")
    parser.add_argument("-k", "--keywords", nargs='+', metavar="WORD", help="Filter posts: keep only those containing at least one keyword (case-insensitive)")
    parser.add_argument("--stdout", action="store_true", help="Print JSON to stdout instead of saving to file")

    args = parser.parse_args()

    if args.auth:
        async with Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE, proxy=PROXY):
            print("\n--- Authorization Successful! ---\n")
        return

    if not args.channel:
        parser.print_help()
        return

    try:
        start_dt = datetime.strptime(args.s, "%d.%m.%Y")
        end_dt = datetime.strptime(args.e, "%d.%m.%Y") if args.e else datetime.now()
        if args.e:
            end_dt = end_dt + timedelta(days=1) - timedelta(microseconds=1)
    except ValueError as e:
        logger.error(f"Date format error: {e}. Use DD.MM.YYYY")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    
    app = Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE, proxy=PROXY)
    all_results = []
    
    async with app:
        for channel_arg in args.channel:
            clean_channel = channel_arg.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "").strip()
            try:
                chat = await app.get_chat(clean_channel)
                channel_id = chat.id
            except Exception as e:
                logger.error(f"Could not find channel '{channel_arg}': {e}")
                continue

            results = await parse_channel(
                app,
                channel_id,
                clean_channel,
                start_dt,
                end_dt,
                args.l,
                args.no_emoji,
                args.keywords,
            )
            all_results.extend(results)

    if args.reverse:
        all_results = list(reversed(all_results))

    if not all_results:
        logger.warning("No messages found for the given criteria.")
        return

    if args.stdout:
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
    else:
        save_results(all_results, args.o, args.f)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass