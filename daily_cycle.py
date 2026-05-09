import logging

from openai_client import client

from config import OPENAI_CHAT_MODEL

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
Ты помощник по завершению дня.

Тебе дают:
- главный фокус дня
- данные о ресурсе и времени
- связь дня с неделей и месяцем
- сегодняшние записи
- недавние результаты

Твоя задача:
1. Коротко описать, как прошёл день.
2. Отметить, что сработало.
3. Отметить, что мешало.
4. Дать главный вывод дня.
5. Дать перенос на завтра.
6. Дать 1 первый шаг на завтра.

Пиши коротко, по-русски, в markdown.

Структура:
## Как прошёл день
...

## Что сработало
...

## Что мешало
...

## Главный вывод
...

## Перенос на завтра
...

## Первый шаг завтра
...
""".strip()


def _fallback_daily_closing(
    focus_text: str,
    energy_label: str,
    time_budget_label: str,
    long_horizon_text: str,
) -> str:
    horizon = long_horizon_text.strip() if long_horizon_text.strip() else "Неделя и месяц пока не зафиксированы."

    return f"""## Как прошёл день
День стоит оценивать через главный фокус, а не через общее ощущение загруженности.

## Что сработало
- Была задана основная линия дня.
- Появилась структура, от которой можно отталкиваться.
- Есть база для следующего дня.

## Что мешало
- Если не было движения, вероятно шаг был слишком большим или неудачно встроен в день.
- Возможны нехватка времени или ресурса.

## Главный вывод
Главный ориентир дня был: {focus_text}

## Перенос на завтра
Сохрани тот же вектор, но начни с более понятного и выполнимого шага.
{horizon}

## Первый шаг завтра
Выбрать один короткий шаг в рамках режима: {energy_label}, {time_budget_label}.
""".strip()


def generate_daily_closing(
    focus_domain: str,
    focus_text: str,
    energy_label: str,
    time_budget_label: str,
    today_notes: str,
    outcome_hints: str,
    long_horizon_text: str = "",
) -> str:
    prompt = f"""
Главный фокус дня:
- domain: {focus_domain}
- focus_text: {focus_text}
- energy: {energy_label}
- time_budget: {time_budget_label}

Связь с неделей и месяцем:
{long_horizon_text or "нет дополнительного контекста"}

Сегодняшние записи:
{today_notes or "нет сегодняшних записей"}

История результатов:
{outcome_hints or "история результатов почти пустая"}
""".strip()

    try:
        response = client.responses.create(
            model=OPENAI_CHAT_MODEL,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            max_output_tokens=700,
            store=False,
        )
        text = response.output_text.strip()
        if not text:
            text = _fallback_daily_closing(
                focus_text,
                energy_label,
                time_budget_label,
                long_horizon_text,
            )
    except Exception:
        logger.exception("generate_daily_closing: OpenAI call failed")
        text = _fallback_daily_closing(
            focus_text,
            energy_label,
            time_budget_label,
            long_horizon_text,
        )

    return text
