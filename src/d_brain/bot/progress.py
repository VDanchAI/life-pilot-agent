"""Async progress-polling utility for long-running tasks."""

import asyncio
from collections.abc import Callable
from typing import Any

from aiogram.types import Message


async def run_with_progress[T](
    fn: Callable[..., T],
    status_msg: Message,
    label: str,
    *args: Any,
) -> T:
    """Run a blocking function in a thread with periodic status updates.

    Args:
        fn: Synchronous callable to execute.
        status_msg: Telegram message to edit with progress.
        label: Status text prefix (e.g. "⏳ Processing...").
        *args: Positional arguments forwarded to *fn*.

    Returns:
        The return value of *fn*.
    """
    task = asyncio.create_task(asyncio.to_thread(fn, *args))

    elapsed = 0
    while not task.done():
        await asyncio.sleep(30)
        elapsed += 30
        if not task.done():
            try:
                await status_msg.edit_text(
                    f"{label} ({elapsed // 60}m {elapsed % 60}s)"
                )
            except Exception:
                pass  # Ignore Telegram edit errors

    return await task
