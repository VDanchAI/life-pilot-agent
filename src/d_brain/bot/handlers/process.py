"""Process command handler — clarification FSM (ТЗ 2) + correction flow (ТЗ 1.2)."""

import asyncio
import logging
from datetime import date
from html import escape as html_escape
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from d_brain.bot.progress import run_with_progress
from d_brain.bot.states import ProcessStates
from d_brain.bot.utils import send_formatted_report, transcribe_voice
from d_brain.services.factory import get_git, get_processor

router = Router(name="process")
logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────


def _correction_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Скорректировать", callback_data="process_correct")
    builder.button(text="✅ Всё ок", callback_data="process_ok")
    builder.adjust(2)
    return builder.as_markup()


def _clarify_keyboard(
    uncertain_item: dict[str, Any], idx: int
) -> InlineKeyboardMarkup:
    """Build keyboard for a single uncertain item."""
    _labels = {"task": "📋 Задача", "thought": "💭 Мысль", "idea": "💡 Идея"}
    builder = InlineKeyboardBuilder()
    for option in uncertain_item.get("options", ["task", "thought"]):
        label = _labels.get(option, option)
        builder.button(
            text=label,
            callback_data=f"process_clarify_{option}_{idx}",
        )
    builder.button(text="⏭ Пропустить все", callback_data="process_skip_all")
    builder.adjust(len(uncertain_item.get("options", [])), 1)
    return builder.as_markup()


async def _send_report_with_correction(
    message: Message,
    status_msg: Message,
    report: dict[str, Any],
    state: FSMContext,
) -> None:
    """Send report and add correction keyboard. Save report in FSM state."""
    formatted = report.get("report", report.get("error", ""))
    try:
        await status_msg.edit_text(formatted)
    except Exception:
        await status_msg.edit_text(formatted, parse_mode=None)

    await message.answer(
        "Всё верно?",
        reply_markup=_correction_keyboard(),
    )
    await state.set_data({"last_report": formatted})


async def _finalize_processing(
    message: Message,
    status_msg: Message,
    entries: list[dict[str, Any]],
    day: date,
    state: FSMContext,
) -> None:
    """Run process_daily_finalize, commit, and send report with correction keyboard."""
    processor = get_processor()
    git = get_git()

    report = await run_with_progress(
        processor.process_daily_finalize,
        status_msg,
        "⏳ Обрабатываю...",
        day,
        entries,
    )

    if "error" not in report:
        today = day.isoformat()
        await asyncio.to_thread(git.commit_and_push, f"chore: process daily {today}")

    await _send_report_with_correction(message, status_msg, report, state)


# ── /process command ──────────────────────────────────────────────────


@router.message(Command("process"))
async def cmd_process(message: Message, state: FSMContext) -> None:
    """Handle /process command — categorize, clarify if needed, then finalize."""
    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info("Process command triggered by user %s", user_id)

    await state.clear()

    status_msg = await message.answer("⏳ Анализирую записи...")

    processor = get_processor()
    git = get_git()
    today = date.today()

    result = await run_with_progress(
        processor.categorize_daily,
        status_msg,
        "⏳ Категоризирую...",
        today,
    )

    if "error" in result:
        await send_formatted_report(status_msg, result)
        return

    if "parse_error" in result:
        logger.warning("Categorization parse failed, falling back to process_daily")
        report = await run_with_progress(
            processor.process_daily, status_msg, "⏳ Обрабатываю...", today,
        )
        if "error" not in report:
            today_str = today.isoformat()
            await asyncio.to_thread(
                git.commit_and_push, f"chore: process daily {today_str}"
            )
        await _send_report_with_correction(message, status_msg, report, state)
        return

    confident = result.get("confident", [])
    uncertain = result.get("uncertain", [])

    if not uncertain:
        await _finalize_processing(
            message, status_msg, confident, today, state,
        )
        return

    await state.set_state(ProcessStates.waiting_clarification)
    await state.set_data({
        "confident": confident,
        "uncertain": uncertain,
        "clarified": [],
        "day": today.isoformat(),
        "status_msg_id": status_msg.message_id,
        "chat_id": message.chat.id,
    })

    first = uncertain[0]
    total = len(uncertain)
    await status_msg.edit_text(
        f"❓ Нашёл {total} неоднозначн{'ую запись' if total == 1 else 'ых записей'}. "
        f"Помоги определить категорию:\n\n"
        f"<b>1/{total}:</b> {html_escape(first.get('question', 'Что это?'))}\n\n"
        f"<i>{html_escape(first.get('text', ''))}</i>",
        reply_markup=_clarify_keyboard(first, 0),
    )


# ── Clarification callbacks ───────────────────────────────────────────


