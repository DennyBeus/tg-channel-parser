#!/usr/bin/env python3
import asyncio
import logging
import os
import shlex
import time
import uuid
from glob import glob

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_ID = int(os.getenv("TELEGRAM_BOT_OWNER_ID", "0"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/tmp")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
SESSION_PATH = os.path.join(DATA_DIR, "user")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE_NUMBER", "")

job_running = False

router = Router()

# --- Localization -----------------------------------------------------------

DEFAULT_LANG = "en"

# Per-user language preference (user_id -> "en" | "ru"). Defaults to DEFAULT_LANG.
user_lang: dict[int, str] = {}


def get_lang(user_id: int | None) -> str:
    if user_id is None:
        return DEFAULT_LANG
    return user_lang.get(user_id, DEFAULT_LANG)


TEXTS = {
    "start": {
        "en": (
            "<b>grabogram is here</b>\n\n"
            "<b>Choose an action:</b>\n"
            "/parse — start parsing\n"
            "/auth — refresh session\n"
            "/cancel — cancel the current action"
        ),
        "ru": (
            "<b>grabogram is here</b>\n\n"
            "<b>Выбери действие:</b>\n"
            "/parse — начать парсинг\n"
            "/auth — обновить сессию\n"
            "/cancel — отменить текущее действие"
        ),
    },
    "btn_help": {"en": "Help", "ru": "Помощь"},
    "btn_lang_ru": {"en": "🇷🇺 Русский", "ru": "🇷🇺 Русский"},
    "btn_lang_en": {"en": "🇬🇧 English", "ru": "🇬🇧 English"},
    "help": {
        "en": (
            "<b>Direct command:</b>\n"
            "<code>/parse https://t.me/channel -s 01.01.2024 -e 31.12.2024 -f json -k bitcoin</code>\n\n"
            "<b>Parameters:</b>\n"
            "-s [DATE] — start (DD.MM.YYYY)\n"
            "-e [DATE] — end (DD.MM.YYYY)\n"
            "-f [txt|json] — output format (txt by default)\n"
            "-l [NUM] — message limit\n"
            "-k [WORDS] — keywords separated by spaces\n"
            "-j — strip emoji\n"
            "-r — oldest to newest\n\n"
            "<b>Other commands:</b>\n"
            "/auth — refresh session\n"
            "/cancel — cancel the current action"
        ),
        "ru": (
            "<b>Прямая команда:</b>\n"
            "<code>/parse https://t.me/channel -s 01.01.2024 -e 31.12.2024 -f json -k bitcoin</code>\n\n"
            "<b>Параметры:</b>\n"
            "-s [DATE] — начало (ДД.ММ.ГГГГ)\n"
            "-e [DATE] — конец (ДД.ММ.ГГГГ)\n"
            "-f [txt|json] — формат вывода (по умолчанию txt)\n"
            "-l [NUM] — лимит сообщений\n"
            "-k [WORDS] — ключевые слова через пробел\n"
            "-j — убрать эмодзи\n"
            "-r — от старых к новым\n\n"
            "<b>Другие команды:</b>\n"
            "/auth — обновить сессию\n"
            "/cancel — отменить текущее действие"
        ),
    },
    "job_running": {
        "en": "Parsing is already running, please wait.",
        "ru": "Уже идёт парсинг, подождите.",
    },
    "parse_started": {"en": "Parsing started...", "ru": "Парсинг запущен..."},
    "parse_error": {
        "en": "Parsing error:\n<pre>{err}</pre>",
        "ru": "Ошибка парсинга:\n<pre>{err}</pre>",
    },
    "no_messages": {
        "en": "No messages found for the given criteria.",
        "ru": "Сообщений не найдено по заданным критериям.",
    },
    "ask_channel": {
        "en": "Send the channel URL (e.g.: https://t.me/durov)",
        "ru": "Отправь URL канала (например: https://t.me/durov)",
    },
    "args_error": {
        "en": "Argument parsing error: {err}",
        "ru": "Ошибка разбора аргументов: {err}",
    },
    "btn_skip": {"en": "Skip", "ru": "Пропустить"},
    "ask_dates": {
        "en": "Specify the period in the format: 01.01.2024-31.12.2024\nOr tap «Skip».",
        "ru": "Укажи период в формате: 01.01.2024-31.12.2024\nИли нажми «Пропустить».",
    },
    "dates_bad_format": {
        "en": "Invalid format. Enter: 01.01.2024-31.12.2024 or tap «Skip».",
        "ru": "Неверный формат. Введи: 01.01.2024-31.12.2024 или нажми «Пропустить».",
    },
    "ask_limit": {
        "en": "Message limit per channel? Enter a number.\nOr tap «Skip».",
        "ru": "Лимит сообщений на канал? Введи число.\nИли нажми «Пропустить».",
    },
    "limit_bad": {
        "en": "Enter a whole number or tap «Skip».",
        "ru": "Введи целое число или нажми «Пропустить».",
    },
    "ask_keywords": {
        "en": "Enter keywords separated by spaces (post filter).\nOr tap «Skip».",
        "ru": "Введи ключевые слова через пробел (фильтр постов).\nИли нажми «Пропустить».",
    },
    "btn_order_old": {"en": "Oldest to newest", "ru": "От старых к новым"},
    "btn_order_new": {"en": "Newest to oldest", "ru": "От новых к старым"},
    "ask_order": {"en": "Message order?", "ru": "Порядок сообщений?"},
    "btn_emoji_remove": {"en": "Remove", "ru": "Удалить"},
    "btn_emoji_keep": {"en": "Keep", "ru": "Оставить"},
    "ask_emoji": {"en": "Emoji in text?", "ru": "Emoji в тексте?"},
    "ask_format": {"en": "Choose the output format:", "ru": "Выбери формат вывода:"},
    "auth_env_error": {
        "en": "Error: API_ID, API_HASH or PHONE_NUMBER are not set in .env",
        "ru": "Ошибка: API_ID, API_HASH или PHONE_NUMBER не заданы в .env",
    },
    "auth_sending_code": {
        "en": "Sending a code request to {phone}...",
        "ru": "Отправляю запрос кода на номер {phone}...",
    },
    "auth_code_sent": {
        "en": "Code sent. Enter it in the format: <code>1 2 3 4 5</code>",
        "ru": "Код отправлен. Введи его в формате: <code>1 2 3 4 5</code>",
    },
    "auth_code_request_failed": {
        "en": "Could not request the code: {err}",
        "ru": "Не удалось запросить код: {err}",
    },
    "auth_expired": {
        "en": "Authorization session expired. Start over: /auth",
        "ru": "Сессия авторизации устарела. Начни заново: /auth",
    },
    "auth_success": {
        "en": "Authorization successful! Session refreshed.",
        "ru": "Авторизация успешна! Сессия обновлена.",
    },
    "auth_need_2fa": {
        "en": "2FA password required. Enter it:",
        "ru": "Требуется пароль 2FA. Введи его:",
    },
    "auth_error": {
        "en": "Authorization error: {err}",
        "ru": "Ошибка авторизации: {err}",
    },
    "auth_2fa_bad": {
        "en": "Invalid 2FA password: {err}",
        "ru": "Неверный пароль 2FA: {err}",
    },
    "cancelled": {"en": "Action cancelled.", "ru": "Действие отменено."},
    "cmd_start": {"en": "Main menu", "ru": "Главное меню"},
    "cmd_parse": {"en": "Start parsing a channel", "ru": "Запустить парсинг канала"},
    "cmd_auth": {"en": "Refresh session", "ru": "Обновить сессию"},
    "cmd_cancel": {"en": "Cancel the current action", "ru": "Отменить текущее действие"},
}


def t(user_id: int | None, key: str, **kwargs) -> str:
    lang = get_lang(user_id)
    text = TEXTS[key].get(lang, TEXTS[key][DEFAULT_LANG])
    return text.format(**kwargs) if kwargs else text


def start_keyboard(user_id: int | None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(user_id, "btn_lang_ru"), callback_data="lang_ru"),
            InlineKeyboardButton(text=t(user_id, "btn_lang_en"), callback_data="lang_en"),
        ],
        [InlineKeyboardButton(text=t(user_id, "btn_help"), callback_data="menu_help")],
    ])


class OwnerFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id == OWNER_ID


class ParseStates(StatesGroup):
    channel = State()
    dates = State()
    limit = State()
    keywords = State()
    reverse = State()
    no_emoji = State()
    fmt = State()


class AuthStates(StatesGroup):
    waiting_code = State()
    waiting_2fa = State()


def cleanup_old_tmp():
    threshold = time.time() - 3600
    for path in glob(os.path.join(OUTPUT_DIR, "*")):
        try:
            if os.path.getmtime(path) < threshold:
                os.remove(path)
        except OSError:
            pass


async def run_parse_job(bot: Bot, chat_id: int, parser_args: list[str], user_id: int | None = None) -> None:
    global job_running
    if job_running:
        await bot.send_message(chat_id, t(user_id, "job_running"))
        return

    output_file = os.path.join(OUTPUT_DIR, uuid.uuid4().hex)
    cmd = ["python", "/app/parser.py"] + parser_args + ["-o", output_file]

    job_running = True
    await bot.send_message(chat_id, t(user_id, "parse_started"))
    logger.info(f"Running: {' '.join(cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )
        stdout, stderr = await proc.communicate()
    finally:
        job_running = False

    if proc.returncode != 0:
        err = stderr.decode(errors="replace")[-2000:]
        await bot.send_message(chat_id, t(user_id, "parse_error", err=err), parse_mode="HTML")
        return

    for ext in (".json", ".txt"):
        path = output_file + ext
        if os.path.exists(path):
            try:
                await bot.send_document(chat_id, FSInputFile(path))
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
            return

    await bot.send_message(chat_id, t(user_id, "no_messages"))


@router.message(OwnerFilter(), Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    await message.answer(
        t(uid, "start"),
        parse_mode="HTML",
        reply_markup=start_keyboard(uid),
    )


@router.callback_query(OwnerFilter(), F.data.in_({"lang_ru", "lang_en"}))
async def cb_set_lang(callback: CallbackQuery):
    uid = callback.from_user.id
    new_lang = "ru" if callback.data == "lang_ru" else "en"
    if get_lang(uid) == new_lang:
        await callback.answer()
        return
    user_lang[uid] = new_lang
    try:
        await callback.message.edit_text(
            t(uid, "start"),
            parse_mode="HTML",
            reply_markup=start_keyboard(uid),
        )
    except Exception:
        # Ignore "message is not modified" or transient edit errors.
        pass
    await callback.answer()


@router.callback_query(OwnerFilter(), F.data == "menu_help")
async def cb_help(callback: CallbackQuery):
    await callback.message.answer(t(callback.from_user.id, "help"), parse_mode="HTML")
    await callback.answer()


@router.message(OwnerFilter(), Command("parse"))
async def cmd_parse(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    args_text = message.text[len("/parse"):].strip()
    if not args_text:
        await state.set_state(ParseStates.channel)
        await message.answer(t(uid, "ask_channel"))
        return
    try:
        args = shlex.split(args_text)
    except ValueError as e:
        await message.answer(t(uid, "args_error", err=e))
        return
    await run_parse_job(message.bot, message.chat.id, args, uid)


@router.message(OwnerFilter(), ParseStates.channel)
async def state_channel(message: Message, state: FSMContext):
    uid = message.from_user.id
    channel = message.text.strip()
    await state.update_data(channel=channel)
    await state.set_state(ParseStates.dates)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(uid, "btn_skip"), callback_data="skip_dates")],
    ])
    await message.answer(t(uid, "ask_dates"), reply_markup=keyboard)


