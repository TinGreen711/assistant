from typing import Dict, List, Optional

from protocols import get_protocol


POSITIVE_KEYWORDS = [
    "сделал",
    "готово",
    "выполнил",
    "закончил",
    "завершил",
    "понял",
]

PARTIAL_KEYWORDS = [
    "частично",
    "часть",
    "продвинулся",
    "продвинул",
]

BLOCKED_KEYWORDS = [
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

SOFT_BLOCK_KEYWORDS = [
    "отвлёкся",
    "отвлекся",
    "помешало",
    "сорвался",
]


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _contains_any(text: str, keywords: List[str]) -> List[str]:
    found = []
    for kw in keywords:
        if kw in text:
            found.append(kw)
    return found


def classify_result(result_label: str) -> Dict:
    text = _normalize(result_label)

    pos = _contains_any(text, POSITIVE_KEYWORDS)
    partial = _contains_any(text, PARTIAL_KEYWORDS)
    blocked = _contains_any(text, BLOCKED_KEYWORDS)
    soft_block = _contains_any(text, SOFT_BLOCK_KEYWORDS)

    if pos and not blocked:
        return {
            "status": "success",
            "confidence": "high",
            "signals": pos,
        }

    if partial:
        return {
            "status": "partial",
            "confidence": "medium",
            "signals": partial,
        }

    if blocked:
        return {
            "status": "blocked",
            "confidence": "high",
            "signals": blocked,
        }

    if soft_block:
        return {
            "status": "blocked",
            "confidence": "medium",
            "signals": soft_block,
        }

    return {
        "status": "unclear",
        "confidence": "low",
        "signals": ["unknown"],
    }


def _build_summary(mode: str, status: str, selected_option: str) -> str:
    if status == "success":
        return f"Шаг сработал: пользователь смог выполнить действие «{selected_option}»."

    if status == "partial":
        return f"Шаг выполнен частично: действие «{selected_option}» сдвинуло ситуацию, но не закрыло её полностью."

    if status == "blocked":
        return f"Шаг не сработал как нужно: действие «{selected_option}» оказалось слишком сложным или что-то помешало."

    return f"Результат шага «{selected_option}» неясен, нужна аккуратная коррекция."


def _build_lesson(mode: str, status: str) -> str:
    if mode == "low_time":
        if status == "success":
            return "Короткие микрошаги работают — можно продолжать цепочку маленькими действиями."
        if status == "blocked":
            return "Даже микрошаг оказался тяжёлым или неудачным — следующий шаг надо ещё сильнее упростить."
        return "Нужно удерживать короткий формат и не расширять задачу."

    if mode == "low_energy":
        if status == "success":
            return "Щадящий формат оказался посильным — важно продолжать без перегруза."
        if status == "blocked":
            return "Текущий уровень всё ещё тяжёлый — нужно ещё больше снизить сопротивление."
        return "Нужен мягкий темп и бережная корректировка."

    if mode == "assistant_building":
        if status == "success":
            return "Инженерный шаг дал результат — можно двигать проект следующей конкретной правкой."
        if status == "blocked":
            return "Шаг по проекту был слишком крупным или неясным — его надо разбить."
        return "Нужно сохранить инженерную конкретику и сузить задачу."

    if mode == "income":
        if status == "success":
            return "Действие действительно двигало в сторону денег — стоит продолжать по этой линии."
        if status == "blocked":
            return "Выбранный шаг не приблизил к доходу или оказался неудобным — нужен более прямой денежный ход."
        return "Нужно проверять пользу через близость к деньгам."

    if mode == "learning":
        if status == "success":
            return "Формат обучения сработал — стоит закреплять практикой."
        if status == "blocked":
            return "Учебный шаг был слишком сложным или неудачно выбран — надо упростить и сделать практичнее."
        return "Лучше держаться коротких практических шагов."

    if mode == "chaos":
        if status == "success":
            return "Удалось снизить хаос — дальше важно не расширять выбор снова."
        if status == "blocked":
            return "Хаос всё ещё не снижен — нужно ещё сильнее сузить фокус."
        return "Нужно не добавлять новые ветки, а упрощать."

    if mode == "execution_report":
        if status == "success":
            return "Есть подтверждение движения — можно переходить к логичному продолжению."
        if status == "blocked":
            return "Отчёт показал препятствие — сначала нужна коррекция, а не новый большой шаг."
        return "Сначала уточняем результат, потом продолжаем."

    if status == "success":
        return "Текущий формат шага работает — можно двигаться дальше без резкого усложнения."
    if status == "blocked":
        return "Шаг оказался неудачным — следующий ход должен быть проще и яснее."
    return "Нужна мягкая коррекция следующего шага."


def _build_next_direction(mode: str, status: str) -> str:
    protocol = get_protocol(mode)

    if status == "success":
        return (
            "Переходи к логичному продолжению, но не делай скачок слишком большим. "
            f"Оставайся в рамках режима «{protocol.label}»."
        )

    if status == "partial":
        return (
            "Либо добей этот же шаг в упрощённом виде, либо выбери очень близкое продолжение. "
            f"Не ломай протокол «{protocol.label}»."
        )

    if status == "blocked":
        return (
            "Следующий шаг нужно сделать проще, меньше и яснее. "
            f"Сохраняй рамки режима «{protocol.label}» и не расширяй задачу."
        )

    return (
        "Нужен осторожный следующий шаг без резкого усложнения. "
        f"Оставайся в логике режима «{protocol.label}»."
    )


def _build_memory_note(
    original_request: str,
    selected_option: str,
    result_label: str,
    mode: str,
    status: str,
) -> str:
    return (
        f"mode={mode}; "
        f"request={original_request.strip()}; "
        f"selected={selected_option.strip()}; "
        f"result={result_label.strip()}; "
        f"status={status}"
    )


def build_review(
    original_request: str,
    selected_option: str,
    result_label: str,
    mode: str,
    history: Optional[List[str]] = None,
    recent_memory: str = "",
) -> Dict:
    history = history or []

    classification = classify_result(result_label)
    status = classification["status"]

    summary = _build_summary(mode, status, selected_option)
    lesson = _build_lesson(mode, status)
    next_direction = _build_next_direction(mode, status)

    history_block = "\n".join(f"- {item}" for item in history[-6:]) if history else "- пока нет"
    recent_block = recent_memory.strip() if recent_memory.strip() else "нет свежих записей"

    next_prompt = f"""
Исходный запрос пользователя:
{original_request}

Выбранное действие:
{selected_option}

Результат:
{result_label}

Классификация результата:
- status: {status}
- confidence: {classification["confidence"]}
- signals: {", ".join(classification["signals"])}

Короткий вывод:
{summary}

Урок:
{lesson}

Направление следующего шага:
{next_direction}

История последних выборов:
{history_block}

Недавняя память:
{recent_block}

Сделай следующее:
1. Дай короткую суть текущего состояния.
2. Дай 3 НОВЫХ варианта следующего действия.
3. Если статус success — продолжай логично.
4. Если status blocked — упрости.
5. Не повторяй буквально прошлый шаг.
6. Учитывай режим: {mode}.
""".strip()

    return {
        "mode": mode,
        "status": status,
        "confidence": classification["confidence"],
        "signals": classification["signals"],
        "summary": summary,
        "lesson": lesson,
        "next_direction": next_direction,
        "next_prompt": next_prompt,
        "memory_note": _build_memory_note(
            original_request=original_request,
            selected_option=selected_option,
            result_label=result_label,
            mode=mode,
            status=status,
        ),
    }


if __name__ == "__main__":
    tests = [
        {
            "original_request": "У меня есть 10 минут времени, предложи маленькую задачу",
            "selected_option": "Проверить 1 рабочий сценарий бота",
            "result_label": "сделал",
            "mode": "low_time",
        },
        {
            "original_request": "Я устал после работы",
            "selected_option": "Сделать 1 простую задачу за 5 минут",
            "result_label": "сил не хватило",
            "mode": "low_energy",
        },
        {
            "original_request": "Хочу подвигать проект ассистента",
            "selected_option": "Улучшить 1 файл проекта",
            "result_label": "ошибка",
            "mode": "assistant_building",
        },
    ]

    for item in tests:
        print("=" * 60)
        review = build_review(
            original_request=item["original_request"],
            selected_option=item["selected_option"],
            result_label=item["result_label"],
            mode=item["mode"],
            history=["предыдущий шаг 1", "предыдущий шаг 2"],
            recent_memory="нет свежих записей",
        )
        for k, v in review.items():
            print(f"{k}: {v}")
        print()
