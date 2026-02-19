"""Reusable per-task inline keyboard with Todoist action handling."""

import asyncio
import logging

from aiogram.types import CallbackQuery, InaccessibleMessage, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from d_brain.services.factory import get_todoist

logger = logging.getLogger(__name__)

# Debounce locks: one lock per task_id to prevent double-taps
_locks: dict[str, asyncio.Lock] = {}


def _get_lock(task_id: str) -> asyncio.Lock:
    if task_id not in _locks:
        _locks[task_id] = asyncio.Lock()
    return _locks[task_id]


# ── Keyboard builders ────────────────────────────────────────────────


def create_task_keyboard(
    task_id: str,
    context: str = "weekly",
) -> InlineKeyboardMarkup:
    """Build an inline keyboard for a single task.

    Args:
        task_id: Todoist task ID (used in callback_data).
        context: 'weekly' or 'monthly' — determines button set.

    Returns:
        InlineKeyboardMarkup with 4 action buttons.

    Callback data format: ``{context}_{action}_{task_id}``
    Actions: move | delete | done | skip | reformulate
    """
    builder = InlineKeyboardBuilder()

    if context == "monthly":
        builder.button(text="📅 Перенести", callback_data=f"monthly_move_{task_id}")
        builder.button(text="🗑 Удалить", callback_data=f"monthly_delete_{task_id}")
        builder.button(
            text="✏️ Переформулировать",
            callback_data=f"monthly_reformulate_{task_id}",
        )
        builder.button(text="⏭ Пропустить", callback_data=f"monthly_skip_{task_id}")
    else:  # weekly (default)
        builder.button(text="📅 Перенести", callback_data=f"weekly_move_{task_id}")
        builder.button(text="🗑 Удалить", callback_data=f"weekly_delete_{task_id}")
        builder.button(text="✅ Выполнено", callback_data=f"weekly_done_{task_id}")
        builder.button(text="⏭ Пропустить", callback_data=f"weekly_skip_{task_id}")

    builder.adjust(2, 2)
    return builder.as_markup()


# ── Universal callback handler ───────────────────────────────────────


async def handle_task_action(callback: CallbackQuery) -> None:
    """Universal handler for task action callbacks.

    Parses ``{context}_{action}_{task_id}`` from callback.data,
    calls appropriate Todoist API, and replaces message keyboard
    with a confirmation text.

    Debounce: asyncio.Lock per task_id prevents double execution.
    On error: shows ❌, leaves buttons in place.
    """
    if callback.data is None:
        await callback.answer()
        return

    parts = callback.data.split("_", 2)
    if len(parts) != 3:
        await callback.answer("Неверный формат callback")
        return

    context, action, task_id = parts

    # Skip action — no API call needed
    if action == "skip":
        await callback.answer("Пропущено")
        msg = callback.message
        if msg and not isinstance(msg, InaccessibleMessage):
            await msg.edit_reply_markup(reply_markup=None)
        return

    # Reformulate is handled separately in monthly_callbacks.py
    if action == "reformulate":
        await callback.answer()
        return

    lock = _get_lock(task_id)
    if lock.locked():
        await callback.answer("Уже обрабатывается...")
        return

    async with lock:
        await callback.answer("Выполняю...")

        msg = callback.message
        if msg is None or isinstance(msg, InaccessibleMessage):
            return

        todoist = get_todoist()
        if not todoist:
            await callback.answer(
                "❌ Todoist API key не настроен", show_alert=True,
            )
            return

        success = False
        confirm_text = ""

        if action == "move":
            success = await asyncio.to_thread(
                todoist.move_to_next_monday, task_id,
            )
            confirm_text = "📅 Перенесено на следующий понедельник"
        elif action == "delete":
            success = await asyncio.to_thread(
                todoist.delete_task, task_id,
            )
            confirm_text = "🗑 Задача удалена"
        elif action == "done":
            success = await asyncio.to_thread(
                todoist.close_task, task_id,
            )
            confirm_text = "✅ Задача выполнена"

        if success:
            original_text = msg.text or msg.caption or ""
            await msg.edit_text(
                f"{original_text}\n\n{confirm_text}",
                reply_markup=None,
            )
        else:
            await callback.answer(
                "❌ Ошибка при обращении к Todoist", show_alert=True,
            )