@router.callback_query(OwnerFilter(), F.data == "skip_dates", ParseStates.dates)
async def cb_skip_dates(callback: CallbackQuery, state: FSMContext):
    await state.update_data(start=None, end=None)
    await _ask_limit(callback.message, state, callback.from_user.id)
    await callback.answer()


@router.message(OwnerFilter(), ParseStates.dates)
async def state_dates(message: Message, state: FSMContext):
    uid = message.from_user.id
    text = message.text.strip()
    if "-" in text:
        parts = text.split("-", 1)
        await state.update_data(start=parts[0].strip(), end=parts[1].strip())
    else:
        await message.answer(t(uid, "dates_bad_format"))
        return
    await _ask_limit(message, state, uid)


async def _ask_limit(message: Message, state: FSMContext, uid: int):
    await state.set_state(ParseStates.limit)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(uid, "btn_skip"), callback_data="skip_limit")],
    ])
    await message.answer(t(uid, "ask_limit"), reply_markup=keyboard)


@router.callback_query(OwnerFilter(), F.data == "skip_limit", ParseStates.limit)
async def cb_skip_limit(callback: CallbackQuery, state: FSMContext):
    await state.update_data(limit=None)
    await _ask_keywords(callback.message, state, callback.from_user.id)
    await callback.answer()


