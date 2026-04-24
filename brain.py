import json
import re
from typing import Dict, List, Optional

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
    MAX_OUTPUT_TOKENS,
    DAILY_MEMORY_LIMIT,
)
from memory import read_profile, read_last_daily_entries
from router import classify_request
from protocols import build_protocol_prompt, get_protocol


client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = """
Ты личный ассистент по продуктивности и планомерному развитию.

Ты НЕ обычный собеседник.
Ты принимаешь запрос, определяешь ситуацию пользователя и даёшь 3 полезных варианта следующего действия.

Жёсткие правила:
1. Не философствуй.
2. Не пиши длинную мотивацию.
3. Не повторяй один и тот же вариант разными словами.
4. Давай только короткие, практичные варианты.
5. Варианты должны быть разными по смыслу.
6. Если у пользователя мало времени — давай микрошаги.
7. Если у пользователя низкая энергия — не давай тяжёлые задачи.
8. Если запрос про проект ассистента — говори инженерно и предметно.
9. Если запрос про доход — сдвигай к действиям, ближе к деньгам.
10. Если запрос — это отчёт о выполнении, сначала обработай результат, а не начинай всё заново.
11. Учитывай адаптационные подсказки. Если сказано упростить шаг — упростить.
12. Не предлагай действия, слишком похожие на запрещённые примеры из адаптации.

Верни только JSON по схеме.
""".strip()


JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "mode": {
            "type": "string",
            "enum": [
                "low_time",
                "low_energy",
                "high_energy",
                "assistant_building",
                "income",
                "learning",
                "chaos",
                "execution_report",
                "general",
            ],
        },
        "text": {"type": "string"},
        "options": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string"},
        },
    },
    "required": ["mode", "text", "options"],
}


def _normalize_text(text: str) -> str:
    return (text or "").strip()


def _clean_option(option: str) -> str:
    value = _normalize_text(option)
    value = re.sub(r"^\d+[\).\s-]*", "", value).strip()
    value = re.sub(r"^[•\-–]\s*", "", value).strip()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _dedupe_options(options: List[str]) -> List[str]:
    cleaned: List[str] = []
    seen = set()

    for item in options:
        value = _clean_option(str(item))
        if not value:
            continue

        key = value.lower()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(value)

    return cleaned


def _extract_json(raw: str) -> Optional[Dict]:
    raw = _normalize_text(raw)
    if not raw:
        return None

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return None


def _extract_numbered_options(raw: str) -> Optional[Dict]:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return None

    text = lines[0]
    options: List[str] = []

    for line in lines:
        if re.match(r"^\d+[\)]", line):
            item = re.sub(r"^\d+[\)]\s*", "", line).strip()
            if item:
                options.append(item)

    options = _dedupe_options(options)

    if len(options) >= 3:
        return {
            "mode": "general",
            "text": text,
            "options": options[:3],
        }

    return None


def _fallback_by_mode(mode: str, user_text: str) -> Dict:
    t = user_text.lower()

    if mode == "low_time":
        return {
            "mode": "low_time",
            "text": "У тебя короткое окно времени — лучше закрыть один маленький шаг.",
            "options": [
                "Записать 3 идеи для следующего улучшения",
                "Проверить 1 рабочий сценарий бота",
                "Открыть 1 файл и поправить 1 мелочь",
            ],
        }

    if mode == "low_energy":
        return {
            "mode": "low_energy",
            "text": "Энергии мало, значит нужен щадящий, но полезный шаг.",
            "options": [
                "Сделать 1 простую задачу за 5 минут",
                "Записать, что сейчас больше всего мешает",
                "Упростить план до 1 выполнимого шага",
            ],
        }

    if mode == "high_energy":
        return {
            "mode": "high_energy",
            "text": "Ресурс есть — стоит вложить его в один сильный шаг.",
            "options": [
                "Сделать заметный шаг по проекту",
                "Закрыть самый полезный хвост",
                "Сфокусироваться на 1 задаче на результат",
            ],
        }

    if mode == "assistant_building":
        return {
            "mode": "assistant_building",
            "text": "Лучше двигать ассистента одним инженерным шагом.",
            "options": [
                "Улучшить 1 файл проекта",
                "Проверить 1 сценарий от сообщения до ответа",
                "Сформулировать следующий модуль системы",
            ],
        }

    if mode == "income":
        return {
            "mode": "income",
            "text": "Сейчас лучше выбрать действие, которое ближе к деньгам.",
            "options": [
                "Выбрать 1 идею, которую можно монетизировать",
                "Сделать 1 шаг к упаковке услуги",
                "Записать 3 действия, ведущих к доходу",
            ],
        }

    if mode == "learning":
        return {
            "mode": "learning",
            "text": "Лучше взять короткий учебный шаг с практикой.",
            "options": [
                "Разобрать 1 команду или 1 ошибку",
                "Сделать 1 маленькую практику",
                "Записать 3 вывода по изученному",
            ],
        }

    if mode == "chaos":
        return {
            "mode": "chaos",
            "text": "Сейчас важнее сузить хаос до одного понятного шага.",
            "options": [
                "Выбрать 1 главное на сейчас",
                "Разбить задачу на 3 маленькие части",
                "Убрать всё лишнее и оставить 1 шаг",
            ],
        }

    if mode == "execution_report":
        return {
            "mode": "execution_report",
            "text": "Нужно обработать результат прошлого шага и скорректировать продолжение.",
            "options": [
                "Сделать логичное продолжение",
                "Упростить следующий шаг",
                "Закрепить то, что уже сработало",
            ],
        }

    return {
        "mode": "general",
        "text": "Выбери следующее полезное действие.",
        "options": [
            "Сделать 1 маленькую задачу",
            "Навести порядок в следующем шаге",
            "Составить короткий план на сейчас",
        ],
    }


