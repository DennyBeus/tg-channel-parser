# Telegram Channel Parser

[English](README.md) | [Русский](README.ru.md)

Простой Python CLI-скрипт для экспорта постов из Telegram-каналов с фильтрацией по дате и экспортом в `txt` или `json`.

Отдельная благодарность автору [`kurigram`](https://github.com/KurimuzonAkuma/kurigram/tree/dev) за помощь в решении проблемы с парсингом постов, использующих стиль шрифта Quote.

## Что делает программа

- подключается к Telegram как пользователь (userbot session);
- читает историю канала;
- извлекает текст постов и подписи к медиа;
- сохраняет дату, текст, просмотры и общее количество реакций;
- может ограничивать количество сообщений и удалять emoji из текста.

## Библиотеки и почему `kurigram` здесь важен

В `requirements.txt` используются:

- `kurigram`
- `tgcrypto==1.2.5`
- `aiohttp==3.9.5`
- `requests`
- `python-dotenv`

### Ключевой момент о `kurigram`

В коде импорт выполняется как `from pyrogram import Client`, но в зависимостях указан `kurigram`.

`kurigram` предоставляет совместимый Telegram API client с интерфейсом в стиле Pyrogram, поэтому в коде используется привычный `Client`, а установка выполняется через `kurigram`.  
Этот client используется для:

- user authorization;
- retrieving channel information;
- reading message history (`get_chat_history`).

`tgcrypto` нужен для ускорения MTProto cryptography, а `python-dotenv` используется для загрузки переменных из `.env`.

## Требования

- Python 3.8+ (рекомендуется современная версия);
- Telegram API credentials: `API_ID`, `API_HASH`, `PHONE_NUMBER`.

Получить `API_ID` и `API_HASH` можно на [`my.telegram.org`](https://my.telegram.org/auth).

## Установка

```bash
pip install -r requirements.txt
```

## Настройка `.env`

Создайте файл `.env` в корне проекта:

```env
API_ID=123456
API_HASH=your_api_hash
PHONE_NUMBER=+79991234567
```

Также можно задать:

```env
DATA_DIR=./data
```

Если `DATA_DIR` не указан, по умолчанию используется `./data`.

## Как это работает пошагово

1. Вы один раз запускаете authorization (`--auth`) для создания session.
2. Скрипт сохраняет session в папке данных (`DATA_DIR/user`).
3. При обычном запуске он определяет канал, читает историю и фильтрует сообщения по дате.
4. Текст нормализуется (удаляются лишние пробелы и пустые строки).
5. С флагом `-j` удаляются emoji.
6. Результат сохраняется в файл.

## Использование

### 1) Авторизация (первый запуск)

```bash
python userbot.py --auth
```

### 2) Базовый парсинг всего канала

```bash
python userbot.py https://t.me/channel_name
```

### 3) Кастомный парсинг

По диапазону дат:

```bash
python userbot.py -s 01.01.2024 -e 31.01.2024 https://t.me/channel_name
```

Лимит сообщений:

```bash
python userbot.py -l 100 https://t.me/channel_name
```

JSON export:

```bash
python userbot.py -f json -o beus_research https://t.me/channel_name
```

Удалить emoji:

```bash
python userbot.py -j https://t.me/channel_name
```

Порядок от старых к новым:

```bash
python userbot.py -r https://t.me/channel_name
```

Комбинированный пример:

```bash
python userbot.py -s 01.01.2024 -e 31.12.2024 -l 500 -f json -o export_2024 -j -r https://t.me/channel_name
```

## CLI arguments

- `channel` — канал (обязателен, кроме режима `--auth`);
- `-a, --auth` — режим authorization;
- `-s START` — start date в формате `DD.MM.YYYY` (по умолчанию: `01.01.1970`);
- `-e END` — end date в формате `DD.MM.YYYY` (по умолчанию: текущая дата);
- `-o OUTPUT` — имя output file (по умолчанию: `result`);
- `-f {txt,json}` — file format (по умолчанию: `txt`);
- `-l LIMIT` — максимальное количество сообщений;
- `-r, --reverse` — записывать output от старых к новым;
- `-j, --no-emoji` — удалить emoji из текста.

## Куда сохраняется результат

- Если указан только file name (например, `-o report`), файл сохраняется в папку `Downloads` пользователя: `report.txt` или `report.json`.
- Если указан path, сохранение выполняется по этому path.

## Формат данных

Каждое сообщение содержит:

- `text` — текст поста или подпись к медиа;
- `date` — дата/время в формате `DD.MM.YYYY HH:MM:SS`;
- `views` — просмотры;
- `reactions_count` — общее количество реакций.

## Полезно знать

- Скрипт читает историю от новых к старым, а с `-r` разворачивает результат перед сохранением.
- Сообщения без текста пропускаются.
- Если по заданным критериям ничего не найдено, скрипт показывает предупреждение и не создаёт файл.

## Нужно обновить

- Я хочу добавить парсинг всех ссылок в посте через entities. Сейчас парсинг работает только с текстом, без markdown.