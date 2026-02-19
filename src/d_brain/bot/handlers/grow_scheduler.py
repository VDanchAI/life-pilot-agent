"""Scheduler functions that trigger GROW sessions and handle reminder logic."""

from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from d_brain.config import get_settings
from d_brain.services.grow import (
    get_period_for_session,
    is_reflection_done,
    load_draft,
    load_grow_state,
    save_grow_state,
)

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3


def _now_iso() -> str:
    """Return current datetime as ISO-8601 string."""
    return datetime.now().isoformat(timespec="seconds")


def _build_start_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """Build a single-button inline keyboard for starting a GROW session."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Начать", callback_data=callback_data)
    return builder.as_markup()


def _build_resume_keyboard(
    resume_callback: str,
    restart_callback: str,
) -> InlineKeyboardMarkup:
    """Build a two-button inline keyboard for resuming or restarting a session."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Продолжить", callback_data=resume_callback)
    builder.button(text="Начать заново", callback_data=restart_callback)
    builder.adjust(2)
    return builder.as_markup()


def _resolve_attempt(
    state: dict,
    session_type: str,
    period: str,
) -> int:
    """Determine the attempt number for the current period.

    Returns the next attempt number (1 on first call, incremented on subsequent
    calls). Returns _MAX_ATTEMPTS + 1 if the maximum has already been reached.
    """
    entry = state.get(session_type, {})
    if entry.get("period") == period and isinstance(entry.get("attempt"), int):
        return entry["attempt"] + 1
    return 1


def _save_attempt(
    state: dict,
    session_type: str,
    period: str,
    attempt: int,
    vault_path,
) -> None:
    """Persist the updated attempt counter into .grow_state.json."""
    state[session_type] = {
        "period": period,
        "attempt": attempt,
        "last_sent": _now_iso(),
    }
    save_grow_state(vault_path, state)


# ---------------------------------------------------------------------------
# Weekly scheduler
# ---------------------------------------------------------------------------


async def scheduled_grow_weekly(bot: Bot, chat_id: int) -> None:
    """Trigger or remind about the weekly GROW reflection.

    Called by the scheduler on Saturday, Sunday, and Monday at 21:00.
    Sends up to _MAX_ATTEMPTS reminders per period.
    """
    settings = get_settings()
    vault_path = settings.vault_path

    period = get_period_for_session("weekly")

    if is_reflection_done("weekly", period, vault_path):
        logger.info("Weekly reflection already done for %s — skipping", period)
        return

    state = load_grow_state(vault_path)
    attempt = _resolve_attempt(state, "weekly", period)

    if attempt > _MAX_ATTEMPTS:
        logger.info(
            "Weekly GROW: max attempts (%d) reached for %s — giving up",
            _MAX_ATTEMPTS,
            period,
        )
        return

    _save_attempt(state, "weekly", period, attempt, vault_path)

    draft = load_draft("weekly", period, vault_path)

    if draft is not None:
        logger.info(
            "Weekly GROW: draft found for %s (attempt %d) — sending resume prompt",
            period,
            attempt,
        )
        keyboard = _build_resume_keyboard(
            resume_callback="grow_w_resume_yes",
            restart_callback="grow_w_resume_restart",
        )
        try:
            await bot.send_message(
                chat_id,
                "У тебя есть незавершённая рефлексия за эту неделю.\n"
                "Продолжить с того места, где остановился?",
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "Failed to send weekly GROW resume prompt (attempt %d)", attempt
            )
        return

    # No draft — send a fresh start prompt with attempt-appropriate wording
    if attempt == 1:
        text = (
            "Привет! Время для недельной рефлексии.\n"
            "Готов уделить 5-10 минут?"
        )
    elif attempt == 2:
        text = "Напоминаю о рефлексии за неделю. Пара минут — и готово."
    else:
        text = "Последнее напоминание о рефлексии за неделю."

    keyboard = _build_start_keyboard("weekly_grow")

    logger.info(
        "Weekly GROW: sending start prompt for %s (attempt %d)", period, attempt
    )
    try:
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception:
        logger.exception(
            "Failed to send weekly GROW start prompt (attempt %d)", attempt
        )


# ---------------------------------------------------------------------------
# Monthly scheduler
# ---------------------------------------------------------------------------


