import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo

from config import (
    ASSISTANT_DB_PATH,
    DEFAULT_MORNING_HOUR,
    DEFAULT_MORNING_MINUTE,
    DEFAULT_EVENING_HOUR,
    DEFAULT_EVENING_MINUTE,
    USER_TIMEZONE,
)


DB_PATH = Path(ASSISTANT_DB_PATH)
TZ = ZoneInfo(USER_TIMEZONE)


def _now_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def _today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def current_week_key() -> str:
    now = datetime.now(TZ)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def current_month_key() -> str:
    return datetime.now(TZ).strftime("%Y-%m")


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


def init_state_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_state (
                chat_id INTEGER PRIMARY KEY,
                active_mode TEXT DEFAULT '',
                active_request TEXT DEFAULT '',
                active_action TEXT DEFAULT '',
                active_stage TEXT DEFAULT '',
                depth INTEGER DEFAULT 0,
                last_result TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
            """
        )

        new_columns = {
            "current_day": "TEXT DEFAULT ''",
            "daily_focus_domain": "TEXT DEFAULT ''",
            "daily_focus_text": "TEXT DEFAULT ''",
            "daily_energy": "TEXT DEFAULT ''",
            "daily_time_budget": "TEXT DEFAULT ''",
            "daily_plan_done": "INTEGER DEFAULT 0",
            "daily_closed": "INTEGER DEFAULT 0",
            "week_key": "TEXT DEFAULT ''",
            "weekly_goal_domain": "TEXT DEFAULT ''",
            "weekly_goal_text": "TEXT DEFAULT ''",
            "weekly_goal_set": "INTEGER DEFAULT 0",
            "month_key": "TEXT DEFAULT ''",
            "monthly_focus_domain": "TEXT DEFAULT ''",
            "monthly_focus_text": "TEXT DEFAULT ''",
            "monthly_focus_set": "INTEGER DEFAULT 0",
            "proactive_enabled": "INTEGER DEFAULT 0",
            "morning_hour": f"INTEGER DEFAULT {DEFAULT_MORNING_HOUR}",
            "morning_minute": f"INTEGER DEFAULT {DEFAULT_MORNING_MINUTE}",
            "evening_hour": f"INTEGER DEFAULT {DEFAULT_EVENING_HOUR}",
            "evening_minute": f"INTEGER DEFAULT {DEFAULT_EVENING_MINUTE}",
            "gilfoyle_mode": "INTEGER DEFAULT 0",
        }

        for column_name, column_type in new_columns.items():
            if not _column_exists(conn, "session_state", column_name):
                conn.execute(
                    f"ALTER TABLE session_state ADD COLUMN {column_name} {column_type}"
                )

        conn.commit()


def get_session_state(chat_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM session_state WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()

    if not row:
        return None

    return dict(row)


def update_session_state(chat_id: int, **fields) -> None:
    existing = get_session_state(chat_id) or {
        "chat_id": chat_id,
        "active_mode": "",
        "active_request": "",
        "active_action": "",
        "active_stage": "",
        "depth": 0,
        "last_result": "",
        "current_day": "",
        "daily_focus_domain": "",
        "daily_focus_text": "",
        "daily_energy": "",
        "daily_time_budget": "",
        "daily_plan_done": 0,
        "daily_closed": 0,
        "week_key": "",
        "weekly_goal_domain": "",
        "weekly_goal_text": "",
        "weekly_goal_set": 0,
        "month_key": "",
        "monthly_focus_domain": "",
        "monthly_focus_text": "",
        "monthly_focus_set": 0,
        "proactive_enabled": 0,
        "morning_hour": DEFAULT_MORNING_HOUR,
        "morning_minute": DEFAULT_MORNING_MINUTE,
        "evening_hour": DEFAULT_EVENING_HOUR,
        "evening_minute": DEFAULT_EVENING_MINUTE,
        "updated_at": "",
    }

    existing.update(fields)
    existing["updated_at"] = _now_str()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO session_state (
                chat_id,
                active_mode,
                active_request,
                active_action,
                active_stage,
                depth,
                last_result,
                current_day,
                daily_focus_domain,
                daily_focus_text,
                daily_energy,
                daily_time_budget,
                daily_plan_done,
                daily_closed,
                week_key,
                weekly_goal_domain,
                weekly_goal_text,
                weekly_goal_set,
                month_key,
                monthly_focus_domain,
                monthly_focus_text,
                monthly_focus_set,
                proactive_enabled,
                morning_hour,
                morning_minute,
                evening_hour,
                evening_minute,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                active_mode=excluded.active_mode,
                active_request=excluded.active_request,
                active_action=excluded.active_action,
                active_stage=excluded.active_stage,
                depth=excluded.depth,
                last_result=excluded.last_result,
                current_day=excluded.current_day,
                daily_focus_domain=excluded.daily_focus_domain,
                daily_focus_text=excluded.daily_focus_text,
                daily_energy=excluded.daily_energy,
                daily_time_budget=excluded.daily_time_budget,
                daily_plan_done=excluded.daily_plan_done,
                daily_closed=excluded.daily_closed,
                week_key=excluded.week_key,
                weekly_goal_domain=excluded.weekly_goal_domain,
                weekly_goal_text=excluded.weekly_goal_text,
                weekly_goal_set=excluded.weekly_goal_set,
                month_key=excluded.month_key,
                monthly_focus_domain=excluded.monthly_focus_domain,
                monthly_focus_text=excluded.monthly_focus_text,
                monthly_focus_set=excluded.monthly_focus_set,
                proactive_enabled=excluded.proactive_enabled,
                morning_hour=excluded.morning_hour,
                morning_minute=excluded.morning_minute,
                evening_hour=excluded.evening_hour,
                evening_minute=excluded.evening_minute,
                updated_at=excluded.updated_at
            """,
            (
                chat_id,
                existing["active_mode"],
                existing["active_request"],
                existing["active_action"],
                existing["active_stage"],
                existing["depth"],
                existing["last_result"],
                existing["current_day"],
                existing["daily_focus_domain"],
                existing["daily_focus_text"],
                existing["daily_energy"],
                existing["daily_time_budget"],
                existing["daily_plan_done"],
                existing["daily_closed"],
                existing["week_key"],
                existing["weekly_goal_domain"],
                existing["weekly_goal_text"],
                existing["weekly_goal_set"],
                existing["month_key"],
                existing["monthly_focus_domain"],
                existing["monthly_focus_text"],
                existing["monthly_focus_set"],
                existing["proactive_enabled"],
                existing["morning_hour"],
                existing["morning_minute"],
                existing["evening_hour"],
                existing["evening_minute"],
                existing["updated_at"],
            ),
        )
        conn.commit()


