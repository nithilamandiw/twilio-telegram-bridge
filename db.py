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
    """Create tables if they don't exist."""
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
    # Track which SMS messages have already been forwarded
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS forwarded_messages (
            message_sid TEXT PRIMARY KEY,
            telegram_chat_id TEXT,
            forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


def get_all_users() -> list[dict]:
    """Get all registered users."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def remove_user(chat_id: int | str) -> None:
    """Delete a user's stored credentials and forwarded message history."""
    conn = _get_conn()
    conn.execute(
        "DELETE FROM forwarded_messages WHERE telegram_chat_id = ?", (str(chat_id),)
    )
    conn.execute(
        "DELETE FROM users WHERE telegram_chat_id = ?", (str(chat_id),)
    )
    conn.commit()
    conn.close()


def is_message_forwarded(message_sid: str) -> bool:
    """Check if a message has already been forwarded."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM forwarded_messages WHERE message_sid = ?", (message_sid,)
    ).fetchone()
    conn.close()
    return row is not None


def mark_message_forwarded(message_sid: str, chat_id: int | str) -> None:
    """Mark a message as forwarded."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO forwarded_messages (message_sid, telegram_chat_id) VALUES (?, ?)",
        (message_sid, str(chat_id)),
    )
    conn.commit()
    conn.close()