async def scheduled_grow_monthly(bot: Bot, chat_id: int) -> None:
    """Trigger or remind about the monthly GROW reflection.

    Called by the scheduler on the 1st of the month (and retries on the 2nd
    and 3rd if no reflection has been completed).
    Sends up to _MAX_ATTEMPTS reminders per period.
    """
    settings = get_settings()
    vault_path = settings.vault_path

    period = get_period_for_session("monthly")

    if is_reflection_done("monthly", period, vault_path):
        logger.info("Monthly reflection already done for %s — skipping", period)
        return

    state = load_grow_state(vault_path)
    attempt = _resolve_attempt(state, "monthly", period)

    if attempt > _MAX_ATTEMPTS:
        logger.info(
            "Monthly GROW: max attempts (%d) reached for %s — giving up",
            _MAX_ATTEMPTS,
            period,
        )
        return

    _save_attempt(state, "monthly", period, attempt, vault_path)

    draft = load_draft("monthly", period, vault_path)

    if draft is not None:
        logger.info(
            "Monthly GROW: draft found for %s (attempt %d) — sending resume prompt",
            period,
            attempt,
        )
        keyboard = _build_resume_keyboard(
            resume_callback="grow_m_resume_yes",
            restart_callback="grow_m_resume_restart",
        )
        try:
            await bot.send_message(
                chat_id,
                "У тебя есть незавершённая рефлексия за этот месяц.\n"
                "Продолжить с того места, где остановился?",
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "Failed to send monthly GROW resume prompt (attempt %d)", attempt
            )
        return

    # No draft — send a fresh start prompt with attempt-appropriate wording
    if attempt == 1:
        text = (
            "Привет! Время для месячной рефлексии.\n"
            "Готов уделить 10-15 минут итогам месяца?"
        )
    elif attempt == 2:
        text = "Напоминаю о рефлексии за месяц. Это важно — всего пара вопросов."
    else:
        text = "Последнее напоминание о рефлексии за месяц."

    keyboard = _build_start_keyboard("monthly_grow")

    logger.info(
        "Monthly GROW: sending start prompt for %s (attempt %d)", period, attempt
    )
    try:
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception:
        logger.exception(
            "Failed to send monthly GROW start prompt (attempt %d)", attempt
        )


# ---------------------------------------------------------------------------
# Quarterly scheduler
# ---------------------------------------------------------------------------


async def scheduled_grow_quarterly(bot: Bot, chat_id: int) -> None:
    """Trigger or remind about the quarterly GROW reflection.

    Called by the scheduler on April 1-3, July 1-3, October 1-3 at 21:00.
    Sends up to _MAX_ATTEMPTS reminders per period.
    """
    settings = get_settings()
    vault_path = settings.vault_path

    period = get_period_for_session("quarterly")

    if is_reflection_done("quarterly", period, vault_path):
        logger.info("Quarterly reflection already done for %s — skipping", period)
        return

    state = load_grow_state(vault_path)
    attempt = _resolve_attempt(state, "quarterly", period)

    if attempt > _MAX_ATTEMPTS:
        logger.info(
            "Quarterly GROW: max attempts (%d) reached for %s — giving up",
            _MAX_ATTEMPTS,
            period,
        )
        return

    _save_attempt(state, "quarterly", period, attempt, vault_path)

    draft = load_draft("quarterly", period, vault_path)

    if draft is not None:
        logger.info(
            "Quarterly GROW: draft found for %s (attempt %d) — sending resume prompt",
            period,
            attempt,
        )
        keyboard = _build_resume_keyboard(
            resume_callback="grow_q_resume_yes",
            restart_callback="grow_q_resume_restart",
        )
        try:
            await bot.send_message(
                chat_id,
                "У тебя есть незавершённая рефлексия за этот квартал.\n"
                "Продолжить с того места, где остановился?",
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "Failed to send quarterly GROW resume prompt (attempt %d)", attempt
            )
        return

    # No draft — send a fresh start prompt with attempt-appropriate wording
    if attempt == 1:
        text = (
            "Привет! Время для квартальной рефлексии.\n"
            "Готов уделить 15-20 минут анализу квартала?"
        )
    elif attempt == 2:
        text = "Напоминаю о квартальной рефлексии. Это важный чекпоинт."
    else:
        text = "Последнее напоминание о квартальной рефлексии."

    keyboard = _build_start_keyboard("quarterly_grow")

    logger.info(
        "Quarterly GROW: sending start prompt for %s (attempt %d)", period, attempt
    )
    try:
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception:
        logger.exception(
            "Failed to send quarterly GROW start prompt (attempt %d)", attempt
        )


# ---------------------------------------------------------------------------
# Yearly-end scheduler
# ---------------------------------------------------------------------------


