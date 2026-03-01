"""Text message handler."""

import logging
import re
from datetime import datetime

from aiogram import Router
from aiogram.types import Message

from d_brain.bot.progress import BusyError, run_with_progress
from d_brain.bot.utils import send_formatted_report
from d_brain.config import get_settings
from d_brain.services.factory import get_processor
from d_brain.services.storage import VaultStorage

router = Router(name="text")
logger = logging.getLogger(__name__)

_ZOOM_OUT_RE = re.compile(
    r"zoom\s*out|погряз|нет смысла|потерял нить|большая картина|зачем всё это",
    re.IGNORECASE,
)
_ZOOM_IN_RE = re.compile(
    r"zoom\s*in|витаю в облаках|что делать сегодня|с чего начать"
    r"|потерялся|за что хвататься|не знаю с чего|не понимаю что делать",
    re.IGNORECASE,
)


@router.message(lambda m: m.text is not None and not m.text.startswith("/"))
async def handle_text(message: Message) -> None:
    """Handle text messages (excluding commands)."""
    if not message.text or not message.from_user:
        return

    text = message.text

    # Zoom Out: big-picture mode
    if _ZOOM_OUT_RE.search(text):
        status_msg = await message.answer("🔭 Смотрю на большую картину...")
        processor = get_processor()
        try:
            report = await run_with_progress(
                processor.zoom_out, status_msg, "🔭 Смотрю на большую картину...",
            )
        except BusyError as e:
            await status_msg.edit_text(str(e))
            return
        await send_formatted_report(status_msg, report)
        return

    # Zoom In: concrete actions mode
    if _ZOOM_IN_RE.search(text):
        status_msg = await message.answer("🎯 Собираю конкретные действия...")
        processor = get_processor()
        try:
            report = await run_with_progress(
                processor.zoom_in, status_msg, "🎯 Собираю конкретные действия...",
            )
        except BusyError as e:
            await status_msg.edit_text(str(e))
            return
        await send_formatted_report(status_msg, report)
        return

    settings = get_settings()
    storage = VaultStorage(settings.vault_path)

    timestamp = datetime.fromtimestamp(message.date.timestamp())
    storage.append_to_daily(text, timestamp, "[text]")

    await message.answer("✓ Сохранено")
    logger.info("Text message saved: %d chars", len(text))
