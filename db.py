import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "bot.db")

# Ensure data directory exists
os.makedirs(DB_DIR, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    """Get a new database connection with WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create the users table if it doesn't exist."""
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_chat_id TEXT PRIMARY KEY,
            twilio_account_sid TEXT,
            twilio_auth_token TEXT,
            twilio_phone_number TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def upsert_user(
    chat_id: int | str,
    account_sid: str,
    auth_token: str,
    phone_number: str,
) -> None:
    """Save or update a user's Twilio credentials (parameterized query)."""
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO users (telegram_chat_id, twilio_account_sid, twilio_auth_token, twilio_phone_number)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_chat_id) DO UPDATE SET
            twilio_account_sid = excluded.twilio_account_sid,
            twilio_auth_token = excluded.twilio_auth_token,
            twilio_phone_number = excluded.twilio_phone_number
        """,
        (str(chat_id), account_sid, auth_token, phone_number),
    )
    conn.commit()
    conn.close()


def get_user(chat_id: int | str) -> dict | None:
    """Get a user's config by their Telegram chat ID."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE telegram_chat_id = ?", (str(chat_id),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_phone(phone_number: str) -> dict | None:
    """Get a user by their Twilio phone number."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE twilio_phone_number = ?", (phone_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def remove_user(chat_id: int | str) -> None:
    """Delete a user's stored credentials."""
    conn = _get_conn()
    conn.execute(
        "DELETE FROM users WHERE telegram_chat_id = ?", (str(chat_id),)
    )
    conn.commit()
    conn.close()
