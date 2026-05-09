from pathlib import Path
from datetime import datetime
from typing import Optional, List
from zoneinfo import ZoneInfo

from config import OBSIDIAN_ROOT, USER_TIMEZONE


ROOT = Path(OBSIDIAN_ROOT)
TZ = ZoneInfo(USER_TIMEZONE)


def ensure_dirs() -> None:
    (ROOT / "profile").mkdir(parents=True, exist_ok=True)
    (ROOT / "daily").mkdir(parents=True, exist_ok=True)
    (ROOT / "decisions").mkdir(parents=True, exist_ok=True)
    (ROOT / "summaries").mkdir(parents=True, exist_ok=True)
    (ROOT / "summaries" / "weekly").mkdir(parents=True, exist_ok=True)


def _today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def _now_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M")


def _week_key() -> str:
    now = datetime.now(TZ)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _month_key() -> str:
    return datetime.now(TZ).strftime("%Y-%m")


def _append_block(path: Path, block: str) -> None:
    ensure_dirs()
    with open(path, "a", encoding="utf-8") as f:
        f.write(block.rstrip() + "\n\n")


def read_profile() -> str:
    ensure_dirs()
    parts = []

    for rel in [
        "profile/goals.md",
        "profile/constraints.md",
        "profile/protocols.md",
        "profile/weekly_goal.md",
        "profile/monthly_focus.md",
    ]:
        path = ROOT / rel
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.append(f"# {path.stem}\n{text}")

    return "\n\n".join(parts).strip()


def append_daily_entry(text: str) -> None:
    ensure_dirs()
    path = ROOT / "daily" / f"{_today_str()}.md"

    block = f"""## {_now_str()}
{text.strip()}"""

    _append_block(path, block)


def append_decision_entry(text: str) -> None:
    ensure_dirs()
    path = ROOT / "decisions" / f"{_today_str()}.md"

    block = f"""## {_now_str()}
{text.strip()}"""

    _append_block(path, block)


def save_interaction(
    source: str,
    user_text: str,
    assistant_text: Optional[str] = None,
    selected_option: Optional[str] = None,
) -> None:
    ensure_dirs()
    path = ROOT / "daily" / f"{_today_str()}.md"

    lines = [
        f"## {_now_str()}",
        f"- source: {source}",
        f"- user: {user_text.strip()}",
    ]

    if assistant_text:
        lines.append(f"- assistant: {assistant_text.strip()}")

    if selected_option:
        lines.append(f"- selected: {selected_option.strip()}")

    _append_block(path, "\n".join(lines))


def save_structured_decision(
    user_text: str,
    selected_option: str,
    next_step_text: Optional[str] = None,
) -> None:
    ensure_dirs()
    path = ROOT / "decisions" / f"{_today_str()}.md"

    block = f"""## {_now_str()}
### Context
- request: {user_text.strip()}

### Decision
- selected: {selected_option.strip()}

### Follow-up
- next: {(next_step_text or '').strip()}
"""

    _append_block(path, block)


def save_daily_plan(plan: dict) -> None:
    ensure_dirs()
    path = ROOT / "daily" / f"{_today_str()}.md"

    priorities = "\n".join(f"- {item}" for item in plan.get("priorities", []))
    stop_signals = "\n".join(f"- {item}" for item in plan.get("stop_signals", []))

    block = f"""## {_now_str()}
### Daily Plan
- focus_domain: {plan.get("focus_domain_label", "")}
- energy: {plan.get("energy_label", "")}
- time_budget: {plan.get("time_budget_label", "")}

### Focus
{plan.get("focus_text", "").strip()}

### 3 Priorities
{priorities}

### Stop Signals
{stop_signals}
"""

    _append_block(path, block)


def save_daily_closing(text: str) -> None:
    ensure_dirs()
    path = ROOT / "daily" / f"{_today_str()}.md"

    block = f"""## {_now_str()}
### Daily Closing
{text.strip()}
"""

    _append_block(path, block)


def save_weekly_goal(domain_label: str, goal_text: str) -> None:
    ensure_dirs()
    path = ROOT / "profile" / "weekly_goal.md"
    content = (
        f"# Weekly Goal {_week_key()}\n\n"
        f"- domain: {domain_label}\n"
        f"- goal: {goal_text.strip()}\n"
    )
    path.write_text(content, encoding="utf-8")


def save_monthly_focus(domain_label: str, focus_text: str) -> None:
    ensure_dirs()
    path = ROOT / "profile" / "monthly_focus.md"
    content = (
        f"# Monthly Focus {_month_key()}\n\n"
        f"- domain: {domain_label}\n"
        f"- focus: {focus_text.strip()}\n"
    )
    path.write_text(content, encoding="utf-8")


def read_today_daily() -> str:
    ensure_dirs()
    path = ROOT / "daily" / f"{_today_str()}.md"

    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8").strip()


def read_last_daily_entries(limit: int = 5) -> str:
    ensure_dirs()
    path = ROOT / "daily" / f"{_today_str()}.md"

    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return ""

    chunks = [chunk.strip() for chunk in text.split("\n## ") if chunk.strip()]
    if not chunks:
        return text

    selected = chunks[-limit:]
    rebuilt = []

    for i, chunk in enumerate(selected):
        if i == 0 and chunk.startswith("## "):
            rebuilt.append(chunk)
        else:
            rebuilt.append("## " + chunk.lstrip("# ").strip())

    return "\n\n".join(rebuilt).strip()


def _list_recent_files(folder_name: str, days: int = 7) -> List[Path]:
    ensure_dirs()
    folder = ROOT / folder_name
    files = sorted(folder.glob("*.md"))
    return files[-days:]


def _read_recent_files(
    folder_name: str,
    days: int = 7,
    max_chars_per_file: int = 4000,
) -> str:
    files = _list_recent_files(folder_name=folder_name, days=days)

    blocks = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue

        if not text:
            continue

        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file].rstrip() + "\n[обрезано]"

        blocks.append(f"# File: {path.name}\n{text}")

    return "\n\n---\n\n".join(blocks).strip()


def list_recent_daily_files(days: int = 7) -> List[Path]:
    return _list_recent_files(folder_name="daily", days=days)


def list_recent_decision_files(days: int = 7) -> List[Path]:
    return _list_recent_files(folder_name="decisions", days=days)


def read_recent_daily_notes(days: int = 7, max_chars_per_file: int = 4000) -> str:
    return _read_recent_files(
        folder_name="daily",
        days=days,
        max_chars_per_file=max_chars_per_file,
    )


def read_recent_decision_notes(days: int = 7, max_chars_per_file: int = 4000) -> str:
    return _read_recent_files(
        folder_name="decisions",
        days=days,
        max_chars_per_file=max_chars_per_file,
    )


def save_weekly_summary(summary_text: str) -> Path:
    ensure_dirs()
    now = datetime.now(TZ)
    iso_year, iso_week, _ = now.isocalendar()
    path = ROOT / "summaries" / "weekly" / f"{iso_year}-W{iso_week:02d}.md"

    header = f"# Weekly Summary {iso_year}-W{iso_week:02d}\n\n"
    path.write_text(header + summary_text.strip() + "\n", encoding="utf-8")
    return path