@router.message(OwnerFilter(), ParseStates.limit)
async def state_limit(message: Message, state: FSMContext):
    uid = message.from_user.id
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(t(uid, "limit_bad"))
        return
    await state.update_data(limit=text)
    await _ask_keywords(message, state, uid)


async def _ask_keywords(message: Message, state: FSMContext, uid: int):
    await state.set_state(ParseStates.keywords)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(uid, "btn_skip"), callback_data="skip_keywords")],
    ])
    await message.answer(t(uid, "ask_keywords"), reply_markup=keyboard)


@router.callback_query(OwnerFilter(), F.data == "skip_keywords", ParseStates.keywords)
async def cb_skip_keywords(callback: CallbackQuery, state: FSMContext):
    await state.update_data(keywords=None)
    await _ask_reverse(callback.message, state, callback.from_user.id)
    await callback.answer()


@router.message(OwnerFilter(), ParseStates.keywords)
async def state_keywords(message: Message, state: FSMContext):
    await state.update_data(keywords=message.text.strip())
    await _ask_reverse(message, state, message.from_user.id)


async def _ask_reverse(message: Message, state: FSMContext, uid: int):
    await state.set_state(ParseStates.reverse)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(uid, "btn_order_old"), callback_data="order_old"),
            InlineKeyboardButton(text=t(uid, "btn_order_new"), callback_data="order_new"),
        ],
    ])
    await message.answer(t(uid, "ask_order"), reply_markup=keyboard)


@router.callback_query(OwnerFilter(), F.data.in_({"order_old", "order_new"}), ParseStates.reverse)
async def cb_reverse(callback: CallbackQuery, state: FSMContext):
    await state.update_data(reverse=(callback.data == "order_old"))
    await _ask_no_emoji(callback.message, state, callback.from_user.id)
    await callback.answer()


async def _ask_no_emoji(message: Message, state: FSMContext, uid: int):
    await state.set_state(ParseStates.no_emoji)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(uid, "btn_emoji_remove"), callback_data="emoji_remove"),
            InlineKeyboardButton(text=t(uid, "btn_emoji_keep"), callback_data="emoji_keep"),
        ],
    ])
    await message.answer(t(uid, "ask_emoji"), reply_markup=keyboard)


@router.callback_query(OwnerFilter(), F.data.in_({"emoji_remove", "emoji_keep"}), ParseStates.no_emoji)
async def cb_no_emoji(callback: CallbackQuery, state: FSMContext):
    await state.update_data(no_emoji=(callback.data == "emoji_remove"))
    await state.set_state(ParseStates.fmt)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="txt", callback_data="fmt_txt"),
            InlineKeyboardButton(text="json", callback_data="fmt_json"),
        ],
    ])
    await callback.message.answer(t(callback.from_user.id, "ask_format"), reply_markup=keyboard)
    await callback.answer()


@router.callback_query(OwnerFilter(), F.data.in_({"fmt_txt", "fmt_json"}), ParseStates.fmt)
async def cb_fmt(callback: CallbackQuery, state: FSMContext):
    fmt = callback.data.split("_")[1]
    await state.update_data(fmt=fmt)
    await _run_from_state(callback.message, state, callback.from_user.id)
    await callback.answer()


async def _run_from_state(message: Message, state: FSMContext, uid: int):
    data = await state.get_data()
    await state.clear()
    args = [data["channel"]]
    if data.get("start"):
        args += ["-s", data["start"]]
    if data.get("end"):
        args += ["-e", data["end"]]
    if data.get("fmt"):
        args += ["-f", data["fmt"]]
    if data.get("limit"):
        args += ["-l", data["limit"]]
    if data.get("no_emoji"):
        args += ["-j"]
    if data.get("reverse"):
        args += ["-r"]
    if data.get("keywords"):
        args += ["-k"] + data["keywords"].split()
    await run_parse_job(message.bot, message.chat.id, args, uid)


