import db
import html
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Any

from config import ASSISTANT_DB_PATH, USER_TIMEZONE
from morning_brief import IT_WORDS

TZ = ZoneInfo(USER_TIMEZONE)
FLASH_SESSION_SIZE = 5
INTERVALS = [1, 3, 7, 14]  # days by streak level: 0→1d, 1→3d, 2→7d, 3+→14d


def init_flash_db() -> None:
    with db.connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flash_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                next_review TEXT NOT NULL,
                streak INTEGER DEFAULT 0,
                UNIQUE(chat_id, word)
            )
        """)


def _today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def get_session_cards(chat_id: int, n: int = FLASH_SESSION_SIZE) -> List[Dict[str, Any]]:
    today = _today()
    by_word = {w["word"]: w for w in IT_WORDS}

    with db.connect() as conn:
        due = [
            r[0] for r in conn.execute(
                "SELECT word FROM flash_progress WHERE chat_id = ? AND next_review <= ? ORDER BY next_review ASC",
                (chat_id, today),
            ).fetchall()
            if r[0] in by_word
        ]
        seen = {r[0] for r in conn.execute(
            "SELECT word FROM flash_progress WHERE chat_id = ?", (chat_id,)
        ).fetchall()}

    new = [w["word"] for w in IT_WORDS if w["word"] not in seen]

    selected = [by_word[w] for w in due[:n]]
    remaining = n - len(selected)
    selected += [by_word[w] for w in new[:remaining]]
    return selected


def update_card(chat_id: int, word: str, knew: bool) -> None:
    today = _today()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT streak FROM flash_progress WHERE chat_id = ? AND word = ?",
            (chat_id, word),
        ).fetchone()

        streak = ((row[0] + 1) if row else 1) if knew else 0
        interval = INTERVALS[min(streak, len(INTERVALS) - 1)]
        next_review = (date.fromisoformat(today) + timedelta(days=interval)).isoformat()

        conn.execute(
            """INSERT INTO flash_progress (chat_id, word, next_review, streak)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(chat_id, word) DO UPDATE SET
                   next_review = excluded.next_review,
                   streak = excluded.streak""",
            (chat_id, word, next_review, streak),
        )


def format_card_front(card: Dict[str, Any], idx: int, total: int) -> str:
    return f"🃏 <b>{html.escape(card['word'])}</b> ({idx}/{total})\n\nКак переводится?"


def format_card_back(card: Dict[str, Any], knew: bool) -> str:
    result = "✅ Знал!" if knew else "❌ Не знал"
    return (
        f"{result}\n\n"
        f"<b>{html.escape(card['word'])}</b> — {html.escape(card['translation'])}\n"
        f"<i>{html.escape(card['example'])}</i>"
    )


def format_session_result(known: int, total: int) -> str:
    pct = int(known / total * 100) if total else 0
    if pct == 100:
        comment = "Все слова знаешь!"
    elif pct >= 60:
        comment = "Неизвестные вернутся завтра."
    else:
        comment = "Карточки вернутся завтра — повторим."
    return f"Сессия: {known}/{total} ({pct}%)\n{comment}"
