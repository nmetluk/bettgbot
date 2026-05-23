"""Интерфейс и общие типы внешнего реестра пользователей.

Бизнес-сервисы зависят только от `ExternalUserRegistryClient` (Protocol);
конкретные реализации — `MockExternalUserRegistryClient`, `HttpExternalUserRegistryClient` —
выбираются фабрикой `get_registry_client()` в `__init__.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "ExternalApiError",
    "ExternalUserRegistryClient",
    "VerificationResult",
]


@dataclass(frozen=True)
class VerificationResult:
    """Результат проверки телефона по реестру."""

    is_allowed: bool
    external_user_id: str | None = None
    display_name: str | None = None
    reason: str | None = None  # "not_found" / "blocked" / прочее для is_allowed=False


@runtime_checkable
class ExternalUserRegistryClient(Protocol):
    """Контракт клиента внешнего реестра пользователей."""

    async def verify(self, phone: str) -> VerificationResult: ...


class ExternalApiError(Exception):
    """Сетевая ошибка / 5xx / исчерпан ретрай / 401 / прочее, не дающее ответа.

    Бизнес-логика бота показывает пользователю generic-ошибку, не пробрасывая детали.
    """

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause
