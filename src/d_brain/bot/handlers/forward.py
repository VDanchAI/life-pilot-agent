"""Forwarded message handler."""

import logging
from datetime import datetime
from html import escape as html_escape

from aiogram import Router
from aiogram.types import (
    Message,
    MessageOriginChannel,
    MessageOriginChat,
    MessageOriginHiddenUser,
    MessageOriginUser,
)

from d_brain.config import get_settings
from d_brain.services.storage import VaultStorage

router = Router(name="forward")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.forward_origin is not None)
async def handle_forward(message: Message) -> None:
    """Handle forwarded messages."""
    if not message.from_user:
        return

    settings = get_settings()
    storage = VaultStorage(settings.vault_path)

    # Determine source name
    source_name = "Unknown"
    origin = message.forward_origin

    if isinstance(origin, MessageOriginUser) and origin.sender_user:
        source_name = origin.sender_user.full_name
    elif isinstance(origin, MessageOriginHiddenUser):
        source_name = origin.sender_user_name
    elif isinstance(origin, MessageOriginChannel) and origin.chat:
        chat = origin.chat
        source_name = f"@{chat.username}" if chat.username else chat.title or "Channel"
    elif isinstance(origin, MessageOriginChat) and origin.sender_chat:
        chat = origin.sender_chat
        source_name = f"@{chat.username}" if chat.username else chat.title or "Chat"

    content = message.text or message.caption or "[media]"
    msg_type = f"[forward from: {source_name}]"

    timestamp = datetime.fromtimestamp(message.date.timestamp())
    storage.append_to_daily(content, timestamp, msg_type)

    await message.answer(f"✓ Сохранено (от {html_escape(source_name)})")
    logger.info("Forwarded message saved from: %s", source_name)