def _postprocess(data: Dict, fallback_mode: str, user_text: str) -> Dict:
    if not isinstance(data, dict):
        return _fallback_by_mode(fallback_mode, user_text)

    mode = _normalize_text(data.get("mode", fallback_mode)) or fallback_mode
    text = _normalize_text(data.get("text", ""))
    options = data.get("options", [])

    if not isinstance(options, list):
        return _fallback_by_mode(fallback_mode, user_text)

    options = _dedupe_options([str(x) for x in options])

    if len(options) < 3 or not text:
        return _fallback_by_mode(fallback_mode, user_text)

    return {
        "mode": mode,
        "text": text,
        "options": options[:3],
    }


def _build_prompt(user_text: str, extra_hints: str = "") -> tuple[str, Dict]:
    route = classify_request(user_text)
    mode = route["mode"]
    _ = get_protocol(mode)

    profile = read_profile() or "нет данных профиля"
    recent = read_last_daily_entries(limit=DAILY_MEMORY_LIMIT) or "нет недавних записей"
    protocol_text = build_protocol_prompt(mode)

    adaptation_block = extra_hints.strip() if extra_hints.strip() else "нет специальных адаптационных подсказок"

    prompt = f"""
Результат роутера:
- mode: {route["mode"]}
- label: {route["mode_label"]}
- confidence: {route["confidence"]}
- summary: {route["summary"]}
- minutes: {route["minutes"]}
- signals: {", ".join(route["signals"]) if route["signals"] else "нет"}

Протокол:
{protocol_text}

Адаптационные подсказки:
{adaptation_block}

Профиль пользователя:
{profile}

Недавние записи памяти:
{recent}

Запрос пользователя:
{user_text}

Сделай следующее:
1. Учитывай режим и протокол как жёсткие правила.
2. Учитывай адаптационные подсказки как приоритетный контекст.
3. Дай короткую суть ситуации.
4. Дай 3 коротких, конкретных, разных варианта следующего действия.
5. Не задавай вопрос, если уже можно предложить действия.
6. Варианты должны быть удобны как кнопки.
""".strip()

    return prompt, route


def _try_structured_response(prompt: str) -> Optional[Dict]:
    response = client.responses.create(
        model=OPENAI_CHAT_MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "decision_options",
                "strict": True,
                "schema": JSON_SCHEMA,
            }
        },
        max_output_tokens=MAX_OUTPUT_TOKENS,
        store=False,
    )

    raw = _normalize_text(response.output_text)
    return _extract_json(raw)


def _try_plain_response(prompt: str) -> Optional[Dict]:
    response = client.responses.create(
        model=OPENAI_CHAT_MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        store=False,
    )

    raw = _normalize_text(response.output_text)

    data = _extract_json(raw)
    if data:
        return data

    data = _extract_numbered_options(raw)
    if data:
        return data

    return None


def generate_options(user_text: str, extra_hints: str = "") -> Dict:
    prompt, route = _build_prompt(user_text, extra_hints=extra_hints)
    mode = route["mode"]

    try:
        data = _try_structured_response(prompt)
        if data:
            return _postprocess(data, mode, user_text)
    except Exception:
        pass

    try:
        data = _try_plain_response(prompt)
        if data:
            return _postprocess(data, mode, user_text)
    except Exception:
        pass

    return _fallback_by_mode(mode, user_text)
