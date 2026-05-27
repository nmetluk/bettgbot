"""Observability интеграции: Sentry для error tracking.

Фабрика `init_sentry()` инициализирует Sentry SDK с конфигом из Settings.
Для бота и ад acres используются разные интеграции, но общие настройки.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import SecretStr

from .config import Settings

__all__ = ["init_sentry"]


def init_sentry(
    *,
    dsn: SecretStr | None,
    environment: str,
    service: Literal["bot", "admin"],
    traces_sample_rate: float = 0.1,
) -> None:
    """Инициализирует Sentry SDK.

    Args:
        dsn: Sentry DSN (если None — Sentry отключён, no-op).
        environment: "dev" | "staging" | "prod".
        service: "bot" для Telegram-бота, "admin" для FastAPI админки.
        traces_sample_rate: Процент транзакций для perf monitoring (0.0-1.0).
    """
    dsn_value = dsn.get_secret_value() if dsn else None
    if not dsn_value:
        # Sentry отключён — не делаем ничего.
        return

    import sentry_sdk

    # PII-filtering: удаляем phone, first_name из событий
    def _strip_pii(event: dict, hint: dict | None) -> dict | None:
        """Sentry before_send hook: вырезаем PII."""
        if "user" in event and isinstance(event["user"], dict):
            # Удаляем PII поля, но оставляем id для группировки
            event["user"].pop("phone", None)
            event["user"].pop("first_name", None)
            event["user"].pop("last_name", None)
            # tg_username оставляем — не PII в контексте бота
        return event

    integrations: list[sentry_sdk.integrations.Integration] = []

    if service == "bot":
        # Для бота: structlog интеграция (breadcrumbs) + manual tags
        from sentry_sdk.integrations.logging import LoggingIntegration

        integrations.append(
            LoggingIntegration(
                level=logging.INFO,  # INFO как breadcrumbs
                event_level=logging.ERROR,  # ERROR как event
            )
        )
    elif service == "admin":
        # Для админки: FastAPI + Starlette
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        integrations.extend([FastApiIntegration(), StarletteIntegration()])

    sentry_sdk.init(
        dsn=dsn_value,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=integrations,
        before_send=_strip_pii,
        # Отключаем встроенный Sentry logging (мы используем structlog)
        send_default_pii=False,  # Не отправлять IP, user-agent и т.п.
    )

    # Тегируем события сервисом
    sentry_sdk.set_tag("service", service)


def _is_sentry_active() -> bool:
    """Проверяет, инициализирован ли Sentry (для тестов)."""
    import sentry_sdk

    return sentry_sdk.Hub.current.client is not None
