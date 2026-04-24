import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import ASSISTANT_DB_PATH


DB_PATH = Path(ASSISTANT_DB_PATH)


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    for row in rows:
        if row["name"] == column_name:
            return True
    return False


def init_outcomes_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                mode TEXT DEFAULT '',
                request_text TEXT DEFAULT '',
                action_text TEXT DEFAULT '',
                result_label TEXT DEFAULT '',
                review_status TEXT DEFAULT '',
                review_summary TEXT DEFAULT ''
            )
            """
        )

        if not _column_exists(conn, "outcomes", "failure_reason"):
            conn.execute(
                """
                ALTER TABLE outcomes
                ADD COLUMN failure_reason TEXT DEFAULT ''
                """
            )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_outcomes_chat_created
            ON outcomes(chat_id, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_outcomes_chat_mode
            ON outcomes(chat_id, mode)
            """
        )
        conn.commit()


def log_outcome(
    chat_id: int,
    mode: str,
    request_text: str,
    action_text: str,
    result_label: str,
    review_status: str,
    review_summary: str,
    failure_reason: str = "",
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO outcomes (
                created_at,
                chat_id,
                mode,
                request_text,
                action_text,
                result_label,
                review_status,
                review_summary,
                failure_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now_str(),
                chat_id,
                mode,
                request_text,
                action_text,
                result_label,
                review_status,
                review_summary,
                failure_reason,
            ),
        )
        conn.commit()


def get_recent_outcomes(
    chat_id: int,
    limit: int = 20,
    mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with _connect() as conn:
        if mode:
            rows = conn.execute(
                """
                SELECT * FROM outcomes
                WHERE chat_id = ? AND mode = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (chat_id, mode, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM outcomes
                WHERE chat_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()

    return [dict(row) for row in rows]


def get_recent_statuses(
    chat_id: int,
    mode: Optional[str] = None,
    limit: int = 5,
) -> List[str]:
    outcomes = get_recent_outcomes(chat_id=chat_id, limit=limit, mode=mode)
    return [
        str(item.get("review_status", "")).strip().lower()
        for item in outcomes
        if str(item.get("review_status", "")).strip()
    ]


def get_recent_actions(
    chat_id: int,
    mode: Optional[str] = None,
    limit: int = 5,
) -> List[str]:
    outcomes = get_recent_outcomes(chat_id=chat_id, limit=limit, mode=mode)
    return [
        str(item.get("action_text", "")).strip()
        for item in outcomes
        if str(item.get("action_text", "")).strip()
    ]


def build_outcome_hints(
    chat_id: int,
    mode: Optional[str] = None,
    limit: int = 30,
) -> str:
    outcomes = get_recent_outcomes(chat_id=chat_id, limit=limit, mode=mode)

    if not outcomes:
        return "История результатов пока почти пустая."

    action_stats: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "success": 0,
            "partial": 0,
            "blocked": 0,
            "unclear": 0,
        }
    )
    reason_stats: Dict[str, int] = defaultdict(int)

    for item in outcomes:
        action = (item.get("action_text") or "").strip()
        status = (item.get("review_status") or "unclear").strip().lower()
        reason = (item.get("failure_reason") or "").strip()

        if reason:
            reason_stats[reason] += 1

        if not action:
            continue

        if status not in {"success", "partial", "blocked", "unclear"}:
            status = "unclear"

        action_stats[action][status] += 1

    if not action_stats:
        return "История результатов пока почти пустая."

    successful = []
    blocked = []

    for action, stats in action_stats.items():
        if stats["success"] > 0:
            successful.append(
                (action, stats["success"], stats["partial"], stats["blocked"])
            )
        if stats["blocked"] > 0:
            blocked.append(
                (action, stats["blocked"], stats["success"], stats["partial"])
            )

    successful.sort(key=lambda x: (x[1], x[2], -x[3]), reverse=True)
    blocked.sort(key=lambda x: (x[1], -x[2], -x[3]), reverse=True)

    parts = ["История результатов пользователя:"]

    if successful:
        parts.append("Лучше срабатывали:")
        for action, success_count, partial_count, blocked_count in successful[:3]:
            parts.append(
                f"- {action} | success={success_count}, partial={partial_count}, blocked={blocked_count}"
            )

    if blocked:
        parts.append("Чаще блокировались:")
        for action, blocked_count, success_count, partial_count in blocked[:3]:
            parts.append(
                f"- {action} | blocked={blocked_count}, success={success_count}, partial={partial_count}"
            )

    if reason_stats:
        parts.append("Частые причины провала:")
        sorted_reasons = sorted(reason_stats.items(), key=lambda x: x[1], reverse=True)
        for reason, count in sorted_reasons[:5]:
            parts.append(f"- {reason} | count={count}")

    if len(parts) == 1:
        parts.append("Пока недостаточно чётких паттернов.")

    return "\n".join(parts)


if __name__ == "__main__":
    init_outcomes_db()
    print("outcomes db ready")
