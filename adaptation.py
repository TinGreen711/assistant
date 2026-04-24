import re
from typing import Dict, List, Optional

from outcomes import get_recent_outcomes
from protocols import get_protocol


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\sа-яА-ЯёЁ-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: str) -> set[str]:
    return {token for token in _normalize(text).split() if len(token) >= 3}


def _too_similar(a: str, b: str) -> bool:
    na = _normalize(a)
    nb = _normalize(b)

    if not na or not nb:
        return False

    if na == nb:
        return True

    if na in nb or nb in na:
        return True

    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return False

    intersection = ta & tb
    union = ta | tb

    if not union:
        return False

    jaccard = len(intersection) / len(union)
    return jaccard >= 0.6


def _dedupe(items: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()

    for item in items:
        value = item.strip()
        if not value:
            continue

        key = _normalize(value)
        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def build_adaptation_hints(
    chat_id: int,
    mode: str,
    history: Optional[List[str]] = None,
    limit: int = 8,
) -> Dict:
    history = history or []
    outcomes = get_recent_outcomes(chat_id=chat_id, limit=limit, mode=mode)

    statuses = [
        str(item.get("review_status", "")).strip().lower()
        for item in outcomes
        if str(item.get("review_status", "")).strip()
    ]

    recent_actions = [
        str(item.get("action_text", "")).strip()
        for item in outcomes
        if str(item.get("action_text", "")).strip()
    ]

    strategy = "neutral"
    reasons: List[str] = []

    if len(statuses) >= 2 and statuses[0] == "blocked" and statuses[1] == "blocked":
        strategy = "simplify_hard"
        reasons.append("Два последних результата в этом режиме были blocked.")
    elif statuses and statuses[0] == "blocked":
        strategy = "simplify"
        reasons.append("Последний результат в этом режиме был blocked.")
    elif len(statuses) >= 2 and statuses[0] == "success" and statuses[1] == "success":
        strategy = "advance"
        reasons.append("Два последних результата в этом режиме были success.")

    avoid_actions = _dedupe((history[-3:] if history else []) + recent_actions[:3])

    protocol = get_protocol(mode)

    parts = [
        "Адаптация по истории:",
        f"- mode: {mode}",
        f"- protocol: {protocol.label}",
        f"- strategy: {strategy}",
    ]

    if reasons:
        for reason in reasons:
            parts.append(f"- reason: {reason}")

    if strategy == "simplify_hard":
        parts.append("- Следующий шаг должен быть заметно проще, меньше и яснее.")
    elif strategy == "simplify":
        parts.append("- Следующий шаг должен быть чуть проще и короче.")
    elif strategy == "advance":
        parts.append("- Следующий шаг можно сделать немного сильнее, но без резкого скачка.")
    else:
        parts.append("- Держи нормальный темп без повторов.")

    if avoid_actions:
        parts.append("- Не предлагай слишком похожие варианты к следующим действиям:")
        for action in avoid_actions[:4]:
            parts.append(f"  - {action}")

    return {
        "strategy": strategy,
        "avoid_actions": avoid_actions,
        "prompt_hints": "\n".join(parts),
    }


def filter_options(
    options: List[str],
    avoid_actions: Optional[List[str]] = None,
    history: Optional[List[str]] = None,
) -> List[str]:
    avoid_actions = avoid_actions or []
    history = history or []

    banned = _dedupe(avoid_actions + history[-3:])
    filtered: List[str] = []

    for option in options:
        value = option.strip()
        if not value:
            continue

        if any(_too_similar(value, banned_item) for banned_item in banned):
            continue

        if any(_too_similar(value, existing) for existing in filtered):
            continue

        filtered.append(value)

    return filtered


def complete_options(
    mode: str,
    strategy: str,
    current_options: List[str],
    avoid_actions: Optional[List[str]] = None,
) -> List[str]:
    avoid_actions = avoid_actions or []
    current_options = filter_options(current_options, avoid_actions=avoid_actions)

    fallback_map = {
        "low_time": [
            "Сделать 1 микрошаг за 5 минут",
            "Проверить 1 маленький сценарий",
            "Записать 3 коротких пункта",
        ],
        "low_energy": [
            "Упростить задачу до 1 лёгкого шага",
            "Сделать 1 простое действие за 5 минут",
            "Коротко записать, что сейчас мешает",
        ],
        "high_energy": [
            "Закрыть 1 заметный кусок работы",
            "Сделать сильный шаг по главной задаче",
            "Выбрать действие с наибольшей отдачей",
        ],
        "assistant_building": [
            "Исправить 1 баг в проекте",
            "Улучшить 1 файл системы",
            "Проверить 1 сценарий от входа до результата",
        ],
        "income": [
            "Сделать 1 шаг ближе к деньгам",
            "Оформить 1 понятное предложение услуги",
            "Записать 3 действия с денежным эффектом",
        ],
        "learning": [
            "Разобрать 1 ошибку или 1 команду",
            "Сделать 1 маленькую практику",
            "Записать 3 вывода по практике",
        ],
        "chaos": [
            "Выбрать 1 главное прямо сейчас",
            "Убрать всё лишнее и оставить 1 шаг",
            "Разделить задачу на 3 маленькие части",
        ],
        "execution_report": [
            "Сделать логичное продолжение",
            "Упростить следующий шаг",
            "Закрепить то, что уже сработало",
        ],
        "general": [
            "Сделать 1 маленькую задачу",
            "Упростить следующий шаг",
            "Составить короткий план на сейчас",
        ],
    }

    base = fallback_map.get(mode, fallback_map["general"])

    if strategy == "simplify_hard":
        extra = [
            "Сделать самый маленький возможный шаг",
            "Сузить задачу до 1 действия",
            "Выбрать действие на 3–5 минут",
        ]
    elif strategy == "simplify":
        extra = [
            "Упростить текущий шаг",
            "Сделать более короткий вариант",
            "Выбрать лёгкое продолжение",
        ]
    elif strategy == "advance":
        extra = [
            "Сделать чуть более сильный шаг",
            "Продвинуть задачу на следующий уровень",
            "Выбрать вариант с большей отдачей",
        ]
    else:
        extra = []

    candidates = current_options + extra + base
    completed: List[str] = []

    for item in candidates:
        item = item.strip()
        if not item:
            continue

        if any(_too_similar(item, existing) for existing in completed):
            continue

        if any(_too_similar(item, banned) for banned in avoid_actions):
            continue

        completed.append(item)

        if len(completed) >= 3:
            break

    return completed[:3]
