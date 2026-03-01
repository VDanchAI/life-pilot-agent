"""Async progress-polling utility for long-running tasks."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from aiogram.types import Message

logger = logging.getLogger(__name__)

_claude_lock = asyncio.Lock()
_queue_size = 0


class BusyError(Exception):
    """Raised when Claude is already processing a request."""


async def run_with_progress[T](
    fn: Callable[..., T],
    status_msg: Message,
    label: str,
    *args: Any,
) -> T:
    """Run a blocking function in a thread with periodic status updates.

    Only one Claude subprocess runs at a time. If busy, waits up to 5 min
    in a queue (max 2 waiting). Beyond that — rejects immediately.

    Args:
        fn: Synchronous callable to execute.
        status_msg: Telegram message to edit with progress.
        label: Status text prefix (e.g. "⏳ Processing...").
        *args: Positional arguments forwarded to *fn*.

    Returns:
        The return value of *fn*.

    Raises:
        BusyError: If the queue is full (>2 waiting).
    """
    global _queue_size  # noqa: PLW0603

    if _claude_lock.locked() and _queue_size >= 2:
        raise BusyError(
            "🚫 Claude занят и очередь полна. Попробуй через пару минут."
        )

    if _claude_lock.locked():
        _queue_size += 1
        position = _queue_size
        try:
            await status_msg.edit_text(
                f"⏳ Claude занят, ты #{position} в очереди..."
            )
        except Exception:
            pass
        try:
            acquired = await asyncio.wait_for(
                _claude_lock.acquire(), timeout=300,
            )
            if not acquired:
                raise BusyError("🚫 Не дождался очереди.")
        except TimeoutError:
            raise BusyError(
                "🚫 Слишком долгое ожидание в очереди. Попробуй позже."
            ) from None
        finally:
            _queue_size -= 1
    else:
        await _claude_lock.acquire()

    try:
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
                    pass

        return await task
    finally:
        _claude_lock.release()
