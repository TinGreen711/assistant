import db
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
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT topic, COUNT(*) FROM study_sessions WHERE chat_id = ? GROUP BY topic",
            (chat_id,),
        ).fetchall()
    return {topic: count for topic, count in rows}


def _get_weekly_pace(chat_id: int) -> float:
    cutoff = (datetime.now(TZ).date() - timedelta(days=28)).isoformat()
    with db.connect() as conn:
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


def format_path(chat_id: int) -> str:
    from xp import format_xp_status
    from sre_roadmap import get_current_skill
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

    lines = [
        "🗺 Путь к Junior SRE",
        format_xp_status(chat_id),
        "",
        "```",
        *bar_lines,
        "```",
    ]

    eta = _fmt_eta(s["months_remaining"])
    lines.append(f"⏱ При текущем темпе: {eta}")
    if s["next_focus"]:
        nf = s["next_focus"]
        skill = get_current_skill(chat_id, nf["key"])
        skill_suffix = f" → скилл «{skill['label']}»" if skill else ""
        lines.append(f"🎯 Следующий фокус: {nf['label']}{skill_suffix} — ещё {nf['remaining']} сессий")

    if s["next_focus"]:
        skill = get_current_skill(chat_id, s["next_focus"]["key"])
        if skill:
            lines.append(f"📌 Сейчас: {skill['label']} — {skill['criteria']}")

    return "\n".join(lines)


def format_path_short(chat_id: int) -> str:
    s = get_path_stats(chat_id)
    return f"📍 Готовность к Junior SRE: {s['readiness_pct']}% | {_fmt_eta(s['months_remaining'])}"


# ─── Readiness history ────────────────────────────────────────────────────────

def init_readiness_history_db() -> None:
    with db.connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readiness_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                readiness_pct INTEGER NOT NULL,
                linux_pct REAL NOT NULL DEFAULT 0,
                networks_pct REAL NOT NULL DEFAULT 0,
                docker_pct REAL NOT NULL DEFAULT 0,
                git_pct REAL NOT NULL DEFAULT 0,
                ai_pct REAL NOT NULL DEFAULT 0,
                prompt_pct REAL NOT NULL DEFAULT 0,
                UNIQUE(chat_id, date)
            )
        """)


def save_readiness_snapshot(chat_id: int) -> None:
    s = get_path_stats(chat_id)
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    skill_pcts = {sk["key"]: sk["pct"] for sk in s["skills"]}
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO readiness_history
                (chat_id, date, readiness_pct, linux_pct, networks_pct, docker_pct, git_pct, ai_pct, prompt_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, date) DO UPDATE SET
                readiness_pct=excluded.readiness_pct,
                linux_pct=excluded.linux_pct,
                networks_pct=excluded.networks_pct,
                docker_pct=excluded.docker_pct,
                git_pct=excluded.git_pct,
                ai_pct=excluded.ai_pct,
                prompt_pct=excluded.prompt_pct
            """,
            (
                chat_id, today,
                s["readiness_pct"],
                skill_pcts.get("linux", 0),
                skill_pcts.get("networks", 0),
                skill_pcts.get("docker", 0),
                skill_pcts.get("git", 0),
                skill_pcts.get("ai", 0),
                skill_pcts.get("prompt", 0),
            ),
        )


