<img src=".github/logo.svg" alt="grabogram — developed by DennyBeus" width="800">

# grabogram

[English](README.md) | [Русский](README.ru.md)

A Telegram channel parser that lives on **your** server and is driven entirely from a **Telegram bot**. Set it up once, and from then on there's no terminal to fuss with — you talk to a bot, the bot does the parsing, and a ready-to-go `txt` or `json` file lands right back in your chat.

Under the hood it's still the same honest CLI parser that's always been here — the bot is just a friendly shell wrapped around it. So if you're the kind of person who likes piping JSON into n8n or a shell script, that path is still wide open (see [Power-user mode: the raw CLI](#power-user-mode-the-raw-cli)).

The whole point: **install it once with a single script, then forget the server even exists.** Add a proxy, re-login, parse channels — all from your phone.

> **Your data stays yours.** The entire codebase is open. Sessions, exported files, and everything else live only on your server. Nothing is sent anywhere — there is no "our cloud" to leak from.

Special thanks to the author of [`kurigram`](https://github.com/KurimuzonAkuma/kurigram/tree/dev) for helping resolve the issue with parsing posts that use the Quote font style.

---

## Table of contents

- [What you get](#what-you-get)
- [Before you start](#before-you-start)
- [Installation (the easy way)](#installation-the-easy-way)
- [Using the bot](#using-the-bot)
  - [The /parse wizard](#the-parse-wizard)
  - [Direct /parse command](#direct-parse-command)
  - [Re-authorizing without touching the server](#re-authorizing-without-touching-the-server)
  - [Switching language](#switching-language)
- [Proxy support](#proxy-support)
- [What the export looks like](#what-the-export-looks-like)
- [Power-user mode: the raw CLI](#power-user-mode-the-raw-cli)
- [Configuration reference (.env)](#configuration-reference-env)
- [Running the server](#running-the-server)
- [How it works under the hood](#how-it-works-under-the-hood)
- [FAQ & good to know](#faq--good-to-know)

---

## What you get

- A Telegram bot that you (and only you) control — it's locked to your numeric Telegram ID.
- A `/parse` command with two flavors: a step-by-step wizard for casual use, and a one-line command with flags for when you know exactly what you want.
- Export to `txt` (human-readable) or `json` (machine-readable), delivered as a file straight into the chat.
- Date-range filtering, message limits, keyword filtering, emoji stripping, and oldest-to-newest ordering.
- Re-login right from the bot (`/auth`) when a session expires — including 2FA — without ever opening a terminal.
- Optional proxy support for regions where Telegram is blocked, or for paid authenticated proxies.
- Bilingual interface: 🇬🇧 English / 🇷🇺 Russian, switchable inside the bot.
- Runs in Docker. One install script does everything: installs Docker, clones the repo, asks a few questions, and starts the container.

Under the hood the parser:

- connects to Telegram as a user (a userbot session);
- reads channel history and extracts post text + media captions;
- pulls inline URLs out of `text_link` entities and inserts them right after the anchor text (with correct emoji/UTF‑16 offset handling, which is the fiddly part);
- saves date, text, views, total reaction count, the post link, and the source channel;
- can parse several channels in one run, cap the number of messages, drop emoji, and filter by keywords.

---

## Before you start

You'll need three things:

1. **A VPS** (any cheap Ubuntu/Debian box will do) where you can run a couple of commands. You'll run the installer there *once*.
2. **Telegram API credentials** — `API_ID` and `API_HASH`. Grab them at [my.telegram.org](https://my.telegram.org/auth) → *API development tools* → create an application.
3. **A bot token** — open [@BotFather](https://t.me/BotFather), send `/newbot`, follow the prompts, and copy the token (looks like `123456789:ABC-DEF1234...`).

You'll also want your own **numeric Telegram ID**, so the bot knows who its owner is. Send `/start` to [@userinfobot](https://t.me/userinfobot) and it'll tell you (a plain number, no `@`).

And the **phone number** of the account that will actually do the reading — channels are parsed *as that account*, so it needs to be able to see the channels you care about.

---

## Installation (the easy way)

On your server, run the installer in one line:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DennyBeus/grabogram/main/install.sh)
```

Prefer doing it the classic way? Clone the repo and run the script by hand — it does exactly the same thing:

```bash
git clone https://github.com/DennyBeus/grabogram.git
```
```bash
cd grabogram
```
```bash
chmod +x install.sh
```
```bash
./install.sh
```

Either way, the script will:

1. Check for `curl` and **install Docker** if it isn't already there.
2. **Clone the repository** (or reuse the folder if you're already inside it).
3. Walk you through creating `.env` — it asks for your `API_ID`, `API_HASH`, phone number, bot token, owner ID, and optionally a proxy. No editing files by hand.
4. **Build and start** the Docker container.
5. Run the **one-time login** for the parsing account: Telegram sends a code to your app (or SMS), you type it in, and you're done. If you have 2FA, it'll ask for your password.

When it finishes you'll see a little summary with the bot commands. Open your bot in Telegram, send `/start`, and you're live.

> From here on, **you never need to come back to the server** for day-to-day use. Sessions expired? Re-login from the bot. Want a proxy? It was set up during install (or add it later, see below). The container restarts itself on reboot.

---

## Using the bot

Open the bot you created with @BotFather and hit **`/start`**. You'll get the main menu with a language switcher and a Help button.

The four commands:

| Command | What it does |
| --- | --- |
| `/start` | Main menu (language toggle + help) |
| `/parse` | Start parsing — either the wizard or a one-liner |
| `/auth` | Refresh the userbot session (when it expires) |
| `/cancel` | Cancel whatever you're in the middle of |

### The /parse wizard

Just send `/parse` with nothing after it, and the bot will hold your hand through it, one question at a time:

1. **Channel URL** — e.g. `https://t.me/durov`
2. **Date period** — `01.01.2024-31.12.2024`, or tap **Skip**
3. **Message limit** — a number, or **Skip**
4. **Keywords** — space-separated words to filter posts by, or **Skip**
5. **Order** — *Oldest to newest* / *Newest to oldest*
6. **Emoji** — *Remove* / *Keep*
7. **Format** — `txt` / `json`

When you're done, the bot runs the job and drops the result file right into the chat. Nothing to download from a server, no files to clean up — old temporary exports are swept away automatically.

### Direct /parse command

If you already know what you want, skip the wizard and pass flags directly:

```
/parse https://t.me/durov -s 01.01.2024 -e 31.12.2024 -f json -k bitcoin
```

The flags mirror the CLI exactly:

| Flag | Meaning |
| --- | --- |
| `-s DATE` | Start date, `DD.MM.YYYY` |
| `-e DATE` | End date, `DD.MM.YYYY` |
| `-f txt\|json` | Output format (`txt` by default) |
| `-l NUM` | Max messages |
| `-k WORDS` | Keywords (space-separated) |
| `-j` | Strip emoji |
| `-r` | Oldest → newest |

(The bot supplies the output file itself, so you don't pass `-o`.)

### Re-authorizing without touching the server

Telegram sessions don't last forever. When yours expires, **you don't need to go back to the server at all** — just send `/auth` to the bot:

1. The bot requests a fresh login code for your number.
2. Telegram sends the code; you type it in (format `1 2 3 4 5` — spaces are fine, they're stripped).
3. If you have 2FA enabled, it'll ask for your password next.
4. Done — session refreshed.

This was the whole motivation for the bot: never again copy-paste login codes through a server console.

### Switching language

Tap 🇷🇺 **Русский** or 🇬🇧 **English** in the `/start` menu. The choice is per-user and applies to every message, button, and prompt from there on. (Telegram itself will also show the command descriptions in Russian if your client's language is Russian.)

---

## Proxy support

If Telegram is blocked in your server's region, or you use a paid authenticated proxy, you can route the userbot through it.

The easiest way is to say **yes** when the installer asks "Configure a proxy?". If you want to add or change it later, edit `.env` in the project folder and restart:

```env
PROXY_SCHEME=http
PROXY_HOSTNAME=127.0.0.1
PROXY_PORT=8080
# Only for proxies that require authentication:
PROXY_USERNAME=your_login
PROXY_PASSWORD=your_password
```

Supported schemes: `http`, `socks5`. Leave `PROXY_USERNAME` / `PROXY_PASSWORD` empty if your proxy needs no auth. After editing, `docker compose restart` to apply.

---

## What the export looks like

Each parsed message carries:

- `text` — post text or media caption (inline URLs from `text_link` entities appear in parentheses after the anchor text);
- `date` — `YYYY-MM-DD HH:MM:SS`;
- `views` — view count;
- `reactions_count` — total reactions across all emoji;
- `link` — direct link to the post (`https://t.me/channel/id`);
- `source_channel` — the channel username.

A `json` export is an array of these objects. A `txt` export is the same data formatted for a human to read:

```
[2024-03-12 18:40:00] (views: 12043, reactions: 318)
Post text goes here, with any inline links (https://example.com) inlined.

---
```

---

## Power-user mode: the raw CLI

The bot is just a wrapper — `parser.py` is a fully standalone CLI, and it's still the right tool if you want to script things or feed JSON into something like n8n. Inside the container (or anywhere you've installed the deps) it works exactly as before. Thanks to `--stdout`, you can pipe JSON straight into another tool from an Execute Command node and pass it downstream.

```bash
# Authorize once (creates the session)
python parser.py --auth

# Basic parse of a whole channel
python parser.py https://t.me/channel_name

# Date range + limit + JSON, named output
python parser.py -s 01.01.2024 -e 31.12.2024 -l 500 -f json -o export_2024 https://t.me/channel_name

# Keyword filter, emoji stripped
python parser.py https://t.me/channel_name -e 01.02.2026 -o grace_info -f json -j -k GRACE

# Print JSON to stdout (for piping into n8n / jq / anything)
python parser.py --stdout -f json -l 10 https://t.me/channel_name

# Several channels at once
python parser.py -f json -o combined https://t.me/channel1 https://t.me/channel2
```

To run it inside the running container:

```bash
docker exec -it grabogram python parser.py --stdout -f json -l 10 https://t.me/durov
```

### CLI arguments

- `channel` — one or more channel URLs (required, except in `--auth` mode);
- `-a, --auth` — authorization mode;
- `-s START` — start date `DD.MM.YYYY` (default: `01.01.1970`);
- `-e END` — end date `DD.MM.YYYY` (default: current date; the whole end day is included);
- `-o OUTPUT` — output file name (default: `result`);
- `-f {txt,json}` — file format (default: `txt`);
- `-l LIMIT` — maximum number of messages per channel;
- `-r, --reverse` — write output from oldest to newest;
- `-j, --no-emoji` — remove emoji from text;
- `-k WORD [WORD ...]` — keep only posts containing at least one keyword (case-insensitive);
- `--stdout` — print JSON to stdout instead of saving to a file.

**Where files land:** if you pass just a name (`-o report`), the CLI saves to the user's `Downloads` folder (`report.txt` / `report.json`). Pass a path and it saves there. With `--stdout` no file is written at all. *(When the bot runs the parser it manages the output path itself and hands you the file in chat.)*

---

## Configuration reference (.env)

The installer writes this for you, but here's what every key means:

```env
API_ID=123456
API_HASH=your_api_hash
PHONE_NUMBER=+79991234567

TELEGRAM_BOT_TOKEN=123456789:ABC-DEF1234...
TELEGRAM_BOT_OWNER_ID=987654321

DATA_DIR=/app/data
OUTPUT_DIR=/app/tmp

PROXY_SCHEME=
PROXY_HOSTNAME=
PROXY_PORT=
PROXY_USERNAME=
PROXY_PASSWORD=
```

| Key | What it's for |
| --- | --- |
| `API_ID`, `API_HASH` | Telegram API credentials from my.telegram.org |
| `PHONE_NUMBER` | The account that does the parsing (with country code) |
| `TELEGRAM_BOT_TOKEN` | Your bot's token from @BotFather |
| `TELEGRAM_BOT_OWNER_ID` | Your numeric Telegram ID — only this user can use the bot |
| `DATA_DIR` | Where the userbot session is stored (persisted via Docker volume) |
| `OUTPUT_DIR` | Temp folder for generated export files (auto-cleaned) |
| `PROXY_*` | Optional proxy settings (see above) |

---

## Running the server

Day to day you won't need these, but for the record:

```bash
docker logs grabogram        # view logs
docker compose restart       # restart (e.g. after editing .env)
docker compose down          # stop
docker compose up -d         # start
docker compose build         # rebuild after a code update
```

### Libraries

From `requirements.txt`:

- `kurigram` — the Telegram client (Pyrogram-compatible API)
- `tgcrypto==1.2.5` — fast MTProto crypto
- `aiohttp==3.9.5`, `requests`
- `python-dotenv` — loads `.env`
- `aiogram==3.13.0` — the bot framework

> **A note on `kurigram`:** in the code we import `from pyrogram import Client`, but install `kurigram`. That's intentional — `kurigram` is a maintained, Pyrogram-compatible client, so the code reads like familiar Pyrogram while the install pulls the fixed fork. It handles authorization, channel lookups, and reading history (`get_chat_history`).

---

## How it works under the hood

1. The container runs `bot.py`, which polls Telegram for your commands.
2. When you `/parse`, the bot assembles the right CLI arguments and runs `parser.py` as a subprocess.
3. The parser resolves the channel(s), reads history newest-first, filters by date, normalizes whitespace, extracts inline links, optionally strips emoji, and applies keyword filtering.
4. The result is written to a temp file, which the bot sends back to you as a document and then deletes.
5. `/auth` talks to Telegram directly to refresh the session stored in `DATA_DIR` — the same session `parser.py` then uses.

---

## FAQ & good to know

- **History is read newest → oldest**, and `-r` reverses the result before saving.
- **Messages without text are skipped.**
- **Nothing matched?** The bot tells you "no messages found" and no file is produced.
- **Only the owner can use the bot.** Anyone else messaging it is silently ignored — the `TELEGRAM_BOT_OWNER_ID` filter sees to that.
- **Sessions live on your server**, in the Docker volume. They never leave the box.
- **One job at a time.** If a parse is already running, the bot asks you to wait rather than piling jobs on top of each other.
