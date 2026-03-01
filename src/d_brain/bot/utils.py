"""Shared bot utilities."""

import logging
from typing import Any

from aiogram import Bot
from aiogram.types import Message

from d_brain.bot.formatters import format_process_report

logger = logging.getLogger(__name__)


async def download_telegram_file(bot: Bot, file_id: str) -> tuple[bytes, str]:
    """Download a file from Telegram servers.

    Args:
        bot: Aiogram Bot instance.
        file_id: Telegram file ID to download.

    Returns:
        Tuple of (file_bytes, file_path).

    Raises:
        ValueError: If file_path is missing or download returns empty result.
    """
    file = await bot.get_file(file_id)
    if not file.file_path:
        raise ValueError("Telegram returned no file_path")

    file_bytes = await bot.download_file(file.file_path)
    if not file_bytes:
        raise ValueError("Telegram returned empty file content")

    return file_bytes.read(), file.file_path


async def send_formatted_report(
    status_msg: Message,
    report: dict[str, Any],
) -> None:
    """Format a Claude report and edit status message, with HTML fallback.

    Args:
        status_msg: Telegram message to edit with the formatted report.
        report: Report dict from ClaudeProcessor (contains "report" or "error").
    """
    formatted = format_process_report(report)
    try:
        await status_msg.edit_text(formatted)
    except Exception:
        await status_msg.edit_text(formatted, parse_mode=None)


async def transcribe_voice(bot: Bot, message: "Message") -> str | None:
    """Download voice message, transcribe via Deepgram, return text or None.

    On failure, sends an error message to the user and returns None.
    """
    from d_brain.config import get_settings
    from d_brain.services.transcription import DeepgramTranscriber

    settings = get_settings()
    transcriber = DeepgramTranscriber(
        settings.deepgram_api_key, settings.transcription_language,
    )
    try:
        audio_bytes, _ = await download_telegram_file(
            bot, message.voice.file_id
        )
        text = await transcriber.transcribe(audio_bytes)
        if not text:
            await message.answer("❌ Не удалось распознать речь")
            return None
        return text
    except Exception as e:
        logger.exception("Failed to transcribe voice")
        await message.answer(f"❌ Не удалось транскрибировать: {e}")
        return None
