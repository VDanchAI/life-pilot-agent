"""Photo message handler."""

import logging
from datetime import datetime

from aiogram import Bot, Router
from aiogram.types import Message

from d_brain.bot.utils import download_telegram_file
from d_brain.config import get_settings
from d_brain.services.storage import VaultStorage

router = Router(name="photo")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.photo is not None)
async def handle_photo(message: Message, bot: Bot) -> None:
    """Handle photo messages."""
    if not message.photo or not message.from_user:
        return

    settings = get_settings()
    storage = VaultStorage(settings.vault_path)

    # Get largest photo
    photo = message.photo[-1]

    try:
        photo_bytes, remote_path = await download_telegram_file(bot, photo.file_id)
        timestamp = datetime.fromtimestamp(message.date.timestamp())

        # Determine extension from file path
        extension = "jpg"
        if "." in remote_path:
            extension = remote_path.rsplit(".", 1)[-1]

        # Save photo and get relative path
        relative_path = storage.save_attachment(
            photo_bytes,
            timestamp.date(),
            timestamp,
            extension,
        )

        # Create content with Obsidian embed
        content = f"![[{relative_path}]]"
        if message.caption:
            content += f"\n\n{message.caption}"

        storage.append_to_daily(content, timestamp, "[photo]")

        await message.answer("📷 ✓ Сохранено")
        logger.info("Photo saved: %s", relative_path)

    except Exception as e:
        logger.exception("Error processing photo")
        await message.answer(f"Error: {e}")
