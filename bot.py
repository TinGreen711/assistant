from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
    JobQueue,
)

from openai import OpenAI

from config import (
    TELEGRAM_BOT_TOKEN,
    OPENAI_API_KEY,
    OPENAI_TRANSCRIBE_MODEL,
    DAILY_MEMORY_LIMIT,
    MAX_DECISION_DEPTH,
    DEBUG,
    USER_TIMEZONE,
    ASSISTANT_DB_PATH,
    validate_config,
)
from brain import generate_options
from memory import (
    ensure_dirs,
    save_interaction,
    save_structured_decision,
    read_last_daily_entries,
    append_daily_entry,
    save_daily_plan,
    save_daily_closing,
    read_today_daily,
    save_weekly_goal,
    save_monthly_focus,
)
from protocols import get_completion_buttons, get_max_depth
from review import build_review
from weekly_summary import generate_weekly_summary
from state import (
    init_state_db,
    set_session_state,
    clear_session_state,
    set_daily_focus,
    mark_daily_closed,
    get_session_state,
    update_session_state,
    set_weekly_goal,
    set_monthly_focus,
    build_long_horizon_context,
    set_proactive_settings,
    get_proactive_settings,
    list_proactive_enabled_sessions,
    set_gilfoyle_mode,
    get_gilfoyle_mode,
)
from outcomes import (
    init_outcomes_db,
    log_outcome,
    build_outcome_hints,
)
from adaptation import (
    build_adaptation_hints,
    filter_options,
    complete_options,
)
from router import classify_request
from recovery import (
    should_ask_failure_reason,
    get_failure_reason_buttons,
    build_recovery,
)
from domains import classify_domain, assess_domain_alignment, DOMAINS
from priority_engine import build_daily_plan, build_focus_hints
from daily_cycle import generate_daily_closing
from strategy_profile import build_strategy_profile
from proactive import build_checkin, build_evening_reminder, assess_pulse, build_midday_nudge, build_streak_guard
from session_memory import init_session_memory_db, save_memory_note, get_recent_memory
from study_tracker import (
    init_study_db,
    log_session,
    get_streak,
    format_study_stats,
    TOPICS,
)
from skills_path import format_path, format_path_short


client = OpenAI(api_key=OPENAI_API_KEY)
TZ = ZoneInfo(USER_TIMEZONE)


def log(*args: object) -> None:
    if DEBUG:
        print(*args)


def today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def build_action_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=str(i + 1), callback_data=f"act_{i}")
        for i in range(len(options))
    ]
    return InlineKeyboardMarkup([buttons])


def build_result_keyboard(buttons: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=button, callback_data=f"res_{i}")]
        for i, button in enumerate(buttons)
    ]
    return InlineKeyboardMarkup(rows)


def build_failure_reason_keyboard(buttons: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=button, callback_data=f"fail_{i}")]
        for i, button in enumerate(buttons)
    ]
    return InlineKeyboardMarkup(rows)


def build_main_menu_keyboard(gilfoyle: bool = False) -> InlineKeyboardMarkup:
    gilfoyle_label = "👤 Обычный режим" if gilfoyle else "🤖 Режим Гилфойла"
    gilfoyle_cmd = "cmd_gilfoyle_off" if gilfoyle else "cmd_gilfoyle_on"
    rows = [
        [InlineKeyboardButton(text="🗓 План дня", callback_data="cmd_plan")],
        [InlineKeyboardButton(text="☀️ Check-in", callback_data="cmd_checkin")],
        [InlineKeyboardButton(text="📡 Pulse", callback_data="cmd_pulse")],
        [InlineKeyboardButton(text="🌙 Закрыть день", callback_data="cmd_close")],
        [InlineKeyboardButton(text="🎯 Цель недели", callback_data="cmd_weekgoal"),
         InlineKeyboardButton(text="🧭 Вектор месяца", callback_data="cmd_monthfocus")],
        [InlineKeyboardButton(text="📚 Обучение /study", callback_data="cmd_study"),
         InlineKeyboardButton(text="🗺 Путь /path", callback_data="cmd_path")],
        [InlineKeyboardButton(text="🧠 Strategy", callback_data="cmd_strategy"),
         InlineKeyboardButton(text="📊 Weekly", callback_data="cmd_weekly")],
        [InlineKeyboardButton(text="🔔 Proactive on", callback_data="cmd_proactive_on"),
         InlineKeyboardButton(text="🔕 Proactive off", callback_data="cmd_proactive_off")],
        [InlineKeyboardButton(text=gilfoyle_label, callback_data=gilfoyle_cmd)],
        [InlineKeyboardButton(text="♻️ Сбросить сессию", callback_data="cmd_reset")],
    ]
    return InlineKeyboardMarkup(rows)


def build_plan_energy_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Низкий ресурс", callback_data="plan_energy_low")],
        [InlineKeyboardButton(text="Нормальный ресурс", callback_data="plan_energy_normal")],
        [InlineKeyboardButton(text="Высокий ресурс", callback_data="plan_energy_high")],
    ]
    return InlineKeyboardMarkup(rows)


def build_plan_time_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="15–30 минут", callback_data="plan_time_short")],
        [InlineKeyboardButton(text="30–90 минут", callback_data="plan_time_medium")],
        [InlineKeyboardButton(text="90+ минут", callback_data="plan_time_long")],
    ]
    return InlineKeyboardMarkup(rows)


def build_study_topic_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"study_topic_{key}")]
        for key, label in TOPICS.items()
    ]
    return InlineKeyboardMarkup(rows)


