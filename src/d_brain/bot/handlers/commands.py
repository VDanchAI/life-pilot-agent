"""Command handlers for /start, /help, /status, /plan."""

import asyncio
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from d_brain.bot.keyboards import get_main_keyboard
from d_brain.config import get_settings
from d_brain.services.factory import get_processor
from d_brain.services.storage import VaultStorage

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(
        "<b>d-brain</b> — твой голосовой дневник\n\n"
        "Отправляй мне:\n"
        "🎤 Голосовые сообщения\n"
        "💬 Текст\n"
        "📷 Фото\n"
        "↩️ Пересланные сообщения\n\n"
        "Всё будет сохранено и обработано.\n\n"
        "<b>Команды:</b>\n"
        "/do — выполнить произвольный запрос\n"
        "/recall — поиск по записям\n"
        "/process — обработать записи дня\n"
        "/plan — план на сегодня\n"
        "/weekly — недельный дайджест\n"
        "/monthly — месячный отчёт\n"
        "/status — статус сегодняшнего дня\n"
        "/help — справка",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "<b>Как использовать d-brain:</b>\n\n"
        "1. Отправь голосовое — я транскрибирую и сохраню\n"
        "2. Отправь текст — сохраню как есть\n"
        "3. Отправь фото — сохраню в attachments\n"
        "4. Перешли сообщение — сохраню с источником\n\n"
        "Вечером используй /process для обработки:\n"
        "Мысли → Obsidian, Задачи → Todoist\n\n"
        "<b>Команды:</b>\n"
        "/do — выполнить произвольный запрос\n"
        "/recall — поиск по записям vault\n"
        "/process — обработать записи дня\n"
        "/plan — план на сегодня из Todoist\n"
        "/weekly — недельный дайджест\n"
        "/monthly — месячный отчёт\n"
        "/status — сколько записей сегодня\n\n"
        "<i>Пример: /do перенеси просроченные задачи на понедельник</i>\n"
        "<i>Пример: /recall встречи с командой</i>"
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """Handle /status command."""
    settings = get_settings()
    storage = VaultStorage(settings.vault_path)

    today = date.today()
    content = storage.read_daily(today)

    if not content:
        await message.answer(f"📅 <b>{today}</b>\n\nЗаписей пока нет.")
        return

    lines = content.strip().split("\n")
    entries = [line for line in lines if line.startswith("## ")]

    voice_count = sum(1 for e in entries if "[voice]" in e)
    text_count = sum(1 for e in entries if "[text]" in e)
    photo_count = sum(1 for e in entries if "[photo]" in e)
    forward_count = sum(1 for e in entries if "[forward from:" in e)

    total = len(entries)

    await message.answer(
        f"📅 <b>{today}</b>\n\n"
        f"Всего записей: <b>{total}</b>\n"
        f"- 🎤 Голосовых: {voice_count}\n"
        f"- 💬 Текстовых: {text_count}\n"
        f"- 📷 Фото: {photo_count}\n"
        f"- ↩️ Пересланных: {forward_count}"
    )

@router.message(Command("plan"))
async def cmd_plan(message: Message) -> None:
    """Handle /plan command - daily plan."""
    processor = get_processor()

    try:
        plan = await asyncio.to_thread(processor.get_daily_plan)
        await message.answer(plan, reply_markup=get_main_keyboard())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
