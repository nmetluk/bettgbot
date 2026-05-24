"""Доменные исключения сервисного слоя.

Сервисы поднимают эти исключения — handler ловит и форматирует ответ.
В моделях и репозиториях этих исключений нет: они работают только с
ORM/SQLAlchemy-ошибками либо возвращают `None`.
"""

from __future__ import annotations

from typing import Literal

__all__ = [
    "AdminInactiveError",
    "AdminInvalidCredentialsError",
    "CategoryHasEventsError",
    "CategoryNotFoundError",
    "CategorySlugConflictError",
    "DomainError",
    "EventAlreadyHasResultError",
    "EventNotEnoughOutcomesError",
    "EventNotFoundError",
    "EventNotPredictableError",
    "InvalidReminderOffsetsError",
    "InvalidReminderOffsetsReason",
    "OutcomeInUseError",
    "OutcomeNotForEventError",
    "OutcomeNotFoundError",
    "PredictionDeadlinePassedError",
    "RegistryUnavailableError",
    "UserBlockedError",
    "UserNotAllowed",
]


InvalidReminderOffsetsReason = Literal["too_many", "duplicate", "below_minimum"]


class DomainError(Exception):
    """Корень иерархии доменных исключений."""


# --- Регистрация / пользователь ---


class UserNotAllowed(DomainError):
    """Телефон не найден или заблокирован во внешнем реестре пользователей."""

    def __init__(self, message: str = "user not allowed", *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


class UserBlockedError(DomainError):
    """Наш `User.is_blocked = true` — действие пользователю запрещено."""


class RegistryUnavailableError(DomainError):
    """Внешний реестр недоступен / ошибка сети / исчерпан ретрай.

    Сервис ловит `ExternalApiError` и оборачивает в этот тип, чтобы handler
    работал только с доменными классами. Исходное в `__cause__`.
    """


# --- Прогнозы ---


class PredictionDeadlinePassedError(DomainError):
    """Попытка сделать или изменить прогноз после `predictions_close_at`."""


class EventNotPredictableError(DomainError):
    """Событие не доступно для прогнозов: не существует / не опубликовано / архивно."""

    def __init__(
        self,
        message: str = "event not predictable",
        *,
        reason: Literal["not_found", "not_published", "archived"],
    ) -> None:
        super().__init__(message)
        self.reason = reason


class OutcomeNotForEventError(DomainError):
    """`outcome_id` не принадлежит указанному `event_id`."""


# --- События (админ) ---


class EventNotEnoughOutcomesError(DomainError):
    """Попытка опубликовать событие с менее чем 2 связанными `Outcome`."""


class EventAlreadyHasResultError(DomainError):
    """Повторная фиксация итога: `result_outcome_id` уже задан."""


class EventNotFoundError(DomainError):
    """Событие не найдено по id."""


class OutcomeNotFoundError(DomainError):
    """Исход не найден по id."""


class OutcomeInUseError(DomainError):
    """Удаление исхода невозможно — на него есть прогнозы (RESTRICT FK)."""


# --- Категории (админ) ---


class CategorySlugConflictError(DomainError):
    """Категория с таким `slug` уже существует."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"category slug {slug!r} already exists")
        self.slug = slug


class CategoryHasEventsError(DomainError):
    """Удаление категории невозможно — есть связанные события (FK RESTRICT)."""

    def __init__(self, category_id: int) -> None:
        super().__init__(f"category {category_id} has events; cannot delete")
        self.category_id = category_id


class CategoryNotFoundError(DomainError):
    """Категория не найдена по id."""

    def __init__(self, category_id: int) -> None:
        super().__init__(f"category {category_id} not found")
        self.category_id = category_id


# --- Админ-аутентификация ---


class AdminInvalidCredentialsError(DomainError):
    """Login не найден или password не подходит. Generic — не раскрываем причину
    (анти-enumeration). Handler рендерит «неверный логин или пароль»."""


class AdminInactiveError(DomainError):
    """Учётка админа найдена, password верный, но `is_active = false`."""

    def __init__(self, *, admin_id: int) -> None:
        super().__init__(f"admin {admin_id} is inactive")
        self.admin_id = admin_id


# --- Напоминания ---


class InvalidReminderOffsetsError(DomainError):
    """Невалидный список offsets: > 5 / < 5 минут / дубликаты.

    `reason` — типизированный код причины (`too_many` / `duplicate` /
    `below_minimum`); handler ловит по нему, а не по подстроке `str(exc)`.
    """

    def __init__(
        self,
        message: str = "invalid reminder offsets",
        *,
        reason: InvalidReminderOffsetsReason,
    ) -> None:
        super().__init__(message)
        self.reason: InvalidReminderOffsetsReason = reason
