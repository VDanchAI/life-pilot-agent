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
    builder.button(text="📊 Статус")
    # Row 3
    builder.button(text="🏥 Здоровье")
    builder.button(text="🧠 Память")
    builder.button(text="🎲 Находка")
    # Row 4
    builder.button(text="🤝 Коуч")
    builder.adjust(3, 3, 3, 1)
    return builder.as_markup(resize_keyboard=True, is_persistent=True)
