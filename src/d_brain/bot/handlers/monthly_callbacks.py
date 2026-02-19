"""Обработчики кнопок месячного отчёта"""

import asyncio
import json
import logging
from html import escape as html_escape
from pathlib import Path
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from d_brain.bot.components.task_keyboard import handle_task_action
from d_brain.bot.states import MonthlyStates
from d_brain.config import get_settings
from d_brain.services.factory import get_todoist

router = Router(name="monthly_callbacks")
logger = logging.getLogger(__name__)


def _set_monthly_processed(vault_path: Path) -> None:
    """Set vault/.monthly_flag processed=true."""
    flag_path = vault_path / ".monthly_flag"
    data: dict[str, Any] = {}
    if flag_path.exists():
        try:
            data = json.loads(flag_path.read_text())
        except Exception:
            pass
    data["processed"] = True
    flag_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ── Per-task action handlers (ТЗ 3) ──────────────────────────────────


@router.callback_query(
    F.data.regexp(r"^monthly_(move|delete|done|skip)_.+$")
)
async def monthly_task_action(callback: CallbackQuery) -> None:
    """Delegate per-task actions to universal handler and mark monthly as processed."""
    action_part = (callback.data or "").split("_")[1]

    await handle_task_action(callback)

    # Mark monthly as processed for any action except skip
    if action_part != "skip":
        try:
            settings = get_settings()
            _set_monthly_processed(settings.vault_path)
        except Exception as e:
            logger.warning("Failed to update monthly flag: %s", e)


# ── Reformulation FSM (ТЗ 3) ─────────────────────────────────────────


@router.callback_query(
    F.data.regexp(r"^monthly_reformulate_.+$")
)
async def handle_reformulate_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start reformulation FSM — ask for new task wording."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    task_id = (callback.data or "").removeprefix("monthly_reformulate_")
    task_text = msg.text or msg.caption or ""

    await state.set_state(MonthlyStates.waiting_reformulation)
    await state.set_data({
        "task_id": task_id,
        "original_text": task_text,
        "msg_id": msg.message_id,
    })

    await msg.edit_reply_markup(reply_markup=None)
    await msg.answer(
        "✏️ <b>Новая формулировка задачи:</b>\n\n"
        f"Текущая: <i>{html_escape(task_text)}</i>\n\n"
        "Напиши новую формулировку:"
    )


@router.message(MonthlyStates.waiting_reformulation)
async def handle_reformulation_input(message: Message, state: FSMContext) -> None:
    """Receive new task wording and update in Todoist."""
    if message.text and message.text.startswith("/"):
        await state.clear()
        return

    if not message.text:
        await message.answer("Отправь текстовую формулировку")
        return

    data = await state.get_data()
    task_id = data.get("task_id", "")
    new_content = message.text.strip()

    await state.clear()

    todoist = get_todoist()
    if not todoist:
        await message.answer("❌ Todoist API key не настроен")
        return

    success = await asyncio.to_thread(
        todoist.update_content, task_id, new_content,
    )
    if success:
        await message.answer(
            f"✅ Задача переформулирована:\n"
            f"<i>{html_escape(new_content)}</i>"
        )
        settings = get_settings()
        _set_monthly_processed(settings.vault_path)
    else:
        await message.answer("❌ Ошибка при обращении к Todoist")


# ── Legacy goal handlers (unchanged) ─────────────────────────────────


@router.callback_query(F.data == "monthly_update_goals")
async def handle_update_goals(callback: CallbackQuery) -> None:
    """Redirect to GROW session for monthly goal review."""
    await callback.answer("Запускаю GROW-рефлексию...")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="Начать рефлексию", callback_data="monthly_grow")
    await msg.answer(
        "Давай проведём GROW-рефлексию по итогам месяца.\n"
        "Это займёт 10-15 минут.",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "monthly_keep_goals")
async def handle_keep_goals(callback: CallbackQuery) -> None:
    """Оставить цели без изменений"""
    await callback.answer("Отлично")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.answer("Цели на месяц остаются прежними")
