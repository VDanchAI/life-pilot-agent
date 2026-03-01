"""Weekly digest command handler."""

import asyncio
import logging
from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from d_brain.bot.components.task_keyboard import create_task_keyboard
from d_brain.bot.progress import BusyError, run_with_progress
from d_brain.bot.utils import send_formatted_report
from d_brain.services.factory import get_git, get_processor, get_todoist

router = Router(name="weekly")
logger = logging.getLogger(__name__)


@router.message(Command("weekly"))
async def cmd_weekly(message: Message) -> None:
    """Handle /weekly command - generate weekly digest."""
    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info("Weekly digest triggered by user %s", user_id)

    status_msg = await message.answer("⏳ Генерирую недельный дайджест...")

    processor = get_processor()
    git = get_git()

    try:
        report = await run_with_progress(
            processor.generate_weekly, status_msg,
            "⏳ Генерирую дайджест...",
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        return

    # Commit any changes (weekly goal updates, etc)
    if "error" not in report:
        ok, reason = await asyncio.to_thread(
            git.commit_and_push, "chore: weekly digest",
        )
        if not ok:
            report.setdefault("warnings", []).append(f"Vault not synced: {reason[:80]}")

    await send_formatted_report(status_msg, report)

    # ── Send per-task keyboards (ТЗ 1.1) ──────────────────────────────
    if "error" in report:
        return

    todoist = get_todoist()
    if not todoist:
        return

    try:
        tasks = await asyncio.to_thread(todoist.fetch_active_tasks)
    except Exception as e:
        logger.warning("Failed to fetch Todoist tasks for weekly: %s", e)
        return

    if not tasks:
        return

    # Filter: tasks due within the next 7 days or overdue
    today = date.today()
    cutoff = (today + timedelta(days=7)).isoformat()
    today_str = today.isoformat()

    relevant = [
        t for t in tasks
        if t.get("due") and t["due"].get("date", "") <= cutoff
    ]

    if not relevant:
        return

    await message.answer(
        f"📋 <b>Задачи к обзору ({len(relevant)}):</b>\n"
        "Выбери действие для каждой задачи:"
    )

    for task in relevant:
        task_id = str(task.get("id", ""))
        content = task.get("content", "Без названия")
        due_date = task.get("due", {}).get("date", "")
        overdue = due_date < today_str if due_date else False

        prefix = "⚠️ " if overdue else "📌 "
        text = f"{prefix}{content}"
        if due_date:
            text += f"\n<i>Срок: {due_date}</i>"

        await message.answer(
            text,
            reply_markup=create_task_keyboard(task_id, "weekly"),
        )
