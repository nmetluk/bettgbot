"""Единая настройка structlog для бота, админки и фоновых задач.

`configure_logging(level, format)` инициализирует структурный логгер один раз
для процесса (повторный вызов — идемпотентен: сбрасывает handlers root-logger'а).
`get_logger(name)` — тонкая обёртка над `structlog.get_logger`, удобная для
импорта в модулях: `logger = get_logger(__name__)`.

Конвенция использования: `logger.info("event_name", key=value, ...)` — события,
не f-строки. См. `docs/08-conventions.md`.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import structlog
from structlog.stdlib import BoundLogger

__all__ = ["configure_logging", "get_logger"]


_SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]


def _get_renderer(format: Literal["json", "console"]) -> Any:
    """Возвращает renderer в зависимости от формата."""
    if format == "json":
        return structlog.processors.JSONRenderer()
    return structlog.dev.ConsoleRenderer(colors=True)


def configure_logging(level: str, format: Literal["json", "console"]) -> None:
    """Конфигурирует structlog + перенаправляет stdlib `logging` в ту же трубу.

    Идемпотентно: сбрасывает все handlers root-logger'а перед добавлением нового,
    чтобы повторный вызов в тестах не плодил дублирующие строки лога.
    """
    renderer = _get_renderer(format)

    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=_SHARED_PROCESSORS,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str | None = None) -> BoundLogger:
    """Возвращает structlog-логгер. Аналог `structlog.get_logger(__name__)`."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
