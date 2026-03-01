"""Handler for /do command - arbitrary Claude requests."""

import logging
from html import escape as html_escape

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from d_brain.bot.progress import BusyError, run_with_progress
from d_brain.bot.states import DoCommandState
from d_brain.bot.utils import send_formatted_report, transcribe_voice
from d_brain.services.factory import get_processor

router = Router(name="do")
logger = logging.getLogger(__name__)


@router.message(Command("do"))
async def cmd_do(message: Message, command: CommandObject, state: FSMContext) -> None:
    """Handle /do command."""
    if command.args:
        await process_request(message, command.args)
        return

    await state.set_state(DoCommandState.waiting_for_input)
    await message.answer(
        "🎯 <b>Что сделать?</b>\n\n"
        "Отправь голосовое или текстовое сообщение с запросом."
    )


@router.message(DoCommandState.waiting_for_input)
async def handle_do_input(message: Message, bot: Bot, state: FSMContext) -> None:
    """Handle voice/text input after /do command."""
    await state.clear()

    prompt = None

    if message.voice:
        await message.chat.do(action="typing")
        prompt = await transcribe_voice(bot, message)
        if not prompt:
            return
        await message.answer(f"🎤 <i>{html_escape(prompt)}</i>")

    elif message.text:
        prompt = message.text

    else:
        await message.answer("❌ Отправь текст или голосовое сообщение")
        return

    await process_request(message, prompt)


async def process_request(message: Message, prompt: str) -> None:
    """Process the user's request with Claude."""
    status_msg = await message.answer("⏳ Выполняю...")

    processor = get_processor()

    try:
        report = await run_with_progress(
            processor.execute_prompt, status_msg,
            "⏳ Выполняю...", prompt,
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        return

    await send_formatted_report(status_msg, report)
