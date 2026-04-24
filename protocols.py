from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class Protocol:
    mode: str
    label: str
    goal: str
    decision_style: str
    allowed_actions: List[str]
    forbidden_actions: List[str]
    followup_style: str
    completion_buttons: List[str]
    max_depth: int
    notes: str


PROTOCOLS: Dict[str, Protocol] = {
    "low_time": Protocol(
        mode="low_time",
        label="Мало времени",
        goal="Помочь выбрать один короткий полезный шаг, который можно сделать за 5–15 минут.",
        decision_style="Максимально конкретно, без длинных рассуждений. Только микрошаги.",
        allowed_actions=[
            "маленькая техническая правка",
            "записать 3 идеи",
            "проверить 1 команду",
            "сделать 1 короткую заметку",
            "разбить задачу на 3 пункта",
            "быстрый запуск или быстрая проверка",
        ],
        forbidden_actions=[
            "большой план на неделю",
            "тяжёлая глубокая работа",
            "многошаговый сложный проект",
            "длинные размышления",
        ],
        followup_style="После выбора переведи пользователя в немедленное выполнение. Затем спроси результат.",
        completion_buttons=["сделал", "не сделал", "нужно упростить"],
        max_depth=2,
        notes="Приоритет — завершить один маленький шаг, а не идеально спланировать всё.",
    ),
    "low_energy": Protocol(
        mode="low_energy",
        label="Низкая энергия",
        goal="Сохранить движение без перегруза и срыва.",
        decision_style="Щадящий режим. Предлагать лёгкие, выполнимые действия.",
        allowed_actions=[
            "очень простая задача",
            "5-минутный шаг",
            "короткая фиксация мыслей",
            "упрощение плана",
            "осознанный отдых с возвратом",
        ],
        forbidden_actions=[
            "сложная концентрационная работа",
            "жёсткий режим",
            "нагруженные планы",
            "агрессивная мотивация",
        ],
        followup_style="После выбора дать один мягкий следующий шаг и затем проверить, стало ли легче продолжать.",
        completion_buttons=["сделал", "не сделал", "сил не хватило"],
        max_depth=2,
        notes="Если уместно, допускается отдых как осознанное действие, а не как провал.",
    ),
    "high_energy": Protocol(
        mode="high_energy",
        label="Высокая энергия",
        goal="Использовать ресурс на полезный шаг с хорошей отдачей.",
        decision_style="Конкретно и чуть смелее. Можно предлагать более ценные действия.",
        allowed_actions=[
            "значимый шаг по проекту",
            "сильная задача с видимым прогрессом",
            "кусок глубокой работы",
            "закрытие важного хвоста",
        ],
        forbidden_actions=[
            "слишком мелкие действия без пользы",
            "бессмысленная суета",
            "абстрактные советы без выхода в действие",
        ],
        followup_style="После выбора перевести в выполнение и затем спросить, что получилось.",
        completion_buttons=["сделал", "частично", "не сделал"],
        max_depth=3,
        notes="Если есть энергия, нельзя тратить её на пустые действия.",
    ),
    "assistant_building": Protocol(
        mode="assistant_building",
        label="Работа над AI-ассистентом",
        goal="Двигать проект ассистента маленькими инженерными шагами.",
        decision_style="Инженерно, предметно, без общей болтовни.",
        allowed_actions=[
            "улучшить 1 файл",
            "добавить 1 модуль",
            "проверить 1 сценарий",
            "исправить 1 баг",
            "сделать 1 тестовый прогон",
            "упростить архитектуру",
        ],
        forbidden_actions=[
            "длинная философия о будущем проекта",
            "слишком широкие стратегии без реализации",
            "размытые формулировки",
        ],
        followup_style="После выбора перевести в конкретную команду или конкретное изменение в файле.",
        completion_buttons=["сделал", "ошибка", "нужно разбить ещё"],
        max_depth=3,
        notes="Главное — чтобы после ответа было ясно, что именно открыть, проверить или изменить.",
    ),
    "income": Protocol(
        mode="income",
        label="Фокус на доходе",
        goal="Сдвигать действия в сторону заработка, клиентов, монетизации и полезных навыков.",
        decision_style="Практично, с приоритетом на близость к деньгам.",
        allowed_actions=[
            "шаг к продаже услуги",
            "шаг к оформлению предложения",
            "шаг к контакту с клиентом",
            "шаг к упаковке навыка",
            "шаг к монетизации проекта",
        ],
        forbidden_actions=[
            "теория без связи с доходом",
            "учёба ради учёбы",
            "красивые, но бесполезные действия",
        ],
        followup_style="После выбора спросить о результате в терминах пользы: приблизило ли это к деньгам.",
        completion_buttons=["сделал", "не сделал", "не ведёт к доходу"],
        max_depth=3,
        notes="Если есть выбор между интересным и денежным, по умолчанию сдвигать в денежную сторону.",
    ),
    "learning": Protocol(
        mode="learning",
        label="Фокус на обучении",
        goal="Выбирать короткие, полезные, практические учебные шаги.",
        decision_style="Простое обучение через практику, а не через перегруз теорией.",
        allowed_actions=[
            "разобрать 1 команду",
            "сделать 1 маленькую практику",
            "исправить 1 ошибку",
            "записать 3 вывода",
            "повторить 1 рабочий сценарий",
        ],
        forbidden_actions=[
            "слишком большой учебный план",
            "много тем сразу",
            "теория без практики",
        ],
        followup_style="После выбора желательно спрашивать не только сделал ли, но и что понял.",
        completion_buttons=["сделал", "не понял", "нужно проще"],
        max_depth=3,
        notes="Учёба должна вести к закреплению через действие.",
    ),
    "chaos": Protocol(
        mode="chaos",
        label="Перегруз / хаос",
        goal="Снизить хаос и сузить выбор до одного понятного следующего шага.",
        decision_style="Максимально упрощать и сужать.",
        allowed_actions=[
            "выбрать 1 главное",
            "убрать лишнее",
            "разделить задачу на 3 части",
            "сделать самый маленький следующий шаг",
            "сначала прояснить приоритет",
        ],
        forbidden_actions=[
            "много вариантов без фильтра",
            "сложные стратегии",
            "нагромождение задач",
        ],
        followup_style="После выбора закрепить одно направление и не расширять снова.",
        completion_buttons=["сделал", "всё ещё хаос", "нужно ещё сузить"],
        max_depth=2,
        notes="Главная цель — уменьшить перегруз, а не придумать идеальный план.",
    ),
    "execution_report": Protocol(
        mode="execution_report",
        label="Отчёт о выполнении",
        goal="Понять результат прошлого шага и скорректировать траекторию.",
        decision_style="Кратко: что получилось, что не получилось, что дальше.",
        allowed_actions=[
            "зафиксировать успех",
            "разобрать препятствие",
            "упростить следующий шаг",
            "дать продолжение",
        ],
        forbidden_actions=[
            "начинать всё заново",
            "игнорировать результат",
            "давать новый хаос вместо анализа",
        ],
        followup_style="Вначале оценить исход, потом предложить продолжение или коррекцию.",
        completion_buttons=["понял", "нужно продолжение", "нужно упростить"],
        max_depth=2,
        notes="Если человек сообщает результат, сначала обработай результат, а не выдавай случайные новые варианты.",
    ),
    "general": Protocol(
        mode="general",
        label="Общий режим",
        goal="Дать 3 понятных действия без перегруза.",
        decision_style="Просто, по делу, с акцентом на следующий шаг.",
        allowed_actions=[
            "маленький полезный шаг",
            "короткий план",
            "простая проверка направления",
        ],
        forbidden_actions=[
            "расплывчатая мотивация",
            "большие абстрактные планы",
        ],
        followup_style="После выбора перевести в действие и затем проверить результат.",
        completion_buttons=["сделал", "не сделал", "нужно уточнить"],
        max_depth=2,
        notes="Используется, когда режим не распознан явно.",
    ),
}


