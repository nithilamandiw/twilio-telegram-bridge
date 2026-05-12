# Twilio SMS → Telegram Forwarder Bot

A Python bot that polls your Twilio account for incoming SMS messages and forwards them to your Telegram chat in real-time.

## Features

- 🔐 Per-user Twilio credential storage (Account SID + Auth Token)
- 📡 Automatic polling — checks Twilio every 15 seconds for new SMS
- ✅ Credential verification on setup
- 🗃️ SQLite database (no external DB needed)
- 🚫 No webhooks, no domain, no port forwarding required

## Prerequisites

- Python 3.10+
- A [Twilio account](https://www.twilio.com/) with a phone number
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Quick Start

### 1. Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Clone & Install

```bash
git clone https://github.com/nithilamandiw/twilio-telegram-bridge.git
cd twilio-telegram-bridge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
nano .env
```

Set your bot token:
```env
BOT_TOKEN=123456789:ABCdefGHIjklMNO-pqrSTUvwxYZ
```

### 4. Run

```bash
python3 main.py
```

### 5. Set Up in Telegram

1. Open your bot in Telegram
2. Send `/setup`
3. Enter your Twilio Account SID
4. Enter your Twilio Auth Token
5. Enter your Twilio phone number (e.g. `+136552729111`)
6. Done! SMS messages will appear in this chat automatically.

## Deploy on VPS

```bash
# SSH into your VPS
ssh ubuntu@YOUR_VPS_IP

# Clone and install
cd ~
git clone https://github.com/nithilamandiw/twilio-telegram-bridge.git
cd twilio-telegram-bridge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env   # paste your BOT_TOKEN

# Create systemd service
sudo nano /etc/systemd/system/twilio-telegram.service
```

Paste this service config:
```ini
[Unit]
Description=Twilio Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/twilio-telegram-bridge
ExecStart=/home/ubuntu/twilio-telegram-bridge/venv/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable twilio-telegram
sudo systemctl start twilio-telegram
sudo systemctl status twilio-telegram
```

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
Twilio Account ←── Bot polls every 15s ──→ New SMS? ──→ Forward to Telegram
```

The bot uses the Twilio REST API to check for incoming messages. No webhooks, no web server, no domain needed.

## Project Structure

```
twilio-telegram-bridge/
├── main.py           # Entry point
├── bot.py            # Telegram bot commands & Twilio polling
├── db.py             # SQLite database
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variable template
├── .gitignore
└── README.md
```

## Security

- **Credentials verified:** Twilio creds are validated via API before saving
- **Auth tokens hidden:** `/status` masks sensitive credentials
- **Parameterized queries:** All DB operations use parameterized queries
- **No token logging:** Auth tokens are never written to logs

## 🧑‍💻 Author

Nithila Mandiw


## 💡 Contributing

Feel free to fork and improve the project!
