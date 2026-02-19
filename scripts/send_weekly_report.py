#!/usr/bin/env python3
"""Отправляет недельный отчёт в Telegram"""

import asyncio
import sys

sys.path.insert(0, '/home/ubuntu/agent-second-brain/src')

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from d_brain.config import get_settings
from d_brain.services.processor import ClaudeProcessor


async def send_weekly_report():
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    
    processor = ClaudeProcessor(
        vault_path=settings.vault_path,
        todoist_api_key=settings.todoist_api_key
    )
    
    try:
        result = processor.generate_weekly()
        report = result.get('report', 'Ошибка генерации отчёта')
        
        # Кнопки для недельного отчёта
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Перенести невыполненное", callback_data="weekly_move_tasks"),
                InlineKeyboardButton(text="❌ Не нужно", callback_data="weekly_skip_tasks")
            ],
            [
                InlineKeyboardButton(text="📝 Обновить цели на неделю", callback_data="weekly_update_goals"),
                InlineKeyboardButton(text="✓ Оставить как есть", callback_data="weekly_keep_goals")
            ]
        ])
        
        chat_id = settings.allowed_user_ids[0]
        await bot.send_message(
            chat_id=chat_id, 
            text=report, 
            parse_mode='HTML',
            reply_markup=keyboard
        )
        print("✅ Недельный отчёт отправлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(send_weekly_report())