@router.callback_query(
    ProcessStates.waiting_clarification,
    F.data.startswith("process_clarify_"),
)
async def handle_clarify_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle category choice for an uncertain item."""
    _cat_labels = {"task": "📋 Задача", "thought": "💭 Мысль", "idea": "💡 Идея"}

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    parts = (callback.data or "").split("_", 3)
    if len(parts) != 4:
        return
    _, _, category, idx_str = parts

    await callback.answer(_cat_labels.get(category, category))
    try:
        idx = int(idx_str)
    except ValueError:
        return

    data = await state.get_data()
    uncertain: list[dict[str, Any]] = data.get("uncertain", [])
    clarified: list[dict[str, Any]] = data.get("clarified", [])
    confident: list[dict[str, Any]] = data.get("confident", [])

    if idx >= len(uncertain):
        return

    item = uncertain[idx]
    clarified.append({"text": item["text"], "category": category, "action": ""})

    next_idx = idx + 1

    if next_idx < len(uncertain):
        next_item = uncertain[next_idx]
        total = len(uncertain)
        question = next_item.get("question", "Что это?")
        text_preview = next_item.get("text", "")
        await msg.edit_text(
            f"<b>{next_idx + 1}/{total}:</b> "
            f"{html_escape(question)}\n\n"
            f"<i>{html_escape(text_preview)}</i>",
            reply_markup=_clarify_keyboard(next_item, next_idx),
        )
        await state.update_data(clarified=clarified)
    else:
        all_entries = confident + clarified
        day = date.fromisoformat(data.get("day", date.today().isoformat()))

        await msg.edit_text("⏳ Обрабатываю все записи...", reply_markup=None)
        await state.clear()

        await _finalize_processing(msg, msg, all_entries, day, state)


@router.callback_query(
    ProcessStates.waiting_clarification,
    F.data == "process_skip_all",
)
async def handle_skip_all(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip all uncertain — treat them all as thoughts."""
    await callback.answer("Пропускаю — всё как мысли")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    data = await state.get_data()
    uncertain: list[dict[str, Any]] = data.get("uncertain", [])
    clarified: list[dict[str, Any]] = data.get("clarified", [])
    confident: list[dict[str, Any]] = data.get("confident", [])

    for item in uncertain[len(clarified):]:
        clarified.append({"text": item["text"], "category": "thought", "action": ""})

    all_entries = confident + clarified
    day = date.fromisoformat(data.get("day", date.today().isoformat()))

    await msg.edit_text("⏳ Обрабатываю все записи...", reply_markup=None)
    await state.clear()

    await _finalize_processing(msg, msg, all_entries, day, state)


# Fallback: text in waiting_clarification state
@router.message(ProcessStates.waiting_clarification)
async def clarification_text_fallback(message: Message, state: FSMContext) -> None:
    """Any text/command in clarification state — remind user to use buttons."""
    if message.text and message.text.startswith("/"):
        await state.clear()
        return
    await message.answer("Нажми одну из кнопок или ⏭ Пропустить все")


# ── Correction callbacks (ТЗ 1.2) ────────────────────────────────────


@router.callback_query(F.data == "process_correct")
async def handle_process_correct(callback: CallbackQuery, state: FSMContext) -> None:
    """Enter correction mode — ask for correction input."""
    await callback.answer("✏️ Корректировка")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)
    await state.set_state(ProcessStates.waiting_correction)
    await msg.answer(
        "✏️ <b>Что скорректировать?</b>\n\n"
        "Отправь текст или голосовое сообщение с правками."
    )


@router.callback_query(F.data == "process_ok")
async def handle_process_ok(callback: CallbackQuery, state: FSMContext) -> None:
    """Accept report as-is, exit FSM."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return
    await msg.edit_reply_markup(reply_markup=None)
    await msg.answer("✅ Выполнено")


@router.message(ProcessStates.waiting_correction)
async def handle_correction_input(
    message: Message, bot: Bot, state: FSMContext
) -> None:
    """Receive correction text/voice, send to Claude, show new report."""
    if message.text and message.text.startswith("/"):
        await state.clear()
        return

    data = await state.get_data()
    original_report = data.get("last_report", "")

    prompt_text: str | None = None

    if message.voice:
        await message.chat.do(action="typing")
        prompt_text = await transcribe_voice(bot, message)
        if not prompt_text:
            return
        await message.answer(f"🎤 <i>{html_escape(prompt_text)}</i>")
    elif message.text:
        prompt_text = message.text
    else:
        await message.answer("Отправь текст или голосовое сообщение")
        return

    status_msg = await message.answer("⏳ Корректирую...")

    processor = get_processor()

    correction_prompt = f"""Вот оригинальный отчёт обработки:

{original_report}

Пользователь просит внести правки:
{prompt_text}

Скорректируй отчёт с учётом правок и обнови данные в Todoist/vault если нужно.

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Start with 📊 <b>Скорректированный отчёт</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>"""

    report = await run_with_progress(
        processor.execute_prompt, status_msg, "⏳ Корректирую...", correction_prompt,
    )

    await state.clear()
    await _send_report_with_correction(message, status_msg, report, state)
