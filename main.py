import os
import sys
import logging

from dotenv import load_dotenv

from db import init_db
from bot import create_bot

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Load environment variables ──────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is required in .env")
    sys.exit(1)


def main() -> None:
    """Start the Telegram bot with Twilio SMS polling."""

    # Initialize database
    init_db()
    logger.info("🗃️  Database initialized")

    # Create and start the bot
    bot_app = create_bot(BOT_TOKEN)

    logger.info("🤖 Starting Telegram bot with SMS polling...")
    bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
