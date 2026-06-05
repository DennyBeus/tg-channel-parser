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


class OwnerFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id == OWNER_ID


class ParseStates(StatesGroup):
    channel = State()
    dates = State()
    fmt = State()
    limit = State()
    no_emoji = State()
    reverse = State()
    keywords = State()


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


async def run_parse_job(bot: Bot, chat_id: int, parser_args: list[str]) -> None:
    global job_running
    if job_running:
        await bot.send_message(chat_id, "Уже идёт парсинг, подождите.")
        return

    output_file = os.path.join(OUTPUT_DIR, uuid.uuid4().hex)
    cmd = ["python", "/app/parser.py"] + parser_args + ["-o", output_file]

    job_running = True
    await bot.send_message(chat_id, "Парсинг запущен...")
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
        await bot.send_message(chat_id, f"Ошибка парсинга:\n<pre>{err}</pre>", parse_mode="HTML")
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

    await bot.send_message(chat_id, "Сообщений не найдено по заданным критериям.")


@router.message(OwnerFilter(), Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Помощь", callback_data="menu_help")],
    ])
    await message.answer(
        "<b>grabogram is here</b>\n\n"
        "<b>Выбери действие:</b>\n"
        "/parse — начать парсинг\n"
        "/auth — обновить сессию\n"
        "/cancel — отменить текущее действие",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(OwnerFilter(), F.data == "menu_help")
async def cb_help(callback: CallbackQuery):
    text = (
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
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.message(OwnerFilter(), Command("parse"))
async def cmd_parse(message: Message, state: FSMContext):
    await state.clear()
    args_text = message.text[len("/parse"):].strip()
    if not args_text:
        await state.set_state(ParseStates.channel)
        await message.answer("Отправь URL канала (например: https://t.me/durov)")
        return
    try:
        args = shlex.split(args_text)
    except ValueError as e:
        await message.answer(f"Ошибка разбора аргументов: {e}")
        return
    await run_parse_job(message.bot, message.chat.id, args)


@router.message(OwnerFilter(), ParseStates.channel)
async def state_channel(message: Message, state: FSMContext):
    channel = message.text.strip()
    await state.update_data(channel=channel)
    await state.set_state(ParseStates.dates)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_dates")],
    ])
    await message.answer(
        "Укажи период в формате: 01.01.2024-31.12.2024\nИли нажми «Пропустить».",
        reply_markup=keyboard,
    )


@router.callback_query(OwnerFilter(), F.data == "skip_dates", ParseStates.dates)
async def cb_skip_dates(callback: CallbackQuery, state: FSMContext):
    await state.update_data(start=None, end=None)
    await state.set_state(ParseStates.fmt)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="txt", callback_data="fmt_txt"),
            InlineKeyboardButton(text="json", callback_data="fmt_json"),
        ],
    ])
    await callback.message.answer("Выбери формат вывода:", reply_markup=keyboard)
    await callback.answer()


@router.message(OwnerFilter(), ParseStates.dates)
async def state_dates(message: Message, state: FSMContext):
    text = message.text.strip()
    if "-" in text:
        parts = text.split("-", 1)
        await state.update_data(start=parts[0].strip(), end=parts[1].strip())
    else:
        await message.answer("Неверный формат. Введи: 01.01.2024-31.12.2024 или нажми «Пропустить».")
        return
    await state.set_state(ParseStates.fmt)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="txt", callback_data="fmt_txt"),
            InlineKeyboardButton(text="json", callback_data="fmt_json"),
        ],
    ])
    await message.answer("Выбери формат вывода:", reply_markup=keyboard)


@router.callback_query(OwnerFilter(), F.data.in_({"fmt_txt", "fmt_json"}), ParseStates.fmt)
async def cb_fmt(callback: CallbackQuery, state: FSMContext):
    fmt = callback.data.split("_")[1]
    await state.update_data(fmt=fmt)
    await state.set_state(ParseStates.limit)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_limit")],
    ])
    await callback.message.answer(
        "Лимит сообщений на канал? Введи число.\nИли нажми «Пропустить».",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(OwnerFilter(), F.data == "skip_limit", ParseStates.limit)
async def cb_skip_limit(callback: CallbackQuery, state: FSMContext):
    await state.update_data(limit=None)
    await _ask_no_emoji(callback.message, state)
    await callback.answer()


@router.message(OwnerFilter(), ParseStates.limit)
async def state_limit(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Введи целое число или нажми «Пропустить».")
        return
    await state.update_data(limit=text)
    await _ask_no_emoji(message, state)


async def _ask_no_emoji(message: Message, state: FSMContext):
    await state.set_state(ParseStates.no_emoji)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Удалить", callback_data="emoji_remove"),
            InlineKeyboardButton(text="Оставить", callback_data="emoji_keep"),
        ],
    ])
    await message.answer("Emoji в тексте?", reply_markup=keyboard)


