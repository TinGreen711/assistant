from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from config import OBSIDIAN_ROOT, USER_TIMEZONE


ROOT = Path(OBSIDIAN_ROOT)
CAPTURES_DIR = ROOT / "captures"
TZ = ZoneInfo(USER_TIMEZONE)

CAPTURE_TYPES: dict[str, tuple[str, str]] = {
    "idea": ("💡", "Идея"),
    "learned": ("📚", "Изучено"),
    "thought": ("🧠", "Мысль"),
    "quote": ("💬", "Цитата"),
}


def ensure_captures_dir() -> None:
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> datetime:
    return datetime.now(TZ)


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _timestamp_str() -> str:
    return _now().strftime("%Y-%m-%d %H:%M")


def _filename(capture_type: str) -> str:
    return _now().strftime("%Y-%m-%d-%H%M") + f"-{capture_type}.md"


def _update_index(stem: str, capture_type: str, preview: str) -> None:
    index_path = CAPTURES_DIR / "index.md"
    icon, label = CAPTURE_TYPES.get(capture_type, ("📝", "Заметка"))
    line = f"- [[{stem}]] — {icon} {label}: {preview[:70]}\n"
    if not index_path.exists():
        index_path.write_text("# Captures\n\n", encoding="utf-8")
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(line)


def save_capture(content: str, capture_type: str = "thought") -> Path:
    ensure_captures_dir()
    icon, label = CAPTURE_TYPES.get(capture_type, ("📝", "Заметка"))
    filename = _filename(capture_type)
    path = CAPTURES_DIR / filename
    today = _today_str()
    ts = _timestamp_str()
    tags_yaml = f"captures, {capture_type}"

    note = (
        f"---\n"
        f"date: {today}\n"
        f"time: {ts}\n"
        f"type: {capture_type}\n"
        f"tags: [{tags_yaml}]\n"
        f"---\n\n"
        f"# {icon} {label}\n\n"
        f"{content.strip()}\n\n"
        f"---\n"
        f"*{ts}*  \n"
        f"[[{today}]] | [[index]]\n"
    )
    path.write_text(note, encoding="utf-8")

    preview = content.strip().replace("\n", " ")
    _update_index(path.stem, capture_type, preview)
    return path


def list_recent_captures(days: int = 7) -> list[Path]:
    ensure_captures_dir()
    since = (_now().date() - timedelta(days=days))
    result = []
    for f in sorted(CAPTURES_DIR.glob("????-??-??-??-*.md")):
        try:
            file_date = datetime.strptime(f.stem[:10], "%Y-%m-%d").date()
            if file_date >= since:
                result.append(f)
        except ValueError:
            continue
    return result


def read_recent_captures(days: int = 7, max_chars: int = 2000) -> str:
    files = list_recent_captures(days=days)
    if not files:
        return ""
    blocks = []
    for path in files[-10:]:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        # strip frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                text = parts[2].strip()
        blocks.append(text[:300])
    combined = "\n\n---\n\n".join(blocks)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n[обрезано]"
    return combined
