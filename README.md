# Twilio SMS → Telegram Forwarder Bot

A Python bot that forwards incoming SMS messages from your Twilio phone number to your Telegram chat in real-time.

## Features

- 🔐 Per-user Twilio credential storage
- ✅ Twilio webhook signature validation
- 💬 Guided setup via Telegram chat commands (ConversationHandler)
- 🗃️ SQLite database (zero external DB dependencies)
- ⚡ Flask webhook server + python-telegram-bot in one process

## Prerequisites

- Python 3.10+
- A [Twilio account](https://www.twilio.com/) with a phone number
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Quick Start

### 1. Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:ABCdefGHIjklMNO-pqrSTUvwxYZ`)

### 2. Clone & Install

```bash
git clone <your-repo-url>
cd twilio-telegram
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
BOT_TOKEN=123456789:ABCdefGHIjklMNO-pqrSTUvwxYZ
PUBLIC_URL=https://yourserver.com
PORT=3000
```

### 4. Run the Server

```bash
python main.py
```

### 5. Expose Locally with ngrok (for testing)

If you're running locally, use [ngrok](https://ngrok.com/) to create a public URL:

```bash
ngrok http 3000
```

Copy the `https://` forwarding URL and set it as `PUBLIC_URL` in your `.env`:

```env
PUBLIC_URL=https://abc123.ngrok-free.app
```

> **Note:** Restart the bot after changing `PUBLIC_URL`.

### 6. Configure Your Twilio Webhook

After running `/setup` in the bot, you'll receive a webhook URL. To configure it in Twilio:

1. Go to the [Twilio Console](https://console.twilio.com)
2. Navigate to **Phone Numbers** → **Manage** → **Active Numbers**
3. Click your phone number
4. Under **Messaging** → **"A message comes in"**, enter:
   ```
   https://YOUR_PUBLIC_URL/webhook/YOUR_CHAT_ID
   ```
5. Set the method to **HTTP POST**
6. Click **Save**

## Bot Commands

| Command   | Description                              |
| --------- | ---------------------------------------- |
| `/start`  | Welcome message and usage instructions   |
| `/setup`  | Configure Twilio credentials (step by step) |
| `/status` | View your current configuration          |
| `/remove` | Delete your stored Twilio credentials    |
| `/cancel` | Abort an in-progress setup               |

## How It Works

```
SMS Sender → Twilio → POST /webhook/:chatId → Validate Signature → Telegram Message
```

1. Someone sends an SMS to your Twilio number
2. Twilio forwards the SMS to your webhook URL
3. The server validates the Twilio request signature
4. The SMS content is forwarded to your Telegram chat

## Message Format

When an SMS arrives, you'll see:

```
📱 New SMS to +15551234567
From: +14449876543

Hello, this is the SMS body text!
```

## Project Structure

```
twilio-telegram/
├── main.py           # Entry point — starts Flask + bot
├── bot.py            # Telegram bot commands & setup flow
├── server.py         # Flask webhook endpoint
├── db.py             # SQLite setup and queries
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variable template
├── .gitignore
└── README.md
```

## Security

- **Webhook validation:** Every incoming Twilio request is validated using `twilio.RequestValidator` to prevent spoofed messages
- **Auth tokens are hidden:** The `/status` command masks sensitive credentials
- **Parameterized queries:** All database operations use parameterized queries to prevent SQL injection
- **No token logging:** Auth tokens are never written to logs

## License

MIT
