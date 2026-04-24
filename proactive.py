from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any

from config import USER_TIMEZONE
from state import get_session_state, build_long_horizon_context
from outcomes import get_recent_statuses
from strategy_profile import build_strategy_profile
from domains import assess_domain_alignment, DOMAINS


TZ = ZoneInfo(USER_TIMEZONE)


def _today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def build_checkin(chat_id: int) -> Dict[str, Any]:
    state = get_session_state(chat_id) or {}
    horizon = build_long_horizon_context(chat_id)
    strategy = build_strategy_profile(chat_id=chat_id, limit=50)

    parts = ["☀️ Check-in"]

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

    if state.get("current_day") == _today_str() and state.get("daily_plan_done") and not state.get("daily_closed"):
        text = (
            "🌙 Напоминание про закрытие дня\n"
            f"Фокус дня: {state.get('daily_focus_text', '')}\n"
            "Полезно закрыть день и зафиксировать вывод."
        )
    else:
        text = (
            "🌙 Напоминание на вечер\n"
            "Если день уже закончен, можно сделать closing и зафиксировать вывод."
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
