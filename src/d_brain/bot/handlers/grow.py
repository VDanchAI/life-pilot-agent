"""GROW coaching session FSM handler.

Manages the full interactive flow: question presentation, answer collection
(text + voice), deferred questions, Claude analysis, confirmation/correction,
goal updates, and git commit.
"""

from __future__ import annotations

import asyncio
import logging
import re
from html import escape as html_escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from d_brain.bot.progress import BusyError, run_with_progress
from d_brain.bot.states import GrowStates
from d_brain.bot.utils import transcribe_voice
from d_brain.config import get_settings
from d_brain.services.factory import get_git, get_processor
from d_brain.services.grow import (
    analyze_answers,
    delete_draft,
    ensure_yearly_goals_file,
    finalize_reflection,
    get_period_for_session,
    is_reflection_done,
    load_draft,
    save_draft,
    select_questions,
    update_goals,
)

router = Router(name="grow")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type abbreviations for callback_data (64-byte limit)
# ---------------------------------------------------------------------------

TYPE_ABBR: dict[str, str] = {
    "weekly": "w",
    "monthly": "m",
    "quarterly": "q",
    "yearly_end": "ye",
    "yearly_start": "ys",
}
ABBR_TYPE: dict[str, str] = {v: k for k, v in TYPE_ABBR.items()}


# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------


def _question_keyboard(session_type: str, question_index: int) -> InlineKeyboardMarkup:
    """Three action buttons for the current question."""
    abbr = TYPE_ABBR[session_type]
    builder = InlineKeyboardBuilder()
    builder.button(text="Готово", callback_data=f"grow_{abbr}_{question_index}_done")
    builder.button(
        text="Пропустить",
        callback_data=f"grow_{abbr}_{question_index}_skip",
    )
    builder.button(text="Следующий", callback_data=f"grow_{abbr}_{question_index}_next")
    builder.adjust(3)
    return builder.as_markup()


def _confirm_keyboard(session_type: str) -> InlineKeyboardMarkup:
    """Confirm / correct summary buttons."""
    abbr = TYPE_ABBR[session_type]
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data=f"grow_{abbr}_confirm")
    builder.button(text="Скорректировать", callback_data=f"grow_{abbr}_correct")
    builder.adjust(2)
    return builder.as_markup()


def _resume_keyboard(session_type: str) -> InlineKeyboardMarkup:
    """Resume / restart / cancel buttons when a draft exists."""
    abbr = TYPE_ABBR[session_type]
    builder = InlineKeyboardBuilder()
    builder.button(text="Продолжить", callback_data=f"grow_{abbr}_resume_yes")
    builder.button(text="Начать заново", callback_data=f"grow_{abbr}_resume_restart")
    builder.button(text="Отменить", callback_data=f"grow_{abbr}_resume_cancel")
    builder.adjust(3)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Helper: send a question
# ---------------------------------------------------------------------------


async def _send_question(
    bot: Bot,
    chat_id: int,
    question: dict,
    session_type: str,
    index: int,
    total: int,
) -> None:
    """Format and send a single GROW question."""
    text = (
        f"\U0001f535 Вопрос {index + 1} из {total}\n\n"
        f"{html_escape(question['text'])}"
    )
    kb = _question_keyboard(session_type, index)
    await bot.send_message(chat_id, text, reply_markup=kb)


# ---------------------------------------------------------------------------
# Entry point (called by scheduler or trigger callbacks)
# ---------------------------------------------------------------------------


