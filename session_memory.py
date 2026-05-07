import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

from config import ASSISTANT_DB_PATH, USER_TIMEZONE


TZ = ZoneInfo(USER_TIMEZONE)


def init_session_memory_db() -> None:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL
            )
        """)


def save_memory_note(chat_id: int, note_type: str, content: str) -> None:
    """Сохраняет заметку о сессии. type: 'lesson', 'closing', 'plan'."""
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    content = content.strip()
    if not content:
        return
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO session_memory (chat_id, date, type, content) VALUES (?, ?, ?, ?)",
            (chat_id, today, note_type, content),
        )


def get_recent_memory(chat_id: int, days: int = 7) -> Optional[str]:
    """Возвращает заметки за последние N дней в виде строки для промпта."""
    since = (datetime.now(TZ).date() - timedelta(days=days)).isoformat()
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        rows = conn.execute(
            """SELECT date, type, content FROM session_memory
               WHERE chat_id = ? AND date >= ?
               ORDER BY date DESC, id DESC LIMIT 30""",
            (chat_id, since),
        ).fetchall()

    if not rows:
        return None

    lines = [f"[{date} / {note_type}] {content}" for date, note_type, content in rows]
    return "\n".join(lines)
