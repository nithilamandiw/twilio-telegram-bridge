import os
import sys
import asyncio
import logging
import threading

from dotenv import load_dotenv

from db import init_db
from bot import create_bot
from server import create_server

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Load environment variables ──────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "3000"))

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is required in .env")
    sys.exit(1)

if not PUBLIC_URL:
    logger.error("❌ PUBLIC_URL is required in .env")
    sys.exit(1)


def main() -> None:
    """Start both the Flask webhook server and the Telegram bot."""

    # Initialize database
    init_db()
    logger.info("🗃️  Database initialized")

    # Create the bot application
    bot_app = create_bot(BOT_TOKEN, PUBLIC_URL)

    # Create the Flask server
    flask_app = create_server(bot_app, PUBLIC_URL)

    # ── Run Flask in a separate thread ──────────────────────
    def run_flask():
        # Disable Flask's reloader — we manage our own lifecycle
        flask_app.run(host="0.0.0.0", port=PORT, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Express-equivalent Flask server listening on port %d", PORT)
    logger.info("📡 Webhook URL: %s/webhook/{chatId}", PUBLIC_URL)

    # ── Store event loop reference so Flask thread can use it ──
    # This is set inside the bot's async context via post_init
    async def post_init(application):
        application.bot_data["event_loop"] = asyncio.get_event_loop()

    bot_app.post_init = post_init

    # ── Start the Telegram bot (blocking, runs the event loop) ──
    logger.info("🤖 Starting Telegram bot...")
    bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
