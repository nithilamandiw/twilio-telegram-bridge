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
        "2️⃣  Configure the webhook URL in your Twilio console\n"
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
    upsert_user(
        chat_id,
        context.user_data["account_sid"],
        context.user_data["auth_token"],
        text,
    )
    context.user_data.clear()

    webhook_url = f"{public_url}/webhook/{chat_id}"

    await update.message.reply_text(
        "🎉 *Setup Complete\\!*\n\n"
        "Your Twilio credentials have been saved\\.\n\n"
        "*Now configure your Twilio webhook:*\n"
        "1\\. Go to the [Twilio Console](https://console\\.twilio\\.com)\n"
        "2\\. Navigate to *Phone Numbers* → *Manage* → *Active Numbers*\n"
        f"3\\. Click your number \\(`{_escape_md2(text)}`\\)\n"
        "4\\. Under *Messaging*, set "A message comes in" to:\n\n"
        f"`{_escape_md2(webhook_url)}`\n\n"
        "5\\. Set the method to *HTTP POST*\n"
        "6\\. Click *Save*\n\n"
        "✅ You'll now receive SMS messages in this chat\\!",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
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
        "_Set this URL in your Twilio console under_\n"
        "_Messaging → Phone Number → A MESSAGE COMES IN_",
        parse_mode="MarkdownV2",
    )


# ── /remove ─────────────────────────────────────────────────
async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = get_user(chat_id)

    if not user:
        await update.message.reply_text("ℹ️ No credentials stored to remove.")
        return

    remove_user(chat_id)
    await update.message.reply_text("🗑️ Your Twilio credentials have been deleted.")


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