@router.message(OwnerFilter(), Command("auth"))
async def cmd_auth(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if not API_ID or not API_HASH or not PHONE:
        await message.answer(t(uid, "auth_env_error"))
        return
    await message.answer(t(uid, "auth_sending_code", phone=PHONE))
    try:
        from pyrogram import Client as PyroClient
        client = PyroClient(SESSION_PATH, api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        sent = await client.send_code(PHONE)
        await state.update_data(phone_code_hash=sent.phone_code_hash)
        await state.set_state(AuthStates.waiting_code)
        await state.update_data(_client_ref=True)
        # Store client in bot data for use in next handler
        message.bot._pyrogram_client = client
        await message.answer(t(uid, "auth_code_sent"), parse_mode="HTML")
    except Exception as e:
        await message.answer(t(uid, "auth_code_request_failed", err=e))


@router.message(OwnerFilter(), AuthStates.waiting_code)
async def auth_code(message: Message, state: FSMContext):
    uid = message.from_user.id
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    phone_code_hash = data.get("phone_code_hash")
    client = getattr(message.bot, "_pyrogram_client", None)

    if client is None or not phone_code_hash:
        await state.clear()
        await message.answer(t(uid, "auth_expired"))
        return

    try:
        from pyrogram.errors import SessionPasswordNeeded
        await client.sign_in(PHONE, phone_code_hash, code)
        await client.disconnect()
        message.bot._pyrogram_client = None
        await state.clear()
        await message.answer(t(uid, "auth_success"))
        logger.info("Re-auth successful via bot")
    except SessionPasswordNeeded:
        await state.set_state(AuthStates.waiting_2fa)
        await message.answer(t(uid, "auth_need_2fa"))
    except Exception as e:
        await client.disconnect()
        message.bot._pyrogram_client = None
        await state.clear()
        await message.answer(t(uid, "auth_error", err=e))


@router.message(OwnerFilter(), AuthStates.waiting_2fa)
async def auth_2fa(message: Message, state: FSMContext):
    uid = message.from_user.id
    password = message.text.strip()
    client = getattr(message.bot, "_pyrogram_client", None)

    if client is None:
        await state.clear()
        await message.answer(t(uid, "auth_expired"))
        return

    try:
        await client.check_password(password)
        await client.disconnect()
        message.bot._pyrogram_client = None
        await state.clear()
        await message.answer(t(uid, "auth_success"))
        logger.info("Re-auth with 2FA successful via bot")
    except Exception as e:
        await client.disconnect()
        message.bot._pyrogram_client = None
        await state.clear()
        await message.answer(t(uid, "auth_2fa_bad", err=e))


@router.message(OwnerFilter(), Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    client = getattr(message.bot, "_pyrogram_client", None)
    if client is not None:
        try:
            await client.disconnect()
        except Exception:
            pass
        message.bot._pyrogram_client = None
    await state.clear()
    await message.answer(t(message.from_user.id, "cancelled"))


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    if not OWNER_ID:
        raise RuntimeError("TELEGRAM_BOT_OWNER_ID is not set")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cleanup_old_tmp()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Default (English) command list.
    await bot.set_my_commands([
        BotCommand(command="start", description=TEXTS["cmd_start"]["en"]),
        BotCommand(command="parse", description=TEXTS["cmd_parse"]["en"]),
        BotCommand(command="auth", description=TEXTS["cmd_auth"]["en"]),
        BotCommand(command="cancel", description=TEXTS["cmd_cancel"]["en"]),
    ])
    # Russian command list shown to clients with a Russian UI language.
    await bot.set_my_commands(
        [
            BotCommand(command="start", description=TEXTS["cmd_start"]["ru"]),
            BotCommand(command="parse", description=TEXTS["cmd_parse"]["ru"]),
            BotCommand(command="auth", description=TEXTS["cmd_auth"]["ru"]),
            BotCommand(command="cancel", description=TEXTS["cmd_cancel"]["ru"]),
        ],
        language_code="ru",
    )

    logger.info(f"Bot started. Owner ID: {OWNER_ID}")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
