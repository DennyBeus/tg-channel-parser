# Telegram Channel Parser

A Python script for parsing and extracting text messages from Telegram channels using Pyrogram.

## Features

- Parse messages from Telegram channels starting from a specified date
- Extract plain text content with automatic link removal
- Support for channel URLs, usernames, and numeric IDs
- Clean text processing (removes links, mentions, and formatting)
- Saves results to a text file in Downloads folder

## Requirements

- Python 3.7+
- Telegram API credentials (API_ID, API_HASH, PHONE_NUMBER)

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root with your Telegram API credentials:

```
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+1234567890
```

## Usage

### Authorization (first time setup)

```bash
python userbot.py auth
```

Follow the interactive prompts to authorize the application.

### Parse Channel

```bash
python userbot.py
```

Enter the channel URL and start date when prompted. Results will be saved to `~/Downloads/result.txt`.

## Supported Input Formats

- Channel URLs: `https://t.me/channel_name`
- Usernames: `@channel_name`
- Numeric IDs: `-1001234567890`

## Output Format

Messages are saved in chronological order (newest first), separated by `---` dividers.