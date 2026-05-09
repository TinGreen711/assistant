import db
import html
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any

from config import ASSISTANT_DB_PATH, USER_TIMEZONE

TZ = ZoneInfo(USER_TIMEZONE)

# (min_xp, level_name)
LEVELS = [
    (0,    "Стажёр"),
    (150,  "Junior SRE I"),
    (400,  "Junior SRE II"),
    (800,  "Junior SRE III"),
    (1500, "Middle SRE I"),
    (2500, "Middle SRE II"),
    (4000, "Senior SRE"),
]

XP_REWARDS: Dict[str, int] = {
    "quiz":        0,   # dynamic: correct * 10 + 20
    "task_done":   30,
    "task_fail":   5,
    "flash_known": 5,
    "flash_session": 10,
    "study":       15,
    "day_close":   25,
}


def init_xp_db() -> None:
    with db.connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS xp_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                source TEXT NOT NULL,
                amount INTEGER NOT NULL
            )
        """)


def get_total_xp(chat_id: int) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_log WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return row[0] if row else 0


def get_level_info(xp: int) -> Dict[str, Any]:
    level_num = 0
    for i, (threshold, _) in enumerate(LEVELS):
        if xp >= threshold:
            level_num = i

    name = LEVELS[level_num][1]
    xp_start = LEVELS[level_num][0]

    if level_num + 1 < len(LEVELS):
        xp_next = LEVELS[level_num + 1][0]
        progress = round((xp - xp_start) / (xp_next - xp_start) * 100)
        to_next = xp_next - xp
    else:
        xp_next = xp
        progress = 100
        to_next = 0

    return {
        "level": level_num,
        "name": name,
        "xp": xp,
        "xp_next": xp_next,
        "progress": progress,
        "to_next": to_next,
        "max": level_num + 1 >= len(LEVELS),
    }


def add_xp(chat_id: int, source: str, amount: int | None = None) -> Dict[str, Any]:
    if amount is None:
        amount = XP_REWARDS.get(source, 0)
    if amount <= 0:
        return {"amount": 0, "leveled_up": False}

    old_xp = get_total_xp(chat_id)
    old_level = get_level_info(old_xp)["level"]

    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO xp_log (chat_id, date, source, amount) VALUES (?, ?, ?, ?)",
            (chat_id, today, source, amount),
        )

    new_xp = old_xp + amount
    new_info = get_level_info(new_xp)
    leveled_up = new_info["level"] > old_level

    return {
        "amount": amount,
        "total": new_xp,
        "info": new_info,
        "leveled_up": leveled_up,
    }


def format_xp_status(chat_id: int) -> str:
    xp = get_total_xp(chat_id)
    info = get_level_info(xp)
    filled = info["progress"] // 10
    bar = "▓" * filled + "░" * (10 - filled)
    if info["max"]:
        return f"⭐ {info['name']} — {xp} XP (максимум)"
    return f"⭐ {info['name']} — {xp} XP  {bar}  +{info['to_next']} до след. уровня"


def format_levelup(info: Dict[str, Any]) -> str:
    return f"🎉 Новый уровень: <b>{html.escape(info['name'])}</b>!\nВсего XP: {info['xp']}"
