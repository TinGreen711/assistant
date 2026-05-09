from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any

from config import USER_TIMEZONE
from state import get_session_state, build_long_horizon_context
from outcomes import get_recent_statuses
from strategy_profile import build_strategy_profile
from domains import assess_domain_alignment, DOMAINS
from study_tracker import get_streak, studied_today, get_days_idle
from morning_brief import build_morning_brief
from state import get_gilfoyle_mode
from achievements import format_daily_xp
from skills_path import get_avg_daily_readiness_delta, format_path_short


TZ = ZoneInfo(USER_TIMEZONE)


def _today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def build_checkin(chat_id: int) -> Dict[str, Any]:
    state = get_session_state(chat_id) or {}
    horizon = build_long_horizon_context(chat_id)
    strategy = build_strategy_profile(chat_id=chat_id, limit=50)
    gilfoyle = get_gilfoyle_mode(chat_id)

    streak = get_streak(chat_id)

    if gilfoyle:
        parts = ["🤖 Check-in"]
        parts.append(f"Стрик: {streak} дн." if streak > 0 else "Стрик: 0.")
        if horizon["weekly_active"]:
            parts.append(f"Цель недели: {horizon['weekly_text']}")
        if state.get("current_day") == _today_str() and state.get("daily_plan_done"):
            parts.append(f"Фокус: {state.get('daily_focus_text', '')}")
        else:
            parts.append("Плана нет. Исправь.")
        brief = build_morning_brief(chat_id, gilfoyle=True)
        if brief:
            parts.append(brief)
    else:
        parts = ["☀️ Check-in"]
        if streak > 0:
            parts.append(f"🔥 Стрик обучения: {streak} дн. подряд")
        else:
            parts.append("📚 Сессий обучения пока нет — хороший день начать")
        if horizon["weekly_active"]:
            parts.append(f"Цель недели: {horizon['weekly_text']}")
        if horizon["monthly_active"]:
            parts.append(f"Вектор месяца: {horizon['monthly_text']}")
        if state.get("current_day") == _today_str() and state.get("daily_plan_done"):
            parts.append(f"Фокус дня уже задан: {state.get('daily_focus_text', '')}")
            parts.append("Сегодня лучше не распыляться и двигать главный фокус.")
        else:
            parts.append("План дня на сегодня ещё не задан.")
            parts.append("Лучший следующий шаг — сделать план дня и зафиксировать главный фокус.")
        brief = build_morning_brief(chat_id, gilfoyle=False)
        if brief:
            parts.append(brief)

    prompt_hints = (
        "Утренний check-in пользователя. "
        "Если плана дня нет, мягко веди к /plan. "
        "Если план уже есть, усиливай движение по текущему фокусу."
    )

    if strategy["prompt_hints"]:
        prompt_hints += "\n" + strategy["prompt_hints"]

    return {
        "text": "\n".join(parts),
        "prompt_hints": prompt_hints,
    }


def build_evening_reminder(chat_id: int) -> Dict[str, Any]:
    state = get_session_state(chat_id) or {}
    daily_xp_line = format_daily_xp(chat_id)

    if state.get("current_day") == _today_str() and state.get("daily_plan_done") and not state.get("daily_closed"):
        text = (
            "🌙 Напоминание про закрытие дня\n"
            f"Фокус дня: {state.get('daily_focus_text', '')}\n"
            f"{daily_xp_line}\n"
            "Полезно закрыть день и зафиксировать вывод.\n"
            "Была мысль или идея за день? /capture — сохранится в Obsidian со связями."
        )
    else:
        text = (
            "🌙 Напоминание на вечер\n"
            f"{daily_xp_line}\n"
            "Если день уже закончен, можно сделать closing и зафиксировать вывод.\n"
            "Была мысль или идея за день? /capture — сохранится в Obsidian со связями."
        )

    return {
        "text": text,
    }


