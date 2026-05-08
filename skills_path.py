import sqlite3
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

from config import ASSISTANT_DB_PATH, USER_TIMEZONE


TZ = ZoneInfo(USER_TIMEZONE)

SKILL_TARGETS: Dict[str, Dict[str, Any]] = {
    "linux":    {"label": "Linux",      "target": 120, "weight": 0.30},
    "networks": {"label": "Сети",       "target": 80,  "weight": 0.25},
    "docker":   {"label": "Docker",     "target": 80,  "weight": 0.20},
    "git":      {"label": "Git",        "target": 50,  "weight": 0.15},
    "ai":       {"label": "AI",         "target": 40,  "weight": 0.05},
    "prompt":   {"label": "Prompt Eng", "target": 25,  "weight": 0.05},
}

BAR_W = 12


def _bar(pct: float, width: int = BAR_W) -> str:
    filled = min(width, round(pct / 100 * width))
    return "█" * filled + "░" * (width - filled)


def _get_session_counts(chat_id: int) -> Dict[str, int]:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT topic, COUNT(*) FROM study_sessions WHERE chat_id = ? GROUP BY topic",
            (chat_id,),
        ).fetchall()
    return {topic: count for topic, count in rows}


def _get_weekly_pace(chat_id: int) -> float:
    cutoff = (datetime.now(TZ).date() - timedelta(days=28)).isoformat()
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT date) FROM study_sessions WHERE chat_id = ? AND date >= ?",
            (chat_id, cutoff),
        ).fetchone()
    days_with_study = row[0] if row else 0
    return (days_with_study / 4)  # дней в неделю за последние 4 недели


def get_path_stats(chat_id: int) -> Dict[str, Any]:
    counts = _get_session_counts(chat_id)
    skills = []
    total_remaining = 0
    weighted_readiness = 0.0

    for key, meta in SKILL_TARGETS.items():
        current = counts.get(key, 0)
        target = meta["target"]
        weight = meta["weight"]
        pct = min(100.0, current / target * 100)
        remaining = max(0, target - current)

        weighted_readiness += (pct / 100) * weight
        total_remaining += remaining

        skills.append({
            "key": key,
            "label": meta["label"],
            "current": current,
            "target": target,
            "pct": pct,
            "remaining": remaining,
            "bar": _bar(pct),
        })

    readiness_pct = round(weighted_readiness * 100)
    weekly_pace = _get_weekly_pace(chat_id)

    if weekly_pace > 0:
        weeks_remaining = total_remaining / weekly_pace
        months_remaining = round(weeks_remaining / 4.3, 1)
    else:
        months_remaining = None

    # Следующий фокус — тема с наибольшим весом где ещё не готов
    next_focus = None
    best_score = -1
    for s in skills:
        if s["remaining"] > 0:
            score = SKILL_TARGETS[s["key"]]["weight"] * (1 - s["pct"] / 100)
            if score > best_score:
                best_score = score
                next_focus = s

    return {
        "skills": skills,
        "readiness_pct": readiness_pct,
        "months_remaining": months_remaining,
        "weekly_pace": round(weekly_pace, 1),
        "next_focus": next_focus,
    }


def _fmt_eta(months_remaining: float | None) -> str:
    if months_remaining is None:
        return "нет данных о темпе"
    m = round(months_remaining)
    if m > 24:
        return ">24 мес."
    return f"~{m} мес."


def format_path(chat_id: int, gilfoyle: bool = False) -> str:
    from xp import format_xp_status
    s = get_path_stats(chat_id)

    lw = max(len(sk["label"]) for sk in s["skills"])  # label width

    def row(label: str, pct: float, current: int = 0, target: int = 0) -> str:
        b = _bar(pct)
        pct_str = f"{round(pct):3}%"
        count = f"{current}/{target}" if target else ""
        return f"{label.ljust(lw)}  {b}  {pct_str}  {count}"

    bar_lines = [row(sk["label"], sk["pct"], sk["current"], sk["target"]) for sk in s["skills"]]
    bar_lines.append("─" * (lw + 2 + BAR_W + 8))
    bar_lines.append(row("Итого", s["readiness_pct"]))

    header = "📍 Путь к Junior SRE" if gilfoyle else "🗺 Путь к Junior SRE"
    lines = [
        header,
        format_xp_status(chat_id),
        "",
        "```",
        *bar_lines,
        "```",
    ]

    eta = _fmt_eta(s["months_remaining"])
    if gilfoyle:
        lines.append(f"Темп: {eta}")
        if s["next_focus"]:
            nf = s["next_focus"]
            lines.append(f"Фокус: {nf['label']} ({nf['remaining']} сес.)")
    else:
        lines.append(f"⏱ При текущем темпе: {eta}")
        if s["next_focus"]:
            nf = s["next_focus"]
            lines.append(f"🎯 Следующий фокус: {nf['label']} — ещё {nf['remaining']} сессий")

    return "\n".join(lines)


def format_path_short(chat_id: int) -> str:
    s = get_path_stats(chat_id)
    return f"📍 Готовность к Junior SRE: {s['readiness_pct']}% | {_fmt_eta(s['months_remaining'])}"
