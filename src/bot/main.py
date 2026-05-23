"""Entrypoint Telegram-бота: dispatcher с Redis FSM, middleware, routers.

Запуск: `python -m src.bot.main` (или `uv run python -m src.bot.main`).
Handler'ы пока пустые — реальные команды добавляются в TASK-011 — TASK-016.
"""

from __future__ import annotations

import asyncio
import contextlib

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from src.shared.config import get_settings
from src.shared.external import get_registry_client
from src.shared.logging import configure_logging, get_logger

from .middlewares import LoggingMiddleware, SessionMiddleware, UserMiddleware
from .routers import all_routers

__all__ = ["build_dispatcher", "main"]


logger = get_logger(__name__)


def build_dispatcher() -> tuple[Bot, Dispatcher]:
    """Чистая сборка `Bot` + `Dispatcher` без запуска polling.

    Выделена отдельно от `main()`-loop, чтобы smoke-тест мог конструировать
    dispatcher без рантайма Telegram-сети. Использует `get_settings()` (не
    module-level `settings`), чтобы тесты с `cache_clear` + `monkeypatch.setenv`
    видели свежий конфиг.
    """
    s = get_settings()
    bot = Bot(
        token=s.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = RedisStorage.from_url(str(s.redis_url))
    dp = Dispatcher(storage=storage)

    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(SessionMiddleware())
    dp.update.middleware(UserMiddleware())

    # workflow-data: handler принимает `registry` как параметр, aiogram инжектит.
    dp["registry"] = get_registry_client()

    dp.include_routers(*all_routers)

    return bot, dp


async def main() -> None:
    s = get_settings()
    configure_logging(s.log_level, s.log_format)
    logger.info("bot.startup", log_format=s.log_format)

    bot, dp = build_dispatcher()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        # HttpExternalUserRegistryClient имеет .close(); Mock — нет.
        closer = getattr(dp["registry"], "close", None)
        if callable(closer):
            await closer()
        await bot.session.close()
        logger.info("bot.shutdown")


if __name__ == "__main__":  # pragma: no cover
    # Лог о shutdown уже делает finally в main(); здесь — тихий выход.
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())
