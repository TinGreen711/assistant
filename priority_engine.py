from typing import Dict, List

from domains import DOMAINS


ENERGY_LABELS = {
    "low": "Низкий ресурс",
    "normal": "Нормальный ресурс",
    "high": "Высокий ресурс",
}

TIME_LABELS = {
    "short": "Короткое окно (15–30 минут)",
    "medium": "Среднее окно (30–90 минут)",
    "long": "Длинное окно (90+ минут)",
}


FOCUS_TEXT_MAP = {
    "assistant_project": "Двигать проект ассистента одним самым полезным инженерным шагом.",
    "income": "Сделать шаг, который реально приближает к деньгам или упаковке навыка.",
    "learning": "Укрепить навык через короткую практику, а не через теорию ради теории.",
    "work": "Снизить хаос и выбрать самый полезный шаг по рабочим задачам.",
    "health": "Сохранить ресурс и выбрать действие, которое улучшает состояние, а не выжигает.",
    "family": "Сделать один полезный шаг, который улучшит семейный или бытовой контекст.",
    "admin": "Навести порядок и уменьшить неопределённость через одну организующую задачу.",
    "general": "Выбрать один главный полезный вектор на день и не распыляться.",
}


def _assistant_project_priorities(energy: str, time_budget: str) -> List[str]:
    if energy == "low" or time_budget == "short":
        return [
            "Проверить 1 рабочий сценарий бота",
            "Улучшить 1 файл проекта",
            "Записать 3 идеи следующего улучшения",
        ]

    if energy == "high" and time_budget == "long":
        return [
            "Сделать заметный инженерный шаг по боту",
            "Проверить сценарий от входа до результата",
            "Упростить архитектуру в одном узком месте",
        ]

    return [
        "Исправить 1 узкое место в проекте",
        "Проверить 1 сценарий работы бота",
        "Сделать 1 понятное улучшение в коде",
    ]


def _income_priorities(energy: str, time_budget: str) -> List[str]:
    if time_budget == "short":
        return [
            "Записать 3 действия ближе к деньгам",
            "Выбрать 1 идею для монетизации",
            "Сформулировать 1 короткое предложение услуги",
        ]

    return [
        "Сделать 1 шаг к упаковке услуги или навыка",
        "Выбрать 1 денежный вектор на ближайшую неделю",
        "Определить 1 действие, которое реально приближает к доходу",
    ]


def _learning_priorities(energy: str, time_budget: str) -> List[str]:
    if energy == "low":
        return [
            "Разобрать 1 команду или 1 ошибку",
            "Сделать 1 короткую практику",
            "Записать 3 вывода в заметки",
        ]

    return [
        "Сделать 1 практический учебный шаг",
        "Разобрать 1 рабочую ошибку или команду",
        "Повторить 1 сценарий до уверенности",
    ]


def _work_priorities(energy: str, time_budget: str) -> List[str]:
    return [
        "Выбрать 1 самый полезный рабочий шаг",
        "Убрать 1 точку хаоса или задержки",
        "Закрыть 1 небольшой, но важный хвост",
    ]


def _health_priorities(energy: str, time_budget: str) -> List[str]:
    return [
        "Сделать 1 шаг на восстановление",
        "Снизить перегрузку на сегодня",
        "Выбрать действие, после которого станет легче продолжать день",
    ]


def _family_priorities(energy: str, time_budget: str) -> List[str]:
    return [
        "Сделать 1 полезный шаг по дому или семье",
        "Закрыть 1 маленький бытовой вопрос",
        "Выбрать действие, которое снизит бытовой хаос",
    ]


def _admin_priorities(energy: str, time_budget: str) -> List[str]:
    return [
        "Сделать 1 шаг по организации дня или недели",
        "Разобрать 1 точку беспорядка",
        "Сформулировать 1 ясный следующий шаг",
    ]


def _general_priorities(energy: str, time_budget: str) -> List[str]:
    return [
        "Выбрать 1 главный шаг на сегодня",
        "Упростить остальное до второстепенного",
        "Не распыляться больше чем на 1 направление",
    ]


def _get_priorities(domain: str, energy: str, time_budget: str) -> List[str]:
    mapping = {
        "assistant_project": _assistant_project_priorities,
        "income": _income_priorities,
        "learning": _learning_priorities,
        "work": _work_priorities,
        "health": _health_priorities,
        "family": _family_priorities,
        "admin": _admin_priorities,
        "general": _general_priorities,
    }
    builder = mapping.get(domain, _general_priorities)
    return builder(energy, time_budget)


def _get_stop_signals(domain: str, energy: str, time_budget: str) -> List[str]:
    common = [
        "Не распыляться на несколько равных задач",
        "Не превращать день в бесконечное планирование",
        "Не делать шаг настолько большим, что его трудно начать",
    ]

    if energy == "low":
        common.append("Не давить на себя тяжёлой задачей при низком ресурсе")

    if time_budget == "short":
        common.append("Не брать задачу, которая не влезает в короткое окно времени")

    if domain == "assistant_project":
        common.append("Не уходить в абстрактные идеи вместо одного инженерного шага")

    if domain == "income":
        common.append("Не тратить главный фокус на активность без связи с доходом")

    if domain == "learning":
        common.append("Не уходить в теорию без короткой практики")

    return common[:3]


def build_daily_plan(
    focus_domain: str,
    energy: str,
    time_budget: str,
) -> Dict:
    focus_domain = (focus_domain or "general").strip()
    energy = (energy or "normal").strip()
    time_budget = (time_budget or "medium").strip()

    focus_text = FOCUS_TEXT_MAP.get(focus_domain, FOCUS_TEXT_MAP["general"])
    priorities = _get_priorities(focus_domain, energy, time_budget)
    stop_signals = _get_stop_signals(focus_domain, energy, time_budget)

    return {
        "focus_domain": focus_domain,
        "focus_domain_label": DOMAINS.get(focus_domain, DOMAINS["general"]),
        "energy": energy,
        "energy_label": ENERGY_LABELS.get(energy, ENERGY_LABELS["normal"]),
        "time_budget": time_budget,
        "time_budget_label": TIME_LABELS.get(time_budget, TIME_LABELS["medium"]),
        "focus_text": focus_text,
        "priorities": priorities[:3],
        "stop_signals": stop_signals[:3],
    }


def build_focus_hints(
    active_focus_domain: str,
    active_focus_text: str,
    request_domain: str,
    relation: str,
) -> str:
    active_focus_label = DOMAINS.get(active_focus_domain, DOMAINS["general"])
    request_label = DOMAINS.get(request_domain, DOMAINS["general"])

    parts = [
        "Фокус дня:",
        f"- active_focus_domain: {active_focus_domain}",
        f"- active_focus_label: {active_focus_label}",
        f"- active_focus_text: {active_focus_text}",
        f"- request_domain: {request_domain}",
        f"- request_label: {request_label}",
        f"- relation: {relation}",
    ]

    if relation == "aligned":
        parts.append("- Запрос хорошо совпадает с главным фокусом дня.")
    elif relation == "related":
        parts.append("- Запрос связан с фокусом дня, но важно не потерять главный вектор.")
    elif relation == "off_focus":
        parts.append("- Запрос уводит в сторону. Если можно, мягко возвращай к главному фокусу дня.")
    else:
        parts.append("- Главный фокус дня пока не определён.")

    return "\n".join(parts)
