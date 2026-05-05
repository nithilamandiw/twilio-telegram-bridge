import logging
from flask import Flask, request, Response
from twilio.request_validator import RequestValidator
from db import get_user

logger = logging.getLogger(__name__)


def create_server(bot_app, public_url: str) -> Flask:
    """
    Create and configure the Flask server with the Twilio webhook endpoint.

    Args:
        bot_app: python-telegram-bot Application instance (for sending messages)
        public_url: The public URL where this server is reachable
    """
    app = Flask(__name__)

    # ── Health check ────────────────────────────────────────
    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}, 200

    # ── Twilio SMS Webhook ──────────────────────────────────
    @app.route("/webhook/<chat_id>", methods=["POST"])
    def twilio_webhook(chat_id: str):
        # Look up user in database
        user = get_user(chat_id)
        if not user:
            logger.warning("Webhook hit for unknown chatId: %s", chat_id)
            return Response(
                "<Response><Message>User not found</Message></Response>",
                status=404,
                mimetype="text/xml",
            )

        # ── Validate Twilio request signature ───────────────
        validator = RequestValidator(user["twilio_auth_token"])
        twilio_signature = request.headers.get("X-Twilio-Signature", "")
        webhook_url = f"{public_url}/webhook/{chat_id}"

        is_valid = validator.validate(
            webhook_url,
            request.form.to_dict(),
            twilio_signature,
        )

        if not is_valid:
            logger.warning("Invalid Twilio signature for chatId: %s", chat_id)
            return Response(
                "<Response><Message>Invalid signature</Message></Response>",
                status=403,
                mimetype="text/xml",
            )

        # ── Parse incoming SMS fields ───────────────────────
        sms_from = request.form.get("From", "Unknown")
        sms_to = request.form.get("To", "Unknown")
        sms_body = request.form.get("Body", "(empty message)")

        # ── Forward to Telegram ─────────────────────────────
        message = (
            f"📱 *New SMS to* `{sms_to}`\n"
            f"*From:* `{sms_from}`\n\n"
            f"{sms_body}"
        )

        import asyncio

        async def send():
            await bot_app.bot.send_message(
                chat_id=int(chat_id),
                text=message,
                parse_mode="Markdown",
            )

        try:
            # Run the async send in the bot's event loop
            loop = bot_app.bot_data.get("event_loop")
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(send(), loop).result(timeout=10)
            else:
                asyncio.run(send())

            logger.info("SMS forwarded to chat %s: %s → %s", chat_id, sms_from, sms_to)
        except Exception as e:
            logger.error("Failed to send Telegram message to %s: %s", chat_id, e)

        # Respond with empty TwiML so Twilio doesn't retry
        return Response("<Response></Response>", mimetype="text/xml")

    return app
