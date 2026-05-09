import db
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import ASSISTANT_DB_PATH, USER_TIMEZONE
from study_tracker import get_streak, get_stats, TOPICS
from morning_brief import IT_WORDS
from quiz import QUIZ_TOPICS
from xp import format_xp_status
from achievements import format_daily_xp, get_unlocked, ACHIEVEMENTS

TZ = ZoneInfo(USER_TIMEZONE)


def _week_start() -> str:
    today = datetime.now(TZ).date()
    return (today - timedelta(days=today.weekday())).isoformat()


def build_stats_text(chat_id: int) -> str:
    streak = get_streak(chat_id)
    study = get_stats(chat_id)
    week = _week_start()

    with db.connect() as conn:
        quiz_rows = conn.execute(
            """SELECT topic, SUM(correct), SUM(total)
               FROM quiz_results WHERE chat_id = ?
               GROUP BY topic ORDER BY CAST(SUM(correct) AS FLOAT)/SUM(total) DESC""",
            (chat_id,),
        ).fetchall()

        task_rows = conn.execute(
            """SELECT topic, SUM(completed), COUNT(*)
               FROM task_completions WHERE chat_id = ?
               GROUP BY topic""",
            (chat_id,),
        ).fetchall()

        flash_known = (conn.execute(
            "SELECT COUNT(*) FROM flash_progress WHERE chat_id = ? AND streak > 0",
            (chat_id,),
        ).fetchone() or [0])[0]

        sessions_this_week = (conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE chat_id = ? AND date >= ?",
            (chat_id, week),
        ).fetchone() or [0])[0]

    lines = ["📊 *Статистика*\n"]

    lines.append(format_xp_status(chat_id))
    lines.append(format_daily_xp(chat_id))
    lines.append("")

    # Streak + weekly activity
    lines.append(f"🔥 Стрик: {streak} дн.")
    lines.append(f"📅 Сессий на этой неделе: {sessions_this_week}")
    total_sessions = sum(t["count"] for t in study["topics"]) if study["topics"] else 0
    lines.append(f"📚 Сессий всего: {total_sessions}")

    # Study sessions by topic
    if study["topics"]:
        lines.append("")
        for t in study["topics"]:
            lines.append(f"  {t['label']}: {t['count']} сес.")

    # Quiz results
    lines.append("\n🧩 *Квизы*")
    if quiz_rows:
        for topic, correct, total in quiz_rows:
            label = QUIZ_TOPICS.get(topic, TOPICS.get(topic, topic))
            pct = round(100 * correct / total) if total else 0
            filled = pct // 10
            bar = "▓" * filled + "░" * (10 - filled)
            lines.append(f"{label}: {correct}/{total} ({pct}%) {bar}")
    else:
        lines.append("Пока нет данных — пройди /quiz")

    # Task results
    lines.append("\n🔧 *Задачи*")
    if task_rows:
        for topic, done, total in task_rows:
            label = TOPICS.get(topic, topic)
            pct = round(100 * done / total) if total else 0
            lines.append(f"{label}: {done}/{total} ({pct}%)")
    else:
        lines.append("Пока нет данных — попробуй /task")

    # Flash progress
    flash_total = len(IT_WORDS)
    lines.append(f"\n🃏 *Флэшкарты*: {flash_known}/{flash_total} слов знаю")

    # Achievements
    unlocked = get_unlocked(chat_id)
    if unlocked:
        lines.append(f"\n🏅 *Ачивки* ({len(unlocked)}/{len(ACHIEVEMENTS)})")
        for key in ACHIEVEMENTS:
            if key in unlocked:
                a = ACHIEVEMENTS[key]
                lines.append(f"  {a['emoji']} {a['name']}")

    return "\n".join(lines)


def build_weekly_report_text(chat_id: int) -> str:
    week = _week_start()

    with db.connect() as conn:
        sessions_week = conn.execute(
            """SELECT topic, COUNT(*) FROM study_sessions
               WHERE chat_id = ? AND date >= ? GROUP BY topic""",
            (chat_id, week),
        ).fetchall()

        quiz_week = conn.execute(
            """SELECT topic, SUM(correct), SUM(total)
               FROM quiz_results WHERE chat_id = ? AND date >= ?
               GROUP BY topic""",
            (chat_id, week),
        ).fetchall()

        tasks_week = conn.execute(
            """SELECT SUM(completed), COUNT(*) FROM task_completions
               WHERE chat_id = ? AND date >= ?""",
            (chat_id, week),
        ).fetchone() or (0, 0)

    streak = get_streak(chat_id)

    lines = ["📋 *Итог недели*\n"]

    lines.append(f"🔥 Стрик: {streak} дн.")

    if sessions_week:
        total_s = sum(c for _, c in sessions_week)
        topic_parts = ", ".join(
            f"{TOPICS.get(t, t)} ×{c}" for t, c in sessions_week
        )
        lines.append(f"📚 Учёба: {total_s} сес. ({topic_parts})")
    else:
        lines.append("📚 Учёба: сессий на этой неделе не было")

    if quiz_week:
        total_c = sum(c for _, c, _ in quiz_week)
        total_t = sum(t for _, _, t in quiz_week)
        pct = round(100 * total_c / total_t) if total_t else 0
        lines.append(f"🧩 Квизы: {total_c}/{total_t} ({pct}%) по {len(quiz_week)} темам")
    else:
        lines.append("🧩 Квизы: не проходил")

    done, total_tasks = tasks_week
    if total_tasks:
        lines.append(f"🔧 Задачи: {done}/{total_tasks} выполнено")
    else:
        lines.append("🔧 Задачи: не брал")

    if not sessions_week and not quiz_week and not total_tasks:
        lines.append("\nНедели без данных — самое время начать. /study /quiz /task")
    else:
        lines.append("\nХорошая работа. Продолжай на следующей неделе.")

    return "\n".join(lines)
