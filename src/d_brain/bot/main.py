"""Telegram bot initialization and polling."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, Update

from d_brain.config import Settings

logger = logging.getLogger(__name__)


def create_bot(settings: Settings) -> Bot:
    """Create and configure the Telegram bot."""
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher with routers."""
    from d_brain.bot.handlers import (
        buttons,
        coach,
        commands,
        do,
        forward,
        grow,
        monthly,
        monthly_callbacks,
        photo,
        process,
        recall,
        reflection,
        text,
        vault_tools,
        voice,
        weekly,
        weekly_callbacks,
    )

    # Use memory storage for FSM (required for /do command state)
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers - ORDER MATTERS
    dp.include_router(commands.router)
    dp.include_router(process.router)
    dp.include_router(weekly.router)
    dp.include_router(weekly_callbacks.router)
    dp.include_router(monthly.router)
    dp.include_router(monthly_callbacks.router)
    dp.include_router(grow.router)  # GROW FSM — after monthly_callbacks
    dp.include_router(reflection.router)
    dp.include_router(recall.router)
    dp.include_router(do.router)  # Before voice/text to catch FSM state
    dp.include_router(coach.router)  # Coach Mode FSM — before buttons/text
    dp.include_router(vault_tools.router)  # /health, /memory, /creative
    dp.include_router(buttons.router)  # Reply keyboard buttons
    dp.include_router(voice.router)
    dp.include_router(photo.router)
    dp.include_router(forward.router)
    dp.include_router(text.router)  # Must be last (catch-all for text)
    return dp


MiddlewareHandler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]
MiddlewareType = Callable[
    [MiddlewareHandler, TelegramObject, dict[str, Any]], Awaitable[Any]
]


def create_auth_middleware(settings: Settings) -> MiddlewareType:
    """Create middleware to check user authorization."""

    async def auth_middleware(
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # If explicitly allowed all users, just bypass check
        if settings.allow_all_users:
            return await handler(event, data)

        user = None
        if isinstance(event, Update):
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user

        # If no users allowed and not allow_all_users -> deny everyone
        if not settings.allowed_user_ids:
            logger.warning(
                "Access denied: no allowed_user_ids configured"
                " and allow_all_users is False"
            )
            return None

        # Check if user is in allowed list
        if user and user.id not in settings.allowed_user_ids:
            logger.warning("Unauthorized access attempt from user %s", user.id)
            return None

        return await handler(event, data)

    return auth_middleware


def _get_first_allowed_chat(settings: Settings) -> int | None:
    """Return first allowed user ID as chat ID for scheduled messages."""
    if settings.allowed_user_ids:
        return settings.allowed_user_ids[0]
    return None


def create_scheduler(bot: Bot, settings: Settings):  # type: ignore[no-untyped-def]
    """Create APScheduler with monthly, GROW weekly/monthly jobs."""
    import pytz
    from apscheduler.schedulers.asyncio import (  # type: ignore[import-untyped]
        AsyncIOScheduler,
    )

    from d_brain.bot.handlers.grow_scheduler import (
        scheduled_grow_monthly,
        scheduled_grow_quarterly,
        scheduled_grow_weekly,
        scheduled_grow_yearly_end,
        scheduled_grow_yearly_start,
    )
    from d_brain.bot.handlers.monthly import (
        scheduled_monthly_reminder,
        scheduled_monthly_report,
    )

    tz = pytz.timezone("Europe/Kyiv")
    scheduler = AsyncIOScheduler(timezone=tz)

    chat_id = _get_first_allowed_chat(settings)
    if chat_id is None:
        logger.warning("No allowed_user_ids configured — scheduled jobs disabled")
        return scheduler

    # Monthly report — 1st of each month at 20:30 (before GROW at 21:00)
    scheduler.add_job(
        scheduled_monthly_report,
        trigger="cron",
        day=1,
        hour=20,
        minute=30,
        kwargs={"bot": bot, "chat_id": chat_id},
        id="monthly_report",
        replace_existing=True,
    )

    # Monthly reminders — 2nd and 3rd at 21:00 if not processed
    scheduler.add_job(
        scheduled_monthly_reminder,
        trigger="cron",
        day="2-3",
        hour=21,
        minute=0,
        kwargs={"bot": bot, "chat_id": chat_id},
        id="monthly_reminder",
        replace_existing=True,
    )

    # GROW weekly — Saturday, Sunday, Monday at 21:00
    scheduler.add_job(
        scheduled_grow_weekly,
        trigger="cron",
        day_of_week="sat,sun,mon",
        hour=21,
        minute=0,
        kwargs={"bot": bot, "chat_id": chat_id},
        id="grow_weekly",
        replace_existing=True,
    )

    # GROW monthly — 1st, 2nd, 3rd of each month at 21:00
    scheduler.add_job(
        scheduled_grow_monthly,
        trigger="cron",
        day="1-3",
        hour=21,
        minute=0,
        kwargs={"bot": bot, "chat_id": chat_id},
        id="grow_monthly",
        replace_existing=True,
    )

    # GROW quarterly — Apr/Jul/Oct 1-3 at 21:00
    scheduler.add_job(
        scheduled_grow_quarterly,
        trigger="cron",
        month="4,7,10",
        day="1-3",
        hour=21,
        minute=0,
        kwargs={"bot": bot, "chat_id": chat_id},
        id="grow_quarterly",
        replace_existing=True,
    )

    # GROW yearly END — Dec 20, 23, 26 at 21:00
    scheduler.add_job(
        scheduled_grow_yearly_end,
        trigger="cron",
        month=12,
        day="20,23,26",
        hour=21,
        minute=0,
        kwargs={"bot": bot, "chat_id": chat_id},
        id="grow_yearly_end",
        replace_existing=True,
    )

    # GROW yearly START — Jan 5, 7, 9 at 21:00
    scheduler.add_job(
        scheduled_grow_yearly_start,
        trigger="cron",
        month=1,
        day="5,7,9",
        hour=21,
        minute=0,
        kwargs={"bot": bot, "chat_id": chat_id},
        id="grow_yearly_start",
        replace_existing=True,
    )

    logger.info(
        "Scheduler configured: monthly (1st 20:30), "
        "reminders (2-3rd 21:00), "
        "GROW weekly/monthly/quarterly/yearly"
    )
    return scheduler


async def run_bot(settings: Settings) -> None:
    """Run the bot with polling."""
    bot = create_bot(settings)
    dp = create_dispatcher()

    # Always add auth middleware for security (it handles allow_all_users internally)
    dp.update.middleware(create_auth_middleware(settings))

    # Start scheduler
    scheduler = create_scheduler(bot, settings)
    scheduler.start()

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
