import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from config import ASSISTANT_DB_PATH, USER_TIMEZONE

TZ = ZoneInfo(USER_TIMEZONE)

ACHIEVEMENTS: dict[str, dict[str, str]] = {
    "first_quiz":    {"name": "Первый квиз",    "desc": "Прошёл первый квиз",            "emoji": "🧩"},
    "perfect_quiz":  {"name": "Отличник",        "desc": "Квиз на 100%",                  "emoji": "💯"},
    "first_task":    {"name": "Практик",         "desc": "Выполнил первую задачу",        "emoji": "🔧"},
    "first_flash":   {"name": "Карточник",       "desc": "Прошёл первую флэш-сессию",     "emoji": "🃏"},
    "all_topics":    {"name": "Полигон",         "desc": "Изучил все 6 тем хоть раз",     "emoji": "🗺"},
    "streak_3":      {"name": "3 дня подряд",    "desc": "Стрик 3 дня",                   "emoji": "🔥"},
    "streak_7":      {"name": "Неделя!",         "desc": "Стрик 7 дней",                  "emoji": "⚡"},
    "streak_14":     {"name": "Две недели",      "desc": "Стрик 14 дней",                 "emoji": "🌟"},
    "streak_30":     {"name": "Месяц!",          "desc": "Стрик 30 дней",                 "emoji": "🏆"},
    "xp_100":        {"name": "100 XP",          "desc": "Набрал 100 XP",                 "emoji": "⭐"},
    "xp_500":        {"name": "500 XP",          "desc": "Набрал 500 XP",                 "emoji": "🌠"},
    "xp_1000":       {"name": "1000 XP",         "desc": "Набрал 1000 XP",                "emoji": "💫"},
    "level_junior":  {"name": "Junior SRE I",    "desc": "Достиг уровня Junior SRE I",    "emoji": "🎯"},
}

DAILY_XP_GOAL = 50


def init_achievements_db() -> None:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                date TEXT NOT NULL,
                UNIQUE(chat_id, key)
            )
        """)


def get_unlocked(chat_id: int) -> set[str]:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT key FROM achievements WHERE chat_id = ?", (chat_id,)
        ).fetchall()
    return {r[0] for r in rows}


def _unlock(chat_id: int, key: str) -> None:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO achievements (chat_id, key, date) VALUES (?, ?, ?)",
            (chat_id, key, today),
        )


def check_and_unlock(
    chat_id: int,
    quiz_correct: int = 0,
    quiz_total: int = 0,
    task_completed: bool = False,
    flash_session_done: bool = False,
) -> list[str]:
    from study_tracker import get_streak
    from xp import get_total_xp, get_level_info

    unlocked = get_unlocked(chat_id)
    to_check = [k for k in ACHIEVEMENTS if k not in unlocked]
    if not to_check:
        return []

    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        quiz_count = (conn.execute(
            "SELECT COUNT(*) FROM quiz_results WHERE chat_id = ?", (chat_id,)
        ).fetchone() or [0])[0]

        task_done_count = (conn.execute(
            "SELECT COUNT(*) FROM task_completions WHERE chat_id = ? AND completed = 1", (chat_id,)
        ).fetchone() or [0])[0]

        flash_count = (conn.execute(
            "SELECT COUNT(*) FROM flash_progress WHERE chat_id = ?", (chat_id,)
        ).fetchone() or [0])[0]

        studied_topics = {r[0] for r in conn.execute(
            "SELECT DISTINCT topic FROM study_sessions WHERE chat_id = ?", (chat_id,)
        ).fetchall()}

    streak = get_streak(chat_id)
    total_xp = get_total_xp(chat_id)
    level = get_level_info(total_xp)["level"]

    conditions: dict[str, bool] = {
        "first_quiz":   quiz_count >= 1,
        "perfect_quiz": quiz_total > 0 and quiz_correct == quiz_total,
        "first_task":   task_done_count >= 1 or task_completed,
        "first_flash":  flash_count >= 1 or flash_session_done,
        "all_topics":   {"linux", "networks", "docker", "git", "ai", "prompt"} <= studied_topics,
        "streak_3":     streak >= 3,
        "streak_7":     streak >= 7,
        "streak_14":    streak >= 14,
        "streak_30":    streak >= 30,
        "xp_100":       total_xp >= 100,
        "xp_500":       total_xp >= 500,
        "xp_1000":      total_xp >= 1000,
        "level_junior": level >= 1,
    }

    newly = []
    for key in to_check:
        if conditions.get(key, False):
            _unlock(chat_id, key)
            newly.append(key)

    return newly


def format_achievement(key: str) -> str:
    a = ACHIEVEMENTS[key]
    return f"{a['emoji']} *{a['name']}* — {a['desc']}"


def get_today_xp(chat_id: int) -> int:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_log WHERE chat_id = ? AND date = ?",
            (chat_id, today),
        ).fetchone()
    return row[0] if row else 0


def format_daily_xp(chat_id: int) -> str:
    earned = get_today_xp(chat_id)
    goal = DAILY_XP_GOAL
    filled = min(10, round(earned / goal * 10))
    bar = "▓" * filled + "░" * (10 - filled)
    pct = min(100, round(earned / goal * 100))
    if earned >= goal:
        return f"⚡ Дневная цель: {earned}/{goal} XP {bar} ✅"
    return f"⚡ Дневная цель: {earned}/{goal} XP {bar} {pct}%"
