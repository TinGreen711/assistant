# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the bot

```bash
# Activate the virtual environment first
source .venv/bin/activate

# Run the bot
python bot.py

# Check Python syntax (same as CI)
python -m py_compile bot.py
```

## Environment

Copy `.env` values — required variables:

```
TELEGRAM_BOT_TOKEN=...
OPENAI_API_KEY=...
```

Optional overrides (with defaults):

```
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
ASSISTANT_DB_PATH=data/assistant.db
OBSIDIAN_ROOT=data/obsidian
USER_TIMEZONE=Asia/Tashkent
MAX_OUTPUT_TOKENS=260
DAILY_MEMORY_LIMIT=5
```

## Architecture

This is a single-user Telegram productivity bot. `bot.py` is the monolith — it owns all handler registration, job scheduling, and keyboard construction. Everything else is a module imported by `bot.py`.

**Request flow:**
1. User sends a message → `handle_text` in `bot.py`
2. `router.py` → `classify_request()` scores the message against keyword lists and returns a `mode` (e.g. `low_time`, `learning`, `chaos`)
3. `brain.py` → `generate_options()` builds an OpenAI prompt from the mode, session state, memory profile, and adaptation hints, then returns 3 JSON action options
4. Options are displayed as numbered inline keyboard buttons; the user picks one
5. The choice triggers a `res_N` callback → bot enters execution tracking, prompts for completion

**State and persistence:**
- `state.py` — SQLite-backed session state per `chat_id` (active mode, focus, daily plan, weekly/monthly goals, proactive settings, Gilfoyle mode)
- `memory.py` — Obsidian markdown files under `OBSIDIAN_ROOT` (profile, daily logs, decisions, summaries). Used to build long-term context for the AI prompt.
- `data/bot_persistence.pkl` — python-telegram-bot `PicklePersistence` for conversation state across restarts
- `data/assistant.db` — SQLite for all structured data (study sessions, quiz results, task completions, XP, achievements, flash progress)

**Learning modules** (each has `init_*_db()`, content data, and formatting helpers):
- `quiz.py` — 5-question multiple-choice quizzes per topic; results tracked in `quiz_results`
- `tasks.py` — hands-on CLI practice tasks with commands and hints; tracked in `task_completions`
- `thinking.py` — SRE incident scenario walkthroughs with AI-evaluated user plans; tracked in `thinking_sessions`
- `flashcards.py` — spaced-repetition IT vocabulary cards; intervals `[1, 3, 7, 14]` days by streak; tracked in `flash_progress`
- `study_tracker.py` — logs free-form study sessions by topic; drives streak counting

**Gamification:**
- `xp.py` — XP points per action type, 7-level SRE progression (Стажёр → Senior SRE)
- `achievements.py` — unlock badges for milestones (streaks, XP thresholds, first completions)
- `stats.py` — aggregates all learning data into `/stats` and weekly report views

**Proactive features:**
- `proactive.py` — generates morning check-in, midday nudge, evening reminder, pulse assessment, streak guard messages
- `daily_cycle.py` — daily closing summary generation
- `morning_brief.py` — morning brief builder + `IT_WORDS` vocabulary list used by flashcards
- Proactive jobs are registered per `chat_id` via `app.job_queue` and restored on restart via `restore_proactive_jobs()`

**AI persona:**
- Default: `SYSTEM_PROMPT` in `brain.py` — practical productivity assistant, 3 options, JSON output
- Gilfoyle mode: `GILFOYLE_PROMPT` — no motivation, facts only, same 3-option JSON structure
- Both return structured JSON validated against `JSON_SCHEMA`; `brain.py` calls OpenAI with `response_format={"type": "json_object"}`

**Topics covered** (shared across quiz/tasks/study tracker):
`linux`, `networks`, `docker`, `git`, `bash`, `systemd`, `nginx`, `monitoring`, `cicd`, `kubernetes`

## Key conventions

- All DB tables are created lazily via `init_*_db()` functions called in `main()`; use `ALTER TABLE` / `PRAGMA table_info` pattern (see `state.py:_column_exists`) when adding columns to existing tables
- `chat_id` (Telegram integer) is the primary per-user key across all tables — there is no separate user table
- All timestamps use `USER_TIMEZONE` via `ZoneInfo`; `today_str()` helpers are duplicated per module intentionally
- Inline keyboard callbacks follow naming conventions: `act_N` (action choice), `res_N` (result/completion), `fail_N` (failure reason), `cmd_*` (menu commands), `plan_*` (plan flow), `quiz_*`, `task_*`, `flash_*`, `think_*`
- `bot.py` contains all `async def *_command` and `handle_*` functions; business logic lives in the modules
