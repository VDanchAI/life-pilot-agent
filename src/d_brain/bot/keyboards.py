"""Reply keyboards for Telegram bot."""

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard with common commands."""
    builder = ReplyKeyboardBuilder()
    # Row 1: Активные инструменты
    builder.button(text="🤖 Сделать")
    builder.button(text="🔍 Найти")
    builder.button(text="🤝 Коуч")
    # Row 2: Планирование и разбор
    builder.button(text="🧹 Разобрать день")
    builder.button(text="📋 План")
    builder.button(text="📅 Неделя")
    # Row 3: Информация и помощь
    builder.button(text="📊 Статус")
    builder.button(text="ℹ️ Помощь")
    builder.button(text="🎲 Находка")
    # Row 4: Техническое здоровье
    builder.button(text="🏥 Здоровье")
    builder.button(text="🧠 Память")
    
    builder.adjust(3, 3, 3, 2)
    return builder.as_markup(resize_keyboard=True, is_persistent=True)
