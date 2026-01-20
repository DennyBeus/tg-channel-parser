#!/usr/bin/env python3
import os
import sys
import re
import asyncio
import logging
import json
import argparse
        
from datetime import datetime

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
def remove_links(text: str) -> str:
    if not text: return ""
    text = re.sub(r'https?://[^\s\n\)]+', '', text)
    text = re.sub(r'[^\s\n]*t\.me/[^\s\n\)]+', '', text)
    text = re.sub(r'@[\w]+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    return re.sub(r'\n{3,}', '\n\n', text).strip()

def extract_plain_text(message) -> str:
    text = message.text or message.caption or ""
    return remove_links(text) if text else ""

# ---------------- Pyrogram client ----------------
app = Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE)

async def resolve_channel(app_client: Client, channel_raw: str):
    clean = channel_raw.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "").strip()
    try:
        chat = await app_client.get_chat(clean)
        return chat.id
    except Exception as e:
        logger.error(f"Failed to resolve {channel_raw}: {e}")
        return None

# ---------------- Core Parsing Logic ----------------
async def parse_channel(channel_id: int, start_date: datetime, end_date: datetime, limit: int):
    messages_data = []
    count = 0
    
    logger.info(f"Parsing from {start_date.date()} to {end_date.date()} (Limit: {limit or 'None'})")
    
    async for message in app.get_chat_history(channel_id):
        # Проверка лимита
        if limit and count >= limit:
            break
            
        # Проверка дат
        msg_date = message.date
        if msg_date < start_date:
            break
        if msg_date > end_date:
            continue

        text = extract_plain_text(message)
        if text:
            messages_data.append({
                'text': text,
                'date': msg_date.strftime("%d.%m.%Y %H:%M:%S")
            })
            count += 1
            if count % 50 == 0: logger.info(f"Parsed {count} messages...")

    return messages_data

def save_results(messages: list, filename: str, fmt: str):
    # Если передан только имя файла, сохраняем в Downloads
    if not os.path.isabs(filename) and os.sep not in filename:
        full_path = os.path.join(DOWNLOADS_DIR, f"{filename}.{fmt}")
    else:
        full_path = filename if filename.endswith(fmt) else f"{filename}.{fmt}"

    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    if fmt == 'json':
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=4)
    else:
        with open(full_path, 'w', encoding='utf-8') as f:
            for m in messages:
                f.write(f"{m['text']}\n\n---\n\n")
    
    logger.info(f"Saved {len(messages)} items to {full_path}")

# ---------------- Execution ----------------
async def main():
    parser = argparse.ArgumentParser(description="Telegram Channel Parser CLI")
    parser.add_argument("channel", nargs='?', help="Channel URL or @username")
    parser.add_argument("-s", "--start", help="Start date DD.MM.YYYY", default="01.01.1970")
    parser.add_argument("-e", "--end", help="End date DD.MM.YYYY", default=None)
    parser.add_argument("-o", "--output", help="Output filename", default="result")
    parser.add_argument("-f", "--format", choices=['txt', 'json'], default='txt', help="Output format")
    parser.add_argument("-l", "--limit", type=int, help="Max messages to parse")
    parser.add_argument("--auth", action="store_true", help="Run authorization mode")

    args = parser.parse_args()

    if args.auth:
        await app.start()
        print("Successfully authorized!")
        await app.stop()
        return

    if not args.channel:
        parser.print_help()
        return

    # Обработка дат
    start_dt = datetime.strptime(args.start, "%d.%m.%Y")
    end_dt = datetime.strptime(args.end, "%d.%m.%Y") if args.end else datetime.now()

    os.makedirs(DATA_DIR, exist_ok=True)
    
    await app.start()
    try:
        channel_id = await resolve_channel(app, args.channel)
        if channel_id:
            results = await parse_channel(channel_id, start_dt, end_dt, args.limit)
            if results:
                save_results(results, args.output, args.format)
            else:
                logger.warning("No messages found.")
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())