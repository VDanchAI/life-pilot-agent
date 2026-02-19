#!/usr/bin/env python3
"""Отправляет месячный чек в Telegram"""

import asyncio
import sys

sys.path.insert(0, '/home/ubuntu/agent-second-brain/src')

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from d_brain.config import get_settings
from d_brain.services.processor import ClaudeProcessor


async def send_monthly_check():
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    
    processor = ClaudeProcessor(
        vault_path=settings.vault_path,
        todoist_api_key=settings.todoist_api_key
    )
    
    try:
        result = processor.generate_monthly()
        report = result.get('report', 'Ошибка генерации отчёта')
        
        # Кнопка для месячного отчёта
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Обновить цели на месяц", callback_data="monthly_update_goals"),
                InlineKeyboardButton(text="✓ Оставить как есть", callback_data="monthly_keep_goals")
            ]
        ])
        
        chat_id = settings.allowed_user_ids[0]
        await bot.send_message(
            chat_id=chat_id, 
            text=report, 
            parse_mode='HTML',
            reply_markup=keyboard
        )
        print("✅ Месячный чек отправлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(send_monthly_check())
