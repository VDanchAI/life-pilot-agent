"""Button handlers for reply keyboard."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from d_brain.bot.states import DoCommandState

router = Router(name="buttons")


@router.message(F.text == "📋 План")
async def btn_plan(message: Message) -> None:
    """Handle Plan button."""
    from d_brain.bot.handlers.commands import cmd_plan

    await cmd_plan(message)


@router.message(F.text == "⚙️ Обработать")
async def btn_process(message: Message, state: FSMContext) -> None:
    """Handle Process button."""
    from d_brain.bot.handlers.process import cmd_process

    await cmd_process(message, state)


@router.message(F.text == "📅 Неделя")
async def btn_weekly(message: Message) -> None:
    """Handle Weekly button."""
    from d_brain.bot.handlers.weekly import cmd_weekly

    await cmd_weekly(message)


@router.message(F.text == "📌 Задача")
async def btn_recall(message: Message, state: FSMContext) -> None:
    """Handle Recall button — enter search FSM."""
    from d_brain.bot.handlers.recall import cmd_recall

    await cmd_recall(message, state, command=None)


@router.message(F.text == "✨ Запрос")
async def btn_do(message: Message, state: FSMContext) -> None:
    """Handle Do button - set state and wait for input."""
    await state.set_state(DoCommandState.waiting_for_input)
    await message.answer(
        "🎯 <b>Что сделать?</b>\n\n"
        "Отправь голосовое или текстовое сообщение с запросом."
    )


@router.message(F.text == "📊 Статус")
async def btn_status(message: Message) -> None:
    """Handle Status button."""
    from d_brain.bot.handlers.commands import cmd_status

    await cmd_status(message)


@router.message(F.text == "🏥 Здоровье")
async def btn_health(message: Message) -> None:
    """Handle Health button."""
    from d_brain.bot.handlers.vault_tools import cmd_health

    await cmd_health(message)


@router.message(F.text == "🧠 Память")
async def btn_memory(message: Message) -> None:
    """Handle Memory button."""
    from d_brain.bot.handlers.vault_tools import cmd_memory

    await cmd_memory(message)


@router.message(F.text == "🎲 Находка")
async def btn_creative(message: Message) -> None:
    """Handle Creative button."""
    from d_brain.bot.handlers.vault_tools import cmd_creative

    await cmd_creative(message, command=None)
