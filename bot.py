import re
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from twilio.rest import Client as TwilioClient

from db import (
    upsert_user,
    get_user,
    get_all_users,
    remove_user,
    is_message_forwarded,
    mark_message_forwarded,
)

logger = logging.getLogger(__name__)

# Conversation states for /setup flow
ACCOUNT_SID, AUTH_TOKEN, PHONE_NUMBER = range(3)

# Polling interval in seconds
POLL_INTERVAL = 5


# ── Keyboard Layouts ────────────────────────────────────────
def main_menu_keyboard():
    """Main menu buttons."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 Setup Twilio", callback_data="setup")],
        [
            InlineKeyboardButton("📊 Status", callback_data="status"),
            InlineKeyboardButton("🗑️ Remove", callback_data="remove"),
        ],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ])


def back_keyboard():
    """Back to main menu button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back to Menu", callback_data="menu")],
    ])


def confirm_remove_keyboard():
    """Confirm deletion buttons."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, delete", callback_data="confirm_remove"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu"),
        ],
    ])


# ── /start ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 *Welcome to the Twilio SMS Forwarder Bot!*\n\n"
        "This bot checks your Twilio account for incoming SMS "
        "and forwards them directly to this chat.\n\n"
        "*How it works:*\n"
        "1️⃣  Tap *Setup Twilio* to register your credentials\n"
        "2️⃣  The bot automatically polls for new messages\n"
        "3️⃣  New SMS messages appear right here!"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ── Button Callback Handler ────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "menu":
        await query.edit_message_text(
            "👋 *Twilio SMS Forwarder Bot*\n\n"
            "Choose an option below:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "setup":
        await query.edit_message_text(
            "🔧 *Twilio Setup*\n\n"
            "To set up, send the /setup command.\n"
            "The bot will ask you for your credentials one by one.\n\n"
            "You'll need:\n"
            "• Twilio Account SID\n"
            "• Twilio Auth Token\n"
            "• Twilio Phone Number",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Start Setup", callback_data="start_setup")],
                [InlineKeyboardButton("« Back to Menu", callback_data="menu")],
            ]),
        )

    elif data == "start_setup":
        # Trigger the setup conversation
        await query.edit_message_text(
            "🔧 *Twilio Setup*\n\n"
            "Let's configure your Twilio credentials step by step.\n\n"
            "*Step 1/3:* Please send your Twilio *Account SID*.\n"
            "_(Find it at https://console.twilio.com)_\n\n"
            "Send /cancel to abort setup.",
            parse_mode="Markdown",
        )
        # Set conversation state manually
        context.user_data["_setup_active"] = True
        context.user_data["_setup_step"] = "account_sid"

    elif data == "status":
        chat_id = update.effective_chat.id
        user = get_user(chat_id)

        if not user:
            await query.edit_message_text(
                "❌ *No Configuration Found*\n\n"
                "You haven't set up your Twilio credentials yet.\n"
                "Tap *Setup Twilio* to get started.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔧 Setup Twilio", callback_data="setup")],
                    [InlineKeyboardButton("« Back to Menu", callback_data="menu")],
                ]),
            )
            return

        sid = user["twilio_account_sid"]
        masked_sid = sid[:6] + "••••••" + sid[-4:]

        await query.edit_message_text(
            "📊 *Your Configuration*\n\n"
            f"*Account SID:* `{masked_sid}`\n"
            f"*Phone Number:* `{user['twilio_phone_number']}`\n"
            "*Auth Token:* `••••••••` (hidden)\n\n"
            f"📡 Polling every {POLL_INTERVAL} seconds for new SMS",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )

    elif data == "remove":
        chat_id = update.effective_chat.id
        user = get_user(chat_id)

        if not user:
            await query.edit_message_text(
                "ℹ️ No credentials stored to remove.",
                reply_markup=back_keyboard(),
            )
            return

        await query.edit_message_text(
            "⚠️ *Are you sure?*\n\n"
            f"This will delete your Twilio credentials for "
            f"`{user['twilio_phone_number']}` and stop SMS forwarding.",
            parse_mode="Markdown",
            reply_markup=confirm_remove_keyboard(),
        )

    elif data == "confirm_remove":
        chat_id = update.effective_chat.id
        remove_user(chat_id)
        await query.edit_message_text(
            "🗑️ *Credentials Deleted*\n\n"
            "Your Twilio credentials have been removed.\n"
            "SMS polling has stopped for your number.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 Setup Again", callback_data="setup")],
                [InlineKeyboardButton("« Back to Menu", callback_data="menu")],
            ]),
        )

    elif data == "help":
        await query.edit_message_text(
            "ℹ️ *Help*\n\n"
            "*Commands:*\n"
            "/start — Show main menu\n"
            "/setup — Configure Twilio credentials\n"
            "/status — View current configuration\n"
            "/remove — Delete stored credentials\n"
            "/cancel — Abort setup\n\n"
            "*How to get Twilio credentials:*\n"
            "1. Sign up at https://twilio.com\n"
            "2. Go to your Dashboard\n"
            "3. Copy your Account SID and Auth Token\n"
            "4. Your Twilio phone number is shown there too",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )


# ── Text handler for button-triggered setup ─────────────────
async def button_setup_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle text messages during button-triggered setup flow."""
    if not context.user_data.get("_setup_active"):
        return

    step = context.user_data.get("_setup_step")
    text = update.message.text.strip()

    if step == "account_sid":
        if not text.startswith("AC") or len(text) < 30:
            await update.message.reply_text(
                "⚠️ That doesn't look like a valid Account SID.\n"
                "It should start with `AC` and be 34 characters long.\n\n"
                "Please try again or /cancel.",
                parse_mode="Markdown",
            )
            return
        context.user_data["account_sid"] = text
        context.user_data["_setup_step"] = "auth_token"
        await update.message.reply_text(
            "✅ Account SID saved.\n\n"
            "*Step 2/3:* Now send your *Auth Token*.\n"
            "_(Find it on the Twilio console dashboard)_",
            parse_mode="Markdown",
        )

    elif step == "auth_token":
        if len(text) < 20:
            await update.message.reply_text(
                "⚠️ That doesn't look like a valid Auth Token.\n"
                "It should be 32 characters long.\n\n"
                "Please try again or /cancel.",
            )
            return
        context.user_data["auth_token"] = text
        context.user_data["_setup_step"] = "phone_number"
        await update.message.reply_text(
            "✅ Auth Token saved.\n\n"
            "*Step 3/3:* Now send your *Twilio phone number* in E.164 format.\n"
            "Example: `+15551234567`",
            parse_mode="Markdown",
        )

    elif step == "phone_number":
        if not re.match(r"^\+[1-9]\d{6,14}$", text):
            await update.message.reply_text(
                "⚠️ Invalid phone number format.\n"
                "Please use E.164 format, e.g. `+15551234567`.\n\n"
                "Try again or /cancel.",
                parse_mode="Markdown",
            )
            return

        chat_id = update.effective_chat.id
        account_sid = context.user_data["account_sid"]
        auth_token = context.user_data["auth_token"]

        await update.message.reply_text("⏳ Verifying your Twilio credentials...")

        try:
            client = TwilioClient(account_sid, auth_token)
            numbers = client.incoming_phone_numbers.list(phone_number=text)
            if not numbers:
                await update.message.reply_text(
                    f"❌ Phone number `{text}` was not found in your Twilio account.\n\n"
                    "Make sure you entered the correct credentials.\n"
                    "Use /setup to try again.",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard(),
                )
                _clear_setup(context)
                return
        except Exception as e:
            logger.error("Failed to verify Twilio credentials: %s", e)
            await update.message.reply_text(
                "❌ Failed to verify Twilio credentials.\n\n"
                f"Error: `{str(e)}`\n\n"
                "Please check your credentials and try /setup again.",
                parse_mode="Markdown",
                reply_markup=back_keyboard(),
            )
            _clear_setup(context)
            return

        upsert_user(chat_id, account_sid, auth_token, text)
        _clear_setup(context)

        await update.message.reply_text(
            "🎉 *Setup Complete!*\n\n"
            "✅ Twilio credentials verified and saved\n"
            f"✅ Monitoring `{text}` for incoming SMS\n\n"
            f"The bot checks for new messages every {POLL_INTERVAL} seconds.\n"
            "You'll receive them right here in this chat!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )


def _clear_setup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear setup state from user_data."""
    for key in ["_setup_active", "_setup_step", "account_sid", "auth_token"]:
        context.user_data.pop(key, None)


# ── /setup command (also works without buttons) ────────────
async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🔧 *Twilio Setup*\n\n"
        "Let's configure your Twilio credentials step by step.\n\n"
        "*Step 1/3:* Please send your Twilio *Account SID*.\n"
        "_(Find it at https://console.twilio.com)_\n\n"
        "Send /cancel to abort setup.",
        parse_mode="Markdown",
    )
    return ACCOUNT_SID


async def receive_account_sid(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
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
        "✅ Account SID saved.\n\n"
        "*Step 2/3:* Now send your *Auth Token*.\n"
        "_(Find it on the Twilio console dashboard)_",
        parse_mode="Markdown",
    )
    return AUTH_TOKEN


async def receive_auth_token(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
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
        "✅ Auth Token saved.\n\n"
        "*Step 3/3:* Now send your *Twilio phone number* in E.164 format.\n"
        "Example: `+15551234567`",
        parse_mode="Markdown",
    )
    return PHONE_NUMBER


async def receive_phone_number(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = update.message.text.strip()

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

    await update.message.reply_text("⏳ Verifying your Twilio credentials...")

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

    except Exception as e:
        logger.error("Failed to verify Twilio credentials: %s", e)
        await update.message.reply_text(
            "❌ Failed to verify Twilio credentials.\n\n"
            f"Error: `{str(e)}`\n\n"
            "Please check your credentials and try /setup again.",
            parse_mode="Markdown",
        )
        context.user_data.clear()
        return ConversationHandler.END

    upsert_user(chat_id, account_sid, auth_token, text)
    context.user_data.clear()

    await update.message.reply_text(
        "🎉 *Setup Complete!*\n\n"
        "✅ Twilio credentials verified and saved\n"
        f"✅ Monitoring `{text}` for incoming SMS\n\n"
        f"The bot checks for new messages every {POLL_INTERVAL} seconds.\n"
        "You'll receive them right here in this chat!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Setup cancelled.",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


# ── /status command ─────────────────────────────────────────
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = get_user(chat_id)

    if not user:
        await update.message.reply_text(
            "❌ No Twilio credentials configured.\nUse /setup to get started.",
            reply_markup=main_menu_keyboard(),
        )
        return

    sid = user["twilio_account_sid"]
    masked_sid = sid[:6] + "••••••" + sid[-4:]

    await update.message.reply_text(
        "📊 *Your Configuration*\n\n"
        f"*Account SID:* `{masked_sid}`\n"
        f"*Phone Number:* `{user['twilio_phone_number']}`\n"
        "*Auth Token:* `••••••••` (hidden)\n\n"
        f"📡 Polling every {POLL_INTERVAL} seconds for new SMS",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )


# ── /remove command ─────────────────────────────────────────
async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = get_user(chat_id)

    if not user:
        await update.message.reply_text(
            "ℹ️ No credentials stored to remove.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await update.message.reply_text(
        "⚠️ *Are you sure?*\n\n"
        f"This will delete your Twilio credentials for "
        f"`{user['twilio_phone_number']}` and stop SMS forwarding.",
        parse_mode="Markdown",
        reply_markup=confirm_remove_keyboard(),
    )


# ── Twilio SMS Polling ──────────────────────────────────────
async def poll_twilio_messages(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Periodic job: check all registered users' Twilio accounts
    for new incoming SMS messages and forward them to Telegram.
    """
    users = get_all_users()

    for user in users:
        chat_id = user["telegram_chat_id"]
        try:
            client = TwilioClient(
                user["twilio_account_sid"],
                user["twilio_auth_token"],
            )

            # Fetch recent incoming messages to the user's Twilio number
            messages = client.messages.list(
                to=user["twilio_phone_number"],
                date_sent_after=datetime.now(timezone.utc) - timedelta(minutes=5),
                limit=20,
            )

            for msg in messages:
                # Skip if already forwarded
                if is_message_forwarded(msg.sid):
                    continue

                # Only forward inbound messages
                if msg.direction != "inbound":
                    continue

                # Forward to Telegram
                text = (
                    f"📱 *New SMS to* `{msg.to}`\n"
                    f"*From:* `{msg.from_}`\n\n"
                    f"{msg.body}"
                )

                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    parse_mode="Markdown",
                )

                # Mark as forwarded
                mark_message_forwarded(msg.sid, chat_id)
                logger.info(
                    "Forwarded SMS %s to chat %s: %s → %s",
                    msg.sid, chat_id, msg.from_, msg.to,
                )

        except Exception as e:
            logger.error("Error polling Twilio for chat %s: %s", chat_id, e)


def create_bot(token: str) -> Application:
    """Build and return a configured python-telegram-bot Application."""
    app = Application.builder().token(token).build()

    # Setup conversation handler (for /setup command)
    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("setup", setup_start)],
        states={
            ACCOUNT_SID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_account_sid)
            ],
            AUTH_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_auth_token)
            ],
            PHONE_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone_number)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(setup_conv)
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("remove", remove))

    # Button callback handler
    app.add_handler(CallbackQueryHandler(button_handler))

    # Text handler for button-triggered setup
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, button_setup_text_handler)
    )

    # Register commands in Telegram's menu
    async def post_init(application: Application) -> None:
        from telegram import BotCommand

        await application.bot.set_my_commands([
            BotCommand("start", "Main menu"),
            BotCommand("setup", "Configure Twilio credentials"),
            BotCommand("status", "View current configuration"),
            BotCommand("remove", "Delete stored credentials"),
            BotCommand("cancel", "Abort setup"),
        ])
        logger.info("✅ Bot commands registered with Telegram")

    app.post_init = post_init

    # Schedule polling job
    app.job_queue.run_repeating(
        poll_twilio_messages,
        interval=POLL_INTERVAL,
        first=5,
    )

    return app
