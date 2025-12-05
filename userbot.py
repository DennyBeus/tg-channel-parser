#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import requests
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

CHANNELS_RAW = os.getenv("CHANNELS", "").split()
WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
WEBHOOK_TOKEN = os.getenv("N8N_WEBHOOK_TOKEN")
WEBHOOK_HEADER = os.getenv("N8N_WEBHOOK_HEADER", "X-N8N-Auth")

RETRY_INTERVAL = int(os.getenv("RETRY_INTERVAL", 30))  # seconds between resend attempts
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 10))    # polling interval

DB_PATH = os.path.join(DATA_DIR, "pending.db")
LAST_ID_PATH = os.path.join(DATA_DIR, "last_message_ids.json")
CHANNEL_IDS = []

# ---------------- Helpers: sending ----------------
def send_or_queue(payload: dict) -> bool:
    """
    Try to send payload to n8n. On failure, save to queue.
    Returns True on success, False otherwise.
    """
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL not configured; saving to queue")
        save_to_queue(payload)
        return False

    headers = {}
    if WEBHOOK_TOKEN:
        headers[WEBHOOK_HEADER] = WEBHOOK_TOKEN

    try:
        r = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            logger.info(f"Sent to n8n: {payload.get('chat_title')} ({payload.get('message_id')})")
            return True
        else:
            logger.error(f"n8n returned HTTP {r.status_code}; saving to queue")
    except Exception as e:
        logger.error(f"Error sending to n8n: {e}; saving to queue")

    save_to_queue(payload)
    return False

# ---------------- Database / queue ----------------
def ensure_data_dir():
    """Создать директорию для данных, если её нет"""
    os.makedirs(DATA_DIR, exist_ok=True)

def init_db():
    ensure_data_dir()  # Убедиться, что директория существует
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_to_queue(payload: dict):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO queue (payload, created_at) VALUES (?, ?)",
                (json.dumps(payload, ensure_ascii=False), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    logger.warning("Message saved to local queue")

def resend_queue():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, payload FROM queue ORDER BY id ASC")
    rows = cur.fetchall()

    for msg_id, payload_json in rows:
        try:
            payload = json.loads(payload_json)
        except Exception:
            logger.error(f"Malformed JSON in queue id {msg_id}, removing")
            cur.execute("DELETE FROM queue WHERE id = ?", (msg_id,))
            conn.commit()
            continue

        headers = {}
        if WEBHOOK_TOKEN:
            headers[WEBHOOK_HEADER] = WEBHOOK_TOKEN

        try:
            r = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                logger.info(f"Resent from queue: {msg_id}")
                cur.execute("DELETE FROM queue WHERE id = ?", (msg_id,))
                conn.commit()
            else:
                logger.error(f"n8n HTTP error {r.status_code} while resending, stopping resender")
                conn.close()
                return
        except Exception as e:
            logger.error(f"Connection error during queue resend: {e}; will retry later")
            conn.close()
            return

    conn.close()

async def background_resender():
    while True:
        try:
            resend_queue()
        except Exception as e:
            logger.exception(f"Unexpected error in resend_queue: {e}")
        await asyncio.sleep(RETRY_INTERVAL)

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
async def resolve_channels(app_client: Client, channels_raw):
    resolved = []
    for ch in channels_raw:
        if not ch:
            continue
        ch = ch.strip()
        # numeric id
        if ch.startswith("-100") or ch.startswith("-"):
            try:
                resolved.append(int(ch))
                logger.info(f"Chat ID added directly: {ch}")
            except ValueError:
                logger.error(f"Invalid numeric ID: {ch}")
            continue

        clean = ch.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "").strip()
        try:
            chat = await app_client.get_chat(clean)
            resolved.append(chat.id)
            logger.info(f"Resolved: {clean} → ID {chat.id}")
        except Exception as e:
            logger.error(f"Failed to resolve {ch}: {e}")
    return resolved

