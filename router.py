import re
from typing import Dict, List, Optional


MODES = {
    "low_time": "Мало времени",
    "low_energy": "Низкая энергия",
    "high_energy": "Высокая энергия",
    "assistant_building": "Работа над AI-ассистентом",
    "income": "Фокус на доходе",
    "learning": "Фокус на обучении",
    "chaos": "Перегруз / хаос",
    "execution_report": "Отчёт о выполнении",
    "general": "Общий режим",
}


LOW_TIME_PATTERNS = [
    r"\b(\d+)\s*мин",
    r"\b(\d+)\s*минут",
    r"\b(\d+)\s*minute",
    r"\bмало времени\b",
    r"\bбыстро\b",
    r"\bна скорую\b",
]

LOW_ENERGY_KEYWORDS = [
    "устал",
    "устала",
    "усталый",
    "разбит",
    "нет сил",
    "мало сил",
    "энергии мало",
    "выжат",
    "сонный",
    "сонная",
    "не вывожу",
    "тяжело",
]

HIGH_ENERGY_KEYWORDS = [
    "хорошо себя чувствую",
    "есть энергия",
    "бодр",
    "бодра",
    "полон сил",
    "полна сил",
    "заряжен",
    "заряжена",
    "в ресурсе",
]

ASSISTANT_BUILDING_KEYWORDS = [
    "ассистент",
    "бот",
    "telegram",
    "телеграм",
    "openai",
    "обсидиан",
    "obsidian",
    "memory",
    "router",
    "brain.py",
    "bot.py",
    "проект",
]

INCOME_KEYWORDS = [
    "доход",
    "деньги",
    "заработ",
    "монет",
    "клиент",
    "продаж",
    "прибыль",
    "заработок",
]

LEARNING_KEYWORDS = [
    "учить",
    "изуч",
    "обуч",
    "linux",
    "линукс",
    "devops",
    "docker",
    "python",
    "код",
    "программ",
]

CHAOS_KEYWORDS = [
    "не понимаю",
    "хаос",
    "распыляюсь",
    "всё навалилось",
    "не знаю с чего начать",
    "не могу собраться",
    "много всего",
    "каша в голове",
]

EXECUTION_DONE_KEYWORDS = [
    "сделал",
    "готово",
    "выполнил",
    "закончил",
    "завершил",
]

EXECUTION_FAIL_KEYWORDS = [
    "не сделал",
    "не получилось",
    "не успел",
    "отвлекся",
    "отвлёкся",
    "помешало",
    "сорвался",
]


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _contains_any(text: str, keywords: List[str]) -> List[str]:
    found = []
    for kw in keywords:
        if kw in text:
            found.append(kw)
    return found