@router.callback_query(OwnerFilter(), F.data.in_({"emoji_remove", "emoji_keep"}), ParseStates.no_emoji)
async def cb_no_emoji(callback: CallbackQuery, state: FSMContext):
    await state.update_data(no_emoji=(callback.data == "emoji_remove"))
    await _ask_reverse(callback.message, state)
    await callback.answer()


async def _ask_reverse(message: Message, state: FSMContext):
    await state.set_state(ParseStates.reverse)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="От старых к новым", callback_data="order_old"),
            InlineKeyboardButton(text="От новых к старым", callback_data="order_new"),
        ],
    ])
    await message.answer("Порядок сообщений?", reply_markup=keyboard)


@router.callback_query(OwnerFilter(), F.data.in_({"order_old", "order_new"}), ParseStates.reverse)
async def cb_reverse(callback: CallbackQuery, state: FSMContext):
    await state.update_data(reverse=(callback.data == "order_old"))
    await state.set_state(ParseStates.keywords)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_keywords")],
    ])
    await callback.message.answer(
        "Введи ключевые слова через пробел (фильтр постов).\nИли нажми «Пропустить».",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(OwnerFilter(), F.data == "skip_keywords", ParseStates.keywords)
async def cb_skip_keywords(callback: CallbackQuery, state: FSMContext):
    await state.update_data(keywords=None)
    await _run_from_state(callback.message, state)
    await callback.answer()


@router.message(OwnerFilter(), ParseStates.keywords)
async def state_keywords(message: Message, state: FSMContext):
    await state.update_data(keywords=message.text.strip())
    await _run_from_state(message, state)


async def _run_from_state(message: Message, state: FSMContext):
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
    await run_parse_job(message.bot, message.chat.id, args)


@router.message(OwnerFilter(), Command("auth"))
async def cmd_auth(message: Message, state: FSMContext):
    await state.clear()
    if not API_ID or not API_HASH or not PHONE:
        await message.answer("Ошибка: API_ID, API_HASH или PHONE_NUMBER не заданы в .env")
        return
    await message.answer(f"Отправляю запрос кода на номер {PHONE}...")
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
        await message.answer(
            "Код отправлен. Введи его в формате: <code>1 2 3 4 5</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"Не удалось запросить код: {e}")


@router.message(OwnerFilter(), AuthStates.waiting_code)
async def auth_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    phone_code_hash = data.get("phone_code_hash")
    client = getattr(message.bot, "_pyrogram_client", None)

    if client is None or not phone_code_hash:
        await state.clear()
        await message.answer("Сессия авторизации устарела. Начни заново: /auth")
        return

    try:
        from pyrogram.errors import SessionPasswordNeeded
        await client.sign_in(PHONE, phone_code_hash, code)
        await client.disconnect()
        message.bot._pyrogram_client = None
        await state.clear()
        await message.answer("Авторизация успешна! Сессия обновлена.")
        logger.info("Re-auth successful via bot")
    except SessionPasswordNeeded:
        await state.set_state(AuthStates.waiting_2fa)
        await message.answer("Требуется пароль 2FA. Введи его:")
    except Exception as e:
        await client.disconnect()
        message.bot._pyrogram_client = None
        await state.clear()
        await message.answer(f"Ошибка авторизации: {e}")


@router.message(OwnerFilter(), AuthStates.waiting_2fa)
async def auth_2fa(message: Message, state: FSMContext):
    password = message.text.strip()
    client = getattr(message.bot, "_pyrogram_client", None)

    if client is None:
        await state.clear()
        await message.answer("Сессия авторизации устарела. Начни заново: /auth")
        return

    try:
        await client.check_password(password)
        await client.disconnect()
        message.bot._pyrogram_client = None
        await state.clear()
        await message.answer("Авторизация успешна! Сессия обновлена.")
        logger.info("Re-auth with 2FA successful via bot")
    except Exception as e:
        await client.disconnect()
        message.bot._pyrogram_client = None
        await state.clear()
        await message.answer(f"Неверный пароль 2FA: {e}")


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
    await message.answer("Действие отменено.")


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

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="parse", description="Запустить парсинг канала"),
        BotCommand(command="auth", description="Обновить сессию"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ])

    logger.info(f"Bot started. Owner ID: {OWNER_ID}")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
