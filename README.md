# Telegram Channel Parser

[English](README.md) | [Русский](README.ru.md)

A simple Python CLI script for exporting posts from Telegram channels with date filtering and export to `txt` or `json`.

Thanks to the CLI interface and `--stdout` JSON output, the script integrates easily into automation platforms like n8n — just call it from an Execute Command node and pass the result downstream.

Special thanks to the author of [`kurigram`](https://github.com/KurimuzonAkuma/kurigram/tree/dev) for helping resolve the issue with parsing posts that use the Quote font style.

## What the program does

- connects to Telegram as a user (userbot session);
- reads channel history;
- extracts post text and media captions;
- extracts inline URLs from text_link entities and inserts them after the anchor text (with correct handling of emoji/UTF-16 offsets);
- saves date, text, views, total reaction count, post link, and source channel;
- supports parsing multiple channels in a single run;
- can limit the number of messages and remove emoji from text;
- can output results as JSON to stdout for piping into other tools.

## Libraries and why `kurigram` is important here

The following are used in `requirements.txt`:

- `kurigram`
- `tgcrypto==1.2.5`
- `aiohttp==3.9.5`
- `requests`
- `python-dotenv`

### Key point about `kurigram`

In the code, import is done as `from pyrogram import Client`, but dependencies specify `kurigram`.

`kurigram` provides a compatible Telegram API client with a Pyrogram-style interface, so the code uses the familiar `Client`, while installation is done via `kurigram`.  
This client is used for:

- user authorization;
- retrieving channel information;
- reading message history (`get_chat_history`).

`tgcrypto` is needed to speed up MTProto cryptography, and `python-dotenv` is used to load variables from `.env`.

## Requirements

- Python 3.8+ (a modern version is recommended);
- Telegram API credentials: `API_ID`, `API_HASH`, `PHONE_NUMBER`.

You can get `API_ID` and `API_HASH` at [`my.telegram.org`](https://my.telegram.org/auth).

## Installation

```bash
pip install -r requirements.txt
```

## `.env` setup

Create a `.env` file in the project root:

```env
API_ID=123456
API_HASH=your_api_hash
PHONE_NUMBER=+79991234567
```

You can also set:

```env
DATA_DIR=./data
```

If `DATA_DIR` is not specified, `./data` is used by default.

### Proxy setup (optional)

If Telegram is blocked in your region or you use a paid proxy, add the following to `.env`:

```env
PROXY_SCHEME=http
PROXY_HOSTNAME=127.0.0.1
PROXY_PORT=8080
# For paid proxies with authentication:
PROXY_USERNAME=your_login
PROXY_PASSWORD=your_password
```

Supported schemes: `http`, `socks5`. `PROXY_USERNAME` and `PROXY_PASSWORD` are optional — omit them if the proxy requires no authentication.

## How it works step by step

1. You run authorization once (`--auth`) to create a session.
2. The script saves the session in the data folder (`DATA_DIR/user`).
3. On a normal run, it resolves the channel(s), reads history, and filters messages by date.
4. The text is normalized (extra spaces and empty lines are removed).
5. Inline URLs from text_link entities are extracted and inserted after the anchor text.
6. With the `-j` flag, emoji are removed.
7. The result is saved to a file or printed to stdout (`--stdout`).

## Usage

### 1) Authorization (first run)

```bash
python userbot.py --auth
```

### 2) Basic channel parsing

```bash
python userbot.py https://t.me/channel_name
```

### 3) With option examples

By date range:

```bash
python userbot.py -s 01.01.2024 -e 31.01.2024 https://t.me/channel_name
```

Message limit:

```bash
python userbot.py -l 100 https://t.me/channel_name
```

JSON export:

```bash
python userbot.py -f json -o beus_research https://t.me/channel_name
```

Remove emoji:

```bash
python userbot.py -j https://t.me/channel_name
```

Order from oldest to newest:

```bash
python userbot.py -r https://t.me/channel_name
```

Print JSON to stdout (for piping or quick preview):

```bash
python userbot.py --stdout -f json -l 10 https://t.me/channel_name
```

Multiple channels in one run:

```bash
python userbot.py -f json -o combined https://t.me/channel1 https://t.me/channel2
```

Combined example:

```bash
python userbot.py -s 01.01.2024 -e 31.12.2024 -l 500 -f json -o export_2024 -j -r https://t.me/channel_name
```

## CLI arguments

- `channel` — one or more channel URLs (required, except in `--auth` mode);
- `-a, --auth` — authorization mode;
- `-s START` — start date in `DD.MM.YYYY` format (default: `01.01.1970`);
- `-e END` — end date in `DD.MM.YYYY` format (default: current date);
- `-o OUTPUT` — output file name (default: `result`);
- `-f {txt,json}` — file format (default: `txt`);
- `-l LIMIT` — maximum number of messages per channel;
- `-r, --reverse` — write output from oldest to newest;
- `-j, --no-emoji` — remove emoji from text;
- `-k WORD [WORD ...]` — filter posts by keywords (case-insensitive); only posts containing at least one word are kept;
- `--stdout` — print JSON to stdout instead of saving to file.

## Where the result is saved

- If only a file name is specified (for example, `-o report`), the file is saved to the user's `Downloads` folder: `report.txt` or `report.json`.
- If a path is specified, saving is done to that path.

## Data format

Each message contains:

- `text` — post text or media caption (inline URLs from text_link entities are appended in parentheses after the anchor text);
- `date` — date/time in `YYYY-MM-DD HH:MM:SS` format;
- `views` — views;
- `reactions_count` — total number of reactions;
- `link` — direct link to the post (`https://t.me/channel/id`);
- `source_channel` — channel username.

## Useful to know

- The script reads history from newest to oldest, and with `-r` reverses the result before saving.
- Messages without text are skipped.
- If nothing is found by the specified criteria, the script shows a warning and does not create a file.

## Recent changes

- Added inline URL extraction from `text_link` entities with correct UTF-16 offset handling for emoji.
- Added `--stdout` flag to print JSON directly to the terminal.
- Added `link` and `source_channel` fields to the output.
- Support for parsing multiple channels in a single run.
- Added `-k / --keywords` flag: filter posts by one or more keywords (case-insensitive). Only posts containing at least one of the specified words are included in the output.
- Added proxy support via `.env` (`PROXY_SCHEME`, `PROXY_HOSTNAME`, `PROXY_PORT`, `PROXY_USERNAME`, `PROXY_PASSWORD`). Useful when Telegram is blocked or when using paid proxies with authentication.
