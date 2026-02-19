"""Friday reflection questions handler (ТЗ 4)."""

import asyncio
import logging
from datetime import date, datetime, timedelta
from html import escape as html_escape
from pathlib import Path

import pytz
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from d_brain.bot.states import ReflectionStates
from d_brain.bot.utils import transcribe_voice
from d_brain.config import get_settings
from d_brain.services.factory import get_runner, get_todoist
from d_brain.services.vault_search import search_vault

router = Router(name="reflection")
logger = logging.getLogger(__name__)

_TZ = pytz.timezone("Europe/Kyiv")


# ── Keyboard ──────────────────────────────────────────────────────────


def _reply_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Ответить", callback_data="reflection_reply")
    builder.button(text="⏭ Пропустить", callback_data="reflection_skip")
    builder.adjust(2)
    return builder.as_markup()


# ── Data collection ───────────────────────────────────────────────────


def _collect_reflection_context(vault_path: Path) -> str:
    """Collect last 7 days of daily notes, goals, and vault search results."""
    context_parts: list[str] = []

    daily_dir = vault_path / "daily"
    if daily_dir.exists():
        daily_entries = []
        today = date.today()
        for i in range(7):
            day = today - timedelta(days=i)
            f = daily_dir / f"{day.isoformat()}.md"
            if f.exists():
                content = f.read_text(encoding="utf-8", errors="replace")[:500]
                daily_entries.append(f"### {day.isoformat()}\n{content}")
        if daily_entries:
            context_parts.append(
                "## Дневник за 7 дней:\n" + "\n\n".join(daily_entries)
            )

    monthly_goal_file = vault_path / "goals" / "2-monthly.md"
    keywords: list[str] = []
    if monthly_goal_file.exists():
        goal_text = monthly_goal_file.read_text()
        context_parts.append(f"## Месячные цели:\n{goal_text[:800]}")
        words = [w.strip(".,!?:;()[]") for w in goal_text.split() if len(w) > 4]
        keywords = list(dict.fromkeys(words))[:5]

    if keywords:
        search_results = search_vault(
            keywords, limit=3, max_chars=400, vault_path=vault_path
        )
        if search_results:
            parts = []
            for r in search_results:
                parts.append(
                    f"- [{r['date']} / {r['category']}]: {r['content'][:200]}"
                )
            context_parts.append("## Релевантные записи:\n" + "\n".join(parts))

    todoist = get_todoist()
    if todoist:
        try:
            tasks = todoist.fetch_active_tasks()
            if tasks:
                today_str = date.today().isoformat()
                overdue = [
                    t for t in tasks
                    if t.get("due") and t["due"].get("date", "") < today_str
                ]
                task_lines = [f"- {t['content']}" for t in tasks[:10]]
                summary = f"Всего активных: {len(tasks)}"
                if overdue:
                    summary += f", просрочено: {len(overdue)}"
                context_parts.append(
                    f"## Задачи ({summary}):\n" + "\n".join(task_lines)
                )
        except Exception as e:
            logger.warning("Failed to fetch tasks for reflection: %s", e)

    return "\n\n".join(context_parts)


# ── Core generation ───────────────────────────────────────────────────


async def _generate_and_send_reflection(bot: Bot, chat_id: int) -> None:
    """Generate reflection questions and send to user."""
    settings = get_settings()

    context = await asyncio.to_thread(
        _collect_reflection_context, settings.vault_path,
    )

    today = date.today()

    prompt = f"""Сегодня {today} (пятница). Сгенерируй рефлексивные вопросы.
Тема: обзор прошедшей недели.

КОНТЕКСТ:
{context}

ЗАДАЧА: Задай 3-4 конкретных рефлексивных вопроса на основе паттернов из данных.

Хорошие вопросы (конкретные, на основе данных):
- "Ты трижды записывал про X — задача Y так и висит. Что мешает?"
- "Цель Z стоит 3 недели. В чём реальный блок?"

Плохие вопросы (шаблонные, без данных):
- "Что было хорошо на этой неделе?"
- "Какие твои успехи?"

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Start with 🤔 <b>Рефлексия за неделю</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Be concise - max 2000 chars"""

    status_msg = await bot.send_message(chat_id, "⏳ Готовлю вопросы для рефлексии...")

    runner = get_runner()
    result = await asyncio.to_thread(
        runner.run, prompt, "Reflection questions",
    )

    formatted = result.get("report", result.get("error", "❌ Ошибка генерации"))
    kb = _reply_keyboard()
    try:
        await status_msg.edit_text(formatted, reply_markup=kb)
    except Exception:
        await status_msg.edit_text(formatted, parse_mode=None, reply_markup=kb)


# ── Scheduled job ─────────────────────────────────────────────────────


async def scheduled_reflection(bot: Bot, chat_id: int) -> None:
    """Called by scheduler every Friday at 20:00."""
    logger.info("Scheduled reflection questions starting")
    await _generate_and_send_reflection(bot, chat_id)


# ── Callback handlers ─────────────────────────────────────────────────


@router.callback_query(F.data == "reflection_reply")
async def handle_reflection_reply(callback: CallbackQuery, state: FSMContext) -> None:
    """Start reflection response FSM."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)
    await state.set_state(ReflectionStates.waiting_response)
    await state.set_data({"started_at": datetime.now(_TZ).isoformat()})

    await msg.answer(
        "💬 <b>Твои размышления:</b>\n\n"
        "Напиши или надиктуй ответ. Он сохранится в vault."
    )


@router.callback_query(F.data == "reflection_skip")
async def handle_reflection_skip(callback: CallbackQuery) -> None:
    """Skip reflection."""
    await callback.answer("Пропущено")
    msg = callback.message
    if msg and not isinstance(msg, InaccessibleMessage):
        await msg.edit_reply_markup(reply_markup=None)


# ── FSM response handler ──────────────────────────────────────────────


@router.message(ReflectionStates.waiting_response)
async def handle_reflection_input(
    message: Message, bot: Bot, state: FSMContext
) -> None:
    """Save reflection response to vault."""
    if message.text and message.text.startswith("/"):
        await state.clear()
        return

    response_text: str | None = None

    if message.voice:
        await message.chat.do(action="typing")
        response_text = await transcribe_voice(bot, message)
        if not response_text:
            return
        await message.answer(f"🎤 <i>{html_escape(response_text)}</i>")
    elif message.text:
        response_text = message.text
    else:
        await message.answer("Отправь текст или голосовое сообщение")
        return

    await state.clear()

    settings = get_settings()
    today = date.today().isoformat()
    reflections_dir = settings.vault_path / "thoughts" / "reflections"
    reflections_dir.mkdir(parents=True, exist_ok=True)

    filename = reflections_dir / f"{today}-reflection.md"

    content = f"""---
date: {today}
type: reflection
---

# Рефлексия {today}

{response_text}
"""

    try:
        filename.write_text(content, encoding="utf-8")
        await message.answer(
            f"✅ Рефлексия сохранена: <code>{filename.name}</code>"
        )
    except OSError as e:
        logger.error("Failed to save reflection: %s", e)
        await message.answer(f"❌ Не удалось сохранить: {e}")