def get_readiness_delta_text(chat_id: int) -> str:
    today = datetime.now(TZ).date()
    yesterday = (today - timedelta(days=1)).isoformat()
    today_str = today.isoformat()

    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT date, readiness_pct, linux_pct, networks_pct, docker_pct, git_pct, ai_pct, prompt_pct
            FROM readiness_history
            WHERE chat_id = ? AND date IN (?, ?)
            ORDER BY date
            """,
            (chat_id, yesterday, today_str),
        ).fetchall()

    if len(rows) < 2:
        return ""

    by_date = {row["date"]: dict(row) for row in rows}
    if yesterday not in by_date or today_str not in by_date:
        return ""

    prev = by_date[yesterday]
    curr = by_date[today_str]

    total_delta = curr["readiness_pct"] - prev["readiness_pct"]

    skill_cols = [
        ("linux_pct", "Linux"),
        ("networks_pct", "Сети"),
        ("docker_pct", "Docker"),
        ("git_pct", "Git"),
        ("ai_pct", "AI"),
        ("prompt_pct", "Prompt"),
    ]
    moved = []
    for col, label in skill_cols:
        d = curr[col] - prev[col]
        if d >= 0.5:
            moved.append(f"+{d:.1f}% {label}")

    parts = []
    if moved:
        parts.append("📈 Сегодня: " + ", ".join(moved))
    if total_delta > 0:
        parts.append(f"Общая готовность: {curr['readiness_pct']}% (+{total_delta}%)")
    elif total_delta == 0:
        parts.append(f"Общая готовность: {curr['readiness_pct']}% (без изменений)")

    return "\n".join(parts) if parts else ""


def get_avg_daily_readiness_delta(chat_id: int, days: int = 7) -> float:
    """Средний прирост готовности в % за последние N дней (0.0 если нет данных)."""
    cutoff = (datetime.now(TZ).date() - timedelta(days=days)).isoformat()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT date, readiness_pct FROM readiness_history WHERE chat_id = ? AND date >= ? ORDER BY date",
            (chat_id, cutoff),
        ).fetchall()
    if len(rows) < 2:
        return 0.0
    first_pct = rows[0]["readiness_pct"]
    last_pct = rows[-1]["readiness_pct"]
    span_days = max(1, len(rows) - 1)
    return round((last_pct - first_pct) / span_days, 2)


def build_progress_chart(chat_id: int, days: int = 7) -> str:
    cutoff = (datetime.now(TZ).date() - timedelta(days=days)).isoformat()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT date, readiness_pct, linux_pct, networks_pct, docker_pct, git_pct, ai_pct, prompt_pct
            FROM readiness_history
            WHERE chat_id = ? AND date >= ?
            ORDER BY date
            """,
            (chat_id, cutoff),
        ).fetchall()

    if not rows:
        return (
            "Нет данных за последние 7 дней.\n"
            "Занимайся каждый день — данные начнут накапливаться с завтрашнего утра."
        )

    BLOCKS = " ▁▂▃▄▅▆▇█"

    def _bar(vals: list[float]) -> str:
        mn, mx = min(vals), max(vals)
        rng = mx - mn
        if rng < 0.1:
            return "─" * len(vals)
        return "".join(BLOCKS[round((v - mn) / rng * 8)] for v in vals)

    skill_cols = [
        ("linux_pct",    "Linux  "),
        ("networks_pct", "Сети   "),
        ("docker_pct",   "Docker "),
        ("git_pct",      "Git    "),
        ("ai_pct",       "AI     "),
        ("prompt_pct",   "Prompt "),
    ]

    first = dict(rows[0])
    last = dict(rows[-1])
    total_delta = last["readiness_pct"] - first["readiness_pct"]
    sign = "+" if total_delta >= 0 else ""

    lines = [
        f"📊 Прогресс за {days} дней ({len(rows)} снапшотов)",
        f"Готовность: {last['readiness_pct']}% ({sign}{total_delta}%)",
        "",
    ]

    for col, label in skill_cols:
        vals = [dict(r)[col] for r in rows]
        delta = vals[-1] - vals[0]
        delta_str = f"+{delta:.1f}%" if delta >= 0 else f"{delta:.1f}%"
        lines.append(f"`{label} {_bar(vals)} {delta_str}`")

    lines.append("")
    if total_delta > 2:
        lines.append("🚀 Ускоряешься — хороший темп!")
    elif total_delta > 0:
        lines.append("📈 Стабильный прогресс")
    elif total_delta == 0:
        lines.append("➡️ Без изменений за период")
    else:
        lines.append("📉 Замедлился — самое время вернуться к занятиям")

    return "\n".join(lines)