def set_session_state(
    chat_id: int,
    active_mode: str = "",
    active_request: str = "",
    active_action: str = "",
    active_stage: str = "",
    depth: int = 0,
    last_result: str = "",
) -> None:
    update_session_state(
        chat_id=chat_id,
        active_mode=active_mode,
        active_request=active_request,
        active_action=active_action,
        active_stage=active_stage,
        depth=depth,
        last_result=last_result,
    )


def set_daily_focus(
    chat_id: int,
    daily_focus_domain: str,
    daily_focus_text: str,
    daily_energy: str,
    daily_time_budget: str,
) -> None:
    update_session_state(
        chat_id=chat_id,
        current_day=_today_str(),
        daily_focus_domain=daily_focus_domain,
        daily_focus_text=daily_focus_text,
        daily_energy=daily_energy,
        daily_time_budget=daily_time_budget,
        daily_plan_done=1,
        daily_closed=0,
    )


def mark_daily_closed(chat_id: int, closed: bool = True) -> None:
    update_session_state(
        chat_id=chat_id,
        daily_closed=1 if closed else 0,
    )


def set_weekly_goal(chat_id: int, weekly_goal_domain: str, weekly_goal_text: str) -> None:
    update_session_state(
        chat_id=chat_id,
        week_key=current_week_key(),
        weekly_goal_domain=weekly_goal_domain,
        weekly_goal_text=weekly_goal_text,
        weekly_goal_set=1,
    )


def set_monthly_focus(chat_id: int, monthly_focus_domain: str, monthly_focus_text: str) -> None:
    update_session_state(
        chat_id=chat_id,
        month_key=current_month_key(),
        monthly_focus_domain=monthly_focus_domain,
        monthly_focus_text=monthly_focus_text,
        monthly_focus_set=1,
    )


