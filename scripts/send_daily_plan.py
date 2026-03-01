#!/usr/bin/env python3
"""Отправляет утренний план в Telegram"""

import asyncio
import sys

import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from aiogram import Bot
from d_brain.config import get_settings
from d_brain.services.processor import ClaudeProcessor


async def send_daily_plan():
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    
    processor = ClaudeProcessor(
        vault_path=settings.vault_path,
        todoist_api_key=settings.todoist_api_key
    )
    
    try:
        plan = processor.get_daily_plan()
        await bot.send_message(
            chat_id=settings.allowed_user_ids[0],
            text=plan
        )
        print("✅ План отправлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(send_daily_plan())
