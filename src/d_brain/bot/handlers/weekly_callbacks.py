"""Обработчики кнопок недельного отчёта"""

import asyncio

from aiogram import F, Router
from aiogram.types import CallbackQuery, InaccessibleMessage

from d_brain.bot.components.task_keyboard import handle_task_action
from d_brain.services.factory import get_processor

router = Router(name="weekly_callbacks")


# ── Per-task action handler (ТЗ 1.1) ──────────────────────────────────────
# Handles: weekly_move_{id}, weekly_delete_{id}, weekly_done_{id}, weekly_skip_{id}


@router.callback_query(
    F.data.regexp(r"^weekly_(move|delete|done|skip)_.+$")
)
async def weekly_task_action(callback: CallbackQuery) -> None:
    """Delegate per-task actions to universal handler."""
    await handle_task_action(callback)


@router.callback_query(F.data == "weekly_move_tasks")
async def handle_move_tasks(callback: CallbackQuery) -> None:
    """Перенести невыполненное на следующую неделю"""
    await callback.answer("Переношу задачи...")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    processor = get_processor()

    result = await asyncio.to_thread(
        processor.execute_prompt,
        "Перенеси все невыполненные задачи с этой недели"
        " на следующий понедельник",
    )

    await msg.answer(
        result.get('report', '✅ Задачи перенесены'),
        parse_mode='HTML',
    )


@router.callback_query(F.data == "weekly_skip_tasks")
async def handle_skip_tasks(callback: CallbackQuery) -> None:
    """Не переносить задачи"""
    await callback.answer("Понятно")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.answer("✓ Невыполненные задачи оставлены как есть")


@router.callback_query(F.data == "weekly_update_goals")
async def handle_update_goals(callback: CallbackQuery) -> None:
    """Redirect to GROW session for weekly goal review."""
    # The actual GROW session is handled by grow.router via "weekly_grow" callback.
    # Re-emit the callback as "weekly_grow" to start the GROW flow.
    await callback.answer("Запускаю GROW-рефлексию...")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="Начать рефлексию", callback_data="weekly_grow")
    await msg.answer(
        "Давай проведём GROW-рефлексию по итогам недели.\n"
        "Это займёт 5-10 минут.",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "weekly_keep_goals")
async def handle_keep_goals(callback: CallbackQuery) -> None:
    """Оставить цели без изменений"""
    await callback.answer("Отлично")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.answer("Цели на неделю остаются прежними")
