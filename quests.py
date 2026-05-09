import db
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional

from config import USER_TIMEZONE

TZ = ZoneInfo(USER_TIMEZONE)

# ─── Определения квестов ──────────────────────────────────────────────────────

QUESTS: List[Dict[str, Any]] = [
    {
        "id": "linux_basics",
        "label": "Linux с нуля",
        "topic": "linux",
        "description": "5 шагов: от процессов до безопасности",
        "steps": [
            {"label": "Процессы: ps aux, kill, /proc", "action": "quiz", "topic": "linux"},
            {"label": "Файловая система: chmod, find, df", "action": "task", "topic": "linux"},
            {"label": "Сеть: ss, ip addr, /etc/hosts", "action": "quiz", "topic": "linux"},
            {"label": "Логи и systemd: journalctl, systemctl", "action": "task", "topic": "systemd"},
            {"label": "Безопасность: sudo, /etc/passwd, SSH", "action": "quiz", "topic": "linux"},
        ],
        "reward": {"badge": "Linux Foundation", "bonus_label": "+15% к Linux"},
    },
    {
        "id": "networks_basics",
        "label": "Сеть с нуля",
        "topic": "networks",
        "description": "5 шагов: от ICMP до TLS",
        "steps": [
            {"label": "ICMP и ping: как пакеты ходят по сети", "action": "quiz", "topic": "networks"},
            {"label": "TCP handshake: tcpdump и curl -v", "action": "task", "topic": "networks"},
            {"label": "DNS: dig, nslookup, записи A/AAAA/MX", "action": "quiz", "topic": "networks"},
            {"label": "HTTP/HTTPS: методы, коды, TLS-сертификаты", "action": "quiz", "topic": "networks"},
            {"label": "Диагностика: traceroute, ss, iptables", "action": "task", "topic": "networks"},
        ],
        "reward": {"badge": "Networks I", "bonus_label": "+15% к Сетям"},
    },
    {
        "id": "docker_intro",
        "label": "Docker за неделю",
        "topic": "docker",
        "description": "5 шагов: от hello-world до compose",
        "steps": [
            {"label": "Первый контейнер: run, ps, logs", "action": "task", "topic": "docker"},
            {"label": "Images: build, Dockerfile, layers", "action": "quiz", "topic": "docker"},
            {"label": "Volumes: постоянные данные", "action": "quiz", "topic": "docker"},
            {"label": "Сети Docker: bridge, host, порты", "action": "task", "topic": "docker"},
            {"label": "Docker Compose: services, depends_on", "action": "quiz", "topic": "docker"},
        ],
        "reward": {"badge": "Docker Sailor", "bonus_label": "+15% к Docker"},
    },
    {
        "id": "git_workflow",
        "label": "Git Flow",
        "topic": "git",
        "description": "5 шагов: от коммита до PR",
        "steps": [
            {"label": "Основы: add, commit, log, diff", "action": "quiz", "topic": "git"},
            {"label": "Ветки: branch, checkout, merge", "action": "task", "topic": "git"},
            {"label": "Remote: push, fetch, pull", "action": "quiz", "topic": "git"},
            {"label": "Stash, rebase, cherry-pick", "action": "task", "topic": "git"},
            {"label": "GitHub Actions: CI/CD pipeline", "action": "quiz", "topic": "cicd"},
        ],
        "reward": {"badge": "Git Master", "bonus_label": "+15% к Git"},
    },
]

QUESTS_BY_ID: Dict[str, Dict[str, Any]] = {q["id"]: q for q in QUESTS}


# ─── DB ───────────────────────────────────────────────────────────────────────

