#!/usr/bin/env python3
import os
import sys
import re
import asyncio
import logging
from datetime import datetime

# Загрузить переменные из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()  # Загружает переменные из .env файла
except ImportError:
    pass  # Если python-dotenv не установлен, используем только системные переменные

# Установить event loop ДО импорта Pyrogram (для Python 3.14+)
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------- Configuration ----------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE_NUMBER", "")
# session file path requested by you:
DATA_DIR = os.getenv("DATA_DIR", "./data")
SESSION_PATH = os.path.join(DATA_DIR, "user")

RESULT_FILE = "result.txt"

# ---------------- Helpers ----------------
def ensure_data_dir():
    """Создать директорию для данных, если её нет"""
    os.makedirs(DATA_DIR, exist_ok=True)

# ---------------- Text processing ----------------
def remove_links(text: str) -> str:
    """
    Remove all links from text while preserving the rest of the content.
    Handles various link formats: http://, https://, t.me/, @username, etc.
    Preserves line breaks in the text.
    """
    if not text:
        return ""
    
    # Remove URLs (http://, https://) - match until space, newline, or end of string
    text = re.sub(r'https?://[^\s\n\)]+', '', text)
    
    # Remove t.me links (with or without protocol)
    text = re.sub(r'[^\s\n]*t\.me/[^\s\n\)]+', '', text)
    
    # Remove @mentions/usernames (these are typically links in Telegram)
    text = re.sub(r'@[\w]+', '', text)
    
    # Clean up multiple spaces (but preserve single spaces and newlines)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Clean up spaces at the start/end of lines
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    text = '\n'.join(lines)
    
    # Remove empty lines (more than 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def extract_plain_text(message) -> str:
    """
    Extract plain text from message, removing links.
    Returns empty string if message has no text.
    In Pyrogram, message.text and message.caption are already plain text strings.
    """
    text = ""
    if message.text:
        # message.text is already a plain text string
        text = message.text
    elif message.caption:
        # message.caption is already a plain text string
        text = message.caption
    
    if not text:
        return ""
    
    # Remove links
    text = remove_links(text)
    
    return text

# ---------------- Pyrogram client ----------------
# Note: pass SESSION_PATH as session name; Pyrogram will create the file there.
app = Client(
    SESSION_PATH,
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE,
    # workers default is fine; we keep single event loop handling
)

# ---------------- Channel resolver ----------------
async def resolve_channel(app_client: Client, channel_raw: str):
    """
    Resolve channel from URL or username to chat ID.
    Returns chat ID or None if failed.
    """
    if not channel_raw:
        return None
    
    channel_raw = channel_raw.strip()
    
    # numeric id
    if channel_raw.startswith("-100") or channel_raw.startswith("-"):
        try:
            chat_id = int(channel_raw)
            logger.info(f"Chat ID added directly: {channel_raw}")
            return chat_id
        except ValueError:
            logger.error(f"Invalid numeric ID: {channel_raw}")
            return None

    # Clean URL: remove https://t.me/, http://t.me/, @
    clean = channel_raw.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "").strip()
    try:
        chat = await app_client.get_chat(clean)
        logger.info(f"Resolved: {clean} → ID {chat.id}")
        return chat.id
    except Exception as e:
        logger.error(f"Failed to resolve {channel_raw}: {e}")
        return None

# ---------------- Parse channel from date ----------------
async def parse_channel_from_date(channel_id: int, start_date: datetime):
    """
    Parse all messages from channel starting from start_date to today.
    Returns list of text messages sorted by date (newest first).
    """
    logger.info(f"Parsing messages from channel {channel_id} from {start_date.strftime('%d.%m.%Y')} to today")
    
    messages_with_text = []
    today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    try:
        async for message in app.get_chat_history(channel_id):
            # Check if message date is before start_date, stop if so
            if message.date and message.date < start_date:
                logger.info(f"Reached start date, stopping parsing")
                break
            
            # Check if message date is after today (shouldn't happen, but safety check)
            if message.date and message.date > today:
                continue
            
            # Extract plain text
            text = extract_plain_text(message)
            
            # Skip messages without text
            if not text:
                continue
            
            # Store message with its date for sorting
            messages_with_text.append({
                'text': text,
                'date': message.date if message.date else datetime.now()
            })
            
            logger.info(f"Parsed message {message.id} from {message.date.strftime('%d.%m.%Y %H:%M') if message.date else 'unknown'}")
            
            # Small throttle to avoid rate limiting
            await asyncio.sleep(0.1)
    
    except Exception as e:
        logger.error(f"Error parsing channel {channel_id}: {e}")
    
    # Sort by date descending (newest first)
    messages_with_text.sort(key=lambda x: x['date'], reverse=True)
    
    logger.info(f"Parsed {len(messages_with_text)} messages with text")
    return messages_with_text

