"""Voice message handler."""

import logging
from datetime import datetime
from html import escape as html_escape

from aiogram import Bot, Router
from aiogram.types import Message

from d_brain.bot.utils import download_telegram_file
from d_brain.config import get_settings
from d_brain.services.storage import VaultStorage
from d_brain.services.transcription import DeepgramTranscriber

router = Router(name="voice")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.voice is not None)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Handle voice messages."""
    if not message.voice or not message.from_user:
        return

    await message.chat.do(action="typing")

    settings = get_settings()
    storage = VaultStorage(settings.vault_path)
    transcriber = DeepgramTranscriber(
        settings.deepgram_api_key, settings.transcription_language,
    )

    try:
        audio_bytes, _ = await download_telegram_file(bot, message.voice.file_id)
        transcript = await transcriber.transcribe(audio_bytes)

        if not transcript:
            await message.answer("Could not transcribe audio")
            return

        timestamp = datetime.fromtimestamp(message.date.timestamp())
        storage.append_to_daily(transcript, timestamp, "[voice]")

        await message.answer(f"🎤 {html_escape(transcript)}\n\n✓ Сохранено")
        logger.info("Voice message saved: %d chars", len(transcript))

    except Exception as e:
        logger.exception("Error processing voice message")
        await message.answer(f"Error: {e}")
