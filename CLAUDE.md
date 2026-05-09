# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the bot

```bash
source .venv/bin/activate
python bot.py

# Syntax check (same as CI)
python -m py_compile bot.py
```

## Environment

Required in `.env`:
```
TELEGRAM_BOT_TOKEN=...
OPENAI_API_KEY=...
```

Optional (shown with defaults):
```
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
ASSISTANT_DB_PATH=data/assistant.db
OBSIDIAN_ROOT=data/obsidian
USER_TIMEZONE=Asia/Tashkent
MAX_OUTPUT_TOKENS=260
MAX_DECISION_DEPTH=3
DAILY_MEMORY_LIMIT=5
DEFAULT_MORNING_HOUR=8
DEFAULT_MORNING_MINUTE=0
DEFAULT_EVENING_HOUR=21
DEFAULT_EVENING_MINUTE=0
DEBUG=true
```

All env vars are loaded and validated by `config.py`; import from there, never directly from `os.getenv`.

## Architecture

A single-user Telegram bot with two purposes: productivity advisor (suggests 3 next actions via OpenAI) and SRE learning platform (quiz, practice tasks, flashcards, incident scenarios).

`bot.py` is the monolith — all handlers, keyboards, and job scheduling live there. Everything else is a module imported by it.

**Core request flow:**
1. Text message → `handle_text` → `router.py:classify_request()` scores message against keyword lists → returns a `mode` (e.g. `low_time`, `learning`, `chaos`)
2. `adaptation.py:build_adaptation_hints()` reads recent outcomes for this mode → determines strategy (`simplify` / `advance` / `neutral`)
3. `brain.py:generate_options()` builds prompt from mode + protocol rules + session state + memory profile + adaptation hints → calls OpenAI → returns 3 JSON action options
4. Options shown as numbered inline buttons; user picks one
5. User reports result → `outcomes.py:log_outcome()` persists success/blocked/skip → feeds back into step 2 on the next request

**Adaptation feedback loop** (`outcomes.py` → `adaptation.py` → `brain.py`):
- Two consecutive `blocked` results in same mode → strategy `simplify_hard` (much easier step)
- One `blocked` → `simplify`
- Two consecutive `success` → `advance` (slightly harder)
- `adaptation.py:filter_options()` also deduplicates against recent actions using Jaccard similarity

**Voice messages:** `handle_voice` transcribes with `OPENAI_TRANSCRIBE_MODEL`, then feeds text through the same flow as text messages.

**State and persistence:**
- `state.py` — SQLite session state per `chat_id`: active mode/request/action, daily plan, weekly/monthly goals, proactive settings, Gilfoyle mode
- `memory.py` — Obsidian markdown under `OBSIDIAN_ROOT`: profile goals/constraints, daily logs, decisions, weekly summaries — fed into the AI prompt as long-term context
- `session_memory.py` — short-term notes in SQLite (`lesson`, `closing`, `plan`, `study` types); last 7 days injected into AI prompt
- `data/bot_persistence.pkl` — python-telegram-bot `PicklePersistence` for PTB-internal conversation state
- `data/assistant.db` — SQLite for all structured data

## Module reference

**Intelligence pipeline:**
- `router.py` — keyword/regex scoring → `mode`; run standalone to test classification (several other modules also support `python <module>.py` for quick smoke tests: `review.py`, `recovery.py`, `outcomes.py`, `protocols.py`, `strategy_profile.py`, `weekly_summary.py`)
- `protocols.py` — per-mode `Protocol` dataclass: allowed/forbidden actions, completion buttons, `max_depth`
- `adaptation.py` — `build_adaptation_hints()`, `filter_options()`, `complete_options()`
- `outcomes.py` — `log_outcome()`, `get_recent_outcomes()`, `build_outcome_hints()`
- `brain.py` — `generate_options()`, `SYSTEM_PROMPT`, `GILFOYLE_PROMPT`, `JSON_SCHEMA`; Gilfoyle mode is toggled globally per chat. Uses the **OpenAI Responses API** (`client.responses.create`), not Chat Completions — params are `instructions`/`input`, response is `.output_text`. Do not refactor to `chat.completions.create`. Three-tier fallback: structured JSON schema → plain text extraction → static `_fallback_by_mode()`