# ---------------- Last IDs store ----------------
def load_last_ids():
    if os.path.exists(LAST_ID_PATH):
        with open(LAST_ID_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_last_ids(last_ids):
    ensure_data_dir()  # Убедиться, что директория существует
    with open(LAST_ID_PATH, "w", encoding="utf-8") as f:
        json.dump(last_ids, f)

# ---------------- Process message ----------------
def process_message(message):
    # Получаем текст в формате Markdown
    text_md = ""
    if message.text:
        text_md = message.text.markdown
    elif message.caption:
        text_md = message.caption.markdown
    
    payload = {
        "chat_id": message.chat.id,
        "chat_title": message.chat.title or (message.chat.username if hasattr(message.chat, "username") else ""),
        "message_id": message.id,
        "date": int(message.date.timestamp()) if message.date else None,
        "text": text_md,
    }
    send_or_queue(payload)

# ---------------- Read history (exact count) ----------------
async def read_history(channel_id: int, count: int):
    """
    Read exactly <count> messages backwards from current end (latest).
    """
    logger.info(f"Reading last {count} messages from {channel_id}")

    messages = []
    async for msg in app.get_chat_history(channel_id, limit=count):
        messages.append(msg)
        if len(messages) >= count:
            break

    logger.info(f"Fetched {len(messages)} messages")

    for msg in reversed(messages):  # oldest -> newest
        try:
            process_message(msg)
        except Exception as e:
            logger.exception(f"Error processing message {getattr(msg, 'id', '<no id>')}: {e}")
        await asyncio.sleep(0.1)  # throttle

    logger.info("History read complete")

# ---------------- Polling (daemon) ----------------
async def poll_channels():
    last_ids = load_last_ids()
    while True:
        for chat_id in CHANNEL_IDS:
            try:
                messages = []
                async for msg in app.get_chat_history(chat_id, limit=50):
                    messages.append(msg)

                for msg in reversed(messages):
                    last_id = last_ids.get(str(chat_id), 0)
                    if msg.id > last_id:
                        process_message(msg)
                        last_ids[str(chat_id)] = msg.id
            except Exception as e:
                logger.error(f"Error polling {chat_id}: {e}")
        save_last_ids(last_ids)
        await asyncio.sleep(POLL_INTERVAL)

# ---------------- Entry point ----------------
def remove_session_files(session_path: str):
    """
    Remove session files that Pyrogram may create.
    The user requested session path: /data/user.session
    Pyrogram may create that path exactly.
    Also try other common variants just in case.
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

def build_channel_list_from_env():
    lst = []
    for item in CHANNELS_RAW:
        if item and item.strip():
            lst.append(item.strip())
    return lst

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
    # determine mode
    mode = sys.argv[1] if len(sys.argv) > 1 else "daemon"
    logger.info(f"Mode: {mode}")

    init_db()

    # AUTH mode: delete session and perform auth, then exit
    if mode == "auth":
        remove_session_files(SESSION_PATH)
        logger.info("Starting authorization (interactive). Follow prompts in stdout/stderr.")
        # start client (it will ask for phone/code interactively)
        await app.start()
        logger.info("Authorization completed (session saved). Stopping client.")
        #await app.stop()
        return

    # HISTORY mode
    if mode == "history":
        if len(sys.argv) < 4:
            logger.error("Usage: python userbot.py history <channel> <count>")
            return
        channel_raw = sys.argv[2]
        try:
            count = int(sys.argv[3])
        except ValueError:
            logger.error("Count must be an integer")
            return

        # start client, resolve channel, read history, stop client
        await app.start()
        try:
            resolved = await resolve_channels(app, [channel_raw])
            if not resolved:
                logger.error(f"Cannot resolve channel: {channel_raw}")
                await app.stop()
                return
            channel_id = resolved[0]
            await read_history(channel_id, count)
        finally:
            pass
#            await app.stop()
        return

    # DAEMON mode (default)
    # start client, resolve channels from env, start background tasks
    await app.start()
    logger.info("UserBot started (daemon)")

    global CHANNEL_IDS
    CHANNEL_IDS = await resolve_channels(app, build_channel_list_from_env())
    if not CHANNEL_IDS:
        logger.error("No channels/groups resolved! Check CHANNELS in environment.")
        await app.stop()
        return

    # start background tasks
    loop = asyncio.get_event_loop()
    loop.create_task(background_resender())
    loop.create_task(poll_channels())

    # block forever
    try:
        await asyncio.Event().wait()
    finally:
        await app.stop()

if __name__ == "__main__":
    # Run main_async in a fresh event loop to avoid cross-loop issues.
    create_event_loop_and_run(main_async())

