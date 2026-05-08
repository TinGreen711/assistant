import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


def _get_str(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


TELEGRAM_BOT_TOKEN = _get_str("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = _get_str("OPENAI_API_KEY")

OPENAI_CHAT_MODEL = _get_str("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
OPENAI_TRANSCRIBE_MODEL = _get_str("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")

OBSIDIAN_ROOT = _get_str("OBSIDIAN_ROOT", str(BASE_DIR / "data" / "obsidian"))
ASSISTANT_DB_PATH = _get_str("ASSISTANT_DB_PATH", str(BASE_DIR / "data" / "assistant.db"))

MAX_OUTPUT_TOKENS = _get_int("MAX_OUTPUT_TOKENS", 260)
DAILY_MEMORY_LIMIT = _get_int("DAILY_MEMORY_LIMIT", 5)
MAX_DECISION_DEPTH = _get_int("MAX_DECISION_DEPTH", 3)

USER_TIMEZONE = _get_str("USER_TIMEZONE", "Asia/Tashkent")
DEFAULT_MORNING_HOUR = _get_int("DEFAULT_MORNING_HOUR", 8)
DEFAULT_MORNING_MINUTE = _get_int("DEFAULT_MORNING_MINUTE", 0)
DEFAULT_EVENING_HOUR = _get_int("DEFAULT_EVENING_HOUR", 21)
DEFAULT_EVENING_MINUTE = _get_int("DEFAULT_EVENING_MINUTE", 0)

DEBUG = _get_bool("DEBUG", True)


def validate_config() -> None:
    missing = []

    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")

    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Не заданы переменные окружения: {joined}")