async def start_grow_session(
    bot: Bot,
    chat_id: int,
    session_type: str,
    state: FSMContext,
    attempt: int = 1,
) -> None:
    """Begin (or resume) a GROW coaching session.

    Called by the scheduler or by inline-button callbacks — not a handler itself.
    """
    settings = get_settings()
    vault_path = settings.vault_path
    period = get_period_for_session(session_type)

    # Ensure yearly goals file exists for yearly_start
    if session_type == "yearly_start":
        from datetime import date
        ensure_yearly_goals_file(date.today().year, vault_path)

    # 1. Already done for this period?
    if is_reflection_done(session_type, period, vault_path):
        await bot.send_message(
            chat_id,
            f"Рефлексия <b>{session_type}</b> за <code>{period}</code> уже проведена.",
        )
        return

    # 2. Draft exists — offer to resume
    draft = load_draft(session_type, period, vault_path)
    if draft is not None:
        await bot.send_message(
            chat_id,
            "У тебя есть незавершённая GROW-сессия. Что делаем?",
            reply_markup=_resume_keyboard(session_type),
        )
        return

    # 3. Generate questions (Claude #1)
    status_msg = await bot.send_message(chat_id, "\u23f3 Подбираю вопросы...")

    questions = await select_questions(session_type)

    # 4. Persist initial draft
    draft_data = {
        "session_type": session_type,
        "period": period,
        "questions": questions,
        "answers": {},
        "current_index": 0,
        "deferred_questions": [],
        "deferred_count": {},
        "current_messages": [],
    }
    save_draft(session_type, period, draft_data, vault_path)

    # 5. Set FSM
    await state.set_state(GrowStates.answering)
    await state.set_data(draft_data)

    # 6. Remove status and send first question
    try:
        await status_msg.delete()
    except Exception:
        pass

    if questions:
        await _send_question(
            bot, chat_id, questions[0], session_type, 0, len(questions)
        )
    else:
        logger.error("No questions generated for %s session", session_type)
        await bot.send_message(chat_id, "Не удалось подобрать вопросы. Попробуй позже.")
        await state.clear()


# ---------------------------------------------------------------------------
# Finalize session (all questions answered / skipped)
# ---------------------------------------------------------------------------