def init_quests_db() -> None:
    with db.connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                quest_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_steps_json TEXT NOT NULL DEFAULT '[]',
                completed_at TEXT,
                UNIQUE(chat_id, quest_id)
            )
        """)


def get_active_quest(chat_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает активный (незавершённый) квест или None."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT quest_id, completed_steps_json FROM quests WHERE chat_id = ? AND completed_at IS NULL ORDER BY started_at DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
    if not row:
        return None
    quest_def = QUESTS_BY_ID.get(row["quest_id"])
    if not quest_def:
        return None
    completed = json.loads(row["completed_steps_json"])
    return {**quest_def, "completed_steps": completed}


def start_quest(chat_id: int, quest_id: str) -> bool:
    """Начинает квест. False если уже активен или не существует."""
    if quest_id not in QUESTS_BY_ID:
        return False
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO quests (chat_id, quest_id, started_at, completed_steps_json) VALUES (?, ?, ?, '[]')",
                (chat_id, quest_id, now),
            )
        return True
    except Exception:
        return False


def complete_quest_step(chat_id: int, step_index: int) -> Dict[str, Any]:
    """Отмечает шаг завершённым. Возвращает {done, total, quest_completed, quest}."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT quest_id, completed_steps_json FROM quests WHERE chat_id = ? AND completed_at IS NULL ORDER BY started_at DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
    if not row:
        return {"done": 0, "total": 0, "quest_completed": False, "quest": None}

    quest_id = row["quest_id"]
    quest_def = QUESTS_BY_ID.get(quest_id, {})
    steps = quest_def.get("steps", [])
    completed = json.loads(row["completed_steps_json"])

    if step_index not in completed:
        completed.append(step_index)

    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    quest_completed = len(completed) >= len(steps)
    completed_at = now if quest_completed else None

    with db.connect() as conn:
        conn.execute(
            "UPDATE quests SET completed_steps_json = ?, completed_at = ? WHERE chat_id = ? AND quest_id = ?",
            (json.dumps(completed), completed_at, chat_id, quest_id),
        )

    return {
        "done": len(completed),
        "total": len(steps),
        "quest_completed": quest_completed,
        "quest": quest_def,
    }


def get_completed_quests(chat_id: int) -> List[str]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT quest_id FROM quests WHERE chat_id = ? AND completed_at IS NOT NULL",
            (chat_id,),
        ).fetchall()
    return [r["quest_id"] for r in rows]


def get_next_quest_step(chat_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает следующий незавершённый шаг активного квеста."""
    active = get_active_quest(chat_id)
    if not active:
        return None
    completed = active["completed_steps"]
    for i, step in enumerate(active["steps"]):
        if i not in completed:
            return {**step, "index": i, "quest_label": active["label"],
                    "total": len(active["steps"]), "done": len(completed)}
    return None


# ─── Форматирование ───────────────────────────────────────────────────────────

def format_quest_status(chat_id: int) -> str:
    active = get_active_quest(chat_id)
    completed_ids = get_completed_quests(chat_id)

    lines = ["🗺 Квесты"]

    if active:
        done = len(active["completed_steps"])
        total = len(active["steps"])
        bar = "█" * done + "░" * (total - done)
        lines.append(f"\n🔄 Активный: {active['label']} [{bar}] {done}/{total}")
        lines.append(f"   {active['description']}")
        # Следующий шаг
        next_step = get_next_quest_step(chat_id)
        if next_step:
            lines.append(f"   → Следующий шаг: {next_step['label']}")
            lines.append(f"   Действие: /{next_step['action']}")
        # Награда
        reward = active.get("reward", {})
        if reward:
            lines.append(f"   Награда: 🏅 {reward['badge']} + {reward['bonus_label']}")
    else:
        lines.append("\nАктивного квеста нет.")

    # Доступные квесты
    completed_set = set(completed_ids)
    available = [q for q in QUESTS if q["id"] != (active["id"] if active else "") and q["id"] not in completed_set]
    if available:
        lines.append("\n📋 Доступные квесты:")
        for q in available:
            lines.append(f"• {q['label']} — {q['description']}")

    if completed_ids:
        lines.append(f"\n✅ Завершены: {len(completed_ids)}/{len(QUESTS)}")

    return "\n".join(lines)


def build_quest_keyboard():
    """Keyboard для выбора квеста."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [[InlineKeyboardButton(text=f"▶️ {q['label']}", callback_data=f"quest_start_{q['id']}")]
            for q in QUESTS]
    return InlineKeyboardMarkup(rows)