async def scheduled_grow_yearly_end(bot: Bot, chat_id: int) -> None:
    """Trigger or remind about the year-end GROW reflection.

    Called by the scheduler on Dec 20, 23, 26 at 21:00.
    Sends up to _MAX_ATTEMPTS reminders per period.
    """
    settings = get_settings()
    vault_path = settings.vault_path

    period = get_period_for_session("yearly_end")

    if is_reflection_done("yearly_end", period, vault_path):
        logger.info("Yearly-end reflection already done for %s — skipping", period)
        return

    state = load_grow_state(vault_path)
    attempt = _resolve_attempt(state, "yearly_end", period)

    if attempt > _MAX_ATTEMPTS:
        logger.info(
            "Yearly-end GROW: max attempts (%d) reached for %s — giving up",
            _MAX_ATTEMPTS,
            period,
        )
        return

    _save_attempt(state, "yearly_end", period, attempt, vault_path)

    draft = load_draft("yearly_end", period, vault_path)

    if draft is not None:
        logger.info(
            "Yearly-end GROW: draft found for %s (attempt %d) — sending resume prompt",
            period,
            attempt,
        )
        keyboard = _build_resume_keyboard(
            resume_callback="grow_ye_resume_yes",
            restart_callback="grow_ye_resume_restart",
        )
        try:
            await bot.send_message(
                chat_id,
                "У тебя есть незавершённые итоги года.\n"
                "Продолжить с того места, где остановился?",
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "Failed to send yearly-end GROW resume prompt (attempt %d)", attempt
            )
        return

    # No draft — send a fresh start prompt with attempt-appropriate wording
    if attempt == 1:
        text = (
            "Привет! Время подвести итоги года.\n"
            "Готов уделить 20-30 минут?"
        )
    elif attempt == 2:
        text = "Напоминаю про подведение итогов года. Это важно."
    else:
        text = "Последнее напоминание — итоги года."

    keyboard = _build_start_keyboard("yearly_end_grow")

    logger.info(
        "Yearly-end GROW: sending start prompt for %s (attempt %d)", period, attempt
    )
    try:
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception:
        logger.exception(
            "Failed to send yearly-end GROW start prompt (attempt %d)", attempt
        )


# ---------------------------------------------------------------------------
# Yearly-start scheduler
# ---------------------------------------------------------------------------


async def scheduled_grow_yearly_start(bot: Bot, chat_id: int) -> None:
    """Trigger or remind about the year-start GROW planning session.

    Called by the scheduler on Jan 5, 7, 9 at 21:00.
    Sends up to _MAX_ATTEMPTS reminders per period.
    """
    settings = get_settings()
    vault_path = settings.vault_path

    period = get_period_for_session("yearly_start")

    if is_reflection_done("yearly_start", period, vault_path):
        logger.info("Yearly-start reflection already done for %s — skipping", period)
        return

    state = load_grow_state(vault_path)
    attempt = _resolve_attempt(state, "yearly_start", period)

    if attempt > _MAX_ATTEMPTS:
        logger.info(
            "Yearly-start GROW: max attempts (%d) reached for %s — giving up",
            _MAX_ATTEMPTS,
            period,
        )
        return

    _save_attempt(state, "yearly_start", period, attempt, vault_path)

    draft = load_draft("yearly_start", period, vault_path)

    if draft is not None:
        logger.info(
            "Yearly-start GROW: draft found for %s (attempt %d) — sending resume",
            period,
            attempt,
        )
        keyboard = _build_resume_keyboard(
            resume_callback="grow_ys_resume_yes",
            restart_callback="grow_ys_resume_restart",
        )
        try:
            await bot.send_message(
                chat_id,
                "У тебя есть незавершённое планирование года.\n"
                "Продолжить с того места, где остановился?",
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "Failed to send yearly-start GROW resume prompt (attempt %d)", attempt
            )
        return

    # No draft — send a fresh start prompt with attempt-appropriate wording
    if attempt == 1:
        text = (
            "Привет! Новый год — время поставить цели.\n"
            "Готов уделить 20-30 минут планированию?"
        )
    elif attempt == 2:
        text = "Напоминаю о планировании года. Давай определим ключевые цели."
    else:
        text = "Последнее напоминание — планирование года."

    keyboard = _build_start_keyboard("yearly_start_grow")

    logger.info(
        "Yearly-start GROW: sending start prompt for %s (attempt %d)", period, attempt
    )
    try:
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception:
        logger.exception(
            "Failed to send yearly-start GROW start prompt (attempt %d)", attempt
        )
