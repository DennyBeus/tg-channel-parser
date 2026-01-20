# Telegram Channel Parser

A Python CLI tool for extracting text messages from Telegram channels using Pyrogram. The script supports date filtering, link removal, and exports results in multiple formats.

## Features

- Parse messages from Telegram channels with date range filtering
- Support for channel URLs, usernames, and numeric IDs
- Optional link and mention removal from extracted text
- Export results as plain text or JSON
- Configurable message limits
- Extracts text from regular messages and media captions
- Progress logging during parsing
- Session-based authentication with persistent storage

## Requirements

- Python 3.7 or higher
- Telegram API credentials (API_ID, API_HASH, PHONE_NUMBER)

## Installation

Install required dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root with your Telegram API credentials:

```
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+1234567890
DATA_DIR=./data
```

The `DATA_DIR` is optional and defaults to `./data` where session files are stored.

## Usage

### Authorization

Run authorization mode to authenticate with Telegram:

```bash
python userbot.py --auth
```

You'll be prompted to enter the verification code sent to your phone. The session is saved for future use.

### Parsing a Channel

Basic usage with required channel argument:

```bash
python userbot.py @channel_name
```

Parse with date range:

```bash
python userbot.py @channel_name -s 01.01.2024 -e 31.01.2024
```

Remove links from extracted text:

```bash
python userbot.py @channel_name --no-links
```

Limit number of messages:

```bash
python userbot.py @channel_name -l 100
```

Export as JSON:

```bash
python userbot.py @channel_name -f json
```

Custom output filename:

```bash
python userbot.py @channel_name -o my_export
```

Combine options:

```bash
python userbot.py https://t.me/channel_name -s 01.01.2024 -e 31.12.2024 --no-links -f json -o export_2024
```

## Command Line Arguments

- `channel` - Channel identifier (required, except for auth mode). Accepts:
  - Channel URLs: `https://t.me/channel_name`
  - Usernames: `@channel_name`
  - Numeric IDs: `-1001234567890`

- `-s, --start` - Start date in DD.MM.YYYY format (default: 01.01.1970)
- `-e, --end` - End date in DD.MM.YYYY format (default: current date)
- `-o, --output` - Output filename without extension (default: `result`). Saves to Downloads folder unless absolute path provided
- `-f, --format` - Output format: `txt` or `json` (default: `txt`)
- `-l, --limit` - Maximum number of messages to parse
- `--no-links` - Remove URLs, t.me links, and @mentions from text
- `--auth` - Run authorization mode

## Output

By default, results are saved to `~/Downloads/result.txt`. Text format includes timestamps in DD.MM.YYYY HH:MM:SS format with messages separated by dividers. JSON format exports structured data with date and text fields for each message.

The script processes messages chronologically (newest first) and only extracts messages that have text content, either from the message body or media captions.