def build_domain_keyboard(prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Проект ассистента", callback_data=f"{prefix}_assistant_project")],
        [InlineKeyboardButton(text="Доход", callback_data=f"{prefix}_income")],
        [InlineKeyboardButton(text="Обучение", callback_data=f"{prefix}_learning")],
        [InlineKeyboardButton(text="Работа", callback_data=f"{prefix}_work")],
        [InlineKeyboardButton(text="Здоровье", callback_data=f"{prefix}_health")],
        [InlineKeyboardButton(text="Семья / быт", callback_data=f"{prefix}_family")],
        [InlineKeyboardButton(text="Организация", callback_data=f"{prefix}_admin")],
    ]
    return InlineKeyboardMarkup(rows)


def get_message_store(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return context.user_data.setdefault("message_store", {})


def get_selection_history(context: ContextTypes.DEFAULT_TYPE) -> list[str]:
    return context.user_data.setdefault("selected_history", [])


def get_plan_draft(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return context.user_data.setdefault("plan_draft", {})


def get_goal_draft(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return context.user_data.setdefault("goal_draft", {})


def format_daily_plan(plan: dict, long_horizon_text: str = "") -> str:
    priorities = "\n".join(f"- {item}" for item in plan.get("priorities", []))
    stops = "\n".join(f"- {item}" for item in plan.get("stop_signals", []))

    text = (
        f"Главный фокус дня\n"
        f"{plan.get('focus_text', '')}\n\n"
        f"Область: {plan.get('focus_domain_label', '')}\n"
        f"Ресурс: {plan.get('energy_label', '')}\n"
        f"Окно времени: {plan.get('time_budget_label', '')}\n\n"
        f"3 приоритета\n{priorities}\n\n"
        f"Стоп-сигналы\n{stops}"
    )

    if long_horizon_text.strip():
        text += f"\n\nСвязь с неделей и месяцем\n{long_horizon_text.strip()}"

    return text


def remove_jobs_for_chat(job_queue: JobQueue | None, chat_id: int) -> None:
    if not job_queue:
        return

    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"midday_{chat_id}", f"streak_{chat_id}"]:
        jobs = job_queue.get_jobs_by_name(name)
        for job in jobs:
            job.schedule_removal()


def schedule_jobs_for_chat(job_queue: JobQueue | None, chat_id: int) -> None:
    if not job_queue:
        return

    settings = get_proactive_settings(chat_id)
    remove_jobs_for_chat(job_queue, chat_id)

    if not settings["enabled"]:
        return

    morning_t = time(
        hour=settings["morning_hour"],
        minute=settings["morning_minute"],
        tzinfo=TZ,
    )
    evening_t = time(
        hour=settings["evening_hour"],
        minute=settings["evening_minute"],
        tzinfo=TZ,
    )

    job_queue.run_daily(
        morning_checkin_job,
        time=morning_t,
        chat_id=chat_id,
        name=f"morning_{chat_id}",
    )
    job_queue.run_daily(
        evening_reminder_job,
        time=evening_t,
        chat_id=chat_id,
        name=f"evening_{chat_id}",
    )
    job_queue.run_daily(
        midday_nudge_job,
        time=time(hour=14, minute=0, tzinfo=TZ),
        chat_id=chat_id,
        name=f"midday_{chat_id}",
    )
    job_queue.run_daily(
        streak_guard_job,
        time=time(hour=18, minute=20, tzinfo=TZ),
        chat_id=chat_id,
        name=f"streak_{chat_id}",
    )


def restore_proactive_jobs(job_queue: JobQueue | None) -> None:
    if not job_queue:
        return

    rows = list_proactive_enabled_sessions()
    for row in rows:
        chat_id = int(row["chat_id"])
        schedule_jobs_for_chat(job_queue, chat_id)


async def morning_checkin_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    payload = build_checkin(chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=payload["text"],
        reply_markup=build_main_menu_keyboard(),
    )


async def evening_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    payload = build_evening_reminder(chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=payload["text"],
        reply_markup=build_main_menu_keyboard(),
    )


async def midday_nudge_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    payload = build_midday_nudge(chat_id)
    if payload is None:
        return
    await context.bot.send_message(
        chat_id=chat_id,
        text=payload["text"],
        reply_markup=build_main_menu_keyboard(),
    )


async def streak_guard_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    payload = build_streak_guard(chat_id)
    if payload is None:
        return
    await context.bot.send_message(
        chat_id=chat_id,
        text=payload["text"],
        reply_markup=build_main_menu_keyboard(),
    )


async def transcribe_voice(file_path: str) -> str:
    with open(file_path, "rb") as audio:
        transcript = client.audio.transcriptions.create(
            model=OPENAI_TRANSCRIBE_MODEL,
            file=audio,
        )
    return (transcript.text or "").strip()


async def send_main_menu(message_target, chat_id: int | None = None) -> None:
    gf = get_gilfoyle_mode(chat_id) if chat_id else False
    await message_target.reply_text(
        "Главное меню:",
        reply_markup=build_main_menu_keyboard(gilfoyle=gf),
    )


async def run_strategy_profile(message_target, chat_id: int) -> None:
    await message_target.chat.send_action(ChatAction.TYPING)

    profile = build_strategy_profile(chat_id=chat_id, limit=80)
    text = profile["summary_text"]

    append_daily_entry("### Strategy profile viewed")
    await message_target.reply_text(text)


async def run_checkin(message_target, chat_id: int) -> None:
    payload = build_checkin(chat_id)
    append_daily_entry("### Check-in viewed")
    await message_target.reply_text(payload["text"])


async def run_pulse(message_target, chat_id: int) -> None:
    payload = assess_pulse(chat_id)
    append_daily_entry(f"### Pulse viewed\n- trigger: {payload['trigger']}")
    await message_target.reply_text(payload["text"])


async def run_weekly_summary(message_target, chat_id: int) -> None:
    await message_target.chat.send_action(ChatAction.TYPING)

    horizon = build_long_horizon_context(chat_id)
    strategy = build_strategy_profile(chat_id=chat_id, limit=80)

    result = generate_weekly_summary(
        days=7,
        long_horizon_text=horizon["summary_text"],
        strategy_text=strategy["summary_text"],
    )
    text = result["text"]
    saved_path = result["saved_path"]

    append_daily_entry(
        f"### Weekly summary generated\n"
        f"- saved_path: {saved_path}\n"
        f"- source_days: {result['source_days']}"
    )

    await message_target.reply_text(
        f"{text}\n\nСохранено в:\n{saved_path}"
    )


async def start_daily_plan(message_target, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["plan_draft"] = {}
    await message_target.reply_text(
        "Выбери текущий уровень ресурса:",
        reply_markup=build_plan_energy_keyboard(),
    )


async def start_weekly_goal_flow(message_target, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["goal_draft"] = {"kind": "weekly"}
    await message_target.reply_text(
        "Для какой области задаём цель недели?",
        reply_markup=build_domain_keyboard("weekgoal_domain"),
    )


async def start_monthly_focus_flow(message_target, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["goal_draft"] = {"kind": "monthly"}
    await message_target.reply_text(
        "Для какой области задаём месячный вектор?",
        reply_markup=build_domain_keyboard("monthfocus_domain"),
    )


async def run_daily_closing(message_target, chat_id: int) -> None:
    state = get_session_state(chat_id)

    if not state:
        await message_target.reply_text("Похоже, план дня ещё не был задан. Сначала сделай план дня.")
        return

    if state.get("current_day") != today_str() or not state.get("daily_plan_done"):
        await message_target.reply_text("На сегодня ещё нет активного плана дня. Сначала сделай план дня.")
        return

    focus_domain = state.get("daily_focus_domain", "")
    focus_text = state.get("daily_focus_text", "")
    daily_energy = state.get("daily_energy", "")
    daily_time_budget = state.get("daily_time_budget", "")

    today_notes = read_today_daily()
    outcome_hints = build_outcome_hints(chat_id=chat_id, mode=focus_domain, limit=20)
    horizon = build_long_horizon_context(chat_id)

    closing_text = generate_daily_closing(
        focus_domain=focus_domain,
        focus_text=focus_text,
        energy_label=daily_energy,
        time_budget_label=daily_time_budget,
        today_notes=today_notes,
        outcome_hints=outcome_hints,
        long_horizon_text=horizon["summary_text"],
    )

    save_daily_closing(closing_text)
    mark_daily_closed(chat_id, closed=True)
    save_memory_note(chat_id=chat_id, note_type="closing", content=closing_text)

    append_daily_entry(
        f"### Daily focus status\n"
        f"- current_day: {today_str()}\n"
        f"- focus_domain: {focus_domain}\n"
        f"- focus_text: {focus_text}\n"
        f"- daily_closed: true"
    )

    await message_target.reply_text(closing_text)


async def send_action_options(
    message_target,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    source: str,
    depth: int = 0,
    original_request: str | None = None,
) -> None:
    original_request = original_request or user_text

    log("➡️ Обрабатываем:", user_text)

    await message_target.chat.send_action(ChatAction.TYPING)

    route = classify_request(original_request)
    pre_mode = route["mode"]

    adaptation = build_adaptation_hints(
        chat_id=message_target.chat.id,
        mode=pre_mode,
        history=get_selection_history(context),
        limit=8,
    )

    state = get_session_state(message_target.chat.id)
    request_domain_info = classify_domain(original_request)
    request_domain = request_domain_info["domain"]

    focus_hints = ""
    focus_notice_parts = []

    if state and state.get("current_day") == today_str() and state.get("daily_plan_done"):
        active_focus_domain = str(state.get("daily_focus_domain", "")).strip()
        active_focus_text = str(state.get("daily_focus_text", "")).strip()

        alignment = assess_domain_alignment(active_focus_domain, request_domain)
        focus_hints = build_focus_hints(
            active_focus_domain=active_focus_domain,
            active_focus_text=active_focus_text,
            request_domain=request_domain,
            relation=alignment["relation"],
        )

        if alignment["relation"] == "off_focus":
            focus_notice_parts.append(
                f"⚠️ Это похоже не на главный фокус дня.\nФокус дня: {active_focus_text}"
            )

    horizon = build_long_horizon_context(message_target.chat.id)
    strategy = build_strategy_profile(chat_id=message_target.chat.id, limit=80)
    pulse = assess_pulse(message_target.chat.id)

    if horizon["weekly_active"]:
        week_alignment = assess_domain_alignment(horizon["weekly_domain"], request_domain)
        if week_alignment["relation"] == "off_focus":
            focus_notice_parts.append(
                f"⚠️ Это уводит в сторону от цели недели.\nЦель недели: {horizon['weekly_text']}"
            )

    if horizon["monthly_active"]:
        month_alignment = assess_domain_alignment(horizon["monthly_domain"], request_domain)
        if month_alignment["relation"] == "off_focus":
            focus_notice_parts.append(
                f"⚠️ Это уводит в сторону от месячного вектора.\nВектор месяца: {horizon['monthly_text']}"
            )

    if pulse["trigger"] in {"recovery", "advance", "refocus_week", "setup_day"}:
        focus_notice_parts.append(pulse["text"])

    combined_hints = adaptation["prompt_hints"]
    if focus_hints:
        combined_hints += "\n\n" + focus_hints
    if horizon["prompt_hints"]:
        combined_hints += "\n\n" + horizon["prompt_hints"]
    if strategy["prompt_hints"]:
        combined_hints += "\n\n" + strategy["prompt_hints"]
    if pulse["prompt_hints"]:
        combined_hints += "\n\n" + pulse["prompt_hints"]

    recent_memory = get_recent_memory(message_target.chat.id, days=7)
    if recent_memory:
        combined_hints += "\n\nПамять из прошлых сессий:\n" + recent_memory

    data = generate_options(
        user_text,
        extra_hints=combined_hints,
        gilfoyle_mode=get_gilfoyle_mode(message_target.chat.id),
    )
    mode = str(data.get("mode", pre_mode)).strip() or pre_mode
    text = (data.get("text") or "Выбери действие:").strip()
    options = data.get("options") or []

    if not isinstance(options, list):
        options = []

    options = [str(x).strip() for x in options if str(x).strip()]

    options = filter_options(
        options=options,
        avoid_actions=adaptation["avoid_actions"],
        history=get_selection_history(context),
    )

    options = complete_options(
        mode=mode,
        strategy=adaptation["strategy"],
        current_options=options,
        avoid_actions=adaptation["avoid_actions"],
    )

    options = options[:3]

    if len(options) < 3:
        await message_target.reply_text("❌ Не удалось построить варианты. Попробуй сказать иначе.")
        return

    notice = ""
    if focus_notice_parts:
        notice = "\n\n".join(focus_notice_parts) + "\n\n"

    numbered = "\n".join(f"{i + 1}. {opt}" for i, opt in enumerate(options))
    keyboard = build_action_keyboard(options)
    sent = await message_target.reply_text(
        notice + text + "\n\n" + numbered,
        reply_markup=keyboard,
    )

    store = get_message_store(context)
    store[str(sent.message_id)] = {
        "stage": "choose_action",
        "source": source,
        "mode": mode,
        "original_request": original_request,
        "options": options,
        "depth": depth,
    }

    chat_id = message_target.chat.id
    set_session_state(
        chat_id=chat_id,
        active_mode=mode,
        active_request=original_request,
        active_action="",
        active_stage="choose_action",
        depth=depth,
        last_result="",
    )

    log("ACTION MESSAGE_ID:", sent.message_id)
    log("MODE:", mode)
    log("DEPTH:", depth)
    log("ADAPT_STRATEGY:", adaptation["strategy"])
    log("OPTIONS:", options)

    save_interaction(
        source=source,
        user_text=original_request,
        assistant_text=f"{text} | options: {' ; '.join(options)}",
    )

    append_daily_entry(
        f"### Adaptation\n"
        f"- mode: {mode}\n"
        f"- request_domain: {DOMAINS.get(request_domain, 'Общее')}\n"
        f"- strategy: {adaptation['strategy']}\n"
        f"- pulse: {pulse['trigger']}\n"
        f"- avoid: {' ; '.join(adaptation['avoid_actions']) if adaptation['avoid_actions'] else 'none'}"
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    clear_session_state(update.effective_chat.id)

    await update.message.reply_text(
        "Я готов.\n\n"
        "Пиши текстом или отправляй голосовое.\n"
        "Сначала я предложу 3 действия.\n"
        "После выбора попрошу отметить результат."
    )
    await send_main_menu(update.message, update.effective_chat.id)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    clear_session_state(update.effective_chat.id)

    if update.message:
        await update.message.reply_text("Сессия сброшена. Начинаем заново.")
        await send_main_menu(update.message, update.effective_chat.id)


async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await run_weekly_summary(update.message, update.effective_chat.id)


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await start_daily_plan(update.message, context)


async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await run_daily_closing(update.message, update.effective_chat.id)


async def weekgoal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await start_weekly_goal_flow(update.message, context)


async def monthfocus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await start_monthly_focus_flow(update.message, context)


async def strategy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await run_strategy_profile(update.message, update.effective_chat.id)


async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await run_checkin(update.message, update.effective_chat.id)


async def pulse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await run_pulse(update.message, update.effective_chat.id)


async def proactive_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.effective_chat.id
    set_proactive_settings(chat_id, enabled=True)
    schedule_jobs_for_chat(context.application.job_queue, chat_id)

    append_daily_entry("### Proactive enabled")
    await update.message.reply_text(
        f"Проактивный режим включён.\n"
        f"Утренний check-in и вечернее напоминание будут идти по часовому поясу {USER_TIMEZONE}."
    )


async def proactive_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.effective_chat.id
    set_proactive_settings(chat_id, enabled=False)
    remove_jobs_for_chat(context.application.job_queue, chat_id)

    append_daily_entry("### Proactive disabled")
    await update.message.reply_text("Проактивный режим выключен.")


async def study_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = format_study_stats(update.effective_chat.id)
    await update.message.reply_text(text)


async def path_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    gf = get_gilfoyle_mode(update.effective_chat.id)
    text = format_path(update.effective_chat.id, gilfoyle=gf)
    await update.message.reply_text(text)


async def gilfoyle_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id
    set_gilfoyle_mode(chat_id, True)
    await update.message.reply_text(
        "🤖 Режим Гилфойла включён.\nНикакой мотивации. Только факты."
    )
    await send_main_menu(update.message, chat_id)


async def gilfoyle_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id
    set_gilfoyle_mode(chat_id, False)
    await update.message.reply_text("👤 Обычный режим включён.")
    await send_main_menu(update.message, chat_id)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await send_main_menu(update.message, update.effective_chat.id)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    chat_id = update.effective_chat.id
    state = get_session_state(chat_id)

    if state:
        active_stage = str(state.get("active_stage", "")).strip()

        if active_stage == "await_weekly_goal_text":
            draft = get_goal_draft(context)
            domain = draft.get("domain", "general")
            set_weekly_goal(chat_id, domain, user_text)
            save_weekly_goal(DOMAINS.get(domain, "Общее"), user_text)

            update_session_state(chat_id, active_stage="")
            context.user_data["goal_draft"] = {}

            append_daily_entry(
                f"### Weekly Goal Set\n"
                f"- domain: {DOMAINS.get(domain, 'Общее')}\n"
                f"- text: {user_text}"
            )

            await update.message.reply_text(
                f"Цель недели зафиксирована.\n\n"
                f"Область: {DOMAINS.get(domain, 'Общее')}\n"
                f"Цель: {user_text}"
            )
            await send_main_menu(update.message, update.effective_chat.id)
            return

        if active_stage == "await_monthly_focus_text":
            draft = get_goal_draft(context)
            domain = draft.get("domain", "general")
            set_monthly_focus(chat_id, domain, user_text)
            save_monthly_focus(DOMAINS.get(domain, "Общее"), user_text)

            update_session_state(chat_id, active_stage="")
            context.user_data["goal_draft"] = {}

            append_daily_entry(
                f"### Monthly Focus Set\n"
                f"- domain: {DOMAINS.get(domain, 'Общее')}\n"
                f"- text: {user_text}"
            )

            await update.message.reply_text(
                f"Месячный вектор зафиксирован.\n\n"
                f"Область: {DOMAINS.get(domain, 'Общее')}\n"
                f"Вектор: {user_text}"
            )
            await send_main_menu(update.message, update.effective_chat.id)
            return

    await send_action_options(
        message_target=update.message,
        context=context,
        user_text=user_text,
        source="text",
        depth=0,
        original_request=user_text,
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.voice:
        return

    voice = update.message.voice
    temp_path = Path(f"/tmp/{voice.file_id}.ogg")

    log("🎤 Получено голосовое:", voice.file_id)

    try:
        await update.message.chat.send_action(ChatAction.TYPING)

        tg_file = await context.bot.get_file(voice.file_id)
        await tg_file.download_to_drive(str(temp_path))

        text = await transcribe_voice(str(temp_path))
        log("🎤 Распознано:", text)

        if not text:
            await update.message.reply_text("❌ Не удалось распознать речь.")
            return

        await update.message.reply_text(f"🎤 Ты сказал:\n{text}")

        await send_action_options(
            message_target=update.message,
            context=context,
            user_text=text,
            source="voice",
            depth=0,
            original_request=text,
        )

    except Exception as e:
        log("Ошибка распознавания:", e)
        await update.message.reply_text(f"❌ Ошибка распознавания: {e}")

    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception as e:
            log("Не удалось удалить временный файл:", e)


async def handle_action_choice(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    payload: dict[str, Any],
) -> None:
    data = query.data or ""
    options = payload.get("options", [])
    mode = str(payload.get("mode", "general"))
    original_request = str(payload.get("original_request", "")).strip()
    depth = int(payload.get("depth", 0))

    try:
        index = int(data.split("_", 1)[1])
    except Exception as e:
        log("Ошибка парсинга action callback:", e)
        await query.edit_message_text("❌ Ошибка выбора.")
        return

    if index < 0 or index >= len(options):
        await query.edit_message_text("❌ Вариант не найден.")
        return

    selected = str(options[index]).strip()
    history = get_selection_history(context)
    history.append(selected)

    log("SELECTED ACTION:", selected)

    await query.edit_message_text(f"✅ Выбрано действие:\n\n{selected}")

    save_structured_decision(
        user_text=original_request,
        selected_option=selected,
        next_step_text="Ожидается результат выполнения",
    )

    save_interaction(
        source="action_button",
        user_text=original_request,
        assistant_text=f"selected action: {selected}",
        selected_option=selected,
    )

    append_daily_entry(
        f"### Action selected\n"
        f"- mode: {mode}\n"
        f"- request: {original_request}\n"
        f"- selected: {selected}\n"
        f"- depth: {depth}"
    )

    set_session_state(
        chat_id=query.message.chat.id,
        active_mode=mode,
        active_request=original_request,
        active_action=selected,
        active_stage="await_result",
        depth=depth,
        last_result="",
    )

    result_buttons = get_completion_buttons(mode)
    result_keyboard = build_result_keyboard(result_buttons)

    sent = await query.message.reply_text(
        "Сделай это и отметь результат:",
        reply_markup=result_keyboard,
    )

    store = get_message_store(context)
    store[str(sent.message_id)] = {
        "stage": "report_result",
        "source": payload.get("source", "text"),
        "mode": mode,
        "original_request": original_request,
        "selected_option": selected,
        "result_buttons": result_buttons,
        "depth": depth,
    }

    log("RESULT MESSAGE_ID:", sent.message_id)
    log("RESULT BUTTONS:", result_buttons)


async def handle_failure_reason_choice(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    payload: dict[str, Any],
) -> None:
    data = query.data or ""
    reason_buttons = payload.get("reason_buttons", [])
    mode = str(payload.get("mode", "general"))
    original_request = str(payload.get("original_request", "")).strip()
    selected_option = str(payload.get("selected_option", "")).strip()
    result_label = str(payload.get("result_label", "")).strip()
    source = str(payload.get("source", "text"))
    depth = int(payload.get("depth", 0))

    try:
        index = int(data.split("_", 1)[1])
    except Exception as e:
        log("Ошибка парсинга failure callback:", e)
        await query.edit_message_text("❌ Ошибка причины провала.")
        return

    if index < 0 or index >= len(reason_buttons):
        await query.edit_message_text("❌ Причина не найдена.")
        return

    failure_reason = str(reason_buttons[index]).strip()
    history = get_selection_history(context)
    recent_memory = read_last_daily_entries(limit=DAILY_MEMORY_LIMIT)

    recovery = build_recovery(
        original_request=original_request,
        selected_option=selected_option,
        result_label=result_label,
        failure_reason=failure_reason,
        mode=mode,
        history=history,
        recent_memory=recent_memory,
    )

    log("FAILURE REASON:", failure_reason)
    log("RECOVERY SUMMARY:", recovery["summary"])

    await query.edit_message_text(
        f"📌 Причина провала:\n\n"
        f"Действие: {selected_option}\n"
        f"Результат: {result_label}\n"
        f"Причина: {failure_reason}"
    )

    log_outcome(
        chat_id=query.message.chat.id,
        mode=mode,
        request_text=original_request,
        action_text=selected_option,
        result_label=result_label,
        review_status="blocked",
        review_summary=recovery["summary"],
        failure_reason=failure_reason,
    )

    set_session_state(
        chat_id=query.message.chat.id,
        active_mode=mode,
        active_request=original_request,
        active_action=selected_option,
        active_stage="recovery",
        depth=depth,
        last_result=result_label,
    )

    save_interaction(
        source="failure_reason_button",
        user_text=original_request,
        assistant_text=(
            f"failure_reason={failure_reason} | "
            f"summary={recovery['summary']} | "
            f"lesson={recovery['lesson']}"
        ),
        selected_option=selected_option,
    )

    append_daily_entry(
        f"### Recovery\n"
        f"- mode: {mode}\n"
        f"- selected: {selected_option}\n"
        f"- result: {result_label}\n"
        f"- failure_reason: {failure_reason}\n"
        f"- summary: {recovery['summary']}\n"
        f"- lesson: {recovery['lesson']}\n"
        f"- memory_note: {recovery['memory_note']}"
    )

    await query.message.reply_text(
        f"Что вижу:\n{recovery['summary']}\n\n"
        f"Вывод:\n{recovery['lesson']}"
    )

    protocol_depth_limit = get_max_depth(mode)
    effective_depth_limit = min(MAX_DECISION_DEPTH, protocol_depth_limit)

    if depth >= effective_depth_limit:
        await query.message.reply_text(
            "На этом шаге лучше остановиться, сделать выводы и вернуться с новым контекстом."
        )
        return

    outcome_hints = build_outcome_hints(
        chat_id=query.message.chat.id,
        mode=mode,
        limit=20,
    )

    next_prompt = (
        f"{recovery['next_prompt']}\n\n"
        f"{outcome_hints}"
    )

    await send_action_options(
        message_target=query.message,
        context=context,
        user_text=next_prompt,
        source=f"recovery:{failure_reason}",
        depth=depth + 1,
        original_request=original_request,
    )


async def handle_result_choice(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    payload: dict[str, Any],
) -> None:
    data = query.data or ""
    result_buttons = payload.get("result_buttons", [])
    mode = str(payload.get("mode", "general"))
    original_request = str(payload.get("original_request", "")).strip()
    selected_option = str(payload.get("selected_option", "")).strip()
    source = str(payload.get("source", "text"))
    depth = int(payload.get("depth", 0))

    try:
        index = int(data.split("_", 1)[1])
    except Exception as e:
        log("Ошибка парсинга result callback:", e)
        await query.edit_message_text("❌ Ошибка результата.")
        return

    if index < 0 or index >= len(result_buttons):
        await query.edit_message_text("❌ Результат не найден.")
        return

    result_label = str(result_buttons[index]).strip()
    log("RESULT LABEL:", result_label)

    await query.edit_message_text(
        f"📌 Результат по шагу:\n\n"
        f"Действие: {selected_option}\n"
        f"Результат: {result_label}"
    )

    if should_ask_failure_reason(result_label):
        reason_buttons = get_failure_reason_buttons()
        keyboard = build_failure_reason_keyboard(reason_buttons)

        sent = await query.message.reply_text(
            "Почему не получилось?",
            reply_markup=keyboard,
        )

        store = get_message_store(context)
        store[str(sent.message_id)] = {
            "stage": "report_failure_reason",
            "source": source,
            "mode": mode,
            "original_request": original_request,
            "selected_option": selected_option,
            "result_label": result_label,
            "reason_buttons": reason_buttons,
            "depth": depth,
        }

        set_session_state(
            chat_id=query.message.chat.id,
            active_mode=mode,
            active_request=original_request,
            active_action=selected_option,
            active_stage="await_failure_reason",
            depth=depth,
            last_result=result_label,
        )

        return

    history = get_selection_history(context)
    recent_memory = read_last_daily_entries(limit=DAILY_MEMORY_LIMIT)

    review = build_review(
        original_request=original_request,
        selected_option=selected_option,
        result_label=result_label,
        mode=mode,
        history=history,
        recent_memory=recent_memory,
    )

    log("REVIEW STATUS:", review["status"])
    log("REVIEW SUMMARY:", review["summary"])

    log_outcome(
        chat_id=query.message.chat.id,
        mode=mode,
        request_text=original_request,
        action_text=selected_option,
        result_label=result_label,
        review_status=review["status"],
        review_summary=review["summary"],
        failure_reason="",
    )

    set_session_state(
        chat_id=query.message.chat.id,
        active_mode=mode,
        active_request=original_request,
        active_action=selected_option,
        active_stage="reviewed",
        depth=depth,
        last_result=result_label,
    )

    save_interaction(
        source="result_button",
        user_text=original_request,
        assistant_text=(
            f"review_status={review['status']} | "
            f"summary={review['summary']} | "
            f"lesson={review['lesson']}"
        ),
        selected_option=selected_option,
    )

    append_daily_entry(
        f"### Review\n"
        f"- mode: {mode}\n"
        f"- selected: {selected_option}\n"
        f"- result: {result_label}\n"
        f"- status: {review['status']}\n"
        f"- summary: {review['summary']}\n"
        f"- lesson: {review['lesson']}\n"
        f"- memory_note: {review['memory_note']}"
    )

    await query.message.reply_text(
        f"Что вижу:\n{review['summary']}\n\n"
        f"Вывод:\n{review['lesson']}"
    )

    save_memory_note(
        chat_id=query.message.chat.id,
        note_type="lesson",
        content=f"{selected_option} → {review['lesson']}",
    )

    if mode == "learning":
        await query.message.reply_text(
            "📚 Какую тему изучал?",
            reply_markup=build_study_topic_keyboard(),
        )

    protocol_depth_limit = get_max_depth(mode)
    effective_depth_limit = min(MAX_DECISION_DEPTH, protocol_depth_limit)

    if depth >= effective_depth_limit:
        await query.message.reply_text(
            "На этом шаге лучше остановиться, сделать выводы и вернуться с новым контекстом."
        )
        return

    outcome_hints = build_outcome_hints(
        chat_id=query.message.chat.id,
        mode=mode,
        limit=20,
    )

    next_prompt = (
        f"{review['next_prompt']}\n\n"
        f"{outcome_hints}"
    )

    await send_action_options(
        message_target=query.message,
        context=context,
        user_text=next_prompt,
        source=f"review:{review['status']}",
        depth=depth + 1,
        original_request=original_request,
    )


async def handle_plan_flow_callback(
    query,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    data = query.data or ""
    draft = get_plan_draft(context)

    if data.startswith("plan_energy_"):
        energy = data.replace("plan_energy_", "", 1)
        draft["energy"] = energy
        await query.edit_message_text(f"Ресурс выбран: {energy}")
        await query.message.reply_text(
            "Сколько времени реально есть на главный фокус дня?",
            reply_markup=build_plan_time_keyboard(),
        )
        return

    if data.startswith("plan_time_"):
        time_budget = data.replace("plan_time_", "", 1)
        draft["time_budget"] = time_budget
        await query.edit_message_text(f"Окно времени выбрано: {time_budget}")
        await query.message.reply_text(
            "Какая область должна стать главным фокусом дня?",
            reply_markup=build_domain_keyboard("plan_domain"),
        )
        return

    if data.startswith("plan_domain_"):
        domain = data.replace("plan_domain_", "", 1)
        draft["focus_domain"] = domain

        energy = draft.get("energy", "normal")
        time_budget = draft.get("time_budget", "medium")
        focus_domain = draft.get("focus_domain", "general")

        plan = build_daily_plan(
            focus_domain=focus_domain,
            energy=energy,
            time_budget=time_budget,
        )

        set_daily_focus(
            chat_id=query.message.chat.id,
            daily_focus_domain=plan["focus_domain"],
            daily_focus_text=plan["focus_text"],
            daily_energy=plan["energy_label"],
            daily_time_budget=plan["time_budget_label"],
        )

        save_daily_plan(plan)

        horizon = build_long_horizon_context(query.message.chat.id)

        append_daily_entry(
            f"### Focus alignment baseline\n"
            f"- current_day: {today_str()}\n"
            f"- focus_domain: {plan['focus_domain']}\n"
            f"- focus_text: {plan['focus_text']}"
        )

        await query.edit_message_text("Область дня выбрана.")

        await query.message.reply_text(
            format_daily_plan(plan, long_horizon_text=horizon["summary_text"]),
        )

        context.user_data["plan_draft"] = {}
        await send_main_menu(query.message)
        return


async def handle_goal_flow_callback(
    query,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    data = query.data or ""
    draft = get_goal_draft(context)

    if data.startswith("weekgoal_domain_"):
        domain = data.replace("weekgoal_domain_", "", 1)
        draft["kind"] = "weekly"
        draft["domain"] = domain
        update_session_state(query.message.chat.id, active_stage="await_weekly_goal_text")
        await query.edit_message_text(f"Область цели недели: {DOMAINS.get(domain, 'Общее')}")
        await query.message.reply_text("Напиши одной фразой главный результат недели.")
        return

    if data.startswith("monthfocus_domain_"):
        domain = data.replace("monthfocus_domain_", "", 1)
        draft["kind"] = "monthly"
        draft["domain"] = domain
        update_session_state(query.message.chat.id, active_stage="await_monthly_focus_text")
        await query.edit_message_text(f"Область месячного вектора: {DOMAINS.get(domain, 'Общее')}")
        await query.message.reply_text("Напиши одной фразой главный вектор месяца.")
        return


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()
    log("👉 Нажата кнопка:", query.data)

    data = query.data or ""

    if data == "cmd_weekly":
        await query.message.reply_text("Собираю weekly summary...")
        await run_weekly_summary(query.message, query.message.chat.id)
        return

    if data == "cmd_reset":
        context.user_data.clear()
        clear_session_state(query.message.chat.id)
        await query.message.reply_text("Сессия сброшена.")
        await send_main_menu(query.message)
        return

    if data == "cmd_plan":
        await start_daily_plan(query.message, context)
        return

    if data == "cmd_close":
        await run_daily_closing(query.message, query.message.chat.id)
        return

    if data == "cmd_weekgoal":
        await start_weekly_goal_flow(query.message, context)
        return

    if data == "cmd_monthfocus":
        await start_monthly_focus_flow(query.message, context)
        return

    if data == "cmd_strategy":
        await run_strategy_profile(query.message, query.message.chat.id)
        return

    if data == "cmd_checkin":
        await run_checkin(query.message, query.message.chat.id)
        return

    if data == "cmd_pulse":
        await run_pulse(query.message, query.message.chat.id)
        return

    if data == "cmd_study":
        text = format_study_stats(query.message.chat.id)
        await query.message.reply_text(text)
        return

    if data == "cmd_path":
        gf = get_gilfoyle_mode(query.message.chat.id)
        text = format_path(query.message.chat.id, gilfoyle=gf)
        await query.message.reply_text(text)
        return

    if data == "cmd_gilfoyle_on":
        chat_id = query.message.chat.id
        set_gilfoyle_mode(chat_id, True)
        await query.message.reply_text("🤖 Режим Гилфойла включён. Никакой мотивации. Только факты.")
        await send_main_menu(query.message, chat_id)
        return

    if data == "cmd_gilfoyle_off":
        chat_id = query.message.chat.id
        set_gilfoyle_mode(chat_id, False)
        await query.message.reply_text("👤 Обычный режим включён.")
        await send_main_menu(query.message, chat_id)
        return

    if data == "cmd_proactive_on":
        chat_id = query.message.chat.id
        set_proactive_settings(chat_id, enabled=True)
        schedule_jobs_for_chat(context.application.job_queue, chat_id)
        append_daily_entry("### Proactive enabled")
        await query.message.reply_text(
            f"Проактивный режим включён.\n"
            f"Утренний check-in и вечернее напоминание будут идти по часовому поясу {USER_TIMEZONE}."
        )
        return

    if data == "cmd_proactive_off":
        chat_id = query.message.chat.id
        set_proactive_settings(chat_id, enabled=False)
        remove_jobs_for_chat(context.application.job_queue, chat_id)
        append_daily_entry("### Proactive disabled")
        await query.message.reply_text("Проактивный режим выключен.")
        return

    if data.startswith("study_topic_"):
        topic = data.replace("study_topic_", "", 1)
        chat_id = query.message.chat.id
        log_session(chat_id, topic)
        label = TOPICS.get(topic, topic)
        streak = get_streak(chat_id)
        await query.edit_message_text(f"✅ {label} — записано\n🔥 Стрик: {streak} дн.")
        return

    if data.startswith("plan_"):
        await handle_plan_flow_callback(query, context)
        return

    if data.startswith("weekgoal_domain_") or data.startswith("monthfocus_domain_"):
        await handle_goal_flow_callback(query, context)
        return

    store = get_message_store(context)
    store_key = str(query.message.message_id)
    payload = store.get(store_key)

    if not payload:
        await query.edit_message_text("❌ Эта сессия уже устарела. Отправь новое сообщение.")
        return

    stage = payload.get("stage", "")
    store.pop(store_key, None)

    if stage == "choose_action":
        await handle_action_choice(query, context, payload)
        return

    if stage == "report_result":
        await handle_result_choice(query, context, payload)
        return

    if stage == "report_failure_reason":
        await handle_failure_reason_choice(query, context, payload)
        return

    await query.edit_message_text("❌ Неизвестный этап.")


def main() -> None:
    ensure_dirs()
    validate_config()
    init_state_db()
    init_outcomes_db()
    init_study_db()
    init_session_memory_db()

    persistence = PicklePersistence(filepath=str(Path(ASSISTANT_DB_PATH).parent / "bot_persistence.pkl"))
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).persistence(persistence).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("weekly", weekly_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("close", close_command))
    app.add_handler(CommandHandler("weekgoal", weekgoal_command))
    app.add_handler(CommandHandler("monthfocus", monthfocus_command))
    app.add_handler(CommandHandler("strategy", strategy_command))
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("pulse", pulse_command))
    app.add_handler(CommandHandler("proactive_on", proactive_on_command))
    app.add_handler(CommandHandler("proactive_off", proactive_off_command))
    app.add_handler(CommandHandler("study", study_command))
    app.add_handler(CommandHandler("path", path_command))
    app.add_handler(CommandHandler("gilfoyle_on", gilfoyle_on_command))
    app.add_handler(CommandHandler("gilfoyle_off", gilfoyle_off_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_button))

    restore_proactive_jobs(app.job_queue)

    log("🚀 Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
