import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

from config import ASSISTANT_DB_PATH, USER_TIMEZONE


TZ = ZoneInfo(USER_TIMEZONE)

TOPICS: Dict[str, str] = {
    "linux": "Linux",
    "networks": "Сети",
    "docker": "Docker",
    "git": "Git",
    "ai": "AI",
    "prompt": "Prompt Engineering",
    "other": "Другое",
}


def init_study_db() -> None:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                topic TEXT NOT NULL
            )
        """)


def log_session(chat_id: int, topic: str) -> None:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO study_sessions (chat_id, date, topic) VALUES (?, ?, ?)",
            (chat_id, today, topic),
        )


def studied_today(chat_id: int) -> bool:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM study_sessions WHERE chat_id = ? AND date = ? LIMIT 1",
            (chat_id, today),
        ).fetchone()
    return row is not None


def get_streak(chat_id: int) -> int:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM study_sessions WHERE chat_id = ? ORDER BY date DESC",
            (chat_id,),
        ).fetchall()

    if not rows:
        return 0

    today = datetime.now(TZ).date()
    most_recent = date.fromisoformat(rows[0][0])

    # Стрик сломан если последняя сессия была 2+ дня назад
    if (today - most_recent).days > 1:
        return 0

    streak = 0
    expected = most_recent
    for (date_str,) in rows:
        d = date.fromisoformat(date_str)
        if d == expected:
            streak += 1
            expected -= timedelta(days=1)
        else:
            break

    return streak


def get_stats(chat_id: int) -> Dict[str, Any]:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT topic, COUNT(*) as cnt, MAX(date) as last_date
            FROM study_sessions
            WHERE chat_id = ?
            GROUP BY topic
            ORDER BY cnt DESC
            """,
            (chat_id,),
        ).fetchall()

    today = datetime.now(TZ).date()
    topics: List[Dict[str, Any]] = []

    for topic, cnt, last_date in rows:
        last = date.fromisoformat(last_date)
        days_ago = (today - last).days
        if days_ago == 0:
            when = "сегодня"
        elif days_ago == 1:
            when = "вчера"
        else:
            when = f"{days_ago} дн. назад"

        topics.append({
            "label": TOPICS.get(topic, topic),
            "count": cnt,
            "when": when,
        })

    return {
        "streak": get_streak(chat_id),
        "topics": topics,
    }


def format_study_stats(chat_id: int) -> str:
    stats = get_stats(chat_id)
    streak = stats["streak"]
    topics = stats["topics"]

    lines = ["📚 Трекер обучения"]

    if streak > 0:
        lines.append(f"🔥 Стрик: {streak} дн. подряд")
    else:
        lines.append("🔥 Стрик: 0 — начни сегодня")

    if topics:
        lines.append("")
        lines.append("По темам:")
        for t in topics:
            session_word = "сессия" if t["count"] == 1 else "сессий" if t["count"] >= 5 else "сессии"
            lines.append(f"• {t['label']} — {t['count']} {session_word} (последний раз: {t['when']})")
    else:
        lines.append("")
        lines.append("Сессий пока нет. Первая — сегодня.")

    return "\n".join(lines)
