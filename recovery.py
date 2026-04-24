from typing import Dict, List, Optional


FAILURE_REASON_BUTTONS = [
    "не хватило времени",
    "не хватило сил",
    "шаг был неясный",
    "отвлёкся",
    "это не то направление",
]


BLOCKED_RESULT_KEYWORDS = [
    "не сделал",
    "не получилось",
    "не успел",
    "ошибка",
    "сил не хватило",
    "не понял",
    "нужно проще",
    "нужно упростить",
    "не ведёт к доходу",
    "всё ещё хаос",
]


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def should_ask_failure_reason(result_label: str) -> bool:
    text = _normalize(result_label)
    return any(keyword in text for keyword in BLOCKED_RESULT_KEYWORDS)


def get_failure_reason_buttons() -> List[str]:
    return FAILURE_REASON_BUTTONS[:]


def _build_summary(selected_option: str, failure_reason: str) -> str:
    mapping = {
        "не хватило времени": f"Шаг «{selected_option}» оказался слишком большим для доступного времени.",
        "не хватило сил": f"Шаг «{selected_option}» не подошёл по текущему уровню энергии.",
        "шаг был неясный": f"Шаг «{selected_option}» был недостаточно понятным и конкретным.",
        "отвлёкся": f"Шаг «{selected_option}» сорвался из-за отвлечения, а не из-за сути задачи.",
        "это не то направление": f"Шаг «{selected_option}» оказался не в том направлении.",
    }
    return mapping.get(failure_reason, f"Шаг «{selected_option}» не сработал и требует коррекции.")


def _build_lesson(mode: str, failure_reason: str) -> str:
    if failure_reason == "не хватило времени":
        return "Следующий шаг должен быть короче, быстрее и без подготовительного разгона."

    if failure_reason == "не хватило сил":
        return "Следующий шаг должен быть мягче, легче и с меньшим сопротивлением."

    if failure_reason == "шаг был неясный":
        return "Нужно переформулировать действие так, чтобы было понятно, что делать прямо сейчас."

    if failure_reason == "отвлёкся":
        return "Нужен шаг, который можно начать моментально и завершить до следующего отвлечения."

    if failure_reason == "это не то направление":
        return "Нужно сменить вектор и выбрать более релевантное действие вместо продолжения той же ветки."

    return "Следующий шаг нужно сделать проще и понятнее."


def _build_next_direction(mode: str, failure_reason: str) -> str:
    if failure_reason == "не хватило времени":
        return "Дай 3 варианта на 3–5 минут без длинного входа."

    if failure_reason == "не хватило сил":
        return "Дай 3 щадящих варианта с минимальной нагрузкой."

    if failure_reason == "шаг был неясный":
        return "Дай 3 предельно конкретных варианта, где ясно, что открыть, проверить или записать."

    if failure_reason == "отвлёкся":
        return "Дай 3 варианта с очень низким порогом входа."

    if failure_reason == "это не то направление":
        return "Дай 3 варианта в другом, более подходящем направлении."

    return "Дай 3 более простых варианта."


def _build_memory_note(
    original_request: str,
    selected_option: str,
    result_label: str,
    failure_reason: str,
    mode: str,
) -> str:
    return (
        f"mode={mode}; "
        f"request={original_request.strip()}; "
        f"selected={selected_option.strip()}; "
        f"result={result_label.strip()}; "
        f"failure_reason={failure_reason.strip()}; "
        f"status=blocked"
    )


def build_recovery(
    original_request: str,
    selected_option: str,
    result_label: str,
    failure_reason: str,
    mode: str,
    history: Optional[List[str]] = None,
    recent_memory: str = "",
) -> Dict:
    history = history or []

    summary = _build_summary(selected_option, failure_reason)
    lesson = _build_lesson(mode, failure_reason)
    next_direction = _build_next_direction(mode, failure_reason)

    history_block = "\n".join(f"- {item}" for item in history[-6:]) if history else "- пока нет"
    recent_block = recent_memory.strip() if recent_memory.strip() else "нет свежих записей"

    next_prompt = f"""
Исходный запрос пользователя:
{original_request}

Выбранный шаг:
{selected_option}

Результат:
{result_label}

Причина провала:
{failure_reason}

Короткий вывод:
{summary}

Урок:
{lesson}

Направление recovery:
{next_direction}

История последних выборов:
{history_block}

Недавняя память:
{recent_block}

Сделай следующее:
1. Дай короткую суть текущего состояния.
2. Дай 3 НОВЫХ варианта следующего действия.
3. Они должны учитывать причину провала.
4. Не повторяй буквально прошлый шаг.
5. Учитывай режим: {mode}.
""".strip()

    return {
        "mode": mode,
        "status": "blocked",
        "failure_reason": failure_reason,
        "summary": summary,
        "lesson": lesson,
        "next_direction": next_direction,
        "next_prompt": next_prompt,
        "memory_note": _build_memory_note(
            original_request=original_request,
            selected_option=selected_option,
            result_label=result_label,
            failure_reason=failure_reason,
            mode=mode,
        ),
    }


if __name__ == "__main__":
    review = build_recovery(
        original_request="У меня есть 10 минут времени, предложи маленькую задачу",
        selected_option="Проверить 1 сценарий бота",
        result_label="не сделал",
        failure_reason="не хватило времени",
        mode="low_time",
        history=["Проверить 1 сценарий бота"],
        recent_memory="нет свежих записей",
    )
    for k, v in review.items():
        print(f"{k}: {v}")