def assess_pulse(chat_id: int) -> Dict[str, Any]:
    state = get_session_state(chat_id) or {}
    horizon = build_long_horizon_context(chat_id)

    mode = str(state.get("active_mode", "")).strip() or None
    statuses = get_recent_statuses(chat_id=chat_id, mode=mode, limit=3)

    if len(statuses) >= 2 and statuses[0] == "blocked" and statuses[1] == "blocked":
        return {
            "trigger": "recovery",
            "text": (
                "📡 Pulse\n"
                "Вижу серию блокеров. Сейчас лучше резко упростить следующий шаг и снизить сопротивление."
            ),
            "prompt_hints": (
                "Proactive trigger: два последних результата в текущем режиме были blocked. "
                "Нужно сильнее упростить следующий шаг, уменьшить размер задачи и снизить порог входа."
            ),
        }

    if len(statuses) >= 3 and statuses[0] == "success" and statuses[1] == "success" and statuses[2] == "success":
        return {
            "trigger": "advance",
            "text": (
                "📡 Pulse\n"
                "Вижу хорошую серию успехов. Можно слегка усилить шаг и взять действие с большей отдачей."
            ),
            "prompt_hints": (
                "Proactive trigger: три последних результата были success. "
                "Можно предложить чуть более сильный следующий шаг без резкого скачка."
            ),
        }

    if horizon["weekly_active"] and state.get("current_day") == _today_str() and state.get("daily_plan_done"):
        daily_focus_domain = str(state.get("daily_focus_domain", "")).strip()
        alignment = assess_domain_alignment(horizon["weekly_domain"], daily_focus_domain)
        if alignment["relation"] == "off_focus":
            return {
                "trigger": "refocus_week",
                "text": (
                    "📡 Pulse\n"
                    "Фокус дня ушёл в сторону от цели недели. Стоит мягко вернуть курс."
                ),
                "prompt_hints": (
                    "Proactive trigger: текущий фокус дня уводит в сторону от цели недели. "
                    "Нужно мягко вернуть пользователя к недельной линии."
                ),
            }

    if horizon["weekly_active"] and not state.get("daily_plan_done"):
        return {
            "trigger": "setup_day",
            "text": (
                "📡 Pulse\n"
                "Цель недели есть, а план дня ещё не задан. Полезно сначала собрать план дня."
            ),
            "prompt_hints": (
                "Proactive trigger: задана цель недели, но на сегодня нет плана дня. "
                "Полезно сначала сделать /plan."
            ),
        }

    return {
        "trigger": "steady",
        "text": (
            "📡 Pulse\n"
            "Сейчас состояние выглядит стабильным. Продолжай держать главный фокус и маленькие проверяемые шаги."
        ),
        "prompt_hints": (
            "Proactive trigger: состояние стабильное. "
            "Держи текущий вектор без лишнего усложнения."
        ),
    }


def _cost_text(chat_id: int, days_idle: int) -> str:
    """Строка с ценой простоя в % и днях отставания."""
    avg_delta = get_avg_daily_readiness_delta(chat_id, days=7)
    if avg_delta <= 0:
        return ""
    lost_pct = round(avg_delta * days_idle, 1)
    readiness_line = format_path_short(chat_id)
    return (
        f"Простой {days_idle} дн. — это −{lost_pct}% от темпа.\n"
        f"{readiness_line}\n"
        "5 минут /quiz или /flash вернут ~+0.5%."
    )


def build_midday_nudge(chat_id: int) -> Dict[str, Any] | None:
    """Возвращает сообщение если к 14:00 нет учебной сессии, иначе None."""
    if studied_today(chat_id):
        return None

    gilfoyle = get_gilfoyle_mode(chat_id)
    days_idle = get_days_idle(chat_id)

    if gilfoyle:
        cost = _cost_text(chat_id, days_idle) if days_idle >= 2 else ""
        text = f"14:00. Сессии обучения нет. /study\n{cost}".strip()
    else:
        cost = _cost_text(chat_id, days_idle) if days_idle >= 2 else ""
        text = (
            "📚 Уже 14:00, а учебной сессии сегодня ещё не было.\n"
            "Даже 15 минут считается — нажми /study и залогируй."
        )
        if cost:
            text += f"\n\n{cost}"

    return {"text": text}


def build_streak_guard(chat_id: int) -> Dict[str, Any] | None:
    """Возвращает сообщение если к 18:20 нет учебной сессии, иначе None."""
    if studied_today(chat_id):
        return None

    gilfoyle = get_gilfoyle_mode(chat_id)
    streak = get_streak(chat_id)
    days_idle = get_days_idle(chat_id)
    cost = _cost_text(chat_id, days_idle) if days_idle >= 2 else ""

    if gilfoyle:
        base = f"18:20. Стрик {streak} дн. сгорит в полночь. /study" if streak > 0 else "18:20. Сессии нет. /study"
        text = f"{base}\n{cost}".strip() if cost else base
    else:
        if streak > 0:
            text = (
                f"⚠️ 18:20 — до полуночи ещё есть время.\n"
                f"Стрик {streak} дн. сгорит если не залогировать сессию сегодня.\n"
                "Открой /study — даже одна тема засчитывается."
            )
        else:
            text = (
                "🌆 18:20 — день ещё не закончен.\n"
                "Учебной сессии сегодня не было. Самое время начать — /study"
            )
        if cost:
            text += f"\n\n{cost}"

    return {"text": text}