**Daily / weekly flow:**
- `priority_engine.py` — `build_daily_plan()`, `build_focus_hints()` using energy/time inputs
- `daily_cycle.py` — daily closing summary
- `morning_brief.py` — morning brief text + `IT_WORDS` list (source for flashcards)
- `weekly_summary.py` — `generate_weekly_summary()` via OpenAI
- `proactive.py` — message content builders only: `build_checkin()`, `build_evening_reminder()`, `assess_pulse()`, `build_midday_nudge()`, `build_streak_guard()`; job scheduling and `restore_proactive_jobs()` live in `bot.py`
- `domains.py` — 6 life domains: `assistant_project`, `income`, `learning`, `work`, `health`, `family`
- `strategy_profile.py` — strategic profile context injected into proactive messages

**Learning modules** — each has `init_*_db()` called in `main()`:
- `quiz.py` — 5-question multiple-choice; topics: `linux`, `networks`, `docker`, `git`, `bash`, `systemd`, `kubernetes`, `nginx`, `cicd`, `monitoring`
- `tasks.py` — hands-on CLI tasks with command + hint + verify question; same topics as quiz minus `kubernetes`
- `thinking.py` — SRE incident scenarios (slow server, service down, etc.); user submits a diagnosis plan, OpenAI evaluates it
- `flashcards.py` — spaced repetition over `IT_WORDS` from `morning_brief.py`; intervals `[1, 3, 7, 14]` days by streak level
- `study_tracker.py` — free-form study sessions; topics: `linux`, `networks`, `docker`, `git`, `ai`, `prompt`, `other` (different set from quiz/tasks)

**Gamification:**
- `xp.py` — XP per source type, 7-level SRE progression (Стажёр → Senior SRE)
- `achievements.py` — badges for milestones (streaks, XP thresholds, first completions per module)
- `stats.py` — aggregates all learning data into `/stats` and weekly report

**Post-action review:**
- `review.py` — `classify_result()` (keyword-based Russian text → `success`/`partial`/`blocked`/`unclear`), `build_review()` (generates summary, lesson, next direction, and `next_prompt` string). In `bot.py` the `next_prompt` is combined with `build_outcome_hints()` and passed as `user_text` directly into `generate_options()` to produce the next set of action buttons

**Skills progress:**
- `skills_path.py` — tracks weighted progress toward Junior SRE across 6 topics (linux, networks, docker, git, ai, prompt); `format_path()` / `format_path_short()` render progress bars; `get_path_stats()` returns ETA in months

**Recovery:**
- `recovery.py` — `should_ask_failure_reason()`, `get_failure_reason_buttons()`, `build_recovery()`; triggered when result indicates failure

## Key conventions

**Adding a new command:**
1. Write `async def my_command(update, context)` in `bot.py`
2. Add `app.add_handler(CommandHandler("mycommand", my_command))` in `main()`
3. If it needs storage, create `init_my_db()` and call it in `main()` alongside the others
4. Add a button to `build_main_menu_keyboard()` if it belongs in the menu

**DB schema changes:** Use `PRAGMA table_info` + `ALTER TABLE` pattern — see `state.py:_column_exists()`. Never drop and recreate tables; data is not versioned.

**Per-user key:** `chat_id` (Telegram integer) is the only user identifier across all tables — no separate users table.

**Timezones:** All date/time uses `USER_TIMEZONE` via `ZoneInfo`. Each module defines its own `_today()` / `today_str()` helper locally.

**Callback naming:** `act_N` — action choice, `res_N` — completion result, `fail_N` — failure reason, `cmd_*` — menu, `plan_*` — plan wizard, `quiz_*` / `task_*` / `flash_*` / `think_*` — learning module flows.