def _extract_minutes(text: str) -> Optional[int]:
    """
    Пытаемся вытащить количество минут из фразы.
    Например:
    - 'у меня есть 10 минут'
    - '5 мин'
    """
    patterns = [
        r"\b(\d{1,3})\s*мин(?:ут)?\b",
        r"\b(\d{1,3})\s*minute(?:s)?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def _score_mode(text: str) -> Dict[str, Dict]:
    """
    Система очков.
    Возвращает словарь вида:
    {
      "low_time": {"score": 3, "signals": [...]},
      ...
    }
    """
    result = {
        "low_time": {"score": 0, "signals": []},
        "low_energy": {"score": 0, "signals": []},
        "high_energy": {"score": 0, "signals": []},
        "assistant_building": {"score": 0, "signals": []},
        "income": {"score": 0, "signals": []},
        "learning": {"score": 0, "signals": []},
        "chaos": {"score": 0, "signals": []},
        "execution_report": {"score": 0, "signals": []},
        "general": {"score": 0, "signals": []},
    }

    minutes = _extract_minutes(text)
    if minutes is not None:
        if minutes <= 15:
            result["low_time"]["score"] += 4
            result["low_time"]["signals"].append(f"minutes={minutes}")
        elif minutes <= 30:
            result["low_time"]["score"] += 2
            result["low_time"]["signals"].append(f"minutes={minutes}")

    for pattern in LOW_TIME_PATTERNS:
        if re.search(pattern, text):
            result["low_time"]["score"] += 1
            result["low_time"]["signals"].append(pattern)

    found = _contains_any(text, LOW_ENERGY_KEYWORDS)
    if found:
        result["low_energy"]["score"] += len(found) * 2
        result["low_energy"]["signals"].extend(found)

    found = _contains_any(text, HIGH_ENERGY_KEYWORDS)
    if found:
        result["high_energy"]["score"] += len(found) * 2
        result["high_energy"]["signals"].extend(found)

    found = _contains_any(text, ASSISTANT_BUILDING_KEYWORDS)
    if found:
        result["assistant_building"]["score"] += len(found) * 2
        result["assistant_building"]["signals"].extend(found)

    found = _contains_any(text, INCOME_KEYWORDS)
    if found:
        result["income"]["score"] += len(found) * 2
        result["income"]["signals"].extend(found)

    found = _contains_any(text, LEARNING_KEYWORDS)
    if found:
        result["learning"]["score"] += len(found) * 2
        result["learning"]["signals"].extend(found)

    found = _contains_any(text, CHAOS_KEYWORDS)
    if found:
        result["chaos"]["score"] += len(found) * 2
        result["chaos"]["signals"].extend(found)

    done_found = _contains_any(text, EXECUTION_DONE_KEYWORDS)
    fail_found = _contains_any(text, EXECUTION_FAIL_KEYWORDS)
    if done_found or fail_found:
        result["execution_report"]["score"] += (len(done_found) + len(fail_found)) * 3
        result["execution_report"]["signals"].extend(done_found + fail_found)

    if all(v["score"] == 0 for v in result.values()):
        result["general"]["score"] = 1
        result["general"]["signals"].append("default")

    return result


def _confidence_from_score(score: int) -> str:
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def classify_request(user_text: str) -> Dict:
    """
    Главная функция роутера.
    Возвращает структуру:
    {
      "mode": "low_time",
      "mode_label": "Мало времени",
      "confidence": "high",
      "minutes": 10,
      "signals": [...],
      "summary": "...",
      "scores": {...}
    }
    """
    text = _normalize(user_text)
    minutes = _extract_minutes(text)
    scores = _score_mode(text)

    best_mode = "general"
    best_score = -1

    for mode, payload in scores.items():
        score = payload["score"]
        if score > best_score:
            best_score = score
            best_mode = mode

    signals = scores[best_mode]["signals"]
    confidence = _confidence_from_score(best_score)

    summary_map = {
        "low_time": "У пользователя мало времени, нужен микрошаг.",
        "low_energy": "У пользователя низкая энергия, нужен щадящий шаг.",
        "high_energy": "У пользователя есть ресурс, можно предложить более сильный шаг.",
        "assistant_building": "Запрос связан с проектом ассистента.",
        "income": "Запрос связан с доходом или деньгами.",
        "learning": "Запрос связан с обучением или практикой.",
        "chaos": "У пользователя ощущение перегруза, нужен упрощающий шаг.",
        "execution_report": "Похоже, пользователь сообщает результат предыдущего шага.",
        "general": "Общий режим без ярко выраженного сценария.",
    }

    return {
        "mode": best_mode,
        "mode_label": MODES[best_mode],
        "confidence": confidence,
        "minutes": minutes,
        "signals": signals,
        "summary": summary_map[best_mode],
        "scores": {mode: payload["score"] for mode, payload in scores.items()},
    }


if __name__ == "__main__":
    tests = [
        "У меня есть 10 минут времени, предложи маленькую задачу",
        "Я устал после работы",
        "Сегодня хорошо себя чувствую, хочу подвигать проект ассистента",
        "Хочу зарабатывать больше, что делать сегодня",
        "Я изучаю Linux и хочу маленькую практику",
        "Не понимаю с чего начать, каша в голове",
        "Сделал задачу, что дальше?",
    ]

    for text in tests:
        print("=" * 60)
        print(text)
        print(classify_request(text))
