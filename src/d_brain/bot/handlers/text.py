"""Text message handler."""

import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import Message

from d_brain.config import get_settings
from d_brain.services.storage import VaultStorage

router = Router(name="text")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.text is not None and not m.text.startswith("/"))
async def handle_text(message: Message) -> None:
    """Handle text messages (excluding commands)."""
    if not message.text or not message.from_user:
        return

    settings = get_settings()
    storage = VaultStorage(settings.vault_path)

    timestamp = datetime.fromtimestamp(message.date.timestamp())
    storage.append_to_daily(message.text, timestamp, "[text]")

    await message.answer("✓ Сохранено")
    logger.info("Text message saved: %d chars", len(message.text))
