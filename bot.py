import re
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from twilio.rest import Client as TwilioClient

from db import upsert_user, get_user, remove_user

logger = logging.getLogger(__name__)

# Conversation states for /setup flow
ACCOUNT_SID, AUTH_TOKEN, PHONE_NUMBER = range(3)


# ── /start ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Welcome to the Twilio SMS Forwarder Bot\\!*\n\n"
        "This bot forwards incoming SMS messages from your Twilio phone "
        "number directly to this Telegram chat\\.\n\n"
        "*How it works:*\n"
        "1️⃣  Use /setup to register your Twilio credentials\n"
        "2️⃣  The bot automatically configures your Twilio webhook\n"
        "3️⃣  Receive SMS messages right here in Telegram\\!\n\n"
        "*Commands:*\n"
        "/setup  — Configure your Twilio credentials\n"
        "/status — View your current configuration\n"
        "/remove — Delete your stored credentials",
        parse_mode="MarkdownV2",
    )


# ── /setup conversation ────────────────────────────────────
async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🔧 *Twilio Setup*\n\n"
        "Let's configure your Twilio credentials step by step\\.\n\n"
        "*Step 1/3:* Please send your Twilio *Account SID*\\.\n"
        "_\\(Find it at https://console\\.twilio\\.com\\)_\n\n"
        "Send /cancel to abort setup\\.",
        parse_mode="MarkdownV2",
    )
    return ACCOUNT_SID


async def receive_account_sid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if not text.startswith("AC") or len(text) < 30:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid Account SID.\n"
            "It should start with `AC` and be 34 characters long.\n\n"
            "Please try again or /cancel.",
            parse_mode="Markdown",
        )
        return ACCOUNT_SID

    context.user_data["account_sid"] = text
    await update.message.reply_text(
        "✅ Account SID saved\\.\n\n"
        "*Step 2/3:* Now send your *Auth Token*\\.\n"
        "_\\(Find it on the Twilio console dashboard\\)_",
        parse_mode="MarkdownV2",
    )
    return AUTH_TOKEN


async def receive_auth_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if len(text) < 20:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid Auth Token.\n"
            "It should be 32 characters long.\n\n"
            "Please try again or /cancel.",
        )
        return AUTH_TOKEN

    context.user_data["auth_token"] = text
    await update.message.reply_text(
        "✅ Auth Token saved\\.\n\n"
        "*Step 3/3:* Now send your *Twilio phone number* in E\\.164 format\\.\n"
        "Example: `\\+15551234567`",
        parse_mode="MarkdownV2",
    )
    return PHONE_NUMBER


async def receive_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    public_url = context.bot_data["public_url"]

    if not re.match(r"^\+[1-9]\d{6,14}$", text):
        await update.message.reply_text(
            "⚠️ Invalid phone number format.\n"
            "Please use E.164 format, e.g. `+15551234567`.\n\n"
            "Try again or /cancel.",
            parse_mode="Markdown",
        )
        return PHONE_NUMBER

    chat_id = update.effective_chat.id
    account_sid = context.user_data["account_sid"]
    auth_token = context.user_data["auth_token"]
    webhook_url = f"{public_url}/webhook/{chat_id}"

    # ── Auto-configure Twilio webhook via API ───────────────
    await update.message.reply_text("⏳ Configuring your Twilio webhook...")

    try:
        client = TwilioClient(account_sid, auth_token)
        numbers = client.incoming_phone_numbers.list(phone_number=text)

        if not numbers:
            await update.message.reply_text(
                f"❌ Phone number `{text}` was not found in your Twilio account.\n\n"
                "Make sure you entered the correct Account SID, Auth Token, "
                "and phone number.\n\nUse /setup to try again.",
                parse_mode="Markdown",
            )
            context.user_data.clear()
            return ConversationHandler.END

        # Update the phone number's SMS webhook URL
        numbers[0].update(sms_url=webhook_url, sms_method="POST")

    except Exception as e:
        logger.error("Failed to configure Twilio webhook: %s", e)
        await update.message.reply_text(
            "❌ Failed to configure Twilio webhook.\n\n"
            f"Error: `{_escape_md2(str(e))}`\n\n"
            "Please check your credentials and try /setup again.",
            parse_mode="MarkdownV2",
        )
        context.user_data.clear()
        return ConversationHandler.END

    # ── Save to database ────────────────────────────────────
    upsert_user(chat_id, account_sid, auth_token, text)
    context.user_data.clear()

    await update.message.reply_text(
        "🎉 *Setup Complete\\!*\n\n"
        "✅ Twilio credentials saved\n"
        f"✅ Webhook auto\\-configured on `{_escape_md2(text)}`\n\n"
        "You will now receive SMS messages directly in this chat\\!",
        parse_mode="MarkdownV2",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Setup cancelled.")
    return ConversationHandler.END


# ── /status ─────────────────────────────────────────────────
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    public_url = context.bot_data["public_url"]

    if not user:
        await update.message.reply_text(
            "❌ No Twilio credentials configured.\nUse /setup to get started."
        )
        return

    sid = user["twilio_account_sid"]
    masked_sid = sid[:6] + "••••••" + sid[-4:]
    webhook_url = f"{public_url}/webhook/{chat_id}"

    await update.message.reply_text(
        "✅ *Your Configuration*\n\n"
        f"*Account SID:* `{_escape_md2(masked_sid)}`\n"
        f"*Phone Number:* `{_escape_md2(user['twilio_phone_number'])}`\n"
        "*Auth Token:* `••••••••` \\(hidden\\)\n\n"
        f"*Webhook URL:*\n`{_escape_md2(webhook_url)}`\n\n"
        "_Webhook is auto\\-configured on your Twilio number_",
        parse_mode="MarkdownV2",
    )


# ── /remove ─────────────────────────────────────────────────
async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = get_user(chat_id)

    if not user:
        await update.message.reply_text("ℹ️ No credentials stored to remove.")
        return

    # Try to clear the webhook from Twilio before deleting
    try:
        client = TwilioClient(user["twilio_account_sid"], user["twilio_auth_token"])
        numbers = client.incoming_phone_numbers.list(
            phone_number=user["twilio_phone_number"]
        )
        if numbers:
            numbers[0].update(sms_url="", sms_method="POST")
            logger.info("Cleared Twilio webhook for chat %s", chat_id)
    except Exception as e:
        logger.warning("Could not clear Twilio webhook for chat %s: %s", chat_id, e)

    remove_user(chat_id)
    await update.message.reply_text("🗑️ Your Twilio credentials and webhook have been removed.")


# ── Helpers ─────────────────────────────────────────────────
def _escape_md2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!\\"
    return re.sub(f"([{re.escape(special)}])", r"\\\1", text)


def create_bot(token: str, public_url: str) -> Application:
    """Build and return a configured python-telegram-bot Application."""
    app = Application.builder().token(token).build()

    # Store public_url so handlers can access it
    app.bot_data["public_url"] = public_url

    # Setup conversation handler
    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("setup", setup_start)],
        states={
            ACCOUNT_SID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_account_sid)],
            AUTH_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_auth_token)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone_number)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(setup_conv)
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("remove", remove))

    return app