def save_to_file(messages: list, filename: str):
    """
    Save messages to file, each separated by '---'.
    Messages should be sorted newest first.
    Format: ---\n\n<text>\n\n---
    """
    logger.info(f"Saving {len(messages)} messages to {filename}")
    
    with open(filename, 'w', encoding='utf-8') as f:
        for i, msg_data in enumerate(messages):
            # Write separator before each message (except before first)
            if i > 0:
                f.write("\n")
            f.write("---\n\n")
            
            # Write message text
            f.write(msg_data['text'])
            
            # Write separator after message
            f.write("\n\n---")
    
    logger.info(f"Successfully saved messages to {filename}")

# ---------------- Entry point ----------------
def remove_session_files(session_path: str):
    """
    Remove session files that Pyrogram may create.
    """
    candidates = [
        session_path,
        session_path + ".session",
        session_path + "-journal",
        session_path + ".session-journal",
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                os.remove(p)
                logger.info(f"Removed session file: {p}")
        except Exception as e:
            logger.warning(f"Could not remove {p}: {e}")

def parse_date(date_str: str) -> datetime:
    """
    Parse date from DD.MM.YYYY format.
    Returns datetime object set to 00:00:00 UTC of that day.
    Pyrogram message dates are in UTC, so we use UTC for consistency.
    """
    try:
        # Parse as local date, then convert to UTC (naive UTC datetime)
        # For simplicity, we'll treat it as UTC directly since Telegram uses UTC
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        # Return as naive UTC datetime (Pyrogram uses naive UTC datetimes)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        raise ValueError(f"Invalid date format. Expected DD.MM.YYYY, got: {date_str}")

def create_event_loop_and_run(coro):
    """
    Create a dedicated event loop and run the coroutine.
    This avoids "attached to a different loop" issues.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # shutdown async generators cleanly
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()

async def main_async():
    # Ensure data directory exists
    ensure_data_dir()
    
    # AUTH mode: delete session and perform auth, then exit
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        remove_session_files(SESSION_PATH)
        logger.info("Starting authorization (interactive). Follow prompts in stdout/stderr.")
        await app.start()
        logger.info("Authorization completed (session saved). Stopping client.")
        return

    # PARSE mode (default): parse channel from date
    logger.info("Starting channel parser")
    
    # Request channel URL
    print("\nEnter Telegram channel URL (e.g., https://t.me/channel_name):")
    channel_url = input().strip()
    
    if not channel_url:
        logger.error("Channel URL is required")
        return
    
    # Request start date
    print("\nEnter start date in format DD.MM.YYYY:")
    date_str = input().strip()
    
    if not date_str:
        logger.error("Start date is required")
        return
    
    try:
        start_date = parse_date(date_str)
    except ValueError as e:
        logger.error(str(e))
        return
    
    logger.info(f"Parsing channel: {channel_url}")
    logger.info(f"Start date: {start_date.strftime('%d.%m.%Y')}")
    
    # Start client
    await app.start()
    logger.info("Client started")
    
    try:
        # Resolve channel
        channel_id = await resolve_channel(app, channel_url)
        if not channel_id:
            logger.error(f"Cannot resolve channel: {channel_url}")
            return
        
        # Parse messages
        messages = await parse_channel_from_date(channel_id, start_date)
        
        if not messages:
            logger.warning("No messages found with text in the specified date range")
            return
        
        # Save to file
        save_to_file(messages, RESULT_FILE)
        
        logger.info(f"Parsing completed. Results saved to {RESULT_FILE}")
    
    finally:
        await app.stop()

if __name__ == "__main__":
    # Run main_async in a fresh event loop to avoid cross-loop issues.
    create_event_loop_and_run(main_async())