def get_protocol(mode: str) -> Protocol:
    return PROTOCOLS.get(mode, PROTOCOLS["general"])


def protocol_to_dict(mode: str) -> Dict:
    protocol = get_protocol(mode)
    return asdict(protocol)


def build_protocol_prompt(mode: str) -> str:
    protocol = get_protocol(mode)

    allowed = "\n".join(f"- {item}" for item in protocol.allowed_actions)
    forbidden = "\n".join(f"- {item}" for item in protocol.forbidden_actions)
    buttons = "\n".join(f"- {item}" for item in protocol.completion_buttons)

    return f"""
Протокол режима: {protocol.label}

Цель:
{protocol.goal}

Стиль принятия решения:
{protocol.decision_style}

Разрешённые типы действий:
{allowed}

Запрещённые типы действий:
{forbidden}

Как вести следующий шаг:
{protocol.followup_style}

Кнопки результата:
{buttons}

Ограничение глубины:
{protocol.max_depth}

Примечание:
{protocol.notes}
""".strip()


def get_completion_buttons(mode: str) -> List[str]:
    protocol = get_protocol(mode)
    return protocol.completion_buttons[:]


def get_max_depth(mode: str) -> int:
    protocol = get_protocol(mode)
    return protocol.max_depth


if __name__ == "__main__":
    test_modes = [
        "low_time",
        "low_energy",
        "assistant_building",
        "income",
        "learning",
        "chaos",
        "execution_report",
        "general",
    ]

    for mode in test_modes:
        print("=" * 60)
        print(mode)
        print(build_protocol_prompt(mode))
        print()
