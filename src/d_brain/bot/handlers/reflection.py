"""Friday reflection handler — DEPRECATED, replaced by GROW weekly.

Kept as a minimal stub to handle old inline buttons in existing Telegram messages.
Old buttons (reflection_reply, reflection_skip) redirect users to /grow.
"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from d_brain.bot.states import ReflectionStates

router = Router(name="reflection")
logger = logging.getLogger(__name__)

_DEPRECATED_MSG = (
    "Эта функция заменена на GROW-рефлексию.\n"
    "Используй /grow для еженедельной рефлексии."
)


@router.callback_query(F.data == "reflection_reply")
async def handle_reflection_reply(callback: CallbackQuery, state: FSMContext) -> None:
    """Redirect old reflection_reply buttons to GROW."""
    await callback.answer(_DEPRECATED_MSG, show_alert=True)
    msg = callback.message
    if msg and not isinstance(msg, InaccessibleMessage):
        await msg.edit_reply_markup(reply_markup=None)
    await state.clear()


@router.callback_query(F.data == "reflection_skip")
async def handle_reflection_skip(callback: CallbackQuery) -> None:
    """Handle old reflection_skip buttons."""
    await callback.answer("Пропущено")
    msg = callback.message
    if msg and not isinstance(msg, InaccessibleMessage):
        await msg.edit_reply_markup(reply_markup=None)


@router.message(ReflectionStates.waiting_response)
async def handle_legacy_reflection_input(
    message: Message, state: FSMContext,
) -> None:
    """Clear stuck FSM state from old reflection sessions."""
    await state.clear()
    await message.answer(_DEPRECATED_MSG)