async def _finalize_session(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Analyze answers, show summary, ask for confirmation."""
    data = await state.get_data()
    session_type: str = data["session_type"]
    period: str = data["period"]
    questions: list[dict] = data["questions"]
    answers: dict = data["answers"]
    settings = get_settings()
    vault_path = settings.vault_path

    # All skipped?
    all_skipped = all(v == "skipped" for v in answers.values())
    if all_skipped:
        finalize_reflection(
            session_type, period, "Сессия пропущена", questions, answers, vault_path,
        )
        git = get_git()
        ok, reason = await asyncio.to_thread(
            git.commit_and_push, f"GROW {session_type} reflection {period} (skipped)",
        )
        await state.clear()
        msg = "Все вопросы пропущены. Сессия завершена."
        if not ok:
            msg += f"\n\n\u26a0\ufe0f Vault not synced: {reason[:80]}"
        await bot.send_message(chat_id, msg)
        return

    # Claude #2 — analysis
    status_msg = await bot.send_message(chat_id, "\u23f3 Анализирую ответы...")
    result = await analyze_answers(session_type, questions, answers)

    summary: str = result.get("summary", "")
    goal_updates = result.get("goal_updates")
    process_goals: list[dict] = result.get("process_goals") or []

    # Store in FSM for confirm/correct flow
    data["summary"] = summary
    data["goal_updates"] = goal_updates
    data["process_goals"] = process_goals
    await state.set_data(data)
    await state.set_state(GrowStates.confirming)

    # Format message
    parts: list[str] = [f"\U0001f4cb <b>Итог рефлексии</b>\n\n{html_escape(summary)}"]
    if goal_updates and isinstance(goal_updates, dict):
        sections = goal_updates.get("sections", {})
        if sections:
            changes = "\n".join(
                f"  \u2022 <b>{html_escape(k)}</b>: {html_escape(str(v))}"
                for k, v in sections.items()
            )
            goal_changes_header = "\n\U0001f4dd <b>Предложенные изменения целей:</b>\n"
            parts.append(goal_changes_header + changes)

    try:
        await status_msg.edit_text(
            "\n".join(parts),
            reply_markup=_confirm_keyboard(session_type),
        )
    except Exception:
        await status_msg.edit_text(
            "\n".join(parts),
            parse_mode=None,
            reply_markup=_confirm_keyboard(session_type),
        )


# ---------------------------------------------------------------------------
# Resume callbacks
# ---------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^grow_\w+_resume_(yes|restart|cancel)$"))
async def handle_resume(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Handle draft-resume decision."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    raw = callback.data or ""
    parts = raw.split("_")
    # grow_{abbr}_resume_{action}
    abbr = parts[1]
    action = parts[3]
    session_type = ABBR_TYPE.get(abbr)
    if session_type is None:
        logger.warning("Unknown abbreviation in resume callback: %s", abbr)
        return

    settings = get_settings()
    vault_path = settings.vault_path
    period = get_period_for_session(session_type)

    await msg.edit_reply_markup(reply_markup=None)

    if action == "yes":
        draft = load_draft(session_type, period, vault_path)
        if draft is None:
            await msg.answer("Черновик не найден. Начинаю заново.")
            await start_grow_session(bot, msg.chat.id, session_type, state)
            return

        await state.set_state(GrowStates.answering)
        await state.set_data(draft)

        idx = draft.get("current_index", 0)
        questions = draft.get("questions", [])
        if idx < len(questions):
            await _send_question(
                bot, msg.chat.id, questions[idx], session_type, idx, len(questions)
            )
        else:
            await _finalize_session(bot, msg.chat.id, state)

    elif action == "restart":
        delete_draft(session_type, period, vault_path)
        await start_grow_session(bot, msg.chat.id, session_type, state)

    elif action == "cancel":
        delete_draft(session_type, period, vault_path)
        await state.clear()
        await msg.answer("GROW-сессия отменена.")


# ---------------------------------------------------------------------------
# Question action callbacks (done / skip / next)
# ---------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^grow_\w+_\d+_(done|skip|next)$"))
async def handle_question_action(
    callback: CallbackQuery, bot: Bot, state: FSMContext,
) -> None:
    """Handle done / skip / next for the current question."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    raw = callback.data or ""
    # grow_{abbr}_{idx}_{action}
    parts = raw.split("_")
    abbr = parts[1]
    idx = int(parts[2])
    action = parts[3]

    session_type = ABBR_TYPE.get(abbr)
    if session_type is None:
        logger.warning("Unknown abbreviation in question callback: %s", abbr)
        return

    data = await state.get_data()
    questions: list[dict] = data.get("questions", [])
    answers: dict = data.get("answers", {})
    current_messages: list[str] = data.get("current_messages", [])
    deferred_questions: list[dict] = data.get("deferred_questions", [])
    deferred_count: dict[str, int] = data.get("deferred_count", {})

    settings = get_settings()
    vault_path = settings.vault_path
    period: str = data.get("period", get_period_for_session(session_type))

    if idx >= len(questions):
        logger.warning("Question index %d out of range (total %d)", idx, len(questions))
        return

    question = questions[idx]
    qid = question["id"]

    await msg.edit_reply_markup(reply_markup=None)

    if action == "done":
        if not current_messages:
            await callback.answer("Сначала напиши или надиктуй ответ.", show_alert=True)
            # Re-show keyboard
            kb = _question_keyboard(session_type, idx)
            await msg.edit_reply_markup(reply_markup=kb)
            return
        answers[qid] = list(current_messages)
        current_messages = []

    elif action == "skip":
        answers[qid] = "skipped"
        current_messages = []

    elif action == "next":
        count = deferred_count.get(qid, 0)
        if count >= 2:
            # Auto-skip after 2 deferrals
            answers[qid] = "skipped"
            current_messages = []
        else:
            deferred_count[qid] = count + 1
            deferred_questions.append(question)
            current_messages = []

    # Advance index
    new_index = idx + 1

    # Update data
    data["answers"] = answers
    data["current_messages"] = current_messages
    data["deferred_questions"] = deferred_questions
    data["deferred_count"] = deferred_count
    data["current_index"] = new_index

    if new_index >= len(questions):
        # Check deferred
        if deferred_questions:
            # Re-queue deferred at the end — deduplicate to prevent accumulation
            # on session resume after restart
            already_queued = {q["id"] for q in questions}
            to_add = [q for q in deferred_questions if q["id"] not in already_queued]
            if to_add:
                questions.extend(to_add)
                data["questions"] = questions
            data["deferred_questions"] = []
            # new_index still valid — it points to first deferred (if any added)
            if not to_add:
                # All deferred already in queue (e.g. after resume) — finalize
                await state.set_data(data)
                save_draft(session_type, period, data, vault_path)
                await _finalize_session(bot, msg.chat.id, state)
                return
        else:
            # All done — finalize
            await state.set_data(data)
            save_draft(session_type, period, data, vault_path)
            await _finalize_session(bot, msg.chat.id, state)
            return

    await state.set_data(data)
    save_draft(session_type, period, data, vault_path)

    # Send next question
    next_q = questions[new_index]
    await _send_question(
        bot, msg.chat.id, next_q, session_type, new_index, len(questions)
    )


# ---------------------------------------------------------------------------
# Confirm / correct callbacks
# ---------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^grow_\w+_confirm$"))
async def handle_confirm(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Confirm the analysis and finalize."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    session_type: str = data["session_type"]
    period: str = data["period"]
    summary: str = data.get("summary", "")
    questions: list[dict] = data.get("questions", [])
    answers: dict = data.get("answers", {})
    goal_updates = data.get("goal_updates")
    process_goals: list[dict] = data.get("process_goals") or []

    settings = get_settings()
    vault_path = settings.vault_path

    # Save final reflection markdown
    finalize_reflection(
        session_type, period, summary, questions, answers, vault_path, process_goals,
    )

    # For monthly sessions: archive old 2-monthly.md and generate new one
    if session_type == "monthly":
        monthly_path = vault_path / "goals" / "2-monthly.md"
        if monthly_path.exists():
            # Detect period of file being archived from frontmatter
            old_text = monthly_path.read_text(encoding="utf-8")
            m = re.search(r"^period:\s*(\S+)", old_text, re.MULTILINE)
            old_period = m.group(1) if m else f"{period}-prev"
            archive_path = vault_path / "goals" / f"2-monthly-{old_period}.md"
            archive_path.write_text(old_text, encoding="utf-8")
            logger.info("Archived 2-monthly.md → 2-monthly-%s.md", old_period)

        # Generate new 2-monthly.md via Claude
        status_new = await bot.send_message(
            msg.chat.id, "⏳ Генерирую план на месяц..."
        )
        processor = get_processor()
        try:
            gen_result = await run_with_progress(
                processor.generate_next_monthly_goals,
                status_new, "⏳ Генерирую...",
                summary, period, process_goals,
            )
            new_content = gen_result.get("content", "")
            if new_content:
                monthly_path.write_text(new_content, encoding="utf-8")
                await status_new.edit_text(
                    f"📅 <b>2-monthly.md обновлён</b> (период {period})\n"
                    f"Архив: <code>2-monthly-{old_period}.md</code>"
                    if monthly_path.exists() else
                    f"📅 <b>2-monthly.md создан</b> (период {period})"
                )
            else:
                await status_new.edit_text("⚠️ Не удалось сгенерировать план на месяц")
        except BusyError as e:
            await status_new.edit_text(str(e))

    # Apply goal updates if present
    if goal_updates and isinstance(goal_updates, dict):
        goal_file = goal_updates.get("file")
        sections = goal_updates.get("sections")
        if goal_file and sections:
            goal_path = vault_path / goal_file
            update_goals(goal_path, sections)

    # Git commit
    git = get_git()
    sync_warning = ""
    try:
        ok, reason = await asyncio.to_thread(
            git.commit_and_push, f"GROW {session_type} reflection {period}",
        )
        if not ok:
            sync_warning = f"\n\n\u26a0\ufe0f Vault not synced: {reason[:80]}"
    except Exception:
        logger.exception("Git commit failed after GROW finalize")
        sync_warning = "\n\n\u26a0\ufe0f Git commit failed"

    await state.clear()
    await bot.send_message(
        msg.chat.id,
        f"\u2705 GROW-рефлексия <b>{html_escape(session_type)}</b> "
        f"за <code>{html_escape(period)}</code> сохранена.{sync_warning}",
    )


@router.callback_query(F.data.regexp(r"^grow_\w+_correct$"))
async def handle_correct(callback: CallbackQuery, state: FSMContext) -> None:
    """Switch to correction mode so the user can adjust the summary."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)
    await state.set_state(GrowStates.correcting)
    await msg.answer(
        "Напиши, что хочешь изменить в итогах. "
        "Я пересоберу анализ с учётом твоих правок."
    )


# ---------------------------------------------------------------------------
# Message handlers (FSM states)
# ---------------------------------------------------------------------------


@router.message(GrowStates.answering)
async def handle_grow_answering(message: Message, bot: Bot, state: FSMContext) -> None:
    """Accumulate text/voice messages as answers to the current question."""
    if message.text and message.text.startswith("/"):
        return

    text: str | None = None

    if message.voice:
        await message.chat.do(action="typing")
        text = await transcribe_voice(bot, message)
        if not text:
            return
        await message.answer(f"\U0001f3a4 <i>{html_escape(text)}</i>")
    elif message.text:
        text = message.text
    else:
        await message.answer("Отправь текст или голосовое сообщение.")
        return

    data = await state.get_data()
    current_messages: list[str] = data.get("current_messages", [])
    current_messages.append(text)
    data["current_messages"] = current_messages
    await state.set_data(data)

    # Persist draft
    session_type = data.get("session_type", "")
    period = data.get("period", "")
    if session_type and period:
        settings = get_settings()
        save_draft(session_type, period, data, settings.vault_path)

    await message.answer("\u2714")


@router.message(GrowStates.correcting)
async def handle_grow_correcting(message: Message, bot: Bot, state: FSMContext) -> None:
    """Re-run analysis with user's correction instructions."""
    if message.text and message.text.startswith("/"):
        return

    correction: str | None = None

    if message.voice:
        await message.chat.do(action="typing")
        correction = await transcribe_voice(bot, message)
        if not correction:
            return
        await message.answer(f"\U0001f3a4 <i>{html_escape(correction)}</i>")
    elif message.text:
        correction = message.text
    else:
        await message.answer("Отправь текст или голосовое сообщение.")
        return

    data = await state.get_data()
    session_type: str = data["session_type"]
    questions: list[dict] = data.get("questions", [])
    answers: dict = data.get("answers", {})

    status_msg = await message.answer("\u23f3 Пересобираю анализ...")
    result = await analyze_answers(
        session_type, questions, answers, correction=correction,
    )

    summary: str = result.get("summary", "")
    goal_updates = result.get("goal_updates")
    process_goals: list[dict] = result.get("process_goals") or []

    data["summary"] = summary
    data["goal_updates"] = goal_updates
    data["process_goals"] = process_goals
    data["answers"] = answers
    await state.set_data(data)
    await state.set_state(GrowStates.confirming)

    parts: list[str] = [f"\U0001f4cb <b>Итог рефлексии</b>\n\n{html_escape(summary)}"]
    if goal_updates and isinstance(goal_updates, dict):
        sections = goal_updates.get("sections", {})
        if sections:
            changes = "\n".join(
                f"  \u2022 <b>{html_escape(k)}</b>: {html_escape(str(v))}"
                for k, v in sections.items()
            )
            goal_changes_header = "\n\U0001f4dd <b>Предложенные изменения целей:</b>\n"
            parts.append(goal_changes_header + changes)

    try:
        await status_msg.edit_text(
            "\n".join(parts),
            reply_markup=_confirm_keyboard(session_type),
        )
    except Exception:
        await status_msg.edit_text(
            "\n".join(parts),
            parse_mode=None,
            reply_markup=_confirm_keyboard(session_type),
        )


# ---------------------------------------------------------------------------
# Trigger callbacks (from weekly / monthly reports)
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "weekly_grow")
async def handle_weekly_grow(
    callback: CallbackQuery, bot: Bot, state: FSMContext
) -> None:
    """Start weekly GROW session from report button."""
    await callback.answer()
    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return
    await msg.edit_reply_markup(reply_markup=None)
    await start_grow_session(bot, msg.chat.id, "weekly", state)


@router.callback_query(F.data == "monthly_grow")
async def handle_monthly_grow(
    callback: CallbackQuery, bot: Bot, state: FSMContext
) -> None:
    """Start monthly GROW session from report button."""
    await callback.answer()
    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return
    await msg.edit_reply_markup(reply_markup=None)
    await start_grow_session(bot, msg.chat.id, "monthly", state)


@router.callback_query(F.data == "quarterly_grow")
async def handle_quarterly_grow(
    callback: CallbackQuery, bot: Bot, state: FSMContext,
) -> None:
    """Start quarterly GROW session from report button."""
    await callback.answer()
    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return
    await msg.edit_reply_markup(reply_markup=None)
    await start_grow_session(bot, msg.chat.id, "quarterly", state)


@router.callback_query(F.data == "yearly_end_grow")
async def handle_yearly_end_grow(
    callback: CallbackQuery, bot: Bot, state: FSMContext,
) -> None:
    """Start yearly-end GROW session."""
    await callback.answer()
    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return
    await msg.edit_reply_markup(reply_markup=None)
    await start_grow_session(bot, msg.chat.id, "yearly_end", state)


@router.callback_query(F.data == "yearly_start_grow")
async def handle_yearly_start_grow(
    callback: CallbackQuery, bot: Bot, state: FSMContext,
) -> None:
    """Start yearly-start GROW session."""
    await callback.answer()
    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return
    await msg.edit_reply_markup(reply_markup=None)
    await start_grow_session(bot, msg.chat.id, "yearly_start", state)