def set_proactive_settings(
    chat_id: int,
    enabled: bool,
    morning_hour: int | None = None,
    morning_minute: int | None = None,
    evening_hour: int | None = None,
    evening_minute: int | None = None,
) -> None:
    update_session_state(
        chat_id=chat_id,
        proactive_enabled=1 if enabled else 0,
        morning_hour=DEFAULT_MORNING_HOUR if morning_hour is None else morning_hour,
        morning_minute=DEFAULT_MORNING_MINUTE if morning_minute is None else morning_minute,
        evening_hour=DEFAULT_EVENING_HOUR if evening_hour is None else evening_hour,
        evening_minute=DEFAULT_EVENING_MINUTE if evening_minute is None else evening_minute,
    )


def get_proactive_settings(chat_id: int) -> Dict[str, Any]:
    state = get_session_state(chat_id) or {}
    return {
        "enabled": bool(state.get("proactive_enabled", 0)),
        "morning_hour": int(state.get("morning_hour", DEFAULT_MORNING_HOUR) or DEFAULT_MORNING_HOUR),
        "morning_minute": int(state.get("morning_minute", DEFAULT_MORNING_MINUTE) or DEFAULT_MORNING_MINUTE),
        "evening_hour": int(state.get("evening_hour", DEFAULT_EVENING_HOUR) or DEFAULT_EVENING_HOUR),
        "evening_minute": int(state.get("evening_minute", DEFAULT_EVENING_MINUTE) or DEFAULT_EVENING_MINUTE),
    }


def list_proactive_enabled_sessions() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM session_state
            WHERE proactive_enabled = 1
            """
        ).fetchall()

    return [dict(row) for row in rows]


def build_long_horizon_context(chat_id: int) -> Dict[str, Any]:
    from domains import DOMAINS

    state = get_session_state(chat_id) or {}

    weekly_active = bool(
        state.get("weekly_goal_set")
        and state.get("week_key") == current_week_key()
        and state.get("weekly_goal_text")
    )
    monthly_active = bool(
        state.get("monthly_focus_set")
        and state.get("month_key") == current_month_key()
        and state.get("monthly_focus_text")
    )

    weekly_domain = str(state.get("weekly_goal_domain", "")).strip()
    weekly_text = str(state.get("weekly_goal_text", "")).strip()
    monthly_domain = str(state.get("monthly_focus_domain", "")).strip()
    monthly_text = str(state.get("monthly_focus_text", "")).strip()

    summary_lines = []
    prompt_lines = ["Долгий горизонт пользователя:"]

    if weekly_active:
        summary_lines.append(
            f"Цель недели: {weekly_text} ({DOMAINS.get(weekly_domain, 'Общее')})"
        )
        prompt_lines.append(f"- weekly_goal_domain: {weekly_domain}")
        prompt_lines.append(f"- weekly_goal_text: {weekly_text}")
    else:
        prompt_lines.append("- weekly_goal: не задана")

    if monthly_active:
        summary_lines.append(
            f"Месячный вектор: {monthly_text} ({DOMAINS.get(monthly_domain, 'Общее')})"
        )
        prompt_lines.append(f"- monthly_focus_domain: {monthly_domain}")
        prompt_lines.append(f"- monthly_focus_text: {monthly_text}")
    else:
        prompt_lines.append("- monthly_focus: не задан")

    return {
        "weekly_active": weekly_active,
        "weekly_domain": weekly_domain,
        "weekly_text": weekly_text,
        "weekly_domain_label": DOMAINS.get(weekly_domain, DOMAINS["general"]),
        "monthly_active": monthly_active,
        "monthly_domain": monthly_domain,
        "monthly_text": monthly_text,
        "monthly_domain_label": DOMAINS.get(monthly_domain, DOMAINS["general"]),
        "summary_text": "\n".join(summary_lines).strip(),
        "prompt_hints": "\n".join(prompt_lines).strip(),
    }


def set_gilfoyle_mode(chat_id: int, enabled: bool) -> None:
    update_session_state(chat_id=chat_id, gilfoyle_mode=1 if enabled else 0)


def get_gilfoyle_mode(chat_id: int) -> bool:
    state = get_session_state(chat_id) or {}
    return bool(state.get("gilfoyle_mode", 0))


def clear_session_state(chat_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM session_state WHERE chat_id = ?", (chat_id,))
        conn.commit()
