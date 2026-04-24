from collections import defaultdict
from typing import Dict, List, Any

from outcomes import get_recent_outcomes


def _fmt_stats(stats: Dict[str, int]) -> str:
    return (
        f"success={stats.get('success', 0)}, "
        f"partial={stats.get('partial', 0)}, "
        f"blocked={stats.get('blocked', 0)}, "
        f"unclear={stats.get('unclear', 0)}"
    )


def build_strategy_profile(chat_id: int, limit: int = 80) -> Dict[str, Any]:
    outcomes = get_recent_outcomes(chat_id=chat_id, limit=limit)

    if not outcomes:
        summary = (
            "## Что у тебя лучше работает\n"
            "- Пока недостаточно данных.\n\n"
            "## Что чаще ломается\n"
            "- Пока недостаточно данных.\n\n"
            "## Частые причины провала\n"
            "- Пока недостаточно данных.\n\n"
            "## Как лучше строить шаги\n"
            "- Держать шаги маленькими и конкретными\n"
            "- После каждого шага отмечать результат\n"
            "- Не распыляться"
        )
        prompt_hints = (
            "Личная стратегия эффективности пользователя пока не накоплена. "
            "Опирайся на базовые правила: короткие, понятные, выполнимые шаги."
        )
        return {
            "summary_text": summary,
            "prompt_hints": prompt_hints,
        }

    mode_stats: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"success": 0, "partial": 0, "blocked": 0, "unclear": 0}
    )
    action_stats: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"success": 0, "partial": 0, "blocked": 0, "unclear": 0}
    )
    reason_stats: Dict[str, int] = defaultdict(int)

    for item in outcomes:
        mode = str(item.get("mode", "")).strip() or "general"
        action = str(item.get("action_text", "")).strip()
        status = str(item.get("review_status", "unclear")).strip().lower()
        reason = str(item.get("failure_reason", "")).strip()

        if status not in {"success", "partial", "blocked", "unclear"}:
            status = "unclear"

        mode_stats[mode][status] += 1

        if action:
            action_stats[action][status] += 1

        if reason:
            reason_stats[reason] += 1

    best_modes = sorted(
        mode_stats.items(),
        key=lambda x: (x[1]["success"], x[1]["partial"], -x[1]["blocked"]),
        reverse=True,
    )[:3]

    weak_modes = sorted(
        mode_stats.items(),
        key=lambda x: (x[1]["blocked"], -x[1]["success"], -x[1]["partial"]),
        reverse=True,
    )[:3]

    working_actions = []
    fragile_actions = []

    for action, stats in action_stats.items():
        if stats["success"] > 0:
            working_actions.append((action, stats))
        if stats["blocked"] > 0:
            fragile_actions.append((action, stats))

    working_actions.sort(
        key=lambda x: (x[1]["success"], x[1]["partial"], -x[1]["blocked"]),
        reverse=True,
    )
    fragile_actions.sort(
        key=lambda x: (x[1]["blocked"], -x[1]["success"], -x[1]["partial"]),
        reverse=True,
    )

    top_reasons = sorted(reason_stats.items(), key=lambda x: x[1], reverse=True)[:5]

    strategy_advice = [
        "Лучше предлагать короткие и конкретные шаги",
        "Не стоит повторять действия, которые уже часто блокировались",
    ]

    if top_reasons:
        reasons = [reason for reason, _ in top_reasons]
        if "не хватило времени" in reasons:
            strategy_advice.append("Чаще давать шаги, которые помещаются в короткое окно времени")
        if "не хватило сил" in reasons:
            strategy_advice.append("При низком ресурсе давать мягкие и щадящие действия")
        if "шаг был неясный" in reasons:
            strategy_advice.append("Формулировать следующий шаг максимально конкретно")
        if "это не то направление" in reasons:
            strategy_advice.append("Чаще проверять, совпадает ли шаг с реальной целью")
        if "отвлёкся" in reasons:
            strategy_advice.append("Снижать порог входа и давать действия, которые можно начать сразу")

    summary_parts: List[str] = ["## Что у тебя лучше работает"]
    if best_modes:
        for mode, stats in best_modes:
            summary_parts.append(f"- mode={mode} | {_fmt_stats(stats)}")
    else:
        summary_parts.append("- Пока недостаточно данных")

    summary_parts.append("\n## Что чаще ломается")
    if weak_modes:
        for mode, stats in weak_modes:
            summary_parts.append(f"- mode={mode} | {_fmt_stats(stats)}")
    else:
        summary_parts.append("- Пока недостаточно данных")

    summary_parts.append("\n## Частые причины провала")
    if top_reasons:
        for reason, count in top_reasons:
            summary_parts.append(f"- {reason} | count={count}")
    else:
        summary_parts.append("- Пока нет выраженных причин")

    summary_parts.append("\n## Как лучше строить шаги")
    for item in strategy_advice[:5]:
        summary_parts.append(f"- {item}")

    summary_text = "\n".join(summary_parts)

    prompt_lines = ["Личная стратегия эффективности пользователя:"]
    if best_modes:
        prompt_lines.append("Лучше срабатывают режимы:")
        for mode, stats in best_modes[:3]:
            prompt_lines.append(f"- {mode} | {_fmt_stats(stats)}")

    if working_actions:
        prompt_lines.append("Чаще срабатывали действия:")
        for action, stats in working_actions[:3]:
            prompt_lines.append(f"- {action} | {_fmt_stats(stats)}")

    if fragile_actions:
        prompt_lines.append("Не повторяй слишком похожие действия к этим:")
        for action, stats in fragile_actions[:3]:
            prompt_lines.append(f"- {action} | {_fmt_stats(stats)}")

    if top_reasons:
        prompt_lines.append("Учитывай частые причины провала:")
        for reason, count in top_reasons[:5]:
            prompt_lines.append(f"- {reason} | count={count}")

    for item in strategy_advice[:5]:
        prompt_lines.append(f"- advice: {item}")

    return {
        "summary_text": summary_text,
        "prompt_hints": "\n".join(prompt_lines),
    }


if __name__ == "__main__":
    print("strategy profile module ready")
