"""Reply keyboards for Telegram bot."""

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard with common commands."""
    builder = ReplyKeyboardBuilder()
    # Row 1
    builder.button(text="✨ Запрос")
    builder.button(text="📌 Задача")
    builder.button(text="⚙️ Обработать")
    # Row 2
    builder.button(text="📋 План")
    builder.button(text="📅 Неделя")
    # Row 3
    builder.button(text="📊 Статус")
    builder.button(text="❓ Помощь")
    builder.adjust(3, 2, 2)
    return builder.as_markup(resize_keyboard=True, is_persistent=True)
