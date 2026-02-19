"""Monthly report handler — /monthly command + scheduled generation (ТЗ 3)."""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytz
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from d_brain.bot.components.task_keyboard import create_task_keyboard
from d_brain.config import get_settings
from d_brain.services.factory import get_runner, get_todoist
from d_brain.services.vault_search import search_vault

router = Router(name="monthly")
logger = logging.getLogger(__name__)

_TZ = pytz.timezone("Europe/Kyiv")


# ── Monthly flag helpers ──────────────────────────────────────────────


def _read_monthly_flag(vault_path: Path) -> dict[str, Any]:
    flag_path = vault_path / ".monthly_flag"
    if flag_path.exists():
        try:
            result: dict[str, Any] = json.loads(flag_path.read_text())
            return result
        except Exception:
            pass
    return {"processed": False}


def _write_monthly_flag(vault_path: Path, data: dict[str, Any]) -> None:
    flag_path = vault_path / ".monthly_flag"
    flag_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _reset_monthly_flag(vault_path: Path) -> None:
    _write_monthly_flag(vault_path, {"processed": False, "report_message_id": None})


# ── Data collection ───────────────────────────────────────────────────


def _collect_monthly_context(vault_path: Path, todoist_api_key: str) -> str:
    """Collect summaries, goals, and vault search results for monthly prompt."""
    context_parts: list[str] = []

    # Last 4 weeks of summaries
    summaries_dir = vault_path / "summaries"
    if summaries_dir.exists():
        cutoff = date.today() - timedelta(days=28)
        files = sorted(summaries_dir.glob("*.md"), reverse=True)
        week_summaries = []
        for f in files:
            try:
                if f.stat().st_mtime >= cutoff.toordinal() * 86400:
                    week_summaries.append(f"### {f.stem}\n{f.read_text()[:2000]}")
            except Exception:
                pass
        if week_summaries:
            joined = "\n\n".join(week_summaries[:4])
            context_parts.append(f"## Итоги недель (последние 4):\n{joined}")

    # Yearly goal
    yearly_goal = vault_path / "goals" / "1-yearly-2026.md"
    if yearly_goal.exists():
        context_parts.append(f"## Годовые цели:\n{yearly_goal.read_text()[:1500]}")

    # Monthly goal keywords for vault search
    monthly_goal_file = vault_path / "goals" / "2-monthly.md"
    keywords: list[str] = []
    if monthly_goal_file.exists():
        goal_text = monthly_goal_file.read_text()
        context_parts.append(f"## Месячные цели:\n{goal_text[:1000]}")
        # Extract a few keywords from goal text (first meaningful words)
        words = [w.strip(".,!?:;") for w in goal_text.split() if len(w) > 4]
        keywords = list(dict.fromkeys(words))[:5]  # unique, max 5

    # Vault search by goal keywords
    if keywords:
        search_results = search_vault(
            keywords, limit=3, max_chars=600, vault_path=vault_path
        )
        if search_results:
            parts = []
            for r in search_results:
                parts.append(f"- [{r['date']} / {r['category']}]: {r['content'][:300]}")
            context_parts.append("## Релевантные записи из vault:\n" + "\n".join(parts))

    return "\n\n".join(context_parts)


# ── Core generation ───────────────────────────────────────────────────


async def _generate_and_send_monthly(bot: Bot, chat_id: int) -> None:
    """Generate and send the monthly report to the specified chat."""
    settings = get_settings()
    runner = get_runner()

    now = datetime.now(_TZ)
    last_month = now.replace(day=1) - timedelta(days=1)
    month_name = last_month.strftime("%B %Y")

    context = await asyncio.to_thread(
        _collect_monthly_context, settings.vault_path, settings.todoist_api_key
    )

    prompt = f"""Сегодня {now.date()}. Сгенерируй месячный отчёт за {month_name}.

КОНТЕКСТ:
{context}

ПЕРВЫМ ДЕЛОМ: вызови mcp__todoist__user-info чтобы убедиться что MCP работает.

WORKFLOW:
1. Используй собранный контекст + Todoist completed tasks за прошлый месяц
2. Сводка ключевых достижений и уроков
3. Задай 3-4 стратегических вопроса — конкретных, на основе паттернов из данных
   Хорошие вопросы: "Цель X стояла 3 недели — что помешало?"
   Плохие вопросы: "Что было хорошо на этой неделе?"

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Start with 📊 <b>Месячный отчёт {month_name}</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Be concise - Telegram has 4096 char limit"""

    status_msg = await bot.send_message(chat_id, "⏳ Генерирую месячный отчёт...")

    result = await asyncio.to_thread(runner.run, prompt, "Monthly report")

    formatted = result.get("report", result.get("error", "❌ Ошибка генерации"))
    try:
        await status_msg.edit_text(formatted)
    except Exception:
        await status_msg.edit_text(formatted, parse_mode=None)

    # Save message ID in flag
    flag_data = _read_monthly_flag(settings.vault_path)
    flag_data["processed"] = False
    flag_data["report_message_id"] = status_msg.message_id
    flag_data["chat_id"] = chat_id
    _write_monthly_flag(settings.vault_path, flag_data)

    # Send per-task keyboards
    if "error" in result:
        return

    todoist = get_todoist()
    if not todoist:
        return

    try:
        tasks = await asyncio.to_thread(todoist.fetch_active_tasks)
    except Exception as e:
        logger.warning("Failed to fetch tasks for monthly: %s", e)
        return

    overdue = [
        t for t in tasks
        if t.get("due") and t["due"].get("date", "") <= now.date().isoformat()
    ]

    if overdue:
        await bot.send_message(
            chat_id,
            f"📋 <b>Невыполненные задачи ({len(overdue)}):</b>",
        )
        for task in overdue:
            task_id = str(task.get("id", ""))
            content = task.get("content", "Без названия")
            due = task.get("due", {}).get("date", "")
            text = f"📌 {content}"
            if due:
                text += f"\n<i>Срок: {due}</i>"
            await bot.send_message(
                chat_id,
                text,
                reply_markup=create_task_keyboard(task_id, "monthly"),
            )


# ── /monthly command ──────────────────────────────────────────────────


@router.message(Command("monthly"))
async def cmd_monthly(message: Message) -> None:
    """Handle /monthly command — generate monthly report manually."""
    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info("Monthly report triggered by user %s", user_id)

    if message.bot is None:
        return

    settings = get_settings()
    # Reset flag on manual trigger
    _reset_monthly_flag(settings.vault_path)

    await _generate_and_send_monthly(message.bot, message.chat.id)


# ── Scheduled job functions ───────────────────────────────────────────


async def scheduled_monthly_report(bot: Bot, chat_id: int) -> None:
    """Called by scheduler on 1st of each month."""
    logger.info("Scheduled monthly report starting")
    settings = get_settings()
    _reset_monthly_flag(settings.vault_path)
    await _generate_and_send_monthly(bot, chat_id)


async def scheduled_monthly_reminder(bot: Bot, chat_id: int) -> None:
    """Called by scheduler on 2nd and 3rd — remind if not processed."""
    settings = get_settings()
    flag = _read_monthly_flag(settings.vault_path)

    if flag.get("processed", True):
        return

    text = "📋 У тебя необработанный monthly report"

    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error("Failed to send monthly reminder: %s", e)
