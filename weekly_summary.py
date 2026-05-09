import logging

from openai_client import client

from config import OPENAI_CHAT_MODEL

logger = logging.getLogger(__name__)
from memory import (
    read_profile,
    read_recent_daily_notes,
    read_recent_decision_notes,
    save_weekly_summary,
)




SYSTEM_PROMPT = """
Ты аналитический ассистент по личной продуктивности.

Тебе дают:
- профиль пользователя
- daily notes за последние дни
- decisions за последние дни
- долгий горизонт (цель недели и месячный вектор)
- личную стратегию эффективности

Особенно обращай внимание на:
- Daily Plan
- Daily Closing
- Focus
- Stop Signals
- реальные результаты
- связь дня с неделей и месяцем

Твоя задача:
сделать короткую, строгую и полезную недельную сводку.

Пиши по-русски, в markdown, без воды.

Структура ОБЯЗАТЕЛЬНА:

## Что реально происходило
2-5 коротких пунктов

## Что сработало
2-5 коротких пунктов

## Что мешало
2-5 коротких пунктов

## Как держался фокус дня
2-5 коротких пунктов

## Как день был связан с неделей и месяцем
2-5 коротких пунктов

## Повторяющиеся паттерны
2-5 коротких пунктов

## Главный вывод недели
1 короткий абзац

## Фокус на следующую неделю
1 короткий абзац

## 3 приоритета
- ...
- ...
- ...

## 3 стоп-сигнала
- ...
- ...
- ...

Очень важно:
- не придумывай лишнее;
- опирайся на записи;
- будь конкретным;
- если данных мало, прямо скажи это.
""".strip()


def _fallback_weekly_summary(daily_notes: str, decision_notes: str, long_horizon_text: str, strategy_text: str) -> str:
    combined = f"{daily_notes}\n\n{decision_notes}".lower()

    success_count = combined.count("status: success") + combined.count("результат: сделал")
    blocked_count = (
        combined.count("status: blocked")
        + combined.count("не сделал")
        + combined.count("ошибка")
        + combined.count("сил не хватило")
    )
    plan_count = combined.count("### daily plan")
    closing_count = combined.count("### daily closing")

    horizon_note = long_horizon_text.strip() if long_horizon_text.strip() else "Горизонт недели и месяца пока почти не оформлен."

    return f"""## Что реально происходило
- На неделе были попытки двигаться через маленькие шаги.
- Daily planning использовался примерно {plan_count} раз.
- Daily closing использовался примерно {closing_count} раз.

## Что сработало
- Есть признаки выполненных шагов: {success_count}.
- Формат коротких действий уже даёт основу для движения.
- Появляется структура вместо хаотичных попыток.

## Что мешало
- Есть блокеры или срывы: {blocked_count}.
- Когда шаг неясный или слишком крупный, движение замедляется.
- Без удержания фокуса день легко распадается на второстепенное.

## Как держался фокус дня
- Если фокус дня был явно задан, структуру удерживать проще.
- Когда план не закреплён, выше риск распыления.
- Фокус выигрывает от маленьких, проверяемых шагов.

## Как день был связан с неделей и месяцем
- {horizon_note}

## Повторяющиеся паттерны
- Лучше работают маленькие конкретные шаги.
- После фиксации результата становится понятнее, что делать дальше.
- Слишком большие или размытые действия снижают полезность.

## Главный вывод недели
Лучший путь сейчас — двигаться короткими, ясными, проверяемыми шагами и держать связь между днём, неделей и месяцем.

## Фокус на следующую неделю
Сделать систему более устойчивой: меньше хаоса, больше завершённых микрошагов и сильнее держать недельный вектор.

## 3 приоритета
- Начинать день с одного главного фокуса
- После каждого действия отмечать результат
- Проверять связь дня с целью недели и месячным вектором

## 3 стоп-сигнала
- Не раздувать шаг до большой задачи
- Не уходить в абстрактные рассуждения
- Не терять главный фокус дня
""".strip()


def generate_weekly_summary(
    days: int = 7,
    long_horizon_text: str = "",
    strategy_text: str = "",
) -> dict:
    profile = read_profile() or "нет данных профиля"
    daily_notes = read_recent_daily_notes(days=days)
    decision_notes = read_recent_decision_notes(days=days)

    if not daily_notes and not decision_notes:
        text = (
            "## Что реально происходило\n"
            "За последние дни почти нет данных.\n\n"
            "## Что сработало\n"
            "- Пока недостаточно записей для уверенных выводов.\n\n"
            "## Что мешало\n"
            "- Недостаточно накопленной истории.\n\n"
            "## Как держался фокус дня\n"
            "- Пока рано делать выводы.\n\n"
            "## Как день был связан с неделей и месяцем\n"
            "- Пока рано делать выводы.\n\n"
            "## Повторяющиеся паттерны\n"
            "- Пока рано делать выводы.\n\n"
            "## Главный вывод недели\n"
            "Сначала нужно накопить несколько дней реального использования.\n\n"
            "## Фокус на следующую неделю\n"
            "Пользоваться ботом регулярно и фиксировать результаты.\n\n"
            "## 3 приоритета\n"
            "- Пользоваться ботом каждый день\n"
            "- Отмечать результат после действия\n"
            "- Начинать день с одного фокуса\n\n"
            "## 3 стоп-сигнала\n"
            "- Не ждать идеальной системы до начала использования\n"
            "- Не пропускать daily history\n"
            "- Не делать слишком большие шаги сразу"
        )
        path = save_weekly_summary(text)
        return {
            "text": text,
            "saved_path": str(path),
            "source_days": 0,
        }

    prompt = f"""
Профиль пользователя:
{profile}

Долгий горизонт:
{long_horizon_text or "нет долгого горизонта"}

Личная стратегия эффективности:
{strategy_text or "нет стратегии"}

Daily notes за последние {days} дней:
{daily_notes or "нет daily notes"}

Decision notes за последние {days} дней:
{decision_notes or "нет decision notes"}
""".strip()

    try:
        response = client.responses.create(
            model=OPENAI_CHAT_MODEL,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            max_output_tokens=950,
            store=False,
        )
        text = response.output_text.strip()
        if not text:
            text = _fallback_weekly_summary(daily_notes, decision_notes, long_horizon_text, strategy_text)
    except Exception:
        logger.exception("generate_weekly_summary: OpenAI call failed")
        text = _fallback_weekly_summary(daily_notes, decision_notes, long_horizon_text, strategy_text)

    path = save_weekly_summary(text)

    return {
        "text": text,
        "saved_path": str(path),
        "source_days": days,
    }


if __name__ == "__main__":
    result = generate_weekly_summary(days=7)
    print(result["text"])
    print()
    print("saved:", result["saved_path"])
